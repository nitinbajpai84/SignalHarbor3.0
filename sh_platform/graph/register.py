"""`GET /api/company/register` (SHAPES 11): one row per measure and definition that appears in a signed record, with the stages that signed it.
Names, owners and links only; no figures. A measure the viewer may not see is one "A restricted measure" row with no owner or pipeline."""
import hashlib
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import governed as GS
from sh_platform.consume.feeds import _cell
from sh_platform.graph.build import _HEX, _newest_baseline, _read
from sh_platform.graph.hooks import rebuild_if_dirty
from sh_platform.graph.read import EMPTY, _sees
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.view import Viewer, norm

log = logging.getLogger(__name__)
router = APIRouter()
STAGES = ("charter", "baseline", "blueprint", "uat", "release")


def _sig(by: Any, at: Any) -> dict:
    return {"by": by or None, "at": at or None}


def _first(rec: dict) -> dict | None:
    """The sign-off of a signed outcome record: its first signer and the signing time."""
    sigs = [s for s in rec.get("signatures") or [] if isinstance(s, dict) and s.get("name")]
    return _sig(sigs[0]["name"], rec.get("signed_at")) if rec.get("signed_at") and sigs else None


def _stages(plane: CompanyPlane, doc: dict) -> dict[str, dict[str, dict | None]]:
    """code (lowercase) -> stage -> sign-off, from the signed records, read by path."""
    out: dict[str, dict[str, dict | None]] = {}

    def put(code: Any, stage: str, sig: dict | None) -> None:
        if code and sig:
            out.setdefault(str(code).lower(), {})[stage] = sig
    base = _newest_baseline(plane)
    base_sig = _first(base) if base else None
    for r in (base.get("catalogue") or {}).get("kpis") or []:
        c = r.get("KPI ID") if isinstance(r, dict) else None
        put(c.get("value") if isinstance(c, dict) else c, "baseline", base_sig)
    cid = str(base.get("charter_outcome_id") or "")
    charter = _read(plane, "intents", "m1_intent", "outcomes", f"{cid}.json") if _HEX.fullmatch(cid) else {}
    ch_sig = _first(charter) if charter.get("kind") == "charter" else None
    problems = {f"problem:{p['id']}" for p in charter.get("problems") or [] if isinstance(p, dict) and p.get("id")}
    for e in doc["edges"]:
        if e["type"] == "measured_by" and e["from"] in problems:
            put(e["to"].removeprefix("measure:"), "charter", ch_sig)
    bp = _read(plane, "build", "blueprint.json")
    if bp.get("state") == "signed":
        s = (bp.get("signed_by") or [{}])[0]
        sig = _sig(s.get("name"), s.get("at")) if isinstance(s, dict) else None
        for x in (bp.get("lineage") or []) + (bp.get("rules") or []):
            put(x.get("measure") if isinstance(x, dict) else None, "blueprint", sig)
    pv = _read(plane, "build", "prove.json")
    rel = pv.get("release") if isinstance(pv.get("release"), dict) else {}
    for m in pv.get("measures") or []:
        if not isinstance(m, dict):
            continue
        u = m.get("uat") if isinstance(m.get("uat"), dict) else {}
        put(m.get("code"), "uat", _sig(u.get("by"), u.get("at")) if u.get("state") == "signed" else None)
        put(m.get("code"), "release", _sig(rel.get("by"), rel.get("at")) if rel.get("state") == "signed" and m.get("release_ready") else None)
    return out


def _pipelines(plane: CompanyPlane) -> dict[str, str]:
    """mart (lowercase) -> pipeline source name, from build/pipelines/*.json."""
    folder, out = plane.path("build", "pipelines"), {}
    for f in sorted(folder.glob("*.json") if folder.is_dir() else []):
        p = _read(plane, "build", "pipelines", f.name)
        for m in p.get("marts") or []:
            out[str(m).lower()] = str(p.get("source") or f.stem)
    return out


def _lineage(plane: CompanyPlane) -> dict[str, str]:
    """measure code (lowercase) -> every source that feeds it, in the blueprint's words, joined with commas."""
    out: dict[str, list[str]] = {}
    for x in _read(plane, "build", "blueprint.json").get("lineage") or []:
        if isinstance(x, dict) and x.get("measure") and x.get("source") and str(x["source"]) not in out.setdefault(str(x["measure"]).lower(), []):
            out[str(x["measure"]).lower()].append(str(x["source"]))
    return {k: ", ".join(v) for k, v in out.items()}


