import random
import itertools
import re
from collections import Counter
import numpy as np
import pandas as pd

CANONICAL_COLORS = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES = ['grey', 'blue', 'black', 'red', 'green']

def parse_cost_string(cost_str):
    """
    Same approach as your original code to parse, e.g. '3*U2W' -> (3, {'U':1, 'W':2}).
    """
    pattern = r'(\d*\*|\d*[WUBRG])'
    matches = re.findall(pattern, cost_str)
    uncolored = 0
    color_costs = Counter()
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
    Unified representation:
      - If the string starts with '>', it's a land (e.g. '>BW') that can produce B or W.
      - If the string has a '>' in the middle, it's a mana-producing spell (e.g. '3*>WUBRG').
      - Otherwise, it's a plain spell (e.g. 'BW').
    """
    def __init__(self, card_str: str):
        self.card_str = card_str
        self.is_land = card_str.startswith('>')

        self.can_produce_mana = False  # True for lands or spells that produce mana
        self.cost_uncolored = 0
        self.cost_colors = Counter()
        self.producible_colors = set()

        if self.is_land:
            # For lands, the part after '>' is the color set
            produce_part = card_str[1:]  # e.g. 'BW'
            self.can_produce_mana = True
            self.producible_colors = set(produce_part)
        else:
            # Possibly a spell that can produce mana if it has '>'
            if '>' in card_str:
                # e.g. '3*>WUBRG'
                cost_part, produce_part = card_str.split('>', 1)
                self.can_produce_mana = True
                self.producible_colors = set(produce_part)
            else:
                # Just a plain spell
                cost_part = card_str

            # Parse out its cost
            uncolored, color_costs = parse_cost_string(cost_part)
            self.cost_uncolored = uncolored
            self.cost_colors = color_costs

    def __repr__(self):
        return f"Card({self.card_str})"


class Deck:
    def __init__(self, cards, total_size=40):
        self.cards = cards
        self.total_size = total_size
        leftover = total_size - len(cards)
        if leftover > 0:
            # Fill with None if deck is smaller than total
            self.cards += [None] * leftover

    def shuffle(self):
        random.shuffle(self.cards)

    def draw_top_n(self, n):
        return self.cards[:n]

    def __len__(self):
        return len(self.cards)

    def __repr__(self):
        return f"Deck(size={self.total_size}, actual_list_len={len(self.cards)})"


def build_deck_from_dict(deck_dict, total_deck_size=40):
    """
    deck_dict: e.g. {
      "BW": 2,
      ">U": 4,
      "3*>WUBRG": 1
    }
    """
    card_objs = []
    for cstr, qty in deck_dict.items():
        for _ in range(qty):
            card_objs.append(Card(cstr))
    return Deck(card_objs, total_deck_size)


def _all_possible_color_combinations(mana_cards):
    """
    Given a list of "sources" that each can produce 1 mana from a set of colors,
    yields all possible ways they could collectively produce mana.
    Each element is a Counter of color -> quantity.
    """
    combos = itertools.product(*(c.producible_colors for c in mana_cards))
    return [Counter(combo) for combo in combos]


def _can_cast_with_sources(spell, sources, lands_playable):
    """
    Checks if 'spell' can be cast using up to 'lands_playable' from the given 'sources'.
    'sources' is a list of Card objects that can produce mana (land or previously castable spells).
    This is analogous to your original 'can_cast', but we unify land/spell producers.
    """
    needed_total = spell.cost_uncolored + sum(spell.cost_colors.values())
    if needed_total > lands_playable:
        return False
    if not sources:
        return False

    indices = range(len(sources))
    for subset_size in range(needed_total, lands_playable + 1):
        if subset_size > len(sources):
            break
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [sources[i] for i in subset_indices]
            for combo_counter in _all_possible_color_combinations(subset):
                # Check color requirements
                if all(combo_counter[color] >= spell.cost_colors[color] for color in spell.cost_colors):
                    # Check leftover (uncolored) mana
                    color_lands_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_lands_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False


def _best_single_color_to_replace(hand, turn, on_play, persisted_producers, colors_to_test=CANONICAL_COLORS):
    """
    This is the same logic from your original code that tries replacing one land
    with a single-color land and sees if that reduces the number of dead spells.
    We'll keep it for continuity.
    """
    base_dead = _count_dead_spells_expanded(hand, turn, on_play, persisted_producers)[0]

    # Separate out the lands in hand
    hand_mana = [c for c in hand if c and c.is_land]
    if not hand_mana:
        return "none"

    best_color = "none"
    best_dead_count = base_dead

    for color in colors_to_test:
        for land_index, original_land in enumerate(hand_mana):
            # Temporarily replace that land with a single-color land
            hypothetical_hand = hand.copy()
            idx_in_hand = hypothetical_hand.index(original_land)
            # Construct a single-color land:
            replaced_land = Card('>' + color)  # e.g. ">W"
            hypothetical_hand[idx_in_hand] = replaced_land

            # Evaluate dead spells
            new_dead = _count_dead_spells_expanded(hypothetical_hand, turn, on_play, persisted_producers)[0]
            if new_dead < best_dead_count:
                best_dead_count = new_dead
                best_color = color

    return best_color


def _count_dead_spells_expanded(hand, turn, on_play, persisted_producers):
    """
    Return (dead_count, newly_castable_list).

    - hand: list of Card objects (some may be None).
    - turn, on_play: used to figure out how many total lands we can use.
    - persisted_producers: list of Card objects that produce mana and were determined castable
      on previous turns, so they effectively function as "land sources" from now on.

    Once a card is found castable at turn X, it remains castable for turn X+1, X+2, etc.
    We do NOT re-check if it's castable again — it's simply an available source from that point onward.

    We'll do a single pass:
      - Combine persisted_producers with any land in the hand to form 'available_sources'.
      - For each card in the hand:
          if it is castable with available_sources (and the turn's land limit),
            then it's not dead. 
            If that card can produce mana (and is not a land), we mark it as newly castable.
          else it's dead.
    """
    # For consistency with your old code:
    lands_playable = turn + 1 if on_play else turn
    if lands_playable < 0:
        lands_playable = 0

    # Build the "available sources" = persisted producers + land in this hand
    available_sources = list(persisted_producers)
    for c in hand:
        if c and c.is_land:
            available_sources.append(c)

    dead_count = 0
    newly_castable = []

    for c in hand:
        if c is None:
            continue
        # If it's a land, it's never "dead" by definition (it doesn't need casting).
        if c.is_land:
            continue

        # Check if c is castable with the current sources
        if _can_cast_with_sources(c, available_sources, lands_playable):
            # It's castable => not dead
            # If it can produce mana (and is not a land), that means we can treat it as
            # an available source for subsequent turns. We add it to 'newly_castable'.
            if c.can_produce_mana and not c.is_land:
                newly_castable.append(c)
        else:
            # It's dead
            dead_count += 1

    return dead_count, newly_castable


def run_simulation(deck_dict,
                   total_deck_size=40,
                   initial_hand_size=7,
                   draws=10,
                   simulations=100_000,
                   seed=None,
                   on_play=True):
    """
    Main entry: similar to your original run_simulation, but uses _count_dead_spells_expanded 
    to handle mana-producing spells across turns.

    Returns:
      df_summary: (turn-wise stats) includes 'p_dead' and fraction of "best color" picks
      df_distribution: distribution of dead spell counts per turn
    """
    if seed is not None:
        random.seed(seed)

    dead_counts_per_turn = [[] for _ in range(draws)]
    best_color_counts = [Counter() for _ in range(draws)]

    for _ in range(simulations):
        # We'll build & shuffle the deck
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        # We'll keep track of "persisted_mana_producers" across turns 
        # so they become available in subsequent turns
        persisted_mana_producers = []

        for turn in range(1, draws + 1):
            # Like your old code: on turn 1, if on_play, no draw step, so total draws so far = turn-1
            if on_play:
                hand_size = initial_hand_size + (turn - 1)
            else:
                hand_size = initial_hand_size + turn

            # Draw the top 'hand_size' from the deck
            hand = deck.draw_top_n(hand_size)

            # Count dead spells, find newly castable
            dead_count, newly_castable = _count_dead_spells_expanded(
                hand, turn, on_play, persisted_mana_producers
            )
            dead_counts_per_turn[turn - 1].append(dead_count)

            # Add newly castable producers to the persisted list (once castable => always available)
            persisted_mana_producers.extend(newly_castable)

            # We also want to track "best color to replace a land" each turn
            best_color = _best_single_color_to_replace(hand, turn, on_play, persisted_mana_producers)
            best_color_counts[turn - 1][best_color] += 1

    # Build df_summary (p_dead, fraction of best color picks, etc.)
    rows_summary = []
    extended_colors = CANONICAL_COLORS + ["none"]

    for turn in range(1, draws + 1):
        arr = np.array(dead_counts_per_turn[turn - 1])
        p_dead = float((arr >= 1).mean())

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
    distribution_rows = []
    for turn in range(1, draws + 1):
        counts = Counter(dead_counts_per_turn[turn - 1])
        for dead_val, freq in counts.items():
            distribution_rows.append({
                "turn": turn,
                "turn_label": str(turn),
                "dead_spells": dead_val,
                "frequency": freq
            })
    df_distribution = pd.DataFrame(distribution_rows)

    return df_summary, df_distribution
