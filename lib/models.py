import random
from collections import Counter
from typing import List, Optional

from .cost_parser import parse_cost_string


class Card:
    """
    Represents any card:
      - Land if leading '>' (e.g. '>BW')
      - Mana-producing if it has '>' anywhere (e.g. '3*>WUBRG')
      - Normal spells have no '>'
    """

    def __init__(self, card_str: str, display_name: Optional[str] = None) -> None:
        self.card_str: str = card_str
        self.display_name: str = display_name if display_name else card_str

        self.is_land: bool = card_str.startswith(">")
        self.can_produce_mana: bool = False
        self.cost_uncolored: int = 0
        self.cost_colors: Counter[str] = Counter()
        self.producible_colors: set[str] = set()

        # Distinguish spells vs. lands vs. mana-producers
        if self.is_land:
            # Everything after '>' is producible
            produce_part = card_str[1:]
            self.can_produce_mana = True
            self.producible_colors = set(produce_part)
        else:
            if ">" in card_str:
                # e.g. '3*>WUBRG' means cost is '3*', produce is 'WUBRG'
                cost_part, produce_part = card_str.split(">", 1)
                self.can_produce_mana = True
                self.producible_colors = set(produce_part)
            else:
                cost_part = card_str

            uncolored, color_costs = parse_cost_string(cost_part)
            self.cost_uncolored = uncolored
            self.cost_colors = color_costs

    def __repr__(self) -> str:
        return f"Card({self.display_name}, {self.card_str})"


class Deck:
    """
    Represents a deck of a fixed total size. Some slots may be None
    if we have fewer actual cards than total_deck_size.
    """

    def __init__(self, cards: List[Card], total_deck_size: int = 40) -> None:
        self.cards = cards
        self.total_deck_size = total_deck_size

        leftover = total_deck_size - len(cards)
        if leftover > 0:
            self.cards += [None] * leftover

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw_top_n(self, n: int):
        return self.cards[:n]

    def __len__(self):
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Deck(size={self.total_deck_size}, actual_list_len={len(self.cards)})"
