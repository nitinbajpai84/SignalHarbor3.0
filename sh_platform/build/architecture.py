"""59: the company architecture record (three views: data, infrastructure, enterprise solution) and its Archify diagrams.

The record is a projection the Architect rebuilds from signed records only (C24, spec 59 "Each agent's moments"): the blueprint (lineage, access,
infra), the pipeline contracts, the profile's systems list and the processes each Initiative handed to Build. It never invents a component.
Files in the company plane (sh_platform/jsonfile.py):
  build/architecture/record.json        {version, regenerated, components: [COMPONENT], history: [...]}   (the current one, proposed included)
  build/architecture/record.v<n>.json   the record as regenerated at version n (the version picker reads it)
  build/architecture/diagrams/<view>.v<n>.json  Archify spec, the shape of docs/architecture/sh-m4-build.json
Regenerated on every signed blueprint and signed release (chain.py calls `regenerate`), and only then. A component that serves a restricted
measure is "Restricted" with no name, owner or interfaces for anyone outside the mart's access list (blueprint `access`)."""
import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store as pstore, view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
VIEWS = ("data", "infrastructure", "enterprise")
STATES = ("proposed", "approved", "built", "tested", "live", "retired")
# component kind -> Archify type and diagram column (C30: the kinds drafted in 59)
KINDS = {"source": ("external", 0), "system": ("external", 0), "bronze": ("database", 1), "silver": ("database", 2), "gold": ("database", 3),
         "runner": ("backend", 0), "restricted file": ("security", 2), "read-only copy": ("database", 2), "webhook": ("backend", 3),
         "process": ("frontend", 1), "consumer": ("frontend", 1)}
MAX_TEXT = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rd(path, empty=None) -> Any:
    try:
        d = read_json_strict(path)
    except (OSError, ValueError):
        log.warning("an architecture input could not be read")
        return empty
    return empty if d is None else d


def _slug(t: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(t or "").lower()).strip("-")


def _cell(v: Any) -> Any:
    return v.get("value") if isinstance(v, dict) else v


def _file(plane, *parts):
    return plane.path("build", "architecture", *parts)


# ---- projection: what the signed records say the company runs ---------------------------------------------------------------------------

def _mart(m: Any) -> str:
    """gold.k02.reported_value_evidence_coverage -> gold.k02"""
    return ".".join(str(m or "").lower().split(".")[:2])


def contracts(plane) -> list[tuple[str, dict]]:
    folder = plane.path("build", "pipelines")
    out = []
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        d = _rd(f, {})
        if not f.name.endswith(".commits.json") and isinstance(d, dict) and d.get("source"):
            out.append((f"build/pipelines/{f.name}", d))
    return out


