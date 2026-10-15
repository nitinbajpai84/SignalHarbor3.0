"""The phased build plan, drafted from what Lens found (M3-P04, D-036). Pure rules plus the two reads behind `inputs_for_plan`.

Three bands (contracts/plan.yaml):
  now    weeks 0-3   ready measures
  next   weeks 3-8   unclear measures, and unknowns whose source is known
  later  8 weeks+    unknowns with no source, measures only on low-impact sources, restricted measures with an undecided risk
One item = one build: the measures of one band that need the same sources (a restricted measure is always its own item).
A person may move an item, or change its effort, team, date or the "covered by" note, with a reason; a re-draft never overwrites
such an edit: the fresh draft's value is kept beside it as a proposal (rule 7).
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from sh_platform.jsonfile import read_json_strict

CONTRACT_FILE = Path(__file__).resolve().parents[1] / "contracts" / "plan.yaml"
UNREADABLE = "The findings or the sources could not be read, so the plan was not changed. Please ask your administrator."
RESTRICTED_NAME = "A restricted measure"
SIZES = ("small", "medium", "large")
EDITABLE = ("band", "effort", "team", "date", "covered_by")


class PlanError(Exception):
    """A plain-words refusal. `code` picks the status the route answers with."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@lru_cache(maxsize=1)
def contract() -> dict:
    return yaml.safe_load(CONTRACT_FILE.read_text(encoding="utf-8"))


# ---- the reads: the only place P01's and P03's files are opened -------------------------------------------------------------------------
def _read(path: Path):
    try:
        return read_json_strict(path)
    except (OSError, ValueError):
        raise PlanError("unreadable", UNREADABLE) from None


