"""Lens in Define (44): the unattended run, the nine kinds, the question cap, the send-back loop.

Everything lives in `define.lens` inside `intents/<id>/intent.json` (ruling 12). Lens reuses the existing agent
(`modules/m2_baseline/agent/lens.py`: prompts, the labelled reply, pre-read, name registration) and the kernel runtime
(`run_agent`, the number guard, the egress client). Other Define cards call `draft_for` and `raise_question`.

Decisions where the spec leaves a gap (also in the report): a cell keeps its own value and source (`value`, `mark`, `by`,
`source`, `redraft`) because the spec's cell record has nowhere else for a draft; the governance lead is
`people.governance_lead`, else `people.approver`, else the sponsor, else the organiser; interviews are read only when
the person marked them `shareable` (none do today); a sealed card is never put in a prompt.
"""
import functools
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.agent import lens as agent
from modules.m2_baseline.agent import pack_text as P
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.agents.loop import run_agent
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.intents import _plane, _viewer, access, events, processes
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()

KINDS = ("mapping", "business_definition", "technical_definition", "catalogue_entry", "owners", "governed_state",
         "process_steps", "data_sources", "ambiguities")  # the order of the spec: cluster mapping first, ambiguities last
LABELS = dict(zip(KINDS, ("Cluster to measure", "Business definition", "Technical definition", "Catalogue entry", "The three owners",
                          "Governed state", "Process steps", "Data sources", "Ambiguities")))
QUESTION_KINDS = ("technical_definition", "owners", "governed_state", "process_steps", "ambiguities")  # where a question can come from
QUESTION_CAP = 3  # open questions per person across Define (ruling 9, A-045)
MAX_NOTE = agent.MAX_ANSWER // 3  # the existing instruction length limit of the m2 redraft (300)
STALE_AFTER = 300  # seconds: a claim older than this was never finished
NOT_KNOWN = "Not known yet"
NO_FIGURE = "Not available yet: Lens found no figure in a record."
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SUGGESTION = "Suggestion from the family office pack, not a draft of yours"


class Refused(Exception):
    """A request the rules turn down; the message is plain words for the person."""


# ---- the runtime: the model client and the gate, from the request or (for another card calling draft_for) from the plane

class _OpenGate:
    """Entitlement is already checked by the route that led here; the agent loop still asks the gate once per step."""

    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return True


@dataclass
class Runtime:
    model: object | None
    gate: object = field(default_factory=_OpenGate)
    company_id: str = ""
    company_name: str = ""
    industry: str = ""
    guidance: P.Guidance = field(default_factory=lambda: P.Guidance(None))
    recorder: object | None = None