def project(plane) -> dict[str, dict]:
    """{component id: component without the people-made fields}. Every component names the record it comes from in `from`."""
    bp = _rd(plane.path("build", "blueprint.json"), {})
    bp = bp if isinstance(bp, dict) else {}
    ver, out = bp.get("version"), {}

    def add(cid, vw, kind, label, src, **kw):
        out[cid] = {"id": cid, "view": vw, "kind": kind, "label": label, "interfaces": [], "from": src, "restricted": False, "may_see": None,
                    "owner_hint": None, "about": None,
                    "refs": {"blueprint_version": ver, "pipeline": None, "mart": None, "graph_node": None}, **kw}
        return out[cid]

    access = {str(a.get("mart")).lower(): a.get("may_see") for a in bp.get("access") or [] if isinstance(a, dict)}
    for ln in bp.get("lineage") or []:
        if not isinstance(ln, dict) or not ln.get("mart"):
            continue
        m = _mart(ln["mart"])
        if f"gold:{m.split('.', 1)[-1]}" in out:
            continue
        may = access.get(m)
        c = add(f"gold:{m.split('.', 1)[-1]}", "data", "gold", m, "build/blueprint.json lineage", restricted=isinstance(may, list),
                may_see=may if isinstance(may, list) else None, about=ln.get("transform"))
        c["refs"].update(mart=m, graph_node=f"measure:{ln.get('measure')}")
    for path, d in contracts(plane):
        s = _slug(d["source"]).replace("-", "_")
        title = d.get("title") or str(d["source"]).replace("_", " ").capitalize()
        marts = [_mart(x) for x in d.get("marts") or []]
        guards = [out[f"gold:{x.split('.', 1)[-1]}"]["may_see"] for x in marts if f"gold:{x.split('.', 1)[-1]}" in out]
        shut = [g for g in guards if g is not None]
        may = sorted(set.intersection(*map(set, shut))) if shut else None  # a pipeline feeding a restricted mart is limited as the mart is
        common = {"restricted": may is not None, "may_see": may, "owner_hint": d.get("owner")}
        src = add(f"source:{s}", "data", "source", title, path, about=f"{d.get('expected') or 'Arrives'} file, landing at {d.get('lands_at') or 'the landing folder'}", **common)
        src["refs"].update(pipeline=path, graph_node=f"pipeline:{_slug(d['source'])}")
        src["interfaces"].append({"to": f"bronze:{s}", "kind": "feeds", "contract": path})
        b = add(f"bronze:{s}", "data", "bronze", f"bronze.{s}", path, about=f"{title} rows as they landed", **common)
        b["refs"]["pipeline"] = path
        b["interfaces"].append({"to": f"silver:{s}", "kind": "feeds", "contract": path})
        sv = add(f"silver:{s}", "data", "silver", f"silver.{s}", path, about=f"{title} rows typed and without duplicates", **common)
        sv["refs"]["pipeline"] = path
        sv["interfaces"] += [{"to": f"gold:{x.split('.', 1)[-1]}", "kind": "writes", "contract": path} for x in marts]
    infra = bp.get("infra") if isinstance(bp.get("infra"), dict) else {}
    if infra:
        wh = infra.get("warehouse")
        add("infra:warehouse", "infrastructure", "system", "Company warehouse file" if wh == "plane" else f"Warehouse: {wh}", "build/blueprint.json infra",
            about="One warehouse file inside this company's space" if wh == "plane" else None)
        add("infra:readonly", "infrastructure", "read-only copy", "Read-only copy for query tools", "build/blueprint.json infra",
            about="Refreshed after each load; query tools read this, never the live file")
        out["infra:warehouse"]["interfaces"].append({"to": "infra:readonly", "kind": "feeds", "contract": None})
        if any(isinstance(v, list) for v in access.values()):
            add("infra:restricted", "infrastructure", "restricted file", "Restricted marts file", "build/blueprint.json access",
                about="Restricted marts, readable only by the people on their list")
        r = infra.get("runner")
        run = add("infra:runner", "infrastructure", "runner", "Built-in runner" if r == "builtin" else f"Runner: {r}", "build/blueprint.json infra")
        run["interfaces"] += [{"to": t, "kind": "writes", "contract": None} for t in ("infra:warehouse", "infra:restricted") if t in out]
    for key, s in (pstore.raw(plane).get("systems") or {}).items():
        if isinstance(s, dict) and _cell(s.get("name")):
            add(f"system:{_slug(key)}", "enterprise", "system", str(_cell(s.get("name"))), "profile systems list",
                owner_hint=_cell(s.get("owner")), about=_cell(s.get("lands")))
    for h in _handoffs(plane):
        for p in h.get("processes") or []:
            if isinstance(p, dict) and p.get("name"):
                c = add(f"process:{_slug(p['name'])}", "enterprise", "process", str(p["name"]), f"intents/{h['_id']}/intent.json build_handoff",
                        owner_hint=p.get("owner"))
                if "infra:warehouse" in out:
                    c["interfaces"].append({"to": "infra:warehouse", "kind": "reads", "contract": None})
    return out


