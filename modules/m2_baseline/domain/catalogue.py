"""The data catalogue (M2-16, M2-17, M2-24, M2-05): the template's five tabs as plain records, each cell a provenance value.

It describes data and never contains it. The layout (tabs, columns, lists, formulas) is read from contracts/catalogue.yaml, which was
taken from signal-harbor-data-catalogue-template.xlsx. Pure functions over dicts: the files are read and written by store/catalogue.py.

Reuse (D-031), earlier repo earlier-repo:
- emitters/baseline.py:433-526 _refresh_glossary_and_conflicts and resolve_conflict, reshaped from "terms in documents" to "cells in
  answers": candidates per cell, a conflict when the distinct values differ, a prior settlement kept, only a named person settles.
- emitters/baseline.py:648-702 build_data_landscape, reshaped: sources placed from the owners' answers, a person's edit never overwritten
  by a rebuild (its _source_touched rule), structured or not carried on every source.
- emitters/column_matcher.py:41-60, 73-80, 98-113, 182-242 (_name_score, _type_agrees, match), names and types only; the sample-value rungs
  (date parse rate, code-like values) are dropped because values never reach the catalogue.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.domain.questionnaire import load_questionnaire, source_rows

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "contracts"
TABS = ("sources", "tables", "fields", "extractions", "kpis")
NOT_A_PERSON = {"lens", "signal harbor", "the pack", "the organiser", "the charter", ""}  # a "named person" is none of these
MAX_TEXT = 2000
DERIVED_BY = "Signal Harbor"
DERIVED_FROM = "worked out from the other cells"
HIDDEN = "_hidden"
_UNDECIDED = "_undecided"  # on a visible source row whose personal-data answer is "Not sure": the screen says it is not decided yet
NOT_YET = "Not available yet"
QUALITY_RULES = "Quality rules (proposed by Lens)"  # the KPI column module 3's scan proposals sit in (contracts/catalogue.yaml `quality_rules`)
FIELD_VISIBILITY = "Who may see it"  # a field's own extra limit (M2-E3): an added cell on the field row, not a template column; only people on the list (and the organiser and sponsor) see the field


class CatalogueError(ValueError):
    """A refusal in plain words; `code` is for the route's status."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ---- the template's layout ------------------------------------------------------------------------------------------------

@lru_cache(maxsize=4)
def contract(folder: str | None = None) -> dict:
    path = Path(folder) / "catalogue.yaml" if folder else DEFAULT_DIR / "catalogue.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise CatalogueError("contract_unreadable", "The catalogue layout could not be read. Please ask your administrator.") from None
    if not isinstance(data, dict) or set(TABS) - set(data.get("tabs", {})):
        raise CatalogueError("contract_unreadable", "The catalogue layout could not be read. Please ask your administrator.")
    return data


def columns(tab: str) -> list[dict]:
    return contract()["tabs"][tab]["columns"]


def headers(tab: str) -> list[str]:
    return [c["header"] for c in columns(tab)]


def id_header(tab: str) -> str:
    return columns(tab)[0]["header"]


def _provenance_headers() -> set[str]:
    return set(contract()["provenance_columns"].values())


def is_computed(c: dict) -> bool:
    return "formula" in c


def input_headers(tab: str) -> list[str]:
    """The columns a person or the build fills: not the formulas, not the three provenance columns."""
    return [c["header"] for c in columns(tab) if not is_computed(c) and c["header"] not in _provenance_headers()]


def status_column(tab: str) -> dict:
    return [c for c in columns(tab) if is_computed(c)][-1]  # "Complete?", or "Ready for module 3?"


@lru_cache(maxsize=8)
def required(tab: str) -> tuple[str, ...]:
    """The input columns the template's own Complete? / Ready? formula counts, read from that formula."""
    head = status_column(tab)["formula"].split("OR(")[0]
    letters: set[str] = set()
    for a, b in re.findall(r"COUNTBLANK\(([A-Z])\{r\}(?::([A-Z])\{r\})?\)", head):
        letters.update(chr(x) for x in range(ord(a), ord(b or a) + 1))
    letters.update(re.findall(r'([A-Z])\{r\}<>""', head))
    by_letter = {c["letter"]: c["header"] for c in columns(tab)}
    return tuple(h for h in (by_letter[x] for x in sorted(letters)) if h in input_headers(tab) and h != id_header(tab))


def options(tab: str, header: str) -> list[str]:
    """The dropdown words of a column, from the Lists tab ([] when it is free text or points at another tab)."""
    ref = next((c.get("validation") for c in columns(tab) if c["header"] == header), None)
    m = re.fullmatch(r"Lists!\$([A-Z])\$2:\$[A-Z]\$(\d+)", ref or "")
    if not m:
        return []
    names = list(contract()["lists"]["columns"])
    return list(contract()["lists"]["columns"][names[ord(m.group(1)) - ord("A")]])


def schema() -> dict:
    """What a screen needs to draw each tab without knowing the template: titles, columns, which are required, the dropdown words, and
    which other tab a column picks its value from."""
    tabs, by_sheet = contract()["tabs"], {t["sheet"]: k for k, t in contract()["tabs"].items()}
    computed = _provenance_headers()
    out = {}
    for tab in TABS:
        need = set(required(tab))
        cols = []
        for c in columns(tab):
            m = re.match(r"'([^']+)'!", c.get("validation") or "")
            cols.append({"header": c["header"], "guidance": c["guidance"] or "", "required": c["header"] in need, "options": options(tab, c["header"]),
                         "computed": is_computed(c) or c["header"] in computed, "picks_from": by_sheet.get(m.group(1)) if m else None})
        out[tab] = {"sheet": tabs[tab]["sheet"], "title": tabs[tab]["title"], "blurb": tabs[tab]["blurb"], "id_header": id_header(tab),
                    "status_header": status_column(tab)["header"], "columns": cols}
    return out


# ---- cells and rows -------------------------------------------------------------------------------------------------------

def norm(text: Any) -> str:
    return " ".join(str(text).lower().split())


def value_of(cell: Any) -> Any:
    return cell.get("value") if isinstance(cell, dict) and cell.get("mark") != "unknown" else None


def text_of(cell: Any) -> str:
    v = value_of(cell)
    if isinstance(v, (list, tuple)):
        return "; ".join(str(x) for x in v)
    return "" if v is None else str(v)


def is_blank(cell: Any) -> bool:
    return not text_of(cell).strip()


def said_unknown(cell: Any) -> bool:
    """A named person said "I do not know" (as opposed to nobody having been asked yet)."""
    return isinstance(cell, dict) and cell.get("mark") == "unknown" and norm(cell.get("by", "")) not in NOT_A_PERSON


def is_manual(cell: Any) -> bool:
    return isinstance(cell, dict) and cell.get("from") in (contract()["from_words"]["edited"], contract()["from_words"]["settled"])


def filled(tab: str, header: str, cell: Any) -> bool:
    """Blank as the template's COUNTBLANK sees it. The one column the template says to answer "Unknown" counts a named person's "Unknown"."""
    if (tab, header) == ("tables", "Related KPIs") and said_unknown(cell):
        return True
    return not is_blank(cell)


def new_row(tab: str, row_id: str, by: str = DERIVED_BY) -> dict:
    row = {h: unknown(by, "not answered yet") for h in input_headers(tab)}
    row[id_header(tab)] = prov(row_id, "stated", DERIVED_BY, "numbered by the catalogue")
    return row


def row_id(tab: str, row: dict) -> str:
    return text_of(row.get(id_header(tab)))


def next_id(tab: str, rows: list[dict]) -> str:
    spec = contract()["ids"][tab]
    taken = [int(m.group(1)) for r in rows if (m := re.fullmatch(rf"{spec['prefix']}(\d+)", row_id(tab, r)))]
    return f"{spec['prefix']}{max(taken, default=0) + 1:0{spec['width']}d}"


