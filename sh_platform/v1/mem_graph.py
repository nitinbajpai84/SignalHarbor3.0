"""The context map (MEM2a, Nitin 9 Oct): what people talk about with the agents, as a graph on the company map's ids, plus the memory vectors.

Nodes: person, agent, conversation, summary, topic, project, intent, case, dashboard, tile, table, definition, document, decision, question.
Edges: talked_with, about, mentions, decided, asked, refers_to, supersedes, same_as. Entities that already live on the company map keep THEIR id
(`table:<name>` as i5_graph.table_id, `measure:<code>`, `concept:...`, `intent:<iid>`), so this is the same graph seen from the talk side, not a
second one; `add_conversation_nodes(g, plane)` is the one-line hook for `build.rebuild` if the talk should also be drawn there.

Program first: ids (project, intent, dashboard, tile), table names, the company map's own labels and the company's people are recognised by rules
(`entities`); the model only proposes topic labels, in mem_summary, through the egress client.

Access: every edge carries `src`, the scope of the conversation or summary that made it (`scopes`: owner + project). A viewer sees an edge when
they own the scope or may read its project (G1); a node is seen only through a seen edge or a seen scope, so a hidden talk reveals no topic.
Files (data/<company>/memory/v1/ctx/graph.json); vectors in index/docs.sqlite beside doc_index's tables (`mem_vec`, `mem_fts`)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import numpy as np

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import doc_embed, doc_index
from sh_platform.v1 import mem_agent as MEM
from sh_platform.v1.i5_graph import table_id

log = logging.getLogger(__name__)
EDGES = ("talked_with", "about", "mentions", "decided", "asked", "refers_to", "supersedes", "same_as")
VERB = {"talked_with": "talked with", "about": "was about", "mentions": "mentions", "decided": "decided", "asked": "asked", "refers_to": "refers to",
        "supersedes": "replaces", "same_as": "is the same as"}
OBJECTS = ("project", "intent", "case", "dashboard", "tile", "table")  # the focus keys an agent passes (mem_agent's focus dict)
KIND = {"Measure": "definition", "Concept": "definition", "Definition": "definition", "Term": "definition", "Table": "table", "Document": "document",
        "Decision": "decision"}
_IDS = (("project", r"\bprj-[0-9a-f]{8}\b"), ("dashboard", r"\bdash-[0-9a-f]{8}\b"), ("tile", r"\bt-[0-9a-f]{6}\b"), ("intent", r"\bint-[A-Za-z0-9_-]{1,40}\b"))
_TABLE = re.compile(r"\b(?:bronze|silver|gold|raw)_[a-z0-9_]{3,}\b")
MAX_GAZ = 400
# LQ-4: the landing talk (talk.py's "company" conversation: a person with Span or Lumen outside any project) is one-to-one. It may be linked to
# a project it named, but its summary and map edges stay the owner's own: never shared with the project's team
LANDING_CONVO = "company"


def is_private(convo: str | None) -> bool:
    return convo == LANDING_CONVO


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def owner_of(viewer) -> str:
    w = MEM.who(viewer)
    return MEM._h(w) if w else ""


def _path(plane):
    return plane.path("memory", "v1", "ctx", "graph.json")


def _load(plane) -> dict:
    d = read_json_strict(_path(plane), dict) or {}
    return {"nodes": d.get("nodes") or {}, "edges": d.get("edges") or [], "scopes": d.get("scopes") or {}, "at": d.get("at")}


def _mutate(plane, fn) -> None:
    p = _path(plane)
    p.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(p):
        g = _load(plane)
        fn(g)
        g["at"] = _now()
        write_json_atomic(p, g)


def _node(g: dict, id: str, type: str, label: str, scope: str | None = None) -> str:
    n = g["nodes"].setdefault(id, {"id": id, "type": type, "label": str(label)[:80]})
    if scope:
        n["scope"] = scope
    return id


def _edge(g: dict, a: str, b: str, type: str, src: str) -> None:
    e = {"from": a, "to": b, "type": type, "src": src}
    if a != b and e not in g["edges"]:  # ponytail: linear scan; index by (from, to, type, src) if one company passes ~50k edges
        g["edges"].append(e)


# ---- who may see what ---------------------------------------------------------------------------------------------------------

def may_project(plane, viewer, pid: str) -> bool:
    from sh_platform.v1 import g1_access
    try:
        return g1_access.may_see_project(plane, viewer, pid) in ("full", "read")
    except Exception:  # noqa: BLE001 - fail closed
        return False


def visible(plane, viewer, owner: str, project: str | None, cache: dict | None = None) -> bool:
    """The owner of a talk, anyone for a company item ("*"), and the people who may read the talk's project."""
    if owner == "*" or (owner and owner == owner_of(viewer)):
        return True
    if not project:
        return False
    cache = {} if cache is None else cache
    if project not in cache:
        cache[project] = may_project(plane, viewer, project)
    return cache[project]


