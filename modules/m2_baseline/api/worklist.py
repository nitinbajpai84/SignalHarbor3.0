"""Module 2, M2-P01: start a baseline from a signed charter, the KPI work list, triage, owners and governance.
Every route is declared in manifest.yaml. The company and the person come from the server session, never from a body.
Reshaped from the earlier webapp/backend/routers/baseline.py (draft / confirm / edit / answer, 52-110): a thin HTTP
wrapper over the domain and store; plain-words answers; a signed baseline refuses every change (409)."""
import functools
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.agent import lens
from modules.m2_baseline.api.governed import ensure_draft as ensure_governed_draft
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governance_view as GV
from modules.m2_baseline.domain import preread as PR
from modules.m2_baseline.domain import readiness as RD
from modules.m2_baseline.domain import triage as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import glossary as SG
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import technical as ST
from modules.m2_baseline.store.answers import read_answers
from modules.m2_baseline.store.requests import StoreError as AnswersUnreadable
from sh_platform.agents.runs import RunRegistry
from sh_platform.context_docs.store import DocStore
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)
ORGANISER_ROLE = "company_admin"
GOVERNOR_ROLES = (ORGANISER_ROLE, "sponsor")  # who may change who can see a measure
PACK_AUTHOR = "the pack"
PRIVATE_KEYS = ("ambiguities", "technical", "technical_proposal", "technical_confirmed", "technical_history")  # M2-E1: shown only through /technical and /ambiguities, filtered per viewer
NOT_YOURS = "You are not named to see this measure, so it cannot be changed from here."


class Forbidden(Exception):
    pass


def plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


_ANSWERS = ((W.Invalid, lambda e: plain(400, "invalid", str(e))),
            (B.Locked, lambda e: plain(409, "signed", str(e))),
            (FileExistsError, lambda e: plain(409, "exists", "That measure is already on the list.")),
            (LookupError, lambda e: plain(404, "not_found", "We could not find that.")),
            (Forbidden, lambda e: plain(403, "forbidden", str(e))),
            (B.StoreError, lambda e: plain(500, "unreadable", str(e))),
            ((PermissionError, CrossCompanyError), lambda e: plain(
                403, "forbidden", "Your company space could not be opened. Please ask your administrator.")))


