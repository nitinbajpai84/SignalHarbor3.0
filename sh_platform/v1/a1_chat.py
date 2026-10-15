"""A1 Span's conversation: the Build Centre is one talk between the architect and Span, which drafts the blueprint inside it.

The signed intent of work (`intents/<iid>/sow.json`) is read-only context. Every person message goes to the model through the kernel
runtime (`run_agent`: egress gateway, number guard, run log) with Span's role, Span's skill (`skills/span/`, loaded by X5's
`skill_loader`), the signed intent of work, the design note, the scan, the mapping sheet, the data model and the questions for the head
of data so far, and the last twelve turns, all flattened by `egress_fit.fit`. Measures go to the model as letter aliases (the reply guard
rewrites digits, so a code like K01 would not survive the trip back). The model answers
{reply, run, data_model, questions, scope, ready}. `run` asks the product to call the existing cards' functions, in order: b1 `design`
(three layers into the blueprint and the architecture record), b2 `run_scan`, b3 `draft` (the mapping sheet). No new logic for them.
With the model off (SH_MODEL_PROVIDER=off) a rule-based Span takes the next missing step per message and labels its turns
"Span (rules only)". The head of data (company_admin) approves in one click: unanswered questions take their defaults, the proposed
scope is agreed through b2 `agree`, and Span hands over to Flow through the room.

Record: `build/blueprint_conversation/<iid>.json` {intent_id, turns, state: open|ready|approved, approved_by, approved_at,
data_model, questions, scope}. data_model, questions and scope are A1's own additions (reported as open questions).
"""
from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.build import architecture as A
from sh_platform.build.agents.runtime import MODULE_ID, SPAN, register_names
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b1_design as B1
from sh_platform.v1 import b2_scan as B2
from sh_platform.v1 import b3_mapping as B3
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import mem_agent as MEM
from sh_platform.v1 import mem_context as MC
from sh_platform.v1 import mem_wire as WIRE
from sh_platform.v1 import p4_benchmarks as P4
from sh_platform.v1.egress_fit import fit
from sh_platform.v1.file_context import added_line, library_lines, preview_for_agent
from sh_platform.v1 import doc_tools as DT
from sh_platform.v1.seats import seat_of

log = logging.getLogger(__name__)
FALLBACK_NAME = f"{SPAN} (rules only)"
STEPS = ("design", "scan", "mapping")
VIEW_LIMIT = 13_000  # the gateway refuses any one string over 20,000 characters; the prompt and question ride beside the context
MAX_TEXT = 4000
LAYER_TITLES = (("source", "Sources"), ("bronze", "Landing"), ("silver", "Cleaned"), ("gold", "Report"))
GREETING = ("Hello {name}. I am Span, the architect. I have read the signed intent of work: {k} measures from {s} sources. "
            "Shall I draft the three layers first?")
SPAN_ROLE = ("You are Span, the solution architect of a small company with no data team. You talk with the company's architect, and the "
             "head of data approves what you draft. You turn the signed intent of work into a blueprint: the three-layer design, the data "
             "model, the scan of the landing files per measure, the agreed scope and the ETL mapping sheet.")
CHAT_PROMPT = """Talk in data terms (layers, grain, keys, conformed dimensions, history, lineage, reconciliation) but in plain words: \
at most four sentences and at most one question per reply. Propose a default instead of asking whenever the playbook has one. A \
decision you cannot take alone goes into questions for the head of data, with your proposed default and why. The intent of work is \
signed and read-only: a gap in it becomes a question, never a guess.

Reply with ONLY one JSON object:
{"reply": "what you say", "run": [steps], "data_model": [...], "questions": [...], "scope": [measure refs] or null, "ready": true or false}
run: any of "design", "scan", "mapping", in that order; the product drafts them with the existing tools and reports the result under \
your reply. design draws the three layers from the signed intent of work; scan reads the landing files per measure; mapping writes the \
ETL mapping sheet. Design comes first, scan before mapping. Do not repeat a step already done unless the person asks for a redraft.
data_model: only report tables you add or change, matched by table name: \
[{"table", "kind": "fact" or "dimension", "grain": "one row per ...", "keys": [], "relationships": ["joins dim_x on x_key"], \
"history": "", "measures": [measure refs]}].
questions: matched by question text: [{"question", "default", "why", "answer"}]; give answer only when the person settled it.
scope: the measures to build now, by ref, only those the scan found available or partly; null when unchanged.
ready: true when design, scan and mapping are done, every report table is in the data model and every open question has a default; \
then say it is ready for the head of data's approval.
Never write digits: write numbers and history types in words ("type two"). Never write ids or codes except measure refs in scope and \
measures. No text outside the JSON."""


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _s(v, limit: int = 600) -> str:
    return " ".join(str(v or "").split())[:limit]


