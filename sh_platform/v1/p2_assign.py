"""V5W-1 Assignments and the Action landing.

A project owner (or a company admin) assigns steps of a project to a person with a message and a due date, or hands the whole
project over. Storage: `assignments/log.jsonl` in the company plane, append-only (assign, handover, done, withdraw); the state
shown is folded from the events, so history is never rewritten. The person assigned joins the project team (g1_access.join) and is
named its builder (p1_project.set_person); the project owner stays the owner.
Today: the assignee gets a "needs me" card, the owner a "worth a look" card (e5_pulse source, no model, words copied from rows).
`landing` gathers the Action page: needs me, assigned to me, waiting for my approval, worth a look."""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import date, datetime, timezone

from sh_platform.agents import handoff
from sh_platform.v1 import e5_pulse, g1_access as G, p1_project as P, wh
from sh_platform.v1.n2_comments import people

log = logging.getLogger(__name__)
STEPS = {"architecture": "Architecture", "pipelines": "Pipelines", "dashboards": "Dashboards and delivery"}
MAX_TEXT = 2000
_LOCK = threading.Lock()


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- events ---------------------------------------------------------------------------------------------------------------------

def _file(plane):
    return plane.path("assignments", "log.jsonl")


def _append(plane, ev: dict) -> dict:
    ev = {"id": uuid.uuid4().hex[:12], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **ev}
    f = _file(plane)
    with _LOCK:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev) + "\n")
    from sh_platform import events  # W3: the Action badge moves
    events.badge(plane.company_id, "action", change=ev.get("event"), to=ev.get("to"))
    return ev


def events(plane, pid: str | None = None) -> list[dict]:
    f = _file(plane)
    out = []
    for line in f.read_text(encoding="utf-8").splitlines() if f.is_file() else []:
        try:
            ev = json.loads(line)
        except ValueError:
            log.warning("an assignment line could not be read and was skipped")
            continue
        if pid is None or ev.get("pid") == pid:
            out.append(ev)
    return out


def open_ones(evs: list[dict]) -> list[dict]:
    """Assignments still open: the newest assign/handover per project step, unless done, withdrawn or replaced by a later one."""
    by_step: dict[tuple[str, str], dict] = {}
    for ev in evs:
        if ev["event"] in ("assign", "handover"):
            for s in ev["steps"]:
                by_step[(ev["pid"], s)] = ev
        elif ev["event"] in ("done", "withdraw"):
            for key in [k for k, v in by_step.items() if v["id"] == ev["ref"]]:
                del by_step[key]
    seen, out = set(), []
    for ev in by_step.values():
        if ev["id"] not in seen:
            seen.add(ev["id"])
            out.append({**ev, "steps": sorted((s for (p, s), v in by_step.items() if v["id"] == ev["id"]), key=list(STEPS).index)})
    return sorted(out, key=lambda e: e["at"])


# ---- who ------------------------------------------------------------------------------------------------------------------------

def _person(plane, who: str) -> dict:
    """A company person by name or by id (Build's dialog sends the id)."""
    key = str(who or "").strip().lower()
    p = next((x for x in people(plane) if key in (x["name"].lower(), x["id"].lower())), None)
    if not p:
        raise Refused(400, "Choose a person from your company.")
    return p


def _same(viewer, who: str | None, account: str | None = None) -> bool:
    return bool(who or account) and (G._me(account, viewer) or G._me(who, viewer))


def _check(plane, steps, to, message, due) -> tuple[list[str], str, str | None]:
    steps = [s for s in dict.fromkeys(steps or []) if s in STEPS]
    if not steps:
        raise Refused(400, "Choose at least one step.")
    message = str(message or "").strip()
    if len(message) > MAX_TEXT:
        raise Refused(400, "Keep the message under 2,000 characters.")
    if due:
        try:
            if date.fromisoformat(str(due)) < wh.today(plane):  # the company's cycle date, not the server clock
                raise Refused(400, "The due date has already passed.")
        except ValueError:
            raise Refused(400, "Write the due date like 2026-10-16.") from None
    return steps, message, str(due) if due else None


