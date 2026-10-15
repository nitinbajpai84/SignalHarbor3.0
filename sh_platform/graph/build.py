"""`rebuild(plane)`: reads the company's records by path and replaces `graph/company.json` (a projection; nothing is edited on it).

Read, never imported from a module (modules.md): the profile store, the newest signed module 2 outcome (catalogue, glossary, process map,
ambiguities, signatures), the charter outcome it names, and the newest module 3 assessment folder (sources, rules, findings, decisions, plan).
Restrictions are derived with the profile's own helpers (`view.sees_source`, `sees_rule`, area `may_see`). The shape of the rebuild (a whole
new graph replaces the old, so stale nodes and edges go) follows the earlier spine's `rebuild_from_graph`; storage is one JSON file.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sh_platform.graph.models import Graph, Guard, meet
from sh_platform.graph.build_nodes import add_build_nodes
from sh_platform.graph.intent_nodes import add_intent_nodes
from sh_platform.graph.knowledge_map import add_map_nodes
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store
from sh_platform.profile.view import NOBODY, ROLE_PASS, _bound, _key, _names, _v, norm, sees_rule, sees_source

log = logging.getLogger(__name__)
VERSION = 1
_HEX = re.compile(r"[0-9a-f]{16,64}")
_LANE = {"tracking": "Problem", "missing": "Pain", "watch": "Signal", "levers": "Lever"}


def _slug(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _t(cell: Any) -> str:
    v = cell.get("value") if isinstance(cell, dict) and "mark" in cell and cell.get("mark") != "unknown" else (None if isinstance(cell, dict) else cell)
    return "; ".join(map(str, v)) if isinstance(v, (list, tuple)) else ("" if v is None else str(v))


def _prov(cell: Any = None, by: str = "", src: str = "", at: str | None = None) -> list[dict]:
    """A provenance list: the cell's own provenance when it is a cell, else a stated one with the given words."""
    if isinstance(cell, dict) and "mark" in cell:
        return [{k: cell[k] for k in ("mark", "by", "at", "from") if k in cell}]
    return [{"mark": "stated", "by": by or "the record", "at": at, "from": src}]


def _read(plane: CompanyPlane, *parts: str, kind: type = dict) -> Any:
    try:
        d = read_json_strict(plane.path(*parts))
    except (OSError, ValueError):
        log.warning("a record could not be read for the company graph")
        return kind()
    return d if isinstance(d, kind) else kind()


def _newest_baseline(plane: CompanyPlane) -> dict:
    """The newest signed module 2 outcome, read by path (the same rule module 3 uses)."""
    folder = plane.path("intents", "m2_baseline", "outcomes")
    found = [d for f in (folder.glob("*.json") if folder.is_dir() else [])
             if (d := _read(plane, "intents", "m2_baseline", "outcomes", f.name)).get("kind") == "baseline" and d.get("signed_at") and d.get("signatures")]
    return max(found, key=lambda d: str(d.get("signed_at")), default={})


def _g(names, item: dict) -> Guard:
    return sorted(names), _bound(item)


def _listed(item: dict) -> frozenset[str]:
    v = _v(item, "may_see")
    return _names(v if isinstance(v, list) else re.split(r"[,;]", str(v or "")))


def _source_guard(item: dict) -> Guard | None:
    """Who may see a source: the profile's own test (`sees_source` for nobody) decides if it is shut; the list follows its rule
    ("not sure" with names also lets the sponsor and the admin in)."""
    if sees_source(item, NOBODY):
        return None
    names = _listed(item)
    return _g(names | ROLE_PASS if norm(_v(item, "personal_data") or "").startswith("not sure") and names and _v(item, "restricted") is not True else names, item)


def _oid(prefix: str, key: str) -> str:
    """An id that says nothing about the record behind it (a decision or plan item about a closed measure)."""
    return f"{prefix}:{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}"


