import itertools
import random
from collections import Counter

import pandas as pd

from .audit import SimulationAuditRecord
from .cost_parser import CANONICAL_COLORS
from .models import Card, Deck


def build_deck_from_dict(deck_dict: dict[str, tuple[str, int]], total_deck_size: int = 40) -> Deck:
    """
    Given a dictionary of {card_name: (mana_string, quantity)}, build and return a Deck object.

    :param deck_dict: Maps each card's display name to a (mana_string, quantity) tuple.
    :param total_deck_size: The total deck size, including fillers if the deck has fewer
                            actual cards.
    :return: A Deck instance.
    """
    cards: list[Card] = []
    uid_counter = 0  # CHANGED: to assign a unique uid to each card instance

    for display_name, (mana_str, qty) in deck_dict.items():
        for _ in range(qty):
            c = Card(mana_str, display_name=display_name)
            c.uid = uid_counter  # CHANGED
            uid_counter += 1
            cards.append(c)

    return Deck(cards, total_deck_size)


def _all_possible_color_combinations(mana_cards: list[Card]) -> itertools.product:
    """
    For a given list of mana-producing cards, yield all possible ways
    to pick exactly one color from each mana-producing card.

    :param mana_cards: A list of cards capable of producing mana.
    :return: An iterator of tuples, where each tuple is one choice of colors
             (one color per card).
    """
    return itertools.product(*(c.producible_colors for c in mana_cards))


def _can_cast_with_sources(spell: Card, sources: list[Card], lands_playable: int) -> bool:
    """
    Check if `spell` can be cast given the available `sources` and the limit of
    `lands_playable` (the total number of mana you can use this turn).

    Each land (or mana-producer) can produce exactly one unit of mana per turn,
    potentially in one of several colors if it has multiple color options.

    :param spell: The card we want to check if we can cast.
    :param sources: A list of cards that can produce mana (including lands).
    :param lands_playable: The maximum number of sources we can use this turn.
    :return: True if we can assemble enough colored and generic mana to cast the spell
             False otherwise.
    """
    needed_total = spell.cost_uncolored + sum(spell.cost_colors.values())
    if needed_total > lands_playable or not sources:
        return False

    max_subset_size = min(lands_playable, len(sources))
    indices = range(len(sources))

    for subset_size in range(needed_total, max_subset_size + 1):
        for subset_indices in itertools.combinations(indices, subset_size):
            subset = [sources[i] for i in subset_indices]
            # Try every possible color combination for these sources:
            for combo_tuple in _all_possible_color_combinations(subset):
                combo_count = Counter(combo_tuple)
                # Do we meet each colored pip requirement?
                if all(combo_count[col] >= spell.cost_colors[col] for col in spell.cost_colors):
                    # Next, ensure leftover "generic mana" covers the uncolored cost:
                    color_pips_used = sum(spell.cost_colors[c] for c in spell.cost_colors)
                    leftover = subset_size - color_pips_used
                    if leftover >= spell.cost_uncolored:
                        return True
    return False


