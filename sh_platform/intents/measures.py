"""Centre counters and measures (spec 19): `GET /api/intents/measures`, M01 to M15, computed on every read from `intents/<id>/intent.json`,
the week files and LI-OUTCOMES (`sh_platform/outcomes.py`, M05 to M07, unchanged). Nothing is cached or written.

`home_counters(plane, viewer)` is the single source of the four home counters (file 04): M01 and M02 this month, M13 over the last six
months, M08 this quarter. `centre_use(plane, window)` is the super admin's counts-only table (Screen 3). A measure with no qualifying record
has `value: null` and `missing` naming what is missing; zero only when such a record exists and none met the condition.
"""
from datetime import datetime, timezone
from statistics import median

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform import outcomes
from sh_platform.intents import _plane, _viewer
from sh_platform.intents.clock import working_days_between
from sh_platform.intents.lifecycle import company_zone
from sh_platform.intents.store import ID_RE, areas_of, tier_of
from sh_platform.jsonfile import read_json_strict
from sh_platform.profile import view as pview

router = APIRouter()

TYPES = ("initiative", "brainstorm", "pulse", "problem", "decision")
WINDOWS = ("3m", "6m", "12m", "quarter")
HOME = ("M01", "M02", "M08", "M13")
SMALL, RATINGS_FROM = 5, 3
NA = "Not available yet. "
NOTHING_CLOSED = NA + "Nothing has closed."
SUPER_ONLY = "Super admin sees counts only"
NAMES = {
    "M01": "Intents opened per type per month", "M02": "Closed inside the time box", "M03": "Days from open to close by type",
    "M04": "Extensions per intent", "M05": "People minutes per intent", "M06": "Cards per person in the first five minutes",
    "M07": "Definitions confirmed unchanged", "M08": "Build-ready charters per quarter", "M09": "Brainstorms that became initiatives",
    "M10": "Weekly check-in items that became problems or backlog", "M11": "Problems closed with a root cause",
    "M12": "Decisions recorded", "M13": "Average rating by type", "M14": "Intents that led to another intent",
    "M15": "Outcomes used after one month"}


# ---- reading ---------------------------------------------------------------------------------------------------------------

def _t(v) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _dirs(plane) -> list:
    try:
        return sorted(p for p in plane.path("intents").iterdir() if p.is_dir() and ID_RE.fullmatch(p.name))
    except OSError:
        return []


def _read(path):
    try:
        return read_json_strict(path, dict)
    except (OSError, ValueError):
        return None  # a damaged record drops out, as in the store's lists


def load(plane) -> list[dict]:
    """Every readable intent record that has left `draft` (drafts are excluded everywhere)."""
    recs = [r for d in _dirs(plane) if isinstance(r := _read(d / "intent.json"), dict)]
    return [r for r in recs if r.get("state") not in (None, "draft") and r.get("type") in TYPES]


def weeks(plane, intent_id: str) -> list[dict]:
    try:
        files = sorted(plane.path("intents", intent_id, "weeks").glob("*.json"))
    except OSError:
        return []
    return [w for f in files if isinstance(w := _read(f), dict)]


# ---- periods ---------------------------------------------------------------------------------------------------------------

def months(window: str, tz, now: datetime | None = None) -> list[str]:
    """Calendar months (YYYY-MM, oldest first) in the company's zone: the last n months, `quarter` (this quarter so far) or `1m`."""
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    n = {"1m": 1, "3m": 3, "6m": 6, "12m": 12}.get(window) or (now.month - 1) % 3 + 1
    out, y, m = [], now.year, now.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def _month(v, tz) -> str | None:
    d = _t(v)
    return d.astimezone(tz).strftime("%Y-%m") if d else None


def _closed_at(r: dict):
    return (r.get("closure") or {}).get("closed_at")


def _opened_at(r: dict):
    st = r.get("stages") or []
    return (st[0] or {}).get("opened_at") if st and isinstance(st[0], dict) else None


def _bm_stage(r: dict) -> dict:
    return next((s for s in r.get("stages") or [] if isinstance(s, dict) and s.get("key") == "build_ready"), {})


# ---- one measure ----------------------------------------------------------------------------------------------------------

def _m(mid: str, value=None, *, numerator=None, denominator=None, by_type=None, by_month=None, ids=(), missing=None,
       small_group=False, **extra) -> dict:
    return {"id": mid, "name": NAMES[mid], "value": value, "numerator": numerator, "denominator": denominator, "by_type": by_type or {},
            "by_month": by_month or [], "ids": sorted(ids), "missing": missing, "small_group": small_group, **extra}


