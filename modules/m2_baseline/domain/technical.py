"""M2-E1: the technical definition of a measure, pure functions. Shared contract (docs/specs/M2-ENHANCEMENTS-PLAN.md):

technical = {sources, tables, fields, calculation, filters, grain, period, currency_basis, notes}

Each part is a provenance value (domain/provenance.py). sources, tables and fields hold ids of catalogue rows (a link, never a copy; an
extraction row id may stand in `fields`); the others are plain text. A part Lens could not ground is unknown and `from` says what is missing.
A person's part is never overwritten by a draft: the draft waits in `technical_proposal` beside it. The data owner's confirmation
(`technical_confirmed`) holds only while the parts are as they were when it was given.
"""
import hashlib
import json
import re

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.glossary import _facts, key as _key, text_of as _text_of
from modules.m2_baseline.domain.provenance import MARKS, prov, unknown

PARTS = ("sources", "tables", "fields", "calculation", "filters", "grain", "period", "currency_basis", "notes")
LINKS = ("sources", "tables", "fields")
NEEDED = ("sources", "fields", "calculation")  # complete means these three are present
LABELS = {"sources": "Sources", "tables": "Tables", "fields": "Fields", "calculation": "Calculation", "filters": "Filters", "grain": "Grain",
          "period": "Period", "currency_basis": "Currency basis", "notes": "Notes"}
TEXT_PARTS = tuple(p for p in PARTS if p not in LINKS)
ANSWERABLE = ("definition", *TEXT_PARTS)  # what a person's answer may change: the business definition and the text parts; a link is made with "Edit"
MAX_PART = 2000
CLOSED_BY_CATALOGUE = "Closed: the catalogue now has it"
CLOSED_BY_DEFINITION = "Closed: the technical definition now says it"
LENS = "Lens"
PACK = "the pack"
NOT_DRAFTED = "not drafted yet"


class Refused(ValueError):
    """A plain-words refusal, shown to the person."""


def parts_of(kpi: dict) -> dict[str, dict]:
    """All nine parts, each a provenance value; one never drafted is unknown."""
    t = kpi.get("technical") if isinstance(kpi.get("technical"), dict) else {}
    return {p: (t[p] if isinstance(t.get(p), dict) and t[p].get("mark") in MARKS else unknown(LENS, NOT_DRAFTED)) for p in PARTS}


def text_of(cell) -> str:
    return _text_of(cell) if isinstance(cell, dict) else ""


def present(cell) -> bool:
    return isinstance(cell, dict) and cell.get("mark") != "unknown" and bool(text_of(cell).strip())


def by_person(cell) -> bool:
    return present(cell) and str(cell.get("by")) not in (LENS, PACK)


def missing(kpi: dict) -> list[str]:
    """The needed parts still absent (sources, fields, calculation), by name."""
    p = parts_of(kpi)
    return [x for x in NEEDED if not present(p[x])]


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()[:20]


def part_digests(kpi: dict) -> dict[str, str]:
    p = parts_of(kpi)
    return {x: _sha(p[x].get("value") if p[x].get("mark") != "unknown" else None) for x in PARTS}


def digest(kpi: dict) -> str:
    return _sha(part_digests(kpi))


def to_confirm(kpi: dict) -> list[str]:
    """After a confirmation, the parts that changed since (or were added): only these need the data owner again. [] when nothing was confirmed."""
    c, now = kpi.get("technical_confirmed"), part_digests(kpi)
    if not isinstance(c, dict):
        return []
    then, p = c.get("parts") or {}, parts_of(kpi)
    return [x for x in PARTS if now[x] != then.get(x) and (present(p[x]) or x in then)]


def confirmed_parts(kpi: dict) -> list[str]:
    """The parts whose confirmation still holds: a change to one part clears the confirmation of that part only."""
    c = kpi.get("technical_confirmed")
    if not isinstance(c, dict):
        return []
    now = part_digests(kpi)
    p = parts_of(kpi)
    return [x for x, d in (c.get("parts") or {}).items() if now.get(x) == d and present(p[x])]


