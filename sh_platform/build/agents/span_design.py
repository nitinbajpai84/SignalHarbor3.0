"""Span's architecture work (plan 3.6, card SF11): the target architecture (room 0), the decision records and risks of a change note
(chain gate 1), and the prose sections of the design document. Span drafts; a named person signs.

Entry points: `draft_target(plane, rt, intent_id)`, `draft_record(plane, rt, by)`, `draft_change_note(plane, note_id, rt, by)` and
`draft_design(plane, rt)`. The last two names are called from chain.py gate 1 (through span_arch) and must keep their signatures.

Every model call is one `run_agent` through the egress gateway with Span's read tools. When there is no model or the call fails, the
rule-based draft stands (R14): `architecture.project` for the target, chain's own `_draft` lines for the change note, and
`design_doc.fill_from_records` for the design, each with the one fallback sentence.

Reuse: decision `normalise` and `check` copied from the earlier emitters/architecture_drafting.py L184-L232 (with `_valid_ref` from
model_drafting.py L410), reshaped to the change note decision line (placement, options, chosen, why, follows). The citation check copied
from emitters/reference_arch.py L439 `_norm` and the quote test inside `verify` L520-L530. ponytail: the earlier `_unsupported_terms`
flag (named products a cited passage never mentions) is not copied; add it when citations are shown with a confidence mark.
Placements use SF05's draft shape and are validated with `archify_spec.validate`; the design is saved through SF06 `design_doc.draft`.
"""
import json
import logging
import re
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from sh_platform.agents.loop import run_agent
from sh_platform.build import architecture as A
from sh_platform.build import archify_spec as S
from sh_platform.build import chain, design_doc
from sh_platform.build.agents import read_tools as T
from sh_platform.build.agents.runtime import MODULE_ID, SPAN, Runtime
from sh_platform.build.proposals import figures_trace
from sh_platform.egress.policy import EgressPolicy
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view

log = logging.getLogger(__name__)
RULES_FILE = Path(__file__).with_name("span_design_rules.yaml")
MAX_TEXT = 2000
MAX_LINES = 8
MIN_WHY = 15  # architecture_drafting: a rationale under 15 characters is too thin to be a reason
MIN_QUOTE_WORDS = 6  # reference_arch.verify: a citation quote of at least six words
SPAN_FROM = "Span's draft"
PLACEMENT_ID = re.compile(r"[A-Za-z][A-Za-z0-9_:-]{0,63}")
NOBODY = view.Viewer("", frozenset())  # specs saved in the design are masked for everyone; screens rebuild them per viewer
# SF14: the target draft, the change note lines and the design document are stored once and read by every role, so Span drafts each from
# what nobody-in-particular may see (restricted sources, components and measures stay out of its context and so out of its words).


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _system(internet: bool) -> str:
    r = rules()
    return "\n".join([r["role"], *(f"- {x}" for x in r["rules"]), *([r["cite"]] if internet else [])])


