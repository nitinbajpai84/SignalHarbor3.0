"""Card B3: nodes and edges of a build plan's architecture diagram (Sources > Bronze > Silver > Gold > Consumers).

Reads the newest `build/<pid>/plan-v<n>.json` (written by B2, fact 5). Pure reading: no model, no writes. The layout is done in the UI."""
from __future__ import annotations

import logging
import re

from sh_platform.jsonfile import read_json_strict

log = logging.getLogger(__name__)
LAYERS = ("source", "bronze", "silver", "gold", "consumer")
_PID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
CONSUMERS = "consumers"


class Missing(Exception):
    pass


def latest_plan(plane, pid: str) -> dict:
    if not _PID.match(pid or ""):
        raise Missing("That project id is not valid.")
    folder = plane.path("build", pid)
    best = None
    for f in folder.glob("plan-v*.json") if folder.is_dir() else ():
        m = re.fullmatch(r"plan-v(\d+)\.json", f.name)
        if m and (best is None or int(m[1]) > best[0]):
            best = (int(m[1]), f)
    if best is None:
        raise Missing("This project has no build plan yet.")
    return read_json_strict(best[1])


def _in_catalogue(plane, name: str) -> bool:
    try:
        from sh_platform.v1 import e0a_catalogue as C
        return C.layer_of(plane, name) is not None  # D1 helper; signature per fact 4 is (plane, table)
    except Exception:  # D1 not landed yet, or the catalogue cannot be read: treat silver as existing
        log.debug("catalogue lookup unavailable for %s", name)
        return True


def diagram(plan: dict, plane=None) -> dict:
    nodes, edges, ids = [], [], set()

    def add(nid: str, label: str, layer: str, new: bool = False, note: str = "") -> None:
        if nid not in ids:
            ids.add(nid)
            nodes.append({"id": nid, "label": label, "layer": layer, "new": new, "note": note})

    for s in plan.get("sources") or []:
        add(f"source:{s['code']}", s["code"], "source", note=f"{s.get('kind', '')} · {s.get('owner') or 'no owner named'}")
    for t in plan.get("tables") or []:
        layer = t.get("layer") if t.get("layer") in ("bronze", "silver", "gold") else "silver"
        new = bool(t.get("new")) or layer != "silver" or (plane is not None and not _in_catalogue(plane, t["name"]))
        add(f"table:{t['name']}", t["name"], layer, new, t.get("purpose") or "")
    for t in plan.get("tables") or []:  # a bronze table named bronze_<code>_<layout> hangs off its source
        if t.get("layer") == "bronze":
            for s in plan.get("sources") or []:
                if t["name"].startswith(f"bronze_{s['code']}_"):
                    edges.append({"from": f"source:{s['code']}", "to": f"table:{t['name']}"})
    links = [(e["from"], e["to"]) for e in plan.get("lineage") or []]
    links += [(d, t["name"]) for t in plan.get("tables") or [] for d in t.get("depends_on") or []]
    for a_, b_ in links:  # a core silver table the plan reads but does not rebuild still sits between bronze and gold
        for n in (a_, b_):
            if f"table:{n}" not in ids and f"source:{n}" not in ids:
                add(f"table:{n}", n, "silver", note="company model, unchanged")
    for a_, b_ in links:
        a, b = (f"table:{a_}", f"table:{b_}")
        if a not in ids and f"source:{a_}" in ids:
            a = f"source:{a_}"
        if a in ids and b in ids and {"from": a, "to": b} not in edges:
            edges.append({"from": a, "to": b})
    golds = [n for n in nodes if n["layer"] == "gold"]
    if golds:
        add(CONSUMERS, "Dashboards and people", "consumer", note="Shown in Consume")
        edges += [{"from": n["id"], "to": CONSUMERS} for n in golds]
    return {"project_id": plan.get("project_id"), "version": plan.get("version"), "state": plan.get("state") or "draft",
            "layers": list(LAYERS), "nodes": nodes, "edges": edges}
