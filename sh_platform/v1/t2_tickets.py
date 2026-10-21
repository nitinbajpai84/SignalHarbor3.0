"""T2 The ticket centre: numbered tickets that agents and people hand each other, each with an audit log.

A ticket is a record `tickets/TCK-0001.json` per company (see docs/plan/V1-BUILD.md, T2). Numbers are sequential and never reused (tickets are
never deleted). Every change appends to `history` and nothing in it is edited. The discussion that goes with a ticket stays a P1 comment (or the
old T1 request row); the ticket links to it (link kind `comment`, ref `<pid>:<cid>`).

Link refs: artefact `<pid>:<kind>`, line `<pid>:<kind>:<line>`, comment `<pid>:<cid>`, run `<source>:<day>`, file `<pid>:<name>`.
Who sees a ticket: its raiser, its current and past assignees, the project team (G1 `may_see_project` == "full") and every company_admin.
A link follows the linked project's own access: a viewer who may not read it gets the lock and the preview G1 gives, never the target.
Agents raise tickets through `raise_ticket(...)`, called guarded from the P5 Watcher, G4, T1, F1 and P1 (run book comments). `migrate` makes
tickets from the older records (P5's comments of kind ticket, G4's approvals, T1's template requests), once."""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone

from sh_platform.jsonfile import claim_new, lock_for, read_json_strict, write_json_atomic
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
STAGES = {"intent": "Intent centre", "design": "Build centre (design)", "build": "Build centre", "ops": "Ops", "consume": "Consume centre"}
STATES = ("open", "in_progress", "waiting", "resolved", "closed")
ACTIVE = ("open", "in_progress", "waiting")
STATE_WORDS = {"open": "open", "in_progress": "in progress", "waiting": "waiting", "resolved": "resolved", "closed": "closed"}
LINK_KINDS = ("artefact", "line", "run", "file", "comment")
AGENTS = {"north": "North", "span": "Span", "flow": "Span", "lumen": "Lumen", "watcher": "Watcher", "nira": "Nira"}
_ID = re.compile(r"^TCK-\d{4,}$")
_PID = re.compile(r"^prj-[0-9a-f]{8}$")
SEEN = frozenset({"comment", "approval", "access"})


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def name_of(who) -> str:
    return AGENTS.get(who, str(who or "someone"))


def _dir(plane):
    return plane.path("tickets")


def _file(plane, tid: str):
    if not isinstance(tid, str) or not _ID.match(tid):
        raise Refused(404, "There is no such ticket.")
    return _dir(plane) / f"{tid}.json"


def _p1():
    try:
        from sh_platform.v1 import p1_project
        return p1_project
    except ImportError:
        return None


def _read(path):
    try:
        got = read_json_strict(path, dict)
    except (OSError, ValueError):
        log.warning("ticket file %s unreadable", path.name)
        return None
    return got if isinstance(got, dict) and got.get("id") else None


def all_tickets(plane) -> list[dict]:
    d = _dir(plane)
    return [t for f in sorted(d.glob("TCK-*.json")) if (t := _read(f))] if d.is_dir() else []


def get(plane, tid: str) -> dict:
    t = _read(_file(plane, tid))
    if t is None:
        raise Refused(404, "There is no such ticket.")
    return t


def _me(who, viewer) -> bool:
    if not who or viewer is None:
        return False
    aid = getattr(viewer, "account_id", None)
    if aid and str(who) == aid:
        return True
    return not getattr(viewer, "shared_name", False) and norm(who) == norm(getattr(viewer, "name", ""))


def _admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


def entry(by, action: str, frm=None, to=None, note: str = "", at: str | None = None) -> dict:
    return {"at": at or _now(), "by": by, "action": action, "from": frm, "to": to, "note": " ".join(str(note or "").split())[:500]}


# ---- raising ---------------------------------------------------------------------------------------------------------------------

def _project_person(plane, pid: str | None, to):
    """A part on the project ("builder") turned into the name that holds it (the raiser when nobody does)."""
    p1 = _p1()
    if not (pid and p1 and to in getattr(p1, "PEOPLE", ())):
        return to
    try:
        return p1.read(plane, pid)["people"].get(to) or p1.read(plane, pid)["people"].get("raiser")
    except Exception:  # noqa: BLE001
        return None


