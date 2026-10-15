"""Module 2, M2-AGENTS: Lens's own block (what it did, what it proposes, what it needs, the redraft and the conversation),
the pre-read checklist, and Nira, the guide. Every route is declared in manifest.yaml and sh_platform/route_permissions.yaml
(same roles as lens/draft). Lens's only actions are the ones it already had: draft or redraft a definition and keep a draft as
a proposal. Everything here shows a person only the measures they may see (Ctx.sees), the same rule as the work list."""
import re

from fastapi import APIRouter, Body, Request

from modules.m2_baseline.agent import lens
from modules.m2_baseline.agent import nira
from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.api.worklist import (NOT_YOURS, PACK_AUTHOR, Ctx, Forbidden, _notes, _pack_definition, _place, _problems,
                                              _restricted_titles, _suggestions, _view, guarded, plain)
from modules.m2_baseline.domain import lens_view as LV
from modules.m2_baseline.domain import preread as PR
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import requests as R
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.triage import ROLES, charter_facts, missing_owners
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.store import technical as ST
from modules.m2_baseline.store.process_map import MapUnreadable, ProcessMapStore
from modules.m2_baseline.store.requests import RequestStore, StoreError
from sh_platform.agents.runs import RunRegistry
from sh_platform.consume.feeds import build as feeds_build
from sh_platform.graph.read import graph_for
from sh_platform.profile.api import _viewer
from sh_platform.context_docs.store import DocStore
from sh_platform.memory.summarise import background, remember_for_account

router = APIRouter(route_class=SignedGuard)
MAX_INSTRUCTION = 300
MAX_QUESTION = 600
_COMMAND = re.compile(r"^\s*(?:please\s+)?(?:make|change|redraft|rewrite|reword|update|edit|shorten|set)\b", re.IGNORECASE)
REDRAFT_NOTES = {"no_model": "Lens cannot redraft this because no model is set up for your company.",
                 "unreachable": "Lens could not reach the model just now, so the wording is unchanged. Please try again.",
                 "no_change": "Lens could not make that change from what it has, so the wording is unchanged.",
                 "kept_yours": "Your own wording is kept. Lens's new draft is beside it for you to use or ignore."}


def _docs(ctx: Ctx) -> list[dict]:
    """The company's documents the asker may see: a restricted one is listed to the company admin alone (as the Company context page does)."""
    try:
        docs = [d for d in DocStore(ctx.plane).documents(lens.DOCUMENT_AGENT) if ctx.organiser or not d.get("restricted")]
    except (OSError, ValueError):
        return []
    if ctx.organiser:
        return docs
    try:
        held = PR.review(ctx.plane, ctx.pack_parts())  # a document waiting for the organiser's personal-data decision is not listed to others
    except (OSError, ValueError):
        return []
    return [d for d in docs if d["doc_id"] not in held]


def _visible(ctx: Ctx, baseline_id: str) -> list[dict]:
    return [k for k in K.read_kpis(ctx.plane, baseline_id) if ctx.sees(k)]


# ---- Lens's block

def waiting_documents(ctx: Ctx) -> list[dict]:
    """The documents waiting for the organiser's decision, with the words found and the restrict route: for the organiser alone (she decides)."""
    if not ctx.organiser:
        return []
    held, scan = PR.review(ctx.plane, ctx.pack_parts()), _scans(ctx.plane)
    return [{"doc_id": d["doc_id"], "title": d["title"], "personal_words": (scan.get(d["doc_id"]) or {}).get("words", [])[:6],
             "restrict_path": f"/api/agents/{lens.DOCUMENT_AGENT}/docs/{d['doc_id']}/visibility"}
            for d in _docs(ctx) if d["doc_id"] in held and not d.get("restricted")]


