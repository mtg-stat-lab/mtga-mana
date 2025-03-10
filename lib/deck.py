# ./lib/deck.py

import difflib
import re

import pandas as pd


def lookup_card_id(df_cards: pd.DataFrame, card_string: str) -> str:
    """
    Look up the card by name and return its mana string from the CSV
    (using closest match).
    """
    all_cards = df_cards.name.values
    result = difflib.get_close_matches(card_string, all_cards, n=1)
    if not result:
        raise ValueError(f"Could not find a match for card {card_string}")
    card_name = result[0]
    card_rows = df_cards.set_index("name").loc[card_name]
    return card_rows["mana_string"]


def _process_line(line: str, df_cards: pd.DataFrame) -> tuple[str, str, int]:
    """
    Return (display_name, mana_string, count) or (None, None, None) on error.
    """
    if not line or " " not in line:
        print(f"Skipping line due to incorrect format: '{line}'")
        return None, None, None
    try:
        line = re.sub(r"\([A-Z]{3}\)\s\d+", "", line).strip()
        count_str, name = line.split(" ", 1)
        count = int(count_str)

        mana_str = lookup_card_id(df_cards, name)
        return name, mana_str, count
    except ValueError as e:
        print(f"Error processing line: '{line}' - {e}")
        return None, None, None


def parse_deck_list(deck_list: str, df_cards: pd.DataFrame):
    """
    Parse a text block with "Deck" and "Sideboard" sections
    and return two dicts: main deck, sideboard
    """
    lines = deck_list.strip().split("\n")
    deck_dict = {}
    sideboard_dict = {}
    is_deck = True

    for line in lines:
        if line == "Deck":
            continue
        elif line.strip() == "":
            continue
        elif line == "Sideboard":
            is_deck = False
            continue

        display_name, mana_str, count = _process_line(line, df_cards)
        dict_to_use = deck_dict if is_deck else sideboard_dict
        if display_name and mana_str and count:
            if display_name in dict_to_use:
                existing_mana, existing_count = dict_to_use[display_name]
                dict_to_use[display_name] = (existing_mana, existing_count + count)
            else:
                dict_to_use[display_name] = (mana_str, count)

    return deck_dict, sideboard_dict