def _ls(v, limit: int = 200) -> list[str]:
    return [_s(x, limit) for x in v if _s(x)] if isinstance(v, list) else []


def _norm(v) -> str:
    return _s(v).lower()


def _letters(i: int) -> str:
    return B3._letters(i)


# ---- records ---------------------------------------------------------------------------------------------------------------------

def _path(plane, iid: str):
    if not B1.IID.fullmatch(iid or ""):
        raise Refused(404, "There is no such intent.")
    return plane.path("build", "blueprint_conversation", f"{iid}.json")


def read(plane, iid: str) -> dict:
    try:
        rec = read_json_strict(_path(plane, iid), dict)
    except (OSError, ValueError):
        raise Refused(409, "Span's conversation cannot be read.") from None
    return rec or {"intent_id": iid, "turns": [], "state": "open", "approved_by": None, "approved_at": None,
                   "data_model": [], "questions": [], "scope": []}


def _sow(plane, iid: str, signed: bool = True) -> dict:
    try:
        sow = B1.read_sow(plane, iid)
    except B1.Refused as e:
        raise Refused(e.status, e.message) from None
    if signed and sow.get("state") != "signed":
        raise Refused(409, "Sign the intent of work first. Span builds from the signed version only.")
    return sow


def _sheet(plane, iid: str) -> dict:
    """G3: the benchmark sheet (rows), {} when there is none or it cannot be read."""
    try:
        from sh_platform.v1 import g3_sheet
        return g3_sheet.read(plane, iid)
    except Exception:  # noqa: BLE001 - another card's record; the design stands without it
        return {}


def _scan(plane, iid: str) -> dict | None:
    try:
        return B2.read_scan(plane, iid)
    except (OSError, ValueError):
        return None


def _mapping(plane, iid: str) -> dict | None:
    return B3.read(plane, iid)


