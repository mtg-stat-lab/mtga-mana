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

Make some assumptions clear in documentation:

* This is the most optimistic scenario for your ability to spend your mana
* It only cares about spending mana, not about value, life or cards
* It isn't actually simulating the gameplay (which is very complex), rather, it
is just answering the question "on this turn, given the cards drawn so far, is there
any way I could have cast this spell given lands and mana producing cards I could have
played on prior turns?)
* We aren't accounting for cards that can tutor a lands from your deck (like Pathfinder) or from your graveyard (like Pothole Mole), so you have to either consider them as producing mana or not. For example, for the Mole, either `2*>WUBRG` for producing mana or `2*G` for not.
* We aren't accounting for any card draw, exhaust or cycling abilities

Make some clearer examples of how the encodings should work:

* Plains: >G
* Thornwood Falls: >UG
* Night Market >WUBRG
* Scurryfoot: G
* Run Over: *G
* Ketradon: 4*2G
* Veloheart bike: 2*G>WUBRG

* Sentence case everywhere
* Enhance the Methodology section
* Add a FAQ section
* Choose a name

* Change from the negative "dead cards" to the positive "castable spells"
* Track for each spell (by key) (a) how often it is in hand, (b) how often it is castable, (c) % of time castable, (d) total mana cost, and (e) % castable over mana cost. Sort by (e) descending

* Make the visualizations searchable

* Add an example in the About for how to enter the JSON

* Limit the number of simulations that can be run to 1,000
* Limit the number of draw steps to 20

* Change the spells / mana input to a single "deck" iput with something like:

```
"4*U"  # a 4 generic 1 blue mana spell
">BU"  # a land that produces black or blue mana
"2*>*" # a 2 generic spell that can then be tapped immediately for any mana color (e.g., Tortoise)
"3*|WUBRG"  # a 3 generic spell that can tutor for any basic land
"*U>*/" # a one generic one blue spell that can tap for generic mana but enters tapped
">UB/" # a blue / white mana that enters tapped
```
maybe have a conversation with ChatGPT about how to represent all these things

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