def runtime_for_plane(plane) -> Runtime:
    try:
        model = build_model_client(plane, load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        model = None
    return Runtime(model, company_id=plane.company_id, recorder=RunRegistry(plane))


def runtime_for_request(request: Request, plane) -> Runtime:
    st = request.app.state
    company = st.entitlements.company(request.state.company_id) or {}
    factory, override = getattr(st, "lens_model_factory", None), getattr(st, "model_env", None)  # tests plug a stub in here
    try:
        model = factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        model = None
    return Runtime(model, st.entitlements, request.state.company_id, str(company.get("name") or ""), str(company.get("industry") or ""),
                   P.load_guidance(st.packs, company.get("industry")), RunRegistry(plane))


# ---- the record: define.lens in the intent file

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file(plane, intent_id: str):
    if not SAFE_ID.match(str(intent_id)):
        raise LookupError("no such intent")
    return plane.path("intents", intent_id, "intent.json")


def _fresh() -> dict:
    return {"run": {"id": None, "state": "idle", "started_at": None, "finished_at": None, "order": list(KINDS), "model_set_up": False},
            "cells": {}, "send_backs": [], "questions": [], "reads": {"documents": 0, "interviews": 0, "profile": False, "pack": False}}


def _qfile(plane, intent_id: str):
    """The questions live in `intents/<id>/lens_questions.json` as a top-level `questions` list with `to_person`: the shared cap
    (processes.question_budget) counts every json file of the intent folder, so Lens's questions count towards the same three."""
    return plane.path("intents", intent_id, "lens_questions.json")


def _with_questions(plane, intent_id: str, doc: dict) -> dict:
    qs = (read_json_strict(_qfile(plane, intent_id), dict) or {}).get("questions", [])
    doc.setdefault("define", {}).setdefault("lens", {})["questions"] = qs
    return doc


def read_intent(plane, intent_id: str) -> dict:
    doc = read_json_strict(_file(plane, intent_id), dict)
    if doc is None:
        raise LookupError("no such intent")
    return _with_questions(plane, intent_id, doc)


def block(intent: dict) -> dict:
    """define.lens, filled in with its defaults (a read never writes)."""
    got = ((intent.get("define") or {}).get("lens")) or {}
    return {**_fresh(), **got}


def _change(plane, intent_id: str, fn):
    """Read, change define.lens (and its questions) under the file's lock and write whole; returns what fn returns."""
    from sh_platform.intents import store as S  # the record's own writers hold the intents lock: Lens holds it too, or a sign or a stage move is lost
    path = _file(plane, intent_id)
    with S.locked(plane), lock_for(path), lock_for(_qfile(plane, intent_id)):
        doc = read_json_strict(path, dict)
        if doc is None:
            raise LookupError("no such intent")
        lens = block(_with_questions(plane, intent_id, doc))
        lens["_ctx"] = (plane, intent_id)
        out = fn(lens, doc)
        qs = lens.pop("questions")
        lens.pop("_ctx")
        write_json_atomic(_qfile(plane, intent_id), {"questions": [{**q, "to_person": q["to"]} for q in qs]})
        doc.setdefault("define", {})["lens"] = lens
        write_json_atomic(path, doc)
        return out


def _person_of(intent: dict, by: str) -> dict:
    """Who acted, for the line: the name from the intent's people (`by` is a name or an account id); never an account id as a name."""
    for v in (intent.get("people") or {}).values():
        for e in v if isinstance(v, list) else [v]:
            if isinstance(e, dict) and e.get("name") and by in (e.get("name"), e.get("account_id")):
                return {"account": str(e.get("account_id") or by), "name": str(e["name"]), "role": ""}
    return {"account": by, "name": "A named person", "role": ""}


def _event(plane, intent_id: str, kind: str, by: str, detail: dict) -> None:
    """One line in events.jsonl through the one writer: keys, enums and numbers only (16). Lens's own lines are drafts; a person's act is theirs."""
    if kind in events.AGENT_LINES:
        events.try_append(plane, intent_id, kind, "lens", {"store": "define.lens", "id": intent_id}, detail, "draft", stage="define")
    else:
        events.try_append(plane, intent_id, kind, _person_of(read_intent(plane, intent_id) or {}, by), {"store": "define.lens", "id": intent_id}, detail, "act", stage="define")


def cell_key(code: str, kind: str) -> str:
    return f"{code}:{kind}"


def is_stale(cell: dict) -> bool:
    return cell.get("state") == "drafting" and time.time() - float(cell.get("claimed_at") or 0) > STALE_AFTER


# ---- what Lens may read: the profile per viewer, never a sealed card, never an unconfirmed interview

_ORGANISER = view.Viewer("", frozenset({"company_admin"}))  # Lens drafts as the organiser's view for shared cells


def read_profile(plane) -> dict:
    """{cards: [plain text], interviews: [plain text], systems: [name], people: [name], card_count_by_word}: sealed cards are dropped whole,
    an anonymous card carries no author, an interview only when its person marked it shareable."""
    try:
        prof = view.read(plane, _ORGANISER)
    except (OSError, ValueError):
        return {"cards": [], "interviews": [], "systems": [], "people": []}
    cards = []
    for c in (prof.get("cards") or {}).values():
        if c.get("silhouette") or view._v(c, "sealed") is True:
            continue  # D-013: a sealed card is never read, in any draft others may see
        cards.append(" ".join(str(view._v(c, q) or "") for q in view._QS).strip())
    interviews = [" ".join(str(view._v(i, k) or "") for k in ("summary", "answers", "text")).strip()
                  for i in (prof.get("interviews") or {}).values() if view._v(i, "shareable") is True]
    systems = [str(view._v(s, "name") or k) for k, s in (prof.get("systems") or {}).items() if not str(k).startswith("restricted-")]
    people = [str(view._v(p, "name") or k) for k, p in (prof.get("people") or {}).items()]
    return {"cards": [c for c in cards if c], "interviews": [i for i in interviews if i], "systems": systems, "people": people}


def _card_lines(prof: dict) -> str:
    return "\n".join(f"- {c}" for c in prof["cards"][:40]) + ("\n" + "\n".join(f"- Interview: {i}" for i in prof["interviews"][:10]) if prof["interviews"] else "")


def _card_hits(prof: dict, term: str) -> int:
    return sum(1 for c in prof["cards"] if term and term.lower() in c.lower())


# ---- one draft: draft_for, the export other cards call

def _guard_text(text: str, source: str, outcome: str = "guessed", titles: list[str] | None = None) -> dict:
    return {"value": text, "mark": "guessed", "by": "Lens", "source": source or "no source found", "outcome": outcome, **({"titles": titles} if titles else {})}


def _unknown(outcome: str, suggestion: str | None = None, value: str | None = NOT_KNOWN) -> dict:
    return {"value": value, "mark": "guessed", "by": "Lens", "source": "no source found", "outcome": outcome, **({"suggestion": suggestion} if suggestion else {})}


def _sources(titles: list[str], extra: str = "") -> str:
    parts = [f"Lens, from {', '.join(titles)}" if titles else "", extra]
    return "; ".join(p for p in parts if p) or "Lens, no source found"


def _pack_suggestion(rt: Runtime, code: str) -> str | None:
    return agent_pack_definition(rt.guidance, code)


def agent_pack_definition(g: P.Guidance, code: str) -> str | None:
    k = P.kpi_by_id(g, code)
    d = (g.defaults.get(code) or {}).get("definition") if k else None
    return str(d) if d else None


def _ask(rt: Runtime, ctx: dict, system: str, question: str) -> str | None:
    """One model call through the runtime and egress; None when the reply was empty or a figure was replaced by the guard.
    Raises agent.ModelUnreachable when the call was refused or failed."""
    res = run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id, agent.MODULE_ID, agent.AGENT_NAME, system, ctx, question, recorder=rt.recorder)
    if res.status in ("refused", "error"):
        raise agent.ModelUnreachable
    if res.status != "done" or res.numbers_replaced:
        return None
    text = "\n".join(ln.rstrip() for ln in res.text.splitlines()).strip()
    return None if not text or text.upper().startswith(("UNKNOWN", agent.NO_DEFINITION)) else text[:agent.MAX_TECHNICAL]


def _model_kind(rt: Runtime, plane, kind: str, code: str, name: str, prof: dict, instruction: str = "", current: str = "") -> dict:
    """A draft of one kind from the profile, the shelf documents and the pack (as a suggestion), or {value: Not known yet}."""
    g = rt.guidance
    pack = P.pack_text(g, code) if P.kpi_by_id(g, code) else ""
    suggestion = agent_pack_definition(g, code)
    passages, titles = agent.preread(plane, P.retrieval_query(g, code, name, []))
    cards = _card_lines(prof)
    base = {"company": rt.company_name, "industry": rt.industry or g.label, "kpi": name, "industry_guidance": pack}
    if passages:
        base["company_documents"] = passages
    if cards:
        base["profile_cards"] = cards
    facts = agent.figures(pack, cards, instruction, current, passages)
    src = _sources(titles, "Lens, from the profile" if cards and not titles else "")
    if kind == "business_definition":
        got = agent.draft_fields(rt.model, rt.gate, rt.company_id, company_name=rt.company_name, industry=base["industry"], kpi_name=name, pack=pack,
                                 documents=passages + ("\n\n" + cards if cards else ""), recorder=rt.recorder, instruction=instruction, current=current)
        if got.get("definition"):
            return _guard_text(got["definition"], src, titles=titles)
        return _unknown("nothing", suggestion)
    if kind == "owners":
        got = agent.draft_fields(rt.model, rt.gate, rt.company_id, company_name=rt.company_name, industry=base["industry"], kpi_name=name, pack=pack,
                                 documents=passages + ("\n\n" + cards if cards else ""), recorder=rt.recorder)
        named = lambda v: v if v and not str(v).lstrip().startswith("[") else None  # noqa: E731 - a placeholder such as "[a name]" is no owner
        owners = {"business_owner": named(got.get("owner")), "data_owner": named(got.get("producer")), "source_owner": None}
        if not any(owners.values()):
            return _unknown("nothing", value=None)
        return {**_guard_text("", src, titles=titles), "value": {k: {"value": v, "mark": "guessed", "by": "Lens", "source": src if v else "Lens, no source found"} for k, v in owners.items()}}
    if kind == "technical_definition":
        text = agent.draft_technical(rt.model, rt.gate, rt.company_id, company_name=rt.company_name, industry=base["industry"], kpi_name=name,
                                     definition=current, pack=pack, catalogue="", documents=passages, recorder=rt.recorder, instruction=instruction, current=current)
        if not text:
            return _unknown("nothing")
        if re.search(r"CALCULATION:\s*UNKNOWN", text):
            return {**_guard_text(text, src, titles=titles), "missing_formula": True}  # a missing formula is a question, never filled in
        return _guard_text(text, src, titles=titles)
    prompts = {"process_steps": f"List the steps of the process behind {name}, one numbered step per line, from the cards, documents and interviews you were shown. Write UNKNOWN if they do not say.",
               "ambiguities": f"List each different meaning of {name} that the sources you were shown give, one per line as 'meaning | where found'. Write UNKNOWN if there are fewer than two."}
    ask = prompts[kind] + (f" The person asks: {instruction}. Current: {current}." if instruction else "")
    text = _ask(rt, {**base, "facts": facts}, agent.system_prompt(documents=bool(passages)), ask)
    if not text:
        return _unknown("nothing", value=None if kind == "ambiguities" else NOT_KNOWN)
    if kind == "ambiguities" and len([ln for ln in text.splitlines() if ln.strip()]) < 2:
        return _unknown("nothing", value=None)
    return _guard_text(text, src, titles=titles)


