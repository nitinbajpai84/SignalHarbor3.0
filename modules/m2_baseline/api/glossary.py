"""M2-E2 routes: the business glossary (view, build, upload a provided glossary, decide, review, download). Declared in manifest.yaml and
sh_platform/route_permissions.yaml; every write is refused on a signed baseline by SignedGuard.

The company and the person come from the server session. A measure the person may not see is a stub in the view and absent from the
downloads (store/glossary.py). The provided glossary is read into terms on this machine; what Lens may read is kept as company context documents tagged as a glossary, split by restriction
and read into terms on this machine; only the unmatched terms' names and the unmatched measures' names go to the model, in one call.
"""
import base64
import binascii
import functools

from fastapi import APIRouter, Body, Request
from fastapi.responses import Response

from modules.m2_baseline.agent import glossary_lens as GL
from modules.m2_baseline.agent import lens
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.api.worklist import Ctx, guarded, plain
from modules.m2_baseline.domain import glossary as G
from modules.m2_baseline.domain import preread as PR
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.domain import glossary_export as E
from modules.m2_baseline.store import glossary as S
from modules.m2_baseline.store import kpis as K
from sh_platform.agents.runs import RunRegistry
from sh_platform.context_docs import reader

router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}/glossary"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ACCEPTED = ("xlsx", "csv", "md", "txt", "docx")
BAD_FILE = "That file could not be read. Please try again."
NO_TERMS = "We found no terms in that file. Each term needs its wording, for example one row per term in a table, or a line like \"Term: what it means\"."
WRONG_TYPE = "Please upload an Excel, csv, Markdown, text or Word file."
XLSX_ROWS = 5000
PARTIAL = f"Only the first {XLSX_ROWS} rows of a long sheet could be read. Split the glossary into smaller sheets if terms are missing."
TOO_MANY = "Only the first {} terms were read. Split the glossary into smaller files if terms are missing."


def answers(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except G.Refused as e:
            return plain(422, "invalid", str(e))
        except reader.Refusal as e:
            return plain(e.status, "refused", str(e))
    return guarded(inner)


def _matcher(ctx: Ctx, baseline_id: str, down: list):
    """The model call for the terms code could not match, or None when no model is set up. A refused call is noted in `down`, never silent."""
    model = ctx.model()
    if model is None:
        return None
    kpis = [k for k in K.read_kpis(ctx.plane, baseline_id) if ctx.sees(k)]
    company = str(ctx.company.get("name") or "")
    lens.register_names(ctx.plane, company, [ctx.name, *(o["value"] for k in kpis for o in k["owners"].values() if o["value"]),
                                             *(n for k in kpis for n in k["governance"]["may_see"])])
    gate, recorder, cid = ctx.request.app.state.entitlements, RunRegistry(ctx.plane), ctx.request.state.company_id

    def run(terms: list[str], measures: list[str]) -> dict[int, int] | None:
        try:
            return GL.match_by_meaning(model, gate, cid, company_name=company, industry=ctx.guidance.label, terms=terms, measures=measures, recorder=recorder)
        except lens.ModelUnreachable:
            down.append(True)
            return None  # not "nothing matched": the build keeps no answer and asks again next time
    return run


def _scans(plane) -> dict:
    try:
        return LS.scans(plane)
    except B.StoreError:
        return {}  # a damaged record: every document waits for the organiser (domain/preread.py `review`)


def _screen(ctx: Ctx, baseline_id: str, down=()) -> dict:
    base = ctx.baseline(baseline_id)
    held = PR.review(ctx.plane, ctx.pack_parts()) if ctx.organiser else set()  # the glossary kept as a company document is read for personal data too
    scan = _scans(ctx.plane)
    ask = [{"doc_id": i, "personal_words": (scan.get(i) or {}).get("words", [])[:6], "restrict_path": f"/api/agents/{lens.DOCUMENT_AGENT}/docs/{i}/visibility"}
           for i in S.read(ctx.plane, baseline_id).get("documents", []) if i in held]
    return {"baseline_id": baseline_id, "signed": base["state"] == "signed", "lens_available": ctx.model() is not None, "personal_documents": ask,

            **S.view(ctx.plane, baseline_id, ctx.sees), **({"lens_note": lens.LENS_NOTE} if down else {})}


@router.get(BASE)
@answers
def read(request: Request, baseline_id: str):
    ctx = Ctx(request)
    return _screen(ctx, baseline_id)


@router.post(BASE + "/build")
@answers
def build(request: Request, baseline_id: str):
    ctx, down = Ctx(request), []
    ctx.baseline(baseline_id)
    S.build(ctx.plane, baseline_id, ctx.sees, _matcher(ctx, baseline_id, down))
    return _screen(ctx, baseline_id, down)


@router.post(BASE + "/upload")
@answers
def upload(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    ctx, down = Ctx(request), []
    ctx.baseline(baseline_id)
    name = reader.safe_name(str(body.get("filename") or ""))
    if reader.ext_of(name) not in ACCEPTED:
        return plain(422, "refused", WRONG_TYPE)
    try:
        data = base64.b64decode(str(body.get("data") or ""), validate=True)
    except (binascii.Error, ValueError):
        return plain(400, "bad_request", BAD_FILE)
    terms, partial = G.parse_provided("\n".join(t for _, t in reader.read_segments(name, data, xlsx_rows=XLSX_ROWS)))
    if not terms:
        return plain(422, "refused", NO_TERMS)
    # the original file is not kept as retrievable text: Lens reads the parsed terms, split by restriction (store.glossary.sync_documents)
    provided = {"title": " ".join(str(body.get("title") or name).split())[:200], "filename": name, "by": ctx.name, "at": G.now(), "truncated": partial, "terms": terms}
    S.build(ctx.plane, baseline_id, ctx.sees, _matcher(ctx, baseline_id, down), provided=provided)
    return {**_screen(ctx, baseline_id, down), **({"note": TOO_MANY.format(G.MAX_TERMS) if len(terms) >= G.MAX_TERMS else PARTIAL} if partial else {})}


@router.put(BASE + "/entries/{kpi_id}")
@answers
def decide(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    S.decide(ctx.plane, baseline_id, kpi_id, ctx.sees, str(body.get("choice") or ""), str(body.get("text") or ""), ctx.name)
    return _screen(ctx, baseline_id)


@router.post(BASE + "/entries/{kpi_id}/review")
@answers
def review(request: Request, baseline_id: str, kpi_id: str):
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    S.review(ctx.plane, baseline_id, kpi_id, ctx.sees, ctx.name)
    return _screen(ctx, baseline_id)


@router.post(BASE + "/review-unchanged")
@answers
def review_unchanged(request: Request, baseline_id: str):
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    S.review_unchanged(ctx.plane, baseline_id, ctx.sees, ctx.name)
    return _screen(ctx, baseline_id)


def _download(request: Request, baseline_id: str):
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    company = str(ctx.company.get("name") or "company")
    rows, unmatched = S.rows_for_download(ctx.plane, baseline_id, ctx.sees)
    return company, rows, unmatched


@router.get(BASE + "/export")
@answers
def export_xlsx(request: Request, baseline_id: str):
    company, rows, unmatched = _download(request, baseline_id)
    return Response(E.build_xlsx(company, rows, unmatched), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{E.safe_filename(company)}.xlsx"'})


@router.get(BASE + "/print")
@answers
def export_html(request: Request, baseline_id: str):
    company, rows, unmatched = _download(request, baseline_id)
    return Response(E.to_html(company, rows, unmatched), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{E.safe_filename(company)}.html"'})
