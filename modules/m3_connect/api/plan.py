"""M3-P04 routes: the risks to accept, the phased plan, the signatures, the outcome for module 4, and Nira's one sentence.
Declared in manifest.yaml and sh_platform/route_permissions.yaml under "M3-P04 plan". The company and the person come from the server session,
never from a body. A signed assessment refuses every write through api/signed_guard.py (applied to the whole router in api/__init__.py)."""
import functools
import logging
from datetime import datetime, timezone

from fastapi import Body, Request

from modules.m3_connect.agent import plan_lens
from modules.m3_connect.api import intake as intake_api
from modules.m3_connect.api.assessment import _plane, _viewer, guarded as scaffold_guarded, plain
from modules.m3_connect.api.signed_guard import GuardedRouter, is_signed
from modules.m3_connect.domain import accept as X
from modules.m3_connect.domain import counters as K
from modules.m3_connect.domain import from_profile as FP
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain.plan import PlanError
from modules.m3_connect.domain.steps import steps_for
from modules.m3_connect.store import assessment as A
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = GuardedRouter()  # a signed assessment answers 409 in the screens' own shape (api/signed_guard.py)
BASE = "/assessments/{assessment_id}"
_STATUS = {"invalid": 422, "bad_value": 400, "unreadable": 500, "restricted": 403}  # every other code is a 409
NOT_FOUND = "We could not find that assessment, risk or plan item."
WAITING = "Lens drafts the plan once the findings are in."
NOT_SIGNED = "The plan is not signed yet, so there is no record for the build."


def guarded(fn):
    """The scaffold's plain-words guard, plus this package's refusals (409 and friends) and "not found"."""
    inner = scaffold_guarded(fn)

    @functools.wraps(fn)
    def outer(*args, **kwargs):
        try:
            return inner(*args, **kwargs)
        except PlanError as e:
            return plain(_STATUS.get(e.code, 409), e.code, e.message)
        except LookupError:
            return plain(404, "not_found", NOT_FOUND)
    return outer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _me(request: Request) -> tuple[str, str]:
    acct = request.app.state.account_store.get(request.state.account_id)
    if not acct or acct.get("company_id") != request.state.company_id or not str(acct.get("display_name") or "").strip():
        raise PlanError("no_account", "We could not confirm who you are. Please sign in again.")
    return acct["account_id"], str(acct["display_name"])


def _model(request: Request, plane):
    """The model client for this company, or None (no key set up, or a setting is wrong). Tests plug a stub into app.state.lens_model_factory."""
    st = request.app.state
    factory = getattr(st, "lens_model_factory", None)
    override = getattr(st, "model_env", None)
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


