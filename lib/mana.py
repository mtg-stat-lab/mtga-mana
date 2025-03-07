from __future__ import annotations

import random
import itertools
import re
from collections import Counter
import pandas as pd

CANONICAL_COLORS: list[str] = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES: list[str] = ['grey', 'blue', 'black', 'red', 'green']


def parse_cost_string(cost_str: str) -> tuple[int, Counter[str]]:
    """
    Parse a cost string such as '3*U2W' into (uncolored, color_costs).
    Example:
      '3*U2W' -> (3, {'U':1, 'W':2})

    The recognized tokens are digits plus '*', or digits plus one of W/U/B/R/G.
    """
    pattern = r'(\d*\*|\d*[WUBRG])'
    matches = re.findall(pattern, cost_str)
    uncolored = 0
    color_costs: Counter[str] = Counter()
    for m in matches:
        digits_str = ''
        for ch in m:
            if ch.isdigit():
                digits_str += ch
            else:
                break
        num = int(digits_str) if digits_str else 1
        symbol = m[len(digits_str):]

        if symbol == '*':
            uncolored += num
        else:
            color_costs[symbol] += num

    return uncolored, color_costs


class Card:
    """
    Represents any card: 
      - Lands (leading '>'), e.g. '>BW'
      - Mana-producing spells ('>' in the middle), e.g. '3*>WUBRG'
      - Normal spells (no '>'), e.g. 'BW'.

    Attributes:
        card_str: Original string representation.
        is_land: True if it's a land (leading '>').
        can_produce_mana: True if it's a land or a mana-producing spell.
        cost_uncolored: Generic mana required.
        cost_colors: Counts of colored mana required.
        producible_colors: Which color(s) this card can produce if it's a land or mana-producing spell.
    """

    def __init__(self, card_str: str) -> None:
        self.card_str: str = card_str
        self.is_land: bool = card_str.startswith('>')

        self.can_produce_mana: bool = False
        self.cost_uncolored: int = 0
        self.cost_colors: Counter[str] = Counter()
        self.producible_colors: set[str] = set()

        if self.is_land:
            # For lands, everything after '>' is the set of producible colors
            produce_part = card_str[1:]
            self.can_produce_mana = True
            self.producible_colors = set(produce_part)
        else:
            # Possibly a spell that can produce mana if it has '>'
            if '>' in card_str:
                cost_part, produce_part = card_str.split('>', 1)
                self.can_produce_mana = True
                self.producible_colors = set(produce_part)
            else:
                cost_part = card_str

            uncolored, color_costs = parse_cost_string(cost_part)
            self.cost_uncolored = uncolored
            self.cost_colors = color_costs

    def __repr__(self) -> str:
        return f"Card({self.card_str})"


class Deck:
    """
    Deck of cards, typically 40 total. Some positions may be None if the deck_dict
    has fewer unique cards than total_size.
    """

    def __init__(self, cards: list[Card], total_size: int = 40) -> None:
        self.cards: list[Card | None] = cards
        self.total_size: int = total_size

        leftover = total_size - len(cards)
        if leftover > 0:
            # Fill with None if deck is smaller than the total
            self.cards += [None] * leftover

    def shuffle(self) -> None:
        """Shuffle the deck in-place."""
        random.shuffle(self.cards)

    def draw_top_n(self, n: int) -> list[Card | None]:
        """
        Return the first n cards (which can include None if the deck has filler).
        This does not 'remove' them from the deck internally; for a snapshot simulation.
        """
        return self.cards[:n]

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Deck(size={self.total_size}, actual_list_len={len(self.cards)})"


def build_deck_from_dict(deck_dict: dict[str, int], total_deck_size: int = 40) -> Deck:
    """
    Build a Deck from a single dictionary mapping card_str -> quantity.
    Example:
      {
        "BW": 2,
        ">U": 4,
        "3*>WUBRG": 1
      }
    """
    card_objs: list[Card] = []
    for cstr, qty in deck_dict.items():
        for _ in range(qty):
            card_objs.append(Card(cstr))
    return Deck(card_objs, total_deck_size)


