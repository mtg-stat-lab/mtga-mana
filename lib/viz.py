from abc import ABC, abstractmethod

import altair as alt
import pandas as pd

from .mana import CANONICAL_COLOR_VALUES, CANONICAL_COLORS


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
        pass

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


class BestColorChart(BaseChart):
    """
    Creates a line chart showing how often switching a land to each color is optimal.
    """

    def render_spec(self) -> dict:
        pass

        if self.df.empty:
            chart = alt.Chart(pd.DataFrame({"No Data": []})).mark_text(text="No data to show.")
            return chart.to_dict()

        max_turn = int(self.df["turn"].max())
        turn_sort = [str(i) for i in range(1, max_turn + 1)]

        rename_map = {f"pct_optimal_{c}": c for c in CANONICAL_COLORS}

        df_colordist = self.df.copy()
        df_colordist.rename(columns=rename_map, inplace=True)

        chart = (
            alt.Chart(df_colordist)
            .transform_fold(CANONICAL_COLORS, as_=["color_type", "pct"])
            .mark_line()
            .encode(
                x=alt.X(
                    "turn_label:N",
                    scale=alt.Scale(domain=turn_sort),
                    axis=alt.Axis(labelAngle=0),
                    title="Turn number",
                ),
                y=alt.Y("pct:Q", title="Percent of simulations", axis=alt.Axis(format="%")),
                color=alt.Color(
                    "color_type:N",
                    scale=alt.Scale(domain=CANONICAL_COLORS, range=CANONICAL_COLOR_VALUES),
                    legend=alt.Legend(title="Mana"),
                ),
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
    Creates a concatenated chart for spell delay.
    Left: a cost chart showing the mana cost as a row of circles.
          The y-axis displays the spell name.
    Right: a bubble chart showing the distribution of dead turns per spell.
           The y-axis labels are hidden so that the spell name appears only on the left.
    Spells are ordered by expected (weighted mean) dead turns descending.
    For generic cost, a single light grey circle shows the total generic cost (with a black number).
    For colored costs, one circle per pip required, using the corresponding color
    with a dark grey outline.
    """

    def __init__(self, df_delay: pd.DataFrame, df_cost: pd.DataFrame):
        self.df_delay = df_delay
        self.df_cost = df_cost

    def render_spec(self) -> dict:
        # Exclude lands for delay data.
        df_delay = self.df_delay[~self.df_delay["card_name"].str.startswith(">")]
        df_cost = self.df_cost.copy()  # assume already filtered upstream

        # Determine ordering by expected dead turns (weighted mean) descending.
        expected = df_delay.groupby("card_name")["delay"].mean().reset_index(name="expected_dead")
        ordering = expected.sort_values("expected_dead", ascending=False)["card_name"].tolist()

        # --- Right Chart: Bubble Chart for Delay Distribution ---
        aggregated = df_delay.groupby(["card_name", "delay"]).size().reset_index(name="count")

        # We'll need the max delay for dynamic right chart width below
        max_delay = aggregated["delay"].max() if len(aggregated) > 0 else 0

        bubble = (
            alt.Chart(aggregated)
            .mark_circle()
            .encode(
                x=alt.X(
                    "delay:Q",
                    title="Turns Dead in Hand",
                    axis=alt.Axis(
                        grid=False,  # no vertical grid lines
                        offset=10,  # add space between x-axis line and marks
                        labelPadding=5,  # space between axis tick labels and the axis line
                    ),
                ),
                y=alt.Y(
                    "card_name:N", title=None, sort=ordering, axis=None
                ),  # hide duplicate spell names
                size=alt.Size("count:Q", title="Frequency", scale=alt.Scale(range=[10, 1000])),
                tooltip=["card_name:N", "delay:Q", "count:Q"],
            )
        )

        # --- Left Chart: Cost Chart for Mana Cost ---
        # Transform cost DataFrame into long format.
        cost_long_rows = []
        for _, row in df_cost.iterrows():
            card_name = row["card_name"]
            pos = 0
            # Add a circle for generic cost if > 0.
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
            # For each colored cost, add one circle per pip.
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

        # We'll need the maximum number of pips for dynamic left chart width
        if not df_cost_long.empty:
            # position is 0-based, so add 1 for total pips
            max_pips = df_cost_long.groupby("card_name")["position"].max().max() + 1
        else:
            max_pips = 0

        # Define cost color mapping.
        cost_color_mapping = {
            "generic": "lightgrey",
            "W": "grey",
            "U": "blue",
            "B": "black",
            "R": "red",
            "G": "green",
        }

        cost_chart = (
            alt.Chart(df_cost_long)
            .mark_circle(size=150, stroke="darkgrey", strokeWidth=1)
            .encode(
                x=alt.X("position:Q", axis=None),
                y=alt.Y(
                    "card_name:N",
                    title=None,
                    sort=ordering,
                    axis=alt.Axis(
                        grid=False,
                        domain=False,
                        ticks=False,  # remove ticks
                        labelPadding=10,  # space between labels and the first pip
                    ),
                ),
                color=alt.Color(
                    "cost_type:N",
                    scale=alt.Scale(
                        domain=["generic"] + CANONICAL_COLORS,
                        range=[cost_color_mapping["generic"]]
                        + [cost_color_mapping[c] for c in CANONICAL_COLORS],
                    ),
                ),
                tooltip=["card_name:N", "cost_type:N", "value:Q"],
            )
        )

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

        # --- Dynamic Sizing ---
        # Height: rows (cards) * row_height
        row_height = 30
        num_cards = len(ordering)
        chart_height = num_cards * row_height

        # Left chart width: max pips * col_width
        col_width = 10
        left_chart_width = max_pips * col_width

        # Right chart width: (max_delay + 1) * turn_width
        turn_width = 30
        right_chart_width = (max_delay + 1) * turn_width

        # Apply the properties with dynamic sizing
        cost_combined = cost_combined.properties(width=left_chart_width, height=chart_height)
        bubble = bubble.properties(width=right_chart_width, height=chart_height)

        # Concatenate horizontally, sharing the y-scale
        concat_chart = alt.hconcat(cost_combined, bubble, spacing=10).resolve_scale(y="shared")

        # Remove outer bounding box
        final_chart = concat_chart.configure(background="transparent").configure_view(stroke=None)

        return final_chart.to_dict()