def confirmed(kpi: dict) -> dict | None:
    """The data owner's confirmation, while it still holds for the parts as they are now."""
    c = kpi.get("technical_confirmed")
    return c if isinstance(c, dict) and c.get("digest") == digest(kpi) and not missing(kpi) else None


def confirm(kpi: dict, by: str, at: str | None = None) -> dict:
    if missing(kpi):
        raise Refused("The technical definition is not complete yet: it needs its sources, fields and calculation before the data owner can confirm it.")
    at = at or A.now()
    cur = parts_of(kpi)  # the data owner's confirmation makes the required parts theirs: stated by them, where each came from kept
    kept = {**kpi, "technical": {**cur, **{x: prov(cur[x]["value"], "stated", by, f"confirmed by the data owner ({cur[x].get('from') or 'a draft'})", at)
                                           for x in NEEDED if cur[x].get("mark") == "guessed"}}}
    return {**kept, "technical_confirmed": {"by": by, "at": at, "digest": digest(kept), "parts": part_digests(kept)}}


# ---- what a person does -------------------------------------------------------------------------------------------------------------

def _clean(part: str, value, known: set[str] | None = None):
    if part in LINKS:
        ids = value if isinstance(value, list) else re.split(r"[,;\s]+", str(value or ""))
        ids = list(dict.fromkeys(str(i).strip() for i in ids if str(i).strip()))
        if known is not None and any(i not in known for i in ids):
            raise Refused("Please choose rows from the catalogue.")
        return ids[:50]
    text = "\n".join(" ".join(ln.split()) for ln in str(value or "").splitlines() if ln.strip())
    if len(text) > MAX_PART:
        raise Refused("That is too long. Please shorten it.")
    return text


def set_part(kpi: dict, part: str, value, mark: str, by: str, known: set[str] | None = None, source: str = "the work list", at: str | None = None) -> dict:
    """A person writes or clears one part. Stated or guessed is theirs to say; an empty value, or unknown, clears it. The earlier draft
    beside it is dropped (they have decided)."""
    if part not in PARTS:
        raise LookupError("no such part")
    if mark not in MARKS:
        raise Refused("Please say whether this is stated, guessed or unknown.")
    v = _clean(part, value, known)
    cell = unknown(by, "cleared by a person") if mark == "unknown" or not v else prov(v, mark, by, source, at)
    prop = {k: x for k, x in (kpi.get("technical_proposal") or {}).items() if k != part}
    return sweep({**kpi, "technical": {**parts_of(kpi), part: cell}, "technical_proposal": prop}, at)


def use_proposal(kpi: dict, part: str, by: str, at: str | None = None) -> dict:
    """"Use this": Lens's draft beside a person's part becomes theirs (stated by them, the draft's source kept)."""
    d = (kpi.get("technical_proposal") or {}).get(part)
    if not present(d):
        raise LookupError("no draft")
    return set_part(kpi, part, d["value"], "stated", by, source=f"Lens's draft, used by {by}" + (f" ({d['from']})" if d.get("from") else ""), at=at)


def merge_draft(kpi: dict, drafted: dict[str, dict]) -> dict:
    """Lens's drafted parts (provenance values) join the measure: they fill a part that is unknown or an earlier draft of Lens or the pack;
    a part a person touched is never overwritten, the draft waits beside it as a proposal."""
    cur, prop = parts_of(kpi), dict(kpi.get("technical_proposal") or {})
    out = dict(cur)
    for part, d in drafted.items():
        if part not in PARTS:
            continue
        if by_person(cur[part]):
            if d.get("mark") != "unknown" and text_of(d) != text_of(cur[part]):
                prop[part] = d
        elif d.get("mark") != "unknown" or cur[part].get("mark") == "unknown":
            out[part] = d
    return sweep({**kpi, "technical": out, "technical_proposal": prop})