class Gate:
    """What the profile closes, as lists: restricted areas, field rules and sources a reader on no list may not see, each with its keys.
    A name like one of those keys (`view.read`'s `shut_names` / `tied`) carries that item's list; so does an item in an area's team or area cell.
    Uses the profile's own helpers (`sees_area`-style lists, `sees_rule`, `sees_source`, `_key`), so the graph is never more open than the profile."""

    def __init__(self, doc: dict) -> None:
        gov = doc["governance"]
        self.areas = [(norm(_v(a, "area") or k), _g(_names(_v(a, "may_see")), a)) for k, a in gov["restricted_areas"].items()]
        area_keys = [({_key(k), _key(_v(a, "area") or "")} - {""}, gd) for (k, a), (_, gd) in zip(gov["restricted_areas"].items(), self.areas)]
        self.shut = list(area_keys)
        for k, r in gov["field_rules"].items():
            if not sees_rule(r, NOBODY):
                own = _names(_v(r, "field_may_see"))
                self.shut.append(({_key(k), _key(_v(r, "field") or "")} - {""}, meet(_g(_listed(r), r), _g(own | ROLE_PASS, r) if own else None)))
        for k, sy in doc["systems"].items():
            keys = {_key(k), _key(_v(sy, "name") or "")} - {""}
            gd = meet(_source_guard(sy), *[g for ks, g in area_keys if keys & ks])
            if gd is not None:
                self.shut.append((keys, gd))

    def cells(self, item: dict) -> Guard | None:
        """An item whose area or team cell names a restricted area (`view.read`'s `open_item`)."""
        mine = {norm(_v(item, "area") or ""), norm(_v(item, "team") or "")} - {""}
        return meet(*[gd for name, gd in self.areas if name in mine])

    def named(self, text: Any) -> Guard | None:
        k = _key(text)
        return meet(*[gd for keys, gd in self.shut if k and k in keys])


def rebuild(plane: CompanyPlane) -> dict:
    doc = store.raw(plane)
    gate = Gate(doc)
    g = Graph(gate.named)
    people = _people(g, doc, gate)
    _profile(g, doc, gate, people)
    base = _newest_baseline(plane)
    cid = str(base.get("charter_outcome_id") or "")
    charter = _read(plane, "intents", "m1_intent", "outcomes", f"{cid}.json") if _HEX.fullmatch(cid) else {}
    charter = charter if charter.get("kind") == "charter" else {}
    _cards(g, doc, gate, people, bool(charter))
    _charter(g, charter, people)
    _baseline(g, plane, base, people)
    _figures(g, doc, gate, people)  # after the baseline, so a reported figure can merge into its measure
    _assessment(g, plane, people)
    add_build_nodes(g, plane, people)  # M4: pipelines, blueprints, releases
    from sh_platform.build.architecture import add_component_nodes; add_component_nodes(g, plane, people)  # 59: Component nodes
    add_intent_nodes(g, plane, people)  # spec 20: intents and the backlog
    add_map_nodes(g, plane, people)  # spec 55: where each data point lives
    from sh_platform.v1.i5_graph import add_sow_nodes; add_sow_nodes(g, plane, people)  # 1.0: intent, problem, sources, KPIs, tables
    from sh_platform.v1.m1_map import add_company_map_nodes; add_company_map_nodes(g, plane, people)  # 1.0 M1: the company map
    out = {"version": VERSION, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "nodes": sorted(g.nodes.values(), key=lambda n: n["id"]), "edges": sorted(g.edges.values(), key=lambda e: (e["from"], e["to"], e["type"]))}
    path = plane.path("graph", "company.json")
    with lock_for(path):
        old = read_json_strict(path, dict) if path.exists() else None
        write_json_atomic(path, out)
    from sh_platform.graph.versions import record_versions_from_build  # lazy: versions imports build
    record_versions_from_build(plane, old, out)  # M1: a version per changed node
    return out