def find(cat: dict, tab: str, wanted: str) -> dict | None:
    return next((r for r in cat.get(tab, []) if row_id(tab, r) == wanted), None)


def split_ids(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", text or "") if p.strip()]


def empty_catalogue() -> dict:
    return {t: [] for t in TABS}


# ---- derived columns: counts, Complete?, Ready?, and the three provenance columns ---------------------------------------------

def _how_sure(tab: str, row: dict) -> tuple[str, str, str]:
    cells = [row.get(h) for h in input_headers(tab) if h != id_header(tab)]
    known = [c for c in cells if isinstance(c, dict) and c.get("mark") in ("stated", "guessed") and not is_blank(c)]
    words = contract()["how_sure_words"]
    if not known:
        return words["unknown"], "", ""
    stated = [c for c in known if c["mark"] == "stated" and norm(c.get("by", "")) not in NOT_A_PERSON]
    by = ", ".join(dict.fromkeys(c["by"] for c in stated))
    at = max((str(c.get("at", ""))[:10] for c in stated), default="")
    return (words["guessed"] if any(c["mark"] == "guessed" for c in known) else words["stated"]), by, at


def _status_text(tab: str, row: dict) -> str:
    missing = sum(1 for h in required(tab) if not filled(tab, h, row.get(h)))
    if tab != "kpis":
        return "Complete" if missing == 0 else f"Missing {missing} required"
    tracking = text_of(row.get("Tracking status"))
    covered = tracking in ("Tracked today", "Can be tracked now") or (
        not is_blank(row.get("Next steps or project")) and not is_blank(row.get("Unknown accepted by (sponsor)")))
    return "Ready" if missing == 0 and covered else "Not ready"


def _mapped(cat: dict, kpi_id: str) -> tuple[int, int, int]:
    tables = sum(1 for t in cat["tables"] if kpi_id in split_ids(text_of(t.get("Related KPIs"))))
    fields = sum(1 for f in cat["fields"] if kpi_id in split_ids(text_of(f.get("Feeds KPI"))))
    extractions = sum(1 for x in cat["extractions"] if kpi_id in split_ids(text_of(x.get("Feeds KPI"))))
    return tables, fields, extractions


def _derived(value: Any, mark: str = "stated", source: str = DERIVED_FROM) -> dict:
    return prov(value, mark, DERIVED_BY, source) if value not in (None, "") else unknown(DERIVED_BY, source)


def with_derived(cat: dict) -> dict:
    """Every column of every tab, the formula columns counted for you, as the template would show them."""
    out = empty_catalogue()
    pc = contract()["provenance_columns"]
    for tab in TABS:
        for row in cat[tab]:
            full = dict(row)
            sure, by, at = _how_sure(tab, row)
            full[pc["how_sure"]] = _derived(sure, "stated")
            full[pc["by"]] = _derived(by)
            full[pc["at"]] = _derived(at)
            if tab == "kpis":
                counts = _mapped(cat, row_id(tab, row))
                for header, n in zip(("Tables mapped", "Fields mapped", "Extractions mapped"), counts):
                    full[header] = _derived(n)
            full[status_column(tab)["header"]] = _derived(_status_text(tab, row))
            out[tab].append({h: full[h] for h in headers(tab) if h in full})
    return out


def with_review(cat: dict, kpis: list[dict], version: dict | None, parts: list[dict]) -> dict:
    """The KPIs tab as it stands now (r4-1): tracking status (`kpis` already carry the one status, readiness.with_tracking), and from the
    open or signed version the review's date, next step and project, the sponsor's acceptance and each owner's confirmation, each cell
    stated by the person who gave it. Nothing is stored: the review changes after a refresh. A person's edit to a cell is kept; a
    measure with nothing to show keeps its "not answered yet"."""
    out = {**cat, "kpis": [dict(r) for r in cat["kpis"]]}
    words, by_id = contract()["mapping"]["tracking"], {str(k.get("id")): k for k in kpis if isinstance(k, dict)}
    version = version or {}
    owner_col = {"definition": "Business owner signed", "source": "Data owner signed", "process": "Process owner signed"}

    def put(row: dict, header: str, value: Any, by: str, source: str, at: Any = None) -> None:
        if value and not is_manual(row.get(header)):
            row[header] = prov(value, "stated", by or "", source, at)

    for row in out["kpis"]:
        kid = row_id("kpis", row)
        tr = (by_id.get(kid) or {}).get("tracking")
        if isinstance(tr, dict) and tr.get("mark") == "stated" and tr.get("value") in words:
            put(row, "Tracking status", words[tr["value"]], tr.get("by"), tr.get("from") or "the owners' answers", tr.get("at"))
        rev = (version.get("review") or {}).get(kid) or {}
        said = rev.get("set") or {}  # who set which field; an older record has none: recorded in the review, no person named
        def mine(*fs):  # the one person who set these fields; two people (or none recorded) name nobody
            got = [said[f] for f in fs if f in said]
            return max(got, key=lambda x: str(x.get("at"))) if got and len({g["by"] for g in got}) == 1 else {}
        put(row, "Tentative date", rev.get("tentative_date"), mine("tentative_date").get("by"), "the review", mine("tentative_date").get("at"))
        put(row, "Next steps or project", "; ".join(x for x in (rev.get("next_step"), rev.get("project") and f"project: {rev['project']}") if x),
            mine("next_step", "project").get("by"), "the review", mine("next_step", "project").get("at"))
        acc = rev.get("accepted") or {}
        put(row, "Unknown accepted by (sponsor)", acc.get("by"), acc.get("by"), "the sponsor's acceptance", acc.get("at"))
        put(row, "Date accepted", str(acc.get("at") or "")[:10], acc.get("by"), "the sponsor's acceptance", acc.get("at"))
        for p in parts:
            got = ((version.get("parts") or {}).get(kid) or {}).get(p["id"]) or {}
            put(row, owner_col[p["id"]], str(got.get("at") or "")[:10], got.get("by"), "confirmed on the sign-off page", got.get("at"))
    return out


def kpi_findings(cat: dict) -> dict[str, list[str]]:
    """What is wrong or unknown for each KPI, so none hides (M2-17, deck slide 13). Codes the screen words in plain language."""
    out: dict[str, list[str]] = {}
    for k in cat["kpis"]:
        kid, found = row_id("kpis", k), []
        if sum(_mapped(cat, kid)) == 0:
            found.append("nothing_mapped")
        found += [f"no_{w}_owner" for w, h in (("business", "Business owner"), ("data", "Data owner"), ("process", "Process owner")) if is_blank(k.get(h))]
        tracking = text_of(k.get("Tracking status"))
        if not tracking:
            found.append("tracking_unknown")
        elif tracking not in ("Tracked today", "Can be tracked now"):
            found.append("not_tracked_today")
        structures = [text_of(s.get("Structured or unstructured")) for t in cat["tables"] if kid in split_ids(text_of(t.get("Related KPIs")))
                      for s in cat["sources"] if row_id("sources", s) == text_of(t.get("Source ID"))]
        if structures and all(s == "Unstructured" for s in structures):
            found.append("only_unstructured")
        out[kid] = found
    return out


# ---- governance (M2-05): a row a person is not named for shows that it exists and nothing else -----------------------------------

@dataclass(frozen=True)
class Viewer:
    name: str
    roles: frozenset[str]
    shared_name: bool = False  # another account of the company has the same display name: a name alone cannot say who this is
    account_id: str | None = None  # the signed-in account, for the work list's account-bound lists (M2-E3 governance view)


def _names(text: str) -> frozenset[str]:
    return frozenset(norm(p) for p in re.split(r"[,;]|\band\b", text or "") if p.strip())


def _restricted_kpi(gov: dict | None) -> bool:
    gov = gov if isinstance(gov, dict) else {}
    return gov.get("personal", "not_sure") != "no" or bool(gov.get("sensitive"))  # "not sure" and nothing said count as personal


def _kpi_guard(gov: dict | None) -> frozenset[str] | None:
    gov = gov if isinstance(gov, dict) else {}
    return frozenset(norm(n) for n in gov.get("may_see") or []) if _restricted_kpi(gov) else None


ROLE_PASS = frozenset({"\0sponsor", "\0company_admin"})  # in a guard: these roles pass too (a "Not sure" source: they settle its conflicts)


def allows(guard: frozenset[str], viewer: Viewer) -> bool:
    """Named people pass. Where nobody has been named yet, only the company admin passes, so someone can name them."""
    if any(g[1:] in viewer.roles for g in guard if g.startswith("\0")):
        return True
    if not guard:
        return "company_admin" in viewer.roles
    return norm(viewer.name) in guard and not viewer.shared_name  # ponytail: lists hold names (SHARED.md); the account id stands in via a unique display name


def guards(cat: dict, governance: dict[str, dict]) -> dict[tuple[str, str], list[frozenset[str]]]:
    """For each row, the lists of names it is limited to. A row is seen only by someone on every list that applies to it."""
    g = contract()["governance"]
    kpi_guard = {k: _kpi_guard(governance.get(k)) for k in (row_id("kpis", r) for r in cat["kpis"])}
    out: dict[tuple[str, str], list[frozenset[str]]] = {}
    src_names: dict[str, frozenset[str]] = {}
    tied = {text_of(t.get("Source ID")) for t in cat["tables"] if any(kpi_guard.get(k) is not None for k in split_ids(text_of(t.get("Related KPIs"))))}
    for s in cat["sources"]:
        sid, names = row_id("sources", s), _names(text_of(s.get("Who may see it")))
        src_names[sid] = names
        cell = s.get("Contains personal data?")
        said = text_of(cell)
        if said in g["open_yes_no"]:
            out[("sources", sid)] = []
        elif norm(said) == "not sure":  # N-B: open unless a restricted measure is tied to it (its table, a named list, or the organiser's own answer)
            restricted = bool(names) or sid in tied or norm(cell.get("by", "")) == "the organiser"
            out[("sources", sid)] = [names | ROLE_PASS] if restricted else []
        else:
            out[("sources", sid)] = [names]
    for k, kg in kpi_guard.items():
        out[("kpis", k)] = [kg] if kg is not None else []
    for t in cat["tables"]:
        tid = row_id("tables", t)
        out[("tables", tid)] = out.get(("sources", text_of(t.get("Source ID"))), []) + [
            kpi_guard[k] for k in split_ids(text_of(t.get("Related KPIs"))) if kpi_guard.get(k) is not None]
    for tab in ("fields", "extractions"):
        for r in cat[tab]:
            rid, tid = row_id(tab, r), text_of(r.get("Item ID" if tab == "fields" else "Item ID (document type)"))
            parent = next((t for t in cat["tables"] if row_id("tables", t) == tid), None)
            kids = split_ids(text_of(r.get("Feeds KPI")))
            found = list(out.get(("tables", tid), []))
            found += [kpi_guard[k] for k in kids if kpi_guard.get(k) is not None]
            cls = text_of(r.get("Personal data class"))
            if cls and cls not in g["open_classes"]:  # a blank class is the source's answer, already in the table's guards
                names = set(src_names.get(text_of(parent.get("Source ID")) if parent else "", frozenset())).union(*(kpi_guard.get(k) or frozenset() for k in kids))
                found.append(frozenset(names))
            own = text_of(r.get(FIELD_VISIBILITY))
            if own:  # M2-E3: the field's own, narrower list; the organiser and the sponsor, who set it, always pass
                found.append(_names(own) | ROLE_PASS)
            out[(tab, rid)] = found
    for s in cat["sources"]:  # a source serving only restricted measures answers to their lists, so a removal from a list takes effect at once
        sid = row_id("sources", s)
        tids = {row_id("tables", t): t for t in cat["tables"] if text_of(t.get("Source ID")) == sid}
        kids = {k for t in tids.values() for k in split_ids(text_of(t.get("Related KPIs")))}
        kids |= {k for tab in ("fields", "extractions") for r in cat[tab]
                 if text_of(r.get("Item ID" if tab == "fields" else "Item ID (document type)")) in tids for k in split_ids(text_of(r.get("Feeds KPI")))}
        if kids and all(kpi_guard.get(k) is not None for k in kids):  # a source an open measure also serves stays visible: that measure already shows it
            out[("sources", sid)].append(frozenset().union(*(kpi_guard[k] for k in kids)))
    return out


def _rules_cell(rules: list[dict]) -> dict:
    return {"value": [f"{r['text']} (from {r['provenance']['from']})" for r in rules], "rules": rules, "mark": "guessed", "by": "Lens",
            "from": "the scan of the data", "at": max((r["provenance"]["at"] for r in rules), default=None)}


def with_quality_rules(cat: dict, rules: dict[str, list[dict]]) -> dict:
    """A copy of the catalogue with module 3's proposed quality rules on each measure's row, beside what was signed (the signed cells are not touched)."""
    out = {**cat, "kpis": []}
    for row in cat["kpis"]:
        row = {h: c for h, c in row.items() if h != QUALITY_RULES}
        if mine := rules.get(row_id("kpis", row)):
            row[QUALITY_RULES] = _rules_cell(mine)
        out["kpis"].append(row)
    return out


def _rules_seen(row: dict, row_guards: dict[tuple[str, str], list[frozenset[str]]], viewer: Viewer) -> None:
    """Keeps only the rules from a source this reader may see (a rule with no source, like a missing benchmark, follows the measure)."""
    cell = row.get(QUALITY_RULES)
    if not isinstance(cell, dict) or not cell.get("rules"):
        return
    keep = [r for r in cell["rules"] if r.get("source_id") is None
            or (("sources", r["source_id"]) in row_guards and all(allows(g, viewer) for g in row_guards[("sources", r["source_id"])]))]  # a source the catalogue does not know stays hidden
    if keep:
        row[QUALITY_RULES] = _rules_cell(keep)
    else:
        row.pop(QUALITY_RULES)


def view_of(cat: dict, row_guards: dict[tuple[str, str], list[frozenset[str]]], viewer: Viewer, drop: bool = False) -> tuple[dict, dict]:
    """The viewer's catalogue and its findings, worked out from the rows they may see only: counts, Complete? and findings never
    reflect a hidden row. The rest become {id, hidden} (or are left out, for the Excel file)."""
    seen = {t: [r for r in cat[t] if all(allows(g, viewer) for g in row_guards.get((t, row_id(t, r)), []))] for t in TABS}
    derived = with_derived(seen)
    out = empty_catalogue()
    for tab in TABS:
        full = iter(derived[tab])
        keep = {id(r) for r in seen[tab]}
        for r in cat[tab]:
            if id(r) in keep:
                shown = next(full)
                if tab == "sources" and norm(text_of(r.get("Contains personal data?"))) == "not sure":
                    shown[_UNDECIDED] = True  # shown, but the screen says the organiser has not decided on personal data yet
                if tab == "kpis":
                    _rules_seen(shown, row_guards, viewer)
                out[tab].append(shown)
            elif not drop:
                out[tab].append({id_header(tab): r[id_header(tab)], HIDDEN: True})
    return out, kpi_findings(seen)


def _undecided_rows(cat: dict, governance: dict[str, dict]) -> set[tuple[str, str]]:
    """Rows whose only reason to be hidden is a "Not sure" personal-data answer: no restricted KPI, named list or organiser setting is behind
    them. Pay and every other restricted row is never in this set, so a count of it says nothing about them."""
    kg = {row_id("kpis", k): _kpi_guard(governance.get(row_id("kpis", k))) for k in cat["kpis"]}
    restricted = lambda ids: any(kg.get(k) is not None for k in split_ids(text_of(ids)))  # noqa: E731
    open_tables = {text_of(t.get("Source ID")) for t in cat["tables"] if not restricted(t.get("Related KPIs"))}
    tied = {text_of(t.get("Source ID")) for t in cat["tables"] if restricted(t.get("Related KPIs"))}
    sure = {row_id("sources", s) for s in cat["sources"] if norm(text_of(s.get("Contains personal data?"))) == "not sure"
            and row_id("sources", s) not in tied and not _names(text_of(s.get("Who may see it")))
            and norm(s["Contains personal data?"].get("by", "")) != "the organiser"}
    out = {("sources", sid) for sid in sure}
    tables = {row_id("tables", t) for t in cat["tables"] if text_of(t.get("Source ID")) in sure and not restricted(t.get("Related KPIs"))}
    out |= {("tables", tid) for tid in tables}
    for tab, item in (("fields", "Item ID"), ("extractions", "Item ID (document type)")):
        out |= {(tab, row_id(tab, r)) for r in cat[tab] if text_of(r.get(item)) in tables and not restricted(r.get("Feeds KPI"))}
    return out


def hidden_note(shown: dict, cat: dict, governance: dict[str, dict]) -> str | None:
    """The plain note for a viewer who is not shown everything (N-B): how many rows wait on the personal-data decision. Rows hidden for any
    other reason (pay, restricted measures) are not counted and not mentioned. None when there are none."""
    why = _undecided_rows(cat, governance)
    n = sum(1 for tab in TABS for r in shown[tab] if r.get(HIDDEN) and (tab, row_id(tab, r)) in why)
    return None if not n else f"{n} {'row is' if n == 1 else 'rows are'} hidden until the organiser decides on personal data"


def apply_governance(shown: dict, row_guards: dict[tuple[str, str], list[frozenset[str]]], viewer: Viewer, drop: bool = False) -> dict:
    """The rows the viewer may see in full; the others become {id, hidden} (or are left out, for the Excel file)."""
    out = empty_catalogue()
    for tab in TABS:
        for row in shown[tab]:
            if all(allows(g, viewer) for g in row_guards.get((tab, row_id(tab, row)), [])):
                out[tab].append(row)
            elif not drop:
                out[tab].append({id_header(tab): row[id_header(tab)], HIDDEN: True})
    return out


# ---- building from the KPIs and the owners' answers (M2-16) ------------------------------------------------------------------

def _set(row: dict, header: str, cell: dict, force: bool = False) -> None:
    """A person's edit or settlement is never overwritten by a rebuild; a build never replaces what is known with an unknown."""
    old = row.get(header)
    if not force and old is not None and (is_manual(old) or (cell.get("mark") == "unknown" and not is_blank(old) and old.get("mark") != "unknown")):
        return
    row[header] = cell


def _p(x: Any, by: str, source: str) -> dict:
    """An answer field is a provenance value; tolerate a bare value."""
    if isinstance(x, dict) and "mark" in x:
        return x
    return prov(x, "stated", by, source) if x not in (None, "") else unknown(by, source)


def _copy(c: dict, source: str, value: Any = None) -> dict:
    return prov(c.get("value") if value is None else value, c["mark"], c.get("by") or "Lens", c.get("from") or source, c.get("at")) \
        if c.get("mark") != "unknown" else unknown(c.get("by") or "Lens", c.get("from") or source)


def _fill_kpis(cat: dict, kpis: list[dict], problem_names: dict[str, str]) -> None:
    tmap = contract()["mapping"]["tracking"]
    for k in kpis:
        kid = str(k["id"])
        row = find(cat, "kpis", kid)
        if row is None:
            row = new_row("kpis", kid)
            cat["kpis"].append(row)
        src = "kpis.json"
        _set(row, "KPI name", prov(k.get("name"), "stated", "the charter", src) if k.get("name") else unknown("the charter", src))
        _set(row, "Definition", _copy(_p(k.get("definition"), "Lens", src), src))
        _set(row, "Priority", prov(k["priority"], "stated", "the charter", src) if k.get("priority") else unknown("the charter", src))
        names = [problem_names.get(p, p) for p in k.get("problem_ids") or []]  # one KPI serving two problems stays one row
        _set(row, "Problem it serves", prov(names, "stated", "the charter", src) if names else unknown("the charter", src))
        owners = k.get("owners") or {}
        for header, key in (("Business owner", "business"), ("Data owner", "data"), ("Process owner", "process")):
            _set(row, header, _copy(_p(owners.get(key), "Lens", src), src))
        tr = _p(k.get("tracking"), "Lens", src)
        _set(row, "Tracking status", unknown(tr.get("by") or "Lens", src) if tr.get("mark") == "unknown" or tr.get("value") not in tmap
             else _copy(tr, src, tmap[tr["value"]]))


def match_name(text: Any) -> str:
    """A system's name as two owners may spell it alike: no "(suffix)", no file extension, _ - . as spaces, lower case."""
    s = re.sub(r"\([^)]*\)", " ", str(text).lower())
    s = re.sub(r"\.(xlsx?|xlsm|csv|pdf|docx?|txt|json|xml|zip)\b", "", s)
    return " ".join(re.sub(r"[_.\-]", " ", s).split())


def _same_system(a: str, b: str) -> bool:
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def _systems(answers: list[dict]) -> dict[str, list[dict]]:
    """Every system or file the owners listed, merged across owners and KPIs (shortest match name -> items): the same match name,
    or one a word-prefix of the other, when the kinds agree (a kind nobody gave agrees with any). Different kinds never merge.
    An item is {row, answer, who}: one owner's row for it under one KPI."""
    clusters: list[dict] = []  # {key, kind, items}
    for a in answers:
        for r in source_rows(a):
            name = text_of(r["name"]).strip()
            if not name:
                continue
            key, kind = match_name(name), norm(text_of(r.get("kind")))
            hit = next((c for c in clusters if _same_system(key, c["key"]) and (not kind or not c["kind"] or kind == c["kind"])), None)
            if hit is None:
                hit = {"key": key, "kind": kind, "items": []}
                clusters.append(hit)
            hit["key"], hit["kind"] = min(hit["key"], key, key=len), hit["kind"] or kind
            hit["items"].append({"row": r, "answer": a, "who": str(a.get("owner_name") or "")})
    out: dict[str, list[dict]] = {}
    for c in clusters:  # two kinds under one name are two systems: the second is keyed "name [kind]"
        out[c["key"] if c["key"] not in out else f"{c['key']} [{c['kind']}]"] = c["items"]
    return out


def _mapped_value(row_key: str, raw: Any, header: str) -> str:
    maps = contract()["mapping"]
    if row_key in ("structure", "kind", "connection", "personal"):
        table = maps["structure"] if row_key == "structure" else maps["personal"] if row_key == "personal" else maps[row_key]
        hit = next((v for k, v in table.items() if norm(k) == norm(raw).replace(" ", "_") or norm(k) == norm(raw)), None)
        if hit:
            return hit
    hit = next((o for o in options("sources", header) if norm(o) == norm(raw).replace("_", " ")), None)
    if hit or row_key != "connection":
        return hit or str(raw)
    return _owner_words("connection", str(raw))  # not a dropdown word: the owner's own words stay, never a default


_questionnaire = lru_cache(maxsize=1)(load_questionnaire)


def _owner_words(row_key: str, value: str) -> str:
    """The label the form showed for a choice ("download" was "I download it"); the value itself when there is none."""
    spec = next((c for c in _questionnaire().fields["sources"]["row"] if c["key"] == row_key), {})
    return next((c["label"] for c in spec.get("choices") or [] if c["value"] == value), value)


def _per_person(items: list[dict], row_key: str, header: str) -> list[dict]:
    """The latest known answer of each person for one cell: {person, value, cell, answer}."""
    latest: dict[str, dict] = {}
    for it in items:
        c = it["row"].get(row_key)
        if not isinstance(c, dict) or c.get("mark") == "unknown" or is_blank(c):
            continue
        item = {"person": it["who"], "value": _mapped_value(row_key, c["value"], header),
                "cell": c, "answer": it["answer"]}
        if it["who"] not in latest or str(c.get("at", "")) >= str(latest[it["who"]]["cell"].get("at", "")):
            latest[it["who"]] = item
    return list(latest.values())


def conflict_id(tab: str, key: str, header: str) -> str:
    return "c-" + hashlib.sha1(f"{tab}|{key}|{header}".encode()).hexdigest()[:10]


def _merge_conflict(prior: dict | None, tab: str, key: str, rid: str, header: str, versions: list[dict], now: str) -> dict:
    sig = sorted({norm(v["value"]) for v in versions})
    rec = {"id": conflict_id(tab, key, header), "tab": tab, "row_id": rid, "column": header, "versions": versions, "signature": sig,
           "state": "open", "settled_by": None, "settled_value": None, "settled_at": None, "note": None, "history": []}
    if prior:
        rec["history"] = list(prior.get("history", []))
        for f in ("state", "settled_by", "settled_value", "settled_at", "note"):
            rec[f] = prior.get(f)
        if prior.get("state") == "settled" and prior.get("signature") != sig:  # someone answered again: it is open again, the history stays
            rec["history"].append({"event": "reopened", "at": now, "was": prior.get("settled_value"), "by": prior.get("settled_by")})
            rec.update(state="open", settled_by=None, settled_value=None, settled_at=None, note=None)
    return rec


def _fill_sources(cat: dict, kpis: list[dict], answers: list[dict], prior: list[dict], now: str) -> list[dict]:
    gov_words = contract()["from_words"]
    by_kpi = {str(k["id"]): k for k in kpis}
    prior_by_id = {c["id"]: c for c in prior}
    conflicts: dict[str, dict] = {}
    used: set[str] = set()
    for key, group in _systems(answers).items():
        name_key = key.split(" [")[0]
        row = next((r for r in cat["sources"] if row_id("sources", r) not in used and _same_system(match_name(text_of(r.get("Source name"))), name_key)), None)
        if row is None:
            row = new_row("sources", next_id("sources", cat["sources"]))
            cat["sources"].append(row)
        sid = row_id("sources", row)
        used.add(sid)
        full = group  # tables and fields stay guarded by their own KPIs; every cell and conflict below comes from open KPIs only
        group = [i for i in full if str(i["answer"].get("kpi_id")) not in by_kpi
                 or not _restricted_kpi(by_kpi[str(i["answer"].get("kpi_id"))].get("governance"))] or full
        _set(row, "Source name", _copy(max(group, key=lambda i: len(" ".join(text_of(i["row"]["name"]).split())))["row"]["name"], "answers.json"))  # the longest spelling
        for spec in contract()["conflict_cells"]:  # a disagreement is found by system: two owners, one system, two answers
            header, versions = spec["column"], _per_person(group, spec["row_key"], spec["column"])
            stated = [v for v in versions if v["cell"]["mark"] == "stated"]
            distinct = {norm(v["value"]) for v in stated}
            cid = conflict_id("sources", key, header)
            if len(distinct) > 1:
                rec = _merge_conflict(prior_by_id.get(cid), "sources", key, sid, header, [
                    {"value": v["value"], "by": v["person"], "at": v["cell"].get("at"), "from": v["cell"].get("from"),
                     "kpi_id": v["answer"].get("kpi_id")} for v in stated], now)
                conflicts[cid] = rec
                if rec["state"] == "settled":
                    _set(row, header, prov(rec["settled_value"], "stated", rec["settled_by"], gov_words["settled"], rec["settled_at"]), force=True)
                else:  # Lens never picks: the cell stays unknown while two owners disagree
                    _set(row, header, unknown("Lens", gov_words["conflict"]), force=True)
                continue
            if cid in prior_by_id and prior_by_id[cid]["state"] == "open":  # the owners now agree
                conflicts[cid] = {**prior_by_id[cid], "state": "closed", "history": prior_by_id[cid]["history"] + [{"event": "answers now agree", "at": now}]}
            elif cid in prior_by_id:
                conflicts[cid] = prior_by_id[cid]
            best = stated or versions
            if best:
                v = max(best, key=lambda x: str(x["cell"].get("at", "")))
                _set(row, header, _copy(v["cell"], "answers.json", v["value"]))
        for header, row_key in (("Source type", "kind"), ("Where it lands or lives", "lands"), ("Data owner", "owner")):  # the connection method itself is a conflict cell (contract)
            versions = _per_person(group, row_key, header)
            if versions:  # no conflict is raised for these: a stated answer beats a guess, the latest beats an older one
                v = max(versions, key=lambda x: (x["cell"]["mark"] == "stated", str(x["cell"].get("at", ""))))
                _set(row, header, _copy(v["cell"], "answers.json", v["value"]))
        detail = row.get("Connection details (no passwords)")  # the questionnaire has no connection detail: an old copy of "lands" is cleared (N7)
        lands = {norm(text_of(row.get("Where it lands or lives")))} | {norm(v["value"]) for v in _per_person(group, "lands", "")}
        if detail and not is_manual(detail) and norm(text_of(detail)) in lands - {""}:
            row["Connection details (no passwords)"] = unknown(DERIVED_BY, "not answered yet")
        _fill_source_governance(row, group, [by_kpi[k] for k in dict.fromkeys(str(i["answer"].get("kpi_id")) for i in group) if k in by_kpi], full)
        _personal_conflict(row, group, key, prior_by_id.get(conflict_id("sources", key, "Contains personal data?")), conflicts, now)
        _fill_items(cat, row, full, by_kpi)
    for cid, rec in prior_by_id.items():
        conflicts.setdefault(cid, rec)  # a settled conflict is history; it is never dropped
    return list(conflicts.values())


def _fill_source_governance(row: dict, group: list[dict], used: list[dict], everyone: list[dict] | None = None) -> None:
    """The source's personal-data cell. `everyone` is every owner's row for the system, restricted measures included: a "Not sure" given
    under a restricted measure still counts (r4-2). Where the owners differ the safer answer wins (yes, then not sure, then no)."""
    mp = contract()["mapping"]["personal"]
    gov = []
    for g in (k.get("governance") or {} for k in used):  # the organiser's answer only when the organiser gave one (r4-3)
        p = "not_sure" if g.get("sensitive") and g.get("personal") in (None, "no") else g.get("personal")  # sensitive counts as personal
        if p:
            gov.append({**g, "personal": p})
    src = "kpis.json (set by the organiser)"
    said = [(it["who"], it["row"].get("personal")) for it in everyone or group]
    said = [(who, c) for who, c in said if isinstance(c, dict) and c.get("mark") != "unknown" and not is_blank(c)]
    order = ["yes", "not_sure", "no"]
    rank = lambda p: order.index(p) if p in order else 1  # noqa: E731
    if gov or said:
        theirs = [(norm(c["value"]).replace(" ", "_"), who, c) for who, c in said]
        worst = min([g["personal"] for g in gov] + [v for v, _, _ in theirs], key=rank)
        if worst in [g["personal"] for g in gov]:
            by, cite = "the organiser", src
        else:
            _, by, c = next(x for x in theirs if x[0] == worst)
            cite = c.get("from") or "answers.json"
            if by not in {it["who"] for it in group}:  # the answer came from under a restricted measure: it counts, its owner is not named
                by, cite = DERIVED_BY, DERIVED_FROM
        _set(row, "Contains personal data?", prov(mp.get(worst, "Not sure"), "stated", by, cite))
        lists = [g.get("may_see") or [] for g in gov if _restricted_kpi(g)] or [g.get("may_see") or [] for g in gov]
        names = [n for n in dict.fromkeys(lists[0] if lists else []) if all(norm(n) in {norm(x) for x in o} for o in lists[1:])]  # narrowest wins
        if names:
            _set(row, "Who may see it", prov(", ".join(names), "stated", "the organiser", src))
    if is_blank(row.get("Data owner")):
        owner = next((k["owners"]["data"] for k in used if isinstance((k.get("owners") or {}).get("data"), dict)
                      and k["owners"]["data"].get("mark") != "unknown"), None)
        if owner:
            _set(row, "Data owner", _copy(owner, "kpis.json"))
    # "Availability" is left unknown: "could we track it?" is about the measure, not this system, so nobody said it (r4-3)


def _personal_conflict(row: dict, everyone: list[dict], key: str, prior: dict | None, conflicts: dict, now: str) -> None:
    """Two named owners gave different personal-data answers for one system: the safer one stays in the cell and the difference is a
    conflict between them. A settlement wins over the draft, and so does a person's own edit (`_set`)."""
    header = "Contains personal data?"
    stated = [v for v in _per_person(everyone, "personal", header) if v["cell"]["mark"] == "stated"]
    cid = conflict_id("sources", key, header)
    if len({norm(v["value"]) for v in stated}) > 1:
        rec = _merge_conflict(prior, "sources", key, row_id("sources", row), header, [
            {"value": v["value"], "by": v["person"], "at": v["cell"].get("at"), "from": v["cell"].get("from"), "kpi_id": v["answer"].get("kpi_id")}
            for v in stated], now)
        conflicts[cid] = rec
        if rec["state"] == "settled":
            _set(row, header, prov(rec["settled_value"], "stated", rec["settled_by"], contract()["from_words"]["settled"], rec["settled_at"]))
    elif prior:
        conflicts[cid] = {**prior, "state": "closed", "history": [*prior["history"], {"event": "answers now agree", "at": now}]} if prior["state"] == "open" else prior


def _split_field(item: str, tables: list[str]) -> tuple[str, str]:
    """A key field or a thing to read out may be written "table: item"; the table is then that one, else the row's first table."""
    head, sep, tail = item.partition(":")
    if sep and norm(head) in {norm(t) for t in tables} and tail.strip():
        return norm(head), tail.strip()
    return (norm(tables[0]) if tables else ""), item.strip()


def _upsert(cat: dict, tab: str, match: dict, cells: dict) -> dict:
    """The row of this tab whose `match` cells all agree (compared as normalised text), made if there is none; then `cells` are set."""
    row = next((r for r in cat[tab] if all(norm(text_of(r.get(h))) == norm(v) for h, v in match.items())), None)
    if row is None:
        row = new_row(tab, next_id(tab, cat[tab]))
        cat[tab].append(row)
    for header, cell in cells.items():
        _set(row, header, cell)
    return row


def _made(text: Any) -> dict:
    return prov(text, "stated", DERIVED_BY, "worked out from the systems listed")


def _fill_items(cat: dict, source_row: dict, group: list[dict], by_kpi: dict[str, dict]) -> None:
    """Tables from the tables, files and document types listed for one system; Fields from the key fields; Extractions from the
    things to read out of an unstructured system's document types. Each is tied to the KPIs the rows were answered under."""
    sid, kind = row_id("sources", source_row), norm(text_of(source_row.get("Source type")))
    unstructured = text_of(source_row.get("Structured or unstructured")) == "Unstructured"
    kinds = contract()["mapping"]["table_kind"]
    table_kind = kinds["email"] if unstructured and "email" in kind else kinds["document"] if unstructured else \
        kinds["file"] if any(w in kind for w in ("file", "excel", "workbook")) else kinds["table"]
    tables: dict[str, dict] = {}  # normalised table name -> {name, kpis, cell}
    listed: list[tuple[str, str, str, dict, list[str]]] = []  # (fields or read_out, KPI, text, the cell it came from, the row's tables)
    for it in group:
        kid = str(it["answer"].get("kpi_id"))
        if kid not in by_kpi:
            continue
        names = [str(n) for n in value_of(it["row"].get("tables")) or []]
        for n in names:
            t = tables.setdefault(norm(n), {"name": n, "kpis": [], "cell": it["row"]["tables"]})
            if kid not in t["kpis"]:
                t["kpis"].append(kid)
        for key in ("fields", "read_out"):
            listed += [(key, kid, str(n), it["row"][key], names) for n in value_of(it["row"].get(key)) or []]
    ids: dict[str, str] = {}
    for nt, t in tables.items():
        c = t["cell"]
        row = _upsert(cat, "tables", {"Source ID": sid, "Name of table, file or document type": nt}, {
            "Source ID": _made(sid), "Kind": _made(table_kind), "Name of table, file or document type": _copy(c, "answers.json", t["name"]),
            "Related KPIs": prov(", ".join(sorted(t["kpis"])), "stated", c.get("by") or DERIVED_BY, c.get("from") or "answers.json")})
        for header in ("How often it arrives", "Expected arrival time or SLA", "Availability"):
            if not is_blank(source_row.get(header)):
                _set(row, header, dict(source_row[header]))
        ids[nt] = row_id("tables", row)
    for key, kid, text, c, names in listed:
        head, name = _split_field(text, names)
        tid = ids.get(head)
        if not tid or (key == "read_out" and not unstructured):
            continue
        tab, item, what = ("fields", "Item ID", "Field name as in the source") if key == "fields" else ("extractions", "Item ID (document type)", "What to extract")
        _merge_item(cat, tab, item, what, tid, kid, c, _copy(c, "answers.json", name), by_kpi)
    # a document type with nothing to read out gets no extraction row: a blank "What to extract" says nothing (r4 N-C)


def _merge_item(cat: dict, tab: str, item: str, what: str, tid: str, kid: str, src: dict, name: dict | None, by_kpi: dict[str, dict]) -> None:
    """One row per (table, field or thing to read out), however many KPIs and owners named it (N-C): the KPIs it serves are listed in
    "Feeds KPI". A person's edit to a cell is never overwritten; a blank "Business meaning" takes the KPI's definition, else "Not available yet"."""
    key = norm(text_of(name)) if name else ""
    row = next((r for r in cat[tab] if norm(text_of(r.get(item))) == norm(tid) and norm(text_of(r.get(what))) == key), None)
    if row is None:
        row = new_row(tab, next_id(tab, cat[tab]))
        cat[tab].append(row)
    _set(row, item, _made(tid))
    if name:
        _set(row, what, name)
    kids = sorted({*split_ids(text_of(row.get("Feeds KPI"))), kid})
    _set(row, "Feeds KPI", prov(", ".join(kids), "stated", src.get("by") or DERIVED_BY, src.get("from") or "answers.json"))
    meaning = row.get("Business meaning")
    if tab == "fields" and (is_blank(meaning) or (isinstance(meaning, dict) and meaning.get("from") == "kpis.json")):
        # a field's meaning is its own description (the technical notes, or its owner), never the measure's definition: an earlier build copied
        # the definition here, so that copy is cleared too
        _set(row, "Business meaning", unknown(DERIVED_BY, NOT_YET), force=True)


LENS = "Lens"


def propose_rows(cat: dict, proposals: dict, kpi_id: str, title: str, restricted: bool, may_see: list[str] | None = None) -> dict[str, list[str]]:
    """Lens's catalogue rows from the technical notes (M2-E1), through the catalogue's own cells: every cell guessed, by Lens, from the document's
    title, for a person to accept or edit in the catalogue. {"sources": [...], "tables": [...], "fields": [...]} the ids of the rows made or
    found (a row of the same name is never made twice, and a person's cell is never changed). A measure that is restricted gives restricted
    rows: the source is personal data, the field is classed personal data, and both link to the measure so its list guards them."""
    guess = lambda v: prov(v, "guessed", LENS, title)  # noqa: E731
    ids: dict[str, list[str]] = {"sources": [], "tables": [], "fields": []}
    listed = ", ".join(may_see or []) if restricted else ""  # a restricted measure's rows are seen by the people on its list, as that list says (guessed, like the rest)

    def found(tab: str, head: str, name: str, **match) -> dict | None:
        return next((r for r in cat[tab] if norm(text_of(r.get(head))) == norm(name) and all(norm(text_of(r.get(h))) == norm(v) for h, v in match.items())), None)

    def made(tab: str, cells: dict) -> dict:
        row = new_row(tab, next_id(tab, cat[tab]))
        cat[tab].append(row)
        row.update({h: guess(v) for h, v in cells.items() if v})
        return row

    def tie(row: dict, header: str) -> None:  # the measure it serves, unless a person already wrote that cell
        if not is_manual(row.get(header)):
            kids = sorted({*split_ids(text_of(row.get(header))), kpi_id})
            row[header] = guess(", ".join(kids))

    def source(name: str, kind: str = "") -> str:
        row = found("sources", "Source name", name)
        if row is None:
            kind = _canonical("sources", "Source type", kind) if kind else ""
            row = made("sources", {"Source name": name, "Source type": kind if kind in options("sources", "Source type") else "",
                                   "Contains personal data?": "Yes" if restricted else "Not sure", "Who may see it": listed})
        return _add(ids["sources"], row_id("sources", row))

    def table(src: str, name: str) -> str:
        sid = source(src)
        row = found("tables", "Name of table, file or document type", name, **{"Source ID": sid}) or made(
            "tables", {"Source ID": sid, "Name of table, file or document type": name})
        tie(row, "Related KPIs")
        return _add(ids["tables"], row_id("tables", row))

    for name, kind in proposals.get("sources", []):
        source(name, kind)
    for src, name in proposals.get("tables", []):
        table(src, name)
    for tbl, name, meaning in proposals.get("fields", []):
        tid = next((row_id("tables", t) for t in cat["tables"] if norm(text_of(t.get("Name of table, file or document type"))) == norm(tbl)), None)
        if tid is None:
            continue  # a column whose table is not in the catalogue or the notes' own proposals has nowhere to sit
        row = found("fields", "Field name as in the source", name, **{"Item ID": tid}) or made(
            "fields", {"Item ID": tid, "Field name as in the source": name, "Business meaning": meaning, "Personal data class": "Personal data" if restricted else "", FIELD_VISIBILITY: listed})
        if is_blank(row.get("Business meaning")):
            row["Business meaning"] = guess(meaning) if meaning else unknown(DERIVED_BY, NOT_YET)
        tie(row, "Feeds KPI")
        _add(ids["fields"], row_id("fields", row))
        _add(ids["tables"], tid)
        _add(ids["sources"], text_of(next(t for t in cat["tables"] if row_id("tables", t) == tid).get("Source ID")))
    return ids


def _add(lst: list[str], rid: str) -> str:
    if rid and rid not in lst:
        lst.append(rid)
    return rid


def _dedupe(cat: dict) -> None:
    """Rows an earlier build left twice (one per KPI) become one with every KPI listed; rows with no table and nothing to read out go (N-C)."""
    for tab, item, what in (("fields", "Item ID", "Field name as in the source"), ("extractions", "Item ID (document type)", "What to extract")):
        kept: dict[tuple[str, str], dict] = {}
        rows = []
        for r in cat[tab]:
            key = (norm(text_of(r.get(item))), norm(text_of(r.get(what))))
            if (key == ("", "") or (tab == "extractions" and not key[1])) and not any(is_manual(c) for c in r.values()):
                continue
            first = kept.setdefault(key, r)
            if first is not r and any(is_manual(c) and is_manual(first.get(h)) and norm(text_of(c)) != norm(text_of(first.get(h))) for h, c in r.items()):
                rows.append(r)  # two people wrote different things in one column: neither is dropped, both rows stay
                continue
            if first is not r:
                for h, c in r.items():  # the copy's person-made cells are not lost
                    if is_manual(c) and not is_manual(first.get(h)):
                        first[h] = c
                ids = sorted({*split_ids(text_of(first.get("Feeds KPI"))), *split_ids(text_of(r.get("Feeds KPI")))})
                if ids and not is_manual(first.get("Feeds KPI")):
                    first["Feeds KPI"] = prov(", ".join(ids), "stated", DERIVED_BY, "answers.json")
                continue
            rows.append(r)
        cat[tab][:] = rows


def build(existing: dict | None, kpis: list[dict], answers: list[dict], prior_conflicts: list[dict] | None = None,
          problem_names: dict[str, str] | None = None, now: str | None = None) -> tuple[dict, list[dict]]:
    """The catalogue and its conflict reports, from the KPIs and answers. Rows a person edited are kept as they are."""
    cat = {t: deepcopy((existing or {}).get(t, [])) for t in TABS}
    stamp = now or datetime.now(timezone.utc).isoformat()
    _dedupe(cat)
    _fill_kpis(cat, kpis, problem_names or {})
    return cat, _fill_sources(cat, kpis, answers, prior_conflicts or [], stamp)


# ---- editing: adding rows and changing cells, every change attributed (M2-17) ----------------------------------------------------

def _check_text(header: str, value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise CatalogueError("invalid", f"“{header}” needs a short piece of text.")
    return "".join(ch for ch in value if unicodedata.category(ch) != "Cc" or ch in "\n\t").strip()  # no NUL: a NUL-prefixed role is the guard's role marker


def _check_link(cat: dict, tab: str, header: str, value: str | None) -> None:
    if value is None:
        return
    known = lambda t: {row_id(t, r) for r in cat[t]}  # noqa: E731
    if (tab, header) == ("tables", "Source ID") and value not in known("sources"):
        raise CatalogueError("invalid", "That source is not in the catalogue yet. Add the source first.")
    if header in ("Item ID", "Item ID (document type)") and value not in known("tables"):
        raise CatalogueError("invalid", "That table or document type is not in the catalogue yet. Add it first.")
    if (tab, header) == ("tables", "Related KPIs") and value.lower() != "unknown":
        bad = [k for k in split_ids(value) if k not in known("kpis")]
        if bad:
            raise CatalogueError("invalid", f"{', '.join(bad)} is not one of this baseline's KPIs.")
    if header == "Feeds KPI":
        bad = [k for k in split_ids(value) if k not in known("kpis")]
        if bad:
            raise CatalogueError("invalid", f"{', '.join(bad)} is not one of this baseline's KPIs.")


def _canonical(tab: str, header: str, value: str) -> str:
    return next((o for o in options(tab, header) if norm(o) == norm(value)), value)


def _open_conflict(conflicts: list[dict], tab: str, rid: str, header: str) -> bool:
    return any(c["state"] == "open" and c["tab"] == tab and c["row_id"] == rid and c["column"] == header for c in conflicts)


def edit_cells(cat: dict, conflicts: list[dict], tab: str, rid: str, changes: dict, by: str, mark: str = "stated", at: str | None = None) -> dict:
    """Set cells on one row. A cleared cell becomes "unknown, said by this person". Returns the changed row."""
    if tab not in TABS or not isinstance(changes, dict) or not changes:
        raise CatalogueError("invalid", "Those details could not be read. Please try again.")
    if norm(by) in NOT_A_PERSON or mark not in ("stated", "guessed"):
        raise CatalogueError("invalid", "A change needs the name of the person making it.")
    row = find(cat, tab, rid)
    if row is None:
        raise CatalogueError("not_found", "We could not find that row.")
    allowed = set(input_headers(tab)) - {id_header(tab)}
    words = contract()["from_words"]
    staged = {}
    for header, raw in changes.items():
        if header not in allowed:
            raise CatalogueError("invalid", f"“{header}” cannot be changed here.")
        personal = (tab, header) == ("sources", "Contains personal data?")  # a person's own answer on this one settles the owners' difference (r4-2)
        if _open_conflict(conflicts, tab, rid, header) and not personal:
            raise CatalogueError("conflict", "Two owners answered this differently. A named person settles it from the conflict report.")
        value = _check_text(header, raw)
        value = _canonical(tab, header, value) if value else None
        _check_link(cat, tab, header, value)
        staged[header] = unknown(by, words["edited"]) if value is None or value.lower() == "unknown" and (tab, header) == ("tables", "Related KPIs") \
            else prov(value, mark, by, words["edited"], at)
    row.update(staged)
    for rec in conflicts:
        cell = staged.get(rec["column"])
        if rec["state"] == "open" and (rec["tab"], rec["row_id"]) == (tab, rid) and cell and cell["mark"] == "stated" and (tab, rec["column"]) == ("sources", "Contains personal data?"):
            settle(cat, conflicts, rec["id"], cell["value"], by)
    return row


def add_row(cat: dict, conflicts: list[dict], tab: str, cells: dict, by: str, mark: str = "stated") -> dict:
    if tab == "kpis":
        raise CatalogueError("invalid", "KPIs come from the charter. Add one there.")
    if tab not in TABS:
        raise CatalogueError("not_found", "We could not find that tab.")
    parent = {"tables": "Source ID", "fields": "Item ID", "extractions": "Item ID (document type)"}.get(tab)
    if parent and not (cells or {}).get(parent):
        raise CatalogueError("invalid", "Say which source this comes from." if tab == "tables" else "Say which table or document type this comes from.")
    row = new_row(tab, next_id(tab, cat[tab]))
    cat[tab].append(row)
    try:
        if cells:
            edit_cells(cat, conflicts, tab, row_id(tab, row), cells, by, mark)
    except CatalogueError:
        cat[tab].remove(row)
        raise
    return row


# ---- conflicts (M2-24) -----------------------------------------------------------------------------------------------------------

def settle(cat: dict, conflicts: list[dict], conflict: str, value: Any, by: str, note: str = "", now: str | None = None) -> dict:
    """A named person settles a conflict: Lens never does. Both versions stay in the record; the cell takes the person's answer."""
    if norm(by) in NOT_A_PERSON:
        raise CatalogueError("invalid", "A conflict is settled by a named person.")
    rec = next((c for c in conflicts if c["id"] == conflict), None)
    if rec is None:
        raise CatalogueError("not_found", "We could not find that conflict.")
    if rec["state"] != "open":
        raise CatalogueError("conflict", "That conflict is already settled.")
    chosen = _check_text("answer", value)
    if chosen is None:
        raise CatalogueError("invalid", "Choose one of the answers, or write the settled one.")
    stamp = now or datetime.now(timezone.utc).isoformat()
    rec.update(state="settled", settled_by=by, settled_value=chosen, settled_at=stamp, note=(_check_text("note", note) or None))
    rec["history"].append({"event": "settled", "by": by, "at": stamp, "value": chosen, "note": rec["note"]})
    row = find(cat, rec["tab"], rec["row_id"])
    if row is not None:
        row[rec["column"]] = prov(chosen, "stated", by, contract()["from_words"]["settled"], stamp)
    return rec


# ---- matching columns to KPIs (names and types only) ---------------------------------------------------------------------------------

_LEVELS = ("low", "medium", "high")
_TYPE_GROUP = {"string": "string", "text": "string", "varchar": "string", "int": "decimal", "integer": "decimal", "bigint": "decimal",
               "decimal": "decimal", "double": "decimal", "float": "decimal", "number": "decimal", "date": "date", "timestamp": "date",
               "datetime": "date", "bool": "boolean", "boolean": "boolean"}


def _type_agrees(column_type: str, field_type: str) -> bool:
    return _TYPE_GROUP.get(norm(column_type), "string") == _TYPE_GROUP.get(norm(field_type), "string")


_GENERIC = frozenset("id no date name code type value amount number key ref flag text".split())  # words too common to say what a column is for


def _tokens(text: str) -> set[str]:
    """period_return, periodReturn and "Period return" all give {period, return}; a plural is its singular; words the contract
    lists as one thing (pay, salary, bonus) share one token."""
    words = re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text)).lower())
    groups = contract().get("column_words") or []
    one = lambda w: next((g[0] for g in groups if w in g), w)  # noqa: E731
    return {one(w[:-1] if len(w) > 3 and w.endswith("s") else w) for w in words if w not in _GENERIC}


