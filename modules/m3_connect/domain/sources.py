"""M3-P01 source map: score every source for impact and readiness from the signed inputs, place it in a zone (D-036: the line sits at zero),
keep a person's override beside Lens's draft, and show each viewer only what they may see.

Pure functions over the dicts `domain/inputs.py` returns, plus sources.json (SHARED.md) in the assessment folder. Weights live in
contracts/scoring.yaml. Nothing here calls a model: the one-sentence summaries come from agent/score_lens.py.
A source or field a viewer may not see is shown as "A restricted source" (no tables, measures or reasons) or left out.
"""
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from modules.m3_connect.domain import inputs as I
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

SCORING = Path(__file__).resolve().parents[1] / "contracts" / "scoring.yaml"
ZONES = {"p1": "Ready to scan, priority 1", "p2": "Ready to scan, priority 2", "identify": "To be identified",
         "unknown": "Unknown zone: resolve first"}
RESTRICTED_SOURCE = "A restricted source"
_STOP = set("""with from that this have into their about over more than when what where which while there these those they them been being were
will your would could should must also just only same some such then very each every many much other across between using make take need needs
data report reports system systems process processes manual issue issues time team work tool tools""".split())
MIN_SHARED, MIN_JACCARD = 2, 0.3  # a link needs this many shared meaningful words, or this word overlap (Jaccard)
_t, _ids, _norm = I._t, I._ids, I._norm


class OverrideError(ValueError):
    """A refusal in plain words."""


@lru_cache(maxsize=1)
def weights() -> dict:
    return yaml.safe_load(SCORING.read_text(encoding="utf-8"))


def zone(impact: float, readiness: float) -> str:
    return ("p1" if readiness >= 0 else "unknown") if impact >= 0 else ("p2" if readiness >= 0 else "identify")


def _score(shares: dict[str, float], w: dict[str, float]) -> float:
    """2 * weighted share - 1: the line sits at zero."""
    total = sum(w.values()) or 1.0
    return round(2 * sum(w[k] * min(max(shares.get(k, 0.0), 0.0), 1.0) for k in w) / total - 1, 3)


def _words(text) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", str(text or "").lower()) if w not in _STOP}


def _effect(share: float) -> str:
    return "raises" if share >= weights()["raises_at"] else "lowers"


# ---- what a source feeds ------------------------------------------------------------------------------------------------------------
def _kind(src: dict) -> str:
    said = _t(src.get("Source type"))
    return next((k["kind"] for k in weights()["source_kind"] if said.startswith(k["starts"])), weights()["default_kind"])


def _source_tables(inputs: dict, sid: str) -> list[dict]:
    return [t for t in inputs["tables"] if _t(t.get("Source ID")) == sid]


def measures_fed(inputs: dict, sid: str) -> list[str]:
    tabs = _source_tables(inputs, sid)
    tids = {_t(t.get("Item ID")) for t in tabs}
    found = [k for t in tabs for k in _ids(_t(t.get("Related KPIs")))]
    found += [k for f in inputs["fields"] if _t(f.get("Item ID")) in tids for k in _ids(_t(f.get("Feeds KPI")))]
    found += [k for e in inputs["extractions"] if _t(e.get("Item ID (document type)")) in tids for k in _ids(_t(e.get("Feeds KPI")))]
    known = {m["id"] for m in inputs["measures"]}
    return [k for k in dict.fromkeys(found) if k in known]


def _linked(items: list[dict], ms: list[dict]) -> list[tuple[str, str]]:
    """(item title, problem title): the charter holds no link from an item to a measure, so a possible one is inferred from the problem the
    measure serves: the item's title and "so that" share at least two meaningful words with the problem's title, or overlap by 0.3 (Jaccard).
    ponytail: the problem's own so_that and details are not in the inputs yet; add them to the problem side when read_inputs carries them."""
    out = []
    for it in items:
        mine = _words(f"{it.get('title') or ''} {it.get('so_that') or ''}")
        for m in ms:
            problem = m.get("problem") or ""
            theirs, both = _words(problem), mine & _words(problem)
            if m["id"] in (it.get("measures") or []) or (theirs and (len(both) >= MIN_SHARED or len(both) / len(mine | theirs) >= MIN_JACCARD)):
                out.append((str(it.get("title") or ""), problem or str(m.get("name") or "")))
                break
    return out