def _simulate_single_run(
    deck_dict: dict[str, tuple[str, int]],
    total_deck_size: int,
    initial_hand_size: int,
    draws: int,
    on_play: bool,
    record_audit: bool = False,
) -> tuple[list[list[int]], list[list[dict[str, int]]], list[dict[str, int]]]:
    """
    Perform one run of the simulation (i.e., one set of draws across N turns).
    Returns (dead_counts_per_turn, missing_color_tallies, delay_records, audit_record or None).

    :param deck_dict: The deck specification as {card_name: (mana_string, quantity)}.
    :param total_deck_size: Total size of the deck.
    :param initial_hand_size: The number of cards drawn at the start of the game.
    :param draws: The number of turns to simulate (beyond the initial turn).
    :param on_play: Whether we are on the play (True) or on the draw (False).
    :return: A tuple of:
        - dead_counts_per_turn: A list of lists of integer dead-spell counts.
        - missing_color_tallies: A list of lists of dicts that track color shortfalls per turn.
        - delay_records: A list of dicts, each with {"card_name": ..., "delay": ...}.
        - audit_record or None: An audit record if this run was selected for auditing.
    """
    deck = build_deck_from_dict(deck_dict, total_deck_size)
    deck.shuffle()

    hand: list[Card] = []
    dead_counts_per_turn: list[list[int]] = [[] for _ in range(draws)]
    missing_color_tallies: list[list[dict[str, int]]] = [[] for _ in range(draws)]
    delay_records: list[dict[str, int]] = []

    audit_record = SimulationAuditRecord(pass_index=-1) if record_audit else None

    # Draw initial hand
    for _ in range(initial_hand_size):
        if deck.cards:
            card = deck.cards.pop(0)
            if card is not None:
                card.draw_turn = 1
            hand.append(card)

    persisted_mana_producers: list[Card] = []
    persisted_castable_spells: set[Card] = set()

    for turn in range(1, draws + 1):
        # Extra draw if turn=1 and not on_play
        if turn == 1 and not on_play:
            if deck.cards:
                card = deck.cards.pop(0)
                if card is not None:
                    card.draw_turn = turn
                hand.append(card)
        # Otherwise, from turn=2 onward, always draw one
        elif turn > 1:
            if deck.cards:
                card = deck.cards.pop(0)
                if card is not None:
                    card.draw_turn = turn
                hand.append(card)

        # Limit on how many lands (or sources) can be used this turn
        lands_playable = turn

        available_sources = persisted_mana_producers + [c for c in hand if c and c.is_land]

        dead_count = 0
        missing_color_counts = {col: 0 for col in CANONICAL_COLORS}

        # CHANGED: Once a spell is in persisted_castable_spells, ensure it's castable this turn, too
        for c in hand:
            if c is not None:
                if (c in persisted_castable_spells) or (c in persisted_mana_producers) or c.is_land:
                    c.is_castable_this_turn = True
                else:
                    c.is_castable_this_turn = False

        for c in hand:
            if c is None:
                continue

            # If it’s already land or known castable, skip the dead-check
            if c.is_land or c.is_castable_this_turn:
                continue

            # Otherwise, see if we can newly cast it:
            total_cost = c.cost_uncolored + sum(c.cost_colors.values())
            if total_cost > lands_playable:
                dead_count += 1
                continue

            if _can_cast_with_sources(c, available_sources, lands_playable):
                # The spell becomes castable
                c.is_castable_this_turn = True
                delay = turn - getattr(c, "draw_turn", turn)
                delay_records.append({"card_name": c.display_name, "delay": delay})
                persisted_castable_spells.add(c)
                # If it produces mana, keep track of it in both sets
                if c.can_produce_mana:
                    persisted_mana_producers.append(c)
            else:
                # Spell is dead for this turn
                dead_count += 1

                # Tally color shortfalls
                source_color_counts = Counter()
                for src in available_sources:
                    for col in src.producible_colors:
                        source_color_counts[col] += 1
                for col in c.cost_colors:
                    needed_pips = c.cost_colors[col]
                    if source_color_counts[col] < needed_pips:
                        missing_color_counts[col] += 1

        dead_counts_per_turn[turn - 1].append(dead_count)
        missing_color_tallies[turn - 1].append(missing_color_counts)

        if record_audit and audit_record:
            audit_record.record_turn_state(turn, hand)

    # After final turn, for spells never castable
    for c in hand:
        if c is not None and not c.is_land and c not in persisted_castable_spells:
            delay_records.append({"card_name": c.display_name, "delay": draws})

    return dead_counts_per_turn, missing_color_tallies, delay_records, audit_record