def sweep(kpi: dict, at: str | None = None) -> dict:
    """Open questions Lens or the code raised whose cause is gone close by themselves, visibly ("Closed: the catalogue now has it"). The cause is
    the part the question waits for (`cause` "has:<part>"); an old question that asks a person for catalogue ids waits for the fields."""
    p = parts_of(kpi)
    for a in list(kpi.get("ambiguities") or []):
        cause = a.get("cause") or ("has:fields" if A.asks_for_ids(a) else "")
        part = cause.removeprefix("has:") if cause.startswith("has:") else ""
        # a catalogue link that exists closes it; any other part only when a PERSON stated it: a guess (Lens's, the pack's, or a person's own guess) never does
        gone = part in LINKS and present(p[part]) or part in PARTS and part not in LINKS and by_person(p[part]) and p[part].get("mark") == "stated"
        if a.get("status") == "open" and a.get("raised_by") == A.LENS and gone:
            kpi = A.close(kpi, a["id"], CLOSED_BY_CATALOGUE if part in LINKS else CLOSED_BY_DEFINITION, at)
    return kpi


def _words_of(text) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def with_wording(kpi: dict, part: str, wording, resolution: str, by: str, at: str | None = None) -> dict:
    """A person answered a question and chose the part it changes: `wording` is THEIR new text for that part (the screen pre-fills it with the
    current text for them to edit), saved as stated by them; what the part said before is kept in `technical_history`. Never the bare answer
    where there already is a wording."""
    if part not in ANSWERABLE:
        raise Refused("Please choose which part this answer changes, or just record the answer.")
    new = _clean(part, wording)
    if not new:
        raise Refused("Please write the new wording for this part. It is shown to you with the current text so you can edit it.")
    cell = kpi.get("definition") if part == "definition" else parts_of(kpi)[part]
    before = text_of(cell) if isinstance(cell, dict) and cell.get("mark") != "unknown" else ""
    if before and _words_of(new) == _words_of(resolution):
        raise Refused("That is only your answer. Please write the whole new wording of this part, starting from the current text.")
    history = {**(kpi.get("technical_history") or {})}
    if before:
        history[part] = [*history.get(part, []), {k: cell.get(k) for k in ("value", "mark", "by", "from", "at")}]
    src = f"answer to an open question, by {by}"
    if part == "definition":
        return {**kpi, "definition": prov(new, "stated", by, src, at), "definition_proposal": None, "technical_history": history}
    return {**set_part(kpi, part, new, "stated", by, source=src, at=at), "technical_history": history}


# ---- the catalogue rows that feed a measure -----------------------------------------------------------------------------------------

def feeding(cat: dict, kpi_id: str) -> dict[str, list[dict]]:
    """The catalogue rows (as a person sees them) that feed one measure: its tables, their sources, its fields and extractions."""
    tables = [t for t in cat.get("tables", []) if not t.get(C.HIDDEN) and kpi_id in C.split_ids(C.text_of(t.get("Related KPIs")))]
    t_ids = {C.row_id("tables", t) for t in tables}
    fields = [f for f in cat.get("fields", []) if not f.get(C.HIDDEN) and (kpi_id in C.split_ids(C.text_of(f.get("Feeds KPI"))) or C.text_of(f.get("Item ID")) in t_ids)]
    fields += [x for x in cat.get("extractions", []) if not x.get(C.HIDDEN) and kpi_id in C.split_ids(C.text_of(x.get("Feeds KPI")))]
    s_ids = {C.text_of(t.get("Source ID")) for t in tables}
    sources = [s for s in cat.get("sources", []) if not s.get(C.HIDDEN) and C.row_id("sources", s) in s_ids]
    return {"sources": sources, "tables": tables, "fields": fields}


def _rid(row: dict, tab: str) -> str:
    """The id of a catalogue row; the `fields` bucket holds field rows and extraction rows."""
    return C.row_id("extractions" if tab == "fields" and "Field name as in the source" not in row else tab, row)


