"""North's read-only tools and grounding (M1-10, M1-13, M1-P04c): industry practice and the problem library, from the
company's own industry pack only, through the pack loader. Registered in the kernel tool registry under module
m1_intent, so a company that does not own the module has no tools (the registry checks the entitlement on every
listing and call).

What North may offer comes from the pack's kpi_tree, industry_defaults, glossary, problems and north files, matched
to what the person said. A tool result holds words only: pack text labelled as a suggestion, never a figure (the
number guard still applies to what North says). No pack, or no match: an empty answer, never an error and never
another industry's content.
"""
import logging
from dataclasses import dataclass, field

import yaml

from modules.m1_intent.domain import private_room as R
from sh_platform.agents.registry import ToolRegistry
from sh_platform.packs import EmptyPack

log = logging.getLogger(__name__)
MODULE_ID = "m1_intent"
MAX_MATCHES = 3
_LIBRARY_CAP = 30
_SUGGESTIONS_SHOWN = 6
NOTHING_MATCHED = "nothing_matched: no industry practice fits what the person said."
NO_GUIDANCE = "No industry guidance is available yet for this company's industry."


@dataclass
class Guidance:
    """The company's pack as North uses it. Empty for an industry with no pack."""
    pack: object
    problems: list = field(default_factory=list)
    kpis: list = field(default_factory=list)
    defaults: dict = field(default_factory=dict)
    terms: list = field(default_factory=list)
    north: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        """The industry's name as its pack gives it (its pack.yaml label); empty with no pack."""
        return str(getattr(self.pack, "label", "") or "")

    @property
    def has_content(self) -> bool:
        return bool(self.problems or self.kpis or self.terms)