def _parse(text: str) -> dict | None:
    """The JSON object in a reply (compile.py `_parse`, with the earlier parse_decision's fence strip)."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    m = re.search(r"\{.*\}", t, re.S)
    try:
        d = json.loads(m.group()) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _items(out: Any) -> list:
    return list(out.get("items") or []) if isinstance(out, dict) and out.get("available") is not False else []


def _texts(v: Any) -> list[str]:
    return [str(x).strip()[:MAX_TEXT] for x in v if str(x).strip()][:MAX_LINES] if isinstance(v, list) else []


def _ln(text: str, src: str = SPAN_FROM, **kw) -> dict:
    return {"text": str(text)[:MAX_TEXT], "mark": "guessed", "from": src, "by": SPAN, "at": _now(), **kw}


# ---- citations: only what checks out (reference_arch.verify) --------------------------------------------------------------------------

class _Capture:
    """Wraps the internet gateway so this run's search replies can be checked against the quotes Span cites. Numbered R-1, R-2 in order
    (the number guard leaves a capital, a hyphen and digits alone, so the refs survive it)."""

    def __init__(self, inner):
        self.inner, self.passages = inner, {}

    def internet_query(self, module_id: str, host: str, query: str):
        reply = self.inner.internet_query(module_id, host, query)
        self.passages[f"R-{len(self.passages) + 1}"] = {"source": host, "text": " ".join(str(reply.text).split())[:T.MAX_TEXT]}
        return reply


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def verify_cites(cites: Any, passages: dict[str, dict]) -> list[dict]:
    """A citation counts only if its quote is really in the passage it names (at least six words, ignoring case and punctuation)."""
    out = []
    for c in cites if isinstance(cites, list) else []:
        if not isinstance(c, dict):
            continue
        ref, q = str(c.get("ref", "")).strip(), _norm(str(c.get("quote", "")))
        if ref in passages and len(q.split()) >= MIN_QUOTE_WORDS and q in _norm(passages[ref]["text"]):
            out.append({"source": passages[ref]["source"], "passage_id": ref, "quote": str(c["quote"]).strip()[:400]})
    return out


# ---- decision records (architecture_drafting normalise and check) ---------------------------------------------------------------------

def normalise(d: Any) -> dict:
    d = d if isinstance(d, dict) else {}
    s = lambda k: str(d.get(k) or "").strip()[:MAX_TEXT]  # noqa: E731
    return {"placement": s("placement")[:200], "options": [str(o).strip()[:400] for o in d.get("options") or [] if str(o).strip()][:5]
            if isinstance(d.get("options"), list) else [], "chosen": s("chosen"), "why": s("why"), "follows": s("follows"),
            "provenance": [str(p).strip() for p in d.get("provenance") or [] if str(p).strip()] if isinstance(d.get("provenance"), list) else [],
            "cites": d.get("cites") if isinstance(d.get("cites"), list) else []}


def _valid_ref(ref: str, known: set[str]) -> bool:
    return ref in known or ref.split(":", 1)[0].strip() in known


def check(d: dict, known_refs: set[str]) -> list[str]:
    """What a person reviewing the decision would otherwise catch by eye. Any error drops the decision."""
    errs = []
    if not d["placement"]:
        errs.append("the decision names no placement")
    if len(d["options"]) < 2:
        errs.append(f"needs at least two options; drafted {len(d['options'])}")
    if len(set(d["options"])) != len(d["options"]):
        errs.append("two options are the same")
    if d["chosen"] not in d["options"]:
        errs.append("the choice is not one of the options")
    if len(d["why"]) < MIN_WHY:
        errs.append("the reason is missing or too thin")
    if not d["follows"]:
        errs.append("what follows is missing")
    errs += [f"it cites {r}, which is not in the records" for r in d["provenance"] if not _valid_ref(r, known_refs)]
    return errs


def decision_lines(raw: Any, known_refs: set[str], passages: dict[str, dict]) -> list[dict]:
    """Change note decision lines from Span's decision records; a record that fails the check is dropped."""
    out = []
    for item in raw if isinstance(raw, list) else []:
        d = normalise(item)
        if check(d, known_refs):
            continue
        other = [o for o in d["options"] if o != d["chosen"]]
        out.append(_ln(f"{d['placement']}: {d['chosen']}, because {d['why']}. Other option: {'; '.join(other)}. Then: {d['follows']}.",
                       d["provenance"][0] if d["provenance"] else SPAN_FROM, placement=d["placement"], options=d["options"], chosen=d["chosen"],
                       why=d["why"], follows=d["follows"], cites=verify_cites(d["cites"], passages)))
    return out


# ---- one model call -------------------------------------------------------------------------------------------------------------------

