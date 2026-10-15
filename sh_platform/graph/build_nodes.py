"""M4: build nodes on the company map: Blueprint, Pipeline and Release, with sign-offs and commits (SHAPES sections 2, 3, 5, 10; A-072).

Reads `build/blueprint.json`, `build/pipelines/*.json` (+ `<source>.commits.json`) and `build/prove.json` by path. A missing file adds nothing.
`record_commit(plane, source, what, by)` appends to `build/pipelines/<source>.commits.json` (`{"commits": [{"id", "when", "what", "by"}]}`).
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sh_platform.graph import models
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)
_BP, _PL, _PV = "build/blueprint.json", "build/pipelines/", "build/prove.json"


def _register() -> None:
    """models.py is not ours to edit: add the build types and edges to its vocabulary here (idempotent)."""
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "Pipeline", "Blueprint", "Release")))
    models.EDGE_TYPES.setdefault("built_by", (["Measure"], ["Pipeline"]))
    models.EDGE_TYPES.setdefault("designed_by", (["Blueprint"], ["Person"]))
    models.EDGE_TYPES.setdefault("designed_in", (["Measure"], ["Blueprint"]))
    models.EDGE_TYPES.setdefault("released_by", (["Release"], ["Person"]))
    models.EDGE_TYPES.setdefault("tested_by", (["Release"], ["Person"]))
    models.EDGE_TYPES.setdefault("released_in", (["Measure"], ["Release"]))
    own = models.EDGE_TYPES["owned_by"][0]
    if "Pipeline" not in own:
        own.append("Pipeline")


def _rd(plane: CompanyPlane, *parts: str) -> dict:
    try:
        d = read_json_strict(plane.path(*parts))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _l(d: dict, k: str) -> list[dict]:
    return [x for x in d.get(k) or [] if isinstance(x, dict)]


def _slug(t: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(t or "").lower()).strip("-")


def record_commit(plane: CompanyPlane, source: str, what: str, by: str) -> dict:
    """Append one commit for a pipeline's code; the runner calls this when it changes the pipeline. Returns the commit."""
    path = plane.path("build", "pipelines", f"{_slug(source)}.commits.json")
    with lock_for(path):
        try:
            commits = read_json_strict(path).get("commits") or []
        except (OSError, ValueError, AttributeError):
            commits = []
        c = {"id": f"c{len(commits) + 1}", "when": datetime.now(timezone.utc).isoformat(timespec="seconds"), "what": what, "by": by}
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, {"commits": [*commits, c]})
    return c


def add_build_nodes(g, plane, people) -> None:
    """Called by build.rebuild after the module records."""
    from sh_platform.graph.build import _person, _prov  # build.py imports this module, so import it late
    _register()
    meet = models.meet
    bp, pv = _rd(plane, "build", "blueprint.json"), _rd(plane, "build", "prove.json")
    lineage = _l(bp, "lineage")
    mart_of = {}  # "gold.k02" -> K02: a pipeline lists the mart table, the lineage names the mart with a suffix, so key by the first two parts
    for m in lineage:
        if m.get("mart") and m.get("measure"):
            mart_of.setdefault(".".join(str(m["mart"]).lower().split(".")[:2]), m["measure"])

    def mguard(code: Any):
        return g.guard(f"measure:{code}")

    def sign(rid: str, who: Any, typ: str, p: list[dict]) -> None:
        pid = _person(g, people, who, p, "build")
        if pid:
            g.edge(rid, pid, typ, p)

    if bp.get("version") is not None:
        p = _prov(by="the blueprint", src=_BP, at=(_l(bp, "signed_by") or [{}])[0].get("at"))
        shut = [(sorted(a["may_see"]), {}) for a in _l(bp, "access") if isinstance(a.get("may_see"), list)]
        bid = g.node(f"blueprint:v{bp['version']}", "Blueprint", f"Blueprint v{bp['version']}", p, "build", meet(*shut))
        for s in _l(bp, "signed_by"):
            sign(bid, s.get("name"), "designed_by", _prov(by=s.get("name") or "the signer", src=_BP, at=s.get("at")))
        for ln in lineage:
            g.edge(f"measure:{ln.get('measure')}", bid, "designed_in", p)

    shown = {_slug(n["label"]): n["label"] for n in g.nodes.values() if n["type"] == "Source"}  # display names from the catalogue
    folder = plane.path("build", "pipelines")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if f.name.endswith(".commits.json"):
            continue
        d = _rd(plane, "build", "pipelines", f.name)
        if not d.get("source"):
            continue
        src, ms = f"{_PL}{f.name}", [mart_of[str(m).lower()] for m in d.get("marts") or [] if mart_of.get(str(m).lower())]
        plain = str(d["source"]).replace("_", " ")
        pid = g.node(f"pipeline:{_slug(d['source'])}", "Pipeline", shown.get(_slug(d["source"])) or plain[:1].upper() + plain[1:], _prov(by="the pipeline contract", src=src), "build",
                     meet(*[mguard(m) for m in ms]))
        for m in ms:
            g.edge(f"measure:{m}", pid, "built_by", _prov(by="the pipeline contract", src=src))
        sign(pid, d.get("owner"), "owned_by", _prov(by=d.get("owner") or "the pipeline contract", src=src))
        g.nodes[pid]["commits"] = _l(_rd(plane, "build", "pipelines", f"{f.name[:-5]}.commits.json"), "commits")

    for ln in lineage:  # a measure whose mart the pipeline does not list is still built by the pipeline of its lineage source
        g.edge(f"measure:{ln.get('measure')}", f"pipeline:{_slug(ln.get('source'))}", "built_by", _prov(by="the blueprint lineage", src=_BP))

    rel = pv.get("release") if isinstance(pv.get("release"), dict) else {}
    if rel.get("state") == "signed":
        month = str(rel.get("at") or "")[:7]
        ms = _l(pv, "measures")
        out_codes = {str(c).lower() for c in rel["released"]} if isinstance(rel.get("released"), list) else None  # the old record has no list: use release_ready
        p = _prov(by=rel.get("by") or "the sponsor", src=_PV, at=rel.get("at"))
        rid = g.node(f"release:{_slug(pv.get('band'))}-{month}", "Release", f"Release {pv.get('band')} {month}".strip(), p, "build")  # open to everyone who may see the map: a release is a name and a date, and each measure's own edge keeps its guard
        sign(rid, rel.get("by"), "released_by", p)
        for m in ms:
            u = m.get("uat") if isinstance(m.get("uat"), dict) else {}
            if u.get("state") == "signed":
                sign(rid, u.get("by"), "tested_by", _prov(by=u.get("by") or "the tester", src=_PV, at=u.get("at")))
            if str(m.get("code")).lower() in out_codes if out_codes is not None else m.get("release_ready"):
                g.edge(f"measure:{m.get('code')}", rid, "released_in", p)