def _code_kind(rt: Runtime, kind: str, code: str, name: str, prof: dict, cells: dict) -> dict:
    """The kinds drafted by code, no model: mapping, catalogue entry, governed state, data sources."""
    if kind == "mapping":
        return _guard_text(name or "No measures yet", "Lens, from the measure list") if name else _unknown("nothing", value="No measures yet")
    if kind == "data_sources":
        names = prof["systems"]
        return _guard_text(", ".join(names), "Lens, from the profile systems list") if names else _unknown("nothing", value=None)
    if kind == "catalogue_entry":
        tech = cells.get(cell_key(code, "technical_definition")) or {}
        rows = [m for ln in str(tech.get("value") or "").splitlines() if ln.upper().startswith(("SOURCES:", "TABLES:", "FIELDS:")) for m in [ln.strip()] if "UNKNOWN" not in m.upper()]
        return _guard_text("\n".join(rows), tech.get("source") or "") if rows else _unknown("nothing", value=None)
    return _unknown("nothing", value=None)  # governed state: no policy, access list or deadlines file is read yet (report: Not available yet)


def _named_owners(plane, intent: dict, code: str) -> list[dict]:
    """The people named as owners of a measure (the baseline's business, data and process owners, or `owners` on a listed measure):
    [{name, role, account_id?}]. Only a named owner may confirm or send back that measure's cells; a guessed owner never counts."""
    ids = (intent.get("refs") or {}).get("baseline_ids") or []
    listed = next((m for m in (intent.get("define") or {}).get("measures") or [] if isinstance(m, dict) and str(m.get("code") or m.get("id")) == code), None)
    found = None
    if ids:
        from modules.m2_baseline.store.kpis import read_kpis
        found = next((k for k in read_kpis(plane, ids[0]) if k["id"] == code), None)
    own = ((found or listed or {}).get("owners")) or {}
    return [{"name": str(o["value"]), "role": f"{r} owner", **({"account_id": o["account_id"]} if o.get("account_id") else {})}
            for r, o in own.items() if isinstance(o, dict) and o.get("value")]


def may_act(plane, intent: dict, me: "access.Me", key: str) -> bool:
    """Confirm, send back and pick: the owner named for the item, or the named governance lead for the governed state and for an item no one owns."""
    c = block(intent)["cells"].get(key)
    if not c or "super_admin" in me.roles:  # being named is the proof (ruling 1: a named owner opens the intent); roles_of knows no owner or approver slot
        return False
    if "analyst" in me.roles or "organiser" in access.roles_of(intent, me):  # the intent's organiser (people.organiser) and the analyst; a company admin who is neither may not
        return True
    owners = c["owned_by"] if "owned_by" in c else _named_owners(plane, intent, c["measure_code"])
    if any(access._is_me(o, me) for o in owners):
        return True
    return (c["kind"] == "governed_state" or not owners) and any(access._named(intent, slot, me) for slot in ("governance_lead", "approver"))


def _require_owner(request: Request, plane, intent: dict, key: str) -> None:
    if not may_act(plane, intent, access.Me.of(request, plane), key):
        raise Refused("Only the person named as owner of this item can do that.")


def draft_for(plane, intent_id: str, kind: str, target: str, *, rt: Runtime | None = None, retry: bool = False,
              instruction: str = "", current: str = "", name: str | None = None, defer_open: bool = False) -> dict:
    """Lens's draft of one kind for one measure code (`target`). Claims the cell first, so a second screen skips it, then drafts,
    stores the result as a guessed cell and returns it: {cell_key, kind, measure_code, state, outcome, value, mark, by, source, drafted_at}.
    A cell already tried is returned as it is unless `retry`. Never raises for a failed model call: the cell becomes `failed`."""
    if kind not in KINDS:
        raise ValueError("unknown kind")
    rt = rt or runtime_for_plane(plane)
    key, held = cell_key(target, kind), []

    def claim(lens, intent):
        c = lens["cells"].get(key)
        if c and not retry and not is_stale(c) and c["state"] != "not_drafted":
            return False
        lens["cells"][key] = {**(c or {}), "kind": kind, "measure_code": target, "state": "drafting", "attempts": int((c or {}).get("attempts") or 0) + 1,
                              "outcome": None, "drafted_at": None, "confirmed_by": None, "confirmed_at": None, "claimed_at": time.time(), "name": name or (c or {}).get("name") or target}
        lens["run"]["model_set_up"] = rt.model is not None
        return True

    if not _change(plane, intent_id, claim):
        return cell_view(read_intent(plane, intent_id), key)
    prof = read_profile(plane)
    owners = _named_owners(plane, read_intent(plane, intent_id), target)
    try:
        result = _draft(rt, plane, kind, target, name or target, prof, block(read_intent(plane, intent_id))["cells"], instruction, current)
        state = "not_drafted" if result["outcome"] == "no_model" else "guessed"
    except agent.ModelUnreachable:
        result, state = {"outcome": "unreachable", "value": None, "suggestion": _pack_suggestion(rt, target)}, "failed"
    except (OSError, ValueError, LookupError):
        log.warning("a Lens draft failed")
        result, state = {"outcome": "unreachable", "value": None}, "failed"

    def store(lens, intent):
        c = lens["cells"][key]
        keep = {k: c[k] for k in ("redraft", "name") if k in c}
        lens["cells"][key] = {**c, **{k: v for k, v in result.items() if k != "missing_formula"}, "state": state, "drafted_at": _now() if state == "guessed" else None, "owned_by": owners, **keep}
        lens["cells"][key].pop("claimed_at", None)
        titles = sorted(set(lens["reads"].get("titles", [])) | set(result.pop("titles", [])))
        lens["reads"] = {"titles": titles, "documents": len(titles), "interviews": len(prof["interviews"]), "profile": bool(prof["cards"] or prof["systems"]), "pack": bool(rt.guidance.kpis)}
        if state == "guessed" and (result.get("missing_formula") or (result["outcome"] == "nothing" and kind in QUESTION_KINDS)):
            _raise(lens, intent, to=None, about=key, text=_question_text(kind, name or target), term=name or target, rank=_card_hits(prof, name or target), kind=kind, defer=defer_open)
        if state == "guessed" and kind == "ambiguities" and result.get("value"):
            _raise(lens, intent, to=None, about=key, text=f"Which meaning of {name or target} is right?", term=name or target, rank=_card_hits(prof, name or target), kind=kind, defer=defer_open)
    _change(plane, intent_id, store)
    return cell_view(read_intent(plane, intent_id), key)