def _ask(plane, rt: Runtime, context: dict, question: str, ids: set[str]) -> tuple[dict | None, dict[str, dict]]:
    """(the reply's JSON object or None, this run's search passages). None means the rule-based draft stands. `ids` are named in the
    question: the number guard leaves figures of the question alone, so record ids such as gold:k12 come back unchanged."""
    if rt.model is None:
        return None, {}
    internet = EgressPolicy(plane).is_internet_allowed(MODULE_ID)
    cap = _Capture(rt.gateway or T._internet_gateway(plane)) if internet else None
    run_rt = replace(rt, gateway=cap) if cap else rt
    try:
        res = run_agent(rt.model, T.span_registry(plane, run_rt), rt.company_id or plane.company_id, MODULE_ID, SPAN, _system(internet),
                        T.as_lines(context), question + (" Ids you may use: " + ", ".join(sorted(ids)) + "." if ids else ""), recorder=rt.recorder)
    except Exception:  # noqa: BLE001 - any failure reaching the model leaves the rule-based draft in place (R14)
        log.warning("Span's architecture call failed")
        return None, {}
    d = _parse(res.text) if res.status == "done" else None
    if d is not None and not figures_trace(res.text, list(context.get("facts") or []) + res.tool_facts, [*ids, json.dumps(context)]):
        log.info("Span's reply stated a figure that does not trace to a fact; the rule-based draft stands")  # SF14: listed ids exempt no bare figure
        d = None
    return d, (cap.passages if cap else {})


# ---- target architecture (room 0) and the architecture record draft (gate 1) ----------------------------------------------------------

def _target_file(plane):
    return plane.path("build", "span", "target.json")


def target_draft(plane) -> dict | None:
    """Span's newest valid target draft, `{"placements": [...], "lines": [...], ...}` (SF05's draft shape), or None."""
    try:
        d = read_json_strict(_target_file(plane))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("placements"), list) else None


def _handoff_ids(plane) -> list[str]:
    return [h["_id"] for h in A._handoffs(plane)]


def _handoff_context(plane, rt: Runtime, intent_ids: list[str]) -> dict:
    """The R16 hand-off through Span's read tool (masked per viewer): charter, measures, processes, sources. Nothing else from the intent."""
    out: dict = {"charters": [], "measures": [], "processes": [], "sources": []}
    for iid in intent_ids:
        h = T.read_handoff(plane, rt, iid)
        if h.get("available") is False:
            continue
        out["charters"].append(h["charter"])
        for k in ("measures", "processes", "sources"):
            out[k] += _items(h[k])
    return out


def _placement_errors(placements: Any, record_ids: set[str]) -> list[str]:
    if not isinstance(placements, list):
        return ["Span's draft has no list of placements."]
    errs, ids = [], {str(p.get("id")) for p in placements if isinstance(p, dict) and p.get("id")}
    for p in placements:
        if not isinstance(p, dict) or not p.get("id") or not p.get("label"):
            errs.append("A placement has no id or no label.")
            continue
        if not PLACEMENT_ID.fullmatch(str(p["id"])):
            errs.append("A placement id has characters an id may not use.")  # also an id the number guard rewrote
        if p["id"] in record_ids:
            errs.append(f"The placement {p['id']} reuses a component the records already have.")
        if p.get("kind") not in A.KINDS:
            errs.append(f"The placement {p['id']} has a kind the record does not know.")
        if (p.get("view") or "data") not in A.VIEWS:
            errs.append(f"The placement {p['id']} names a view that does not exist.")
        errs += [f"The placement {p['id']} connects to {i.get('to')}, which is not in the diagram." for i in p.get("interfaces") or []
                 if not isinstance(i, dict) or i.get("to") not in record_ids | ids]
    return errs


def check_placements(plane, draft: dict) -> list[str]:
    """Plain-word errors for a target draft; empty means it may be saved. The placement checks, then SF05's validation of every view."""
    record_ids = {c["id"] for c in A.read(plane)["components"]}
    errs = _placement_errors(draft.get("placements"), record_ids)
    if errs:
        return errs
    for vw in A.VIEWS:
        errs += S.validate(S.target(plane, NOBODY, draft, vw), S.known_ids(plane, NOBODY, draft, vw))
    return errs


