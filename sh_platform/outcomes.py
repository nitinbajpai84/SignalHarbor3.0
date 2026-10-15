"""LI-OUTCOMES: `GET /api/company/outcomes`, the measures of the Intent Centre itself, for the signed-in company. Numbers only: no name, no text,
no id. Module records are read by path (never imported); the platform's own profile and interview readers are used as the other pages use them.
`null` always means "not yet", never zero. Restricted measures are never counted in the trial or the governed numbers (for any viewer); they are
reported as one separate count. Cards and files come through the profile's own per-viewer filter, and a sealed card shown only as a silhouette is
not counted."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

from sh_platform.interview import engine
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import reader, store, view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
FIRST_MINUTES = 5
NEEDED = ("sources", "fields", "calculation")  # the technical parts a data owner confirms (modules/m2_baseline/domain/technical.py NEEDED)
CONFIRMED_AS_DRAFTED = "confirmed by the data owner"  # the `from` that technical.confirm writes on a part Lens drafted and the person left as it was
STAGES = ("Not started", "Think unfiltered", "Define strategically", "Moment of truth")


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _files(folder: Path) -> list[Path]:
    try:
        return sorted(folder.glob("*.json"))
    except OSError:
        return []


def _dirs(folder: Path) -> list[Path]:
    try:
        return sorted(p for p in folder.iterdir() if p.is_dir())
    except OSError:
        return []


def _time(v) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _days(a: datetime | None, b: datetime | None) -> float | None:
    return None if a is None or b is None else round(max((b - a).total_seconds(), 0) / 86400, 1)


def _v(cell):
    return cell.get("value") if isinstance(cell, dict) and cell.get("mark") != "unknown" else None


def _intents(plane, *parts) -> Path:
    return plane.path("intents", *parts)


def _open(k: dict) -> bool:
    g = k.get("governance") if isinstance(k.get("governance"), dict) else {}
    return g.get("personal") == "no" and not g.get("sensitive")  # modules/m3_connect/domain/inputs.py `_restricted`, inverted; "not sure" is closed


def _m1(plane) -> dict:
    total = {"actions": 0, "free_text": 0}
    opened, ended, seen, closed = [], [], False, False
    for f in _files(_intents(plane, "m1_intent", "sessions")):
        s = _load(f)
        if not isinstance(s, dict) or not isinstance(s.get("inputs"), dict):
            continue
        seen = True
        total = {k: total[k] + int(s["inputs"].get(k) or 0) for k in total}
        st = _load(_intents(plane, "m1_intent", "stages", f.name)) or {}
        t = (st.get("started") or {}).get("private_rooms") if isinstance(st, dict) else None
        if isinstance(t, (int, float)):
            opened.append(datetime.fromtimestamp(t, timezone.utc))
        if s.get("state") == "closed":
            closed = True
            o = _load(_intents(plane, "m1_intent", "outcomes", f"{s.get('outcome_id')}.json")) or {}
            if _time(o.get("signed_at")):
                ended.append(_time(o["signed_at"]))
    first = min(opened, default=None)
    mins = round((max(ended) - first).total_seconds() / 60) if first and ended else None
    return {"seen": seen, "closed": closed, "open": first, "actions": total["actions"] if seen else None,
            "free_text": total["free_text"] if seen else None, "minutes": mins}


def _m2(plane) -> dict:
    """The newest signed baseline, else the newest baseline: its measures that are open (the same for every viewer) and the count that are not."""
    folder = _intents(plane, "m2_baseline")
    signed = [o for f in _files(folder / "outcomes") if isinstance(o := _load(f), dict) and o.get("signed_at") and o.get("baseline_id")]
    bid = max(signed, key=lambda o: str(o["signed_at"]))["baseline_id"] if signed else None
    if bid is None:
        found = [(str((_load(d / "baseline.json") or {}).get("created_at")), d.name) for d in _dirs(folder) if d.name != "outcomes"]
        bid = max(found)[1] if found else None
    out = {"exists": bid is not None, "signed": bool(signed), "measures": [], "restricted": 0, "owned": 0, "kept": 0, "confirmed": 0}
    if bid is None:
        return out
    try:
        kpis = _load(plane.path("intents", "m2_baseline", bid, "kpis.json")) or []
        gov = _load(plane.path("intents", "m2_baseline", bid, "governed_state.json")) or {}
    except CrossCompanyError:
        return out
    kpis = [k for k in kpis if isinstance(k, dict) and k.get("id")] if isinstance(kpis, list) else []
    gov = gov if isinstance(gov, dict) else {}
    mine = [k for k in kpis if _open(k)]
    out.update(measures=[str(k["id"]) for k in mine], restricted=len(kpis) - len(mine))
    out["owned"] = sum(1 for k in mine if isinstance(gov.get(k["id"]), dict) and (gov[k["id"]].get("owners") or {}).get("mark") == "stated")
    for k in mine:
        if not isinstance(k.get("technical_confirmed"), dict):
            continue
        out["confirmed"] += 1
        t = k.get("technical") if isinstance(k.get("technical"), dict) else {}
        out["kept"] += all(str((t.get(p) or {}).get("from") or "").startswith(CONFIRMED_AS_DRAFTED) for p in NEEDED)
    return out


def _m3(plane, ids: list[str]) -> dict:
    mine = [(str((_load(d / "assessment.json") or {}).get("created_at")), d) for d in _dirs(_intents(plane, "m3_connect", "assessments"))]
    out = {"exists": bool(mine), "signed": None, "created": None, "actions": None, "free_text": None, "matches": [], "counts": None, "auto": 0}
    if not mine:
        return out
    created, d = max(mine, key=lambda x: x[0])
    trial, plan, rules, ic = (_load(d / n) for n in ("trial.json", "plan.json", "rules.json", "inputs_count.json"))
    trial, rules = trial if isinstance(trial, dict) else {}, rules if isinstance(rules, dict) else {}
    out["created"] = _time(created)
    if isinstance(plan, dict) and plan.get("signed_at"):
        out["signed"] = _time(plan["signed_at"])
    if isinstance(ic, dict):
        out["actions"], out["free_text"] = int(ic.get("actions_total") or 0), int(ic.get("free_text") or 0)
    rows = [trial[m] for m in ids if isinstance(trial.get(m), dict)]
    res = [r.get("result") for r in rows]
    if rows:
        out["counts"] = {"matches": res.count("matches"), "gap": res.count("gap"), "cannot": res.count("cannot")}
    out["matches"] = [t for r in rows if r.get("result") == "matches" and (t := _time(r.get("computed_at")))]
    out["auto"] = sum(1 for m in ids if isinstance(rules.get(m), dict) and rules[m].get("auto_checked") and (trial.get(m) or {}).get("result") == "matches")
    return out


def build(plane, viewer: view.Viewer, account_names: list[str]) -> dict:
    prof = view.read(plane, viewer)
    whole = [c for c in prof["cards"].values() if not c.get("silhouette")]
    stamps = [t for c in whole if (t := _time((c.get("lane") or {}).get("at")))]
    first_card = min(stamps, default=None)
    doc = store.load(plane)
    first_file = min((t for g in doc["inputs"].values() if (t := _time((g.get("documents") or {}).get("at")))), default=None)
    m1, m2 = _m1(plane), _m2(plane)
    m3 = _m3(plane, m2["measures"])
    people = engine.people(plane, account_names)
    done = sum(1 for p in people if engine.status_of(plane, p["id"])["status"] == "done")
    named = {_v(c.get("author")) for c in whole if _v(c.get("anonymous")) is not True and _v(c.get("author"))}
    early = [c for c in whole if m1["open"] and _v(c.get("anonymous")) is not True and (t := _time((c.get("lane") or {}).get("at")))
             and 0 <= (t - m1["open"]).total_seconds() <= FIRST_MINUTES * 60]
    files = sum(len(g["files"]) for g in reader.readiness(plane)["groups"])
    stage = STAGES[3] if m2["signed"] else STAGES[2] if m1["closed"] else STAGES[1] if m1["seen"] else STAGES[0]
    counts = m3["counts"]
    not_yet = len(m2["measures"]) - (sum(counts.values()) if counts else 0)
    accepted = (m2["kept"] + m3["auto"]) if (m2["confirmed"] or m3["auto"]) else None
    return {
        "headline": {
            "days_file_to_match": _days(first_file, min(m3["matches"], default=None)),
            "days_card_to_report": _days(first_card, m3["signed"]), "stage": None if m3["signed"] else stage,
            "definitions_unchanged": {"unchanged": m2["kept"], "of": m2["confirmed"]} if m2["confirmed"] else None,
            "match": {**counts, "not_yet": max(not_yet, 0), "restricted": m2["restricted"]} if counts else None,
            "cards_first_five": round(len(early) / len(named), 1) if early and named else None,
            "files_read": files or None, "interviews": {"done": done, "of": len(people)} if people and done else None,
            "drafts_accepted": accepted},
        "modules": [{"module": "m1_intent", "actions": m1["actions"], "free_text": m1["free_text"], "minutes": m1["minutes"]},
                    {"module": "m2_baseline", "actions": None, "free_text": None, "minutes": None},
                    {"module": "m3_connect", "actions": m3["actions"], "free_text": m3["free_text"],
                     "minutes": round((m3["signed"] - m3["created"]).total_seconds() / 60) if m3["signed"] and m3["created"] else None}],
        "funnel": {"cards": len(whole), "clusters": len({_v(c.get("cluster")) for c in whole if _v(c.get("cluster"))}),
                   "measures": len(m2["measures"]), "owned": m2["owned"], "matching": counts["matches"] if counts else 0}}


@router.get("/api/company/outcomes")
def outcomes(request: Request) -> dict:
    names = [str(a.get("display_name") or "") for a in request.app.state.account_store.in_company(request.state.company_id)]
    return build(_plane(request), _viewer(request), [n for n in names if n])