def guarded(fn):
    """Route decorator: the module's failures become plain answers; nothing technical reaches the screen."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - re-raised below unless it is one of ours
            for kinds, answer in _ANSWERS:
                if isinstance(e, kinds):
                    return answer(e)
            raise
    return inner


class Ctx:
    """Who is asking and what they work with, all from the server session."""
    def __init__(self, request: Request):
        st = request.app.state
        try:
            self.plane = PlaneStore(st.settings.data_root).plane_for(request.state.company_id).ensure()
        except (LookupError, CrossCompanyError, ValueError):
            raise PermissionError("no company space") from None
        self.request = request
        acct = (st.account_store.get(request.state.account_id) if request.state.account_id is not None else None) or {}
        self.name = str(acct.get("display_name") or "")
        self.account_id = request.state.account_id
        self.organiser = ORGANISER_ROLE in (request.state.roles or [])
        self.governor = any(r in (request.state.roles or []) for r in GOVERNOR_ROLES)
        self.company = st.entitlements.company(request.state.company_id) or {}
        self.guidance = P.load_guidance(st.packs, self.company.get("industry"))

    def accounts_named(self, name: str) -> list[str]:
        """Ids of this company's accounts whose display name is `name`."""
        want = name.strip().casefold()
        return [a["account_id"] for a in self.request.app.state.account_store.in_company(self.request.state.company_id)
                if str(a.get("display_name") or "").strip().casefold() == want]

    def nominee_account(self, body) -> str | None:
        """The account a nominee with an account belongs to; None when they have none, or the name fits several accounts."""
        ids = self.accounts_named(str(body.get("name") or "")) if isinstance(body, dict) and body.get("has_account") else []
        return ids[0] if len(ids) == 1 else None

    def people(self) -> list[dict]:
        """The company's accounts, to pick an owner from: {account_id, display_name}. Nothing else about them."""
        return [{"account_id": a["account_id"], "display_name": a["display_name"]}
                for a in self.request.app.state.account_store.in_company(self.request.state.company_id) if not a.get("disabled")]

    def nomination(self, body) -> dict:
        """One nomination. A person picked from the company's accounts (`account_id`) is stored with that account; a name
        typed freely still works, for a person with no account."""
        picked = body.get("account_id") if isinstance(body, dict) else None
        if picked:
            who = next((p for p in self.people() if p["account_id"] == picked), None)
            if who is None:
                raise W.Invalid("That person is not one of your company's accounts. Please pick someone from the list.")
            return W.nominee({"name": who["display_name"], "has_account": True}, self.name, who["account_id"])
        return W.nominee(body, self.name, self.nominee_account(body))

    def is_named(self, name: str) -> bool:
        """Is the asker the person called `name`: by account when that name belongs to an account, else by name."""
        ids = self.accounts_named(name)
        return self.account_id in ids if ids else name.strip().casefold() == self.name.strip().casefold()

    def sees(self, kpi: dict) -> bool:
        return W.may_see(kpi, self.name, self.account_id, self.organiser)

    def viewer(self) -> C.Viewer:
        """The asker as the catalogue's rules see them (M2-E1: the technical definition and the open questions use the same filter as the catalogue)."""
        twins = [a for a in self.request.app.state.account_store.in_company(self.request.state.company_id)
                 if C.norm(a.get("display_name") or "") == C.norm(self.name)]
        return C.Viewer(self.name, frozenset(self.request.state.roles or []), len(twins) > 1, self.account_id)

    def pack_parts(self) -> dict:
        return GV.pack_parts(self.request.app.state.packs, str(self.company.get("industry", "")))

    def read_documents(self, query: str, restricted_ok: bool = False) -> tuple[str, list[str]]:
        """Lens's way into the company's documents (every module 2 retrieval): a document that mentions personal data and waits for the organiser's
        decision is not read for a measure not marked personal (domain/preread.py `read`)."""
        return PR.read(self.plane, self.pack_parts(), query, restricted_ok=restricted_ok)

    def baseline(self, baseline_id: str) -> dict:
        b = B.read_baseline(self.plane, baseline_id)
        if b is None:
            raise LookupError("no baseline")
        return b

    def kpi(self, baseline_id: str, kpi_id: str) -> dict:
        """One KPI the asker may see and change; a restricted one is refused (M2-05, enforced here, not in the page)."""
        k = next((k for k in K.read_kpis(self.plane, baseline_id) if k["id"] == kpi_id), None)
        if k is None:
            raise LookupError("no KPI")
        if not self.sees(k):
            raise Forbidden(NOT_YOURS)
        return k

    def model(self):
        """The model client for this company, or None (no key set up, or a setting is wrong)."""
        st = self.request.app.state
        factory = getattr(st, "lens_model_factory", None)  # tests plug a stub in here
        override = getattr(st, "model_env", None)  # tests set {}: the real .env holds keys and a test must never reach a live model
        try:
            return factory(self.plane) if factory else build_model_client(self.plane, dict(override) if override is not None else load_model_env())
        except ProviderError:
            log.warning("the model settings are not valid")
            return None


# ---- the view

def _kpi_view(k: dict, base: dict, ctx: Ctx, answers: list[dict] = (), derived: dict | None = None) -> dict:
    if not ctx.sees(k):
        return W.hidden(k, base["state"])
    d = (derived or {}).get(k["id"], 0)  # open governance questions, worked out from the catalogue
    k = W.with_answers(k, [a for a in answers if a.get("kpi_id") == k["id"]])
    gov = {n: v for n, v in k["governance"].items() if n != "may_see_accounts"}  # account ids stay on the server
    own = {n: v for n, v in k.items() if n not in PRIVATE_KEYS}  # the technical definition and the open questions have their own filtered routes
    return {**own, "governance": gov, "restricted": False, "state": W.state_of(k, base["state"]), "triage": T.triage(k),
            "missing_owners": T.missing_owners(k), "treated_as_personal": W.treated_as_personal(k["governance"]),
            "build": {"ready": RD.ready_to_build(k, d)[0], "label": RD.open_label(k, d)}}  # M2-E1: the pill on the list


