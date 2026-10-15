"""E2 screen view: the shapes the Evidence Explorer (`ui/src/v1/e2/api.ts`) reads, built from E2a documents, E2b fields and E2c identifiers.

One place joins them so the routes and the screen agree: `rows` (list), `detail` (statement page), `field_view` (one field after a decision),
`match_of_identifier` (one match after an approval). Dates are ISO days. Nothing here writes.
"""
from __future__ import annotations

import re
from decimal import Decimal

from sh_platform.v1 import e2_extract as X
from sh_platform.v1 import e2_intake as E
from sh_platform.v1 import wh

BASE = "/api/v1/evidence/documents"
NAMES = {"nav": "Net asset value", "units": "Units outstanding", "valuation_date": "Valuation date", "currency": "Currency",
         "status_label": "Status", "call_amount": "Capital called", "notice_kind": "Kind of notice", "due_date": "Due date", "fund": "Fund",
         "distribution_amount": "Distribution amount"}
KIND_WORDS = {"call": "Capital call", "distribution": "Distribution", "recallable": "Recallable distribution"}
CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}
STATE = {"pending": "waiting"}
STATUS_WORDS = {"estimate": "Estimate", "final": "Final", "revised_estimate": "Revised estimate"}


def _day(v) -> str:
    return str(v)[:10] if v else ""


def _shown(f: dict) -> str:
    """A field's value as a person reads it: money with its currency, else the text; a correction wins."""
    if f.get("corrected_value_text"):
        return f"{f['currency'] or ''} {Decimal(f['corrected_value_text']):,.2f}".strip() if f["field_name"] in ("nav", "call_amount", "distribution_amount") else f["corrected_value_text"]
    if f["field_name"] in ("nav", "call_amount", "distribution_amount") and f.get("value_numeric") is not None:
        return f"{f['currency'] or ''} {Decimal(str(f['value_numeric'])):,.2f}".strip()
    if f["field_name"] == "units" and f.get("value_numeric") is not None:
        return f"{Decimal(str(f['value_numeric'])):,}"
    if f["field_name"] == "notice_kind":
        return KIND_WORDS.get(f.get("value_text"), f.get("value_text") or "")
    return f.get("value_text") or ""


def _instrument_names(plane) -> dict[str, str]:
    with wh.connect(plane, read_only=True) as con:
        return {str(i): n for i, n in con.execute("select id, canonical_name from instruments").fetchall()}


def can_see(plane, viewer, instrument_id, cache: dict | None = None) -> bool:
    """Operations (analyst, company admin) read every statement; others only those of funds held in a portfolio they may see (E1d, fail closed).
    A statement not yet matched to a fund is for Operations only. Pass one `cache` dict across a list so the grants and holdings are read once."""
    if set(getattr(viewer, "roles", ()) or ()) & X.WORKERS:
        return True
    if not instrument_id:
        return False
    from sh_platform.v1 import e1_access
    c = {} if cache is None else cache
    if "held" not in c:
        held: dict[str, set[str]] = {}
        with wh.connect(plane, read_only=True) as con:
            for i, p in con.execute("select distinct instrument_id, portfolio_id from valuation_observations where portfolio_id is not null").fetchall():
                held.setdefault(str(i), set()).add(str(p))
        c["held"], c["seen"] = held, {str(x) for x in e1_access.visible_portfolios(plane, viewer)}
    return bool(c["held"].get(str(instrument_id), set()) & c["seen"])


def check(plane, viewer, doc_id: str, d: dict | None = None) -> None:
    from sh_platform.v1.i2_north import Refused
    d = d or E.detail(plane, doc_id)
    if not can_see(plane, viewer, d["instrument_id"]):
        raise Refused(403, "You do not have access to this statement.")


def rows(plane, viewer, instrument_id: str | None = None) -> list[dict]:
    """The statement list: every document the viewer may see, with the fund's name and Current / Superseded."""
    names, cache = _instrument_names(plane), {}
    return [{**d, "instrument_name": names.get(d["instrument_id"] or "") or "Not matched to a fund yet", "label": "Current" if d["current"] else "Superseded",
             "valuation_date": _day(d["valuation_date"]), "received_at": _day(d["received_at"])} for d in E.listing(plane, instrument_id)
            if can_see(plane, viewer, d["instrument_id"], cache)]


def _fields_by_doc(plane, ids: list[str]) -> dict[str, dict[str, dict]]:
    return {i: {f["field_name"]: f for f in X.fields_of(plane, i)} for i in ids}


