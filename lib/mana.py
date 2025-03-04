import random
import itertools
from collections import Counter

class Spell:
    """
    Represents a spell that requires a certain color combination.
    For example, cost_str='UB' => requires 1 Blue, 1 Black.
    """
    def __init__(self, cost_str: str):
        self.cost_str = cost_str
        self.required_colors = Counter(cost_str)

    def __repr__(self):
        return f"Spell(cost='{self.cost_str}')"


class Mana:
    """
    Represents a mana card. For example, 'UB' => can produce either U or B (but only 1 pip).
    'WUBRG' => can produce any of W, U, B, R, or G.
    """
    def __init__(self, mana_str: str):
        self.mana_str = mana_str
        self.producible_colors = set(mana_str)  # e.g. 'UB' -> {'U','B'}

    def __repr__(self):
        return f"Mana(mana='{self.mana_str}')"


def build_deck_from_dicts(spells_dict, mana_dict, total_deck_size=40):
    """
    Builds a list of Spell objects and a list of Mana objects from dictionaries like:
        spells_dict = {
            'U': 3,
            'B': 5,
            'UU': 1,
            'UB': 2
        }
        mana_dict = {
            'U': 7,
            'UB': 2,
            'B': 6,
            'WUBRG': 1
        }

    total_deck_size is the nominal deck size (e.g. 40) but we do not enforce that
    spells + mana sum exactly to 40, in case there's overlap or extraneous cards.
    """
    spells = []
    for cost_str, qty in spells_dict.items():
        for _ in range(qty):
            spells.append(Spell(cost_str))

    mana_cards = []
    for mana_str, qty in mana_dict.items():
        for _ in range(qty):
            mana_cards.append(Mana(mana_str))

    # Return them as separate lists, plus an integer specifying total deck size
    return spells, mana_cards, total_deck_size


def all_possible_color_combinations(mana_cards):
    """
    For a given list of Mana objects, return all possible ways to pick exactly one color
    from each card. Example:
        if mana_cards = [Mana('UB'), Mana('U')],
        then color_sets = [ {'U','B'}, {'U'} ]
        the product is:
            ('U','U') => Counter({'U':2})
            ('B','U') => Counter({'B':1,'U':1})
    """
    color_sets = [m.producible_colors for m in mana_cards]
    combos = itertools.product(*color_sets)  # Cartesian product
    combo_counters = []
    for combo in combos:
        c = Counter(combo)
        combo_counters.append(c)
    return combo_counters


def can_cast(spell, mana_cards):
    """
    Returns True if there's at least one way to assign exactly one color from each Mana
    such that the total color pips >= the spell's required colors.
    """
    required = spell.required_colors
    combos = all_possible_color_combinations(mana_cards)
    for combo_counter in combos:
        # Check if this color combination meets or exceeds all required pips
        if all(combo_counter[color] >= required[color] for color in required):
            return True
    return False


def simulate_dead_cards(spells_dict, mana_dict, total_deck_size=40,
                        draws=10, simulations=100_000, seed=None):
    """
    Monte Carlo approach:
      - Build a "physical" deck list of length total_deck_size by combining
        the Spell and Mana cards. If the sum < total_deck_size, fill the rest
        with "other" placeholder cards that are never dead (e.g. colorless or unmodeled).
      - Shuffle, draw 7 cards initially, then 1 more each turn up to 'draws' turns.
      - Check how many spells in hand are "dead" at each draw.
      - Repeat for 'simulations' trials and average.

    Return a list/array of average dead card counts per draw index: [turn0, turn1, ...].
    """

    if seed is not None:
        random.seed(seed)

    # Build the deck as a list of Python objects: spells, mana, + fill
    spells, mana_cards, _ = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)
    
    # We'll treat any leftover capacity as "neutral" cards that are never dead.
    deck_list = spells + mana_cards
    leftover = total_deck_size - len(deck_list)
    if leftover > 0:
        # We'll just make them None to denote "non-dead, non-mana" cards
        deck_list += [None] * leftover

    # Precompute how many turns: turn 0 means the initial 7-card hand,
    # turn i means 7 + i cards drawn.
    # We'll do draws from 0 to draws-1 (so total draws steps is 'draws').
    dead_counts_accum = [0] * draws  # Accumulator for dead card count

    for _ in range(simulations):
        # Shuffle deck and draw
        random.shuffle(deck_list)
        hand = []

        for turn in range(draws):
            if turn == 0:
                # draw initial 7
                hand = deck_list[:7]
            else:
                # add 1 more card for each turn after 0
                next_card_index = 7 + turn - 1
                hand = deck_list[:7 + turn]

            # Separate spells vs. mana in the hand
            hand_spells = [c for c in hand if isinstance(c, Spell)]
            hand_mana   = [c for c in hand if isinstance(c, Mana)]
            
            # Check how many spells are dead
            dead_count = 0
            for s in hand_spells:
                if not can_cast(s, hand_mana):
                    dead_count += 1

            dead_counts_accum[turn] += dead_count

    # Average the results
    dead_counts_avg = [dc / simulations for dc in dead_counts_accum]
    return dead_counts_avg


