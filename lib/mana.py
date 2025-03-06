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
    Parse a cost string like 'U', '3U', '4*', '4*U2W', etc.
    Returns (uncolored_cost, color_costs_dict).
    Example:
      '4*U2W' -> (4, {'U':1, 'W':2})
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


class Spell:
    def __init__(self, cost_str: str):
        self.cost_str = cost_str
        self.uncolored_cost, self.required_colors = parse_cost_string(cost_str)

    def __repr__(self) -> str:
        return f"Spell(cost='{self.cost_str}')"


class Mana:
    """
    A 'land' or mana card that can produce exactly 1 mana,
    but it can be any one color from the set 'producible_colors'.
    """
    def __init__(self, mana_str: str):
        self.mana_str = mana_str
        self.producible_colors = set(mana_str)

    def __repr__(self) -> str:
        return f"Mana(mana='{self.mana_str}')"


def all_possible_color_combinations(mana_cards):
    """
    Given a list of Mana objects, yields all possible ways
    they could collectively produce mana (as a list of Counters).
    """
    combos = itertools.product(*(m.producible_colors for m in mana_cards))
    return [Counter(combo) for combo in combos]


def can_cast(spell, mana_cards, lands_playable):
    """
    Check if 'spell' can be cast using up to 'lands_playable' mana cards.
    The function tries subsets of the available mana cards.
    """
    needed_total = spell.uncolored_cost + sum(spell.required_colors.values())
    if needed_total > lands_playable:
        return False
    if not mana_cards:
        return False

    indices = range(len(mana_cards))
    for subset_size in range(needed_total, lands_playable + 1):
        if subset_size > len(mana_cards):
            break
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [mana_cards[i] for i in subset_indices]
            for combo_counter in all_possible_color_combinations(subset):
                # Check color requirements
                if all(combo_counter[color] >= spell.required_colors[color]
                       for color in spell.required_colors):
                    # Check leftover (uncolored) mana
                    color_lands_used = sum(spell.required_colors[c] for c in spell.required_colors)
                    leftover = subset_size - color_lands_used
                    if leftover >= spell.uncolored_cost:
                        return True
    return False


class Deck:
    def __init__(self, spells, mana_cards, total_size=40):
        self.spells = spells
        self.mana_cards = mana_cards
        self.total_size = total_size

        self.deck_list = spells + mana_cards
        leftover = total_size - len(self.deck_list)
        if leftover > 0:
            # Fill remaining with None
            self.deck_list += [None] * leftover

    def shuffle(self):
        random.shuffle(self.deck_list)

    def draw_top_n(self, n):
        return self.deck_list[:n]

    def __len__(self):
        return len(self.deck_list)

    def __repr__(self) -> str:
        return (
            f"Deck(size={self.total_size}, spells={len(self.spells)}, "
            f"mana={len(self.mana_cards)}, actual_list_len={len(self.deck_list)})"
        )


def build_deck_from_dicts(spells_dict, mana_dict, total_deck_size=40):
    """
    Builds a Deck from the spells_dict and mana_dict,
    each of which map strings -> quantity.
    """
    spells = []
    for cost_str, qty in spells_dict.items():
        for _ in range(qty):
            spells.append(Spell(cost_str))

    mana_cards = []
    for mana_str, qty in mana_dict.items():
        for _ in range(qty):
            mana_cards.append(Mana(mana_str))

    return Deck(spells, mana_cards, total_deck_size)


def _count_dead_spells(hand, turn, on_play):
    """
    Count how many spells in 'hand' are uncastable on a given turn,
    considering how many lands you could have played.
    """
    # If on the play, on turn X, you can have played X lands (turns 1..X).
    # If on the draw, on turn X, you can have played X-1 lands (since you drew first).
    # The code below uses turn+1 if on_play, else turn.
    lands_playable = turn + 1 if on_play else turn
    if lands_playable < 0:
        lands_playable = 0

    hand_spells = [c for c in hand if isinstance(c, Spell)]
    hand_mana = [c for c in hand if isinstance(c, Mana)]

    dead_count = 0
    for s in hand_spells:
        if not can_cast(s, hand_mana, lands_playable):
            dead_count += 1
    return dead_count


def _best_single_color_to_replace(hand, turn, on_play, colors_to_test=CANONICAL_COLORS):
    """
    Determine which single-color land replacement reduces dead spells the most.
    We consider replacing exactly one of the existing Mana cards in `hand`
    with a single-color Mana(...) from `colors_to_test`.
    """

    base_dead = _count_dead_spells(hand, turn, on_play)

    # Separate out the lands in hand
    hand_mana = [c for c in hand if isinstance(c, Mana)]
    if not hand_mana:
        # No mana in hand => can't replace anything
        return "none"

    best_color = "none"
    best_dead_count = base_dead  # we want to minimize dead spells

    for color in colors_to_test:
        # We'll see if replacing *any* single land with this color helps.
        best_for_this_color = base_dead

        for land_index, original_land in enumerate(hand_mana):
            hypothetical_hand = hand.copy()
            idx_in_hand = hypothetical_hand.index(original_land)
            hypothetical_hand[idx_in_hand] = Mana(color)

            new_dead = _count_dead_spells(hypothetical_hand, turn, on_play)
            if new_dead < best_for_this_color:
                best_for_this_color = new_dead

        if best_for_this_color < best_dead_count:
            best_dead_count = best_for_this_color
            best_color = color

    return best_color


def run_simulation(spells_dict,
                   mana_dict,
                   total_deck_size=40,
                   initial_hand_size=7,
                   draws=10,
                   simulations=100_000,
                   seed=None,
                   on_play=True):
    """
    Runs the simulation and returns two DataFrames:

      df_summary      -> stats per turn, including p_dead and fraction of "best color" picks.
      df_distribution -> distribution of dead spell counts per turn.

    'on_play' indicates whether we are on the play (vs. on the draw).
    """
    if seed is not None:
        random.seed(seed)

    deck = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)

    dead_counts_per_turn = [[] for _ in range(draws)]
    best_color_counts = [Counter() for _ in range(draws)]

    for _ in range(simulations):
        deck.shuffle()

        for turn in range(1, draws + 1):
            # On the play => no draw step on turn 1 => total draws so far = turn-1
            # On the draw => there is a draw on turn 1 => total draws so far = turn
            if on_play:
                hand_size = initial_hand_size + (turn - 1)
            else:
                hand_size = initial_hand_size + turn

            hand = deck.draw_top_n(hand_size)

            dead_count = _count_dead_spells(hand, turn, on_play)
            dead_counts_per_turn[turn - 1].append(dead_count)

            best_color = _best_single_color_to_replace(hand, turn, on_play)
            best_color_counts[turn - 1][best_color] += 1

    # Build df_summary
    rows_summary = []
    extended_colors = CANONICAL_COLORS + ["none"]

    for turn in range(1, draws + 1):
        dead_array = np.array(dead_counts_per_turn[turn - 1])
        p_dead = float((dead_array >= 1).mean())

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
