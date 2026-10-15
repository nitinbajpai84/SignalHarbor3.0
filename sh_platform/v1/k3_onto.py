"""K3 (v5 card V5W-6) The company map as one living ontology.

One graph, read from records already in the plane: people, agents, projects, intents, sources, tables (bronze, silver, gold), definitions,
dashboards, reports, cases and decisions, joined by six labelled relations (owns, feeds, defined by, decided in, raised from, built by).
It reuses `k3_map` (data flow, definitions, health), `p1_project` (projects and their people), `mem_graph` (decisions) and `e4_cases`
(cases); nothing is drawn by hand and everything is filtered by the same access rules those modules apply.

Verified or in progress: anything that belongs to a project is "in progress" until the project is live (complete) AND the head of data has
admitted it from the review queue; the admission (who, when) is kept in graph/verified.json. A rejection keeps the reason and returns the
item to its owner. Things that belong to no project (sources, raw tables, people, agents, cases) are the company's baseline and verified.
A link is solid only when both ends are verified.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import k3_map as K
from sh_platform.v1 import p1_project as P
from sh_platform.v1.seats import seat_of

log = logging.getLogger(__name__)

HEAD_OF_DATA = "head_of_data"  # the seat (sh_platform.v1.seats): head of data, or the company administrator
REL = ("owns", "feeds", "defined by", "decided in", "raised from", "built by")
TYPE_WORDS = {"person": "Person", "agent": "Agent", "project": "Project", "intent": "Intent", "source": "Source", "table": "Table",
              "definition": "Definition", "dashboard": "Dashboard", "report": "Report", "case": "Case", "decision": "Decision"}
AGENTS = (("north", "North", "Intent"), ("span", "Span", "Build"), ("lumen", "Lumen", "Consume"), ("tally", "Tally", "Action"))
STAGE_WORDS = {"talking": "Being defined with North", "signed": "Intent signed", "designed": "Plan approved", "built": "Pipelines verified", "live": "Live"}
STEPS = (("Intent", "Intent signed"), ("Architecture", "Plan approved"), ("Pipelines", "Pipeline verified"), ("Dashboards and delivery", "Dashboard published"))
# layered layout: the column a node sits in, left to right; meaning (definitions, decisions, cases) sits in a band below
COLS = ("People", "Agents", "Projects", "Sources", "Bronze", "Silver", "Gold", "Dashboards and reports")
BAND = {"definition", "decision", "case"}
LENSES = [
    {"id": "flow", "label": "Data flow", "types": ["source", "table", "dashboard", "report", "person"], "rels": ["feeds"]},
    {"id": "process", "label": "Process", "types": ["person", "agent", "project", "intent", "dashboard", "report"], "rels": ["owns", "built by", "raised from"]},
    {"id": "definitions", "label": "Definitions", "types": ["definition", "table", "dashboard", "report", "project"], "rels": ["defined by", "built by"]},
    {"id": "people", "label": "People and decisions", "types": ["person", "agent", "project", "decision", "case"], "rels": ["owns", "decided in", "raised from", "built by"]},
    {"id": "health", "label": "Health", "types": ["source", "table", "dashboard", "report"], "rels": ["feeds"]},
]
_CLOSED = ("resolved", "closed", "approved", "rejected")


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- the verification record ------------------------------------------------------------------------------------------------------

def _vpath(plane):
    return plane.path("graph", "verified.json")


def _store(plane) -> dict:
    got = K._read(_vpath(plane)) or {}
    return {"verified": got.get("verified") or {}, "sent_back": got.get("sent_back") or {}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- building the graph -----------------------------------------------------------------------------------------------------------

def _person_id(name) -> str | None:
    n = " ".join(str(name or "").split())
    return f"person:{n}" if n and not n.startswith(("acc-", "x-")) else None


def _merge_people(nodes: dict, edges: dict) -> None:
    """V6 review: one person, one node. An agent's name ("lumen") is the agent; a first name ("Leo") is the one full name it starts ("Leo Park")."""
    people = [n for n in nodes.values() if n["type"] == "person"]
    agents = {n["label"].lower(): n["id"] for n in nodes.values() if n["type"] == "agent"}
    into: dict[str, str] = {}
    for n in people:
        lab = " ".join(str(n["label"]).split())
        full = [m["id"] for m in people if m is not n and " " not in lab and str(m["label"]).split()[:1] == [lab] and len(str(m["label"]).split()) > 1]
        if lab.lower() in agents:
            into[n["id"]] = agents[lab.lower()]
        elif len(full) == 1:
            into[n["id"]] = full[0]
    for old, new in into.items():
        nodes.pop(old, None)
        for k in [k for k in edges if old in (k[0], k[1])]:
            e = edges.pop(k)
            a, b = (new if x == old else x for x in (k[0], k[1]))
            if a != b and a in nodes and b in nodes:
                edges[(a, b, k[2])] = {**e, "from": a, "to": b}


