"""Proving (spec 58): a closed Initiative's change is followed from go-live to its review date.

Records: `intents/<id>/proving.json` (the track) and `intents/<id>/proving/<week_key>.json` (one weekly report). The intent record stays
read-only; the only key written on it is `outcome_used` (spec 10) when the review is confirmed. No scheduler: `tick` runs on the first
read on or after the company's report day (default Friday, C13), under the intent lock, the check-in clock pattern (checkin.tick).
North drafts the report from the warehouse (read-only), applies the four verdict rules in order and words its confidence; people
confirm, change the verdict, add notes and settle the review. Others import `tick`, `pulse_lines`, `chip_of`, `begin`, `seed`.
Run `python -m sh_platform.intents.proving seed <data_root> <company>` to start Proving for the seeded Initiatives.
"""
import calendar
import copy
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, events, lifecycle as L, store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
router = APIRouter()

WORDS = {"working": "Working", "partly": "Partly", "not": "Not working", "too_early": "Too early"}
SURE = {"fairly_sure": "Fairly sure", "not_sure": "Not sure", "unlikely": "Unlikely"}
CHIP = {"waiting": "Waiting for release", "proving": "Proving", "reviewing": "Proving", "proved": "Proved",
        "returned": "Sent back to the radar", "stopped": "Stopped"}
LIVE, ENDED = ("waiting", "proving", "reviewing"), ("proved", "returned", "stopped")
ACTIONS = ("keep", "more_time", "send_back", "stop")
DAYS = ("mon", "tue", "wed", "thu", "fri")
MIN_DEFAULT = {"monthly": 2, "daily": 6}  # C12
COUNTER_DEFAULT, KEEP_DAYS, TEXT_MAX = 6, 14, 600  # C12, C17
# C18: a breakdown where the gold table carries none of its own (gold.k23 has no reader column; its silver source does)
BREAKDOWN = {"K23": ("silver.engagement_report_opens_monthly", "reader", "report_opens")}
NOT_FOUND = "We could not find that."
MINUTES = {"decision": 3, "outcome": 2}


