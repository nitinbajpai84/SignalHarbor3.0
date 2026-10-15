"""IC v2 card B16 (spec 29): the business glossary of an Initiative and the company's one definition per term.

The Initiative's terms stay in the m2_baseline glossary (`outcome.glossary.baseline_id` points at it); this file adds what the spec marks New:
the company term store `glossary/company-terms.json` with its proposals, the owner's "mine / not mine", accepting an ambiguity as a known risk
by a settler, the three-question cap (A-045, ruling 9) and `GET /api/intents/{id}/glossary-start` for the Initiative start check (spec 22).
Reuse: m2 `domain/glossary.py` (key, text_of, decide), `domain/ambiguities.py` (accept), `sh_platform/graph/versions.py` (append_version).
"""
import logging
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import glossary as G
from sh_platform.graph.versions import append_version
from sh_platform.intents import _plane, _viewer
from sh_platform.intents import store as S
from sh_platform.intents.processes import question_budget as shared_budget
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import view as pview

log = logging.getLogger(__name__)
router = APIRouter()

QUESTION_CAP = 3  # A-045: at most three open questions per person across Define (ruling 9)
MAX_TEXT = 2000
RESTRICTED = G.RESTRICTED_NAME
ANON = "an anonymous card"
SETTLER_ROLES = frozenset({"company_admin", "sponsor"})


class Refused(ValueError):
    """A plain-words refusal, shown to the person."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _words(text: object, what: str) -> str:
    t = " ".join(str(text or "").split())
    if not t:
        raise Refused(f"Please write {what}.")
    if len(t) > MAX_TEXT:
        raise Refused("That is too long. Please shorten it.")
    return t


# ---- the company term store: one record per term, one definition company-wide ----------------------------------------------

def _terms_path(plane: CompanyPlane):
    return plane.path("glossary", "company-terms.json")


def load_terms(plane: CompanyPlane) -> list[dict]:
    try:
        doc = read_json_strict(_terms_path(plane), dict)
    except (OSError, ValueError):
        log.warning("the company term store could not be read")
        raise Refused("The company's terms could not be read. Please tell your administrator.") from None
    return list((doc or {}).get("terms") or [])


def _save(plane: CompanyPlane, terms: list[dict]) -> None:
    write_json_atomic(_terms_path(plane), {"terms": terms})


def term_id_of(name: str) -> str:
    return G.key(name).replace(" ", "-")


def node_id(term_id: str) -> str:
    return f"term:{term_id}"


def find_term(terms: list[dict], name: str) -> dict | None:
    """By name, then by alias (the same comparison the glossary matcher uses)."""
    k = G.key(name)
    return next((t for t in terms if G.key(t["term"]) == k), None) or next(
        (t for t in terms if k in {G.key(a) for a in t.get("aliases") or []}), None)


def add_term(plane: CompanyPlane, term: str, definition: str, owner: str | None, by: str, intent_id: str,
             aliases: list[str] | None = None, restricted: bool = False) -> tuple[dict, str]:
    """(the company term, "created" | "reused" | "proposed"). A term the company already holds is never duplicated: the same wording is
    reused; a different wording becomes a proposal on it, a version only when its owner confirms."""
    name, wording = _words(term, "the term")[:G.MAX_TERM], _words(definition, "the definition")
    with lock_for(_terms_path(plane)):
        terms = load_terms(plane)
        have = find_term(terms, name)
        if have:
            if G.key(have["definition"]) == G.key(wording):
                return have, "reused"
            propose(plane, have["term_id"], wording, "A different wording was found in this Initiative.", by, intent_id)
            return find_term(load_terms(plane), name) or have, "proposed"
        row = {"term_id": term_id_of(name), "term": name, "aliases": list(aliases or []), "definition": wording, "owner": owner,
               "state": "confirmed", "restricted": restricted, "created_from": intent_id, "confirmed_by": by, "confirmed_at": _now(),
               "proposals": []}
        _save(plane, terms + [row])
    append_version(plane, node_id(row["term_id"]), "First confirmed", by, intent_id)
    return row, "created"


def _edit(plane: CompanyPlane, term_id: str, change) -> dict:
    with lock_for(_terms_path(plane)):
        terms = load_terms(plane)
        i = next((n for n, t in enumerate(terms) if t["term_id"] == term_id), None)
        if i is None:
            raise LookupError(term_id)
        terms[i] = change(dict(terms[i]))
        _save(plane, terms)
        return terms[i]


def propose(plane: CompanyPlane, term_id: str, wording: str, reason: str, by: str, intent_id: str | None) -> dict:
    p = {"id": "prop-" + secrets.token_hex(4), "wording": _words(wording, "the new wording"), "reason": _words(reason, "why it should change"),
         "by": by, "at": _now(), "intent_id": intent_id, "status": "pending"}
    _edit(plane, term_id, lambda t: {**t, "proposals": [*(t.get("proposals") or []), p]})
    return p


def may_settle_term(term: dict, viewer: pview.Viewer, governance_lead: bool) -> bool:
    """The term's owner confirms; the governance lead does when the term has no owner (spec 29 rules, Open question 6)."""
    if term.get("owner"):
        return not viewer.shared_name and pview.norm(term["owner"]) == pview.norm(viewer.name)
    return governance_lead


