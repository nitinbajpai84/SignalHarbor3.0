"""The company's own pack as Lens reads it (kpi_tree, industry_defaults, glossary, problems), through the pack loader.
Copied and trimmed from modules/m1_intent/tools/pack_tools.py (`load_guidance`, `_rows`, `ground_text`): a module may
not import another module, so the few lines live here. An industry with no pack is an empty Guidance, never another
industry's content. Text for the model is plain labelled lines, never lists of objects (the gateway reads those as rows).
"""
import logging
import re
from dataclasses import dataclass, field

import yaml

from sh_platform.packs import EmptyPack

log = logging.getLogger(__name__)
LABEL = "Industry practice (suggestion)"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and are as at be by for from has have how in is it of on or that the this to was were what "
                  "when where which who will with we our".split())


@dataclass
class Guidance:
    pack: object
    kpis: list = field(default_factory=list)
    defaults: dict = field(default_factory=dict)
    terms: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return str(getattr(self.pack, "label", "") or "")

    @property
    def has_content(self) -> bool:
        return bool(self.kpis)


_LABEL_FRAGMENT = re.compile(r"\(?\bIndustry practice(?:\s*\(suggestion\))?\)?\s*[:.;,\-]*\s*", re.IGNORECASE)


def strip_label(text: str) -> str:
    """The label belongs in its own field (the value's source), never inside a sentence of the definition."""
    return " ".join(_LABEL_FRAGMENT.sub(" ", text).split()).strip(" ;,-")


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
        pack = EmptyPack(str(industry or ""))
    defaults = {d.get("kpi_id"): d for d in _rows(pack, "industry_defaults", "defaults") if d.get("kpi_id")}
    return Guidance(pack, [k for k in _rows(pack, "kpi_tree", "kpis") if k.get("id") and isinstance(k.get("name"), str)],
                    defaults, _rows(pack, "glossary", "terms"), _rows(pack, "problems", "problems"))


def _stem(w: str) -> str:
    """calls and call, exposure and exposures and exposed, are one stem; the first five letters then fold the rest."""
    for suffix in ("ing", "ed", "es", "s", "e"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            break
    return w[:5]


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(str(text).lower()) if len(w) > 2 and w not in _STOP}


def kpi_by_id(g: Guidance, kpi_id) -> dict | None:
    return next((k for k in g.kpis if k["id"] == kpi_id), None)


def _words_of(problem: dict) -> set[str]:
    notes = problem.get("notes")
    return _stems(" ".join([str(problem.get("title") or ""), str(problem.get("so_that") or ""),
                            " ".join(map(str, notes)) if isinstance(notes, list) else str(notes or "")]))


def _pack_problem_words(p: dict) -> set[str]:
    """What a pack problem is about: its question, decision, belief, typical actions and what the customer decides."""
    parts = [p.get("question"), p.get("decision"), p.get("belief_to_test")]
    for key in ("typical_actions", "customer_decides"):
        v = p.get(key)
        parts += (v.get("items") if isinstance(v, dict) else v) if isinstance(v, (dict, list)) else [v]
    return _stems(" ".join(str(x) for x in parts if isinstance(x, str)))


def _kpi_ids_of(p: dict) -> list:
    """The measures a pack problem serves: its own kpi_ids, then the related_kpi_ids the pack adds for measures that help without being its core."""
    return [i for key in ("kpi_ids", "related_kpi_ids") for i in p.get(key) or []]


def matching_pack_problems(g: Guidance, problem: dict) -> list[dict]:
    """The pack problems a custom charter problem most resembles: the best by shared word stems with its title and notes
    (at least two shared, or one that no other pack problem uses; ties all count). A suggestion, never a link: only a
    person's confirmation links."""
    words = [(p, _pack_problem_words(p)) for p in g.problems]
    words = [(p, w) for p, w in words if _kpi_ids_of(p)]  # a pack problem that names no measure can win nothing: it would only hide the ones that do
    uses = {s: sum(1 for _, w in words if s in w) for _, w in words for s in w}
    for mine in (_stems(problem.get("title") or ""), _words_of(problem)):  # the title says what the problem is; notes only when the title matches nothing
        scored = [(len(mine & w), p) for p, w in words if len(mine & w) >= 2 or any(uses[s] == 1 for s in mine & w)]
        if scored:
            top = max(n for n, _ in scored)
            return [p for n, p in scored if n == top]
    return []


