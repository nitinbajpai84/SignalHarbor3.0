"""M2-E2 the business glossary of a baseline: pure functions, no files, no network.

One entry per measure (the shared contract in docs/specs/M2-ENHANCEMENTS-PLAN.md): {kpi_id, term, aliases, business_definition, owner,
frequency, who_may_see, personal, change, previous, assumption, source_document, reviewed}. term, aliases, business_definition, owner,
frequency and previous are provenance values (domain/provenance.py); the rest is plain. Added, all optional: sensitive, match (how a provided
term was found: name or meaning), decided {choice, by, at}, proposal (a later draft kept beside a person's wording).

Reuse (D-031): provenance cells from domain/provenance.py and the catalogue's `is_manual` idea (a person's wording is never overwritten,
a later draft becomes a proposal beside it, as `definition_proposal` does on the work list); visibility is the work list's `may_see`
(the caller passes the rule in). Nothing in the earlier repo was a business glossary (searched: glossary, business_glossary, catalogue_chat).
"""
import csv
import io
import re
from datetime import datetime, timezone

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain.provenance import prov, unknown

CHANGES = ("unchanged", "changed", "new")
CHOICES = ("ours", "provided", "edited")
NOT_SAME = "not_same"  # not a wording choice: it undoes the match (store.glossary.reject_match)
MAX_TERMS, MAX_TERM, MAX_TEXT, MAX_ALIAS = 500, 120, 2000, 120
NOT_YET = "Not available yet"
RESTRICTED_NAME = "A restricted measure"
OPEN_TO_ALL = "Everyone in the company"
MORE_ROWS = "... (more rows)"  # what the context documents reader writes where it stopped reading a sheet
ASK_FIRST = "Only the company admin, until people are named"

_HEAD = {"term": ("term", "name", "measure", "kpi", "metric", "business term"),
         "definition": ("definition", "meaning", "description", "business definition"),
         "aliases": ("alias", "aliases", "synonym", "synonyms", "also known as", "aka", "also called"),
         "owner": ("owner", "data owner", "business owner", "steward"),
         "frequency": ("frequency", "reported", "how often", "reporting frequency"),
         "source": ("source", "system", "source system")}
_BULLET = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)")
# the labels of a heading-and-bullet entry ("- Meaning: ...") and the field each fills; labels are words, never terms
_FIELD = {"meaning": "definition", "definition": "definition", "description": "definition", "owner": "owner", "data owner": "owner", "steward": "owner",
          "reported": "frequency", "how often reported": "frequency", "how often": "frequency", "frequency": "frequency",
          "source": "source", "where the number comes from": "source", "system": "source", "also": "aliases", "also called": "aliases",
          "aliases": "aliases", "last updated": "", "updated": ""}
_LABEL_WORDS = set(_FIELD) | ({w for words in _HEAD.values() for w in words} - {"name", "measure", "kpi", "metric", "term", "business term"})
_HEADING = re.compile(r"^#{2,4}\s+(.+?)\s*#*\s*$")
_ALSO = re.compile(r"^(.*?)\s*\(\s*(?:also|aka|also called|also known as)\s*:?\s*(.*?)\)\s*$", re.I)
_FIELD_LINE = re.compile(r"^[-*•]\s+\**([^:*]{1,40}?)\**\s*:\s*(.*)$")
_QUOTES = re.compile("[\"“”']")
_FREE = re.compile(r"^\**\s*([^:|*]{1,%d}?)\s*\**\s*(?::|\s[-–—]\s)\s*(.+)$" % MAX_TERM)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def key(text) -> str:
    """Words and numbers only, lower case: how two wordings are compared."""
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def text_of(cell) -> str:
    v = cell.get("value") if isinstance(cell, dict) and cell.get("mark") != "unknown" else None
    return "; ".join(map(str, v)) if isinstance(v, (list, tuple)) else ("" if v is None else str(v))


# ---- reading a provided glossary (the text the context documents reader gives) --------------------------------------------------

def _cells(line: str, style: str) -> list[str]:
    if style == "bar":
        return [c.strip() for c in line.strip().strip("|").split("|")]
    if style == "tab":
        return [c.strip() for c in line.split("\t")]
    return [c.strip() for c in next(csv.reader([line]), [])]


def _style(line: str) -> str | None:
    return "bar" if "|" in line else "tab" if "\t" in line else "comma" if "," in line else None


