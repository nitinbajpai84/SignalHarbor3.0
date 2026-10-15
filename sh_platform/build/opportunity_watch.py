"""The Watcher's pattern step for data-backed opportunities (spec 56). Reads runs.json, alerts.json, the pipelines, the Weekly check-in
week files, the read-only warehouse marts (feed values by period) and nothing else. It drafts; it never opens an intent and never states a
number it cannot trace.

How many late arrivals, drifting periods or check-in weeks make a pattern is NOT decided here (spec 56, open question 1): the three
thresholds are company settings (`opportunity` in the admin defaults, file 48). A threshold that is not set means that detector
stays silent and the screen says "Not available yet".
"""
import importlib
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from sh_platform import warehouse
from sh_platform.consume import range as rng

log = logging.getLogger(__name__)
KEYS = ("late_arrivals", "drift_periods", "checkin_weeks")
NOT_SET = "Not available yet. Set the thresholds in the admin defaults."
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


SETTING = {"late_arrivals": "late_same_weekday", "drift_periods": "drift_periods", "checkin_weeks": "checkin_items_same_step"}  # admin.OPPORTUNITY_KEYS


def thresholds(plane) -> dict[str, int | None]:
    """The three thresholds from the company settings (admin.read_settings()["opportunity"]), None where unset or the settings are not there yet.
    ponytail: the admin's `window_days` is not applied; every stored run and week counts. Apply it here if a window is ruled."""
    try:
        read = getattr(importlib.import_module("sh_platform.intents.admin"), "read_settings", None)
        got = (read(plane) if read else None) or {}
        opp = (got.get("opportunity") or {}) if isinstance(got, dict) else {}
        raw = {k: opp.get(v) for k, v in SETTING.items()}
    except (ImportError, OSError, ValueError, TypeError, KeyError) as e:
        log.info("no settings for the Watcher: %s", type(e).__name__)
        raw = {}
    return {k: v if isinstance(v := raw.get(k), int) and not isinstance(v, bool) and v > 0 else None for k in KEYS}


def missing(t: dict) -> list[str]:
    return [k for k in KEYS if t.get(k) is None]


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


def _plain(s: str) -> str:
    t = str(s).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def _pipes(plane) -> list[dict]:
    return [p for f in sorted(plane.path("build", "pipelines").glob("*.json")) if isinstance(p := _load(f, None), dict) and p.get("source")]


def _measures(pipe: dict) -> list[str]:
    return sorted({m.group(1).upper() for mart in pipe.get("marts") or [] if (m := re.fullmatch(r"(?:gold\.)?(k\d+)", str(mart).lower()))})


def _late(plane, pipes: list[dict], today: date, need: int) -> list[dict]:
    runs = _load(plane.path("warehouse", "runs.json"), {}).get("runs") or []
    alerts = _load(plane.path("build", "alerts.json"), {}).get("alerts") or []
    by_pipe = {p["source"]: p for p in pipes}
    seen: dict[tuple, list[date]] = {}
    for r in runs:
        d = _day(r.get("started"))
        if r.get("source") in by_pipe and d and d <= today and (r.get("status") == "late" or r.get("on_time") is False):
            seen.setdefault((r["source"], d.weekday()), []).append(d)
    out = []
    for (src, wd), days in sorted(seen.items()):
        days = sorted(set(days))
        if len(days) < need:
            continue
        last = days[-1].isoformat()
        nums = [{"label": f"Late {DAYS[wd]} arrivals", "value": len(days), "unit": "runs",
                 "trace": {"kind": "run", "ref": f"warehouse/runs.json#{src}:{DAYS[wd]}", "at": last}}]
        a = next((a for a in alerts if a.get("source") == src and a.get("state") != "closed" and a.get("kind") in ("late", "missing")), None)
        if a:
            nums.append({"label": "Open alert", "value": 1, "unit": "alert", "trace": {"kind": "alert", "ref": a["id"], "at": a.get("opened") or last}})
        out.append({"title": f"{_plain(src)} arrives late on {DAYS[wd]}s",
                    "areas": [], "touches": {"measures": _measures(by_pipe[src]), "processes": [], "sources": [src]},
                    "pattern": {"text": f"The {_plain(src).lower()} file arrived late on {len(days)} {DAYS[wd]}s.", "periods": [d.isoformat() for d in days], "numbers": nums}})
    return out