def _handoffs(plane) -> list[dict]:
    from sh_platform.intents import store as istore
    out = []
    for r in istore.read_index(plane):
        if r.get("type") != "initiative":
            continue
        try:
            rec = istore.read_intent(plane, r["id"]) or {}
        except istore.Unreadable:
            continue
        if isinstance(rec.get("build_handoff"), dict):
            out.append({**rec["build_handoff"], "_id": rec["id"]})
    return out


def handoffs(plane) -> list[dict]:
    """Every Initiative's build_handoff, with `_id` (the intent id): the public name of `_handoffs`."""
    return _handoffs(plane)


# ---- the record -----------------------------------------------------------------------------------------------------------------------

def read(plane, v: int | None = None) -> dict:
    blank = {"version": 0, "regenerated": None, "components": [], "history": []}
    d = _rd(_file(plane, "record.json" if v is None else f"record.v{int(v)}.json"), None)
    return d if isinstance(d, dict) and isinstance(d.get("components"), list) else blank


def _same(old: dict, new: dict) -> bool:
    return all(old.get(k) == new.get(k) for k in ("label", "interfaces", "refs", "restricted", "may_see"))


def _fresh(p: dict, state: str, made_by: str | None) -> dict:
    by = "Lens" if p["view"] == "enterprise" else "Architect"
    desc = {"text": str(p["about"])[:MAX_TEXT], "mark": "guessed", "by": by, "from": p["from"], "at": _now()} if p.get("about") else None
    c = {k: v for k, v in p.items() if k not in ("owner_hint", "about")}
    return {**c, "description": desc, "owner": p.get("owner_hint") or None, "version": 1, "state": state, "made_by": made_by,
            "changed_by": [made_by] if made_by else []}


def propose(plane, change_id: str, ids: list[str]) -> None:
    """The Architect's draft: the change's new components go into the record as `proposed` (no new version: that is the regeneration)."""
    proj = project(plane)
    with lock_for(_file(plane, "record.json")):
        rec = read(plane)
        have = {c["id"] for c in rec["components"]}
        rec["components"] += [_fresh(proj[i], "proposed", change_id) for i in ids if i in proj and i not in have]
        for c in rec["components"]:
            if c["id"] in ids and change_id not in c.get("changed_by", []):
                c.setdefault("changed_by", []).append(change_id)
        write_json_atomic(_file(plane, "record.json"), rec)


def drop(plane, change_id: str) -> None:
    """A stopped change: its never-built components leave the draft record; nothing signed is undone."""
    with lock_for(_file(plane, "record.json")):
        rec = read(plane)
        rec["components"] = [c for c in rec["components"] if not (c.get("state") == "proposed" and c.get("made_by") == change_id)]
        write_json_atomic(_file(plane, "record.json"), rec)


def set_state(plane, change_id: str, state: str) -> None:
    with lock_for(_file(plane, "record.json")):
        rec = read(plane)
        for c in rec["components"]:
            if change_id in (c.get("changed_by") or []) and c.get("state") != "retired":
                c["state"] = state
        write_json_atomic(_file(plane, "record.json"), rec)


