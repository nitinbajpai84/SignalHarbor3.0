"""The data knowledge map (spec 55): where each data point lives, on the one company graph. Follows `build_nodes.py`.

`add_map_nodes(g, plane, people)` runs inside `build.rebuild` (after the build and intent nodes) and adds
File, Charter, GapReport and Mart nodes, the `held_in`, `lands_at`, `produces`, `consumes`, `defined_in`, `led_to` and `verified_by` edges, and
`owner_kind` on `owned_by` edges. Records are read by path. A missing record adds nothing. Nothing here reads a row value or a document's text.

`graph/updates.json`: `[{id, moment, ref, by, at, added: {type: count}, added_ids, changed, removed, line}]`, one row per update moment
(`record_moment`: a forced rebuild, a version on each new node, one row). `verify.json` (written by `scan_assessment` and the two owner
buttons) is `{rows: [...]}`, older rows kept; the newest row per node draws the `verified_by` edge.
"""
import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.graph import build_nodes, models
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)
MOMENTS = {"charter_signed": "charter", "gap_report_signed": "gap report", "blueprint_signed": "blueprint", "release": "release", "scan_run": "scan"}
CONFIDENT = ("medium", "high")  # open question 8: a medium match counts as available; a low one does not
_ASSESS = ("intents", "m3_connect", "assessments")


def _register() -> None:
    """models.py is not ours to edit: widen its vocabulary here (idempotent), the way build_nodes does."""
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "File", "Charter", "GapReport", "Mart")))
    E = models.EDGE_TYPES
    E.setdefault("held_in", (["Field", "Source", "File"], ["System"]))
    E.setdefault("lands_at", (["Source", "Pipeline"], ["System"]))
    E.setdefault("produces", (["Process", "Step"], ["Field", "Source", "File"]))
    E.setdefault("consumes", (["Process", "Step", "Pipeline"], ["Field", "Source", "File"]))
    E.setdefault("defined_in", (["Measure", "Term", "Field", "Mart"], ["File", "Charter", "GapReport", "Blueprint"]))
    if "Mart" not in E["defined_in"][0]:
        E["defined_in"][0].append("Mart")
    E.setdefault("verified_by", (["Field", "Source"], ["GapReport"]))
    E.setdefault("led_to", ([], []))
    E.setdefault("came_from", ([], []))
    for t in ("led_to", "came_from"):
        for side in E[t]:
            side[:] = list(dict.fromkeys([*side, "Intent", "Charter", "GapReport", "Blueprint", "Release"]))
    for t in ("Field", "File", "Mart"):
        if t not in E["owned_by"][0]:
            E["owned_by"][0].append(t)
    for t in ("Field", "Mart"):
        if t not in E["fed_by"][1]:
            E["fed_by"][1].append(t)
    if "Mart" not in E["built_by"][0]:
        E["built_by"][0].append("Mart")


_slug, _rd, _l = build_nodes._slug, build_nodes._rd, build_nodes._l


def _t(cell) -> str:
    v = cell.get("value") if isinstance(cell, dict) else cell
    return "" if v is None else str(v)


def newest_assessment(plane: CompanyPlane) -> str:
    """The assessment folder the graph reads (the one `build._assessment` reads: newest `created_at`)."""
    root = plane.path(*_ASSESS)
    found = [(str(_rd(plane, *_ASSESS, d.name, "assessment.json").get("created_at") or ""), d.name) for d in (root.iterdir() if root.is_dir() else []) if d.is_dir()]
    return max(found)[1] if found else ""


def verify_rows(plane: CompanyPlane, aid: str) -> list[dict]:
    return [r for r in _l(_rd(plane, *_ASSESS, aid, "verify.json"), "rows") if r.get("node")] if aid else []


def effective(row: dict) -> str:
    """What the map shows: a rejected 'found elsewhere' is Missing; a confirmed one stays found elsewhere (the tag says it is confirmed)."""
    return "missing" if row.get("rejected_by") else str(row.get("result") or "")