def _draft(rt: Runtime, plane, kind: str, code: str, name: str, prof: dict, cells: dict, instruction: str, current: str) -> dict:
    if kind in ("mapping", "catalogue_entry", "governed_state", "data_sources"):
        return _code_kind(rt, kind, code, name if kind == "mapping" else name, prof, cells)
    if rt.model is None:
        s = agent_pack_definition(rt.guidance, code) if kind == "business_definition" else None
        return {**_unknown("no_model", s, None)}
    return _model_kind(rt, plane, kind, code, name, prof, instruction, current)


def _question_text(kind: str, name: str) -> str:
    return {"technical_definition": f"The documents do not say how {name} is calculated. How is it calculated?",
            "owners": f"Who owns {name}: the business owner, the data owner and the source owner?",
            "governed_state": f"Who may see {name}, and how is it classified?",
            "process_steps": f"What are the steps of the process behind {name}?"}.get(kind, f"What does {name} mean here?")


def cell_view(intent: dict, key: str) -> dict:
    c = dict(block(intent)["cells"].get(key) or {})
    if not c:
        return {"cell_key": key, "state": "not_drafted"}
    if is_stale(c):
        c["state"], c["outcome"] = "failed", "unreachable"
    c.pop("claimed_at", None)
    return {"cell_key": key, **c}


# ---- the questions: the shared cap of three open per person

def question_budget(plane, intent_id: str, person: str | None) -> int:
    """How many more questions `person` may have open across Define: the shared cap less every open one, B14's count (process map,
    glossary, catalogue) included. Derived from the records, never stored."""
    shared = getattr(processes, "question_budget", None)
    if shared and person:
        return int(shared(plane, intent_id, person)["free"])
    lens = block(read_intent(plane, intent_id))
    return max(0, QUESTION_CAP - sum(1 for q in lens["questions"] if q["state"] == "open" and q["to"] == person))


def _open_elsewhere(lens: dict, person: str | None) -> int:
    """Open questions this person holds in the other Define stores (B14's count less what Lens's own file already holds on disk)."""
    ctx, shared = lens.get("_ctx"), getattr(processes, "question_budget", None)
    if not ctx or not person or not shared:
        return 0
    plane, iid = ctx
    on_disk = (read_json_strict(_qfile(plane, iid), dict) or {}).get("questions", [])
    mine = sum(1 for q in on_disk if q.get("state") == "open" and view.norm(q.get("to") or "") == view.norm(person))
    return max(0, int(shared(plane, iid, person)["open"]) - mine)


def governance_lead(intent: dict, avoid: str | None = None) -> str | None:
    p = intent.get("people") or {}
    pick = lambda v: v.get("account_id") or v.get("id") or v.get("name") if isinstance(v, dict) else v  # noqa: E731
    for slot in ("governance_lead", "approver", "sponsor", "organiser"):
        who = pick(p.get(slot))
        if who and who != avoid:
            return str(who)
    return None


_OWNER_SLOT = {"business_definition": "business", "ambiguities": "business", "technical_definition": "data", "catalogue_entry": "data",
               "data_sources": "data", "mapping": "data", "process_steps": "process"}  # which named owner answers which kind of item


def _owner_of(lens: dict, intent: dict, about: str) -> tuple[str | None, bool]:
    """Who a question goes to, and whether the item has no named owner at all. The owner named for the item and the kind (a data owner
    for a technical definition), else any named owner of it; with none, or for the governed state, the governance lead."""
    code, _, kind = about.partition(":")
    cell = lens["cells"].get(about) or next((c for c in lens["cells"].values() if c.get("measure_code") == code and c.get("owned_by")), None) or {}
    owners = cell.get("owned_by") or []
    named = lambda o: o.get("account_id") or o.get("name")  # noqa: E731
    want = _OWNER_SLOT.get(kind)
    pick = next((o for o in owners if want and o["role"].startswith(want)), None) or (owners[0] if owners and kind != "governed_state" else None)
    return (named(pick) if pick else governance_lead(intent)), not owners


def _raise(lens: dict, intent: dict, *, to, about: str, text: str, term: str, rank: int, kind: str, defer: bool = False) -> dict | None:
    """Add a question (merged into an open or queued one that shares the term), then open up to three per person. Callers inside _change."""
    no_owner = False
    if not to:
        to, no_owner = _owner_of(lens, intent, about)
    same = next((q for q in lens["questions"] if q["state"] in ("queued", "open") and q["term"].lower() == term.lower() and q["to"] == to), None)
    if same:
        return same
    q = {"id": uuid.uuid4().hex[:12], "to": to, "about_cell": about, "kind": kind, "text": text, "term": term, "rank": rank, "state": "queued",
         "raised_at": None, "answered_at": None, "answer": None, **({"no_owner": True} if no_owner else {})}
    lens["questions"].append(q)
    if not defer:  # a run defers, then opens the best three per person in one go (ranked)
        promote(lens)
    return q