def _business_owners(plane: CompanyPlane) -> dict[str, str]:
    """measure code (lowercase) -> business owner from the signed baseline's governed state: the lookup Feeds uses, so the two screens agree."""
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    gov = GS._read(plane, base["id"]) if base else {}
    out = {}
    for code, g in gov.items():
        o = _cell(g, "owners") if isinstance(g, dict) else None
        if isinstance(o, dict) and o.get("business"):
            out[str(code).lower()] = str(o["business"])
    return out


def _versions(plane: CompanyPlane, node_id: str) -> int:
    v = read_json_strict(plane.path("graph", "versions.json"), dict) if plane.path("graph", "versions.json").exists() else {}
    h = v.get(node_id) if isinstance(v, dict) else None
    return len(h) if isinstance(h, list) and h else 1


def _name(n: dict, label: dict, code: str) -> str:
    """A definition is named after its measure when the glossary term was stored as a record rather than a word (build.py str()s a cell)."""
    return label.get(f"measure:{code}") or n["label"] if n["type"] == "Term" and str(n["label"]).startswith("{") else n["label"]


def _signed_records(plane: CompanyPlane) -> list[dict]:
    """PF2: every signed record of the 1.0 product, names, signer and date only: each signed intent of work and its measures,
    each approved rule version and each approved build plan. The graph rows above only know the 2.0 charter and baseline,
    so a company that signed through Intent (intents/<iid>/sow.json) used to read "Nothing has been signed yet"."""
    out: list[dict] = []
    root = plane.path("intents")
    for f in sorted(root.glob("*/sow.json") if root.is_dir() else []):
        sow = _read(plane, "intents", f.parent.name, "sow.json")
        if sow.get("state") != "signed":
            continue
        sig = sow.get("signature") if isinstance(sow.get("signature"), dict) else {}
        by, at, iid = sig.get("name") or None, sig.get("at") or None, f.parent.name
        title = str(sow.get("title") or (sow.get("goal") or {}).get("line") or "Intent of work")
        out.append({"kind": "intent", "name": title, "by": by, "at": at, "of": None, "href": f"/centre/intent/{iid}"})
        out += [{"kind": "measure", "name": str(k.get("name") or k.get("code")), "by": by, "at": at, "of": title, "href": f"/centre/intent/{iid}"}
                for k in sow.get("kpis") or [] if isinstance(k, dict) and (k.get("name") or k.get("code"))]
    out += _signed_rules(plane)
    build = plane.path("build")
    for d in sorted(p for p in build.iterdir() if p.is_dir()) if build.is_dir() else []:
        plans = sorted(d.glob("plan-v*.json"), key=lambda p: int(p.stem.removeprefix("plan-v")) if p.stem.removeprefix("plan-v").isdigit() else 0)
        for f in reversed(plans):  # the newest approved version of each project's plan
            plan = _read(plane, "build", d.name, f.name)
            if plan.get("approved_by") and plan.get("state") in ("approved", "built", "live"):
                title = _read(plane, "projects", f"{d.name}.json").get("title") or "a project"
                out.append({"kind": "plan", "name": f"Build plan for {title}, version {plan.get('version') or 1}",
                            "by": plan.get("approved_by"), "at": plan.get("approved_at"), "of": None, "href": f"/centre/build/p/{d.name}"})
                break
    return out


def _signed_rules(plane: CompanyPlane) -> list[dict]:
    """The approved versions of the company's rules, from the warehouse (only when it exists; reading never creates it)."""
    from sh_platform.v1 import e3_rules, wh
    if not wh.path(plane).exists():
        return []
    try:
        with wh.connect(plane, read_only=True) as con:
            rows = con.execute(e3_rules._SELECT + " and v.approval_status = 'approved' order by r.rule_code, v.version_number",
                               [e3_rules._org(plane)]).fetchall()
    except Exception:  # noqa: BLE001  a warehouse busy or without the rules tables: the register still shows the rest
        log.warning("register: the rules could not be read", exc_info=True)
        return []
    return [{"kind": "rule", "name": f"{v['rule_code']}, version {v['version_number']}", "by": v["approved_by"], "at": v["approved_at"], "of": None,
             "href": "/centre/settings/rules"} for v in map(e3_rules._version, rows)]


DATA_TEAM = frozenset({"analyst", "head_of_data", "company_admin"})


