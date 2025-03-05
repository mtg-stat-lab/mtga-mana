import random
import itertools
from collections import Counter
import numpy as np
import pandas as pd
import altair as alt

CANONICAL_COLORS = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES = ['grey', 'blue', 'black', 'red', 'green']

class Spell:
    """
    Represents a spell that requires a certain color combination.
    For example, cost_str='UB' => requires 1 Blue, 1 Black.
    """
    def __init__(self, cost_str: str):
        self.cost_str = cost_str
        self.required_colors = Counter(cost_str)

    def __repr__(self) -> str:
        return f"Spell(cost='{self.cost_str}')"

class Mana:
    """
    Represents a mana card. For example, 'UB' => can produce either U or B (but only 1 pip).
    'WUBRG' => can produce any of W, U, B, R, G.
    """
    def __init__(self, mana_str: str):
        self.mana_str = mana_str
        self.producible_colors = set(mana_str)

    def __repr__(self) -> str:
        return f"Mana(mana='{self.mana_str}')"

def all_possible_color_combinations(mana_cards):
    """
    For a given list of Mana objects, return all possible ways to pick exactly one color
    from each card.
    """
    combos = itertools.product(*(m.producible_colors for m in mana_cards))  # Cartesian product
    combo_counters = []
    for combo in combos:
        combo_counters.append(Counter(combo))
    return combo_counters

def can_cast(spell, mana_cards):
    """
    Returns True if there's at least one way to assign exactly one color from each Mana
    such that the total color pips >= the spell's required colors.
    """
    required = spell.required_colors
    combos = all_possible_color_combinations(mana_cards)
    for combo_counter in combos:
        if all(combo_counter[color] >= required[color] for color in required):
            return True
    return False

class Deck:
    """
    Represents a deck of size `total_size`. It can contain spells, mana cards, and filler (None).
    """
    def __init__(self, spells, mana_cards, total_size=40):
        self.spells = spells
        self.mana_cards = mana_cards
        self.total_size = total_size

        self.deck_list = spells + mana_cards
        leftover = total_size - len(self.deck_list)
        if leftover > 0:
            self.deck_list += [None] * leftover  # "other" filler cards

    def shuffle(self):
        random.shuffle(self.deck_list)

    def draw_top_n(self, n):
        return self.deck_list[:n]

    def __len__(self):
        return len(self.deck_list)

def build_deck_from_dicts(spells_dict, mana_dict, total_deck_size=40):
    spells = []
    for cost_str, qty in spells_dict.items():
        for _ in range(qty):
            spells.append(Spell(cost_str))

    mana_cards = []
    for mana_str, qty in mana_dict.items():
        for _ in range(qty):
            mana_cards.append(Mana(mana_str))

    return Deck(spells, mana_cards, total_deck_size)

def _count_dead_spells(hand):
    """
    Return how many spells in 'hand' are uncastable given the mana in 'hand'.
    """
    hand_spells = [c for c in hand if isinstance(c, Spell)]
    hand_mana   = [c for c in hand if isinstance(c, Mana)]
    dead_count = sum(not can_cast(s, hand_mana) for s in hand_spells)
    return dead_count

def _best_single_color_to_add(hand, colors_to_test=CANONICAL_COLORS):
    """
    Among `colors_to_test`, find which single color would reduce
    the number of dead spells the most.
    """
    base_dead = _count_dead_spells(hand)
    color_results = []
    for color in colors_to_test:
        hypothetical_hand = hand + [Mana(color)]
        hypothetical_dead = _count_dead_spells(hypothetical_hand)
        color_results.append((color, hypothetical_dead))
    min_dead = min(cr[1] for cr in color_results)
    if min_dead >= base_dead:
        return "none"
    top_candidates = [cr[0] for cr in color_results if cr[1] == min_dead]
    return random.choice(top_candidates)