# ---- recognising things (the program, not the model) --------------------------------------------------------------------------

def _gazetteer(plane) -> list[tuple[str, dict, str]]:
    """(normalised label, node, kind) of the company map's own definitions, tables, documents and decisions. A restricted node is never used."""
    try:
        raw = read_json_strict(plane.path("graph", "company.json"), dict) or {}
    except (OSError, ValueError):
        return []
    out = [(norm(n.get("label")), n, KIND[n["type"]]) for n in raw.get("nodes", []) if n.get("type") in KIND and n.get("restricted_to") is None]
    return [x for x in out if len(x[0]) >= 4][:MAX_GAZ]


def _plain(table: str) -> str:
    """A table name in plain words for a screen: no layer prefix, no underscores."""
    return re.sub(r"^(?:bronze|silver|gold|raw)_", "", table).replace("_", " ").capitalize()


def _project_label(plane, pid: str) -> str:
    from sh_platform.v1 import p1_project
    try:
        return p1_project.read(plane, pid).get("title") or pid
    except Exception:  # noqa: BLE001
        return pid


def _intent_project(plane, iid: str) -> str | None:
    from sh_platform.v1 import p1_project
    try:
        return (p1_project.for_intent(plane, iid) or {}).get("id")
    except Exception:  # noqa: BLE001
        return None


def entities(plane, text: str, viewer=None) -> list[dict]:
    """[{id, type, label}] named in the words: project/dashboard/tile/intent ids, table names, the company map's own labels, the company's people.
    A project or intent the viewer may not read is left out; a restricted node or person is never named."""
    text = str(text or "")
    low, seen, out = " " + norm(text) + " ", set(), []

    def add(id, type, label):
        if id not in seen:
            seen.add(id)
            out.append({"id": id, "type": type, "label": str(label)[:80]})
    for kind, rx in _IDS:
        for m in re.finditer(rx, text):
            v = m.group(0)
            if kind == "project":
                if viewer is None or may_project(plane, viewer, v):
                    add(f"project:{v}", "project", _project_label(plane, v))
            elif kind == "intent":
                pid = _intent_project(plane, v)
                if pid is None or viewer is None or may_project(plane, viewer, pid):
                    add(f"intent:{v}", "intent", v)
            else:
                add(f"{kind}:{v}", kind, f"{kind.title()} {v}")
    names = _TABLE.findall(text.lower())
    real = known_tables(plane) if names else set()
    for t in names:
        if t in real:  # SS-2: a table-like word that is not a table of this company ("gold_exfil" in a planted note) is never a node
            add(table_id(t), "table", _plain(t))
    for lab, n, kind in _gazetteer(plane):
        if f" {lab} " in low:
            add(n["id"], kind, n["label"])
    try:
        from sh_platform.memory import filters
        terms = filters.restricted_terms(plane)
        me = norm(getattr(viewer, "name", "")) if viewer else ""
        for name in filters.person_names(plane):
            if len(name) >= 3 and norm(name) != me and f" {norm(name)} " in low and filters.allowed(name, terms):
                add("named:" + norm(name).replace(" ", "-"), "person", name)
    except Exception:  # noqa: BLE001 - without the people list or the restricted names no person is named
        log.warning("people could not be recognised")
    return out


def known_tables(plane) -> set[str]:
    """The table names of this company's model: the shared catalogue and the registered bronze and gold tables (empty when unreadable:
    then no table word becomes a node)."""
    try:
        from sh_platform.v1 import e0a_catalogue as E
        return {t["name"] for t in E.current(plane)["tables"]} | set(E._registry(plane))
    except Exception:  # noqa: BLE001
        return set()


def focus_ids(plane, focus: dict | None) -> list[dict]:
    """The nodes the focus object names: {project: pid, case: id, tile: id, ...} -> [{id, type, label}]."""
    out = []
    for k in OBJECTS:
        v = (focus or {}).get(k)
        if not isinstance(v, str) or not v:
            continue
        out.append({"id": table_id(v) if k == "table" else f"{k}:{v}", "type": k,
                    "label": _project_label(plane, v) if k == "project" else _plain(v) if k == "table" else f"{k.title()} {v}"})
    return out


# ---- writing the map ----------------------------------------------------------------------------------------------------------

