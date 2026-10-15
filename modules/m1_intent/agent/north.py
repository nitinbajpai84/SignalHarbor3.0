"""North, the industry expert, in a private room (M1-08, M1-10, M1-13, M1-P04c), on the kernel agent runtime.

North's model reaches the outside only through the egress client (production) or a stub (tests). The kernel
runs the tool loop, applies the number guard and records the run (no prompt, answer, name or figure in it).
What the person said is the only source of figures North may repeat: it goes in as the `question`, and the
guard replaces any other number in the reply. The note read-back is not North's to word: the room puts the
person's own words back, so North's reply is a short recommended draft and at most one question.

By default North listens and checks: it reads the note back and asks at most one question, with no industry
suggestion. The pack grounding below is added only when the organiser's practice switch is on or the person asks
how others do it (`ask_how_others`).

Every turn is grounded on the company's pack (kpi_tree, industry_defaults, glossary, problems), matched to what the
person said: it goes in as `industry_guidance` (labelled plain text), labelled as a suggestion. The wording that belongs to one industry
(advisor role, peers, usual breakdowns, domain rules) is the pack's north.yaml, never code.
"""
import json
import re
from pathlib import Path

import yaml

from modules.m1_intent.domain import private_room as R
from modules.m1_intent.tools.pack_tools import MODULE_ID, NO_GUIDANCE, NOTHING_MATCHED, Guidance, ground_text, register_north_tools
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry

AGENT_NAME = "North"
RULES_FILE = Path(__file__).with_name("north_rules.yaml")
EARLIER_REPLIES = 6   # how much of North's own side of the conversation it is shown again
EARLIER_PERSON = 8    # how much of the person's side (also what the number guard counts as given by the person)
GROUNDED_ON = 4       # how many of the person's latest messages the pack is matched against
SAY_SOMETHING_NEW = " NOTE: your last reply was the same as the one before. Say something new."
_DEFAULT_WORDING = {"advisor_role": "the industry expert", "peers": "others in the industry",
                    "typical_breakdowns": "the usual ways of splitting the figures"}


# the question handed to the model is only the person's latest message, labelled; earlier turns are background
LATEST = "LATEST MESSAGE FROM THE PERSON (answer this one; the earlier turns in the context are only background):"
_ASKS_OTHERS = re.compile(r"\b(usually|typically|normally|commonly|most (?:family offices|firms|companies|offices)|"
                          r"others|other (?:family offices|firms|companies|offices)|peers|industry (?:norm|practice|standard)|best practice)\b", re.I)
_QUESTION = re.compile(r"^\s*(?:who|what|which|how|is there|are there|do|does|should|can)\b[^?]*\?", re.I)  # a real question, not "And then?"


def load_rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def _wording(north: dict | None) -> dict:
    return {k: str(north[k]).strip() if north and north.get(k) else v for k, v in _DEFAULT_WORDING.items()}


def system_prompt(*, practice: bool, library: bool, north: dict | None = None, has_pack: bool = True,
                  documents: bool = False) -> str:
    """`practice` is the organiser's switch; `north` is the pack's north.yaml (None: no pack)."""
    rules, w = load_rules(), _wording(north)
    parts = [rules["role"].strip().format(**w), "Rules:\n" + "\n".join(f"- {r}" for r in rules["rules"])]
    # what a person may bring besides what they intend to do now (pain points, what to watch in future, levers): said in every
    # session, with or without a pack, in plain business words; the industry's own examples come only with practice on
    parts.append("What else to hear about, in turn:\n" + "\n".join(f"- {r}" for r in rules["themes_rules"])
                 + "\n" + "\n".join(f"- {q}" for q in rules["themes"].values()))
    parts.append("The kind of each note:\n" + "\n".join(f"- {r}" for r in rules["kind_rules"]))
    if not practice:
        parts.append("Listen and check:\n" + "\n".join(f"- {r}" for r in rules["listen_rules"]))
    if not has_pack:  # said whatever the organiser's switch: a company with no pack is told, never left guessing
        parts.append("Industry practice:\n" + "\n".join(f"- {r}" for r in rules["no_guidance_rules"]))
    elif practice:
        advisor = [r.format(**w) for r in rules["advisor_rules"]]
        if north and north.get("example_data_line"):
            advisor.append(rules["example_rule"].format(example_data_line=str(north["example_data_line"]).strip().rstrip(".")))
        if north and all(north.get(k) for k in ("example_pain_line", "example_signal_line", "example_lever_line")):
            advisor.append(rules["theme_example_rule"].format(pain=str(north["example_pain_line"]).strip().rstrip("."),
                                                              signal=str(north["example_signal_line"]).strip().rstrip("."),
                                                              lever=str(north["example_lever_line"]).strip().rstrip(".")))
        advisor += rules["practice_rules"]
        parts.append("Industry practice:\n" + "\n".join(f"- {r}" for r in advisor))
        own = [str(r).strip() for r in (north or {}).get("rules") or [] if str(r).strip()]
        if own:
            parts.append("Rules for this industry:\n" + "\n".join(f"- {r}" for r in own))
    if library:
        parts.append("Problem library:\n" + "\n".join(f"- {r}" for r in rules["library_rules"]))
    if documents:
        parts.append("Company documents:\n" + "\n".join(f"- {r}" for r in rules["documents_rules"]))
    return "\n\n".join(parts)


