"""BC-7 Ops: `GET /api/company/build/ops`, the Watcher's daily read. Reads warehouse/runs.json (SHAPES section 4), build/pipelines/*.json
(section 3) and the read-only warehouse copy. Counts and flags only; a figure is shown to a viewer on the measure's access list.
The drafted ask is text only: sending is another package's."""
import copy
import json
import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform import warehouse
from sh_platform.build import alerts as store_alerts
from sh_platform.consume import range as rng
from sh_platform.perf import cached
from sh_platform.profile import store, view
from sh_platform.profile.api import _plane, _viewer
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
router = APIRouter()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _day(v) -> date | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()


def _ask(owner: str, source: str, what: str) -> str:
    return f"Hello {owner}, {what} for {source}. Could you tell us what happened and when we can expect it?"


def _breaks(plane, pipes: list[dict], viewer: view.Viewer) -> list[dict]:
    try:
        con = warehouse.open_readonly(plane)
    except duckdb.Error as e:  # the read-only copy is not there yet
        log.info("no read-only warehouse copy: %s", type(e).__name__)
        return []
    rules = store.raw(plane)["governance"]["field_rules"]
    out = []
    try:
        for p in pipes:
            for mart in p.get("marts") or []:
                schema, _, name = str(mart).partition(".")
                if schema != "gold" or not name.isidentifier() or any(o["mart"] == mart for o in out):  # one mart can feed two pipelines: one break
                    continue
                t = rng.trend(con, name)
                verdict = rng.breaks(t)
                if not verdict["break"]:
                    continue
                latest, mean = t[-1]["value"], statistics.fmean(x["value"] for x in t[:-1])
                key = view._key(name)
                shut = any(not view.sees_rule(r, viewer) for k, r in rules.items() if key in {view._key(k), view._key(view._v(r, "field") or "")})
                out.append({"mart": mart, "source": p.get("source"), "owner": p.get("owner"), "flag": "outside_range", "margin": rng.SPREADS, "basis": verdict["basis"],
                            "latest": None if shut else latest, "mean": None if shut else round(mean, 2)})
    finally:
        con.close()
    return out


def build(plane, viewer: view.Viewer, today: date) -> dict:
    """Cached per company, viewer and day until any file of the company changes; each caller gets its own copy."""
    return copy.deepcopy(cached(plane, "ops", [plane.root], lambda: _build_open(plane, viewer, today), viewer=(viewer, today)))


def _build_open(plane, viewer: view.Viewer, today: date) -> dict:
    pipes = [p for f in sorted(plane.path("build", "pipelines").glob("*.json")) if isinstance(p := _load(f, None), dict) and p.get("source")]
    runs = _load(plane.path("warehouse", "runs.json"), {}).get("runs") or []
    runs = [r for r in runs if r.get("source") in {p.get("source") for p in pipes}]  # a run of a source with no current contract is history, not an arrival
    owners = {p.get("source"): p.get("owner") for p in pipes}
    days = {d for r in runs if (d := _day(r.get("started"))) and d <= today}
    # Read the latest day on which most sources ran, so one source run by hand today does not turn every other source into "not arrived".
    names = {p.get("source") for p in pipes} | {r.get("source") for r in runs}
    full = [d for d in days if len({r.get("source") for r in runs if _day(r.get("started")) == d}) * 2 > len(names)]
    if full and today not in full:
        today = max(full)
    elif days and today not in days:
        today = max(days)
    sources = list(dict.fromkeys([p.get("source") for p in pipes] + [r.get("source") for r in runs]))
    arrivals, failed, alerts = [], [], []
    for s in sources:
        mine = [r for r in runs if r.get("source") == s]
        got = next((r for r in reversed(mine) if _day(r.get("ended") or r.get("started")) == today), None)
        owner = owners.get(s) or (mine[-1].get("owner") if mine else None)
        state = "missing" if got is None else ("late" if got.get("status") == "late" or not got.get("on_time") else "on_time")
        arrivals.append({"source": s, "state": state, "owner": owner, "arrived": got.get("ended") if got else None, "rows": got.get("rows") if got else None})
        if state != "on_time":
            alerts.append({"id": f"{s}:{state}", "source": s, "measure": None, "kind": state, "owner": owner,
                           "ask": _ask(owner or "team", s, "the file has not arrived" if state == "missing" else "the file arrived late")})
        for r in (got or {}).get("rules") or []:
            if not r.get("passed"):
                failed.append({"source": s, "rule": r.get("rule"), "count": r.get("count")})
        if got and (got.get("status") == "failed" or got.get("schema_ok") is False):
            alerts.append({"id": f"{s}:failed", "source": s, "measure": None, "kind": "failed", "owner": owner, "ask": _ask(owner or "team", s, "today's run failed its checks")})
    ranges = _breaks(plane, pipes, viewer)
    alerts += [{"id": f"{b['mart']}:range", "source": b["source"], "measure": b["mart"].removeprefix("gold."), "kind": "outside_range", "owner": b["owner"],
                "ask": _ask(b["owner"] or "team", b["mart"], "the latest value is outside its usual range")} for b in ranges]
    alerts = list({a["id"]: a for a in alerts}.values())  # one alert per id
    from sh_platform.build import chain  # 59: the change that built the pipeline, and who is told (developer before live, ops after)
    tell: dict = {}
    for a in alerts:
        if a["source"] not in tell:
            try:
                tell[a["source"]] = chain.alert_fields(plane, a["source"])
            except (OSError, ValueError, KeyError, TypeError):
                log.warning("the chain fields were not read for %s", a["source"], exc_info=True)
                tell[a["source"]] = {"change_id": None, "tell": None}
        a.update(tell[a["source"]])
    kept = store_alerts.sync(plane, alerts, today.isoformat())
    asks = {a["id"]: a["ask"] for a in alerts}
    alerts = [{**a, "ask": asks[a["id"]]} for a in kept if a["state"] != "closed"]
    history = []
    for n in range(6, -1, -1):
        d = today - timedelta(days=n)
        st = [r.get("status") for r in runs if _day(r.get("started")) == d]
        history.append({"date": d.isoformat(), "ok": st.count("ok"), "late": st.count("late"), "failed": st.count("failed")})
    book = [{k: p.get(k) for k in ("source", "title", "expected", "sla", "depends_on", "marts", "owner")} for p in pipes]
    return {"date": today.isoformat(), "arrivals": arrivals, "failed_checks": failed, "range_breaks": ranges, "alerts": alerts, "run_book": book, "history": history}


@router.get("/api/company/build/ops")
def get_api_company_build_ops(request: Request) -> dict:
    return build(plane := _plane(request), _viewer(request), wh.today(plane))


def _act(request: Request, alert_id: str, action: str, body: dict) -> dict:
    note = body.get("note")
    hit = store_alerts.act(_plane(request), alert_id, action, _viewer(request).name, note.strip()[:500] if isinstance(note, str) and note.strip() else None)
    if hit is None:
        raise HTTPException(404, "No such alert")
    return hit


@router.post("/api/company/build/alerts/{alert_id}/ack")
def post_api_company_build_alerts_ack(alert_id: str, request: Request, body: dict = Body(default={})) -> dict:
    return _act(request, alert_id, "ack", body)


@router.post("/api/company/build/alerts/{alert_id}/close")
def post_api_company_build_alerts_close(alert_id: str, request: Request, body: dict = Body(default={})) -> dict:
    return _act(request, alert_id, "close", body)