def newest_by_node(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:  # file order is time order: rows are appended
        out[r["node"]] = r
    return out


def add_map_nodes(g, plane: CompanyPlane, people: dict) -> None:
    """Called by `build.rebuild` after the build nodes."""
    from sh_platform.graph.build import _newest_baseline, _person, _prov, _t as cell_text
    _register()
    base, bp, pv = _newest_baseline(plane), _rd(plane, "build", "blueprint.json"), _rd(plane, "build", "prove.json")
    aid = newest_assessment(plane)

    def ev(src: str, by: str = "the map", at=None):
        return _prov(by=by, src=src, at=at)

    # -- systems: a source is held in the system its name (or the data sources map's system_ref) names
    systems = {n["label"]: i for i, n in g.nodes.items() if n["type"] == "System"}
    by_slug = {_slug(lbl): sid for lbl, sid in systems.items()}
    dsrc = {}
    if base.get("baseline_id"):
        dsrc = (_rd(plane, "intents", "m2_baseline", str(base["baseline_id"]), "data_sources.json").get("sources") or {})
        dsrc = dsrc if isinstance(dsrc, dict) else {}
    held: dict[str, str] = {}
    for sid, n in [(i, n) for i, n in g.nodes.items() if n["type"] == "Source"]:
        key, code = _slug(n["label"]), sid.split(":", 1)[1]
        ref = _t((dsrc.get(code) or {}).get("system_ref")).split(".")[-1] if isinstance(dsrc.get(code), dict) else ""
        sysid = by_slug.get(_slug(ref)) if ref else None
        sysid = sysid or by_slug.get(key) or next((i for s, i in by_slug.items() if key and (key in s or s in key) and len(s) > 3), None)
        if sysid and g.edge(sid, sysid, "held_in", ev("the systems list and the catalogue")):
            held[sid] = sysid
    for (a, b, t) in list(g.edges):  # a field is held where its source is
        if t == "uses" and b.startswith("field:") and a in held:
            g.edge(b, held[a], "held_in", ev("the catalogue"))
    for (a, b, t) in list(g.edges):  # the inverse of produced_by, drawn from the process's side
        if t == "produced_by":
            g.edge(b, a, "produces", ev("the process map"))
    for code, row in dsrc.items():  # the data sources map: steps a source is used in
        steps = ((row or {}).get("used_in") or {}).get("steps") if isinstance(row, dict) else None
        for s in steps or []:
            hit = next((i for i, n in g.nodes.items() if n["type"] == "Step" and (i == s or i.endswith(f":{s}"))), None)
            if hit:
                g.edge(hit, f"source:{code}", "produces", ev("the data sources map"))

    # -- pipelines land somewhere: a landing area is a System node (open question 5)
    folder = plane.path("build", "pipelines")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        d = _rd(plane, "build", "pipelines", f.name)
        if f.name.endswith(".commits.json") or not d.get("source") or not d.get("lands_at"):
            continue
        place = str(d["lands_at"])
        lid = g.node(f"system:landing-{_slug(place)}", "System", "Landing zone" if place == "landing" else place.replace("_", " ").capitalize(),
                     ev(f"build/pipelines/{f.name}", "the pipeline contract"), "build")
        pid = f"pipeline:{_slug(d['source'])}"
        g.edge(pid, lid, "lands_at", ev(f"build/pipelines/{f.name}", "the pipeline contract"))
        for sid in [i for i, n in g.nodes.items() if n["type"] == "Source" and _slug(n["label"]) == _slug(d.get("title") or d["source"])]:
            g.edge(sid, lid, "lands_at", ev(f"build/pipelines/{f.name}", "the pipeline contract"))

    # -- marts, from the blueprint's lineage
    pipes = {_slug(n["label"]): i for i, n in g.nodes.items() if n["type"] == "Pipeline"}
    for ln in _l(bp, "lineage"):
        if not (ln.get("mart") and f"measure:{ln.get('measure')}" in g.nodes):
            continue
        mid = f"mart:{_slug(ln['mart'])}"
        g.node(mid, "Mart", str(ln["mart"]), ev("build/blueprint.json", "the blueprint lineage"), "build", g.guard(f"measure:{ln['measure']}"))
        g.edge(f"measure:{ln['measure']}", mid, "fed_by", ev("build/blueprint.json", "the blueprint lineage"))
        pl = pipes.get(_slug(ln.get("source"))) or next((i for i in g.nodes if i == f"pipeline:{_slug(ln.get('source'))}"), None)
        if pl:
            g.edge(mid, pl, "built_by", ev("build/blueprint.json", "the blueprint lineage"))
            for (a, b, t) in list(g.edges):
                if a == pl and t == "owned_by":
                    g.edge(mid, b, "owned_by", ev("build/blueprint.json", "the blueprint lineage"))
        if bp.get("version") is not None:
            g.edge(f"measure:{ln['measure']}", f"blueprint:v{bp['version']}", "defined_in", ev("build/blueprint.json", "the blueprint"))

    # -- documents on the shelves: title only; a private or restricted document is never a node; only a document that names a measure is kept
    folder = plane.path("context", "agent_docs")
    measures = {i: n["label"].lower() for i, n in g.nodes.items() if n["type"] == "Measure" and n.get("restricted_to") is None}
    for agent in sorted(folder.iterdir()) if folder.is_dir() else []:
        for f in sorted(agent.glob("*.json")) if agent.is_dir() else []:
            d = _rd(plane, "context", "agent_docs", agent.name, f.name)
            if d.get("visibility") not in ("shared", "shared_full") or d.get("restricted") or not d.get("title"):
                continue
            title = str(d["title"]).lower()
            hit = [m for m, lbl in measures.items() if len(lbl) > 3 and lbl in title]
            if hit:
                fid = g.node(f"file:{agent.name}-{d.get('doc_id') or f.stem}", "File", str(d["title"]), ev(f"context/agent_docs/{agent.name}", "the shelf"), "define")
                for m in hit:
                    g.edge(m, fid, "defined_in", ev("a document on the shelf"))

    # -- files that arrived with a scan (names only): held in the source's system
    if aid:
        for sdir in [d for d in (plane.path(*_ASSESS, aid, "intake").iterdir() if plane.path(*_ASSESS, aid, "intake").is_dir() else []) if d.is_dir()]:
            sid = f"source:{sdir.name}"
            for fl in _l(_rd(plane, *_ASSESS, aid, "intake", sdir.name, "profile.json"), "files"):
                name = re.sub(r"^[0-9a-f]{8}_", "", str(fl.get("file") or ""))
                if name and sid in g.nodes:
                    fid = g.node(f"file:{sdir.name}-{_slug(name)}", "File", name, ev("a file received in the scan"), "truth", g.guard(sid))
                    if sid in held:
                        g.edge(fid, held[sid], "held_in", ev("a file received in the scan"))

    # -- owner kinds (spec rule 11): business, data, source
    def kind(a: str, who_name, k: str) -> None:
        who = _person(g, people, who_name, ev("the catalogue"), "define") if who_name else None
        if who and a in g.nodes:
            g.edge(a, who, "owned_by", ev("the catalogue"))
            e = g.edges.get((a, who, "owned_by"))
            if e is not None:
                e["owner_kind"] = sorted({*e.get("owner_kind", []), k})
    cat = base.get("catalogue") or {}
    for r in [r for r in cat.get("kpis") or [] if isinstance(r, dict)]:
        mid = f"measure:{cell_text(r.get('KPI ID'))}"
        kind(mid, cell_text(r.get("Business owner")), "business")
        kind(mid, cell_text(r.get("Data owner")), "data")
        kind(f"process:{cell_text(r.get('KPI ID'))}", cell_text(r.get("Process owner")), "business")
    for r in [r for r in cat.get("sources") or [] if isinstance(r, dict)]:
        sid = f"source:{cell_text(r.get('Source ID'))}"
        kind(sid, cell_text(r.get("Data owner")), "data")
        row = dsrc.get(cell_text(r.get("Source ID"))) if isinstance(dsrc, dict) else None
        if isinstance(row, dict):
            kind(sid, _t(row.get("source_owner")), "source")
            kind(sid, _t(row.get("business_owner")), "business")
    for (a, b, t) in list(g.edges):  # a field has its source's owners; a mart its pipeline's owner (data)
        if t == "uses" and b.startswith("field:"):
            for (x, who, tt) in list(g.edges):
                if x == a and tt == "owned_by" and g.edges[(x, who, tt)].get("owner_kind"):
                    g.edge(b, who, "owned_by", ev("the catalogue"))
                    g.edges[(b, who, "owned_by")]["owner_kind"] = list(g.edges[(x, who, tt)]["owner_kind"])
    for (a, b, t) in list(g.edges):
        if t == "owned_by" and a.startswith("mart:"):
            g.edges[(a, b, t)]["owner_kind"] = ["data"]
    _governed_owners(g, plane, base, kind)

    # -- work chain: charter, gap report, blueprint, release
    chain = []
    ch = _rd(plane, "intents", "m1_intent", "outcomes", f"{base['charter_outcome_id']}.json") if re.fullmatch(r"[0-9a-f]{16,64}", str(base.get("charter_outcome_id") or "")) else {}
    if ch.get("signed_at"):
        cid = g.node(f"charter:{base['charter_outcome_id']}", "Charter", "Charter", ev("the charter", "the charter", ch.get("signed_at")), "wall")
        chain.append(cid)
        for (a, b, t) in list(g.edges):  # a measure is written down in the charter when one of its problems is
            if t == "measured_by" and a.startswith("problem:"):
                g.edge(b, cid, "defined_in", ev("the charter"))
    if aid:
        plan = _rd(plane, *_ASSESS, aid, "plan.json")
        gid = g.node(f"gapreport:{aid[:12]}", "GapReport", "Gap report" if plan.get("signed_at") else "Gap report (not signed yet)",
                     ev("the gap report", "the gap analysis", plan.get("signed_at")), "truth")
        if plan.get("signed_at"):
            chain.append(gid)
        for nid, row in newest_by_node(verify_rows(plane, aid)).items():
            if g.edge(nid, gid, "verified_by", ev("the scan", row.get("scanned_by") or "the scan", row.get("scanned_at"))):
                e = g.edges[(nid, gid, "verified_by")]
                e.update({"result": effective(row), "found_in": row.get("found_in"), "scanned_at": row.get("scanned_at"), "claimed": row.get("claimed"),
                          "confirmed_by": row.get("confirmed_by"), "rejected_by": row.get("rejected_by"), "column": row.get("column")})
    if bp.get("version") is not None and bp.get("state", "signed") == "signed":
        chain.append(f"blueprint:v{bp['version']}")
    for mid in [i for i, n in g.nodes.items() if n["type"] == "Mart"]:  # a mart is written down where its measure is
        for (a, b, t) in list(g.edges):
            if t == "fed_by" and b == mid:
                for (x, doc_, tt) in list(g.edges):
                    if x == a and tt == "defined_in":
                        g.edge(mid, doc_, "defined_in", ev("the measure it serves"))
    for n in [i for i, n in g.nodes.items() if n["type"] == "Release"]:
        chain.append(n)
    for a, b in zip(chain, chain[1:]):
        if g.edge(a, b, "led_to", ev("the work order")):
            g.edge(b, a, "came_from", ev("the work order"))


def _governed_owners(g, plane: CompanyPlane, base: dict, kind) -> None:
    """The signed baseline's governed state names each measure's business and data owner: it wins over the catalogue's columns. A mart
    carries its measure's owners, and as source owner the source owners of the measure's sources (their data owner while none is named)."""
    from modules.m2_baseline.store import governed as GS
    bid = str(base.get("baseline_id") or "")
    try:
        gov = GS._read(plane, bid) if re.fullmatch(r"[0-9a-f]{16,64}", bid) else {}
    except (OSError, ValueError):
        gov = {}
    for code, row in (gov or {}).items():
        own = ((row or {}).get("owners") or {}).get("value") if isinstance(row, dict) else None
        mid = f"measure:{code}"
        if not isinstance(own, dict) or mid not in g.nodes:
            continue
        for k in ("business", "data"):
            who = _t(own.get(k))
            if not who:
                continue
            kind(mid, who, k)
            named = _slug(who)
            for key in [e for e in list(g.edges) if e[0] == mid and e[2] == "owned_by" and e[1] != f"person:{named}"]:
                ks = [x for x in g.edges[key].get("owner_kind") or [] if x != k]
                if ks:
                    g.edges[key]["owner_kind"] = ks
                else:
                    g.edges.pop(key)

    def owners(nid: str, k: str) -> list[str]:
        return [b for (a, b, t), e in g.edges.items() if a == nid and t == "owned_by" and k in (e.get("owner_kind") or [])]
    for mart in [i for i, n in g.nodes.items() if n["type"] == "Mart"]:
        measure = next((a for (a, b, t) in g.edges if t == "fed_by" and b == mart and a.startswith("measure:")), None)
        if not measure:
            continue
        add: dict[str, set] = {}
        for k in ("business", "data"):
            for who in owners(measure, k):
                add.setdefault(who, set()).add(k)
        srcs = [b for (a, b, t) in g.edges if a == measure and t == "fed_by" and b.startswith("source:")]
        for src in srcs:
            for who in owners(src, "source") or owners(src, "data"):
                add.setdefault(who, set()).add("source")
        if "data" in {k for ks in add.values() for k in ks}:  # the governed data owner replaces the pipeline owner as data owner
            for key in [e for e in list(g.edges) if e[0] == mart and e[2] == "owned_by" and e[1] not in add]:
                g.edges.pop(key)
        for who, ks in add.items():
            if g.edge(mart, who, "owned_by", _prov_owner()):
                e = g.edges[(mart, who, "owned_by")]
                e["owner_kind"] = sorted(set(e.get("owner_kind") or []) | ks)


def _prov_owner() -> list[dict]:
    from sh_platform.graph.build import _prov
    return _prov(by="the governed state", src="the signed baseline")


# ---- lineage ----------------------------------------------------------------------------------------------------------------------------

UP = (("fed_by", 1), ("held_in", 1), ("lands_at", 1), ("built_by", 1), ("produced_by", 1), ("uses", 0), ("produces", 0))  # 1: follow from -> to
DOWN = (("fed_by", 0), ("held_in", 0), ("lands_at", 0), ("built_by", 0), ("produced_by", 0), ("uses", 1), ("produces", 1),
        ("released_in", 1), ("designed_in", 1), ("defined_in", 1))


def _walk(seeds: list[str], edges: list[dict], rules) -> set[str]:
    seen, todo = set(seeds), list(seeds)
    while todo:
        cur = todo.pop()
        for e in edges:
            for t, out in rules:
                a, b = (e["from"], e["to"]) if out else (e["to"], e["from"])
                if e["type"] == t and a == cur and b not in seen:
                    seen.add(b)
                    todo.append(b)
    return seen


def lineage(g: dict, focus: str) -> dict | None:
    """`view=lineage`: the focus thing's own line, what supplies it (upstream) and what uses it (downstream), no other topic. A field stands
    with its source but other fields of that source drop out. The same walk as the Map page's `lineageIds`. None for an unknown focus."""
    types = {n["id"]: n["type"] for n in g["nodes"]}
    if focus not in types:
        return None
    seeds = [focus, *([e["from"] for e in g["edges"] if e["type"] == "uses" and e["to"] == focus] if types[focus] == "Field" else [])]
    keep = _walk(seeds, g["edges"], UP) | _walk(seeds, g["edges"], DOWN)
    if types[focus] == "Field":
        keep = {i for i in keep if i == focus or types.get(i) != "Field"}
    return {**g, "focus": focus, "nodes": [n for n in g["nodes"] if n["id"] in keep],
            "edges": [e for e in g["edges"] if e["from"] in keep and e["to"] in keep]}


# ---- update moments ----------------------------------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_updates(plane: CompanyPlane) -> list[dict]:
    try:
        d = read_json_strict(plane.path("graph", "updates.json"), list)
    except (OSError, ValueError):
        return []
    return [r for r in d or [] if isinstance(r, dict)]


def _edge_sets(doc: dict) -> dict[str, set]:
    out: dict[str, set] = {}
    for e in doc.get("edges", []):
        for end in (e["from"], e["to"]):
            out.setdefault(end, set()).add((e["from"], e["to"], e["type"]))
    return out


def record_moment(plane: CompanyPlane, moment: str, ref: str, by: str) -> dict:
    """An update moment (charter, gap report, blueprint or release signed; a scan run): rebuild the map now, put a version with `ref` on each
    node the moment added, and write one `updates.json` row. Returns the row ({} when this moment and ref were recorded already and nothing moved)."""
    from sh_platform.graph.build import rebuild
    from sh_platform.graph.versions import append_version
    if moment not in MOMENTS:
        raise ValueError("unknown update moment")
    path = plane.path("graph", "company.json")
    try:
        old = read_json_strict(path, dict) or {}
    except (OSError, ValueError):
        old = {}
    new = rebuild(plane)
    was, now = {n["id"]: n for n in old.get("nodes", [])}, {n["id"]: n for n in new["nodes"]}
    added = sorted(i for i in now if i not in was) if was else []
    removed = sorted(i for i in was if i not in now)
    oe, ne = _edge_sets(old), _edge_sets(new)
    ov, nv = _checks(old), _checks(new)
    checked = sorted(i for i in nv if nv[i] != ov.get(i))  # a new or different scan result is a change too (spec 55: a new version line)
    changed = sorted(i for i in now if i in was and (oe.get(i, set()) != ne.get(i, set()) or was[i]["label"] != now[i]["label"] or i in checked))
    counts: dict[str, int] = {}
    for i in added:
        counts[now[i]["type"]] = counts.get(now[i]["type"], 0) + 1
    if not added and not changed and not removed and any(r.get("moment") == moment and r.get("ref") == ref for r in read_updates(plane)):
        return {}  # the same moment seen again (a sign route and the next read both record it): one row, not two
    row = {"id": secrets.token_hex(6), "moment": moment, "ref": ref, "by": by, "at": _now(), "added": counts, "added_ids": added,
           "changed": len(changed), "removed": len(removed), "line": line_for(moment, by, counts)}
    upath = plane.path("graph", "updates.json")
    with lock_for(upath):
        rows = read_updates(plane)
        upath.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(upath, [*rows, row])
    what = f"Added to the map when the {MOMENTS[moment]} was {'run' if moment == 'scan_run' else 'signed'}"
    for i in added:
        append_version(plane, i, what, by, ref)
    for i in checked if moment == "scan_run" else []:
        res, where = nv[i][0], now.get(nv[i][1] or "", {}).get("label") or "another system"
        append_version(plane, i, f"Checked by the scan: {'found in ' + where if res == 'found_elsewhere' else res}", by, ref)
    return row


def _signers(rec: dict) -> str:
    names = [str(x.get("name")) for x in rec.get("signatures") or rec.get("signed_by") or [] if isinstance(x, dict) and x.get("name")]
    return ", ".join(dict.fromkeys(names)) or str(rec.get("by") or "") or "the signer"


def _charter_aliases(plane: CompanyPlane, outcome_id: str) -> set[str]:
    """A charter moment's ref is the intent id when its sign route recorded it: the intents whose charter is this outcome."""
    from sh_platform.intents import store as istore
    out = {outcome_id}
    for r in istore.read_index(plane):
        try:
            rec = istore.read_intent(plane, r["id"]) or {}
        except istore.Unreadable:
            continue
        if (rec.get("refs") or {}).get("charter_outcome_id") == outcome_id:
            out.add(rec["id"])
    return out


def backfill(plane: CompanyPlane) -> int:
    """Signed records that predate the map (a seeded charter, gap report, blueprint or release): one `updates.json` row each, dated by the
    record's own signature, and a version on each node that record put on the map. Idempotent: a moment already recorded for the same record
    is skipped, so a later read writes nothing. Returns the number of rows written."""
    from sh_platform.graph.build import _newest_baseline, rebuild
    have = {(r.get("moment"), str(r.get("ref"))) for r in read_updates(plane)}
    base, bp, pv = _newest_baseline(plane), _rd(plane, "build", "blueprint.json"), _rd(plane, "build", "prove.json")
    todo = []  # (moment, ref, by, at, pick(doc) -> node ids)
    cid = str(base.get("charter_outcome_id") or "")
    ch = _rd(plane, "intents", "m1_intent", "outcomes", f"{cid}.json") if re.fullmatch(r"[0-9a-f]{16,64}", cid) else {}
    if ch.get("signed_at") and ("charter_signed", cid) not in have and not any(("charter_signed", a) in have for a in _charter_aliases(plane, cid)):
        todo.append(("charter_signed", cid, _signers(ch), ch["signed_at"],
                     lambda d: [f"charter:{cid}", *[e["from"] for e in d["edges"] if e["type"] == "defined_in" and e["to"] == f"charter:{cid}" and not e["from"].startswith("mart:")]]))
    aid = newest_assessment(plane)
    plan = _rd(plane, *_ASSESS, aid, "plan.json") if aid else {}
    if plan.get("signed_at") and ("gap_report_signed", aid) not in have:
        gid = f"gapreport:{aid[:12]}"
        todo.append(("gap_report_signed", aid, _signers(plan), plan["signed_at"],
                     lambda d: [gid, *[e["from"] for e in d["edges"] if e["type"] == "verified_by" and e["to"] == gid]]))
    if bp.get("state") == "signed" and bp.get("version") is not None and ("blueprint_signed", f"v{bp['version']}") not in have:
        at = next((x.get("at") for x in _l(bp, "signed_by") if x.get("at")), None)
        todo.append(("blueprint_signed", f"v{bp['version']}", _signers(bp), at,
                     lambda d: [n["id"] for n in d["nodes"] if n["id"] == f"blueprint:v{bp['version']}" or n["type"] in ("Mart", "Pipeline")]))
    rel = pv.get("release") if isinstance(pv.get("release"), dict) else {}
    if rel.get("state") == "signed" and rel.get("at") and not any(m == "release" and r == str(rel["at"]) for m, r in have):
        todo.append(("release", str(rel["at"]), str(rel.get("by") or "the sponsor"), rel["at"],
                     lambda d: [*[n["id"] for n in d["nodes"] if n["type"] == "Release"], *[e["from"] for e in d["edges"] if e["type"] == "released_in"]]))
    if not todo:
        return 0
    try:
        doc = read_json_strict(plane.path("graph", "company.json"), dict) or rebuild(plane)  # the map as it stands: a read never rebuilds twice
    except (OSError, ValueError):
        doc = rebuild(plane)
    types = {n["id"]: n["type"] for n in doc["nodes"]}
    new_rows, versions = [], {}
    for moment, ref, by, at, pick in todo:
        ids = sorted({i for i in pick(doc) if i in types})
        counts: dict[str, int] = {}
        for i in ids:
            counts[types[i]] = counts.get(types[i], 0) + 1
        new_rows.append({"id": secrets.token_hex(6), "moment": moment, "ref": ref, "by": by, "at": str(at or _now()), "added": counts, "added_ids": ids,
                         "changed": 0, "removed": 0, "line": line_for(moment, by, counts), "backfilled": True})
        what = f"Added to the map when the {MOMENTS[moment]} was signed"
        for i in ids:
            versions.setdefault(i, []).append({"what": what, "by": by, "at": str(at or _now()), "ref": ref})
    upath = plane.path("graph", "updates.json")
    with lock_for(upath):
        rows = read_updates(plane)
        keys = {(r.get("moment"), str(r.get("ref"))) for r in rows}
        fresh = [r for r in new_rows if (r["moment"], r["ref"]) not in keys]  # another reader got here first
        if not fresh:
            return 0
        upath.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(upath, sorted([*rows, *fresh], key=lambda r: str(r.get("at") or "")))  # dated by the record: the newest stays last
    vpath = plane.path("graph", "versions.json")
    with lock_for(vpath):
        try:
            vdoc = read_json_strict(vpath, dict) or {}
        except (OSError, ValueError):
            vdoc = {}
        for nid, add in versions.items():
            merged = sorted([*vdoc.get(nid, []), *add], key=lambda r: str(r.get("at") or ""))
            vdoc[nid] = [{**r, "v": n + 1} for n, r in enumerate(merged)]
        write_json_atomic(vpath, vdoc)
    from sh_platform.graph.hooks import mark_dirty
    mark_dirty(plane)  # the next read rebuilds with the signed records' owners and links
    return len(fresh)


def try_backfill(plane: CompanyPlane) -> None:
    """backfill for a read: a map failure never fails the page."""
    try:
        backfill(plane)
    except Exception:  # noqa: BLE001 - the page is served whatever the backfill does
        log.warning("The knowledge map could not backfill the signed records.", exc_info=True)


def try_moment(plane: CompanyPlane, moment: str, ref: str, by: str) -> None:
    """record_moment for a sign route: a map failure never blocks or undoes a signature."""
    try:
        record_moment(plane, moment, ref, by)
    except Exception:  # noqa: BLE001 - the signature stands whatever the map does
        logging.getLogger(__name__).warning("The knowledge map was not updated for %s.", moment, exc_info=True)


def _checks(doc: dict) -> dict[str, tuple]:
    """Each checked node's scan result as drawn on its `verified_by` edge: (result, found in)."""
    return {e["from"]: (e.get("result"), e.get("found_in")) for e in doc.get("edges", []) if e["type"] == "verified_by"}


NOUN = {"Intent": "intent", "Field": "field", "System": "system", "Source": "source", "File": "file", "Mart": "mart", "Measure": "measure", "Process": "process",
        "Pipeline": "pipeline", "Charter": "charter", "GapReport": "gap report", "Blueprint": "blueprint", "Release": "release"}


def gained(counts: dict[str, int]) -> str:
    """"4 fields and 2 systems", over the kinds a person reads on the map (people, rules and cards are not counted)."""
    parts = [f"{n} {NOUN[t]}{'' if n == 1 else 's'}" for t, n in ((t, counts.get(t, 0)) for t in NOUN) if n]
    return " and ".join([", ".join(parts[:-1]), parts[-1]] if len(parts) > 1 else parts)


def line_for(moment: str, by: str, counts: dict[str, int]) -> str:
    """The fixed template line (the spec's fallback; no model call is made here)."""
    who = (by or "someone").split(" ")[0]
    what = gained(counts)
    if moment == "scan_run":
        return "The scan checked what people said about their data" + (f" and the map gained {what}" if what else "")
    word = {"charter_signed": "charter signed", "gap_report_signed": "gap report signed", "blueprint_signed": "blueprint signed", "release": "release signed"}[moment]
    return (f"The map gained {what} from the {word} by {who}" if what else f"The map was updated after the {word} by {who}")


def scan_and_record(plane: CompanyPlane, aid: str, by: str) -> None:
    """Module 3's scan step (each file received is profiled): check the claims, then the scan_run moment. Never fails the upload."""
    try:
        scan_assessment(plane, aid, by)
        record_moment(plane, "scan_run", aid, by)
    except Exception:  # noqa: BLE001 - the file is kept whatever the map does
        log.warning("The knowledge map was not updated after a scan.", exc_info=True)


def install_scan_hook() -> None:
    """Module 3 is not ours to edit: wrap its upload step (`_take`, looked up by name at call time) so every profiled file runs the scan and
    the scan_run moment. Idempotent. The one-line call in module 3 (Shared files needed) would replace this wrapper."""
    from modules.m3_connect.api import intake as m3
    if getattr(m3._take, "_km_hooked", False):
        return
    take = m3._take

    def hooked(ctx, request, source_id, filename, data, by, viewer=None):
        out = take(ctx, request, source_id, filename, data, by, viewer)
        scan_and_record(ctx.plane, ctx.aid, getattr(viewer, "name", None) or by)
        return out
    hooked._km_hooked = True
    m3._take = hooked


# ---- the scan ----------------------------------------------------------------------------------------------------------------------------

def scan_assessment(plane: CompanyPlane, aid: str, by: str) -> dict:
    """Checks each catalogue field of a source that has a profile: its own columns first (matched, medium or better: available), then every
    other source's columns (a high match: found elsewhere), else missing. Names and types only. Appends rows to `verify.json` and returns counts."""
    from modules.m3_connect.domain.intake_match import _name_score
    from sh_platform.graph.build import _newest_baseline, _t as cell_text
    base = _newest_baseline(plane)
    cat = base.get("catalogue") or {}
    tables = {cell_text(t.get("Item ID")): cell_text(t.get("Source ID")) for t in cat.get("tables") or []}
    sources = {cell_text(s.get("Source ID")): s for s in cat.get("sources") or []}
    prof, idir = {}, plane.path(*_ASSESS, aid, "intake")
    for d in (idir.iterdir() if idir.is_dir() else []):
        p = _rd(plane, *_ASSESS, aid, "intake", d.name, "profile.json")
        if p:
            prof[d.name] = [c for t in _l(p, "tables") for c in _l(t, "columns")]
    held = {}
    try:
        doc = read_json_strict(plane.path("graph", "company.json"), dict) or {}
        held = {e["from"].split(":", 1)[1]: e["to"] for e in doc.get("edges", []) if e["type"] == "held_in" and e["from"].startswith("source:")}
    except (OSError, ValueError):
        pass
    scan_id, at, rows = secrets.token_hex(4), _now(), []
    for f in [f for f in cat.get("fields") or [] if isinstance(f, dict)]:
        fid, src = cell_text(f.get("Field ID")), tables.get(cell_text(f.get("Item ID")), "")
        name = cell_text(f.get("Field name as in the source"))
        if not (fid and src in prof):
            continue  # not scanned: no file has arrived for its source
        avail = cell_text((sources.get(src) or {}).get("Availability")).lower()
        claimed = "available" if avail.startswith("available") else "missing" if avail.startswith(("not", "no")) else "unknown"
        mine = next((c for c in prof[src] if c.get("field_id") == fid and (c.get("match") or {}).get("confidence") in CONFIDENT), None)
        row = {"node": f"field:{fid}", "claimed": claimed, "claimed_by": cell_text((sources.get(src) or {}).get("Data owner")) or None, "scan_id": scan_id,
               "scanned_at": at, "scanned_by": by, "found_in": None, "column": None, "confidence": None, "result": "missing"}
        if mine:
            row.update(result="available", column=mine.get("name"), confidence=(mine.get("match") or {}).get("confidence"))
        else:
            for other, cols in prof.items():
                hit = next((c for c in cols if other != src and _name_score(str(c.get("name") or ""), name)[0] >= 3), None)
                if hit:
                    row.update(result="found_elsewhere", found_in=held.get(other) or f"source:{other}", column=hit.get("name"), confidence="high")
                    break
        rows.append(row)
    path = plane.path(*_ASSESS, aid, "verify.json")
    with lock_for(path):
        old = _l(_rd(plane, *_ASSESS, aid, "verify.json"), "rows")
        write_json_atomic(path, {"rows": [*old, *rows]})
    out = {"available": 0, "missing": 0, "found_elsewhere": 0}
    for r in rows:
        out[r["result"]] += 1
    return {"checked": len(rows), **out}


def decide(plane: CompanyPlane, aid: str, node: str, by: str, reason: str | None) -> dict | None:
    """The source owner's answer on the newest 'found elsewhere' row of a node: confirm (reason None) or reject (reason). None if there is none."""
    path = plane.path(*_ASSESS, aid, "verify.json")
    with lock_for(path):
        rows = _l(_rd(plane, *_ASSESS, aid, "verify.json"), "rows")
        row = next((r for r in reversed(rows) if r["node"] == node), None)
        if not row or row.get("result") != "found_elsewhere" or row.get("confirmed_by") or row.get("rejected_by"):
            return None
        row.update({"confirmed_by": by, "confirmed_at": _now()} if reason is None else {"rejected_by": by, "rejected_at": _now(), "reason": reason})
        write_json_atomic(path, {"rows": rows})
    return row
