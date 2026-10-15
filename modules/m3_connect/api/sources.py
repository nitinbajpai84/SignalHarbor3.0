"""M3-P01 source map routes: the map, a re-score, one source's panel, a person's override. The company and the person come from the server
session. Lens scores from the signed baseline and charter; a viewer is shown only what they may see (domain/sources.py)."""
import logging

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m3_connect.agent import score_lens
from modules.m3_connect.api.assessment import NOT_FOUND, _plane, _viewer, guarded, plain
from modules.m3_connect.domain import counters as K
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import sources as S
from modules.m3_connect.store import assessment as A
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
BAD_BODY = "That could not be read. Please check the values and try again."
NO_SOURCE = "We could not find that source."
OUTSIDER = I.Viewer("", frozenset())  # someone with no standing: what they cannot see is what is restricted


def _context(request: Request, assessment_id: str):
    """(plane, assessment folder, baseline outcome, assessment) or None when there is no such assessment or baseline."""
    plane = _plane(request)
    a = A.read_assessment(plane, assessment_id)
    baseline = I.read_baseline_outcome(plane, a["baseline_outcome_id"]) if a else None
    return (plane, A.folder(plane, assessment_id), baseline, a) if baseline else None


def _extras(plane, baseline: dict) -> dict:
    """Who answered, and which measures have a sample, from module 2's answers file (read by path)."""
    bid = baseline.get("baseline_id")
    rows = read_json_strict(plane.path("intents", "m2_baseline", bid, "answers.json")) if I._HEX.fullmatch(str(bid)) else None
    rows = [r for r in rows or [] if isinstance(r, dict)]
    return {"answered": {I._norm(r.get("owner_name")) for r in rows},
            "samples": {r.get("kpi_id") for r in rows if r.get("sample_doc_id") and I._t(r["sample_doc_id"])}}


def _model(request: Request, plane):
    factory = getattr(request.app.state, "lens_model_factory", None)  # tests plug a stub in here
    override = getattr(request.app.state, "model_env", None)
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _rescore(request: Request, plane, folder, baseline, a) -> dict:
    full = I.read_inputs(plane, baseline, a["charter_outcome_id"], I.SYSTEM)
    outsider = I.read_inputs(plane, baseline, a["charter_outcome_id"], OUTSIDER)
    scored = S.score_all(full, outsider, _extras(plane, baseline))
    return S.save_scored(folder, score_lens.apply(_model(request, plane), scored), not_needed=S.unneeded(full))


def _doc(request: Request, assessment_id: str, rescore: bool = False):
    ctx = _context(request, assessment_id)
    if ctx is None:
        return None
    plane, folder, baseline, a = ctx
    doc = None if rescore else S.read(folder)
    doc = doc or _rescore(request, plane, folder, baseline, a)
    return doc, I.read_inputs(plane, baseline, a["charter_outcome_id"], _viewer(request)), folder


def _map(doc: dict, viewer_inputs: dict) -> dict:
    seen = {I._t(s.get("Source ID")) for s in viewer_inputs["sources"]}  # a source this viewer may not see is not named, not even as not needed
    return {"scored_at": doc["scored_at"], "zones": S.ZONES, "sources": [S.view(s, viewer_inputs) for s in doc["sources"]],
            "not_needed": [u for u in doc.get("not_needed") or [] if u["id"] in seen],
            "left_out": [{"measure": x["kpi_id"], "name": x.get("name"), "reason": x.get("reason"), "restricted": bool(x.get("restricted"))}
                         for x in viewer_inputs.get("left_out") or []]}


@router.get("/assessments/{assessment_id}/sources")
@guarded
def get_map(assessment_id: str, request: Request):
    got = _doc(request, assessment_id)
    return _map(got[0], got[1]) if got else plain(404, "not_found", NOT_FOUND)


@router.post("/assessments/{assessment_id}/sources/score")
@guarded
def rescore(assessment_id: str, request: Request):
    got = _doc(request, assessment_id, rescore=True)
    return _map(got[0], got[1]) if got else plain(404, "not_found", NOT_FOUND)


@router.get("/assessments/{assessment_id}/sources/{source_id}")
@guarded
def get_source(assessment_id: str, source_id: str, request: Request):
    got = _doc(request, assessment_id)
    if got is None:
        return plain(404, "not_found", NOT_FOUND)
    s = next((x for x in got[0]["sources"] if x["id"] == source_id), None)
    if s is None:
        return plain(404, "not_found", NO_SOURCE)
    shown = S.panel(s, got[1], _viewer(request))
    if shown is None:  # restricted for this viewer: the panel is the placeholder name and nothing else
        return {"source": S.view(s, got[1]), "tables": [], "measures": [], "missing": [], "impact_reasons": [], "readiness_reasons": []}
    return {"source": shown, **{k: shown[k] for k in ("tables", "measures", "missing", "impact_reasons", "readiness_reasons")}}


@router.put("/assessments/{assessment_id}/sources/{source_id}/override")
@guarded
def put_override(assessment_id: str, source_id: str, request: Request, body: dict | None = Body(default=None)):
    if not isinstance(body, dict):
        return plain(400, "bad_request", BAD_BODY)
    got = _doc(request, assessment_id)
    if got is None:
        return plain(404, "not_found", NOT_FOUND)
    s = next((x for x in got[0]["sources"] if x["id"] == source_id), None)
    if s is None or S._hidden(s, got[1]):
        return plain(404, "not_found", NO_SOURCE)
    try:
        moved = S.set_override(got[2], source_id, body.get("impact"), body.get("readiness"), body.get("reason"), _viewer(request).name,
                            by_id=str(request.state.account_id))
    except S.OverrideError as e:
        return plain(400, "bad_request", str(e))
    K.bump(got[2], "override_source", free_text=bool(str(body.get("reason") or "").strip()))
    return JSONResponse({"source": S.view(moved, got[1])})
