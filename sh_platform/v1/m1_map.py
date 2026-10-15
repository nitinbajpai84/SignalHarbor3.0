"""M1 The company map: the ontology that grows underneath every conversation, shown to everyone, built from records only.

`add_company_map_nodes(g, plane, people)` is called by `sh_platform.graph.build.rebuild` (one line, after I5's `add_sow_nodes`). It reads
the 1.0 records by path and writes nothing: the intent of work (goal, process, KPIs, sources and documents read, catalogue, rules, settled
points, signatures), the thread and the other agents' conversations (who was spoken to), the design approval (A1), the mapping sheet (B3),
the Loaded confirmations (B5), the consumption brief (C3) and the company glossary. Every record may be absent; a damaged one is skipped.

Every node carries where it came from: `said_by`, `from_file` or `from_record`, `at`, a one-sentence `what`, and `intents` (the intent
clusters it belongs to). A KPI with no source is never guessed: it gets a dashed "no source yet" stub (type Gap) that says why.

`touch(plane)` marks the graph dirty and rebuilds it in the background; other cards may call it after a write (guarded import).
`ask(nodes, q)` matches a phrase against names, plain definitions and document text.
"""
from __future__ import annotations

import logging
import re
from contextlib import suppress

from modules.m2_baseline.domain.catalogue import match_name
from sh_platform.graph import models
from sh_platform.jsonfile import read_json_strict
from sh_platform.v1 import i5_graph

log = logging.getLogger(__name__)
NEW_TYPES = ("Intent", "Table", "Document", "Signed", "View", "Gap", "Concept", "Definition")
EDGES = ("asked_for", "spoke_to", "owns", "does", "uses", "feeds", "defined_in", "derived_from", "signed_by", "shown_in",
         "governed_by", "supersedes", "step_of", "decided_by", "variant_of")


def _register() -> None:
    i5_graph._register()
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, *NEW_TYPES)))
    every = list(models.NODE_TYPES)
    for e in EDGES:  # the map's edges join any two kinds; an existing edge type keeps its own ends and gains the rest
        src, dst = models.EDGE_TYPES.setdefault(e, ([], []))
        src.extend(t for t in every if t not in src)
        dst.extend(t for t in every if t not in dst)


def touch(plane) -> None:
    """Mark the company map for a rebuild and start it in the background. Never raises: a map must not undo the write before it."""
    try:
        from sh_platform.graph import hooks
        hooks.mark_dirty(plane)
        if plane.path("graph", "company.json").exists():
            hooks._background(plane)
    except Exception:  # noqa: BLE001
        log.warning("the company map could not be refreshed")


def _rd(plane, *parts: str):
    try:
        return read_json_strict(plane.path(*parts), dict) or {}
    except (OSError, ValueError):
        log.warning("a record could not be read for the company map")
        return {}


def _slug(text) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _s(v) -> str:
    return "; ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v)).strip()


class _Map:
    """One intent's pass over the graph: puts nodes with their origin, joins them, remembers people's roles."""

    def __init__(self, g, people: dict, iid: str, title: str):
        from sh_platform.graph.build import _person, _prov
        self.g, self.people, self.iid, self.title, self._person, self._prov = g, people, iid, title, _person, _prov
        self.short = title if len(title) <= 60 else title[:57].rstrip() + "…"

    def put(self, nid: str, type_: str, label: str, what: str = "", said_by: str = "", record: str = "", file: str = "", at=None,
            room: str = "intent", **info) -> str:
        prov = self._prov(by=said_by or "the record", src=file or record, at=at)
        self.g.node(nid, type_, str(label)[:160] or type_, prov, room)
        n = self.g.nodes[nid]
        for k, v in (("what", what), ("said_by", said_by), ("from_record", record), ("from_file", file), ("at", at), *info.items()):
            if v not in (None, "", [], {}) and not n.get(k):
                n[k] = v
        if self.iid not in n.setdefault("intents", []):
            n["intents"].append(self.iid)
        return nid

    def link(self, a: str | None, b: str | None, type_: str, said_by: str = "", record: str = "", at=None) -> None:
        if a and b and a != b:
            self.g.edge(a, b, type_, self._prov(by=said_by or "the record", src=record, at=at))

    def person(self, name, role: str, record: str, at=None) -> str | None:
        name = _s(name)
        if not name or name.lower() in ("decision maker", "north", "span", "flow", "lumen", "nira"):
            return None
        pid = self._person(self.g, self.people, name, self._prov(by=name, src=record, at=at), "intent")
        if pid:
            n = self.g.nodes[pid]
            line = f"{role} in {self.short}"
            if line not in n.setdefault("roles", []):
                n["roles"].append(line)
            n.setdefault("what", f"{n['label']}, a person this company's agents have spoken to or heard of.")
            if self.iid not in n.setdefault("intents", []):
                n["intents"].append(self.iid)
        return pid

    def who(self, name, role: str, record: str, at=None) -> str | None:
        """A person when the name is a person we know or a full name; a team otherwise ("Operations", "The investment committee")."""
        name = _s(name)
        if not name:
            return None
        if _slug(name) in self.people or (len(name.split()) in (2, 3) and all(w[:1].isupper() for w in name.split()) and not name.lower().startswith("the ")):
            return self.person(name, role, record, at)
        return self.put(f"team:{_slug(name)}", "Team", name, f"{name}, a team or group named in {self.title}.", record=record, at=at)


