"""E2b: the intake agent reads a manager statement on this machine and writes `extracted_fields`; a person confirms the value.

`extract(plane, document_id, viewer) -> [field ids]` reads value, units, valuation date, currency and status label, each with page and line,
using the X5 locator (`x5_extract._locate`). Rules only: no text from the document is sent to a model, and document text is never an
instruction. A value (nav) always waits for a person; other fields at high confidence are marked confirmed by the reader.
Recommendation 2: when the value is read (still pending review) a `pending` valuation row supersedes the earlier one and
`e3_impact.on_new_valuation` runs at once, so the case, the Operations task and the CIO's unverified change exist before anyone confirms.
`confirm(plane, field_id, viewer, corrected_value=None) -> dict`: a confirmed nav becomes a `confirmed` valuation row superseding the pending
one (append-only: both stay) and a `valuation_confirmed` event is added to the open revision case.
Capital call and distribution notices (K4): when the text is a notice, `fund`, `due_date`, `distribution_amount` and `notice_kind` (call,
distribution, recallable) are read too, each with page and line. The amount waits for a person. Reading records a `noticed` cash movement
per commitment of the fund; confirming records a `confirmed` one that supersedes it, linked to the commitment, and a call due soon opens a
Finance case (k6_liquidity).
"""
from __future__ import annotations

import contextlib
import logging
import re
from decimal import Decimal, InvalidOperation

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.x5_extract import _locate

log = logging.getLogger(__name__)
PROMPT_VERSION, TOOL_POLICY = "intake-rules-1", "read-only-local"
WORKERS = frozenset({"analyst", "company_admin"})
FIELDS = [
    {"name": "nav", "format": "number", "where_usually": "Net asset value (estimate) | Net asset value | NAV | Fund value | Capital account balance"},
    {"name": "call_amount", "format": "number", "where_usually": "Capital required | Call amount | Amount due"},
    {"name": "units", "format": "number", "where_usually": "Units outstanding | Units held | Units"},
    {"name": "valuation_date", "format": "date", "where_usually": "Valuation date | NAV date | As at | As of"},
    {"name": "currency", "format": "text", "where_usually": "Base currency | Currency"},
    {"name": "status_label", "format": "text", "where_usually": "Status | Basis | NAV status"},
]
NOTICE_FIELDS = [
    {"name": "fund", "format": "text", "where_usually": "Fund name | Name of fund | Partnership | Fund:"},
    {"name": "due_date", "format": "date", "where_usually": "Due date | Payment due | Due on | Pay by | Payable by | Value date"},
    {"name": "distribution_amount", "format": "number", "where_usually": "Distribution amount | Amount distributed | Total distribution"},
]
NOTICE_AMOUNT = {"call": "call_amount", "distribution": "distribution_amount", "recallable": "distribution_amount"}
_CALL = re.compile(r"capital call(?!ed)|drawdown|draw-down|call notice|call for capital", re.I)
_DIST = re.compile(r"distribution (?:notice|amount)|notice of distribution|amounts? distributed", re.I)
_NEGATED = re.compile(r"(?:no|not|non)[- ](?:a )?(?:capital call|distribution|recallable)", re.I)
SCALES = (("thousand", Decimal(1000)), ("'000", Decimal(1000)), ("000s", Decimal(1000)), ("million", Decimal(1_000_000)), (" mn", Decimal(1_000_000)))
CCY = re.compile(r"\b(USD|SGD|EUR|GBP|HKD|CHF|JPY|AUD)\b")
PICTURES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


def _need(viewer) -> None:
    if not (set(getattr(viewer, "roles", ()) or ()) & WORKERS):
        raise PermissionError("not permitted")


def _segments(plane, uri: str) -> list[tuple[int, list[tuple[int, str]]]]:
    """[(page, [(line number, cleaned text)])] read locally from the original."""
    from sh_platform.context_docs import reader
    p = plane.path(*str(uri).replace("\\", "/").split("/")) if not str(uri).startswith(("/", "\\")) and ":" not in str(uri)[:3] else plane.path(uri)
    if not p.is_file():
        raise Refused(404, "The original file for this document is not in the company's files.")
    try:
        segs = reader.read_segments(p.name, p.read_bytes())
    except reader.Refusal as e:
        raise Refused(422, str(e)) from None
    pages = []
    for loc, text in segs:
        chunks = text.split("\f")
        for chunk in chunks:
            m = re.search(r"(\d+)", loc or "") if len(chunks) == 1 else None
            lines = [(k, re.sub(r"[*_`]", "", ln).strip()) for k, ln in enumerate(chunk.splitlines(), 1)]
            pages.append((int(m.group(1)) if m else len(pages) + 1, [(k, ln) for k, ln in lines if ln and not re.fullmatch(r"[\s|:\-]+", ln)]))
    return pages