def _scope(g: dict, plane, viewer, src: str, ctx: dict | None, convo: str | None = None) -> None:
    pid = None if is_private(convo) else (ctx or {}).get("project")  # LQ-4: a landing talk's scope is its owner only
    g["scopes"].setdefault(src, {"owner": owner_of(viewer), "project": pid if isinstance(pid, str) and may_project(plane, viewer, pid) else None})


def _actors(g: dict, viewer, agent: str, src: str) -> str:
    me = _node(g, "person:" + owner_of(viewer), "person", getattr(viewer, "name", "") or "Someone")
    _edge(g, me, _node(g, "agent:" + agent, "agent", MEM.NAMES.get(agent, agent)), "talked_with", src)
    return me


def note_turn(plane, viewer, agent: str, convo: str, text: str, ctx: dict | None = None) -> str | None:
    """A turn happened: the person talked with the agent, the talk is about the focus objects and mentions what the words name. Returns the talk's scope id."""
    if not owner_of(viewer):
        return None
    src = "c-" + MEM._h(f"{agent}|{MEM.who(viewer)}|{convo}")
    ents, objs = entities(plane, text, viewer), focus_ids(plane, ctx)

    def go(g):
        _scope(g, plane, viewer, src, ctx, convo)
        _actors(g, viewer, agent, src)
        c = _node(g, "convo:" + src, "conversation", f"Talk with {MEM.NAMES.get(agent, agent)}", src)
        for o in objs:
            _edge(g, c, _node(g, o["id"], o["type"], o["label"]), "about", src)
        for e in ents:
            _edge(g, c, _node(g, e["id"], e["type"], e["label"]), "mentions", src)
    _mutate(plane, go)
    return src


def add_summary(plane, viewer, s: dict, ents: list[dict]) -> None:
    """A summary (mem_summary's record) joins the map: refers to its talk, is about the focus objects and topics, mentions entities, decided,
    asked (open questions), and replaces the earlier summary of the same talk."""
    src, sid = s["id"], "summary:" + s["id"]
    talk = "c-" + MEM._h(f"{s['agent']}|{MEM.who(viewer)}|{s['convo']}")
    objs = focus_ids(plane, s.get("ctx"))

    def go(g):
        _scope(g, plane, viewer, src, s.get("ctx"), s.get("convo"))
        me = _actors(g, viewer, s["agent"], src)
        n = _node(g, sid, "summary", s["about"] or "A talk", src)
        _edge(g, me, n, "talked_with", src)
        _edge(g, n, _node(g, "convo:" + talk, "conversation", f"Talk with {MEM.NAMES.get(s['agent'], s['agent'])}", talk), "refers_to", src)
        for o in objs:
            _edge(g, n, _node(g, o["id"], o["type"], o["label"]), "about", src)
        for e in ents:
            _edge(g, n, _node(g, e["id"], e["type"], e["label"]), "mentions", src)
        for t in s.get("topics") or []:
            tn = _node(g, "topic:" + norm(t).replace(" ", "-"), "topic", t)
            _edge(g, n, tn, "about", src)
            for e in ents:  # a topic that is the company map's own word is the same thing
                if norm(e["label"]) == norm(t):
                    _edge(g, tn, e["id"], "same_as", src)
        for i, d in enumerate(s.get("decisions") or []):
            _edge(g, n, _node(g, f"decision:{s['id']}-{i}", "decision", d), "decided", src)
        for i, q in enumerate(s.get("open") or []):
            _edge(g, n, _node(g, f"question:{s['id']}-{i}", "question", q), "asked", src)
        if s.get("replaces"):
            _edge(g, n, "summary:" + s["replaces"], "supersedes", src)
    _mutate(plane, go)


def drop(plane, sid: str) -> None:
    """Forget a summary: its node, its edges, the things only it made, its scope and its vectors."""
    def go(g):
        g["edges"] = [e for e in g["edges"] if e["src"] != sid]
        g["scopes"].pop(sid, None)
        for k in [k for k in g["nodes"] if k == "summary:" + sid or k.startswith((f"decision:{sid}-", f"question:{sid}-"))]:
            del g["nodes"][k]
        used = {x for e in g["edges"] for x in (e["from"], e["to"])}
        for k in [k for k, n in g["nodes"].items() if k not in used and not n.get("scope")]:
            del g["nodes"][k]
        for k in [k for k, n in g["nodes"].items() if n.get("scope") and k not in used and n["scope"] not in g["scopes"]]:
            del g["nodes"][k]
    if _path(plane).is_file():
        _mutate(plane, go)
    drop_vec(plane, sid)