def _write(plane, viewer, pid: str, kind: str, steps, to: str, message, due) -> dict:
    rec, _ = G.require(plane, viewer, pid, "full")
    if not (G.can_manage(rec, viewer) or G._me((rec.get("people") or {}).get("sponsor"), viewer)):
        raise Refused(403, "Only the project owner, its sponsor or a company administrator can assign its steps.")
    steps, message, due = _check(plane, steps, to, message, due)
    person = _person(plane, to)
    ev = _append(plane, {"event": kind, "pid": pid, "title": rec.get("title"), "steps": steps, "to": person["name"], "to_account": person["account_id"],
                         "by": getattr(viewer, "name", ""), "by_account": getattr(viewer, "account_id", None), "message": message, "due": due})
    G.join(plane, pid, person["name"], "builder", person["account_id"])
    P.set_person(plane, pid, "builder", person["name"])
    _close_cards(plane)  # a step given to someone else closes the earlier person's card
    return ev


def assign(plane, viewer, pid: str, steps, to: str, message="", due=None) -> dict:
    """Assign steps of a project to a person. The owner stays the owner."""
    try:
        return _write(plane, viewer, pid, "assign", steps, to, message, due)
    except P.Refused as e:
        raise Refused(e.status, e.message) from None


def handover(plane, viewer, pid: str, to: str, message="", due=None, steps=None) -> dict:
    """Hand the project over: every step you name (all three when none are named) goes to this person."""
    try:
        return _write(plane, viewer, pid, "handover", list(steps or STEPS), to, message, due)
    except P.Refused as e:
        raise Refused(e.status, e.message) from None


def finish(plane, viewer, aid: str, kind: str = "done") -> dict:
    """`done`: the assignee says their part is finished. `withdraw`: the person who assigned it (or an admin) takes it back."""
    ev = next((e for e in open_ones(events(plane)) if e["id"] == aid), None)
    if not ev:
        raise Refused(404, "That assignment is not open.")
    if kind == "done" and not _same(viewer, ev["to"], ev.get("to_account")):
        raise Refused(403, "Only the person it was assigned to can finish it.")
    if kind == "withdraw" and not (_same(viewer, ev["by"], ev.get("by_account")) or "company_admin" in set(getattr(viewer, "roles", ()) or ())):
        raise Refused(403, "Only the person who assigned it can take it back.")
    out = _append(plane, {"event": kind, "pid": ev["pid"], "ref": aid, "by": getattr(viewer, "name", "")})
    _close_cards(plane)
    return out


def _close_cards(plane) -> None:
    """Today keeps cards until someone acts on them; an assignment that is done, withdrawn or replaced closes its own cards."""
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    e5_pulse._LAST.pop(str(plane.root), None)  # the new card shows on the next Today load, not after the five-minute refresh
    live = {e["id"] for e in open_ones(events(plane))}
    try:
        with wh.connect(plane) as con:
            rows = con.execute("select id, summary from pulse_items where organization_id = ? and delivery_status = 'pending'", [org_id(plane)]).fetchall()
            stale = [rid for rid, s in rows if (k := str(json.loads(s).get("key") or "")).startswith(("assign:", "assigned:")) and k.split(":", 1)[1] not in live]
            for rid in stale:
                con.execute("update pulse_items set delivery_status = 'dismissed', acknowledged_at = ?, outcome = 'closed' where id = ?", [wh.now(), rid])
    except Exception:  # noqa: BLE001 - a busy warehouse never fails the assignment; the card closes on the next change
        log.warning("closing finished assignment cards on Today failed", exc_info=True)


def candidates(plane, viewer, pid: str) -> dict:
    """Who a step can go to: every active person of the company with their role and how many steps they already have open."""
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    history(plane, viewer, pid)  # same access as reading the project's assignments
    busy: dict[str, int] = {}
    for e in open_ones(events(plane)):
        busy[e["to"]] = busy.get(e["to"], 0) + len(e["steps"])
    with wh.connect(plane, read_only=True) as con:
        roles = dict(con.execute("select id, business_role from users where organization_id = ? and is_active", [org_id(plane)]).fetchall())
    return {"people": [{"id": p["id"], "name": p["name"], "role": roles.get(p["id"]) or "", "open_steps": busy.get(p["name"], 0)} for p in people(plane)]}


