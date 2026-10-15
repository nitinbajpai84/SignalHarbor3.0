"""I5: the 1.0 intents on the company map. intent -solves-> problem -uses-> source -feeds-> KPI, source -feeds-> table -feeds-> KPI,
and a document source -defines-> the KPI it defines.

Pattern copied from sh_platform/graph/intent_nodes.py: `_register()` widens models' vocabulary, `add_sow_nodes(g, plane, people)` reads
`intents/*/sow.json` by path and writes nothing. The graph is a projection rebuilt from records, so `build.rebuild` must call this
(one line, a shared edit); `catalogue_scan.scan` marks the graph dirty after every write.
"""
import logging
import re

from modules.m2_baseline.domain.catalogue import match_name
from sh_platform.graph import models
from sh_platform.jsonfile import read_json_strict

log = logging.getLogger(__name__)


def _register() -> None:
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "Intent", "Table")))
    models.ROOMS = tuple(dict.fromkeys((*models.ROOMS, "intent")))
    e = models.EDGE_TYPES
    e.setdefault("solves", (["Intent"], ["Problem"]))
    e.setdefault("feeds", (["Source", "Table"], ["Measure", "Table"]))
    e.setdefault("defines", (["Source"], ["Measure"]))
    for end, add in ((0, "Problem"), (1, "Source")):
        if add not in e["uses"][end]:
            e["uses"][end].append(add)


def table_id(name: str) -> str:
    return "table:" + re.sub(r"[^a-z0-9_]+", "_", str(name).lower()).strip("_")


def _sows(plane) -> list[tuple[str, dict]]:
    root = plane.path("intents")
    out = []
    for d in sorted(root.iterdir() if root.is_dir() else []):
        f = d / "sow.json"
        if not f.is_file():
            continue
        try:
            sow = read_json_strict(f, dict)
        except (OSError, ValueError):
            log.warning("an intent of work could not be read for the company graph")
            continue
        if isinstance(sow.get("goal"), dict):  # the 1.0 shape; a 2.0 record in the same folder is not ours
            out.append((d.name, sow))
    return out


def add_sow_nodes(g, plane, people: dict | None = None) -> None:
    from sh_platform.graph.build import _person, _prov
    _register()
    people = {} if people is None else people
    for iid, sow in _sows(plane):
        prov = _prov(by="the intent of work", src=f"intents/{iid}/sow.json")
        goal = sow["goal"]
        nid = g.node(f"intent:{iid}", "Intent", str(sow.get("title") or goal.get("line") or "An intent"), prov, "intent")
        pid = None
        if goal.get("line"):
            pid = g.node(f"problem:sow-{iid}", "Problem", str(goal["line"]), prov, "intent")
            g.edge(nid, pid, "solves", prov)
        kpis = {}
        for k in sow.get("kpis") or []:
            if isinstance(k, dict) and k.get("code"):
                kpis[str(k["code"])] = g.node(f"measure:{k['code']}", "Measure", str(k.get("name") or k["code"]), prov, "intent")
        by_name = {match_name(k.get("name") or ""): kpis[str(k["code"])] for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")}
        by_name.update({match_name(c): m for c, m in kpis.items()})
        for s in sow.get("sources") or []:
            if not (isinstance(s, dict) and s.get("id")):
                continue
            sp = _prov(by="the intent of work", src=str(s.get("sample_path") or f"intents/{iid}/sow.json"))
            sn = g.node(f"source:{s['id']}", "Source", str(s.get("name") or s["id"]), sp, "intent")
            if pid:
                g.edge(pid, sn, "uses", sp)
            who = _person(g, people, s.get("owner"), sp, "intent")
            if who:
                g.edge(sn, who, "owned_by", sp)
            for d in (s.get("read") or {}).get("definitions") or []:
                m = by_name.get(match_name(d.get("term") or ""))
                if m:
                    g.edge(sn, m, "defines", [{"mark": "stated", "by": d.get("file"), "at": None, "from": d.get("quote")}])
        for k in sow.get("kpis") or []:
            for sid in (k.get("source_ids") or []) if isinstance(k, dict) and str(k.get("code")) in kpis else []:
                g.edge(f"source:{sid}", kpis[str(k["code"])], "feeds", prov)
        for c in sow.get("catalogue") or []:
            if not (isinstance(c, dict) and c.get("table")):
                continue
            tid = g.node(table_id(c["table"]), "Table", str(c["table"]), prov, "intent")
            g.nodes[tid]["layer"] = c.get("layer")
            g.edge(f"source:{c.get('source_id')}", tid, "feeds", prov)
            for code in c.get("feeds_kpis") or []:
                if str(code) in kpis:
                    g.edge(tid, kpis[str(code)], "feeds", prov)
