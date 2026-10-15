"""Matching an uploaded file's column names to the catalogue's fields (M3-P02). Names and types only; nothing here looks at a value.

Copied from module 2 (`modules/m2_baseline/domain/catalogue.py` ~922-998, module 2 is not imported): `_tokens`, `_name_score`,
`_type_agrees` and the type groups, with the contract's `column_words` as a constant here. Changed: module 2 suggests which KPI a column
may feed from the pack's feeds; here the catalogue's own field names are the target (the signed baseline already says what is expected),
and the pack's `column_synonyms.yaml` spellings are extra spellings for a catalogue field whose name equals a pack field's id or label.
Not copied: `match_columns` and `_by_kpi_name` (they answer "which KPI", which the catalogue already says here).
"""
import re
from difflib import SequenceMatcher

_TYPE_GROUP = {"string": "string", "text": "string", "varchar": "string", "int": "decimal", "integer": "decimal", "bigint": "decimal",
               "decimal": "decimal", "double": "decimal", "float": "decimal", "number": "decimal", "date": "date", "timestamp": "date",
               "datetime": "date", "bool": "boolean", "boolean": "boolean"}
COLUMN_WORDS = [["pay", "salary", "bonus", "compensation", "wage", "payroll", "remuneration"], ["return", "performance", "alpha"],
                ["benchmark", "index"], ["class", "cls", "category"], ["value", "val", "valuation", "amount", "amt"], ["date", "dt"], ["account", "acct"]]
_GENERIC = frozenset("id no name code type number key ref flag text".split())  # too common to say what a column is for
LEVELS = ("low", "medium", "high")


def _type_agrees(column_type: str, field_type: str) -> bool:
    norm = lambda s: str(s or "").strip().lower()  # noqa: E731
    return _TYPE_GROUP.get(norm(column_type), "string") == _TYPE_GROUP.get(norm(field_type), "string")


def _tokens(text: str) -> set[str]:
    """period_return, periodReturn and "Period return" all give {period, return}; a plural is its singular; listed words are one thing."""
    words = re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text)).lower())
    one = lambda w: next((g[0] for g in COLUMN_WORDS if w in g), w)  # noqa: E731
    return {one(w[:-1] if len(w) > 3 and w.endswith("s") else w) for w in words if w not in _GENERIC}


def _name_score(column: str, field_name: str, spellings: list[str] | None = None) -> tuple[int, str]:
    """0 no match, 1 low (some words shared), 2 medium (most words), 3 high (the same words, or a spelling the pack knows)."""
    name = column.strip()
    if name.lower() == field_name.strip().lower():
        return 3, f"“{column}” has the same name as “{field_name}”"
    if name.lower() in (s.lower() for s in spellings or []):
        return 3, f"“{column}” is a spelling the industry pack knows for “{field_name}”"
    a, b = _tokens(name), _tokens(field_name)
    for s in spellings or []:
        if (t := _tokens(s)) and t == a:
            return 3, f"“{column}” is a spelling the industry pack knows for “{field_name}”"
    if not a or not b:
        return 0, ""
    if a == b:
        return 3, f"“{column}” says the same as “{field_name}”"
    close = sum(1 for w in a if any(w == v or (min(len(w), len(v)) >= 3 and (w.startswith(v) or v.startswith(w))) or SequenceMatcher(None, w, v).ratio() >= 0.85 for v in b))
    share = close / max(len(a), len(b))
    if share >= 0.99:
        return 3, f"“{column}” says the same as “{field_name}”"
    if share >= 0.6:
        return 2, f"“{column}” shares most words with “{field_name}”"
    if close:
        return 1, f"“{column}” shares a word with “{field_name}”"
    return 0, ""


def pack_spellings(synonyms: dict, field_name: str) -> list[str]:
    """Spellings the pack lists for any field whose id or label says the same as this catalogue field."""
    want = _tokens(field_name)
    out: list[str] = []
    for feed in (synonyms or {}).values():
        for fid, entry in (feed or {}).items():
            if want and _tokens(fid) == want:
                out += [str(s.get("spelling") or "") for s in (entry or {}).get("spellings") or [] if isinstance(s, dict)]
    return out


def match_columns(columns: list[dict], fields: list[dict], synonyms: dict | None = None) -> dict[str, dict]:
    """{column name: {field_id, field, confidence, reasons}} for each column that has a best field (one field per column, one column per field).
    `columns` is [{name, type}]; `fields` is [{field_id, name, type?}]."""
    options = []
    for c in columns:
        for f in fields:
            level, why = _name_score(c["name"], f["name"], pack_spellings(synonyms or {}, f["name"]))
            if level:
                agrees = "type" not in c or not f.get("type") or _type_agrees(c["type"], f["type"])  # a column's type is checked only when both sides say one
                options.append((level if agrees else max(level - 1, 1), c["name"], f["field_id"], f["name"], why + ("" if agrees else "; its type does not fit")))
    out, used = {}, set()
    for level, col, fid, fname, why in sorted(options, key=lambda o: -o[0]):
        if col in out or fid in used or level < 2:  # a low match is a hint for a person, not a match
            continue
        out[col] = {"field_id": fid, "field": fname, "confidence": LEVELS[level - 1], "reasons": [why]}
        used.add(fid)
    return out