def _governance_note(ctx: Ctx, kpis: list[dict]) -> str | None:
    """P4: while nobody is named to see a restricted measure, only the organiser sees it. Say so plainly."""
    n = sum(1 for k in kpis if (k["governance"]["sensitive"] or W.treated_as_personal(k["governance"])) and not k["governance"]["may_see"])
    if not n:
        return None
    if ctx.organiser:
        return f"{n} measure{'s are' if n != 1 else ' is'} visible only to you until you set who may see {'them' if n != 1 else 'it'}."
    return f"{n} measure{'s are' if n != 1 else ' is'} visible only to the organiser until they set who may see {'them' if n != 1 else 'it'}."


def _answers(ctx: Ctx, baseline_id: str) -> list[dict]:
    try:
        return read_answers(ctx.plane, baseline_id)
    except AnswersUnreadable:  # an unreadable answers file never stops the work list
        return []


def _derived_open(ctx: Ctx, baseline_id: str) -> dict[str, int]:
    """{measure id: open governance questions over EVERY row, not this person's view}: the ready-to-build gate is the same for everyone. {} when the
    catalogue cannot be read (that never stops the work list)."""
    try:
        return SA.derived_open_all(ctx.plane, baseline_id)
    except (ST.S.StoreError, ST.C.CatalogueError, B.StoreError, OSError, ValueError):
        return {}


def _view(ctx: Ctx, base: dict) -> dict:
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    kpis = K.read_kpis(ctx.plane, base["id"])
    answers = _answers(ctx, base["id"])
    derived = _derived_open(ctx, base["id"])
    mine = [k for k in kpis if ctx.sees(k)]  # counts never include a measure the asker cannot see
    problems = [{"id": p["id"], "title": p["title"], "priority": p.get("priority"), "kind": p.get("kind", "problem"),
                 "kpi_ids": [k["id"] for k in mine if p["id"] in k["problem_ids"]]} for p in (charter or {}).get("problems", [])]
    g = ctx.guidance
    return {"baseline": base,
            "charter": {"outcome_id": base["charter_outcome_id"], "signed_at": charter.get("signed_at")} if charter else None,
            "problems": [{**p, "has_kpi": bool(p["kpi_ids"])} for p in problems],
            "charter_groups": T.charter_groups(charter),
            "kpis": [_kpi_view(k, base, ctx, answers, derived) for k in kpis],
            "suggestions": _suggestions(ctx, base, charter, kpis),
            "suggestion_label": g.pack.suggestion_label,
            "pack": {"available": g.has_content, "label": g.label},
            "people": ctx.people(),
            "owners_complete": sum(1 for k in mine if not T.missing_owners(k)),
            "governance_note": _governance_note(ctx, kpis),
            "lens_available": ctx.model() is not None}


def _suggestions(ctx: Ctx, base: dict, charter, kpis: list[dict]) -> list[dict]:
    """What Lens suggests, each with its first draft: what Lens drafted from the documents, else the pack's own wording."""
    mine = LS.read(ctx.plane, base["id"])["drafts"]
    return [{**s, "definition": (mine.get(s["id"]) or {}).get("definition") or _pack_definition(ctx.guidance, s["id"])}
            for s in P.propose_kpis(ctx.guidance, (charter or {}).get("problems", []), {k["id"] for k in kpis})]


def _pack_definition(g: P.Guidance, kpi_id: str) -> dict | None:
    text = P.pack_definition(g, kpi_id) if P.kpi_by_id(g, kpi_id) else ""
    return prov(text, "guessed", PACK_AUTHOR, f"{g.label} industry pack (suggestion)") if text else None


# ---- start

@router.get("/baselines")
@guarded
def list_baselines(request: Request) -> dict:
    ctx = Ctx(request)
    named = {c["outcome_id"]: c for c in B.charters(ctx.plane)}  # R4 defect 9: each baseline says which charter it came from
    bs = [{**b, "kpi_count": sum(1 for k in K.read_kpis(ctx.plane, b["id"]) if ctx.sees(k)),
           "charter_title": (named.get(b["charter_outcome_id"]) or {}).get("title"),
           "charter_signed_at": (named.get(b["charter_outcome_id"]) or {}).get("signed_at")} for b in B.baselines(ctx.plane)]
    started = {b["charter_outcome_id"]: b["id"] for b in bs}
    return {"charters": [{**c, "baseline_id": started.get(c["outcome_id"])} for c in B.charters(ctx.plane)], "baselines": bs}