def _person(g: Graph, people: dict[str, str], name: Any, prov: list[dict], room: str, from_key: bool = False) -> str | None:
    """The person node for a name or profile key (made when new). `people` maps profile keys and name slugs to node ids."""
    s = _slug(name)
    if not s or s == "not-available-yet":  # an unanswered owner is no person
        return None
    if s not in people and _HEX.fullmatch(s):  # an account id with no person in the people list is never shown as a name
        return None
    if s not in people:
        people[s] = g.node(f"person:{s}", "Person", s.replace("-", " ").title() if from_key else str(name), prov, room)
    return people[s]


def _people(g: Graph, doc: dict, gate: Gate) -> dict[str, str]:
    people: dict[str, str] = {}
    for k, p in doc["people"].items():
        name = _t(p.get("name")) or k
        pid = g.node(f"person:{_slug(name)}", "Person", name, _prov(p.get("name"), by="the people list", src="People list"), "wall", gate.cells(p))
        people[_slug(k)] = people[_slug(name)] = pid
        acct = _slug(_t(p.get("account_id")))
        if acct:  # a card's author is an account id: it resolves to the person's name
            people[acct] = pid
        team = _t(p.get("team"))
        if team:
            tid = g.node(f"team:{_slug(team)}", "Team", team, _prov(p.get("team")), "wall", gate.cells({"team": p["team"]}))
            g.edge(pid, tid, "member_of", _prov(p.get("team")))
    return people


def _profile(g: Graph, doc: dict, gate: Gate, people: dict) -> None:
    for k, s in doc["systems"].items():  # a name like a restricted thing is limited by the graph itself (`gate.named`)
        g.node(f"system:{_slug(k)}", "System", _t(s.get("name")) or k, _prov(s.get("name"), by="the systems list", src="Systems list"), "wall",
               meet(gate.cells(s), _source_guard(s)))
        who = _person(g, people, _t(s.get("owner")), _prov(s.get("owner"), src="Systems list"), "wall")
        if who:
            g.edge(f"system:{_slug(k)}", who, "owned_by", _prov(s.get("owner"), src="Systems list"))
    for k, r in doc["governance"]["field_rules"].items():
        own = _names(_v(r, "field_may_see"))
        gd = None if sees_rule(r, NOBODY) else meet(_g(_listed(r), r), _g(own | ROLE_PASS, r) if own else None)
        g.node(f"rule:{_slug(k)}", "Rule", _t(r.get("field")) or k, _prov(r.get("field"), by="the policy", src="Governance"), "wall", gd)


def _figures(g: Graph, doc: dict, gate: Gate, people: dict) -> None:
    """A reported figure merges into the baseline measure of the same name (case-insensitive); with no such measure it is its own node unless its figure is empty."""
    by_name = {n["label"].strip().lower(): i for i, n in g.nodes.items() if n["type"] == "Measure"}
    for k, f in doc["reported_figures"].items():
        m = (_t(f.get("measure")) or k).strip()
        nid = by_name.get(m.lower())
        if nid is None and "figure" in f and not _t(f["figure"]):  # a figure cell that says nothing: drop (no figure cell at all is a bare name, kept)
            continue
        nid = g.node(nid or f"measure:{_slug(m)}", "Measure", m, _prov(f.get("measure") or f.get("figure"), by="a reported figure", src="Reported figures"), "wall", gate.cells(f))
        who = _person(g, people, _t(f.get("owner")), _prov(f.get("owner"), src="Reported figures"), "wall")
        if who and not any(a == nid and t == "owned_by" for (a, _, t) in g.edges):
            g.edge(nid, who, "owned_by", _prov(f.get("owner"), src="Reported figures"))