def _header(cells: list[str]) -> dict[str, int] | None:
    found = {}
    for i, c in enumerate(cells):
        for field, words in _HEAD.items():
            if field not in found and key(c) in words:
                found[field] = i
    return found if "term" in found and "definition" in found else None


def _aliases(text: str) -> list[str]:
    return [a for a in dict.fromkeys(p.strip() for p in re.split(r"[;/]" if re.search(r"[;/]", text or "") else ",", text or "")) if a][:20]


def _clean(row: dict) -> dict:
    row = {k: ([a[:MAX_ALIAS] for a in v] if k == "aliases" else " ".join(str(v).split())[:MAX_TEXT]) for k, v in row.items()}
    return {k: ("" if k != "aliases" and key(v) == key(NOT_YET) else v) for k, v in row.items()}  # our own placeholder, provided again, says nothing


def _headed(lines: list[str]) -> list[dict]:
    """Entries written as a heading (the term, "(also: alias)") followed by "- Label: value" bullets. Only an entry with a wording counts."""
    out, cur = [], None
    for raw in lines:
        line = raw.strip()
        if m := _HEADING.match(line):
            title = m.group(1).strip().strip("*")
            a = _ALSO.match(title)
            cur = {"term": (a.group(1) if a else title).strip(), "definition": "", "aliases": _aliases(_QUOTES.sub("", a.group(2))) if a else [],
                   "owner": "", "frequency": "", "source": ""}
            out.append(cur)
        elif cur is not None and (m := _FIELD_LINE.match(line)) and key(m.group(1)) in _FIELD:
            f = _FIELD[key(m.group(1))]
            if f == "aliases":
                cur["aliases"] = _aliases(_QUOTES.sub("", m.group(2)))
            elif f:
                cur[f] = m.group(2)
    return [_clean(r) for r in out if r["definition"].strip() and r["term"] and len(r["term"]) <= MAX_TERM and key(r["term"]) not in _LABEL_WORDS][:MAX_TERMS]


def parse_provided(text: str) -> tuple[list[dict], bool]:
    """([{term, definition, aliases, owner, frequency, source}], read_only_part). A table (xlsx sheet, csv, markdown, tabs) with a header
    row naming a term and a definition column is read by its columns; anything else line by line as "Term: wording" or "Term - wording".
    Text is kept as text; the screens and downloads escape it. The flag is true when the reader stopped early on a long sheet."""
    terms, head, style, capped = [], None, None, False
    lines = str(text or "").splitlines()
    if headed := _headed(lines):
        return headed, len(headed) >= MAX_TERMS or MORE_ROWS in str(text or "")
    tabled = any((st := _style(ln)) and _header(_cells(ln, st)) for ln in lines)  # a table is in the file: lines outside it are titles and notes
    for raw in lines:
        line = raw.rstrip()
        if line.startswith("## Sheet"):
            head, style = None, None
            continue
        if not line.strip() or re.fullmatch(r"[\s|:\-]+", line):
            continue
        s = _style(line)
        if head is None and s and (h := _header(_cells(line, s))):
            head, style = h, s
            continue
        if head is not None and s == style:
            cells = _cells(line, style)
            pick = lambda f: cells[head[f]] if f in head and head[f] < len(cells) else ""  # noqa: E731
            row = {"term": pick("term"), "definition": pick("definition"), "aliases": _aliases(pick("aliases")),
                   "owner": pick("owner"), "frequency": pick("frequency"), "source": pick("source")}
        elif line.strip() == MORE_ROWS:
            continue
        elif tabled:
            continue
        else:
            m = _FREE.match(_BULLET.sub("", line).strip())
            if not m:
                continue
            row = {"term": m.group(1), "definition": m.group(2), "aliases": [], "owner": "", "frequency": "", "source": ""}
        row = _clean(row)
        if row["term"] and len(row["term"]) <= MAX_TERM and key(row["term"]) not in _LABEL_WORDS:
            terms.append(row)
        if len(terms) >= MAX_TERMS:
            capped = True
            break
    return terms, capped or MORE_ROWS in str(text or "")


# ---- matching a provided term to a measure ------------------------------------------------------------------------------------