def history(plane, viewer, pid: str) -> dict:
    """The assignments of one project, open ones and every event, for someone who may read the project."""
    try:
        rec, _ = G.require(plane, viewer, pid, "read")
    except P.Refused as e:
        raise Refused(e.status, e.message) from None
    evs = events(plane, pid)
    return {"project": {"id": pid, "title": rec.get("title"), "owner": (rec.get("people") or {}).get("raiser")},
            "steps": [{"id": k, "label": v} for k, v in STEPS.items()], "open": [_row(e) for e in open_ones(evs)], "history": [_row(e) for e in evs],
            "assignments": [_step_row(e, s) for e in open_ones(evs) for s in e["steps"]],
            "handoffs": handoff.timeline(plane, pid)}  # W3: agent referrals, for the project timeline  # one row per step, the shape Build's project page reads


def _step_row(e: dict, step: str) -> dict:
    return {"step": step, "assignee": e.get("to_account") or e["to"], "assignee_name": e["to"], "role": "builder", "note": e.get("message") or None,
            "due": e.get("due"), "by": e.get("by_account") or e["by"], "by_name": e["by"], "at": e["at"], "state": "assigned"}


def _row(e: dict) -> dict:
    out = {k: e.get(k) for k in ("id", "event", "pid", "title", "to", "by", "message", "due", "at", "ref")}
    out["steps"] = [STEPS[s] for s in e.get("steps", [])]
    out["link"] = f"/centre/build/p/{e['pid']}"
    return out


# ---- Today -----------------------------------------------------------------------------------------------------------------------

def pulse_cards(plane, con, today) -> list[dict]:
    """The assignee: a needs-me card. The project owner: a worth-a-look card that it was assigned. Both by `recipient` (users.id)."""
    ppl = {p["name"].lower(): p["id"] for p in people(plane)}
    by_acct = {p["account_id"]: p["id"] for p in people(plane) if p["account_id"]}
    out = []
    for e in open_ones(events(plane)):
        day, steps, what = e["at"][:10], ", ".join(STEPS[s] for s in e["steps"]), "handed you" if e["event"] == "handover" else "assigned you"
        link = f"/centre/build/p/{e['pid']}"
        mine = by_acct.get(e.get("to_account")) or ppl.get(str(e["to"]).lower())
        if mine:
            c = e5_pulse.card("*", f"assign:{e['id']}", "assignment", f"{e['by']} {what} {e.get('title') or 'a project'}",
                              f"{steps}." + (f" Due {e['due']}." if e.get("due") else "") + (f' "{e["message"]}"' if e.get("message") else ""),
                              status_word="Assigned to you", urgency="needs_me", action_type="open_build", action="Open project", as_of=day, received=day,
                              owner=e["by"], due=e.get("due"), link=link, rank=1)
            c["recipient"] = mine
            out.append(c)
        try:
            owner_name = (P.read(plane, e["pid"]).get("people") or {}).get("raiser")
        except P.Refused:
            continue
        theirs = ppl.get(str(owner_name or "").lower())
        if theirs and theirs != mine:
            c = e5_pulse.card("*", f"assigned:{e['id']}", "assignment", f"{e['to']} has {steps} on {e.get('title') or 'a project'}",
                              f"{e['by']} assigned it on {day}." + (f" Due {e['due']}." if e.get("due") else ""), status_word="Assigned", urgency="worth_a_look",
                              action_type="open_build", action="Open project", as_of=day, received=day, owner=e["to"], due=e.get("due"), link=link, rank=4)
            c["recipient"] = theirs
            out.append(c)
    return out


e5_pulse.register_source(pulse_cards)


# ---- the Action landing -----------------------------------------------------------------------------------------------------------