# ---- reading the map (access-filtered) ----------------------------------------------------------------------------------------

def view(plane, viewer) -> dict:
    """{built_at, nodes: [{id, type, label}], edges: [{from, to, type}]} as this viewer may see it."""
    g, cache = _load(plane), {}

    def ok(src):
        s = g["scopes"].get(src)
        return bool(s) and visible(plane, viewer, s["owner"], s.get("project"), cache)

    def readable(id):
        """A shared talk can name a project (or an intent of one) the viewer may not read: that node and its edges stay hidden (review MEM2a)."""
        pid = id[8:] if id.startswith("project:") else _intent_project(plane, id[7:]) if id.startswith("intent:") else None
        if pid is None:
            return True
        if pid not in cache:
            cache[pid] = may_project(plane, viewer, pid)
        return cache[pid]
    # AQF10-07: a talk shows its latest summary only; an earlier version (the target of a supersedes edge) stays in the file for history and
    # for forgetting the whole chain, but neither it nor the decisions and questions only it holds are drawn
    old = {e["to"] for e in g["edges"] if e["type"] == "supersedes"}
    edges = [e for e in g["edges"] if ok(e["src"]) and readable(e["from"]) and readable(e["to"]) and e["from"] not in old and e["to"] not in old]
    ids = {x for e in edges for x in (e["from"], e["to"])} | {k for k, n in g["nodes"].items() if n.get("scope") and ok(n["scope"]) and k not in old}
    nodes = [{k: n[k] for k in ("id", "type", "label")} for k, n in g["nodes"].items() if k in ids]
    return {"built_at": g["at"], "nodes": nodes, "edges": [{k: e[k] for k in ("from", "to", "type")} for e in edges if e["from"] in ids and e["to"] in ids]}


def neighbours(plane, viewer, seeds: list[str], hops: int = 2) -> dict:
    """The seen part of the map within `hops` of the seed ids."""
    v = view(plane, viewer)
    near, frontier = set(seeds), set(seeds)
    for _ in range(hops):
        step = {x for e in v["edges"] for a, b in ((e["from"], e["to"]), (e["to"], e["from"])) if a in frontier for x in (b,)} - near
        near |= step
        frontier = step
    by = {n["id"]: n for n in v["nodes"]}
    return {"nodes": [by[i] for i in near if i in by], "edges": [e for e in v["edges"] if e["from"] in near and e["to"] in near]}


def sentences(nodes: list[dict], edges: list[dict], limit: int = 12) -> list[str]:
    """Edges as plain sentences for a prompt (strings only). Plumbing (talk to summary) is left out."""
    by = {n["id"]: n["label"] for n in nodes}
    out = []
    for e in edges:
        if e["type"] == "refers_to" or e["from"] not in by or e["to"] not in by:
            continue
        line = f"{by[e['from']]} {VERB[e['type']]} {by[e['to']]}"
        if line not in out:
            out.append(line)
    return out[:limit]


# ---- vectors: summaries and memory items, beside doc_index's passages -------------------------------------------------------

_VSCHEMA = """
create table if not exists mem_vec(id text primary key, kind text, owner text, project text, text text, model text, vec blob);
create virtual table if not exists mem_fts using fts5(text, id unindexed, tokenize='porter unicode61');
"""


def _con(plane):
    con = doc_index._db(plane)
    con.executescript(_VSCHEMA)
    return con


def _embed(texts: list[str]) -> list[bytes | None]:
    try:
        return [v.tobytes() for v in doc_embed.embed(texts)]
    except Exception:  # noqa: BLE001 - Unavailable or any failure: words only, embedded at a later search
        return [None] * len(texts)


def index_text(plane, id: str, kind: str, owner: str, project: str | None, text: str) -> None:
    """Store a summary or a memory item for words and meaning search. Idempotent per id."""
    vec = _embed([text])[0]
    with lock_for(plane.path("index", "docs.sqlite")):
        con = _con(plane)
        try:
            with con:
                con.execute("delete from mem_fts where id=?", (id,))
                con.execute("insert or replace into mem_vec values(?,?,?,?,?,?,?)", (id, kind, owner, project, text, doc_embed.MODEL if vec else "", vec))
                con.execute("insert into mem_fts(text, id) values(?,?)", (text, id))
        finally:
            con.close()


def drop_vec(plane, *ids: str) -> None:
    if not plane.path("index", "docs.sqlite").is_file():
        return
    with lock_for(plane.path("index", "docs.sqlite")):
        con = _con(plane)
        try:
            with con:
                for i in ids:
                    con.execute("delete from mem_vec where id=?", (i,))
                    con.execute("delete from mem_fts where id=?", (i,))
        finally:
            con.close()


