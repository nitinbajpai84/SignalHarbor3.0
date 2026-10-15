"""Structural checks on what an outgoing payload holds. No text heuristics.

BY DESIGN, table-shaped free text is NOT detected any more: a block of comma, tab, pipe, colon,
equals or YAML lines typed into a question or a message is not recognised as rows. This is
accepted residual risk. Reasons: each company runs in its own container, and the tool registry
returns counts and totals only (never rows), so free text of that shape does not come from the
agent's own tools. Closing that gap is later work.

What IS checked (all on structure, never on wording):
- Payload keys and message shape: see gateway._check_structure (allowlist question, facts, summary,
  messages, tools; each message exactly {role, content}).
- JSON found in a string (the whole string, or text followed by JSON such as a marker line then a
  tool result, or one JSON value per line):
  * a LIST of two or more objects or lists is rows and is refused, unless every item is an
    aggregate (an object carrying its own group_size of 5 or more). A single object is never a row,
    however many keys it has: the agent loop sends {"context": ..., "question": ...} and tool
    results like {"count": 40, "group_size": 8};
  * ANY object, at any depth, that has a group_size which is not an integer of 5 or more, or that
    looks like a fact (has both "label" and "value") but has no group_size, is refused as a
    suppressed figure, and its numbers are returned so they join the per-call SuppressedFigures;
  * nesting deeper than 100 levels is refused.
- Size: any string (a message, the question, a string value inside JSON) over MAX_STRING_CHARS is
  refused; the summary and the whole payload have their own caps in the gateway.
Not covered: JSON written inside a JSON string value, rows split over many messages, and anything
that is not JSON.
"""
import json

MAX_STRING_CHARS = 20_000
_MIN_GROUP = 5  # same rule as aggregates.MIN_GROUP (kept local: this module stands alone)
_MAX_DEPTH = 100


def _parse(text: str):
    """(prefix, parsed JSON) if the text is JSON or text then JSON, else None."""
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        return None
    i = min(starts)
    try:
        return text[:i], json.loads(text[i:])
    except (ValueError, RecursionError):
        return None


def _group_ok(size) -> bool:
    return isinstance(size, int) and not isinstance(size, bool) and size >= _MIN_GROUP


def _is_aggregate(x) -> bool:
    return isinstance(x, dict) and _group_ok(x.get("group_size"))


def _list_is_rows(items: list) -> bool:
    boxes = [x for x in items if isinstance(x, (dict, list))]
    return len(boxes) >= 2 and not all(_is_aggregate(x) for x in boxes)


def _walk(o, found: dict, depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        found["rows"] = True  # too deep to trust
    elif isinstance(o, str):
        if len(o) > MAX_STRING_CHARS:
            found["big"] = True
    elif isinstance(o, list):
        if _list_is_rows(o):
            found["rows"] = True
        for x in o:
            _walk(x, found, depth + 1)
    elif isinstance(o, dict):
        if "group_size" in o:
            if not _group_ok(o["group_size"]):
                found["bad"].append(o)
        elif "label" in o and "value" in o:
            found["bad"].append(o)
        for v in o.values():
            _walk(v, found, depth + 1)


def _json_values(text: str) -> list:
    parsed = _parse(text)
    if parsed is not None:
        return [parsed[1]]
    objs = []
    for ln in text.splitlines():
        s = ln.strip()
        if s[:1] in ("{", "[") and len(s) > 4:
            try:
                objs.append(json.loads(s))
            except (ValueError, RecursionError):
                pass
    return [objs] if len(objs) >= 2 else objs  # JSON lines count as a list of records


def json_findings(text: str):
    """(code, bad_objects): code is None, "suppressed_figure", "raw_rows" or "payload_too_large"."""
    if len(text) > MAX_STRING_CHARS:
        return "payload_too_large", []
    found = {"rows": False, "big": False, "bad": []}
    for v in _json_values(text):
        _walk(v, found)
    if found["bad"]:
        return "suppressed_figure", found["bad"]
    if found["rows"]:
        return "raw_rows", []
    return ("payload_too_large", []) if found["big"] else (None, [])


def text_has_rows(text: str) -> bool:
    return json_findings(text)[0] == "raw_rows"
