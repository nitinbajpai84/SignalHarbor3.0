"""Profiling one uploaded table (M3-P02): types, how full each column is, row count, date range, a duplicate-key hint, and the gap list.

Ported from the earlier product: `emitters/profiler.py` `_infer_type`, `_column_profile` (type inference, null counts, distinct counts,
candidate key) and the gap kinds of `emitters/gap_report.py` (missing, quality = too empty), reshaped to this module's rows and to the
catalogue's fields as the expected side. Nothing here leaves the machine; samples are never kept for a personal-data column.

`coerce` turns a cell into a typed value (None for empty, int, float, ISO date text, bool, or text). `profile_table(header, rows)` returns
the table profile; `rows_of(...)` the typed rows P03 reads. `gaps_for(...)` compares with what was asked for.
"""
import re
from datetime import date, datetime, timedelta

EMPTY = {"", "null", "none", "nan", "n/a", "na", "#n/a"}
HALF_EMPTY = 0.80          # below this fill rate a requested column is "half empty"
SERIES_DATES = 10          # a date column with this many different days is a time series: it should reach the period's end
SERIES_SLACK_DAYS = 3      # a weekend and a holiday do not count as short
SAMPLES = 3
PERSONAL_WORDS = {"email", "phone", "mobile", "dob", "birth", "passport", "nric", "ssn", "address", "salary", "bonus", "tax"}
_INT, _FLOAT = re.compile(r"^-?\d+$"), re.compile(r"^-?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?$|^-?\d+[eE][-+]?\d+$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$")
_DMY = re.compile(r"^(\d{1,2})[ \-/]([A-Za-z]{3})[a-z]*[ \-/](\d{4})$")
_MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
_DATE_NAME = re.compile(r"date|_dt$|\bdt\b|day|period|as.?at", re.I)


def coerce(v):
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    t = str(v).strip()
    if t.lower() in EMPTY:
        return None
    if _INT.match(t):
        return int(t) if len(t) < 16 or t.startswith("-") else t
    if _FLOAT.match(t):
        return float(t)
    if _ISO.match(t):
        try:
            return date.fromisoformat(t[:10]).isoformat()
        except ValueError:
            return t
    if m := _DMY.match(t):
        try:
            return date(int(m.group(3)), _MON[m.group(2).lower()], int(m.group(1))).isoformat()
        except (KeyError, ValueError):
            return t
    return t


def is_date(v) -> bool:
    return isinstance(v, str) and bool(_ISO.match(v)) and len(v) == 10


def infer_type(values: list) -> str:
    """Conservative: every value must agree for a type more specific than text (profiler._infer_type)."""
    vs = [v for v in values if v is not None]
    if not vs:
        return "unknown"
    if all(isinstance(v, bool) for v in vs):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in vs):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vs):
        return "decimal"
    if all(is_date(v) for v in vs):
        return "date"
    return "string"


def _personal_by_name(name: str) -> bool:
    return bool(set(re.findall(r"[a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", name).lower())) & PERSONAL_WORDS)


def rows_of(header: list[str], rows: list[list]) -> list[dict]:
    return [{h: coerce(c) for h, c in zip(header, r)} for r in rows]


def profile_table(header: list[str], rows: list[list], personal: set[str] = frozenset()) -> dict:
    """{row_count, columns[{name,type,non_empty,nulls,fill,distinct,personal,samples}], date_column, date_range, duplicate_key}.
    `personal` = column names already known to hold personal data (a name hint is added)."""
    typed = rows_of(header, rows)
    total, cols = len(typed), []
    for h in header:
        vals = [r[h] for r in typed]
        got = [v for v in vals if v is not None]
        flag = h in personal or _personal_by_name(h)
        distinct = list(dict.fromkeys(str(v) for v in got))
        cols.append({"name": h, "type": infer_type(got), "non_empty": len(got), "nulls": total - len(got),
                     "fill": round(len(got) / total, 4) if total else 0.0, "distinct": len(distinct), "personal": flag,
                     "samples": [] if flag else distinct[:SAMPLES]})
    dates = [c for c in cols if c["type"] == "date"]
    dcol = next((c for c in dates if _DATE_NAME.search(c["name"])), dates[0] if dates else None)
    span, series = None, False
    if dcol:
        days = sorted({r[dcol["name"]] for r in typed if r[dcol["name"]]})
        span, series = {"from": days[0], "to": days[-1]}, len(days) >= SERIES_DATES
    return {"row_count": total, "columns": cols, "date_column": dcol["name"] if dcol else None, "date_range": span, "series": series,
            "duplicate_key": duplicate_key(typed, cols)}


