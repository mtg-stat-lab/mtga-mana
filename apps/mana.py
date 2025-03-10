# flake8: noqa: E402

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from flask import Flask, jsonify, render_template, request

from lib.audit import pick_audit_passes
from lib.cost_parser import CANONICAL_COLORS, parse_cost_string
from lib.deck import parse_deck_list
from lib.simulator import run_simulation_all
from lib.viz import DistributionChart, MissingColorChart, SpellDelayChart

# Calculate the absolute path to the project root
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, template_folder=os.path.join(basedir, "templates"))

# Load the CSV of card data (ensure the relative path is correct)
csv_path = os.path.join(basedir, "data", "DFT Card Mana - DFT.csv")
df_cards = pd.read_csv(csv_path)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/simulate", methods=["POST"])
def simulate():
    try:
        data = request.get_json()
        deck_size = int(data["deck_size"])
        hand_size = int(data["hand_size"])
        draws = int(data["draws"])
        simulations = int(data["simulations"])
        seed = int(data["seed"])
        on_play_or_draw = data.get("on_play_or_draw", "play").lower()
        on_play = on_play_or_draw == "play"

        # --- Parse deck list from pasted text ---
        deck_list_str = data["deck_list"]
        deck_dict, _ = parse_deck_list(deck_list_str, df_cards)

        cost_rows = []
        for card_name, (mana, count) in deck_dict.items():
            # If the mana string contains '>', extract cost portion before '>' for the cost
            if ">" in mana:
                cost_str = mana.split(">")[0]
            else:
                cost_str = mana
            uncolored, color_costs = parse_cost_string(cost_str)
            row = {"card_name": card_name, "generic": uncolored}
            for c in CANONICAL_COLORS:
                row[c] = color_costs.get(c, 0)
            row["count"] = count
            cost_rows.append(row)

        df_cost = pd.DataFrame(cost_rows)

        # Choose up to 10 passes to audit
        audit_pass_indices = pick_audit_passes(simulations, sample_size=10, seed=seed)

        # --- Run the simulation ---
        df_summary, df_distribution, df_delay, audit_data = run_simulation_all(
            deck_dict=deck_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size,
            on_play=on_play,
            audit_pass_indices=audit_pass_indices,
        )

        # --- Create chart specs ---
        dist_chart_spec = DistributionChart(df_distribution).render_spec()
        missing_color_chart_spec = MissingColorChart(df_summary).render_spec()
        spell_delay_chart_spec = SpellDelayChart(df_delay, df_cost).render_spec()

        # --- Calculate top-level stats ---
        total_turns = draws * simulations  # We measure each turn across all sims
        zero_dead_rows = df_distribution[df_distribution["dead_spells"] == 0]
        num_zero_dead = zero_dead_rows["frequency"].sum()
        pct_turns_zero_dead = num_zero_dead / total_turns if total_turns > 0 else 0

        df_distribution["weighted_dead"] = (
            df_distribution["dead_spells"] * df_distribution["frequency"]
        )
        total_dead_spells = df_distribution["weighted_dead"].sum()
        expected_dead_per_turn = total_dead_spells / total_turns if total_turns > 0 else 0

        stats = {
            "pct_turns_zero_dead": pct_turns_zero_dead,
            "expected_dead_per_turn": expected_dead_per_turn,
        }

        return jsonify(
            {
                "dist_chart_spec": dist_chart_spec,
                "missing_color_chart_spec": missing_color_chart_spec,
                "spell_delay_chart_spec": spell_delay_chart_spec,
                "stats": stats,
                "audit_data": audit_data,
            }
        )

    except Exception as e:
        print("Error in /simulate:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    default_port = 5001
    port = int(os.environ.get("PORT", default_port))
    app.run(host="0.0.0.0", port=port)
