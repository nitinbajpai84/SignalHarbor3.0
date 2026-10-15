"""SF13: the Span and Flow routes (plan 3.8), thin over span_model (SF09), span_suggest (SF10), span_design (SF11), flow (SF12),
design_doc (SF06) and archify_spec (SF05), plus the Pulse lines of plan 3.7 that are not proposals (proposals.pulse_lines carries those).

Every route: the permission table names the roles; this file refuses a company whose Build centre is switched off, and, where the plan
says "handler: architect role", anyone but the change's architect (a company admin may act when no architect is named, plan S2). Each GET
carries the R14 `fallback` flag and its one sentence. Agents draft, people sign: nothing here signs, applies or runs anything."""
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from sh_platform.build import alerts, architecture as A, archify_spec as S, chain as C, design_doc, proposals, runner
from sh_platform.build.agents import flow, runtime as R, span_design, span_model, span_suggest
from sh_platform.jsonfile import lock_for, write_json_atomic
from sh_platform.profile import view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
KINDS = ("current", "target", "delta")
DATA_ALERTS = ("failed", "missing", "late", "outside_range")  # flow.incident_note's kinds
INTENT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
EMPTY_TARGET = "Span drafts the target architecture once an Initiative is handed to Build."
NOT_ARCHITECT = "Only the change's architect can ask Span for this."
NOBODY = view.Viewer("", frozenset())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _spawn(fn) -> None:
    """Long drafts run beside the request (plan 3.1); tests replace this to run inline."""
    threading.Thread(target=fn, daemon=True).start()


def _switched_on(request: Request) -> bool:
    """The company exists and its Build centre is not switched off (absent switch means on, as entitlements.centres_for reads it)."""
    ent, cid = getattr(request.app.state, "entitlements", None), getattr(request.state, "company_id", None)
    if ent is None or not cid or ent.company(cid) is None:
        return False
    return ent.switches(cid)["centres"].get("build", True) is True


def _ctx(request: Request, architect: bool = False):
    if not _switched_on(request):
        return None, _err(403, "build_off", "The Build centre is switched off for this company.")
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return None, _err(403, "forbidden", "This company space cannot be opened.")
    if architect and not (C.holds(plane, viewer, ("architect",)) or "company_admin" in viewer.roles):
        return None, _err(403, "not_architect", NOT_ARCHITECT)
    return (plane, viewer), None


def _rt(request: Request, plane, viewer):
    return R.runtime_for_request(request, plane, viewer)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


# ---- diagrams per viewer -----------------------------------------------------------------------------------------------------------

def _secrets(plane, viewer: view.Viewer) -> set[str]:
    """Lower-case words this viewer may not read: the ids and labels of restricted components, and restricted source-map names (SF14)."""
    out = set()
    for c in A.read(plane)["components"]:
        if not A.may_see(c, viewer):
            out |= {str(c.get("id") or ""), S._safe(c.get("id") or "", set()), str(c.get("label") or "")}
    if "company_admin" not in viewer.roles:
        out |= {str(r.get("name") or "") for h in A._handoffs(plane) for r in h.get("source_map") or [] if isinstance(r, dict) and r.get("restricted")}
    return {w.lower() for w in out if len(w) >= 3}


def _stated_ok(plane, viewer: view.Viewer, spec: dict) -> bool:
    """An uploaded spec is shown as uploaded only to a viewer it names nothing hidden from (an id outside what they may see, or a restricted
    name anywhere in its text); anyone else gets the spec rebuilt from the records for them (SF14, SF13 finding 4)."""
    ids = {c.get("id") for c in spec.get("components") or [] if isinstance(c, dict)}
    if not ids <= S.known_ids(plane, viewer, span_design.target_draft(plane)) | {S.EGRESS}:
        return False
    text = json.dumps(spec, ensure_ascii=False).lower()
    return not any(w in text for w in _secrets(plane, viewer))


def _upload_errors(spec) -> list[str]:
    """What the plain renderer and every viewer's screen need from an upload beyond the schema: no markup, no web address, and a position
    and size on every component (a component without them would stop the page drawing for everyone)."""
    if not isinstance(spec, dict):
        return []
    text = json.dumps(spec, ensure_ascii=False).lower()
    if any(x in text for x in ("<", ">", "://", "javascript:")):
        return ["the diagram holds markup or a web address, which an uploaded diagram may not."]
    if any(not (isinstance(c, dict) and c.get("pos") and c.get("size")) for c in spec.get("components") or []):
        return ["every component needs a position and a size."]
    return []