def _strs(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else ([str(v)] if v else [])


def _flags(marks) -> set[str]:
    if isinstance(marks, dict):
        return {str(k) for k, v in marks.items() if v and k != "effort"}
    return {str(m) for m in marks} if isinstance(marks, (list, tuple, set)) else set()


def _owner(o) -> dict:
    if isinstance(o, dict):
        return {"name": str(o.get("name") or o.get("owner") or "").strip(), "role": str(o.get("role") or "").strip(),
                "team": str(o.get("team") or "").strip()}
    return {"name": str(o or "").strip(), "role": "", "team": ""}


def _source(s: dict) -> dict:
    marks = s.get("marks")
    effort = s.get("effort") or (marks.get("effort") if isinstance(marks, dict) else None)
    imp = s.get("impact")
    imp = imp.get("score") if isinstance(imp, dict) else imp
    over = s.get("override") if isinstance(s.get("override"), dict) else {}
    imp = over["impact"] if isinstance(over.get("impact"), (int, float)) and not isinstance(over.get("impact"), bool) else imp  # a person's move counts
    flags = _flags(marks) | ({"restricted"} if s.get("restricted") else set())
    return {"id": str(s.get("id")), "name": str(s.get("name") or s.get("id")), "effort": effort if effort in SIZES else None,
            "owners": [o for o in map(_owner, s.get("owners") or []) if o["name"] or o["team"]], "marks": sorted(flags),
            "impact": imp if isinstance(imp, (int, float)) and not isinstance(imp, bool) else None}


def _ids_of(v) -> list[str]:
    """Ids from a list of ids or of {id, ...} entries (P03's pain points and levers are {id, title})."""
    return [str(x.get("id")) if isinstance(x, dict) else str(x) for x in v or [] if (x.get("id") if isinstance(x, dict) else x)] if isinstance(v, (list, tuple)) else []


def _finding(f: dict, mid=None, fed: dict[str, list[str]] | None = None) -> dict:
    mid = str(f.get("measure_id") or f.get("measure") or mid)
    return {"measure_id": mid, "group": f.get("group") if f.get("group") in ("ready", "unclear", "unknown") else "unknown",
            "reasons": _strs(f.get("reasons")), "pain_points": _ids_of(f.get("pain_points")), "levers": _ids_of(f.get("levers")),
            "sources": _strs(f.get("sources")) or (fed or {}).get(mid, [])}


def _risk(r: dict) -> dict:
    return {"id": str(r.get("id")), "kind": r.get("kind") if r.get("kind") in ("risk", "ambiguity", "unknown") else "risk",
            "text": str(r.get("text") or ""), "measures": _strs(r.get("measures")), "pain_points": _ids_of(r.get("pain_points")),
            "decision": r.get("decision") if isinstance(r.get("decision"), dict) else None, "rechecked_at": r.get("rechecked_at"),
            "restricted": bool(r.get("restricted")),  # about a restricted measure: the head of data decides it
            "accepted_in_module_2": r.get("accepted_in_module_2") if isinstance(r.get("accepted_in_module_2"), dict) else None}


def inputs_for_plan(assessment_dir: Path) -> dict:
    """{ready, findings, risks, sources, left_out}: P03's findings.json ({measures: {id: entry}, risks, left_out}) and P01's sources.json
    ({sources: [...]}), read in one place (SHARED.md). The sources a measure comes from are the ones whose `measures` list it (P01 holds that).
    `ready` is False until findings.json exists. A missing sources.json reads as no sources. A list of findings (with measure_id) is read too."""
    f = _read(Path(assessment_dir) / "findings.json")
    s = _read(Path(assessment_dir) / "sources.json")
    f = f if isinstance(f, (dict, list)) else None
    rows = f if isinstance(f, list) else (f or {}).get("findings") or (f or {}).get("measures") or []
    if isinstance(rows, dict):
        rows = [{**v, "measure": v.get("measure") or k} for k, v in rows.items() if isinstance(v, dict)]
    risks = (f or {}).get("risks") or [] if isinstance(f, dict) else []
    left = (f or {}).get("left_out") or [] if isinstance(f, dict) else []
    srcs = s if isinstance(s, list) else ((s or {}).get("sources") or []) if isinstance(s, dict) else []
    fed: dict[str, list[str]] = {}
    for y in srcs:
        for m in _strs(y.get("measures")) if isinstance(y, dict) and y.get("id") else []:
            fed.setdefault(m, []).append(str(y["id"]))
    return {"ready": f is not None, "findings": [_finding(x, None, fed) for x in rows if isinstance(x, dict) and (x.get("measure_id") or x.get("measure"))],
            "risks": [_risk(x) for x in risks if isinstance(x, dict) and x.get("id")],
            "left_out": [{"measure_id": str(x["measure"]), "name": x.get("name"), "reason": str(x.get("reason") or "no reason given"), "restricted": bool(x.get("restricted"))}
                         for x in left if isinstance(x, dict) and x.get("measure")],
            "sources": {x["id"]: x for x in (_source(y) for y in srcs if isinstance(y, dict) and y.get("id"))}}


# ---- risks as the plan sees them ---------------------------------------------------------------------------------------------------------
def risk_state(risk: dict, decision: dict | None) -> str:
    """open (nobody decided), accepted, sent_back (waiting for Lens to re-check) or rechecked (sent back, re-checked since: decided)."""
    d = decision or risk.get("decision")
    what = (d or {}).get("decision") or (d or {}).get("state")
    if what == "accepted":
        return "accepted"
    if what == "sent_back":
        got = str(risk.get("rechecked_at") or "")
        return "rechecked" if got and got > str((d or {}).get("at") or "") else "sent_back"
    return "open"


def is_decided(state: str) -> bool:
    return state in ("accepted", "rechecked")


# ---- drafting ---------------------------------------------------------------------------------------------------------------------------
def _big(sizes: list[str | None]) -> str:
    known = [s for s in sizes if s in SIZES]
    return max(known, key=SIZES.index) if known else contract()["default_effort"]


def _band(f: dict, srcs: dict, restricted: bool, undecided: bool) -> tuple[str, str | None]:
    """(band, why de-scoped). Restricted and undecided first, then no source, then low impact, then the group."""
    c = contract()["later_why"]
    known = [srcs[s] for s in f["sources"] if s in srcs]
    if restricted and undecided:
        return "later", c["restricted_undecided"]
    if not f["sources"]:
        return ("later", c["no_source"]) if f["group"] == "unknown" else ("next" if f["group"] == "unclear" else "now", None)
    if known and all(s["impact"] is not None and s["impact"] < 0 for s in known):
        return "later", c["low_impact"]
    return ("now" if f["group"] == "ready" else "next"), None


def _blockers(f: dict, srcs: dict, open_risks: list[dict]) -> tuple[list[str], list[str]]:
    """(blocked by, who unblocks) from the sources' marks and the measure's open risks; the finding's first reason when nothing else says."""
    c = contract()
    by, who = [], []
    for sid in f["sources"]:
        s = srcs.get(sid)
        for m in (s["marks"] if s else []):
            if m not in c["blockers"]:
                continue
            by.append(c["blockers"][m]["text"])
            owners = [f"{o['name']} ({o['role']})" if o["role"] else o["name"] for o in (s["owners"] if s else []) if o["name"]]
            who.extend([c["unblock_sponsor"]] if c["blockers"][m]["who"] == "sponsor" else owners or [c["unblock_unnamed"]])
    by.extend(r["text"] for r in open_risks if r["kind"] != "risk" and r["text"])
    if not by and f["reasons"]:
        by.append(f["reasons"][0])
    return list(dict.fromkeys(by)), list(dict.fromkeys(who)) or [c["unblock_unnamed"]]


def _team(srcs: list[dict]) -> list[str]:
    c = contract()
    out = [o["team"] or o["name"] for s in srcs for o in s["owners"] if o["team"] or o["name"]]
    return list(dict.fromkeys(out)) or [c["default_team"]]


def draft(inputs: dict, restricted: set[str], states: dict[str, str]) -> list[dict]:
    """The automatic plan: a list of items in band order. `restricted`: ids of the restricted measures; `states`: risk id -> risk_state."""
    srcs, risks = inputs["sources"], inputs["risks"]
    for_sources = {s["id"] for s in srcs.values() if "restricted" in s["marks"]}
    groups: dict[str, dict] = {}
    for f in inputs["findings"]:
        mid = f["measure_id"]
        mine = [r for r in risks if mid in r["measures"]]
        opened = [r for r in mine if not is_decided(states.get(r["id"], "open"))]
        locked = mid in restricted or bool(set(f["sources"]) & for_sources)
        band, why = _band(f, srcs, locked, bool(opened))
        known = [srcs[s] for s in f["sources"] if s in srcs]
        key = f"{band}:" + (f"r:{mid}" if locked else "+".join(sorted(f["sources"])) or f"m:{mid}")
        g = groups.setdefault(key, {"key": key, "band": band, "measures": [], "pain_points": [], "levers": [], "sources": sorted(f["sources"]),
                                    "restricted": locked, "known": known, "blocked_by": [], "who_unblocks": [], "reasons": [], "why": why})
        g["measures"].append(mid)
        g["pain_points"] += [p for p in f["pain_points"] if p not in g["pain_points"]]
        g["levers"] += [p for p in f["levers"] if p not in g["levers"]]
        g["reasons"] += [] if locked else f["reasons"]
        if band == "next" and not locked:  # a restricted item keeps no blocker, reason or owner: nothing derived from restricted data is stored
            by, who = _blockers(f, srcs, opened)
            g["blocked_by"] += [b for b in by if b not in g["blocked_by"]]
            g["who_unblocks"] += [w for w in who if w not in g["who_unblocks"]]
    order = {b: i for i, b in enumerate(contract()["bands"])}
    items = []
    for g in sorted(groups.values(), key=lambda g: (order[g["band"]], g["key"])):
        effort, team = _big([s["effort"] for s in g["known"]]), _team([] if g["restricted"] else g["known"])
        items.append({"key": g["key"], "band": g["band"], "measures": sorted(g["measures"]), "pain_points": g["pain_points"], "levers": g["levers"],
                      "sources": g["sources"], "restricted": g["restricted"], "effort": effort, "team": team, "blocked_by": g["blocked_by"],
                      "who_unblocks": g["who_unblocks"], "date": None, "why_descoped": g["why"], "covered_by": None, "reasons": g["reasons"],
                      "summary": "", "auto": {"band": g["band"], "effort": effort, "team": team, "date": None, "covered_by": None},
                      "edits": {}, "proposals": {}})
    return items  # a measure left out in module 2 is not an item: the plan answer lists it once, apart (api/plan.py)


def fallback_summary(item: dict, names: dict[str, str]) -> str:
    """The one-line summary without the model, from names and the item's own facts only. A restricted item never names its measure."""
    c = contract()
    label = RESTRICTED_NAME if item["restricted"] else ", ".join(names.get(m, m) for m in item["measures"])
    blocked = [] if item["restricted"] else item["blocked_by"]  # a restricted item's blockers are never worded, whatever it holds
    if item["band"] == "now":
        return f"{label}: ready to build. Effort: {c['effort'][item['effort']]['label'].lower()}."
    if item["band"] == "next":
        return f"{label}: waiting on {'; '.join(blocked).lower() or 'a decision'}."
    return f"{label}: later. {item['why_descoped'] or 'Not planned yet.'}"


# ---- a re-draft keeps what a person changed -----------------------------------------------------------------------------------------------
def merge(fresh: list[dict], previous: list[dict]) -> list[dict]:
    """The fresh draft with every human edit kept. Where the fresh draft now says something else, it waits in `proposals`.
    An edited item the draft no longer produces stays, marked `stale`; an unedited one goes."""
    old = {i["key"]: i for i in previous}
    out = []
    for a in fresh:
        p = old.pop(a["key"], None)
        if not p or not p.get("edits"):
            out.append(a)
            continue
        item = {**a, "edits": p["edits"], "proposals": {}}
        for field, e in p["edits"].items():
            item[field] = e["value"]
            if a["auto"][field] != e["auto"]:
                item["proposals"][field] = a["auto"][field]
        out.append(item)
    out.extend({**p, "stale": True} for p in old.values() if p.get("edits"))
    return out


def _clean(v, limit: int, what: str, required: bool = False) -> str:
    v = " ".join(str(v or "").split())
    if required and not v:
        raise PlanError("invalid", f"Please say why: the {what} is needed.")
    if len(v) > limit:
        raise PlanError("invalid", f"The {what} is too long: keep it under {limit} characters.")
    return v


def edit_item(items: list[dict], key: str, changes: dict, reason, by: str, acct: str, now: str) -> list[dict]:
    """A person's change to one item, with a reason. `changes` holds any of band, effort, team, date, covered_by."""
    c, lim = contract(), contract()["limits"]
    i = next((n for n, x in enumerate(items) if x["key"] == key), None)
    if i is None:
        raise LookupError("no item")
    given = {k: v for k, v in changes.items() if k in EDITABLE}
    ok = {"band": isinstance(given.get("band"), str), "effort": isinstance(given.get("effort"), str),
          "team": isinstance(given.get("team"), str) or (isinstance(given.get("team"), list) and all(isinstance(t, str) for t in given["team"])),
          "date": given.get("date") is None or isinstance(given.get("date"), str),
          "covered_by": given.get("covered_by") is None or isinstance(given.get("covered_by"), str)}
    if (reason is not None and not isinstance(reason, str)) or any(not ok[k] for k in given):
        raise PlanError("bad_value", "One of the values is not in the form we expected. Please check what you typed and try again.")
    if not given:
        raise PlanError("invalid", "Please change the band, the effort, the team, the date or the covered-by note.")
    reason = _clean(reason, lim["reason"], "reason", required=True)
    item = {**items[i], "edits": dict(items[i]["edits"]), "proposals": dict(items[i].get("proposals") or {})}
    for field, v in given.items():
        if field == "band" and v not in c["bands"]:
            raise PlanError("invalid", "Please pick Now, Next or Later.")
        if field == "effort" and v not in SIZES:
            raise PlanError("invalid", "Please pick small, medium or large effort.")
        if field == "team":
            v = [t for t in (_clean(t, lim["team"], "team") for t in (v if isinstance(v, list) else str(v or "").split(","))) if t]
            if not v:
                raise PlanError("invalid", "Please name the team.")
        if field == "date":
            try:
                v = date.fromisoformat(v).isoformat() if v else None
            except (TypeError, ValueError):
                raise PlanError("invalid", "Please give the date as year-month-day, or leave it empty.") from None
        if field == "covered_by":
            v = _clean(v, lim["covered_by"], "covered-by note") or None
        item[field] = v
        item["proposals"].pop(field, None)
        item["edits"][field] = {"value": v, "auto": item["auto"][field], "reason": reason, "by": by, "account_id": acct, "at": now}
    return [*items[:i], item, *items[i + 1:]]


# ---- the plan as one person may see it -----------------------------------------------------------------------------------------------------
def band_view(items: list[dict], names: dict[str, str], hidden: set[str], titles: dict[str, str]) -> dict:
    """{now: [...], next: [...], later: [...]} with names in place of ids. A restricted item whose measure the viewer may not see is only
    its key, its band and the words "A restricted measure": no source, team, blocker or reason (SHARED.md)."""
    c = contract()
    out = {b: [] for b in c["bands"]}
    for it in items:
        if set(it["measures"]) & hidden:
            out[it["band"]].append({"key": it["key"], "band": it["band"], "restricted": True, "summary": RESTRICTED_NAME, "measures": [],
                                    "pain_points": [], "team": [], "blocked_by": [], "who_unblocks": []})
            continue
        shown = {k: v for k, v in it.items() if k not in ("auto", "reasons", "sources", "levers")}
        if it["restricted"]:  # restricted through its source: the viewer sees the measure, never the owners, blockers or reasons behind it
            shown.update(team=[], blocked_by=[], who_unblocks=[], edits={}, proposals={}, summary=RESTRICTED_NAME, why_descoped=None,
                         covered_by=None)  # typed by a person: it could name the source
        out[it["band"]].append({**shown, "measures": [{"id": m, "name": names.get(m, m)} for m in it["measures"]],
                                "pain_points": [{"id": p, "title": titles.get(p, p)} for p in it["pain_points"]],
                                "effort_label": c["effort"][it["effort"]]["label"], "date_text": it["date"],  # None until a person sets a date: the screen says "No date yet"
                                "covered_text": shown["covered_by"] or c["not_planned"]})
    return out