def indexed(plane, kind: str, owner: str | None = None) -> set[str]:
    if not plane.path("index", "docs.sqlite").is_file():
        return set()
    con = _con(plane)
    try:
        q, a = "select id from mem_vec where kind=?", [kind]
        if owner is not None:
            q, a = q + " and owner=?", a + [owner]
        return {r[0] for r in con.execute(q, a)}
    finally:
        con.close()


def search(plane, query: str, ok, limit: int = 6) -> list[dict]:
    """Words (BM25) and meaning (vectors) merged by reciprocal rank, as doc_index does: [{id, kind, text, how}]. `ok(owner, project, kind)` is the
    access filter and is applied BEFORE ranking, so a hidden row never takes a place."""
    if not str(query).strip() or not plane.path("index", "docs.sqlite").is_file():
        return []
    con = _con(plane)
    try:
        rows = {r[0]: r for r in con.execute("select id, kind, owner, project, text, model, vec from mem_vec") if ok(r[2], r[3], r[1])}
        if not rows:
            return []
        q = doc_index._match(query)
        words = [r[0] for r in con.execute("select id from mem_fts where mem_fts match ? order by bm25(mem_fts) limit ?", (q, limit * 4))
                 if r[0] in rows] if q else []
        # a row stored while the model was away is embedded now
        todo = [r for r in rows.values() if not r[6] or r[5] != doc_embed.MODEL]
    finally:
        con.close()
    if todo:
        new = _embed([r[4] for r in todo])
        if any(new):
            with lock_for(plane.path("index", "docs.sqlite")):
                c2 = _con(plane)
                try:
                    with c2:
                        for r, v in zip(todo, new):
                            if v:
                                c2.execute("update mem_vec set vec=?, model=? where id=?", (v, doc_embed.MODEL, r[0]))
                                rows[r[0]] = (*r[:5], doc_embed.MODEL, v)
                finally:
                    c2.close()
    meaning: list[str] = []
    have = [r for r in rows.values() if r[6] and r[5] == doc_embed.MODEL]
    if have:
        try:
            qv = doc_embed.embed([query], query=True)[0]
            ok_ = [r for r in have if len(r[6]) == qv.nbytes]
            if ok_:
                sims = np.frombuffer(b"".join(r[6] for r in ok_), dtype=np.float32).reshape(len(ok_), -1) @ qv
                meaning = [ok_[i][0] for i in np.argsort(-sims)[:limit * 3] if sims[i] >= doc_index.MIN_COS]
        except Exception:  # noqa: BLE001 - meaning search is optional
            log.warning("meaning search of the memory failed; using words only")
    score: dict[str, float] = {}
    for ranked in (words, meaning):
        for r, k in enumerate(ranked):
            score[k] = score.get(k, 0.0) + 1.0 / (doc_index.RRF_K + r + 1)
    return [{"id": k, "kind": rows[k][1], "text": rows[k][4], "how": "both" if k in words and k in meaning else "meaning" if k in meaning else "words"}
            for k in sorted(score, key=lambda k: -score[k])[:limit]]


def sync_items(plane, viewer) -> None:
    """Index the viewer's live memory items and the company's; purge vectors of items that are no longer live (forgotten elsewhere too)."""
    me = owner_of(viewer)
    live = {}
    try:
        if me:
            live.update({i["id"]: (me, i["text"]) for i in MEM.mine(plane, viewer)})
        live.update({i["id"]: ("*", i["text"]) for i in MEM.company_items(plane)})
    except Exception:  # noqa: BLE001
        log.warning("memory items could not be indexed")
        return
    have = indexed(plane, "item", me) | indexed(plane, "item", "*")
    for i, (o, t) in live.items():
        if i not in have and t:
            index_text(plane, i, "item", o, None, t)
    drop_vec(plane, *[i for i in have - set(live)])


def add_conversation_nodes(g, plane, people: dict | None = None) -> None:
    """Hook for `build.rebuild`: draw the talk on the company graph too. Only what the company may see: the agents and the things talked about,
    never who said what (the person-level map stays behind /api/v1/memory/graph, filtered per viewer). Not wired; see docs/plan/v4-landings/MEM2a.md."""
    from sh_platform.graph import models
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "Agent", "Topic")))
    for n in _load(plane)["nodes"].values():
        if n["type"] in ("agent", "topic"):
            g.node(n["id"], n["type"].title(), n["label"], [{"mark": "stated", "by": "the talk with the agents", "at": None, "from": None}], "consume")