def _spec(plane, viewer: view.Viewer, kind: str, doc: dict | None = None) -> dict:
    """A spec a person uploaded (stated) wins, for a viewer it hides nothing from; otherwise it is rebuilt for this viewer from the records
    and Span's target draft."""
    doc = doc if doc is not None else design_doc.read(plane)
    if doc and kind in (doc.get("stated_specs") or {}) and isinstance((doc.get("specs") or {}).get(kind), dict)             and _stated_ok(plane, viewer, doc["specs"][kind]):
        return doc["specs"][kind]
    draft = span_design.target_draft(plane)
    return S.current(plane, viewer) if kind == "current" else (S.target if kind == "target" else S.delta)(plane, viewer, draft)


def _diagrams(plane, viewer: view.Viewer, doc: dict | None) -> tuple[dict[str, str], list[str]]:
    svgs, errs = {}, []
    known = S.known_ids(plane, viewer, span_design.target_draft(plane))
    for kind in KINDS:
        sp = _spec(plane, viewer, kind, doc)
        e = S.validate(sp, known)
        if e:
            errs.append(f"The diagram could not be drawn: {e[0]}")
        else:
            svgs[kind] = S.svg_with_boundaries(sp)
    return svgs, errs


# ---- Span: room 0 target architecture -------------------------------------------------------------------------------------------------

def _target_view(plane, viewer: view.Viewer, draft: dict | None) -> dict:
    sp = S.target(plane, viewer, draft)
    e = S.validate(sp, S.known_ids(plane, viewer, draft))
    return {"spec": None if e else sp, "svg": None if e else S.svg_with_boundaries(sp), "diagram_error": f"The diagram could not be drawn: {e[0]}" if e else None}


