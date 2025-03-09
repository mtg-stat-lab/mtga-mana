from __future__ import annotations

import random
import itertools
import re
from collections import Counter
import pandas as pd

from lib.deck import parse_deck_list  # ensure deck parsing is available

CANONICAL_COLORS: list[str] = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES: list[str] = ['grey', 'blue', 'black', 'red', 'green']

def parse_cost_string(cost_str: str) -> tuple[int, Counter[str]]:
    """
    Parse a cost string such as '3*U2W' into (uncolored, color_costs).
    Example:
      '3*U2W' -> (3, {'U':1, 'W':2})
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
        card_str: The mana string representation.
        display_name: The card's actual name.
        is_land: True if it's a land (leading '>').
        can_produce_mana: True if it's a land or a mana-producing spell.
        cost_uncolored: Generic mana required.
        cost_colors: Counts of colored mana required.
        producible_colors: Which color(s) this card can produce.
    """
    def __init__(self, card_str: str, display_name: str | None = None) -> None:
        self.card_str: str = card_str
        self.display_name: str = display_name if display_name is not None else card_str
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
        return f"Card({self.display_name}, {self.card_str})"

class Deck:
    """
    Deck of cards. Some positions may be None if the deck_dict
    has fewer unique cards than total_size.
    """
    def __init__(self, cards: list[Card], total_size: int = 40) -> None:
        self.cards: list[Card | None] = cards
        self.total_size: int = total_size

        leftover = total_size - len(cards)
        if leftover > 0:
            self.cards += [None] * leftover

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw_top_n(self, n: int) -> list[Card | None]:
        return self.cards[:n]

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Deck(size={self.total_size}, actual_list_len={len(self.cards)})"

def build_deck_from_dict(deck_dict: dict[str, tuple[str, int]], total_deck_size: int = 40) -> Deck:
    """
    Build a Deck from a dictionary mapping card display name -> (mana string, quantity).
    """
    card_objs: list[Card] = []
    for display_name, (mana, qty) in deck_dict.items():
        for _ in range(qty):
            card_objs.append(Card(mana, display_name=display_name))
    return Deck(card_objs, total_deck_size)

def _all_possible_color_combinations(mana_cards: list[Card]) -> itertools.Generator[Counter[str], None, None]:
    for combo in itertools.product(*(c.producible_colors for c in mana_cards)):
        yield Counter(combo)

def _can_cast_with_sources(spell: Card, sources: list[Card], lands_playable: int) -> bool:
    needed_total = spell.cost_uncolored + sum(spell.cost_colors.values())
    if needed_total > lands_playable or not sources:
        return False

    max_subset_size = min(lands_playable, len(sources))
    indices = range(len(sources))

    for subset_size in range(needed_total, max_subset_size + 1):
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [sources[i] for i in subset_indices]
            for combo_counter in _all_possible_color_combinations(subset):
                if all(combo_counter[color] >= spell.cost_colors[color] for color in spell.cost_colors):
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
    lands_playable = turn + 1 if on_play else turn
    if lands_playable < 0:
        lands_playable = 0

    available_sources = list(persisted_producers)
    for c in hand:
        if c is not None and c.is_land:
            available_sources.append(c)

    dead_count = 0
    newly_castable: list[Card] = []

    for c in hand:
        if c is None or c.is_land:
            continue

        if (not c.can_produce_mana) and (c in persisted_castable_spells):
            continue

        if _can_cast_with_sources(c, available_sources, lands_playable):
            if c.can_produce_mana and (not c.is_land):
                newly_castable.append(c)
            else:
                persisted_castable_spells.add(c)
        else:
            dead_count += 1

    return dead_count, newly_castable

def _average_spells_revived_if_replace_any_one_land(
    hand: list[Card | None],
    turn: int,
    on_play: bool,
    persisted_producers: list[Card],
    persisted_castable_spells: set[Card],
    color: str
) -> float:
    """
    For each land in 'hand', temporarily replace it with a land of `color`,
    see how many more spells become castable than with the original configuration,
    and then average that across all the lands in the hand.
    """
    # First figure out how many spells are currently alive
    base_dead_count, _ = _count_dead_spells_expanded(
        hand, turn, on_play, persisted_producers[:], persisted_castable_spells.copy()
    )
    # Count how many spells are in hand total (ignoring lands)
    total_spells = len([c for c in hand if c and not c.is_land])
    base_alive_count = total_spells - base_dead_count

    lands_in_hand = [c for c in hand if c is not None and c.is_land]
    if not lands_in_hand:
        return 0.0  # No lands to replace => no change

    total_revived = 0
    for old_land in lands_in_hand:
        test_hand = hand[:]  # shallow copy
        test_producers = persisted_producers[:]
        test_castable = persisted_castable_spells.copy()

        # Replace old_land with a new land of the chosen color
        idx = test_hand.index(old_land)
        test_hand[idx] = Card('>' + color, display_name=f"{color}_basic")

        new_dead_count, _ = _count_dead_spells_expanded(
            test_hand, turn, on_play, test_producers, test_castable
        )
        new_alive_count = total_spells - new_dead_count
        revived = new_alive_count - base_alive_count
        total_revived += revived

    # Return the average across all replaced lands
    return total_revived / len(lands_in_hand)

