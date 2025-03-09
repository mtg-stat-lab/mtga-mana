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
    """
    needed_total = spell.cost_uncolored + sum(spell.cost_colors.values())
    if needed_total > lands_playable or not sources:
        return False

    max_subset_size = min(lands_playable, len(sources))
    indices = range(len(sources))

    for subset_size in range(needed_total, max_subset_size + 1):
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [sources[i] for i in subset_indices]
            for combo_counter in _all_possible_color_combinations(subset):
                combo_count = Counter(combo_counter)
                if all(combo_count[col] >= spell.cost_colors[col] for col in spell.cost_colors):
                    # We can produce enough colored pips...
                    color_lands_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_lands_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False


def _count_dead_spells_and_missing_colors(
    hand: List[Card],
    turn: int,
    on_play: bool,
    persisted_producers: List[Card],
    persisted_castable_spells: Set[Card],
):
    lands_playable = turn if not on_play else (turn + 1)
    if lands_playable < 0:
        lands_playable = 0

    available_sources = list(persisted_producers)
    # Add any lands from this hand
    available_sources.extend(c for c in hand if c and c.is_land)

    dead_count = 0
    newly_castable: List[Card] = []
    missing_color_counts = {c: 0 for c in CANONICAL_COLORS}

    for c in hand:
        if c is None or c.is_land:
            continue
        # Already counted as castable in a prior turn
        if (not c.can_produce_mana) and (c in persisted_castable_spells):
            continue

        total_cost = c.cost_uncolored + sum(c.cost_colors.values())
        if total_cost > lands_playable:
            # Not enough total mana
            dead_count += 1
            continue

        if _can_cast_with_sources(c, available_sources, lands_playable):
            if c.can_produce_mana and (not c.is_land):
                newly_castable.append(c)
            else:
                persisted_castable_spells.add(c)
        else:
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

    return dead_count, newly_castable, missing_color_counts


def run_simulation(
    deck_dict: Dict[str, Tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int = None,
    on_play: bool = True,
):
    if seed is not None:
        random.seed(seed)

    dead_counts_per_turn = [[] for _ in range(draws)]
    missing_color_tallies = [[] for _ in range(draws)]

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        persisted_mana_producers: List[Card] = []
        persisted_castable_spells: Set[Card] = set()

        for turn in range(1, draws + 1):
            hand_size = (initial_hand_size + (turn - 1)) if on_play else (initial_hand_size + turn)
            hand = deck.draw_top_n(hand_size)

            dead_count, newly_castable, missing_colors = _count_dead_spells_and_missing_colors(
                hand, turn, on_play, persisted_mana_producers, persisted_castable_spells
            )
            dead_counts_per_turn[turn - 1].append(dead_count)
            missing_color_tallies[turn - 1].append(missing_colors)
            persisted_mana_producers.extend(newly_castable)

    # Build summary DataFrame
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

    # Build distribution DataFrame
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

    return df_summary, df_distribution


def run_simulation_with_delay(
    deck_dict: Dict[str, Tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int = None,
    on_play: bool = True,
):
    """
    Records how many turns each non-land spell remains uncastable
    from the time it enters your hand.
    """
    if seed is not None:
        random.seed(seed)

    delay_records = []

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        # The "hand" is persistent across turns
        hand = []
        # Opening hand
        for _ in range(initial_hand_size):
            if deck.cards:
                card = deck.cards.pop(0)
                if card and not card.is_land:
                    card.draw_turn = 1
                hand.append(card)

        persisted_mana_producers = []

        for turn in range(1, draws + 1):
            if turn > 1 and deck.cards:
                card = deck.cards.pop(0)
                if card and not card.is_land:
                    card.draw_turn = turn
                hand.append(card)

            lands_playable = turn if not on_play else (turn + 1)

            # Attempt to cast any newly-castable spells
            available_sources = persisted_mana_producers + [c for c in hand if c and c.is_land]
            # Make a copy so we can remove from hand when cast
            for card in hand.copy():
                if not card or card.is_land:
                    continue
                if _can_cast_with_sources(card, available_sources, lands_playable):
                    # The delay is how many turns it spent in your hand
                    # from draw_turn until 'turn'
                    delay = turn - getattr(card, "draw_turn", turn)
                    delay_records.append({"card_name": card.display_name, "delay": delay})
                    if card.can_produce_mana and (not card.is_land):
                        persisted_mana_producers.append(card)
                    hand.remove(card)

    return pd.DataFrame(delay_records)