def _all_possible_color_combinations(mana_cards: list[Card]) -> itertools.Generator[Counter[str], None, None]:
    """
    Produce a generator of Counter(...) representing each color assignment
    from the given mana_cards. Each card can produce one of its producible_colors.

    We yield results on the fly for short-circuiting in _can_cast_with_sources.
    """
    for combo in itertools.product(*(c.producible_colors for c in mana_cards)):
        yield Counter(combo)


def _can_cast_with_sources(spell: Card, sources: list[Card], lands_playable: int) -> bool:
    """
    Check if 'spell' can be cast using up to 'lands_playable' from the given 'sources'.
    Each source is assumed to produce exactly 1 mana from one of its producible colors.
    We short-circuit as soon as a valid combination is found.
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
                # Check color requirements
                if all(combo_counter[color] >= spell.cost_colors[color] for color in spell.cost_colors):
                    # Check leftover for uncolored
                    color_lands_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_lands_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False


def _count_dead_spells_expanded(
    hand: list[Card | None],
    turn: int,
    on_play: bool,
    persisted_producers: list[Card],
    persisted_castable_spells: set[Card]
) -> tuple[int, list[Card]]:
    """
    Determine how many spells are 'dead' on this turn, given:
      - The current hand (some items may be None).
      - The number of lands playable (turn-based logic).
      - A set of persisted mana producers (already cast in prior turns).
      - A set of persisted normal spells that are known castable (no re-check needed).

    Returns:
      (dead_count, newly_castable)
        * dead_count: how many spells in this hand cannot be cast
        * newly_castable: mana-producing spells discovered castable this turn

    Once a normal spell is found castable in a previous turn, we do NOT re-check it.
    For new or unconfirmed spells, we call _can_cast_with_sources.
    """
    # Example logic: on the play, you can have turn+1 lands by turn X
    lands_playable = turn + 1 if on_play else turn
    if lands_playable < 0:
        lands_playable = 0

    # Build the "available sources": old producers + any land in this hand
    available_sources = list(persisted_producers)
    for c in hand:
        if c is not None and c.is_land:
            available_sources.append(c)

    dead_count = 0
    newly_castable: list[Card] = []

    for c in hand:
        if c is None or c.is_land:
            # Land doesn't need to be cast, so never "dead"
            continue

        # If this is a normal spell we already marked as castable, skip re-check
        if (not c.can_produce_mana) and (c in persisted_castable_spells):
            # It's known castable => not dead
            continue

        # Otherwise, we see if we can cast it now
        if _can_cast_with_sources(c, available_sources, lands_playable):
            # It's castable
            if c.can_produce_mana and (not c.is_land):
                # A newly discovered mana-producer => track for subsequent turns
                newly_castable.append(c)
            else:
                # Normal spell => remember it so we skip future checks
                persisted_castable_spells.add(c)
        else:
            dead_count += 1

    return dead_count, newly_castable


def _best_single_color_to_replace(
    hand: list[Card | None],
    turn: int,
    on_play: bool,
    persisted_producers: list[Card],
    persisted_castable_spells: set[Card],
    colors_to_test: list[str] = CANONICAL_COLORS
) -> str:
    """
    Attempt to replace exactly one land in 'hand' with a single-color land, e.g. '>W',
    to see if that reduces the number of dead spells. Return the color that yields
    the greatest improvement, short-circuiting if we ever get 0 dead.

    Returns the color string ('W','U','B','R','G') or 'none' if no improvement.
    """
    base_dead, _ = _count_dead_spells_expanded(
        hand, turn, on_play, persisted_producers, persisted_castable_spells
    )
    hand_mana = [c for c in hand if (c is not None) and c.is_land]
    if not hand_mana:
        return "none"

    best_color = "none"
    best_dead_count = base_dead

    # Replace in-place, revert, short-circuit if we hit zero dead
    for color in colors_to_test:
        single_color_land = Card('>' + color)

        for original_land in hand_mana:
            idx = hand.index(original_land)
            old_land = hand[idx]
            hand[idx] = single_color_land

            new_dead, _ = _count_dead_spells_expanded(
                hand, turn, on_play, persisted_producers, persisted_castable_spells
            )
            hand[idx] = old_land  # revert

            if new_dead < best_dead_count:
                best_dead_count = new_dead
                best_color = color
                if best_dead_count == 0:
                    return best_color

    return best_color


def run_simulation(
    deck_dict: dict[str, int],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int | None = None,
    on_play: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main simulation routine. For each simulation:
      1. Build & shuffle a deck from 'deck_dict'.
      2. For turns 1..draws:
         a. Determine the current hand size (depends on play vs. draw).
         b. Draw that many cards from the top (snapshot).
         c. Count how many spells are dead. Track newly castable mana-producers.
         d. Choose the best single-color replacement land (for charts).
      3. Collect per-turn stats for "dead spells" distribution and best-color picks.

    We track:
      - persisted_mana_producers: Spells that produce mana once discovered castable
      - persisted_castable_spells: Normal spells discovered castable in earlier turns

    Returns:
      (df_summary, df_distribution)

      * df_summary has one row per turn, with "p_dead" and fraction of best-color picks
      * df_distribution has one row per turn+dead_spells, with frequency.

    Example usage:
        df_summary, df_distribution = run_simulation(deck_dict, 40, 7, 10, 100_000)
    """
    if seed is not None:
        random.seed(seed)

    dead_counts_per_turn: list[list[int]] = [[] for _ in range(draws)]
    best_color_counts: list[Counter[str]] = [Counter() for _ in range(draws)]

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        persisted_mana_producers: list[Card] = []
        persisted_castable_spells: set[Card] = set()

        for turn in range(1, draws + 1):
            if on_play:
                # On the play: Turn 1 has no draw step => hand_size = initial + (turn - 1)
                hand_size = initial_hand_size + (turn - 1)
            else:
                # On the draw: Turn 1 includes a draw => hand_size = initial + turn
                hand_size = initial_hand_size + turn

            hand = deck.draw_top_n(hand_size)

            dead_count, newly_castable = _count_dead_spells_expanded(
                hand,
                turn,
                on_play,
                persisted_mana_producers,
                persisted_castable_spells
            )
            dead_counts_per_turn[turn - 1].append(dead_count)

            # Add newly-castable mana producers for future turns
            persisted_mana_producers.extend(newly_castable)

            # Determine best color to replace a land
            best_color = _best_single_color_to_replace(
                hand,
                turn,
                on_play,
                persisted_mana_producers,
                persisted_castable_spells
            )
            best_color_counts[turn - 1][best_color] += 1

    # Build df_summary
    rows_summary: list[dict[str, float | str]] = []
    extended_colors = CANONICAL_COLORS + ["none"]

    for turn in range(1, draws + 1):
        turn_dead_list = dead_counts_per_turn[turn - 1]
        count_ge1 = sum(1 for d in turn_dead_list if d >= 1)
        p_dead = count_ge1 / len(turn_dead_list)

        total_sims = float(simulations)
        color_fracs = {
            color: best_color_counts[turn - 1][color] / total_sims
            for color in extended_colors
        }

        row = {
            "turn": turn,
            "turn_label": str(turn),
            "p_dead": p_dead,
            **{f"pct_optimal_{c}": color_fracs[c] for c in extended_colors}
        }
        rows_summary.append(row)

    df_summary = pd.DataFrame(rows_summary)

    # Build df_distribution
    distribution_rows: list[dict[str, int | float]] = []
    for turn in range(1, draws + 1):
        freq_counter = Counter(dead_counts_per_turn[turn - 1])
        for dead_val, freq in freq_counter.items():
            distribution_rows.append({
                "turn": turn,
                "turn_label": str(turn),
                "dead_spells": dead_val,
                "frequency": freq
            })

    df_distribution = pd.DataFrame(distribution_rows)

    return df_summary, df_distribution