def duplicate_key(typed: list[dict], cols: list[dict]) -> dict | None:
    """The best candidate key and how many rows repeat it: a column called id/ref/code/key if one is there, else the first two columns together."""
    if len(typed) < 2:
        return None
    names = [c["name"] for c in cols]
    idish = [n for n in names if re.search(r"(^|[\s_])(id|ref|key|code|no|number)($|[\s_])", n, re.I)]
    for pick in ([[n] for n in idish] + ([names[:2]] if len(names) > 1 else []) + [[names[0]]]):
        keys = [tuple(r[n] for n in pick) for r in typed if all(r[n] is not None for n in pick)]
        if keys:
            return {"columns": pick, "duplicates": len(keys) - len(set(keys))}
    return None


def month_of(today: date) -> dict:
    """The latest full month before `today`: {from, to, label}."""
    last = today.replace(day=1) - timedelta(days=1)
    return {"from": last.replace(day=1).isoformat(), "to": last.isoformat(), "label": last.strftime("%B %Y")}


def gaps_for(source_id: str, tables: list[dict], expected: list[dict], period: dict) -> list[dict]:
    """The gap list. `tables` = profiled tables [{table_id, columns[{name, fill, field_id}], series, date_range, ...}]; `expected` =
    [{field_id, name, table_id, measures[]}]. Kinds (from gap_report): missing_column, half_empty (quality), some_empty, period_short;
    `file_not_arrived` when nothing has come."""
    if not tables:
        return [{"kind": "file_not_arrived", "text": "Nothing has arrived for this source yet.", "field_id": None, "measures": []}]
    out, by_field = [], {}
    for t in tables:
        for c in t["columns"]:
            if c.get("field_id"):
                by_field[c["field_id"]] = c
    def empty_gap(c: dict, name: str, base: dict) -> dict | None:
        total = c["non_empty"] + c["nulls"]
        if c["fill"] < HALF_EMPTY:
            return {**base, "kind": "half_empty", "fill": c["fill"], "text": f"“{name}” is only {round(c['fill'] * 100)}% full ({c['nulls']} empty of {total} rows)."}
        if c["nulls"]:
            return {**base, "kind": "some_empty", "fill": c["fill"], "text": f"“{name}” is empty in {c['nulls']} of {total} rows."}
        return None

    for e in expected:
        c = by_field.get(e["field_id"])
        base = {"field_id": e["field_id"], "column": e["name"], "measures": e.get("measures", [])}
        if c is None:
            out.append({**base, "kind": "missing_column", "text": f"The column “{e['name']}” was not found in what arrived."})
        elif gap := empty_gap(c, e["name"], base):
            out.append(gap)
    for t in tables:  # a column that matched no catalogue field is still a gap when it is low on fill or empty in some rows (never a personal one: its name stays hidden)
        out += [g for c in t["columns"] if not c.get("field_id") and not c.get("personal")
                and (g := empty_gap(c, c["name"], {"field_id": None, "column": c["name"], "measures": []}))]
    for t in tables:
        r = t.get("date_range")
        if t.get("series") and r and period.get("to"):
            behind = (date.fromisoformat(period["to"]) - date.fromisoformat(r["to"])).days
            if behind > SERIES_SLACK_DAYS:
                ids = [e for e in expected if e.get("table_id") == t.get("table_id")]
                out.append({"kind": "period_short", "field_id": None, "column": t.get("date_column"), "table": t.get("name"),
                            "measures": sorted({m for e in ids for m in e.get("measures", [])}),
                            "text": f"The data stops on {datetime.fromisoformat(r['to']).strftime('%d %B')}, but the period you asked for ends on {datetime.fromisoformat(period['to']).strftime('%d %B')}."})
    return out
