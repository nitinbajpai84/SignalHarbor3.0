"""The trial (M3-P03): Lens's figure for each measure next to the one the customer reports, the result, and the likely reason.

Reads module 3's other files only through the three functions below (the one place to change if P02's files move):
  rows_for(assessment_dir, source_id)  -> list[dict]   intake/<source_id>/rows.json, keys = matched catalogue field names
  profile_for(assessment_dir, source_id) -> dict       {rows, columns: {name: {type, fill, min, max}}, gaps}, from intake/<source_id>/profile.json,
                                                         anything it lacks worked out from the rows
  benchmarks(assessment_dir)           -> list[dict]   benchmarks.json: measure_id, figure, unit, period_end, source_note
trial.json = {measure_id: entry}; the reasons are deterministic, from counts, dates and column names; Lens may only reword them (agent/explain.py).
"""
import re
from decimal import Decimal
from pathlib import Path

import yaml

from sh_platform.jsonfile import read_json_strict

from modules.m3_connect.domain import engine as E
from modules.m3_connect.domain import rules as R

CONTRACT = yaml.safe_load((Path(__file__).resolve().parents[1] / "contracts" / "trial.yaml").read_text(encoding="utf-8"))


# ---- the reader interface (P02's files) ------------------------------------------------------------------------------------------------
def _load(path: Path):
    """A JSON file of any shape; None when it is missing or unreadable (R.read_file only returns the shape of its default)."""
    try:
        return read_json_strict(path)
    except (OSError, ValueError):
        return None


def _field_names(adir: Path, source_id: str) -> dict[str, str]:
    """{catalogue field id: catalogue field name} from the source's profile.json `expected` list (P02)."""
    prof = R.read_file(Path(adir) / "intake" / str(source_id), "profile.json", {})
    return {str(e["field_id"]): str(e["name"]) for e in prof.get("expected") or [] if isinstance(e, dict) and e.get("field_id") and e.get("name")}


def rows_for(assessment_dir: Path, source_id: str) -> list[dict]:
    """P02's rows.json ({source_id, tables: [{columns: [{name, field_id}], rows}]}): every table's rows, a matched column keyed by its catalogue
    field name (found through field_id), an unmatched one by its own name. A plain list of rows is read as it is.
    ponytail: tables of one source are concatenated; give each leaf a table_id if a source ever holds two tables with the same columns."""
    d = _load(Path(assessment_dir) / "intake" / str(source_id) / "rows.json")
    if isinstance(d, list):
        return [r for r in d if isinstance(r, dict)]
    if not isinstance(d, dict):
        return []
    names, out = _field_names(assessment_dir, source_id), []
    for t in d.get("tables") or []:
        if not isinstance(t, dict):
            continue
        rename = {c["name"]: names.get(str(c.get("field_id")), c["name"]) for c in t.get("columns") or [] if isinstance(c, dict) and c.get("name")}
        out += [{rename.get(k, k): v for k, v in r.items()} for r in t.get("rows") or [] if isinstance(r, dict)]
    return out


def _kind(values: list) -> str:
    vals = [v for v in values if not E.empty(v)]
    if vals and all(E.num(v) is not None for v in vals):
        return "number"
    if vals and all(isinstance(v, str) and len(v) >= 10 and v[4:5] == "-" and v[:4].isdigit() for v in vals):
        return "date"
    return "text"


def profile_for(assessment_dir: Path, source_id: str) -> dict:
    rows = rows_for(assessment_dir, source_id)
    raw = R.read_file(Path(assessment_dir) / "intake" / str(source_id), "profile.json", {})
    cols: dict[str, dict] = {}
    for name in dict.fromkeys(k for r in rows for k in r):
        vals = [r.get(name) for r in rows]
        full = [v for v in vals if not E.empty(v)]
        t = _kind(vals)
        cols[name] = {"type": t, "fill": len(full) / len(vals) if vals else 0.0,
                      "min": min(map(str, full)) if t == "date" and full else None, "max": max(map(str, full)) if t == "date" and full else None}
    given = raw.get("columns") if isinstance(raw, dict) else None
    for c in (given.values() if isinstance(given, dict) else given or []):  # tolerant of a list or a dict of per-column facts
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("field") or c.get("column")
        if name in cols or (name and not rows):
            span = c.get("date_range") if isinstance(c.get("date_range"), dict) else {}
            cur = cols.setdefault(name, {"type": "text", "fill": 0.0, "min": None, "max": None})
            cur.update({k: v for k, v in (("type", c.get("type")), ("fill", c.get("fill_rate", c.get("fill"))),
                                          ("min", c.get("min", span.get("from"))), ("max", c.get("max", span.get("to")))) if v is not None})
    return {"rows": len(rows) or int((raw or {}).get("row_count") or 0), "columns": cols,
            "gaps": [g for g in (raw.get("gaps") or []) if isinstance(g, dict)] if isinstance(raw, dict) else []}


