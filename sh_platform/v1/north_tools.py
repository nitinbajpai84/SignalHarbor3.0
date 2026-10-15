"""North's own tools for the agent loop: read the intents the person may see, and propose checked drafts.

Read tools (`list_intents`, `get_intent`, `get_process_map`, `list_sources`) are filtered by what the signed-in person may read
(G1) and return plain text lines, so no bare number reaches the registry's aggregate rule. Propose tools
(`propose_intent_section`, `propose_process_step`) only check their arguments and return the cleaned draft; `i6_chat.ask` turns
the drafts into the same proposals the conversation already shows, and the person accepts them there. Nothing is written here.
"""
from __future__ import annotations

import re

from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.jsonfile import read_json_strict
from sh_platform.intents import store as S
from sh_platform.v1 import egress_fit, g1_access
from sh_platform.v1 import k8_sop as K8

MODULE = "m1_intent"
MAX_ITEMS = 40
PROMPT_LINE = ("Work in steps: plan what you need, call tools (list_intents, get_intent, get_process_map, list_sources, the document "
               "and memory tools), check what came back, then answer. Never state a figure that no tool or the context returned. "
               "To suggest a change to the draft call propose_intent_section "
               "or propose_process_step: they only draft, the person accepts. For a question about a "
               "figure, a document, a person or what was said before, call a tool before you answer, and if nothing holds it say what is "
               "missing and who can tell them. Your final answer is plain text holding the JSON object.")
# propose_intent_section: section -> (key in sow_patch, the fields allowed, the field that names the row, fields that are lists)
SECTIONS = {
    "goal": ("goal", ("line", "why", "readers", "decisions", "needed_by"), None, ("readers", "decisions")),
    "kpi": ("kpis", ("name", "definition", "formula", "unit", "period", "owner", "sources", "benchmark", "benchmark_by"), "name",
            ("sources", "benchmark_by")),
    "source": ("sources", ("name", "holds", "owner", "structure", "arrives", "samples", "kind"), "name", ("samples",)),
    "governance": ("governance", ("rule", "applies_to", "kind"), "rule", ("applies_to",)),
    "open_question": ("unclear", ("question", "about", "who_can_settle"), "question", ()),
}
# NU-06: the names a model reaches for (the JSON answer's own keys, plurals) mean the same section
ALIASES = {"kpis": "kpi", "figure": "kpi", "figures": "kpi", "sources": "source", "input": "source", "inputs": "source",
           "rule": "governance", "rules": "governance", "unclear": "open_question", "open_questions": "open_question",
           "question": "open_question", "questions": "open_question", "goals": "goal"}
CHOICES = {"benchmark": ("given", "none"), "kind": ("system", "file", "document", "access", "retention", "approval"),
           "structure": ("structured", "unstructured")}
TEMPLATE_KEYS = ("result", "success")  # FIXD: template sections the person states in words; any other key goes as section template_fields
REFUSALS_BEFORE_STOP = 3
STOP = (" Stop calling this tool for this turn: put the change in sow_patch (or process_steps) of your final JSON answer instead, "
        "or say in your reply what you could not draft.")
STEP_FIELDS = ("name", "who", "does", "system", "control", "exception", "manual")


def _text(v, name: str, limit: int, empty: bool = True) -> str:
    if not isinstance(v, str):
        raise ToolRefused(f"{name} must be text.")
    v = " ".join(v.split())
    if not v and not empty:
        raise ToolRefused(f"{name} must not be empty.")
    if len(v) > limit:
        raise ToolRefused(f"{name} must be at most {limit} characters.")
    return v