def _share(mid, pool, ok, mons, tz, when, missing, **extra) -> dict:
    """An "n of m" measure: `pool` qualifies, `ok(r)` meets the condition; month of `when(r)`."""
    if not pool:
        return _m(mid, missing=missing)
    inw = [r for r in pool if _month(when(r), tz) in mons]
    if not inw:  # records exist, none in this window: not "0 of 0"
        return _m(mid, missing=missing)
    good = [r for r in inw if ok(r)]
    by_type = {t: {"numerator": sum(1 for r in good if r["type"] == t), "denominator": n}
               for t in TYPES if (n := sum(1 for r in inw if r["type"] == t))}
    by_month = [{"month": mo, "numerator": sum(1 for r in good if _month(when(r), tz) == mo),
                 "denominator": sum(1 for r in inw if _month(when(r), tz) == mo)} for mo in mons]
    return _m(mid, len(good), numerator=len(good), denominator=len(inw), by_type=by_type, by_month=by_month,
              ids=[r["id"] for r in inw], **extra)


def m01(recs, mons, tz) -> dict:
    if not recs:
        return _m("M01", missing=NA + "No intent has been opened.")
    inw = [r for r in recs if _month(_opened_at(r), tz) in mons]
    return _m("M01", len(inw), numerator=len(inw), by_type={t: n for t in TYPES if (n := sum(1 for r in inw if r["type"] == t))},
              by_month=[{"month": mo, "count": sum(1 for r in inw if _month(_opened_at(r), tz) == mo),
                         **{t: sum(1 for r in inw if r["type"] == t and _month(_opened_at(r), tz) == mo) for t in TYPES}} for mo in mons],
              ids=[r["id"] for r in inw])


def _in_box(r: dict) -> bool:
    c, e = _t(_closed_at(r)), _t((r.get("time_box") or {}).get("ends"))  # `ends` is the end after every extension
    return bool(c and e and c <= e)


def m02(closed, mons, tz) -> dict:
    judged = [r for r in closed if (r.get("time_box") or {}).get("ends")]  # no end date: cannot be judged, left out
    return _share("M02", judged, _in_box, mons, tz, _closed_at, NOTHING_CLOSED)


def _wdays(r: dict) -> float | None:
    a, b = _t(_opened_at(r)), _t(_closed_at(r))
    return round(working_days_between(a, b), 1) if a and b else None


def m03(closed, mons, tz) -> dict:
    if not closed:
        return _m("M03", missing=NOTHING_CLOSED)
    inw = [(r, d) for r in closed if _month(_closed_at(r), tz) in mons and (d := _wdays(r)) is not None]
    if not inw:
        return _m("M03", missing=NOTHING_CLOSED)

    def med(ds):
        return (round(median(ds), 1), False) if len(ds) >= SMALL else (None, True)
    by_type = {}
    for t in TYPES:
        ds = [d for r, d in inw if r["type"] == t]
        if ds:
            v, small = med(ds)
            by_type[t] = {"count": len(ds), "median": v, "small_group": small}
    v, small = med([d for _, d in inw])
    return _m("M03", v, denominator=len(inw), by_type=by_type, small_group=small, ids=[r["id"] for r, _ in inw],
              by_month=[{"month": mo, "count": sum(1 for r, _ in inw if _month(_closed_at(r), tz) == mo)} for mo in mons])


def _ext(r: dict) -> int:
    return len((r.get("time_box") or {}).get("extended_by") or [])


def m04(closed, mons, tz) -> dict:
    out = _share("M04", closed, lambda r: _ext(r) > 0, mons, tz, _closed_at, NOTHING_CLOSED)
    if out["missing"] is None:
        inw = [r for r in closed if _month(_closed_at(r), tz) in mons]
        out["extensions"] = sum(_ext(r) for r in inw)
        for t, row in out["by_type"].items():
            row["extensions"] = sum(_ext(r) for r in inw if r["type"] == t)
    return out


def _signed_walls(plane) -> int:
    try:
        files = plane.path("intents", "m1_intent", "outcomes").glob("*.json")
        return sum(1 for f in files if isinstance(o := _read(f), dict) and o.get("signed_at"))
    except OSError:
        return 0


