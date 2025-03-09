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

### Card dataHistory

This app uses manually entered card data for spell casting / mana production costs that
is maintained in a google sheet [here](https://docs.google.com/spreadsheets/d/1NzkW7K1MEjIbj91Wgb5BYoGfQQgyAi6Kc_ONQymDrb8/edit?usp=sharing).

### TODO

* Add linting for python and html

* Why do we have two simulation runs?

* Move expected dead spells per color to be the first summary card
* Add expected turns to cast first spell

* Add new plot by color of expected dead spells as a horizontal bard chart

* Account for hand smoother and some mulligan logic?

From the latest change:

* Show x3 for a card that has 3 copies in the deck
* Shouldn't turns go to 10 for the cards?
* Looks like we are asking if we had an additional mana rather than if we replaced a mana, which isn't quite right
* Maybe get rid of the `0` bubbles on the dead in hand as that's not really dead?

Other:

* Can you account for tapped lands appearing on the turn they are drawn not being useful?

* Have o1 try to refactor this some more

* Update methodology to reflect latest changes

* Have a few examples with links the user can click on to automatically populate decks for testing (also include 17lands links for each?)

* Add traceback information in the errors as well as the error message

* Add status information about run time

* Are lands like the Raceway that produce only generic mana properly accounted for with a `>*` string?

* Run the simulation swapping all basic lands and show those results?

* Check that the deck size is correct

* Consolidate some of the configuration into horizontal cards

* Add a FAQ section

* Change from the negative "dead cards" to the positive "castable spells"

* Make the visualizations searchable

* Limit the number of simulations that can be run to 1,000
* Limit the number of draw steps to 20

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
