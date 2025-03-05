# mtga-mana
Mana calculator

## Instructions

### Running the app on Render

* In Render dashboard [here](https://dashboard.render.com/web/srv-cv430uggph6c73aanba0).
* Deployed URL is [https://mtg-got-pips.onrender.com](https://mtg-got-pips.onrender.com).

### Running the app locally

Create the virtual environment

``` bash
python3 -m venv venv
```

Activate the virtual env

``` bash
source venv/bin/activate
```

Install dependencies

``` bash
pip install -r requirements.txt
```

Run the app

``` bash
python apps/mana.py
```

Go to [this URL](http://127.0.0.1:5001/) to see the app!

### History

Started this shell based on this [ChatGPT conversation](https://chatgpt.com/share/67c5a082-dca4-8003-8937-992d41ee3bb1).


### TODO

"Dead spells in hand"
"Mana pip most needed"

* Compute some summary statistics and display them in a table at the top of the charts
  -- percent of turns with 0 dead spells
  -- percent of runs with 0 dead spells
  -- expected number of dead spells per turn
  -- most desired pip color
  -- least desired pip color (of those used in spells)

* Keep track of the number of dead spells in each simulation and plot the distribution of dead spell count as stacked bars over ste

* Make the chart widths proportional to the number of draw steps so they appear more fixed

* Add tooltips

* Limit the number of simulations that can be run to 1,000

* Limit the number of draw steps to 10 (and make that the default)
* Have the `0` draw step be the starting hand, and go up from there 10 draws
* In the X-axis for the charts, change the `0` to be `"start"`

* Ask ChatGPT to style this so that it's prettier

* Keep track of a version number displayed somewhere on the main page
(maybe in the main page)

* Setup some CI and unit testing

* Share with Alex

* Share in LLU, 17lands

* Connect to LoL and share there as well

### Other

To get the app into context for an LLM:

``` bash
find . -type f \( -name '*.py' -o -name '*.html' \) -not -path './venv*' -print0 | sort -z | while IFS= read -r -d '' file; do
  echo "===== $file ====="
  cat "$file"
  echo ""
done | pbcopy
```
