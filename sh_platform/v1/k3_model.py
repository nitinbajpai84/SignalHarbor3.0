"""K3 (DM1) The Map's "Data model" view: bronze, silver and gold side by side, with what each table feeds and reads.

One read-only payload, built from records that already exist: the governed catalogue (e0a_catalogue: core DBML plus approved company
additions, column meanings from its notes), the layer registry (bronze and gold tables), the build plans (what each gold table reads),
the dashboards' tile SQL (what reads a gold table) and the warehouse (row counts only, never rows). Nothing is listed by hand.

Access follows the rest of the Map (k3_map): the data team sees every layer; anyone else sees only the gold tables of projects they may
see (G1) and what those feed. Bronze and silver detail is the data team's.
"""
from __future__ import annotations

import logging
import re

from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import k3_map as K
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import wh
from sh_platform.v1.agent_tools import AgentTools

log = logging.getLogger(__name__)

LAYERS = {
    "bronze": {"label": "Bronze", "title": "as it arrived", "meaning": "Each source's file, kept exactly as received, with when it was loaded."},
    "silver": {"label": "Silver", "title": "the office's clean model, shared by every project",
               "meaning": "Cleaned, matched and kept with its history. Grouped the way the core model is."},
    "gold": {"label": "Gold", "title": "ready-made figures", "meaning": "One table per question a project answers. Dashboards read only these."},
}
ADDED = "added"  # the group key of tables a company's approved versions added
_WORD = {"rag": "search"}  # DBML group names in plain words: documents_and_rag reads as "Documents and search"


def _plain(name: str) -> str:
    return " ".join(_WORD.get(w, w) for w in re.sub(r"[_\s]+", " ", name).strip().split()).capitalize()


def _shown(layer: str, real: str) -> str:
    """The layer-prefixed name: bronze_x -> bronze.x, gold_x -> gold.x, a silver table keeps its name."""
    return f"{layer}.{real.removeprefix(layer + '_')}" if layer != "silver" else f"silver.{real}"


def _link_words(table: str, col: dict, refs: list[dict]) -> str:
    """A column with no note of its own: what the model says about it (a key, or the table it points to)."""
    for r in refs:
        if r["from"]["table"] == table and col["name"] in r["from"]["columns"]:
            return f"Links to {r['to']['table']}"
    return "Identifies the row" if col.get("pk") else ""


def _edges(plane, viewer) -> tuple[set[tuple[str, str]], dict[str, dict]]:
    """(from, to) real table names, and plan tables by name, from the newest build plans of projects the viewer may see."""
    from sh_platform.v1 import b6_plan as B
    edges, tables = set(), {}
    for p in P.all_projects(plane):
        if G1.may_see_project(plane, viewer, p["id"]) == "none":
            continue
        plan = B.get(plane, p["id"]) or {}
        for t in plan.get("tables") or []:
            tables.setdefault(t["name"], {**t, "project_id": p["id"], "proposed_by": plan.get("proposed_by")})
            edges.update((d, t["name"]) for d in t.get("depends_on") or [])
        edges.update((str(e["from"]), str(e["to"])) for e in plan.get("lineage") or [] if e.get("from") and e.get("to"))
    return edges, tables


def _close(start: str, step: dict[str, set[str]]) -> list[str]:
    seen, todo = [], [start]
    while todo:
        for n in sorted(step.get(todo.pop(), ())):
            if n not in seen and n != start:
                seen.append(n)
                todo.append(n)
    return seen


