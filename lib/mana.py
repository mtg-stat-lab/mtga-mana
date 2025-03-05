import random
import itertools
from collections import Counter
import numpy as np
import pandas as pd
import altair as alt

CANONICAL_COLORS = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES = ['grey', 'blue', 'black', 'red', 'green']


class Spell:
    def __init__(self, cost_str: str):
        self.cost_str = cost_str
        self.required_colors = Counter(cost_str)

    def __repr__(self) -> str:
        return f"Spell(cost='{self.cost_str}')"


class Mana:
    def __init__(self, mana_str: str):
        self.mana_str = mana_str
        self.producible_colors = set(mana_str)

    def __repr__(self) -> str:
        return f"Mana(mana='{self.mana_str}')"


def all_possible_color_combinations(mana_cards):
    combos = itertools.product(*(m.producible_colors for m in mana_cards))
    return [Counter(combo) for combo in combos]


def can_cast(spell, mana_cards):
    required = spell.required_colors
    combos = all_possible_color_combinations(mana_cards)
    for combo_counter in combos:
        if all(combo_counter[color] >= required[color] for color in required):
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
    hand_spells = [c for c in hand if isinstance(c, Spell)]
    hand_mana = [c for c in hand if isinstance(c, Mana)]
    dead_count = sum(not can_cast(s, hand_mana) for s in hand_spells)
    return dead_count


def _best_single_color_to_add(hand, colors_to_test=CANONICAL_COLORS):
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
    Runs 'simulations' number of trials, each trial simulating draws from the deck
    up to 'draws' times (turns). Returns:
        - df_summary: stats per turn
        - df_distribution: distribution of dead_spells counts per turn
        - zero_dead_runs_count: how many entire runs had 0 dead spells at every turn
    """
    if seed is not None:
        random.seed(seed)

    deck = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)

    dead_counts_per_turn = [[] for _ in range(draws + 1)]
    best_color_counts = [Counter() for _ in range(draws + 1)]
    zero_dead_runs_count = 0

    # Simulate
    for _ in range(simulations):
        deck.shuffle()
        run_has_no_dead_spells = True

        for turn in range(draws + 1):
            hand_size = initial_hand_size + turn
            hand = deck.draw_top_n(hand_size)
            dead_count = _count_dead_spells(hand)
            dead_counts_per_turn[turn].append(dead_count)

            if dead_count > 0:
                run_has_no_dead_spells = False

            best_color = _best_single_color_to_add(hand, CANONICAL_COLORS)
            best_color_counts[turn][best_color] += 1

        if run_has_no_dead_spells:
            zero_dead_runs_count += 1

    # Build df_summary
    rows_summary = []
    extended_colors = CANONICAL_COLORS + ["none"]

    for turn in range(draws + 1):
        dead_array = np.array(dead_counts_per_turn[turn])
        p_dead = float((dead_array >= 1).mean())
        turn_lbl = "start" if turn == 0 else str(turn)

        total_sims = float(simulations)
        color_fracs = {
            color: best_color_counts[turn][color] / total_sims
            for color in extended_colors
        }

        row = {
            "turn": turn,
            "turn_label": turn_lbl,
            "p_dead": p_dead,
            **{f"pct_optimal_{c}": color_fracs[c] for c in extended_colors}
        }
        rows_summary.append(row)

    df_summary = pd.DataFrame(rows_summary)

    # Build df_distribution
    distribution_rows = []
    for turn in range(draws + 1):
        turn_lbl = "start" if turn == 0 else str(turn)
        counts = Counter(dead_counts_per_turn[turn])
        for dead_val, freq in counts.items():
            distribution_rows.append({
                "turn": turn,
                "turn_label": turn_lbl,
                "dead_spells": dead_val,
                "frequency": freq
            })

    df_distribution = pd.DataFrame(distribution_rows)

    return df_summary, df_distribution, zero_dead_runs_count


def create_altair_charts(df_summary, df_distribution):
    plot_width = 600
    plot_height = 300

    # Determine maximum turn and set x-axis order.
    max_turn = int(df_summary["turn"].max()) if not df_summary.empty else 0
    turn_sort = ["start"] + [str(i) for i in range(1, max_turn + 1)]

    # Compute the maximum dead spells from the full distribution data.
    if not df_distribution.empty:
        max_dead = int(df_distribution["dead_spells"].max())
    else:
        max_dead = 0

    # Build the domain for dead spells bars (excluding 0) in ascending order.
    dead_domain = list(range(1, max_dead + 1))

    # Distribution chart
    distribution_chart = (
        alt.Chart(df_distribution)
        .transform_joinaggregate(
            total_simulations='sum(frequency)',
            groupby=['turn_label']
        )
        .transform_calculate(
            percent='datum.frequency / datum.total_simulations'
        )
        .transform_filter("datum.dead_spells > 0")
        .mark_bar()
        .encode(
            x=alt.X("turn_label:N",
                    scale=alt.Scale(domain=turn_sort),
                    title="Draw step"),
            y=alt.Y("percent:Q",
                    title="Percent of simulations",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format='%')),
            color=alt.Color("dead_spells:O",
                            title="Dead spells",
                            scale=alt.Scale(domain=dead_domain,
                                            scheme="magma",
                                            reverse=False)),
            order=alt.Order("dead_spells:Q", sort="descending")
        )
        .properties(
            width=plot_width,
            height=plot_height,
            title="Percent of simulations with a number of dead spells"
        )
    )

    # Bottom chart: fraction of times each color is 'best' to add
    df_colordist = df_summary.copy()
    rename_map = {f"pct_optimal_{c}": c for c in CANONICAL_COLORS}
    df_colordist.rename(columns=rename_map, inplace=True)

    bottom_chart = (
        alt.Chart(df_colordist)
        .transform_fold(
            CANONICAL_COLORS,
            as_=["color_type", "pct"]
        )
        .mark_line()
        .encode(
            x=alt.X("turn_label:N",
                    scale=alt.Scale(domain=turn_sort),
                    title="Draw step"),
            y=alt.Y("pct:Q",
                    title="Percent of simulations",
                    axis=alt.Axis(format="%")),
            color=alt.Color("color_type:N",
                            scale=alt.Scale(
                                domain=CANONICAL_COLORS,
                                range=CANONICAL_COLOR_VALUES
                            ),
                            legend=alt.Legend(title="Mana"))
        )
        .properties(
            width=plot_width,
            height=plot_height,
            title="Percent of simulations where an extra pip of each color is optimal"
        )
    )

    # Concatenate vertically
    combined_chart = alt.vconcat(distribution_chart, bottom_chart)
    combined_chart = combined_chart.resolve_scale(color="independent", x="shared")

    return combined_chart
