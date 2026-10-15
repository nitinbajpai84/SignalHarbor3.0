"""North groups the submitted notes into named problem clusters (M1-18), on the kernel agent runtime.

Ported from the earlier North's gather (emitters/intent_sessions.py `run_gather` 751-815 and the `session_gather` prompt,
emitters/catalogue_chat.py 230-238): one grouping call over every submitted note, a fenced json reply, ids checked
against what was sent, a pack problem id kept only if it was offered. Changed for this kernel: the call goes through
the egress runtime; the notes and the pack's problems go in as plain text lines (never a list of objects, which the
gateway reads as rows: the lesson of 3 October); a note that fits no group stays on its own instead of an "Ungrouped"
group; the label of each note is a short one (n1, n2...), so the model never sees or invents a real id.

The model sees the notes' words only: no author, no name field, no time, no position. Names inside the words are
tokenised by the gateway. Every run is recorded by the kernel without content.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from modules.m1_intent.domain import private_room as R
from modules.m1_intent.domain.board import BoardSettings
from modules.m1_intent.tools.pack_tools import MODULE_ID, Guidance
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry

log = logging.getLogger(__name__)
AGENT_NAME = "North"
RULES_FILE = Path(__file__).with_name("gather_rules.yaml")
PACK_PROBLEMS_SHOWN = 20  # the same as the earlier gather
MAX_ROUNDS = 5  # calls when replies keep being cut off at the model's output limit (live Gemini: 1-2 groups a call)
_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)


@dataclass
class Grouping:
    """`groups`: North's own groups as read (labels already mapped back to note ids). `ok` is False when the model
    could not answer or answered something unreadable: the board then shows every note on its own."""
    ok: bool
    groups: list[dict] = field(default_factory=list)
    message: str | None = None
    problem_ids: set[str] = field(default_factory=set)


def load_rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def system_prompt(north: dict | None = None) -> str:
    rules = load_rules()
    role = str((north or {}).get("advisor_role") or "").strip() or "the industry expert"
    return "\n\n".join([rules["role"].strip().format(advisor_role=role), "Rules:\n" + "\n".join(f"- {r}" for r in rules["rules"]),
                        "Reply shape: " + rules["reply_shape"].strip().format()])


def build_question(s: BoardSettings, notes: list[dict], guidance: Guidance) -> tuple[str, dict[str, str]]:
    """(the plain-text instruction, label -> note id). One line per note, one per pack problem; notes beyond the size
    budget are left out here and stay on their own on the board."""
    labels: dict[str, str] = {}
    lines = ["Notes to group (label: the person's words):"]
    spent = 0
    for n in notes:
        text = " ".join(n["text"].split())[:s.note_chars_sent]
        if spent + len(text) > s.notes_chars_sent:
            break
        spent += len(text)
        labels[f"n{len(labels) + 1}"] = n["id"]
        lines.append(f"- n{len(labels)}: {text}")
    problems = [p for p in guidance.problems if p.get("id") and p.get("question")][:PACK_PROBLEMS_SHOWN]
    if problems:
        lines.append("Problems in this industry's pack, as candidate wording (id: question):")
        lines += [f"- {p['id']}: {' '.join(str(p['question']).split())}" for p in problems]
    return "\n".join(lines), labels


def parse(text: str, labels: dict[str, str]) -> list[dict] | None:
    """The groups in the reply with labels mapped back to note ids; None when no readable json block is there."""
    raw = _group_objects(text)
    if raw is None:
        return None
    by_label = {k.lower(): v for k, v in labels.items()}
    return [{"name": g.get("name"), "pack_problem_id": g.get("pack_problem_id"), "reasoning": g.get("reasoning"),
             "note_ids": [by_label[str(x).strip().lower()] for x in g.get("note_ids") or [] if str(x).strip().lower() in by_label]}
            for g in raw]


def _group_objects(text: str) -> list[dict] | None:
    """The group objects in the reply: fences and prose around them ignored, a top-level object or array both fine, and
    a reply cut off by the model's output limit (live Gemini, 4 October) still gives every group that was complete.
    None when no array of groups is there at all."""
    t = _FENCE.sub("", text or "")
    start = t.find("[", max(t.find('"groups"'), 0))
    if start < 0:
        return None
    dec, pos, out = json.JSONDecoder(), start + 1, []
    while (j := t.find("{", pos)) >= 0:
        try:
            obj, pos = dec.raw_decode(t, j)
        except ValueError:
            break  # a group cut off half way is left out; its notes stay on their own
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _complete(text: str) -> bool:
    """True when the reply holds one whole json object or array (not cut off)."""
    t = _FENCE.sub("", text or "")
    i = min((j for j in (t.find("{"), t.find("[")) if j >= 0), default=-1)
    try:
        json.JSONDecoder().raw_decode(t, i)
    except ValueError:
        return False
    return i >= 0


def group_notes(model, gate, recorder, company_id: str, s: BoardSettings, notes: list[dict], guidance: Guidance) -> Grouping:
    """One grouping call over the submitted notes (`notes` are public records). No notes: no model call."""
    rules = load_rules()
    if not notes:
        return Grouping(True, [], rules["messages"]["none_to_group"])
    if model is None:
        return Grouping(False, [], rules["messages"]["unavailable"])
    # the notes' own figures may be repeated by the number guard; the context is one small object, no list of records
    ctx = {"stage": "board", "facts": R.figures(*(n["text"] for n in notes))}
    groups, left, complete = [], notes, False
    for _ in range(MAX_ROUNDS):
        question, labels = build_question(s, left, guidance)
        res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, system_prompt(guidance.north or None),
                        ctx, question, recorder=recorder)
        got = parse(res.text, labels) if res.status == "done" else None
        if got is None:
            log.warning("North's grouping could not be used (%s)", res.status)
            break
        groups += got
        complete = _complete(res.text)
        taken = {i for g in got for i in g["note_ids"]}
        left = [n for n in left if n["id"] not in taken]
        # a reply cut off by the model's output limit is asked again, over the notes still ungrouped
        if complete or len(left) < s.min_notes:
            break
    if not groups and not complete:
        return Grouping(False, [], rules["messages"]["failed"])
    return Grouping(True, groups, None, {str(p["id"]) for p in guidance.problems if p.get("id")})