def lens_state(ctx: Ctx, base: dict) -> dict:
    kpis, charter = _visible(ctx, base["id"]), (B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None)
    titles = {p["id"]: p["title"] for p in (charter or {}).get("problems", [])}
    sug = _suggestions(ctx, base, charter, K.read_kpis(ctx.plane, base["id"]))
    store, locked = LS.read(ctx.plane, base["id"]), base["state"] == "signed"
    ids = [k["id"] for k in kpis] + [s["id"] for s in sug]
    attempts = {i: ("unreachable" if LS.is_stale(store, i) else store["attempts"][i]) for i in ids if i in store["attempts"]}  # a claim nobody finished is a failure
    drafting = [i for i, o in attempts.items() if o == "working"]  # another tab is drafting it now
    defined = lambda i: ({k["id"]: k["definition"] for k in kpis} | {s["id"]: s["definition"] for s in sug}).get(i)  # noqa: E731
    names = {k["id"]: k["name"] for k in kpis} | {s["id"]: s["name"] for s in sug}
    filled = sum(1 for i in ids if (d := defined(i)) and d.get("mark") != "unknown" and d.get("value"))
    unsure = [(names[i], o) for i, o in attempts.items() if o in ("nothing", "unreachable", "no_model") and not (defined(i) or {}).get("value")]
    failed = [i for i, o in attempts.items() if o == "unreachable"]
    asking = LV.asks(kpis, set(attempts), store["drafts"])
    docs = [d for d in _docs(ctx) if not d.get("restricted")]
    return {"available": ctx.model() is not None, "locked": locked, "technical": technical_state(ctx, base, kpis, store, locked), "pack": {"available": ctx.guidance.has_content, "label": ctx.guidance.label},
            "pending": [] if locked else [i for i in ids if i not in attempts], "waiting": waiting_documents(ctx), "failed": failed, "drafting": drafting, "documents": len(docs), "people": ctx.people(),
            "refine": LV.refine_items(kpis, sug, titles, ctx.guidance.pack.suggestion_label), "asks": asking,
            "say": LV.sentences(pack_available=ctx.guidance.has_content, label=ctx.guidance.label, problems=len(titles), suggested=len(sug), measures=len(kpis),
                                drafted=filled, pending=0 if locked else sum(1 for i in ids if i not in attempts) + len(drafting), failed=len(failed),
                                nothing=sum(1 for _, o in unsure if o == "nothing"), available=ctx.model() is not None, locked=locked,
                                asking=asking[0]["text"] if asking else None, documents=len(docs), unsure=unsure)}


def technical_state(ctx: Ctx, base: dict, kpis: list[dict], store: dict, locked: bool) -> dict:
    """M2-E1: how far Lens is with the technical definitions and the open questions, for the measures this person may see only: counts of
    records, never a name. `pending` are the measures it has not tried yet (the block drafts them one at a time)."""
    try:
        items = SA.listing(ctx.plane, base["id"], ctx.viewer(), ctx.sees)
    except (ST.S.StoreError, ST.C.CatalogueError, OSError, ValueError):
        items = []
    open_n = sum(1 for a in items if a["status"] == "open")
    drafted = sum(1 for k in kpis if any(T.present(c) for c in T.parts_of(k).values()))
    tried = lambda k: store["attempts"].get(f"tech:{k['id']}")  # noqa: E731
    pending = [] if locked else [k["id"] for k in kpis if tried(k) is None or LS.is_stale(store, f"tech:{k['id']}")]
    say = (f"I drafted the technical definition for {drafted} of {len(kpis)} measure{'s' if len(kpis) != 1 else ''}. "
           f"{open_n} open question{'s' if open_n != 1 else ''} need{'s' if open_n == 1 else ''} a person.") if kpis else ""
    return {"drafted": drafted, "measures": len(kpis), "open": open_n, "pending": pending, "failed": [k["id"] for k in kpis if tried(k) == "unreachable"], "say": say}


@router.get("/baselines/{baseline_id}/lens")
@guarded
def get_lens(request: Request, baseline_id: str) -> dict:
    ctx = Ctx(request)
    return lens_state(ctx, ctx.baseline(baseline_id))


