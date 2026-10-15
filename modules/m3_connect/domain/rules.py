"""Rules Lens compiles (M3-P03): check a rule against the columns that exist, fix its column names, say it in plain words, keep rules.json.

The shape is SHARED.md's (op, column, filters, period, ratio parts), plus the few extras the engine documents (group_by/pick/having, left/right).
A rule is data, never code. `rules.json` is {measure_id: record}; record = {measure, state: draft|checked|could_not_compile, origin
(technical|definition|pack hint), rule, words, reason, checked_by, checked_at, compiled_at}. A checked rule is a human's: a recompile never replaces it.
"""
import copy
import re
from datetime import datetime, timezone
from pathlib import Path

from modules.m3_connect.domain import engine as E
from modules.m3_connect.domain import intake_match as M
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

STATES = ("draft", "checked", "could_not_compile")
COULD_NOT = "could_not_compile"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_file(adir: Path, name: str, default):
    try:
        d = read_json_strict(adir / name)
    except (OSError, ValueError):
        return default
    return d if isinstance(d, type(default)) else default  # a missing file reads as None


def write_file(adir: Path, name: str, data) -> None:
    with lock_for(adir):
        write_json_atomic(adir / name, data)


def read_rules(adir: Path) -> dict:
    d = read_file(adir, "rules.json", {})
    return d if isinstance(d, dict) else {}


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _fix_deductions(node: dict) -> None:
    """A difference taken inside a ratio's top is a deduction (net of fees): the trial can then show the figure without it."""
    top = node.get("numerator") if node.get("op") == "ratio" and isinstance(node.get("numerator"), dict) else {}
    if top.get("op") == "difference" and (top.get("right") or {}).get("op") == "sum":
        top["deduction"] = True
    for k in ("numerator", "denominator", "left", "right"):
        if isinstance(node.get(k), dict):
            _fix_deductions(node[k])


def shape_problems(node, top=True) -> list[str]:
    """What is wrong with the rule's form, in plain words; [] when it can be run."""
    if not isinstance(node, dict):
        return ["the rule is not an object"]
    op = node.get("op")
    if op in E.COMBINE:
        keys = ("numerator", "denominator") if op == "ratio" else ("left", "right")
        bad = ["the scale must be 1 or 100"] if "scale" in node and (isinstance(node["scale"], bool) or node["scale"] not in (1, 100)) else []
        return bad + [p for k in keys for p in (shape_problems(node.get(k), False) if isinstance(node.get(k), dict) else [f"{op} needs a {k}"])]
    if op not in E.LEAF:
        return [f"the operation {op!r} is not one Lens can run"]
    out = []
    if op != "count" and not str(node.get("column") or "").strip():
        out.append(f"{op} needs a column")
    for f in node.get("filters") or []:
        if not isinstance(f, dict) or f.get("op") not in E.FILTER_OPS or not f.get("column") or (f["op"] != "not_null" and "value" not in f):
            out.append("a filter is not in the form column, op, value")
        elif f["op"] == "in" and not isinstance(f["value"], list) or f["op"] == "between" and not (isinstance(f["value"], list) and len(f["value"]) == 2):
            out.append("a filter's value does not fit its op")
        elif f["op"] == "listed_in" and not (isinstance(f["value"], str) and isinstance(f.get("where", ""), str)):
            out.append("a listed_in filter needs the column of the other list, and optionally one that must be filled")
    p = node.get("period")
    if p is not None and not (isinstance(p, dict) and p.get("column")):
        out.append("the period names no column")
    h = node.get("having")
    if h and not (isinstance(h, dict) and {"column", "older_than_business_days"} <= set(h)):
        out.append("the 'having' part is not in the form column, older_than_business_days")
    elif h and (isinstance(h["older_than_business_days"], bool) or not isinstance(h["older_than_business_days"], int) or h["older_than_business_days"] < 0):
        out.append("older_than_business_days must be a whole number, zero or more")
    if node.get("group_by") is not None and not (isinstance(node["group_by"], str) or (isinstance(node["group_by"], list) and all(isinstance(g, str) for g in node["group_by"]))):
        out.append("group_by must be a column or a list of columns")
    if op in ("latest", "first") and not (node.get("order_by") or (p or {}).get("column")):
        out.append(f"{op} needs a column to order by")
    return out


