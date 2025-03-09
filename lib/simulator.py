import itertools
import random
from collections import Counter
from typing import Dict, List, Set, Tuple

import pandas as pd

from .cost_parser import CANONICAL_COLORS
from .models import Card, Deck


def build_deck_from_dict(deck_dict: Dict[str, Tuple[str, int]], total_deck_size=40) -> Deck:
    """
    Given deck_dict: display_name -> (mana_string, quantity),
    build a Deck object (list of Cards).
    """
    cards = []
    for display_name, (mana_str, qty) in deck_dict.items():
        for _ in range(qty):
            cards.append(Card(mana_str, display_name=display_name))
    return Deck(cards, total_deck_size)


def _all_possible_color_combinations(mana_cards: List[Card]):
    """
    For a given list of mana-producing cards, yield all possible ways
    to pick exactly one color from each card that can produce mana.
    """
    return itertools.product(*(c.producible_colors for c in mana_cards))


def _can_cast_with_sources(spell: Card, sources: List[Card], lands_playable: int) -> bool:
    """
    Check if `spell` can be cast with the given `sources` within `lands_playable` usage.
    Each land (or mana-producer) can produce exactly one unit of mana per turn,
    potentially in one of several colors if it has multiple color options.
    """
    needed_total = spell.cost_uncolored + sum(spell.cost_colors.values())
    if needed_total > lands_playable or not sources:
        return False

    max_subset_size = min(lands_playable, len(sources))
    indices = range(len(sources))

    for subset_size in range(needed_total, max_subset_size + 1):
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [sources[i] for i in subset_indices]
            # Try every possible color combination for these sources:
            for combo_tuple in _all_possible_color_combinations(subset):
                combo_count = Counter(combo_tuple)
                # Do we meet each colored pip requirement?
                if all(combo_count[col] >= spell.cost_colors[col] for col in spell.cost_colors):
                    # Next, ensure leftover "generic mana" can cover uncolored cost:
                    color_pips_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_pips_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False


