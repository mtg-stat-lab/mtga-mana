import random
import itertools
import re
from collections import Counter
import numpy as np
import pandas as pd
import altair as alt

CANONICAL_COLORS = ['W', 'U', 'B', 'R', 'G']
CANONICAL_COLOR_VALUES = ['grey', 'blue', 'black', 'red', 'green']

def parse_cost_string(cost_str):
    """
    Parse a cost string like 'U', '3U', '4*', '4*U2W', etc.
    Returns (uncolored_cost, color_costs_dict), where:
      - uncolored_cost is an integer (sum of any digits preceding '*')
      - color_costs_dict is a Counter, e.g. {'U': 1, 'W': 2}
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
    For a list of Mana objects, yield all possible ways
    they could collectively produce mana.
    """
    combos = itertools.product(*(m.producible_colors for m in mana_cards))
    return [Counter(combo) for combo in combos]

def can_cast(spell, mana_cards, lands_playable):
    """
    Check if 'spell' can be cast using up to 'lands_playable' mana cards.
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
                if all(combo_counter[color] >= spell.required_colors[color] for color in spell.required_colors):
                    # Check uncolored (leftover) requirement
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

def _count_dead_spells(hand, turn, on_play):
    """
    Count spells in 'hand' that are uncastable on a given turn,
    considering how many lands you could have played.
    """
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

def _best_single_color_to_add(hand, turn, on_play, colors_to_test=CANONICAL_COLORS):
    """
    Which single-color land would reduce dead spells the most if added to the hand?
    """
    base_dead = _count_dead_spells(hand, turn, on_play)
    color_results = []
    for color in colors_to_test:
        hypothetical_hand = hand + [Mana(color)]
        hypothetical_dead = _count_dead_spells(hypothetical_hand, turn, on_play)
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
                   seed=None,
                   on_play=True):
    """
    Returns:
        - df_summary (stats per turn, including p_dead and best-color picks)
        - df_distribution (distribution of dead spell counts per turn)
    """
    if seed is not None:
        random.seed(seed)

    deck = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)

    dead_counts_per_turn = [[] for _ in range(draws + 1)]
    best_color_counts = [Counter() for _ in range(draws + 1)]

    for _ in range(simulations):
        deck.shuffle()

        for turn in range(draws + 1):
            hand_size = initial_hand_size + turn
            hand = deck.draw_top_n(hand_size)
            dead_count = _count_dead_spells(hand, turn, on_play)
            dead_counts_per_turn[turn].append(dead_count)

            best_color = _best_single_color_to_add(hand, turn, on_play)
            best_color_counts[turn][best_color] += 1

    # Build DataFrames
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

    return df_summary, df_distribution

def create_altair_charts(df_summary, df_distribution):
    plot_width = 600
    plot_height = 300

    max_turn = int(df_summary["turn"].max()) if not df_summary.empty else 0
    turn_sort = ["start"] + [str(i) for i in range(1, max_turn + 1)]

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
                    title="Draw step",
                    scale=alt.Scale(domain=turn_sort)),
            y=alt.Y("percent:Q",
                    title="Percent of simulations",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format='%')),
            color=alt.Color("dead_spells:O",
                            title="Dead spells",
                            scale=alt.Scale(scheme="magma", reverse=False)),
            order=alt.Order("dead_spells:Q", sort="descending")
        )
        .properties(
            width=plot_width,
            height=plot_height,
            title="Percent of simulations with a given number of dead spells"
        )
    )

    # Bottom chart: fraction of times each color is best
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

    combined_chart = alt.vconcat(distribution_chart, bottom_chart)
    combined_chart = combined_chart.resolve_scale(color="independent", x="shared")
    return combined_chart
