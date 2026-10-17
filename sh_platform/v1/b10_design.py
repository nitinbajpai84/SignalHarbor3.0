"""FIXC: Span designs the use case's OWN gold tables from the signed intent, and proposes the silver they need.

The existing reporting template (holdings, net worth, benchmark) stays one case in b6_span. This module takes the figures the rules and the earlier
steps could not place (the "could not place the KPI" notes) and gives each one a column of a gold table, at the grain the intent states. With a
model the design is the model's (checked by the plan check); without one it is drawn by rules from the KPIs' names, units, periods and "by" words.
A figure with no definition is still placed, and listed as needing one. When the company model has no table to read, the silver table is proposed
as a model change (e0a), one proposal per project, linked to the pack and approved by the head of data.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import logging
import os
import re

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b6_plan as B
from sh_platform.v1.b6_span import _not_a_plain_total  # the same guard as the plan's rules (UC5)
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
_UNPLACED = re.compile(r"could not place the KPI '([^']+)'")
_STOP = {"within", "days", "day", "by", "after", "total", "number", "of", "the", "in", "and", "to", "per", "month", "monthly", "all", "from", "at",
         "as", "a", "an", "for", "than", "above", "below", "net", "new", "last", "this", "with", "that", "are", "is", "on", "or", "gross"}
_PERIOD = {"month": "month", "monthly": "month", "day": "day", "daily": "day", "week": "week", "weekly": "week", "quarter": "quarter", "quarterly": "quarter",
           "year": "year", "yearly": "year", "annual": "year"}
_COUNT = re.compile(r"\b(number of|count|how many)\b|^(?:\w+\s+)?(?:trades|breaks|exceptions|cases|notices|calls|items)\b", re.I)
_RATIO = ("percent", "pct", "%", "ratio", "share")
SILVER_TYPES = "text, date, timestamp, integer, bigint, boolean, uuid, numeric(18,2)"


def _slug(text, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:n].strip("_")
    return ("c_" + s) if s[:1].isdigit() else (s or "x")


# ---- the model change (one proposal for the project; e0a does the filing and the approval) ------------------------------------------

def parse_columns(text: str) -> list[dict]:
    """'item_key text; due_date date; amount numeric(18,2)' as [{name, type, note}]; types are normalised (varchar, decimal, datetime ...) and checked."""
    out = []
    for part in re.split(r"[;\n]", str(text)):
        part = part.strip()
        if not part:
            continue
        bits = part.split(None, 1)
        name, rest = bits[0].lower(), (bits[1] if len(bits) > 1 else "")
        typ, _, note = rest.partition(" - ")
        out.append({"name": name, "type": E.norm_type(typ or "text"), "note": note.strip()[:200]})
    return check_columns(out)


def check_columns(cols: list[dict]) -> list[dict]:
    if not cols or len(cols) > 40:
        raise Refused(400, "Give between 1 and 40 columns.")
    seen = set()
    for c in cols:
        c["name"] = E.slug(c.get("name"))  # 'unmatched count' becomes unmatched_count; never blocks plan approval
        c["type"] = E.norm_type(c.get("type") or "text")
        if not _NAME.fullmatch(str(c.get("name") or "")) or c["name"] in seen:
            raise Refused(400, f"'{c.get('name')}' is not a usable column name (lowercase letters, digits, underscores, once each).")
        seen.add(c["name"])
        E._duck_type(c["type"])  # refuses a type the warehouse cannot hold
    return cols


def _q(text: str) -> str:
    return "'" + str(text).replace("\\", " ").replace("'", " ")[:200] + "'"


def to_dbml(tables: list[dict]) -> str:
    out = []
    for t in tables:
        lines = [f"Table {t['name']} {{"]
        for c in t["columns"]:
            attrs = (["pk"] if c["name"] == "id" and c["type"] == "uuid" else []) + ([f"note: {_q(c['note'])}"] if c.get("note") else [])
            lines.append(f"  {c['name']} {c['type']}" + (f" [{', '.join(attrs)}]" if attrs else ""))
        if t.get("purpose"):
            lines.append(f"  Note: {_q(t['purpose'])}")
        out.append("\n".join(lines) + "\n}")
    return "\n\n".join(out)


def _path(plane, pid: str):
    return B.folder(plane, pid) / "model-change.json"


def _record(plane, pid: str) -> dict:
    try:
        return read_json_strict(_path(plane, pid), dict) or {}
    except (OSError, ValueError):
        return {}


def missing_forms(plane, tables: list[dict]) -> list[dict]:
    """Of the silver tables a design wants, what the current company model lacks: a whole table, or the columns a table lacks."""
    have = {t["name"]: {c["name"] for c in t["columns"]} for t in E.current(plane)["tables"]}
    out = []
    for t in tables:
        if t["name"] not in have:
            out.append(t)
        elif (cols := [c for c in t["columns"] if c["name"] not in have[t["name"]]]):
            out.append({**t, "columns": cols, "adds": True})
    return out


def file_model_change(plane, viewer, pid: str, tables: list[dict], note: str = "") -> dict | None:
    """Propose (through e0a) the silver tables in `tables` that the model lacks, with the ones this project already has waiting, as ONE proposal for the
    head of data. Returns {version, tables} or None when nothing is missing. Called by the pack and by Span's chat tool."""
    forms = missing_forms(plane, tables)
    with lock_for(B.folder(plane, pid)):
        rec = _record(plane, pid)
        waiting = rec.get("version") and E.proposal(plane, int(rec["version"]))["state"] == "proposed"
        known = {t["name"]: t for t in (rec.get("tables") or [] if waiting else [])}
        union = {**known, **{f["name"]: f for f in forms}}
        if not union:
            return None
        if waiting and set(union) == set(known) and all(union[k] == known[k] for k in union):
            return {"version": int(rec["version"]), "tables": list(known.values())}
        got = E.propose(plane, viewer, dbml=to_dbml(list(union.values())), note=note or "Needed by the design pack: the silver tables its gold tables read.")
        write_json_atomic(_path(plane, pid), {"version": got["version"], "tables": list(union.values())})
    return {"version": got["version"], "tables": list(union.values())}