def promote(lens: dict) -> None:
    """Open queued questions per person, largest card count first, then alphabetical by term, while they have fewer than three open."""
    for person in {q["to"] for q in lens["questions"]}:
        room = QUESTION_CAP - sum(1 for q in lens["questions"] if q["state"] == "open" and q["to"] == person) - _open_elsewhere(lens, person)
        waiting = sorted((q for q in lens["questions"] if q["state"] == "queued" and q["to"] == person), key=lambda q: (-int(q["rank"]), q["term"].lower()))
        for q in waiting[:max(room, 0)]:
            q["state"], q["raised_at"] = "open", _now()


def raise_question(plane, intent_id: str, *, to: str | None, about: str, text: str, term: str, rank: int = 0, kind: str = "ambiguities", defer: bool = False) -> dict | None:
    """For the process map (27) and the glossary (29): their questions go into the same list and the same cap."""
    return _change(plane, intent_id, lambda lens, intent: _raise(lens, intent, to=to, about=about, text=text, term=term, rank=rank, kind=kind, defer=defer))


def open_next(plane, intent_id: str) -> None:
    """Open the ranked, queued questions up to three per person (after a batch of deferred ones)."""
    _change(plane, intent_id, lambda lens, intent: promote(lens))


def _find_q(lens: dict, qid: str) -> dict:
    q = next((q for q in lens["questions"] if q["id"] == qid), None)
    if q is None:
        raise LookupError("no such question")
    return q


def answer_question(plane, intent_id: str, qid: str, by: str, answer: str) -> dict:
    text = " ".join(str(answer or "").split())
    if not text:
        raise Refused("Please say it in your words.")

    def go(lens, intent):
        q = _find_q(lens, qid)
        if q["state"] != "open" or q["to"] != by:
            raise Refused("That question is not open for you.")
        q.update(state="answered", answer=text[:agent.MAX_ANSWER], answered_at=_now())
        promote(lens)  # Lens opens the next queued question after each answer
        return q
    q = _change(plane, intent_id, go)
    _event(plane, intent_id, "lens_question_answered", by, {"question": qid})
    return q


def reassign_question(plane, intent_id: str, qid: str, by: str, person: str) -> dict:
    def go(lens, intent):
        q = _find_q(lens, qid)
        if q["state"] != "open" or q["to"] != by or not person:
            raise Refused("That question is not open for you.")
        q.update(to=person, state="queued", raised_at=None)
        promote(lens)  # the new person's cap applies: queued if they are at three
        return q
    return _change(plane, intent_id, go)


def drop_question(plane, intent_id: str, qid: str, by: str, reason: str) -> dict:
    if not str(reason or "").strip():
        raise Refused("Please say why.")

    def go(lens, intent):
        q = _find_q(lens, qid)
        if q["state"] not in ("open", "queued"):
            raise Refused("That question is already closed.")
        q.update(state="dropped", answer=str(reason).strip()[:200], answered_at=_now())
        promote(lens)
        return q
    return _change(plane, intent_id, go)


# ---- the send-back loop: one redraft, then the governance lead

def send_back(plane, intent_id: str, key: str, by: str, note: str, *, rt: Runtime | None = None) -> dict:
    """First send back: Lens redrafts once with the note and the redraft goes beside the first. Second: no redraft, the cell is escalated
    to the governance lead (to the sponsor when the lead is the person sending it back) with a question. Returns {outcome, cell}."""
    text = " ".join(str(note or "").split())
    if not text:
        raise Refused("Please say what to change.")
    if len(text) > MAX_NOTE:
        raise Refused(f"Please keep the note under {MAX_NOTE} characters.")
    intent = read_intent(plane, intent_id)
    cell = block(intent)["cells"].get(key)
    if not cell:
        raise LookupError("no such cell")
    if cell["state"] in ("confirmed", "drafting"):
        raise Refused("This cannot be sent back now.")
    rounds = [s for s in block(intent)["send_backs"] if s["cell_key"] == key]
    if rounds and cell["state"] == "escalated":
        raise Refused("This is already with the person who decides.")
    if not rounds:
        rt = rt or runtime_for_plane(plane)
        if rt.model is None:
            return {"outcome": "no_model", "note": "Lens cannot redraft this because drafting is not set up for your company.", "cell": cell_view(intent, key)}
        try:
            redraft = _model_kind_for_cell(rt, plane, cell, text)
        except agent.ModelUnreachable:
            return {"outcome": "unreachable", "note": "Lens could not draft just now, so the wording is unchanged. Please try again.", "cell": cell_view(intent, key)}
        if not redraft or redraft.get("value") in (None, ""):
            return {"outcome": "no_change", "note": "Lens could not make that change from what it has, so the wording is unchanged.", "cell": cell_view(intent, key)}

        def first(lens, intent_):
            lens["cells"][key]["redraft"] = {"value": redraft["value"], "source": redraft["source"], "note": text, "at": _now()}
            lens["cells"][key]["state"] = "redrafted"
            lens["send_backs"].append({"cell_key": key, "by": by, "at": _now(), "note": text, "round": 1, "redraft_ref": key, "escalated_to": None, "decision": None})
        _change(plane, intent_id, first)
        _event(plane, intent_id, "lens_send_back", by, {"cell": key, "round": 1})
        return {"outcome": "redrafted", "cell": cell_view(read_intent(plane, intent_id), key)}

    def second(lens, intent_):
        to = governance_lead(intent_, avoid=by)
        lens["send_backs"].append({"cell_key": key, "by": by, "at": _now(), "note": text, "round": 2, "redraft_ref": None, "escalated_to": to, "decision": None})
        lens["cells"][key]["state"] = "escalated"
        c = lens["cells"][key]
        _raise(lens, intent_, to=to, about=key, text=f"Two people sent back {LABELS[c['kind']].lower()} for {c.get('name') or c['measure_code']}. Which wording is right?",
               term=f"{c.get('name') or c['measure_code']} {c['kind']}", rank=0, kind="escalation")
    _change(plane, intent_id, second)
    _event(plane, intent_id, "lens_escalated", by, {"cell": key, "round": 2})
    return {"outcome": "escalated", "cell": cell_view(read_intent(plane, intent_id), key)}


def _model_kind_for_cell(rt: Runtime, plane, cell: dict, note: str) -> dict | None:
    cur = cell.get("value")
    cur = cur if isinstance(cur, str) else "; ".join(f"{k}: {v.get('value')}" for k, v in (cur or {}).items() if isinstance(v, dict))
    if cell["kind"] in ("mapping", "catalogue_entry", "governed_state", "data_sources"):
        return None  # code-first kinds have nothing to redraft with a model
    return _model_kind(rt, plane, cell["kind"], cell["measure_code"], cell.get("name") or cell["measure_code"], read_profile(plane), note, cur)