def run_simulation(spells_dict,
                   mana_dict,
                   total_deck_size=40,
                   initial_hand_size=7,
                   draws=10,
                   simulations=100_000,
                   seed=None):
    """
    Monte Carlo simulation steps:
      1) Build a Deck, shuffle, and draw each turn.
      2) For each draw step, count the number of dead spells and which color would help most.
      3) Keep track of p_dead = Probability of at least 1 dead spell on that turn.
      4) Keep track of how many times each color is optimal (including 'none').
      5) Also build a distribution of 'dead spells' across all simulations for each turn.
    Returns a tuple of dataframes: (df_summary, df_distribution)
      - df_summary has columns:
          turn, p_dead,
          pct_optimal_W, pct_optimal_U, pct_optimal_B, pct_optimal_R, pct_optimal_G, pct_optimal_none
      - df_distribution has columns:
          turn, dead_spells, frequency
        meaning: On `turn`, `dead_spells` occurred `frequency` times across the simulations.
    """
    if seed is not None:
        random.seed(seed)

    deck = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)
    # For each turn, we store list of dead spell counts from each simulation:
    dead_counts_per_turn = [[] for _ in range(draws)]
    # For each turn, we also track best color picks:
    best_color_counts = [Counter() for _ in range(draws)]
    extended_colors = CANONICAL_COLORS + ["none"]

    for _ in range(simulations):
        deck.shuffle()
        for turn in range(draws):
            hand_size = initial_hand_size + turn
            hand = deck.draw_top_n(hand_size)
            dead_count = _count_dead_spells(hand)
            dead_counts_per_turn[turn].append(dead_count)

            best_color = _best_single_color_to_add(hand, CANONICAL_COLORS)
            best_color_counts[turn][best_color] += 1

    # Build df_summary
    rows_summary = []
    for turn in range(draws):
        dead_array = np.array(dead_counts_per_turn[turn])
        # Probability of at least 1 dead spell
        p_dead = float((dead_array >= 1).mean())

        # Fraction of times each color is best
        total_sims = float(simulations)
        color_fracs = {
            color: best_color_counts[turn][color] / total_sims
            for color in extended_colors
        }
        row = {
            "turn": turn,
            "p_dead": p_dead,
            **{f"pct_optimal_{c}": color_fracs[c] for c in extended_colors}
        }
        rows_summary.append(row)

    df_summary = pd.DataFrame(rows_summary)

    # Build df_distribution for stacked bar chart
    distribution_rows = []
    for turn in range(draws):
        counts = Counter(dead_counts_per_turn[turn])
        for dead_val, freq in counts.items():
            distribution_rows.append({
                "turn": turn,
                "dead_spells": dead_val,
                "frequency": freq
            })

    df_distribution = pd.DataFrame(distribution_rows)
    return df_summary, df_distribution

def create_altair_charts(df_summary, df_distribution):
    """
    Creates three Altair charts, stacked vertically:
      1) Probability of ≥1 dead spell (area chart)
      2) Distribution of dead spells (stacked bar chart by turn)
      3) Percent of time each color is optimal
    """

    # --- 1) Top Chart: Probability of ≥1 dead spell ---
    prob_chart = alt.Chart(df_summary).mark_area(interpolate="monotone", opacity=0.3, color="red").encode(
        x=alt.X('turn:Q', title='Draw step', axis=alt.Axis(format='d')),
        y=alt.Y('p_dead:Q', title='Probability of ≥1 dead spell', axis=alt.Axis(format='%'),
                scale=alt.Scale(domain=[0, 1]))
    ).properties(
        width=600,
        height=200,
        title="Probability of having one or more dead spells"
    )

    # Add text annotation of average probability
    avg_prob = df_summary['p_dead'].mean() if len(df_summary) > 0 else 0
    avg_label = f"Avg: {avg_prob*100:.1f}%"
    max_turn = df_summary['turn'].max() if not df_summary.empty else 10
    text_annot = alt.Chart(pd.DataFrame({
        'turn': [max_turn],
        'p_dead': [0.95],
        'label': [avg_label]
    })).mark_text(
        align='right',
        baseline='top',
        fontWeight='bold',
        fontSize=14,
        dx=-5
    ).encode(
        x='turn:Q',
        y='p_dead:Q',
        text='label:N'
    )

    prob_chart = prob_chart + text_annot

    # --- 2) Middle Chart: Stacked bar distribution of dead spells ---
    distribution_chart = (
        alt.Chart(df_distribution)
        .mark_bar()
        .encode(
            x=alt.X('turn:O', title='Draw step'),  # discrete axis
            y=alt.Y('frequency:Q', title='Number of simulations'),
            color=alt.Color(
                'dead_spells:N',
                title='Dead Spells in Hand',
                scale=alt.Scale(scheme='magma')  # Use the magma color scheme
            ),
            order=alt.Order('dead_spells', sort='ascending')
        )
        .properties(
            width=600,
            height=200,
            title="Distribution of Dead Spells (Stacked)"
        )
    )

    # --- 3) Bottom Chart: Which color was optimal? ---
    # For convenience, rename the color columns in df_summary for Altair
    # (like your original code, but we no longer have 'dead_cards_10p' / 'dead_cards_90p', etc.)
    df_colordist = df_summary.copy()
    canonical_map = {f"pct_optimal_{c}": c for c in CANONICAL_COLORS}
    df_colordist.rename(columns=canonical_map, inplace=True)

    bottom_chart = (
        alt.Chart(df_colordist)
        .transform_fold(
            CANONICAL_COLORS,
            as_=['color_type', 'pct']
        )
        .mark_line()
        .encode(
            x=alt.X('turn:Q', title='Draw step', axis=alt.Axis(format='d')),
            y=alt.Y('pct:Q', title='Percent of the time', axis=alt.Axis(format='%')),
            color=alt.Color(
                'color_type:N',
                scale=alt.Scale(domain=CANONICAL_COLORS, range=CANONICAL_COLOR_VALUES),
                legend=alt.Legend(title='Mana')
            )
        )
        .properties(
            width=600,
            height=200,
            title="Percent of time you'll wish you had an extra pip of a given color"
        )
    )

    # Concatenate the three charts vertically
    combined_chart = alt.vconcat(prob_chart, distribution_chart, bottom_chart).resolve_scale(color='independent')
    return combined_chart