def _read(pages, picture: bool) -> list[dict]:
    """One dict per field found: name, text, numeric, currency, page, line, confidence."""
    found = {}
    for spec in FIELDS:
        for page, lines in pages:
            got = _locate([t for _, t in lines], spec)
            if got["line"] is not None:
                found[spec["name"]] = (page, lines[got["line"]][0], got["value"], got["raw"], lines[got["line"]][1], " ".join(t for _, t in lines))
                break
    out = []
    for name, (page, line, value, raw, whole, page_text) in sorted(found.items()):
        row = {"field_name": name, "value_text": value, "value_numeric": None, "currency": None, "page_number": page, "line_number": line}
        if name in ("nav", "units", "call_amount", "distribution_amount"):
            scale = next((f for k, f in SCALES if k in page_text.lower()), Decimal(1)) if name == "nav" else Decimal(1)
            row["value_numeric"] = Decimal(value) * scale
            if scale != 1:
                row["value_text"] = f"{value} (stated in {'thousands' if scale == 1000 else 'millions'})"
            m = CCY.search(whole)
            row["currency"] = m.group(1) if m else None
        elif name == "currency":
            m = CCY.search(raw)
            if not m:
                continue
            row["value_text"] = row["currency"] = m.group(1)
        elif name == "status_label":
            m = re.search(r"estimate|final|amended|revised|restated", raw, re.I)
            if not m:
                continue  # document text is never stored as a status word
            row["value_text"] = m.group().lower()
        sure = not picture and (name != "nav" or row["currency"] or "currency" in found)
        row["confidence"] = "high" if sure else "low" if picture else "medium"
        out.append(row)
    return out + _notice(pages, picture, {r["field_name"]: r for r in out})


def _notice(pages, picture: bool, have: dict) -> list[dict]:
    """The extra fields of a capital call or distribution notice, or [] when the text is not one (a statement is read as before)."""
    kind = None
    for page, lines in pages:
        for k, ln in lines:
            if not _NEGATED.search(ln) and (_CALL.search(ln) or _DIST.search(ln)):
                kind = ("call" if _CALL.search(ln) else "distribution", page, k)
                break
        if kind:
            break
    if not kind:
        return []
    k, page, line = kind
    whole = "\n".join(t for _, ls in pages for _, t in ls)
    if k == "distribution" and re.search(r"(?<![-\w])recallable", whole, re.I):
        k = "recallable"
    amount_name = NOTICE_AMOUNT[k]
    extra = {}
    for spec in NOTICE_FIELDS:
        for pg, lines in pages:
            got = _locate([t for _, t in lines], spec)
            if got["line"] is not None:
                extra[spec["name"]] = (pg, lines[got["line"]][0], got["value"], got["raw"], lines[got["line"]][1])
                break
    if amount_name not in have and amount_name not in extra:
        return []
    out = [{"field_name": "notice_kind", "value_text": k, "value_numeric": None, "currency": None, "page_number": page, "line_number": line,
            "confidence": "low" if picture else "high"}]
    for name, (pg, ln, value, raw, whole_line) in sorted(extra.items()):
        row = {"field_name": name, "value_text": value, "value_numeric": None, "currency": None, "page_number": pg, "line_number": ln,
               "confidence": "low" if picture else "high"}
        if name == "distribution_amount":
            row["value_numeric"] = Decimal(value)
            m = CCY.search(whole_line)
            row["currency"] = m.group(1) if m else None
        out.append(row)
    return out


def _open_case(plane, instrument_id) -> str | None:
    """The newest open revision case for the instrument, or None."""
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select id from exceptions where instrument_id = ? and exception_type = 'revision' and status in ('new','assigned','investigating','waiting_check')"
                        " order by detected_at desc limit 1", [instrument_id]).fetchone()
    return str(r[0]) if r else None