def _target(plane, rt: Runtime, intent_ids: list[str], by: str) -> dict:
    rt = replace(rt, viewer=NOBODY)
    hand = _handoff_context(plane, rt, intent_ids)
    current = _items(T.read_architecture(plane, rt, "all"))
    context = {"company": rt.company_name, "industry": rt.industry, **hand, "current": {"components": current}, "facts": []}
    ids = {c["id"] for c in current} | {str(m.get("code")) for m in hand["measures"] if m.get("code")}
    d, _ = _ask(plane, rt, context, rules()["target"].replace("{kinds}", ", ".join(A.KINDS)), ids)
    if d is None:
        return {"fallback": True, "message": rules()["fallback"], "projection": sorted(A.project(plane)), "saved": False, "errors": [],
                "draft": target_draft(plane)}
    draft = {"placements": [{k: p.get(k) for k in ("id", "kind", "label", "view", "interfaces", "why") if k in p}
                            for p in d.get("placements") or [] if isinstance(p, dict)] if isinstance(d.get("placements"), list) else d.get("placements"),
             "lines": _texts(d.get("lines"))}
    errs = check_placements(plane, draft)
    if errs:  # an invalid draft is never saved; the previous one stays
        return {"fallback": False, "message": f"The diagram could not be drawn: {errs[0]}", "saved": False, "errors": errs, "draft": target_draft(plane)}
    draft.update(by=SPAN, asked_by=by, at=_now(), intent_ids=intent_ids)
    with lock_for(_target_file(plane)):
        write_json_atomic(_target_file(plane), draft)
    return {"fallback": False, "message": None, "saved": True, "errors": [], "draft": draft}


def draft_target(plane, rt: Runtime, intent_id: str) -> dict:
    """Room 0: Span's target architecture for one Initiative handed to Build. {fallback, message, saved, errors, draft[, projection]}."""
    return _target(plane, rt, [intent_id], rt.viewer.name or SPAN)


def draft_record(plane, rt: Runtime, by: str) -> dict:
    """Chain gate 1: Span's target placements for the architecture record, over every Initiative handed to Build. Same result shape as
    `draft_target`. Nothing is written to the record itself; a person accepts it through the change note."""
    return _target(plane, rt, _handoff_ids(plane), by)


# ---- the change note (chain gate 1) ---------------------------------------------------------------------------------------------------

def _known_refs(note: dict) -> set[str]:
    secs = note.get("sections") or {}
    refs = {str(ln.get(k)) for v in secs.values() for ln in v or [] if isinstance(ln, dict) for k in ("from", "component", "contract") if ln.get(k)}
    comps = note.get("components") or {}
    return refs | {str(i) for k in ("added", "changed", "retired") for i in comps.get(k) or []} | {str(m) for m in note.get("measures") or []}


def _merge(old: list[dict], new: list[dict], key: str | None) -> list[dict]:
    """Stated lines stay (rule 7). New guessed lines replace guessed ones with the same key (or the same text); the rest stay."""
    stated = [x for x in old if x.get("mark") == "stated"]
    taken = {x.get(key) for x in stated + new if key and x.get(key)} | {x["text"] for x in stated}
    kept = [x for x in old if x.get("mark") != "stated" and not (key and x.get(key) in taken)]
    return stated + kept + [x for x in new if x["text"] not in {s["text"] for s in stated + kept}]