def catalogue_lines(feed: dict[str, list[dict]]) -> str:
    """Plain labelled lines for the model: ids, names, types and units; never a value of the data."""
    out = [f"Source {_rid(s, 'sources')}: {C.text_of(s.get('Source name'))} ({C.text_of(s.get('Source type')) or 'type not stated'})" for s in feed["sources"]]
    out += [f"Table {_rid(t, 'tables')} in source {C.text_of(t.get('Source ID'))}: {C.text_of(t.get('Name of table, file or document type'))}"
            f"{'; one row is ' + C.text_of(t.get('What one row or record means')) if C.text_of(t.get('What one row or record means')) else ''}" for t in feed["tables"]]
    for f in feed["fields"]:
        if "Field name as in the source" in f:
            extra = [x for x in (C.text_of(f.get("Data type")), C.text_of(f.get("Format or unit")), C.text_of(f.get("Business meaning"))) if x]
            out.append(f"Field {_rid(f, 'fields')} in table {C.text_of(f.get('Item ID'))}: {C.text_of(f.get('Field name as in the source'))}" + (f" ({'; '.join(extra)})" if extra else ""))
        else:
            out.append(f"Extraction {_rid(f, 'fields')} in document type {C.text_of(f.get('Item ID (document type)'))}: {C.text_of(f.get('What to extract'))}")
    return "\n".join(out)


def feeding_ids(feed: dict[str, list[dict]]) -> dict[str, set[str]]:
    return {k: {_rid(r, k) for r in rows} for k, rows in feed.items()}


def row_names(cat: dict) -> dict[str, str]:
    """{row id: name} of every row in this catalogue view, for showing a link as words."""
    out = {}
    for tab, head in (("sources", "Source name"), ("tables", "Name of table, file or document type"), ("fields", "Field name as in the source"), ("extractions", "What to extract")):
        for r in cat.get(tab, []):
            if not r.get(C.HIDDEN):
                out[C.row_id(tab, r)] = C.text_of(r.get(head))
    return out


# ---- reading Lens's reply -----------------------------------------------------------------------------------------------------------

_LABELS = ("SOURCES", "TABLES", "FIELDS", "CALCULATION", "FILTERS", "GRAIN", "PERIOD", "CURRENCY", "NOTES", "MISSING", "CONFLICT", "NEW_SOURCE", "NEW_TABLE", "NEW_FIELD")
_LABEL_LINE = re.compile(r"^\s*(" + "|".join(_LABELS) + r")\s*:\s*(.*)$", re.IGNORECASE)
_PART_OF = {"SOURCES": "sources", "TABLES": "tables", "FIELDS": "fields", "CALCULATION": "calculation", "FILTERS": "filters", "GRAIN": "grain",
            "PERIOD": "period", "CURRENCY": "currency_basis", "NOTES": "notes"}
_NONE = ("UNKNOWN", "NONE", "NO DEFINITION", "NOT STATED")


def parse_reply(text: str, allowed: dict[str, set[str]]) -> dict:
    """{parts: {part: value}, missing: str, conflicts: [(kind, where, text, question, suggestion)], catalogue: {sources: [(name, type)], tables:
    [(source, name)], fields: [(table, name, meaning)]}}. UNKNOWN fills nothing. A link to a row
    that is not in `allowed` (the rows this person may see that feed the measure) is dropped: Lens cannot link what it was not shown."""
    blocks: list[list] = []
    for line in str(text or "").splitlines():
        m = _LABEL_LINE.match(line)
        if m:
            blocks.append([m.group(1).upper(), [m.group(2)]])
        elif blocks and line.strip():
            blocks[-1][1].append(line.rstrip())
    parts, missing_, conflicts, cat = {}, "", [], {"sources": [], "tables": [], "fields": []}
    for label, lines in blocks:
        body = "\n".join(lines).strip()
        if label.startswith("NEW_"):
            f = [" ".join(x.split())[:200] for x in body.split("|")]
            tab = {"NEW_SOURCE": "sources", "NEW_TABLE": "tables", "NEW_FIELD": "fields"}[label]
            if (len(f) >= 2 and f[0] and f[1]) or (tab == "sources" and f[0]):
                cat[tab].append(tuple((f + ["", ""])[: 3 if tab == "fields" else 2]))
            continue
        if label == "CONFLICT":
            f = [x.strip() for x in body.split("|")]
            if len(f) >= 4 and f[2] and f[3]:
                conflicts.append((f[0].lower() if f[0].lower() in A.KINDS and f[0].lower() != "governance" else "other", f[1], f[2], f[3], f[4] if len(f) > 4 else ""))
            continue
        if not body or body.upper().startswith(_NONE):
            continue
        if label == "MISSING":
            missing_ = " ".join(body.split())[:300]
        elif label in ("SOURCES", "TABLES", "FIELDS"):
            part = _PART_OF[label]
            canon = {x.upper(): x for x in allowed.get(part, set())}
            ids = [canon[i] for i in dict.fromkeys(re.split(r"[,;\s]+", body.upper())) if i in canon]
            if ids:
                parts[part] = ids
        else:
            value = _clean(_PART_OF[label], body)
            if value:
                parts[_PART_OF[label]] = value
    return {"parts": parts, "missing": missing_, "conflicts": conflicts, "catalogue": cat}