def change_view(plane, pid: str) -> dict | None:
    """The project's model change as the pack shows it: version, state, who proposed it, the tables and columns it adds."""
    rec = _record(plane, pid)
    if not rec.get("version"):
        return None
    try:
        m = E.proposal(plane, int(rec["version"]))
    except Refused:
        return None
    return {"version": int(rec["version"]), "state": m["state"], "proposed_by": m.get("proposed_by"), "summary": m.get("summary", ""), "tables": rec.get("tables") or [],
            "approved_by": m.get("approved_by")}


# ---- reuse first: which silver table of the company model can hold a figure --------------------------------------------------------------------

_SYN = {"trade": "transaction", "trades": "transaction", "payment": "movement", "payments": "movement"}
_COND = re.compile(r"\b(within|above|below|only|excluding|without|matched|unmatched|minus|after|before|over|under|except|not)\b", re.I)
# UC6 H1: a day window on a date ("within 30 days of the as-at date", "31 to 60 days after ..."), and a word the figure leaves out ("not yet confirmed")
_WINDOW = re.compile(r"\b(?:(?:within|in the next|next)\s+(\d+)|(\d+)\s*(?:to|-)\s*(\d+))\s+days?\b(?:\s+(?:of|after|from)\s+(?:the\s+)?[a-z -]*?date\b)?", re.I)
_NOT = re.compile(r"\b(?:but\s+)?(?:not|no|without|excluding|except)\s+(?:yet\s+)?([a-z]+)", re.I)
# UC6 H1: a closing balance, or one figure minus another, is never the plain total of a table's rows
_LEVEL = re.compile(r"\b(minus|closing|opening|balance)\b|\bless\b(?!\s+than)", re.I)
# c3 ops_lead: a break or a difference between two sources is one source against the other, never the plain total of one table's movements
_COMPARE = re.compile(r"\b(breaks?|differences?|differ(?:s|ent)?|variances?|mismatch(?:es)?|reconcil\w*|against|versus|vs)\b", re.I)


# UC6 G: uncalled commitment = commitment - called to date (kept on the commitment from the file) - confirmed calls received after the file's as-at date.
# The same rule as k6_liquidity.commitments(): no stored figure -> the confirmed calls; a figure with an as-at date -> the figure plus calls received after it;
# a figure with no date -> the confirmed calls when there are any, else the figure. ponytail: as the tables stand now (the latest file), not at each month end.
_UNCALLED = re.compile(r"\buncalled\b", re.I)
_CALLS = ("(select coalesce(sum(c.amount), 0) from cash_movements as c where c.commitment_id = f.id and c.notice_kind = 'call' "
          "and c.confirmation_status in ('confirmed', 'paid') and not exists (select 1 from cash_movements as s where s.supersedes_cash_movement_id = c.id)")