def _waiting(plane, viewer) -> list[dict]:
    """Things that wait for this person's decision: dashboards, build plans and intents (reviews and deliveries join when their steps exist)."""
    from sh_platform.v1 import b6_plan, cx_dash, d1_delivery
    from sh_platform.v1.seats import HEAD_OF_DATA, seat_of
    out = []
    for rec in P.all_projects(plane):
        if G.level(plane, viewer, rec) == "none":
            continue
        pid, title = rec["id"], rec.get("title") or "A project"
        for f in sorted(cx_dash._dir(plane, pid).glob("dash-*.json")):
            try:
                d = cx_dash._load(plane, pid, f.stem)
            except cx_dash.Refused:
                continue
            if cx_dash.can_approve(viewer, d):
                lc = d["lifecycle"]
                out.append({"kind": "dashboard", "title": f"Dashboard: {d.get('title')}", "project": title, "from": lc.get("submitted_by_name"),
                            "since": (lc.get("submitted_at") or "")[:10], "link": f"/centre/build/p/{pid}/dashboards"})
        try:  # V5W-8: delivery channels sent for approval
            for ch in d1_delivery._load(plane, pid)["channels"]:
                if d1_delivery.can_approve(viewer, ch):
                    out.append({"kind": "delivery", "title": f"Delivery: {ch.get('title')}", "project": title, "from": ch.get("submitted_by_name") or ch.get("made_by_name"),
                                "since": str(ch.get("submitted_at") or ch.get("made_at") or "")[:10], "link": f"/centre/build/p/{pid}/delivery"})
        except d1_delivery.Refused:
            pass
        try:
            plan = b6_plan.get(plane, pid)
        except Exception:  # noqa: BLE001 - an unreadable plan is not waiting on anyone
            plan = None
        if plan and plan.get("state") == "proposed" and HEAD_OF_DATA in seat_of(viewer) and not _same(viewer, plan.get("proposed_by"), plan.get("proposed_by_id")):
            out.append({"kind": "plan", "title": f"Plan v{plan.get('version')}: {title}", "project": title, "from": plan.get("proposed_by"),
                        "since": str(plan.get("proposed_at") or "")[:10], "link": f"/centre/build/p/{pid}/architecture"})
        try:  # V6: a design pack sent to the head of data waits there too (never for the people who made it)
            from sh_platform.v1 import b10_pack
            pack = next((p_ for p_ in (b10_pack.get(plane, pid, n) for n in reversed(b10_pack.versions(plane, pid))) if p_ and p_.get("state") == "proposed"), None)
            if pack and HEAD_OF_DATA in seat_of(viewer) and b10_pack._id(viewer) not in b10_pack.makers(pack):
                out.append({"kind": "pack", "title": f"Design pack v{pack.get('version')}: {title}", "project": title, "from": pack.get("created_by"),
                            "since": str(pack.get("created_at") or "")[:10], "link": f"/centre/build/p/{pid}/architecture"})
        except Exception:  # noqa: BLE001 - an unreadable pack is not waiting on anyone
            log.warning("could not read the design pack for %s", pid, exc_info=True)
        sow = P._rec(plane, f"intents/{rec['intent_id']}/sow.json") or {}
        thread = P._rec(plane, f"intents/{rec['intent_id']}/thread.json") or {}
        named = (rec.get("people") or {}).get("sponsor")
        # V6 (walk gap 4): nobody is named sponsor until the intent is signed, so an unsigned intent waits for every sponsor (the decision maker), never for its raiser
        mine = _same(viewer, named) if named else "sponsor" in set(getattr(viewer, "roles", ()) or ()) and not _same(viewer, (rec.get("people") or {}).get("raiser"), rec.get("raiser_id"))
        if sow.get("state") != "signed" and thread.get("state") == "sow_ready" and mine:
            turns = [str(t.get("at")) for t in thread.get("turns") or [] if isinstance(t, dict) and t.get("at")]
            out.append({"kind": "intent", "title": f"Sign the intent: {title}", "project": title, "from": (rec.get("people") or {}).get("raiser"),
                        "since": (max(turns) if turns else str(sow.get("updated_at") or ""))[:10], "link": f"/centre/intent/{rec['intent_id']}/sign"})
    return out


def landing(plane, viewer, day: date | None = None) -> dict:
    """The Action page: counts and rows for the four sections. Pulse cards come from e5_pulse as they are; assignments are not repeated in them."""
    cards = e5_pulse.view(plane, viewer, day)["items"]
    mine = [_row(e) | {"assigned_by": e["by"]} for e in open_ones(events(plane)) if _same(viewer, e["to"], e.get("to_account"))]
    by_me = [_row(e) for e in open_ones(events(plane)) if _same(viewer, e["by"], e.get("by_account"))]
    out = {"needs_me": [c for c in cards if c["urgency"] == "needs_me" and c["kind"] != "assignment"],
           "assigned_to_me": mine, "assigned_by_me": by_me, "waiting_approval": _waiting(plane, viewer),
           "worth_a_look": [c for c in cards if c["urgency"] != "needs_me" and c["kind"] != "assignment"]}
    return out | {"counts": {k: len(v) for k, v in out.items()}, "viewer": getattr(viewer, "name", "")}
