"""Harbor 3.0: emails, notes and Word files dropped into a data build are documents, never tables (skill intent.read-company-doc).

An .eml, .md, .txt or .docx file of the thread is
  1. registered through the 2.0 document intake (e2_intake: hash, fund match, which document replaces which) and read into text on this
     machine (context_docs.reader); the text is indexed, so Lumen and Knowledge can cite it;
  2. read for figures: a line "Label: CCY amount" (an amended NAV in a revision notice) is a figure the document states. It becomes one
     PENDING 2.0 extracted field (nav, with its paragraph and line) and one question in Decision 2 that quotes the line. Nothing loads
     before the person picks the line; the pick is confirmed through e2_extract.confirm, which records the valuation that supersedes the
     earlier one of the same fund and date (supersedes_valuation_id) and runs the revision check;
  3. a document with no such line, or one the person keeps as context, is listed as "read as context", never as "not loaded".
An uploaded document is context, never by itself the source of a figure: a figure here reaches the warehouse only after a person confirms it.
Prose figures ("from 7,050,000 to 7,012,500 USD") are not offered; they stay in the indexed text for Lumen to quote.
State: thread["docs"] = {name: {doc_id, status: context|asked|confirmed|kept|aside, figures: [{label, value, para, line, quote, field_id}]}}."""
import base64
import logging
import re

log = logging.getLogger(__name__)
SKILL = "intent.read-company-doc"
TEXT = (".eml", ".md", ".txt", ".docx")
CONTEXT = "Keep it as context only"
FIGURE = re.compile(r"^([A-Za-z][A-Za-z ()/'&.-]{1,48}?)\s*:\s*([+-]?[A-Z]{3}\s*[-+]?\d[\d,]*(?:\.\d+)?)\b")
CCY = re.compile(r"[A-Z]{3}")


def is_doc(name: str) -> bool:
    return str(name).lower().endswith(TEXT)


def figures_of(name: str, data: bytes) -> list[dict]:
    """[{label, value, amount, currency, para, line, quote}]: each "Label: CCY amount" line, with its paragraph (blank-line separated) and line."""
    from sh_platform.context_docs import reader
    text = "\n".join(t for _, t in reader.read_segments(name, data))
    out, para, blank = [], 1, False
    for k, raw in enumerate(text.splitlines(), 1):
        t = " ".join(re.sub(r"[*_`|]", " ", raw).split())
        if not t:
            blank = True
            continue
        if blank:
            para, blank = para + 1, False
        m = FIGURE.match(t)
        if m and not re.search(r"\d", m.group(1)):
            v = m.group(2).lstrip("+")
            out.append({"label": m.group(1).strip(), "value": v, "amount": re.sub(r"[^\d.-]", "", v), "currency": CCY.search(v).group(),
                        "where": f"paragraph {para}", "para": para, "line": k, "quote": t})
    return out


def fund_named(plane, name: str, data: bytes) -> list[str]:
    """The fund an email or note names near its top (subject, heading): an APPROVED name of the manager statements source whose cleaned form is
    in the first lines, when exactly one fund has such a name. 2.0's matcher then matches the document (no proposal is made for a heading)."""
    from sh_platform.v1 import e2_intake as E, e2_match as M, wh
    from sh_platform.v1.e1_write import org_id
    from sh_platform.v1.doc_index import read_lines
    try:
        head = f" {M.normalise(' '.join(read_lines(name, data)[0][:15]))} "
        with wh.connect(plane) as con:
            sid = E._source(con, org_id(plane), "manager_email")
            rows = con.execute("select instrument_id, identifier_value from instrument_identifiers where source_system_id = ? and mapping_status = 'approved'",
                               [sid]).fetchall()
    except Exception:  # noqa: BLE001 - no match is a help only; the document is registered either way
        log.warning("the fund an email names could not be looked up", exc_info=True)
        return []
    hits = {}
    for iid, v in rows:
        if M.normalise(v) and f" {M.normalise(v)} " in head:
            hits.setdefault(str(iid), []).append(v)
    return [max(hits.popitem()[1], key=len)] if len(hits) == 1 else []


