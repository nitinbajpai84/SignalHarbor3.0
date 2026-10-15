"""GET /api/company/feeds/{code}: one measure's own page. The full trend, the latest and its change, the range verdict with its basis, the
definition (from the baseline), the pipeline that feeds it and its last run. Someone outside the access list gets name, owner and the
restricted text only (same rule as feeds.build)."""
import json
import logging

import duckdb
from fastapi import APIRouter, HTTPException, Request

from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store.kpis import read_kpis
from sh_platform.consume import feeds
from sh_platform.profile.api import _plane, _viewer
from sh_platform.warehouse import open_readonly

from sh_platform.consume.range import CODE, breaks  # the one range rule for the product

log = logging.getLogger(__name__)
router = APIRouter()


def _full_trend(plane, code: str) -> list[dict]:
    """Every period of gold.<code>, oldest first (feeds._trend keeps nine)."""
    table = code.lower()
    if not CODE.fullmatch(table):
        return []
    try:
        con = open_readonly(plane)
    except duckdb.Error:
        return []
    try:
        cols = [c[0] for c in con.execute(f"describe gold.{table}").fetchall()]
        if len(cols) < 2:
            return []
        rows = con.execute(f'select "{cols[0]}", sum(try_cast("{cols[-1]}" as double)) from gold.{table} group by 1 order by 1').fetchall()
    except duckdb.Error:
        return []
    finally:
        con.close()
    return [{"period": str(r[0]), "value": float(r[1])} for r in rows if r[1] is not None]


def _range(trend: list[dict]) -> dict:
    """The one range rule (sh_platform/consume/range.py) with its own basis text."""
    r = breaks(trend)
    out = bool(r.get("break"))
    verdict = "Outside its usual range" if out else ("Within its usual range" if len(trend) > 1 else "Not available yet")
    return {"verdict": verdict, "outside": out, "basis": r.get("basis") or "Not available yet"}


def _unit(name: str, definition: str) -> str | None:
    """What the figure counts, read from the measure's own definition text. None when it does not say."""
    d, n = definition.lower(), name.lower()
    if "person-hours" in d:
        return "hours"
    if "/" in d or "divided by" in d:
        return "share of total (0 to 1)" if any(w in n for w in ("share", "allocation", "concentration")) else "ratio (0 to 1)"
    if "sgd" in d or any(w in d for w in ("cash", "funding", "commitment", "obligations")):
        return "SGD"
    return None


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pipeline(plane, code: str) -> dict | None:
    mart, runs = f"gold.{code.lower()}", ((_read(plane.path("warehouse", "runs.json")) or {}).get("runs") or [])
    folder = plane.path("build", "pipelines")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        p = _read(f)
        if isinstance(p, dict) and mart in (p.get("marts") or []):
            last = next((r for r in reversed(runs) if r.get("source") == p.get("source")), None)  # newest last
            return {"source": p.get("source"), "expected": p.get("expected"), "sla": p.get("sla"), "owner": p.get("owner"), "last_run": last}
    return None


def _definition(plane, k: dict) -> dict:
    d = k.get("definition")
    parts = T.parts_of(k)
    return {"business": T.text_of(d) if isinstance(d, dict) and d.get("mark") != "unknown" else None,
            "technical": [{"label": T.LABELS[p], "text": T.text_of(parts[p])} for p in T.TEXT_PARTS if T.present(parts[p])]}


def _card(plane, viewer, pack_names, code: str):
    from sh_platform.consume import cards  # lazy: cards imports feeds
    return cards.get_card(plane, viewer, feeds.build(plane, viewer, pack_names)["measures"], code)[1]


def build(plane, viewer, pack_names: dict[str, str] | None, code: str) -> dict | None:
    card = next((m for m in feeds.build(plane, viewer, pack_names)["measures"] if m["code"] == code), None)
    if card is None:
        return None
    head = {"code": code, "name": card["name"], "owner": card["owner"], "may_see": card["may_see"],
            "links": {"map": f"/centre/intent/map/measure:{code}", "register": "/centre/register"}}
    if not card["may_see"]:
        return {**head, "restricted": f"Restricted: ask {card['owner'] or 'the owner'}"}
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    k = next((x for x in read_kpis(plane, base["id"]) if isinstance(x, dict) and x.get("id") == code), None) if base else None
    trend = _full_trend(plane, code)
    prev = trend[-2] if len(trend) > 1 else None
    latest = trend[-1] if trend else None
    change = {"previous_period": prev["period"], "absolute": latest["value"] - prev["value"],
              "percent": (latest["value"] - prev["value"]) / prev["value"] * 100 if prev["value"] else None} if prev else None
    biz = T.text_of(k.get("definition")) if k and isinstance(k.get("definition"), dict) else ""
    return {**head, "restricted": None, "unit": _unit(card["name"], biz) if k else None, "trend": trend, "latest": latest, "change": change, "range": _range(trend),
            "definition": _definition(plane, k) if k else None, "baseline_id": base["id"] if base and k else None,
            "pipeline": _pipeline(plane, code), "card": _card(plane, viewer, pack_names, code)}


@router.get("/api/company/feeds/{code}")
def get_api_company_feed(code: str, request: Request) -> dict:
    out = build(_plane(request), _viewer(request), feeds._pack_names(request), code)
    if out is None:
        raise HTTPException(404, "No such measure.")
    return out