def m05_m07(plane, viewer, account_names: list[str]) -> list[dict]:
    """LI-OUTCOMES unchanged. These are company-wide current figures, so they carry no month strip and no intent ids."""
    li = outcomes.build(plane, viewer, account_names)
    head, wall = li["headline"], li["modules"][0]
    no_minutes = {t: {"missing": NA + "This type records no minutes."} for t in TYPES if t != "initiative"}
    if wall["minutes"] is None:
        m5 = _m("M05", missing=NA + "No wall has been signed.", by_type=no_minutes)
    elif (n := _signed_walls(plane)) < SMALL:
        m5 = _m("M05", denominator=n, small_group=True, by_type=no_minutes)
    else:
        m5 = _m("M05", wall["minutes"], denominator=n, actions=wall["actions"], free_text=wall["free_text"], by_type=no_minutes)
    v1 = {"note": "v1, Initiatives only"}
    if head["cards_first_five"] is None:
        m6 = _m("M06", missing=NA + "No card has been written.", **v1)
    else:
        whole = [c for c in pview.read(plane, viewer)["cards"].values() if not c.get("silhouette")]
        named = {outcomes._v(c.get("author")) for c in whole if outcomes._v(c.get("anonymous")) is not True and outcomes._v(c.get("author"))}
        small = len(named) < SMALL
        m6 = _m("M06", None if small else head["cards_first_five"], denominator=len(named), small_group=small, **v1)
    du = head["definitions_unchanged"]
    m7 = (_m("M07", du["unchanged"], numerator=du["unchanged"], denominator=du["of"]) if du
          else _m("M07", missing=NA + "No data owner has confirmed a definition."))
    return [m5, m6, m7]


def m08(recs, mons, tz) -> dict:
    reached = [r for r in recs if r["type"] == "initiative" and r["state"] != "cancelled" and _bm_stage(r).get("closed_at")]
    if not reached:
        return _m("M08", missing=NA + "No Initiative has reached the check.")
    ready = [r for r in reached if (r.get("outcome") or {}).get("build_ready") is True
             and _month(_bm_stage(r)["closed_at"], tz) in mons]
    handed = [r for r in ready if (r.get("links") or {}).get("build")]
    return _m("M08", len(ready), numerator=len(handed), denominator=len(ready), handed=len(handed), waiting=len(ready) - len(handed),
              by_type={"initiative": len(ready)} if ready else {}, ids=[r["id"] for r in ready],
              by_month=[{"month": mo, "count": sum(1 for r in ready if _month(_bm_stage(r)["closed_at"], tz) == mo)} for mo in mons])


def _next(r: dict) -> list[dict]:
    return [n for n in (r.get("closure") or {}).get("next") or [] if isinstance(n, dict)]


def m09(closed_all, by_id, mons, tz) -> dict:
    def became(r):
        return any(n.get("kind") == "initiative" and (t := by_id.get(n.get("ref"))) and t["type"] == "initiative"
                   and (t.get("links") or {}).get("from") == r["id"] for n in _next(r))
    pool = [r for r in closed_all if r["type"] == "brainstorm"]
    return _share("M09", pool, became, mons, tz, _closed_at, NA + "No Brainstorm has closed.")


def m10(plane, recs, by_id, mons, tz) -> dict:
    series = [r for r in recs if r["type"] == "pulse" and r["state"] != "cancelled"]
    closed = [(r["id"], w) for r in series for w in weeks(plane, r["id"]) if w.get("closed_at")]
    if not closed:
        return _m("M10", missing=NA + "No weekly check-in week has closed.")
    counts, ids, unresolved, by_month = {"problem": 0, "backlog": 0, "handled": 0, "nothing": 0}, set(), [], []
    month_counts = {mo: {"problem": 0, "backlog": 0, "handled": 0, "nothing": 0, "items": 0} for mo in mons}
    for iid, w in closed:
        mo = _month(w["closed_at"], tz)
        if mo not in mons:
            continue
        ids.add(iid)
        for it in w.get("items") or []:
            if not isinstance(it, dict):
                continue
            fate = it.get("fate") if it.get("fate") in counts else "nothing"
            if fate == "problem":
                ref = it.get("fate_ref") or (it.get("decision") or {}).get("fate_ref")
                if not ((t := by_id.get(ref)) and t["type"] == "problem"):
                    fate = "nothing"
                    unresolved.append(f"{w.get('week_key')}/{it.get('id')}")
            counts[fate] += 1
            month_counts[mo][fate] += 1
            month_counts[mo]["items"] += 1
    total = sum(counts.values())
    if not ids:
        return _m("M10", missing=NA + "No weekly check-in week has closed.")
    by_month = [{"month": mo, **c} for mo, c in month_counts.items()]
    missing = (f"{len(unresolved)} problem {'fate has' if len(unresolved) == 1 else 'fates have'} no Problem intent behind "
               f"{'it' if len(unresolved) == 1 else 'them'} and {'is' if len(unresolved) == 1 else 'are'} counted as nothing.") if unresolved else None
    return _m("M10", counts["problem"] + counts["backlog"], numerator=counts["problem"] + counts["backlog"], denominator=total,
              by_type={"pulse": counts}, by_month=by_month, ids=ids, missing=missing, fates=counts, unresolved=unresolved)