def kpis_for_problem(g: Guidance, problem: dict) -> list[dict]:
    """The pack KPIs that serve one charter problem: those its library problem lists; with no library problem, those of the
    pack problems it shares words with (matching_pack_problems), else the KPIs whose name shares two word stems with its title."""
    lib = next((p for p in g.problems if p.get("id") == problem.get("library_problem_id")), None)
    libs = [lib] if lib is not None else matching_pack_problems(g, problem)
    if libs:
        ids = dict.fromkeys(i for p in libs for i in _kpi_ids_of(p))
        return [k for i in ids if (k := kpi_by_id(g, i))]
    mine = _stems(f"{problem.get('title', '')} {problem.get('so_that') or ''}")
    return [k for k in g.kpis if len(mine & _stems(k["name"])) >= 2]


def pack_definition(g: Guidance, kpi_id) -> str:
    """The pack's plain statement of how the industry defines the KPI; "" when it has none."""
    for v in (g.defaults.get(kpi_id) or {}).get("definition_variants") or []:
        t = v.get("variant") if isinstance(v, dict) else None
        if isinstance(t, str) and t.strip() and not t.startswith("This pack"):
            return strip_label(t)
    k = kpi_by_id(g, kpi_id) or {}
    return strip_label(str(k.get("definition") or ""))


def formula_question(name: str) -> str:
    return f"What is the formula for {name}? Lens does not invent formulas, so the business needs to say."


def customer_questions(g: Guidance, kpi_id) -> list[str]:
    """What only the business can answer: the pack's customer_decides, and a formula question when the pack has no
    formula (Lens never invents a formula)."""
    out = []
    for q in (g.defaults.get(kpi_id) or {}).get("customer_decides") or []:
        t = q.get("question") if isinstance(q, dict) else q
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
    k = kpi_by_id(g, kpi_id) or {}
    if k and not k.get("formula"):
        out.append(formula_question(k["name"]))
    return out


def propose_kpis(g: Guidance, problems: list, taken: set) -> list[dict]:
    """What Lens suggests the charter's problems need measured, from the pack's KPI tree: one suggestion per KPI, linked
    to every problem it serves. Nothing is a KPI until a person confirms it; those already confirmed are left out."""
    out: dict[str, dict] = {}
    for p in problems:
        for k in kpis_for_problem(g, p):
            if k["id"] not in taken:
                s = out.setdefault(k["id"], {"id": k["id"], "name": k["name"], "problem_ids": [], "priority": p.get("priority")})
                s["problem_ids"].append(p["id"])
    return list(out.values())


def retrieval_query(g: Guidance, kpi_id, name: str, problem_titles: list) -> str:
    """What to look for in the company's documents for one measure: its name, the pack's keywords for it (words the
    industry uses for the same thing) and the titles of the problems it serves."""
    kw = (kpi_by_id(g, kpi_id) or {}).get("keywords")
    return " ".join([name, *(map(str, kw) if isinstance(kw, list) else []), *map(str, problem_titles)])


def pack_text(g: Guidance, kpi_id) -> str:
    """One KPI's pack entry as labelled plain text for the model."""
    k, d = kpi_by_id(g, kpi_id) or {}, g.defaults.get(kpi_id) or {}
    first = f"{LABEL} - KPI: {k.get('name', '')}: definition {pack_definition(g, kpi_id)}"
    if d.get("cadence"):
        first += f"; usually refreshed {d['cadence']}"
    mine = _stems(k.get("name", ""))
    terms = [f"{LABEL} - term: {t['term']}: {t['definition']}" for t in g.terms
             if isinstance(t.get("term"), str) and isinstance(t.get("definition"), str) and mine & _stems(t["term"])]
    return "\n".join([first, *terms[:3]])
