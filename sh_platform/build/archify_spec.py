"""SF05: the Archify specs of the design document (plan 3.6): current, target and the delta, with two fixed boundaries, the strategic flag on
sources, validation before render and a plain SVG with the boundaries drawn.

Wraps architecture.py (never edits it): its `masked` decides what a viewer sees and its `spec` lays the components out; this file makes the
result schema-valid (Archify ids allow letters, digits, `_` and `-` only), adds the "Company plane" boundary around every component and the
"Egress gateway" node sitting on that boundary (the only exit), and checks every spec against the copied Archify schema in `archify/`
(MIT, see archify/LICENCE-ARCHIFY.txt) with no network: the two schemas are loaded from disk and any other reference is refused.

A Span target draft is `{"placements": [{"id", "kind", "label", "view"?, "interfaces"?: [{"to", "kind"}], "why"?}]}`; each placement is drawn
tagged "Span's suggestion". Every other component traces to the architecture record."""
import html
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

from sh_platform.build import architecture as A
from sh_platform.intents import source_map as SM
from sh_platform.profile import view

SCHEMAS = Path(__file__).parent / "archify"
EGRESS = "egress-gateway"
PLANE_LABEL, EGRESS_LABEL = "Company plane", "Egress gateway"
SPAN_TAG = "Span's suggestion"
SPAN_FROM = "Span's target draft"
PAD = 20
NODE_W, NODE_H = 160, 64
EMPTY_BOX = (40, 40, 360, 200)  # the plane drawn for a company with nothing recorded yet


# ---- building the three specs ---------------------------------------------------------------------------------------------------------

def _safe(raw: str, taken: set[str]) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw)).strip("-") or "c"
    s = s if s[0].isalpha() else f"c-{s}"
    out, n = s, 2
    while out in taken or out == EGRESS:
        out, n = f"{s}-{n}", n + 1
    taken.add(out)
    return out


def _placements(draft: dict | None, vw: str, have: set[str]) -> list[dict]:
    """Span's placements as record-shaped components (state proposed, from Span's draft). A placement reusing a record id is ignored."""
    out = []
    for p in (draft or {}).get("placements") or []:
        if not isinstance(p, dict) or not p.get("id") or not p.get("label") or (p.get("view") or "data") != vw or str(p["id"]) in have:
            continue
        ifs = [{"to": str(i["to"]), "kind": str(i.get("kind") or "feeds")} for i in p.get("interfaces") or [] if isinstance(i, dict) and i.get("to")]
        out.append({"id": str(p["id"]), "view": vw, "kind": str(p.get("kind") or "system"), "label": str(p["label"])[:80], "state": "proposed",
                    "from": SPAN_FROM, "restricted": False, "may_see": None, "interfaces": ifs})
        have.add(str(p["id"]))
    return out


def _strategic(plane, viewer: view.Viewer) -> dict[str, dict]:
    """{normalised source name: source map row} from every Initiative handed to Build (R16). A restricted row is never used for a viewer
    outside the company admin, so a hidden source's flag cannot be read off the diagram."""
    out: dict[str, dict] = {}
    for h in A._handoffs(plane):
        for r in h.get("source_map") or []:
            if isinstance(r, dict) and r.get("name") and (not r.get("restricted") or "company_admin" in viewer.roles):
                out.setdefault(view.norm(r["name"]), r)
    return out


def _finish(sp: dict, shown: list[dict], vw: str, kind: str, plane, viewer: view.Viewer, focus_label: str | None) -> dict:
    """Schema-safe ids, the Span tag, the strategic flag, the egress node and the two boundaries."""
    taken: set[str] = set()
    ids = {c["id"]: _safe(c["id"], taken) for c in sp["components"]}
    by = {c["id"]: c for c in shown}
    flags, cards = _strategic(plane, viewer), []
    comps = []
    for c in sp["components"]:
        rec = by.get(c["id"], {})
        n = {**c, "id": ids[c["id"]], "label": str(c.get("label") or "Unnamed")[:80], "sublabel": str(c.get("sublabel") or rec.get("kind") or "")}
        if rec.get("from") == SPAN_FROM:
            n["tag"] = SPAN_TAG
        row = flags.get(view.norm(rec.get("label"))) if rec.get("kind") == "source" and not str(rec.get("id")).startswith("restricted-") else None  # masked ones stay unnamed
        if row:
            if row.get("strategic"):
                n["sublabel"] = "strategic"
            cards.append(f"{n['label']}: {SM.ZONES.get(row.get('zone'), SM.ZONES['unknown'])}{', strategic' if row.get('strategic') else ''}")
        comps.append(n)
    conns = [{**k, "id": f"{ids[k['from']]}--{ids[k['to']]}", "from": ids[k["from"]], "to": ids[k["to"]], "label": str(k.get("label") or "")}
             for k in sp.get("connections") or [] if k["from"] in ids and k["to"] in ids]
    wraps = [c["id"] for c in comps]
    x0, y0, x1, y1 = _box(comps)
    comps.append({"id": EGRESS, "type": "security", "label": EGRESS_LABEL, "sublabel": "the only exit", "pos": [x1 - NODE_W / 2, (y0 + y1 - NODE_H) / 2],
                  "size": [NODE_W, NODE_H]})
    focus = [ids[i] for v in sp["meta"].get("views") or [] for i in v.get("focus") or [] if i in ids]
    meta = {"title": sp["meta"]["title"], "output": f"build/design/{vw}-{kind}.html"}
    if focus and focus_label:
        meta["views"] = [{"id": "this-change", "label": focus_label, "focus": focus}]
    out = {"schema_version": 1, "diagram_type": "architecture", "meta": meta, "components": comps, "connections": conns,
           "boundaries": [{"kind": "region", "label": PLANE_LABEL, "wraps": wraps or [EGRESS], "pad": PAD},
                          {"kind": "security-group", "label": EGRESS_LABEL, "wraps": [EGRESS], "pad": 8}],
           "cards": [{"dot": "amber", "title": "Sources and their strategic flags", "items": cards}] if cards else []}
    return out