def _runs(plane: CompanyPlane, limit: int = 40) -> list[dict]:
    """ROLE1: the run log's newest runs as activity rows (who started it, when, how it ended). No figures."""
    from sh_platform.v1 import run_log
    try:
        runs = run_log.list_runs(plane, limit=limit)
    except Exception:  # noqa: BLE001  an unreadable log leaves the rest of the trail
        log.warning("register: the run log could not be read", exc_info=True)
        return []
    return [{"kind": "run", "name": f"{str(r.get('kind') or 'run').replace('_', ' ').capitalize()} run, {r.get('status') or 'unknown'}", "by": r.get("who") or None,
             "at": r.get("started"), "of": None, "href": ""} for r in runs]


def _taught(plane: CompanyPlane, limit: int = 60) -> list[dict]:
    """TEACH1: each add, switch-off, switch-on and replace of an agent's knowledge (who, when, which agent and title; nothing from inside a document)."""
    from sh_platform.v1 import teach
    return [{"kind": "knowledge", "name": f"Taught {teach.AGENTS.get(r.get('agent'), 'an agent')}: {r.get('title')} ({r.get('action')})", "by": r.get("by") or None,
             "at": r.get("at"), "of": None, "href": ""} for r in teach.trail(plane, limit)]


def _activity(plane: CompanyPlane, viewer: Viewer) -> list[dict]:
    """Every recorded action (signatures, approvals, runs) for the data team; for anyone else only their own."""
    recs = _signed_records(plane) + _runs(plane) + _taught(plane)
    if DATA_TEAM & set(viewer.roles):
        return recs
    if viewer.shared_name or not viewer.name:  # RSEC: rows carry names only, so a name twin cannot tell whose they are; show none
        return []
    return [r for r in recs if r.get("by") and norm(r["by"]) == norm(viewer.name)]


def register(plane: CompanyPlane, viewer: Viewer) -> dict:
    doc = read_json_strict(plane.path("graph", "company.json"), dict) or EMPTY
    hidden = sorted((n["id"] for n in doc["nodes"] if not _sees(n, viewer)), key=lambda x: hashlib.sha256(x.encode()).hexdigest())
    alias = {old: f"restricted-{i}" for i, old in enumerate(hidden, 1)}  # the same numbering as read.graph_for, so the link resolves
    stages, marts, feeds, boss = _stages(plane, doc), _pipelines(plane), _lineage(plane), _business_owners(plane)
    label = {n["id"]: n["label"] for n in doc["nodes"]}
    owner = {e["from"]: label.get(e["to"]) for e in doc["edges"] if e["type"] == "owned_by"}
    ntype = {n["id"]: n["type"] for n in doc["nodes"]}
    origin = {}  # measure id -> the charter problem, pain point or future signal it came from (first by id), as a name and a map link
    for e in sorted(doc["edges"], key=lambda e: e["from"]):
        if e["type"] == "measured_by" and ntype.get(e["from"]) in ("Problem", "Pain", "Signal") and e["from"] not in alias:
            origin.setdefault(e["to"], {"name": label[e["from"]], "kind": ntype[e["from"]].lower(), "href": f"/centre/intent/map/{e['from']}"})
    rows = []
    for n in doc["nodes"]:
        kind = {"Measure": "measure", "Term": "definition"}.get(n["type"])
        code = n["id"].split(":", 1)[-1]
        sg = stages.get(code.lower(), {})
        if not kind or not sg:
            continue
        signed = {s: sg.get(s) for s in STAGES}
        if n["id"] in alias:
            rows.append({"code": alias[n["id"]], "name": f"A restricted {kind}", "kind": kind, "owner": None, "pipeline": None,
                         "source": None, "signed": {s: _sig(None, v["at"]) if v else None for s, v in signed.items()}, "version": 1, "href": f"/centre/intent/map/{alias[n['id']]}"})
            continue
        mid = f"measure:{code}"
        rows.append({"code": code, "name": _name(n, label, code), "kind": kind, "owner": boss.get(code.lower()) or owner.get(n["id"]) or owner.get(mid),
                     "pipeline": feeds.get(code.lower()) or marts.get(f"gold.{code.lower()}"),
                     "source": origin.get(mid) or origin.get(f"measure:{code}"), "signed": signed, "version": _versions(plane, n["id"]), "href": f"/centre/intent/map/{n['id']}"})
    return {"rows": sorted(rows, key=lambda r: (r["name"].lower(), r["kind"])), "records": _activity(plane, viewer)}


@router.get("/api/company/register")
def get_api_company_register(request: Request) -> dict:
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, "Your company space could not be opened. Please ask your administrator.") from None
    rebuild_if_dirty(plane)
    return register(plane, viewer)