@router.get("/api/company/build/span/target")
def get_target(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    draft = span_design.target_draft(plane)
    if draft is None:
        return {"draft": None, "fallback": False, "message": None, "empty": EMPTY_TARGET}
    return {"draft": {k: draft.get(k) for k in ("placements", "lines", "by", "at")}, "fallback": False, "message": None, "empty": None,
            **_target_view(plane, viewer, draft)}


@router.post("/api/company/build/span/target")
async def post_target(request: Request):
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    iid = (await _body(request)).get("intent_id")
    if not isinstance(iid, str) or not INTENT_ID.fullmatch(iid):
        return _err(422, "invalid", "Say which Initiative Span drafts the target for.")
    res = span_design.draft_target(plane, _rt(request, plane, viewer), iid)
    return {**res, **_target_view(plane, viewer, res.get("draft"))}


# ---- Span: model draft (room 1) -------------------------------------------------------------------------------------------------------

@router.get("/api/company/build/span/model-draft")
def get_model_draft(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    rec = span_model.latest(c[0])
    return {**rec, "fallback": bool(rec.get("fallback"))}


@router.post("/api/company/build/span/model-draft")
async def post_model_draft(request: Request):
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    try:
        rec = span_model.start(plane, _rt(request, plane, viewer), viewer.name, str((await _body(request)).get("changes") or ""))
    except span_model.DraftRefused as x:
        return _err(x.status, x.code, x.message)
    return JSONResponse({**rec, "fallback": bool(rec.get("fallback"))}, status_code=202)


@router.post("/api/company/build/span/model-draft/{draft_id}/file")
def post_model_file(request: Request, draft_id: str):
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    try:
        return span_model.file(plane, draft_id, viewer.name)
    except span_model.DraftRefused as x:
        return _err(x.status, x.code, x.message)


# ---- Span: suggestions to the data team -----------------------------------------------------------------------------------------------

@router.post("/api/company/build/span/review")
async def post_review(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    iid = (await _body(request)).get("intent_id")
    res = span_suggest.review(plane, _rt(request, plane, viewer), iid if isinstance(iid, str) and INTENT_ID.fullmatch(iid) else None)
    return {**res, "proposals": [proposals.shown(viewer, p) for p in res.get("proposals") or [] if proposals.visible(plane, viewer, p)]}


def after_blueprint_signed(request: Request, plane) -> None:
    """The sign hook (plan 3.5 step 5): Span reviews the model once after each blueprint signature, beside the request."""
    rt = R.runtime_for_request(request, plane, NOBODY)

    def run():
        try:
            span_suggest.review(plane, rt)
        except Exception:  # noqa: BLE001  a failed review never undoes a signature
            log.warning("Span's review after the blueprint signature failed", exc_info=True)
    _spawn(run)


# ---- the design document --------------------------------------------------------------------------------------------------------------

@router.get("/api/company/build/design")
def get_design(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    doc = design_doc.read(plane)
    if doc is None:
        return {"doc": None, "diagrams": {}, "fallback": False, "message": None, "empty": design_doc.EMPTY, "can_edit": False}
    svgs, errs = _diagrams(plane, viewer, doc)
    fb = bool((doc.get("drafted") or {}).get("fallback"))
    return {"doc": {k: v for k, v in doc.items() if k != "specs"}, "diagrams": svgs, "diagram_errors": errs, "fallback": fb,
            "message": design_doc.SPAN_SENTENCE if fb else None, "empty": None,
            "can_edit": C.holds(plane, viewer, ("architect",)) or "company_admin" in viewer.roles}


@router.get("/api/company/build/design/download")
def get_design_download(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    doc = design_doc.read(plane)
    svgs = _diagrams(plane, viewer, doc)[0] if doc else {}
    name = f"design-document-v{int(doc['version'])}.html" if doc else "design-document.html"
    return HTMLResponse(design_doc.render_plain(doc, svgs), headers={
        "Content-Disposition": f'attachment; filename="{name}"', "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:"})


@router.get("/api/company/build/design/spec")
def get_design_spec(request: Request, kind: str = "target"):
    c, e = _ctx(request)
    if e:
        return e
    if kind not in KINDS:
        return _err(422, "invalid", "Ask for the current, target or delta diagram.")
    plane, viewer = c
    doc = design_doc.read(plane)
    sp = _spec(plane, viewer, kind, doc)
    return {"kind": kind, "spec": sp, "stated": kind in ((doc or {}).get("stated_specs") or {}) and sp is (doc or {}).get("specs", {}).get(kind)}


@router.put("/api/company/build/design/spec")
async def put_design_spec(request: Request):
    """An architect's own layout: validated against the schema and the reference check, then kept as stated (a redraft keeps it)."""
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    b = await _body(request)
    kind, spec = b.get("kind"), b.get("spec")
    if kind not in KINDS:
        return _err(422, "invalid", "Say which diagram this is: current, target or delta.")
    errs = _upload_errors(spec) or S.validate(spec, S.known_ids(plane, viewer, span_design.target_draft(plane)))
    if errs:
        return _err(422, "invalid_spec", f"The diagram could not be drawn: {errs[0]}")
    path = design_doc._file(plane)
    with lock_for(path):
        doc = design_doc.read(plane)
        if doc is None:
            return _err(404, "no_design", design_doc.EMPTY)
        if doc["state"] == "signed":  # the signed version stays as design.v<n>.json; this opens the next one (as edit_line does)
            doc = {**doc, "version": doc["version"] + 1, "state": "draft", "signed_by": []}
        doc["specs"] = {**(doc.get("specs") or {}), kind: spec}
        doc["stated_specs"] = {**(doc.get("stated_specs") or {}), kind: {"mark": "stated", "by": viewer.name, "at": _now()}}
        write_json_atomic(path, doc)
    return {"kind": kind, "spec": spec, "stated": True, "version": doc["version"]}


@router.put("/api/company/build/design/lines")
async def put_design_line(request: Request):
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    b = await _body(request)
    sec, idx, text = b.get("section"), b.get("index"), b.get("text")
    if not isinstance(sec, str) or not isinstance(idx, int) or isinstance(idx, bool) or not isinstance(text, str) or not text.strip():
        return _err(422, "invalid", "Say which line changes and what it says.")
    doc = design_doc.edit_line(plane, sec, idx, text.strip(), viewer.name)
    if doc is None:
        return _err(404, "no_line", "There is no such line in the design document.")
    return {"doc": {k: v for k, v in doc.items() if k != "specs"}}


def _redraft(plane, rt) -> None:
    """Span's redraft, then the stated specs put back (draft_design writes fresh specs; a person's own layout is never overwritten, S6)."""
    kept = design_doc.read(plane) or {}
    stated = {k: kept["specs"][k] for k in (kept.get("stated_specs") or {}) if k in (kept.get("specs") or {})}
    try:
        span_design.draft_design(plane, rt)
    except Exception:  # noqa: BLE001  the previous draft stays
        log.warning("Span's design redraft failed", exc_info=True)
        return
    if stated:
        with lock_for(design_doc._file(plane)):
            doc = design_doc.read(plane)
            if doc:
                write_json_atomic(design_doc._file(plane), {**doc, "specs": {**(doc.get("specs") or {}), **stated},
                                                            "stated_specs": kept["stated_specs"]})


@router.post("/api/company/build/design/redraft")
def post_design_redraft(request: Request):
    c, e = _ctx(request, architect=True)
    if e:
        return e
    plane, viewer = c
    if not design_doc.has_records(plane):
        return _err(409, "no_change", design_doc.EMPTY)
    rt = _rt(request, plane, viewer)
    _spawn(lambda: _redraft(plane, rt))
    return JSONResponse({"state": "drafting", "message": "Span is redrafting the design document."}, status_code=202)


# ---- Flow: run notes (room 2) and incident notes (room 3) -------------------------------------------------------------------------------

def _run_seen(plane, viewer: view.Viewer, run_id: str) -> bool:
    run = next((r for r in runner.read_runs(plane) if r.get("id") == run_id), None)
    return run is not None and run.get("source") not in runner._hidden_sources(plane, viewer)


@router.get("/api/company/build/flow/runs/{run_id}")
def get_run_note(request: Request, run_id: str):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    note = (flow.read_note(plane, run_id) if _run_seen(plane, viewer, run_id) else None) or flow.explain_run(plane, run_id, _rt(request, plane, viewer))
    if note is None:
        return _err(404, "not_found", "There is no such run.")
    return {**note, "fallback": bool(note.get("fallback"))}


@router.post("/api/company/build/flow/runs/{run_id}/explain")
def post_run_explain(request: Request, run_id: str):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    note = flow.explain_run(plane, run_id, _rt(request, plane, viewer), fresh=True)
    if note is None:
        return _err(404, "not_found", "There is no such run.")
    return {**note, "fallback": bool(note.get("fallback"))}


@router.get("/api/company/build/flow/incidents")
def get_incidents(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c
    rt, out = _rt(request, plane, viewer), []
    for a in alerts._read(plane):
        if a.get("state") != "open" or a.get("kind") not in DATA_ALERTS:
            continue
        p = flow.incident_note(plane, rt, str(a.get("id")))
        if p and proposals.visible(plane, viewer, p):
            out.append({"alert_id": a.get("id"), "note": proposals.shown(viewer, p), "fallback": bool(p.get("fallback")), "sentence": p.get("sentence")})
    return {"incidents": out, "fallback": any(i["fallback"] for i in out)}


# ---- Pulse (plan 3.7): drafts to check and Flow's run notes; the suggestion lines come from proposals.pulse_lines ----------------------

def agent_lines(plane, v: view.Viewer) -> dict[str, list[dict]]:
    from sh_platform.pulse.lines import line
    decide, watch = [], []
    if C.holds(plane, v, ("architect",)):
        doc = design_doc.read(plane)
        if doc and doc.get("state") == "draft" and (doc.get("drafted") or {}).get("by") == "Span":
            t = next((n.get("title") for n in C.all_notes(plane) if n.get("state") not in ("live", "stopped")), None) or "the open change"
            decide.append(line(f"span-design:v{doc['version']}", "request", f"Span drafted the design document for {t}. Check it.", f"Version {doc['version']}",
                               "/centre/build/blueprint#design", "Open the design document", "build/design/design.json", (doc.get("drafted") or {}).get("at")))
        rec = span_model.latest(plane)
        if rec.get("state") == "failed":
            decide.append(line(f"span-model:{rec.get('id')}", "request", "Span could not make the model build. See why.", str(rec.get("message") or ""),
                               "/centre/build/blueprint", "See why", "build/span/model_draft.json", rec.get("started_at")))
    if C.holds(plane, v, ("developer",)):
        since, hidden = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(), runner._hidden_sources(plane, v)
        newest: dict[str, dict] = {}
        for r in runner.read_runs(plane):
            if r.get("id") and r.get("source") not in hidden:
                newest[r["source"]] = r
        for src, r in newest.items():
            note = flow.read_note(plane, r["id"])
            if note and note.get("status") == "failed" and str(note.get("at")) >= since:
                watch.append(line(f"flow-run:{r['id']}", "brief", f"Flow explained why {str(src).replace('_', ' ')} failed its checks.", str(note.get("first_missing_link") or ""),
                                  "/centre/build/pipelines", "Read the note", f"build/flow/runs/{r['id']}.json", note.get("at")))
    return {"decide": decide, "watch": watch}
