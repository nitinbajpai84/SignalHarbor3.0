"""P5 Go live, ops daily state and tickets.

Go live: the project owner (the raiser or the sponsor on the project record) presses Go live on the project page (`go_live`): the
project's `stage` becomes `live`, ops reads and comments on its artefacts, the run book is drafted (g2_runbook) and Pulse starts showing
the project's daily state. There is no hand-over and no acceptance.

Tickets: raised by ops (`raise_ticket`) or by the Watcher (`after_ops`, called from b5_ops.summary: a failed check, a late file or one
that has not arrived, on a live project, raises one per source per day), addressed to the project's builder. A ticket is a comment on
the build pack with kind ticket, through P1 (`p1_project.comment`, guarded); build/ops/tickets.json is the ops ledger of every ticket
(and, while P1 is absent, the only place a ticket lives).

Daily state: after each ops read, every live project's sources and their state for the day go to build/ops/daily.json
{date, projects: {pid: {state, sources: [{source_id, state, rows, last_run}]}}}; Pulse reads it through `daily(plane, pid)`."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
PID = re.compile(r"^prj-[0-9a-f]{8}$")
SOURCE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
WATCHED = {"late": "the file arrived late", "missing": "the file has not arrived", "failed": "today's run failed its checks"}
WORST = ["failed", "missing", "late", "on_time"]
BUILD_PACK = "build_pack"


class Refusal(ValueError):
    """A plain sentence for the person; the route turns it into 409."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path, kind=dict, default=None):
    try:
        data = read_json_strict(path, kind)
    except (OSError, ValueError) as e:
        log.warning("%s unreadable: %s", path.name, type(e).__name__)
        return default
    return default if data is None else data


def _p1():
    try:
        from sh_platform.v1 import p1_project
        return p1_project
    except ImportError:
        return None


def project(plane, pid: str) -> dict:
    if not isinstance(pid, str) or not PID.match(pid):
        raise LookupError("no such project")
    rec = _read(plane.path("projects", f"{pid}.json"))
    if not rec:
        raise LookupError("no such project")
    return rec


def projects(plane) -> list[dict]:
    d = plane.path("projects")
    return [r for f in sorted(d.glob("prj-*.json")) if (r := _read(f)) and r.get("id")] if d.is_dir() else []


def _set(plane, pid: str, **fields) -> dict:
    """Patch the project record: stage, and people names that are not set yet."""
    path = plane.path("projects", f"{pid}.json")
    with lock_for(path):
        rec = project(plane, pid)
        people = dict(rec.get("people") or {})
        for k, v in fields.pop("people", {}).items():
            people[k] = people.get(k) or v
        rec.update(fields, people=people)
        write_json_atomic(path, rec)
    try:
        from sh_platform.v1.m1_map import touch; touch(plane)
    except ImportError:
        pass
    return rec


def _say(plane, pid: str, line_ref: str, by: str, to: str, text: str, kind: str) -> str | None:
    """A build-pack comment through P1 (Pulse shows it to `to`); None while P1 is absent or the write fails (the ledger keeps the act)."""
    p1 = _p1()
    if p1 is None:
        return None
    try:
        c = p1.comment(plane, pid, BUILD_PACK, line_ref, by, to, text, kind=kind)
        return c.get("id") if isinstance(c, dict) else None
    except Exception:  # noqa: BLE001 - P1 is another card
        log.warning("%s comment on %s failed", kind, pid, exc_info=True)
        return None


def _t2(plane):
    try:
        from sh_platform.v1 import t2_tickets
        return t2_tickets
    except ImportError:
        return None


def go_live(plane, pid: str, by: str) -> dict:
    """The project's owner (the raiser or the sponsor on the record) takes it live. Refused with a plain sentence while a blocking comment
    is open, the build pack is unsigned or a benchmark miss has no resolution (P4's sign_block). Ops then reads and comments on the project's
    artefacts, and the run book is drafted if it has none."""
    p1, rec = _p1(), project(plane, pid)
    ppl = rec.get("people") or {}
    if by not in {ppl.get("raiser"), ppl.get("sponsor")} - {None}:
        raise Refusal(f"Only {' or '.join(n for n in (ppl.get('raiser'), ppl.get('sponsor')) if n) or 'the project owner'} can take this project live.")
    if rec.get("stage") == "live":
        raise Refusal("This project is already live.")
    if p1 is None:
        raise Refusal("Projects are not available yet, so this project cannot go live.")
    iid, doc = rec["intent_id"], p1.read(plane, pid)
    if next((a["state"] for a in doc["artefacts"] if a["kind"] == BUILD_PACK), None) != "signed":
        raise Refusal("The build pack is not signed yet. The head of data signs it once the benchmarks are met.")
    from sh_platform.v1 import p4_benchmarks
    if miss := p4_benchmarks.sign_block(plane, iid):
        raise Refusal(miss)
    if blocking := [c for c in p1.comments(plane, pid) if c.get("state") == "open" and c.get("kind") not in (*p1.QUIET, "ticket")]:
        raise Refusal(f"{len(blocking)} comment{'s' if len(blocking) > 1 else ''} on this project {'are' if len(blocking) > 1 else 'is'} still open "
                      f"(first: {p1.KIND_NAMES.get(blocking[0]['artefact'], 'the project').lower()}, to {blocking[0].get('to') or 'nobody named'}). Answer and resolve them first.")
    rec = _set(plane, pid, stage="live", live_by=by, live_at=_now())
    try:
        from sh_platform.v1 import g2_runbook
        if not g2_runbook.read(plane, iid):
            g2_runbook.draft(plane, rec)
    except Exception:  # noqa: BLE001 - going live never waits on the draft; ops can ask for it on the run book
        log.warning("run book draft for %s skipped", pid, exc_info=True)
    return rec