def _kpis(sow: dict) -> list[dict]:
    return [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")]


def _alias(sow: dict) -> dict[str, str]:
    """{letter alias: KPI code}: digit-free refs the model can echo."""
    return {_letters(i): k["code"] for i, k in enumerate(_kpis(sow))}


def _turn(by: str, name: str, text: str, did: list[str] | None = None) -> dict:
    return {"id": _id("t"), "by": by, "name": name, "text": text, "at": _now(), "did": did or []}


# ---- the data model: Span's own, else read from the blueprint -------------------------------------------------------------------

def _from_blueprint(plane, sow: dict) -> list[dict]:
    """The blueprint's model (b1's rule-based draft) as data-model rows: facts and dimensions with grain, keys and relationships."""
    try:
        model = (read_json_strict(plane.path("build", "blueprint.json"), dict) or {}).get("model") or {}
    except (OSError, ValueError):
        return []
    names = {k["code"]: k.get("name") or k["code"] for k in _kpis(sow)}
    dims = [d for d in model.get("dimensions") or [] if isinstance(d, dict)]
    out = []
    for f in model.get("facts") or []:
        if not isinstance(f, dict):
            continue
        keys = [str(k) for k in f.get("keys") or []]
        out.append({"table": str(f.get("name") or ""), "kind": "fact", "grain": str(f.get("grain") or ""), "keys": keys,
                    "relationships": [f"joins {d.get('name')} on {k}" for d in dims for k in keys if k in (d.get("keys") or [])],
                    "history": "", "measures": [names.get(str(m), str(m)) for m in f.get("measures") or []]})
    for d in dims:
        ent = str(d.get("name") or "").removeprefix("dim_")
        out.append({"table": str(d.get("name") or ""), "kind": "dimension", "grain": f"one row per {ent}" + (" per change" if d.get("scd") == 2 else ""),
                    "keys": [str(k) for k in d.get("keys") or []], "relationships": [],
                    "history": "type two: a row per change" if d.get("scd") == 2 else "type one: overwrite", "measures": []})
    return out


# ---- what Span sees, and the model call -------------------------------------------------------------------------------------------

def context(plane, iid: str, sow: dict, rec: dict, files: list | None = None, viewer=None) -> dict:
    alias = _alias(sow)
    ref = {v: k for k, v in alias.items()}
    kname = {k["code"]: k.get("name") for k in _kpis(sow)}
    sname = {s.get("id"): s.get("name") for s in sow.get("sources") or [] if isinstance(s, dict)}
    design, scan, mapping = B1.read_design(plane, iid), _scan(plane, iid), _mapping(plane, iid)
    unclear_rows = [f"{r.get('target_table')}.{r.get('target_field')}: {r.get('transformation')}"
                    for r in ((mapping or {}).get("sheet") or {}).get("rows") or [] if r.get("status") == "unclear"]
    return fit({
        "intent_of_work": {
            "title": sow.get("title"), "goal": {k: (sow.get("goal") or {}).get(k) for k in ("line", "why", "readers", "needed_by")},
            "measures": [{"ref": ref[k["code"]], "name": k.get("name"), "definition": k.get("definition"), "formula": k.get("formula"),
                          "unit": k.get("unit"), "period": k.get("period"), "status": k.get("status"),
                          "sources": [sname.get(x) for x in k.get("source_ids") or [] if sname.get(x)]} for k in _kpis(sow)],
            "sources": [{"name": s.get("name"), "kind": s.get("kind"), "holds": s.get("holds"), "owner": s.get("owner"),
                         "fields": [f.get("name") for f in s.get("fields") or [] if isinstance(f, dict)][:30]}
                        for s in sow.get("sources") or [] if isinstance(s, dict)],
            "tables": [{"table": t.get("table"), "layer": t.get("layer"), "meaning": t.get("meaning"), "source": sname.get(t.get("source_id")),
                        "feeds": [kname.get(x) for x in t.get("feeds_kpis") or [] if kname.get(x)]}
                       for t in sow.get("catalogue") or [] if isinstance(t, dict)],
            "rules": [g.get("rule") for g in sow.get("governance") or [] if isinstance(g, dict)],
            "unclear": [u.get("question") for u in sow.get("unclear") or [] if isinstance(u, dict) and not u.get("settled")],
        },
        "benchmarks_to_meet": [{"measure": b.get("name"), "by": b.get("dims"), "period": b.get("period"), "expected": b.get("expected"),
                                "proposed": b.get("proposed")} for b in P4.for_design(sow, sheet=_sheet(plane, iid))],
        "steps_done": [s for s, ok in zip(STEPS, (design, scan, mapping)) if ok],
        "design": (design or {}).get("lines") or "not drafted yet",
        "scan": [{"ref": ref.get(k.get("code")), "status": k.get("status"), "missing": [m.get("what") for m in k.get("missing") or []]}
                 for k in (scan or {}).get("kpis") or [] if ref.get(k.get("code"))] or "not run yet",
        "mapping": {"rows": len(((mapping or {}).get("sheet") or {}).get("rows") or []), "unclear_rows": unclear_rows} if mapping else "not drafted yet",
        "data_model": [{**{k: t.get(k) for k in ("table", "kind", "grain", "keys", "relationships", "history")},
                        "measures": t.get("measures")} for t in rec.get("data_model") or []],
        "questions_for_head_of_data": [{k: q.get(k) for k in ("question", "default", "answer")} for q in rec.get("questions") or []],
        "scope_proposed": [ref[c] for c in rec.get("scope") or [] if c in ref],
        "earlier_turns": [{"by": t.get("name"), "text": t.get("text")} for t in rec["turns"][-13:-1]],
        "files_now": preview_for_agent(plane, iid, files or []),  # V1: what was dropped in this turn
        "library": library_lines(plane, iid, viewer),  # C4: the context-library items ticked for this conversation
        "company_rules": _rules(plane),  # T1: the company admin's governance rules, baked into the design
    }, (("earlier_turns", None), ("files_now", None), ("library", None), ("intent_of_work", "tables"), ("intent_of_work", "sources"), ("mapping", "unclear_rows")), limit=VIEW_LIMIT)


def _skill(plane=None) -> str:
    try:
        from sh_platform.v1.skill_loader import load_skill
        return load_skill("span", plane)
    except ImportError:  # X5's loader is missing: the skill folder is read directly
        from pathlib import Path
        d = Path(__file__).resolve().parents[2] / "skills" / "span"
        return "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md")))[:6000] if d.is_dir() else ""


