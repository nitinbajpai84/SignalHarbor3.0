"""IC v2 (20): Intent and Backlog nodes on the company map, with `led_to`, `came_from`, `built_by` and `owned_by` edges.

Pattern copied from build_nodes.py: `_register()` adds the types to models' vocabulary (models.py is not ours), and
`add_intent_nodes(g, plane, people)` reads `intents/*/intent.json` and `intents/backlog.json` by path and writes nothing.
The node guard is the names of people tagged to the intent's areas, its named people and the company admin; drafts are left out
(a draft has no node, ruling 14). Payload: type, state, areas, organiser, the outcome line or the cancel reason. Never content.
"""
import logging

from sh_platform.graph import models

log = logging.getLogger(__name__)


def _register() -> None:
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "Intent", "Backlog")))
    models.ROOMS = tuple(dict.fromkeys((*models.ROOMS, "intent")))
    models.EDGE_TYPES.setdefault("led_to", (["Intent"], ["Intent", "Backlog"]))
    models.EDGE_TYPES.setdefault("came_from", (["Intent", "Backlog"], ["Intent"]))
    models.EDGE_TYPES.setdefault("built_by", (["Measure"], ["Pipeline"]))
    for typ, end, add in (("owned_by", 0, "Intent"), ("built_by", 0, "Intent"), ("built_by", 1, "Blueprint")):
        if add not in models.EDGE_TYPES[typ][end]:
            models.EDGE_TYPES[typ][end].append(add)


def _status(src: dict, tgt: dict | None) -> str:
    """The link's status from the records: a cancelled end says so (spec 20, what is written when a linked intent is cancelled)."""
    if src["state"] == "cancelled":
        return "source_cancelled"
    if tgt and tgt["state"] == "cancelled":
        return "target_cancelled"
    return "active"


def add_intent_nodes(g, plane, people) -> None:
    """Called by build.rebuild after add_build_nodes."""
    from sh_platform.graph.build import _person, _prov
    from sh_platform.intents import backlog as B
    from sh_platform.intents import links as K
    from sh_platform.intents import store as S
    from sh_platform.profile import store as profile_store
    from sh_platform.profile import view as pview
    _register()
    from sh_platform.profile import areas as areas_store
    doc = profile_store.load(plane)
    names = {a["id"]: a["name"] for a in areas_store.listing(doc) if a.get("name")}
    team_of: dict[str, set[str]] = {}  # area (id or name, normalised) to the names of the people tagged to it (05 tags)
    for p in (doc.get("people") or {}).values():
        if pview._v(p, "name"):
            for a in areas_store.people_areas(p):
                for key in {pview.norm(a), pview.norm(names.get(a) or a)}:
                    team_of.setdefault(key, set()).add(pview.norm(pview._v(p, "name")))
    recs = {}
    for i in S._ids_on_disk(plane):
        try:
            rec = S.read_intent(plane, i)
        except S.Unreadable:
            continue
        if rec and rec["state"] != "draft":
            recs[i] = rec
    for i, rec in recs.items():
        p, c = rec.get("people") or {}, rec.get("closure") or {}
        named = {pview.norm(x["name"]) for x in [p.get(s) for s in S.SLOTS] + [y for k in S.LISTS for y in p.get(k) or []]
                 if isinstance(x, dict) and x.get("name")}
        tagged = set().union(*[team_of.get(pview.norm(a), set()) for a in rec.get("areas") or []]) if rec.get("areas") else set()
        guard = (sorted(named | tagged | {"\0company_admin"}), {})
        organiser = (p.get("organiser") or {}).get("name")
        prov = _prov(by=organiser or "the organiser", src=f"intents/{i}/intent.json", at=rec.get("created_at"))
        nid = g.node(f"intent:{i}", "Intent", rec.get("title") or "An intent", prov, "intent", guard)
        g.nodes[nid].update(intent_type=rec["type"], state=rec["state"], areas=rec.get("areas") or [], organiser=organiser,
                            outcome_line=K._first_sentence(c.get("what_came_out")) if rec["state"] == "closed" else "",
                            cancel_reason=c.get("cancel_reason") if rec["state"] == "cancelled" else None,
                            build="Waiting for Build" if (rec.get("links") or {}).get("build") else None)
        who = _person(g, people, organiser, prov, "intent")
        if who:
            g.edge(nid, who, "owned_by", prov)
    items = {it["id"]: it for it in B.read_items(plane)}
    for i, rec in recs.items():
        for r in K.log_of(rec):
            if r["dir"] != "to":
                continue
            oid = (r.get("other") or {}).get("id")
            prov = [{"mark": "stated", "by": r.get("created_by") or "the organiser", "at": r.get("created_at"),
                     "from": f"linked by {r.get('created_by') or 'the organiser'} on {str(r.get('created_at') or '')[:10]}"}]
            if r["kind"] == "backlog" and oid in items:
                it = items[oid]
                bid = g.node(f"backlog:{oid}", "Backlog", it["title"], prov, "intent", g.guard(f"intent:{i}"))
                g.nodes[bid]["status"] = it["status"]
                g.edge(f"intent:{i}", bid, "led_to", prov)
                g.edge(bid, f"intent:{i}", "came_from", prov)
            elif r["kind"] == "build":
                bp = next((n for n in g.nodes.values() if n["type"] == "Blueprint"), None)  # 20 open question 6: the ref names no version yet
                if bp:
                    g.edge(f"intent:{i}", bp["id"], "built_by", [{**prov[0], "from": f"handed to Build by {r.get('created_by')}"}])
                    g.nodes[f"intent:{i}"]["build"] = None
            elif oid in recs:
                st = _status(rec, recs[oid])
                if g.edge(f"intent:{i}", f"intent:{oid}", "led_to", prov):
                    g.edges[(f"intent:{i}", f"intent:{oid}", "led_to")]["status"] = st
                if g.edge(f"intent:{oid}", f"intent:{i}", "came_from", prov):
                    g.edges[(f"intent:{oid}", f"intent:{i}", "came_from")]["status"] = st