def _impact(ms: list[dict], inputs: dict) -> tuple[float, list[dict]]:
    c = weights()["impact"]
    pts = {k.lower(): v for k, v in c["priority_points"].items()}
    best = max(((pts.get(str(m.get("priority") or "").lower(), 0.0), m) for m in ms), key=lambda p: p[0], default=(0.0, None))
    shares, reasons = {}, []
    if best[1] is None:
        reasons.append({"text": "It feeds no measure yet.", "effect": "lowers"})
    else:
        shares["priority"] = best[0]
        reasons.append({"text": f'The highest priority it feeds is {best[1].get("priority") or "not set"} ({best[1]["name"]}).',
                        "effect": _effect(best[0])})
    shares["breadth"] = len(ms) / c["full_at"]["breadth"]
    reasons.append({"text": f"It feeds {len(ms)} measure{'s' if len(ms) != 1 else ''}.", "effect": _effect(shares["breadth"])})
    for key, label in (("pain_points", "pain point"), ("future_signals", "future signal"), ("levers", "lever")):
        hits = _linked(inputs.get(key) or [], ms)
        shares[key] = len(hits) / c["full_at"][key]
        if hits:
            probs = ", ".join(dict.fromkeys(p for _, p in hits))
            reasons.append({"text": f'{len(hits)} {label}{"s" if len(hits) != 1 else ""} ({", ".join(t for t, _ in hits)}): possible link through the problem {probs}.',
                            "effect": _effect(shares[key])})
        else:
            reasons.append({"text": f"No {label} is linked to what it feeds.", "effect": "lowers"})
    return _score(shares, c["weights"]), reasons


def _readiness(src: dict, inputs: dict, ms_ids: list[str], extras: dict) -> tuple[float, list[dict], list[str]]:
    c = weights()["readiness"]
    sid = _t(src.get("Source ID"))
    tabs = _source_tables(inputs, sid)
    reasons, missing, shares = [], [], {}

    def put(key: str, share: float, good: str, bad: str, miss: str):
        shares[key] = share
        reasons.append({"text": good if share >= weights()["raises_at"] else bad, "effect": _effect(share)})
        if share < 1:
            missing.append(miss)

    conn = _t(src.get("Connection method"))
    lands = _t(src.get("Where it lands or lives"))
    put("connection", 1.0 if conn and not conn.startswith("Manual") else 0.5 if lands else 0.0,
        "How it reaches us is known.", "How it lands or connects is not settled.", "How the data will reach us")
    owner, answered = _t(src.get("Data owner")), extras.get("answered") or set()
    put("owner", 1.0 if owner and _norm(owner) in answered else 0.4 if owner else 0.0,
        "A named owner has answered.", "The owner has not answered yet." if owner else "Nobody owns it yet.",
        "An owner who answers for it" if not owner else "An answer from the owner")
    put("sample", 1.0 if set(ms_ids) & set(extras.get("samples") or ()) else 0.0,
        "A sample was given in the baseline.", "No sample has been given yet.", "A sample of the data")
    structure = _norm(_t(src.get("Structured or unstructured"))) or "unknown"
    put("structure", weights()["readiness"]["structure_points"].get(structure, 0.0),
        "It is structured data." if structure == "structured" else "It is partly structured.",
        "It is unstructured, which takes more work." if structure == "unstructured" else "Whether it is structured is not known.",
        "Whether it is structured or unstructured")
    put("personal", 1.0 if _norm(_t(src.get("Contains personal data?"))) in ("yes", "no") else 0.0,
        "The personal-data decision is made.", "The personal-data decision is not made.", "A decision on personal data")
    put("arrival", 1.0 if _t(src.get("How often it arrives")) or _t(src.get("Expected arrival time or SLA"))
        or any(_t(t.get("How often it arrives")) for t in tabs) else 0.0,
        "When it arrives is known.", "When it arrives is not known.", "When the data arrives")
    conflicts = {g.get("kpi_id") for g in inputs.get("gaps") or [] if g.get("type") == "conflict"} & set(ms_ids)
    put("agreed", 0.0 if conflicts else 1.0, "Its owners agree.", "Its owners gave different answers that are not settled.",
        "Owners to settle their different answers")
    return _score(shares, c["weights"]), reasons, missing


def _blocked(inputs: dict, ms_ids: list[str]) -> bool:
    """An upstream step with no named owner, or one waiting on someone."""
    for k in ms_ids:
        for s in ((inputs.get("process_map") or {}).get(k) or {}).get("steps") or []:
            if s.get("waiting") or s.get("from") == "waiting" or "waiting on" in str(s.get("text") or "").lower() \
                    or ("owner" in s and not s["owner"]):
                return True
    return False


def _effort(kind: str, structure: str) -> str:
    c, order = weights()["effort"], weights()["effort_order"]
    i = order.index(c.get(kind, "medium")) + (0 if _norm(structure) == "structured" else 1)
    return order[min(i, len(order) - 1)]