def _record_valuation(plane, doc: dict, field: dict, amount: Decimal, ccy: str, vdate, approval_status: str, supersede_id: str | None = None) -> str:
    """One valuation row for the statement's value. It supersedes `supersede_id`, else the newest row of the same fund and date; the
    portfolio comes from that row (a new row never loses its subject keys)."""
    from sh_platform.v1 import e1_write
    with wh.connect(plane, read_only=True) as con:
        prev = None
        if supersede_id:
            prev = con.execute("select id, portfolio_id from valuation_observations where id = ?", [supersede_id]).fetchone()
        if prev is None:
            prev = con.execute("select v.id, v.portfolio_id from valuation_observations v where v.instrument_id = ? and v.valuation_date = ? and not exists"
                               " (select 1 from valuation_observations s where s.supersedes_valuation_id = v.id) order by v.recorded_at desc limit 1",
                               [doc["instrument_id"], vdate]).fetchone()
    return str(e1_write.record(plane, "valuation_observations", {
        "instrument_id": doc["instrument_id"], "portfolio_id": str(prev[1]) if prev and prev[1] else None, "evidence_document_id": field["document_id"],
        "extracted_field_id": field["id"], "valuation_date": vdate, "received_at": doc["received_at"], "value_amount": amount, "currency": ccy,
        "approval_status": approval_status,
        "valuation_type": "manager_estimate" if doc["document_status"] in ("estimate", "revised_estimate") else "manager_final"},
        supersedes_id=str(prev[0]) if prev else None))


def _doc(con, document_id: str) -> dict:
    cur = con.execute("select instrument_id, valuation_date, received_at, document_status from documents where id = ?", [document_id])
    return dict(zip([c[0] for c in cur.description], cur.fetchone()))


def _matched(plane, document_id: str, doc: dict) -> dict:
    """The document row with its fund filled in from an approved match when the upload could not match it."""
    if doc["instrument_id"] is None:
        from sh_platform.v1 import e2_intake
        doc = {**doc, "instrument_id": e2_intake.rematch(plane, document_id)}
    return doc


def _scan(plane, document_id: str, pages) -> None:
    """Instruction-like text in a statement is never followed; a person is told (the document is flagged)."""
    from sh_platform.v1 import e4_guard
    hits = e4_guard.scan_document_text("\n".join(t for _, lines in pages for _, t in lines))
    if hits:
        log.warning("a statement contains instruction-like text (%d phrase(s)); flagged for a person", len(hits))
        with wh.connect(plane) as con:
            con.execute("update documents set processing_status = 'flagged' where id = ?", [document_id])


def read_document(plane, document_id: str, viewer) -> dict:
    """Read a document and write its extracted fields (once). Returns {ids, exception_id}: when the value is found and the fund is matched, a
    pending valuation is recorded and the revision check runs now, so the case exists before Operations confirms."""
    _need(viewer)
    with wh.connect(plane) as con:
        d = con.execute("select original_uri, original_filename from documents where id = ?", [document_id]).fetchone()
        if d is None:
            raise Refused(404, "We could not find that document.")
        have = [str(r[0]) for r in con.execute("select id from extracted_fields where document_id = ? order by field_name", [document_id]).fetchall()]
        doc = _doc(con, document_id)
    doc = _matched(plane, document_id, doc)
    if have:
        return {"ids": have, "exception_id": _open_case(plane, doc["instrument_id"]) if doc["instrument_id"] else None}
    picture = str(d[1] or d[0]).lower().endswith(PICTURES)
    pages = _segments(plane, d[0])
    found = _read(pages, picture)
    if not found:
        raise Refused(422, "No value could be read from this document. A person should read it.")
    _scan(plane, document_id, pages)
    try:
        from sh_platform.v1.e6_trace import agent_run
        ctx = agent_run(plane, viewer, "intake", "rules-only", PROMPT_VERSION, TOOL_POLICY)
    except ImportError:
        log.warning("e6_trace is not available; the extraction run is not recorded")
        ctx = contextlib.nullcontext()
    ids, rows = [], {}
    notice = any(f["field_name"] == "notice_kind" for f in found)
    with ctx as run:
        run_id = run if isinstance(run, str) else getattr(run, "id", None)
        with wh.connect(plane) as con:
            for f in found:
                fid = wh.new_id()
                auto = f["confidence"] == "high" and f["field_name"] != "nav" and not (notice and f["field_name"] in NOTICE_AMOUNT.values())
                con.execute(
                    "insert into extracted_fields (id, organization_id, document_id, field_name, value_text, value_numeric, currency, page_number,"
                    " line_number, confidence, extracted_by_agent_run_id, review_status, reviewed_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [fid, org_id(plane), document_id, f["field_name"], f["value_text"], f["value_numeric"], f["currency"], f["page_number"],
                     f["line_number"], f["confidence"], run_id, "confirmed" if auto else "pending", wh.now() if auto else None])
                ids.append(fid)
                rows[f["field_name"]] = {**f, "id": fid, "document_id": document_id}
    nav = rows.get("nav")
    vdate = doc["valuation_date"] or (rows.get("valuation_date") or {}).get("value_text")
    ccy = (nav or {}).get("currency") or (rows.get("currency") or {}).get("value_text")
    exc = None
    if notice:
        _noticed(plane, document_id, doc, rows)
    if nav and doc["instrument_id"] and vdate and ccy:
        from sh_platform.v1 import e3_impact  # needed: fail loudly, never skip the impact check
        vid = _record_valuation(plane, doc, nav, Decimal(str(nav["value_numeric"])), ccy, vdate, "pending")
        exc = e3_impact.on_new_valuation(plane, vid)
    return {"ids": ids, "exception_id": exc}


