import random
from typing import Any


def pick_audit_passes(
    simulations: int, sample_size: int = 10, seed: int | None = None
) -> list[int]:
    """
    Randomly pick up to `sample_size` distinct pass indices out of `simulations`.
    Done before running the simulation, to reduce memory usage.
    """
    if seed is not None:
        rand = random.Random(seed)
    else:
        rand = random

    if simulations <= sample_size:
        return list(range(simulations))
    return sorted(rand.sample(range(simulations), sample_size))


class SimulationAuditRecord:
    """
    Stores per-turn data for a single simulation pass.
    For each turn, we keep a list of dicts describing each card in hand:
      {
        uid, card_name, is_land, can_produce_mana, turn_drawn, is_castable,
        cost_uncolored, cost_colors, producible_colors
      }
    """

    def __init__(self, pass_index: int):
        self.pass_index = pass_index
        self.turns_data: dict[int, list[dict[str, Any]]] = {}

    def record_turn_state(self, turn: int, hand_snapshot: list[Any]):
        turn_list = []
        for c in hand_snapshot:
            if c is None:
                continue
            turn_list.append(
                {
                    "uid": getattr(c, "uid", -1),
                    "card_name": c.display_name,
                    "is_land": c.is_land,
                    "can_produce_mana": c.can_produce_mana,
                    "turn_drawn": getattr(c, "draw_turn", None),
                    "is_castable": getattr(c, "is_castable_this_turn", False),
                    # NEW: store cost info for spells
                    "cost_uncolored": getattr(c, "cost_uncolored", 0),
                    "cost_colors": dict(getattr(c, "cost_colors", {})),
                    # For mana or lands, store producible colors
                    "producible_colors": sorted(list(getattr(c, "producible_colors", set()))),
                }
            )
        self.turns_data[turn] = turn_list

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_index": self.pass_index,
            "turns_data": self.turns_data,
        }
