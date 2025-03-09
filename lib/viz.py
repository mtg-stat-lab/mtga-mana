from abc import ABC, abstractmethod

import altair as alt
import pandas as pd

from .cost_parser import CANONICAL_COLOR_VALUES, CANONICAL_COLORS


class BaseChart(ABC):
    """
    Abstract base class for Altair charts in this app.
    Each chart class should:
      - store references to the relevant data
      - implement `render_spec` which returns the Altair JSON spec (as a Python dict)
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    @abstractmethod
    def render_spec(self) -> dict:
        pass


class DistributionChart(BaseChart):
    """
    Creates a bar chart of how often each number of dead spells occurs per turn,
    ignoring the case of 0 dead spells.
    """

    def render_spec(self) -> dict:
        if self.df.empty:
            chart = alt.Chart(pd.DataFrame({"No Data": []})).mark_text(text="No data to show.")
            return chart.to_dict()

        max_turn = int(self.df["turn"].max())
        turn_sort = [str(i) for i in range(1, max_turn + 1)]

        chart = (
            alt.Chart(self.df)
            .transform_joinaggregate(total_simulations="sum(frequency)", groupby=["turn_label"])
            .transform_calculate(percent="datum.frequency / datum.total_simulations")
            .transform_filter("datum.dead_spells > 0")
            .mark_bar()
            .encode(
                x=alt.X(
                    "turn_label:N",
                    title="Turn number",
                    scale=alt.Scale(domain=turn_sort),
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "percent:Q",
                    title="Percent of simulations",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%"),
                ),
                color=alt.Color(
                    "dead_spells:O",
                    title="Dead spells",
                    scale=alt.Scale(scheme="magma", reverse=False),
                ),
                order=alt.Order("dead_spells:Q", sort="descending"),
            )
            .properties(width=500, height=300)
            .configure(background="transparent")
            .configure_view(stroke=None)
        )
        return chart.to_dict()


class MissingColorChart(BaseChart):
    def render_spec(self) -> dict:
        if self.df.empty:
            chart = alt.Chart(pd.DataFrame({"No Data": []})).mark_text(text="No data to show.")
            return chart.to_dict()

        rename_map = {}
        for c in CANONICAL_COLORS:
            rename_map[f"avg_missing_{c}"] = c

        df_copy = self.df.copy()
        df_copy.rename(columns=rename_map, inplace=True)

        max_turn = int(df_copy["turn"].max())
        turn_sort = [str(i) for i in range(1, max_turn + 1)]

        chart = (
            alt.Chart(df_copy)
            .transform_fold(CANONICAL_COLORS, as_=["color_type", "avg_missing"])
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "turn_label:N",
                    scale=alt.Scale(domain=turn_sort),
                    axis=alt.Axis(labelAngle=0),
                    title="Turn number",
                ),
                y=alt.Y("avg_missing:Q", title="Avg # of spells dead due to missing color"),
                color=alt.Color(
                    "color_type:N",
                    scale=alt.Scale(domain=CANONICAL_COLORS, range=CANONICAL_COLOR_VALUES),
                    legend=alt.Legend(title="Color"),
                ),
                tooltip=[
                    alt.Tooltip("turn_label:N", title="Turn"),
                    alt.Tooltip("color_type:N", title="Color"),
                    alt.Tooltip("avg_missing:Q", title="Avg. missing spells", format=".2f"),
                ],
            )
            .properties(width=500, height=300)
            .configure(background="transparent")
            .configure_view(stroke=None)
        )
        return chart.to_dict()


def get_card_color(card_str: str) -> str:
    """
    Determine the color for a card. If the card is mono-colored, return its mapped color.
    If multi-colored, return 'slategray'.
    """
    clean = card_str.lstrip(">")
    colors = set(ch for ch in clean if ch in CANONICAL_COLORS)
    if len(colors) == 1:
        mapping = {"W": "grey", "U": "blue", "B": "black", "R": "red", "G": "green"}
        return mapping[list(colors)[0]]
    else:
        return "slategray"


class SpellDelayChart(BaseChart):
    """
    Creates a three-part, horizontally concatenated chart:
      1) A "cost chart" on the left, showing the mana cost as circles/pips.
      2) A "copies chart" in the middle, showing "xN" if a card has multiple copies.
      3) A bubble chart on the right, showing how frequently a card is delayed X turns
         (with bubble area = % of times drawn that it is delayed that many turns).
    """

    def __init__(self, df_delay: pd.DataFrame, df_cost: pd.DataFrame):
        self.df_delay = df_delay
        self.df_cost = df_cost

    def render_spec(self) -> dict:
        # --------------------------------------------------
        # 1) PREPARE THE DELAY DISTRIBUTION (% rather than raw count)
        # --------------------------------------------------
        # Exclude land rows from consideration
        df_delay = self.df_delay[~self.df_delay["card_name"].str.startswith(">")].copy()

        # Count how many times each (card_name, delay) occurs
        aggregated = df_delay.groupby(["card_name", "delay"]).size().reset_index(name="count")

        # Count total appearances for each card_name
        df_appearances = df_delay.groupby("card_name").size().reset_index(name="total_appearances")

        # Merge to compute fraction = count / total_appearances
        aggregated = aggregated.merge(df_appearances, on="card_name", how="left")
        aggregated["frac"] = aggregated["count"] / aggregated["total_appearances"]
        aggregated["pct"] = aggregated["frac"] * 100

        # For sorting the Y-axis by descending expected delay
        expected = df_delay.groupby("card_name")["delay"].mean().reset_index(name="expected_dead")
        ordering = expected.sort_values("expected_dead", ascending=False)["card_name"].tolist()

        # Determine the max delay to help set chart width
        max_delay = aggregated["delay"].max() if not aggregated.empty else 0

        # --------------------------------------------------
        # 2) BUBBLE CHART (using % for bubble size)
        # --------------------------------------------------

        bubble = (
            alt.Chart(aggregated)
            .mark_circle()
            .encode(
                x=alt.X(
                    "delay:Q",
                    title="Turns Dead in Hand",
                    axis=alt.Axis(
                        labelExpr=f"datum.value === {max_delay} ? '{max_delay}+' : datum.value"
                    ),
                ),
                y=alt.Y("card_name:N", title=None, sort=ordering, axis=None),
                size=alt.Size(
                    "pct:Q",
                    title="% of times dead",
                    # Adjust the range to taste so big percentages are more visible
                    scale=alt.Scale(range=[10, 1000]),
                ),
                tooltip=[
                    alt.Tooltip("card_name:N", title="Card"),
                    alt.Tooltip("delay:Q", title="Delay (turns)"),
                    alt.Tooltip("frac:Q", title="% of appearances", format=".1%"),
                ],
                color=alt.value("#4682B4"),  # If you want a fixed color
            )
        )

        # --------------------------------------------------
        # 3) COST CHART (left side, unchanged from your original approach)
        #    We just replicate your existing logic to show pips
        # --------------------------------------------------
        df_cost = self.df_cost.copy()

        # Build a long form for cost pips
        cost_long_rows = []
        for _, row in df_cost.iterrows():
            card_name = row["card_name"]
            pos = 0
            if row["generic"] > 0:
                cost_long_rows.append(
                    {
                        "card_name": card_name,
                        "cost_type": "generic",
                        "value": row["generic"],
                        "position": pos,
                    }
                )
                pos += 1
            for color in CANONICAL_COLORS:
                count = row[color]
                for i in range(int(count)):
                    cost_long_rows.append(
                        {
                            "card_name": card_name,
                            "cost_type": color,
                            "value": 1,
                            "position": pos,
                        }
                    )
                    pos += 1

        df_cost_long = pd.DataFrame(cost_long_rows)

        cost_color_mapping = {
            "generic": "lightgrey",
            "W": "grey",
            "U": "blue",
            "B": "black",
            "R": "red",
            "G": "green",
        }

        # Circles for the pips
        cost_chart = (
            alt.Chart(df_cost_long)
            .mark_circle(size=150, stroke="darkgrey", strokeWidth=1)
            .encode(
                x=alt.X("position:Q", axis=None),
                y=alt.Y(
                    "card_name:N",
                    title=None,
                    sort=ordering,
                    axis=alt.Axis(grid=False, domain=False, ticks=False, labelPadding=10),
                ),
                color=alt.Color(
                    "cost_type:N",
                    scale=alt.Scale(
                        domain=["generic"] + CANONICAL_COLORS,
                        range=[cost_color_mapping["generic"]]
                        + [cost_color_mapping[c] for c in CANONICAL_COLORS],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("card_name:N", title="Card"),
                    alt.Tooltip("cost_type:N", title="Cost type"),
                    alt.Tooltip("value:Q", title="Value"),
                ],
            )
        )

        # Text for generic cost
        cost_text = (
            alt.Chart(df_cost_long)
            .mark_text(color="black", opacity=0.8, size=8, font="monospace", dy=0.5)
            .encode(
                x=alt.X("position:Q", axis=None),
                y=alt.Y("card_name:N", sort=ordering),
                text=alt.condition(
                    alt.datum.cost_type == "generic", alt.Text("value:Q"), alt.value("")
                ),
            )
        )

        cost_combined = cost_chart + cost_text

        # --------------------------------------------------
        # 4) COPIES CHART (middle). Show "xN" if a card has multiple copies.
        #    We'll produce a single circle + text if decklist has >1 copy,
        #    otherwise no row.
        # --------------------------------------------------

        df_copy_counts = df_cost.copy()[["card_name", "count"]].rename(
            columns={"count": "num_copies"}
        )

        # Filter to only those > 1
        df_copy_counts = df_copy_counts[df_copy_counts["num_copies"] > 1].copy()
        df_copy_counts["label"] = "x" + df_copy_counts["num_copies"].astype(str)
        df_copy_counts["position"] = 0  # We'll just place them at x=0

        # Filter to only those in the df_cost_long (as having some mana cost, e.g., not lands)
        mana_cost_cards = set(df_cost_long["card_name"])
        df_copy_counts = df_copy_counts[df_copy_counts["card_name"].isin(mana_cost_cards)]

        # Text
        copy_text = (
            alt.Chart(df_copy_counts)
            .mark_text(color="black", opacity=0.9, size=10, font="monospace")
            .encode(
                x=alt.X("position:Q", axis=None),
                y=alt.Y(
                    "card_name:N",
                    title=None,
                    sort=ordering,
                    axis=None,
                ),
                text="label:N",
            )
        )

        # --------------------------------------------------
        # 5) SIZE AND CONCATENATE THE THREE CHARTS
        # --------------------------------------------------
        # Determine dynamic sizing
        num_cards = len(ordering)
        row_height = 30
        chart_height = num_cards * row_height

        if not df_cost_long.empty:
            max_pips = df_cost_long.groupby("card_name")["position"].max().max() + 1
        else:
            max_pips = 0

        col_width = 10
        left_chart_width = max_pips * col_width

        copy_chart_width = 40
        turn_width = 30
        bubble_chart_width = (max_delay + 1) * turn_width

        cost_combined = cost_combined.properties(width=left_chart_width, height=chart_height)
        copy_text = copy_text.properties(width=copy_chart_width, height=chart_height)
        bubble = bubble.properties(width=bubble_chart_width, height=chart_height)

        # Concat horizontally, sharing the Y scale
        final_chart = (
            alt.hconcat(cost_combined, copy_text, bubble, spacing=-10)
            .resolve_scale(y="shared")
            .configure(background="transparent")
            .configure_view(stroke=None)
        )

        return final_chart.to_dict()