def redraft_one(ctx: Ctx, base: dict, item: dict, instruction: str, *, is_kpi: bool) -> str:
    """Lens redrafts one definition as asked. A person's wording is never overwritten: the draft goes beside it as a proposal.
    A suggestion's draft is kept for the suggestion. Returns the outcome: redrafted, kept_yours, no_model, unreachable, no_change."""
    model, g = ctx.model(), ctx.guidance
    if model is None:
        return "no_model"
    current = ((item["definition"] if is_kpi else item.get("definition")) or {}).get("value") or ""
    passages, sources = ctx.read_documents(P.retrieval_query(g, item["id"], item["name"], [p["title"] for p in _problems(ctx, base, item)]),
                                           restricted_ok=is_kpi and item["governance"]["personal"] == "yes")
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""), [ctx.name])
    try:
        text = lens.draft_definition(model, ctx.request.app.state.entitlements, ctx.request.state.company_id, company_name=str(ctx.company.get("name") or ""),
                                     industry=g.label, kpi_name=item["name"], pack=P.pack_text(g, item["id"]) if P.kpi_by_id(g, item["id"]) else "",
                                     documents=passages, recorder=RunRegistry(ctx.plane), instruction=instruction, current=current)
    except lens.ModelUnreachable:
        return "unreachable"
    if not text:
        return "no_change"
    draft = prov(text, "guessed", "Lens", ", ".join(sources) or "your instruction")
    if is_kpi and item["governance"]["personal"] == "yes" and any(t in _restricted_titles(ctx.plane) for t in sources):
        draft["restricted"] = True  # drawn from a restricted document: cleared for good when the measure is relaxed
    if not is_kpi:
        LS.record(ctx.plane, base["id"], item["id"], "redrafted", {"definition": draft})
        return "redrafted"
    d = item["definition"]
    K.change(ctx.plane, base["id"], item["id"], lambda k: _place(k, draft))
    return "kept_yours" if d["mark"] != "unknown" and d["by"] not in (lens.AGENT_NAME, PACK_AUTHOR) else "redrafted"


def _target(ctx: Ctx, base: dict, item_id) -> tuple[dict, bool]:
    k = next((k for k in K.read_kpis(ctx.plane, base["id"]) if k["id"] == item_id), None)
    if k is not None:
        if not ctx.sees(k):
            raise Forbidden(NOT_YOURS)
        return k, True
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    s = next((s for s in _suggestions(ctx, base, charter, K.read_kpis(ctx.plane, base["id"])) if s["id"] == item_id), None)
    if s is None:
        raise LookupError("no such measure")
    return s, False