def build_registry(gate, guidance: Guidance, *, practice: bool, library: bool, facts: list | None = None) -> ToolRegistry:
    registry = ToolRegistry(gate)
    register_north_tools(registry, guidance, practice=practice and guidance.has_content,
                         library=library and bool(guidance.problems), facts=facts)
    return registry


def next_question(model, gate, company_id: str, guidance: Guidance, turns: list[dict], *, practice: bool,
                  library: bool, recorder=None, company_name: str = "", ask_how_others: bool = False,
                  documents: str = "", background: str = "") -> tuple[str, bool]:
    """(North's reply, answered). `turns` ends with the person's message. When the model cannot answer the reply
    is the runtime's plain message and `answered` is False (the person's note is already saved)."""
    # listen and check is the default: pack grounding only when the organiser's switch (the session stance) allows
    # suggestions, or the person explicitly asks how others do it
    person = [t["text"] for t in turns if t["role"] == "person"][-EARLIER_PERSON:]
    latest = person[-1] if person else ""
    # a question about the work is a request for what the industry usually does, so it needs no switch
    practice = practice or ask_how_others or bool(_ASKS_OTHERS.search(latest) or _QUESTION.search(latest))
    context = {"company": company_name, "industry": guidance.label,
               "background_earlier_person_messages": person[:-1],
               "background_earlier_north_replies": [t["text"] for t in turns if t["role"] == "north" and t.get("answered", True)][-EARLIER_REPLIES:],
               "tools": {"industry_practice": practice and guidance.has_content,
                         "problem_library": library and bool(guidance.problems)}}
    context["facts"] = R.figures(*person)  # the person's number words ("six"); the tool adds pack figures as it runs
    if not guidance.has_content:
        context["industry_guidance"] = {"none_for_this_industry": True, "note": NO_GUIDANCE}
    elif practice:
        # the latest message first (it is the question); the earlier ones only when it matched nothing on its own, and
        # then without the pack's "what the company decides" question: it was matched to older words, not this message
        text = ground_text(guidance, [latest])
        context["industry_guidance"] = ground_text(guidance, person[-GROUNDED_ON:], decides=False) if text == NOTHING_MATCHED else text  # text, not lists of objects: see ground_text
        # a figure in the grounded pack text may be repeated; any other figure is replaced by the guard
        context["facts"] += R.figures(context["industry_guidance"])
    if documents:  # D-032: passages already wrapped as untrusted plain text; never added to the facts the guard trusts
        context["company_documents"] = documents
    if background:  # MEM-2: what North remembers, already wrapped as background (memory.summarise.background); never added to the facts
        context["background_memory"] = background
    prompt = system_prompt(practice=practice, library=library, north=guidance.north or None, has_pack=guidance.has_content,
                           documents=bool(documents))
    registry = build_registry(gate, guidance, practice=practice, library=library, facts=context["facts"])
    earlier = [t["text"] for t in turns if t["role"] == "north" and t.get("answered", True)]
    said_before = R.said_decides(earlier)

    def ask(extra: str = "") -> tuple[str, bool]:
        res = run_agent(model, registry, company_id, MODULE_ID, AGENT_NAME, prompt, context, f"{LATEST} {latest}{extra}",
                        recorder=recorder)  # a space, not a newline: JSON writes a newline as backslash-n, which glues to a name after it
        if res.status != "done":
            return res.text, False
        return R.tidy_reply(res.text, said_before), True

    def same(r: str) -> bool:
        return bool(earlier) and (R.same_reply(r, earlier[-1]) or R.same_reply(move_on(r, earlier), earlier[-1]))

    reply, answered = ask()
    if answered and same(reply):  # never the same reply twice in a row
        reply, answered = ask(SAY_SOMETHING_NEW)  # a failed second try is shown as the plain failure
        if answered and same(reply):
            return R.read_back(latest), answered
    return (move_on(reply, earlier) if answered else reply), answered


_ECHO = re.compile(r"^\s*(?:so\s+)?(?:you(?:'re|\s+are)\s+(?:again\s+)?(?:emphasi[sz]ing|stating|saying|repeating|noting|highlighting|stressing|describing|mentioning|explaining|pointing\s+out|telling\s+me)"
                   r"|you(?:'ve|\s+have)?\s+said\s+again)\b", re.I)
_FIRST_SENTENCE = re.compile(r"^[^.?!]*[.?!]+\s*")


def _opening(text: str) -> str:
    first = _FIRST_SENTENCE.match((text or "").strip())
    return " ".join(re.findall(r"[a-z']+", (first.group(0) if first else text or "").lower())[:3])


