"""GET /api/pulse (SHAPES 1, A-071): the signed-in person's day, built from records only. Readers are in lines.py."""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile import view
from sh_platform.profile.api import _plane, _viewer
from sh_platform.pulse import lines as L

router = APIRouter()
CAP = 7


def _order(rows: list[dict]) -> list[dict]:
    """Due date first (none last), then the newest record first: two stable passes."""
    rows = sorted(rows, key=lambda x: x["source"]["at"] or "", reverse=True)
    return sorted(rows, key=lambda x: (x["due"] is None, x["due"] or ""))


def layout(v: view.Viewer) -> str:
    """Which artboard this person's pulse follows: the data team (analyst) first, then the organiser, the sponsor, everyone else."""
    if "analyst" in v.roles:
        return "data"
    if "company_admin" in v.roles:
        return "organiser"
    return "sponsor" if "sponsor" in v.roles else "participant"


def _strips(plane, v: view.Viewer, briefs: Path | None, now: datetime, kind: str) -> list[tuple[str, list[dict]]]:
    signs = L.signatures(plane, v, now) + L.blueprint(plane, v, now) + L.release(plane, v, now)
    decide = L.measures(plane, v, now) + L.purpose_asks(plane, v, now) + L.gaps(plane, v, now) + L.suggestions(plane, v, now)
    common = [("invited", L.invited(plane, v, now) + L.interview(plane, v, now)),
              ("decide", decide + ([] if kind == "data" else signs)),
              ("give", L.requests(plane, v, now) + L.late_files(plane, v, now)),
              ("watch", L.range_breaks(plane, v, now) + L.brief(plane, v, briefs, now) + ([] if kind == "data" else L.ops(plane, v, now)))]
    if kind == "organiser":
        return [("start", L.starts(plane, v, now)), ("running", L.running(plane, v, now)), ("waiting", L.waiting(plane, v, now)), *common]
    if kind == "data":
        return [("ops", L.critical(plane, v, now) + L.late_runs(plane, v, now)), ("sign", signs), *common]
    if kind == "sponsor":
        return [common[1], common[0], *common[2:]]
    return common


def _panels(plane, v: view.Viewer, now: datetime, kind: str) -> dict:
    """Counters and tables for the role's artboard. They are not lines and do not count against the cap."""
    if kind == "organiser":
        return {"quarter": L.quarter(plane, v, now), "drafts": L.drafts(plane, v)}
    if kind == "data":
        return {"ops_report": L.ops_report(plane, v, now)}
    if kind == "sponsor":
        return {"initiatives": L.initiatives(plane, v, now), "watch": L.watch_stats(plane, v, now)}
    return {}


def build(plane, v: view.Viewer, briefs: Path | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    kind = layout(v)
    left, out, seen = CAP, [], set()
    for key, rows in _strips(plane, v, briefs, now, kind):  # the cap falls on the last strip first, so Watch is dropped first
        rows = [r for r in _order(rows) if not (r["id"] in seen or seen.add(r["id"]))][:left]  # a record shown in an earlier strip is not repeated
        left -= len(rows)
        if rows:
            out.append({"key": key, "lines": rows})
    return {"date": now.date().isoformat(), "person": {"name": v.name, "roles": sorted(v.roles)}, "layout": kind,
            "minutes": sum(x["minutes"] for s in out for x in s["lines"]), "strips": out, "map": L.new_nodes(plane, v, now),
            "panels": _panels(plane, v, now, kind)}


def _briefs(request: Request) -> Path | None:
    rec = request.app.state.entitlements.company(request.state.company_id) or {}
    folder = Path(request.app.state.packs.root) / str(rec.get("industry") or "-")
    try:
        versions = sorted((p for p in folder.iterdir() if p.name.isdigit()), key=lambda p: int(p.name))
    except OSError:
        return None
    return versions[-1] / "market_briefs" if versions else None


@router.get("/api/pulse")
def get_api_pulse(request: Request):
    try:
        plane = _plane(request)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
    return build(plane, _viewer(request), _briefs(request))