def _name_score(column: str, field_id: str, synonym_entry: dict | None) -> tuple[int, str]:
    """0 no match, 1 low (one word of the column is a spelling the pack knows), 2 medium (the field's own id), 3 high (the pack's own
    spelling pattern). Copied from column_matcher._name_score, with the pack's listed spellings and word-level matching added."""
    name = column.strip()
    regex = (synonym_entry or {}).get("regex")
    if regex:
        try:
            if re.fullmatch(regex, name, re.IGNORECASE):
                return 3, f"“{column}” is a spelling the industry pack knows for “{field_id}”"
        except re.error:
            pass
    if name.lower() == field_id.strip().lower():
        return 2, f"“{column}” has the same name as “{field_id}”"
    spellings = [str(s.get("spelling") or "") for s in (synonym_entry or {}).get("spellings") or [] if isinstance(s, dict)]
    if name.lower() in (s.lower() for s in spellings):
        return 3, f"“{column}” is a spelling the industry pack knows for “{field_id}”"
    single = set().union(*(_tokens(s) for s in spellings if re.fullmatch(r"[A-Za-z0-9]+", s)))  # one-word spellings only ("nav", not "value_native")
    if (hit := _tokens(name) & single):
        return 1, f"“{column}” contains “{sorted(hit)[0]}”, a spelling the industry pack knows for “{field_id}”"
    return 0, ""