def regenerate(plane, moment: str, ref: str, by: str, change_ids: list[str]) -> dict:
    """A new version from the signed records: components refreshed (owners and descriptions people stated are kept), the version and
    its three diagrams written, history row added. `moment` is blueprint_signed or release_signed."""
    proj = project(plane)
    with lock_for(_file(plane, "record.json")):
        rec = read(plane)
        old = {c["id"]: c for c in rec["components"]}
        added, changed, comps = [], [], []
        for cid, p in proj.items():
            o = old.pop(cid, None)
            if o is None:
                comps.append(_fresh(p, "live", None))
                added.append(cid)
                continue
            new = {**o, **{k: p[k] for k in ("view", "kind", "label", "interfaces", "refs", "restricted", "may_see", "from")}}
            if o.get("state") == "proposed" and o.get("made_by") not in change_ids:
                pass  # still a draft of an open change
            elif o.get("state") == "proposed":
                added.append(cid)
            elif not _same(o, p):
                new["version"] = int(o.get("version") or 1) + 1
                changed.append(cid)
            d = o.get("description")
            if p.get("about") and (not isinstance(d, dict) or d.get("mark") == "guessed"):  # a draft never overwrites a person's words
                new["description"] = {"text": str(p["about"])[:MAX_TEXT], "mark": "guessed", "by": "Lens" if p["view"] == "enterprise" else "Architect",
                                      "from": p["from"], "at": (d or {}).get("at") or _now()}
            comps.append(new)
        comps += list(old.values())  # never retired outside a change note (59 "Not in this feature")
        n = int(rec.get("version") or 0) + 1
        regen = {"moment": moment, "ref": ref, "by": by, "at": _now()}
        rec = {"version": n, "regenerated": regen, "components": comps,
               "history": [*rec.get("history", []), {"version": n, **regen, "added": added, "changed": changed, "retired": [], "changes": change_ids}]}
        write_json_atomic(_file(plane, "record.json"), rec)
        write_json_atomic(_file(plane, f"record.v{n}.json"), rec)
        for vw in VIEWS:
            write_json_atomic(_file(plane, "diagrams", f"{vw}.v{n}.json"), spec(rec, vw, set(added) | set(changed)))
    return rec


def ensure(plane) -> bool:
    """A signed blueprint with no record yet (the seeded company: its blueprint and release predate the record) regenerates version 1 once,
    from the signed records only. Idempotent: does nothing once any version exists. True when it wrote one."""
    if read(plane).get("version"):
        return False
    bp = _rd(plane.path("build", "blueprint.json"), {})
    if not (isinstance(bp, dict) and bp.get("state") == "signed" and bp.get("version") is not None):
        return False
    with lock_for(_file(plane, "backfill")):
        if read(plane).get("version"):
            return False
        who = next((s.get("name") for s in bp.get("signed_by") or [] if isinstance(s, dict) and s.get("name")), None) or "the head of data"
        regenerate(plane, "blueprint_signed", f"v{bp['version']}", who, [])
    from sh_platform.graph.hooks import mark_dirty
    mark_dirty(plane)  # the map draws the record's components
    return True


def spec(rec: dict, vw: str, focus: set[str]) -> dict:
    """The Archify spec of one view: components on a grid by kind, connections from the interfaces inside the view."""
    comps = [c for c in rec["components"] if c.get("view") == vw and c.get("state") != "retired"]
    ids, rows, out = {c["id"] for c in comps}, {}, []
    for c in comps:
        typ, col = KINDS.get(c.get("kind"), ("backend", 0))
        row = rows[col] = rows.get(col, -1) + 1
        out.append({"id": c["id"], "type": typ, "label": c["label"], "sublabel": c.get("kind"), "pos": [40 + col * 220, 40 + row * 90], "size": [160, 64]})
    conns = [{"id": f"{c['id']}>{i['to']}", "from": c["id"], "to": i["to"], "label": i.get("kind")}
             for c in comps for i in c.get("interfaces") or [] if i.get("to") in ids]
    return {"schema_version": 1, "diagram_type": "architecture",
            "meta": {"title": f"{vw.capitalize()} view, version {rec.get('version')}",
                     "views": [{"id": "this-change", "label": "This change", "focus": sorted(focus & ids)}]},
            "components": out, "connections": conns, "cards": []}


# ---- what a viewer may see ------------------------------------------------------------------------------------------------------------

def may_see(c: dict, viewer: view.Viewer) -> bool:
    if not c.get("restricted") or "company_admin" in viewer.roles:
        return True
    return view.allows(frozenset(view.norm(n) for n in c.get("may_see") or []), viewer)


