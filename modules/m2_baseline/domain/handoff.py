"""The hand-off to module 3 (M2-28, D-026): the baseline outcome record, built from a signed version and checked against
contracts/baseline_outcome.yaml. Pure Python; the file is written by store/signoff.py. Module 3 reads only this.

Shape follows module 1's domain/handoff.py (build_outcome from a contract). The gap rows follow the earlier product's
emitters/gap_report.py (type, label, severity, why, action), real kinds only.
"""
from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import gate as GT
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain.readiness import ContractError, load_contract

MODULE_ID = "m2_baseline"
_TABS = ("sources", "tables", "fields", "extractions", "kpis")


def load_outcome_contract(folder=None) -> dict:
    d = load_contract("baseline_outcome.yaml", folder)
    if any(k not in d for k in ("kind", "required", "signature_fields", "confirmation_fields", "gap_fields", "gap_types")):
        raise ContractError("baseline_outcome.yaml is not valid.")
    return d


def _is_prov(cell) -> bool:
    return isinstance(cell, dict) and "mark" in cell


def _val(cell):
    return cell.get("value") if _is_prov(cell) else cell


def _pick(row: dict, fields) -> dict:
    return {f: row[f] for f in fields}


def _empty(cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip()) or (_is_prov(cell) and cell.get("value") in (None, "") and cell.get("mark") != "unknown")


def _own(catalogue: dict) -> dict:
    """The catalogue as people filled it: the columns worked out from other cells (counts, Complete?, Ready?, how sure,
    confirmed by, date confirmed) are derived, never gaps for a person to fill and never part of what was signed."""
    return {t: [{h: c for h, c in r.items() if h in C.input_headers(t) or h == C.FIELD_VISIBILITY} if isinstance(r, dict) else r for r in catalogue.get(t) or []]
            for t in _TABS}


def _row_name(tab: str, i: int, row: dict) -> str:
    rid = _val(row.get(C.id_header(tab)))
    return f"{tab} {rid}" if rid else f"{tab} row {i + 1}"


_NAME_HEADS = {"sources": "Source name", "tables": "Name of table, file or document type", "fields": "Field name as in the source", "extractions": "What to extract"}
WITHHELD = "Withheld: it names something you may not see."


def _hidden_terms(cat: dict, shown: dict, kpis: list[dict], seen: set[str]) -> list[str]:
    """What this person may not see by name: catalogue rows (ids and names) and measures. A new-key text that names one is withheld."""
    kept = {(t, C.row_id(t, r)) for t in _TABS for r in shown[t]}
    gone = [x for t, head in _NAME_HEADS.items() for r in cat.get(t) or [] if (t, C.row_id(t, r)) not in kept for x in (C.row_id(t, r), C.text_of(r.get(head)))]
    return [g for g in gone if g] + [k["name"] for k in kpis if isinstance(k, dict) and k.get("id") and k["id"] not in seen]


def _new_keys_for_viewer(record: dict, cat: dict, shown: dict, kpis: list[dict], seen: set[str]) -> dict:
    """M2-E4: the glossary, technical definitions, known risks, left-out measures and fingerprints, filtered as the work list, the technical
    definition and the open questions are: only measures this person may see, a link only to a row they may see, a text that names
    something hidden withheld. A key an older record lacks is not added."""
    hidden, names, out = _hidden_terms(cat, shown, kpis, seen), T.row_names(shown), {}
    if "glossary" in record:
        out["glossary"] = [e for e in record["glossary"] if e.get("kpi_id") in seen]
    if "technical" in record:
        out["technical"] = {kid: {**{p["part"]: p["cell"] for p in T.view_parts({"technical": b}, names, hidden)}, "confirmed": b.get("confirmed")}
                            for kid, b in record["technical"].items() if kid in seen}
    if "ambiguities" in record:
        out["ambiguities"] = [a for a in record["ambiguities"] if a.get("kpi_id") in seen and all(r.get("id") in names for r in a.get("refs") or [])
                              and not A.mentions(a, hidden)]
    if "left_out" in record:
        out["left_out"] = [{**r, "reason": WITHHELD if A.mentions({"text": r.get("reason")}, hidden) else r.get("reason")} for r in record["left_out"] if r.get("kpi_id") in seen]
    return out


def for_viewer(record: dict, kpis: list[dict], seen: set[str], viewer: C.Viewer) -> dict:
    """The record as one person may see it (N1): the same rule as every other route. Catalogue rows by the governance guards
    and the visible measures, the process map, confirmations and gaps of visible measures only. Module 3 reads the whole
    record through read_baseline_outcome; this is for the screens and the route."""
    if "company_admin" in viewer.roles:  # the head of data signs for the whole, so sees the whole (A-044)
        return record
    cat = record.get("catalogue") or {}
    shown = C.apply_governance(cat, C.guards(cat, {str(k["id"]): k.get("governance") or {} for k in kpis if isinstance(k, dict) and k.get("id")}),
                               viewer, drop=True)
    shown["kpis"] = [r for r in shown["kpis"] if C.row_id("kpis", r) in seen]
    kept = {(t, C.row_id(t, r)) for t in _TABS for r in shown[t]}
    gone = tuple(f"{_row_name(t, i, r)}:" for t in _TABS for i, r in enumerate(cat.get(t) or []) if (t, C.row_id(t, r)) not in kept)  # same naming as build_gaps
    pmap = record.get("process_map")
    return {**record, "catalogue": shown, **_new_keys_for_viewer(record, cat, shown, kpis, seen),
            "process_map": {k: v for k, v in pmap.items() if k in seen} if isinstance(pmap, dict) else pmap,
            "confirmations": [c for c in record.get("confirmations") or [] if c.get("kpi_id") in seen],
            "gaps": [g for g in record.get("gaps") or []
                     if (g.get("kpi_id") is None or g["kpi_id"] in seen) and not str(g.get("where") or "").startswith(gone)]}