def _links(links) -> list[dict]:
    return [{"kind": k["kind"], "ref": str(k["ref"])[:200]} for k in links or []
            if isinstance(k, dict) and k.get("kind") in LINK_KINDS and k.get("ref")][:20]


def raise_ticket(plane, *, by, to, title: str, body: str = "", project: str | None = None, stage: str = "build", priority: str = "normal",
                 links=None, due: str | None = None, once: bool = False, at: str | None = None, state: str = "open") -> dict | None:
    """One new ticket (`by` an agent key or a person's name; `to` a person, an agent key or a part on the project). With `once`, nothing is
    raised when this raiser already raised one on the same project and link (the Watcher: one per source per day); None is returned."""
    title = " ".join(str(title or "").split())[:200]
    if not title:
        raise Refused(400, "Say in a line what the ticket is about.")
    if stage not in STAGES or priority not in ("normal", "high") or state not in STATES:
        raise Refused(400, "Unknown stage, priority or state.")
    if project is not None and not (isinstance(project, str) and _PID.match(project)):
        raise Refused(400, "There is no such project.")
    who = _project_person(plane, project, to)
    if not who:
        raise Refused(409, "Nobody is named to take this ticket yet.")
    links = _links(links)
    d = _dir(plane)
    with lock_for(d):
        have = all_tickets(plane)
        if once and any(t["raised_by"] == by and t.get("project") == project and {(k["kind"], k["ref"]) for k in t["links"]} & {(k["kind"], k["ref"]) for k in links}
                        for t in have):
            return None
        n = 1 + max([int(t["id"][4:]) for t in have] + [0])
        d.mkdir(parents=True, exist_ok=True)
        while True:  # ponytail: the file itself is the claim, so a second process (8200 and the watch script) cannot take the same number
            try:
                claim_new(_file(plane, f"TCK-{n:04d}"))
                break
            except FileExistsError:
                n += 1
        t = {"id": f"TCK-{n:04d}", "project": project, "stage": stage, "title": title, "body": str(body or "").strip()[:4000], "raised_by": by,
             "assigned_to": who, "state": state, "priority": priority, "links": links, "due": due, "created_at": at or _now(),
             "history": [entry(by, "raised", None, who, "", at)]}
        write_json_atomic(_file(plane, t["id"]), t)
    return t


def raise_guarded(plane, **kw) -> dict | None:
    """For the other cards' raise sites: a ticket must never break the act that raised it."""
    try:
        return raise_ticket(plane, **kw)
    except Exception:  # noqa: BLE001 - the old comment still carries the act
        log.warning("ticket not raised", exc_info=True)
        return None


# ---- acting ----------------------------------------------------------------------------------------------------------------------

def _change(plane, tid: str, fn) -> dict:
    with lock_for(_file(plane, tid)):
        t = get(plane, tid)
        fn(t)
        write_json_atomic(_file(plane, tid), t)
    return t


def _was(t: dict, viewer, plane=None) -> bool:
    """May change it: whoever raised or holds it, a company admin, or (for an agent's ticket) the project team."""
    return (_me(t["raised_by"], viewer) or _me(t["assigned_to"], viewer) or _admin(viewer)
            or bool(plane and t.get("project") and t["raised_by"] in AGENTS and G1_level(plane, viewer, t["project"]) == "full"))


def _active_only(t: dict) -> None:
    if t["state"] in ("resolved", "closed"):
        raise Refused(409, "This ticket is " + STATE_WORDS[t["state"]] + ". Reopen it first.")


def _checked(plane, viewer, tid: str) -> dict:
    t = get(plane, tid)
    if not can_see(plane, viewer, t):
        raise Refused(403, "You cannot see this ticket.")
    return t


def people(plane) -> list[str]:
    """Names a ticket can go to: the company's people (not disabled) and the agents."""
    try:
        from sh_platform.v1.k1_access import directory
        return sorted({p["name"] for p in directory(plane).values() if not p["disabled"]})
    except Exception:  # noqa: BLE001
        return []


