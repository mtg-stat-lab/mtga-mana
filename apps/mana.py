import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
import json
from lib.mana import run_simulation, create_altair_charts, CANONICAL_COLORS
import numpy as np
import pandas as pd

app = Flask(__name__)

# Calculate the absolute path to the project root
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, template_folder=os.path.join(basedir, "templates"))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.get_json()
        deck_size = int(data['deck_size'])
        hand_size = int(data['hand_size'])
        draws = int(data['draws'])
        simulations = int(data['simulations'])
        seed = int(data['seed'])
        spells_dict = json.loads(data['spells_json'])
        mana_dict = json.loads(data['mana_json'])

        # NEW/UPDATED: parse the on_play_or_draw field
        on_play_or_draw = data.get('on_play_or_draw', 'play')
        on_play = (on_play_or_draw.lower() == 'play')

        # run the simulation
        df_summary, df_distribution, zero_dead_runs_count = run_simulation(
            spells_dict,
            mana_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size,
            on_play=on_play  # pass the boolean
        )

        # Create the Vega-Lite chart
        chart = create_altair_charts(df_summary, df_distribution)
        chart_spec = chart.to_dict()

        # 1) Percent of turns with 0 dead spells
        total_turns = (draws + 1) * simulations
        zero_dead_rows = df_distribution[df_distribution['dead_spells'] == 0]
        num_zero_dead = zero_dead_rows['frequency'].sum()
        pct_turns_zero_dead = num_zero_dead / total_turns

        # 2) Percent of runs with 0 dead spells
        pct_runs_zero_dead = zero_dead_runs_count / simulations

        # 3) Expected number of dead spells per turn
        df_distribution['weighted_dead'] = df_distribution['dead_spells'] * df_distribution['frequency']
        total_dead_spells = df_distribution['weighted_dead'].sum()
        expected_dead_per_turn = total_dead_spells / total_turns

        # 4) Most desired pip color
        color_fractions = {}
        for c in CANONICAL_COLORS:
            frac_sum = df_summary[f"pct_optimal_{c}"].sum()
            color_fractions[c] = frac_sum / (draws + 1)
        most_desired_color = max(color_fractions, key=color_fractions.get)

        # 5) Least desired pip color (restricted to those used in spells)
        used_spell_colors = set()
        for cost_str in spells_dict.keys():
            # We won't parse the cost string fully here. Just check letters W/U/B/R/G.
            # A robust approach is to parse fully, but let's keep it short:
            for ch in cost_str:
                if ch in CANONICAL_COLORS:
                    used_spell_colors.add(ch)

        if used_spell_colors:
            least_desired_color = min(used_spell_colors, key=lambda c: color_fractions[c])
        else:
            least_desired_color = "N/A"

        stats = {
            "pct_turns_zero_dead": pct_turns_zero_dead,
            "pct_runs_zero_dead": pct_runs_zero_dead,
            "expected_dead_per_turn": expected_dead_per_turn,
            "most_desired_color": most_desired_color,
            "least_desired_color": least_desired_color
        }

        return jsonify({
            'chart_spec': chart_spec,
            'stats': stats
        })

    except Exception as e:
        print("Error in /simulate:", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    default_port = 5001  # Use 5001 by default
    port = int(os.environ.get('PORT', default_port))
    app.run(host='0.0.0.0', port=port)