def _build_summary_tables(
    dead_counts_runs: list[list[list[int]]],
    missing_color_runs: list[list[list[dict[str, int]]]],
    delay_records_all: list[list[dict[str, int]]],
    draws: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Aggregate results across all runs into three DataFrames:
      1) df_summary: aggregated stats per turn (including p_dead, average missing colors).
      2) df_distribution: distribution of "dead spells" counts per turn.
      3) df_delay: rows of (card_name, delay).

    :param dead_counts_runs: A list of length `simulations`, where each element is
                             a list of length `draws` with dead-spell counts.
    :param missing_color_runs: Same shape as dead_counts_runs, but each item is
                               a dict of color shortfalls.
    :param delay_records_all: A list of lists, each sub-list is the delay_records for one run.
    :param draws: The number of turns simulated.
    :return: (df_summary, df_distribution, df_delay).
    """

    # 1) Build summary stats (p_dead and avg_missing) per turn
    rows_summary = []
    for turn_idx in range(draws):
        # Flatten across runs
        turn_dead_lists = [run[turn_idx] for run in dead_counts_runs]  # each run is a list of ints
        all_dead_values = []
        for dlist in turn_dead_lists:
            all_dead_values.extend(dlist)  # but we actually have only one value per run anyway
        total_sims = float(len(all_dead_values))
        count_ge1 = sum(1 for d in all_dead_values if d >= 1)
        p_dead = count_ge1 / total_sims if total_sims > 0 else 0

        # Combine color tallies
        turn_color_dicts = [run[turn_idx] for run in missing_color_runs]
        all_color_counts = []
        for mclist in turn_color_dicts:
            all_color_counts.extend(mclist)

        color_sums = Counter()
        for cdict in all_color_counts:
            color_sums.update(cdict)

        avg_missing = {
            col: (color_sums[col] / total_sims) if total_sims > 0 else 0 for col in CANONICAL_COLORS
        }

        row = {
            "turn": turn_idx + 1,
            "turn_label": str(turn_idx + 1),
            "p_dead": p_dead,
        }
        for c in CANONICAL_COLORS:
            row[f"avg_missing_{c}"] = avg_missing[c]
        rows_summary.append(row)

    df_summary = pd.DataFrame(rows_summary)

    # 2) Distribution of "dead spells" counts per turn
    # We combine all runs into a single distribution
    distribution_rows = []
    for turn_idx in range(draws):
        # For each run, we have exactly one dead_count for that turn -> a list of lists
        # But we only used dead_counts_per_turn[turn_idx][0] in the original code
        # so each sub-list is length=1. We'll handle it in a more general way anyway.
        freq_counter = Counter()
        for run in dead_counts_runs:
            for dead_val in run[turn_idx]:
                freq_counter[dead_val] += 1

        for dead_val, freq in freq_counter.items():
            distribution_rows.append(
                {
                    "turn": turn_idx + 1,
                    "turn_label": str(turn_idx + 1),
                    "dead_spells": dead_val,
                    "frequency": freq,
                }
            )

    df_distribution = pd.DataFrame(distribution_rows)

    # 3) Delay DataFrame (flat list of all records from all runs)
    all_delay_records = []
    for run_delays in delay_records_all:
        all_delay_records.extend(run_delays)

    df_delay = pd.DataFrame(all_delay_records)

    return df_summary, df_distribution, df_delay


def run_simulation_all(
    deck_dict: dict[str, tuple[str, int]],
    total_deck_size: int = 40,
    initial_hand_size: int = 7,
    draws: int = 10,
    simulations: int = 100_000,
    seed: int | None = None,
    on_play: bool = True,
    audit_pass_indices: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Unified simulation:
     - Count dead spells & color shortfalls
     - Track delay (turns spent uncastable)
     - Optionally collect audit data for certain pass indices

    Returns four DataFrames:
      - df_summary: aggregated stats per turn (p_dead and average missing color).
      - df_distribution: distribution of dead-spell counts per turn (e.g., 0,1,2,...).
      - df_delay: (card_name, delay) for each card that eventually became castable,
                  representing how many turns it spent in hand before first becoming castable.
      - df_audit: detailed per-turn data for a subset of simulation passes.
    :param deck_dict: A dict mapping card_name -> (mana_string, quantity).
    :param total_deck_size: The total number of cards in the deck (including filler if needed).
    :param initial_hand_size: How many cards are drawn in your opening hand.
    :param draws: Number of turns to simulate.
    :param simulations: How many times to run the entire simulation.
    :param seed: Optional RNG seed for reproducibility.
    :param on_play: If True, simulates "on the play"; if False, "on the draw".
    :return: (df_summary, df_distribution, df_delay, df_audit)
    """
    if seed is not None:
        random.seed(seed)

    # We store the per-run results in lists, then combine them at the end.
    dead_counts_runs: list[list[list[int]]] = []
    missing_color_runs: list[list[list[dict[str, int]]]] = []
    delay_records_all: list[list[dict[str, int]]] = []

    audit_data = {}

    for pass_idx in range(simulations):
        record_audit = audit_pass_indices is not None and pass_idx in audit_pass_indices

        (
            dead_counts_per_turn,
            missing_color_tallies,
            delay_records,
            audit_record,
        ) = _simulate_single_run(
            deck_dict=deck_dict,
            total_deck_size=total_deck_size,
            initial_hand_size=initial_hand_size,
            draws=draws,
            on_play=on_play,
            record_audit=record_audit,
        )

        if record_audit and audit_record is not None:
            audit_record.pass_index = pass_idx
            audit_data[pass_idx] = audit_record.to_dict()

        dead_counts_runs.append(dead_counts_per_turn)
        missing_color_runs.append(missing_color_tallies)
        delay_records_all.append(delay_records)

    # Build and return final DataFrames summarizing all runs
    df_summary, df_distribution, df_delay = _build_summary_tables(
        dead_counts_runs, missing_color_runs, delay_records_all, draws
    )

    return df_summary, df_distribution, df_delay, audit_data