def draft_change_note(plane, note_id: str, rt: Runtime, by: str) -> dict | None:
    """Span's decision records and risks for change note `note_id`, merged into its sections. Returns
    {"note": the note with merged sections (NOT saved: chain.py saves it), "fallback": bool, "message": str | None, "dropped": int},
    or None when there is no such note. Stated lines are kept; a decision that fails the check is dropped and the rule line stays."""
    if not chain.CID.fullmatch(str(note_id)):
        return None
    rt = replace(rt, viewer=NOBODY)
    note = next((n for n in chain.all_notes(plane) if n.get("id") == note_id), None)
    if note is None:
        return None
    secs = {k: list((note.get("sections") or {}).get(k) or []) for k in chain.SECTIONS}
    rule_dec = [{"placement": x.get("placement"), "options": x.get("options"), "chosen": x.get("chosen")} for x in secs["decisions"] if x.get("placement")]
    known = _known_refs(note)
    context = {"company": rt.company_name, "industry": rt.industry, "title": note.get("title"), "measures": note.get("measures") or [],
               **_handoff_context(plane, rt, [note["intent_id"]] if note.get("intent_id") else []),
               "what_changes": [x["text"] for x in secs["what_changes"]], "rule_decisions": rule_dec,
               "accepted_risks": [x["text"] for x in secs["risks"]], "known_refs": sorted(known), "facts": []}
    d, passages = _ask(plane, rt, context, rules()["change_note"] + " " + rules()["decisions"], known)
    if d is None:
        return {"note": note, "fallback": True, "message": rules()["fallback"], "dropped": 0}
    raw = d.get("decisions") if isinstance(d.get("decisions"), list) else []
    dec = decision_lines(raw, known, passages)
    risks = [_ln(t) for t in _texts(d.get("risks"))]
    secs["decisions"] = _merge(secs["decisions"], dec, "placement")
    secs["risks"] = _merge(secs["risks"], risks, None)
    log.info("Span drafted change note %s for %s", note_id, "a person" if by else "the chain")
    return {"note": {**note, "sections": secs}, "fallback": False, "message": None, "dropped": len(raw) - len(dec)}


# ---- the design document --------------------------------------------------------------------------------------------------------------

def _specs(plane, draft: dict | None) -> tuple[dict, list[str]]:
    """The three data-view specs for the design, masked for everyone; only valid ones are returned (the previous ones stay otherwise)."""
    out, errs = {}, []
    for kind, sp in (("current", S.current(plane, NOBODY)), ("target", S.target(plane, NOBODY, draft)), ("delta", S.delta(plane, NOBODY, draft))):
        e = S.validate(sp, S.known_ids(plane, NOBODY, draft))
        if e:
            errs.append(f"{kind}: {e[0]}")
        else:
            out[kind] = sp
    return out, errs


def draft_design(plane, rt: Runtime) -> dict:
    """Fill Span's design sections (purpose, target, model, decisions, risks) and the three diagrams, then save through design_doc.draft.
    {"doc": the saved draft or None, "fallback": bool, "message": str | None, "spec_errors": [str]}. None doc: no change note yet."""
    if not design_doc.has_records(plane):
        return {"doc": None, "fallback": False, "message": design_doc.EMPTY, "spec_errors": []}
    rt = replace(rt, viewer=NOBODY)
    tdraft = target_draft(plane)
    notes = chain.all_notes(plane)
    old = design_doc.read(plane) or {}
    specs, spec_errs = _specs(plane, tdraft)
    specs = {**(old.get("specs") or {}), **specs}
    known = set().union(*(_known_refs(n) for n in notes)) if notes else set()
    context = {"company": rt.company_name, "industry": rt.industry,
               **_handoff_context(plane, rt, [n["intent_id"] for n in notes if n.get("intent_id")]),
               "model": T.read_model(plane, rt), "target_placements": (tdraft or {}).get("placements") or [],
               "target_lines": (tdraft or {}).get("lines") or [],
               "rule_decisions": [{"placement": x.get("placement"), "options": x.get("options"), "chosen": x.get("chosen")}
                                  for n in notes for x in (n.get("sections") or {}).get("decisions") or [] if x.get("placement")],
               "accepted_risks": [x["text"] for n in notes for x in (n.get("sections") or {}).get("risks") or []],
               "known_refs": sorted(known), "facts": []}
    d, passages = _ask(plane, rt, context, rules()["design"] + " " + rules()["decisions"], known | {c["id"] for c in A.read(plane)["components"]})
    if d is None:
        doc = design_doc.draft(plane, None, specs, fallback=True)
        return {"doc": doc, "fallback": True, "message": design_doc.SPAN_SENTENCE, "spec_errors": spec_errs}
    span = {sid: [_ln(t) for t in _texts(d.get(sid))] for sid in ("purpose", "target", "model", "risks")}
    span["decisions"] = decision_lines(d.get("decisions"), known, passages)
    doc = design_doc.draft(plane, {k: v for k, v in span.items() if v}, specs, fallback=False)
    return {"doc": doc, "fallback": False, "message": None, "spec_errors": spec_errs}