def pick(plane, intent_id: str, key: str, by: str, choice: str) -> dict:
    """"Use this one" (the redraft becomes the value, still guessed) or "Keep the first"."""
    if choice not in ("redraft", "first"):
        raise Refused("Pick the redraft or the first draft.")

    def go(lens, intent):
        c = lens["cells"].get(key)
        if not c or c["state"] != "redrafted":
            raise Refused("There is no redraft to choose from.")
        if choice == "redraft":
            c["value"], c["source"] = c["redraft"]["value"], c["redraft"]["source"]
        c["picked"] = {"choice": choice, "by": by, "at": _now()}
        c.pop("redraft", None)
        c["state"] = "guessed"
    _change(plane, intent_id, go)
    return cell_view(read_intent(plane, intent_id), key)


def decide(plane, intent_id: str, key: str, by: str, choice: str, wording: str = "") -> dict:
    """The governance lead: use the first draft, use the redraft (in the cell's history), write it, or mark it not known with a known risk."""
    def go(lens, intent):
        c = lens["cells"].get(key)
        if not c or c["state"] != "escalated":
            raise Refused("Nothing is waiting for a decision here.")
        sb = next(s for s in reversed(lens["send_backs"]) if s["cell_key"] == key and s["round"] == 2)
        if choice == "redraft" and c.get("redraft"):
            c["value"], c["source"] = c["redraft"]["value"], c["redraft"]["source"]
        elif choice == "write":
            if not wording.strip():
                raise Refused("Please write the wording.")
            c.update(value=wording.strip(), mark="stated", by=by, source=f"Stated by {by}")
        elif choice == "unknown":
            c.update(value=NOT_KNOWN, known_risk=True)
        elif choice != "first":
            raise Refused("Pick one of the options.")
        c.pop("redraft", None)
        c["state"] = "guessed"
        sb["decision"] = {"choice": choice, "by": by, "at": _now()}
        for q in lens["questions"]:
            if q["about_cell"] == key and q["kind"] == "escalation" and q["state"] in ("open", "queued"):
                q.update(state="answered", answered_at=_now(), answer=choice)
        promote(lens)
    _change(plane, intent_id, go)
    return cell_view(read_intent(plane, intent_id), key)


def confirm(plane, intent_id: str, key: str, by: str) -> dict:
    def go(lens, intent):
        c = lens["cells"].get(key)
        if not c or c["state"] not in ("guessed",) or c.get("value") in (None, ""):
            raise Refused("There is nothing to confirm yet.")
        c.update(state="confirmed", confirmed_by=by, confirmed_at=_now(), mark="stated")
    _change(plane, intent_id, go)
    return cell_view(read_intent(plane, intent_id), key)


# ---- the unattended run

def measures_for(plane, intent: dict) -> list[dict]:
    """[{code, name}] of every measure the intent's clusters map to: define.measures when the Define screen wrote it, else the measures of the
    first baseline in refs. Empty means the strip says "Not available yet: no measures to draft"."""
    listed = (intent.get("define") or {}).get("measures")
    if isinstance(listed, list) and listed:
        return [{"code": str(m.get("code") or m.get("id")), "name": str(m.get("name") or m.get("code") or m.get("id")), "restricted": bool(m.get("restricted"))} for m in listed if isinstance(m, dict)]
    ids = ((intent.get("refs") or {}).get("baseline_ids")) or []
    if not ids:
        return []
    from modules.m2_baseline.store.kpis import read_kpis
    return [{"code": k["id"], "name": k["name"], "restricted": bool((k.get("governance") or {}).get("sensitive"))} for k in read_kpis(plane, ids[0])]


def _register(plane, rt: Runtime, prof: dict) -> None:
    agent.register_names(plane, rt.company_name, prof["people"])


def _drafted(lens: dict) -> int:
    return sum(1 for c in lens["cells"].values() if c.get("state") in ("guessed", "redrafted", "escalated", "confirmed"))


def run(plane, intent_id: str, rt: Runtime | None = None, *, retry: bool = False) -> dict:
    """Draft every measure in the nine-kind order, one measure at a time, so one failure never blocks the rest. `retry` takes only failed cells
    again. A run already on (and not stale) is left alone: another screen started it."""
    rt = rt or runtime_for_plane(plane)
    intent = read_intent(plane, intent_id)
    measures = measures_for(plane, intent)

    def start(lens, intent_):
        r = lens["run"]
        if r["state"] == "running" and intent_id in _LIVE and time.time() - _ts(r["started_at"]) < STALE_AFTER * 12:
            return False  # a run still going in this process; one left "running" by a restart is not live and may be started again
        stopped = r["state"] == "running"  # left running by a restart: carry on with the cells not yet drafted
        for k in [k for k, c in lens["cells"].items() if stopped and c.get("state") == "drafting"]:
            del lens["cells"][k]  # the claim belonged to the process that died; the cell is simply missing
        _LIVE.add(intent_id)
        lens["run"] = {**r, "id": uuid.uuid4().hex[:12], "state": "running", "started_at": _now(), "finished_at": None, "order": list(KINDS), "model_set_up": rt.model is not None,
                       "resumed_from": _drafted(lens) if stopped else None}
        return True
    if not _change(plane, intent_id, start):
        return block(read_intent(plane, intent_id))["run"]
    _event(plane, intent_id, "lens_run_started", "", {"measures": len(measures), "retry": retry})
    prof = read_profile(plane)
    if rt.model is not None:
        _register(plane, rt, prof)
    failed = False
    for m in measures:  # one measure at a time, the kinds in order
        for kind in KINDS:
            c = block(read_intent(plane, intent_id))["cells"].get(cell_key(m["code"], kind))
            if retry and c and not (c["state"] == "failed" or is_stale(c)):  # a retry takes failed and missing cells, never one already drafted
                continue
            cv = draft_for(plane, intent_id, kind, m["code"], rt=rt, retry=retry, name=m["name"], defer_open=True)
            failed = failed or cv.get("state") == "failed"
    open_next(plane, intent_id)  # rank across the whole run, then open the first three per person
    done = _change(plane, intent_id, lambda lens, i: lens["run"].update(state="partial" if failed else "done", finished_at=_now()) or lens["run"]["state"])
    _LIVE.discard(intent_id)
    _event(plane, intent_id, "lens_run_finished", "", {"state": done})
    return block(read_intent(plane, intent_id))["run"]