def run_simulation_all(
    deck_dict: Dict[str, Tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int = None,
    on_play: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    A unified simulation that does BOTH:
      1) Dead-spell counting & missing-color tallies (like run_simulation).
      2) Spell delay tracking (like run_simulation_with_delay).

    Returns:
      - df_summary: aggregated stats per turn (including p_dead and average missing colors).
      - df_distribution: distribution of "dead spells" counts per turn.
      - df_delay: rows of (card_name, delay), where delay is how many turns
                  the card spent in hand before first becoming castable.
    """
    if seed is not None:
        random.seed(seed)

    # For the distribution summary:
    dead_counts_per_turn = [[] for _ in range(draws)]
    missing_color_tallies = [[] for _ in range(draws)]

    # For the delay data: one record per card that eventually got cast
    #  i.e. once it became castable, we record (card_name, delay).
    delay_records = []

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        # The "hand" persists across turns; we'll add newly drawn cards each turn.
        hand: List[Card] = []
        # Track when each card was drawn, so we can compute delay = (turn_cast - turn_drawn).
        # We'll store the turn number in card.draw_turn = integer.

        # Draw initial hand
        for _ in range(initial_hand_size):
            if deck.cards:
                card = deck.cards.pop(0)
                if card is not None:
                    card.draw_turn = 1
                hand.append(card)

        persisted_mana_producers: List[Card] = []
        persisted_castable_spells: Set[Card] = set()  # normal spells that we've marked "castable"

        # We simulate exactly `draws` turns
        for turn in range(1, draws + 1):
            # If it's after turn 1 (or if we are on the draw on turn=1), draw your typical draw step
            if turn == 1:
                # In real Magic: If on the draw, you get a card on turn 1; if on play, you do not.
                # We'll replicate that logic:
                if not on_play:  # on the draw
                    if deck.cards:
                        card = deck.cards.pop(0)
                        if card is not None:
                            card.draw_turn = turn
                        hand.append(card)
            else:
                # Turn >=2 -> always draw 1 card
                if deck.cards:
                    card = deck.cards.pop(0)
                    if card is not None:
                        card.draw_turn = turn
                    hand.append(card)

            lands_playable = turn if not on_play else (turn + 1)
            if lands_playable < 0:
                lands_playable = 0

            # Build a list of currently available mana sources:
            available_sources = list(persisted_mana_producers) + [
                c for c in hand if c and c.is_land
            ]

            dead_count = 0
            missing_color_counts = {c: 0 for c in CANONICAL_COLORS}

            # Check each card in your hand that isn't already known to be castable:
            for c in hand:
                if c is None or c.is_land:
                    continue
                # If it's a normal (non-mana-producer) spell that's already known to be castable,
                # then it's not "dead" anymore; skip it.
                if not c.can_produce_mana and c in persisted_castable_spells:
                    continue

                # If you can produce enough mana (colored + generic) to cast it:
                total_cost = c.cost_uncolored + sum(c.cost_colors.values())
                if total_cost > lands_playable:
                    # We definitely can't cast it, not enough total mana
                    dead_count += 1
                    continue

                if _can_cast_with_sources(c, available_sources, lands_playable):
                    # Spell is castable this turn
                    delay = turn - getattr(c, "draw_turn", turn)
                    # Record the delay for this card exactly once
                    # (the first time it is castable).
                    delay_records.append({"card_name": c.display_name, "delay": delay})

                    if c.can_produce_mana and not c.is_land:
                        # e.g. an artifact creature that taps for mana
                        persisted_mana_producers.append(c)
                    else:
                        persisted_castable_spells.add(c)
                else:
                    # Spell is dead for this turn
                    dead_count += 1

                    # Tally color shortfalls
                    source_color_counts = Counter()
                    for src in available_sources:
                        for col in src.producible_colors:
                            source_color_counts[col] += 1
                    for col in c.cost_colors:
                        needed_pips = c.cost_colors[col]
                        if source_color_counts[col] < needed_pips:
                            missing_color_counts[col] += 1

            dead_counts_per_turn[turn - 1].append(dead_count)
            missing_color_tallies[turn - 1].append(missing_color_counts)

    # Build summary DataFrames
    # ---------------------------------------
    # 1) Summary of dead spells per turn + average missing color
    rows_summary = []
    for turn_idx in range(draws):
        turn_dead_list = dead_counts_per_turn[turn_idx]
        total_sims = float(len(turn_dead_list))
        count_ge1 = sum(1 for d in turn_dead_list if d >= 1)
        p_dead = count_ge1 / total_sims

        color_sums = Counter()
        for sim_dict in missing_color_tallies[turn_idx]:
            color_sums.update(sim_dict)
        avg_missing = {col: color_sums[col] / total_sims for col in CANONICAL_COLORS}

        row = {
            "turn": turn_idx + 1,
            "turn_label": str(turn_idx + 1),
            "p_dead": p_dead,
        }
        for c in CANONICAL_COLORS:
            row[f"avg_missing_{c}"] = avg_missing[c]

        rows_summary.append(row)

    df_summary = pd.DataFrame(rows_summary)

    # 2) Distribution of "dead spells" counts per turn
    distribution_rows = []
    for turn_idx in range(draws):
        freq_counter = Counter(dead_counts_per_turn[turn_idx])
        for dead_val, freq in freq_counter.items():
            distribution_rows.append(
                {
                    "turn": turn_idx + 1,
                    "turn_label": str(turn_idx + 1),
                    "dead_spells": dead_val,
                    "frequency": freq,
                }
            )
    df_distribution = pd.DataFrame(distribution_rows)

    # 3) Delay DataFrame
    # Each row = (card_name, delay).
    df_delay = pd.DataFrame(delay_records)

    return df_summary, df_distribution, df_delay