def _box(comps: list[dict]) -> tuple[float, float, float, float]:
    """The plane rectangle: every component except the egress node, padded. The egress node's centre sits on its right edge."""
    inside = [c for c in comps if c["id"] != EGRESS and isinstance(c.get("pos"), list) and isinstance(c.get("size"), list)]
    if not inside:
        return EMPTY_BOX
    return (min(c["pos"][0] for c in inside) - PAD, min(c["pos"][1] for c in inside) - PAD,
            max(c["pos"][0] + c["size"][0] for c in inside) + PAD, max(c["pos"][1] + c["size"][1] for c in inside) + PAD)


def _build(plane, viewer: view.Viewer, comps: list[dict], version: int, vw: str, kind: str, title: str, focus: set[str],
           focus_label: str | None = None) -> dict:
    shown, ids = A.masked(comps, viewer)
    sp = A.spec({"components": shown, "version": version}, vw, {ids[i] for i in focus if i in ids})
    sp["meta"]["title"] = title
    return _finish(sp, shown, vw, kind, plane, viewer, focus_label)


def _signed(plane) -> dict:
    """The newest regenerated record version (record.v<n>.json), the one the signed records made."""
    n = int(A.read(plane).get("version") or 0)
    return A.read(plane, n) if n else A.read(plane)


def current(plane, viewer: view.Viewer, vw: str = "data") -> dict:
    rec = _signed(plane)
    n = int(rec.get("version") or 0)
    return _build(plane, viewer, rec["components"], n, vw, "current", f"Current state, {vw} view, version {n}" if n else f"Current state, {vw} view",
                  set())


def _target_parts(plane, vw: str, draft: dict | None) -> tuple[list[dict], set[str], int]:
    """The draft record (signed components plus the open changes' proposed ones) and Span's placements; the ids that change."""
    rec = A.read(plane)
    comps = [c for c in rec["components"] if c.get("view") == vw]
    spans = _placements(draft, vw, {c["id"] for c in rec["components"]})
    changing = {c["id"] for c in comps if c.get("state") == "proposed"} | {p["id"] for p in spans}
    return comps + spans, changing, int(rec.get("version") or 0)


def target(plane, viewer: view.Viewer, draft: dict | None = None, vw: str = "data") -> dict:
    comps, _, n = _target_parts(plane, vw, draft)
    return _build(plane, viewer, comps, n, vw, "target", f"Target architecture, {vw} view", set())


def delta(plane, viewer: view.Viewer, draft: dict | None = None, vw: str = "data") -> dict:
    comps, changing, n = _target_parts(plane, vw, draft)
    return _build(plane, viewer, comps, n, vw, "delta", f"What changes, {vw} view", changing, "This change")


def known_ids(plane, viewer: view.Viewer, draft: dict | None = None, vw: str = "data") -> set[str]:
    """The ids a spec for this viewer may hold: the record's components, Span's placements and the fixed egress node (for `validate`)."""
    return {c["id"] for c in target(plane, viewer, draft, vw)["components"]}


# ---- validation before render ---------------------------------------------------------------------------------------------------------

def _refuse(uri: str):
    raise NoSuchResource(ref=uri)  # no network: only the two schemas on disk resolve


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    arch, common = (json.loads((SCHEMAS / f).read_text(encoding="utf-8")) for f in ("architecture.schema.json", "common.schema.json"))
    reg = Registry(retrieve=_refuse).with_resources([(s["$id"], Resource.from_contents(s)) for s in (arch, common)])
    return Draft202012Validator(arch, registry=reg)