_UNCALLED_SQL = (f"(f.commitment_amount - case when f.called_to_date is null then {_CALLS}) "
                 f"when f.called_as_at is not null then f.called_to_date + {_CALLS} and cast(c.received_at as date) > f.called_as_at) "
                 f"when {_CALLS}) = 0 then f.called_to_date else {_CALLS}) end)")


def _stem(w: str) -> str:
    w = _SYN.get(w, w)
    w = re.sub(r"ies$", "y", w)
    return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w


def _toks(text) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", str(text).lower()) if w not in _STOP}


def _kind(k: dict) -> str:
    unit = str(k.get("unit") or "").lower()
    text = f"{k.get('name') or ''} {k.get('definition') or ''}"
    if unit in _RATIO or re.search(r"\b(percent|percentage|ratio)\b|%", text.lower()):
        return "ratio"
    if re.fullmatch(r"[a-z]{3}", unit) and unit != "pct":
        return "money"
    if unit in ("count", "number", "#", "trades", "items") or (not unit and _COUNT.search(str(k.get("name") or ""))):
        return "count"
    return "money"


def _dims(k: dict, default: list[str]) -> list[str]:
    own = [_slug(b, 30) for b in k.get("benchmark_by") or [] if str(b).lower() not in _PERIOD]
    if not own:
        text = f"{k.get('name')} {k.get('definition') or ''}".lower()
        own = [_slug(w, 30) for m in re.finditer(r"\b(?:by|per)\s+([a-z]+)", text) if (w := m.group(1)) not in _PERIOD and w not in _STOP]
    return list(dict.fromkeys(own)) or list(default)


def _enum(note) -> list[str]:
    """The values a column's note lists ('subscription, redemption, call'), when it lists at least three."""
    items = [x.strip().lower() for x in re.sub(r"^(added:|e\.g\.)\s*", "", str(note or "").lower().strip()).split(",")]
    return items if len(items) >= 3 and all(re.fullmatch(r"[a-z_ ]{2,30}", x) for x in items) else []


_PREFER: contextvars.ContextVar[frozenset] = contextvars.ContextVar("prefer_tables", default=frozenset())


@contextlib.contextmanager
def prefer(tables):
    """While the block runs, a table that already holds the loaded data outranks an equal fit (v3_figures: design on what the load filled)."""
    token = _PREFER.set(frozenset(tables))
    try:
        yield
    finally:
        _PREFER.reset(token)


def rank_tables(plane, words: set[str]) -> list[dict]:
    """The company model's tables, best fit first: {table, score, matched, missing}. A word in a table's name counts most, then a listed value of one of its
    columns (calls: movement_type lists 'call'), then its note and column names. Tables under `prefer(...)` that match at all get +3."""
    out = []
    for t in E.current(plane)["tables"]:
        name, note = _toks(t["name"].replace("_", " ")), _toks(t.get("note") or "")
        score, hit = 0, set()
        for w in words:
            got = 3 * (w in name) + (w in note)
            for c in t["columns"]:
                got += (w in _toks(c["name"].replace("_", " "))) + 2 * (w in {_stem(x) for v in _enum(c.get("note")) for x in re.findall(r"[a-z]+", v)})
            score += got
            if got:
                hit.add(w)
        out.append({"table": t["name"], "score": score + (3 if score and t["name"] in _PREFER.get() else 0), "matched": sorted(hit), "missing": sorted(words - hit)})
    return sorted(out, key=lambda r: (-r["score"], r["table"]))


def usage(plane, viewer, pid: str, tables: list[str]) -> dict[str, list[dict]]:
    """For each silver table: the gold tables of OTHER projects that read it, directly or further down (the lineage the Map data model view uses)."""
    from sh_platform.v1 import k3_model as K3
    try:
        edges, plan = K3._edges(plane, viewer)
    except Exception:  # noqa: BLE001 - a lineage that cannot be read adds nothing
        log.warning("the lineage could not be read for the pack")
        return {t: [] for t in tables}
    down: dict[str, set[str]] = {}
    for a, b in edges:
        down.setdefault(a, set()).add(b)
    return {t: [{"table": n, "project_id": plan[n].get("project_id")} for n in K3._close(t, down)
                if n in plan and plan[n].get("project_id") != pid and plan[n].get("layer") == "gold"] for t in tables}


def project_titles(plane, ids: set) -> dict[str, str]:
    from sh_platform.v1 import p1_project as P1
    out = {}
    for i in ids:
        try:
            out[i] = str(P1.read(plane, i).get("title") or i)
        except Refused:
            out[i] = str(i)
    return out


def _text(c: dict) -> bool:
    return not c["name"].endswith("_id") and str(c["type"]).lower().startswith(("text", "varchar", "char"))