def build(plane, viewer) -> dict:
    team, store = K._team(viewer), _store(plane)
    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}

    def add(nid: str, typ: str, label: str, **kw) -> dict:
        n = nodes.setdefault(nid, {"id": nid, "type": typ, "layer": None, "label": label, "sub": "", "owner": None, "project_id": None, "at": None,
                                   "health": None, "health_note": None, "steps": {}})
        n.update({k: v for k, v in kw.items() if v not in (None, "")})
        return n

    def link(a: str, b: str, rel: str) -> None:
        if a in nodes and b in nodes and a != b:
            edges[(a, b, rel)] = {"from": a, "to": b, "rel": rel}

    def person(name) -> str | None:
        pid = _person_id(name)
        if pid:
            add(pid, "person", str(name))
        return pid

    for aid, name, centre in AGENTS:
        add(f"agent:{aid}", "agent", name, sub=f"{centre} agent")

    # data flow: sources, tables, dashboards, audience (k3_map already filters by who may see what)
    fl = K.flow(plane, viewer)
    reports = _report_ids(plane, viewer)
    files = {n["id"]: "source:" + n["id"].split(":", 1)[1] for n in fl["nodes"] if n["stage"] == "file"}
    for n in fl["nodes"]:
        st = n["stage"]
        if st == "file":
            continue
        typ = {"source": "source", "dashboard": "dashboard", "person": "person"}.get(st, "table")
        if typ == "dashboard" and n["id"].split(":", 1)[1] in reports:
            typ = "report"
        add(n["id"], typ, n["label"], layer=st if typ == "table" else None, sub=n["note"] or "", owner=n["owner"], at=n["last_load"],
            project_id=n["project_id"])
    for e in fl["edges"]:
        link(files.get(e["from"], e["from"]), files.get(e["to"], e["to"]), "feeds")
    for n in list(nodes.values()):
        if n["owner"] and n["type"] in ("source", "table", "dashboard", "report") and (pid := person(n["owner"])):
            link(pid, n["id"], "owns")

    # projects, their intents, people and builders
    projects = {}
    for p in P.all_projects(plane):
        if G1.may_see_project(plane, viewer, p["id"]) not in ("full", "read"):
            continue
        projects[p["id"]] = p
        pn = f"project:{p['id']}"
        add(pn, "project", p.get("title") or "A project", sub=STAGE_WORDS.get(p["stage"], p["stage"]), project_id=p["id"], owner=(p["people"] or {}).get("sponsor") or (p["people"] or {}).get("raiser"))
        ppl = p.get("people") or {}
        if (who := person(ppl.get("sponsor") or ppl.get("raiser"))):
            link(who, pn, "owns")
        if (who := person(ppl.get("builder"))):
            link(pn, who, "built by")
        if (who := person(ppl.get("head_of_data"))):
            for g in nodes.values():
                if g["project_id"] == p["id"] and g["layer"] == "gold":
                    link(who, g["id"], "owns")
        rank = P.STAGES.index(p["stage"]) if p["stage"] in P.STAGES else 0
        for aid, need in (("north", 0), ("span", 2), ("lumen", 4)):
            if rank >= need:
                link(pn, f"agent:{aid}", "built by")
        iid = p.get("intent_id")
        if iid:
            add(f"intent:{iid}", "intent", p.get("title") or "An intent", sub="Intent of work", project_id=p["id"])
            link(pn, f"intent:{iid}", "raised from")
    for n in list(nodes.values()):
        if n["project_id"] in projects and n["type"] in ("table", "dashboard", "report"):
            link(n["id"], f"project:{n['project_id']}", "built by")

    # definitions (k2) belong to the project that signed them
    try:
        for c in K.definitions(plane, viewer):
            for v in c["variants"]:
                if v.get("hidden"):
                    continue
                did = f"def:{v['id']}"
                pid = v.get("project_id") if v.get("project_id") in projects else None
                add(did, "definition", v["name"], sub=(v.get("definition") or "")[:160], owner=v.get("owner"), at=v.get("signed_on"), project_id=pid)
                if pid:
                    link(f"project:{pid}", did, "defined by")
                    for g in list(nodes.values()):
                        if g["project_id"] == pid and g["type"] in ("table", "dashboard", "report") and g["layer"] in (None, "gold"):
                            link(g["id"], did, "defined by")
    except Exception:  # noqa: BLE001 - the map opens without definitions rather than not at all
        log.warning("the ontology could not read the definitions", exc_info=True)

    _decisions(plane, viewer, nodes, projects, link, add)
    if team:
        _cases(plane, viewer, add, link)
    _health(plane, viewer, nodes, edges)
    _merge_people(nodes, edges)

    # growth: which step of which project brought each item onto the map
    out_projects = []
    for pid, p in projects.items():
        mem = _members(pid, nodes, edges, p)
        out_projects.append(_project_card(plane, p, mem, nodes))

    # verified or in progress
    live = {pid for pid, p in projects.items() if p["stage"] == "live"}
    for n in nodes.values():
        n.update(state="verified", waiting=False, sent_back=None, verified_by=None, verified_at=None)
        if not n["project_id"]:
            continue
        v, sb = store["verified"].get(n["id"]), store["sent_back"].get(n["id"])
        if n["project_id"] in live and v:
            n.update(verified_by=v.get("by"), verified_at=v.get("at"))
        else:
            n.update(state="in_progress", waiting=n["project_id"] in live and not sb, sent_back=sb)
    for e in edges.values():
        e["state"] = "verified" if nodes[e["from"]]["state"] == nodes[e["to"]]["state"] == "verified" else "in_progress"
    for n in nodes.values():
        n["col"] = _col(n)
        n["band"] = n["type"] in BAND
        n["type_word"] = TYPE_WORDS[n["type"]] + (f" - {n['layer']}" if n["layer"] else "")
    ordered = sorted(nodes.values(), key=lambda n: (n["col"], n["band"], str(n["label"]).lower()))
    counts = {t: sum(n["type"] == t for n in ordered) for t in TYPE_WORDS}
    return {"nodes": ordered, "edges": sorted(edges.values(), key=lambda e: (e["from"], e["to"], e["rel"])), "lenses": LENSES, "columns": list(COLS),
            "relations": list(REL), "counts": counts, "projects": sorted(out_projects, key=lambda p: p["title"].lower()),
            "states": {"verified": sum(n["state"] == "verified" for n in ordered), "in_progress": sum(n["state"] == "in_progress" for n in ordered)},
            "waiting": sum(n["waiting"] for n in ordered), "can_review": HEAD_OF_DATA in seat_of(viewer), "team": team}