def benchmarks(assessment_dir: Path) -> list[dict]:
    """P02's benchmarks.json ({file, measures: {measure_id: {figure, unit, period_end, came_from, ...}}, unmatched}) as a list of
    {measure_id, figure, unit, period_end, source_note}. A plain list in that form is read as it is."""
    d = _load(Path(assessment_dir) / "benchmarks.json")
    if isinstance(d, dict):
        d = [{"measure_id": k, "figure": v.get("figure"), "unit": v.get("unit"), "period_end": v.get("period_end"), "source_note": v.get("came_from")}
             for k, v in (d.get("measures") or {}).items() if isinstance(v, dict)]
    return [b for b in d if isinstance(b, dict) and b.get("measure_id")] if isinstance(d, list) else []


def source_ids(adir: Path) -> list[str]:
    base = Path(adir) / "intake"
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "rows.json").is_file()) if base.is_dir() else []


def source_marks(adir: Path) -> list[dict]:
    """P01's sources.json ({sources: [...]} or a list: id, name, measures fed, extra marks); [] until it exists."""
    d = _load(Path(adir) / "sources.json")
    d = d.get("sources") if isinstance(d, dict) else d  # P01 writes {scored_at, sources: [...]}
    return [s for s in d if isinstance(s, dict) and s.get("id")] if isinstance(d, list) else []


def feeders(adir: Path, measure_id: str) -> list[str]:
    return [str(s["id"]) for s in source_marks(adir) if measure_id in [str(m) for m in s.get("measures") or s.get("measures_fed") or []]]


def columns_by_source(adir: Path) -> dict[str, dict]:
    return {sid: {c: v["type"] for c, v in profile_for(adir, sid)["columns"].items()} for sid in source_ids(adir)}


# ---- the trial -------------------------------------------------------------------------------------------------------------------------
def _dec(v) -> Decimal | None:
    return E.num(v)


def result_for(ours: float | None, theirs: Decimal | None) -> str:
    if ours is None or theirs is None:
        return "cannot"
    t = CONTRACT["tolerance"]
    diff = abs(Decimal(str(ours)) - theirs)
    return "matches" if diff <= max(Decimal(str(t["absolute"])), Decimal(str(t["relative"])) * abs(theirs)) else "gap"


def _date_columns(rule: dict) -> list[tuple[str, str]]:
    out = []
    for lf in E.leaves(rule):
        for c in ((lf.get("period") or {}).get("column"), lf.get("order_by"), (lf.get("having") or {}).get("column")):
            if c:
                out.append((lf.get("source") or "", c))
    return out


def _reasons(adir, rec: dict, rule: dict, res: dict, bench: dict, definition: str, rowsfn) -> list[str]:
    T, out = CONTRACT["reasons"], []
    end = str(bench.get("period_end") or "")[:10]
    ends = [m for s, c in _date_columns(rule) if (m := profile_for(adir, s)["columns"].get(c, {}).get("max"))]
    if end and ends and max(map(str, ends)) < end:
        out.append(T["data_ends"].format(data_end=E.day_words(max(map(str, ends))), bench_end=E.day_words(end)))
    for lf in E.leaves(rule):
        to = (lf.get("period") or {}).get("to")
        if end and to and to != "benchmark_end" and to != end:
            out.append(T["period_end"].format(bench_end=E.day_words(end), rule_end=E.day_words(to)))
            break
    ded = next((n for n in _walk(rule) if n.get("deduction")), None)
    if ded and set(CONTRACT["net_words"]) & set(re.findall(r"[a-z]+", definition.lower())):
        without = E.run(rule, rowsfn, end or None, drop_deduction=True)["value"]
        if result_for(without, _dec(bench.get("figure"))) == "matches":
            out.append(T["net"].format(what=E.label(next(E.leaves(ded["right"]))["column"])))
    for col, n in sorted(res["skipped"].items()):
        if res["rows"] and n / res["rows"] >= CONTRACT["empty_share"]:
            out.append(T["half_empty"].format(column=E.label(col).capitalize(), n=n, total=res["rows"]))
    if any(g.get("kind") == "rows_missing" for s in {lf.get("source") or "" for lf in E.leaves(rule)} for g in profile_for(adir, s)["gaps"]):
        out.append(T["rows_missing"])
    return out or [T["none_found"]]


def _walk(n: dict):
    yield n
    for k in ("numerator", "denominator", "left", "right"):
        if isinstance(n.get(k), dict):
            yield from _walk(n[k])


