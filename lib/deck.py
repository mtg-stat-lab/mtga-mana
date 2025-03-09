import difflib
import re

import pandas as pd


def lookup_card_id(df_cards: pd.DataFrame, card_string: str):
    """
    Look up the card by name and return its mana string from the CSV.
    """
    all_cards = df_cards.name.values
    result = difflib.get_close_matches(card_string, all_cards, n=1)
    if len(result) > 0:
        card_name = result[0]
    else:
        raise ValueError(f"Could not find a match for card {card_string}")
    card_rows = df_cards.set_index("name").loc[card_name]
    return card_rows.loc["mana_string"]


def _process_line(
    line: str, df_cards: pd.DataFrame | None = None
) -> tuple[str | None, str | None, int | None]:
    """
    Process a single line of the deck, returning:
      (display_name, mana_string, count)
    """
    if not line or " " not in line:
        print(f"Skipping line due to incorrect format: '{line}'")
        return None, None, None

    try:
        # Remove any unwanted patterns (e.g., tournament info)
        line = re.sub(r"\([A-Z]{3}\)\s\d+", "", line).strip()
        count, name = line.split(" ", 1)
        count = int(count)
        if df_cards is not None:
            mana = lookup_card_id(df_cards, name)
            return name, mana, count
        else:
            return name, name, count
    except ValueError as e:
        print(f"Error processing line: '{line}' - {e}")
        return None, None, None


def _add_card_to_list(card_dict: dict, display_name: str, mana: str, count: int):
    if display_name is None or mana is None or count is None:
        return
    else:
        if display_name in card_dict:
            existing_mana, existing_count = card_dict[display_name]
            card_dict[display_name] = (existing_mana, existing_count + count)
        else:
            card_dict[display_name] = (mana, count)


def parse_deck_list(deck_list: str, df_cards: pd.DataFrame | None) -> tuple[dict, dict]:
    """
    Parse a deck list (including "Deck" and "Sideboard" sections) into two dictionaries.
    Each dictionary is a mapping of card display name -> (mana string, count).
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

        display_name, mana, count = _process_line(line, df_cards)
        dict_to_use = deck_dict if is_deck else sideboard_dict
        try:
            _add_card_to_list(dict_to_use, display_name, mana, count)
        except Exception as e:
            print(f"Error adding {display_name} card to list: {e}")

    return deck_dict, sideboard_dict
