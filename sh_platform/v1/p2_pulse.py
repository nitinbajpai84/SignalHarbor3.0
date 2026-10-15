"""P2 Pulse, the landing page (replaces X2 Home): three bands computed on read, cached 60 s per company and viewer.

Needs you: X2's seat waits (x2_home._intent, by import), comments and tickets addressed to the person (P1's
projects/<pid>/comments.json), formulas Span asked the data engineer to confirm (f1_chat.points).
Your projects today: one line per project (P1's projects/<pid>.json; an intent without one stands in) the person is on or may read.
Worth a look: a loaded figure that jumped (c1_cards), a source whose file stopped arriving (warehouse/runs.json), documents in the
review queue (x5_extract.queue), open map notes on nodes the viewer may see (graph.read.graph_for), and items the feeds write to signals/.
Visibility follows the routes each fact already has: the review queue for company_admin, sponsor, analyst; source state for the ops seat;
map notes gated by the viewer's map; a project not yet signed only for the decision maker and the people named on it.
Every file may be absent or damaged; P1, F1, X5, C1 and the map are imported guarded. Nothing is written."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sh_platform.jsonfile import read_json_strict
from sh_platform.profile.view import norm
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import x2_home as X2
from sh_platform.v1.seats import DATA_ENGINEER, DECISION_MAKER, OPS_MANAGER, seat_of

log = logging.getLogger(__name__)
TTL = 60.0
JUMP = 0.20  # ponytail: the pack's own threshold has no field in the 1.0 records yet; 20 % for every KPI until it does
QUEUE_ROLES = frozenset({"company_admin", "sponsor", "analyst"})
ARTEFACT_NAMES = {"intent": "the intent of work", "design": "the system design", "build_pack": "the build pack", "brief": "the consumption brief"}
CARD = {"comment": ("comment", "need your answer", "needs your answer", "Answer"), "ticket": ("ticket", "are yours", "is yours", "Open the ticket"),
        "handover": ("hand-over", "wait for you to accept", "waits for you to accept", "Accept the hand-over"),
        "approval": ("request", "need your decision", "needs your decision", "Approve / Not this"),
        "suggestion": ("suggestion", "wait for your answer", "waits for your answer", "Accept / Decline"),  # K2: a change suggested to a definition
        "access": ("access request", "wait for your answer", "waits for your answer", "Approve / Not now")}  # G1: a person asks to read a project  # P1 kinds; a note only tells
AGENT_KEYS = frozenset({"north", "span", "flow", "lumen", "watcher", "nira"})
_cache: dict[tuple, tuple[float, dict]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _guard(what: str, fn, default):
    """Another card's code: a missing or broken module is a band with less in it, never a 500."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        log.warning("pulse: %s unavailable", what, exc_info=True)
        return default


def _is_me(to, viewer) -> bool:
    if not to:
        return False
    if viewer.account_id and str(to) == viewer.account_id:
        return True
    return not viewer.shared_name and norm(to) == norm(viewer.name)


# ---- records ---------------------------------------------------------------------------------------------------------------------

def _p1():
    try:
        from sh_platform.v1 import p1_project
        return p1_project
    except ImportError:
        return None


def _projects(plane) -> dict[str, dict]:
    """intent_id -> project record (P1, stage synced from the records). Empty while P1 has not landed."""
    p1 = _p1()
    if p1 is not None:
        got = _guard("p1 projects", lambda: p1.all_projects(plane), None)
        if got is not None:
            return {str(p["intent_id"]): p for p in got if isinstance(p, dict) and p.get("id") and p.get("intent_id")}
    root = plane.path("projects")
    out = {}
    for f in sorted(root.glob("prj-*.json")) if root.is_dir() else []:
        p = X2._read(f)
        if p.get("id") and p.get("intent_id"):
            out[str(p["intent_id"])] = p
    return out


