import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
import json
import numpy as np
import pandas as pd
import random

from lib.mana import run_simulation, run_simulation_with_delay, CANONICAL_COLORS
from lib.viz import DistributionChart, BestColorChart, SpellDelayChart
from lib.deck import parse_deck_list  # using deck list parser

# Calculate the absolute path to the project root
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, template_folder=os.path.join(basedir, "templates"))

# Load the CSV of card data (ensure the relative path is correct)
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

        # --- Parse deck list from pasted text ---
        deck_list_str = data['deck_list']  # using deck_list instead of deck_json
        deck_dict, _ = parse_deck_list(deck_list_str, df_cards)  # ignore sideboard

        # Run the simulation for dead spells and best color
        df_summary, df_distribution = run_simulation(
            deck_dict=deck_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size,
            on_play=on_play
        )

        # Create chart specs
        dist_chart_spec = DistributionChart(df_distribution).render_spec()
        best_color_chart_spec = BestColorChart(df_summary).render_spec()

        # Calculate additional statistics
        total_turns = (draws + 1) * simulations
        zero_dead_rows = df_distribution[df_distribution['dead_spells'] == 0]
        num_zero_dead = zero_dead_rows['frequency'].sum()
        pct_turns_zero_dead = num_zero_dead / total_turns if total_turns > 0 else 0

        df_distribution['weighted_dead'] = df_distribution['dead_spells'] * df_distribution['frequency']
        total_dead_spells = df_distribution['weighted_dead'].sum()
        expected_dead_per_turn = total_dead_spells / total_turns if total_turns > 0 else 0

        # Determine "most desired" pip color
        color_fractions = {}
        for c in CANONICAL_COLORS:
            col_name = f"pct_optimal_{c}"
            frac_sum = df_summary[col_name].sum() if col_name in df_summary.columns else 0
            color_fractions[c] = frac_sum / (draws + 1) if draws > 0 else 0
        most_desired_color = max(color_fractions, key=color_fractions.get) if color_fractions else "N/A"

        # Determine "least desired" pip color (among colors used in deck, if any)
        used_spell_colors = set()
        for card_str in deck_dict.keys():
            if card_str.startswith('>'):
                continue
            for ch in card_str:
                if ch in CANONICAL_COLORS:
                    used_spell_colors.add(ch)

        if used_spell_colors:
            least_desired_color = min(used_spell_colors, key=lambda c: color_fractions.get(c, 0))
        else:
            least_desired_color = "N/A"

        stats = {
            "pct_turns_zero_dead": pct_turns_zero_dead,
            "expected_dead_per_turn": expected_dead_per_turn,
            "most_desired_color": most_desired_color,
            "least_desired_color": least_desired_color
        }

        # Run the delay simulation to track when spells become castable.
        df_delay = run_simulation_with_delay(
            deck_dict=deck_dict,
            total_deck_size=deck_size,
            initial_hand_size=hand_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            on_play=on_play
        )
        spell_delay_chart_spec = SpellDelayChart(df_delay).render_spec()

        return jsonify({
            'dist_chart_spec': dist_chart_spec,
            'best_color_chart_spec': best_color_chart_spec,
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
