"""E2a Document intake and revision detection (v2.0 manager statements).

`register` keeps the original untouched under `landing/originals/<sha256>__<name>`, writes one `documents` row, indexes the text for
search, matches the manager's fund name to an instrument (E2c `resolve`) and links a revision to the statement it replaces.
Documents are never updated: a revision is a new row whose `supersedes_document_id` points at the old one.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from pathlib import Path

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
GROUP = "Manager statements"
REVISED_WORDS = re.compile(r"\b(amended|revised|restated)\b", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DAY_MON = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b")
_MON_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_CUE = re.compile(r"(valuation date|valued|as at|as of|nav date|period end)", re.I)
_FUND = re.compile(r"\b(fund|lp|l\.p\.|trust|partners|capital)\b", re.I)
DOC_TYPES = {"Statements and invoices": "manager_statement", "Capital calls and distributions": "capital_call_notice"}
COLS = ["id", "instrument_id", "document_type", "title", "original_filename", "original_uri", "valuation_date", "received_at",
        "document_status", "supersedes_document_id", "processing_status", "contains_personal_data"]


def _d(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _dates(line: str) -> list[date]:
    out = [_d(int(a), int(b), int(c)) for a, b, c in _ISO.findall(line)]
    for d, mon, y in _DAY_MON.findall(line):
        if mon[:3].lower() in MONTHS:
            out.append(_d(int(y), MONTHS[mon[:3].lower()], int(d)))
    for mon, d, y in _MON_DAY.findall(line):
        if mon[:3].lower() in MONTHS:
            out.append(_d(int(y), MONTHS[mon[:3].lower()], int(d)))
    return [x for x in out if x]


def valuation_date_of(name: str, lines: list[str]) -> date | None:
    """The date on a line that says valuation date / as at / valued; else the only date in the first lines; else one in the file name."""
    for ln in lines[:60]:
        if _DATE_CUE.search(ln) and (ds := _dates(ln)):
            return ds[0]
    seen = [d for ln in lines[:20] for d in _dates(ln)]
    if len(set(seen)) == 1:
        return seen[0]
    ds = _dates(name)
    return ds[0] if ds else None


def label_of(lines: list[str]) -> str | None:
    """The status word the manager printed: 'final', 'estimate' or None."""
    text = " ".join(lines[:80]).lower()
    if re.search(r"(?<!not )(?<!non-)(?<!non )\bfinal\b", text):
        return "final"
    return "estimate" if re.search(r"\b(estimate|estimated|unaudited|preliminary)\b", text) else None


_PREFIX = re.compile(r"^\s*fund\s*(?:[A-Za-z]\s*[-:\u2013]|:)\s*", re.I)


def fund_names(name: str, lines: list[str]) -> list[str]:
    """Candidate fund names, best first: heading lines that look like a fund ('Fund A - ' / 'Fund:' stripped), else the first two short lines,
    then the file name. Only these are resolved, so an upload does not create a proposal per heading."""
    short = [ln for ln in lines[:15] if len(ln) < 90 and not _DATE_CUE.search(ln) and not _dates(ln)]
    heads = [_PREFIX.sub("", ln).strip() for ln in short if _FUND.search(ln)] or short[:2]
    return list(dict.fromkeys(h for h in heads if h)) + [re.sub(r"[_\-]+", " ", name.rsplit(".", 1)[0])]


def _source(con, org: str, code: str) -> str:
    row = con.execute("select id from source_systems where organization_id=? and source_code=?", [org, code]).fetchone()
    if row:
        return str(row[0])
    sid = wh.new_id()
    con.execute("insert into source_systems values (?,?,?,?,?,?,?,?,?,?,?)",
                [sid, org, code, code.replace("_", " ").capitalize(), "document", "upload", None, None, None, None, True])
    return sid


def _group(con, org: str) -> str:
    row = con.execute("select id from access_groups where organization_id=? and group_name=?", [org, GROUP]).fetchone()
    if row:
        return str(row[0])
    gid = wh.new_id()
    con.execute("insert into access_groups values (?,?,?,?)", [gid, org, GROUP, "Who may read manager statements"])
    return gid


def _stored(plane, name: str, data: bytes, sha: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-120:] or "file"
    rel = f"landing/originals/{sha}__{safe}"
    p = plane.path(*rel.split("/"))
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return rel


def _find_instrument(plane, source_id: str, names: list[str]) -> str | None:
    try:
        from sh_platform.v1 import e2_match
    except ImportError:
        log.warning("E2c e2_match is not installed: fund names cannot be matched")
        raise
    for n in names:
        got = e2_match.resolve(plane, n, source_id)
        if got.get("instrument_id") and got.get("status") == "approved":
            return got["instrument_id"]
    return None


def rematch(plane, document_id: str) -> str | None:
    """The fund this statement means, now: its own instrument, else the approved match of the fund name in the original (a person may have
    approved the match after the upload; documents are never updated, so this is worked out when needed)."""
    from sh_platform.v1 import doc_index
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select source_system_id, original_filename, original_uri, instrument_id from documents where id=?", [document_id]).fetchone()
    if r is None or r[3]:
        return str(r[3]) if r and r[3] else None
    try:
        lines, _ = doc_index.read_lines(r[1], plane.path(*str(r[2]).split("/")).read_bytes())
    except Exception:  # noqa: BLE001
        return None
    return _find_instrument(plane, str(r[0]), fund_names(r[1] or "", lines))


def _previous(con, org: str, instrument_id: str | None, vdate: date | None) -> dict | None:
    """The newest statement for the same fund and valuation date that no later one replaces yet."""
    if not (instrument_id and vdate):
        return None
    row = con.execute("""select id, received_at from documents d where organization_id=? and instrument_id=? and valuation_date=?
                         and not exists (select 1 from documents n where n.supersedes_document_id = d.id)
                         order by received_at desc, recorded_at desc limit 1""", [org, instrument_id, vdate]).fetchone()
    return {"id": str(row[0]), "received_at": row[1]} if row else None


def register(plane, file_path, viewer, source_code: str = "manager_email", received_at: datetime | None = None,
             data: bytes | None = None, filename: str | None = None) -> str:
    """Register a statement and return its document id. The same file again returns the same id (hash). `data`/`filename` stand in
    for reading `file_path` (an upload); `received_at` defaults to now (the demo seed and tests set it)."""
    name = filename or Path(str(file_path)).name
    data = data if data is not None else Path(str(file_path)).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    org = org_id(plane)
    received = received_at or wh.now()
    from sh_platform.v1 import doc_index, k1_classify, l3_library
    try:
        lines, _ = doc_index.read_lines(name, data)
    except Exception:  # noqa: BLE001 - an unreadable file is still kept; the person reads it
        log.warning("a statement could not be read for intake")
        lines = []
    head = " ".join(lines[:15])
    folder = l3_library.classify(name, head)["folder"]
    dtype = DOC_TYPES.get(folder) or ("manager_statement" if _FUND.search(head) else re.sub(r"\W+", "_", folder.lower()))
    with wh.connect(plane) as con:
        dup = con.execute("select id from documents where organization_id=? and content_hash=?", [org, sha]).fetchone()
        if dup:
            return str(dup[0])
        source = _source(con, org, source_code)
    instrument = _find_instrument(plane, source, fund_names(name, lines))
    vdate = valuation_date_of(name, lines)
    rel = _stored(plane, name, data, sha)
    pii = bool(k1_classify.scan_pii(name, data).get("found"))
    words = bool(REVISED_WORDS.search(" ".join(lines[:80])))
    with wh.connect(plane) as con:
        prev = _previous(con, org, instrument, vdate)
        if prev and not (words or received > prev["received_at"]):
            prev = None
        status = "final" if label_of(lines) == "final" else ("revised_estimate" if prev else "estimate")
        did = wh.new_id()
        con.execute("insert into documents (id, organization_id, source_system_id, source_record_id, access_group_id, instrument_id, external_document_id,"
                    " document_type, title, original_filename, original_uri, content_hash, document_date, valuation_date, received_at, recorded_at,"
                    " document_status, supersedes_document_id, processing_status, contains_personal_data) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [did, org, source, None, _group(con, org), instrument, None, dtype, (lines[0] if lines else name)[:300], name, rel, sha,
                     None, vdate, received, wh.now(), status, prev["id"] if prev else None,
                     "registered" if instrument else "needs_match", pii])
    if doc_index._slow(rel):
        doc_index.index_later(plane, rel)
    else:
        doc_index.ensure(plane, rel)
    return did


def supersession_of(plane, document_id: str) -> str | None:
    """The id of the document this one replaces, or None."""
    with wh.connect(plane, read_only=True) as con:
        row = con.execute("select supersedes_document_id from documents where id=? and organization_id=?",
                          [document_id, org_id(plane)]).fetchone()
    return str(row[0]) if row and row[0] else None


def listing(plane, instrument_id: str | None = None) -> list[dict]:
    """Documents, newest received first, each marked `current` when no later document replaces it."""
    q, args = f"select {', '.join(COLS)} from documents where organization_id=?", [org_id(plane)]
    if instrument_id:
        q, args = q + " and instrument_id=?", args + [instrument_id]
    with wh.connect(plane, read_only=True) as con:
        rows = [{k: (v.isoformat() if hasattr(v, "isoformat") else str(v) if k.endswith("id") and v else v) for k, v in zip(COLS, r)}
                for r in con.execute(q + " order by received_at desc", args).fetchall()]
        replaced = {str(r[0]) for r in con.execute("select supersedes_document_id from documents where organization_id=? "
                                              "and supersedes_document_id is not null", [org_id(plane)]).fetchall()}
    for r in rows:
        r["current"] = r["id"] not in replaced
    return rows


def detail(plane, document_id: str) -> dict:
    """The document with its chain, oldest first (statements it replaced, itself, any that replaced it)."""
    rows = {r["id"]: r for r in listing(plane)}
    if document_id not in rows:
        raise Refused(404, "We could not find that document.")
    nxt = {r["supersedes_document_id"]: r["id"] for r in rows.values() if r["supersedes_document_id"]}
    chain, cur = [document_id], rows[document_id]
    while cur["supersedes_document_id"] in rows:
        cur = rows[cur["supersedes_document_id"]]
        chain.insert(0, cur["id"])
    cur = rows[document_id]
    while cur["id"] in nxt:
        cur = rows[nxt[cur["id"]]]
        chain.append(cur["id"])
    return {**rows[document_id], "chain": [rows[i] for i in chain]}