def _doc_row(plane, did: str) -> dict:
    from sh_platform.v1 import e2_intake as E, e2_screen as S
    d = E.detail(plane, did)
    return {"fund": S._instrument_names(plane).get(d["instrument_id"] or "") or "", "date": str(d["valuation_date"] or "")[:10]}


def _pending_field(plane, did: str, f: dict) -> str:
    """One pending 2.0 extracted field (nav) for the quoted line: it waits in the Evidence review queue until a person confirms it."""
    from decimal import Decimal
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    fid = wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_text, value_numeric, currency, page_number,"
                    " line_number, confidence, extracted_by_agent_run_id, review_status, reviewed_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [fid, org_id(plane), did, "nav", f["amount"], Decimal(f["amount"]), f["currency"], f["para"], f["line"], "medium", None, "pending", None])
    return fid


def _take(x, names: list[str]) -> dict:
    """Register and read the named documents; returns the thread's docs state."""
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1 import wh
    st = x.th.setdefault("docs", {})
    with H._skill(x, SKILL, "Reading the emails and notes as documents"):
        for n in names:
            data = H.blob(x.plane, n)
            try:
                figs = figures_of(n, data)
            except Exception:  # noqa: BLE001 - a document that cannot be read is still kept as context
                figs = []
            did = x.api("leo", "POST", "/api/v1/evidence/documents", {"filename": n, "data": base64.b64encode(data).decode(), "fund_names": fund_named(x.plane, n, data)}, soft=True).get("id")
            x.th.setdefault("intake", {})[n] = f"doc:{did or ''}"
            rec = st[n] = {"doc_id": did, "status": "context", "figures": []}
            if not (did and figs):
                continue
            with wh.connect(x.plane, read_only=True) as con:  # read once: a second intake of the same file reuses its fields
                have = con.execute("select count(*) from extracted_fields where document_id = ?", [did]).fetchone()[0]
            if have:
                continue
            rec.update(status="asked", figures=figs, **_doc_row(x.plane, did))
    return st


def intake(x) -> None:
    """a_intake: every email or note of the thread goes to the document intake, never to table intake."""
    from sh_platform.v1 import v3_harbor as H
    x.th["docs"] = {}
    names = [f["name"] for f in H.my_files(x, "source") if is_doc(f["name"])]
    if names:
        _take(x, names)


def _opt(f: dict) -> str:
    return f'"{f["quote"]}" ({f["where"]})'


def offer(x, name: str, did: str | None, pairs: list[dict]) -> None:
    """v3_pdf: a letter (not a statement) is context; each "Label: CCY amount" line it states is offered for confirmation like an email's."""
    from sh_platform.v1 import v3_pdf as V
    figs = [{"label": p["label"], "value": p["value"], "amount": re.sub(r"[^\d.-]", "", p["value"]), "currency": p["value"][:3],
             "where": f"page {p['page']}", "para": p["page"], "line": p["line"], "quote": p["quote"].replace(chr(10), " ")}
            for p in pairs if V.CCY_AMOUNT.match(p["value"])]
    rec = x.th.setdefault("docs", {})[name] = {"doc_id": did, "status": "context", "figures": [], "pdf": True}
    if did and figs:
        rec.update(status="asked", figures=figs, **_doc_row(x.plane, did))


def questions(x) -> list[dict]:
    """d2: one question per document that states a figure, each option the quoted line and its paragraph."""
    from sh_platform.v1.e2_intake import REVISED_WORDS
    out = []
    for n, d in (x.th.get("docs") or {}).items():
        if d["status"] != "asked":
            continue
        of = f" for {d['fund']}" + (f" at {d['date']}" if d.get("date") else "") if d.get("fund") else ""
        opts = [_opt(f) for f in d["figures"]]
        hit = next((o for o, f in zip(opts, d["figures"]) if REVISED_WORDS.search(f["label"])), None)  # a revision notice: its amended line
        out.append({"id": f"doc:{n}", "text": f"{n} states a value{of}. A document is context until you confirm a line. Which line is the value to load?",
                    "options": [*opts, CONTEXT], "assumed": hit or CONTEXT})
    return out