def decide_proposal(plane: CompanyPlane, term_id: str, prop_id: str, confirm: bool, viewer: pview.Viewer, governance_lead: bool = False) -> dict:
    """Confirm (the wording becomes the company definition and a version is added, ref the proposing intent) or decline."""
    t = find_by_id(load_terms(plane), term_id)
    if t is None:
        raise LookupError(term_id)
    if not may_settle_term(t, viewer, governance_lead):
        raise Refused("Only the owner of this term can decide on a change.")
    p = next((x for x in t.get("proposals") or [] if x["id"] == prop_id and x["status"] == "pending"), None)
    if p is None:
        raise Refused("This proposal has already been decided.")
    at, status = _now(), "confirmed" if confirm else "declined"

    def go(term: dict) -> dict:
        props = [{**x, "status": status, "decided_by": viewer.name, "decided_at": at} if x["id"] == prop_id else x for x in term["proposals"]]
        if not confirm:
            return {**term, "proposals": props}
        return {**term, "proposals": props, "definition": p["wording"], "confirmed_by": viewer.name, "confirmed_at": at}

    out = _edit(plane, term_id, go)
    if confirm:
        append_version(plane, node_id(term_id), f"Definition changed: {p['reason']}", viewer.name, p.get("intent_id") or "")
    return out


def find_by_id(terms: list[dict], term_id: str) -> dict | None:
    return next((t for t in terms if t["term_id"] == term_id), None)


# ---- terms found in cards (Lens's deterministic pass: known terms by name and alias) -------------------------------------------

def _hits(text: str, names: list[str]) -> bool:
    k = f" {G.key(text)} "
    return any(G.key(n) and f" {G.key(n)} " in k for n in names)


def terms_in_cards(cards: list[dict], candidates: list[dict]) -> list[dict]:
    """[{term, sources}] for each candidate term ({term, aliases}) a card uses. A sealed or anonymous card is never quoted or numbered."""
    out = []
    for c in candidates:
        names = [c["term"], *(c.get("aliases") or [])]
        src = [ANON if (card.get("anonymous") or card.get("sealed")) else
               f"Card {card.get('n') or card.get('id')}" + (f" ({card['lane']})" if card.get("lane") else "")
               for card in cards if _hits(str(card.get("text") or ""), names)]
        if src:
            out.append({"term": c["term"], "sources": src})
    return out


# ---- the owner: mine or not mine (sign-off ownership, A-044b) ---------------------------------------------------------------

def holds(entry: dict, viewer: pview.Viewer) -> bool:
    """A name-only owner holds the term only when no other account shares the name (A-043, A-044b)."""
    return not viewer.shared_name and bool(G.text_of(entry.get("owner"))) and pview.norm(G.text_of(entry["owner"])) == pview.norm(viewer.name)