def code_matches(kpis: list[dict], terms: list[dict], prior: dict[str, list[str]] | None = None, rejected: set | None = None) -> dict[str, int]:
    """{kpi_id: index of the term} by exact name or by an alias, in code. `prior` is each measure's aliases from an earlier build.
    One term serves one measure and one measure takes one term (the first). A pair a person said is not the same thing is never matched again."""
    out: dict[str, int] = {}
    used: set[int] = set()
    pairs = []  # (rank, kpi order, term order, kpi id): best match first, ties by the order of the measures and then of the terms
    for n, k in enumerate(kpis):
        names = {_stems(a) for a in (k["name"], *(prior or {}).get(k["id"], []))} - {()}
        for i, t in enumerate(terms):
            if (k["id"], key(t["term"])) in (rejected or ()):
                continue
            rank = max((_overlap(a, b) for a in names for b in {_stems(x) for x in (t["term"], *t["aliases"])} - {()}), default=0)
            if rank:
                pairs.append((-rank, n, i, k["id"]))
    for _, _, i, kid in sorted(pairs):  # one term serves one measure and one measure takes one term
        if i not in used and kid not in out:
            out[kid] = i
            used.add(i)
    return out


def _stems(text) -> tuple[str, ...]:
    """The words of a name with plurals folded ("calls" is "call"), so "Capital calls" and "Capital call" compare equal."""
    return tuple(re.sub(r"(?<=[a-z]{3})(?<!s)s$", "", re.sub(r"(?<=[a-z]{3})ies$", "y", w)) for w in key(text).split())