class Ctx:
    """Everything one request needs: the assessment, the plan inputs, and what this viewer may see."""

    def __init__(self, request: Request, assessment_id: str):
        self.request, self.plane = request, _plane(request)
        a = A.read_assessment(self.plane, assessment_id)
        if a is None:
            raise LookupError("no assessment")
        self.a, self.dir, self.viewer = a, A.folder(self.plane, assessment_id), _viewer(request)
        baseline = I.read_baseline_outcome(self.plane, a["baseline_outcome_id"])
        empty = {"measures": [], "pain_points": []}
        everyone = I.Viewer("", frozenset())  # sees no restricted measure: the names that are safe to store
        full = I.read_inputs(self.plane, baseline, a["charter_outcome_id"], everyone) if baseline else empty
        mine = I.read_inputs(self.plane, baseline, a["charter_outcome_id"], self.viewer) if baseline else empty
        self.inputs = P.inputs_for_plan(self.dir)
        # one rule: a measure fed by a source that is shut is a restricted measure. The shared records (draft, outcome) use the closed view, the same
        # for everyone; what a viewer is shown also hides what the sources shut for that viewer feed
        self.restricted = {m["id"] for m in full["measures"] if m["restricted"]} | FP.fed_by(self.inputs["findings"], FP.closed_sources(self.dir, self.plane))
        self.safe_names = {m["id"]: m["name"] for m in full["measures"] if m["id"] not in self.restricted} | {x["kpi_id"]: x["name"] for x in full.get("left_out", [])}
        self.names = {m["id"]: m["name"] for m in mine["measures"]} | {x["kpi_id"]: x["name"] for x in mine.get("left_out", [])}
        shut = FP.shut_sources(self.dir, self.plane, intake_api._pv(request, self.viewer))
        self.hidden = {m["id"] for m in mine["measures"] if m["restricted"]} | FP.fed_by(self.inputs["findings"], shut)
        self.titles = {p["id"]: p["title"] for p in mine["pain_points"]}
        admin = I.read_inputs(self.plane, baseline, a["charter_outcome_id"], I.SYSTEM) if baseline else None
        self.terms = I.hidden_terms(admin, mine) if admin else []  # what this reader may not see by name: a risk text that names it is withheld
        self.baseline = baseline or {}
        self._owners(full)

    def _owners(self, full: dict) -> None:
        """LI-M3: a source with no owner on file gets its owners from the catalogue and module 2's measure owners, and their teams from the profile's
        people (the same view for everyone: the plan is shared), so an item is never "Team not named yet" while an owner is known. A source marked restricted is left alone."""
        teams = FP.people_teams(self.plane)
        for s in self.inputs["sources"].values():
            if not s["owners"] and "restricted" not in s["marks"]:
                s["owners"] = FP.source_owners(full, s["id"], [f["measure_id"] for f in self.inputs["findings"] if s["id"] in f["sources"]], teams)

    def risks(self) -> list[dict]:
        return X.with_decisions(self.inputs["risks"], X.read_decisions(self.dir))

    def draft(self, use_model: bool) -> dict:
        """Draft again from the findings, the sources and the decisions; every human edit stays (plan.merge)."""
        old = X.read_plan(self.dir)
        states = {r["id"]: r["state"] for r in self.risks()}
        items = P.draft(self.inputs, self.restricted, states)
        kept = {i["key"]: i["summary"] for i in (old or {}).get("items") or []}
        if use_model:
            st, company = self.request.app.state, self.request.state.company_id
            info = st.entitlements.company(company) or {}
            model = _model(self.request, self.plane)
            if model is not None:
                owners = [o["name"] for s in self.inputs["sources"].values() for o in s["owners"]]
                plan_lens.register_names(self.plane, str(info.get("name") or ""), [self.viewer.name, *owners])
            items = plan_lens.word_items(model, st.entitlements, company, company_name=str(info.get("name") or ""), industry=str(info.get("industry") or ""),
                                         items=items, names=self.safe_names, recorder=RunRegistry(self.plane) if model is not None else None)
        else:
            items = [{**i, "summary": (None if i["restricted"] else kept.get(i["key"])) or P.fallback_summary(i, self.safe_names)} for i in items]
        return X.draft_plan(self.dir, items, _now(), self.a["id"])


def _left_out_view(ctx: Ctx) -> list[dict]:
    """"Left out in module 2", once: the measures module 2 left out, with their reasons. One a viewer may not see is only "A restricted measure"."""
    return [{"measure": x["measure_id"], "name": P.RESTRICTED_NAME, "reason": None, "restricted": True} if x["measure_id"] in ctx.hidden
            else {"measure": x["measure_id"], "name": x.get("name"), "reason": I.mask_text(x.get("reason"), ctx.terms), "restricted": bool(x.get("restricted"))}
            for x in ctx.inputs.get("left_out") or []]


def _risk_view(r: dict, ctx: Ctx) -> dict:
    if set(r["measures"]) & ctx.hidden:
        return {"id": r["id"], "kind": r["kind"], "text": P.RESTRICTED_NAME, "restricted": True, "measures": [], "pain_points": [], "state": r["state"],
                "decision": None, "accepted_in_module_2": None}
    d = r["decision"] or {}
    return {"id": r["id"], "kind": r["kind"], "text": I.mask_text(r["text"], ctx.terms), "restricted": False, "state": r["state"],
            "accepted_in_module_2": {k: r["accepted_in_module_2"].get(k) for k in ("by", "at")} if r.get("accepted_in_module_2") else None,
            "measures": [{"id": m, "name": ctx.names.get(m, m)} for m in r["measures"]],
            "pain_points": [{"id": p, "title": ctx.titles.get(p, p)} for p in r["pain_points"]],
            "decision": {"decision": d.get("decision") or d.get("state"), "note": d.get("note"), "reason": d.get("reason"), "by": d.get("by"), "at": d.get("at")} if d else None}