def _find(name: str, columns, synonyms: dict | None) -> str | None:
    """The column a rule's name means: the same ignoring case and punctuation, else a spelling the pack knows or the same words (the matcher P02
    matches uploaded columns with, domain/intake_match.py, so a catalogue with the office's own spaced names resolves the pack's hints too)."""
    for c in columns:
        if _key(c) == _key(name):
            return c
    spellings = M.pack_spellings(synonyms or {}, name)
    return next((c for c in columns if M._name_score(c, name, spellings)[0] == 3), None)


def resolve(rule: dict, columns: dict[str, dict], feeders: list[str] = (), synonyms: dict | None = None) -> tuple[dict, list[str]]:
    """(rule with real column names and a source on every leaf, problems). `columns` = {source_id: {column name: type}};
    a name matches a column as `_find` says; the source is the first (a feeder of the measure first) that has them all."""
    rule = copy.deepcopy(rule)
    problems = shape_problems(rule)
    if problems:
        return rule, problems
    order = [s for s in feeders if s in columns] + [s for s in columns if s not in feeders]
    for leaf in E.leaves(rule):
        need = E.columns_of(leaf)
        chosen = None
        for sid in order:
            found = {n: _find(n, columns[sid], synonyms) for n in need}
            if all(found.values()):
                chosen, mapping = sid, found
                break
        if chosen is None:
            missing = sorted(n for n in need if not any(_find(n, cols, synonyms) for cols in columns.values()))
            problems.append(("the column " + ", ".join(missing) + " is not in the data received") if missing
                            else "the columns it needs are not all in one source")
            continue
        leaf["source"] = chosen
        problems += _join(leaf, [s for s in order if s != chosen], columns, synonyms)
        _rename(leaf, mapping)
    _fix_deductions(rule)
    return rule, problems


def _join(leaf: dict, others: list[str], columns: dict[str, dict], synonyms: dict | None) -> list[str]:
    """Each listed_in filter reads another source: the first (a feeder first) that has its columns; its source and real column names are set."""
    out = []
    for f in E.joined(leaf):
        need = [c for c in (f["value"], f.get("where")) if c]
        for sid in others:
            found = {n: _find(n, columns[sid], synonyms) for n in need}
            if all(found.values()):
                f["source"] = sid
                f["value"], f["where"] = found[f["value"]], found.get(f.get("where"))
                if not f["where"]:
                    del f["where"]
                break
        else:
            out.append("the column " + ", ".join(sorted(need)) + " is not in the data received")
    return out


def _rename(leaf: dict, m: dict) -> None:
    if leaf.get("column"):
        t = E.terms(leaf["column"])
        leaf["column"] = " ".join([m[t[0][1]]] + [f"{'+' if s > 0 else '-'} {m[c]}" for s, c in t[1:]])
    for f in leaf.get("filters") or []:
        f["column"] = m[f["column"]]
        if f["op"] == "not_in_column":
            f["value"] = m[f["value"]]
    for k in ("order_by",):
        if leaf.get(k):
            leaf[k] = m[leaf[k]]
    if (leaf.get("period") or {}).get("column"):
        leaf["period"]["column"] = m[leaf["period"]["column"]]
    g = leaf.get("group_by")
    if g:
        leaf["group_by"] = m[g] if isinstance(g, str) else [m[x] for x in g]
    if leaf.get("having"):
        leaf["having"]["column"] = m[leaf["having"]["column"]]