def _loaded(plane, shown: dict[str, dict], systems: dict[str, dict], reg: dict) -> tuple[dict[tuple[str, str], int | None], dict[str, str]]:
    """DM3: the edges of what was actually loaded, by (from id, to id) -> rows. Source -> bronze (the table's `bronze_<source>_` name or its registry
    source; rows = the source's records) and bronze (or, with none, the source) -> each silver table whose rows point at a source record
    (rows = how many). One grouped query per silver table, counts only. Returns also node id -> source system name. Empty for a viewer without silver."""
    silver = [n for n, t in shown.items() if t["layer"] == "silver"]
    if not systems or not silver:
        return {}, {}
    names = {c: str(sy["name"]) for c, sy in systems.items()}
    bronze: dict[str, list[str]] = {}
    for n, t in shown.items():
        if t["layer"] == "bronze":
            code = max((c for c in systems if n.startswith(f"bronze_{c}_")), key=len, default=None) or K._canon(str((reg.get(n) or {}).get("source")), set(systems))
            if code in systems:
                bronze.setdefault(code, []).append(t["id"])
    src = lambda c: f"source:{names[c]}"  # noqa: E731 - the id a bronze table's registry source already gives its node
    links: dict[tuple[str, str], int | None] = {(src(c), b): None for c, bs in bronze.items() for b in bs}
    try:
        with wh.connect(plane, read_only=True) as con:
            have = {r[0] for r in con.execute("select table_name from information_schema.columns where table_schema = 'main' and column_name = 'source_record_id'").fetchall()}
            join = "join source_records r on r.id = {t}.source_record_id join source_batches b on b.id = r.source_batch_id join source_systems sy on sy.id = b.source_system_id"
            for code, n in con.execute("select sy.source_code, count(*) from source_records r join source_batches b on b.id = r.source_batch_id "
                                       "join source_systems sy on sy.id = b.source_system_id group by 1").fetchall():
                for b in bronze.get(code, []):
                    links[(src(code), b)] = n
            for name in silver:
                if name not in have or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
                    continue
                for code, n in con.execute(f'select sy.source_code, count(*) from "{name}" t {join.format(t="t")} group by 1').fetchall():  # name is a catalogue table
                    if code in systems and n:
                        for a in bronze.get(code) or [src(code)]:
                            links[(a, shown[name]["id"])] = n
    except Exception:  # noqa: BLE001 - the graph opens without the load edges
        log.warning("the data model could not read what was loaded", exc_info=True)
    return links, {src(c): n for c, n in names.items()}


def _lineage(out, reg, plan, titles, readers, edges, cat, systems, plane=None) -> dict:
    """DM2: the same records as a graph (DM3: plus the edges of what was actually loaded, with their row counts). Nodes: source, bronze, silver, gold, dashboard, report, project. Edges (from, to): source->bronze (the registry),
    plan depends_on (bronze->silver, silver->gold), gold->dashboard/report (tile SQL), gold->project (who owns it). Only nodes the viewer was given."""
    shown = {t["real"]: t for t in out}
    nodes = {t["id"]: {"id": t["id"], "kind": t["layer"], "label": t["id"], "used_by": 0} for t in out}
    links: set[tuple[str, str]] = set()
    rows, src_names = _loaded(plane, shown, systems, reg) if plane is not None else ({}, {})
    for (a, b) in rows:
        for x in (a, b):
            if x in src_names:
                nodes.setdefault(x, {"id": x, "kind": "source", "label": src_names[x], "used_by": 0})
        links.add((a, b))
    for a, b in edges:
        if a in shown and b in shown:
            links.add((shown[a]["id"], shown[b]["id"]))
    for name, t in shown.items():
        if t["layer"] == "bronze" and t["source"]:
            nodes.setdefault(f"source:{t['source']}", {"id": f"source:{t['source']}", "kind": "source", "label": t["source"], "used_by": 0})
            links.add((f"source:{t['source']}", t["id"]))
        if t["layer"] == "gold":
            for pid in (reg.get(name) or {}).get("project_ids") or [(plan.get(name) or {}).get("project_id")]:
                if pid in titles:
                    nodes.setdefault(f"project:{pid}", {"id": f"project:{pid}", "kind": "project", "label": titles[pid], "used_by": 0})
                    links.add((t["id"], f"project:{pid}"))
        for r in readers.get(name, []) if t["layer"] == "gold" else []:
            nodes.setdefault(r["id"], {"id": r["id"], "kind": r["kind"], "label": r["label"], "used_by": 0})
            links.add((t["id"], r["id"]))
    down: dict[str, set[str]] = {}
    for a, b in links:
        down.setdefault(a, set()).add(b)
    for n in nodes.values():
        if n["kind"] == "silver":
            n["used_by"] = sum(1 for x in _close(n["id"], down) if x.startswith("project:"))
    return {"nodes": sorted(nodes.values(), key=lambda n: n["id"]), "edges": [{"from": a, "to": b, **({"rows": rows[(a, b)]} if rows.get((a, b)) else {})} for a, b in sorted(links)]}