def _talkers(plane, iid: str) -> list[tuple[str, str, str, str]]:
    """(name, role, record, at) of every person who spoke in a conversation about this intent."""
    out = []
    for parts, role in ((("intents", iid, "thread.json"), "spoke to North"),
                        (("build", "blueprint_conversation", f"{iid}.json"), "architect"), (("build", "engineer", f"{iid}.json"), "data engineer"),
                        (("consume", "chat", f"{iid}.json"), "consumer")):
        rec = _rd(plane, *parts)
        for t in (rec.get("turns") or rec.get("posts") or []):
            if isinstance(t, dict) and t.get("by") == "person" and t.get("name"):
                out.append((str(t["name"]), role, "/".join(parts), t.get("at")))
    return out


def _state(plane, iid: str, sow: dict, loaded: set[str]) -> str:
    if (_rd(plane, "consume", "brief", f"{iid}.json").get("views")) and loaded:
        return "live"
    if loaded:
        return "loaded"
    if _rd(plane, "build", "blueprint_conversation", f"{iid}.json").get("state") == "approved" or plane.path("build", "design", f"{iid}.json").is_file():
        return "designed"
    return "signed" if sow.get("state") == "signed" else "talking"


def add_company_map_nodes(g, plane, people: dict | None = None) -> None:
    _register()
    people = {} if people is None else people
    loaded_rows = [p for p in _rd(plane, "build", "ops", "loaded.json").get("periods") or [] if isinstance(p, dict)]
    terms = [t for t in _rd(plane, "glossary", "company-terms.json").get("terms") or [] if isinstance(t, dict)]
    sows = i5_graph._sows(plane)
    names: dict[str, set] = {}
    for _, sow in sows:
        for k in sow.get("kpis") or []:
            if isinstance(k, dict) and k.get("code"):
                names.setdefault(str(k["code"]), set()).add(match_name(k.get("name") or k["code"]))
    shared = {c for c, n in names.items() if len(n) > 1}
    _drop_shared_measures(g, shared)
    for iid, sow in sows:
        try:
            _intent(g, plane, people, iid, sow, loaded_rows, terms, shared)
            with suppress(Exception):  # G1: a restricted project's nodes are the team's
                from sh_platform.v1 import g1_access
                g1_access.restrict_nodes(g, plane, iid)
        except Exception:  # noqa: BLE001 - one damaged intent never empties the whole map
            log.exception("an intent could not be drawn on the company map")
    try:  # K2: the concepts and definitions of the signed intents of work
        from sh_platform.v1 import k2_map
        k2_map.add_nodes(g, plane, people)
    except Exception:  # noqa: BLE001 - the rest of the map stands without them
        log.exception("the concepts could not be drawn on the company map")


