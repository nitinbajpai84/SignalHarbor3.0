"""The under-five rule, shared by the registry, the context pack and the guard."""
import re

_NUMERIC_TEXT = re.compile(r"\s*[-+]?(?:\d{1,3}(?:,\d{3})+|\d*)\.?\d+\s*%?\s*")
MIN_GROUP = 5  # same rule as egress; defined here so this package imports nothing from it


def group_ok(size) -> bool:
    """A group size counts only if it is a real integer (not a bool or string) of MIN_GROUP or more."""
    return isinstance(size, int) and not isinstance(size, bool) and size >= MIN_GROUP


def is_figure(key: str, value) -> bool:
    """A figure is a number (not a bool), or a numeric string such as "2", "3.5" or "1,200", under a label.
    Ids and the group size itself are not figures."""
    k = str(key).lower()
    if k in ("group_size", "id") or k.endswith("_id"):
        return False
    if isinstance(value, str):
        return bool(_NUMERIC_TEXT.fullmatch(value))
    return isinstance(value, (int, float)) and not isinstance(value, bool)