def _ts(iso) -> float:
    try:
        return datetime.fromisoformat(str(iso)).timestamp()
    except ValueError:
        return 0.0


def start_in_background(plane, intent_id: str, rt: Runtime, retry: bool = False) -> None:
    threading.Thread(target=lambda: _safe_run(plane, intent_id, rt, retry), daemon=True).start()


_LIVE: set[str] = set()  # intents with a run going in this process: after a restart the record may still say "running"


def _safe_run(plane, intent_id, rt, retry) -> None:
    try:
        run(plane, intent_id, rt, retry=retry)
    except Exception:  # noqa: BLE001 - a background run must never die loudly; the strip shows what is not drafted
        log.exception("the Lens run stopped")
        _change(plane, intent_id, lambda lens, i: lens["run"].update(state="partial", finished_at=_now()))
    finally:
        _LIVE.discard(intent_id)


# ---- what the screen reads: counts from the record, per viewer

DETAIL_ROLES = {"company_admin", "analyst", "sponsor", "approver"}


def _person_name(intent: dict, who) -> str:
    """The display name for an account id or name held in a record: the intent's own people entries first, else what is held."""
    for entry in (e for v in (intent.get("people") or {}).values() for e in (v if isinstance(v, list) else [v])):
        if isinstance(entry, dict) and entry.get("name") and who in (entry.get("account_id"), entry.get("person_id"), entry.get("name")):
            return str(entry["name"])
    return str(who or "")


def people_names(intent: dict) -> list[str]:
    """Every person named in the intent, for the "Not mine, it is ..." picker."""
    out = [str(e["name"]) for v in (intent.get("people") or {}).values() for e in (v if isinstance(v, list) else [v]) if isinstance(e, dict) and e.get("name")]
    return sorted(set(out))


def _question_card(q: dict, cells: dict, me: set) -> dict:
    """A question with the item it is about, why it is asked of this person and the meanings found (screen 4)."""
    cell = cells.get(q["about_cell"]) or {}
    item = cell.get("name") or cell.get("measure_code") or q["term"]
    role = next((o["role"] for o in cell.get("owned_by") or [] if {o.get("name"), o.get("account_id")} & me), None)
    amb = cells.get(f"{cell.get('measure_code')}:ambiguities") or {}
    meanings = [{"meaning": a.strip(), "where": b.strip()} for ln in str(amb.get("value") or "").splitlines() if ln.strip()
                for a, _, b in [ln.partition("|")]] if q["kind"] != "escalation" else []
    why = ("You decide because this was sent back twice." if q["kind"] == "escalation" else f"You are named as {role} of {item}." if role
           else f"No owner is named for this item yet, so Lens is asking you as governance lead." if q.get("no_owner")
           else f"This question about {item} was passed to you.")
    return {**q, "item": item, "why": why, "meanings": meanings}


def state_for(intent: dict, *, account: str | None, name: str, roles: set[str], measures: int | None = None) -> dict:
    """Run, counts by state, the run detail (only for the roles that may see it), the viewer's own questions in full and totals for the rest."""
    lens = block(intent)
    cells = {k: cell_view(intent, k) for k in lens["cells"]}
    cells = {k: c for k, c in cells.items() if not c.get("restricted") or roles & {"company_admin"}}
    counts: dict[str, int] = {}
    for c in cells.values():
        counts[c["state"]] = counts.get(c["state"], 0) + 1
    drafted = sum(n for s, n in counts.items() if s in ("guessed", "redrafted", "escalated", "confirmed"))
    me = {account, name} - {None, ""}
    qs = lens["questions"]
    mine = [q for q in qs if q["to"] in me and q["state"] in ("open", "answered")]
    lead = bool(roles & {"approver"})
    codes = {c["measure_code"] for c in cells.values()}
    measures = max(measures or 0, len(codes))
    out = {"run": lens["run"], "reads": lens["reads"], "counts": counts, "total": max(len(cells), measures * len(KINDS)), "measures": measures, "drafted": drafted,
           "failed": [k for k, c in cells.items() if c["state"] == "failed"],
           "questions": {"mine_open": sum(1 for q in mine if q["state"] == "open"), "waiting": sum(1 for q in qs if q["state"] == "queued"),
                         "open_total": sum(1 for q in qs if q["state"] == "open")},
           "my_questions": [_question_card(q, cells, me) for q in [q for q in mine if q["state"] == "open"] + ([q for q in qs if q["kind"] == "escalation" and q["state"] == "open" and q["to"] not in me] if lead else [])],
           "may_decide": bool(roles & {"approver", "sponsor"}),
           "escalated": [{"cell_key": k, "with": _person_name(intent, next((s["escalated_to"] for s in reversed(lens["send_backs"]) if s["cell_key"] == k), None)),
                          "notes": [s["note"] for s in lens["send_backs"] if s["cell_key"] == k]} for k, c in cells.items() if c["state"] == "escalated"]}
    if roles & DETAIL_ROLES:
        out["cells"] = cells
    else:
        out["cells"] = {k: {x: c.get(x) for x in ("cell_key", "kind", "measure_code", "name", "state", "value", "mark", "by", "source", "outcome", "confirmed_by", "confirmed_at")} for k, c in cells.items()}
    return out


# ---- routes (the permission lines they need are in the report: route_permissions.yaml is the orchestrator's)

def _tier(plane, intent: dict, request: Request) -> str | None:
    from sh_platform.intents import store as S  # lazy: the store's visibility adapters import the request helpers
    v = _viewer(request)
    return S.tier_of(intent, v, S.areas_of(plane, v))


def _intent_for(request: Request):
    """The record, only for a person file 05's matrix lets open it: hidden answers exactly like missing (404), the card tier 403."""
    plane = _plane(request)
    intent = read_intent(plane, request.path_params["intent_id"])
    tier = _tier(plane, intent, request)
    if tier is None:
        raise LookupError("hidden")
    if tier != "content":
        raise Refused("You can see that this exists. You can open it if the organiser adds you.")
    return plane, intent


def _person(request: Request) -> tuple[str | None, str, set[str]]:
    v = _viewer(request)
    return request.state.account_id, v.name, set(request.state.roles or [])


def _organiser_or_analyst(plane, intent: dict, request: Request) -> bool:
    """The intent's organiser, or an analyst who may open the intent; never an analyst it is hidden from."""
    me = access.Me.of(request, plane)
    if _tier(plane, intent, request) != "content":
        return False
    return "analyst" in me.roles or "organiser" in access.roles_of(intent, me)