def owner_reply(entry: dict, viewer: pview.Viewer, mine: bool, sponsor: str | None = None, new_owner: str | None = None,
                wording: str | None = None, at: str | None = None) -> dict:
    """"Mine, wording is right" / "Mine, change the wording" confirm the entry; "Not mine, it is X" releases the owner cell and withdraws
    the confirmation, unless the sponsor named this owner: then nothing changes and the person is told to ask the sponsor."""
    if not holds(entry, viewer):
        raise Refused("Only the owner of this term can answer for it.")
    at = at or G.now()
    if mine:
        try:
            return G.decide(entry, "edited", wording, viewer.name, at) if wording else G.decide(entry, "ours", "", viewer.name, at)
        except G.Refused as e:
            raise Refused(str(e)) from None
    if sponsor and pview.norm((entry.get("owner") or {}).get("by")) == pview.norm(sponsor):
        raise Refused(f"Ask the sponsor, {sponsor}.")
    cell = {"value": new_owner, "mark": "stated", "by": viewer.name, "from": "not mine", "at": at} if new_owner else \
        {"value": None, "mark": "unknown", "by": viewer.name, "from": "no owner", "at": at}
    return {**entry, "owner": cell, "reviewed": None}


# ---- the governance lead: accept an ambiguity as a known risk ---------------------------------------------------------------

def may_settle(viewer: pview.Viewer, governance_lead: str | None) -> bool:
    """Only the governance lead, the sponsor or the company admin settle or accept (spec 29 rules)."""
    return bool(viewer.roles & SETTLER_ROLES) or bool(governance_lead and viewer.account_id == governance_lead)


def accept_as_risk(kpi: dict, amb_id: str, reason: str, viewer: pview.Viewer, governance_lead: str | None = None) -> dict:
    if not may_settle(viewer, governance_lead):
        raise Refused("Only the governance lead, the sponsor or the company admin can accept this as a known risk.")
    try:
        return A.accept(kpi, amb_id, reason, viewer.name)
    except A.Refused as e:
        raise Refused(str(e)) from None


def ready(entries: list[dict], ambiguities: list[dict]) -> bool:
    """Ready for the build-ready check: no term draft, no ambiguity open; one accepted as a known risk counts as ready."""
    return bool(entries) and all(e.get("reviewed") for e in entries) and A.open_count(ambiguities) == 0


# ---- the three-question cap (A-045, ruling 9) -------------------------------------------------------------------------------
# B14's `question_budget` (processes.py) is the shared cap: it counts the open questions in every `intents/<id>/*.json`. The glossary's
# own questions live in `outcome.glossary.questions_asked` (spec 29 fields), so they are taken off what B14 says is free.

def question_budget(plane: CompanyPlane, rec: dict, account_id: str | None, name: str) -> int:
    asked = int((((rec.get("outcome") or {}).get("glossary") or {}).get("questions_asked") or {}).get(account_id or "") or 0)
    return max(0, shared_budget(plane, rec["id"], name)["free"] - asked)


def ask(plane: CompanyPlane, rec: dict, owner_account: str | None, owner_name: str) -> str:
    """Who gets the question: "owner" (counted in outcome.glossary.questions_asked; the caller writes the record) or "governance_lead"
    when the owner's three across Define are used."""
    if not owner_account or question_budget(plane, rec, owner_account, owner_name) == 0:
        return "governance_lead"
    g = rec.setdefault("outcome", {}).setdefault("glossary", {})
    q = g.setdefault("questions_asked", {})
    q[owner_account] = int(q.get(owner_account) or 0) + 1
    return "owner"


# ---- glossary-start: company terms that look related to the Initiative (spec 22, Q4) -----------------------------------------

_STOP = {"the", "and", "for", "of", "to", "a", "an", "in", "on", "our", "we", "is", "with", "by", "at", "from", "how", "what", "why"}


def _stems(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(w) > 2 and w not in _STOP}


def start_terms(terms: list[dict], rec: dict, viewer: pview.Viewer) -> list[dict]:
    """Company terms whose name, aliases or definition share words with the title, purpose and areas. A restricted term reads
    "A restricted measure" without id to anyone but the company admin."""
    want = _stems(" ".join([rec.get("title") or "", rec.get("purpose") or "", *(rec.get("areas") or [])]))
    out = []
    for t in terms:
        if not want & _stems(" ".join([t["term"], *(t.get("aliases") or []), t.get("definition") or ""])):
            continue
        if t.get("restricted") and pview.ADMIN not in viewer.roles:
            out.append({"term": RESTRICTED, "restricted": True})
            continue
        out.append({"term_id": t["term_id"], "term": t["term"], "aliases": t.get("aliases") or [], "definition": t["definition"],
                    "owner": t.get("owner"), "confirmed_at": t.get("confirmed_at"), "restricted": False})
    return out