def _cards(g: Graph, doc: dict, gate: Gate, people: dict, chartered: bool = False) -> None:
    """A card is a Problem, Pain, Signal or Lever by its lane. An anonymous card has no `raised_by` edge and no author anywhere.
    With a signed charter the problems are the charter's, so a blank wall card in the Problem lane is not shown as one."""
    for k, c in doc.get("cards", {}).items():
        lane, anon = _v(c, "lane"), _v(c, "anonymous") is True
        if lane not in _LANE:
            continue
        text = " ".join(str(_v(c, q) or "") for q in ("q1", "q2", "q3", "q4")).strip()
        if chartered and lane == "tracking" and not text:  # ponytail: only a card with no words is dropped; one with words stays until the charter names it
            continue
        prov = [{**p, "by": "anonymous"} if anon else p for p in _prov(c.get("q1"), by="a participant", src="A card on the wall")]
        guard = None
        if _v(c, "sealed") is True:  # the profile's rule: whole only to who may see every restricted area its words name
            words = f" {_key(text)} "
            hit = [gd for keys, gd in gate.shut[:len(gate.areas)] if any(f" {n} " in words for n in keys)]
            guard = meet(*hit) if hit else ([], {})
        sealed = _v(c, "sealed") is True  # a sealed card's words never reach the projection file
        nid = g.node(f"card:{_slug(k)}", _LANE[lane], "Sealed card" if sealed else text[:80] or "A card", prov, "wall", guard)
        if not anon and _t(c.get("author")):
            who = _person(g, people, _t(c["author"]), prov, "wall", from_key=True)
            if who:
                g.edge(nid, who, "raised_by", prov)


def _decision(g: Graph, people: dict, key: str, label: str, rec: dict, room: str, guard: Guard | None = None) -> str | None:
    """A Decision node from a signed record: one `decided_by` edge to each signer, with the date."""
    sigs = [s for s in rec.get("signatures") or [] if isinstance(s, dict) and s.get("name")]
    if not (rec.get("signed_at") and sigs):
        return None
    d = g.node(_oid("decision", key), "Decision", label, _prov(by=sigs[0]["name"], src=label, at=rec["signed_at"]), room, guard)
    for s in sigs:
        p = _prov(by=s["name"], src=label, at=s.get("at"))
        who = _person(g, people, s["name"], p, room)
        if who:
            g.edge(d, who, "decided_by", p)
    return d


def _charter(g: Graph, ch: dict, people: dict) -> None:
    if not ch:
        return
    p = _prov(by="the charter", src=f"Charter outcome {ch.get('outcome_id') or ''}".strip(), at=ch.get("signed_at"))
    sign = _decision(g, people, f"charter-{ch.get('outcome_id')}", "Charter signed", ch, "wall")
    for it in [i for sec in ("problems", "pain_points", "future_signals", "levers") for i in ch.get(sec) or []]:  # the charter's items; links to measures are kpis.json `problem_ids`
        if isinstance(it, dict) and it.get("id"):
            nid = g.node(f"problem:{it['id']}", "Problem", str(it.get("title") or it["id"]), p, "wall")
            if sign:
                g.edge(nid, sign, "decided_by", p)