def known(plane, to) -> str:
    """The company's spelling of a name, or an agent key; Refused when nobody has it (an empty directory accepts the name as typed)."""
    to = " ".join(str(to or "").split())[:120]
    if to in AGENTS or not (names := people(plane)):
        return to
    got = next((n for n in names if norm(n) == norm(to)), None)
    if not got:
        raise Refused(400, f"Nobody called {to} works in this company.")
    return got


def reassign(plane, viewer, tid: str, to: str, note: str = "") -> dict:
    """Delegate (the assignee hands it on) or assign (the raiser or a company admin gives it to someone). The previous assignee keeps read access."""
    t = _checked(plane, viewer, tid)
    to = known(plane, to)
    if not to:
        raise Refused(400, "Say who it goes to.")
    if not _was(t, viewer, plane):
        raise Refused(403, f"Only {name_of(t['assigned_to'])}, who has it, or {name_of(t['raised_by'])}, who raised it, or the project team can pass it on.")

    def go(x):
        _active_only(x)
        frm = x["assigned_to"]
        action = "delegated" if _me(frm, viewer) else "assigned"
        x["history"].append(entry(viewer.name, action, frm, to, note))
        x["assigned_to"] = to
        if x["state"] == "waiting":
            x["state"] = "open"
    return _change(plane, tid, go)


def say(plane, viewer, tid: str, text: str) -> dict:
    t = _checked(plane, viewer, tid)
    text = " ".join(str(text or "").split())[:1000]
    if not text:
        raise Refused(400, "Write what you want to say.")
    return _change(plane, tid, lambda x: x["history"].append(entry(viewer.name, "commented", None, None, text)))


def set_state(plane, viewer, tid: str, state: str, note: str = "") -> dict:
    t = _checked(plane, viewer, tid)
    if state not in STATES:
        raise Refused(400, "Choose open, in progress, waiting, resolved or closed.")
    if not _was(t, viewer, plane):
        raise Refused(403, f"Only {name_of(t['assigned_to'])}, who has it, or {name_of(t['raised_by'])}, who raised it, or the project team can change it.")
    return _apply_state(plane, tid, viewer.name, state, note)


def _apply_state(plane, tid: str, by, state: str, note: str = "") -> dict:
    def go(x):
        frm = x["state"]
        if frm == state:
            raise Refused(409, "It is already " + STATE_WORDS[state] + ".")
        if frm in ("resolved", "closed") and state != "open":
            raise Refused(409, "This ticket is " + STATE_WORDS[frm] + ". Reopen it first.")
        action = "resolved" if state == "resolved" else "reopened" if state == "open" and frm in ("resolved", "closed") else "state"
        x["history"].append(entry(by, action, frm, state, note))
        x["state"] = state
    return _change(plane, tid, go)


def link(plane, viewer, tid: str, kind: str, ref: str) -> dict:
    _checked(plane, viewer, tid)
    got = _links([{"kind": kind, "ref": ref}])
    if not got:
        raise Refused(400, "Name what to link: an artefact, a line, a run, a file or a comment.")
    return _change(plane, tid, lambda x: (x["links"].append(got[0]), x["history"].append(entry(viewer.name, "linked", None, None, f"{kind} {got[0]['ref']}"))))


def start(plane, viewer, body: dict) -> dict:
    """A person raises a ticket from the centre, a document line or a Pulse card."""
    pid = body.get("project") or None
    if pid and G1_level(plane, viewer, pid) not in ("full", "read"):
        raise Refused(403, "You cannot raise a ticket on a project you cannot read.")
    return raise_ticket(plane, by=viewer.name, to=known(plane, body.get("assigned_to")) or viewer.name, title=body.get("title"), body=body.get("body") or "",
                        project=pid, stage=body.get("stage") or "build", priority=body.get("priority") or "normal", links=body.get("links"),
                        due=str(body["due"])[:10] if body.get("due") else None)


def work(plane, viewer, tid: str) -> dict:
    """A ticket held by an agent: with no model on, the agent hands it back to a person with a note (labelled). Resolving takes the model."""
    t = _checked(plane, viewer, tid)
    if t["assigned_to"] not in AGENTS:
        raise Refused(409, "This ticket is held by a person, not an agent.")
    owner = next((n for n in [_project_person(plane, t.get("project"), k) for k in ("builder", "head_of_data", "raiser")] + [t["raised_by"]]
                  if n and n not in AGENTS), None)
    if not owner:
        raise Refused(409, "Nobody is named to take this ticket yet.")
    return _change(plane, tid, lambda x: (x["history"].append(entry(x["assigned_to"], "delegated", x["assigned_to"], owner,
                   "Not worked by an agent here (rules only, no model). Over to you.")), x.__setitem__("assigned_to", owner)))