@router.post("/baselines/{baseline_id}/lens/redraft")
@guarded
def lens_redraft(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """"Tell Lens what to change": body {kpi_id, instruction}. kpi_id is a measure on the list or one of Lens's suggestions."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    instruction = W.text_of(body.get("instruction"), "what to change", MAX_INSTRUCTION)
    item, is_kpi = _target(ctx, base, body.get("kpi_id"))
    outcome = redraft_one(ctx, base, item, instruction, is_kpi=is_kpi)
    return {**_view(ctx, base), "outcome": outcome, **({"lens_note": REDRAFT_NOTES[outcome]} if outcome in REDRAFT_NOTES else {})}


# ---- the conversation

def _num(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _figure_lines(ctx: Ctx) -> list[str]:
    """One line per measure the asker may see (feeds.build honours the governed access list): latest period and value, the previous value,
    the change, whether it is outside its usual range, and the pipeline that feeds it. A measure with no figure gets none."""
    try:
        viewer = _viewer(ctx.request)
        g, feeds = graph_for(ctx.plane, viewer), feeds_build(ctx.plane, viewer)["measures"]
    except (OSError, ValueError, PermissionError) as exc:
        return []
    label = {n["id"]: n["label"] for n in g["nodes"]}
    out = []
    for m in feeds:
        t = m.get("trend") or []
        if not m.get("may_see") or not t:
            continue
        pipes = [label[e["to"]] for e in g["edges"] if e["from"] == f"measure:{m['code']}" and e["type"] == "built_by" and e["to"] in label]
        line = f"Figures for {m['name']} ({m['code']}), recorded in the warehouse: latest period {t[-1]['period']}, value {_num(t[-1]['value'])}"
        if len(t) > 1:
            d = t[-1]["value"] - t[-2]["value"]
            line += f"; previous period {t[-2]['period']}, value {_num(t[-2]['value'])}; {'up' if d >= 0 else 'down'} by {_num(abs(d))} on the previous period"
        line += ("; this is outside its usual range" if m.get("range_break") else "; this is within its usual range") + (f". Fed by pipeline {', '.join(pipes)}." if pipes else ".")
        out.append(line)
    return out


def lens_facts(ctx: Ctx, base: dict) -> str:
    """Everything Lens may rely on in a conversation, as plain sentences: only what the asker may see (a restricted measure is
    not mentioned at all), and every number a count of records."""
    kpis, charter = _visible(ctx, base["id"]), (B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None)
    all_kpis = K.read_kpis(ctx.plane, base["id"])
    sug = _suggestions(ctx, base, charter, all_kpis)
    g, said = ctx.guidance, lambda p: "unknown" if p["mark"] == "unknown" else f"{p['value']} ({p['mark']}, by {p['by']}{', from ' + p['from'] if p['from'] else ''})"  # noqa: E731
    out = [("Industry pack: " + g.label + ". Its measures are what others in the industry usually track (a suggestion, never the company's policy).")
           if g.has_content else "No industry knowledge is held for this company, so nothing is suggested from industry practice."]
    out.append(f"The baseline is {'signed and read-only' if base['state'] == 'signed' else 'not signed yet'}. {len(kpis)} measures you may see are on the list; {len(sug)} are suggested.")
    for p in (charter or {}).get("problems", []):
        mine = [k["name"] for k in kpis if p["id"] in k["problem_ids"]]
        theirs = [s["name"] for s in sug if p["id"] in s["problem_ids"]]
        out.append(f"Charter problem: {p['title']} (priority {p.get('priority') or 'not set'}). On the list for it: {', '.join(mine) or 'none'}. "
                   f"Suggested for it from the industry pack, not yet on the list: {', '.join(theirs) or 'none'}.")
    out += charter_facts(charter)
    try:  # M2-E1: only what this person may see (rows they may not see are not named, a part that names one is left out)
        viewer = ctx.viewer()
        shown, _ = ST.catalogue_for(ctx.plane, base["id"], viewer)
        names, hidden, items = T.row_names(shown), ST.hidden_terms(ctx.plane, base["id"], viewer, ctx.sees), SA.listing(ctx.plane, base["id"], viewer, ctx.sees)
    except (ST.S.StoreError, ST.C.CatalogueError, OSError, ValueError):
        names, hidden, items = {}, [], []
    for k in kpis:
        shown_parts = [p for p in T.view_parts(k, names, hidden) if T.present(p["cell"])]
        mine = [a for a in items if a["kpi_id"] == k["id"] and a["status"] == "open"]
        out.append(f"Technical definition of {k['name']}: " + (" ".join(f"{p['label']}: {'; '.join(l['name'] for l in p['links']) if p['links'] else T.text_of(p['cell'])}." for p in shown_parts) or "none yet.")
                   + f" {len(mine)} open questions" + (": " + " ".join(f"({a['kind']}) {a['question']}" for a in mine[:5]) if mine else "") + ".")
        o = {r: (k["owners"][r]["value"] or "not named") for r in ROLES}
        out.append(f"Measure {k['name']}: definition {said(k['definition'])}. Business owner {o['business']}, data owner {o['data']}, process owner {o['process']}. "
                   f"Who produces the data: {said(k.get('producer'))}. How it is gathered: {said(k.get('gathered'))}. "
                   f"{sum(1 for q in k.get('questions') or [] if (q.get('answer') or {}).get('mark') == 'unknown')} questions are open. "
                   + (f"Lens's newer draft beside the person's wording: {k['definition_proposal']['value']}." if k.get("definition_proposal") else ""))
    out += _figure_lines(ctx)
    for s in sug:
        d = s.get("definition")
        out.append(f"Suggested measure {s['name']}: draft definition {said(d) if d else 'none yet'}.")
    # recorded figures lead, so the budget trims the older definition facts from the tail, never the figures
    figs = [f for f in out if f.startswith("Figures for ")]
    head = "\n".join(figs)
    return (head + "\n" + "\n".join(f for f in out if f not in figs)[:max(0, 7000 - len(head) - 1)]).strip()


def _mentioned(question: str, ctx: Ctx, base: dict) -> list[tuple[dict, bool]]:
    """The measures or suggestions the question names (longest names first, one only when one fits)."""
    charter = B.read_charter(ctx.plane, base["charter_outcome_id"]) if base["charter_outcome_id"] else None
    pool = [(k, True) for k in _visible(ctx, base["id"])] + [(s, False) for s in _suggestions(ctx, base, charter, K.read_kpis(ctx.plane, base["id"]))]
    low = question.casefold()
    hits = [(i, k) for i, k in pool if i["name"].casefold() in low]
    longest = max((len(i["name"]) for i, _ in hits), default=0)
    return [(i, k) for i, k in hits if len(i["name"]) == longest]


@router.post("/baselines/{baseline_id}/lens/ask")
@guarded
def lens_ask(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)) -> dict:
    """The person types to Lens. "Make the definition of X about Y" redrafts X (the same redraft as the button); anything else is
    answered from recorded facts. Open on a signed baseline: only the redraft is refused there."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    question = W.text_of(body.get("question"), "your question", MAX_QUESTION)
    said = {"name": lens.AGENT_NAME, "role": "the business analyst", "changed": False}
    hit = _mentioned(question, ctx, base)
    if _COMMAND.match(question) and len(hit) == 1:
        item, is_kpi = hit[0]
        if base["state"] == "signed":
            return {**said, "available": True, "text": "This baseline is signed, so I cannot change that definition. I can still explain it."}
        outcome = redraft_one(ctx, base, item, question, is_kpi=is_kpi)
        text = (f"I redrafted the definition of “{item['name']}”. Please check it and use it, edit it or tell me what else to change."
                if outcome == "redrafted" else REDRAFT_NOTES.get(outcome, ""))
        return {**said, "available": outcome != "no_model", "text": text, "changed": outcome in ("redrafted", "kept_yours")}
    model = ctx.model()
    if model is None:
        return {**said, "available": False, "text": lens.NO_MODEL_ASK}
    mine = _visible(ctx, baseline_id)
    names = [ctx.name, *(o["value"] for k in mine for o in k["owners"].values() if o["value"])]
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""), names)
    restricted_ok = any(i["name"].casefold() in question.casefold() and k and i["governance"]["personal"] == "yes" for i, k in hit)
    passages, _ = ctx.read_documents(question, restricted_ok=restricted_ok)
    try:
        text = lens.converse(model, request.app.state.entitlements, request.state.company_id, company_name=str(ctx.company.get("name") or ""),
                             industry=ctx.guidance.label, facts=lens_facts(ctx, base), documents=passages, question=question, recorder=RunRegistry(ctx.plane),
                             background=background(ctx.plane, "lens", request.state.account_id))
    except lens.ModelUnreachable:
        return {**said, "available": True, "text": "I could not reach the model just now. Please ask again in a moment."}
    if text:  # MEM-2: the ask box keeps no conversation on the server, so each answered exchange is its own conversation
        remember_for_account(ctx.plane, "lens", request.state.account_id, [f"Person: {question}", f"Lens: {text}"], model=model,
                             gate=request.app.state.entitlements, recorder=RunRegistry(ctx.plane), company_id=request.state.company_id,
                             module_id=lens.MODULE_ID, conversation=f"Lens, baseline {baseline_id}")
    return {**said, "available": True, "text": text or "I could not put an answer together from what is recorded. Tell me what you need and I will say what is missing."}