def _root_and_fix(r: dict) -> bool:
    o = r.get("outcome") or {}
    rc = o.get("root_cause")
    named_cause = bool(rc) and not (isinstance(rc, dict) and rc.get("unknown") is True)
    return named_cause and bool((o.get("fix") or {}).get("by") if isinstance(o.get("fix"), dict) else False)


def m11(closed_all, mons, tz) -> dict:
    return _share("M11", [r for r in closed_all if r["type"] == "problem"], _root_and_fix, mons, tz, _closed_at, NA + "No Problem has closed.")


def m12(closed_all, mons, tz) -> dict:
    def recorded(r):
        o = r.get("outcome") or {}
        return all(o.get(k) for k in ("chosen", "decided_by", "why"))
    return _share("M12", [r for r in closed_all if r["type"] == "decision"], recorded, mons, tz, _closed_at, NA + "No Decision has closed.")


def _scores(r: dict) -> list[int]:
    return [s for x in r.get("ratings") or [] if isinstance(x, dict) and isinstance(s := x.get("score"), int) and 1 <= s <= 5]


def m13(closed, mons, tz) -> dict:
    if not any(_scores(r) for r in closed):
        return _m("M13", missing=NA + "No ratings have been given.")
    inw = [r for r in closed if _month(_closed_at(r), tz) in mons and _scores(r)]
    if not inw:
        return _m("M13", missing=NA + "No ratings have been given.")

    def mean(ss):
        return (round(sum(ss) / len(ss), 1), False) if len(ss) >= RATINGS_FROM else (None, True)
    by_type = {}
    for t in TYPES:
        ss = [s for r in inw if r["type"] == t for s in _scores(r)]
        if ss:
            v, small = mean(ss)
            by_type[t] = {"mean": v, "ratings": len(ss), "small_group": small}
    allss = [s for r in inw for s in _scores(r)]
    v, small = mean(allss)
    return _m("M13", v, denominator=len(allss), ratings=len(allss), by_type=by_type, small_group=small, ids=[r["id"] for r in inw],
              by_month=[{"month": mo, "ratings": sum(len(_scores(r)) for r in inw if _month(_closed_at(r), tz) == mo)} for mo in mons])


def m14(closed_all, by_id, mons, tz) -> dict:
    def led(r):
        return any(n.get("kind") in ("initiative", "problem") and n.get("ref") in by_id for n in _next(r))
    return _share("M14", closed_all, led, mons, tz, _closed_at, NOTHING_CLOSED)


def m15(closed_all, mons, tz) -> dict:
    asked = [r for r in closed_all if isinstance(r.get("outcome_used"), dict) and r["outcome_used"].get("asked_at")]
    if not asked:
        return _m("M15", missing=NA + "Nobody has been asked whether the outcome is used.")
    inw = [r for r in asked if _month(_closed_at(r), tz) in mons]
    if not inw:
        return _m("M15", missing=NA + "Nobody has been asked whether the outcome is used.")
    ans = [r["outcome_used"].get("answer") for r in inw]
    answers = {"yes": ans.count("yes"), "partly": ans.count("partly"), "no": ans.count("no"),
               "not_answered": sum(1 for a in ans if a not in ("yes", "partly", "no"))}
    by_type = {t: {"denominator": n} for t in TYPES if (n := sum(1 for r in inw if r["type"] == t))}
    return _m("M15", answers["yes"], numerator=answers["yes"], denominator=len(inw), answers=answers, by_type=by_type,
              ids=[r["id"] for r in inw],
              by_month=[{"month": mo, "count": sum(1 for r in inw if _month(_closed_at(r), tz) == mo)} for mo in mons])