def _guard(fn):
    @functools.wraps(fn)
    def wrapped(request: Request, *a, **kw):
        try:
            return fn(request, *a, **kw)
        except LookupError:
            return JSONResponse({"detail": "We could not find that."}, status_code=404)
        except Refused as e:
            return JSONResponse({"error": "not_allowed", "message": str(e), "detail": str(e)}, status_code=403)  # `message` is what the screen shows
        except PermissionError:
            return JSONResponse({"error": "not_allowed", "message": "You may not do that here.", "detail": "Not allowed."}, status_code=403)
    return wrapped


def _need(roles: set[str], allowed: set[str]) -> None:
    if not roles & allowed:
        raise PermissionError


@router.get("/api/intents/{intent_id}/define/lens")
@_guard
def get_lens(request: Request, intent_id: str):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    out = state_for(intent, account=acct, name=name, roles=roles, measures=len(measures_for(plane, intent)))
    me = access.Me.of(request, plane)
    out["may_act"] = [k for k in out["cells"] if may_act(plane, intent, me, k)]
    for k in out["may_act"]:  # the owner also sees a redraft and the pack's suggestion (screen 2)
        out["cells"][k] = {**cell_view(intent, k), **out["cells"][k]}
    out["people"], out["lead"] = people_names(intent), _person_name(intent, governance_lead(intent))
    if out["run"]["state"] == "running" and intent_id not in _LIVE:  # a restart ended the run
        if _organiser_or_analyst(plane, intent, request):  # one who may start it carries it on from the cells already drafted
            start_in_background(plane, intent_id, runtime_for_request(request, plane), True)
            out["run"] = {**out["run"], "resumed_from": out["drafted"]}
        else:
            out["run"] = {**out["run"], "state": "partial"}  # the strip offers "Try again" instead of waiting for ever
    return out


@router.post("/api/intents/{intent_id}/define/lens/run")
@_guard
def post_run(request: Request, intent_id: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    if not _organiser_or_analyst(plane, intent, request):  # North starts it when Define opens; the intent's organiser and the analyst may retry failed items
        raise PermissionError
    retry = body.get("retry") is True
    start_in_background(plane, intent_id, runtime_for_request(request, plane), retry)
    return {"started": True, "retry": retry}


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/try-again")
@_guard
def post_try_again(request: Request, intent_id: str, cell_key: str):
    plane, intent = _intent_for(request)
    c = block(intent)["cells"].get(cell_key)
    if not c:
        raise LookupError
    if not may_act(plane, intent, access.Me.of(request, plane), cell_key):  # organiser, analyst or the item's named owner
        raise PermissionError
    if cell_view(intent, cell_key)["state"] != "failed":
        raise Refused("Only an item that failed can be tried again.")  # a guessed, sent back or confirmed cell is never redrafted from here
    return draft_for(plane, intent_id, c["kind"], c["measure_code"], rt=runtime_for_request(request, plane), retry=True, name=c.get("name"))


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/send-back")
@_guard
def post_send_back(request: Request, intent_id: str, cell_key: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    _require_owner(request, plane, intent, cell_key)
    return send_back(plane, intent_id, cell_key, acct or name, str(body.get("note") or ""), rt=runtime_for_request(request, plane))


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/pick")
@_guard
def post_pick(request: Request, intent_id: str, cell_key: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    _require_owner(request, plane, intent, cell_key)
    return pick(plane, intent_id, cell_key, acct or name, str(body.get("choice") or ""))


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/decide")
@_guard
def post_decide(request: Request, intent_id: str, cell_key: str, body: dict = Body(default_factory=dict)):
    plane, _ = _intent_for(request)
    acct, name, roles = _person(request)
    _need(roles, {"approver", "sponsor"})
    return decide(plane, intent_id, cell_key, acct or name, str(body.get("choice") or ""), str(body.get("wording") or ""))


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/not-mine")
@_guard
def post_not_mine(request: Request, intent_id: str, cell_key: str, body: dict = Body(default_factory=dict)):
    """"Not mine, it is <name>": the named owner hands the item to someone else in the intent; their name becomes the owner of the cell."""
    plane, intent = _intent_for(request)
    _require_owner(request, plane, intent, cell_key)
    person = str(body.get("person") or "").strip()
    if person not in people_names(intent):
        raise Refused("Please pick a person named in this intent.")
    acct = request.state.account_id or ""

    def go(lens, intent_):
        c = lens["cells"][cell_key]
        role = (c.get("owned_by") or [{}])[0].get("role", "owner")
        c["owned_by"] = [{"name": person, "role": role}]
        for q in lens["questions"]:
            if q["about_cell"] == cell_key and q["state"] in ("open", "queued") and q["kind"] != "escalation":
                q.update(to=person, state="queued", raised_at=None)
        promote(lens)
    _change(plane, intent_id, go)
    _event(plane, intent_id, "lens_reassigned", acct, {"cell": cell_key})
    return cell_view(read_intent(plane, intent_id), cell_key)


@router.post("/api/intents/{intent_id}/define/lens/cells/{cell_key}/confirm")
@_guard
def post_confirm(request: Request, intent_id: str, cell_key: str):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    _require_owner(request, plane, intent, cell_key)  # only the named owner (or the governance lead where no one owns it) confirms; Lens never does
    return confirm(plane, intent_id, cell_key, name or str(acct))


@router.post("/api/intents/{intent_id}/define/lens/questions/{qid}/answer")
@_guard
def post_answer(request: Request, intent_id: str, qid: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    lens = block(intent)
    q = _find_q(lens, qid)
    return answer_question(plane, intent_id, qid, q["to"] if q["to"] in {acct, name} else "", str(body.get("answer") or ""))


@router.post("/api/intents/{intent_id}/define/lens/questions/{qid}/reassign")
@_guard
def post_reassign(request: Request, intent_id: str, qid: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    acct, name, roles = _person(request)
    q = _find_q(block(intent), qid)
    return reassign_question(plane, intent_id, qid, q["to"] if q["to"] in {acct, name} else "", str(body.get("person") or ""))


@router.post("/api/intents/{intent_id}/define/lens/questions/{qid}/drop")
@_guard
def post_drop(request: Request, intent_id: str, qid: str, body: dict = Body(default_factory=dict)):
    plane, intent = _intent_for(request)
    me = access.Me.of(request, plane)
    if not any(access._named(intent, slot, me) for slot in ("governance_lead", "approver")):
        raise PermissionError
    return drop_question(plane, intent_id, qid, "", str(body.get("reason") or ""))
