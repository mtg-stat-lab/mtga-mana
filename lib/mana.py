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
        self.cost_str: str = cost_str
        self.required_colors: Counter[str] = Counter(cost_str)

    def __repr__(self) -> str:
        return f"Spell(cost='{self.cost_str}')"

class Mana:
    """
    Represents a mana card. For example, 'UB' => can produce either U or B (but only 1 pip).
    'WUBRG' => can produce any of W, U, B, R, G.
    """
    def __init__(self, mana_str: str):
        self.mana_str: str = mana_str
        self.producible_colors: set[str] = set(mana_str)

    def __repr__(self) -> str:
        return f"Mana(mana='{self.mana_str}')"

def all_possible_color_combinations(mana_cards: list[Mana]) -> list[Counter[str]]:
    """
    For a given list of Mana objects, return all possible ways to pick exactly one color
    from each card.
    """
    color_sets = [m.producible_colors for m in mana_cards]
    combos = itertools.product(*color_sets)  # Cartesian product
    combo_counters: list[Counter[str]] = []
    for combo in combos:
        c = Counter(combo)
        combo_counters.append(c)
    return combo_counters

def can_cast(spell: Spell, mana_cards: list[Mana]) -> bool:
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
    Represents a deck of size `total_size`. It can contain:
      - A list of `Spell` objects
      - A list of `Mana` objects
      - Additional slots for "other" cards (filled with None by default).
    """
    def __init__(self, spells: list[Spell], mana_cards: list[Mana], total_size: int = 40):
        self.spells: list[Spell] = spells
        self.mana_cards: list[Mana] = mana_cards
        self.total_size: int = total_size

        # Construct the "physical" deck: a list of all cards (Spell, Mana, or None).
        self.deck_list: list[Spell | Mana | None] = [*spells, *mana_cards]
        leftover = total_size - len(self.deck_list)
        if leftover > 0:
            # Pad with None to represent "other" cards that are never dead (no color cost).
            self.deck_list += [None] * leftover

    def shuffle(self) -> None:
        random.shuffle(self.deck_list)

    def draw_top_n(self, n: int) -> list[Spell | Mana | None]:
        """
        Returns the top `n` cards from the deck (non-destructively).
        """
        return self.deck_list[:n]

    def __len__(self) -> int:
        return len(self.deck_list)

    def __repr__(self) -> str:
        return (f"Deck(size={self.total_size}, spells={len(self.spells)}, "
                f"mana={len(self.mana_cards)}, actual_list_len={len(self.deck_list)})")

def build_deck_from_dicts(spells_dict: dict[str, int],
                          mana_dict: dict[str, int],
                          total_deck_size: int = 40) -> Deck:
    """
    Builds a Deck from dictionaries like:
        spells_dict = {'U': 3, 'B': 5, 'UU': 1, 'UB': 2}
        mana_dict = {'U': 7, 'UB': 2, 'B': 6, 'WUBRG': 1}
    """
    spells: list[Spell] = []
    for cost_str, qty in spells_dict.items():
        for _ in range(qty):
            spells.append(Spell(cost_str))

    mana_cards: list[Mana] = []
    for mana_str, qty in mana_dict.items():
        for _ in range(qty):
            mana_cards.append(Mana(mana_str))

    return Deck(spells, mana_cards, total_deck_size)

def _count_dead_spells(hand: list[Spell | Mana | None]) -> int:
    """
    Given a hand, return how many spells are 'dead'
    (i.e. uncastable given the current mana in that hand).
    """
    hand_spells = [c for c in hand if isinstance(c, Spell)]
    hand_mana   = [c for c in hand if isinstance(c, Mana)]
    dead_count = 0
    for s in hand_spells:
        if not can_cast(s, hand_mana):
            dead_count += 1
    return dead_count

def _best_single_color_to_add(hand: list[Spell | Mana | None],
                              colors_to_test: list[str] = CANONICAL_COLORS) -> str:
    """
    Among the given list of colors, find which single color would reduce
    the number of dead spells the most if we added exactly one Mana(color).
    """
    base_dead = _count_dead_spells(hand)
    color_results: list[tuple[str, int]] = []
    for color in colors_to_test:
        hypothetical_hand = hand + [Mana(color)]
        hypothetical_dead = _count_dead_spells(hypothetical_hand)
        color_results.append((color, hypothetical_dead))
    min_dead = min(cr[1] for cr in color_results)
    if min_dead >= base_dead:
        return "none"
    top_candidates = [cr[0] for cr in color_results if cr[1] == min_dead]
    best_color = random.choice(top_candidates)
    return best_color

def run_simulation(spells_dict: dict[str, int],
                   mana_dict: dict[str, int],
                   total_deck_size: int = 40,
                   initial_hand_size: int = 7,
                   draws: int = 10,
                   simulations: int = 100_000,
                   seed: int | None = None) -> pd.DataFrame:
    """
    Monte Carlo simulation steps:
      1) Build a Deck from spells_dict and mana_dict.
      2) For each simulation:
         - Shuffle the deck.
         - For turn in [0..draws-1]:
           - Draw (7 + turn) cards.
           - Count how many spells are dead.
           - Find which color is best to add (or "none" if not helpful).
      3) Collect distribution of dead spells over all simulations, for each turn.
      4) Compute average dead spells, 80% CI (10th–90th percentile), probability of having ≥1 dead spell,
         and fraction each color was chosen as "best" (including "none").

    Returns a pd.DataFrame with columns:
        - "turn": 0, 1, ..., draws-1
        - "avg_dead_cards", "dead_cards_10p", "dead_cards_90p", "p_dead",
        - "pct_optimal_W", "pct_optimal_U", "pct_optimal_B", "pct_optimal_R", "pct_optimal_G", "pct_optimal_none"
    """
    if seed is not None:
        random.seed(seed)

    deck = build_deck_from_dicts(spells_dict, mana_dict, total_deck_size)
    dead_counts_per_turn: list[list[int]] = [[] for _ in range(draws)]
    best_color_counts: list[Counter[str]] = [Counter() for _ in range(draws)]
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

    rows = []
    for turn in range(draws):
        dead_array = np.array(dead_counts_per_turn[turn])
        avg_dead = float(dead_array.mean())
        low_80 = float(np.percentile(dead_array, 10))
        high_80 = float(np.percentile(dead_array, 90))
        p_dead = float((dead_array >= 1).mean())
        total_sims = float(simulations)
        color_fracs = {
            color: best_color_counts[turn][color] / total_sims
            for color in extended_colors
        }
        row = {
            "turn": turn,
            "avg_dead_cards": avg_dead,
            "dead_cards_10p": low_80,
            "dead_cards_90p": high_80,
            "p_dead": p_dead,
            **{f"pct_optimal_{c}": color_fracs[c] for c in extended_colors}
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df

def create_altair_charts(df):
    """
    Create three stacked Altair charts:
      1) Top chart: Probability of having one or more dead spells (area chart) vs. draw step,
         with an annotation for the average probability.
      2) Middle chart: Average dead spells (solid) plus 10th/90th percentile (dashed) vs. draw step,
         with a legend indicating the 20% (10th percentile), average, and 80% (90th percentile) lines.
      3) Bottom chart: Percent of time each color was optimal, excluding 'none'
         (white displayed as 'grey')
    """

    # Fix column names for canonical colors
    df = df.copy()
    column_names = [f"pct_optimal_{c}" for c in CANONICAL_COLORS]
    df.rename(columns=dict(zip(column_names, CANONICAL_COLORS)), inplace=True)

    plot_width = 600
    plot_height = 200
    slate_gray = "#708090"

    # --- Top Chart: Probability of ≥1 dead spell (area chart) with annotation ---
    prob_chart = alt.Chart(df).mark_area(interpolate="monotone", opacity=0.3, color="red").encode(
        x=alt.X('turn:Q', title='Draw step', axis=alt.Axis(format='d')),
        y=alt.Y(
            'p_dead:Q', 
            title='Probability of ≥1 dead spell', 
            axis=alt.Axis(format='%'),
            scale=alt.Scale(domain=[0, 1])
        )
    ).properties(
        width=plot_width,
        height=plot_height,
        title="Probability of having one or more dead spells"
    )

    # Compute overall average probability and create a text annotation.
    avg_prob = df['p_dead'].mean()  # average probability (0-1)
    avg_label = f"Avg: {avg_prob*100:.1f}%"
    max_turn = df['turn'].max() if not df.empty else 10
    text = alt.Chart(pd.DataFrame({
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
        x=alt.X('turn:Q'),
        y=alt.Y('p_dead:Q'),
        text=alt.Text('label:N')
    )

    prob_chart = prob_chart + text

    # --- Middle Chart: 'Dead' Spells in Hand with Legend ---
    top_chart = alt.Chart(df).transform_fold(
        ['avg_dead_cards', 'dead_cards_10p', 'dead_cards_90p'],
        as_=['metric', 'value']
    ).mark_line().encode(
        x=alt.X('turn:Q', title='Draw step', axis=alt.Axis(format='d')),
        y=alt.Y('value:Q', title="'Dead' spells in hand"),
        color=alt.Color(
            'metric:N',
            scale=alt.Scale(
                domain=['dead_cards_10p', 'avg_dead_cards', 'dead_cards_90p'],
                range=[slate_gray, slate_gray, slate_gray]
            ),
            legend=alt.Legend(
                title="Line Type",
                labelExpr=(
                    "datum.value == 'avg_dead_cards' ? 'Average' : "
                    "datum.value == 'dead_cards_10p' ? '20% line' : '80% line'"
                )
            )
        ),
        strokeDash=alt.StrokeDash(
            'metric:N',
            scale=alt.Scale(
                domain=['dead_cards_10p', 'avg_dead_cards', 'dead_cards_90p'],
                range=[[4, 4], [], [4, 4]]
            ),
            legend=None
        )
    ).properties(
        width=plot_width,
        height=plot_height,
        title="Expected number of 'dead' spells in your hand"
    )

    # --- Bottom Chart: Percent Optimal Color ---
    bottom_chart = (
        alt.Chart(df)
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
                scale=alt.Scale(
                    domain=CANONICAL_COLORS,
                    range=CANONICAL_COLOR_VALUES,
                ),
                legend=alt.Legend(title='Mana')
            )
        )
        .properties(
            width=plot_width,
            height=plot_height,
            title="Percent of time you'll wish you had an extra pip of a given color"
        )
    )

    # Concatenate the three charts vertically.
    combined_chart = alt.vconcat(prob_chart, top_chart, bottom_chart).resolve_scale(color='independent')
    return combined_chart