def anchored(cat: dict, passages: str) -> dict:
    """Lens's proposed catalogue rows kept only where the passages it was shown say the name (a source, table or column is never made up from
    nothing), whatever the case or the punctuation."""
    hay = " ".join(re.findall(r"[a-z0-9]+", str(passages or "").lower()))
    said = lambda n: bool(" ".join(re.findall(r"[a-z0-9]+", str(n).lower()))) and " ".join(re.findall(r"[a-z0-9]+", str(n).lower())) in hay  # noqa: E731
    out = {"sources": [r for r in cat.get("sources", []) if said(r[0])],
           "tables": [r for r in cat.get("tables", []) if said(r[1]) and said(r[0])],
           "fields": [r for r in cat.get("fields", []) if said(r[1]) and said(r[0])]}
    return out if any(out.values()) else {}


def drafted_parts(reply: dict, sources: list[str], at: str | None = None) -> dict[str, dict]:
    """The reply as provenance values: guessed, by Lens, from the documents, the catalogue and the pack it was shown (`sources`).
    Every part the reply did not give is unknown, and the calculation's says what is missing."""
    came = ", ".join(dict.fromkeys(sources)) or "the catalogue"
    out = {p: prov(reply["parts"][p], "guessed", LENS, came, at) for p in PARTS if p in reply["parts"]}
    for p in PARTS:
        if p not in out:
            out[p] = unknown(LENS, ("Missing: " + reply["missing"]) if p == "calculation" and reply["missing"] else "Missing: nothing in the documents, the catalogue or the industry text says")
    return out


# ---- code checks: what a build needs and the documents do not say --------------------------------------------------------------------

_SECTION = re.compile(r"^\s*#{1,4}\s+(.*)$")
_THRESHOLD = re.compile(r"(?i)\b(?:our |the |a )?(?:usual|reasonable|agreed|normal|standard)\s+(?:stress\s+)?(?:limit|multiplier|threshold|age|waiting time|number)\b|\bbig enough\b|\bis reasonable\b|\blonger than reasonable\b")
_ASK = re.compile(r"(?i)\bask\s+([A-Z][a-z]+)\b|\bnot noted\b")


WITHHELD = "Part of this is limited to people named for it."


def _hides(cell, hidden) -> bool:
    return A.mentions({"text": text_of(cell)}, hidden)


