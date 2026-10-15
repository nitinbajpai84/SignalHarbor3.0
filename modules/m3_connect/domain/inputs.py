"""What module 3 starts from, read from the company plane by path (a module never imports another module).

- the newest signed module 2 outcome: intents/m2_baseline/outcomes/<outcome_id>.json   (contracts/baseline_outcome.yaml)
- the module 1 charter outcome it names:  intents/m1_intent/outcomes/<outcome_id>.json
- the measures' stored governance (who may see a restricted measure): intents/m2_baseline/<baseline_id>/kpis.json

`read_inputs` returns one plain dict. A viewer who may not see a restricted measure gets "A restricted measure" and nothing of it:
no definition, no owners, and none of the tables, fields or sources only reachable through it. The rule is module 2's
(domain/catalogue.py `_restricted_kpi`, `allows`): personal data not ruled out, or sensitive, makes a measure restricted; the named
people in `may_see` pass, and the head of data (company_admin) sees the whole (handoff.for_viewer).
"""
import re
from dataclasses import dataclass

from sh_platform.jsonfile import read_json_strict

RESTRICTED_NAME = "A restricted measure"
UNREADABLE = "The baseline or charter records could not be read. Please ask your administrator."
_HEX = re.compile(r"[0-9a-f]{16,64}")
_TABS = ("sources", "tables", "fields", "extractions", "kpis")


class InputsUnreadable(Exception):
    """A plain-words failure; never contains a path or an id."""


@dataclass(frozen=True)
class Viewer:
    name: str
    roles: frozenset[str]
    shared_name: bool = False  # another account has the same display name, so a name alone cannot say who this is


SYSTEM = Viewer("", frozenset({"_system"}))  # builds shared records and scores; may see everything, is never served to a person


def _norm(text) -> str:
    return " ".join(str(text or "").lower().split())


def _read(plane, *parts) -> object:
    try:
        return read_json_strict(plane.path(*parts))
    except (OSError, ValueError):
        raise InputsUnreadable(UNREADABLE) from None


def _outcome(plane, area: str, outcome_id, kind: str) -> dict | None:
    if not (isinstance(outcome_id, str) and _HEX.fullmatch(outcome_id)):
        return None
    d = _read(plane, "intents", area, "outcomes", f"{outcome_id}.json")
    return d if isinstance(d, dict) and d.get("kind") == kind else None


def read_baseline_outcome(plane, outcome_id) -> dict | None:
    """Only a signed outcome counts: a signing date and at least one signature. An unsigned file is refused."""
    d = _outcome(plane, "m2_baseline", outcome_id, "baseline")
    return d if d and str(d.get("signed_at") or "").strip() and d.get("signatures") else None


def read_charter_outcome(plane, outcome_id) -> dict | None:
    return _outcome(plane, "m1_intent", outcome_id, "charter")


def signed_baselines(plane) -> list[dict]:
    folder = plane.path("intents", "m2_baseline", "outcomes")
    return [d for f in (folder.glob("*.json") if folder.is_dir() else []) if (d := read_baseline_outcome(plane, f.stem))]


def latest_signed_baseline(plane) -> dict | None:
    """The outcome record of the newest signed baseline in this company, or None."""
    return max(signed_baselines(plane), key=lambda d: str(d.get("signed_at") or ""), default=None)


# ---- reading cells ------------------------------------------------------------------------------------------------------------------
def _v(cell):
    """A catalogue cell is {value, mark, ...}; anything else is the value itself. An unknown reads as None, never as a blank answer."""
    if isinstance(cell, dict) and "mark" in cell:
        return None if cell.get("mark") == "unknown" else cell.get("value")
    return cell


def _t(cell) -> str:
    v = _v(cell)
    return "; ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else ("" if v is None else str(v))