def _risks_answer(ctx: Ctx, extra: dict | None = None) -> dict:
    risks = ctx.risks()
    plan = X.read_plan(ctx.dir)
    count = lambda s: len([r for r in risks if r["state"] == s])  # noqa: E731
    out_of_sight = [r for r in risks if set(r["measures"]) & ctx.hidden and not P.is_decided(r["state"])]
    return {"risks": [_risk_view(r, ctx) for r in risks], "notes": X.known_notes([r for r in risks if not set(r["measures"]) & ctx.hidden]),
            "restricted_note": X.restricted_note(len(out_of_sight)), "counts": {"open": count("open"), "sent_back": count("sent_back"), "accepted": count("accepted"),
                                                                    "rechecked": count("rechecked")},
            "signed": bool(plan and plan["signed_at"]), "locked": bool(plan and plan["signatures"]), "ready": ctx.inputs["ready"], **(extra or {})}


def _plan_answer(ctx: Ctx, plan: dict | None) -> dict:
    c = P.contract()
    risks = ctx.risks()
    undecided = [r for r in risks if not P.is_decided(r["state"])]
    sigs = (plan or {}).get("signatures") or []
    acct_id, who = _me(ctx.request)
    slot = None if any(s.get("account_id") == acct_id for s in sigs) or (plan or {}).get("signed_at") else X.slot_for(
        set(ctx.request.state.roles or []), {s["slot"] for s in sigs})
    return {"drafted": plan is not None, "waiting": None if ctx.inputs["ready"] else WAITING, "bands_info": c["bands"],
            "bands": P.band_view((plan or {}).get("items") or [], ctx.names, ctx.hidden, ctx.titles), "left_out": _left_out_view(ctx),
            "drafted_at": (plan or {}).get("drafted_at"), "signed_at": (plan or {}).get("signed_at"), "outcome_id": (plan or {}).get("outcome_id") if (plan or {}).get("signed_at") else None,
            "signatures": [{k: s.get(k) for k in ("slot", "label", "name", "at", "restricted_covered", "note")} for s in sigs],
            "waiting_for": [s["label"] for s in c["countersign"] if s["slot"] not in {x["slot"] for x in sigs}],
            "risks_undecided": len(undecided), "can_sign": bool(plan) and not undecided, "restricted_hidden": len(ctx.hidden),
            "effort": {k: v["label"] for k, v in c["effort"].items()},
            "viewer": {"name": who, "slot": slot, "can_edit": not sigs}}


@router.get(BASE + "/plan")
@guarded
def get_plan(request: Request, assessment_id: str) -> dict:
    ctx = Ctx(request, assessment_id)
    plan = X.read_plan(ctx.dir)
    if plan is None and ctx.inputs["ready"] and not is_signed(ctx.plane, assessment_id):  # a signed assessment is never written to, not even by a GET
        plan = ctx.draft(use_model=True)  # the first draft is automatic
    return _plan_answer(ctx, plan)


@router.post(BASE + "/plan/draft")
@guarded
def draft_again(request: Request, assessment_id: str) -> dict:
    ctx = Ctx(request, assessment_id)
    if not ctx.inputs["ready"]:
        raise PlanError("no_findings", WAITING)
    return _plan_answer(ctx, ctx.draft(use_model=True))


@router.put(BASE + "/plan/item")
@guarded
def edit_item(request: Request, assessment_id: str, body: dict = Body(...)) -> dict:
    """A person's change to one item (band, effort, team, date, covered by), with a reason."""
    ctx = Ctx(request, assessment_id)
    acct_id, who = _me(request)
    key = body.get("key")
    shown = next((i for i in (X.read_plan(ctx.dir) or {}).get("items") or [] if i["key"] == key), None)
    if shown is None:
        raise LookupError("no item")
    if set(shown["measures"]) & ctx.hidden:
        raise PlanError("restricted", "This item is about a restricted measure that you may not see, so it cannot be changed from here.")
    now = _now()
    plan = X.change_plan(ctx.dir, lambda p: {**p, "items": P.edit_item(p["items"], key, body, body.get("reason"), who, acct_id, now)}, now)
    K.bump(ctx.dir, "edit_plan_item", free_text=bool(str(body.get("reason") or "").strip()))
    return _plan_answer(ctx, plan)


@router.get(BASE + "/risks")
@guarded
def get_risks(request: Request, assessment_id: str) -> dict:
    return _risks_answer(Ctx(request, assessment_id))


