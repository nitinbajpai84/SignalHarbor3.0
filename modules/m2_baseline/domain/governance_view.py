"""M2-E3: the governance view of a baseline, DERIVED from where governance is stored today and never a second store.

Stored today: per measure (kpis.json) personal, sensitive, may_see; per source (catalogue) "Contains personal data?" and
"Who may see it"; per field (catalogue) "Personal data class", and now the field's own "Who may see it" cell (an added cell on
the field row, C.FIELD_VISIBILITY, a narrower limit only). This file reads those and answers:
  analyse()          everything, for every row, unfiltered (the server only)
  view()             what one person may see: a measure with its sources and fields, five columns of governance, a summary
  table()            the same rows flat, for the Excel sheet "Governance"
  governance_ready() (ready, reasons) for the later sign-off; ambiguities() in the shared contract's shape
  propose()          Lens's guess of a field's personal-data class, from its name, its pack and its measure (no model call)
  set_field_names()  the organiser or sponsor narrows one field; never wider than its source and measures allow
  confirm_proposals() a person turns guesses into their own decision; a decision already made is never replaced
The viewer filtering is the catalogue's own (`C.guards`, `W.may_see`): one rule, everywhere.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov, unknown

FIELD_CLASS = "Personal data class"
RESTRICTED_NOTE = "Some measures are restricted to named people"
EVERYONE = "Everyone in the company with access to this module"
ORGANISER_ONLY = "Only the organiser, until people are named"
NAMED_PEOPLE = "Named people"
UNDECIDED_CLASSES = ("", "not sure")
GOVERNORS = ("company_admin", "sponsor")  # who may change who can see (the work list's rule)
CONFIRMED_FROM = "confirmed from Lens's proposal"
FIELD_COLUMNS = ("Level", "Name", "Belongs to", "Holds personal data", "Sensitive to the business", "Who may see it",
                 "Decided by", "Decided on", "Still undecided")


@lru_cache(maxsize=1)
def _words() -> dict:
    d = yaml.safe_load((Path(__file__).resolve().parent.parent / "contracts" / "governance.yaml").read_text(encoding="utf-8"))
    return {"kinds": {k: [re.compile(p) for p in v] for k, v in d["kinds"].items()}, "kind_words": d["kind_words"],
            "document_kinds": {k: [re.compile(p) for p in v] for k, v in d["document_kinds"].items()}}


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _people(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", text or "") if p.strip()]


def _is_governor(viewer: C.Viewer) -> bool:
    return any(r in viewer.roles for r in GOVERNORS)


def _stamp(cell: Any) -> dict | None:
    return {"by": cell.get("by"), "at": cell.get("at")} if isinstance(cell, dict) and cell.get("by") and C.text_of(cell) else None


# ---- everything, unfiltered ---------------------------------------------------------------------------------------------------

def analyse(cat: dict, kpis: list[dict]) -> dict:
    """The whole baseline's governance, row by row, for the server to filter. `cat` is the catalogue as stored (before the derived
    columns); `kpis` is kpis.json."""
    gov = {str(k["id"]): k.get("governance") or {} for k in kpis if isinstance(k, dict) and k.get("id")}
    guards = C.guards(cat, gov)
    sources, tables, fields = {}, {}, {}
    for t in cat["tables"]:
        tables[C.row_id("tables", t)] = {"name": C.text_of(t.get("Name of table, file or document type")), "source": C.text_of(t.get("Source ID")),
                                          "kpis": C.split_ids(C.text_of(t.get("Related KPIs")))}
    for s in cat["sources"]:
        sid, cell = C.row_id("sources", s), s.get("Contains personal data?")
        said = C.text_of(cell)
        sources[sid] = {"kind": "source", "id": sid, "name": C.text_of(s.get("Source name")) or sid, "personal": said,
                        "own": _people(C.text_of(s.get("Who may see it"))), "guards": guards.get(("sources", sid), []),
                        "decided": _stamp(cell) if said and said.lower() != "not sure" else None,
                        "undecided": [] if said and said.lower() != "not sure" else ["personal data is not decided"]}
    for f in cat["fields"]:
        fid, cell = C.row_id("fields", f), f.get(FIELD_CLASS)
        said, tid = C.text_of(cell), C.text_of(f.get("Item ID"))
        table = tables.get(tid, {})
        fields[fid] = {"kind": "field", "id": fid, "name": C.text_of(f.get("Field name as in the source")) or fid, "table": table.get("name", ""),
                       "source_id": table.get("source", ""), "feeds": C.split_ids(C.text_of(f.get("Feeds KPI"))), "class": said,
                       "own": _people(C.text_of(f.get(C.FIELD_VISIBILITY))), "guards": guards.get(("fields", fid), []),
                       "decided": _stamp(cell) if said.lower() not in UNDECIDED_CLASSES else None,
                       "undecided": [] if said.lower() not in UNDECIDED_CLASSES else ["no personal-data decision"], "proposal": None}
    measures, order = {}, []
    for k in kpis:
        if not isinstance(k, dict) or not k.get("id"):
            continue
        kid, g = str(k["id"]), k.get("governance") or {}
        why = []
        if g.get("personal", "not_sure") == "not_sure":
            why.append("personal data is not decided")
        if C._restricted_kpi(g) and not g.get("may_see"):
            why.append("nobody is named to see it yet")
        measures[kid] = {"kind": "measure", "id": kid, "name": str(k.get("name") or kid), "personal": g.get("personal", "not_sure"),
                         "sensitive": bool(g.get("sensitive")), "restricted": C._restricted_kpi(g), "names": [str(n) for n in g.get("may_see") or []],
                         "decided": k.get("governance_decided") if "personal data is not decided" not in why else None, "undecided": why, "kpi": k}
        order.append(kid)
    for f in fields.values():
        f["sensitive"] = f["class"] == "Sensitive to the business" or any(measures.get(k, {}).get("sensitive") for k in f["feeds"])
    return {"measures": measures, "order": order, "sources": sources, "tables": tables, "fields": fields, "guards": guards}


def _links(an: dict, kid: str) -> tuple[list[dict], list[dict]]:
    """The sources and the fields that serve one measure."""
    sids = dict.fromkeys(t["source"] for t in an["tables"].values() if kid in t["kpis"] and t["source"] in an["sources"])
    return [an["sources"][s] for s in sids], [f for f in an["fields"].values() if kid in f["feeds"]]


# ---- Lens proposes (pure code: names, the pack's own spellings and flags, the measure) -----------------------------------------

def pack_parts(packs, industry: str) -> dict:
    """The parts of the company's industry pack the proposals read: the feeds (with their personal-data flags), the column spellings
    and the document fields. The industry is a parameter; an industry with no pack gives empty parts."""
    out = {"feeds": {}, "synonyms": {}, "evidence": {}, "label": ""}
    try:
        pack = packs.load(str(industry or ""))
    except ValueError:
        return out
    out["label"] = getattr(pack, "suggestion_label", "")
    for key, name, inner in (("feeds", "feeds", "feeds"), ("synonyms", "column_synonyms", "feeds"), ("evidence", "evidence_fields", "fields")):
        try:
            raw = pack.section(name) if name in pack.sections() else None
        except (KeyError, OSError, ValueError):
            raw = None
        got = raw.get(inner) if isinstance(raw, dict) else None
        out[key] = got if isinstance(got, dict) else {}
    return out


def _snake(name: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name)).lower()))


def propose(name: str, measures: list[dict], parts: dict | None = None) -> dict | None:
    """Lens's guess of one field's personal-data class: {class, kind, mark: "guessed", reason}, or None when nothing says anything.
    `measures` are the analysed measures the field feeds. A guess is never a decision: it is shown as a guess and a person confirms it."""
    parts = parts or {}
    guess = lambda cls, kind, why: {"class": cls, "kind": kind, "mark": "guessed", "reason": why, "by": "Lens"}  # noqa: E731
    hits = []
    for feed, body in (parts.get("feeds") or {}).items():
        for fld in (body or {}).get("fields") or []:
            level, why = C._name_score(name, str(fld.get("id")), ((parts.get("synonyms") or {}).get(feed) or {}).get(fld.get("id")))
            if level >= 2:
                hits.append((bool(fld.get("pii")), why))
    if hits:
        personal = next((h for h in hits if h[0]), None)
        if personal:
            return guess("Personal data", "other", f"{personal[1]}, and the industry pack marks that as personal data")
        return guess("Neither", None, f"{hits[0][1]}, and the industry pack does not mark that as personal data")
    key = _snake(name)
    for kind, patterns in _words()["kinds"].items():
        if any(p.search(key) for p in patterns):
            return guess("Personal data", kind, f"the name looks like {_words()['kind_words'][kind]}")
    if key in {_snake(k) for k in (parts.get("evidence") or {})}:
        return guess("Neither", None, "the industry pack lists it as a business field read from documents")
    if measures and all(m["personal"] == "no" and not m["sensitive"] for m in measures):
        return guess("Neither", None, "nothing in its name suggests personal data, and the measure it feeds is not personal")
    return None


def attach_proposals(an: dict, parts: dict | None) -> dict:
    for f in an["fields"].values():
        if f["undecided"]:
            f["proposal"] = propose(f["name"], [an["measures"][k] for k in f["feeds"] if k in an["measures"]], parts)
    return an


# ---- who may see what, for one person -------------------------------------------------------------------------------------------

def _seen_measure(an: dict, kid: str, viewer: C.Viewer) -> bool:
    return "company_admin" in viewer.roles or W.may_see(an["measures"][kid]["kpi"], viewer.name, viewer.account_id, False)


def _seen_row(an: dict, row: dict, viewer: C.Viewer) -> bool:
    if "company_admin" in viewer.roles:
        return True
    if not all(C.allows(g, viewer) for g in row["guards"]):
        return False
    return all(_seen_measure(an, k, viewer) for k in row.get("feeds", []) if k in an["measures"])


def _names_shown(names: list[str], viewer: C.Viewer) -> list[str]:
    """A named list is shown to the organiser, the sponsor and the people on it; to nobody else."""
    return names if _is_governor(viewer) or C.norm(viewer.name) in {C.norm(n) for n in names} else []


def _visible_to(an: dict, row: dict, viewer: C.Viewer) -> dict:
    if row["kind"] == "measure":
        if not row["restricted"]:
            return {"mode": "everyone", "text": EVERYONE, "names": []}
        names = _names_shown(row["names"], viewer)
        if not row["names"]:
            return {"mode": "organiser", "text": ORGANISER_ONLY, "names": []}
        return {"mode": "named", "text": ", ".join(names) or NAMED_PEOPLE, "names": names}
    if row["own"]:
        names = _names_shown(row["own"], viewer)
        return {"mode": "named", "text": ", ".join(names) or NAMED_PEOPLE, "names": names}
    if row["kind"] == "source":
        return {"mode": "organiser", "text": ORGANISER_ONLY, "names": []} if row["guards"] else {"mode": "everyone", "text": EVERYONE, "names": []}
    follows = [an["measures"][k]["name"] for k in row["feeds"] if k in an["measures"] and an["measures"][k]["restricted"]]
    if follows:
        return {"mode": "follows", "text": "Follows the measure " + ", ".join(f"“{n}”" for n in follows), "names": []}
    if row["guards"]:
        return {"mode": "follows", "text": "Follows its source", "names": []}
    return {"mode": "everyone", "text": EVERYONE, "names": []}


def _public(an: dict, row: dict, viewer: C.Viewer) -> dict:
    kind = row["kind"]
    base = {"kind": kind, "id": row["id"], "name": row["name"], "visible_to": _visible_to(an, row, viewer), "decided": row["decided"],
            "undecided": row["undecided"], "restricted": row["restricted"] if kind == "measure" else bool(row["guards"])}
    if kind == "measure":
        return {**base, "personal": row["personal"], "sensitive": row["sensitive"]}
    if kind == "source":
        return {**base, "personal": row["personal"], "sensitive": None}
    return {**base, "personal": row["class"], "sensitive": row["sensitive"], "table": row["table"], "source": an["sources"].get(row["source_id"], {}).get("name", ""),
            "feeds": [{"id": k, "name": an["measures"][k]["name"]} for k in row["feeds"] if k in an["measures"]], "proposal": row["proposal"]}


def _lines(measures: list[dict], sources: list[dict], fields: list[dict]) -> list[str]:
    out = []
    for rows, one, many in ((measures, "measure", "measures"), (sources, "source", "sources"), (fields, "field", "fields")):
        n = sum("personal data is not decided" in r["undecided"] or "no personal-data decision" in r["undecided"] for r in rows)
        if n:
            out.append(f"{_plural(n, one, many)} {'has' if n == 1 else 'have'} no personal-data decision")
    n = sum("nobody is named to see it yet" in r["undecided"] for r in measures)
    if n:
        out.append(f"{_plural(n, 'restricted measure', 'restricted measures')} {'has' if n == 1 else 'have'} nobody named to see {'it' if n == 1 else 'them'}")
    return out


def _summary(measures: list[dict], sources: list[dict], fields: list[dict], restricted) -> dict:
    count = lambda rows: {"total": len(rows), "decided": sum(not r["undecided"] for r in rows), "undecided": sum(bool(r["undecided"]) for r in rows),  # noqa: E731
                          "restricted": sum(bool(restricted(r)) for r in rows)}
    return {"measures": count(measures), "sources": count(sources), "fields": count(fields), "lines": _lines(measures, sources, fields)}


def view(an: dict, viewer: C.Viewer) -> dict:
    """What this person may see. A measure, field or source they may not see is left out entirely (no stub, no id, no count); `note` says
    in plain words, without a number, that some measures are restricted. Counts come from the rows shown only."""
    rows, seen_m, seen_s, seen_f, used_s, used_f, omitted = [], [], {}, {}, set(), set(), False
    for kid in an["order"]:
        m = an["measures"][kid]
        if not _seen_measure(an, kid, viewer):
            omitted = True  # no row, no id, no count: only that something is left out
            continue
        srcs, flds = _links(an, kid)
        srcs = [s for s in srcs if _seen_row(an, s, viewer)]
        flds = [f for f in flds if _seen_row(an, f, viewer)]
        used_s.update(s["id"] for s in srcs)
        used_f.update(f["id"] for f in flds)
        seen_m.append(m)
        seen_s.update({s["id"]: s for s in srcs})
        seen_f.update({f["id"]: f for f in flds})
        rows.append({**_public(an, m, viewer), "sources": [_public(an, s, viewer) for s in srcs], "fields": [_public(an, f, viewer) for f in flds]})
    loose_s = [s for s in an["sources"].values() if s["id"] not in used_s and _seen_row(an, s, viewer)
               and not any(s["id"] == t["source"] and t["kpis"] for t in an["tables"].values())]
    loose_f = [f for f in an["fields"].values() if f["id"] not in used_f and not any(k in an["measures"] for k in f["feeds"]) and _seen_row(an, f, viewer)]
    seen_s.update({s["id"]: s for s in loose_s})
    seen_f.update({f["id"]: f for f in loose_f})
    restricted = lambda r: r["restricted"] if r["kind"] == "measure" else bool(r["guards"])  # noqa: E731
    return {"summary": _summary(seen_m, list(seen_s.values()), list(seen_f.values()), restricted), "measures": rows,
            "other_sources": [_public(an, s, viewer) for s in loose_s], "other_fields": [_public(an, f, viewer) for f in loose_f],
            "can_change": _is_governor(viewer), "organiser": "company_admin" in viewer.roles, "note": RESTRICTED_NOTE if omitted else None}


# ---- the Excel sheet: the same table, flat --------------------------------------------------------------------------------------

_PERSONAL = {"yes": "Yes", "no": "No", "not_sure": "Not decided"}


def _holds(row: dict) -> str:
    if row["kind"] == "measure":
        return _PERSONAL.get(row["personal"], "Not decided")
    said = str(row.get("personal") or "")
    return "Not decided" if said.lower() in UNDECIDED_CLASSES else said


def table(v: dict) -> list[list[str]]:
    """The view as rows of text under FIELD_COLUMNS. Exactly what `view` shows this person, in the order it shows it."""
    def line(r: dict, level: str, parent: str) -> list[str]:
        sens = "" if r.get("sensitive") is None else "Yes" if r["sensitive"] else "No"
        who = r.get("decided") or {}
        return [level, r["name"], parent, _holds(r), sens, r["visible_to"]["text"], str(who.get("by") or ""), str(who.get("at") or "")[:10],
                "; ".join(r["undecided"])]
    out = []
    for m in v["measures"]:
        out.append(line(m, "Measure", ""))
        out += [line(s, "Source", m["name"]) for s in m["sources"]] + [line(f, "Field", m["name"]) for f in m["fields"]]
    out += [line(s, "Source", "") for s in v["other_sources"]] + [line(f, "Field", "") for f in v["other_fields"]]
    return out


def columns(v: dict) -> dict:
    """The three governance columns the catalogue screen shows beside its Fields and KPIs tabs: {"kpis": {id: ...}, "fields": {id: ...}},
    each {personal, sensitive, who}. Only rows the person may see are in it."""
    pick = lambda r: {"personal": _holds(r), "sensitive": "" if r.get("sensitive") is None else "Yes" if r["sensitive"] else "No", "who": r["visible_to"]["text"]}  # noqa: E731
    flds = {f["id"]: pick(f) for m in v["measures"] if not m.get("hidden") for f in m["fields"]}
    flds.update({f["id"]: pick(f) for f in v["other_fields"]})
    return {"kpis": {m["id"]: pick(m) for m in v["measures"] if not m.get("hidden")}, "fields": flds}


# ---- the later sign-off, and the ambiguity list ---------------------------------------------------------------------------------

def governance_ready(cat: dict, kpis: list[dict], viewer: C.Viewer | None = None) -> tuple[bool, list[str]]:
    """(ready, reasons): ready only when no measure, source or field is left without its personal-data decision and no restricted
    measure is left with nobody named. The reasons are plain sentences with counts and name nothing. Does not sign anything.
    Without a viewer (the sign-off gate's own call) or for the organiser or sponsor the counts cover everything; for anyone else
    `ready` is still about everything but the sentences count only the rows that person may see."""
    an = analyse(cat, kpis)
    ms, ss, fs = list(an["measures"].values()), list(an["sources"].values()), list(an["fields"].values())
    full = _lines(ms, ss, fs)
    if viewer is None or _is_governor(viewer):
        return (not full, full)
    return (not full, _lines([m for m in ms if _seen_measure(an, m["id"], viewer)], [s for s in ss if _seen_row(an, s, viewer)],
                             [f for f in fs if _seen_row(an, f, viewer)]))


def ambiguity(key: str, text: str, question: str, where: str) -> dict:
    """One open governance ambiguity in the shared contract's shape; built by the one shared helper (domain/ambiguities.py), with a stable id."""
    return A.make("governance", text, question, where, None, id="gov-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]) | {"at": None}


def ambiguities(cat: dict, kpis: list[dict], viewer: C.Viewer) -> dict[str, list[dict]]:
    """The undecided governance items this person may see, as open ambiguities, listed under the measure each belongs to ("" when it
    belongs to none). Every item, its text and its `where` are built only from rows `viewer` may see; there is no unfiltered variant."""
    an, out = analyse(cat, kpis), {}
    def add(kid: str, key: str, text: str, question: str, where: str) -> None:
        out.setdefault(kid, []).append(ambiguity(f"{kid}|{key}", text, question, where))
    for kid, m in an["measures"].items():
        if not _seen_measure(an, kid, viewer):
            continue
        if "personal data is not decided" in m["undecided"]:
            add(kid, f"measure:{kid}", f"Personal data is not decided for “{m['name']}”.", f"Does “{m['name']}” hold personal data: yes or no?", f"{m['name']}: governance")
        if "nobody is named to see it yet" in m["undecided"]:
            add(kid, f"people:{kid}", f"Nobody is named to see “{m['name']}”.", f"Who may see “{m['name']}”?", f"{m['name']}: governance")
        srcs, flds = _links(an, kid)
        for s in srcs:
            if s["undecided"] and _seen_row(an, s, viewer):
                add(kid, f"source:{s['id']}", f"Personal data is not decided for the source “{s['name']}”.",
                    f"Does “{s['name']}” contain personal data?", f"{m['name']}: source {s['name']}")
        for f in flds:
            if f["undecided"] and _seen_row(an, f, viewer):
                add(kid, f"field:{f['id']}", f"The field “{f['name']}” has no personal-data decision.",
                    f"Is “{f['name']}” personal data, sensitive to the business, or neither?", f"{m['name']}: field {f['name']}")
    for f in an["fields"].values():
        if f["undecided"] and not any(k in an["measures"] for k in f["feeds"]) and _seen_row(an, f, viewer):
            add("", f"field:{f['id']}", f"The field “{f['name']}” has no personal-data decision.",
                f"Is “{f['name']}” personal data, sensitive to the business, or neither?", f"field {f['name']}")
    return out


# ---- changes (the caller holds the catalogue lock and saves) -----------------------------------------------------------------------

def set_field_names(cat: dict, kpis: list[dict], field_id: str, names: Any, by: str) -> dict:
    """The organiser or sponsor limits one field to these people (an empty list takes the limit away, so it follows its measures again).
    Never wider than the field's source and measures allow: a person they do not already let see it is refused. Returns the row."""
    row = C.find(cat, "fields", field_id)
    if row is None:
        raise C.CatalogueError("not_found", "We could not find that field.")
    if not isinstance(names, list) or len(names) > W.MAX_PEOPLE or not all(isinstance(n, str) and len(n) <= W.MAX_NAME for n in names):
        raise C.CatalogueError("invalid", "Please give the names of the people who may see it.")
    clean = list(dict.fromkeys(" ".join(n.split()) for n in names if n.strip()))
    if any(re.search(r"[,;\x00-\x1f]|\band\b", n, re.IGNORECASE) for n in clean):  # the stored list is read back splitting on these (C._names)
        raise C.CatalogueError("invalid", "Please give one name at a time, without commas, semicolons or the word “and”.")
    own = row.pop(C.FIELD_VISIBILITY, None)
    gov = {str(k["id"]): k.get("governance") or {} for k in kpis if isinstance(k, dict) and k.get("id")}
    try:
        base = C.guards(cat, gov).get(("fields", field_id), [])
    finally:
        if own is not None:
            row[C.FIELD_VISIBILITY] = own
    for n in clean:
        if not all(C.norm(n) in g for g in base):  # a wider list than the measure or source allows would relax it
            raise C.CatalogueError("invalid", "That would let someone see this field who may not see its measure or source. Give them access there first.")
    row[C.FIELD_VISIBILITY] = prov("; ".join(clean), "stated", by, C.contract()["from_words"]["edited"]) if clean else unknown(by, C.contract()["from_words"]["edited"])
    return row


def confirm_proposals(cat: dict, an: dict, viewer: C.Viewer, by: str, field_ids: Any = None, only_not_personal: bool = False) -> dict:
    """A person turns Lens's guesses into their own decision on the fields they may see. A field that already has a decision is left
    alone; a "Not sure" is only replaced by the organiser or sponsor (it would let more people see the field).
    `field_ids` limits it to those fields; `only_not_personal` to the guesses that say "Neither". Returns {confirmed, skipped}."""
    wanted = set(field_ids) if isinstance(field_ids, list) and all(isinstance(i, str) for i in field_ids) else None
    done = []
    for fid, f in an["fields"].items():
        p = f["proposal"]
        if (wanted is not None and fid not in wanted) or p is None or (only_not_personal and p["class"] != "Neither") or not _seen_row(an, f, viewer):
            continue
        if f["class"].lower() == "not sure" and not _is_governor(viewer):
            continue
        row = C.find(cat, "fields", fid)
        if row is not None:
            row[FIELD_CLASS] = prov(p["class"], "stated", by, CONFIRMED_FROM)
            done.append(fid)
    return {"confirmed": done, "skipped": len((wanted or set()) - set(done))}