def _sources(plane, rec: dict) -> set[str]:
    sow = _read(plane.path("intents", str(rec.get("intent_id") or "_"), "sow.json"), default={})
    return {str(v) for s in sow.get("sources") or [] if isinstance(s, dict) for v in (s.get("id"), s.get("name")) if v}


def tickets(plane) -> list[dict]:
    return [t for t in _read(plane.path("build", "ops", "tickets.json"), list, default=[]) if isinstance(t, dict)]


def raise_ticket(plane, body: dict, by: str, *, day: date | None = None) -> dict:
    """One ticket, addressed to the project's builder. The Watcher's are deduplicated per project, source and day."""
    pid, source, text = body.get("pid"), body.get("source_id"), body.get("text")
    if not isinstance(source, str) or not SOURCE.match(source):
        raise ValueError("source_id is not valid")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("say what is wrong")
    try:
        rec = project(plane, pid)
    except LookupError:
        raise ValueError("no such project") from None
    to = (rec.get("people") or {}).get("builder")
    if not to:
        raise Refusal("Nobody has been named as this project's builder yet, so the ticket has no one to go to.")
    day_s = (day or datetime.now(timezone.utc).date()).isoformat()
    path = plane.path("build", "ops", "tickets.json")
    with lock_for(path):
        items = tickets(plane)
        if by == "watcher" and any(t.get("by") == "watcher" and (t.get("pid"), t.get("source_id"), t.get("day")) == (pid, source, day_s) for t in items):
            return {}
        t = {"id": f"tk-{len(items) + 1:04d}", "pid": pid, "source_id": source, "text": text.strip()[:1000], "by": by, "to": to,
             "kind": "ticket", "state": "open", "day": day_s, "at": _now(), "comment_id": None}
        t["comment_id"] = _say(plane, pid, source, by, to, t["text"], "ticket")
        if t2 := _t2(plane):  # T2: the ticket centre carries it; the comment above is its discussion
            t2.raise_guarded(plane, by=by, to=to, title=t["text"][:120], body=t["text"], project=pid, stage="ops",
                             links=[{"kind": "run", "ref": f"{source}:{day_s}"}] + ([{"kind": "comment", "ref": f"{pid}:{t['comment_id']}"}] if t["comment_id"] else []))
        write_json_atomic(path, [*items, t])
    return t


def after_ops(plane, today: date, rows: list[dict]) -> None:
    """Called by b5_ops.summary with the day's source rows: write each live project's daily state; the Watcher raises tickets."""
    out = {}
    for rec in projects(plane):
        if rec.get("stage") != "live":
            continue
        mine = [{k: r.get(k) for k in ("source_id", "state", "rows", "last_run")} for r in rows if r.get("source_id") in _sources(plane, rec)]
        out[rec["id"]] = {"state": min((r["state"] for r in mine), key=WORST.index, default="no_runs"), "sources": mine}
        for r in mine:
            if r["state"] in WATCHED:
                try:
                    raise_ticket(plane, {"pid": rec["id"], "source_id": r["source_id"],
                                         "text": f"Watcher: {r['source_id']} on {today.isoformat()}: {WATCHED[r['state']]}."}, "watcher", day=today)
                except ValueError:
                    log.warning("watcher ticket for %s not raised", rec["id"], exc_info=True)
    path = plane.path("build", "ops", "daily.json")
    with lock_for(path):
        write_json_atomic(path, {"date": today.isoformat(), "projects": out})


def daily(plane, pid: str) -> dict | None:
    """The project's ops state for the last ops read, or None while the project is not live (for Pulse's "your projects today")."""
    d = _read(plane.path("build", "ops", "daily.json"), default={})
    p = (d.get("projects") or {}).get(pid)
    return {"date": d.get("date"), **p} if p else None


def board(plane, iid: str | None = None) -> dict:
    """What the ops card shows: each live project (or the one for this intent) with its daily state and open tickets."""
    ts, p1 = tickets(plane), _p1()

    def is_open(t: dict) -> bool:  # with T2, when its ticket is resolved or closed; with P1, when its comment is resolved on the build pack
        if (t2 := _t2(plane)) and t.get("comment_id") and (s := t2.state_of_comment(plane, t["pid"], t["comment_id"])):
            return s in t2.ACTIVE
        if p1 is None or not t.get("comment_id"):
            return t.get("state") == "open"
        try:
            return any(c.get("id") == t["comment_id"] and c.get("state") != "resolved" for c in p1.comments(plane, t["pid"], BUILD_PACK))
        except Exception:  # noqa: BLE001
            return True
    rows = [{"pid": r["id"], "title": r.get("title"), "intent_id": r.get("intent_id"), "stage": r.get("stage"),
             "builder": (r.get("people") or {}).get("builder"), "daily": daily(plane, r["id"]),
             "tickets": [t for t in ts if t.get("pid") == r["id"] and is_open(t)]}
            for r in projects(plane) if r.get("stage") == "live" and (iid is None or r.get("intent_id") == iid)]
    return {"projects": rows, "tickets_in": "comments" if p1 else "ledger"}