# ---- the pre-read checklist: a view over the company's own documents

def _scans(plane) -> dict:
    """The record of which documents mention personal data; a damaged file reads as empty (every document then waits, see domain/preread.py `review`)."""
    try:
        return LS.scans(plane)
    except B.StoreError:
        return {}


@router.get("/baselines/{baseline_id}/preread")
@guarded
def get_preread(request: Request, baseline_id: str) -> dict:
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    docs = _docs(ctx)
    held = PR.review(ctx.plane, ctx.pack_parts()) if ctx.organiser else set()  # a new upload is read for personal data; only the organiser is asked
    scan = _scans(ctx.plane)
    ask = lambda d: ({"personal_words": (scan.get(d["doc_id"]) or {}).get("words", [])[:6], "restrict_path": f"/api/agents/{lens.DOCUMENT_AGENT}/docs/{d['doc_id']}/visibility"}  # noqa: E731
                     if d["doc_id"] in held and not d.get("restricted") else {})
    return {"kinds": PR.view(LS.read(ctx.plane, baseline_id)["inputs"], docs),
            "documents": [{"doc_id": d["doc_id"], "title": d["title"], "restricted": bool(d.get("restricted")), **ask(d)} for d in docs],
            "can_upload": ctx.organiser, "pack": {"available": ctx.guidance.has_content, "label": ctx.guidance.label}}