@router.post("/baselines")
@guarded
def start_baseline(request: Request, body: dict = Body(default_factory=dict)):
    ctx = Ctx(request)
    try:
        base, created = B.start(ctx.plane, body.get("charter_outcome_id"))
    except LookupError:
        return plain(404, "no_charter", "We could not find that signed charter. Please choose one from the list.")
    return JSONResponse(_view(ctx, base), status_code=201 if created else 200)


@router.get("/baselines/{baseline_id}")
@guarded
def get_baseline(request: Request, baseline_id: str) -> dict:
    ctx = Ctx(request)
    return _view(ctx, ctx.baseline(baseline_id))


# ---- the KPIs: a person confirms, adds or removes

@router.post("/baselines/{baseline_id}/kpis")
@guarded
def confirm_kpi(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """Confirm a suggestion (body: suggestion_id, the problems it serves) or add one by name. Either way a person did it."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    known = {p["id"]: p for p in (charter or {}).get("problems", [])}
    problem_ids = [i for i in body.get("problem_ids") or [] if i in known]
    pid, g = body.get("suggestion_id"), ctx.guidance
    if pid is not None:
        pk = P.kpi_by_id(g, pid)
        if pk is None:
            raise LookupError("no suggestion")
        if not problem_ids:  # confirming a suggestion links it to the charter problems it was suggested for
            problem_ids = [i for i, p in known.items() if any(k["id"] == pid for k in P.kpis_for_problem(g, p))]
        mine = LS.read(ctx.plane, baseline_id)["drafts"].get(pid) or {}  # what Lens drafted from the documents before the person said yes
        kpi = W.new_kpi(pid, pk["name"], problem_ids, known[problem_ids[0]].get("priority") if problem_ids else None,
                        mine.get("definition") or _pack_definition(g, pid), P.customer_questions(g, pid))
        kpi.update({f: mine[f] for f in ("producer", "gathered") if f in mine})  # guessed by Lens, with its source
    else:
        name = W.text_of(body.get("name"), "the name of the measure", W.MAX_NAME)
        kpi = W.new_kpi(W.new_id(), name, problem_ids, known[problem_ids[0]].get("priority") if problem_ids else None,
                        None, [P.formula_question(name)])
    K.add(ctx.plane, baseline_id, kpi)
    _forget_left_out(ctx, baseline_id, kpi["id"])  # added again: no status from an earlier measure of this id
    return JSONResponse(_view(ctx, base), status_code=201)


def _forget_left_out(ctx: Ctx, baseline_id: str, kpi_id: str) -> None:
    from modules.m2_baseline.store.signoff import SignoffStore  # imported here: that file imports this module's siblings
    SignoffStore(ctx.plane, contracts_dir=getattr(ctx.request.app.state, "m2_contracts_dir", None)).forget_left_out(baseline_id, ctx.name, kpi_id)


@router.delete("/baselines/{baseline_id}/kpis/{kpi_id}")
@guarded
def remove_kpi(request: Request, baseline_id: str, kpi_id: str):
    ctx = Ctx(request)
    ctx.kpi(baseline_id, kpi_id)
    K.remove(ctx.plane, baseline_id, kpi_id)
    _forget_left_out(ctx, baseline_id, kpi_id)
    return _view(ctx, ctx.baseline(baseline_id))


# ---- triage: definition, producer, how it is gathered (the owner is nominated below)

_TRIAGE_FIELDS = {"definition": "the definition", "producer": "who produces the data", "gathered": "how it is gathered"}


@router.put("/baselines/{baseline_id}/kpis/{kpi_id}/triage")
@guarded
def put_triage(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    """body: any of definition, producer, gathered, each {text, mark}. A person's wording is "stated" or "guessed", by them."""
    ctx = Ctx(request)
    ctx.kpi(baseline_id, kpi_id)
    new = {f: W.person_value(body[f], what, ctx.name, "triage") for f, what in _TRIAGE_FIELDS.items() if f in body}
    if not new:
        raise W.Invalid("Please give the definition, who produces the data, or how it is gathered.")
    K.change(ctx.plane, baseline_id, kpi_id, lambda k: {**k, **new, "definition_proposal": None if "definition" in new else k["definition_proposal"]})
    return _view(ctx, ctx.baseline(baseline_id))


@router.put("/baselines/{baseline_id}/kpis/{kpi_id}/questions/{question_id}")
@guarded
def answer_question(request: Request, baseline_id: str, kpi_id: str, question_id: str, body: dict = Body(default_factory=dict)):
    """The business answers a question Lens asked. Only a named person writes an answer (rule 4 of the earlier build)."""
    ctx = Ctx(request)
    k = ctx.kpi(baseline_id, kpi_id)
    if not any(q["id"] == question_id for q in k["questions"]):
        raise LookupError("no question")
    answer = W.person_value({"mark": "stated", "text": body.get("answer")}, "an answer", ctx.name, "answer to Lens's question")
    K.change(ctx.plane, baseline_id, kpi_id, lambda k: {**k, "questions": [
        {**q, "answer": answer} if q["id"] == question_id else q for q in k["questions"]]})
    return _view(ctx, ctx.baseline(baseline_id))


# ---- owners (M2-04) and governance (M2-05)

@router.put("/baselines/{baseline_id}/kpis/{kpi_id}/owners")
@guarded
def put_owners(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    """body: any of business, data, process, each {account_id} (a person picked from the company's accounts) or {name,
    has_account} (a name typed freely); an empty name withdraws the nomination. The
    same name may fill all three (one person working alone). Records who nominated."""
    ctx = Ctx(request)
    ctx.kpi(baseline_id, kpi_id)
    new = {r: ctx.nomination(body[r]) for r in T.ROLES if r in body}
    if not new:
        raise W.Invalid("Please name the business, data or process owner.")
    K.change(ctx.plane, baseline_id, kpi_id, lambda k: {**k, "owners": {**k["owners"], **new}})
    return _view(ctx, ctx.baseline(baseline_id))


@router.post("/baselines/{baseline_id}/kpis/{kpi_id}/owners/{role}/decline")
@guarded
def decline_owner(request: Request, baseline_id: str, kpi_id: str, role: str):
    """The nominated person (or the organiser for them) says no: the nomination returns to the organiser as "no owner"."""
    ctx = Ctx(request)
    k = ctx.kpi(baseline_id, kpi_id)
    if role not in T.ROLES:
        raise LookupError("no such role")
    owner = k["owners"][role]
    mine = ctx.account_id == owner["account_id"] if owner.get("account_id") else owner["value"] and ctx.is_named(owner["value"])
    if owner["value"] and not (ctx.organiser or mine):
        raise Forbidden("Only the person nominated, or the organiser, can decline a nomination.")
    K.change(ctx.plane, baseline_id, kpi_id, lambda k: {**k, "owners": {**k["owners"], role: W.declined(k["owners"][role])}})
    return _view(ctx, ctx.baseline(baseline_id))


@router.put("/baselines/{baseline_id}/kpis/{kpi_id}/governance")
@guarded
def put_governance(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    """body: any of personal (yes, no, not_sure), sensitive (true or false), may_see (names)."""
    ctx = Ctx(request)
    k = ctx.kpi(baseline_id, kpi_id)
    if isinstance(body, dict) and "may_see" in body and not ctx.governor:
        raise Forbidden("Only the company admin or the sponsor can change who may see a measure.")
    gov = W.governance(k["governance"], body, ctx.accounts_named)
    lowered = W.rank(gov) < W.rank(k["governance"])
    if lowered and not ctx.governor:  # lowering would show what Lens drew from a restricted document to everyone
        raise Forbidden("Only the company admin or the sponsor can make a measure less restricted.")
    gone = _restricted_titles(ctx.plane) if lowered else ()
    decided = {"by": ctx.name, "at": datetime.now(timezone.utc).isoformat()}  # M2-E3: who set it and when, for the governance view
    changed = lambda k: {**k, "governance": gov, "governance_decided": decided}  # noqa: E731
    K.change(ctx.plane, baseline_id, kpi_id, lambda k: _unmarked(changed(k), gone) if lowered else changed(k))
    if lowered:
        LS.clear_restricted(ctx.plane, baseline_id, kpi_id, gone)  # the likely owner Lens kept aside
    SG.refresh_governance(ctx.plane, baseline_id)  # the glossary entry follows
    return _view(ctx, ctx.baseline(baseline_id))


# ---- Lens drafts (M2-03) and the pre-read of the company's documents

@router.post("/baselines/{baseline_id}/lens/draft")
@guarded
def lens_draft(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """Lens drafts definitions for the KPIs you can see (or the ones named in kpi_ids). From the pack first; then, when
    the company has documents about the measure, from their passages (marked guessed, from the document's title). A
    definition a person stated is never overwritten: Lens's draft is kept beside it as a proposal."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    want, want_s = body.get("kpi_ids"), body.get("suggestion_ids")
    kpis = [k for k in K.read_kpis(ctx.plane, baseline_id)
            if ctx.sees(k) and (not isinstance(want, list) or k["id"] in want)]
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    taken = {k["id"] for k in K.read_kpis(ctx.plane, baseline_id)}
    suggestions = [s for s in P.propose_kpis(ctx.guidance, (charter or {}).get("problems", []), taken)
                   if isinstance(want_s, list) and s["id"] in want_s]  # suggestions only when asked for by id
    outcomes = draft_items(ctx, base, kpis, suggestions, retry=body.get("retry") is True)
    ensure_governed_draft(request, baseline_id)  # the governed state is drafted with the definitions, no one has to ask
    return {**_view(ctx, base), "outcomes": outcomes, **_notes(outcomes, {k["id"]: k["name"] for k in kpis} | {s["id"]: s["name"] for s in suggestions})}


def _notes(outcomes: dict, names: dict) -> dict:
    """The plain words for what did not work: {} when every draft came out; never silent (Part 0 of M2-AGENTS)."""
    said = [lens.LENS_NOTE] if "unreachable" in outcomes.values() else []
    said += [lens.NO_MODEL_NOTE] if "no_model" in outcomes.values() else []
    said += [lens.nothing_note([names[i] for i, o in outcomes.items() if o == "nothing"][:5])] if "nothing" in outcomes.values() else []
    return {"lens_note": " ".join(said)} if said else {}


def fill_one(ctx: Ctx, base: dict, model, item_id: str, name: str, titles: list[str], *, restricted_ok: bool, pack_first: bool = True) -> tuple[dict, str]:
    """What Lens can fill for one measure or suggestion: ({definition, producer, gathered, owner} as provenance values, outcome).
    The pack's wording first; then the company's own documents, with the model (marked guessed, from the document titles)."""
    g = ctx.guidance
    fields = {"definition": d} if pack_first and (d := _pack_definition(g, item_id)) else {}
    passages, sources = ctx.read_documents(P.retrieval_query(g, item_id, name, titles), restricted_ok=restricted_ok)  # pay and HR text only for a measure marked personal, which only its viewers see
    if not passages:
        return fields, "pack" if fields else "nothing"
    if model is None:
        return fields, "no_model"
    try:
        got = lens.draft_fields(model, ctx.request.app.state.entitlements, ctx.request.state.company_id, company_name=str(ctx.company.get("name") or ""),
                                industry=g.label, kpi_name=name, pack=P.pack_text(g, item_id) if P.kpi_by_id(g, item_id) else "",
                                documents=passages, recorder=RunRegistry(ctx.plane))
    except lens.ModelUnreachable:
        return fields, "unreachable"
    secret = restricted_ok and any(t in _restricted_titles(ctx.plane) for t in sources)  # drawn from a restricted document: flagged for good
    fields.update({f: {**prov(v, "guessed", "Lens", ", ".join(sources)), **({"restricted": True} if secret else {})} for f, v in got.items()})
    return fields, "documents" if got else ("pack" if fields else "nothing")


def draft_items(ctx: Ctx, base: dict, kpis: list[dict], suggestions: list[dict], retry: bool = False) -> dict:
    """Lens fills what it can for the measures on the list and for its suggestions, two calls at a time, and records what
    happened to each: {id: outcome}. A person's value is never overwritten (a draft beside it is a proposal); a suggestion's
    draft waits until a person confirms the measure."""
    claimed = set(LS.claim(ctx.plane, base["id"], [i["id"] for i in (*kpis, *suggestions)], retry))  # before any model call: a second tab skips these
    kpis, suggestions = [k for k in kpis if k["id"] in claimed], [s for s in suggestions if s["id"] in claimed]
    model = ctx.model() if kpis or suggestions else None
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""),
                        [ctx.name, *(o["value"] for k in kpis for o in k["owners"].values() if o["value"]), *(n for k in kpis for n in k["governance"]["may_see"])])
    titles = lambda s: [p["title"] for p in _problems(ctx, base, s)]  # noqa: E731
    jobs = [(k, titles(k), k["governance"]["personal"] == "yes", k["definition"]["mark"] == "unknown") for k in kpis] + \
           [(s, titles(s), False, True) for s in suggestions]  # a suggestion has no governance yet: never a restricted document
    outcomes, on_list, done = {}, {k["id"] for k in kpis}, set()
    try:
        results = lens.run_in_order(lambda j: fill_one(ctx, base, model, j[0]["id"], j[0]["name"], j[1], restricted_ok=j[2], pack_first=j[3]), jobs)
        for (item, _, _, _), (fields, outcome) in zip(jobs, results):
            outcomes[item["id"]] = outcome
            if item["id"] in on_list:
                def apply(k, f=fields):
                    k = _place(k, f["definition"]) if "definition" in f else k
                    return {**k, **{x: f[x] for x in ("producer", "gathered") if x in f and k[x]["mark"] == "unknown"}}
                if fields:
                    K.change(ctx.plane, base["id"], item["id"], apply)
                LS.record(ctx.plane, base["id"], item["id"], outcome, {"owner": fields["owner"]} if "owner" in fields else None)
            else:
                LS.record(ctx.plane, base["id"], item["id"], outcome, {f: v for f, v in fields.items() if v["by"] != PACK_AUTHOR} or None)
            done.add(item["id"])
    finally:
        for i in claimed - done:  # anything that raised: never leave a claim as "working"; the block then offers "Try again"
            LS.record(ctx.plane, base["id"], i, "unreachable")
    return outcomes


def _restricted_titles(plane) -> list[str]:
    try:
        return [str(d["title"]) for d in DocStore(plane).documents(lens.DOCUMENT_AGENT) if d.get("restricted")]
    except (OSError, ValueError):
        return []


def _unmarked(kpi: dict, titles) -> dict:
    """Everything Lens drew from a restricted document (definition, its proposal, producer, gathered) is cleared when the measure
    is made less restricted. Drafts carry `restricted: true` from the moment they are made, so this does not depend on the
    document still being restricted or still having its title; the title match covers drafts made before the flag existed."""
    out = ST.unmark_restricted(kpi, titles)  # M2-E1: the technical definition and open questions drawn from a restricted document
    drawn = lambda v: isinstance(v, dict) and v.get("by") == lens.AGENT_NAME and (v.get("restricted") or any(t in str(v.get("from") or "") for t in titles))  # noqa: E731
    for f in ("definition", "producer", "gathered"):
        if drawn(kpi[f]):
            out[f] = unknown(lens.AGENT_NAME, "cleared: drawn from a restricted document")
    if drawn(kpi.get("definition_proposal")):
        out["definition_proposal"] = None
    return out


def _problems(ctx: Ctx, base: dict, kpi: dict) -> list[dict]:
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    return [p for p in (charter or {}).get("problems", []) if p["id"] in kpi["problem_ids"]]


def _place(kpi: dict, draft: dict) -> dict:
    """A draft fills an unknown or an earlier draft of Lens or the pack; a definition a person touched (stated or
    guessed by a person) is never overwritten: the draft is only kept beside it as a proposal."""
    d = kpi["definition"]
    if d["mark"] != "unknown" and d["by"] not in (lens.AGENT_NAME, PACK_AUTHOR):
        return {**kpi, "definition_proposal": draft} if draft["value"] != d["value"] else kpi
    return {**kpi, "definition": draft}
