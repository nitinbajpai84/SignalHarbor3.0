"""M2-E1 routes: the technical definition of a measure and the open questions (ambiguities) of a baseline. Declared in manifest.yaml and
sh_platform/route_permissions.yaml; every write is refused on a signed baseline by SignedGuard.

The company and the person come from the server session. A measure the person may not see answers like one that does not exist; a part
or question that names a row or measure they may not see is left out or withheld (store/technical.py, store/ambiguities.py).
"""
import functools
import re

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.agent import lens
from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.api.catalogue import _viewer
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.api.worklist import Ctx, Forbidden, _problems, _restricted_titles, guarded, plain
from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import readiness as RD
from modules.m2_baseline.domain import requests as R
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.questionnaire import load_questionnaire
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import catalogue as SC
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.store import technical as ST
from modules.m2_baseline.store.requests import OwnerIndex, RequestStore
from sh_platform.agents.runs import RunRegistry

router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}"
MAX_INSTRUCTION = 300
ONLY_GOVERNORS = "Only the organiser or the sponsor can accept a question as a known risk."
ONLY_DATA_OWNER = "Only the data owner named for this measure can confirm its technical definition."
NO_DATA_OWNER = "No data owner is named for this measure yet. Name one on the work list first."
TECH_ASK = " Include the steps in order, the source, the fields and the period."


def answers(fn):
    """The module's plain answers, plus this package's own refusals."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (A.Refused, T.Refused) as e:
            return plain(422, "invalid", str(e))
        except W.Invalid as e:
            return plain(400, "invalid", str(e))
        except Forbidden as e:  # a rule about who may do this: the sentence says which, so it has its own code (the client shows "forbidden" as a generic refusal)
            return plain(403, "not_allowed", str(e))
    return guarded(inner)


def _tid(kpi_id: str) -> str:
    return f"tech:{kpi_id}"


# ---- reading

def _kpi_state(k: dict, names: dict, hidden: list[str], visible_open: int, derived_all: int) -> dict:
    """One measure for one person. The gate (`ready`, the label) is computed over EVERY open question, so it is the same for everyone; the reasons
    are the ones this person may see, plus a plain "Something restricted is still open" when something they may not see is also open."""
    ok, why = RD.ready_to_build(k, derived_all)
    total = RD.open_total(k, derived_all)
    return {**ST.definition_view(k, names, hidden), "open": visible_open,
            "ready": {"ready": ok, "reasons": RD.reasons_for_viewer(why, total, visible_open), "label": RD.open_label(k, derived_all)}}


def screen(ctx: Ctx, baseline_id: str) -> dict:
    """What the technical-definition and open-questions screens draw from, for this person only."""
    base = ctx.baseline(baseline_id)
    viewer = _viewer(ctx.request)
    shown, _ = ST.catalogue_for(ctx.plane, baseline_id, viewer)
    names, hidden = T.row_names(shown), ST.hidden_terms(ctx.plane, baseline_id, viewer, ctx.sees)
    items = SA.listing(ctx.plane, baseline_id, viewer, ctx.sees)
    open_by: dict[str, int] = {}
    for a in items:
        if a["status"] == "open" and a["kpi_id"]:
            open_by[a["kpi_id"]] = open_by.get(a["kpi_id"], 0) + 1
    derived_all = SA.derived_open_all(ctx.plane, baseline_id)
    kpis = [k for k in ST.read_with_notes(ctx.plane, baseline_id) if ctx.sees(k)]
    out = [_kpi_state(k, names, hidden, open_by.get(k["id"], 0), derived_all.get(k["id"], 0)) for k in kpis]
    return {"baseline_id": baseline_id, "signed": base["state"] == "signed", "lens_available": ctx.model() is not None, "kpis": out,
            "ambiguities": items, "counts": SA.counts(items),
            "summary": {"measures": len(kpis), "drafted": sum(1 for o in out if any(T.present(p["cell"]) for p in o["parts"])),
                        "ready": sum(1 for o in out if o["ready"]["ready"]), "open": sum(1 for a in items if a["status"] == "open")}}


@router.get(BASE + "/technical")
@answers
def get_technical(request: Request, baseline_id: str):
    return screen(Ctx(request), baseline_id)


@router.get(BASE + "/ambiguities")
@answers
def get_ambiguities(request: Request, baseline_id: str):
    s = screen(Ctx(request), baseline_id)
    return {k: s[k] for k in ("baseline_id", "signed", "ambiguities", "counts")}


# ---- a person: edit, use the draft, confirm

@router.put(BASE + "/kpis/{kpi_id}/technical")
@answers
def put_part(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    """body: part, value (text, or a list of catalogue row ids for sources, tables, fields), mark (stated, guessed or unknown)."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    ST.edit(ctx.plane, baseline_id, kpi_id, str(body.get("part") or ""), body.get("value"), str(body.get("mark") or "stated"), ctx.name, _viewer(request), ctx.sees)
    return screen(ctx, baseline_id)