@router.put("/baselines/{baseline_id}/preread/{kind}")
@guarded
def put_preread(request: Request, baseline_id: str, kind: str, body: dict = Body(default_factory=dict)) -> dict:
    """Tag documents as one kind of input, or say "we do not have this". The documents are uploaded on the Company context page's route."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    docs, none = PR.checked(kind, body, {d["doc_id"] for d in _docs(ctx)})
    LS.set_input(ctx.plane, baseline_id, kind, docs, none)
    return get_preread(request, baseline_id)


@router.post("/baselines/{baseline_id}/preread/documents/{doc_id}/not-personal")
@guarded
def not_personal(request: Request, baseline_id: str, doc_id: str) -> dict:
    """"This document does not hold personal data": Lens may read it for every measure. The other answer, "Mark it restricted", is the Company
    context page's own restrict route (the screen calls it). Only the company admin decides, as on that page."""
    ctx = Ctx(request)
    ctx.baseline(baseline_id)
    if not ctx.organiser:
        raise Forbidden("Only the company admin can decide whether a document is personal data.")
    PR.clear(ctx.plane, doc_id)
    return get_preread(request, baseline_id)


# ---- Nira, the guide

def nira_state(ctx: Ctx, base: dict, step: str) -> dict:
    kpis = _visible(ctx, base["id"])
    seen = {k["id"] for k in kpis}
    try:
        reqs = [r for r in RequestStore(ctx.plane, base["id"]).all() if set(r["kpi_ids"]) <= seen]  # nobody tied to a measure the asker cannot see
    except (StoreError, OSError, ValueError):
        reqs = []
    try:
        mapped = sum(1 for kid in ProcessMapStore(ctx.plane, base["id"]).maps() if kid in seen)
    except (MapUnreadable, ValueError):
        mapped = 0
    return {"step": step, "signed": base["state"] == "signed", "measures": len(kpis),
            "owners_complete": sum(1 for k in kpis if not missing_owners(k)), "definitions": sum(1 for k in kpis if k["definition"]["mark"] != "unknown"),
            "open_questions": sum(1 for k in kpis for q in k["questions"] if q["answer"]["mark"] == "unknown"),
            "held": len(waiting_documents(ctx)), "requests": len(reqs), "answered": sum(1 for r in reqs if r["state"] == "answered"),
            "waiting": list(dict.fromkeys(r["owner_name"] for r in reqs if r["state"] in R.OPEN_STATES)), "mapped": mapped}


@router.post("/baselines/{baseline_id}/nira")
@guarded
def ask_nira(request: Request, baseline_id: str, body: dict = Body(default_factory=dict)):
    """body: kind (welcome, now, ask), step (which screen), question (for ask). Welcome and now are fixed messages from the state."""
    ctx = Ctx(request)
    base = ctx.baseline(baseline_id)
    kind, step = body.get("kind"), body.get("step") if body.get("step") in nira.STEPS else "baselines"
    if kind not in nira.KINDS:
        return plain(422, "invalid", "Please choose what you want to ask Nira.")
    cfg, state = nira.load_rules(), nira_state(ctx, base, step)
    said = {"name": cfg["name"], "role": cfg["role"], "facts": nira.lines(state, cfg)}
    if kind != "ask":
        return {**said, "available": True, "text": nira.say(kind, state, cfg)}
    question = W.text_of(body.get("question"), "your question for Nira", MAX_QUESTION)
    st = request.app.state
    factory = getattr(st, "nira_model_factory", None)
    model = factory(ctx.plane) if factory else ctx.model()
    if model is None:
        return {**said, "available": False, "text": cfg["unavailable"]}
    lens.register_names(ctx.plane, str(ctx.company.get("name") or ""), [ctx.name, *state["waiting"]])
    text = nira.ask_nira(model, st.entitlements, RunRegistry(ctx.plane), request.state.company_id, str(ctx.company.get("name") or ""),
                         ctx.guidance.label or "this company", state=state, question=question, cfg=cfg)
    return {**said, "available": True, "text": text}
