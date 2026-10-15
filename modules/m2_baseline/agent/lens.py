"""Lens, the business analyst, on the kernel agent runtime (M2-03, M2-P01).

Lens reaches the outside only through the egress client (production) or a stub (tests); the kernel runs the loop,
applies the number guard and records the run (no prompt, answer, name or figure in it). Lens has no tools: what it
is shown is the company's own pack text for one KPI and, when the company uploaded documents, the few relevant
passages (the pre-read, D-032), both as plain text, never as lists of objects. Its reply is only ever a draft: the
caller stores it as a "guessed" value, never "stated".
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from modules.m2_baseline.agent.pack_text import strip_label
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.context_docs.retrieval import INTRO, retrieve, whole_sentences, wrap_untrusted
from sh_platform.context_docs import documents_for
from sh_platform.context_docs.store import DocStore
from sh_platform.egress.names import STOP_WORDS, protected_names
from sh_platform.egress.vault import NameVault, VaultUnavailable
from sh_platform.plane import CrossCompanyError

log = logging.getLogger(__name__)

AGENT_NAME = "Lens"
MODULE_ID = "m2_baseline"
RULES_FILE = Path(__file__).with_name("lens_rules.yaml")
NO_DEFINITION = "NO DEFINITION"
MAX_DEFINITION = 600
MAX_ANSWER = 900
DOCUMENT_AGENT = "lens"  # Lens reads her own shelf plus the other agents' shared documents (sh_platform.context_docs `documents_for`)
_NUMBER_WORDS = {w: str(i) for i, w in enumerate("one two three four five six seven eight nine ten eleven twelve".split(), 1)}
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?|\b(?:" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def load_rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def system_prompt(*, documents: bool, conversation: bool = False, technical: bool = False) -> str:
    r = load_rules()
    parts = [r["role"].strip(), "Rules:\n" + "\n".join(f"- {x}" for x in r["rules"]),
             ("Talking with a person:\n" + "\n".join(f"- {x}" for x in r["conversation_rules"])) if conversation else
             ("The technical definition:\n" + "\n".join(f"- {x}" for x in r["technical_rules"])) if technical else
             "Drafting a definition:\n" + "\n".join(f"- {x}" for x in r["draft_rules"])]
    if documents:
        parts.append("Company documents:\n" + "\n".join(f"- {x}" for x in r["documents_rules"]))
    return "\n\n".join(parts)


def figures(*texts: str) -> list[dict]:
    """The figures in the text the model was shown, as facts for the number guard ("six" counts as 6): they are the
    pack's, never the company's own. Copied from modules/m1_intent/domain/private_room.py `figures`."""
    seen = {_NUMBER_WORDS.get(m.group().lower(), m.group().rstrip(",")) for m in _FIGURE.finditer(" ".join(t for t in texts if t))}
    return [{"id": "shown", "label": "figure in the text shown", "value": v, "group_size": 5} for v in sorted(seen)]


def _plain(text: str) -> str:
    """A line that starts like JSON gets a quote mark, so a JSON file can never be read by the gateway as records."""
    return "\n".join(f"> {ln}" if ln.lstrip()[:1] in ("{", "[") else ln for ln in text.splitlines())


class _WithRestricted(DocStore):
    """The store as a person allowed to see a restricted measure (pay, HR) may use it: restricted documents count too."""

    def own_chunks(self, agent: str) -> list[dict]:
        return [{"title": d["title"], "text": c["text"], "location": c.get("location"), "source": "own_document",
                 "restricted": bool(d.get("restricted"))} for d in documents_for(self.plane, agent, restricted_ok=True) for c in d.get("chunks", [])]


def preread(plane, query: str, *, restricted_ok: bool = False) -> tuple[str, list[str]]:
    """(plain quoted passages, their document titles) from the company's uploaded documents that fit `query`;
    ("", []) when there are none or the store cannot be read. A document problem never stops Lens. A restricted
    document is read only with restricted_ok, which the caller sets for a restricted measure the asker may see:
    its draft is then kept on that measure, which nobody else sees."""
    try:
        hits = retrieve((_WithRestricted if restricted_ok else DocStore)(plane), DOCUMENT_AGENT, query)
    except (OSError, ValueError, CrossCompanyError):
        return "", []
    hits = [{**h, "text": whole_sentences(h["text"])} if h.get("restricted") else h for h in hits]  # pay text: whole sentences, no figures
    hits = [h for h in hits if h.get("title") and h["text"]]
    if not hits:
        return "", []
    text = "\n\n".join([INTRO] + [wrap_untrusted(_plain(h["text"]), " ".join(str(h["title"]).split())[:80]) for h in hits])
    return text, list(dict.fromkeys(" ".join(str(h["title"]).split())[:80] for h in hits))


LENS_NOTE = "Lens could not reach the model just now; these are the pack's suggestions."
NO_MODEL_NOTE = "Lens could not read your documents because no model is set up for your company; these are the industry pack's suggestions."
NO_MODEL_ASK = "I cannot talk it through yet: no model is set up for your company. The definitions and questions in this block still work."


def nothing_note(names: list[str]) -> str:
    """The plain words for measures that no document and no industry text could define: Lens asks the person instead."""
    return f"Lens found nothing in your documents or the industry text that says what {', '.join(f'“{n}”' for n in names)} means, so it will ask you."


class ModelUnreachable(Exception):
    """The model call was refused (by the egress gateway, say) or failed: the person is told, never silently served the pack."""


def converse(model, gate, company_id: str, *, company_name: str, industry: str, facts: str, documents: str, question: str,
             recorder=None, background: str = "") -> str | None:
    """Lens's answer to one typed question, from `facts` (plain lines of what is recorded for the asker), the pack and the
    passages of the documents the asker may use. Raises ModelUnreachable on a refused or failed call; None when it had no answer."""
    context = {"company": company_name, "industry": industry, "baseline_facts": facts, "facts": figures(facts)}
    if documents:
        context["company_documents"] = documents
    if background:
        context["background_memory"] = background  # MEM-2: wrapped as background by memory.summarise.background
    res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME,
                    system_prompt(documents=bool(documents), conversation=True), context, question, recorder=recorder)
    if res.status in ("refused", "error"):
        raise ModelUnreachable
    text = " ".join(res.text.split())
    return text[:MAX_ANSWER] if res.status == "done" and text else None


FIELD_LABELS = {"DEFINITION": "definition", "OWNER": "owner", "PRODUCER": "producer", "GATHERED": "gathered"}
_LABELLED = re.compile(r"\b(DEFINITION|OWNER|PRODUCER|GATHERED):")
FILL = ("Draft the definition of: {name}. From the passages, also fill what they say about the likely owner, who produces the data "
        "and how it is gathered. Reply as four labelled lines: DEFINITION: ... OWNER: ... PRODUCER: ... GATHERED: ... "
        "Write UNKNOWN for anything the passages do not say.")


def parse_fields(text: str) -> dict:
    """{definition, owner, producer, gathered} the reply filled; a reply with no labels is a plain definition. UNKNOWN fills nothing."""
    flat = " ".join(text.split())
    parts = _LABELLED.split(flat)
    pairs = [("DEFINITION", flat)] if len(parts) == 1 else list(zip(parts[1::2], parts[2::2]))
    out = {}
    for label, value in pairs:
        value = strip_label(value.strip(" ;"))
        if value and not value.upper().startswith(("UNKNOWN", NO_DEFINITION)):
            out[FIELD_LABELS[label]] = value[:MAX_DEFINITION]
    return out


def draft_fields(model, gate, company_id: str, *, company_name: str, industry: str, kpi_name: str, pack: str,
                 documents: str, recorder=None, instruction: str = "", current: str = "") -> dict:
    """What the company's passages and the pack text say about one KPI: {definition, owner, producer, gathered}, only the parts
    they say ({} when they say nothing). Raises ModelUnreachable when the call was refused or failed. Plain text, never a
    list of objects. With `instruction` (what the person asked to change) and `current` it redrafts the definition alone."""
    context = {"company": company_name, "industry": industry, "kpi": kpi_name, "industry_guidance": pack,
               "facts": figures(pack, instruction, current)}
    if documents:
        context["company_documents"] = documents  # plain text, marked untrusted; never added to the facts

    def ask(prompt: str) -> dict:
        res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, system_prompt(documents=bool(documents)),
                        context, prompt, recorder=recorder)
        if res.status in ("refused", "error"):
            raise ModelUnreachable
        if res.status != "done" or res.numbers_replaced:
            return {}  # a figure the guard replaced leaves "not available yet" in the text: never saved
        return parse_fields(res.text)

    if instruction:
        got = ask(f"Redraft the definition of: {kpi_name}. Current wording: {current or 'none yet'}. The person asks: {instruction}")
        return {k: v for k, v in got.items() if k == "definition"}
    first = FILL.format(name=kpi_name) if documents else f"Draft the definition of: {kpi_name}"
    got = ask(first)
    if got.get("definition") and is_thin(got["definition"]):  # one retry: a line that only restates the name tells the owner nothing
        got = {**got, **ask(f"{first} Your last line only restated the name: say what is counted and how.")}
    return got


MAX_TECHNICAL = 4000


def draft_technical(model, gate, company_id: str, *, company_name: str, industry: str, kpi_name: str, definition: str, pack: str, catalogue: str,
                    documents: str, recorder=None, instruction: str = "", current: str = "") -> str | None:
    """ONE model call for one measure's technical definition and the open questions it finds (M2-E1): the labelled reply text (read by
    domain/technical.parse_reply), or None when the reply was empty or a figure it stated was not in what it was shown (the number guard).
    `catalogue` is plain lines about the rows this person may see that feed the measure; `documents` the passages. With `instruction`
    and `current` it redrafts as the person asked. Raises ModelUnreachable when the call was refused or failed."""
    context = {"company": company_name, "industry": industry, "kpi": kpi_name, "business_definition": definition, "industry_guidance": pack,
               "catalogue_rows": catalogue, "facts": figures(pack, definition, catalogue, instruction, current, documents)}
    if documents:
        context["company_documents"] = documents  # plain text, marked untrusted; never the company's own figure
    ask = (f"Redraft the technical definition of: {kpi_name}. Current: {current or 'none yet'}. The person asks: {instruction}" if instruction
           else f"Write the technical definition of: {kpi_name}, and raise what is unclear.")
    res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, system_prompt(documents=bool(documents), technical=True), context, ask, recorder=recorder)
    if res.status in ("refused", "error"):
        raise ModelUnreachable
    if res.status != "done" or res.numbers_replaced:
        return None
    text = "\n".join(ln.rstrip() for ln in res.text.splitlines()).strip()
    return text[:MAX_TECHNICAL] or None


def draft_definition(*args, **kwargs) -> str | None:
    """The definition alone (see draft_fields)."""
    return draft_fields(*args, **kwargs).get("definition")


def is_thin(text: str) -> bool:
    """One short sentence with no word that says something is counted or compared: it repeats the name, not the measure."""
    r = load_rules()["thin_definition"]
    words = re.findall(r"[a-z']+", text.lower())
    return len(re.findall(r"[.!?](?:\s|$)", text)) <= 1 and len(words) <= r["max_words"] and not (set(words) & set(r["says_how"]))


CALL_WORKERS = 2  # the egress gateway lets two model calls through at a time (gateway._call_slot): more threads would only queue


def run_in_order(fn, items: list) -> list:
    """fn over the items on a small thread pool: a draw of 16 measures takes about half the time, and the results come back in the
    order of the items, so the outcome never depends on which call finished first."""
    with ThreadPoolExecutor(CALL_WORKERS) as pool:
        return list(pool.map(fn, items))


# A job title is not part of a name; the other stop words (custody, services, fund ...) mark an organisation.
TITLES = frozenset("""sponsor admin administrator analyst owner approver participant guest officer executive director head lead
assistant coordinator reviewer chief senior junior vice deputy associate principal managing manager mr mrs ms dr""".split())


def sort_names(company: str, people: list[str], organisations=()) -> tuple[list[str], list[str]]:
    """(people, organisations). A job title around a name is dropped and the person registered ("Mei Tan Chief Executive Officer" is
    "Mei Tan", "Director Lee" is "Lee"); a name with an organisation word in it ("Northgate Custody") is an organisation; what is
    left of a title and a word of the company's own name ("Sponsor Lakeside") is nobody."""
    clean = lambda t: re.findall(r"[\w'’-]+", re.sub(r"\([^)]*\)", " ", str(t)))  # noqa: E731
    mine = {w.casefold() for w in clean(company)}
    keep, orgs = [], list(organisations)
    for n in people:
        words = clean(n)
        if len(words) < 2:
            keep.append(n)
            continue
        i, j = 0, len(words)
        while i < j and words[i].casefold() in TITLES:
            i += 1
        while j > i and words[j - 1].casefold() in TITLES:
            j -= 1
        core = words[i:j]
        low = [w.casefold() for w in core]
        if not core or all(w in STOP_WORDS or w in mine for w in low):
            continue
        if any(w in STOP_WORDS for w in low):
            orgs.append(n)
        else:
            keep.append(" ".join(core))
    return keep, orgs


def register_names(plane, company: str, people: list[str], organisations=()) -> None:
    """The company, the signed-in person and everyone named on the baseline go into the egress vault before anything
    leaves (D-007). A name that only a document holds is masked on the way out of sh_platform.context_docs.retrieval."""
    vault = NameVault(plane)
    for kind, name in protected_names(company, *sort_names(company, people, organisations)):
        try:
            if name:
                vault.register(kind, name)
        except (ValueError, VaultUnavailable):
            log.warning("a name could not be registered with the egress vault")  # the gateway then refuses to send