def settle_comment(plane, cid: str, by, state: str, note: str = "") -> int:
    """The discussion behind a ticket was answered or resolved (G4's approval): the ticket follows. Returns how many tickets moved."""
    n = 0
    for t in all_tickets(plane):
        if t["state"] in ACTIVE and any(k["kind"] == "comment" and k["ref"].endswith(f":{cid}") for k in t["links"]):
            try:
                _apply_state(plane, t["id"], by, state, note)
                n += 1
            except Refused:
                pass
    return n


def state_of_comment(plane, pid: str, cid: str) -> str | None:
    """For P5's board: the state of the ticket that carries this comment, or None."""
    return next((t["state"] for t in all_tickets(plane) if {"kind": "comment", "ref": f"{pid}:{cid}"} in t["links"]), None)


# ---- who sees what ---------------------------------------------------------------------------------------------------------------

def G1_level(plane, viewer, pid: str) -> str:
    """G1's `may_see_project`; while G1 is absent, the people named on the project (and company admins) are the team."""
    try:
        from sh_platform.v1 import g1_access
        return g1_access.may_see_project(plane, viewer, pid)
    except ImportError:
        p1 = _p1()
        try:
            rec = p1.read(plane, pid)
        except Exception:  # noqa: BLE001
            return "none"
        return "full" if _admin(viewer) or any(_me(n, viewer) for n in (rec.get("people") or {}).values()) else "none"


def can_see(plane, viewer, t: dict) -> bool:
    if _admin(viewer) or _me(t["raised_by"], viewer) or _me(t["assigned_to"], viewer):
        return True
    if any(_me(h.get(k), viewer) for h in t["history"] if h["action"] in ("assigned", "delegated", "raised") for k in ("from", "to")):
        return True
    return bool(t.get("project")) and G1_level(plane, viewer, t["project"]) == "full"


def _label(plane, kind: str, ref: str) -> tuple[str | None, str, str | None]:
    """(project id, words, href) for one link."""
    p1, parts = _p1(), ref.split(":")
    pid = parts[0] if _PID.match(parts[0]) else None
    names = getattr(p1, "KIND_NAMES", {}) if p1 else {}
    if kind == "artefact" and pid:
        return pid, names.get(parts[1], parts[1].replace("_", " ").capitalize()), f"/centre/project/{pid}?artefact={parts[1]}"
    if kind == "line" and pid and len(parts) >= 3:
        line = ":".join(parts[2:])
        return pid, f"{names.get(parts[1], parts[1])}, line {line.removeprefix('deviation:') if line.startswith('deviation:') else line}", f"/centre/project/{pid}?artefact={parts[1]}&line={line}"
    if kind == "comment" and pid and len(parts) >= 2:
        art = ""
        try:
            art = next((c.get("artefact") for c in p1.comments(plane, pid) if c.get("id") == parts[1]), "") or ""
        except Exception:  # noqa: BLE001
            pass
        return pid, "The discussion on " + (names.get(art, "the project").lower()), f"/centre/project/{pid}?artefact={art}&comment={parts[1]}"
    if kind == "run":
        return None, f"Run of {parts[0]}" + (f" on {parts[1]}" if len(parts) > 1 else ""), "/centre/build/ops"
    return pid, ref.split(":", 1)[-1], None


def links_for(plane, viewer, t: dict) -> list[dict]:
    out = []
    for k in t["links"]:
        pid, words, href = _label(plane, k["kind"], k["ref"])
        pid = pid or t.get("project")
        lvl = G1_level(plane, viewer, pid) if pid else "full"
        if lvl in ("full", "read"):
            out.append({**k, "label": words, "href": href, "locked": False})
            continue
        row = {}
        try:
            from sh_platform.v1 import g1_access
            row = g1_access.lock_row(_p1().read(plane, pid), lvl)
        except Exception:  # noqa: BLE001
            pass
        out.append({**k, "label": row.get("title") or "A project you cannot read", "href": None, "locked": True, "preview": row.get("title") and
                    f"{row.get('title')}, {row.get('stage')}, owner {row.get('owner')}"})
    return out


