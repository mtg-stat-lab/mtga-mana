import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
import json
import numpy as np
import pandas as pd
import random

from lib.mana import (
    run_simulation,
    run_simulation_with_delay,
    CANONICAL_COLORS,
    parse_cost_string
)
from lib.viz import (
    DistributionChart,
    SpellDelayChart,
    MissingColorChart
)
from lib.deck import parse_deck_list

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, template_folder=os.path.join(basedir, "templates"))

csv_path = os.path.join(basedir, "data", "DFT Card Mana - DFT.csv")
df_cards = pd.read_csv(csv_path)

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
        on_play_or_draw = data.get('on_play_or_draw', 'play').lower()
        on_play = (on_play_or_draw == 'play')

        deck_list_str = data['deck_list']
        deck_dict, _ = parse_deck_list(deck_list_str, df_cards)

        cost_rows = []
        for card_name, (mana, count) in deck_dict.items():
            if '>' in mana:
                cost_str = mana.split('>')[0]
            else:
                cost_str = mana
            uncolored, color_costs = parse_cost_string(cost_str)
            row = {"card_name": card_name, "generic": uncolored}
            for c in CANONICAL_COLORS:
                row[c] = color_costs.get(c, 0)
            cost_rows.append(row)

        df_cost = pd.DataFrame(cost_rows)

        df_summary, df_distribution = run_simulation(
            deck_dict=deck_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size,
            on_play=on_play
        )

        dist_chart_spec = DistributionChart(df_distribution).render_spec()
        missing_color_chart_spec = MissingColorChart(df_summary).render_spec()

        total_turns = (draws + 1) * simulations
        zero_dead_rows = df_distribution[df_distribution['dead_spells'] == 0]
        num_zero_dead = zero_dead_rows['frequency'].sum()
        pct_turns_zero_dead = num_zero_dead / total_turns if total_turns > 0 else 0

        df_distribution['weighted_dead'] = df_distribution['dead_spells'] * df_distribution['frequency']
        total_dead_spells = df_distribution['weighted_dead'].sum()
        expected_dead_per_turn = total_dead_spells / total_turns if total_turns > 0 else 0

        stats = {
            "pct_turns_zero_dead": pct_turns_zero_dead,
            "expected_dead_per_turn": expected_dead_per_turn
        }

        df_delay = run_simulation_with_delay(
            deck_dict=deck_dict,
            total_deck_size=deck_size,
            initial_hand_size=hand_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            on_play=on_play
        )
        spell_delay_chart_spec = SpellDelayChart(df_delay, df_cost).render_spec()

        return jsonify({
            'dist_chart_spec': dist_chart_spec,
            'missing_color_chart_spec': missing_color_chart_spec,
            'spell_delay_chart_spec': spell_delay_chart_spec,
            'stats': stats
        })

    except Exception as e:
        print("Error in /simulate:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    default_port = 5001
    port = int(os.environ.get('PORT', default_port))
    app.run(host='0.0.0.0', port=port)
