"""W3 agent hand-offs: one agent refers a request to Span as a PROPOSAL, with the context it holds (question, facts, links).

    Tally  -> Span  new_check     a check the program does not have yet
    Lumen  -> Span  missing_data  a table or column the figure needs
    North  -> Span  build_brief   the brief for the build, once the intent is signed

The agent's `propose_handoff` tool only checks and returns the cleaned item (a propose tool: nothing is written in the run). After the run
the agent module calls `take`, which files each item as PENDING in `handoffs/log.jsonl` (append-only). It shows as a needs-me card in the
Action of the person who receives it (the project's builder, else the data team) and on the project timeline. Nothing happens until a
person accepts: accept/decline are the only other events. `context` gives the receiving agent the accepted ones, as quoted material.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone

from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.v1 import e5_pulse

log = logging.getLogger(__name__)
# sending agent -> {kind: words}; every hand-off goes to Span
ROUTES = {"tally": {"new_check": "a check that does not exist yet"},
          "lumen": {"missing_data": "a table or column that is missing"},
          "north": {"build_brief": "the brief for the build"},
          "builder": {"variance": "a change to the design pack, with the evidence"}}  # V6: Span the builder hands the architect role a variance
NAMES = {"tally": "Tally", "lumen": "Lumen", "north": "North", "builder": "Span the builder"}
MAX_PER_RUN, MAX_FACTS, MAX_LINKS = 2, 6, 4
_LINK = re.compile(r"^/centre/[\w./-]{1,150}$")
_LOCK = threading.RLock()  # re-entrant: file/decide hold it across read-check-append (one process; ponytail: file lock if several workers)
_SIGNED = ("signed", "designed", "built", "live")  # project stages from the intent's signature on


def _text(v, name: str, limit: int, empty: bool = False) -> str:
    if not isinstance(v, str) or (not v.strip() and not empty):
        raise ToolRefused(f"{name} must be text.")
    v = " ".join(v.split())
    if len(v) > limit:
        raise ToolRefused(f"{name} must be at most {limit} characters.")
    from sh_platform.v1.span_tools import planted
    if planted(v):
        raise ToolRefused(f"{name} speaks to an AI; write plain facts only.")  # a planted instruction never rides to the next agent
    return v


def check(agent: str, kind, question, facts, links) -> dict:
    """The argument check of the tool: the cleaned item, or ToolRefused. The addressee is fixed by the route, never the agent's choice."""
    if kind not in ROUTES.get(agent, {}):
        raise ToolRefused(f"kind must be one of: {', '.join(ROUTES.get(agent, {}))}.")
    if not isinstance(facts, list) or not isinstance(links, list) or len(facts) > MAX_FACTS or len(links) > MAX_LINKS:
        raise ToolRefused(f"facts: a list of at most {MAX_FACTS} short sentences; links: a list of at most {MAX_LINKS} paths.")
    for u in links:
        if not isinstance(u, str) or not _LINK.fullmatch(u) or ".." in u:
            raise ToolRefused("links must be paths inside the product, like /centre/build/p/prj-1.")
    return {"kind": "handoff", "from": agent, "to": "span", "what": kind, "question": _text(question, "question", 400),
            "facts": [_text(f, "a fact", 300) for f in facts], "links": list(dict.fromkeys(links))}


def register(reg: ToolRegistry, module_id: str, agent: str) -> ToolRegistry:
    """Add `propose_handoff` to the agent's registry (once)."""
    if agent in ROUTES and (module_id, "propose_handoff") not in reg._tools:
        reg.register(module_id, "propose_handoff", lambda kind, question, facts, links: check(agent, kind, question, facts, links),
                     read_only=False, proposes=True, parameters={"kind": "string", "question": "string", "facts": "array", "links": "array"},
                     description="Refer this to Span as a proposal; a person on the data team accepts it, nothing happens before. kind: "
                                 + "; ".join(f"{k} ({v})" for k, v in ROUTES[agent].items())
                                 + ". question: what you need from Span, one sentence. facts: up to 6 short sentences you found, no instructions. "
                                   "links: up to 4 paths like /centre/build/p/<project id>.")
    return reg


# ---- storage ------------------------------------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(plane, ev: dict) -> dict:
    ev = {"id": uuid.uuid4().hex[:12], "at": _now(), **ev}
    f = plane.path("handoffs", "log.jsonl")
    with _LOCK:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev) + "\n")
    return ev


