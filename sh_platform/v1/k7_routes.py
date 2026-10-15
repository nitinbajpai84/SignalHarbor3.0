"""K7 benchmark read path (Consume).

GET /api/v1/benchmarks                                                    signed definitions with status; in_progress ones carry the policy question
GET /api/v1/benchmarks/comparison?portfolio=&code=&start=YYYY-MM&end=YYYY-MM   per month: portfolio return, benchmark return (per component, blended), difference
Nothing is calculated here except the liquid-sleeve line (the signed components with no spread, weights renormalised, Decimal); every other figure is
e3_calc via k7_benchmark.comparison. Returns are fractions (0.035 = 3.5%) with a `pct` string rounded to 4 places. Read only: asking never opens a case."""
import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e1_access, k7_benchmark, wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found"}
NOTICE = "In progress: not used for certified figures."
QUESTION = "Who decides what this benchmark contains, and from when?"


def _fig(v) -> dict | None:
    return None if v is None else {"value": str(v), "pct": str((v * 100).quantize(Decimal("0.0001"), ROUND_HALF_UP))}


def _plain(v) -> str:
    return format(Decimal(v).normalize(), "f")  # 0.5000000000 -> 0.5


def _month(s: str) -> date:
    try:
        y, m = (int(x) for x in s.split("-"))
        return date(y, m, 1)
    except ValueError:
        raise Refused(400, "Months are written like 2026-09.") from None


def _end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def definitions(plane) -> dict:
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute("select id, benchmark_code, benchmark_name, version_number, reporting_currency, effective_from, effective_to, approval_status "
                          "from benchmark_definitions order by benchmark_code, version_number")
        rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
        cases = {r[0]: {"case_id": str(r[1]), "title": r[0], "status": r[2]} for r in con.execute(
            "select title, id, status from exceptions where exception_type = ? and status not in ('resolved', 'rejected')", [k7_benchmark.POLICY_TYPE]).fetchall()}
        out = []
        for d in rows:
            comps = con.execute("select market_series_key, component_weight, spread_bps from benchmark_components "
                                "where benchmark_definition_id = ? order by market_series_key, weight_effective_from", [d["id"]]).fetchall()
            item = {"benchmark_code": d["benchmark_code"], "benchmark_name": d["benchmark_name"], "version": d["version_number"], "currency": d["reporting_currency"],
                    "effective_from": str(d["effective_from"]), "effective_to": d["effective_to"] and str(d["effective_to"]), "status": d["approval_status"],
                    "components": [{"series_key": c[0], "weight": _plain(c[1]), "spread_bps": _plain(c[2] or 0)} for c in comps]}
            if d["approval_status"] != "approved":
                item["notice"] = NOTICE
                item["policy_question"] = {"question": QUESTION, "case": cases.get(k7_benchmark._title(d["benchmark_code"]))}
            out.append(item)
    return {"definitions": out}


def _portfolio(plane, viewer, ref: str) -> tuple[str, str]:
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select id, portfolio_code from portfolios where cast(id as varchar) = ? or portfolio_code = ?", [ref, ref]).fetchone()
    if not r or e1_access.level(plane, viewer, portfolio_id=str(r[0])) == "none":
        raise Refused(404, "That portfolio was not found.")  # a portfolio you may not see looks the same as one that does not exist
    return str(r[0]), r[1]


def _liquid(components: list[dict]) -> Decimal | None:
    """Return of the components with no spread, weights renormalised (the liquid sleeve alone)."""
    liquid = [c for c in components if c["spread_return"] == 0]
    w = sum(c["weight"] for c in liquid)
    return sum(c["weight"] * c["index_return"] for c in liquid) / w if liquid and len(liquid) < len(components) and w else None


def monthly(plane, viewer, portfolio: str, code: str, start: str, end: str) -> dict:
    pid, pcode = _portfolio(plane, viewer, portfolio)
    last = _month(end) if end else (_month(start) if start else (wh.today(plane).replace(day=1) - timedelta(1)).replace(day=1))
    first = _month(start) if start else last
    if last < first or (last.year - first.year) * 12 + last.month - first.month > 35:
        raise Refused(400, "Choose a period of up to 36 months, ending after it starts.")
    months, m, d = [], first, None
    while m <= last:
        opening = m - timedelta(1)
        c = k7_benchmark.comparison(plane, pid, code, opening, _end(m))
        d = c["benchmark"]["definition"] or d   # the version the last month was actually worked out with
        comps = c["benchmark"]["components"]
        liquid = _liquid(comps)
        p = c["portfolio"]["value"]
        months.append({
            "month": f"{m:%Y-%m}", "period_start": str(opening), "period_end": str(_end(m)),
            "portfolio": _fig(p), "benchmark": _fig(c["benchmark"]["value"]), "difference": _fig(c["difference"]),
            "components": [{"series_key": x["series_key"], "weight": _plain(x["weight"]), "index_return": _fig(x["index_return"]),
                            "spread_return": _fig(x["spread_return"]), "return": _fig(x["index_return"] + x["spread_return"])} for x in comps],
            "liquid_sleeve": None if liquid is None else {**_fig(liquid), "difference": None if p is None else _fig(p - liquid)},
            "certified": c["certified"], "problems": c["problems"]})
        m = (m + timedelta(32)).replace(day=1)
    version = None if d is None else {"version": d["version_number"], "status": d["approval_status"], "name": d["benchmark_name"]}
    if version and version["status"] != "approved":
        version["notice"] = NOTICE
    return {"portfolio": {"id": pid, "code": pcode}, "benchmark_code": code, "version_used": version, "months": months}


async def _run(request: Request, fn):
    viewer = require_seat(request, CONSUMER)
    try:
        return await run_in_threadpool(fn, _plane(request), viewer)
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


@router.get("/api/v1/benchmarks")
async def get_definitions(request: Request):
    return await _run(request, lambda p, v: definitions(p))


@router.get("/api/v1/benchmarks/comparison")
async def get_comparison(request: Request, portfolio: str = "", code: str = "", start: str = "", end: str = ""):
    if not portfolio or not code:
        return JSONResponse({"error": "invalid", "message": "Choose a portfolio and a benchmark."}, status_code=400)
    return await _run(request, lambda p, v: monthly(p, v, portfolio, code, start, end))