class NorthTools:
    def __init__(self, plane, viewer, iid: str):
        self.plane, self.viewer, self.iid = plane, viewer, iid

    def _sow(self, intent_id: str) -> dict:
        """The SOW of an intent this person may read ('' means this conversation); anything else looks the same: not found."""
        iid = _text(intent_id, "intent_id", 64) or self.iid
        if not S.ID_RE.fullmatch(iid) or not g1_access.can_read_intent(self.plane, self.viewer, iid):
            raise ToolRefused("intent_id is not an intent you may read.")
        try:
            sow = read_json_strict(self.plane.path("intents", iid, "sow.json"), dict)
        except (OSError, ValueError):
            sow = None
        if not sow:
            raise ToolRefused("intent_id is not an intent you may read.")
        return sow

    # ---- read ---------------------------------------------------------------------------------------------------------------
    def list_intents(self) -> dict:
        out = []
        for p in sorted(self.plane.path("intents").glob("*/sow.json")):
            iid = p.parent.name
            if not S.ID_RE.fullmatch(iid) or not g1_access.can_read_intent(self.plane, self.viewer, iid):
                continue
            try:
                sow = read_json_strict(p, dict) or {}
            except (OSError, ValueError):
                continue
            state = "signed" if sow.get("state") == "signed" else "draft"
            out.append(f"{iid}: {str(sow.get('title') or 'Untitled')[:120]} ({state})")
        return {"intents": out[:MAX_ITEMS], "more": "yes" if len(out) > MAX_ITEMS else "no"}

    def get_intent(self, intent_id) -> dict:
        s = self._sow(intent_id)
        goal = s.get("goal") if isinstance(s.get("goal"), dict) else {}
        rows = lambda k, f: [str(r.get(f) or "")[:120] for r in (s.get(k) or []) if isinstance(r, dict)][:MAX_ITEMS]  # noqa: E731
        sig = s.get("signature") if isinstance(s.get("signature"), dict) else {}
        # EG2: flatten turns a goal list of records (readers, decisions) into lines, so the gateway never sees raw rows
        return egress_fit.flatten({"title": str(s.get("title") or "")[:300], "state": "signed" if s.get("state") == "signed" else "draft",
                "signed_by": str(sig.get("name") or sig.get("by") or "") if s.get("state") == "signed" else "",
                "goal": {k: (goal.get(k) if isinstance(goal.get(k), list) else str(goal.get(k) or ""))
                         for k in SECTIONS["goal"][1]},
                "kpis": rows("kpis", "name"), "sources": rows("sources", "name"), "governance": rows("governance", "rule"),
                "template_fields": {str(k)[:80]: str(v)[:200] for k, v in (s.get("template_fields") or {}).items() if v},
                "open_questions": [str(r.get("question") or "")[:200] for r in (s.get("unclear") or [])
                                   if isinstance(r, dict) and not r.get("settled")][:MAX_ITEMS]})

    def get_process_map(self, intent_id) -> dict:
        sow = self._sow(intent_id)
        steps = (sow.get("process") or {}).get("steps") or []
        signed = {" ".join(str(r.get("name") or "").lower().split()) for r in steps if isinstance(r, dict)}
        if not str(intent_id or "").strip() or intent_id == self.iid:  # NI2-07: this conversation's map includes the steps waiting for a yes
            try:
                from sh_platform.v1 import i6_chat
                steps = (i6_chat.with_pending(self.plane, self.iid, sow).get("process") or {}).get("steps") or steps
            except Exception:  # noqa: BLE001 - the accepted map is still an answer
                pass
        lines = []
        for i, r in enumerate(x for x in steps if isinstance(x, dict)):
            wait = " (drafted, waiting for a yes)" if " ".join(str(r.get("name") or "").lower().split()) not in signed else ""
            system = str(r.get("system") or "")
            manual = K8.is_manual(r) or (not isinstance(r.get("manual"), bool) and not system)  # no flag and no system: done by hand
            lines.append(f"step {i + 1}: {str(r.get('name') or '')[:120]}{wait} | owner: {str(r.get('who') or 'not said')[:80]} | "
                         f"system: {system[:80] or 'none'} | manual: {'yes' if manual else 'no'}"
                         + (f" | control: {str(r['control'])[:160]}" if r.get("control") else "")
                         + (f" | exception: {str(r['exception'])[:160]}" if r.get("exception") else ""))
        return {"steps": lines[:MAX_ITEMS]}

    def list_sources(self, intent_id) -> dict:
        src = self._sow(intent_id).get("sources") or []
        return {"sources": [f"{str(r.get('name') or '')[:120]} | owner: {str(r.get('owner') or 'not said')[:80]} | "
                            f"arrives: {str(r.get('arrives') or 'not said')[:60]} | sample present: "
                            f"{'yes' if r.get('sample_path') or r.get('samples') else 'no'}"
                            for r in src if isinstance(r, dict)][:MAX_ITEMS]}

    # ---- propose (check and return; nothing is written) -----------------------------------------------------------------------
    def _refused(self, e: ToolRefused):
        """NU-06: a model that keeps sending arguments the tool cannot take is told, after a few tries, to stop and answer instead."""
        self.refusals = getattr(self, "refusals", 0) + 1
        return ToolRefused(str(e) + STOP) if self.refusals >= REFUSALS_BEFORE_STOP else e

    def propose_intent_section(self, section, content) -> dict:
        try:
            return self._section(section, content)
        except ToolRefused as e:
            raise self._refused(e) from None

    def _section(self, section, content) -> dict:
        section = ALIASES.get(str(section or "").strip().lower(), str(section or "").strip().lower())
        if section in TEMPLATE_KEYS or section == "template_fields":
            return self._template(section, content)
        if section not in SECTIONS:
            raise ToolRefused(f"section must be one of: {', '.join(SECTIONS)}.")
        key, fields, name_field, lists = SECTIONS[section]
        rows = content if isinstance(content, list) and key != "goal" else [content]  # NU-06: several rows of one section in one call
        if not rows or len(rows) > 10 or not all(isinstance(r, dict) and r for r in rows):
            raise ToolRefused("content must be an object of fields.")
        out = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                if k not in fields or v in (None, "", []):
                    continue  # NU-06: a field this section does not keep is left out, never a refusal of the whole draft
                if k in lists:
                    v = [v] if isinstance(v, str) else v
                    if not isinstance(v, list) or len(v) > 10:
                        raise ToolRefused(f"{k} must be a list of at most 10 texts.")
                    clean[k] = [_text(x, k, 200, False) for x in v]
                elif k in CHOICES:
                    if str(v).strip().lower() in CHOICES[k]:
                        clean[k] = str(v).strip().lower()
                else:
                    clean[k] = _text(v, k, 600)
            if not clean:
                raise ToolRefused(f"content may only hold: {', '.join(fields)}.")
            if name_field and not clean.get(name_field):
                raise ToolRefused(f"content must include {name_field}.")
            out.append(clean)
        if self._sow("").get("state") == "signed":
            raise ToolRefused("section cannot change: the intent of work is signed.")
        return {"kind": "sow", "section": section, "sow_patch": {key: out[0] if key == "goal" else out}}

    def _template(self, section, content) -> dict:
        """FIXD: a template section with no table of its own ("What the result looks like", "How you will know it worked"), in the
        person's words: {"result": "..."} or, for section result or success, the text itself."""
        if section != "template_fields":
            content = {section: content.get("text") or content.get(section) if isinstance(content, dict) else content}
        if not isinstance(content, dict) or not content:
            raise ToolRefused("content must be an object of template keys and texts.")
        out = {}
        for k, v in content.items():
            if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", k):
                raise ToolRefused("a template key must be a short word such as result or success.")
            out[k] = _text(v, k, 600, False)
        if self._sow("").get("state") == "signed":
            raise ToolRefused("section cannot change: the intent of work is signed.")
        return {"kind": "sow", "section": "template_fields", "sow_patch": {"template_fields": out}}

    def propose_process_step(self, name, who, does, system, control, exception, manual, handover_to_next) -> dict:
        try:
            return self._step(name, who, does, system, control, exception, manual, handover_to_next)
        except ToolRefused as e:
            raise self._refused(e) from None

    def _step(self, name, who, does, system, control, exception, manual, handover_to_next) -> dict:
        """ER-13, NI-13: a step carries its control, its known exception and whether it is done by hand, as the person or the note says."""
        flag = {True: "yes", False: "no"}.get(manual) if isinstance(manual, bool) else _text(manual, "manual", 5).lower()
        flag = {"true": "yes", "false": "no", "y": "yes", "n": "no"}.get(flag, flag)
        if flag not in ("yes", "no", ""):
            raise ToolRefused("manual must be yes, no or empty.")
        step = {"name": _text(name, "name", 120, False), "who": _text(who, "who", 120), "does": _text(does, "does", 600),
                "system": _text(system, "system", 120), "control": _text(control, "control", 300),
                "exception": _text(exception, "exception", 300), "handover": _text(handover_to_next, "handover_to_next", 300)}
        if flag:
            step["manual"] = flag == "yes"
        if self._sow("").get("state") == "signed":
            raise ToolRefused("step cannot change: the intent of work is signed.")
        return {"kind": "process_step", "step": {k: v for k, v in step.items() if v or v is False}}