def _rules(plane) -> list[str]:
    try:
        from sh_platform.v1 import t1_templates as T1
        return T1.governance_rules(plane)
    except Exception:  # noqa: BLE001 - no rules is the same as none set
        return []


def _skill_label(plane=None) -> str:
    try:
        from sh_platform.v1.skill_loader import skill_label
        return skill_label("span", plane)
    except ImportError:
        return "Architect playbook"


def ask(rt, plane, iid: str, sow: dict, rec: dict, latest: str, people: list[str], files: list | None = None, viewer=None) -> dict | None:
    """The model's answer as {reply, run, data_model, questions, scope, ready}, or None (then the fallback runs)."""
    ctx = context(plane, iid, sow, rec, files, viewer)
    question = f"LATEST MESSAGE FROM THE ARCHITECT: {latest}"
    wire = WIRE.Wire(plane, "span", viewer, latest, WIRE.intent_focus(plane, iid), WIRE.readable_paths(plane, iid, viewer), iid,
                     cap=19_000 - len(json.dumps(ctx)) - len(question) - 3000) if viewer is not None else None
    if wire:
        ctx.update(wire.sections())  # MEM2b: one context_for per turn: what we remember, related talks and decisions, document passages (outside material)
    ctx.update(L2.facts(plane, iid, ("design",)))  # L2: what waits for a yes, and what was turned down and why
    try:
        from sh_platform.v1.i6_chat import _facts  # figures the person said, so the number guard lets them through
        ctx["facts"] = _facts(ctx, question, [latest] + [str(t.get("text") or "") for t in rec["turns"][-13:]])
    except Exception:  # noqa: BLE001 - without facts the guard only rewrites more figures
        ctx["facts"] = []
    system = "\n\n".join(x for x in (SPAN_ROLE, "Your playbook:\n" + _skill(plane), CHAT_PROMPT) if x)
    register_names(plane, rt.company_name, people)
    rt = rt.routed("span", "reply", iid, plane, want_json=True, text=latest, files=bool(files))  # R1
    try:
        reg, _ = DT.registry(rt.gate, MODULE_ID, plane, iid, viewer, ctx["facts"])  # D1: search_documents and read_document
        if viewer is not None:  # LOOP-S: the shared read tools too (memory, definitions, tables, access); search_documents above is kept
            from sh_platform.v1.agent_tools import tools_for
            tools_for(plane, viewer, "span", module_id=MODULE_ID, iid=iid, registry=reg)
        from sh_platform.v1 import e6_trace
        with e6_trace.trace(e6_trace.turn_trace_id(plane, viewer, "span") if viewer is not None else None):  # hashed person, never a name
            res = run_agent(rt.model, reg, rt.company_id or plane.company_id, MODULE_ID, SPAN, system + "\n\n" + DT.PROMPT_LINE, ctx, question,
                            recorder=wire.recorder(rt.recorder) if wire else rt.recorder)
    except Exception:  # noqa: BLE001 - a model failure leaves the rule-based Span answering
        log.warning("Span's conversation call failed")
        return None
    if res.status != "done":
        return None
    a, b = (res.text or "").find("{"), (res.text or "").rfind("}")
    try:
        got = json.loads(res.text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        return None
    if not isinstance(got, dict) or not _s(got.get("reply")):
        return None
    alias = _alias(sow)
    return {"reply": _s(got["reply"], 1500), "run": [s for s in STEPS if s in (got.get("run") or [])],
            "data_model": got.get("data_model"), "questions": got.get("questions"),
            "scope": [alias[x] for x in got["scope"] if x in alias] if isinstance(got.get("scope"), list) else None,
            "ready": got.get("ready") is True, "alias": alias}


def _default_questions() -> list[dict]:
    """skills/span/questions.md lines "- question? Default: answer." as the rule-based Span's questions."""
    out = []
    for line in _skill().splitlines():
        q, sep, d = line.removeprefix("- ").partition(" Default: ")
        if line.startswith("- ") and sep:
            out.append({"question": q.strip(), "default": d.strip().rstrip("."), "why": "From the architect playbook."})
    return out


REDO = re.compile(r"\b(?:again|redraft|re-?run|re-?do)\b", re.I)


def fallback(plane, iid: str, sow: dict, rec: dict, text: str) -> dict:
    """No model: Span takes the next missing step (or the one the person asks to redo), then the data model, defaults and scope."""
    done = dict(zip(STEPS, (B1.read_design(plane, iid), _scan(plane, iid), _mapping(plane, iid))))
    redo = [s for s, w in (("design", r"design|layer"), ("scan", r"scan"), ("mapping", r"mapping|sheet")) if REDO.search(text) and re.search(w, text, re.I)]
    nxt = redo[:1] or [s for s in STEPS if not done[s]][:1]
    out = {"run": nxt, "data_model": None, "questions": None, "scope": None, "ready": False, "alias": _alias(sow)}
    if nxt == ["design"]:
        out["reply"] = "I will draft the three layers from the signed intent of work: landing as it arrives, cleaned, and a report table per measure."
    elif nxt == ["scan"]:
        out["reply"] = "Next I read the landing files against each measure, to see what can be built now."
    elif nxt == ["mapping"]:
        out["reply"] = ("I am writing the mapping sheet and the data model, with defaults for the head of data. Everything the scan found "
                        "available or partly available is proposed for the scope.")
        out["questions"] = [] if rec.get("questions") else _default_questions()
        out["ready"] = True
    else:
        out["reply"] = "Design, scan and mapping are drafted. The head of data can approve, or tell me what to redraft."
        out["ready"] = True
    return out


# ---- merging and running ------------------------------------------------------------------------------------------------------------

def merge(rec: dict, got: dict, sow: dict) -> None:
    names = {k["code"]: k.get("name") or k["code"] for k in _kpis(sow)}
    model = rec.setdefault("data_model", [])
    for it in got.get("data_model") or [] if isinstance(got.get("data_model"), list) else []:
        if not isinstance(it, dict) or not _s(it.get("table"), 120):
            continue
        row = next((t for t in model if _norm(t.get("table")) == _norm(it["table"])), None)
        if row is None:
            row = {"table": _s(it["table"], 120), "kind": "fact", "grain": "", "keys": [], "relationships": [], "history": "", "measures": []}
            model.append(row)
        if it.get("kind") in ("fact", "dimension"):
            row["kind"] = it["kind"]
        for f in ("grain", "history"):
            if _s(it.get(f)):
                row[f] = _s(it[f], 300)
        for f in ("keys", "relationships"):
            if _ls(it.get(f)):
                row[f] = _ls(it[f])
        ms = [names.get(got["alias"].get(m), "") for m in it.get("measures") or [] if isinstance(m, str)]
        if any(ms):
            row["measures"] = [m for m in ms if m]
    qs = rec.setdefault("questions", [])
    for it in got.get("questions") or [] if isinstance(got.get("questions"), list) else []:
        if not isinstance(it, dict) or not _s(it.get("question")):
            continue
        row = next((q for q in qs if _norm(q.get("question")) == _norm(it["question"])), None)
        if row is None:
            row = {"id": _id("q"), "question": _s(it["question"], 300), "default": "", "why": "", "answer": "", "settled": False}
            qs.append(row)
        for f in ("default", "why"):
            if _s(it.get(f)):
                row[f] = _s(it[f], 300)
        if _s(it.get("answer")):
            row["answer"], row["settled"] = _s(it["answer"], 300), True
    if got.get("scope"):
        rec["scope"] = list(dict.fromkeys(got["scope"]))


def propose_patch(plane, iid: str, rec: dict, got: dict, sow: dict, who: str) -> int:
    """L2: the model's data model, questions and scope wait for a yes. Returns how many changes."""
    import copy
    twin = copy.deepcopy(rec)
    merge(twin, got, sow)
    keep = ("data_model", "questions", "scope")
    changes = L2.diff({k: rec.get(k) for k in keep}, {k: twin.get(k) for k in keep})
    payload = {"got": {k: got.get(k) for k in (*keep, "alias")}, "who": who}
    return len(changes) if L2.propose(plane, iid, "design", None, changes, payload=payload) else 0


def apply_proposal(plane, iid: str, p: dict, who: str) -> None:
    """Accept: the same merge as before, on the live conversation record."""
    sow, path = _sow(plane, iid), _path(plane, iid)
    with lock_for(path):
        rec = read(plane, iid)
        if rec["state"] == "approved":
            raise Refused(409, "The design is approved and handed to Flow. It can no longer change here.")
        merge(rec, p["payload"]["got"], sow)
        write_json_atomic(path, rec)


def run_steps(plane, rt, iid: str, steps: list[str], by: str) -> list[str]:
    """Call b1, b2, b3 as asked; each returns one factual line for the turn. A refusal becomes the line, never a failed turn."""
    did = []
    for s in steps:
        try:
            if s == "design":
                d = B1.design(plane, rt, iid, by)
                c = d["counts"]
                did.append(f"Design drafted: {c['source']} sources, {c['bronze']} landing, {c['silver']} cleaned, {c['gold']} report tables.")
            elif s == "scan":
                k = B2.run_scan(plane, iid)["kpis"]
                n = lambda st: sum(1 for x in k if x["status"] == st)  # noqa: E731
                did.append(f"Scan: {n('available')} of {len(k)} measures available, {n('partly')} partly, {n('not')} not.")
            elif s == "mapping":
                sheet = B3.draft(plane, iid, rt)["sheet"]
                u = sum(1 for r in sheet["rows"] if r["status"] == "unclear")
                did.append(f"Mapping sheet version {sheet['version']}: {len(sheet['rows'])} rows, {u} unclear.")
        except (B1.Refused, B2.ScanError) as e:
            did.append(f"{s.capitalize()} not drafted: {e.message}")
        except (B3.NotFound, B3.Refusal) as e:
            did.append(f"Mapping not drafted: {e}")
    return did


def _available_scope(plane, iid: str) -> list[str]:
    return [k["code"] for k in (_scan(plane, iid) or {}).get("kpis") or [] if k.get("status") in ("available", "partly")]


def chat(plane, rt, iid: str, viewer, text: str, files: list[dict] | None = None) -> dict:
    """The architect's message and Span's reply. Returns the view."""
    from sh_platform.v1 import g1_access as G1; G1.check_agent(plane, iid, viewer, lambda m: Refused(403, m))  # G1: the agent reads a project's artefacts only for a person who may see it
    files = list(files or [])
    text = str(text or "").strip()[:MAX_TEXT] or added_line(files)
    if not text:
        raise Refused(400, "Write something to Span.")
    sow = _sow(plane, iid)
    path = _path(plane, iid)
    with lock_for(path):
        act = "architect" in seat_of(viewer)  # anyone may talk to Span; only the architect changes the design
        if act:
            L2.resolve_words(plane, iid, text, viewer.name, ("design",))  # L2: "yes" accepts what Span proposed, "no ..." turns it down with the reason
        rec = read(plane, iid)
        if rec["state"] == "approved":
            raise Refused(409, "The design is approved and handed to Flow. It can no longer change here.")
        rec["turns"].append(_turn("person", viewer.name, text, [f["name"] for f in files]))
        got = ask(rt, plane, iid, sow, rec, text, [viewer.name], files, viewer) if rt.model is not None else None
        name = SPAN if got else FALLBACK_NAME
        got = got or fallback(plane, iid, sow, rec, text)
        if not act:  # talk yes, act no: answered and kept, but nothing is run, merged or proposed
            MC.after_turn(plane, "span", viewer, iid, text, got["reply"], WIRE.intent_focus(plane, iid))  # talk yes, act no: it is still remembered
            rec["turns"].append(_turn("span", name, got["reply"] + " (The design is changed by the architect; I have noted what you said for them.)", []))
            write_json_atomic(path, rec)
            return view(plane, iid)
        did = run_steps(plane, rt, iid, got["run"], viewer.name or "The architect")
        if name == SPAN:  # L2: the model's patch waits for a yes; the rules-only answer applies as before
            if proposed := propose_patch(plane, iid, rec, got, sow, viewer.name):
                got["ready"], got["reply"] = False, (got["reply"] + L2.tail(proposed)).strip()
        else:
            merge(rec, got, sow)
        if ("mapping" in got["run"] or not rec.get("data_model")) and not L2.pending(plane, iid, ("design",)):  # L2: not under a proposed model
            rec["data_model"] = rec.get("data_model") or _from_blueprint(plane, sow)
        if not rec.get("scope"):
            rec["scope"] = _available_scope(plane, iid)
        done = B1.read_design(plane, iid) and _scan(plane, iid) and _mapping(plane, iid)
        rec["state"] = "ready" if got["ready"] and done else "open"
        if shown := MC.after_turn(plane, "span", viewer, iid, text, got["reply"], WIRE.intent_focus(plane, iid), model=rt.model):  # memory: kept, and said
            got["reply"] += " " + MEM.remember_line(shown)
        rec["turns"].append(_turn("span", name, got["reply"], did))
        write_json_atomic(path, rec)
    if rec["state"] == "ready":
        from sh_platform.v1 import g1_access as G1
        from sh_platform.v1 import p1_project as P1
        if prj := P1.for_intent(plane, iid):
            G1.join(plane, prj["id"], G1.head_of_data(plane), "head of data")  # G1: submitting the design brings the head of data onto the team
    return view(plane, iid)


def approve(plane, iid: str, viewer) -> dict:
    """The head of data approves the design and mapping for the engineer: defaults stand for unanswered questions, the scope is agreed
    (b2), and Span hands over to Flow through the room."""
    sow = _sow(plane, iid)
    path = _path(plane, iid)
    with lock_for(path):
        rec = read(plane, iid)
        if rec["state"] == "approved":
            raise Refused(409, "This design is already approved.")
        with __import__("contextlib").suppress(ImportError): from sh_platform.v1 import p1_project as P1; P1.check_sign(plane, iid, "design", viewer.name, lambda m: Refused(409, m))  # P1
        scan = _scan(plane, iid)
        if not (B1.read_design(plane, iid) and scan and _mapping(plane, iid)):
            raise Refused(409, "Span has not drafted the design, the scan and the mapping sheet yet.")
        if not scan.get("agreed"):
            status = {k["code"]: k["status"] for k in scan.get("kpis") or []}
            scope = [c for c in rec.get("scope") or [] if status.get(c) in ("available", "partly")] or _available_scope(plane, iid)
            if not scope:
                raise Refused(409, "No measure can be built from the files in hand yet, so there is no scope to agree.")
            try:
                scan = B2.agree(plane, iid, scope, viewer.name or "The head of data")
            except B2.ScanError as e:
                raise Refused(e.status, e.message) from None
        rec["scope"] = scan["agreed"]["scope"]
        try:  # the sheet follows the agreed scope: rows for measures left out go; person edits stay (b3 keeps them)
            B3.draft(plane, iid)
        except Exception:  # noqa: BLE001 - a failed redraft leaves the earlier sheet; the approval stands
            log.warning("the mapping sheet could not be redrafted to the agreed scope")
        for q in rec.get("questions") or []:
            if not q.get("settled"):
                q.update(answer=q.get("default") or "", settled=True, defaulted=True)
        rec.update(state="approved", approved_by=viewer.name, approved_at=_now())
        rec["benchmarks"] = P4.for_design(sow, sheet=_sheet(plane, iid))  # P4/G3: the design carries the benchmark sheet's rows, a proposed row only for a KPI the owner gave none
        rec["data_model"] = rec.get("data_model") or _from_blueprint(plane, sow)
        write_json_atomic(path, rec)
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    with __import__("contextlib").suppress(Exception): from sh_platform.v1 import p1_project as P1; P1.comment(plane, iid, "design", None, "span", "builder", f"{viewer.name} approved the design and the mapping sheet. Please load from the build pack.", kind="handover")  # P1
    try:
        from sh_platform.v1 import room
        names = {k["code"]: k.get("name") for k in _kpis(sow)}
        room.post(plane, iid, "span", "handover",
                  f"{viewer.name} approved the design and the mapping sheet. Flow, please load: {', '.join(names.get(c, c) for c in rec['scope'])}.",
                  to=["flow", "people"], refs=[{"kind": "mapping", "id": iid}, {"kind": "scan", "id": iid}])
    except Exception:  # noqa: BLE001 - a missing room never breaks the approval
        log.warning("the room post for Span's approval failed")
    return view(plane, iid)


# ---- the view ---------------------------------------------------------------------------------------------------------------------

def layers(plane, iid: str, sow: dict) -> dict:
    """The design record's data components for this intent, as four columns (sources, landing, cleaned, report) and their links:
    the Archify layered view the Design tab draws."""
    comps = [c for c in A.read(plane)["components"] if c.get("view") == "data"]
    mine = {c["id"] for c in comps if c.get("from") == f"intents/{iid}/sow.json"}
    mine |= {i["to"] for c in comps if c["id"] in mine for i in c.get("interfaces") or []}
    mine |= {f"gold:{k['code'].lower()}" for k in _kpis(sow)}
    keep = [c for c in comps if c["id"] in mine]
    cols = [{"kind": k, "title": t, "items": [{"id": c["id"], "label": "Restricted" if c.get("restricted") else c.get("label") or c["id"],
                                                 "about": "" if c.get("restricted") else ((c.get("description") or {}).get("text") or "")}
                                                for c in keep if c.get("kind") == k]} for k, t in LAYER_TITLES]
    ids = {c["id"] for c in keep}
    links = [{"from": c["id"], "to": i["to"]} for c in keep for i in c.get("interfaces") or [] if i.get("to") in ids]
    return {"columns": cols, "links": links}


def summary(rec: dict, sow: dict, design, scan, mapping) -> list[str]:
    names = {k["code"]: k.get("name") or k["code"] for k in _kpis(sow)}
    rows = ((mapping or {}).get("sheet") or {}).get("rows") or []
    open_q = [q for q in rec.get("questions") or [] if not q.get("settled")]
    out = []
    if design:
        c = design.get("counts") or {}
        out.append(f"Three layers: {c.get('bronze', 0)} landing, {c.get('silver', 0)} cleaned, {c.get('gold', 0)} report tables.")
    out.append(f"Data model: {len(rec.get('data_model') or [])} tables.")
    if scan:
        out.append("Scope: " + (", ".join(names.get(c, c) for c in rec.get("scope") or []) or "nothing buildable yet") + ".")
    if mapping:
        out.append(f"Mapping sheet: {len(rows)} rows, {sum(1 for r in rows if r.get('status') == 'unclear')} unclear.")
    bm = P4.for_design(sow)
    if bm:
        n = sum(1 for b in bm if b["proposed"])
        out.append(f"Benchmarks: {len(bm) - n} from the intent of work, {n} proposed for the raiser to confirm against the first load.")
    out.append(f"Questions for the head of data: {len(open_q)} open; approving accepts Span's defaults." if open_q else "No open questions.")
    return out


def _proposals(plane, iid: str) -> dict:
    try:
        return L2.view(plane, iid)
    except L2.Refused:
        return {"pending": [], "recent": []}


def view(plane, iid: str, viewer=None) -> dict:
    sow = _sow(plane, iid, signed=False)
    rec = read(plane, iid)
    design, scan, mapping = B1.read_design(plane, iid), _scan(plane, iid), _mapping(plane, iid)
    names = {k["code"]: k.get("name") or k["code"] for k in _kpis(sow)}
    rows = ((mapping or {}).get("sheet") or {}).get("rows") or []
    first = ((viewer.name if viewer else "") or "").split(" ")[0] or "there"
    return {
        "intent_id": iid, "title": sow.get("title") or iid, "skill": _skill_label(plane),
        "sow": {"state": sow.get("state"), "version": sow.get("version"), "signature": sow.get("signature"),
                "kpis": [{"code": k["code"], "name": names[k["code"]], "status": k.get("status")} for k in _kpis(sow)],
                "sources": [{"id": s.get("id"), "name": s.get("name"), "kind": s.get("kind")} for s in sow.get("sources") or [] if isinstance(s, dict)],
                "catalogue": [{"table": t.get("table"), "layer": t.get("layer"), "meaning": t.get("meaning")}
                              for t in sow.get("catalogue") or [] if isinstance(t, dict)]},
        "turns": rec["turns"], "state": rec["state"], "approved_by": rec.get("approved_by"), "approved_at": rec.get("approved_at"),
        "greeting": "" if rec["turns"] else GREETING.format(name=first, k=len(names), s=len(sow.get("sources") or [])),
        "data_model": rec.get("data_model") or _from_blueprint(plane, sow), "questions": rec.get("questions") or [],
        "scope": rec.get("scope") or [],
        "design": {k: design.get(k) for k in ("lines", "fallback", "message", "counts", "at")} if design else None,
        "layers": layers(plane, iid, sow) if design else None,
        "scan": {"kpis": [{**k, "name": names.get(k.get("code"), k.get("code"))} for k in scan.get("kpis") or []],
                 "agreed": scan.get("agreed")} if scan else None,
        "mapping": {"version": mapping["sheet"].get("version"), "rows": len(rows), "unclear": sum(1 for r in rows if r.get("status") == "unclear"),
                    "fallback": mapping.get("fallback")} if mapping else None,
        "summary": summary(rec, sow, design, scan, mapping),
        "benchmarks": rec.get("benchmarks") or P4.for_design(sow, sheet=_sheet(plane, iid)),
        "amendments": rec.get("amendments") or [],  # G4: approved deviations, signed by the head of data
        "proposals": _proposals(plane, iid),
    }
