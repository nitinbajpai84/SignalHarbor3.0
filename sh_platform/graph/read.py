"""`graph_for(plane, viewer)` and `summary(plane, viewer)`: the graph as one person may see it (the same Viewer as the profile).

A node with `restricted_to` is a silhouette to anyone not on the list (the company admin passes only while nobody is named, A-069): `{id: restricted-N, type, restricted,
label: "A restricted <type>"}`, the id opaque so no name leaks. An edge is kept when both ends are visible, or when it is structural
(measured_by, fed_by); then it carries no provenance and is labelled restricted. Account binding is a profile matter: names only here.
"""
import hashlib
import threading

from sh_platform.graph.models import STRUCTURAL
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane
from sh_platform.profile.view import Viewer, _passes

EMPTY = {"version": 1, "built_at": None, "nodes": [], "edges": []}


def _sees(node: dict, viewer: Viewer) -> bool:
    """The profile's own test (`view._passes`): the admin passes; a named person passes by account where the name was bound to accounts, by
    display name otherwise, and never by a name another account shares."""
    names = node.get("restricted_to")
    return names is None or _passes(frozenset(names), node.get("restricted_bound") or {}, viewer)


_cache: dict[tuple, dict] = {}  # ponytail: unbounded (one entry per company file version and viewer); evict old versions if it ever grows
_lock = threading.Lock()


def graph_for(plane: CompanyPlane, viewer: Viewer) -> dict:
    """The viewer's gated graph, cached per (graph file version, whole viewer): another viewer never gets this one. Treat the result as read-only."""
    path = plane.path("graph", "company.json")
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size, viewer)  # the file's version, not only built_at: an edit with the same built_at still misses
    except OSError:
        return _gate(plane, viewer)
    with _lock:
        hit = _cache.get(key)
    if hit is None:
        hit = _gate(plane, viewer)
        with _lock:
            for old in [k for k in _cache if k[0] == key[0] and k[1:3] != key[1:3]]:
                del _cache[old]  # an older file version is never read again
            _cache[key] = hit
    return hit


def _gate(plane: CompanyPlane, viewer: Viewer) -> dict:
    doc = read_json_strict(plane.path("graph", "company.json"), dict) or EMPTY
    hidden = [n["id"] for n in doc["nodes"] if not _sees(n, viewer)]
    # numbered in hash order, not name order, so a silhouette's number says nothing about the hidden name
    alias = {old: f"restricted-{i}" for i, old in enumerate(sorted(hidden, key=lambda x: hashlib.sha256(x.encode()).hexdigest()), 1)}
    edges, dropped = [], set()
    for e in doc["edges"]:
        if e["from"] not in alias and e["to"] not in alias:
            edges.append({k: e[k] for k in ("from", "to", "type")})
        elif e["type"] in STRUCTURAL:
            edges.append({"from": alias.get(e["from"], e["from"]), "to": alias.get(e["to"], e["to"]), "type": e["type"], "restricted": True})
        else:
            dropped.update((e["from"], e["to"]))
    linked = {x for e in edges for x in (e["from"], e["to"])}
    nodes = []
    for n in doc["nodes"]:
        if n["id"] in alias:
            nodes.append({"id": alias[n["id"]], "type": n["type"], "restricted": True, "label": f"A restricted {n['type'].lower()}"})
        elif n["type"] == "Person" and n["id"] in dropped and n["id"] not in linked:
            continue  # a person whose only links were to hidden things would say who owns them
        else:
            nodes.append({"id": n["id"], "type": n["type"], "label": n["label"]})  # labels only: no provenance, room or names lists
    return {"version": doc["version"], "built_at": doc["built_at"], "nodes": sorted(nodes, key=lambda n: n["id"]), "edges": edges}


def summary(plane: CompanyPlane, viewer: Viewer) -> dict:
    """Counts per type and the holes, over this viewer's graph: a Measure with no Source, a Source with no owner, a Problem with no Measure."""
    g = graph_for(plane, viewer)
    counts: dict[str, int] = {}
    for n in g["nodes"]:
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    has = {(e["from"], e["type"]) for e in g["edges"]}

    def holes(type_: str, edge: str) -> list[dict]:
        return [{"id": n["id"], "label": n["label"]} for n in g["nodes"] if n["type"] == type_ and (n["id"], edge) not in has]
    return {"counts": counts, "nodes": len(g["nodes"]), "edges": len(g["edges"]),
            "holes": {"measure_no_source": holes("Measure", "fed_by"), "source_no_owner": holes("Source", "owned_by"),
                      "problem_no_measure": holes("Problem", "measured_by")}}