def _baseline(g: Graph, plane: CompanyPlane, base: dict, people: dict) -> None:
    if not base:
        return
    bid, src = str(base.get("baseline_id") or ""), f"Baseline outcome {base.get('outcome_id') or ''}".strip()
    b = _prov(by="the baseline", src=src, at=base.get("signed_at"))
    cat = base.get("catalogue") or {}
    rows = {t: [r for r in cat.get(t) or [] if isinstance(r, dict)] for t in ("kpis", "sources", "tables", "fields")}
    kp = _read(plane, "intents", "m2_baseline", bid, "kpis.json", kind=list) if _HEX.fullmatch(bid) else []
    gov = {str(k["id"]): k for k in kp if isinstance(k, dict) and k.get("id")}
    _decision(g, people, f"baseline-{base.get('outcome_id')}", "Baseline signed", base, "define")
    names, kpi = {}, {}
    for r in rows["kpis"]:
        mid = _t(r.get("KPI ID"))
        if not mid:
            continue
        kpi[mid], k = r, gov.get(mid) or {}
        gv = k.get("governance") if isinstance(k.get("governance"), dict) else {}
        shut = gv.get("personal", "not_sure") != "no" or bool(gv.get("sensitive"))  # module 2's rule: not sure counts as personal
        names[mid] = _t(r.get("KPI name")) or mid
        g.node(f"measure:{mid}", "Measure", names[mid], _prov(r.get("KPI name"), by="the baseline", src=src), "define",
               (sorted(_names(gv.get("may_see") or [])), {}) if shut else None)
        for pid in k.get("problem_ids") or []:
            g.edge(f"problem:{pid}", f"measure:{mid}", "measured_by", b)
        for col in ("Business owner", "Data owner"):
            who = _person(g, people, _t(r.get(col)), _prov(r.get(col), src=src), "define")
            if who:
                g.edge(f"measure:{mid}", who, "owned_by", _prov(r.get(col), src=src))
    for e in base.get("glossary") or []:
        mid = str(e.get("kpi_id") or "") if isinstance(e, dict) else ""
        if mid in names:
            g.node(f"term:{mid}", "Term", str(e.get("term") or names[mid]), _prov(by="the glossary", src=src), "define", g.guard(f"measure:{mid}"))
            g.edge(f"measure:{mid}", f"term:{mid}", "defined_as", b)
    for r in rows["sources"]:
        sid = _t(r.get("Source ID"))
        if not sid:
            continue
        probe = {"personal_data": {"mark": "stated", "value": _t(r.get("Contains personal data?"))}, "may_see": {"mark": "stated", "value": _t(r.get("Who may see it"))}}
        g.node(f"source:{sid}", "Source", _t(r.get("Source name")) or sid, _prov(r.get("Source name"), by="the baseline", src=src), "define",
               _source_guard(probe))
        who = _person(g, people, _t(r.get("Data owner")), _prov(r.get("Data owner"), src=src), "define")
        if who:
            g.edge(f"source:{sid}", who, "owned_by", _prov(r.get("Data owner"), src=src))
    table_src = {_t(t.get("Item ID")): _t(t.get("Source ID")) for t in rows["tables"]}
    for t in rows["tables"]:
        for m in re.split(r"[,;]", _t(t.get("Related KPIs"))):
            g.edge(f"measure:{m.strip()}", f"source:{_t(t.get('Source ID'))}", "fed_by", _prov(t.get("Related KPIs"), by="the baseline", src=src))
    for f in rows["fields"]:
        fid, sn = _t(f.get("Field ID")), f"source:{table_src.get(_t(f.get('Item ID')))}"
        if fid and sn in g.nodes:
            g.node(f"field:{fid}", "Field", _t(f.get("Field name as in the source")) or fid, _prov(f.get("Field name as in the source"), by="the baseline", src=src), "define",
                   g.guard(sn))
            g.edge(sn, f"field:{fid}", "uses", b)
    for mid, pm in (base.get("process_map") or {}).items():
        if not isinstance(pm, dict) or f"measure:{mid}" not in g.nodes:
            continue
        pr, shut = f"process:{mid}", g.guard(f"measure:{mid}")
        pp = _prov(by="the process map", src=src)
        g.node(pr, "Process", f"Process for {names[mid]}", pp, "define", shut)
        for s in pm.get("steps") or []:
            if isinstance(s, dict) and s.get("id") and s.get("state") != "removed":
                g.node(f"step:{mid}:{s['id']}", "Step", str(s.get("text") or s["id"]), pp, "define", shut)
                g.edge(f"step:{mid}:{s['id']}", pr, "step_of", pp)
        who = _person(g, people, _t(kpi[mid].get("Process owner")), _prov(kpi[mid].get("Process owner"), src=src), "define")
        if who:
            g.edge(pr, who, "owned_by", pp)
        for (m, s, kind) in list(g.edges):
            if m == f"measure:{mid}" and kind == "fed_by":
                g.edge(s, pr, "produced_by", pp)
    for a in base.get("ambiguities") or []:
        mn = f"measure:{a.get('kpi_id')}" if isinstance(a, dict) else ""
        if mn in g.nodes and a.get("status") == "accepted":
            p = _prov(by=a.get("by") or "the baseline", src="An accepted ambiguity", at=a.get("at"))
            rid = g.node(f"risk:ambiguity-{a.get('kpi_id')}-{a.get('id')}", "Risk", str(a.get("text") or a.get("question") or "An accepted ambiguity"), p, "define",
                         g.guard(mn))
            g.edge(mn, rid, "at_risk", p)
            d = g.node(_oid("decision", rid), "Decision", "Ambiguity accepted", p, "define", g.guard(rid))
            g.edge(rid, d, "decided_by", p)
            who = _person(g, people, a.get("by"), p, "define")
            if who:
                g.edge(d, who, "decided_by", p)