# ---- the audit log in plain words --------------------------------------------------------------------------------------------------

def _when(at: str) -> str:
    try:
        d = datetime.fromisoformat(at)
        return f"{d.day} {d:%b %H:%M}"
    except (TypeError, ValueError):
        return str(at)


def words(h: dict) -> str:
    by, to, note = name_of(h["by"]), name_of(h.get("to")), h.get("note")
    a, when = h["action"], _when(h["at"])
    q = f" with '{note}'" if note else ""
    if a == "raised":
        s = f"{by} raised it to {to} on {when}"
    elif a in ("assigned", "delegated"):
        s = f"{by} {a} it to {to} on {when}{q}"
    elif a == "commented":
        s = f"{by} commented on {when}: '{note}'"
    elif a == "state":
        s = f"{by} set it to {STATE_WORDS.get(h.get('to'), h.get('to'))} on {when}{q}"
    elif a == "resolved":
        s = f"{by} resolved it on {when}{q}"
    elif a == "reopened":
        s = f"{by} reopened it on {when}{q}"
    else:
        s = f"{by} linked {note} on {when}"
    return s + "."


def log_csv(t: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["at", "by", "action", "from", "to", "note", "in words"])
    for h in t["history"]:
        w.writerow([h["at"], name_of(h["by"]), h["action"], name_of(h.get("from")) if h.get("from") else "", name_of(h.get("to")) if h.get("to") else "",
                    h.get("note") or "", words(h)])
    return out.getvalue()


# ---- views -----------------------------------------------------------------------------------------------------------------------

def _title(plane, pid: str | None) -> str | None:
    try:
        return _p1().read(plane, pid)["title"] if pid else None
    except Exception:  # noqa: BLE001
        return None


def _title_for(plane, viewer, pid: str | None) -> str | None:
    """G1: a project's title only to a person who may see it or its lock row; for a Restricted project the words are the lock's."""
    if viewer is not None and pid and G1_level(plane, viewer, pid) == "none":
        return "A restricted project"
    return _title(plane, pid)


def row(plane, t: dict, titles: dict, viewer=None) -> dict:
    last, now = t["history"][-1], datetime.now(timezone.utc)
    try:
        age = (now - datetime.fromisoformat(t["created_at"])).days
    except (TypeError, ValueError):
        age = 0
    if t.get("project") not in titles:
        titles[t.get("project")] = _title_for(plane, viewer, t.get("project"))
    return {"id": t["id"], "title": t["title"], "project": t.get("project"), "project_title": titles[t.get("project")], "stage": t["stage"],
            "stage_name": STAGES[t["stage"]], "assigned_to": t["assigned_to"], "assigned_name": name_of(t["assigned_to"]), "raised_by": t["raised_by"],
            "raised_name": name_of(t["raised_by"]), "state": t["state"], "priority": t["priority"], "due": t.get("due"), "created_at": t["created_at"],
            "last_change": {"at": last["at"], "text": words(last)}, "age_days": max(age, 0)}


def listing(plane, viewer, *, project=None, stage=None, assignee=None, raised_by=None, state=None, priority=None) -> dict:
    """The tickets this viewer may see, newest change first. assignee / raised_by "me" means the viewer; state "active" means open, in progress or waiting."""
    migrate(plane)
    titles: dict = {}

    def who(t, key, want):
        return _me(t[key], viewer) if want == "me" else norm(name_of(t[key])) == norm(want) or norm(t[key]) == norm(want)
    rows = []
    for t in all_tickets(plane):
        if project and t.get("project") != project or stage and t["stage"] != stage or priority and t["priority"] != priority:
            continue
        if state and (t["state"] not in ACTIVE if state == "active" else t["state"] != state):
            continue
        if assignee and not who(t, "assigned_to", assignee) or raised_by and not who(t, "raised_by", raised_by):
            continue
        if can_see(plane, viewer, t):
            rows.append(row(plane, t, titles, viewer))
    rows.sort(key=lambda r: r["last_change"]["at"], reverse=True)
    return {"tickets": rows, "stages": STAGES}


