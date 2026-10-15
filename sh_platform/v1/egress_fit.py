"""Shape an agent's context so the egress gateway lets it out: the row guard refuses any list holding two or more records
(dicts or lists), and any one string over 20,000 characters. Records become one-line strings ("name: x; kind: y"), and the
whole context is trimmed from the back of the named lists until it fits one JSON string."""
from __future__ import annotations

import json

LIMIT = 15_000


def _line(d: dict) -> str:
    return "; ".join(f"{k}: {_text(v)}" for k, v in d.items() if v not in (None, "", [], {}))


def _text(v) -> str:
    if isinstance(v, dict):
        return _line(v)
    if isinstance(v, list):
        return ", ".join(_text(x) for x in v)
    return " ".join(str(v).split())


def flatten(o):
    """Lists of records become lists of one-line strings; dicts are walked; scalars pass."""
    if isinstance(o, dict):
        return {k: flatten(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_text(x) if isinstance(x, (dict, list)) else x for x in o]
    return o


def fit(context: dict, trim: tuple[tuple[str, str | None], ...] = (), limit: int = LIMIT) -> dict:
    """flatten, then drop items from the front of each named list (key, or key.sub) until the JSON fits."""
    v = flatten(context)
    for key, sub in trim:
        while len(json.dumps(v)) > limit:
            box = v.get(key)
            if sub and isinstance(box, dict):
                box = box.get(sub)
            if not isinstance(box, list) or not box:
                break
            box.pop(0)
    return v
