import re
from collections import Counter

CANONICAL_COLORS: list[str] = ["W", "U", "B", "R", "G"]
CANONICAL_COLOR_VALUES: list[str] = ["grey", "blue", "black", "red", "green"]


def parse_cost_string(cost_str: str) -> tuple[int, Counter[str]]:
    """
    Parse a cost string such as '3*U2W' into (uncolored, color_costs).
    Example:
      '3*U2W' -> (3, {'U':1, 'W':2})
    """
    pattern = r"(\d*\*|\d*[WUBRG])"
    matches = re.findall(pattern, cost_str)
    uncolored = 0
    color_costs: Counter[str] = Counter()
    for m in matches:
        digits_str = ""
        for ch in m:
            if ch.isdigit():
                digits_str += ch
            else:
                break
        num = int(digits_str) if digits_str else 1
        symbol = m[len(digits_str) :]
        if symbol == "*":
            uncolored += num
        else:
            color_costs[symbol] += num
    return uncolored, color_costs