def _by_kpi_name(columns_seen: list[dict], kpi_names: dict[str, str]) -> list[dict]:
    """A column that shares a word with a KPI's name (period_return with "Excess return versus benchmark"): a low suggestion."""
    out = []
    for col in columns_seen or []:
        mine = _tokens(str(col.get("name") or ""))
        for kid, kname in kpi_names.items():
            if (hit := mine & _tokens(kname)):
                out.append({"column": col.get("name"), "field": None, "feed": None, "kpi_ids": [kid], "confidence": "low", "personal": False,
                            "reasons": [f"“{col.get('name')}” shares the word “{sorted(hit)[0]}” with the measure “{kname}”"]})
    return out


def match_columns(columns_seen: list[dict], feeds: dict, synonyms: dict, kpi_ids: set[str], kpi_names: dict[str, str] | None = None) -> list[dict]:
    """Suggest which KPIs a table's columns feed. `columns_seen` is [{name, type}] only; nothing here looks at a value.
    A field that is a business rule (customer_decides) is never above medium: it is a question, not a match.
    `kpi_names` ({id: name}, only the KPIs the asker may see) adds low suggestions from words shared with a measure's name."""
    out: list[dict] = []
    for feed_name, feed in (feeds or {}).items():
        for field in (feed or {}).get("fields") or []:
            fid, ftype = field["id"], str(field.get("type") or "string")
            kpis = [k for k in field.get("required_for") or [] if k in kpi_ids]
            for col in columns_seen or []:
                level, reason = _name_score(str(col.get("name") or ""), fid, ((synonyms or {}).get(feed_name) or {}).get(fid))
                if level == 0 or not kpis:
                    continue
                reasons = [reason]
                agrees = _type_agrees(str(col.get("type") or "string"), ftype)
                reasons.append("its type fits" if agrees else "its type does not fit")
                level = level if agrees else max(level - 1, 1)
                if field.get("customer_decides") and level == 3:
                    level = 2
                    reasons.append("the meaning is a business rule, so someone must confirm it")
                out.append({"column": col.get("name"), "field": fid, "feed": feed_name, "kpi_ids": kpis, "confidence": _LEVELS[level - 1],
                            "reasons": reasons, "personal": bool(field.get("pii"))})
    named = {(s["column"], k) for s in out for k in s["kpi_ids"]}
    for s in _by_kpi_name(columns_seen, {k: n for k, n in (kpi_names or {}).items() if k in kpi_ids}):
        if (s["column"], s["kpi_ids"][0]) not in named:  # a field match already says it
            out.append(s)
    return out