def _after_decision(ctx: Ctx) -> None:
    """A decision can move a restricted item out of Later: draft again, without the model (the wording already there is kept)."""
    if X.read_plan(ctx.dir) is not None:
        ctx.draft(use_model=False)


@router.post(BASE + "/risks/accept-all")
@guarded
def accept_all(request: Request, assessment_id: str, body: dict = Body(default={})) -> dict:
    """Accept every risk nobody decided yet, in one action; each still gets its own record."""
    ctx = Ctx(request, assessment_id)
    acct_id, who = _me(request)
    got = X.decide_all(ctx.dir, ctx.risks(), body.get("note"), who, acct_id, _now(), ctx.hidden)
    ctx.inputs = P.inputs_for_plan(ctx.dir)
    K.bump(ctx.dir, "accept_all_risks", free_text=bool(str(body.get("note") or "").strip()))
    _after_decision(ctx)
    return _risks_answer(ctx, got)


@router.post(BASE + "/risks/{risk_id}/decision")
@guarded
def decide(request: Request, assessment_id: str, risk_id: str, body: dict = Body(...)) -> dict:
    """Accept one risk (a note is optional) or send it back (a reason is required)."""
    ctx = Ctx(request, assessment_id)
    acct_id, who = _me(request)
    found = R.read_file(ctx.dir, "findings.json", {})
    risk_id = F.real_id(ctx.dir, found, risk_id) or risk_id  # a client that was shown an opaque id (P03 for_viewer) lands on the real risk
    X.decide(ctx.dir, ctx.risks(), risk_id, body.get("decision"), body.get("reason") if body.get("decision") == "sent_back" else body.get("note"),
             who, acct_id, _now(), ctx.hidden)
    K.bump(ctx.dir, "decide_risk", free_text=bool(str(body.get("reason") if body.get("decision") == "sent_back" else body.get("note") or "").strip()))
    _after_decision(ctx)
    return _risks_answer(ctx)


@router.post(BASE + "/plan/sign")
@guarded
def sign(request: Request, assessment_id: str) -> dict:
    """The sponsor signs, then the head of data. The second signature writes the outcome record for module 4."""
    ctx = Ctx(request, assessment_id)
    acct_id, who = _me(request)
    facts = {"names": ctx.safe_names, "restricted": sorted(ctx.restricted), "baseline_outcome_id": ctx.a["baseline_outcome_id"],
             "charter_outcome_id": ctx.a["charter_outcome_id"]}
    plan = X.sign(ctx.dir, who, acct_id, set(request.state.roles or []), _now(), len(ctx.hidden), facts)
    K.bump(ctx.dir, "sign_plan")
    if plan.get("signed_at"):  # the second signature finishes the gap report: a map update moment
        from sh_platform.graph.knowledge_map import try_moment
        try_moment(ctx.plane, "gap_report_signed", assessment_id, who)
    return _plan_answer(ctx, plan)


@router.get(BASE + "/next")
@guarded
def next_step(request: Request, assessment_id: str) -> dict:
    """Nira's one sentence for the stage the assessment is really in: signed (it ends there), else the first step in progress, else the first
    not started; what it waits for and on whom comes from the steps registry."""
    ctx = Ctx(request, assessment_id)
    if is_signed(ctx.plane, assessment_id):
        return {"step": None, "done": True, "sentence": X.SIGNED_SENTENCE}
    steps = steps_for(ctx.dir)
    waiting = next((s for s in steps if s["state"] == "in_progress"), None) or next((s for s in steps if s["state"] != "done"), None)
    if waiting is None:
        return {"step": None, "done": True, "sentence": "Every step is done."}
    return {"step": waiting["id"], "done": False, "sentence": waiting["waiting_on"]}


@router.get(BASE + "/outcome")
@guarded
def outcome(request: Request, assessment_id: str):
    """The read-only record module 4 reads, once both have signed."""
    ctx = Ctx(request, assessment_id)
    plan = X.read_plan(ctx.dir)
    if not (plan and plan["signed_at"]):
        return plain(404, "not_signed", NOT_SIGNED)
    record = X._read(X.outcomes_dir(ctx.dir) / f"{plan['outcome_id']}.json")
    if record is None:
        raise PlanError("unreadable", X.UNREADABLE)
    return record