def _col(n: dict) -> int:
    t = n["type"]
    if t == "person":
        return 0
    if t == "agent":
        return 1
    if t in ("project", "intent"):
        return 2
    if t == "source":
        return 3
    if t == "table":
        return {"bronze": 4, "silver": 5}.get(n["layer"], 6)
    if t in ("dashboard", "report"):
        return 7
    return {"definition": 3, "decision": 5, "case": 7}[t]  # the band below spreads meaning across the width


def _report_ids(plane, viewer) -> set[str]:
    try:
        from sh_platform.v1 import cx_dash
        return {r["id"] for r in cx_dash.company_reports(plane, viewer)}
    except Exception:  # noqa: BLE001
        return set()


def _decisions(plane, viewer, nodes, projects, link, add) -> None:
    """Decisions made in talks (mem_graph, already filtered): decided in the project the talk was about."""
    try:
        from sh_platform.v1 import mem_graph as M
        v = M.view(plane, viewer)
    except Exception:  # noqa: BLE001
        log.warning("the ontology could not read the decisions", exc_info=True)
        return
    by = {n["id"]: n for n in v["nodes"]}
    about: dict[str, str] = {}
    for e in v["edges"]:
        if e["type"] == "about" and e["to"] in by:
            t = e["to"]
            pid = t[8:] if t.startswith("project:") else M._intent_project(plane, t[7:]) if t.startswith("intent:") else None
            if pid in projects:
                about[e["from"]] = pid
    for e in v["edges"]:
        if e["type"] == "decided" and e["from"] in about and e["to"] in by:
            pid = about[e["from"]]
            add(e["to"], "decision", by[e["to"]]["label"], sub="Chosen in a talk", project_id=pid)
            link(e["to"], f"project:{pid}", "decided in")