# ---- plain words ------------------------------------------------------------------------------------------------------------------------
def _cols(column: str) -> str:
    return "".join((" minus " if sg < 0 else " plus ") * (i > 0) + E.label(t) for i, (sg, t) in enumerate(E.terms(column)))


def _list(v) -> str:
    v = [str(x) for x in v]
    return ", ".join(v[:-1]) + " or " + v[-1] if len(v) > 1 else "".join(v)


def _filter(f: dict) -> str:
    c, op, v = E.label(f["column"]), f["op"], f.get("value")
    if op == "in":
        return f"{c} is {_list(v)}"
    if op == "between":
        return f"{c} is between {v[0]} and {v[1]}"
    if op == "not_in_column":
        return f"{c} was not replaced (it is not listed in {E.label(str(v))})"
    if op == "listed_in":
        return f"{c} is in the list of {E.label(str(v))}" + (f" that has a {E.label(f['where'])}" if f.get("where") else "")
    return {"eq": f"{c} is {v}", "ne": f"{c} is not {v}", "not_null": f"{c} is filled in", "not_contains": f"{c} does not say \"{v}\""}[op]


def _leaf_words(n: dict) -> str:
    op, col = n["op"], _cols(n.get("column") or "")
    gb = n.get("group_by")
    gb = [gb] if isinstance(gb, str) else list(gb or [])
    by = " and ".join(E.label(g) for g in gb)
    if op == "count":
        s = f"the number of different {by}" if gb else f"the number of rows with a {col}" if col else "the number of rows"
        if n.get("having"):
            h = n["having"]
            s += f" whose newest {E.label(h['column'])} is more than {h['older_than_business_days']} business days before the latest one"
    elif gb:
        s = f"the {'largest' if n.get('pick', 'max') == 'max' else 'smallest'} {by} total of {col}"
    else:
        s = {"sum": f"the sum of {col}", "avg": f"the average of {col}", "min": f"the lowest {col}", "max": f"the highest {col}",
             "latest": f"the latest {col}", "first": f"the first {col}"}[op]
    f = "".join(f", where {_filter(x)}" if i == 0 else f" and {_filter(x)}" for i, x in enumerate(n.get("filters") or []))
    p = n.get("period") or {}
    when = (f", for {E.label(p['column'])} from {'the start of the period' if p['from'] == 'benchmark_start' else p['from']}" if p.get("from") else "") + \
           (f" up to {'the period end of your figure' if p.get('to') == 'benchmark_end' else p['to']}" if p.get("to") else "") if p.get("column") else ""
    return s + f + when


def words(rule: dict) -> str:
    """The rule in plain words, e.g. "The sum of closing value minus opening value, less the sum of fees (net of fees), divided by ..."."""
    def w(n: dict) -> str:
        if n["op"] == "ratio":
            return f"{w(n['numerator'])}, divided by {w(n['denominator'])}" + (" (as a percentage)" if n.get("scale") in (100, "100") else "")
        if n["op"] == "difference":
            return f"{w(n['left'])}, less {w(n['right'])}" + (f" (net of {E.label(next(E.leaves(n['right']))['column'])})" if n.get("deduction") else "")
        return _leaf_words(n)
    s = w(rule)
    return s[:1].upper() + s[1:] + "."


def set_scale(rule: dict, unit: str) -> dict:
    """A top-level ratio with no scale is a share; a figure reported in per cent is compared on the same scale."""
    r = copy.deepcopy(rule)
    if r.get("op") == "ratio" and "scale" not in r and str(unit).strip().lower() in ("%", "percent", "per cent"):
        r["scale"] = 100
    return r


def hint_for(pack_kpis: list, measure_id: str) -> dict | None:
    """The pack's rule hint for a measure (a suggestion; kpi_tree.yaml `rule`), or None."""
    k = next((k for k in pack_kpis or [] if isinstance(k, dict) and k.get("id") == measure_id), None)
    return copy.deepcopy(k["rule"]) if k and isinstance(k.get("rule"), dict) else None
