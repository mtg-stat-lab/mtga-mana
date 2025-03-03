from flask import Flask, render_template_string, request
import numpy as np
import pandas as pd
import altair as alt

app = Flask(__name__)

FORM_HTML = '''
<!doctype html>
<html>
<head>
    <title>Calculation Form</title>
</head>
<body>
    <h1>Enter Your Values</h1>
    <form method="post">
        <label for="start">Start:</label>
        <input type="number" id="start" name="start" value="0" step="any" required>
        <br><br>
        <label for="end">End:</label>
        <input type="number" id="end" name="end" value="10" step="any" required>
        <br><br>
        <input type="submit" value="Submit">
    </form>
</body>
</html>
'''

RESULT_HTML = '''
<!doctype html>
<html>
<head>
    <title>Calculation Result</title>
</head>
<body>
    <h1>Chart Result</h1>
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
            start = float(request.form['start'])
            end = float(request.form['end'])
        except ValueError:
            return "Invalid input, please enter valid numbers."
        x_values = np.linspace(start, end, 100)
        y_values = x_values ** 2
        df = pd.DataFrame({'x': x_values, 'y': y_values})
        chart = alt.Chart(df).mark_line().encode(
            x='x',
            y='y'
        ).properties(
            title=f'Square Function from {start} to {end}'
        )
        chart_html = chart.to_html()
        return render_template_string(RESULT_HTML, chart=chart_html)
    return render_template_string(FORM_HTML)

if __name__ == '__main__':
    app.run(debug=True)