# ---- the sets ---------------------------------------------------------------------------------------------------------------

def _visible(plane, viewer: pview.Viewer, recs: list[dict]) -> list[dict]:
    """Company admin: every intent. Anyone else: only those they may see (file 01's tiers)."""
    if pview.ADMIN in viewer.roles:
        return recs
    areas = areas_of(plane, viewer)
    return [r for r in recs if tier_of(r, viewer, areas)]


def _pools(recs):
    live = [r for r in recs if r["state"] != "cancelled"]
    closed_all = [r for r in live if r["state"] == "closed"]
    return live, closed_all, [r for r in closed_all if r["type"] != "pulse"]  # a check-in series is not rated and has no close


def compute(plane, viewer: pview.Viewer, window: str = "6m", type_: str | None = None, account_names: list[str] | None = None,
            now: datetime | None = None) -> dict:
    tz = company_zone(plane)
    full = pview.ADMIN in viewer.roles
    every = load(plane)
    recs = [r for r in _visible(plane, viewer, every) if not type_ or r["type"] == type_]
    by_id = {r["id"]: r for r in every}
    mons = months(window, tz, now)
    live, closed_all, closed = _pools(recs)
    if not full:
        ms = [m01(recs, mons, tz), m02(closed, mons, tz), m08(recs, mons, tz), m13(closed, mons, tz)]
    else:
        ms = [m01(recs, mons, tz), m02(closed, mons, tz), m03(closed, mons, tz), m04(closed, mons, tz),
              *m05_m07(plane, viewer, account_names or []), m08(recs, mons, tz), m09(closed_all, by_id, mons, tz),
              m10(plane, live, by_id, mons, tz), m11(closed_all, mons, tz), m12(closed_all, mons, tz), m13(closed, mons, tz),
              m14(closed_all, by_id, mons, tz), m15(closed_all, mons, tz)]
    return {"company": plane.company_id, "window": window, "months": mons, "time_zone": str(tz), "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "all" if full else "visible", "measures": ms}


def home_counters(plane, viewer: pview.Viewer, now: datetime | None = None) -> dict:
    """The four home counters (file 04), by id: M01 and M02 this month, M08 this quarter, M13 the last six months."""
    tz = company_zone(plane)
    recs = _visible(plane, viewer, load(plane))
    _, _, closed = _pools(recs)
    month, quarter, six = months("1m", tz, now), months("quarter", tz, now), months("6m", tz, now)
    return {"scope": "all" if pview.ADMIN in viewer.roles else "visible",
            "M01": m01(recs, month, tz), "M02": m02(closed, month, tz), "M08": m08(recs, quarter, tz), "M13": m13(closed, six, tz)}


def centre_use(plane, window: str = "6m", now: datetime | None = None) -> dict:
    """Super admin, Screen 3: per month, intents opened per type, closed, cancelled. Exact counts, no title, person, rating or content."""
    tz = company_zone(plane)
    recs = load(plane)
    rows = [{"month": mo,
             "opened": {t: sum(1 for r in recs if r["type"] == t and _month(_opened_at(r), tz) == mo) for t in TYPES},
             "closed": sum(1 for r in recs if r["state"] == "closed" and _month(_closed_at(r), tz) == mo),
             "cancelled": sum(1 for r in recs if r["state"] == "cancelled" and _month(_closed_at(r), tz) == mo)}
            for mo in months(window if window in ("6m", "12m") else "6m", tz, now)]
    return {"company": plane.company_id, "scope": "counts", "time_zone": str(tz), "opened_any": bool(recs), "months": rows}


@router.get("/api/intents/measures")
def get_intents_measures(request: Request, window: str = "6m", type: str | None = None):
    if "super_admin" in (request.state.roles or []):
        return JSONResponse({"error": "super_admin_counts_only", "message": SUPER_ONLY}, status_code=403)
    if window not in WINDOWS:
        window = "6m"
    if type is not None and type not in TYPES:
        type = None
    try:
        plane = _plane(request)
    except PermissionError:
        return JSONResponse({"error": "no_company", "message": "We could not find that."}, status_code=404)
    names = [str(a.get("display_name") or "") for a in request.app.state.account_store.in_company(request.state.company_id)]
    return compute(plane, _viewer(request), window, type, [n for n in names if n])