def view_parts(kpi: dict, names: dict[str, str], hidden: list[str]) -> list[dict]:
    """The nine parts as one person may see them: [{part, label, cell, links, proposal, withheld}]. A link is shown only to a row in `names`
    (the rows this person may see); a text part, or a draft beside it, that names something in `hidden` is withheld whole."""
    cur, prop, out, hist = parts_of(kpi), kpi.get("technical_proposal") or {}, [], kpi.get("technical_history") or {}
    for p in PARTS:
        cell, draft = cur[p], prop.get(p)
        before = [h for h in hist.get(p, []) if p not in LINKS and not _hides(h, hidden)]  # what the part said before a person's answer replaced it
        if p in LINKS:
            ids = [i for i in (cell.get("value") or []) if i in names] if present(cell) else []
            cell = {**cell, "value": ids} if present(cell) else cell
            if present(cell) and not ids:
                cell = unknown(cell.get("by", LENS), cell.get("from", ""))
            links = [{"id": i, "name": names[i]} for i in ids]
            draft = {**draft, "value": [i for i in draft.get("value") or [] if i in names]} if present(draft) else None
            draft = draft if draft and draft["value"] else None
            out.append({"part": p, "label": LABELS[p], "cell": cell, "links": links, "proposal": draft, "withheld": False, "history": []})
            continue
        hide = present(cell) and _hides(cell, hidden)
        out.append({"part": p, "label": LABELS[p], "cell": unknown(LENS, WITHHELD) if hide else cell, "links": [],
                    "proposal": None if not draft or _hides(draft, hidden) else draft, "withheld": hide, "history": [] if hide else before})
    return out


def flat(kpi: dict, names: dict[str, str]) -> dict[str, str]:
    """The technical definition as plain text, for the catalogue's KPIs tab and the Excel sheet: links are the rows' names."""
    p, out = parts_of(kpi), {}
    for x in PARTS:
        v = p[x].get("value") if present(p[x]) else None
        out[x] = ("; ".join(names.get(i, i) for i in v if i in names) if x in LINKS else str(v or "")) if v else ""
    return out


_SUBJECTS = (("sources", ("source", "tracker", "workbook", "file", "portal")), ("fields", ("field", "column")),
             ("period", ("period", "month end", "business day", "cut-off", "reporting date", "bucket")),
             ("currency_basis", ("currency", "fx", "exchange", "rate", "usd", "sgd")),
             ("filters", ("limit", "threshold", "multiplier", "filter", "exclude", "index", "benchmark")),
             ("grain", ("grain", "per")), ("calculation", ("calculat*", "formula", "step", "denominator", "headcount", "age", "net", "gross", "fee", "count")))
# a keyword is a whole word (a plural counts); one ending in * is a stem ("calculat*" is calculate, calculation): "age" is not in "management"
_SUBJECT_RES = tuple((part, re.compile("|".join((rf"\b{re.escape(w[:-1])}\w*" if w.endswith("*") else rf"\b{re.escape(w)}s?\b") for w in words), re.IGNORECASE))
                     for part, words in _SUBJECTS)
_STOP = frozenset("a an and are as at be by for from in is it its of on or our the their this to your with".split())


def subject_of(where: str, text: str) -> str:
    """The part of the technical definition a finding is about, worked out in CODE from the words of the finding (the model's own label first, then its
    text): whole words only. "" when none fits."""
    for hay in (str(where), str(text)):
        for part, rx in _SUBJECT_RES:
            if rx.search(hay):
                return part
    return ""


def subject_words(where: str, n: int = 4) -> str:
    """The first few significant words of a finding's label (lower case, small words dropped): what it is about, so "stress limit" and "age limit"
    are two findings and a rephrasing with the same label is one."""
    return " ".join([w for w in re.findall(r"[a-z0-9]+", str(where).lower()) if w not in _STOP][:n])


def finding_key(name: str, kind: str, where: str, text: str) -> str:
    """`measure: kind (part) subject`: one finding per measure, kind, part and subject. Code-raised items pass the phrase they already build for
    `where`; the model's own wording stays in `text` and never decides identity."""
    s, w = subject_of(where, text), subject_words(where)
    return f"{name}: {kind}" + (f" ({s})" if s else "") + (f" {w}" if w else "")


def section_of(text: str, name: str) -> str:
    """The lines of the document passages under a heading that names this measure ("" when the passages have none): what the document says
    about THIS measure and not its neighbours."""
    lines, grab, got = str(text or "").splitlines(), False, []
    want = _key(name)
    for ln in lines:
        m = _SECTION.match(ln)
        if m:
            grab = bool(want) and want in _key(re.sub(r"\(.*?\)", "", m.group(1)))
            continue
        if grab:
            got.append(ln)
    return "\n".join(got)