def build_gaps(contract: dict, kpi_views: list[dict], catalogue: dict, governance: dict | None = None) -> list[dict]:
    """The gaps of real kinds only, in the contract's order (N-F): a conflict nobody settled, a part with no owner, personal
    data undecided (a measure's, or a source's), tracking unknown with no next step, an owner who never answered and was
    accepted by the sponsor, and a measure not tracked today. A blank catalogue cell is not a gap."""
    found: list[dict] = []

    def add(kind, kpi, where, accepted=None):
        found.append({"type": kind, "kpi_id": kpi, "where": where, "accepted": accepted})

    for k in kpi_views:
        rev, name = k["review"] or {}, k["name"]
        for s in [{"label": "Source", "status": k["source"]["status"]}, *k["sensing"]]:
            if s["status"] == "conflict":
                add("conflict", k["id"], f"{name}: {s['label'].lower()}, two owners answered differently")
        for p in k["parts"]:
            if p["owner_status"] == "no_owner":
                add("no_owner", k["id"], f"{name}: no {p['owner_label']}")
        if ((governance or {}).get(k["id"]) or {}).get("personal") == "not_sure":
            add("personal_undecided", k["id"], f"{name}: personal data not decided")
        if k["tracking"]["mark"] != "stated" and not (rev.get("next_step") or rev.get("project") or rev.get("tentative_date")):
            add("tracking_unknown", k["id"], f"{name}: not known if it is tracked today, and no next step")
        for who in dict.fromkeys(p["owner_name"] for p in k["parts"] if p["silent"]):
            if rev.get("accepted"):
                add("silent_accepted", k["id"], f"{name}: {who} never answered", rev["accepted"])
        if k["tracking"]["mark"] == "stated" and not k["tracking"]["today"]:
            add("not_tracked", k["id"], f"{name}: {k['tracking']['label'] or 'tracking not stated'}"
                + (f"; next step: {rev['next_step']}" if rev.get("next_step") else "")
                + (f"; project: {rev['project']}" if rev.get("project") else "")
                + (f"; expected {rev['tentative_date']}" if rev.get("tentative_date") else ""), rev.get("accepted"))
    for i, row in enumerate(_own(catalogue).get("sources") or []):
        if isinstance(row, dict) and str(_val(row.get("Contains personal data?")) or "").strip().lower() == "not sure":
            add("personal_undecided", None, f"{_row_name('sources', i, row)}: Contains personal data?")
    types = {t["id"]: t for t in contract["gap_types"]}
    order = list(types)
    out = []
    for n, g in enumerate(sorted(found, key=lambda g: order.index(g["type"])), 1):
        t = types[g["type"]]
        row = {"id": f"G{n:03d}", "type": g["type"], "label": t["label"], "kpi_id": g["kpi_id"], "where": g["where"],
               "severity": t["severity"], "why": t["why"], "action": t["action"], "accepted": g["accepted"]}
        out.append(_pick(row, contract["gap_fields"]))
    return out


def _signed_documents(version: dict, glossary: list[dict], kpis: list[dict]) -> dict:
    """M2-E4: the keys added to the record (contracts/baseline_outcome.yaml `added_keys`): what the two signed documents hold, and their fingerprints."""
    left = version.get("left_out") or {}
    keep = [k for k in kpis if isinstance(k, dict) and k.get("id") and k["id"] not in left]
    return {"glossary": [e for e in glossary if e.get("kpi_id") not in left],
            "technical": {k["id"]: {**T.parts_of(k), "confirmed": ({"by": c["by"], "at": c["at"]} if (c := T.confirmed(k)) else None)} for k in keep},
            "ambiguities": GT.accepted_risks(kpis, left), "left_out": GT.left_out_rows(kpis, left), "documents": version.get("documents") or {}}


def build_outcome(contract: dict, *, outcome_id: str, session_id: str, baseline: dict, version: dict, view: dict,
                  process_map, catalogue: dict, governance: dict | None = None, glossary: list[dict] | None = None, kpis: list[dict] | None = None) -> dict:
    """The record for a signed version. Raises ValueError for one that is not signed: nothing unsigned leaves module 2."""
    if version["status"] != "signed" or not version["countersign"]:
        raise ValueError("only a signed baseline can be handed on")
    conf = [{"kpi_id": kid, "part": pid, "name": got["by"], "at": got["at"]}
            for kid, parts in version["parts"].items() for pid, got in parts.items()]
    cat = _own(catalogue)
    record = {"outcome_id": outcome_id, "session_id": session_id, "module": MODULE_ID, "kind": contract["kind"],
              "baseline_id": baseline["id"], "baseline_version": version["version"],
              "charter_outcome_id": baseline.get("charter_outcome_id"), "signed_at": version["signed_at"],
              "signatures": [{f: s.get(f) for f in contract["signature_fields"]} for s in version["countersign"]],
              "confirmations": [_pick(c, contract["confirmation_fields"]) for c in conf],
              "process_map": process_map if process_map is not None else {}, "catalogue": cat,
              "gaps": build_gaps(contract, view["kpis"], cat, governance), **_signed_documents(version, glossary or [], kpis or [])}
    missing = [k for k in contract["required"] if k not in record]
    if missing:
        raise ValueError(f"the outcome record lacks {missing}")
    return record