def _cases(plane, viewer, add, link) -> None:
    """The data team's open and closed cases (e4_cases decides who may see each)."""
    from sh_platform.v1 import e4_cases as E4
    from sh_platform.v1 import wh
    try:
        with wh.connect(plane, read_only=True) as con:
            rows = E4._dicts(con.execute("select * from exceptions order by detected_at desc limit 60"))
            for r in rows:
                if not E4._can_see(plane, viewer, r, con):
                    continue
                cid = f"case:{r['id']}"
                done = str(r.get("status")) in _CLOSED
                add(cid, "case", str(r.get("title") or "A case"), sub=("Closed" if done else "Open"), at=K._iso(r.get("detected_at")))
                link(cid, "agent:tally", "raised from")
    except Exception:  # noqa: BLE001 - no warehouse yet: no cases on the map
        log.warning("the ontology could not read the cases", exc_info=True)


def _health(plane, viewer, nodes, edges) -> None:
    """Source freshness and failures as a colour (data team only), carried to everything downstream."""
    if not K._team(viewer):
        return
    try:
        srcs = K.health(plane, viewer)["sources"]
        bad = {f"source:{s['code']}": ("Late" if s["is_late"] else "Loads not accepted") for s in srcs if s["is_late"] or s["rejected"]}
        ok = {f"source:{s['code']}" for s in srcs}
    except Exception:  # noqa: BLE001
        return
    for sid in ok:
        if sid in nodes:
            nodes[sid]["health"] = "attention" if sid in bad else "ok"
            nodes[sid]["health_note"] = bad.get(sid)
    down: dict[str, list[str]] = {}
    for a, b, rel in edges:
        if rel == "feeds":
            down.setdefault(a, []).append(b)
    for sid, why in bad.items():
        stack, seen = list(down.get(sid, [])), set()
        while stack:
            x = stack.pop()
            if x in seen or x not in nodes:
                continue
            seen.add(x)
            nodes[x]["health"] = nodes[x]["health"] or "affected"
            nodes[x]["health_note"] = nodes[x]["health_note"] or f"Fed by {nodes[sid]['label']}: {why.lower()}"
            stack += down.get(x, [])
    for n in nodes.values():
        if n["type"] in ("table", "dashboard", "report") and n["health"] is None:
            n["health"] = "ok"


# ---- project growth ---------------------------------------------------------------------------------------------------------------