class Refuse(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- the events this file writes, joined to the one writer's table (Shared files needed: move into events.py) -------------
def _register_kinds() -> None:
    events.DETAIL.update({"proving_started": {"from", "by_clock"}, "proving_start_changed": set(), "report_drafted": {"week_key", "verdict", "state"},
                          "report_confirmed": {"week_key", "verdict"}, "verdict_changed": {"week_key", "from", "to"},
                          "review_sent": {"action"}, "review_returned": set(), "review_confirmed": {"action"}, "sent_back": {"opportunity"}})
    events.AGENT_LINES.setdefault("report_drafted", "north")
    events.CLOCK_OK = events.CLOCK_OK | {"proving_started"}
    events.AFTER_CLOSE = events.AFTER_CLOSE | {"proving_started", "proving_start_changed", "report_drafted", "report_confirmed", "verdict_changed",
                                               "review_sent", "review_returned", "review_confirmed", "sent_back", "note_added"}
    events.GROUP_OF.update({"proving_started": "stages", "report_drafted": "agent", "proving_start_changed": "signoff", "report_confirmed": "signoff",
                            "verdict_changed": "signoff", "review_sent": "signoff", "review_returned": "signoff", "review_confirmed": "signoff",
                            "sent_back": "links"})


_register_kinds()


def _event(plane, iid: str, kind: str, who, detail: dict, status: str = "act") -> None:
    events.try_append(plane, iid, kind, who, {"store": "proving", "id": iid}, detail, status, stage="proving")


# ---- files ---------------------------------------------------------------------------------------------------------------
def _pfile(plane, iid: str):
    return plane.path("intents", iid, "proving.json")


def _rfile(plane, iid: str, wk: str):
    return plane.path("intents", iid, "proving", f"{wk}.json")


def _read(path) -> dict | None:
    try:
        d = read_json_strict(path, dict)
    except (OSError, ValueError):
        raise S.Unreadable(str(path)) from None
    return d


def read_proving(plane, iid: str) -> dict | None:
    return _read(_pfile(plane, iid)) if S.ID_RE.fullmatch(str(iid)) else None


def read_report(plane, iid: str, wk: str) -> dict | None:
    return _read(_rfile(plane, iid, wk)) if re.fullmatch(r"\d{4}-W\d{2}", str(wk)) else None


def _write(plane, pv: dict) -> None:
    write_json_atomic(_pfile(plane, pv["intent_id"]), pv)
    _index(plane, pv["intent_id"], index_fields(pv))


def index_fields(pv: dict | None) -> dict:
    """The index row fields (C20): `proving` (state) and `proving_since` (start day)."""
    return {"proving": pv["state"] if pv else None, "proving_since": (pv.get("start") or {}).get("at", "")[:10] or None if pv else None}


def _index(plane, iid: str, fields: dict) -> None:
    """Row field `proving` (C20). ponytail: patched in place; store._row drops it on the intent's next write (Shared files needed)."""
    path = plane.path("intents", "_index.json")
    with S.locked(plane):
        try:
            doc = read_json_strict(path, dict)
        except (OSError, ValueError):
            return
        for r in (doc or {}).get("rows") or []:
            if r.get("id") == iid and any(r.get(k) != x for k, x in fields.items()):
                r.update(fields)
                write_json_atomic(path, doc)
                return


def chip_of(plane, iid: str) -> str | None:
    """The chip word for the home card and the Past row, or None when the Initiative has no Proving."""
    try:
        pv = read_proving(plane, iid)
    except S.Unreadable:
        return None
    return CHIP.get(pv["state"]) if pv else None


# ---- settings (Screen D): settings/intent_centre.json `proving`; 57's counter_periods sits in its own block ------------------
def _whole(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def rules(plane) -> dict:
    try:
        c = read_json_strict(plane.path("settings", "intent_centre.json"), dict) or {}
    except (OSError, ValueError):
        c = {}
    p = c.get("proving") if isinstance(c.get("proving"), dict) else {}
    counter = next((b.get("counter_periods") for b in (c.get("radar"), c.get("opportunity"), p) if isinstance(b, dict) and _whole(b.get("counter_periods"))), None)
    return {"proving_min_periods": p.get("proving_min_periods") if _whole(p.get("proving_min_periods")) else None,
            "counter_periods": counter, "report_day": p.get("report_day") if p.get("report_day") in DAYS else "fri"}


def _effective(r: dict, grain: str) -> tuple[int, int]:
    return r["proving_min_periods"] or MIN_DEFAULT[grain], r["counter_periods"] or COUNTER_DEFAULT


# ---- dates ---------------------------------------------------------------------------------------------------------------
def _today(plane, now: datetime) -> date:
    return now.astimezone(L.company_zone(plane)).date()


def report_day(today: date, day: str) -> date:
    """The latest report day on or before `today`."""
    return today - timedelta(days=(today.weekday() - DAYS.index(day)) % 7)


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _bounds(period: str) -> tuple[date, date]:
    if len(period) == 7:
        y, m = int(period[:4]), int(period[5:7])
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    d = date.fromisoformat(period[:10])
    return d, d


def _day(text) -> date:
    return date.fromisoformat(str(text)[:10])


# ---- the hypothesis (57) and the warehouse ---------------------------------------------------------------------------------
def _hyp(plane, rec: dict) -> tuple[str, dict] | None:
    ref = rec.get("hypothesis_ref") or {}
    hid = str(ref.get("id") or "")
    if not re.fullmatch(r"hyp-[a-z0-9-]{1,80}", hid):
        return None
    try:
        doc = read_json_strict(plane.path("intents", "hypotheses", f"{hid}.json"), dict) or {}
    except (OSError, ValueError):
        return None
    vs = doc.get("versions") or []
    v = next((x for x in vs if x.get("v") == ref.get("version")), vs[-1] if vs else None)
    return (hid, v) if v and (v.get("measure") or {}).get("id") else None


def _worst(vals: dict, direction: int) -> float | None:
    """A per-segment target holds only when every named segment meets it: the segment furthest from the target speaks for all."""
    xs = [float(x) for x in vals.values() if isinstance(x, (int, float))]
    return (max(xs) if direction < 0 else min(xs)) if xs else None


def _measure(plane, code: str, named: list[str] | None, direction: int) -> tuple[dict, dict, str]:
    """({period: value}, {period: {segment: value}}, trace table). Named segments (a per-entity baseline) give the whole value; otherwise
    the gold value (summed over a breakdown column) is the whole and the breakdown is read for the segment check."""
    if not re.fullmatch(r"K\d{2}", code):
        return {}, {}, ""
    from sh_platform import warehouse
    table = f"gold.{code.lower()}"
    try:
        con = warehouse.open_readonly(plane)
    except Exception as e:  # noqa: BLE001  no warehouse yet: every figure reads "Not available yet"
        log.warning("proving: warehouse unreadable (%s)", type(e).__name__)
        return {}, {}, table
    try:
        cols = [r[0] for r in con.execute(f"describe {table}").fetchall()]
        seg = next((c for c in cols if c not in ("period", "value") and not c.startswith("_")), None)
        whole, segs = {}, {}
        for p, s, v in con.execute(f'select period, {f"{seg}" if seg else "null"}, value from {table}').fetchall():
            if v is None:
                continue
            if s is not None:
                segs.setdefault(str(p), {})[str(s)] = float(v)
            whole[str(p)] = whole.get(str(p), 0.0) + float(v)
        if named:
            whole = {p: w for p, d in segs.items() if (w := _worst({k: d.get(k) for k in named}, direction)) is not None}
            segs = {}  # the named segments are the whole
        elif not seg and code in BREAKDOWN:
            src, scol, vcol = BREAKDOWN[code]
            for p, s, v in con.execute(f"select period, {scol}, {vcol} from {src}").fetchall():
                if v is not None:
                    segs.setdefault(str(p), {})[str(s)] = float(v)
        return whole, segs, table
    except Exception as e:  # noqa: BLE001  a missing table is "Not available yet", never a 500
        log.warning("proving: %s unreadable (%s)", table, type(e).__name__)
        return {}, {}, table
    finally:
        con.close()


def _release(plane) -> dict:
    try:
        return (read_json_strict(plane.path("build", "prove.json"), dict) or {}).get("release") or {}
    except (OSError, ValueError):
        return {}


def _figures_ok(plane, code: str, v) -> bool:
    """A measure the blueprint carries follows its access list (prove._may_see). A measure outside the blueprint: the content tier
    (already required) decides, as it does for the hypothesis that names it."""
    try:
        bp = read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    except (OSError, ValueError):
        return False
    if any(ln.get("measure") == code for ln in bp.get("lineage") or []):
        from sh_platform.build.prove import _may_see
        return _may_see(plane, code, v)
    return True


# ---- North's weekly draft ----------------------------------------------------------------------------------------------------
def _fmt(x) -> str:
    return "Not available yet" if x is None else f"{x:,.4f}".rstrip("0").rstrip(".") if abs(x) < 1 else f"{x:,.2f}".rstrip("0").rstrip(".")


def _others_on(plane, iid: str, code: str) -> list[dict]:
    """Another live Initiative on the same measure: a note traced to it (no title: the reader may not see it)."""
    out, folder = [], plane.path("intents", "hypotheses")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            doc = read_json_strict(f, dict) or {}
        except (OSError, ValueError):
            continue
        v = (doc.get("versions") or [{}])[-1]
        for c in doc.get("carried_into") or []:
            other = c.get("intent")
            if other and other != iid and (v.get("measure") or {}).get("id") == code:
                try:
                    rec = S.read_intent(plane, other)
                except S.Unreadable:
                    rec = None
                if rec and rec["state"] != "cancelled":
                    out.append({"text": "Another Initiative works on the same measure in the same periods.", "by": "North",
                                "trace": {"kind": "intent", "ref": other}, "at": S.now_iso(), "cause": True})
    return out


def _alerts(plane, code: str, start: date) -> list[dict]:
    from sh_platform.build import alerts
    return [{"text": "An alert on this measure was raised in the period.", "by": "North", "trace": {"kind": "alert", "ref": a.get("id")},
             "at": S.now_iso(), "cause": True}
            for a in alerts._read(plane) if a.get("measure") == code and str(a.get("opened") or "")[:10] >= start.isoformat()]


def draft(plane, pv: dict, hv: dict, friday: date, r: dict) -> dict:
    """One report for the week of `friday`, by the rules of spec 58 (Agent behaviour, steps 1 to 5)."""
    code, base, tgt = hv["measure"]["id"], hv.get("baseline") or {}, hv.get("target") or {}
    named = sorted(base["value"]) if isinstance(base.get("value"), dict) else None
    target = tgt.get("value") if isinstance(tgt.get("value"), (int, float)) else None
    bval = base.get("value")
    direction = 0
    if target is not None and bval is not None:
        b0 = _worst(bval, -1 if target < min(bval.values()) else 1) if named else float(bval)
        direction = 1 if target > b0 else -1
    before = _worst(bval, direction) if named and direction else (float(bval) if isinstance(bval, (int, float)) else None)
    whole, segs, table = _measure(plane, code, named, direction or -1)
    start = _day(pv["start"]["at"])
    landed = sorted(p for p in whole if _bounds(p)[1] <= friday)
    grain = "monthly" if landed and len(landed[0]) == 7 else "daily"
    min_p, counter = _effective(r, grain)
    prior = [p for p in landed if _bounds(p)[1] < start][-counter:]
    after = [p for p in landed if _bounds(p)[0] >= start]
    since = [p for p in landed if _bounds(p)[1] >= start]
    series = [p for p in landed if prior and p >= prior[0]] or since
    lo, hi = (min(whole[p] for p in prior), max(whole[p] for p in prior)) if prior else (None, None)
    now = whole[since[-1]] if since else None
    at = (lambda x: (x - target) * direction >= 0) if direction else (lambda x: False)
    notes = _others_on(plane, pv["intent_id"], code) + _alerts(plane, code, start)

    def moved(x, low, high):  # outside the normal range in the direction of the target
        return x > high if direction > 0 else x < low

    seg_moved, seg_still = [], []
    if segs and prior and after and direction:
        for s in sorted({k for p in prior for k in segs.get(p, {})}):
            pre = [segs[p][s] for p in prior if s in segs.get(p, {})]
            last = segs.get(after[-1], {}).get(s)
            if pre and last is not None:
                (seg_moved if moved(last, min(pre), max(pre)) else seg_still).append(s)
        if seg_moved and seg_still:
            notes.append({"text": f"{' and '.join(seg_moved)} moved outside their usual range towards the target; {' and '.join(seg_still)} did not.",
                          "by": "North", "trace": {"kind": "data", "ref": BREAKDOWN.get(code, (table,))[0]}, "at": S.now_iso(), "cause": False})
    # step 4: the first rule that fires wins
    if before is None or target is None:
        verdict, rule = "too_early", "Too early: the hypothesis carries no " + ("baseline." if before is None else "target.")
    elif len(after) < min_p:
        verdict, rule = "too_early", f"Too early: {len(after)} full period{'s' if len(after) != 1 else ''} since the start; a verdict needs {min_p}."
    elif all(at(whole[p]) for p in after[-min_p:]):
        verdict, rule = "working", f"Working: the last {min_p} periods are all at or past the target."
    elif prior and moved(whole[after[-1]], lo, hi) and not at(whole[after[-1]]):
        verdict, rule = "partly", "Partly: the latest period is outside the normal range towards the target, but not at it."
    elif seg_moved and seg_still:
        verdict, rule = "partly", "Partly: one group moved outside its normal range towards the target while another did not."
    else:
        wrong = prior and (whole[after[-1]] - (hi if direction < 0 else lo)) * -direction > 0 and not (lo <= whole[after[-1]] <= hi)
        verdict, rule = "not", "Not working: the latest period is " + ("past the normal range in the wrong direction." if wrong else "inside the normal range.")
    # step 5: confidence in words
    early = len(prior) >= 2 and moved(whole[prior[-1]], min(whole[p] for p in prior[:-1]), max(whole[p] for p in prior[:-1]))
    confidence = "not_sure" if verdict == "too_early" or early or any(n["cause"] for n in notes) else "fairly_sure"
    trace = lambda p: {"kind": "data", "ref": f"{table}#{p}"}  # noqa: E731
    return {"week_key": week_key(friday), "report_day": friday.isoformat(), "drafted_at": S.now_iso(), "state": "drafted",
            "measure": {"code": code, "name": hv["measure"].get("name"), "unit": base.get("unit") or tgt.get("unit"), "grain": grain},
            "before": {"value": before, "segments": bval if named else None, "unit": base.get("unit"), "periods": base.get("periods"),
                       "trace": {"kind": "hypothesis", "ref": base.get("trace")}} if before is not None else None,
            "now": {"value": now, "period": since[-1], "trace": trace(since[-1])} if since else None,
            "target": {"value": target, "unit": tgt.get("unit"), "by": tgt.get("by")} if target is not None else None,
            "series": [{"period": p, "value": whole[p], "change": None if before is None else round(whole[p] - before, 6)} for p in series],
            "start_period": next(iter(after), None), "periods_since_start": len(after),
            "normal_range": {"low": lo, "high": hi, "periods": prior} if prior else None,
            "notes": [{k: n[k] for k in ("text", "by", "trace", "at")} | {"cause": n["cause"]} for n in notes],
            "verdict": verdict, "rule": rule, "confidence": confidence, "changed_verdict": None, "confirmed_by": None, "confirmed_at": None}


# ---- the clock ------------------------------------------------------------------------------------------------------------
def _review_date(pv: dict) -> date | None:
    ds = pv.get("review_dates") or []
    return _day(ds[-1]["date"]) if ds and ds[-1].get("date") else None


def _receipts(plane, pv: dict, hv: dict, kind: str) -> None:
    """Named voices in the evidence and the person who picked the opportunity up. Anonymous voices get no line (spec 58 rules)."""
    to = [e.get("by") for e in hv.get("evidence") or [] if e.get("record_kind") == "voice" and e.get("by")]
    to += [(hv.get("picked_up") or {}).get("by")] if isinstance(hv.get("picked_up"), dict) else []
    have = {(x["to"], x["kind"]) for x in pv["receipts"]}
    for acct in dict.fromkeys(a for a in to if isinstance(a, str) and a):
        if (acct, kind) not in have:
            pv["receipts"].append({"id": f"r{len(pv['receipts']) + 1}", "to": acct, "kind": kind, "at": S.now_iso(), "seen_at": None})


def _go(plane, pv: dict, hv: dict, at: str, from_: str, ref: str | None) -> None:
    pv.update(state="proving", start={"at": at, "from": from_, "ref": ref, "changed": None})
    _receipts(plane, pv, hv, "started")
    _event(plane, pv["intent_id"], "proving_started", "north", {"from": from_, "by_clock": True})


def tick(plane, iid: str, now: datetime | None = None) -> dict | None:
    """Release check, review date, this week's draft. Returns the fresh proving record or None."""
    now = now or datetime.now(timezone.utc)
    with S.locked(plane):
        pv = read_proving(plane, iid)
        if not pv or pv["state"] in ENDED:
            return pv
        rec = S.read_intent(plane, iid)
        h = rec and _hyp(plane, rec)
        if not h:
            return pv
        today, before = _today(plane, now), copy.deepcopy(pv)
        if pv["state"] == "waiting":
            rel = _release(plane)
            if rel.get("state") == "signed" and pv["measure"]["code"] in (rel.get("released") or []):
                _go(plane, pv, h[1], rel["at"], "release", "build/prove.json#release")
        if pv["state"] == "proving" and (rd := _review_date(pv)) and today >= rd:
            pv["state"] = "reviewing"
        if pv["state"] in ("proving", "reviewing") and pv.get("start"):
            friday = report_day(today, rules(plane)["report_day"])
            wk = week_key(friday)
            if friday >= _day(pv["start"]["at"]) and wk not in pv["reports"]:
                rep = draft(plane, pv, h[1], friday, rules(plane))
                prev = read_report(plane, iid, pv["reports"][-1]) if pv["reports"] else None
                if prev and rep["now"] and prev.get("now") and rep["now"]["period"] == prev["now"]["period"] and not any(n["by"] != "North" for n in prev.get("notes") or []):
                    rep["state"] = "no_change"  # C16: one line, no Pulse line to anyone
                write_json_atomic(_rfile(plane, iid, wk), rep)
                pv["reports"].append(wk)
                _event(plane, iid, "report_drafted", "north", {"week_key": wk, "verdict": rep["verdict"], "state": rep["state"]}, "draft")
        if pv != before:
            _write(plane, pv)
        return pv


def begin(plane, rec: dict, *, at: str | None = None, from_: str | None = None, ref: str | None = None) -> dict | None:
    """Create proving.json for an Initiative with a hypothesis (spec 58 states, first row). A cancelled Initiative, or one with no
    hypothesis, gets none. `at`/`from_` force the start (the seed); otherwise build needed "no" starts at closure, a signed release
    that carries the measure starts at the release, else it waits."""
    h = _hyp(plane, rec) if rec.get("type") == "initiative" and rec.get("state") != "cancelled" else None
    if not h:
        return None
    with S.locked(plane):
        if (pv := read_proving(plane, rec["id"])) is not None:
            return pv
        hid, hv = h
        pv = {"intent_id": rec["id"], "state": "waiting", "hypothesis_ref": {"id": hid, "version": hv.get("v")},
              "measure": {"code": hv["measure"]["id"], "name": hv["measure"].get("name"), "unit": (hv.get("baseline") or {}).get("unit"),
                          "grain": None},
              "start": None, "review_dates": [{"date": hv.get("review_date"), "by": "hypothesis", "reason": None}] if hv.get("review_date") else [],
              "reports": [], "review": None, "returned_to": None, "receipts": []}
        no_build = rec.get("build_needed") is False or (rec.get("outcome") or {}).get("build_needed") == "no"
        rel = _release(plane)
        if at:
            _go(plane, pv, hv, at, from_ or "closure", ref)
        elif no_build and (rec.get("closure") or {}).get("closed_at"):
            _go(plane, pv, hv, rec["closure"]["closed_at"], "closure", f"intents/{rec['id']}/intent.json#closure")
        elif rel.get("state") == "signed" and pv["measure"]["code"] in (rel.get("released") or []):
            _go(plane, pv, hv, rel["at"], "release", "build/prove.json#release")
        _write(plane, pv)
        return pv


def seed(plane, now: datetime | None = None) -> list[dict]:
    """Start Proving for every Initiative a seeded hypothesis was carried into, from the day its change went live (the running stage's
    start, `time_box.starts`), then run the clock once. Idempotent."""
    out = []
    for f in sorted(plane.path("intents", "hypotheses").glob("hyp-ini-*.json")):
        doc = read_json_strict(f, dict) or {}
        for c in doc.get("carried_into") or []:
            try:
                rec = S.read_intent(plane, c.get("intent"))
            except S.Unreadable:
                rec = None
            if rec and (starts := (rec.get("time_box") or {}).get("starts")):
                begin(plane, rec, at=str(starts), from_="go_live", ref=f"intents/{rec['id']}/intent.json#time_box.starts")
                out.append(tick(plane, rec["id"], now))
    return out


# ---- who is who ---------------------------------------------------------------------------------------------------------------
def _slot(rec: dict, key: str, v) -> bool:
    return S._named((rec.get("people") or {}).get(key), v)


def _who(v, role: str) -> dict:
    return {"account": v.account_id, "name": v.name, "role": role}


def _load(request: Request, iid: str, *, content: bool = True):
    plane, v = _plane(request), _viewer(request)
    rec = S.read_intent(plane, iid)
    tier = rec and S.tier_of(rec, v, S.areas_of(plane, v))
    if not tier or rec["type"] != "initiative":
        raise Refuse(404, NOT_FOUND)
    if content and tier != "content":
        raise Refuse(403, "You can see this Initiative but not its proving.")
    return plane, v, rec, tier


def _run(fn):
    try:
        return fn()
    except Refuse as e:
        return JSONResponse({"message": e.message, **({"error": "not_allowed"} if e.status == 403 else {})}, status_code=e.status)
    except S.Unreadable:
        return JSONResponse({"message": S.UNREADABLE}, status_code=500)
    except S.VersionConflict:
        return JSONResponse({"message": S.CONFLICT}, status_code=409)
    except PermissionError:
        return JSONResponse({"message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


def _text(body: dict, key: str, what: str, need: bool = True) -> str | None:
    t = body.get(key)
    t = t.strip() if isinstance(t, str) else ""
    if need and not t:
        raise Refuse(422, f"Write {what}.")
    if len(t) > TEXT_MAX:
        raise Refuse(422, f"Keep {what} under {TEXT_MAX} characters.")
    return t or None



# ---- views (shapes agreed with the Proving screens) ------------------------------------------------------------------------
_FIGURES = ("before", "now", "target", "series", "normal_range", "notes", "rule")


def _word(rep: dict) -> str:
    return WORDS[(rep.get("changed_verdict") or {}).get("to") or rep["verdict"]]


def _missing(rep: dict) -> list[str]:
    return [m for k, m in (("before", "the hypothesis carries no baseline"), ("now", f"no period of {rep['measure'].get('name')} has landed since the start"),
                           ("target", "the hypothesis carries no target")) if not rep.get(k)]


def _cut_report(rep: dict, figs: bool) -> dict:
    out = {k: v for k, v in rep.items() if figs or k not in _FIGURES}
    out["notes"] = [{k: v for k, v in n.items() if k != "cause"} for n in rep.get("notes") or []] if figs else None
    out.update(verdict_word=_word(rep), confidence_word=SURE.get(rep.get("confidence")), figures=figs, missing=_missing(rep))
    return out


def _may_note(rec: dict, pv: dict, v) -> bool:
    return (_slot(rec, "organiser", v) or _slot(rec, "sponsor", v) or "analyst" in v.roles) and pv["state"] not in ENDED


def report_out(plane, rec: dict, pv: dict, rep: dict, v) -> dict:
    out = _cut_report(rep, _figures_ok(plane, pv["measure"]["code"], v))
    out["can"] = {"confirm": _slot(rec, "organiser", v) and rep["state"] == "drafted", "add_note": _may_note(rec, pv, v)}
    return out


def _review(reports: list[dict], rec: dict, pv: dict) -> dict:
    """North's review summary and proposed outcome (agent behaviour step 7), with what the organiser sent."""
    conf = [r for r in reports if r["state"] == "confirmed"]
    rv = pv.get("review") or {}
    out = {"verdicts": [_word(r) for r in conf], "proposed": None, "learning": rv.get("learning"), "sent": bool(rv.get("sent_at")),
           "summary": None, **{k: rv.get(k) for k in ("action", "by", "reason", "review_date", "returned", "confirmed_by", "confirmed_at")}}
    if not conf:
        return out
    last = conf[-1]
    word = (last.get("changed_verdict") or {}).get("to") or last["verdict"]
    out["proposed"] = {"working": "keep", "too_early": "more_time"}.get(word, "send_back")
    name = last["measure"].get("name") or "its measure"
    out["summary"] = f"{len(conf)} confirmed report{'s' if len(conf) != 1 else ''}: {', '.join(out['verdicts'])}. North proposes: " + {
        "keep": "it works, keep it running.", "more_time": "give it more time.", "send_back": "send it back to the radar."}[out["proposed"]]
    if out["proposed"] == "send_back" and not out["learning"]:
        seg = next((n["text"] for n in last.get("notes") or [] if not n.get("cause") and n["by"] == "North"), None)
        out["learning"] = (f"{rec.get('title')} moved {name} only part of the way to its target." if word == "partly"
                           else f"{rec.get('title')} did not move {name} out of its normal range.") + (f" {seg}" if seg else " North found no group or period that moved differently.")
    return out


def view(plane, rec: dict, pv: dict | None, v, tier: str) -> dict:
    p = rec.get("people") or {}
    out = {"intent_id": rec["id"], "title": rec.get("title"), "state": pv["state"] if pv else None, "chip": CHIP[pv["state"]] if pv else None}
    if pv is None:
        return out
    reports = [r for wk in pv["reports"] if (r := read_report(plane, rec["id"], wk))]
    confirmed = [r for r in reports if r["state"] == "confirmed"]
    out.update(proving_since=pv["start"]["at"][:10] if pv.get("start") else None, verdict_word=_word(confirmed[-1]) if confirmed else None)
    if tier != "content":
        return out  # area members: the chip and the confirmed verdict word
    org, spon = _slot(rec, "organiser", v), _slot(rec, "sponsor", v)
    figs = _figures_ok(plane, pv["measure"]["code"], v)
    h = _hyp(plane, rec)
    hv = h[1] if h else {}
    tgt = hv.get("target") or {}
    r = rules(plane)
    rv = pv.get("review") or {}
    start = pv.get("start")
    out.update({
        "organiser": (p.get("organiser") or {}).get("name"), "sponsor": (p.get("sponsor") or {}).get("name"),
        "review_date": str(_review_date(pv) or "") or None, "review_dates": pv.get("review_dates"), "measure": pv["measure"], "figures": figs,
        "hypothesis": {"id": pv["hypothesis_ref"]["id"], "version": pv["hypothesis_ref"]["version"], "belief": hv.get("belief"), "lens": hv.get("lens"),
                       "measure": hv.get("measure"), "target": {k: tgt.get(k) for k in ("value", "unit")} if figs and tgt else None,
                       "target_by": tgt.get("by"), "frozen_by": hv.get("frozen_by"),
                       "href": f"/centre/intent/backlog?hypothesis={pv['hypothesis_ref']['id']}"} if hv else None,
        "start": {**start, "who": _start_who(plane, start)} if start else None,
        "latest": report_out(plane, rec, pv, reports[-1], v) if reports else None,
        "reports": [{"week_key": x["week_key"], "verdict_word": _word(x), "state": x["state"]} for x in reports],
        "rules": {"proving_min_periods": r["proving_min_periods"] or MIN_DEFAULT["monthly"], "counter_periods": _effective(r, "monthly")[1],
                  "report_day": r["report_day"], "set": {"proving_min_periods": r["proving_min_periods"] is not None, "counter_periods": r["counter_periods"] is not None}},
        "review": _review(reports, rec, pv) if pv["state"] in ("reviewing", *ENDED) or rv else None, "returned_to": pv.get("returned_to"),
        "can": {"change_start": org and pv["state"] in ("waiting", "proving") and not confirmed,
                "review": org and pv["state"] in ("proving", "reviewing") and not rv.get("sent_at"),
                "confirm_review": spon and bool(rv.get("sent_at") and not rv.get("confirmed_at")), "add_note": _may_note(rec, pv, v)}})
    out["receipts"] = {"named": len({x["to"] for x in pv["receipts"]}), "anonymous": 0, "seen": sum(1 for x in pv["receipts"] if x.get("seen_at"))} if org or spon else None
    return out


def _start_who(plane, start: dict) -> str | None:
    """Who the start rests on: the release signer, or the person who changed the date."""
    if (start.get("changed") or {}).get("by"):
        return start["changed"]["by"]
    return _release(plane).get("by") if start.get("from") == "release" else None


# ---- routes ------------------------------------------------------------------------------------------------------------------
@router.get("/api/intents/{intent_id}/proving")
def get_proving(intent_id: str, request: Request):
    def work():
        plane, v, rec, tier = _load(request, intent_id, content=False)
        if rec["state"] == "closed" and read_proving(plane, intent_id) is None:
            begin(plane, rec)  # a closure written before this file existed, or by a module that does not call begin
        return view(plane, rec, tick(plane, intent_id), v, tier)
    return _run(work)


@router.get("/api/intents/{intent_id}/proving/reports/{week_key}")
def get_report(intent_id: str, week_key: str, request: Request):
    def work():
        plane, v, rec, _ = _load(request, intent_id)
        pv = tick(plane, intent_id)
        rep = pv and week_key in pv["reports"] and read_report(plane, intent_id, week_key)
        if not rep:
            raise Refuse(404, NOT_FOUND)
        out = report_out(plane, rec, pv, rep, v)
        out["earlier"] = [w for w in pv["reports"] if w != week_key][::-1]
        return out
    return _run(work)


def _need(plane, iid: str, states=LIVE) -> dict:
    pv = read_proving(plane, iid)
    if not pv:
        raise Refuse(404, "This Initiative is not being proved.")
    if pv["state"] not in states:
        raise Refuse(409, "Proving has ended for this Initiative.")
    return pv


@router.post("/api/intents/{intent_id}/proving/reports/{week_key}/confirm")
def post_confirm(intent_id: str, week_key: str, request: Request, body: dict = Body(default={})):
    def work():
        plane, v, rec, _ = _load(request, intent_id)
        if not _slot(rec, "organiser", v):
            raise Refuse(403, "Only the organiser confirms the weekly report.")
        b = body if isinstance(body, dict) else {}
        ch = {"to": b["verdict"]} if b.get("verdict") is not None else None
        if ch and ch["to"] not in WORDS:
            raise Refuse(422, "Pick one of the four verdicts.")
        reason = _text(b, "reason", "why you changed the verdict") if ch else None
        with S.locked(plane):
            _need(plane, intent_id)
            rep = read_report(plane, intent_id, week_key)
            if not rep:
                raise Refuse(404, NOT_FOUND)
            if rep["state"] != "drafted":
                raise Refuse(409, "This report is already confirmed." if rep["state"] == "confirmed" else "Nothing to confirm this week.")
            if ch and ch["to"] != rep["verdict"]:
                rep["changed_verdict"] = {"from": rep["verdict"], "to": ch["to"], "reason": reason}
                _event(plane, intent_id, "verdict_changed", _who(v, "organiser"), {"week_key": week_key, "from": rep["verdict"], "to": ch["to"]})
            rep.update(state="confirmed", confirmed_by=v.name, confirmed_at=S.now_iso())
            write_json_atomic(_rfile(plane, intent_id, week_key), rep)
        _event(plane, intent_id, "report_confirmed", _who(v, "organiser"), {"week_key": week_key, "verdict": (rep["changed_verdict"] or {}).get("to") or rep["verdict"]})
        return report_out(plane, rec, read_proving(plane, intent_id), rep, v)
    return _run(work)


@router.post("/api/intents/{intent_id}/proving/reports/{week_key}/notes")
def post_note(intent_id: str, week_key: str, request: Request, body: dict = Body(default={})):
    def work():
        plane, v, rec, _ = _load(request, intent_id)
        role = "organiser" if _slot(rec, "organiser", v) else "sponsor" if _slot(rec, "sponsor", v) else "analyst" if "analyst" in v.roles else None
        if not role:
            raise Refuse(403, "The organiser, the sponsor and the analyst add notes.")
        b = body if isinstance(body, dict) else {}
        text = _text(b, "text", "the note")
        trace = _text(b, "trace", "the record the note rests on, or the words No record")
        with S.locked(plane):
            _need(plane, intent_id)
            rep = read_report(plane, intent_id, week_key)
            if not rep:
                raise Refuse(404, NOT_FOUND)
            rep["notes"].append({"text": text, "by": v.name, "trace": None if trace.lower() == "no record" else {"kind": "record", "ref": trace},
                                 "at": S.now_iso(), "cause": True})
            write_json_atomic(_rfile(plane, intent_id, week_key), rep)
        _event(plane, intent_id, "note_added", _who(v, role), {"n": len(rep["notes"])})
        return report_out(plane, rec, read_proving(plane, intent_id), rep, v)
    return _run(work)


@router.post("/api/intents/{intent_id}/proving/start")
def post_start(intent_id: str, request: Request, body: dict = Body(default={})):
    """Start Proving on a closed Initiative that has none yet, or change the start date before the first confirm (C14)."""
    def work():
        plane, v, rec, tier = _load(request, intent_id)
        if not _slot(rec, "organiser", v):
            raise Refuse(403, "Only the organiser changes the start date.")
        b = body if isinstance(body, dict) else {}
        if read_proving(plane, intent_id) is None:
            if rec["state"] != "closed" or not begin(plane, rec):
                raise Refuse(409, "Proving starts when a closed Initiative carries a hypothesis.")
            return view(plane, rec, tick(plane, intent_id), v, tier)
        try:
            at = date.fromisoformat(str(b.get("at") or ""))
        except ValueError:
            raise Refuse(422, "Pick the date the change went live.") from None
        reason = _text(b, "reason", "why the start date changes")
        with S.locked(plane):
            pv = _need(plane, intent_id, ("waiting", "proving"))
            if at > _today(plane, datetime.now(timezone.utc)):
                raise Refuse(422, "The start date cannot be in the future.")
            if any((r := read_report(plane, intent_id, wk)) and r["state"] == "confirmed" for wk in pv["reports"]):
                raise Refuse(409, "A report is already confirmed, so the start date stays.")
            for wk in pv["reports"]:  # North redraws from the new date
                _rfile(plane, intent_id, wk).unlink(missing_ok=True)
            pv.update(state="proving", reports=[], start={"at": at.isoformat(), "from": (pv.get("start") or {}).get("from") or "closure",
                                                         "ref": (pv.get("start") or {}).get("ref"), "changed": {"by": v.name, "at": S.now_iso(), "reason": reason}})
            _write(plane, pv)
        _event(plane, intent_id, "proving_start_changed", _who(v, "organiser"), {})
        return view(plane, rec, tick(plane, intent_id), v, tier)
    return _run(work)


def _settle(plane, rec: dict, pv: dict, who: dict) -> None:
    """The sponsor confirmed (or the organiser alone, with no sponsor): write the outcome."""
    rv, iid, by = pv["review"], rec["id"], who["name"]
    rv.update(confirmed_by=by, confirmed_at=S.now_iso())
    h = _hyp(plane, rec)
    hv = h[1] if h else {}
    last = next((r for wk in reversed(pv["reports"]) if (r := read_report(plane, iid, wk)) and r["state"] == "confirmed"), None)
    word = ((last or {}).get("changed_verdict") or {}).get("to") or (last or {}).get("verdict")
    if rv["action"] == "more_time":
        pv["review_dates"].append({"date": rv["review_date"], "by": by, "reason": rv["reason"]})
        pv.update(state="proving", review=None)
        return
    pv["state"] = {"keep": "proved", "send_back": "returned", "stop": "stopped"}[rv["action"]]
    answer = "yes" if rv["action"] == "keep" else "partly" if rv["action"] == "send_back" and word == "partly" else "no"

    def used(r):
        u = r.get("outcome_used") if isinstance(r.get("outcome_used"), dict) else {"ask_at": None, "asked_at": None, "deferred": 0, "dropped_at": None}
        r["outcome_used"] = {**u, "answer": answer, "note": "From the Proving review", "answered_by": by, "answered_at": S.now_iso()}
    S.update_intent(plane, iid, S.read_intent(plane, iid)["version"], used)
    if rv["action"] == "send_back" and h:
        pv["returned_to"] = _send_back(plane, rec, h[0], hv, rv["learning"], by)
        _event(plane, iid, "sent_back", who, {"opportunity": pv["returned_to"]})
    _receipts(plane, pv, hv, "ended")
    _remember(plane, rec, rv["action"])


def _send_back(plane, rec: dict, hid: str, hv: dict, learning: str, by: str) -> str:
    """A 57 opportunity, under review, from this Initiative, with a new hypothesis version carrying the learning."""
    from sh_platform.intents import opportunities as O
    opp = O._create(plane, {"title": f"What we learnt from {rec.get('title')}"[:160], "areas": list(rec.get("areas") or []),
                            "touches": {"measures": [hv["measure"]["id"]], "processes": [], "sources": []},
                            "pattern": {"text": learning, "periods": [], "numbers": []}}, by, {"text": learning, "kind": "supports"})
    path = plane.path("intents", "hypotheses", f"{hid}.json")
    with lock_for(path):
        doc = read_json_strict(path, dict) or {}
        n = 1 + max((x.get("v") or 0 for x in doc.get("versions") or []), default=0)
        doc.setdefault("versions", []).append({**hv, "v": n, "at": S.now_iso(), "by": by, "learning": learning, "frozen_by": None})
        doc["state"] = "under_review"
        write_json_atomic(path, doc)
    opp.update(origin={"kind": "initiative", "ref": rec["id"]}, hypothesis_ref={"id": hid, "version": n})
    O._save(plane, opp)
    return opp["id"]


def _remember(plane, rec: dict, action: str) -> None:
    """One company memory line (C19): title and outcome word, no figure, no name."""
    word = {"keep": "proved and kept running", "send_back": "sent back to the radar", "stop": "stopped"}[action]
    try:
        from sh_platform import memory
        memory.remember(plane, "north", None, [{"kind": "fact", "text": f"{rec.get('title')} was {word} at its review in {datetime.now(timezone.utc):%B}.",
                                                 "conversation": f"proving:{rec['id']}", "at": S.now_iso()}])
    except Exception as e:  # noqa: BLE001  memory never blocks the outcome
        log.warning("proving: memory line skipped (%s)", type(e).__name__)


@router.post("/api/intents/{intent_id}/proving/review")
def post_review(intent_id: str, request: Request, body: dict = Body(default={})):
    def work():
        plane, v, rec, tier = _load(request, intent_id)
        if not _slot(rec, "organiser", v):
            raise Refuse(403, "Only the organiser chooses the review outcome.")
        b = body if isinstance(body, dict) else {}
        action = b.get("action")
        if action not in ACTIONS:
            raise Refuse(422, "Choose one of the four outcomes.")
        reason = _text(b, "reason", "the reason", need=action in ("more_time", "stop"))
        learning = _text(b, "learning", "what was learnt", need=action == "send_back")
        new_date = None
        if action == "more_time":
            try:
                new_date = date.fromisoformat(str(b.get("date") or b.get("review_date") or ""))
            except ValueError:
                raise Refuse(422, "Pick the new review date.") from None
            if new_date <= _today(plane, datetime.now(timezone.utc)):
                raise Refuse(422, "The new review date must be after today.")
        with S.locked(plane):
            pv = _need(plane, intent_id, ("proving", "reviewing"))
            if pv["state"] == "proving" and action != "stop":
                raise Refuse(409, "The review opens on the review date.")
            if (pv.get("review") or {}).get("sent_at"):
                raise Refuse(409, "The review is already with the sponsor.")
            pv["review"] = {"action": action, "by": v.name, "at": S.now_iso(), "reason": reason, "learning": learning,
                            "review_date": new_date.isoformat() if new_date else None, "sent_at": S.now_iso(), "returned": None,
                            "confirmed_by": None, "confirmed_at": None}
            _event(plane, intent_id, "review_sent", _who(v, "organiser"), {"action": action})
            if not (rec.get("people") or {}).get("sponsor"):
                _settle(plane, rec, pv, _who(v, "organiser"))  # no sponsor: the organiser confirms alone
                _event(plane, intent_id, "review_confirmed", _who(v, "organiser"), {"action": action})
            _write(plane, pv)
        return view(plane, S.read_intent(plane, intent_id), pv, v, tier)
    return _run(work)


@router.post("/api/intents/{intent_id}/proving/review/confirm")
def post_review_confirm(intent_id: str, request: Request, body: dict = Body(default={})):
    """The sponsor confirms the outcome ({}), or sends it back to the organiser ({"return": true, "reason"})."""
    def work():
        plane, v, rec, tier = _load(request, intent_id)
        if not _slot(rec, "sponsor", v):
            raise Refuse(403, "Only the sponsor confirms the outcome.")
        b = body if isinstance(body, dict) else {}
        back = b.get("return") is True
        reason = _text(b, "reason", "why it goes back") if back else None
        with S.locked(plane):
            pv = _need(plane, intent_id, ("proving", "reviewing"))
            rv = pv.get("review")
            if not (rv and rv.get("sent_at")) or rv.get("confirmed_at"):
                raise Refuse(409, "There is no review waiting for you.")
            if back:
                rv.update(sent_at=None, returned={"by": v.name, "at": S.now_iso(), "reason": reason})
                _event(plane, intent_id, "review_returned", _who(v, "sponsor"), {})
            else:
                action = rv["action"]
                _settle(plane, rec, pv, _who(v, "sponsor"))
                _event(plane, intent_id, "review_confirmed", _who(v, "sponsor"), {"action": action})
            _write(plane, pv)
        return view(plane, S.read_intent(plane, intent_id), pv, v, tier)
    return _run(work)


@router.post("/api/intents/{intent_id}/proving/receipts/{receipt_id}/seen")
def post_receipt_seen(intent_id: str, receipt_id: str, request: Request):
    def work():
        plane, v = _plane(request), _viewer(request)
        with S.locked(plane):
            pv = read_proving(plane, intent_id)
            r = pv and next((x for x in pv["receipts"] if x["id"] == receipt_id and x["to"] == v.account_id), None)
            if not r:
                raise Refuse(404, NOT_FOUND)
            r["seen_at"] = r.get("seen_at") or S.now_iso()
            _write(plane, pv)
        return {"id": receipt_id, "seen_at": r["seen_at"]}
    return _run(work)


# ---- Pulse (spec 58, Nira's lines). Shared files needed: one reader in pulse/intent_lines.others() --------------------------
def _line(iid: str, what: str, kind: str, title: str, detail: str, href: str, action: str, at) -> dict:
    return {"id": f"proving:{iid}:{what}", "kind": kind, "title": title, "detail": detail, "href": href, "action": action,
            "minutes": MINUTES[kind], "due": None, "source": {"record": f"intents/{iid}/proving.json", "at": str(at) if at else None}}


def pulse_lines(plane, v, now: datetime | None = None) -> dict[str, list[dict]]:
    """{"decide": [...], "watch": [...]} for this person. Only confirmed verdicts reach the sponsor; figures only past the access list."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    out: dict[str, list[dict]] = {"decide": [], "watch": []}
    for f in sorted(plane.path("intents").glob("*/proving.json")):
        iid = f.parent.name
        try:
            pv = tick(plane, iid, now)
            rec = S.read_intent(plane, iid)
        except (S.Unreadable, OSError, ValueError):
            continue
        if not pv or not rec:
            continue
        t, base = rec.get("title") or "your Initiative", f"/centre/intent/{iid}"
        org, spon = _slot(rec, "organiser", v), _slot(rec, "sponsor", v)
        reps = [r for wk in pv["reports"] if (r := read_report(plane, iid, wk))]
        rv = pv.get("review") or {}
        if org and reps and reps[-1]["state"] == "drafted":
            out["decide"].append(_line(iid, "report", "decision", f"Check this week's uplift report on {t}", "North drafted this week's uplift report.",
                                       f"{base}?week={reps[-1]['week_key']}", "Check it", reps[-1]["drafted_at"]))
        if org and pv["state"] == "reviewing" and not rv.get("sent_at"):
            detail = f"{rv['returned']['by']} sent the review back: {rv['returned']['reason']}" if rv.get("returned") else "North has proposed an outcome."
            out["decide"].append(_line(iid, "review", "decision", f"Review {t}: its review date has come", detail, f"{base}?focus=review", "Open the review", None))
        if spon and rv.get("sent_at") and not rv.get("confirmed_at"):
            out["decide"].append(_line(iid, "confirm", "decision", f"Confirm the outcome of {t}", f"{rv.get('by')} sent the review.", f"{base}?focus=review",
                                       "Confirm the outcome", rv["sent_at"]))
        conf = [r for r in reps if r["state"] == "confirmed"]
        if spon and conf and str(conf[-1]["confirmed_at"]) >= cutoff:
            word = WORDS[(conf[-1].get("changed_verdict") or {}).get("to") or conf[-1]["verdict"]]
            out["watch"].append(_line(iid, "uplift", "outcome", f"Uplift on {t}: {word}", f"Confirmed by {conf[-1]['confirmed_by']}.",
                                      f"{base}?week={conf[-1]['week_key']}", "Read it", conf[-1]["confirmed_at"]))
        for r in pv["receipts"]:
            if r["to"] == v.account_id and not r.get("seen_at") and str(r["at"]) >= cutoff:
                if r["kind"] == "started":
                    title = f"Your item became {t}. It went live on {(pv.get('start') or {}).get('at', '')[:10]}."
                else:
                    last = conf[-1] if conf else None
                    word = CHIP[pv["state"]]
                    moved = last and last.get("now") and last.get("before")
                    if moved and _figures_ok(plane, pv["measure"]["code"], v):
                        word += f". {pv['measure'].get('name')} moved from {_fmt(last['before']['value'])} to {_fmt(last['now']['value'])}."
                    elif moved:
                        hit = last["verdict"] in ("working", "partly")
                        word += f". {pv['measure'].get('name')} " + ("moved the way the Initiative hoped." if hit else "did not move.")
                    title = f"{t} was reviewed: {word}"
                out["watch"].append(_line(iid, f"receipt:{r['id']}", "outcome", title, "", f"{base}?focus=proving", "Open it", r["at"]))
    return out


def install(app) -> None:
    """Called once from sh_platform/app.py, before ic_records (its {intent_id} lines must not catch these)."""
    app.include_router(router)


if __name__ == "__main__":  # python -m sh_platform.intents.proving seed <data_root> <company>
    from sh_platform.plane import PlaneStore
    if len(sys.argv) == 4 and sys.argv[1] == "seed":
        for pv in seed(PlaneStore(Path(sys.argv[2])).plane_for(sys.argv[3])):
            print(pv and (pv["intent_id"], pv["state"], pv["reports"][-1:] if pv["reports"] else None))
    else:
        print(__doc__)