def _reach(cat: dict, refs: list[dict], start: str, dim: str, by_note: bool = False):
    """A text column that names `dim`, on `start` or up to three joins away along foreign keys: ('j2.entity_name', ['left join ...']). When no
    column is named for it, a table whose column notes list it (instruments: 'fund, bond, ...') gives its name column (UC6 H1: by fund)."""
    from sh_platform.v1.agent_tools import _ref
    todo = [(start, "f", [])]
    seen = {start}
    while todo:
        t, alias, joins = todo.pop(0)
        for c in cat[t]["columns"]:
            if not by_note and dim in _toks(c["name"].replace("_", " ")) and _text(c):
                return f"{alias}.{c['name']}", joins
        if by_note and any(dim in _toks(c.get("note")) for c in cat[t]["columns"]):
            name = next((c["name"] for c in cat[t]["columns"] if _text(c) and "name" in c["name"]), None)
            if name:
                return f"{alias}.{name}", joins
        if len(joins) < 3:
            for r in refs:
                child, fk, parent, pk = _ref(r)
                if child == t and parent not in seen and parent in cat:
                    seen.add(parent)
                    a2 = f"j{len(joins) + 1}"
                    todo.append((parent, a2, joins + [(parent, f"left join {parent} as {a2} on {alias}.{fk} = {a2}.{pk}")]))
    return None if by_note else _reach(cat, refs, start, dim, True)


def _fit_kpi(plane, k: dict, grain: dict, cat: dict, refs: list[dict]) -> dict | None:
    """The rules' placement of one figure on a table the model already has: which table, its measure, the date it counts at, the dimensions (reached by
    joins), and a filter for each listed value the figure names (calls -> movement_type = 'call'). None when no table fits."""
    dims = _dims(k, grain["dims"])
    text = f"{k.get('name')} {k.get('definition') or ''}"
    words = _toks(text) - {_stem(d) for d in dims} - set(_PERIOD)
    own = _toks(k.get("name")) - {_stem(d) for d in dims} - set(_PERIOD)  # UC6 H1: a figure is named after what it counts (uncalled commitment)
    best = next((r for r in [rank_tables(plane, own)[0]] if r["score"] >= 3), None) if own else None
    best = best or (rank_tables(plane, words)[0] if words else None)
    if not best or best["score"] < 3:
        return None
    t = cat[best["table"]]
    kind = _kind(k)
    num = [c["name"] for c in t["columns"] if str(c["type"]).lower().startswith(("numeric", "decimal", "double", "int", "bigint", "float")) and not c["name"].endswith("_id")]
    meas = next((c for c in num if words & _toks(c.replace("_", " "))), None) or next((c for c in num if "amount" in c), None) or (num[0] if num else None)
    if kind != "count" and meas is None:
        return None
    dates = [c["name"] for c in t["columns"] if str(c["type"]).lower().startswith(("date", "timestamp")) and not c["name"].startswith(("recorded", "received", "called"))]
    named = next((c for c in dates if words & (_toks(c.replace("_", " ")) - {"date"})), None)  # "due date" names due_date, not every date
    when = named or next((c for c in dates if "effective" in c or "trade" in c), None) or (dates[0] if dates else None)
    if when is None:
        return None
    m = _WINDOW.search(str(k.get("definition") or "")) or _WINDOW.search(str(k.get("name") or ""))
    # ponytail: a window is counted from each month end only; a daily or weekly as-at needs its own spine
    window = (int(m.group(2) or 0), int(m.group(1) or m.group(3))) if m and named and grain.get("period", "monthly") in ("month", "monthly") else None
    joins, dexp = [], []
    for d in dims:
        got = _reach(cat, refs, best["table"], _stem(d))
        if got is None:
            return None
        dexp.append((d, got[0]))
        joins += [j for j in got[1] if j not in joins]
    keep = words - {_stem(w.lower()) for w in _NOT.findall(text)}  # "calls not yet confirmed": confirmed is what it leaves out, not a filter
    by_col: dict[str, list[str]] = {}  # UC5: values of one column are alternatives (OR), different columns all hold (AND)
    for c in t["columns"]:
        for v in _enum(c.get("note")):
            if {_stem(x) for x in re.findall(r"[a-z]+", v)} & keep:
                by_col.setdefault(c["name"], []).append(f"f.{c['name']} = '{v}'")
    filt = [x[0] if len(x) == 1 else "(" + " or ".join(x) + ")" for x in by_col.values()]
    sup = next((c["name"] for c in t["columns"] if c["name"].startswith("supersedes_") and c["name"].endswith("_id")), None)
    return {"table": best["table"], "kind": kind, "measure": meas, "when": when, "dims": dexp, "joins": joins, "filter": filt, "window": window,
            "dates": dates, "supersedes": sup if any(c["name"] == "id" for c in t["columns"]) else None}