def _plain(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def _glossary_ambiguities(request: Request, bid: str | None) -> list[dict]:
    """The meaning questions the glossary itself raised, on the measures this person may see (an owner has no route to the technical list)."""
    from modules.m2_baseline.api.worklist import Ctx
    from modules.m2_baseline.store import kpis as K
    try:
        ctx = Ctx(request)
        return [{**a, "kpi_id": k["id"], "kpi_name": k["name"], "derived": False} for k in K.read_kpis(ctx.plane, bid) if bid and ctx.sees(k)
                for a in k.get("ambiguities") or [] if str(a.get("where") or "").startswith("Business glossary")]
    except Exception:  # noqa: BLE001 - the list is a convenience; the screen says there are none rather than failing
        log.warning("the glossary questions could not be read")
        return []


@router.get("/api/intents/{intent_id}/glossary-start")
def get_intents_by_intent_id_glossary_start(request: Request, intent_id: str):
    plane, viewer = _plane(request), _viewer(request)
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        return _plain(500, S.UNREADABLE)
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if tier is None:
        return _plain(404, S.NOT_FOUND)
    if tier != "content":
        return _plain(403, "You can see this intent exists, but not what is inside it.")
    try:
        terms = load_terms(plane)
    except Refused as e:
        return _plain(500, str(e))
    g = (rec.get("outcome") or {}).get("glossary") or {}
    counts = {k: g.get(k) for k in ("terms", "confirmed", "draft", "ambiguous_accepted", "reused", "changed") if k in g}
    bid = _baseline_of(rec)
    return {"intent_id": intent_id, "terms": start_terms(terms, rec, viewer), "ambiguities": _glossary_ambiguities(request, bid), "can_settle": may_settle(viewer, g.get("governance_lead")),
            "people": [{"display_name": a["display_name"]} for a in request.app.state.account_store.in_company(request.state.company_id) if not a.get("disabled")],
            "baseline_id": _baseline_of(rec), "counts": counts or None, "governance_lead": g.get("governance_lead"),
            "questions_left": question_budget(plane, rec, viewer.account_id, viewer.name)}


# ---- the company's terms (Register and proposal flow; company-wide, so not keyed by an intent) --------------------------------

def _shown(t: dict, viewer: pview.Viewer) -> dict:
    if t.get("restricted") and pview.ADMIN not in viewer.roles:
        return {"term": RESTRICTED, "restricted": True}
    return {**{k: v for k, v in t.items() if k != "proposals"}, "restricted": bool(t.get("restricted")),
            "proposals": t.get("proposals") or [] if may_settle_term(t, viewer, pview.ADMIN in viewer.roles) else []}


def _terms_or_500(plane):
    try:
        return load_terms(plane), None
    except Refused as e:
        return None, _plain(500, str(e))


@router.get("/api/intents/glossary/terms")
def get_intents_glossary_terms(request: Request):
    plane, viewer = _plane(request), _viewer(request)
    terms, err = _terms_or_500(plane)
    return err or {"terms": [_shown(t, viewer) for t in terms]}


@router.get("/api/intents/glossary/terms/{term_id}")
def get_intents_glossary_terms_by_term_id(request: Request, term_id: str):
    plane, viewer = _plane(request), _viewer(request)
    terms, err = _terms_or_500(plane)
    t = None if err else find_by_id(terms, term_id)
    if err or t is None or (t.get("restricted") and pview.ADMIN not in viewer.roles):
        return err or _plain(404, S.NOT_FOUND)
    versions = (read_json_strict(plane.path("graph", "versions.json"), dict) or {}).get(node_id(term_id)) or []
    return {**_shown(t, viewer), "versions": versions}


@router.post("/api/intents/glossary/terms/{term_id}/proposals")
async def post_intents_glossary_terms_by_term_id_proposals(request: Request, term_id: str):
    plane, viewer = _plane(request), _viewer(request)
    body = await request.json()
    terms, err = _terms_or_500(plane)
    t = None if err else find_by_id(terms, term_id)
    if err or t is None or (t.get("restricted") and pview.ADMIN not in viewer.roles):
        return err or _plain(404, S.NOT_FOUND)
    iid = body.get("intent_id") or None
    try:
        rec = S.read_intent(plane, iid) if iid else None
    except S.Unreadable:
        return _plain(500, S.UNREADABLE)
    in_it = bool(rec and rec.get("state") == "open" and S.tier_of(rec, viewer, S.areas_of(plane, viewer)) == "content")
    if not in_it and not may_settle_term(t, viewer, False):
        return _plain(403, "Only someone in an open Initiative, or the owner, can propose a change.")
    try:
        return JSONResponse(propose(plane, term_id, body.get("wording"), body.get("reason"), viewer.name, iid if in_it else None), status_code=201)
    except Refused as e:
        return _plain(400, str(e))


def _decide(request: Request, term_id: str, prop_id: str, confirm: bool):
    plane, viewer = _plane(request), _viewer(request)
    t = find_by_id(load_terms(plane), term_id)
    if t is None or (t.get("restricted") and pview.ADMIN not in viewer.roles):
        return _plain(404, S.NOT_FOUND)
    try:
        return _shown(decide_proposal(plane, term_id, prop_id, confirm, viewer, pview.ADMIN in viewer.roles), viewer)
    except Refused as e:
        return _plain(403, str(e))


@router.post("/api/intents/glossary/terms/{term_id}/proposals/{proposal_id}/confirm")
def post_intents_glossary_proposal_confirm(request: Request, term_id: str, proposal_id: str):
    return _decide(request, term_id, proposal_id, True)


@router.post("/api/intents/glossary/terms/{term_id}/proposals/{proposal_id}/decline")
def post_intents_glossary_proposal_decline(request: Request, term_id: str, proposal_id: str):
    return _decide(request, term_id, proposal_id, False)


# ---- the owner's and the settler's replies on one term of the Initiative's baseline glossary -------------------------------------
# One route: POST /api/intents/{intent_id}/glossary/{term_id}/reply, {action, ...}; term_id is the entry's id in the baseline glossary.
#   mine {wording?} | not_mine {owner?} | both_used {note?, amb_id}   : the term's owner (a name-only owner passes only when no account shares the name)
#   keep_both {amb_id, second_term} | reopen {reason, amb_id?}          : the governance lead, the sponsor or the company admin (the owner may reopen)
# Each reply writes the baseline entry, the company term where one is made or confirmed, and a version on the term's node.

def _baseline_of(rec: dict) -> str | None:
    g = (rec.get("outcome") or {}).get("glossary") or {}
    return g.get("baseline_id") or ((rec.get("refs") or {}).get("baseline_ids") or [None])[-1]


def _reply(ctx, plane, rec: dict, viewer: pview.Viewer, kpi_id: str, body: dict) -> dict:
    from modules.m2_baseline.store import glossary as SG
    from modules.m2_baseline.store import kpis as K
    bid, act, iid = _baseline_of(rec), str(body.get("action") or ""), rec["id"]
    if not bid:
        raise Refused("This Initiative has no baseline glossary yet.")
    entry = next((e for e in SG.seen(plane, bid, ctx.sees) if e["kpi_id"] == kpi_id), None)
    if entry is None:
        raise LookupError(S.NOT_FOUND)
    kpi = next(k for k in K.read_kpis(plane, bid) if k["id"] == kpi_id)
    gov = ((rec.get("outcome") or {}).get("glossary") or {}).get("governance_lead")
    term, owner = G.text_of(entry["term"]), holds(entry, viewer)
    settler = may_settle(viewer, gov)
    wording = lambda: G.text_of(next(e for e in SG.read(plane, bid)["entries"] if e["kpi_id"] == kpi_id)["business_definition"])  # noqa: E731
    version = lambda what: append_version(plane, node_id(term_id_of(term)), what, viewer.name, iid)  # noqa: E731
    amb = lambda: next((a for a in kpi.get("ambiguities") or [] if a["id"] == body.get("amb_id")), None)  # noqa: E731
    if act == "mine":
        if not owner:
            raise Refused("Only the owner of this term can answer for it.")
        text = " ".join(str(body.get("wording") or "").split())
        SG.decide(plane, bid, kpi_id, ctx.sees, "edited" if text else "ours", _words(text, "the wording") if text else "", viewer.name)
        _, how = add_term(plane, term, wording(), viewer.name, viewer.name, iid, restricted=bool(entry.get("sensitive")))
        if how != "created":
            version("Owner confirmed the wording")
        return {"done": "mine", "company_term": how}
    if act == "not_mine":
        if not owner:
            raise Refused("Only the owner of this term can answer for it.")
        named = " ".join(str(body.get("owner") or "").split())
        who = next((p["display_name"] for p in ctx.people() if pview.norm(p["display_name"]) == pview.norm(named)), None) if named else None
        if named and not who:
            raise Refused("Please pick someone from your company's list, or say you do not know.")
        sponsor = ((rec.get("people") or {}).get("sponsor") or {}).get("name")
        owner_reply(entry, viewer, False, sponsor, who)  # refuses before anything is written when the sponsor named this owner
        SG._change_entry(plane, bid, kpi_id, ctx.sees, lambda e: owner_reply(e, viewer, False, sponsor, who))
        version(f"Owner handed the term to {who}" if who else "Owner does not know who owns the term")
        return {"done": "not_mine", "owner": who}
    if act == "both_used":
        if not owner:
            raise Refused("Only the owner of this term can answer for it.")
        if amb() is None:
            raise Refused("We could not find that question.")
        note = " ".join(str(body.get("note") or "").split()) or f"{viewer.name} says both meanings are used."
        K.change(plane, bid, kpi_id, lambda k: A.accept(A.asked(k, body["amb_id"], viewer.name), body["amb_id"], _words(note, "a note"), viewer.name))
        version("Both meanings are used; accepted as a known risk")
        return {"done": "both_used"}
    if act == "keep_both":
        if not settler:
            raise Refused("Only the governance lead, the sponsor or the company admin can settle this.")
        a = amb()
        if a is None or a.get("status") != "open":
            raise Refused("That question is no longer open.")
        second = _words(body.get("second_term"), "the name of the second term")[:G.MAX_TERM]
        if G.key(second) == G.key(term):
            raise Refused("The second term needs a different name.")
        K.change(plane, bid, kpi_id, lambda k: A.settle(k, body["amb_id"], f"Kept both: the other meaning is now the term {second}.", viewer.name))  # first: a signed baseline refuses before a company term is made
        row, how = add_term(plane, second, a["text"], None, viewer.name, iid)
        version(f"Kept both meanings; the second is the term {second}")
        return {"done": "keep_both", "second_term": row["term"], "company_term": how}
    if act == "reopen":
        if not (settler or owner):
            raise Refused("Only the governance lead, the sponsor, the company admin or the owner can reopen this.")
        why = _words(body.get("reason"), "why you are reopening it")
        if body.get("amb_id"):
            K.change(plane, bid, kpi_id, lambda k: A.reopen(k, body["amb_id"], why))
        SG._change_entry(plane, bid, kpi_id, ctx.sees, lambda e: {k: v for k, v in e.items() if k != "reviewed"} | {"reviewed": None})
        version(f"Reopened: {why}")
        return {"done": "reopen"}
    raise Refused("Please choose one of the replies.")


@router.post("/api/intents/{intent_id}/glossary/{term_id}/reply")
async def post_intents_by_intent_id_glossary_by_term_id_reply(request: Request, intent_id: str, term_id: str):
    from modules.m2_baseline.api.worklist import Ctx
    from modules.m2_baseline.store import baseline as B
    plane, viewer = _plane(request), _viewer(request)
    body = await request.json()
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        return _plain(500, S.UNREADABLE)
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if tier is None:
        return _plain(404, S.NOT_FOUND)
    if tier != "content":
        return _plain(403, "You can see this intent exists, but not what is inside it.")
    try:
        return _reply(Ctx(request), plane, rec, viewer, term_id, body if isinstance(body, dict) else {})
    except Refused as e:
        return _plain(403 if "Only" in str(e) or "Ask the sponsor" in str(e) else 400, str(e))
    except (A.Refused, G.Refused) as e:
        return _plain(400, str(e))
    except LookupError:
        return _plain(404, S.NOT_FOUND)
    except B.Locked as e:
        return _plain(409, str(e))
    except B.StoreError as e:
        return _plain(500, str(e))