def _noticed(plane, document_id: str, doc: dict, rows: dict) -> None:
    """A read notice is recorded at once as a `noticed` cash movement, so the forecast shows the call as unconfirmed before a person confirms."""
    from sh_platform.v1 import k6_liquidity
    kind = rows["notice_kind"]["value_text"]
    amt = rows.get(NOTICE_AMOUNT[kind])
    ccy = (amt or {}).get("currency") or (rows.get("currency") or {}).get("value_text")
    due = (rows.get("due_date") or {}).get("value_text")
    if not (amt and doc["instrument_id"] and ccy) or (kind == "call" and not due):
        return
    try:
        k6_liquidity.record_notice(plane, document_id, str(doc["instrument_id"]), kind, amt["value_numeric"], ccy, due, "noticed")
    except Refused as e:
        log.warning("a notice was read but not recorded: %s", e.message)


def _confirm_notice(plane, f: dict, viewer, corrected: Decimal | None, status: str, note: str | None) -> dict | None:
    """Confirming the amount of a call or distribution notice: the confirmed cash movement per commitment; None when the field is not one."""
    with wh.connect(plane, read_only=True) as con:
        kind = con.execute("select value_text from extracted_fields where document_id = ? and field_name = 'notice_kind'", [f["document_id"]]).fetchone()
        if not kind or NOTICE_AMOUNT.get(kind[0]) != f["field_name"]:
            return None
        others = dict(con.execute("select field_name, coalesce(corrected_value_text, value_text) from extracted_fields where document_id = ?"
                                  " and review_status in ('confirmed','corrected')", [f["document_id"]]).fetchall())
        doc = _doc(con, f["document_id"])
    doc = _matched(plane, f["document_id"], doc)
    ccy = f["currency"] or others.get("currency")
    if doc["instrument_id"] is None:
        raise Refused(409, "This notice is not matched to a fund yet. Match the fund first.")
    if not ccy:
        raise Refused(409, "The currency must be confirmed first.")
    from sh_platform.v1 import k6_liquidity
    amount = corrected if corrected is not None else Decimal(str(f["value_numeric"]))
    got = k6_liquidity.record_notice(plane, f["document_id"], str(doc["instrument_id"]), kind[0], amount, ccy, others.get("due_date"), "confirmed", viewer,
                                     f["page_number"], f["line_number"])
    with wh.connect(plane) as con:
        _review(plane, con, f["id"], viewer, status, note)
    return {"field_id": f["id"], "review_status": status, "valuation_id": None, "exception_id": got["exception_id"], "cash_movement_ids": got["ids"]}


def extract(plane, document_id: str, viewer) -> list[str]:
    """Read a document and write its extracted fields (once: a second call returns the same ids)."""
    return read_document(plane, document_id, viewer)["ids"]


def fields_of(plane, document_id: str) -> list[dict]:
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute("select * from extracted_fields where document_id = ? order by field_name", [document_id])
        cols = [c[0] for c in cur.description]
        return [{k: (v if v is None or isinstance(v, (str, int, bool)) else str(v)) for k, v in zip(cols, r)} for r in cur.fetchall()]