def run_simulation(
    deck_dict: dict[str, tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int | None = None,
    on_play: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if seed is not None:
        random.seed(seed)

    # Figure out which colors are used in the deck (for spells)
    used_spell_colors: set[str] = set()
    for card_name, (mana_str, qty) in deck_dict.items():
        if not mana_str.startswith('>'):  # skip pure land lines
            for ch in mana_str:
                if ch in CANONICAL_COLORS:
                    used_spell_colors.add(ch)

    dead_counts_per_turn: list[list[int]] = [[] for _ in range(draws)]
    # We'll store sum of revived spells only for used colors
    from collections import defaultdict
    revived_color_counts = [defaultdict(float) for _ in range(draws)]

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        persisted_mana_producers: list[Card] = []
        persisted_castable_spells: set[Card] = set()

        for turn in range(1, draws + 1):
            if on_play:
                hand_size_for_turn = initial_hand_size + (turn - 1)
            else:
                hand_size_for_turn = initial_hand_size + turn

            hand = deck.draw_top_n(hand_size_for_turn)

            dead_count, newly_castable = _count_dead_spells_expanded(
                hand,
                turn,
                on_play,
                persisted_mana_producers,
                persisted_castable_spells
            )
            dead_counts_per_turn[turn - 1].append(dead_count)

            persisted_mana_producers.extend(newly_castable)

            # For each used color, see how many spells would be revived
            for color in used_spell_colors:
                revived_avg = _average_spells_revived_if_replace_any_one_land(
                    hand,
                    turn,
                    on_play,
                    persisted_mana_producers,
                    persisted_castable_spells,
                    color
                )
                revived_color_counts[turn - 1][color] += revived_avg

    # Build df_summary
    rows_summary: list[dict[str, float | str]] = []

    for turn in range(1, draws + 1):
        turn_dead_list = dead_counts_per_turn[turn - 1]
        count_ge1 = sum(1 for d in turn_dead_list if d >= 1)
        p_dead = count_ge1 / len(turn_dead_list)

        row = {
            "turn": turn,
            "turn_label": str(turn),
            "p_dead": p_dead,
        }
        # Add the average revived spells for each used color
        for c in used_spell_colors:
            total_revived_for_color = revived_color_counts[turn - 1][c]
            row[f"avg_revived_{c}"] = total_revived_for_color / float(simulations)

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

def run_simulation_with_delay(
    deck_dict: dict[str, tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int | None = None,
    on_play: bool = True
) -> pd.DataFrame:
    """
    Simulate a persistent hand and record, for each non-land spell,
    how many turns it sat in hand (i.e. delay between draw and first being castable).
    Lands are skipped because they are always castable on turn 1.
    """
    if seed is not None:
        random.seed(seed)
    
    delay_records = []
    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()
        hand = []
        # Draw the opening hand
        for _h in range(initial_hand_size):
            if deck.cards:
                card = deck.cards.pop(0)
                if card is not None and not card.is_land:
                    card.draw_turn = 1
                hand.append(card)
        
        persisted_mana_producers = []

        for turn in range(1, draws + 1):
            if turn > 1 and deck.cards:
                card = deck.cards.pop(0)
                if card is not None and not card.is_land:
                    card.draw_turn = turn
                hand.append(card)
            
            available_sources = persisted_mana_producers + [c for c in hand if c is not None and c.is_land]
            lands_playable = turn

            for card in hand.copy():
                if card is None or card.is_land:
                    continue
                if _can_cast_with_sources(card, available_sources, lands_playable):
                    delay = turn - getattr(card, 'draw_turn', turn)
                    delay_records.append({
                        'card_name': card.display_name,
                        'delay': delay
                    })
                    if card.can_produce_mana and (not card.is_land):
                        persisted_mana_producers.append(card)
                    hand.remove(card)
    return pd.DataFrame(delay_records)