def masked(comps: list[dict], viewer: view.Viewer) -> tuple[list[dict], dict[str, str]]:
    """Components as this viewer may see them, and {real id: shown id}. A restricted one keeps only its view, kind and state."""
    out, ids = [], {}
    for n, c in enumerate(comps):
        if may_see(c, viewer):
            ids[c["id"]] = c["id"]
            out.append({k: v for k, v in c.items() if k not in ("may_see",)})
        else:
            ids[c["id"]] = f"restricted-{n + 1}"
            out.append({"id": ids[c["id"]], "view": c.get("view"), "kind": c.get("kind"), "label": "Restricted", "state": c.get("state"),
                        "version": c.get("version"), "restricted": True, "owner": None, "description": None, "interfaces": [], "changed_by": []})
    for c in out:
        c["interfaces"] = [{**i, "to": ids.get(i["to"], i["to"])} for i in c.get("interfaces") or [] if i.get("to") in ids]
    return out, ids


def _ui_spec(sp: dict, ids: dict[str, str], shown: dict[str, dict]) -> dict:
    comps = [{**c, "id": ids.get(c["id"], c["id"]), "label": shown.get(ids.get(c["id"], c["id"]), {}).get("label", c["label"]),
              "pos": {"x": c["pos"][0], "y": c["pos"][1]}, "size": {"w": c["size"][0], "h": c["size"][1]}} for c in sp.get("components") or []]
    conns = [{**k, "from": ids.get(k["from"], k["from"]), "to": ids.get(k["to"], k["to"])} for k in sp.get("connections") or []]
    return {**sp, "components": comps, "connections": conns}


def svg(sp: dict) -> str:
    """A plain SVG of an Archify spec (C24: no renderer bundled)."""
    cs = sp.get("components") or []
    by = {c["id"]: c for c in cs}
    w = max([c["pos"]["x"] + c["size"]["w"] for c in cs] + [400]) + 40
    h = max([c["pos"]["y"] + c["size"]["h"] for c in cs] + [200]) + 40
    mid = lambda c: (c["pos"]["x"] + c["size"]["w"] / 2, c["pos"]["y"] + c["size"]["h"] / 2)  # noqa: E731
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif" font-size="12">']
    for k in sp.get("connections") or []:
        if k["from"] in by and k["to"] in by:
            (x1, y1), (x2, y2) = mid(by[k["from"]]), mid(by[k["to"]])
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#888"/>')
    for c in cs:
        x, y, cw, ch = c["pos"]["x"], c["pos"]["y"], c["size"]["w"], c["size"]["h"]
        parts.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="6" fill="#fff" stroke="#333"/>'
                     f'<text x="{x + 8}" y="{y + 24}">{html.escape(str(c["label"]))[:40]}</text>'
                     f'<text x="{x + 8}" y="{y + 44}" fill="#666">{html.escape(str(c.get("sublabel") or ""))}</text>')
    return "".join(parts) + "</svg>"


# ---- routes ---------------------------------------------------------------------------------------------------------------------------

def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _open(request: Request):
    try:
        return _plane(request), _viewer(request)
    except PermissionError:
        return None, None


def _ensure_quiet(plane) -> None:
    try:
        ensure(plane)
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the architecture record was not built from the signed blueprint", exc_info=True)


def _editor(plane, viewer) -> bool:
    """The architect role or the head of department of any open change (or of the latest charter when no change is open)."""
    from sh_platform.build import chain
    return chain.holds(plane, viewer, ("architect", "head_of_department"))