def _drop_shared_measures(g, shared: set[str]) -> None:
    """I5 keys a KPI by its code alone, so a K01 that means different things in two intents became one node. Such a code is redrawn per
    intent as `measure:<iid>:<code>`; I5's merged node goes when only 1.0 intents of work drew it (a measure a 2.0 record names stays)."""
    gone = {nid for nid, n in g.nodes.items() if n["type"] == "Measure" and nid in {f"measure:{c}" for c in shared} and n["provenance"]
            and all(str(p.get("from") or "").startswith("intents/") for p in n["provenance"])}
    for nid in gone:
        del g.nodes[nid]
    for k in [k for k in g.edges if k[0] in gone or k[1] in gone]:
        del g.edges[k]


def _intent(g, plane, people, iid: str, sow: dict, loaded_rows: list, terms: list, shared: set[str]) -> None:
    goal = sow.get("goal") or {}
    title = _s(sow.get("title") or goal.get("line")) or "An intent"
    rec = f"intents/{iid}/sow.json"
    M = _Map(g, people, iid, title)
    sources = {str(s["id"]): s for s in sow.get("sources") or [] if isinstance(s, dict) and s.get("id")}
    loaded = {p["source_id"] for p in loaded_rows if p.get("state") == "loaded" and str(p.get("source_id")) in sources}
    periods = sorted({str(k.get("period")) for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("period")})
    sig = sow.get("signature") if isinstance(sow.get("signature"), dict) else None
    state = _state(plane, iid, sow, loaded)
    it = M.put(f"intent:{iid}", "Intent", title, f"{goal.get('line') or title}" + (f", so that {goal['why']}" if goal.get("why") else ""),
               said_by=_s((sig or {}).get("name")), record=rec, at=(sig or {}).get("at"), state=state, readers=goal.get("readers") or [],
               decisions=goal.get("decisions") or [], needed_by=goal.get("needed_by") or "", frequency=", ".join(periods),
               link=f"/centre/intent/{iid}")
    g.nodes[it]["state"] = state  # the newest records decide, never an older build

    # people: who asked, who read, who was spoken to
    talk = _talkers(plane, iid)
    if talk:
        M.link(M.person(talk[0][0], "decision maker", talk[0][2], talk[0][3]), it, "asked_for", talk[0][0], talk[0][2], talk[0][3])
    for name, role, r, at in talk:
        M.link(it, M.person(name, role, r, at), "spoke_to", name, r, at)
    for reader in goal.get("readers") or []:
        M.link(M.who(reader, "reader", rec), it, "asked_for", "", rec)

    # process and steps
    steps = [s for s in (sow.get("process") or {}).get("steps") or [] if isinstance(s, dict) and s.get("name")]
    if steps:
        pr = M.put(f"process:{iid}", "Process", f"How {title} is made today", f"The process behind {title}, as told to North.", record=rec)
        M.link(it, pr, "uses", record=rec)
        by_name = {match_name(s.get("name")): sid for sid, s in sources.items()}
        for s in steps:
            system = _s(s.get("system"))
            manual = not system
            st = M.put(f"step:{iid}:{s.get('n')}", "Step", f"{s.get('n')}. {s['name']}", _s(s.get("does")) or s["name"], record=rec,
                       manual=manual, inputs=s.get("inputs") or [], outputs=s.get("outputs") or [])
            M.link(st, pr, "step_of", record=rec)
            M.link(M.who(s.get("who"), f"does step {s.get('n')}", rec), st, "does", record=rec)
            if system:
                sid = by_name.get(match_name(system))
                M.link(st, f"source:{sid}" if sid else M.put(f"system:{_slug(system)}", "System", system, f"{system}, a system used in {title}.", record=rec),
                       "uses", record=rec)

    # sources, documents and fields (I5 drew the nodes; the map adds where each came from, what was read, and its owner)
    for sid, s in sources.items():
        doc = s.get("kind") == "document"
        nid = f"source:{sid}"
        holds = _s(s.get("holds"))
        M.put(nid, "Source", s.get("name") or sid, (f"A document: {holds}" if doc else f"A {s.get('kind') or 'source'} that holds {holds or 'data'}") + ".",
              said_by=_s((s.get("read") or {}).get("by")), record=rec, file=_s(s.get("sample_path")), read=s.get("read") or {},
              loaded=sorted({p["period"] for p in loaded_rows if p.get("source_id") == sid and p.get("state") == "loaded"}))
        if doc:
            g.nodes[nid]["type"] = "Document"  # one node per document: I5 drew it as a source
        M.link(M.who(s.get("owner"), f"owner of {s.get('name') or sid}", rec), nid, "owns", record=rec)
        read = s.get("read") or {}
        for o in read.get("owners") or []:
            if isinstance(o, dict):
                M.link(M.who(o.get("who"), f"owner of {o.get('what') or 'a document'}", _s(o.get("file"))), nid, "owns", _s(o.get("file")), _s(o.get("file")))
        for i, r in enumerate(read.get("rules") or []):
            if isinstance(r, dict) and (r.get("rule") or r.get("text")):
                rl = M.put(f"rule:{sid}:{i}", "Rule", _s(r.get("rule") or r.get("text")), "A rule read from a document.", said_by=_s(r.get("file")),
                           file=_s(r.get("file") or s.get("sample_path")), quote=_s(r.get("quote")))
                M.link(nid, rl, "governed_by", record=rec)
        for f in (s.get("fields") or [])[:60]:  # ponytail: first 60 fields per source; a wide file lists the rest on its own page
            if isinstance(f, dict) and f.get("name"):
                fid = M.put(f"field:{sid}:{_slug(f['name'])}", "Field", f["name"], _s(f.get("meaning")) or f"A field of {s.get('name') or sid}.",
                            file=_s(s.get("sample_path")), record=rec, field_type=_s(f.get("type")), example=_s(f.get("example")))
                M.link(nid, fid, "uses", record=rec)

    # KPIs, their definitions, owners and the stub when nothing feeds them
    scan = {str(k.get("code")): k for k in _rd(plane, "build", "scan", f"{iid}.json").get("kpis") or [] if isinstance(k, dict)}
    fed_by_table = {str(c) for t in sow.get("catalogue") or [] if isinstance(t, dict) for c in t.get("feeds_kpis") or []}
    kpis = {}
    for k in sow.get("kpis") or []:
        if not (isinstance(k, dict) and k.get("code")):
            continue
        code = str(k["code"])
        mid = kpis[code] = M.put(f"measure:{iid}:{code}" if code in shared else f"measure:{code}", "Measure", k.get("name") or code, _s(k.get("definition")) or f"{k.get('name') or code}: not defined yet.",
                                 said_by=_s(k.get("sources_by")), record=rec, code=code, definition=_s(k.get("definition")), formula=_s(k.get("formula")),
                                 unit=_s(k.get("unit")), period=_s(k.get("period")), status=_s(k.get("status")))
        M.link(it, mid, "uses", record=rec)
        for sid in k.get("source_ids") or []:
            M.link(f"source:{sid}" if str(sid) in sources else None, mid, "feeds", record=rec)
        M.link(M.who(k.get("owner"), f"owner of {k.get('name') or code}", rec), mid, "owns", record=rec)
        if not [x for x in k.get("source_ids") or [] if str(x) in sources] and code not in fed_by_table:
            miss = [m for m in (scan.get(code) or {}).get("missing") or [] if isinstance(m, dict)]
            why = "; ".join(f"{m.get('what')} (expected in {m.get('where_expected')})" for m in miss) or "The intent of work names no source for it yet."
            gap = M.put(f"gap:{iid}:{code}", "Gap", "No source yet", f"Nothing feeds {k.get('name') or code} yet: {why}",
                        record=f"build/scan/{iid}.json" if miss else rec, stub=True)
            M.link(mid, gap, "derived_from", record=rec)
        for t in terms:
            if match_name(t.get("term")) == match_name(k.get("name")) or match_name(k.get("name")) in {match_name(a) for a in t.get("aliases") or []}:
                tid = M.put(f"term:{_slug(t.get('term_id') or t.get('term'))}", "Term", t.get("term") or "A term", _s(t.get("definition")),
                            said_by=_s(t.get("confirmed_by")), record="glossary/company-terms.json", at=t.get("confirmed_at"), definition=_s(t.get("definition")))
                M.link(mid, tid, "defined_in", record="glossary/company-terms.json")
    by_name = {match_name(n["label"]): nid for nid, n in g.nodes.items() if nid in kpis.values()}
    for sid, s in sources.items():
        for d in (s.get("read") or {}).get("definitions") or []:
            m = by_name.get(match_name((d or {}).get("term") or "")) if isinstance(d, dict) else None
            M.link(m, f"source:{sid}", "defined_in", _s(d.get("file")) if m else "", rec)

    # tables (I5 drew them; the map adds meaning and fields' origin)
    for c in sow.get("catalogue") or []:
        if isinstance(c, dict) and c.get("table"):
            tid = M.put(i5_graph.table_id(c["table"]), "Table", c["table"], _s(c.get("meaning")) or f"A {c.get('layer') or ''} table.", record=rec,
                        layer=_s(c.get("layer")))
            for code in c.get("feeds_kpis") or []:
                M.link(tid, kpis.get(str(code)), "feeds", record=rec)

    # rules and settled points
    for i, r in enumerate(sow.get("governance") or []):
        if not (isinstance(r, dict) and r.get("rule")):
            continue
        rl = M.put(f"rule:{iid}:{i}", "Rule", r["rule"], f"A {r.get('kind') or ''} rule for {title}.".replace("  ", " "), said_by=_s(r.get("stated_by")),
                   record=rec, kind=_s(r.get("kind")))
        if r.get("kind") == "approval":
            M.link(M.who(r.get("stated_by"), "approver", rec), rl, "owns", record=rec)
        targets = [kpis.get(str(a)) or (f"source:{a}" if str(a) in sources else None) for a in r.get("applies_to") or []]
        for tgt in [t for t in targets if t] or [it]:
            M.link(tgt, rl, "governed_by", _s(r.get("stated_by")), rec)
    for u in sow.get("unclear") or []:
        if isinstance(u, dict) and u.get("settled") and u.get("id"):
            d = M.put(f"decision:{iid}:{u['id']}", "Decision", _s(u.get("question")) or "A settled point", f"Settled: {_s(u.get('answer')) or 'answered'}",
                      said_by=_s(u.get("who_can_settle")), record=rec, answer=_s(u.get("answer")))
            M.link(it, d, "governed_by", record=rec)
            M.link(d, M.who(u.get("who_can_settle"), "settled a point", rec), "decided_by", record=rec)

    # signed documents: every intent of work version (newer supersedes older), the approved design, the mapping sheet, the brief
    sigs = [x for x in sow.get("signatures") or [] if isinstance(x, dict)] or ([{**sig, "version": sow.get("version") or 1}] if sig else [])
    prev = None
    for x in sorted(sigs, key=lambda x: int(x.get("version") or 0)):
        v = int(x.get("version") or 1)
        sd = M.put(f"signed:{iid}:sow:v{v}", "Signed", f"Intent of work, version {v}", f"The intent of work for {title}, version {v}, as signed.",
                   said_by=_s(x.get("name")), record=rec, at=x.get("at"), link=f"/centre/intent/{iid}/sow")
        M.link(it, sd, "derived_from", record=rec)
        M.link(sd, M.person(x.get("name"), f"signed the intent of work ({x.get('role') or 'decision maker'})", rec, x.get("at")), "signed_by", _s(x.get("name")), rec, x.get("at"))
        M.link(sd, prev, "supersedes", record=rec)
        prev = sd
    bc = _rd(plane, "build", "blueprint_conversation", f"{iid}.json")
    if bc.get("state") == "approved":
        r = f"build/blueprint_conversation/{iid}.json"
        des = _rd(plane, "build", "design", f"{iid}.json")
        sd = M.put(f"signed:{iid}:design", "Signed", "Approved design", " ".join(map(str, des.get("lines") or [])) or f"The design for {title}, approved for the engineer.",
                   said_by=_s(bc.get("approved_by")), record=r, at=bc.get("approved_at"), link=f"/centre/build/{iid}")
        M.link(it, sd, "derived_from", record=r)
        M.link(sd, M.person(bc.get("approved_by"), "approved the design", r, bc.get("approved_at")), "signed_by", record=r)
    mp = _rd(plane, "build", "mapping", f"{iid}.json")
    if mp.get("rows"):
        r = f"build/mapping/{iid}.json"
        meta = _rd(plane, "build", "mapping", f"{iid}.meta.json")
        sd = M.put(f"signed:{iid}:mapping", "Signed", f"Mapping sheet, version {mp.get('version') or 1}",
                   f"How each table is filled from the sources: {len(mp['rows'])} lines.", said_by="Span", record=r, at=meta.get("at"),
                   room="build", link=f"/centre/build/{iid}/mapping")
        M.link(it, sd, "derived_from", record=r)
        for row in mp["rows"]:
            if isinstance(row, dict) and row.get("target_table") and str(row.get("source_id")) in sources:
                tid = M.put(i5_graph.table_id(row["target_table"]), "Table", row["target_table"], f"A {row.get('layer') or ''} table filled by the mapping sheet.".replace("  ", " "),
                            record=r, layer=_s(row.get("layer")), room="build")
                M.link(tid, f"source:{row['source_id']}", "derived_from", "Span", r)
                M.link(tid, sd, "derived_from", "Span", r)
    brief = _rd(plane, "consume", "brief", f"{iid}.json")
    if brief.get("views"):
        r = f"consume/brief/{iid}.json"
        sd = M.put(f"signed:{iid}:brief", "Signed", "Consumption brief", f"What the readers of {title} want to see.", said_by="Lumen", record=r,
                   room="consume", link="/centre/consume/design")
        M.link(it, sd, "derived_from", record=r)
        codes = {match_name(n["label"]): nid for nid, n in g.nodes.items() if nid in kpis.values()} | {match_name(c): nid for c, nid in kpis.items()}
        for v in brief["views"]:
            if not (isinstance(v, dict) and v.get("name")):
                continue
            vid = M.put(f"view:{iid}:{_slug(v['name'])}", "View", v["name"], f"A view for {_s(v.get('audience')) or 'its readers'}, refreshed {_s(v.get('refresh')) or 'as loaded'}.",
                        said_by="Lumen", record=r, room="consume", audience=v.get("audience"), comparisons=v.get("comparisons") or [], filters=v.get("filters") or [])
            M.link(vid, sd, "derived_from", record=r)
            for k in v.get("kpis") or []:
                M.link(codes.get(match_name(k)), vid, "shown_in", record=r)
            for a in v.get("audience") if isinstance(v.get("audience"), list) else [v.get("audience")]:
                M.link(M.who(a, f"reads {v['name']}", r), vid, "asked_for", record=r)