def _field_rows(plane, doc_id: str, chain: list[dict]) -> list[dict]:
    by = _fields_by_doc(plane, [c["id"] for c in chain])
    first = by[chain[0]["id"]] if chain[0]["id"] != doc_id else {}
    return [{"id": f["id"], "field": NAMES.get(n, n), "original": _shown(first[n]) if n in first else None, "amended": _shown(f),
             "confidence": CONFIDENCE.get(f["confidence"], 0.3), "state": STATE.get(f["review_status"], f["review_status"]),
             "page": f["page_number"], "line": f["line_number"]} for n, f in by[doc_id].items()]


def field_view(plane, field_id: str) -> dict:
    """One field in the screen's shape (the answer to Confirm reads / Not right)."""
    with wh.connect(plane, read_only=True) as con:
        doc_id = str(con.execute("select document_id from extracted_fields where id = ?", [field_id]).fetchone()[0])
    return next(f for f in _field_rows(plane, doc_id, E.detail(plane, doc_id)["chain"]) if f["id"] == field_id)


def _can_approve(viewer) -> bool:
    from sh_platform.v1.seats import DATA_ENGINEER, OPS_MANAGER, seat_of
    return bool(seat_of(viewer) & {OPS_MANAGER, DATA_ENGINEER})


def match_of_identifier(plane, identifier_id: str, viewer) -> dict:
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select i.id, i.identifier_value, i.mapping_status, n.canonical_name from instrument_identifiers i"
                        " left join instruments n on n.id = i.instrument_id where i.id = ?", [identifier_id]).fetchone()
    return {"identifier_id": str(r[0]), "source_name": r[1], "instrument_name": r[3], "status": r[2], "can_approve": _can_approve(viewer)}


def _match(plane, doc_id: str, viewer) -> dict:
    """How the manager's fund name was matched: the identifier for this source that fits a name in the file."""
    with wh.connect(plane, read_only=True) as con:
        d = con.execute("select source_system_id, original_filename, original_uri, instrument_id from documents where id = ?", [doc_id]).fetchone()
        ids = con.execute("select id, identifier_value, mapping_status, instrument_id from instrument_identifiers where source_system_id = ?"
                          " and mapping_status in ('approved','proposed') order by approved_at desc nulls last", [d[0]]).fetchall()
    names, lines = [], []
    try:
        from sh_platform.v1 import doc_index
        lines = doc_index.read_lines(d[1], plane.path(*str(d[2]).split("/")).read_bytes())[0]
        names = E.fund_names(d[1] or "", lines)
    except Exception:  # noqa: BLE001 - an unreadable original just means no name to show
        names = [d[1] or "this statement"]
    # fund_names can return the manager's heading first; any whole line of the file that is a known name of the fund counts too
    keys = {re.sub(r"\W+", "", n.lower()): n for n in [*lines, *names] if n and n.strip()}
    for i in ids:
        if re.sub(r"\W+", "", i[1].lower()) in keys and (str(i[3]) == str(d[3]) or not d[3]):
            return match_of_identifier(plane, str(i[0]), viewer)
    own = _instrument_names(plane).get(str(d[3])) if d[3] else None
    if own and re.sub(r"\W+", "", own.lower()) in keys:   # filed on the fund and the file names it by its own name
        return {"identifier_id": "", "source_name": own, "instrument_name": own, "status": "approved", "can_approve": False}
    return {"identifier_id": "", "source_name": names[0] if names else "This statement", "instrument_name": None, "status": "unknown",
            "can_approve": False}


def detail(plane, doc_id: str, viewer) -> dict:
    """The statement page: versions side by side (oldest first), the fields with original and amended values, the match."""
    d = E.detail(plane, doc_id)
    check(plane, viewer, doc_id, d)
    chain = d["chain"]
    by = _fields_by_doc(plane, [c["id"] for c in chain])
    versions = []
    for k, c in enumerate(chain):
        f = by[c["id"]]
        nav = f.get("nav")
        said = f.get("status_label", {}).get("value_text")
        versions.append({"id": c["id"], "label": "Current" if k == len(chain) - 1 else "Superseded", "received_at": _day(c["received_at"]),
                         "status_label": (said or "").capitalize() or STATUS_WORDS.get(c["document_status"], c["document_status"]),
                         "value_text": _shown(nav) if nav else "Not read yet", "page": nav["page_number"] if nav else None,
                         "line": nav["line_number"] if nav else None, "excerpt": "", "file_url": f"{BASE}/{c['id']}/original"})
    names = _instrument_names(plane)
    return {"id": doc_id, "instrument_name": names.get(d["instrument_id"] or "") or d["title"], "valuation_date": _day(d["valuation_date"]),
            "versions": versions, "fields": _field_rows(plane, doc_id, chain), "match": _match(plane, doc_id, viewer),
            "can_review": bool(set(getattr(viewer, "roles", ()) or ()) & X.WORKERS)}