@router.get("/api/company/build/architecture")
def get_architecture(request: Request, v: str | None = None, focus: str | None = None):
    view_ = request.query_params.get("view") or "data"
    plane, viewer = _open(request)
    if plane is None:
        return _err(403, "forbidden", "This company space cannot be opened.")
    if view_ not in VIEWS:
        return _err(422, "invalid", "The view is data, infrastructure or enterprise.")
    _ensure_quiet(plane)
    cur = read(plane)
    rec = cur
    if v not in (None, "") and v != str(cur.get("version")):
        if not str(v).isdigit() or not _file(plane, f"record.v{int(v)}.json").is_file():
            return _err(404, "no_version", "There is no such version of the architecture.")
        rec = read(plane, int(v))
    n = int(rec.get("version") or 0)
    shown, ids = masked(rec["components"], viewer)
    by_id = {c["id"]: c for c in shown}
    notes = _change_titles(plane)
    hist = next((h for h in rec.get("history", []) if h.get("version") == n), None)
    focus_ids = ([ids[i] for i in (hist or {}).get("added", []) + (hist or {}).get("changed", []) if i in ids] if focus == "change"
                 else [focus] if focus in by_id else [])
    for c in shown:
        c["changed_by"] = [{"id": x, "title": notes.get(x, x)} for x in c.get("changed_by") or []]
        c["owner_id"] = _person_id(plane, c.get("owner"))
    sp = _rd(_file(plane, "diagrams", f"{view_}.v{n}.json"), None) if n else None
    editor = _editor(plane, viewer)
    out = {
        "version": n, "regenerated": rec.get("regenerated"),
        "counts": {vw: sum(1 for c in shown if c.get("view") == vw and c.get("state") != "retired") for vw in VIEWS},
        "versions": [{"v": h["version"], "moment": h["moment"], "at": h["at"]} for h in cur.get("history", [])],
        "components": [c for c in shown if c.get("view") == view_],
        "diagram": _ui_spec(sp, ids, by_id) if isinstance(sp, dict) else None,
        "focus_ids": focus_ids,
        "this_version": None if not hist or n == 1 else {k: len(hist.get(k) or []) for k in ("added", "changed", "retired")},
        "changes": [{"id": x, "title": notes.get(x, x), "added": sum(1 for c in rec["components"] if c.get("made_by") == x and c["id"] in hist["added"]),
                     "changed": sum(1 for c in rec["components"] if x in (c.get("changed_by") or []) and c["id"] in hist["changed"])}
                    for x in (hist or {}).get("changes", [])] if hist else [],
        "can_edit": editor,
        "can_download": bool(n) and (editor or "company_admin" in viewer.roles),
    }
    out["html_url"] = f"/api/company/build/architecture/diagram?view={view_}&v={n}" if out["can_download"] and sp else None
    if editor or "company_admin" in viewer.roles:
        out["owners_missing"] = [{"id": c["id"], "label": c["label"]} for c in shown if not c.get("owner") and not c.get("restricted") and c.get("state") != "retired"]
    if editor:
        out["people"] = [{"id": k, "name": str(_cell(p.get("name")))} for k, p in (pstore.raw(plane).get("people") or {}).items()
                         if isinstance(p, dict) and _cell(p.get("name"))]
    return out


@router.get("/api/company/build/architecture/diagram")
def get_architecture_diagram(request: Request):
    """The download (C24): one HTML page holding the SVG and the spec JSON, masked for the viewer."""
    plane, viewer = _open(request)
    if plane is None:
        return _err(403, "forbidden", "This company space cannot be opened.")
    vw, v = request.query_params.get("view") or "data", request.query_params.get("v") or ""
    if vw not in VIEWS or not v.isdigit():
        return _err(422, "invalid", "Name the view and the version.")
    if not (_editor(plane, viewer) or "company_admin" in viewer.roles):
        return _err(403, "forbidden", "Only the architect, the head of department or a company admin may download the diagram.")
    sp, rec = _rd(_file(plane, "diagrams", f"{vw}.v{int(v)}.json"), None), read(plane, int(v))
    if not isinstance(sp, dict):
        return _err(404, "no_diagram", "Nothing drawn yet for this view.")
    shown, ids = masked(rec["components"], viewer)
    ui = _ui_spec(sp, ids, {c["id"]: c for c in shown})
    title = html.escape(ui["meta"]["title"])
    body = (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body><h1>{title}</h1>{svg(ui)}"
            f"<script type='application/json' id='spec'>{html.escape(json.dumps(ui))}</script></body></html>")
    return HTMLResponse(body, headers={"Content-Disposition": f'attachment; filename="architecture-{vw}-v{int(v)}.html"'})


