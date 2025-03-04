import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template_string, request, jsonify
import json
import altair as alt
import pandas as pd
from lib.mana import run_simulation, create_altair_charts

app = Flask(__name__)

INDEX_HTML = '''
<!doctype html>
<html>
<head>
    <title>Mana Simulation</title>
    <!-- Include Vega, Vega-Lite, and vega-embed libraries -->
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { display: flex; }
        .form-container { width: 40%; }
        .result-container { width: 60%; padding-left: 20px; }
        input, textarea { width: 100%; padding: 8px; margin: 4px 0 10px 0; box-sizing: border-box; }
        textarea { height: 180px; }
        label { font-weight: bold; }
        button { padding: 10px 20px; }
        #loading { display: none; font-style: italic; color: #555; }
    </style>
</head>
<body>
    <h1>Mana Simulation</h1>
    <div class="container">
        <div class="form-container">
            <form id="simulation-form">
                <label for="deck_size">Deck Size:</label>
                <input type="number" id="deck_size" name="deck_size" value="40" required>
                
                <label for="hand_size">Initial Hand Size:</label>
                <input type="number" id="hand_size" name="hand_size" value="7" required>
                
                <label for="draws">Number of Draw Steps:</label>
                <input type="number" id="draws" name="draws" value="10" required>
                
                <label for="simulations">Number of Simulations:</label>
                <input type="number" id="simulations" name="simulations" value="10000" required>
                
                <label for="seed">Random Seed:</label>
                <input type="number" id="seed" name="seed" value="42" required>
                
                <label for="spells_json">Spells (JSON):</label>
                <textarea id="spells_json" name="spells_json">
{
    "U": 6,
    "B": 5,
    "W": 4,
    "WB": 1,
    "UB": 1,
    "WU": 1
}
                </textarea>
                
                <label for="mana_json">Mana (JSON):</label>
                <textarea id="mana_json" name="mana_json">
{
    "U": 5,
    "B": 4,
    "W": 4,
    "UB": 1,
    "WB": 1,
    "WU": 1,
    "WUBRG": 1
}
                </textarea>
                
                <button type="submit">Run Simulation</button>
            </form>
            <p id="loading">Running simulation, please wait...</p>
        </div>
        <div class="result-container">
            <div id="chart-result">
                <!-- The simulation chart will appear here -->
            </div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('simulation-form');
        const loading = document.getElementById('loading');
        const resultContainer = document.getElementById('chart-result');
        
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            loading.style.display = 'block';
            resultContainer.innerHTML = '';
            
            // Collect form data into a JSON object.
            const formData = new FormData(form);
            const data = {};
            formData.forEach((value, key) => {
                data[key] = value;
            });
            
            // Post the form data to our /simulate endpoint.
            fetch('/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(json => {
                loading.style.display = 'none';
                if (json.error) {
                    resultContainer.innerHTML = 'Error: ' + json.error;
                } else {
                    // Embed the chart using the returned Vega-Lite spec
                    vegaEmbed('#chart-result', json.chart_spec);
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                resultContainer.innerHTML = 'Error: ' + error;
            });
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

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
    app.run(debug=True, port=5001)