_ITEM = {"components": "component", "connections": "connection", "boundaries": "boundary"}


def _where(spec: dict, path: list) -> str:
    if len(path) >= 2 and path[0] in _ITEM and isinstance(path[1], int):
        item = (spec.get(path[0]) or [None] * (path[1] + 1))[path[1]]
        name = (item.get("id") or item.get("label")) if isinstance(item, dict) else None
        return " ".join([f"{_ITEM[path[0]]} {name or path[1] + 1}", *map(str, path[2:])])
    return " ".join(map(str, path)) or "the diagram"


def _plain(spec: dict, e) -> str:
    where = _where(spec, list(e.absolute_path))
    if e.validator in ("enum", "const"):
        return f"{where}: {json.dumps(e.instance)[:60]} is not an allowed value."
    if e.validator == "required":
        return f"{where}: {e.message.split(' is a required')[0]} is missing."
    if e.validator == "additionalProperties":
        return f"{where}: has a field the diagram does not allow."
    if e.validator == "pattern":
        return f"{where}: uses characters an id may not use."
    if e.validator == "minItems":
        return f"{where}: is empty."
    return f"{where}: {e.message[:160]}"


def validate(spec: Any, known: set[str] | None = None) -> list[str]:
    """Plain-word errors, first one first; empty means it may be drawn. Schema check, then the reference check: connections, boundaries and
    views name components that exist, and (when `known` is given) every component traces to the record, a Span placement or the egress node."""
    if not isinstance(spec, dict):
        return ["The diagram is not a JSON object."]
    errs = [_plain(spec, e) for e in sorted(_validator().iter_errors(spec), key=lambda e: e.json_path)]
    comps = [c for c in spec.get("components") or [] if isinstance(c, dict)] if isinstance(spec.get("components"), list) else []
    ids = [c.get("id") for c in comps]
    have = set(ids)
    errs += [f"Two components share the id {i}." for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    for k in spec.get("connections") or [] if isinstance(spec.get("connections"), list) else []:
        if isinstance(k, dict) and not {k.get("from"), k.get("to")} <= have:
            errs.append(f"The connection from {k.get('from')} to {k.get('to')} points at a component that is not in the diagram.")
    for b in spec.get("boundaries") or [] if isinstance(spec.get("boundaries"), list) else []:
        if isinstance(b, dict):
            errs += [f"The boundary {b.get('label')} wraps {w}, which is not in the diagram." for w in b.get("wraps") or [] if w not in have]
    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    for v in meta.get("views") or [] if isinstance(meta.get("views"), list) else []:
        if isinstance(v, dict):
            errs += [f"The view {v.get('label')} focuses on {f}, which is not in the diagram." for f in v.get("focus") or [] if f not in have]
    if known is not None:
        errs += [f"The component {i} traces to no record and is not one of Span's suggestions." for i in ids if i not in known | {EGRESS}]
    return errs


# ---- render (step 1) ------------------------------------------------------------------------------------------------------------------

def boundary_rects(spec: dict) -> list[dict]:
    """[{label, kind, x, y, w, h}] in drawing order: the plane first, then the egress group around its node."""
    comps = spec.get("components") or []
    out = []
    for b in spec.get("boundaries") or []:
        if b.get("label") == PLANE_LABEL:
            x0, y0, x1, y1 = _box(comps)
        else:
            inside = [c for c in comps if c["id"] in b.get("wraps", [])]
            if not inside:
                continue
            p = b.get("pad", PAD)
            x0, y0 = min(c["pos"][0] for c in inside) - p, min(c["pos"][1] for c in inside) - p
            x1, y1 = max(c["pos"][0] + c["size"][0] for c in inside) + p, max(c["pos"][1] + c["size"][1] for c in inside) + p
        out.append({"label": b["label"], "kind": b["kind"], "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
    return out


def svg_with_boundaries(spec: dict) -> str:
    """architecture.svg plus a dashed rectangle per boundary, drawn behind the components. Call `validate` first."""
    ui = A._ui_spec(spec, {}, {})
    body = A.svg(ui)
    head, rest = body.split(">", 1)
    rects = "".join(
        f'<rect x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" rx="10" fill="none" stroke="{"#b45309" if r["kind"] == "security-group" else "#555"}" '
        f'stroke-dasharray="6 4"/><text x="{r["x"] + 8}" y="{r["y"] - 6 if r["kind"] == "region" else r["y"] + r["h"] + 14}" fill="#555">{html.escape(str(r["label"]))}</text>'
        for r in boundary_rects(spec))
    return f"{head}>{rects}{rest}"