def model(plane, viewer) -> dict:
    team = K._team(viewer)
    tools = AgentTools(plane, viewer, "span")
    cur = E.current(plane)
    made = [v for v in E.versions(plane) if v["version"] > 1 and v.get("approved_by")]
    cat = tools._catalogue()  # silver from the model; bronze and gold only where the viewer may see a project of the table
    edges, plan = _edges(plane, viewer)
    counts = tools._counts({n for n, t in cat.items() if team or t["layer"] == "gold"})
    titles = {p["id"]: str(p.get("title") or "") for p in tools._projects()}
    systems = K._systems(plane) if team else {}
    known = set(systems) | {r["source"] for r in cat.values() if r.get("source")}
    by_name = {t["name"]: t for t in cur["tables"]}
    reg = E._registry(plane)

    down: dict[str, set[str]] = {}
    up: dict[str, set[str]] = {}
    for a, b in edges:
        down.setdefault(a, set()).add(b)
        up.setdefault(b, set()).add(a)
    reports = set()
    try:
        from sh_platform.v1 import cx_dash
        reports = {r["id"] for r in cx_dash.company_reports(plane, viewer)}
    except Exception:  # noqa: BLE001 - a map opens without the reports list
        log.warning("the data model could not list the company reports", exc_info=True)
    readers: dict[str, list[dict]] = {}  # gold table -> dashboards and reports that read it
    for d in K._dashboards(plane, viewer, team):
        kind = "report" if d.get("id") in reports else "dashboard"
        for g in dict.fromkeys(m for t in d.get("tiles") or [] for m in K._GOLD.findall(str(t.get("sql") or ""))):
            readers.setdefault(g, []).append({"kind": kind, "id": f"dash:{d.get('id')}", "label": d.get("title") or "Dashboard", "project": titles.get(d.get("project_id") or "", "")})

    def of_project(name: str) -> list[str]:
        return [titles[p] for p in (reg.get(name) or {}).get("project_ids", []) if p in titles] or [titles[p] for p in [(plan.get(name) or {}).get("project_id")] if p in titles]

    def columns(name: str, layer: str) -> list[dict]:
        if layer == "silver":
            return [{"name": c["name"], "type": c["type"], "meaning": c.get("note") or _link_words(name, c, cur["refs"]), "required": not c.get("null", True)}
                    for c in cat[name]["columns"]]
        src = {c["name"]: c for c in (plan.get(name) or {}).get("columns") or []}
        return [{"name": c["name"], "type": c.get("type") or "text", "meaning": ("From " + str(src[c["name"]]["from"])) if src.get(c["name"], {}).get("from")
                 else ("As received" if layer == "bronze" else ""), "required": False} for c in cat[name]["columns"]]

    out = []
    order = {n: i for i, n in enumerate(by_name)}  # silver in the model's own order (so its groups follow it); the rest by name
    for name, t in sorted(cat.items(), key=lambda kv: (kv[1]["layer"] != "silver", order.get(kv[0], 0), kv[0])):
        layer = t["layer"]
        if not team and layer != "gold":
            continue
        row = counts.get(name)
        silver = by_name.get(name) if layer == "silver" else None
        added = bool(silver and silver["layer"] == "company")
        r = reg.get(name) or {}
        sy = systems.get(K._canon(str(r.get("source")), known)) if layer == "bronze" else None
        below = _close(name, down)
        feeds = [{"kind": "table", "id": _shown(cat[n]["layer"], n), "label": _shown(cat[n]["layer"], n), "project": ", ".join(of_project(n))}
                 for n in below if n in cat]
        for n in [name, *below]:
            feeds += [r for r in readers.get(n, []) if r not in feeds]  # a dashboard on two of the gold tables is listed once
        group = ADDED if added else (silver["group"] if silver else "")
        out.append({
            "id": _shown(layer, name), "real": name, "layer": layer, "group": group, "group_label": "Added for this office" if added else _plain(group),
            "added": added, "rows": row[0] if row else None, "loaded": bool(row and row[0]),
            "meaning": " ".join(str((plan.get(name) or {}).get("purpose") or ("" if silver and not t["note"] else t["purpose"]) or "").split()),
            "source": (sy or {}).get("name") or (str(r.get("source")) if r.get("source") else ""), "cadence": (sy or {}).get("cadence") or "",
            "owner": (sy or {}).get("owner") or (plan.get(name) or {}).get("proposed_by") or "",
            "project": ", ".join(of_project(name)), "columns": columns(name, layer),
            "reads": sorted(_shown(cat[n]["layer"], n) for n in _close(name, up) if n in cat),
            "feeds": feeds,
        })
    n_add = len(made)
    lineage = _lineage(out, reg, plan, titles, readers, edges, cat, systems, plane)
    return {"version": cur["version"], "additions": n_add, "team": team, "layers": LAYERS,
            "tables": out, "lineage": lineage, "counts": {"loaded": sum(1 for t in out if t["loaded"]), "whole": len(out)},
            "intro": f"How data is kept, in three layers. Model version {cur['version']}: the core model Span starts from"
                     + (f", plus {n_add} approved addition{'s' if n_add != 1 else ''}." if n_add else ".")}