def _members(pid: str, nodes: dict, edges: dict, p: dict) -> dict[str, int]:
    """id -> the step (1-4) that brought it onto the map, for everything this project made or stands on."""
    seed = {n["id"] for n in nodes.values() if n["project_id"] == pid}
    up: dict[str, list[str]] = {}
    for a, b, rel in edges:
        if rel == "feeds":
            up.setdefault(b, []).append(a)
    mem, stack = set(seed), [i for i in seed if nodes[i]["type"] in ("table", "dashboard", "report")]
    while stack:  # what the project's outputs stand on, upstream only
        for u in up.get(stack.pop(), []):
            if u not in mem:
                mem.add(u)
                stack.append(u)
    step: dict[str, int] = {}
    for i in mem:
        n = nodes[i]
        t = n["type"]
        step[i] = (1 if t in ("project", "intent", "definition") else 4 if t in ("dashboard", "report") else 3 if t == "source"
                   else 2 if t in ("table", "decision") else 2)
    ppl = p.get("people") or {}
    keyed = {"raiser": 1, "sponsor": 1, "head_of_data": 2, "builder": 3, "ops": 4}
    for key, s in keyed.items():
        pid_ = _person_id(ppl.get(key))
        if pid_ in nodes:
            step[pid_] = min(step.get(pid_, s), s)
    for a, b, rel in edges:  # audience and owners join with the thing they belong to
        if rel in ("owns", "feeds") and nodes[a]["type"] == "person" and b in step and a not in step:
            step[a] = step[b]
        if rel == "built by" and a == f"project:{pid}" and nodes[b]["type"] == "agent":
            step[b] = {"agent:north": 1, "agent:span": 2, "agent:lumen": 4}.get(b, 1)
    for i, s in step.items():
        nodes[i]["steps"][pid] = s
    return step


def _project_card(plane, p: dict, mem: dict[str, int], nodes: dict) -> dict:
    rank = P.STAGES.index(p["stage"]) if p["stage"] in P.STAGES else 0
    arts = {a["kind"]: a for a in p.get("artefacts") or []}
    when = {1: (arts.get("intent") or {}).get("signed_at"), 2: (arts.get("design") or {}).get("signed_at"),
            3: max((nodes[i]["at"] for i in mem if nodes[i]["layer"] == "gold" and nodes[i]["at"]), default=None),
            4: max((nodes[i]["at"] for i in mem if nodes[i]["type"] in ("dashboard", "report") and nodes[i]["at"]), default=None)}
    steps = [{"n": n, "name": STEPS[n - 1][0], "label": STEPS[n - 1][1], "at": K._iso(when[n]) if n <= rank else None, "reached": n <= rank,
              "added": sum(s == n for s in mem.values())} for n in range(1, 5)]
    ppl = p.get("people") or {}
    return {"id": p["id"], "title": p.get("title") or "A project", "stage": p["stage"], "stage_word": STAGE_WORDS.get(p["stage"], p["stage"]),
            "complete": p["stage"] == "live", "completed_at": steps[3]["at"] if p["stage"] == "live" else None,
            "owner": ppl.get("sponsor") or ppl.get("raiser"), "built_by": ppl.get("builder"), "steps": steps}


# ---- the review queue -------------------------------------------------------------------------------------------------------------

KIND_WORDS = {"project": "Project", "intent": "Intent of work", "definition": "Definition", "dashboard": "Dashboard", "report": "Report",
              "decision": "Decision", "table": "Table", "case": "Case"}


