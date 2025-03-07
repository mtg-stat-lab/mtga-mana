import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
import json
import numpy as np
import pandas as pd

# Import the simulation code (unified approach now)
from lib.mana import run_simulation, CANONICAL_COLORS
# Import the updated chart classes
from lib.viz import DistributionChart, BestColorChart

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

        # 'on_play_or_draw' is optional; default 'play'
        on_play_or_draw = data.get('on_play_or_draw', 'play').lower()
        on_play = (on_play_or_draw == 'play')

        # The user now provides one single deck JSON
        deck_dict = json.loads(data['deck_json'])

        # Run the simulation
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

        # Determine "most desired" color
        color_fractions = {}
        for c in CANONICAL_COLORS:
            col_name = f"pct_optimal_{c}"
            frac_sum = df_summary[col_name].sum() if col_name in df_summary.columns else 0
            color_fractions[c] = frac_sum / (draws + 1) if draws > 0 else 0
        most_desired_color = max(color_fractions, key=color_fractions.get) if color_fractions else "N/A"

        # Determine "least desired" color (among colors used in deck, if any)
        used_spell_colors = set()
        for card_str in deck_dict.keys():
            # We'll parse out the color letters from the cost part only
            # Because something like ">BW" is a land, not a spell requiring B/W.
            # We'll do a naive parse:
            if card_str.startswith('>'):
                # It's a land
                continue
            # If it has a '>' inside, strip off the produce part
            cost_part = card_str.split('>', 1)[0]
            # Gather W/U/B/R/G from cost_part
            for ch in cost_part:
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

        return jsonify({
            'dist_chart_spec': dist_chart_spec,
            'best_color_chart_spec': best_color_chart_spec,
            'stats': stats
        })

    except Exception as e:
        print("Error in /simulate:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    default_port = 5001
    port = int(os.environ.get('PORT', default_port))
    app.run(host='0.0.0.0', port=port)