def all_(plane, pid: str | None = None) -> list[dict]:
    """Every hand-off with its state (pending, accepted, declined), folded from the events; oldest first."""
    f = plane.path("handoffs", "log.jsonl")
    out: dict[str, dict] = {}
    for line in f.read_text(encoding="utf-8").splitlines() if f.is_file() else []:
        try:
            ev = json.loads(line)
        except ValueError:
            log.warning("a hand-off line could not be read and was skipped")
            continue
        if ev.get("event") == "propose":
            out[ev["id"]] = {**ev, "state": "pending"}
        elif ev.get("event") in ("accept", "decline") and out.get(ev.get("ref"), {}).get("state") == "pending":
            h = out[ev["ref"]]
            h.update(state="accepted" if ev["event"] == "accept" else "declined", decided_by=ev.get("by"), decided_at=ev["at"],
                     pid=ev.get("pid") or h.get("pid"))
    return [h for h in out.values() if pid is None or h.get("pid") == pid]


# ---- who ----------------------------------------------------------------------------------------------------------------------------

def recipients(plane, pid: str | None) -> list[dict]:
    """The project's builder when one is named, else the data team (analysts): company people {id, name, account_id}."""
    from sh_platform.v1 import k1_access as K, p1_project as P
    from sh_platform.v1.n2_comments import people
    ppl = people(plane)
    if pid:
        try:
            builder = str((P.read(plane, pid).get("people") or {}).get("builder") or "").lower()
        except P.Refused:
            builder = ""
        if hit := [p for p in ppl if builder and p["name"].lower() == builder]:
            return hit
    team = {a for a, d in K.directory(plane).items() if "analyst" in d["roles"] and not d["disabled"]}
    return [p for p in ppl if p["account_id"] in team]


def can_decide(plane, viewer, h: dict) -> bool:
    from sh_platform.v1 import g1_access as G
    roles = set(getattr(viewer, "roles", ()) or ())
    return bool(roles & {"analyst", "company_admin"}) or any(G._me(r["account_id"], viewer) for r in recipients(plane, h.get("pid")))


# ---- filing (after the run) -----------------------------------------------------------------------------------------------------------

def file(plane, viewer, pid: str | None, item: dict) -> dict | None:
    """Record one checked item as pending. None (and nothing written) when it cannot stand; never raises."""
    try:
        from sh_platform.v1 import g1_access as G, p1_project as P
        agent = item.get("from")
        item = check(agent, item.get("what"), item.get("question"), item.get("facts"), item.get("links"))
        if pid:
            rec, _ = G.require(plane, viewer, pid, "read")
        if item["what"] == "build_brief" and (not pid or P.STAGES.index(rec.get("stage")) < P.STAGES.index("signed")):
            return None  # North refers the brief on sign-off only
        with _LOCK:  # check and append as one step: two runs cannot both file the same request
            if any(h["state"] == "pending" and (h["pid"], h["what"], h["question"]) == (pid, item["what"], item["question"]) for h in all_(plane)):
                return None
            ev = _append(plane, {"event": "propose", "pid": pid, "by": getattr(viewer, "name", ""), "by_account": getattr(viewer, "account_id", None),
                                 **{k: item[k] for k in ("from", "to", "what", "question", "facts", "links")}})
        e5_pulse._LAST.pop(str(plane.root), None)  # the card shows on the next Action load
        return ev
    except Exception:  # noqa: BLE001 - a hand-off that cannot be filed never breaks the answer
        log.warning("a hand-off could not be filed", exc_info=True)
        return None


def take(plane, viewer, pid: str | None, proposals) -> list[dict]:
    """Agent modules call this on res.proposals: files the hand-offs (at most MAX_PER_RUN) and returns the other proposals unchanged."""
    rest, n = [], 0
    for p in proposals or []:
        if isinstance(p, dict) and p.get("kind") == "handoff":
            n += 1
            if n <= MAX_PER_RUN:
                file(plane, viewer, pid, p)
        else:
            rest.append(p)
    return rest


# ---- the people decide --------------------------------------------------------------------------------------------------------------