def effective(s: dict) -> dict:
    """The position the map shows: the person's value where one was given, else Lens's draft."""
    o = s.get("override") or {}
    i = o.get("impact") if o.get("impact") is not None else s["impact"]["score"]
    r = o.get("readiness") if o.get("readiness") is not None else s["readiness"]["score"]
    return {"impact": i, "readiness": r, "zone": zone(i, r)}


def score_all(inputs: dict, outsider: dict, extras: dict) -> list[dict]:
    """`inputs`: what the head of data sees (everything). `outsider`: what someone with no standing sees: it marks what is restricted."""
    hidden_ms = {m["id"] for m in outsider["measures"] if m.get("restricted")}
    visible_src = {_t(s.get("Source ID")) for s in outsider["sources"]}
    measures = {m["id"]: m for m in inputs["measures"]}
    out = []
    for src in inputs["sources"]:
        sid = _t(src.get("Source ID"))
        ids = measures_fed(inputs, sid)
        if not ids:
            continue  # feeds no measure that is left in: off the map, listed by `unneeded`
        ms = [measures[k] for k in ids]
        impact, ireasons = _impact(ms, inputs)
        ready, rreasons, missing = _readiness(src, inputs, ids, extras)
        kind = _kind(src)
        structure = _t(src.get("Structured or unstructured"))
        s = {"id": sid, "name": _t(src.get("Source name")) or sid, "kind": kind, "measures": ids,
             "impact": {"score": impact, "reasons": ireasons}, "readiness": {"score": ready, "reasons": rreasons, "missing": missing},
             "marks": {"restricted": sid not in visible_src or bool(set(ids) & hidden_ms), "blocked_upstream": _blocked(inputs, ids),
                       "effort": _effort(kind, structure), "licence": kind == "outside feed",
                       "owners_disagree": any(g.get("type") == "conflict" and g.get("kpi_id") in ids for g in inputs.get("gaps") or [])},
             "override": None}
        s["zone"] = effective(s)["zone"]
        s["summary"], s["summary_by"] = fallback_summary(s), "rules"
        out.append(s)
    return out


def unneeded(inputs: dict) -> list[dict]:
    """The sources that feed no measure which is left in ("Not needed for any measure"): [{id, name}]."""
    return [{"id": _t(s.get("Source ID")), "name": _t(s.get("Source name")) or _t(s.get("Source ID"))} for s in inputs["sources"]
            if _t(s.get("Source ID")) and not measures_fed(inputs, _t(s.get("Source ID")))]


def fallback_summary(s: dict) -> str:
    """One deterministic sentence, used when the model is not reachable."""
    z = effective(s)["zone"]
    why = next((r["text"] for r in s["readiness"]["reasons"] if r["effect"] == "lowers"), None) if z in ("unknown", "identify") else None
    tail = f" Next: {why[0].lower() + why[1:]}" if why else ""
    return f"{s['name']} is in the zone {ZONES[z].lower()}, with {len(s['measures'])} measure{'s' if len(s['measures']) != 1 else ''} fed.{tail}"


# ---- the file ---------------------------------------------------------------------------------------------------------------------
def path(folder: Path) -> Path:
    return folder / "sources.json"


def read(folder: Path) -> dict | None:
    d = read_json_strict(path(folder), dict)
    return d if isinstance(d, dict) and isinstance(d.get("sources"), list) else None


def save_scored(folder: Path, sources: list[dict], now: str | None = None, not_needed: list[dict] | None = None) -> dict:
    """A re-score keeps every override and writes Lens's new draft beside it. `not_needed`: the sources left off the map (see `unneeded`)."""
    with lock_for(path(folder)):
        old = {s["id"]: s.get("override") for s in (read(folder) or {}).get("sources", [])}
        for s in sources:
            s["override"] = old.get(s["id"])
            s["zone"] = effective(s)["zone"]
        doc = {"scored_at": now or datetime.now(timezone.utc).isoformat(), "sources": sources, "not_needed": not_needed or []}
        write_json_atomic(path(folder), doc)
        return doc


def set_override(folder: Path, sid: str, impact, readiness, reason, by: str, now: str | None = None, by_id: str | None = None) -> dict:
    def num(v, what):
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not -1 <= v <= 1:
            raise OverrideError(f"Please give the new {what} as a number from -1 to 1.")
        return round(float(v), 3)
    impact, readiness = num(impact, "impact"), num(readiness, "readiness")
    reason = " ".join(str(reason or "").split())
    if impact is None and readiness is None:
        raise OverrideError("Please give a new impact, a new readiness, or both.")
    if not reason or len(reason) > 500:
        raise OverrideError("Please say why you are moving this source, in a few words." if not reason else "Please keep the reason under 500 characters.")
    with lock_for(path(folder)):
        doc = read(folder)
        s = next((x for x in (doc or {}).get("sources", []) if x["id"] == sid), None)
        if s is None:
            raise LookupError("no source")
        s["override"] = {"impact": impact, "readiness": readiness, "reason": reason, "by": by, "by_id": by_id,
                         "at": now or datetime.now(timezone.utc).isoformat()}
        s["zone"] = effective(s)["zone"]
        write_json_atomic(path(folder), doc)
        return s