def register(reg: ToolRegistry, plane, viewer, iid: str) -> ToolRegistry:
    t = NorthTools(plane, viewer, iid)
    idp = {"intent_id": "string"}
    note = " intent_id: its id from list_intents, or empty for this conversation."
    for name, fn, params, text in (
        ("list_intents", t.list_intents, {}, "The intents you may see: id, title and whether it is signed or draft."),
        ("get_intent", t.get_intent, idp, "One intent's title, state (signed or draft), goal, KPI, source and rule names and open questions." + note),
        ("get_process_map", t.get_process_map, idp, "The process map's swim-lane steps: owner, system and whether the step is manual." + note),
        ("list_sources", t.list_sources, idp, "The data sources of an intent: owner, how often it arrives, whether a sample is present." + note)):
        reg.register(MODULE, name, fn, read_only=True, description=text, parameters=params)
    reg.register(MODULE, "propose_intent_section", t.propose_intent_section, read_only=False, proposes=True,
                 parameters={"section": "string", "content": "object"},
                 description="Draft a change for the person to accept. section: goal, kpi, source, governance, open_question, result (what the "
                             "result looks like) or success (how they will know it worked); "
                             "content: an object of that section's fields, or a list of such objects for several rows (goal: line, why, "
                             "readers, decisions, needed_by; kpi: name, definition, formula, unit, period, owner, sources, benchmark, "
                             "benchmark_by; source: name, holds, owner, structure, arrives, samples, kind; governance: rule, applies_to, "
                             "kind; open_question: question, about, who_can_settle; result or success: {\"text\": the person's words}).")
    reg.register(MODULE, "propose_process_step", t.propose_process_step, read_only=False, proposes=True,
                 parameters={"name": "string", "who": "string", "does": "string", "system": "string", "control": "string",
                             "exception": "string", "manual": "string", "handover_to_next": "string"},
                 description="Draft one process step for the person to accept. who: the owner's name as written; system: the tool used, "
                             "or empty; control: the check on this step as stated, or empty; exception: what happens when it goes wrong as "
                             "stated, or empty; manual: yes when done by hand (a spreadsheet, a file drop, an email, downloading, pasting or "
                             "typing figures in), no when a system does it, empty only when nothing says; "
                             "handover_to_next: how the work passes to the next step (who to whom, by what), or empty. Call it once per step, in order.")
    return reg