def _fact_kind(kind: str) -> str:
    return {"period": "period", "basis": "calculation", "currency": "currency"}[kind]


def code_ambiguities(kpi: dict, passages: str, titles: list[str], feed: dict[str, list[dict]], at: str | None = None) -> list[dict]:
    """The ambiguities code can see without a model: a needed part missing, a calculation with no catalogue field, a period or currency
    the calculation needs and nobody stated, the business and technical wording disagreeing, an input a document says "ask" about, and a
    threshold named with no number. Each is one item (kind and place), so a second build never adds it again."""
    name, p, out = kpi["name"], parts_of(kpi), []
    doc = ", ".join(titles) or "the documents"

    def add(kind, text, question, where, **x):
        out.append(A.make(kind, text, question, finding_key(name, kind, where, text), at, **x))  # the same key scheme as Lens's findings: one item per measure, kind and part

    if not present(p["calculation"]):
        add("calculation", f"Nothing says how “{name}” is worked out.", f"How is “{name}” calculated, step by step?", "calculation", cause="has:calculation")
    else:  # an input with no catalogue row is not asked of a person: Lens proposes the rows from the notes (propose_rows) and the fields part links them
        if not present(p["period"]):
            add("period", f"The period for “{name}” is not stated: month end, last business day or another cut-off.", "Which date is the reporting date for this measure?", "period", cause="has:period")
        wording = " ".join(text_of(p[x]) for x in ("calculation", "filters", "notes")).lower() + " " + " ".join(
            C.text_of(f.get("Format or unit")).lower() + " " + C.text_of(f.get("Field name as in the source")).lower() for f in feed.get("fields", []))
        if not present(p["currency_basis"]) and re.search(r"\b(currency|convert|conversion|fx|exchange rate|usd|sgd|eur|gbp)\b", wording):
            add("currency", f"The currency basis for “{name}” is not stated: which currency, which rate, from where and on which date.", "Which rate, from where, on which date?", "currency basis", cause="has:currency_basis")
    # the business and the technical wording must agree on period, net or gross and currency
    biz = text_of(kpi.get("definition")) if (kpi.get("definition") or {}).get("mark") != "unknown" else ""
    tech = " ".join(text_of(p[x]) for x in ("calculation", "period", "currency_basis", "filters"))
    if biz and tech.strip():
        a, b = _facts(biz), _facts(tech)
        for f, label in (("period", "reporting period"), ("basis", "net or gross"), ("currency", "currency")):
            if a[f] and b[f] and a[f] != b[f]:
                add("conflict", f"The business definition says {'/'.join(sorted(a[f]))} for the {label}; the technical definition says {'/'.join(sorted(b[f]))}.",
                    f"Which is right for the {label}?", f"{label} (business and technical definition)")
    mine = section_of(passages, name)
    for ln in mine.splitlines():
        if _THRESHOLD.search(ln) and not re.search(r"\d", ln):
            add("threshold", f"“{name}” depends on a limit that has no number in {doc}: “{' '.join(_THRESHOLD.search(ln).group(0).split())}”.",
                "What is the number, and does it differ by asset class?", f"threshold ({' '.join(_THRESHOLD.search(ln).group(0).lower().split())})")
        m = _ASK.search(ln)
        if m:
            who = m.group(1)
            what = "currency" if re.search(r"(?i)rate|currency|fx", ln) else "threshold" if re.search(r"(?i)limit|multiplier|threshold", ln) else "calculation" if re.search(r"(?i)count|whether|denominator|rows", ln) else "other"
            add(what, f"A document leaves an input of “{name}” open: “{' '.join(ln.split())[:160]}”" + (f" It says to ask {who}." if who else ""),
                f"What is the answer{' (' + who + ' knows)' if who else ''}?", f"open input ({' '.join(ln.split())[:40]})")
    return out
