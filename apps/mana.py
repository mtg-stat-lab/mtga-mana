import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
import json
from lib.mana import run_simulation, create_altair_charts

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

        # Run the simulation.
        df_results = run_simulation(
            spells_dict,
            mana_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size
        )
        chart = create_altair_charts(df_results)
        
        # Return the Vega-Lite specification
        chart_spec = chart.to_dict()
        return jsonify({'chart_spec': chart_spec})
    except Exception as e:
        print("Error in /simulate:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    default_port = 5001 # 5000 being used on my mac by something
    port = int(os.environ.get('PORT', default_port))
    app.run(host='0.0.0.0', port=port)