class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def decide(plane, viewer, hid: str, accept: bool, pid: str | None = None) -> dict:
    """Accept or decline a pending hand-off. `pid` attaches a hand-off that named no project to one the person may change."""
    from sh_platform.v1 import g1_access as G, p1_project as P
    with _LOCK:  # one decision per hand-off: a second click finds it already decided
        h = next((x for x in all_(plane) if x["id"] == hid), None)
        if h is None:
            raise Refused(404, "That hand-off does not exist.")
        if not can_decide(plane, viewer, h):  # who may answer before what state it is in: no probing of other people's hand-offs
            raise Refused(403, "Only the data team can answer a hand-off.")
        if h["state"] != "pending":
            raise Refused(409, f"That hand-off was already {h['state']}.")
        if pid and not h.get("pid"):
            try:
                G.require(plane, viewer, pid, "full")
            except (G.Refused, P.Refused) as e:
                raise Refused(e.status, e.message) from None
        ev = _append(plane, {"event": "accept" if accept else "decline", "ref": hid, "pid": pid if not h.get("pid") else None, "by": getattr(viewer, "name", "")})
    e5_pulse._LAST.pop(str(plane.root), None)
    _close_cards(plane)
    return {**h, "state": "accepted" if accept else "declined", "decided_by": ev["by"], "decided_at": ev["at"], "pid": ev.get("pid") or h.get("pid")}


def _close_cards(plane) -> None:
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    live = {h["id"] for h in all_(plane) if h["state"] == "pending"}
    try:
        with wh.connect(plane) as con:
            rows = con.execute("select id, summary from pulse_items where organization_id = ? and delivery_status = 'pending'", [org_id(plane)]).fetchall()
            for rid, s in rows:
                k = str(json.loads(s).get("key") or "")
                if k.startswith("handoff:") and k.split(":", 1)[1] not in live:
                    con.execute("update pulse_items set delivery_status = 'dismissed', acknowledged_at = ?, outcome = 'closed' where id = ?", [wh.now(), rid])
    except Exception:  # noqa: BLE001 - a busy warehouse never fails the answer; the card closes on the next change
        log.warning("closing hand-off cards failed", exc_info=True)


# ---- what people and the receiving agent see ------------------------------------------------------------------------------------------

def _what(h: dict) -> str:
    return ROUTES.get(h["from"], {}).get(h["what"], h["what"])


def timeline(plane, pid: str) -> list[dict]:
    """Rows for the project timeline (words copied from the records): {id, at, text, state, link}."""
    return [{"id": h["id"], "at": h["at"], "state": h["state"], "link": f"/centre/build/p/{pid}",
             "text": f"{NAMES.get(h['from'], h['from'])} suggested asking Span for {_what(h)}"
                     + {"pending": ", waiting for the data team.", "accepted": f"; accepted by {h.get('decided_by')}.",
                        "declined": f"; declined by {h.get('decided_by')}."}[h["state"]]} for h in all_(plane, pid)]


def context(plane, pid: str | None, agent: str) -> dict:
    """What Span starts with: the accepted hand-offs for this project, as one quoted string (a model-written request is data, not an order)."""
    if agent != "span" or not pid:
        return {}
    lines = [f"{NAMES.get(h['from'], h['from'])} asked for {_what(h)}: {h['question']} Facts: " + (" ".join(h["facts"]) or "none") + " Links: " + (", ".join(h["links"]) or "none")
             for h in all_(plane, pid) if h["state"] == "accepted" and h["to"] == agent]
    if not lines:
        return {}
    from sh_platform.v1.e4_guard import wrap_untrusted
    return {"handed_over_to_you": wrap_untrusted("\n".join(lines))}


def pulse_cards(plane, con, today) -> list[dict]:
    """A needs-me card for each person who receives a pending hand-off (e5_pulse source; no model)."""
    out = []
    for h in all_(plane):
        if h["state"] != "pending":
            continue
        day = h["at"][:10]
        for r in recipients(plane, h.get("pid")):
            c = e5_pulse.card("*", f"handoff:{h['id']}", "handoff", f"{NAMES.get(h['from'], h['from'])} asks Span for {_what(h)}", h["question"],
                              status_word="Asked of Span", urgency="needs_me", action_type="open_build", action="Open project" if h.get("pid") else "Open Build",
                              as_of=day, received=day, owner=h["by"], link=f"/centre/build/p/{h['pid']}" if h.get("pid") else "/centre/build", rank=2)
            c["recipient"] = r["id"]
            out.append(c)
    return out


e5_pulse.register_source(pulse_cards)