def _comments(plane, pid: str) -> list[dict]:
    p1 = _p1()
    if p1 is not None:
        return _guard("p1 comments", lambda: p1.comments(plane, pid), [])
    try:
        got = read_json_strict(plane.path("projects", pid, "comments.json"), list) or []
    except (OSError, ValueError):
        return []
    return [c for c in got if isinstance(c, dict)]


def _people(project: dict) -> set[str]:
    p = project.get("people")
    vals = p.values() if isinstance(p, dict) else []
    return {norm(v) for v in vals if isinstance(v, str)} | {norm(x) for v in vals if isinstance(v, list) for x in v if isinstance(x, str)}


def _daily(plane, pid: str | None):
    from sh_platform.v1 import p5_handover
    return p5_handover.daily(plane, pid) if pid else None


# ---- needs you -------------------------------------------------------------------------------------------------------------------

def _comment_cards(pid: str, title: str, comments: list[dict], viewer, iid: str = "") -> list[dict]:
    """One card per artefact and kind: "2 comments on the system design need your answer"; opens the first open line."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in comments:
        kind = c.get("kind") or "comment"
        if kind == "handover" and c.get("by") in AGENT_KEYS:  # an agent's hand-over tells; the seat wait already shows the act
            continue
        if c.get("state") == "open" and kind in CARD and _is_me(c.get("to"), viewer):
            groups.setdefault((str(c.get("artefact") or ""), kind), []).append(c)
    out = []
    for (art, kind), items in groups.items():
        items.sort(key=lambda c: str(c.get("at") or ""))
        first, n, where = items[0], len(items), ARTEFACT_NAMES.get(art, art.replace("_", " ") or "the project")
        word, many, one, action = CARD[kind]
        href = ("/centre/build/ops" if kind == "handover" else f"/centre/build/{iid}/deviations" if kind == "approval" and iid  # G4: the request itself
                else f"/centre/intent/graph?node={first.get('line_ref') or ''}" if kind == "suggestion"
                else f"/centre/project/{pid}?artefact={art}&line={first.get('line_ref') or ''}&comment={first.get('id') or ''}")
        out.append({"id": f"{pid}:{art}:{kind}", "kind": kind, "project": title, "pid": pid, "action": action, "href": href,
                    "text": (str(first.get("text") or "").split(chr(10))[0] if kind in ("approval", "access") and n == 1  # G4: "Span asks to take Net worth from the statements ..."
                             else f"{X2._plural(n, word)} on {where} {one if n == 1 else many}."),
                    "since": X2._day(first["at"]) if first.get("at") else None})
    return out


def _formula_cards(plane, iid: str, title: str) -> list[dict]:
    def ask():
        from sh_platform.v1 import f1_chat
        return [p for p in f1_chat.points(plane, iid) if p.get("kind") == "formula"]
    got = _guard("f1 points", ask, [])
    if not got:
        return []
    return [{"id": f"{iid}:formula", "kind": "formula", "project": title, "pid": None,
             "text": f"Span asked you to confirm {X2._plural(len(got), 'formula')}.", "action": "Confirm the formula",
             "href": f"/centre/build/{iid}/engineer", "since": None}]


# ---- your projects today ---------------------------------------------------------------------------------------------------------

def _moved(kpis: list[dict]) -> dict | None:
    """The figure that moved most between its last two loaded periods, by relative change."""
    best = None
    for k in kpis:
        t = k.get("trend") or []
        if len(t) < 2:
            continue
        a, b = t[-2]["value"], t[-1]["value"]
        change = (b - a) / abs(a) if a else (0.0 if b == a else float("inf"))
        if best is None or abs(change) > abs(best["change"]):
            best = {"code": k["code"], "name": k["name"], "unit": k.get("unit"), "period": t[-1]["period"], "from": a, "to": b, "change": change}
    if best and best["change"] in (float("inf"), float("-inf")):
        best["change"] = None
    return best


def _last_load(loaded: list[dict], src_ids: set[str]) -> dict | None:
    mine = [p for p in loaded if p.get("source_id") in src_ids and p.get("period")]
    if not mine:
        return None
    period = max(str(p["period"]) for p in mine)
    states = [p for p in mine if str(p["period"]) == period]
    bad = next((p for p in states if p.get("state") == "not_loaded"), None)
    return {"period": period, "state": "not_loaded" if bad else "loaded", "reason": (bad or {}).get("reason")}


# ---- worth a look ----------------------------------------------------------------------------------------------------------------

def _stopped(plane) -> list[dict]:
    """A source whose latest run is older than the latest day any source ran: its file stopped arriving."""
    runs = [r for r in X2._read(plane.path("warehouse", "runs.json")).get("runs") or [] if isinstance(r, dict) and r.get("source")]
    last: dict[str, str] = {}
    for r in runs:
        day = str(r.get("ended") or r.get("started") or "")[:10]
        if day > last.get(r["source"], ""):
            last[r["source"]] = day
    if not last:
        return []
    newest = max(last.values())
    return [{"id": f"stopped:{s}", "kind": "source", "text": f"{s.removeprefix('v1_').split('__')[0]}: no file since {X2._day(d) or d}.",
             "href": "/centre/build/ops"} for s, d in sorted(last.items()) if d and d < newest]


def _map_notes(plane, viewer) -> list[dict]:
    from sh_platform.graph.read import graph_for
    try:
        from sh_platform.graph.hooks import rebuild_if_dirty
        rebuild_if_dirty(plane)
    except Exception:  # noqa: BLE001
        pass
    seen = {n["id"]: n["label"] for n in graph_for(plane, viewer)["nodes"] if not n.get("restricted")}
    try:
        notes = read_json_strict(plane.path("graph", "comments.json"), dict) or {}
    except (OSError, ValueError):
        return []
    return [{"id": f"note:{c.get('id')}", "kind": "map_note", "text": f"A note on {seen[nid]}: {str(c.get('text') or '')[:160]}",
             "href": "/centre/intent/graph"}
            for nid, items in notes.items() if nid in seen and isinstance(items, list)
            for c in items if isinstance(c, dict) and c.get("state") == "open"]


def _signals(plane) -> list[dict]:
    """What the feeds write to signals/*.json: one item, a list, or {"items": [...]}; an item needs a text (or a title)."""
    root = plane.path("signals")
    out = []
    for f in sorted(root.glob("*.json")) if root.is_dir() else []:
        try:
            got = read_json_strict(f)
        except (OSError, ValueError):
            continue
        items = got.get("items", [got]) if isinstance(got, dict) else got if isinstance(got, list) else []
        for i, s in enumerate(x for x in items if isinstance(x, dict)):
            text = s.get("text") or s.get("title")
            if text:
                out.append({"id": f"signal:{f.stem}:{s.get('id') or i}", "kind": str(s.get("kind") or "market"), "text": str(text)[:200],
                            "href": s.get("href") if str(s.get("href") or "").startswith("/centre/") else None})
    return out


# ---- the page --------------------------------------------------------------------------------------------------------------------

def _compute(plane, viewer) -> dict:
    seats, roles = seat_of(viewer), set(viewer.roles)
    loaded = X2._list(X2._read(plane.path("build", "ops", "loaded.json")), "periods")
    root = plane.path("intents")
    iids = sorted({f.parent.name for pat in ("*/thread.json", "*/sow.json") for f in root.glob(pat)}) if root.is_dir() else []
    projects = _projects(plane)
    def cards():
        from sh_platform.v1 import c1_cards
        return c1_cards.build(plane)
    figures = {i["intent_id"]: i["kpis"] for i in _guard("c1 cards", cards, {"intents": []})["intents"]}

    needs, lines, look = [], [], []
    for iid in iids:
        line, waits = X2._intent(plane, iid, seats, loaded)
        sow = X2._read(plane.path("intents", iid, "sow.json"))
        prj = projects.get(iid) or {}
        pid = prj.get("id")
        on = norm(viewer.name) in _people(prj) and not viewer.shared_name
        comments = _comments(plane, pid) if pid else []
        lvl = G1.level(plane, viewer, prj, comments) if pid else "full" if DECISION_MAKER in seats or sow.get("state") == "signed" else "none"  # G1
        if lvl == "preview":  # Internal and not a member: the lock line (title, stage, owner), no cards
            lines.append({**G1.lock_row(prj, lvl), "pid": pid, "intent_id": iid, "on": False, "href": f"/centre/project/{pid}"})
            continue
        if lvl == "none" or (lvl != "full" and sow.get("state") != "signed"):
            continue  # a project still being talked through is the team's until it is signed
        title = prj.get("title") or line["title"]
        needs += [{"id": w["id"], "kind": w["kind"], "project": title, "pid": pid, "text": w["text"], "action": w["action"],
                   "href": w["href"], "since": w["since"]} for w in waits]
        needs += _comment_cards(pid, title, comments, viewer, iid) if pid else []
        if DATA_ENGINEER in seats and plane.path("build", "mapping", f"{iid}.json").is_file():
            needs += _formula_cards(plane, iid, title)
        src_ids = {s["id"] for s in X2._list(sow, "sources") if s.get("id")}
        kpis = figures.get(iid, [])
        open_c = [c for c in comments if c.get("state") == "open"]
        lines.append({"pid": pid, "intent_id": iid, "title": title, "stage": prj.get("stage") or line["stage"], "on": on,
                      "last_load": _last_load(loaded, src_ids), "daily": _guard("p5 daily", lambda: _daily(plane, pid), None), "moved": _moved(kpis),
                      "open_comments": sum(1 for c in open_c if (c.get("kind") or "comment") == "comment"),
                      "open_tickets": sum(1 for c in open_c if c.get("kind") == "ticket"),
                      "href": f"/centre/project/{pid}" if pid else line["open"]})
        for k in kpis:
            t = k.get("trend") or []
            if len(t) >= 2 and t[-2]["value"] and abs(t[-1]["value"] / t[-2]["value"] - 1) > JUMP or k.get("range_break"):
                look.append({"id": f"jump:{iid}:{k['code']}", "kind": "anomaly", "href": "/centre/consume",
                             "text": f"{k['name']} ({title}) moved to {t[-1]['value']:,.4g} in {t[-1]['period']}, from {t[-2]['value']:,.4g}."
                             if len(t) >= 2 else f"{k['name']} ({title}) is outside its usual range."})

    if OPS_MANAGER in seats:
        look += _guard("runs", lambda: _stopped(plane), [])
    if roles & QUEUE_ROLES:
        def queue():
            from sh_platform.v1 import x5_extract
            q = x5_extract.queue(plane)
            return [{"id": "review-queue", "kind": "document", "text": q["line"] + " in the review queue.", "href": "/centre/extract/review"}] \
                if q.get("count") else []
        look += _guard("x5 queue", queue, [])
    look += _guard("map notes", lambda: _map_notes(plane, viewer), [])
    look += _guard("k2 variants", lambda: __import__("sh_platform.v1.k2_map", fromlist=["pulse_items"]).pulse_items(plane, viewer), [])  # K2
    look += _signals(plane)

    _guard("t2 tickets", lambda: __import__("sh_platform.v1.t2_tickets", fromlist=["extend"]).extend(plane, viewer, needs, look, lines), None)  # T2
    order = list(X2.SEAT_NAMES)
    at = _now()
    return {"name": viewer.name, "seats": [{"id": s, "name": X2.SEAT_NAMES[s]} for s in order if s in seats],
            "may_start": True,  # Round 6: anyone may start a project; the sign-off carries the weight
            "needs_you": {"refreshed": at, "cards": needs}, "projects": {"refreshed": at, "lines": lines},
            "worth_a_look": {"refreshed": at, "items": look}}


def build(plane, viewer) -> dict:
    key = (str(plane.root), viewer.name, viewer.account_id, tuple(sorted(viewer.roles)))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    out = _compute(plane, viewer)
    _cache[key] = (time.monotonic(), out)
    return out