def review(plane, viewer) -> dict:
    """What completed projects made, waiting for the head of data, already admitted, or sent back. The data team reads it; only the head approves."""
    if not K._team(viewer):
        return {"allowed": False, "can_review": False, "projects": [], "totals": {}}
    o = build(plane, viewer)
    store = _store(plane)
    out = []
    for pr in o["projects"]:
        if not pr["complete"]:
            continue
        items = []
        for n in o["nodes"]:
            if n["project_id"] != pr["id"]:
                continue
            st = "approved" if n["state"] == "verified" else "sent_back" if n["sent_back"] else "waiting"
            rec = store["verified"].get(n["id"]) or n["sent_back"] or {}
            items.append({"id": n["id"], "type": n["type"], "kind": KIND_WORDS.get(n["type"], n["type"]) + (f" - {n['layer']}" if n["layer"] else ""),
                          "label": n["label"], "sub": n["sub"], "owner": n["owner"], "at": n["at"], "status": st, "by": rec.get("by"), "decided_at": rec.get("at"),
                          "reason": rec.get("reason")})
        order = {"waiting": 0, "sent_back": 1, "approved": 2}
        items.sort(key=lambda i: (order[i["status"]], i["kind"], i["label"].lower()))
        out.append({**{k: pr[k] for k in ("id", "title", "owner", "built_by", "completed_at")}, "items": items, "mine": _built(viewer, pr["built_by"]),
                    "counts": {s: sum(i["status"] == s for i in items) for s in order}})
    tot = {s: sum(p["counts"][s] for p in out) for s in ("waiting", "sent_back", "approved")}
    return {"allowed": True, "can_review": o["can_review"], "projects": out, "totals": tot}


def _head(viewer) -> None:
    if HEAD_OF_DATA not in seat_of(viewer):
        raise Refused(403, "Only the head of data admits items to the verified map.")


def _built(viewer, builder) -> bool:
    """Maker never checker: the person who built the project may not admit or send back what it made."""
    return G1._me(builder, viewer)


def _not_maker(plane, viewer, items) -> None:
    builders = {p["id"]: (p.get("people") or {}).get("builder") for p in P.all_projects(plane)}
    if any(_built(viewer, builders.get(n["project_id"])) for n in items):
        raise Refused(403, "You built this project, so another person has to review what it made.")


def _waiting(plane, viewer) -> dict[str, dict]:
    o = build(plane, viewer)
    done = {p["id"] for p in o["projects"] if p["complete"]}
    return {n["id"]: n for n in o["nodes"] if n["project_id"] in done and n["state"] == "in_progress"}


def approve(plane, viewer, ids: list[str]) -> dict:
    """Admit the chosen items of completed projects into the verified map, recording who and when."""
    _head(viewer)
    ids = [str(i) for i in dict.fromkeys(ids or [])][:200]
    if not ids:
        raise Refused(400, "Choose at least one item to approve.")
    pending = _waiting(plane, viewer)
    bad = [i for i in ids if i not in pending]
    if bad:
        raise Refused(409, "Some of those items are not waiting for review any more. Reload and try again.")
    _not_maker(plane, viewer, [pending[i] for i in ids])
    at, by = _now(), viewer.name
    plane.path("graph").mkdir(parents=True, exist_ok=True)
    with lock_for(plane.path("graph")):
        st = _store(plane)
        for i in ids:
            st["verified"][i] = {"by": by, "at": at, "project_id": pending[i]["project_id"], "label": pending[i]["label"], "type": pending[i]["type"]}
            st["sent_back"].pop(i, None)
        write_json_atomic(_vpath(plane), st)
    return {"approved": ids, "by": by, "at": at}


def reject(plane, viewer, item_id: str, reason: str) -> dict:
    _head(viewer)
    reason = " ".join(str(reason or "").split())[:500]
    if not reason:
        raise Refused(400, "Say why, so the owner knows what to change.")
    pending = _waiting(plane, viewer)
    if item_id not in pending:
        raise Refused(409, "That item is not waiting for review any more. Reload and try again.")
    _not_maker(plane, viewer, [pending[item_id]])
    at, by = _now(), viewer.name
    plane.path("graph").mkdir(parents=True, exist_ok=True)
    with lock_for(plane.path("graph")):
        st = _store(plane)
        st["verified"].pop(item_id, None)
        st["sent_back"][item_id] = {"by": by, "at": at, "reason": reason, "project_id": pending[item_id]["project_id"], "label": pending[item_id]["label"]}
        write_json_atomic(_vpath(plane), st)
    return {"sent_back": item_id, "by": by, "at": at, "reason": reason}