def step_state(folder: Path) -> dict:
    try:
        doc = read(folder)
    except (OSError, ValueError):
        return {"state": "not_started"}
    return {"state": "done" if doc else "not_started", "waiting_on": ""}


# ---- what a viewer sees -----------------------------------------------------------------------------------------------------------
def _hidden(s: dict, viewer_inputs: dict) -> bool:
    seen = {_t(x.get("Source ID")) for x in viewer_inputs["sources"]}
    cut = {m["id"] for m in viewer_inputs["measures"] if m.get("restricted")}
    return s["id"] not in seen or bool(set(s["measures"]) & cut)


def view(s: dict, viewer_inputs: dict) -> dict:
    """One source as this viewer may see it. A restricted one shows only its position: no name, tables, measures or reasons."""
    e = effective(s)
    if _hidden(s, viewer_inputs):
        return {"id": s["id"], "name": RESTRICTED_SOURCE, "restricted": True, "kind": "hidden", "measures_fed": 1, **e,
                "zone_label": ZONES[e["zone"]], "marks": {"restricted": True}, "override": None, "summary": ""}
    o = s.get("override")
    return {"id": s["id"], "name": s["name"], "restricted": False, "kind": s["kind"], "measures_fed": len(s["measures"]), **e,
            "zone_label": ZONES[e["zone"]], "marks": s["marks"], "summary": s.get("summary") or "",
            "draft": {"impact": s["impact"]["score"], "readiness": s["readiness"]["score"]},
            "override": {k: v for k, v in o.items() if k != "by_id"} if o else None}  # the account id stays in the file, never on the screen


def _field_ok(row: dict, viewer: I.Viewer, source_row: dict | None = None, measures: dict | None = None) -> bool:
    """Module 2's field rules: the field's own "Who may see it" can only narrow (M2-E3; the sponsor and the head of data pass), and a field
    whose "Personal data class" is not "Neither" is for the people named on its source or on a restricted measure it feeds."""
    src = I._names(_t((source_row or {}).get("Who may see it")))
    named = frozenset().union(*(I._names("; ".join((measures or {}).get(k, {}).get("may_see") or []))
                                for k in _ids(_t(row.get("Feeds KPI"))) if (measures or {}).get(k, {}).get("guarded")))
    if not I.class_ok(row, src, named, viewer):
        return False
    own = _t(row.get("Who may see it"))
    if not own or {"sponsor", "company_admin"} & set(viewer.roles):
        return True
    return _norm(viewer.name) in I._names(own) and not viewer.shared_name


def panel(s: dict, viewer_inputs: dict, viewer: I.Viewer) -> dict | None:
    """The side panel, or None for a source this viewer may not see."""
    if _hidden(s, viewer_inputs):
        return None
    by_id = {m["id"]: m for m in viewer_inputs["measures"]}
    src_row = next((x for x in viewer_inputs["sources"] if _t(x.get("Source ID")) == s["id"]), None)
    tables = []
    for t in _source_tables(viewer_inputs, s["id"]):
        tid = _t(t.get("Item ID"))
        fields = [{"name": _t(f.get("Field name as in the source")), "meaning": _t(f.get("Business meaning")), "type": _t(f.get("Data type"))}
                  for f in viewer_inputs["fields"] if _t(f.get("Item ID")) == tid and _field_ok(f, viewer, src_row, by_id)]
        fields += [{"name": _t(x.get("What to extract")), "meaning": _t(x.get("Why it matters")), "type": _t(x.get("Expected format"))}
                   for x in viewer_inputs["extractions"] if _t(x.get("Item ID (document type)")) == tid and _field_ok(x, viewer, src_row, by_id)]
        tables.append({"name": _t(t.get("Name of table, file or document type")) or tid, "kind": _t(t.get("Kind")), "fields": fields})
    ms = [{"id": k, "name": by_id[k]["name"], "priority": by_id[k].get("priority"), "owners": by_id[k].get("owners") or {}}
          for k in s["measures"] if k in by_id]
    return {**view(s, viewer_inputs), "tables": tables, "measures": ms, "missing": s["readiness"]["missing"],
            "impact_reasons": s["impact"]["reasons"], "readiness_reasons": s["readiness"]["reasons"]}
