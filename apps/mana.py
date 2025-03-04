import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template_string, request
import json
import altair as alt
import pandas as pd
from lib.mana import run_simulation, create_altair_charts

app = Flask(__name__)

FORM_HTML = '''
<!doctype html>
<html>
<head>
    <title>Mana Simulation Form</title>
</head>
<body>
    <h1>Enter Simulation Parameters</h1>
    <form method="post">
        <label for="deck_size">Deck Size:</label>
        <input type="number" id="deck_size" name="deck_size" value="40" required>
        <br><br>
        <label for="hand_size">Initial Hand Size:</label>
        <input type="number" id="hand_size" name="hand_size" value="7" required>
        <br><br>
        <label for="draws">Number of Draw Steps:</label>
        <input type="number" id="draws" name="draws" value="10" required>
        <br><br>
        <label for="simulations">Number of Simulations:</label>
        <input type="number" id="simulations" name="simulations" value="10000" required>
        <br><br>
        <label for="seed">Random Seed:</label>
        <input type="number" id="seed" name="seed" value="42" required>
        <br><br>
        <label for="spells_json">Spells (JSON):</label><br>
        <textarea id="spells_json" name="spells_json" rows="5" cols="50">
{
    "U": 6,
    "B": 5,
    "W": 4,
    "WB": 1,
    "UB": 1,
    "WU": 1
}
        </textarea>
        <br><br>
        <label for="mana_json">Mana (JSON):</label><br>
        <textarea id="mana_json" name="mana_json" rows="5" cols="50">
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
        <br><br>
        <input type="submit" value="Run Simulation">
    </form>
</body>
</html>
'''

RESULT_HTML = '''
<!doctype html>
<html>
<head>
    <title>Mana Simulation Result</title>
</head>
<body>
    <h1>Simulation Chart Result</h1>
    <div>{{ chart|safe }}</div>
    <br>
    <a href="/">Back</a>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            deck_size = int(request.form['deck_size'])
            hand_size = int(request.form['hand_size'])
            draws = int(request.form['draws'])
            simulations = int(request.form['simulations'])
            seed = int(request.form['seed'])
            spells_json = request.form['spells_json']
            mana_json = request.form['mana_json']
            spells_dict = json.loads(spells_json)
            mana_dict = json.loads(mana_json)
        except Exception as e:
            return f"Invalid input: {e}"

        # Run the simulation using the provided parameters.
        # Note: This assumes that run_simulation now accepts an extra parameter "initial_hand_size".
        df_results = run_simulation(
            spells_dict,
            mana_dict,
            total_deck_size=deck_size,
            draws=draws,
            simulations=simulations,
            seed=seed,
            initial_hand_size=hand_size  # Make sure your library supports this parameter.
        )
        
        chart = create_altair_charts(df_results)
        chart_html = chart.to_html()
        return render_template_string(RESULT_HTML, chart=chart_html)
    return render_template_string(FORM_HTML)

if __name__ == '__main__':
    app.run(debug=True, port=5001)