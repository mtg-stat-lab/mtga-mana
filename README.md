# mtga-mana
Mana calculator

## Instructions

### Running the app

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

* Limit the number of simulations that can be run

* Keep track of a version number displayed somewhere on the main page

* Add some documentation and help

* Keep track of the number of dead spells in each simulation and plot the distribution of dead spell count as stacked bars over step

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
