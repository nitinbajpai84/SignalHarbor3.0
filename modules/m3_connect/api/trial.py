"""M3-P03 routes: compile the rules, run the trial, read it, mark a rule checked, read the findings.
Base /api/modules/m3_connect/assessments/{assessment_id}/. The company and the person come from the session. A measure the viewer may not see
is "A restricted measure" and nothing else: no rule, no figure, no source. Declared in manifest.yaml and sh_platform/route_permissions.yaml."""
import logging

from fastapi import APIRouter, Request

from modules.m3_connect.agent import compile as C
from modules.m3_connect.agent import explain as X
from modules.m3_connect.api import intake as intake_api
from modules.m3_connect.api.assessment import NOT_FOUND, _plane, _viewer, guarded, plain
from modules.m3_connect.domain import counters as K
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import from_profile as FP
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import intake_store as S
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import trial as T
from modules.m3_connect.store import assessment as A

log = logging.getLogger(__name__)
router = APIRouter()
NO_RULE = "There is no rule to check for that measure."
NOT_ALLOWED = "Only the data analyst or the head of data can do that."
CANNOT_CHECK = "A rule that could not be written cannot be marked as checked."


def _may(request: Request, *roles: str) -> bool:
    """The manifest lets all three roles in (module 3's table); who may change something is decided here, in plain words."""
    return bool(set(request.state.roles or []) & set(roles))


class _Ctx:
    def __init__(self, request: Request, assessment_id: str):
        self.request, self.plane, self.viewer = request, _plane(request), _viewer(request)
        self.a = A.read_assessment(self.plane, assessment_id)
        self.adir = A.folder(self.plane, assessment_id)
        baseline = I.read_baseline_outcome(self.plane, self.a["baseline_outcome_id"]) if self.a else None
        self.inputs = I.read_inputs(self.plane, baseline, self.a["charter_outcome_id"], self.viewer) if baseline else None
        st = request.app.state
        self.company = st.entitlements.company(request.state.company_id) or {}
        # the same read as the head of data (sees everything): what it has and this viewer's read lacks was withheld by module 2's guards
        self.full = I.read_inputs(self.plane, baseline, self.a["charter_outcome_id"], I.SYSTEM) if baseline else None

    @property
    def ok(self) -> bool:
        return self.a is not None and self.inputs is not None

    def shut(self) -> frozenset[str]:
        """Sources whose rows came from a restricted profile sample this viewer may not see: their figures are masked like a restricted measure's."""
        return frozenset(FP.shut_sources(self.adir, self.plane, intake_api._pv(self.request, self.viewer)))

    def hidden(self) -> set[str]:
        return T.hidden_measures(self.inputs, R.read_rules(self.adir), self.viewer, self.full, T.source_marks(self.adir), self.shut())

    def sources_seen(self) -> set[str]:
        return {I._t(s.get("Source ID")) for s in self.inputs.get("sources") or []} - self.shut()

    def pack_kpis(self) -> list:
        try:
            return list((self.request.app.state.packs.load(str(self.company.get("industry", ""))).section("kpi_tree") or {}).get("kpis") or [])
        except (ValueError, KeyError, OSError, AttributeError):
            return []

    def synonyms(self) -> dict:
        """The industry pack's column spellings (suggestions only), as P02 reads them; {} when the pack has none."""
        try:
            pack = self.request.app.state.packs.load(str(self.company.get("industry", "")))
            raw = pack.section("column_synonyms") if "column_synonyms" in pack.sections() else None
        except (ValueError, KeyError, OSError, AttributeError):
            return {}
        return raw.get("feeds") if isinstance(raw, dict) and isinstance(raw.get("feeds"), dict) else {}

    def model(self):
        model = C.get_model(self.request.app.state, self.plane)
        if model is not None:
            owners = [str(v) for m in self.inputs["measures"] if not m.get("restricted") for v in (m.get("owners") or {}).values() if v]
            C.register_names(self.plane, str(self.company.get("name") or ""), owners)
        return model


def _view(ctx: _Ctx) -> dict:
    rules, trial, bench = R.read_rules(ctx.adir), R.read_file(ctx.adir, "trial.json", {}), {b["measure_id"]: b for b in T.benchmarks(ctx.adir)}
    hide, rows = ctx.hidden(), []
    for m in ctx.inputs["measures"]:
        if m["id"] in hide:
            rows.append({"measure": m["id"], "name": I.RESTRICTED_NAME, "restricted": True})
            continue
        r, t = rules.get(m["id"]) or {}, trial.get(m["id"]) or {}
        rows.append({**t, "measure": m["id"], "name": m.get("name"), "restricted": False, "benchmark": bench.get(m["id"]),
                     "rule": {"state": r.get("state"), "origin": r.get("origin"), "words": r.get("words"), "reason": r.get("reason"),
                              "checked_by": r.get("checked_by"), "checked_at": r.get("checked_at"),
                              "auto_checked": bool(r.get("auto_checked"))} if r else None})
    return {"measures": rows, "compiled": bool(rules), "run": bool(trial), "model_used": any((r.get("origin") != "pack hint") for r in rules.values() if r.get("rule"))}


