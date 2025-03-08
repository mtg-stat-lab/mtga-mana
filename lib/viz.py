from abc import ABC, abstractmethod
import altair as alt
import pandas as pd

from .mana import CANONICAL_COLORS, CANONICAL_COLOR_VALUES

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
        plot_width = 600
        plot_height = 300

        if self.df.empty:
            chart = alt.Chart(pd.DataFrame({"No Data": []})).mark_text(text="No data to show.")
            return chart.to_dict()

        max_turn = int(self.df["turn"].max())
        turn_sort = [str(i) for i in range(1, max_turn + 1)]

        chart = (
            alt.Chart(self.df)
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
                x=alt.X(
                    "turn_label:N",
                    title="Turn number",
                    scale=alt.Scale(domain=turn_sort),
                    axis=alt.Axis(labelAngle=0)
                ),
                y=alt.Y(
                    "percent:Q",
                    title="Percent of simulations",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format='%')
                ),
                color=alt.Color(
                    "dead_spells:O",
                    title="Dead spells",
                    scale=alt.Scale(scheme="magma", reverse=False)
                ),
                order=alt.Order("dead_spells:Q", sort="descending")
            )
            .properties(
                width=plot_width,
                height=plot_height
            )
            .configure(background='transparent')
            .configure_view(stroke=None)
        )
        return chart.to_dict()


class BestColorChart(BaseChart):
    """
    Creates a line chart showing how often switching a land to each color is optimal.
    """
    def render_spec(self) -> dict:
        plot_width = 600
        plot_height = 300

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
            .transform_fold(
                CANONICAL_COLORS,
                as_=["color_type", "pct"]
            )
            .mark_line()
            .encode(
                x=alt.X(
                    "turn_label:N",
                    scale=alt.Scale(domain=turn_sort),
                    axis=alt.Axis(labelAngle=0),
                    title="Turn number"
                ),
                y=alt.Y(
                    "pct:Q",
                    title="Percent of simulations",
                    axis=alt.Axis(format='%')
                ),
                color=alt.Color(
                    "color_type:N",
                    scale=alt.Scale(
                        domain=CANONICAL_COLORS,
                        range=CANONICAL_COLOR_VALUES
                    ),
                    legend=alt.Legend(title="Mana")
                )
            )
            .properties(
                width=plot_width,
                height=plot_height
            )
            .configure(background='transparent')
            .configure_view(stroke=None)
        )
        return chart.to_dict()


def get_card_color(card_str: str) -> str:
    """
    Determine the color for a card. If the card is mono-colored, return its mapped color.
    If multi-colored, return 'slategray'.
    """
    clean = card_str.lstrip('>')
    colors = set(ch for ch in clean if ch in CANONICAL_COLORS)
    if len(colors) == 1:
        mapping = {'W': 'grey', 'U': 'blue', 'B': 'black', 'R': 'red', 'G': 'green'}
        return mapping[list(colors)[0]]
    else:
        return 'slategray'


class SpellDelayChart(BaseChart):
    """
    Creates a bubble chart showing, for each spell (by card name), the distribution of dead turns.
    The y-axis displays the spell name, the x-axis shows the number of turns the spell was dead,
    and the area of each circle is proportional to the frequency (count) of that delay.
    Spells are ordered by their expected (weighted mean) dead turns descending.
    """
    def render_spec(self) -> dict:
        if self.df.empty:
            chart = alt.Chart(pd.DataFrame({"No Data": []})).mark_text(text="No data to show.")
            return chart.to_dict()

        # Aggregate delay data: count occurrences for each (card_name, delay)
        aggregated = self.df.groupby(["card_name", "delay"]).size().reset_index(name="count")
        # Compute expected dead turns per card (weighted mean)
        expected = self.df.groupby("card_name")["delay"].mean().reset_index(name="expected_dead")
        aggregated = aggregated.merge(expected, on="card_name")
        # Order spells by expected_dead descending
        ordered_cards = aggregated.groupby("card_name")["expected_dead"].mean().sort_values(ascending=False).index.tolist()

        chart = alt.Chart(aggregated).mark_circle().encode(
            x=alt.X("delay:Q", title="Turns Dead in Hand"),
            y=alt.Y("card_name:N", title="Spell Name", sort=ordered_cards),
            size=alt.Size("count:Q", title="Frequency", scale=alt.Scale(range=[10, 1000])),
            tooltip=["card_name:N", "delay:Q", "count:Q"]
        ).properties(
            width=300,
            height=400
        ).configure(background='transparent')
        return chart.to_dict()