def measure_trial(adir: Path, mid: str, rec: dict | None, bench: dict | None, definition: str = "") -> dict:
    """One measure's trial entry. A figure that is missing is None, never zero."""
    T = CONTRACT["reasons"]
    out = {"measure": mid, "our_figure": None, "their_figure": None, "unit": (bench or {}).get("unit"), "period_end": (bench or {}).get("period_end"),
           "source_note": (bench or {}).get("source_note"), "difference": None, "relative": None, "result": "cannot", "reasons": [], "likely_reason": "",
           "missing": None, "skipped": {}, "rows": 0, "groups": [], "suppressed_groups": 0, "computed_at": R.now(),
           "rule_state": (rec or {}).get("state", "none"), "checked_by": (rec or {}).get("checked_by")}
    theirs = _dec((bench or {}).get("figure"))
    out["their_figure"] = None if theirs is None else float(theirs)
    if not rec or rec.get("state") == R.COULD_NOT or not rec.get("rule"):
        out["missing"] = T["no_rule"].format(why=(rec or {}).get("reason") or "no rule has been written yet") if rec else T["no_rule"].format(why="no rule has been written yet")
        return out
    rule = R.set_scale(rec["rule"], str((bench or {}).get("unit") or ""))
    cache = {}
    def rowsfn(sid):
        if sid not in cache:
            cache[sid] = rows_for(adir, sid) or None
        return cache[sid]
    for lf in E.leaves(rule):
        have = profile_for(adir, lf.get("source") or "")["columns"]
        gone = sorted(c for c in E.columns_of(lf) if c not in have)
        if not rowsfn(lf.get("source") or ""):
            out["missing"] = T["no_data"]
            return out
        if gone:
            out["missing"] = T["missing_column"].format(column=E.label(gone[0]).capitalize())
            return out
    end = str((bench or {}).get("period_end") or "")[:10] or None
    res = E.run(rule, rowsfn, end)
    out.update(skipped=res["skipped"], rows=res["rows"], groups=res["groups"], suppressed_groups=res["suppressed_groups"], our_figure=res["value"])
    if res["cannot"]:
        out["missing"] = res["cannot"][:1].upper() + res["cannot"][1:] + "."
    elif theirs is None:
        out["missing"] = T["no_benchmark"]
    if res["value"] is not None and theirs is not None:
        d = Decimal(str(res["value"])) - theirs
        out["difference"] = float(d)
        out["relative"] = float(d / abs(theirs)) if theirs else None
    if res["picked_size"] is not None and res["picked_size"] < CONTRACT["min_group"]:
        out["group_note"] = T["group_hidden"]  # the chosen group's own figure is not shown; the overall figure stays
    out["result"] = result_for(res["value"], theirs)
    if out["result"] == "gap":
        out["reasons"] = _reasons(adir, rec, rule, res, bench, definition, rowsfn)
        out["likely_reason"] = " ".join(out["reasons"][:2])
    elif out["result"] == "cannot":
        out["reasons"] = [out["missing"]] if out["missing"] else []
        out["likely_reason"] = out["missing"] or ""
    return out


def run_trial(adir: Path, measures: list[dict]) -> dict:
    """Runs every measure in `measures` (the ones the caller may see) and merges into trial.json; entries for other measures are kept."""
    rules, bench = R.read_rules(adir), {b["measure_id"]: b for b in benchmarks(adir)}
    done = R.read_file(adir, "trial.json", {})
    done = done if isinstance(done, dict) else {}
    for m in measures:
        if not m.get("restricted"):
            try:
                done[m["id"]] = measure_trial(adir, m["id"], rules.get(m["id"]), bench.get(m["id"]), str(m.get("definition") or ""))
            except (ArithmeticError, ValueError, TypeError, KeyError, AttributeError):  # one bad rule never fails the others
                done[m["id"]] = {**measure_trial(adir, m["id"], None, bench.get(m["id"])), "missing": CONTRACT["reasons"]["bad_rule"]}
                done[m["id"]]["likely_reason"] = CONTRACT["reasons"]["bad_rule"]
    R.write_file(adir, "trial.json", done)
    return auto_check(adir, measures, done)


AUTO_BY = "Lens (matches your figure)"


def auto_check(adir: Path, measures: list[dict], done: dict) -> dict:
    """LI-M3: a rule whose figure matches the customer's own within the tolerance is "checked automatically (matches your figure)", so the analyst
    reviews only the gaps and the figures that cannot be worked out. A person's check is never touched; an automatic check is taken back when the rule
    stops matching (`auto_checked` is the mark)."""
    rules, changed = R.read_rules(adir), False
    for m in measures:
        rec, t = rules.get(m["id"]), done.get(m["id"])
        if not isinstance(rec, dict) or not isinstance(t, dict) or m.get("restricted") or not rec.get("rule"):
            continue
        if t.get("result") == "matches" and rec.get("state") == "draft":
            rules[m["id"]] = {**rec, "state": "checked", "checked_by": AUTO_BY, "checked_at": R.now(), "auto_checked": True}
        elif t.get("result") != "matches" and rec.get("auto_checked"):
            rules[m["id"]] = {**{k: v for k, v in rec.items() if k != "auto_checked"}, "state": "draft", "checked_by": None, "checked_at": None}
        else:
            t["auto_checked"] = bool(rec.get("auto_checked")) and rec.get("state") == "checked"
            continue
        changed = True
        r = rules[m["id"]]
        t.update(rule_state=r["state"], checked_by=r["checked_by"], auto_checked=bool(r.get("auto_checked")))
    if changed:
        R.write_file(adir, "rules.json", rules)
    R.write_file(adir, "trial.json", done)
    return done