def _review(plane, con, fid: str, viewer, status: str, corrected: str | None) -> None:
    try:
        from sh_platform.v1.e6_trace import _user_uuid  # the person's id in the users table (None when not seeded)
        who = _user_uuid(plane, getattr(viewer, "account_id", None))
    except ImportError:
        who = None
    con.execute("update extracted_fields set review_status = ?, reviewed_by = ?, reviewed_at = ?, corrected_value_text = ? where id = ?",
                [status, who, wh.now(), corrected, fid])


def _pending(con, fid: str) -> dict:
    cur = con.execute("select * from extracted_fields where id = ?", [fid])
    cols = [c[0] for c in cur.description]
    r = cur.fetchone()
    if r is None:
        raise Refused(404, "We could not find that field.")
    f = dict(zip(cols, r))
    if f["review_status"] != "pending":
        raise Refused(409, "This field has already been reviewed.")
    return f


def reject(plane, field_id: str, viewer, reason: str = "") -> dict:
    _need(viewer)
    with wh.connect(plane) as con:
        _pending(con, field_id)
        _review(plane, con, field_id, viewer, "rejected", (reason or "")[:255] or None)
    return {"field_id": field_id, "review_status": "rejected", "valuation_id": None, "exception_id": None}


def confirm(plane, field_id: str, viewer, corrected_value=None) -> dict:
    """Confirm (or correct) a field. A nav becomes the new valuation and the revision check runs."""
    _need(viewer)
    corrected = None
    if corrected_value not in (None, ""):
        try:
            corrected = Decimal(re.sub(r"[,\s]", "", str(corrected_value)))
        except InvalidOperation:
            raise Refused(422, "That is not a number. Type the value as it appears, for example 10,180,000.") from None
    with wh.connect(plane) as con:
        f = _pending(con, field_id)
    status = "corrected" if corrected is not None else "confirmed"
    note = None if corrected is None else str(corrected)
    if f["field_name"] in NOTICE_AMOUNT.values() and (got := _confirm_notice(plane, f, viewer, corrected, status, note)):
        return got
    if f["field_name"] != "nav":
        with wh.connect(plane) as con:
            _review(plane, con, field_id, viewer, status, note)
        return {"field_id": field_id, "review_status": status, "valuation_id": None, "exception_id": None}
    try:  # all are needed before anything is written: fail loudly, never skip the impact check
        from sh_platform.v1 import e3_impact
        from sh_platform.v1.e4_cases import add_event
    except ImportError:
        log.warning("e3_impact or e4_cases is missing; a valuation cannot be confirmed yet")
        raise
    with wh.connect(plane, read_only=True) as con:
        doc = _doc(con, f["document_id"])
    doc = _matched(plane, f["document_id"], doc)
    with wh.connect(plane, read_only=True) as con:
        others = dict(con.execute("select field_name, coalesce(corrected_value_text, value_text) from extracted_fields where document_id = ?"
                                  " and review_status in ('confirmed','corrected')", [f["document_id"]]).fetchall())
        pending = con.execute("select id from valuation_observations where extracted_field_id = ? and approval_status = 'pending'", [field_id]).fetchone()
    vdate = others.get("valuation_date") or doc["valuation_date"]
    ccy = f["currency"] or others.get("currency")
    if doc["instrument_id"] is None:
        raise Refused(409, "This statement is not matched to a fund yet. Match the fund first.")
    if not vdate or not ccy:
        raise Refused(409, "The valuation date and currency must be confirmed first.")
    amount = corrected if corrected is not None else Decimal(str(f["value_numeric"]))
    vid = _record_valuation(plane, doc, f, amount, ccy, vdate, "confirmed", str(pending[0]) if pending else None)
    with wh.connect(plane) as con:
        _review(plane, con, field_id, viewer, status, note)
    exc = _open_case(plane, doc["instrument_id"])
    if exc:
        said = f"Operations confirmed the manager-reported valuation of {amount:,.2f} {ccy} read from the amended statement."
        if corrected is not None:
            said += f" Operations corrected the figure read from the page ({Decimal(str(f['value_numeric'])):,.2f}); the case impacts keep the value read from the page."
        add_event(plane, exc, viewer, "valuation_confirmed", said, evidence_document_id=f["document_id"])
    else:  # the first statement for this fund: nothing was raised at extraction
        exc = e3_impact.on_new_valuation(plane, vid)
    return {"field_id": field_id, "review_status": status, "valuation_id": vid, "exception_id": exc}
