"""B1: `GET /api/company/build/home`, the Build centre's three rooms lit from records. Reads warehouse/environment.json (through build_env),
build/blueprint.json (SHAPES 2), build/pipelines/*.json (3), warehouse/runs.json (4), build/prove.json (5) and ops.build. Counts only.
Room state: room 1 always open; room 2 next once the blueprint is signed; room 3 open whenever the run log has runs, otherwise locked (the release is a separate signature, not a gate for Ops)."""
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request

from sh_platform import build_env
from sh_platform.build import ops
from sh_platform.graph.register import _business_owners
from sh_platform.intents import store as intents_store
from sh_platform.profile import store, view
from sh_platform.profile.api import _plane, _viewer
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
router = APIRouter()
from sh_platform.build.gap_analysis import router as _room0  # noqa: E402  room 0's list and start, served with the Build home
router.include_router(_room0)


KIND = {"outside_range": "outside its usual range", "late": "file late", "missing": "file not arrived", "failed": "run failed its checks"}


def _src(s) -> str:
    """custodian_daily_file -> Custodian daily file (the words the blueprint uses)."""
    return str(s or "A source").replace("_", " ").capitalize()


def _day(at) -> str:
    """2026-06-12T10:00:00+00:00 -> 12 June 2026; anything unreadable -> Not available yet."""
    try:
        d = date.fromisoformat(str(at)[:10])
    except ValueError:
        return "Not available yet"
    return f"{d.day} {d:%B %Y}"


def _measure(m: dict) -> str:
    """match when every period matches; gap when any period is a gap; otherwise not_yet (including no periods)."""
    res = [p.get("result") for p in m.get("periods") or []]
    return "gap" if "gap" in res else ("match" if res and all(r == "match" for r in res) else "not_yet")


def room0(plane) -> dict:
    """Room 0 (the gap analysis): the newest Initiative handed to Build, or none. Read from the records, newest update first."""
    rows = sorted((r for r in intents_store.read_index(plane) if r["type"] == "initiative" and r["state"] in ("open", "closing", "closed")),
                  key=lambda r: r.get("updated_at") or "", reverse=True)
    for r in rows:
        try:
            rec = intents_store.read_intent(plane, r["id"])
        except intents_store.Unreadable:
            continue
        h = (rec or {}).get("build_handoff")
        if h:
            return {"state": "open", "handed_over_from": {"id": rec["id"], "title": rec.get("title"), "at": h.get("at"), "by": (h.get("by") or {}).get("name")}}
    return {"state": "open", "handed_over_from": None}


def build(plane, viewer: view.Viewer, today: date) -> dict:
    qs = build_env.read(plane, store.raw(plane))["questions"]
    bp = ops._load(plane.path("build", "blueprint.json"), {})
    bp = bp if isinstance(bp, dict) else {}
    signed = bp.get("state") == "signed"
    state = "signed" if signed else ("draft" if bp.get("state") == "draft" else "none")
    pipes = [p for f in sorted(plane.path("build", "pipelines").glob("*.json")) if isinstance(p := ops._load(f, None), dict)]
    runs = ops._load(plane.path("warehouse", "runs.json"), {}).get("runs") or []
    last = {}
    for r in runs:  # newest last
        last[r.get("source")] = r.get("status")
    prove = ops._load(plane.path("build", "prove.json"), {})
    measures = prove.get("measures") or [] if isinstance(prove, dict) else []
    results = [_measure(m) for m in measures]
    release = ((prove.get("release") or {}).get("state") if isinstance(prove, dict) else None) or "none"
    o = ops.build(plane, viewer, today)
    alerts = list({a["id"]: a for a in reversed(o["alerts"])}.values())[::-1]  # one alert per id: a measure fed by two sources is one record
    kinds = [a["kind"] for a in alerts]
    sig = [x for x in bp.get("signed_by") or [] if isinstance(x, dict)] if signed else []
    waiting = len(qs) - sum(1 for q in qs if q["answer"].get("mark") == "stated")
    d1 = ([f"{waiting} environment answer{'s' if waiting != 1 else ''} wait for the head of data to confirm"] if waiting else []) + [
        f"Blueprint signed by {sig[0].get('name')} on {_day(sig[0].get('at'))}" if sig else
        "Blueprint drafted: waits for the head of data to sign" if state == "draft" else "No blueprint yet"]
    d2 = [f"{_src(a['source'])}: {a['kind']}, source owner {a['owner'] or 'not named'}" for a in alerts if a["kind"] in ("late", "failed")][:4]
    d2 += [f"Measure {m.get('code')}: {r.replace('_', ' ')}" for m, r in zip(measures, results) if r != "match"][:4]
    if measures and release != "signed":
        d2.append(f"Release {release}: waits for the head of data and the measure owners")
    boss = _business_owners(plane)  # a measure has one owner everywhere: its business owner; a source alert names the source owner
    d3 = [f"{str(a['measure']).upper() if a.get('measure') else _src(a['source'])}: {KIND.get(a['kind'], a['kind'])}, "
          f"{'owner ' + (boss.get(str(a['measure']).lower()) or a['owner'] or 'not named') if a.get('measure') else 'source owner ' + (a['owner'] or 'not named')}, "
          f"{a.get('state') or 'open'} since {_day(a.get('opened'))}" for a in alerts][:5]
    from sh_platform.build import chain  # 59: the chain panel
    try:
        rows = chain.home_rows(plane, viewer)
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the chain rows were not read", exc_info=True)
        rows = {"chain": [], "live": 0}
    return {
        **rows,
        "room0": room0(plane),
        "rooms": [
            {"room": 1, "state": "open",
             "environment": {"confirmed": sum(1 for q in qs if q["answer"].get("mark") == "stated"), "of": len(qs)},
             "blueprint": {"state": state, "signed_by": [s.get("name") for s in sig], "signed_at": str(sig[0].get("at"))[:10] if sig else None}, "detail": d1},
            {"room": 2, "state": "next" if signed else "locked",
             "pipelines": {"sources": len(pipes), "last_run": {k: sum(1 for v in last.values() if v == k) for k in ("ok", "late", "failed")}},
             "proven": {"match": results.count("match"), "gap": results.count("gap"), "not_yet": results.count("not_yet"),
                        "uat_signed": sum(1 for m in measures if (m.get("uat") or {}).get("state") == "signed")},
             "release": release, "detail": d2},
            {"room": 3, "state": "open" if runs else "locked",
             "today": {"late": kinds.count("late"), "failed": kinds.count("failed"), "open_alerts": sum(1 for a in alerts if a.get("state", "open") == "open")}, "detail": d3},
        ]
    }


@router.get("/api/company/build/home")
def get_api_company_build_home(request: Request) -> dict:
    return build(plane := _plane(request), _viewer(request), wh.today(plane))