def _assessment(g: Graph, plane: CompanyPlane, people: dict) -> None:
    root = plane.path("intents", "m3_connect", "assessments")
    found = [(str(_read(plane, "intents", "m3_connect", "assessments", d.name, "assessment.json").get("created_at") or ""), d.name)
             for d in (root.iterdir() if root.is_dir() else []) if d.is_dir()]
    if not found:
        return
    aid = max(found)[1]

    def rd(name: str) -> dict:
        return _read(plane, "intents", "m3_connect", "assessments", aid, name)
    src = "The module 3 assessment"
    t = _prov(by="the trial", src=src)
    for s in rd("sources.json").get("sources") or []:
        if isinstance(s, dict) and f"source:{s.get('id')}" in g.nodes:
            for m in s.get("measures") or []:
                g.edge(f"measure:{m}", f"source:{s['id']}", "fed_by", t)
    for mid, r in rd("rules.json").items():
        if isinstance(r, dict) and r.get("rule") and f"measure:{mid}" in g.nodes:
            mn = g.nodes[f"measure:{mid}"]
            rid = g.node(f"rule:{mid}", "Rule", f"Rule for {mn['label']}", _prov(by=r.get("checked_by") or "Lens", src=src), "truth", g.guard(f"measure:{mid}"))
            g.edge(f"measure:{mid}", rid, "governed_by", t)
    decisions = rd("decisions.json").get("risks")
    for r in rd("findings.json").get("risks") or []:
        if not (isinstance(r, dict) and r.get("id")):
            continue
        guard = meet(*[g.guard(f"measure:{m}") for m in r.get("measures") or []], ([], {}) if r.get("restricted") else None)
        rid = g.node(f"risk:{r['id']}", "Risk", str(r.get("text") or r["id"]), t, "truth", guard)
        for m in r.get("measures") or []:
            g.edge(f"measure:{m}", rid, "at_risk", t)
        dec = decisions.get(r["id"]) if isinstance(decisions, dict) else None
        if isinstance(dec, dict) and dec.get("decision"):
            p = _prov(by=dec.get("by") or "a decider", src=f"Risk {dec['decision']}", at=dec.get("at"))
            d = g.node(_oid("decision", rid), "Decision", f"Risk {dec['decision']}", p, "truth", g.guard(rid))
            g.edge(rid, d, "decided_by", p)
            who = _person(g, people, dec.get("by"), p, "truth")
            if who:
                g.edge(d, who, "decided_by", p)
    plan = rd("plan.json")
    for it in plan.get("items") or []:
        if isinstance(it, dict) and it.get("key"):
            guard = meet(*[g.guard(f"source:{x}") for x in it.get("sources") or []], ([], {}) if it.get("restricted") else None)
            pid = g.node(_oid("plan", str(it["key"])), "PlanItem", f"Plan item ({it.get('band') or 'unplaced'})",  # opaque: a key can name a measure
                         _prov(by="the plan", src=src, at=plan.get("updated_at")), "truth", guard)
            for s in it.get("sources") or []:
                g.edge(f"source:{s}", pid, "planned_in", _prov(by="the plan", src=src))
    _decision(g, people, f"plan-{aid}", "Plan signed", plan, "truth")