def move_on(reply: str, earlier: list[str]) -> str:
    """North never opens two replies the same way and never parrots: a first sentence that echoes the person ("You're emphasizing
    ...", "So you are saying ...") or opens like North's previous reply is dropped, so the reply goes straight on to its question.
    The reply is kept whole when that sentence is all there is."""
    if not (_ECHO.match(reply or "") or (earlier and _opening(reply) == _opening(earlier[-1]))):
        return reply
    rest = _FIRST_SENTENCE.sub("", reply.strip(), count=1).strip()
    return rest[:1].upper() + rest[1:] if rest else reply


CARDS_PROMPT = (
    "You are North, the industry expert. Read what this person said in their private conversation and write the note cards they "
    "would otherwise have to type: one card for each separate thing they raised, at most {limit}. Reply with ONLY one JSON object "
    "{{\"notes\": [{{\"text\": ..., \"kind\": ..., \"fields\": {{...}}}}]}}. text is the person's own words, shortened. kind is one of: "
    "intent (something they intend to do now), pain_point (something that hurts today), future_signal (something to keep an eye "
    "on in future) or lever (something they change to move a KPI). fields holds only what they said, with these ids for each "
    "kind: {kinds}. Never invent a problem, a figure, a name or a rule. Never give a number for what the person believes. "
    "Leave a field out when they did not speak to it. If they raised nothing new, reply {{\"notes\": []}}. No text outside the JSON."
)


def propose_cards(model, gate, company_id: str, turns: list[dict], kinds_help: list[str], limit: int, recorder=None) -> list[dict]:
    """North's note cards from the person's conversation (LI-M1): [{text, kind, fields}], or [] when the model cannot answer.
    Only the person's own side of the conversation goes in, with the numbers they said as the only facts the guard trusts. The
    cards are suggestions: the room makes drafts of them and the person confirms each (domain/interview_notes.card_note)."""
    person = [t["text"] for t in turns if t["role"] == "person"][-EARLIER_PERSON:]
    if not person:
        return []
    registry = build_registry(gate, [], practice=False, library=False)
    res = run_agent(model, registry, company_id, MODULE_ID, AGENT_NAME, CARDS_PROMPT.format(limit=limit, kinds="; ".join(kinds_help)),
                    {"conversation": person, "facts": R.figures(*person)}, "Write the note cards.", recorder=recorder)
    start, end = res.text.find("{"), res.text.rfind("}")
    try:
        data = json.loads(res.text[start:end + 1]) if res.status == "done" and 0 <= start < end else {}
    except ValueError:
        return []
    rows = data.get("notes") if isinstance(data, dict) else None
    return [r for r in rows if isinstance(r, dict)][:limit] if isinstance(rows, list) else []


DRAFT_PROMPT = (
    "You are North, the industry expert. Read what this person said in their private conversation. If they have said both what one "
    "thing is (a measure they track now, something missing that hurts, something to keep an eye on, or a lever they change to move a "
    "KPI) and where it bites (who feels it, how often, what it costs), write ONE wall card for it. Reply with ONLY one JSON object "
    "{{\"kind\": ..., \"what\": ..., \"where\": ..., \"track\": ..., \"define\": ...}}. kind is one of: intent, pain_point, "
    "future_signal, lever. what: {q1} where: {q2} track: {q3} define: {q4} Use the person's own words, shortened. Leave track or define "
    "as \"\" when they did not speak to it. "
    "Never invent a problem, a figure, a name or a rule. If they have not yet said both what it is and where it bites, reply "
    "{{\"kind\": null}}. No text outside the JSON."
)


_DRAFT_KEYS = {"q1": "what", "q2": "where", "q3": "track", "q4": "define"}  # words, not q1..q4: the number guard rewrites digits


def draft_card(model, gate, company_id: str, said: list[str], leads: dict[str, str], recorder=None) -> dict | None:
    """One wall card North drafts from what the person has said since their last card: {kind, q1..q4}, or None when they have not yet
    said what it is and where it bites (or the model cannot answer). The room keeps it as a draft the person confirms."""
    if not said:
        return None
    registry = build_registry(gate, [], practice=False, library=False)
    res = run_agent(model, registry, company_id, MODULE_ID, AGENT_NAME, DRAFT_PROMPT.format(**leads),
                    {"conversation": said[-EARLIER_PERSON:], "facts": R.figures(*said)}, "Write the card, or say not yet.", recorder=recorder)
    start, end = res.text.find("{"), res.text.rfind("}")
    try:
        data = json.loads(res.text[start:end + 1]) if res.status == "done" and 0 <= start < end else {}
    except ValueError:
        return None
    got = {"kind": data.get("kind"), **{q: data.get(k) for q, k in _DRAFT_KEYS.items()}} if isinstance(data, dict) else {}
    return got if all(isinstance(got.get(q), str) and got[q].strip() for q in ("q1", "q2")) else None