def _rest(d: str) -> str:
    """The definition less what the rules do write (a day window, a word it leaves out), to see whether a condition is left over."""
    return _NOT.sub(" ", _WINDOW.sub(" ", d))


def _rules_design(plane, slug: str, kpis: list[dict], grain: dict, notes: list[str]) -> dict:
    """The design without a model, reusing the company model first: each figure is placed on the table that holds its records, grouped by that table and
    its dimensions into gold tables. A figure whose definition carries a condition the rules cannot write, or that no table fits, is still a column or a
    listed gap with a "Define the KPI" note, never silently dropped. No silver table is invented here."""
    cat = {t["name"]: t for t in E.current(plane)["tables"]}
    refs = E.current(plane)["refs"]
    period = _PERIOD.get(grain.get("period", "monthly"), "month")
    groups: dict[tuple, list] = {}
    for k in kpis:
        fit = _fit_kpi(plane, k, grain, cat, refs)
        d = str(k.get("definition") or k.get("formula") or "").strip()
        if fit is None:
            notes.append(f"Define the KPI '{k.get('name')}': no table of the company model holds its records, so it is not in a gold table yet. "
                         "Ask Span for a model change if a new fact must be kept.")
            continue
        if _not_a_plain_total(k, f"{k.get('name')} {d}"):  # UC5: a share or a conditional count is never shown as a plain total under its name
            notes.append(f"Define the KPI '{k.get('name')}': it is a share or a count under a condition, which a plain total of the "
                         f"{fit['table'].replace('_', ' ')} cannot give, so it is not in a gold table yet.")
            continue
        have = {c["name"] for c in cat[fit["table"]]["columns"]}
        if fit["table"] == "commitments" and _UNCALLED.search(str(k.get("name"))) and {"called_to_date", "called_as_at"} <= have and not fit["window"]:
            fit = {**fit, "measure_expr": _UNCALLED_SQL}  # UC6 G: a stored called-to-date lets the rules write it
        elif _LEVEL.search(d) or _COMPARE.search(f"{k.get('name')} {d}"):  # UC6 H1: closing cash is not the sum of movements; uncalled is commitment minus called
            notes.append(f"Define the KPI '{k.get('name')}': it is a closing balance or one figure minus another, which a plain total of the "
                         f"{fit['table'].replace('_', ' ')} cannot give, so it is not in a gold table yet.")
            continue
        if "measure_expr" not in fit and (not d or _COND.search(_rest(d))):
            notes.append(f"Define the KPI '{k.get('name')}': " + ("it has no definition" if not d else "its definition has a condition the rules cannot write")
                         + f", so its column is Span's plain {'count' if fit['kind'] == 'count' else 'total'} of the {fit['table'].replace('_', ' ')} until it is defined.")
        groups.setdefault((fit["table"], fit["when"], tuple(x for x, _ in fit["dims"]), bool(fit["window"])), []).append((k, fit))
    gold = []
    for (tbl, when, dims, win), items in groups.items():
        cols, defs = [], {}
        joins = list(dict.fromkeys(j for _, f in items for j in f["joins"]))
        dexp = dict(x for _, f in items for x in f["dims"])
        for k, f in items:
            col = _slug(k.get("name"), 40)
            cond = f["filter"] + ([f"f.{when} between a.as_at + {f['window'][0]} and a.as_at + {f['window'][1]}"] if win else [])
            where = f" filter (where {' and '.join(cond)})" if cond else ""  # FILTER belongs to the aggregate, inside the cast
            m = f.get("measure_expr") or f"f.{f['measure']}"
            total = f"coalesce(sum({m}){where}, 0)" if win else f"sum({m}){where}"
            agg = f"count(*){where}" if f["kind"] == "count" else f"cast({total} as decimal(18,2))"
            cols.append(f"{agg} as {col}")
            defs[col] = str(k.get("definition") or k.get("formula") or "").strip() or "Needs a definition"
        f0 = items[0][1]
        # a figure due in a window is as at each month end: one row for each month any date of the table falls in, not the month of the due date
        head = (f"with asat as (select distinct last_day(x) as as_at from ({' union all '.join(f'select {c} as x from {tbl}' for c in f0['dates'])}) as d "
                f"where x is not null) ") if win else ""
        month = f"cast(date_trunc('{period}', a.as_at) as date)" if win else f"cast(date_trunc('{period}', f.{when}) as date)"
        sel = [f"{month} as {period}"] + [f"{dexp[d]} as {d}" for d in dims] + cols
        # ponytail: a superseded row is left out as the table stands now, not as known at each month end (k6 does that for the Office view)
        live = f" where not exists (select 1 from {tbl} as s where s.{f0['supersedes']} = f.id)" if f0["supersedes"] else ""
        name = (f"gold_{slug}_{tbl}{'_due' if win else ''}_{period}ly" + (f"_by_{'_'.join(dims)}" if dims else ""))[:63].rstrip("_")
        gold.append({"name": name, "purpose": "Figures of the intent, built on " + tbl.replace("_", " ") + ": " + ", ".join(str(k.get("name")) for k, _ in items) + "."
                     + (f" Due dates are counted from each {period} end." if win else ""),
                     "grain": f"{period.capitalize()} by {' and '.join(dims)}" if dims else period.capitalize(), "keys": [period, *dims], "col_defs": defs,
                     "kpis": [str(k.get("name")) for k, _ in items], "depends_on": [tbl, *[j[0] for j in joins], *(["cash_movements"] if any(f.get("measure_expr") for _, f in items) else [])],
                     "sql": f"create table {name} as {head}select {', '.join(sel)} from {'asat as a cross join ' if win else ''}{tbl} as f "
                            f"{' '.join(j[1] for j in joins)}{live} group by {', '.join(str(i + 1) for i in range(len(sel) - len(cols)))}".replace("  ", " ")})
    return {"silver": [], "gold": gold}