def _overlap(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    """0 for no match; 1000 for the same words (in any order); else the word count of the shorter name when it sits whole inside the longer
    (two words at least, so "Exposure" alone never claims "Exposure (currency)")."""
    if sorted(a) == sorted(b):
        return 1000
    short, long_ = sorted((a, b), key=len)
    return len(short) if len(short) >= 2 and any(long_[i:i + len(short)] == short for i in range(len(long_) - len(short) + 1)) else 0


# ---- what disagrees, for the ambiguity list -----------------------------------------------------------------------------------

_PERIODS = {"daily": "daily", "day": "daily", "weekly": "weekly", "week": "weekly", "monthly": "monthly", "month": "monthly",
            "quarterly": "quarterly", "quarter": "quarterly", "annual": "annual", "annually": "annual", "yearly": "annual", "year": "annual"}
_CURRENCY = re.compile(r"\b(USD|SGD|EUR|GBP|JPY|CHF|HKD|AUD|CAD|CNY|INR)\b|\b(base|local|reporting|home) currency\b", re.I)


def _facts(text: str) -> dict[str, set[str]]:
    words = re.findall(r"[a-z]+", str(text).lower())
    return {"period": {_PERIODS[w] for w in words if w in _PERIODS}, "basis": {w for w in words if w in ("net", "gross")},
            "currency": {m.group(0).lower() for m in _CURRENCY.finditer(str(text))}}


_KINDS = {"period": ("period", "Which reporting period should this measure use?", "period"),
          "basis": ("calculation", "Is this measure net or gross?", "net or gross"),
          "currency": ("currency", "Which currency should this measure use?", "currency")}


def disagreements(cur: str, prov_text: str, cur_owner: str, prov_owner: str, cur_source: str, prov_source: str) -> list[tuple[str, str, str]]:
    """[(kind, what, question)] for what matters to a build: period, net or gross, currency, owner, source. Only where both sides say something."""
    out = []
    a, b = _facts(cur), _facts(prov_text)
    for f, (kind, question, label) in _KINDS.items():
        if a[f] and b[f] and a[f] != b[f]:
            out.append((kind, f"Your glossary says {'/'.join(sorted(b[f]))} for the {label}; this baseline says {'/'.join(sorted(a[f]))}.", question))
    for kind, x, y, label, question in (("owner", cur_owner, prov_owner, "owner", "Who owns this measure?"),
                                        ("source", cur_source, prov_source, "source", "Which source feeds this measure?")):
        if key(x) and key(y) and key(x) != key(y) and key(x) not in key(y) and key(y) not in key(x):
            out.append((kind, f"Your glossary names {y} as the {label}; this baseline names {x}.", question))
    return out


# ---- building the entries ------------------------------------------------------------------------------------------------------

def _assumption(cur: str, hit: dict, found: list) -> str:
    if not cur:
        return "This measure had no definition yet, so Lens used your glossary's wording until its owner confirms."
    if found:
        what = " and ".join(sorted({k for k, _, _ in found}))
        return f"Your glossary and this baseline disagree on the {what}; Lens kept the baseline's wording and raised a question."
    return "Lens kept the baseline's wording; your glossary words it differently."


def _fresh(k: dict, hit: dict | None, how: str, doc: str, at: str) -> tuple[dict, list[dict]]:
    cur = dict(k.get("definition") or unknown("Lens"))
    gov = k.get("governance") or {}
    owner = dict((k.get("owners") or {}).get("business") or unknown("Lens"))
    e = {"kpi_id": k["id"], "term": prov(k["name"], "stated", "the work list", "the baseline's measures", at),
         "aliases": unknown("Lens", "none known"), "business_definition": cur, "owner": owner,
         "frequency": unknown("Lens", "not asked yet"), "data_source": unknown("Lens", "not asked yet"), "who_may_see": list(gov.get("may_see") or []),
         "personal": gov.get("personal", "not_sure"), "sensitive": bool(gov.get("sensitive")),
         "change": "new", "previous": unknown("Lens", "not in your glossary" if doc else "no glossary provided"),
         "assumption": "This measure is not in your glossary, so Lens wrote the entry from the baseline." if doc else "",
         "source_document": "", "reviewed": None}
    if not hit:
        return e, []
    d, mine = hit["definition"], text_of(cur)
    names = [a for a in dict.fromkeys([hit["term"], *hit["aliases"]]) if key(a) != key(k["name"])]
    e.update(source_document=doc, match=how, matched_term=hit["term"], change="unchanged", assumption="",
             aliases=prov(names, "stated", doc, doc, at) if names else e["aliases"],
             previous=prov(d, "stated", doc, doc, at) if d else unknown("Lens", "no wording in your glossary"))
    if hit["frequency"]:  # provided values are stated by the glossary; the owner only fills a gap (a different one is raised below)
        e["frequency"] = prov(hit["frequency"], "stated", doc, doc, at)
    if hit["source"]:
        e["data_source"] = prov(hit["source"], "stated", doc, doc, at)
    if hit["owner"] and not text_of(owner):
        e["owner"] = owner = prov(hit["owner"], "stated", doc, doc, at)
    found = disagreements(mine, d, text_of(owner), hit["owner"], text_of(k.get("producer")), hit["source"]) if d else []
    if d and not mine:
        e.update(change="changed", business_definition=prov(d, "guessed", "Lens", doc, at), assumption=_assumption("", hit, found))
    elif d and key(d) != key(mine):
        e.update(change="changed", assumption=_assumption(mine, hit, found))
    where = f"Business glossary: {k['name']}"
    return e, [A.make(kind, what, q, where, at) for kind, what, q in found]


def build_entries(kpis: list[dict], terms: list[dict], matches: dict[str, tuple[int, str]], doc: str, prior: list[dict], at: str | None = None
                  ) -> tuple[list[dict], dict[str, list[dict]]]:
    """(entries in the measures' order, {kpi_id: new ambiguities}). `matches` is {kpi_id: (term index, "name" or "meaning")}; `doc` is the
    provided glossary's title ("" when none). A measure a person decided on keeps that wording, change, assumption and review; a fresh
    wording that differs is kept beside it as `proposal`. A review is dropped when the wording changed under it."""
    at, before, entries, raised = at or now(), {e["kpi_id"]: e for e in prior}, [], {}
    for k in kpis:
        t, how = matches.get(k["id"], (None, ""))
        e, amb = _fresh(k, terms[t] if t is not None else None, how, doc, at)
        old = before.get(k["id"])
        if old:
            if old.get("decided"):
                kept = {x: old[x] for x in ("business_definition", "change", "assumption", "decided", "reviewed") if x in old}
                new_text = text_of(e["business_definition"])
                e = {**e, **kept}
                if new_text and key(new_text) != key(text_of(old["business_definition"])):
                    e["proposal"] = prov(new_text, "guessed", "Lens", doc or "the work list", at)
            elif old.get("reviewed") and key(text_of(old["business_definition"])) == key(text_of(e["business_definition"])):
                e["reviewed"] = old["reviewed"]
        entries.append(e)
        if amb:
            raised[k["id"]] = amb
    return entries, raised


# ---- a person's decisions ------------------------------------------------------------------------------------------------------

class Refused(ValueError):
    """A plain-words refusal, shown to the person."""


def decide(entry: dict, choice: str, text: str, by: str, at: str | None = None) -> dict:
    """Keep ours, keep the provided wording, or edit. The wording becomes stated by this person; the entry counts as reviewed."""
    at = at or now()
    cur, was, doc = text_of(entry["business_definition"]), text_of(entry["previous"]), entry.get("source_document") or "your glossary"
    if choice == "ours" and not cur:
        raise Refused("There is no wording in this baseline to keep yet. Keep the provided wording or write your own.")
    if choice == "provided" and not was:
        raise Refused("Your glossary has no wording for this measure. Keep ours or write your own.")
    if choice == "edited" and not (" ".join(str(text).split()) and len(str(text)) <= MAX_TEXT):
        raise Refused("Please write the wording in a few sentences.")
    if choice not in CHOICES:
        raise Refused("Please choose one of the three options.")
    value = {"ours": cur, "provided": was, "edited": " ".join(str(text).split())}[choice]
    where = {"ours": "kept the baseline's wording", "provided": f"kept the wording in {doc}", "edited": "edited in the glossary"}[choice]
    return {**entry, "business_definition": prov(value, "stated", by, where, at), "decided": {"choice": choice, "by": by, "at": at},
            "reviewed": {"by": by, "at": at}}


def with_chosen_definition(kpi: dict, value: str, by: str, at: str | None = None) -> dict:
    """The measure's own definition after a person chose a wording in the glossary: stated by that person when the definition is not
    already a person's value; when it is, the chosen wording is kept beside it as a proposal. (Same rule as the work list's `_place`.)"""
    d = kpi.get("definition") or {}
    if not value or key(text_of(d)) == key(value):
        return kpi
    mine = d.get("mark") != "unknown" and str(d.get("by")) not in ("Lens", "the pack")
    new = prov(value, "stated", by, "chosen in the business glossary", at or now())
    return {**kpi, "definition_proposal": new} if mine else {**kpi, "definition": new}


def reviewed(entry: dict, by: str, at: str | None = None) -> dict:
    return {**entry, "reviewed": {"by": by, "at": at or now()}}


# ---- what is shown and downloaded ----------------------------------------------------------------------------------------------

def who_text(e: dict) -> str:
    if e.get("personal", "not_sure") == "no" and not e.get("sensitive"):
        return OPEN_TO_ALL
    return ", ".join(e.get("who_may_see") or []) or ASK_FIRST


def _sure(cell) -> str:
    m = cell.get("mark") if isinstance(cell, dict) else "unknown"
    return {"stated": f"Stated by {cell.get('by')}", "guessed": f"A guess ({cell.get('by')})"}.get(m, NOT_YET)


def flat(e: dict) -> dict[str, str]:
    """One entry as plain text, the same for the screen's table, the Excel file and the printed page."""
    shown = lambda c: text_of(c) or NOT_YET  # noqa: E731
    r, d = e.get("reviewed"), e.get("decided")
    return {"term": text_of(e["term"]), "aliases": text_of(e["aliases"]), "definition": shown(e["business_definition"]),
            "how_sure": _sure(e["business_definition"]), "previous": text_of(e["previous"]) or NOT_YET, "owner": shown(e["owner"]),
            "frequency": shown(e["frequency"]), "data_source": shown(e.get("data_source")), "who": who_text(e),
            "personal": {"yes": "Yes", "no": "No"}.get(e.get("personal"), "Not sure yet"),
            "change": {"unchanged": "Unchanged", "changed": "Changed", "new": "New"}[e["change"]], "assumption": e.get("assumption") or "",
            "source": e.get("source_document") or "", "reviewed": f"{r['by']}, {str(r['at'])[:10]}" if r else "Not reviewed yet",
            "decided_by": f"{d['by']} ({ {'ours': 'kept ours', 'provided': 'kept the provided wording', 'edited': 'edited'}[d['choice']] })" if d else "Not decided yet",
            "proposal": text_of(e.get("proposal"))}


def counts(entries: list[dict]) -> dict[str, int]:
    return {"all": len(entries), **{c: sum(1 for e in entries if e["change"] == c) for c in CHANGES},
            "reviewed": sum(1 for e in entries if e.get("reviewed"))}


def glossary_ready(entries: list[dict], measures_missing: int = 0) -> tuple[bool, list[str]]:
    """What the sign-off gate (M2-E4) asks: (ready, reasons in plain words). Ready when every measure has an entry and every entry is
    reviewed. Counts only: a reason never names a measure."""
    why = []
    if not entries:
        why.append("The glossary has not been built yet.")
    if measures_missing:
        why.append(f"{measures_missing} {'measure is' if measures_missing == 1 else 'measures are'} not in the glossary yet. Ask Lens to update it.")
    open_ = [e for e in entries if not e.get("reviewed")]
    for c, label in (("changed", "changed"), ("new", "new"), ("unchanged", "unchanged")):
        n = sum(1 for e in open_ if e["change"] == c)
        if n:
            why.append(f"{n} {label} {'entry has' if n == 1 else 'entries have'} not been reviewed.")
    return not why, why