def answer(x, name: str, val: str) -> str:
    d = (x.th.get("docs") or {}).get(name)
    if not d or d["status"] != "asked":
        return ""
    pick = next((f for f in d["figures"] if val == _opt(f)), None)
    d["status"], d["pick"] = ("confirmed", pick) if pick else ("kept", None)
    return f"{name}: " + (f"confirmed {pick['quote']}" if pick else "kept as context")


def _settle(x, n: str, d: dict) -> dict | None:
    """The picked line becomes a 2.0 extracted field, confirmed through e2_extract (the valuation and its supersession). A problem is named."""
    if not d.get("pick"):
        d["status"] = "context"
        return None
    try:
        fid = d["pick"].get("field_id") or _pending_field(x.plane, d["doc_id"], d["pick"])
        d["pick"]["field_id"] = fid  # a retry confirms the same field
        got = x.api("anita", "POST", f"/api/v1/evidence/fields/{fid}/confirm", {})
        d["status"], d["valuation_id"] = "loaded", got.get("valuation_id")  # a retry of the load does not confirm it twice
        return None
    except Exception as e:  # noqa: BLE001 - the field waits in the Evidence review queue; the person is told why
        d["status"] = "aside"
        return {"file": n, "title": f"{n} needs a look", "text": f"The line you confirmed did not load: {getattr(e, 'text', e)} It waits in Evidence."[:240]}


def load(x) -> tuple[int, list[dict]]:
    """b_load: (documents whose confirmed figure loaded, set-aside problems). Context documents are taken in, not set aside."""
    from sh_platform.v1 import v3_harbor as H
    n, aside = 0, []
    for name, d in (x.th.get("docs") or {}).items():
        if d["status"] in ("confirmed", "kept"):
            p = _settle(x, name, d)
            if p:
                aside.append(p)
                H.set_status(x.plane, name, "question")
                continue
            n += d["status"] == "loaded"
        H.set_status(x.plane, name, "loaded")
    return n, aside


def monthly(x, names: list[str]) -> list[dict]:
    """m_load: no question is asked on a live thread; a stated figure waits in the Evidence review queue and is named as an exception."""
    st, aside = _take(x, names), []
    from sh_platform.v1 import v3_harbor as H
    for n in names:
        d = st.get(n) or {}
        H.set_status(x.plane, n, "loaded")
        if d.get("status") == "asked":
            from sh_platform.v1.e2_intake import REVISED_WORDS
            one = d["figures"] if len(d["figures"]) == 1 else [f for f in d["figures"] if REVISED_WORDS.search(f["label"])][:1]
            for f in one:  # the line to confirm waits in the Evidence review queue (2.0 keeps one value field per document)
                f["field_id"] = _pending_field(x.plane, d["doc_id"], f)
            lines = "; ".join(_opt(f) for f in d["figures"])[:200]
            aside.append({"file": n, "title": f"{n} needs a look", "text": f"It states {lines}. " + ("Confirm the line in Evidence to load it; until then it is context." if one
                                                                    else "A person should say which line, if any, to load; until then it is context.")})
    return aside


def d2_files(x) -> list[dict]:
    rows = []
    for n, d in (x.th.get("docs") or {}).items():
        if d.get("pdf"):
            continue  # a letter: v3_pdf.d2_files lists it
        asked = d["status"] == "asked"
        rows.append({"name": n, "read_as": "a document stating a value" if asked else "read as context",
                     "goes_to": "valuations, once you confirm the line" if asked else "kept as a document Lumen and Knowledge can cite",
                     "state": "new", "confidence": "medium" if asked else "high"})
    return rows