@router.post(BASE + "/kpis/{kpi_id}/technical/use")
@answers
def use_part(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    ST.use(ctx.plane, baseline_id, kpi_id, str(body.get("part") or ""), ctx.name, _viewer(request), ctx.sees)
    return screen(ctx, baseline_id)


def _data_owner(ctx: Ctx, k: dict) -> bool:
    return ST.is_data_owner(k, ctx.account_id, ctx.is_named)


@router.get(BASE + "/my-technical")
@answers
def my_technical(request: Request, baseline_id: str):
    """The technical definitions of the measures this person is the named data owner of, whatever their role (like /my-parts): exactly these,
    matched by account id, and nothing else of the baseline."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    viewer = _viewer(request)
    shown, _ = ST.catalogue_for(ctx.plane, baseline_id, viewer)
    names, hidden = T.row_names(shown), ST.hidden_terms(ctx.plane, baseline_id, viewer, ctx.sees)
    mine = [k for k in ST.read_with_notes(ctx.plane, baseline_id) if ctx.sees(k) and _data_owner(ctx, k)]
    return {"baseline_id": baseline_id, "signed": base["state"] == "signed", "kpis": [ST.definition_view(k, names, hidden) for k in mine]}


@router.post(BASE + "/kpis/{kpi_id}/technical/confirm")
@answers
def confirm_part(request: Request, baseline_id: str, kpi_id: str):
    """The data owner confirms the technical definition as it is now (any role: the route admits the named person, this checks who they are)."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    k = ctx.kpi(baseline_id, kpi_id)
    owner = (k["owners"].get("data") or {})
    if owner.get("mark") == "unknown" or not owner.get("value"):
        raise Forbidden(NO_DATA_OWNER)
    if not _data_owner(ctx, k):
        raise Forbidden(ONLY_DATA_OWNER)
    ST.confirm(ctx.plane, baseline_id, kpi_id, ctx.name, ctx.sees)
    return screen(ctx, baseline_id)


@router.post(BASE + "/measures/{kpi_id}/send-back")
@answers
def send_back(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(default_factory=dict)):
    """body: note. The note is kept beside the technical definition and shows on its data owner's list as "Sent back: <note>"."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    ST.send_back(ctx.plane, baseline_id, kpi_id, body.get("note"), ctx.name, ctx.sees)
    return screen(ctx, baseline_id)


# ---- Lens drafts it

def _job(ctx: Ctx, base: dict, model, k: dict, shown: dict, secret_titles: list[str]) -> tuple[dict, str]:
    """What Lens makes of one measure: ({parts: provenance values, ambiguities: [...]}, outcome). Code checks always run; the model is called only
    when there is something to read (a passage, a catalogue row or the pack) and then ONCE for the parts and the contradictions."""
    g, kid, name = ctx.guidance, k["id"], k["name"]
    restricted_ok = k["governance"]["personal"] == "yes"
    feed = T.feeding(shown, kid)
    lines = T.catalogue_lines(feed)
    titles = [p["title"] for p in _problems(ctx, base, k)]
    passages, docs = ctx.read_documents(P.retrieval_query(g, kid, name, titles) + " source table columns steps formula period currency", restricted_ok=restricted_ok)
    pack = P.pack_text(g, kid) if P.kpi_by_id(g, kid) else ""
    secret = restricted_ok and any(t in secret_titles for t in docs)  # drawn from a restricted document: flagged for good
    reply, outcome = {"parts": {}, "missing": "", "conflicts": [], "catalogue": {}}, "nothing"
    if passages or lines or pack:
        if model is None:
            outcome = "no_model"
        else:
            try:
                text = lens.draft_technical(model, ctx.request.app.state.entitlements, ctx.request.state.company_id, company_name=str(ctx.company.get("name") or ""),
                                            industry=g.label, kpi_name=name, definition=T.text_of(k.get("definition")), pack=pack, catalogue=lines, documents=passages,
                                            recorder=RunRegistry(ctx.plane))
                reply = T.parse_reply(text, T.feeding_ids(feed)) if text else reply
                outcome = "drafted" if reply["parts"] or any(reply["catalogue"].values()) else "nothing"
            except lens.ModelUnreachable:
                outcome = "unreachable"
    came = [*docs, *(["the catalogue"] if lines else []), *([f"{g.label} industry pack (suggestion)"] if pack and not docs else [])]
    parts = T.drafted_parts(reply, came)
    raised = T.code_ambiguities(T.merge_draft(k, parts), passages, docs, feed)  # on the measure WITH this draft, so a part just drafted is not asked for
    if secret:
        parts = {p: ({**c, "restricted": True} if c.get("mark") != "unknown" else c) for p, c in parts.items()}
    ids = {C.row_id(t, r) for t in C.TABS for r in shown[t]}  # the ids come from the catalogue rows themselves, never from a pattern
    for kind, where, text, question, suggestion in reply["conflicts"]:
        said = {w.lower() for w in re.findall(r"[A-Za-z0-9_-]+", " ".join((text, question, where)))}
        refs = [{"id": i} for i in sorted(ids) if i.lower() in said]
        raised.append(A.make(kind, text, question, T.finding_key(name, kind, where, text), None, refs=refs,
                             suggestion={"value": suggestion, "mark": "guessed", "by": "Lens"} if suggestion else None))
    raised = [{**a, "basis": list(docs)} for a in raised] if docs else raised
    if secret:
        raised = [{**a, "restricted": True} for a in raised]
    return {"parts": parts, "ambiguities": A.fresh([], raised), "secret": secret, "title": ", ".join(docs), "restricted": W.treated_as_personal(k["governance"]) or bool(k["governance"].get("sensitive")),
            "proposals": T.anchored(reply["catalogue"], passages) if docs else {}}, outcome


def _with_rows(plane, baseline_id: str, k: dict, made: dict) -> dict:
    """Lens builds the catalogue rows the technical notes name and the catalogue lacks (guessed, with the document's title, for a person to accept
    there) and the measure's sources, tables and fields link them by id. The links are Lens's draft like any other part."""
    if not made.get("proposals"):
        return made
    try:
        ids = SC.propose_rows(plane, baseline_id, made["proposals"], k["id"], made["title"] or "the technical notes", made["restricted"], k["governance"].get("may_see"))
    except (C.CatalogueError, SC.StoreError):
        return made  # nothing was saved, so there is nothing to link
    parts, came = dict(made["parts"]), f"{made['title'] or 'the technical notes'} (rows Lens proposed, for a person to accept in the catalogue)"
    for part in T.LINKS:
        if ids[part]:
            have = parts[part].get("value") if parts[part].get("mark") != "unknown" else []
            parts[part] = {**prov(list(dict.fromkeys([*(have or []), *ids[part]])), "guessed", T.LENS, came), **({"restricted": True} if made["secret"] else {})}
    return {**made, "parts": parts}


def draft_technical_items(ctx: Ctx, base: dict, kpis: list[dict], retry: bool = False) -> dict:
    """Lens drafts the technical definition and raises the open questions for each measure, two calls at a time, and records what happened to each
    ("tech:<id>": drafted, nothing, no_model, unreachable). A claim is taken before any model call, as for definitions. A person's part is never
    overwritten (the draft waits beside it); a question already raised (even settled) is not raised again. Returns {kpi id: outcome}."""
    claimed = set(LS.claim(ctx.plane, base["id"], [_tid(k["id"]) for k in kpis], retry))
    kpis = [k for k in kpis if _tid(k["id"]) in claimed]
    if not kpis:
        return {}
    model = ctx.model()
    viewer = _viewer(ctx.request)
    shown, _ = ST.catalogue_for(ctx.plane, base["id"], viewer)
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""),
                        [ctx.name, *(o["value"] for k in kpis for o in k["owners"].values() if o["value"]), *(n for k in kpis for n in k["governance"]["may_see"])],
                        [C.text_of(s.get("Source name")) for s in shown["sources"]])
    secret, outcomes, done = _restricted_titles(ctx.plane), {}, set()
    try:
        for k, (made, outcome) in zip(kpis, lens.run_in_order(lambda k: _job(ctx, base, model, k, shown, secret), kpis)):
            outcomes[k["id"]] = outcome
            if outcome not in ("unreachable", "no_model"):
                made = _with_rows(ctx.plane, base["id"], k, made)
                K.change(ctx.plane, base["id"], k["id"], lambda x, m=made: A.with_ambiguities(T.merge_draft(x, m["parts"]), m["ambiguities"]))
            LS.record(ctx.plane, base["id"], _tid(k["id"]), outcome)
            done.add(_tid(k["id"]))
    finally:
        for i in claimed - done:
            LS.record(ctx.plane, base["id"], i, "unreachable")
    return outcomes


@router.post(BASE + "/lens/technical")
@answers
def lens_technical(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """Lens drafts the technical definition for the measures you can see (or the kpi_ids named). Marked guessed, with where it came from."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    want = body.get("kpi_ids")
    kpis = [k for k in K.read_kpis(ctx.plane, baseline_id) if ctx.sees(k) and (not isinstance(want, list) or k["id"] in want)]
    outcomes = draft_technical_items(ctx, base, kpis, retry=body.get("retry") is True)
    note = ("Lens could not reach the model just now; the code checks still ran." if "unreachable" in outcomes.values() else
            lens.NO_MODEL_NOTE if "no_model" in outcomes.values() else "")
    return {**screen(ctx, baseline_id), "outcomes": outcomes, **({"lens_note": note} if note else {})}


@router.post(BASE + "/lens/technical/redraft")
@answers
def lens_technical_redraft(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """"Tell Lens what to change": body {kpi_id, instruction}. A person's part stays; the new draft waits beside it."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    instruction = W.text_of(body.get("instruction"), "what to change", MAX_INSTRUCTION)
    k = ctx.kpi(baseline_id, str(body.get("kpi_id") or ""))
    model = ctx.model()
    if model is None:
        return {**screen(ctx, baseline_id), "outcome": "no_model", "lens_note": lens.NO_MODEL_NOTE}
    viewer = _viewer(request)
    shown, _ = ST.catalogue_for(ctx.plane, baseline_id, viewer)
    feed = T.feeding(shown, k["id"])
    g, titles = ctx.guidance, [p["title"] for p in _problems(ctx, base, k)]
    passages, docs = ctx.read_documents(P.retrieval_query(g, k["id"], k["name"], titles) + " source table columns steps formula", restricted_ok=k["governance"]["personal"] == "yes")
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""), [ctx.name], [C.text_of(s.get("Source name")) for s in shown["sources"]])
    cur = "\n".join(f"{T.LABELS[p]}: {T.text_of(c) if p not in T.LINKS else '; '.join(c.get('value') or [])}" for p, c in T.parts_of(k).items() if T.present(c))
    try:
        text = lens.draft_technical(model, request.app.state.entitlements, request.state.company_id, company_name=str(ctx.company.get("name") or ""), industry=g.label,
                                    kpi_name=k["name"], definition=T.text_of(k.get("definition")), pack=P.pack_text(g, k["id"]) if P.kpi_by_id(g, k["id"]) else "",
                                    catalogue=T.catalogue_lines(feed), documents=passages, recorder=RunRegistry(ctx.plane), instruction=instruction, current=cur)
    except lens.ModelUnreachable:
        return {**screen(ctx, baseline_id), "outcome": "unreachable", "lens_note": "Lens could not reach the model just now, so the wording is unchanged. Please try again."}
    reply = T.parse_reply(text, T.feeding_ids(feed)) if text else {"parts": {}, "missing": "", "conflicts": []}
    if not reply["parts"]:
        return {**screen(ctx, baseline_id), "outcome": "no_change", "lens_note": "Lens could not make that change from what it has, so the wording is unchanged."}
    drafted = {p: v for p, v in T.drafted_parts(reply, [*docs, "your instruction"]).items() if p in reply["parts"]}
    if k["governance"]["personal"] == "yes" and any(t in _restricted_titles(ctx.plane) for t in docs):
        drafted = {p: {**v, "restricted": True} for p, v in drafted.items()}
    K.change(ctx.plane, baseline_id, k["id"], lambda x: T.merge_draft(x, drafted))
    return {**screen(ctx, baseline_id), "outcome": "redrafted"}


# ---- the open questions: answer, ask the owner, accept as a known risk

@router.post(BASE + "/kpis/{kpi_id}/ambiguities/{amb_id}/answer")
@answers
def answer_item(request: Request, baseline_id: str, kpi_id: str, amb_id: str, body: dict = Body(default_factory=dict)):
    """A person writes the answer, which is recorded on the question. Only if they chose a part (`part`, with their own new `wording` for it) does a
    definition change, stated by them, with the old text kept; the bare answer never replaces a part."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    out = SA.answer(ctx.plane, baseline_id, kpi_id, amb_id, str(body.get("resolution") or ""), ctx.name, _viewer(request), ctx.sees,
                    body.get("part") or None, None if body.get("wording") is None else str(body.get("wording")))
    return {**screen(ctx, baseline_id), "changed": out["part"]}


@router.post(BASE + "/kpis/{kpi_id}/ambiguities/{amb_id}/accept")
@answers
def accept_item(request: Request, baseline_id: str, kpi_id: str, amb_id: str, body: dict = Body(default_factory=dict)):
    """"Accept as a known risk": only the organiser or the sponsor, with a reason."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    if not ctx.governor:
        raise Forbidden(ONLY_GOVERNORS)
    SA.accept(ctx.plane, baseline_id, kpi_id, amb_id, str(body.get("reason") or ""), ctx.name, _viewer(request), ctx.sees)
    return screen(ctx, baseline_id)


@router.post(BASE + "/kpis/{kpi_id}/ambiguities/{amb_id}/ask")
@answers
def ask_owner(request: Request, baseline_id: str, kpi_id: str, amb_id: str, body: dict = Body(default_factory=dict)):
    """"Ask the owner": the question joins that owner's request (the existing request mechanism), pre-filled for the email. A person with no
    request yet gets one; its link is returned here once, with the email text to copy."""
    from modules.m2_baseline.api.requests import _email, _full_link  # the existing request mechanism's own email and link (imported here: that file is a sibling router)
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    ctx.kpi(baseline_id, kpi_id)
    role = body.get("role") if body.get("role") in ("business", "data", "process") else None
    item, owner, question = SA.prepare_ask(ctx.plane, baseline_id, kpi_id, amb_id, _viewer(request), ctx.sees, role)
    role = role or A.role_of(item["kind"])
    store = RequestStore(ctx.plane, baseline_id)
    account = (ctx.kpi(baseline_id, kpi_id)["owners"].get(role) or {}).get("account_id")
    row, token = store.ask(OwnerIndex(request.app.state.settings.data_root), load_questionnaire(), owner, role, kpi_id, {"ambiguity_id": amb_id, "kpi_id": kpi_id, "text": question}, account)
    SA.mark_asked(ctx.plane, baseline_id, kpi_id, amb_id, owner, row["id"])
    seen = {k["id"] for k in K.read_kpis(ctx.plane, baseline_id) if ctx.sees(k)}  # the email names only measures the asker may see
    email = _email(store, row, ctx.name, R.email_text if token else R.reminder_text, link=_full_link(request, token) if token else None, only=seen)
    return {**screen(ctx, baseline_id), "asked": {"owner": owner, "email": email, "link_path": f"/answer/{token}" if token else None}}