def detail(plane, viewer, tid: str) -> dict:
    t = _checked(plane, viewer, tid)
    titles: dict = {}
    mine = _was(t, viewer, plane)
    return {**row(plane, t, titles, viewer), "body": t["body"], "links": links_for(plane, viewer, t), "can_act": mine,
            "log": [{**h, "text": words(h)} for h in t["history"]]}


def assigned_on(plane, viewer, pid: str) -> bool:
    """The viewer holds an active ticket on this project that someone else with "full" on it gave them (or an agent did). A person's own ticket
    never counts: nobody joins the team by raising or passing a ticket to themselves."""
    from sh_platform.v1 import g1_access as G1
    try:
        rec = _p1().read(plane, pid)
    except Exception:  # noqa: BLE001
        return False
    for t in all_tickets(plane):
        if t.get("project") != pid or t["state"] not in ACTIVE or not _me(t["assigned_to"], viewer):
            continue
        by = next((h["by"] for h in reversed(t["history"]) if h["action"] in ("assigned", "delegated", "raised")), t["raised_by"])
        if by not in AGENTS and not _me(by, viewer) and G1.named_full(plane, rec, by):
            return True
    return False


def open_counts(plane) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in all_tickets(plane):
        if t["state"] in ACTIVE and t.get("project"):
            out[t["project"]] = out.get(t["project"], 0) + 1
    return out


# ---- Pulse (called by p2_pulse in one guarded line) -------------------------------------------------------------------------------

def extend(plane, viewer, needs: list, look: list, lines: list) -> None:
    """Needs you: open tickets assigned to the viewer (one card per project). Worth a look: tickets they raised that someone else changed in the
    last week. Project lines get their open ticket counts. A ticket whose discussion is already a card (a comment of kind approval or ticket)
    shows through that card, which this points at the ticket centre."""
    p1, shown = _p1(), {l.get("pid"): l for l in lines if l.get("pid")}
    counts = open_counts(plane)
    for pid, line in shown.items():
        if line.get("locked"):
            continue  # G1: a lock line says nothing about the work behind it, not even how many tickets
        line["open_tickets"] = max(line.get("open_tickets") or 0, counts.get(pid, 0))  # P2 counts old comments of kind ticket; a migrated one counts once
    for c in needs:
        if c.get("kind") == "ticket" and c.get("pid") and counts.get(c["pid"]):
            c["href"] = f"/centre/tickets?project={c['pid']}"
    mine: dict = {}
    for t in all_tickets(plane):
        if t.get("project") and t["project"] not in shown or not can_see(plane, viewer, t):
            continue
        if t["state"] in ("open", "in_progress") and _me(t["assigned_to"], viewer) and not _covered(plane, p1, t, viewer):
            mine.setdefault(t.get("project"), []).append(t)
        last = t["history"][-1]
        if _me(t["raised_by"], viewer) and not _me(last["by"], viewer) and last["action"] != "raised" and _fresh(last["at"]):
            look.append({"id": f"ticket:{t['id']}:{last['at']}", "kind": "ticket", "href": f"/centre/tickets/{t['id']}",
                         "text": f"{t['id']} ({t['title']}): {words(last)}"})
    for pid, ts in mine.items():
        ts.sort(key=lambda t: t["created_at"])
        title = (shown.get(pid) or {}).get("title") or _title_for(plane, viewer, pid) or "No project"
        n = len(ts)
        needs.append({"id": f"tck:{pid}", "kind": "ticket", "project": title, "pid": pid, "action": "Open the ticket" if n == 1 else "Open the tickets",
                      "href": f"/centre/tickets/{ts[0]['id']}" if n == 1 else f"/centre/tickets?project={pid or ''}",
                      "text": (f"{ts[0]['id']}: {ts[0]['title']}" if n == 1 else f"{n} tickets are yours."), "since": " ".join(_when(ts[0]["created_at"]).split()[:2])})


def _fresh(at: str, days: int = 7) -> bool:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(at)).days < days
    except (TypeError, ValueError):
        return False