def _drift(plane, pipes: list[dict], need: int) -> list[dict]:
    try:
        con = warehouse.open_readonly(plane)
    except duckdb.Error as e:
        log.info("no read-only warehouse copy: %s", type(e).__name__)
        return []
    out, done = [], set()
    try:
        for p in pipes:
            for mart in p.get("marts") or []:
                schema, _, name = str(mart).partition(".")
                if schema != "gold" or not name.isidentifier() or mart in done:
                    continue
                done.add(mart)
                t = rng.trend(con, name)[-(need + 1):]
                if len(t) < need + 1:
                    continue
                steps = [b["value"] - a["value"] for a, b in zip(t, t[1:])]
                if not (all(s > 0 for s in steps) or all(s < 0 for s in steps)):
                    continue
                way = "up" if steps[0] > 0 else "down"
                ms = _measures({"marts": [mart]})
                out.append({"title": f"{_plain(name)} keeps moving {way}", "areas": [], "touches": {"measures": ms, "processes": [], "sources": [p["source"]]},
                            "pattern": {"text": f"{_plain(name)} moved {way} in each of the last {need} periods.", "periods": [x["period"] for x in t],
                                        "numbers": [{"label": "Periods moving the same way", "value": need, "unit": "periods",
                                                     "trace": {"kind": "feed", "ref": mart, "at": t[-1]["period"]}}]}})
    finally:
        con.close()
    return out


def _checkin(plane, need: int) -> list[dict]:
    """Items of kind `broke` that name the same step (the same `ref`, else the same words) in several different weeks. Anonymous items are never read."""
    groups: dict[tuple, dict] = {}
    for f in sorted(plane.path("intents").glob("*/intent.json")):
        rec = _load(f, None)
        if not isinstance(rec, dict) or rec.get("type") != "pulse" or rec.get("state") not in ("open", "in_session", "closing"):
            continue
        for wf in sorted(f.parent.glob("weeks/*.json")):
            wk = _load(wf, {})
            for it in wk.get("items") or []:
                step = str(it.get("ref") or " ".join(re.findall(r"[a-z0-9]+", str(it.get("text") or "").lower())))
                if it.get("kind") != "broke" or it.get("by") == "anonymous" or not step:
                    continue
                g = groups.setdefault((rec["id"], step), {"area": rec.get("areas") or [], "weeks": {}})
                g["weeks"].setdefault(str(wk.get("week_key") or wf.stem), it.get("id"))
    out = []
    for (iid, step), g in sorted(groups.items()):
        if len(g["weeks"]) < need:
            continue
        wk, item = sorted(g["weeks"].items())[-1]
        out.append({"title": "The same check-in step broke again and again", "areas": list(g["area"]), "touches": {"measures": [], "processes": [], "sources": []},
                    "pattern": {"text": f"Check-in items about the same step came up in {len(g['weeks'])} different weeks.", "periods": sorted(g["weeks"]),
                                "numbers": [{"label": "Weeks with an item on the same step", "value": len(g["weeks"]), "unit": "weeks",
                                             "trace": {"kind": "week_item", "ref": f"{iid}/weeks/{wk}#{item}"}}]}})
    return out


def detect(plane, today: date, t: dict | None = None) -> list[dict]:
    """Drafts (title, areas, touches, pattern) for every pattern the set thresholds find. A detector whose threshold is unset is skipped."""
    t = thresholds(plane) if t is None else t
    pipes = _pipes(plane)
    out = []
    if t.get("late_arrivals"):
        out += _late(plane, pipes, today, t["late_arrivals"])
    if t.get("drift_periods"):
        out += _drift(plane, pipes, t["drift_periods"])
    if t.get("checkin_weeks"):
        out += _checkin(plane, t["checkin_weeks"])
    return out


def same(draft: dict, rec: dict) -> bool:
    """True when a stored record is already this pattern. Runs and feeds match on the first number's trace; a check-in pattern matches on the same
    intent and a shared week. ponytail: two different steps in one series that share a week read as one pattern; key on the step if that bites."""
    a, b = draft["pattern"]["numbers"][0]["trace"], ((rec.get("pattern") or {}).get("numbers") or [{}])[0].get("trace") or {}
    if a["kind"] != b.get("kind"):
        return False
    if a["kind"] == "week_item":
        return a["ref"].split("/weeks/")[0] == str(b.get("ref")).split("/weeks/")[0] and bool(set(draft["pattern"]["periods"]) & set(rec["pattern"].get("periods") or []))
    return a["ref"] == b.get("ref")
