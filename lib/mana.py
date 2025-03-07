import random
import itertools
import re
from collections import Counter
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
    - If the string starts with '>', it's a land (e.g. '>BW') that can produce B or W.
    - If the string has a '>' in the middle, it's a mana-producing spell (e.g. '3*>WUBRG').
    - Otherwise, it's a plain spell (e.g. 'BW').
    """
    def __init__(self, card_str: str):
        self.card_str = card_str
        self.is_land = card_str.startswith('>')

        self.can_produce_mana = False
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
    Return a generator of Counter(...) for each possible color assignment.
    This lets us short-circuit in _can_cast_with_sources as soon as a valid assignment is found.
    """
    for combo in itertools.product(*(c.producible_colors for c in mana_cards)):
        yield Counter(combo)

def _can_cast_with_sources(spell, sources, lands_playable):
    """
    Checks if 'spell' can be cast using up to 'lands_playable' from 'sources',
    short-circuiting as soon as we find one valid subset+assignment.
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
                if all(combo_counter[color] >= spell.cost_colors[color] for color in spell.cost_colors):
                    color_lands_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_lands_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False

def _count_dead_spells_expanded(
    hand,
    turn,
    on_play,
    persisted_producers,
    persisted_castable_spells
):
    """
    Return (dead_count, newly_castable).

    - persisted_producers: list of Card objects that produce mana and were determined castable
      in previous turns, so they function as "land sources".
    - persisted_castable_spells: set of Card objects (or card_str) that were determined castable
      in previous turns but do NOT produce mana. Once castable => always castable => skip checks.

    We do a single pass:
      - Combine persisted_producers with land in the hand to form 'available_sources'.
      - For each new or not-yet-castable card in hand, see if it is castable.
        - If yes and can_produce_mana => add to newly_castable.
        - If yes and not can_produce_mana => add to persisted_castable_spells so we skip next time.
        - Else it's dead.
    """
    lands_playable = turn + 1 if on_play else turn
    if lands_playable < 0:
        lands_playable = 0

    # Build "available sources" = old producers + land in this hand
    available_sources = list(persisted_producers)
    for c in hand:
        if c and c.is_land:
            available_sources.append(c)

    dead_count = 0
    newly_castable = []

    for c in hand:
        if c is None or c.is_land:
            # Land doesn't need casting => not dead
            continue

        # If we've already marked this card as castable in prior turns, skip check
        if c.can_produce_mana:
            # For mana producers, we rely on whether it's in persisted_mana_producers
            # so if it is not in persisted_mana_producers, we still re-check.
            pass
        else:
            # Non-mana spell: if it's in persisted_castable_spells, skip re-check
            if c in persisted_castable_spells:
                continue  # definitely not dead
        # Otherwise, check castability
        if _can_cast_with_sources(c, available_sources, lands_playable):
            if c.can_produce_mana and not c.is_land:
                # newly discovered mana-producer => add to newly_castable
                newly_castable.append(c)
            else:
                # normal spell => mark as persisted castable
                persisted_castable_spells.add(c)
        else:
            dead_count += 1

    return dead_count, newly_castable

def _best_single_color_to_replace(
    hand,
    turn,
    on_play,
    persisted_producers,
    persisted_castable_spells,
    colors_to_test=CANONICAL_COLORS
):
    """
    Attempt replacing one land in the hand with a single-color land (e.g. ">W"),
    see if that reduces the number of dead spells. Short-circuit if we find zero dead.
    """
    # Evaluate "base_dead" first
    base_dead, _ = _count_dead_spells_expanded(
        hand, turn, on_play, persisted_producers, persisted_castable_spells
    )
    hand_mana = [c for c in hand if c and c.is_land]
    if not hand_mana:
        return "none"

    best_color = "none"
    best_dead_count = base_dead

    # In-place replacement + revert
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
    deck_dict,
    total_deck_size=40,
    initial_hand_size=7,
    draws=10,
    simulations=100_000,
    seed=None,
    on_play=True
):
    """
    Main entry. Key differences from prior code:
      - We track both persisted_mana_producers (like before) AND
        persisted_castable_spells (for normal spells).
      - If a normal spell is found castable in any prior turn, we skip checking it again.

    Everything else is the same logic, just with an extra skip for known-castable spells.
    """
    if seed is not None:
        random.seed(seed)

    dead_counts_per_turn = [[] for _ in range(draws)]
    best_color_counts = [Counter() for _ in range(draws)]

    for _ in range(simulations):
        deck = build_deck_from_dict(deck_dict, total_deck_size)
        deck.shuffle()

        # Already known producers + already known castable spells
        persisted_mana_producers = []
        persisted_castable_spells = set()

        for turn in range(1, draws + 1):
            if on_play:
                hand_size = initial_hand_size + (turn - 1)
            else:
                hand_size = initial_hand_size + turn

            hand = deck.draw_top_n(hand_size)

            dead_count, newly_castable = _count_dead_spells_expanded(
                hand, turn, on_play,
                persisted_mana_producers,
                persisted_castable_spells
            )
            dead_counts_per_turn[turn - 1].append(dead_count)

            # Any new producers discovered => add them for future turns
            persisted_mana_producers.extend(newly_castable)

            best_color = _best_single_color_to_replace(
                hand, turn, on_play,
                persisted_mana_producers,
                persisted_castable_spells
            )
            best_color_counts[turn - 1][best_color] += 1

    # Build df_summary
    rows_summary = []
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
    distribution_rows = []
    for turn in range(1, draws + 1):
        c = Counter(dead_counts_per_turn[turn - 1])
        for dead_val, freq in c.items():
            distribution_rows.append({
                "turn": turn,
                "turn_label": str(turn),
                "dead_spells": dead_val,
                "frequency": freq
            })

    df_distribution = pd.DataFrame(distribution_rows)

    return df_summary, df_distribution