def _ids(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", text) if p.strip()]


def _names(text: str) -> frozenset[str]:
    return frozenset(_norm(p) for p in re.split(r"[,;]|\band\b", text or "") if p.strip())


def _restricted(gov) -> bool:
    gov = gov if isinstance(gov, dict) else {}
    return gov.get("personal", "not_sure") != "no" or bool(gov.get("sensitive"))  # not sure counts as personal


def _on_list(names: frozenset[str], viewer: Viewer, roles: tuple[str, ...] = ()) -> bool:
    """Module 2's `allows` (domain/catalogue.py): a listed role passes; named people pass; where nobody is named, only the company admin."""
    if set(roles) & viewer.roles or "_system" in viewer.roles:
        return True
    if not names and not roles:
        return "company_admin" in viewer.roles
    return _norm(viewer.name) in names and not viewer.shared_name


def class_ok(row: dict, source_names: frozenset[str], measure_names: frozenset[str], viewer: Viewer) -> bool:
    """Module 2's field class guard: a field whose "Personal data class" is not "Neither" (blank is the source's own answer) is seen only by
    people named on its source or on a restricted measure it feeds; where nobody is named, only the company admin."""
    cls = _t(row.get("Personal data class"))
    return not cls or cls == "Neither" or _on_list(source_names | measure_names, viewer)


def _may_see(gov: dict, viewer: Viewer) -> bool:
    gov = gov if isinstance(gov, dict) else {}
    restricted = _restricted(gov)
    if not restricted or "_system" in viewer.roles:
        return True
    names = {_norm(n) for n in gov.get("may_see") or [] if _norm(n)}
    if not names:  # A-069: nobody named yet, only the company admin; once named the admin is like anyone else
        return "company_admin" in viewer.roles
    return _norm(viewer.name) in names and not viewer.shared_name


def _kpi_governance(plane, baseline_id) -> dict[str, dict]:
    if not (isinstance(baseline_id, str) and _HEX.fullmatch(baseline_id)):
        return {}
    rows = _read(plane, "intents", "m2_baseline", baseline_id, "kpis.json")
    return {str(k["id"]): k for k in rows if isinstance(k, dict) and k.get("id")} if isinstance(rows, list) else {}


def _problem_priority(charter: dict) -> dict[str, str]:
    return {str(p["id"]): str(p.get("priority") or "") for p in charter.get("problems") or [] if isinstance(p, dict) and p.get("id")}


def _item(it: dict, hidden: set[str]) -> dict:
    """A pain point, future signal or lever. The charter holds no link to measures (outcome.yaml); a `measures` list is kept if one is there."""
    links = [m for m in it.get("measures") or it.get("measure_ids") or [] if m not in hidden]
    return {"id": it.get("id"), "title": it.get("title"), "priority": it.get("priority"), "so_that": it.get("so_that"), "measures": links}


WITHHELD = "Withheld: it names something you may not see."
_TECH_IDS = ("sources", "tables", "fields")
_TECH_TEXT = ("calculation", "filters", "grain", "period", "currency_basis", "notes")


def _norm_words(text) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def _mentions(text, terms: list[str]) -> bool:
    """Module 2's rule (domain/ambiguities.py `mentions`): a text that names something this viewer may not see. A name of 2 or 3 characters
    must match as a whole word; a longer one also inside a word."""
    hay = _norm_words(text)
    pad = f" {hay} "
    return any((len(t) >= 4 and t in hay) or (len(t) >= 2 and f" {t} " in pad) for t in (_norm_words(x) for x in terms))


_MARKDOWN, _ROW_ID = re.compile(r"[`*]+"), re.compile(r"\b[A-Z]{1,2}\d{2,4}\b")


def plain_text(text, names: dict[str, str | None]):
    """Module 2's text as plain words: no backticks or asterisks, and a catalogue row id ("F001") becomes the row's name, or goes when the
    reader may not see the row (`names[id]` is None). An id followed by its own name keeps the name once. Anything not in `names` stays."""
    if text is None:
        return None
    out = _MARKDOWN.sub("", str(text))
    for rid, name in names.items():
        if name:
            out = re.sub(rf"\b{re.escape(rid)}\b(?:\s*\(\s*{re.escape(name)}\s*\)|\s+{re.escape(name)}(?!\w))", name, out)
    out = _ROW_ID.sub(lambda m: (names[m.group()] or "") if m.group() in names else m.group(), out)
    return re.sub(r"\s+([,.;:])", r"\1", " ".join(out.split()))


def _row_names(rows: dict, kept: dict, hidden: set[str]) -> dict[str, str | None]:
    """{catalogue row id: name for a reader who may see it, None for one who may not}: sources, tables, fields, extractions and measures."""
    heads = {"sources": ("Source ID", "Source name"), "tables": ("Item ID", "Name of table, file or document type"),
             "fields": ("Field ID", "Field name as in the source"), "extractions": ("Extract ID", "What to extract")}
    out = {_t(r.get(i)): (_t(r.get(n)) or None) if any(r is k for k in kept[t]) else None
           for t, (i, n) in heads.items() for r in rows[t] if _t(r.get(i))}
    out.update({_t(r.get("KPI ID")): None if _t(r.get("KPI ID")) in hidden else (_t(r.get("KPI name")) or None) for r in rows["kpis"] if _t(r.get("KPI ID"))})
    return out


def _technical(block, ids: dict[str, set[str]]) -> dict:
    """One measure's technical definition (M2-E4), plain: a text part is its value (None when marked unknown), an id part only the ids
    of catalogue rows this reader may see. `confirmed` is {by, at} or None."""
    block = block if isinstance(block, dict) else {}
    out = {k: [x for x in _ids(_t(block.get(k))) if x in ids[k]] for k in _TECH_IDS}
    out.update({k: (_t(block.get(k)).strip() or None) for k in _TECH_TEXT})
    out["confirmed"] = block.get("confirmed") if isinstance(block.get("confirmed"), dict) else None
    return out


def _new_keys(record: dict, kept: dict, rows: dict, hidden: set[str], guarded: set[str]) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """(technical by measure id, accepted ambiguities, left-out measures, glossary) from the keys module 2 added (M2-E4); an older record has
    none, which reads as empty. Restricted measures, and any text naming a catalogue row or measure this viewer may not see, are left out."""
    heads = {"sources": ("Source ID", "Source name"), "tables": ("Item ID", "Name of table, file or document type"),
             "fields": ("Field ID", "Field name as in the source")}
    ids = {t: {_t(r.get(heads[t][0])) for r in kept[t]} for t in _TECH_IDS}
    terms = [x for t, (i, n) in heads.items() for r in rows[t] if _t(r.get(i)) not in ids[t] for x in (_t(r.get(i)), _t(r.get(n))) if x]
    terms += [x for r in rows["kpis"] if _t(r.get("KPI ID")) in hidden for x in (_t(r.get("KPI ID")), _t(r.get("KPI name"))) if x]
    tech = record.get("technical") if isinstance(record.get("technical"), dict) else {}
    names = _row_names(rows, kept, hidden)
    amb = [{**a, **{f: plain_text(a[f], names) for f in ("text", "question", "where", "reason") if a.get(f)}}
           for a in record.get("ambiguities") or [] if isinstance(a, dict) and a.get("kpi_id") and a["kpi_id"] not in hidden
           and not _mentions(" ".join(str(a.get(f) or "") for f in ("text", "question", "where", "reason")), terms)]
    left = [{"kpi_id": str(r["kpi_id"]), "name": r.get("name"), "by": r.get("by"), "at": r.get("at"),
             "reason": WITHHELD if _mentions(r.get("reason"), terms) else plain_text(r.get("reason"), names), "restricted": str(r["kpi_id"]) in guarded}
            for r in record.get("left_out") or [] if isinstance(r, dict) and r.get("kpi_id") and r["kpi_id"] not in hidden]
    gl = [e for e in record.get("glossary") or [] if isinstance(e, dict) and e.get("kpi_id") not in hidden]
    return {k: _technical(b, ids) for k, b in tech.items() if k not in hidden}, amb, left, gl


def hidden_terms(full: dict, mine: dict) -> list[str]:
    """Names and ids of what `full` (the head of data's read) has and `mine` lacks: catalogue rows and measures this reader may not see."""
    heads = {"sources": ("Source ID", "Source name"), "tables": ("Item ID", "Name of table, file or document type"), "fields": ("Field ID", "Field name as in the source")}
    out = [x for t, (i, n) in heads.items() for r in full[t] if not any(_t(r.get(i)) == _t(k.get(i)) for k in mine[t]) for x in (_t(r.get(i)), _t(r.get(n))) if x]
    mine_ids = {m["id"]: m for m in mine["measures"]}
    out += [x for m in full["measures"] if mine_ids.get(m["id"], {}).get("restricted") for x in (m["id"], m.get("name")) if x]
    return out + [x for r in full.get("left_out", []) if r["restricted"] and r["kpi_id"] not in {y["kpi_id"] for y in mine.get("left_out", [])} for x in (r["kpi_id"], r.get("name")) if x]


def mask_text(text, terms: list[str]):
    """The text, or "Withheld" when it names something this reader may not see."""
    return WITHHELD if text and _mentions(text, terms) else text


def read_inputs(plane, baseline_outcome: dict, charter_outcome_id, viewer: Viewer) -> dict:
    cat = baseline_outcome.get("catalogue") or {}
    rows = {t: [r for r in cat.get(t) or [] if isinstance(r, dict)] for t in _TABS}
    charter = read_charter_outcome(plane, charter_outcome_id) or {}
    gov = _kpi_governance(plane, baseline_outcome.get("baseline_id"))
    priority = _problem_priority(charter)

    measures, hidden = [], set()
    for r in rows["kpis"]:
        mid = _t(r.get("KPI ID"))
        k = gov.get(mid, {})
        if not _may_see(k.get("governance"), viewer):
            hidden.add(mid)
            measures.append({"id": mid, "name": RESTRICTED_NAME, "restricted": True})
            continue
        problems = [str(p) for p in k.get("problem_ids") or []]
        prio = next((priority[p] for p in problems if priority.get(p)), None) or _t(r.get("Priority")) or None
        measures.append({"id": mid, "name": _t(r.get("KPI name")), "restricted": False, "guarded": _restricted(k.get("governance")), "priority": prio,
                         "problem_ids": problems, "problem": _t(r.get("Problem it serves")) or None,
                         "definition": _t(r.get("Definition")) or None,
                         "owners": {"business": _t(r.get("Business owner")) or None, "data": _t(r.get("Data owner")) or None,
                                    "process": _t(r.get("Process owner")) or None},
                         "may_see": list((k.get("governance") or {}).get("may_see") or [])})

    def touches(text: str) -> bool:
        return any(m in hidden for m in _ids(text))

    tables = [t for t in rows["tables"] if not touches(_t(t.get("Related KPIs")))]
    behind_hidden = {_t(t.get("Source ID")) for t in rows["tables"] if touches(_t(t.get("Related KPIs")))} - {_t(t.get("Source ID")) for t in tables}
    guarded = {m: frozenset(_norm(n) for n in (k.get("governance") or {}).get("may_see") or [])
               for m, k in gov.items() if _restricted(k.get("governance"))}
    tied = {_t(t.get("Source ID")) for t in rows["tables"] if any(m in guarded for m in _ids(_t(t.get("Related KPIs"))))}

    def source_open(s: dict) -> bool:
        """Module 2's source rule (catalogue.guards): "No" is open; "Not sure" is open unless a list is named, a restricted measure is tied to
        it or the organiser answered, then the named, the sponsor and the head of data pass; anything else needs a name, and with none only the head of data."""
        sid, names, cell = _t(s.get("Source ID")), _names(_t(s.get("Who may see it"))), s.get("Contains personal data?")
        said = _t(cell)
        if said == "No":
            return True
        if _norm(said) == "not sure":
            organiser = _norm(cell.get("by", "") if isinstance(cell, dict) else "") == "the organiser"
            return _on_list(names, viewer, ("sponsor", "company_admin")) if (names or sid in tied or organiser) else True
        return _on_list(names, viewer)

    sources = [s for s in rows["sources"] if _t(s.get("Source ID")) not in behind_hidden and source_open(s)]
    open_ids = {_t(s.get("Source ID")) for s in sources}
    tables = [t for t in tables if _t(t.get("Source ID")) in open_ids]
    kept_t = {_t(t.get("Item ID")) for t in tables}
    src_names = {_t(s.get("Source ID")): _names(_t(s.get("Who may see it"))) for s in sources}
    table_src = {_t(t.get("Item ID")): _t(t.get("Source ID")) for t in tables}

    def class_pass(r: dict, item_key: str) -> bool:
        feeds = _ids(_t(r.get("Feeds KPI")))
        return class_ok(r, src_names.get(table_src.get(_t(r.get(item_key)), ""), frozenset()),
                        frozenset().union(*(guarded.get(m, frozenset()) for m in feeds)), viewer)

    fields = [f for f in rows["fields"] if _t(f.get("Item ID")) in kept_t and not touches(_t(f.get("Feeds KPI"))) and class_pass(f, "Item ID")]
    extractions = [e for e in rows["extractions"] if _t(e.get("Item ID (document type)")) in kept_t and not touches(_t(e.get("Feeds KPI")))
                   and class_pass(e, "Item ID (document type)")]

    kept = {"sources": sources, "tables": tables, "fields": fields, "extractions": extractions}
    tech, amb, left, glossary = _new_keys(baseline_outcome, kept, rows, hidden, set(guarded))
    left_ids = {r["kpi_id"] for r in left}
    for m in (m for m in measures if not m.get("restricted")):  # M2-E4 keys ride on the measure; a restricted one stays a bare placeholder
        m["technical"] = tech.get(m["id"])
        m["ambiguities"] = [a for a in amb if a["kpi_id"] == m["id"]]
    # a left-out measure is not scored or tried
    measures = [m for m in measures if m["id"] not in left_ids]
    idh = {"sources": "Source ID", "tables": "Item ID", "fields": "Field ID", "extractions": "Extract ID"}
    gone = tuple(f"{t} {_t(r.get(idh[t]))}:" if _t(r.get(idh[t])) else f"{t} row {i + 1}:"  # module 2's naming (handoff._row_name)
                 for t, lst in kept.items() for i, r in enumerate(rows[t]) if not any(r is k for k in lst))

    return {"baseline_outcome_id": baseline_outcome.get("outcome_id"), "charter_outcome_id": charter_outcome_id,
            "measures": measures, "left_out": left, "glossary": glossary, "sources": sources, "tables": tables, "fields": fields, "extractions": extractions,
            "pain_points": [_item(i, hidden) for i in charter.get("pain_points") or [] if isinstance(i, dict)],
            "future_signals": [_item(i, hidden) for i in charter.get("future_signals") or [] if isinstance(i, dict)],
            "levers": [_item(i, hidden) for i in charter.get("levers") or [] if isinstance(i, dict)],
            "process_map": {k: v for k, v in (baseline_outcome.get("process_map") or {}).items() if k not in hidden}
            if isinstance(baseline_outcome.get("process_map"), dict) else {},
            "gaps": [g for g in baseline_outcome.get("gaps") or []
                     if g.get("kpi_id") not in hidden and not str(g.get("where") or "").startswith(gone)]}