@router.post("/assessments/{assessment_id}/trial/compile")
@guarded
def compile_rules(assessment_id: str, request: Request):
    if not _may(request, "analyst", "company_admin"):
        return plain(403, "forbidden", NOT_ALLOWED)
    ctx = _Ctx(request, assessment_id)
    if not ctx.ok:
        return plain(404, "not_found", NOT_FOUND)
    plane, cid = ctx.plane, request.state.company_id
    measures = [m for m in ctx.inputs["measures"] if not m.get("restricted")]
    C.compile_all(ctx.model(), request.app.state.entitlements, cid, plane, ctx.adir, measures, T.columns_by_source(ctx.adir),
                  lambda mid: T.feeders(ctx.adir, mid), ctx.pack_kpis(), F.technical_of, ctx.synonyms())
    K.bump(ctx.adir, "compile_rules")
    return _view(ctx)


@router.post("/assessments/{assessment_id}/trial/run")
@guarded
def run_trial(assessment_id: str, request: Request):
    if not _may(request, "analyst", "company_admin"):
        return plain(403, "forbidden", NOT_ALLOWED)
    ctx = _Ctx(request, assessment_id)
    if not ctx.ok:
        return plain(404, "not_found", NOT_FOUND)
    try:  # the profile's samples and figures are taken first, so the trial never waits for what the company already brought
        intake_api.Ctx(ctx.plane, request.state.company_id, assessment_id, intake_api._clock(request)).adopt(request, ctx.viewer)
    except (S.StoreError, LookupError) as e:
        log.warning("the profile could not be read for the trial: %s", type(e).__name__)
    hide = ctx.hidden()
    trial = T.run_trial(ctx.adir, [m for m in ctx.inputs["measures"] if m["id"] not in hide])
    model = ctx.model()
    if model is not None:
        trial = X.reword_all(model, request.app.state.entitlements, request.state.company_id, ctx.plane,
                             {k: v for k, v in trial.items() if k not in hide}, {m["id"]: m.get("name") for m in ctx.inputs["measures"]})
        R.write_file(ctx.adir, "trial.json", {**R.read_file(ctx.adir, "trial.json", {}), **trial})
    F.build(ctx.adir, ctx.full, hide)  # built from the whole (the head of data's read), shown to each reader through F.for_viewer
    K.bump(ctx.adir, "run_trial")
    return _view(ctx)


@router.get("/assessments/{assessment_id}/trial")
@guarded
def get_trial(assessment_id: str, request: Request):
    ctx = _Ctx(request, assessment_id)
    return _view(ctx) if ctx.ok else plain(404, "not_found", NOT_FOUND)


@router.post("/assessments/{assessment_id}/trial/rules/{measure_id}/check")
@guarded
def check_rule(assessment_id: str, measure_id: str, request: Request):
    if not _may(request, "analyst"):
        return plain(403, "forbidden", NOT_ALLOWED)
    ctx = _Ctx(request, assessment_id)
    if not ctx.ok:
        return plain(404, "not_found", NOT_FOUND)
    rules = R.read_rules(ctx.adir)
    rec = rules.get(measure_id)
    if measure_id in ctx.hidden() or not rec:
        return plain(404, "not_found", NO_RULE)
    if rec.get("state") == R.COULD_NOT:
        return plain(409, "cannot_check", CANNOT_CHECK)
    rules[measure_id] = {**{k: v for k, v in rec.items() if k != "auto_checked"}, "state": "checked", "checked_by": ctx.viewer.name, "checked_at": R.now()}  # a person's check replaces Lens's own
    R.write_file(ctx.adir, "rules.json", rules)
    trial = R.read_file(ctx.adir, "trial.json", {})
    if measure_id in trial:
        trial[measure_id].update(rule_state="checked", checked_by=ctx.viewer.name)
        R.write_file(ctx.adir, "trial.json", trial)
    F.build(ctx.adir, ctx.full, ctx.hidden())
    K.bump(ctx.adir, "check_rule")
    return _view(ctx)


@router.get("/assessments/{assessment_id}/findings")
@guarded
def get_findings(assessment_id: str, request: Request):
    ctx = _Ctx(request, assessment_id)
    if not ctx.ok:
        return plain(404, "not_found", NOT_FOUND)
    data = R.read_file(ctx.adir, "findings.json", {})
    return {"built": bool(data), **F.for_viewer(data if isinstance(data, dict) else {}, ctx.hidden(), ctx.sources_seen(), ctx.adir, I.hidden_terms(ctx.full, ctx.inputs))}