@router.put("/api/company/build/architecture/components/{component_id}")
async def put_component(request: Request, component_id: str):
    """Owner (architect role or head of department) or description (also the component's owner); saved as stated with by and at."""
    plane, viewer = _open(request)
    if plane is None:
        return _err(403, "forbidden", "This company space cannot be opened.")
    try:
        body = await request.json()
    except ValueError:
        return _err(422, "invalid", "Send the owner or the description as JSON.")
    if not isinstance(body, dict) or not ({"owner", "description"} & set(body)):
        return _err(422, "invalid", "Send the owner or the description.")
    editor = _editor(plane, viewer)
    people = pstore.raw(plane).get("people") or {}
    with lock_for(_file(plane, "record.json")):
        rec = read(plane)
        c = next((x for x in rec["components"] if x["id"] == component_id), None)
        if c is None or not may_see(c, viewer):
            return _err(404, "not_found", "There is no such component.")
        own = bool(c.get("owner")) and view.allows(frozenset({view.norm(c["owner"])}), viewer)
        if "owner" in body:
            if not editor:
                return _err(403, "forbidden", "Only the architect or the head of department sets an owner.")
            pid = body["owner"]
            if pid is not None and (not isinstance(pid, str) or pid not in people):
                return _err(422, "invalid", "Pick a person from the company people list.")
            c["owner"] = str(_cell(people[pid].get("name"))) if pid else None
            c["owner_by"] = {"mark": "stated", "by": viewer.name, "at": _now()}
        if "description" in body:
            if not (editor or own):
                return _err(403, "forbidden", "Only the component's owner or the architect edits the description.")
            t = body["description"]
            if not isinstance(t, str) or not t.strip() or len(t) > MAX_TEXT:
                return _err(422, "invalid", f"The description is a line of text, up to {MAX_TEXT} characters.")
            c["description"] = {"text": t.strip(), "mark": "stated", "by": viewer.name, "from": "Edited in the architecture record", "at": _now()}
        write_json_atomic(_file(plane, "record.json"), rec)
    shown, _ = masked([c], viewer)
    return shown[0]


def _person_id(plane, name: Any) -> str | None:
    if not name:
        return None
    for k, p in (pstore.raw(plane).get("people") or {}).items():
        if isinstance(p, dict) and view.norm(_cell(p.get("name")) or "") == view.norm(name):
            return k
    return None


def _change_titles(plane) -> dict[str, str]:
    from sh_platform.build import chain
    return {n["id"]: n.get("title") or n["id"] for n in chain.all_notes(plane)}


# ---- the map: Component nodes (55) ----------------------------------------------------------------------------------------------------

def add_component_nodes(g, plane, people) -> None:
    """Called by graph/build.py rebuild after add_build_nodes: one Component node per live record component, edges changed_by (to the
    Initiative that changed it) and part_of (to the blueprint). Restricted components carry the mart's list as their guard."""
    from sh_platform.graph import models
    from sh_platform.graph.build import _prov
    models.NODE_TYPES = tuple(dict.fromkeys((*models.NODE_TYPES, "Component")))
    models.EDGE_TYPES.setdefault("changed_by", (["Component"], ["Intent"]))
    models.EDGE_TYPES.setdefault("part_of", (["Component"], ["Blueprint"]))
    rec = read(plane)
    if not rec.get("version"):
        return
    from sh_platform.build import chain
    intent_of = {n["id"]: n.get("intent_id") for n in chain.all_notes(plane)}
    p = _prov(by="the architecture record", src="build/architecture/record.json", at=(rec.get("regenerated") or {}).get("at"))
    for c in rec["components"]:
        if c.get("state") in ("proposed", "retired"):
            continue
        guard = (sorted(view.norm(n) for n in c.get("may_see") or []), {}) if c.get("restricted") else None
        nid = g.node(f"component:{c['id']}", "Component", c["label"], p, "build", guard)
        for x in c.get("changed_by") or []:
            if intent_of.get(x):
                g.edge(nid, f"intent:{intent_of[x]}", "changed_by", p)
        bv = (c.get("refs") or {}).get("blueprint_version")
        if bv is not None:
            g.edge(nid, f"blueprint:v{bv}", "part_of", p)