def _covered(plane, p1, t: dict, viewer) -> bool:
    """Its discussion is an open comment that Pulse already shows this person as a card."""
    for k in t["links"]:
        if k["kind"] == "comment" and p1:
            pid, _, cid = k["ref"].partition(":")
            try:
                if any(c.get("id") == cid and c.get("state") == "open" and c.get("kind") in SEEN | {"ticket"} and _me(c.get("to"), viewer)
                   for c in p1.comments(plane, pid)):
                    return True
            except Exception:  # noqa: BLE001
                pass
    return False


# ---- raise sites that are not in the cards' own files ------------------------------------------------------------------------------

def from_runbook_comment(plane, pid: str, c: dict) -> None:
    """P1 calls this for a person's comment on the run book: ops asks the data engineer, as a ticket (the comment is its thread)."""
    if c.get("by") in AGENTS or not c.get("to"):
        return
    raise_guarded(plane, by=c["by"], to=c["to"], title=str(c["text"]).split("\n")[0][:120], body=c["text"], project=pid, stage="ops",
                  links=[{"kind": "line", "ref": f"{pid}:run_book:{c['line_ref']}"} if c.get("line_ref") else {"kind": "artefact", "ref": f"{pid}:run_book"},
                         {"kind": "comment", "ref": f"{pid}:{c['id']}"}])


def admins(plane) -> list[str]:
    try:
        from sh_platform.v1.k1_access import directory
        return sorted(p["name"] for p in directory(plane).values() if "company_admin" in p["roles"] and not p["disabled"])
    except Exception:  # noqa: BLE001
        return []


# ---- migration (one time, idempotent: a source already carried by a ticket is skipped) --------------------------------------------------

def migrate(plane) -> int:
    """Tickets from P5's comments of kind ticket, G4's approvals and T1's template requests. Safe to call on every read: it costs one
    marker file once it has run. The raise sites link their old record the same way, so a record they already carried is never made twice."""
    marker = _dir(plane) / "_migrated.json"
    if marker.is_file():
        return 0
    n = 0
    with lock_for(_dir(plane)):
        have = {(k["kind"], k["ref"]) for t in all_tickets(plane) for k in t["links"]}
        p1 = _p1()
        for f in sorted(plane.path("projects").glob("prj-*.json")) if p1 and plane.path("projects").is_dir() else []:
            try:
                comments = p1.comments(plane, f.stem)
            except Exception:  # noqa: BLE001
                continue
            for c in comments:
                ref = ("comment", f"{f.stem}:{c.get('id')}")
                if c.get("kind") not in ("ticket", "approval") or ref in have or not c.get("to"):
                    continue
                ok = c.get("state") in ("answered", "resolved")
                art = c.get("artefact") or "build_pack"
                ls = [{"kind": "comment", "ref": ref[1]}] + ([{"kind": "run", "ref": f"{c['line_ref']}:{str(c['at'])[:10]}"}] if c["kind"] == "ticket" and c.get("line_ref") else [])
                t = raise_guarded(plane, by=c.get("by") or "someone", to=c["to"], title=str(c["text"]).split("\n")[0][:120], body=c["text"], project=f.stem,
                                  stage="design" if c["kind"] == "approval" else "ops", links=ls, at=c.get("at"), state="resolved" if ok else "open")
                if t:
                    n += 1
                    if ok:
                        t["history"].append(entry(c.get("resolved_by") or c["to"], "resolved", "open", "resolved", "Answered in the discussion.", c.get("answered_at")))
                        write_json_atomic(_file(plane, t["id"]), t)
        try:
            reqs = read_json_strict(plane.path("templates", "requests.json"), list) or []
        except (OSError, ValueError):
            reqs = []
        to = (admins(plane) or [None])[0]
        for r in reqs:
            ref = ("file", f"templates/requests.json#{r.get('id')}")
            if not isinstance(r, dict) or ref in have or not to:
                continue
            t = raise_guarded(plane, by=r.get("by") or "someone", to=to, title=f"{'Skill' if r.get('kind') == 'skill' else 'Template'} request: {r.get('text', '')}"[:120],
                              body=r.get("text") or "", stage="intent", links=[{"kind": "file", "ref": ref[1]}], at=r.get("at"))
            if t:
                n += 1
        write_json_atomic(marker, {"at": _now(), "made": n})
    return n