# ---- who may see what ------------------------------------------------------------------------------------------------------------------
def source_marks_of(marks) -> list[dict]:
    return [s for s in marks or [] if isinstance(s, dict) and s.get("id")]


def hidden_measures(inputs: dict, rules: dict, viewer, full: dict | None = None, marks=(), shut: frozenset[str] = frozenset()) -> set[str]:
    """Measures this viewer must not see: restricted ones, and ones whose rule reads a field the viewer may not see. `inputs` is what
    inputs.read_inputs gave this viewer (module 2's guards applied there: the field's personal data class, the source's "Contains personal
    data?" and "Who may see it"); `full` is the same read for the head of data, so a field in `full` but not in `inputs` is withheld, whichever
    guard did it. `shut` = sources whose data came from a restricted profile sample this viewer may not see: treated as withheld. The field's own "Who may see it" list is checked here too. The head of data (company_admin) sees all."""
    hide = {m["id"] for m in inputs.get("measures") or [] if m.get("restricted")}
    organiser = "company_admin" in viewer.roles  # the organiser roles pass a field's own list (sources.field_open), but not a source or sample shut to them (A-069)
    me = " ".join(viewer.name.lower().split())
    have = {_cell(f.get("Field ID")) for f in inputs.get("fields") or []}
    bad = {R._key(_cell(f.get("Field name as in the source"))) for f in (full or {}).get("fields") or [] if _cell(f.get("Field ID")) not in have}
    for f in inputs.get("fields") or []:
        names = {" ".join(n.lower().split()) for n in str(_cell(f.get("Who may see it"))).replace(";", ",").split(",") if n.strip()}
        if names and not organiser and (me not in names or viewer.shared_name):
            bad.add(R._key(_cell(f.get("Field name as in the source"))))
    sid = lambda s: _cell(s.get("Source ID"))  # noqa: E731
    gone = ({sid(s) for s in (full or {}).get("sources") or []} - {sid(s) for s in inputs.get("sources") or []}) | set(shut)  # sources withheld from this viewer
    for s in source_marks_of(marks):
        if str(s["id"]) in gone:  # a source that feeds a measure hides it, rule or no rule
            hide |= {str(m) for m in s.get("measures") or s.get("measures_fed") or []}
    for mid, rec in rules.items():
        try:
            if rec.get("rule") and ({R._key(c) for c in E.columns_of(rec["rule"], others=True)} & bad
                                    or set().union(*(E.sources_of(lf) for lf in E.leaves(rec["rule"]))) & gone):
                hide.add(mid)
        except (KeyError, TypeError, AttributeError):  # a rule that cannot be read is hidden rather than guessed at
            hide.add(mid)
    return hide


def _cell(c) -> str:
    v = c.get("value") if isinstance(c, dict) and "mark" in c else c
    return "" if v is None else str(v)


def state(adir: Path) -> dict:
    """The "trial" step: done once the trial has been run and the analyst has checked every rule Lens wrote; in progress while the rule checks
    or the figures you report are awaited."""
    t = R.read_file(Path(adir), "trial.json", {})
    if not source_ids(adir):  # a run on no source data proves nothing yet
        return {"state": "not_started", "waiting_on": "Waiting for the source files."}
    if isinstance(t, dict) and t:
        found = R.read_file(Path(adir), "findings.json", {}).get("measures")  # rules of measures since left out are not waited on
        todo = [m for m, r in R.read_rules(adir).items() if isinstance(r, dict) and r.get("rule") and r.get("state") not in ("checked", R.COULD_NOT)
                and (not isinstance(found, dict) or m in found)]
        if todo:
            return {"state": "in_progress", "waiting_on": f"Waiting for the data analyst to check {len(todo)} rule{'s' if len(todo) != 1 else ''} Lens wrote."}
        return {"state": "done", "waiting_on": ""}
    if benchmarks(adir) or source_ids(adir):
        return {"state": "in_progress", "waiting_on": "Lens is checking its figures against yours. Nothing is needed from you."}
    return {"state": "not_started", "waiting_on": ""}