SYSTEM = ("You are Span, the architect. The company's silver tables are its data model and stay stable: REUSE them. Design the gold tables this use case "
          "needs from the signed intent's figures (kpis), reading only tables in model. Every figure in unplaced must be a column of one gold table, at the grain "
          "the intent states (one row per ...); add a table that lists each exception when the figures count exceptions (compare two sources by their source "
          "system: cash_movements rows reach their source through source_record_id -> source_records.source_batch_id -> source_batches.source_system_id). A difference between two sources where one reports balances (position_snapshots: a cash position per portfolio and day) and the other reports movements (cash_movements of that source system) is, per entity and day, the change in the balance since the first day both cover minus the sum of the movements after that day up to this one (join portfolios to legal_entities for the entity; the cash instrument is the instruments row of type cash); one row per entity and day with the entity as a column; build it on the loaded rows, never on an empty table. Gold SQL is DuckDB 'create table <name> as select ...'; write 'group by all', never column positions. Only when NO table or column of model can hold a needed fact, list a silver change "
          "in silver: prefer table = an existing table with the new columns; a new table only if no existing table fits; say what you looked_for and, for each "
          "considered table, why_not. Types from silver_types. Gold names start with gold_prefix. Never write a digit that is not in the intent. When tables_with_data is given, build on those tables: a gold table that reads only other, empty tables shows nothing. Reply with ONLY "
          "JSON {\"gold\": [{\"name\", \"purpose\", \"grain\", \"keys\": [], \"kpis\": [names], \"sql\", \"depends_on\": [tables], \"columns\": [{\"name\", "
          "\"definition\"}]}], \"silver\": [{\"table\", \"purpose\", \"looked_for\", \"considered\": [{\"table\", \"why_not\"}], \"columns\": [{\"name\", \"type\", \"note\"}]}]}.")


def _intent_numbers(ctx: dict) -> str:
    """The numbers the intent itself states ("over 5,000", "between 60 and 90"), put in the ask: the number guard lets through a number that is in the question,
    and would otherwise blank a threshold in the SQL ("amount > not available yet")."""
    found = list(dict.fromkeys(re.findall(r"\d[\d,]*(?:\.\d+)?", json.dumps({k: ctx.get(k) for k in ("kpis", "goal")}, ensure_ascii=False))))
    found = list(dict.fromkeys([*found, "100"]))  # c3 risk_officer: a share is a part over a whole times 100; without it the guard blanked the 100 and the SQL broke
    return " The intent states these numbers, which you may write in the SQL: " + ", ".join(found) + " (100 is only for turning a share into a percentage)."