# ---- reading the map --------------------------------------------------------------------------------------------------------------

STOP = frozenset("a an and are as at be by come comes did do does for from how i in is it its of on or the this to was we what when where which who why with".split())


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in STOP and len(w) > 1]


def _haystack(n: dict, documents: bool) -> str:
    parts = [n.get("label"), n.get("what"), n.get("definition"), n.get("formula"), n.get("code")]
    if documents:
        read = n.get("read") or {}
        parts += [x.get(k) for sec in ("definitions", "owners", "systems", "rules") for x in read.get(sec) or [] if isinstance(x, dict)
                  for k in ("term", "definition", "what", "who", "rule", "quote", "name")]
        parts.append(n.get("quote"))
    return " ".join(str(p) for p in parts if p).lower()


def ask(nodes: list[dict], q: str, documents: bool = True, limit: int = 20) -> list[dict]:
    """Nodes matching a phrase, best first: every word found in the name or definition counts twice, in what was read once. Names and
    definitions only come back, never rows."""
    words = _words(q)
    if not words:
        return []
    scored = []
    for n in nodes:
        if n.get("restricted"):
            continue
        name, hay = f"{n.get('label', '')} {n.get('definition', '')}".lower(), _haystack(n, documents)
        score = sum(2 if w in name else 1 for w in words if w in hay)
        if score:
            scored.append((-score, n["type"] != "Measure", n["label"], n))
    return [{"id": n["id"], "type": n["type"], "label": n["label"], "what": n.get("what") or "", "definition": n.get("definition") or ""}
            for *_, n in sorted(scored, key=lambda s: s[:3])[:limit]]


def ask_company(plane, q: str) -> list[dict]:
    """For the agents: the open part of the map only (a node anyone may be shown), names and definitions only."""
    doc = _rd(plane, "graph", "company.json")
    return ask([n for n in doc.get("nodes") or [] if n.get("restricted_to") is None], q, documents=False)