def _rows(pack, section: str, key: str) -> list:
    if pack.empty or section not in pack.sections():
        return []
    try:
        raw = pack.section(section)
    except (KeyError, OSError, ValueError, yaml.YAMLError):
        log.warning("a pack file could not be read")
        return []
    rows = raw.get(key) if isinstance(raw, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def load_guidance(packs, industry) -> Guidance:
    """Never raises: a missing, damaged or industry-less pack is an empty guidance."""
    try:
        pack = packs.load(str(industry or ""))
    except ValueError:
        pack = EmptyPack(str(industry or ""))  # an industry that cannot be a pack name has no pack
    north = {}
    if not pack.empty and "north" in pack.sections():
        try:
            north = pack.section("north")
        except (KeyError, OSError, ValueError, yaml.YAMLError):
            log.warning("a pack file could not be read")
    defaults = {d.get("kpi_id"): d for d in _rows(pack, "industry_defaults", "defaults") if d.get("kpi_id")}
    return Guidance(pack, _rows(pack, "problems", "problems"), _rows(pack, "kpi_tree", "kpis"), defaults,
                    _rows(pack, "glossary", "terms"), north if isinstance(north, dict) else {})


# the pack's intent_examples file keeps one list of plain examples for each kind of note beyond an intent
SUGGESTION_KEYS = {"pain_point": "pain_point_examples", "future_signal": "future_signal_examples", "lever": "lever_examples"}


def kind_suggestions(g: Guidance) -> dict[str, list[str]]:
    """What others in the industry usually raise for each kind of note, from the company's own pack: {kind: [text]}.
    Every kind is present; the lists are empty with no pack or no such file. Words only, always shown as a suggestion."""
    raw = {}
    if not g.pack.empty and "intent_examples" in g.pack.sections():
        try:
            raw = g.pack.section("intent_examples")
        except (KeyError, OSError, ValueError, yaml.YAMLError):
            log.warning("a pack file could not be read")
    raw = raw if isinstance(raw, dict) else {}
    return {kind: [x.strip() for x in raw.get(key) or [] if isinstance(x, str) and x.strip()][:_SUGGESTIONS_SHOWN]
            for kind, key in SUGGESTION_KEYS.items()}


def load_problems(packs, industry) -> tuple[object, list[dict]]:
    g = load_guidance(packs, industry)
    return g.pack, g.problems


def ground(g: Guidance, texts: list[str], decides: bool = True) -> dict:
    """What the pack offers for what the person said, labelled as a suggestion: matching KPIs (with how the
    industry usually defines, refreshes and splits them, and what the company must decide), the matching problem's
    belief to test and usual actions, and glossary terms. Words only; no ids, no figures. What the company must decide
    (the pack's customer_decides questions) is offered for the best-matching measure only, and only when `decides`
    (the match was made on the person's latest message): a lesser match would ask an off-topic question."""
    texts = [t for t in texts if t]
    offers = R.kpi_offers(g.kpis, g.defaults, texts)
    kpi_ids = {o["id"] for o in offers}
    card = R.match_practice(g.problems, " ".join(texts))
    chosen = [p for p in g.problems if (card and p.get("id") == card["problem_id"]) or kpi_ids & set(p.get("kpi_ids") or [])]
    problems = {}
    for p in chosen[:MAX_MATCHES]:
        problems[R.plain(p.get("question"))] = {
            "belief_to_test": R.plain(p.get("belief_to_test")),
            "usually_tracked": [v for v in (R.plain(i) for i in R._items(p)) if v],
            "usually_split_by": [str(b) for b in p.get("breakdowns") or []][:6]}
    out = {"label": R.PRACTICE_LABEL, "note": R.COMPANY_DECIDES,
           "kpis": {o["name"]: {k: v for k, v in o.items() if k not in ("id", "name") and v and (k != "your_company_decides" or (decides and i == 0))}
                    for i, o in enumerate(offers)},
           "problems": problems, "terms": {t["term"]: t["definition"] for t in R.term_offers(g.terms, texts)}}
    return out if offers or problems or out["terms"] else {"nothing_matched": True}


def _join(v) -> str:
    return ", ".join(map(str, v)) if isinstance(v, list) else str(v)


def ground_text(g: Guidance, texts: list[str], decides: bool = True) -> str:
    """`ground` as labelled plain text, one line per offer. The model is sent text, never lists of objects: the egress
    gateway refuses a JSON list of two or more objects as rows."""
    out = ground(g, texts, decides)
    if out.get("nothing_matched"):
        return NOTHING_MATCHED
    def line(kind, name, fields):
        return f"{R.PRACTICE_LABEL} - {kind}: {name}: " + "; ".join(f"{k.replace('_', ' ')} {_join(v)}" for k, v in fields.items() if v)
    lines = [line("KPI", n, k) for n, k in out["kpis"].items()] + [line("problem", n, p) for n, p in out["problems"].items()]
    lines += [f"{R.PRACTICE_LABEL} - term: {t}: {d}" for t, d in out["terms"].items()]
    return "\n".join(lines)  # no closing "Your company decides." line: the model copied it onto nearly every reply; tidy_reply adds it once


def register_north_tools(registry: ToolRegistry, g: Guidance, *, practice: bool, library: bool,
                         facts: list | None = None) -> None:
    """Only the tools the organiser switched on for this session are registered. `facts` collects the figures in
    what the practice tool returned, so the number guard lets North repeat them."""
    if practice:
        def industry_practice(topic: str) -> dict:
            text = ground_text(g, [str(topic)])
            if facts is not None:
                facts.extend(R.figures(text))
            return {"nothing_matched": True} if text == NOTHING_MATCHED else {"label": R.PRACTICE_LABEL, "text": text}
        registry.register(MODULE_ID, "industry_practice", industry_practice, read_only=True,
                          description="What others in the industry usually track for a kind of problem, from the company's industry pack: "
                                      "matching measures (KPIs) with how they are usually defined, refreshed and split, and what the company "
                                      "must decide. A suggestion only; the company decides. Says nothing_matched when nothing fits.",
                          parameters={"topic": "the person's own words about the problem or measure"})
    if library:
        def problem_library() -> dict:
            return {"label": R.PRACTICE_LABEL, "problems": [p["text"] for p in R.library_list(g.problems)[:_LIBRARY_CAP]]}
        registry.register(MODULE_ID, "problem_library", problem_library, read_only=True,
                          description="Common problems in the company's industry, from its pack, as a suggestion the person may choose from.",
                          parameters={})