def _ask_design(plane, model, viewer, pid: str, ctx: dict, ask: str = "Design the gold tables.") -> dict | None:
    """The model's design as JSON, or None. The same input gets the same reply (temperature 0, and the reply kept by a hash of the input); a call that fails
    or comes back unreadable is asked again, and only after two failed calls does the caller fall back to the rules."""
    if model is None or os.environ.get("SH_MODEL_PROVIDER", "").lower() == "off":
        return None
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.agents.runs import RunRegistry
    from sh_platform.build.agents.runtime import OpenGate
    from sh_platform.egress.providers import TEMPERATURE
    from sh_platform.v1.egress_fit import fit
    from sh_platform.v1.router import route
    fitted, question = fit(ctx), ask + _intent_numbers(ctx)
    key = hashlib.sha256(json.dumps([SYSTEM, fitted, question], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:32]
    kept = plane.path("v3", "design_cache", key + ".json")
    try:
        if kept.is_file():
            return json.loads(kept.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("a kept design reply could not be read", exc_info=True)
    for attempt in (1, 2):
        token = TEMPERATURE.set(0)
        try:
            res = run_agent(route(model, "span", "plan", "", plane, want_json=True), ToolRegistry(OpenGate()), plane.company_id, "m3_connect", "Span", SYSTEM,
                            fitted, question, recorder=RunRegistry(plane))
            a, b = res.text.find("{"), res.text.rfind("}")
            got = json.loads(res.text[a:b + 1]) if res.status == "done" and 0 <= a < b else None
        except Exception:  # noqa: BLE001 - a failed call is asked again; two failed calls leave the rules' design
            log.warning("Span's design call %s failed", attempt, exc_info=True)
            got = None
        finally:
            TEMPERATURE.reset(token)
        if got is not None:
            try:
                kept.parent.mkdir(parents=True, exist_ok=True)
                kept.write_text(json.dumps(got, sort_keys=True), encoding="utf-8")
            except OSError:
                log.warning("a design reply could not be kept", exc_info=True)
            return got
    log.warning("Span's design call failed twice; rules only")
    return None


def justify(plane, s: dict, words: set[str]) -> dict:
    """A silver change with what was looked for and the tables considered with why they do not fit (the model's words, else worked out from the ranking)."""
    top = [r for r in rank_tables(plane, words) if r["score"]][:3]
    why = {str(c.get("table")): str(c.get("why_not") or "")[:200] for c in s.get("considered") or [] if isinstance(c, dict)}
    s["looked_for"] = str(s.get("looked_for") or s.get("purpose") or "")[:300]
    own = [{"table": t, "why_not": w} for t, w in why.items() if t and w]
    s["considered"] = own + [{"table": r["table"], "why_not": "Matches " + ", ".join(r["matched"]) + (" but has nothing for " + ", ".join(r["missing"]) if r["missing"] else "")}
                             for r in top if r["table"] not in why and r["table"] != s.get("name")][:max(0, 3 - len(own))]
    return s


def _from_model(plane, got: dict, slug: str, words: set[str]) -> dict:
    cat = {t["name"] for t in E.current(plane)["tables"]}
    silver = []
    for s in got.get("silver") or []:
        name = str(s.get("table") or s.get("name") or "") if isinstance(s, dict) else ""
        if _NAME.fullmatch(name):
            try:
                cols = check_columns([{"name": str(c.get("name") or ""), "type": str(c.get("type") or "text"), "note": str(c.get("note") or "")[:200]}
                                      for c in s.get("columns") or [] if isinstance(c, dict)])
                silver.append(justify(plane, {**s, "name": name, "purpose": str(s.get("purpose") or "")[:300], "columns": cols, "extends": name in cat}, words))
            except Refused as e:
                log.warning("a silver change of the design was dropped: %s", e.message)
    gold = []
    for g in got.get("gold") or []:
        if isinstance(g, dict) and str(g.get("name") or "").startswith(f"gold_{slug}_") and str(g.get("sql") or "").strip():
            gold.append({"name": str(g["name"]), "purpose": str(g.get("purpose") or "")[:300], "grain": str(g.get("grain") or "")[:200],
                         "keys": [str(x) for x in g.get("keys") or []], "kpis": [str(x) for x in g.get("kpis") or []], "sql": str(g["sql"]),
                         "depends_on": [str(x) for x in g.get("depends_on") or []],
                         "col_defs": {E.slug(c.get("name")): str(c.get("definition") or "")[:600] for c in g.get("columns") or [] if isinstance(c, dict) and c.get("name")}})
    return {"silver": silver, "gold": gold}


def design(plane, viewer, pid: str, sow: dict, plan: dict, grain: dict, model=None) -> dict:
    """Place the figures the plan could not place. Returns the plan with the designed gold tables added (and `model_changes` and `new_silver` set when the
    model needs a change), its notes updated: a placed figure loses its "could not place" note, one that needs a definition gains a "Define the KPI" note."""
    notes = plan.setdefault("notes", [])
    unplaced = [m.group(1) for n in notes if (m := _UNPLACED.search(n))]
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("name") in unplaced]
    if not kpis:
        return plan
    slug = plan["project_slug"]
    from sh_platform.v1 import v3_recipes as R  # A7: a figure with a recipe (or a design this office saved) is built from it; the model is asked for the rest
    kpis = R.place(plane, viewer, pid, kpis, slug, grain, plan, notes)
    if not kpis:
        return plan
    words = set().union(*[_toks(f"{k.get('name')} {k.get('definition') or ''}") for k in kpis])
    ranked = rank_tables(plane, words)
    schema = {t["name"]: [c["name"] for c in t["columns"]] for t in E.current(plane)["tables"]}
    ctx = {"unplaced": [k["name"] for k in kpis], "kpis": [{x: k.get(x) for x in ("name", "definition", "unit", "period", "benchmark_by")} for k in kpis],
           "goal": (sow.get("goal") or {}).get("line"), "model": {r["table"]: schema[r["table"]] for r in ranked[:12] if r["score"]} or {t: [] for t in schema},
           "model_tables": sorted(schema), "gold_prefix": f"gold_{slug}_", "silver_types": SILVER_TYPES, **({"tables_with_data": sorted(_PREFER.get())} if _PREFER.get() else {})}
    got = _ask_design(plane, model, viewer, pid, ctx)
    mine = _from_model(plane, got, slug, words) if got else {"silver": [], "gold": []}
    rules = None
    from sh_platform.v1 import b6_span as S
    tries = [mine, None]
    for attempt in tries:  # the model's design, its one repair, then the rules
        if attempt is None:
            rules = rules or _rules_design(plane, slug, kpis, grain, notes)
            attempt = rules
        attempt["gold"][:] = R.allowed(attempt["gold"], notes, kpis)  # A8: a design that reads a table its figure's recipe forbids is dropped, with the reason
        if not attempt["gold"]:
            continue
        change = file_model_change(plane, viewer, pid, attempt["silver"]) if attempt["silver"] else None
        trial_notes: list[str] = []
        ok = S.keep_valid(plane, {**plan, "model_changes": change["version"] if change else plan.get("model_changes")},
                          [{"name": g["name"], "layer": "gold", "purpose": g["purpose"], "columns": [], "sql": g["sql"], "depends_on": g["depends_on"],
                            **{x: g[x] for x in ("grain", "keys", "col_defs", "kpis") if g.get(x)}} for g in attempt["gold"]], trial_notes)
        if ok:
            break
        if attempt is mine and len(tries) == 2:  # UC6 H1: the plan check's words go back to the model once ("Expected END after CASE") before the rules
            fixed = _ask_design(plane, model, viewer, pid, {**ctx, "your_design": got, "plan_check_said": trial_notes},
                                "Your design failed the plan check (plan_check_said). Fix it and reply with the whole design again.")
            if fixed:
                mine = _from_model(plane, fixed, slug, words)
                tries.insert(1, mine)
                continue
        notes.extend(trial_notes)
    else:
        for k in kpis:
            if not any(f"Define the KPI '{k['name']}'" in n for n in notes):
                notes.append(f"Define the KPI '{k['name']}': Span could not place it on a gold table.")
        plan["notes"] = [n for n in notes if not ((m := _UNPLACED.search(n)) and m.group(1) in {k["name"] for k in kpis})]
        return plan
    placed = {k for t in ok for k in t.get("kpis") or []}
    gap = {k["name"] for k in kpis if k["name"] not in placed}
    if attempt is mine:  # the model's design: a figure it left out, or with no definition, is listed rather than dropped
        notes += [f"Define the KPI '{k['name']}': Span could not place it on a gold table." for k in kpis if k["name"] in gap]
        notes += [f"Define the KPI '{k['name']}': it has no definition, so its column holds Span's draft until it is defined."
                  for k in kpis if k["name"] in placed and not (k.get("definition") or k.get("formula"))]
    plan["notes"] = [n for n in notes if not ((m := _UNPLACED.search(n)) and (m.group(1) in placed or m.group(1) in gap))]  # "Define the KPI" is the listing
    plan["tables"] = plan["tables"] + ok
    if attempt is mine:
        plan["built_by"] = "rules and model"
    plan["new_silver"] = attempt["silver"] if change else []
    if change:
        plan["model_changes"] = change["version"]
    return plan
