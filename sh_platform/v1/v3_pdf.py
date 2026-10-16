"""Harbor 3.0: PDFs go down the 2.0 document path, spreadsheets keep today's path (skill data.read-pdf-fields).

A PDF (manager statement, notice, confirmation) is
  1. registered as a document (e2_intake: hash, fund match, revisions), read into text on this machine (reader, ocr_local for pictures);
  2. read by LAYOUT: lines that hold a label and its value ("Label: value", or the label on one line and the value on the next) become
     pairs, each with its page and the quoted lines. A layout is the first heading plus the kind of document;
  3. a NEW layout costs one question in Decision 2 ("which line holds the amount?", the fields it read as one-click options). The answer
     is remembered per office (v3/pdf_layouts.json) and kept as an x5_extract type (fields, checks, review queue), so the next file of that
     layout loads without asking;
  4. each file's values go to rows the build can use: one row per document in a CSV (value, page and quote per field) that takes the
     normal intake and mapping path. A value that fails the layout's checks is never loaded: it goes to the x5 review queue and the Desk.
Harbor confirms a value on the person's behalf only when it is quoted from the page and passes the layout's checks; otherwise a person is asked.
The 2.0 reader e2_extract is NOT run on these files: it reads "units" from prose such as "set out on page 2" and confirms it.
State: thread["pdf"] = {files: {name: {doc_id, sig, status}}, ask: {slug: {...}}}; memory: <company>/v3/pdf_layouts.json."""
import csv
import hashlib
import io
import json
import logging
import re
import threading

log = logging.getLogger(__name__)
SKILL = "data.read-pdf-fields"
LEAVE = "Leave these PDFs out"
LOCK = threading.RLock()
COLON = re.compile(r"^([A-Za-z][A-Za-z ()/'&.-]{1,48}?)\s*:\s*(\S.{0,160})$")
CCY_AMOUNT = re.compile(r"^[A-Z]{3}\s*[-+]?\d")
MAX_FIELDS = 14
MANAGER = "manager_email"
FUND_LABEL = re.compile(r"^(fund|fund name|name of fund|partnership)$", re.I)
DATE_LABEL = re.compile(r"period|valuation|as (at|of)|nav date|statement date", re.I)
REF_LABEL = re.compile(r"\bref(erence)?\b", re.I)  # a trade reference is text; it is a field only on an FX confirmation
LETTER = re.compile(r"\b(news)?letter\b", re.I)  # the kind of document named in its layout (x5_extract's type words)


def is_pdf(name: str) -> bool:
    return str(name).lower().endswith(".pdf")


def _norm(s) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split())


# ---- reading the page --------------------------------------------------------------------------------------------------------------

def pages_of(name: str, data: bytes) -> list[tuple[int, list[tuple[int, str]]]]:
    """[(page, [(line number, text)])], read on this machine."""
    from sh_platform.context_docs import reader
    out = []
    for loc, text in reader.read_segments(name, data):
        m = re.search(r"(\d+)", loc or "")
        lines = [(k, re.sub(r"[*_`]", "", ln).strip()) for k, ln in enumerate(text.splitlines(), 1)]
        out.append((int(m.group(1)) if m else len(out) + 1, [(k, t) for k, t in lines if t]))
    return out


def is_picture(data: bytes) -> bool:
    """True when the PDF has no text layer: the lines came from the local picture reader (ocr_local), so a value read from them is a guess."""
    try:
        import fitz
        with fitz.open(stream=data, filetype="pdf") as doc:
            return not any(pg.get_text().strip() for pg in doc)
    except Exception:  # noqa: BLE001 - no PyMuPDF: the text layer cannot be checked, the checks still apply
        return False


def _short(t: str) -> bool:
    return len(t.split()) <= 8 and len(t) <= 70 and "|" not in t and ":" not in t and not (t.endswith(".") and len(t.split()) > 4)


def _block(run: list[tuple[int, str]]) -> list[tuple[tuple, tuple]]:
    """A run of short lines alternates label, value. The start parity that gives labels without digits and values with digits wins;
    a run with fewer than two numbers is prose, not a table. A table of three columns (line, value, status) does not alternate: there each
    amount takes the line above it, and that reading wins only when it scores higher."""
    best, top = [], 1
    amount = re.compile(r"^(?:[A-Z]{3}\s*)?[-+]?\d[\d,]*(?:\.\d+)?$")
    by_amount = [(run[i - 1], run[i]) for i in range(1, len(run)) if amount.match(run[i][1]) and re.search(r"[A-Za-z]", run[i - 1][1])]
    for ps in [[(run[i], run[i + 1]) for i in range(start, len(run) - 1, 2)] for start in (1, 0)] + [by_amount]:
        score = sum(bool(re.search(r"\d", v[1])) for _, v in ps) - 2 * sum(bool(re.search(r"\d", lb[1])) for lb, _ in ps)
        if score > top:
            best, top = ps, score
    return best


def pairs_of(pages) -> list[dict]:
    """[{label, value, page, line, quote}] in page order: colon pairs (several to a line when separated by 2+ spaces) and table blocks."""
    out = []
    for page, lines in pages:
        run = []

        def flush():
            for lb, v in _block(run):
                out.append({"label": lb[1], "value": v[1], "page": page, "line": lb[0], "quote": f"{lb[1]}\n{v[1]}"})
            run.clear()
        for k, t in lines:
            segs = [m for m in (COLON.match(s) for s in re.split(r"\s{2,}", t)) if m]
            if segs:
                flush()
                for m in segs:
                    if not re.search(r"\d", m.group(1)):
                        out.append({"label": m.group(1).strip(), "value": m.group(2).strip(), "page": page, "line": k, "quote": t, "colon": True})
            elif _short(t):
                run.append((k, t))
            else:
                flush()
        flush()
    return out


def layout_of(pages) -> tuple[str, str]:
    """(signature, plain name): the first line and the line that says what kind of document it is."""
    from sh_platform.v1 import x5_extract as X5
    lines = [t for _, ls in pages[:1] for _, t in ls]
    head = next((t for t in lines if not re.search(r"\d", t)), "Document")
    kind = next((t for t in lines if X5._TYPE_WORDS.search(t) and len(t.split()) <= 8 and not re.search(r"\d|:", t)), "")
    name = " - ".join(x.strip() for x in dict.fromkeys([head, kind]) if x.strip())[:80]
    return _norm(name), name


def slug_of(sig: str) -> str:
    return (re.sub(r"\W+", "_", sig)[:30].strip("_") or "layout") + "_" + hashlib.sha1(sig.encode()).hexdigest()[:6]


# ---- the proposal and the memory ---------------------------------------------------------------------------------------------------

def _fmt(value: str) -> str:
    """x5's format of a value, except that a reference such as HB2026001 or FXF-2026-001 is text, not a number or a date."""
    from sh_platform.v1 import x5_extract as X5
    return "text" if re.fullmatch(r"[A-Za-z]+[-_]?[\w-]*\d[\w-]*", value.strip()) else X5._fmt_of(value)


def _is_fx(pairs: list[dict]) -> bool:
    """An FX confirmation: a trade date, a value date, and a line for what the client sells and a line for what it buys."""
    labels = [p["label"].lower() for p in pairs]
    return all(any(re.search(w, lb) for lb in labels) for w in (r"^trade date", r"^value date", r"\bsells?\b", r"\bbuys?\b"))


def propose(pairs: list[dict]) -> list[dict]:
    """Fields of a layout from the first file: every pair of a table block, and colon pairs that hold a date or a number.
    On an FX confirmation the colon pairs that hold a reference are fields too (the trade reference is what the desk's trade is matched on)."""
    from sh_platform.v1 import x5_extract as X5
    fields, seen, fx = [], set(), _is_fx(pairs)
    for p in pairs:
        fmt = _fmt(p["value"])
        label = re.sub(r"\s+", " ", p["label"]).strip()
        ref = fx and p.get("colon") and REF_LABEL.search(label) and len(p["value"]) <= 40
        if _norm(label) in seen or len(fields) >= MAX_FIELDS or (p.get("colon") and not ref and (fmt == "text" or len(p["value"]) > 40)) or not X5.parse(fmt, p["value"]):
            continue
        seen.add(_norm(label))
        fields.append({"name": label.lower(), "meaning": "", "format": fmt, "where_usually": label, "required": fmt == "date" and not p.get("colon")})
    return fields


def candidates(pairs: list[dict], fields: list[dict]) -> list[dict]:
    """The lines that could hold the amount, in page order: a number written with a currency code."""
    names = {f["name"] for f in fields if f["format"] == "number"}
    return [p for p in pairs if p["label"].lower() in names and CCY_AMOUNT.match(p["value"])]


def _mem_path(plane):
    return plane.path("v3", "pdf_layouts.json")


def memory(plane) -> dict:
    p = _mem_path(plane)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _remember(plane, sig: str, entry: dict) -> None:
    with LOCK:
        m = memory(plane)
        m[sig] = entry
        _mem_path(plane).write_text(json.dumps(m, indent=1), encoding="utf-8")


def _has_key(layout: dict, pairs: list[dict]) -> bool:
    key = next((f for f in layout["fields"] if f["name"] == layout["key"]), None)
    from sh_platform.v1 import x5_extract as X5
    have = {_norm(p["label"]) for p in pairs}
    return bool(key) and any(_norm(lb) in have for lb in X5._labels(key))


def read_values(plane, layout: dict, pairs: list[dict]) -> tuple[dict, list[dict], str]:
    """(values, checks, status): each value from the line whose label is the field's label; page and quote kept; the layout's checks run."""
    from sh_platform.v1 import x5_extract as X5
    values = {}
    for f in layout["fields"]:
        labels = {_norm(lb) for lb in X5._labels(f)}
        hit = next((p for p in pairs if _norm(p["label"]) in labels), None)
        if not hit:
            values[f["name"]] = {"value": "", "raw": "", "line": None, "page": None, "quote": "", "by": "rules"}
            continue
        fmt = f.get("format") or "text"
        values[f["name"]] = {"value": " ".join(hit["value"].split()) if fmt == "text" else X5.parse(fmt, hit["value"]), "raw": hit["value"], "line": hit["line"], "page": hit["page"], "quote": hit["quote"], "by": "rules"}
    checks = X5.run_checks(plane, {"fields": layout["fields"], "checks": layout.get("checks") or []}, values)
    for n, v in values.items():  # a value is only taken from the page: what is kept must be in the quote
        if v["raw"] and v["raw"] not in v["quote"]:
            checks.append({"kind": "quoted", "field": n, "detail": "", "ok": False, "why": "the value is not in the quoted lines"})
    return values, checks, "ok" if all(c["ok"] for c in checks) else "review"


# ---- chain A: read the files, find the layouts ------------------------------------------------------------------------------------

def _prematch(x, pairs: list[dict]) -> list[str]:
    """The fund name quoted on the page, if it is the cleaned name of exactly one instrument (2.0's own rule: e2_match), is approved for the
    manager statements source before the document is registered, so the document matches its fund. Spelling-only (near) matches are not
    approved: they stay proposed for a person."""
    from sh_platform.v1 import e2_intake as E, e2_match as M, wh
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1.e1_write import org_id
    quoted = next((p["value"] for p in pairs if FUND_LABEL.match(p["label"])), "")
    name = E._PREFIX.sub("", quoted).strip()
    if not name:
        return []
    try:
        with wh.connect(x.plane) as con:
            sid = E._source(con, org_id(x.plane), MANAGER)
        got = M.resolve(x.plane, name, sid)
        if got.get("status") != "proposed" or not got.get("identifier_id"):
            return [name]
        mine = next((p for p in M.proposals(x.plane) if str(p["id"]) == str(got["identifier_id"])), None)
        if mine and mine.get("instrument_name") and M.normalise(mine["name_in_file"]) == M.normalise(mine["instrument_name"]):
            with H._skill(x, "data.match-identity", "Matching the fund name quoted on the page"):
                x.api("leo", "POST", f"/api/v1/evidence/aliases/{got['identifier_id']}/approve", {}, soft=True)
    except Exception:  # noqa: BLE001 - the match is a help; the document is registered either way
        log.warning("the fund name could not be pre-matched", exc_info=True)
    return [name]


def _register(x, name: str, data: bytes, pairs: list[dict]) -> str | None:
    """The 2.0 document intake: hash, fund match, which statement replaces which. A failure never stops the reading. The source stays the
    office's own default (the manager statements source): its approved fund names are what match a statement to a fund."""
    import base64
    names = _prematch(x, pairs)  # the fund name read from the page goes to the 2.0 matcher first
    try:
        return x.api("leo", "POST", "/api/v1/evidence/documents", {"filename": name, "data": base64.b64encode(data).decode(), "fund_names": names}).get("id")
    except Exception:  # noqa: BLE001
        log.warning("a PDF could not be registered as a document", exc_info=True)
        return None


def intake(x) -> None:
    """a_intake: read every PDF of the thread. Known layouts are read at once; each new layout becomes one question for Decision 2."""
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1 import v3_loads as L
    pdfs = [f for f in H.my_files(x, "source") if is_pdf(f["name"])]
    st = x.th["pdf"] = {"files": {}, "ask": {}}
    if not pdfs:
        return
    mem = memory(x.plane)
    with H._skill(x, SKILL, "Reading the PDFs and the lines that hold each value"):
        for f in pdfs:
            data = H.blob(x.plane, f["name"])
            try:
                pages = pages_of(f["name"], data)
            except Exception:  # noqa: BLE001 - a PDF that cannot be read is named to the person at load
                pages = []
            pairs = pairs_of(pages)
            doc_id = _register(x, f["name"], data, pairs)
            x.th["intake"][f["name"]] = f"pdf:{doc_id or ''}"
            sig, name = layout_of(pages) if pages else ("", "")
            rec = st["files"][f["name"]] = {"doc_id": doc_id, "sig": sig, "status": "read" if pairs else "context" if pages else "unreadable"}
            if not pairs:
                continue  # text with no label and value (a letter in prose) is context: Lumen and Knowledge cite it
            if LETTER.search(name):  # a letter is not a statement: context, and a figure it states is offered for confirmation, not a layout
                rec["status"] = "context"
                from sh_platform.v1 import v3_docs as D
                D.offer(x, f["name"], doc_id, pairs)
                continue
            known = mem.get(sig)
            if known and _has_key(known, pairs):
                continue
            slug = slug_of(sig)
            ask = st["ask"].get(slug)
            if ask is None:
                fresh = propose(pairs)
                fields = (known or {}).get("fields") or fresh
                cands = candidates(pairs, fresh)
                if not cands:  # no amount with a currency code: a report of labelled figures (v3_loads keeps them), else nothing to read
                    rec["status"] = "figures" if any(L._num(p["value"]) is not None for p in pairs) else "context"
                    continue
                ask = st["ask"][slug] = {"sig": sig, "name": name, "fields": fields, "files": [], "changed": bool(known),
                                         "cands": [{k: c[k] for k in ("label", "value", "page")} for c in cands],
                                         "read": [{k: p[k] for k in ("label", "value", "page")} for p in pairs if p["label"].lower() in {g["name"] for g in fresh}][:8]}
            ask["files"].append(f["name"])
            rec["status"], rec["ask"] = "asked", slug


def questions(x) -> list[dict]:
    """d2: one plain question per new layout, the fields it read as one-click options."""
    from sh_platform.v1 import v3_expected as EX
    out = EX.questions(x)  # "How often does <fund> send statements?" for a fund nothing on file can tell
    for slug, a in ((x.th.get("pdf") or {}).get("ask") or {}).items():
        if a.get("done"):
            continue
        saw = "; ".join(f"{r['label']}: {r['value']}" for r in a["read"])
        opts = [f"{c['label']}: {c['value']}" for c in a["cands"]]
        why = (f"The layout of {a['name']} looks different now: the line I used before is not there." if a["changed"]
               else f"I have not seen the layout of {a['name']} before ({len(a['files'])} file{'s' if len(a['files']) != 1 else ''}, for example {a['files'][0]}).")
        out.append({"id": f"pdf:{slug}", "text": f"{why} In the first one I read: {saw}. Which line holds the amount to load? Every file with this layout will be read the same way.",
                    "options": [*opts, LEAVE], "assumed": opts[0]})
    return out


def _goes_to(fields: list[dict]) -> str:
    lay = {"fields": fields}
    return "FX confirmations" if _fx_roles(lay) else "valuations" if _roles(lay, "?") else "kept with page and quote"


def d2_files(x) -> list[dict]:
    mem, rows = memory(x.plane), []
    for n, f in ((x.th.get("pdf") or {}).get("files") or {}).items():
        if f["status"] == "figures":
            continue  # v3_loads.d2_files lists it
        if f["status"] == "context":
            rows.append({"name": n, "read_as": "read as context", "goes_to": "kept as a document Lumen and Knowledge can cite", "state": "new", "confidence": "high"})
            continue
        if f["status"] == "unreadable":
            rows.append({"name": n, "read_as": "not recognised", "goes_to": "nowhere yet", "state": "new", "confidence": "low"})
        else:
            lay = mem.get(f["sig"]) or {}
            rows.append({"name": n, "read_as": (lay.get("name") or ((x.th["pdf"]["ask"].get(f.get("ask") or "") or {}).get("name")) or "a PDF layout"),
                         "goes_to": _goes_to(lay.get("fields") or (x.th["pdf"]["ask"].get(f.get("ask") or "") or {}).get("fields") or []),
                         "state": "reused" if f["status"] == "read" else "new", "confidence": "high" if f["status"] == "read" else "medium"})
    return rows


def answer(x, slug: str, val: str) -> str:
    """b_answers: the person's pick for a new layout is remembered; a pick made a second time for the same layout becomes an office skill."""
    from sh_platform.v1 import v3_harbor as H
    if slug.startswith("freq-"):
        from sh_platform.v1 import v3_expected as EX
        return EX.answer(x, slug[5:], val)
    st = x.th.get("pdf") or {}
    a = (st.get("ask") or {}).get(slug)
    if not a or a.get("done"):
        return ""
    a["done"] = True
    if val == LEAVE or not any(val == f"{c['label']}: {c['value']}" for c in a["cands"]):
        for n in a["files"]:
            st["files"][n]["status"] = "left_out"
        return f"{a['name']}: left out"
    label = next(c["label"] for c in a["cands"] if val == f"{c['label']}: {c['value']}")
    old = memory(x.plane).get(a["sig"]) or {}
    key = old.get("key") or label.lower()  # a changed layout keeps its amount field and learns the new label
    fields = old.get("fields") or a["fields"]
    for f in fields:  # a changed layout keeps the old label and adds the new one (x5_extract's revised spec)
        if f["name"] == key:
            f["required"] = True
            if _norm(label) not in {_norm(lb) for lb in f["where_usually"].split("|")}:
                f["where_usually"] = f"{f['where_usually']} | {label}"
    who = x.th.get("started_by") or "the person"
    _remember(x.plane, a["sig"], {"name": a["name"], "fields": fields, "checks": [], "key": key, "by": who, "at": H.now(),
                                  "marks": int(old.get("marks") or 0) + 1})
    for n in a["files"]:
        st["files"][n]["status"] = "read"
    H._learn(x.plane, x.th, f"pdf:{a['name']}", f"{a['name']}: the person marked the amount under {label}")
    return f"{a['name']}: amount under {label}"


# ---- chain B / M: load ------------------------------------------------------------------------------------------------------------

def _spec_type(x, layout: dict) -> dict | None:
    """The layout as an x5_extract type of this intent (fields, checks, review queue, revisions)."""
    from sh_platform.v1 import x5_extract as X5
    try:
        t = X5.upsert(x.plane, x.th["iid"], {"name": layout["name"], "fields": layout["fields"], "checks": layout.get("checks") or [], "files": []}, state="confirmed")
        return t
    except Exception:  # noqa: BLE001 - the review queue is a help; the rows still load
        log.warning("the PDF layout could not be stored as an extraction type", exc_info=True)
        return None


def _cell(v: dict) -> str:
    """The value as read; "n/a" and its kind are no value, so the cell stays empty rather than hold words in a number column."""
    return "" if re.match(r"(?i)^(n/?a|none|nil|-+)(\W|$)", v["value"].strip()) else v["value"]


def _roles(layout: dict, key: str | None = None) -> dict:
    """The columns 2.0's valuation sheets use (fund, valuation date, value), when the layout holds them: the fund line, the date line named
    period end / valuation date / as at, and the amount the person marked."""
    fund = next((f["name"] for f in layout["fields"] if FUND_LABEL.match(f["name"])), None)
    day = next((f["name"] for f in layout["fields"] if f["format"] == "date" and DATE_LABEL.search(f["name"])), None)
    return {"fund": fund, "valuation date": day, "value": key or layout["key"]} if fund and day else {}


def _csv(layout: dict, rows: list[dict]) -> tuple[str, str]:
    """(csv text, file name): one row per document. A layout with a fund, a date and an amount leads with 2.0's valuation columns (fund,
    valuation date, value, currency), each with its page and quote, so the normal mapper reads it as valuations. Every other field goes,
    with its page and quote, into one `pdf reading` cell: a column of its own would be matched to a model field by its name (status)."""
    roles = _roles(layout)
    rest = [f for f in layout["fields"] if f["name"] not in roles.values() and not (roles and f["name"] == "currency")]
    cols = ["file", "layout", *roles, "currency", *[f"{r} {w}" for r in roles for w in ("page", "quote")], "pdf reading"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        v = r["values"]
        row = [r["file"], layout["name"], *[_cell(v[n]) for n in roles.values()]]
        row.append((re.match(r"[A-Z]{3}", v[layout["key"]]["raw"]) or [""])[0])
        row += [c for n in roles.values() for c in (v[n].get("page") or "", v[n].get("quote", "").replace(chr(10), " / "))]
        row.append(json.dumps({f["name"]: {"value": _cell(v[f["name"]]), "page": v[f["name"]].get("page"), "quote": v[f["name"]].get("quote", "").replace(chr(10), " / ")}
                               for f in rest}, ensure_ascii=False))
        w.writerow(row)
    return buf.getvalue(), f"{slug_of(layout['name'].lower())}_{'valuation_' if roles else ''}rows.csv"


def _fx_roles(layout: dict) -> dict | None:
    """The fields of an FX confirmation layout (trade reference, dates, the two legs, rate, counterparty), or None when it is not one."""
    names = [f["name"] for f in layout["fields"]]

    def pick(*pats):
        return next((n for pat in pats for n in names if re.search(pat, n)), None)
    r = {"ref": pick(r"\b(our|client|trade|deal|your) ref", r"\bref(erence)?\b"), "trade": pick(r"^trade date", r"^deal date"),
         "value": pick(r"^value date", r"^settlement date", r"maturity"), "sold": pick(r"\bsells?\b"), "bought": pick(r"\bbuys?\b"),
         "rate": pick(r"\brate\b"), "cp": pick(r"^counterparty")}
    return r if all(r[k] for k in ("ref", "trade", "sold", "bought")) else None


def _leg(v: dict, name: str) -> tuple[str, str]:
    """(currency, amount) of a leg: the code written before the amount, else the code in the line's label, e.g. 'Client sells (USD)'."""
    m = re.match(r"([A-Z]{3})\b", v["raw"]) or re.search(r"\(([A-Za-z]{3})\)", name)
    return (m.group(1).upper() if m else ""), _cell(v)


def _fx_csv(layout: dict, fx: dict, rows: list[dict], docs: dict) -> tuple[str, str]:
    """One row per confirmation, both legs, the document id and the page of the reference; every value with its page and quote in `pdf reading`."""
    cols = ["file", "layout", "trade reference", "trade date", "value date", "currency bought", "amount bought", "currency sold", "amount sold", "rate",
            "counterparty", "source document", "source page", "pdf reading"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        v = r["values"]
        cb, ab = _leg(v[fx["bought"]], fx["bought"])
        cs, a_s = _leg(v[fx["sold"]], fx["sold"])
        get = lambda k: _cell(v[fx[k]]) if fx.get(k) else ""  # noqa: E731
        w.writerow([r["file"], layout["name"], get("ref"), get("trade"), get("value"), cb, ab, cs, a_s, get("rate"), get("cp"), docs.get(r["file"]) or "",
                    v[fx["ref"]].get("page") or "",
                    json.dumps({f["name"]: {"value": _cell(v[f["name"]]), "page": v[f["name"]].get("page"), "quote": v[f["name"]].get("quote", "").replace(chr(10), " / ")}
                                for f in layout["fields"]}, ensure_ascii=False)])
    return buf.getvalue(), f"{slug_of(layout['name'].lower())}_fx_rows.csv"


def _into_rows(x, name: str, text: str) -> None:
    """The rows file takes the normal intake path: upload, the mapping Harbor proposes is approved as in chain B, load."""
    r = x.api("leo", "POST", "/api/v1/intake/upload", files={"file": (name, text.encode("utf-8"))}, data={"source_code": MANAGER})  # the source whose approved fund names match these rows
    fid = r.get("file_id")
    base = f"/api/v1/intake/files/{fid}/load"
    out = x.api("leo", "POST", base, {}, soft=True)
    for m in x.api("leo", "GET", "/api/v1/model/mappings?state=proposed", soft=True) or []:
        d = x.api("leo", "GET", f"/api/v1/model/mappings/{m['id']}", soft=True)
        if d.get("example_file") == name:
            x.api("anita", "POST", f"/api/v1/model/mappings/{m['id']}/approve", {"note": "Approved by the head of data: rows read from PDFs."}, soft=True)
    out = x.api("leo", "POST", base, {}) or out
    if isinstance(out, dict) and out.get("state") in ("failed", "blocked", "refused", "quarantined", "nothing_loaded"):
        raise ValueError((out.get("load_result") or {}).get("message") or out.get("note") or out.get("state"))


def _accepted(plane, doc: str) -> dict | None:
    from sh_platform.v1 import x5_extract as X5
    try:
        rec = X5.read_extraction(plane, doc)
    except Exception:  # noqa: BLE001 - not read before
        return None
    return rec if rec.get("accepted_by") and rec.get("status") == "ok" else None


def load_files(x, names: list[str], monthly: bool = False) -> tuple[int, list[dict]]:
    """Read the named PDFs under their remembered layouts and load their rows. (loaded, set-aside problems). Never invents: a file whose
    layout is not remembered, whose value fails a check, or that cannot be read is set aside and named."""
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1 import x5_extract as X5
    st = x.th.setdefault("pdf", {"files": {}, "ask": {}})
    mem, aside, by_layout, done, valued = memory(x.plane), [], {}, [], set()
    who = x.th.get("started_by") or "the person"
    with H._skill(x, SKILL, "Taking the values from the PDFs, each with its page and quote"):
        for n in names:
            f = st["files"].setdefault(n, {"doc_id": None, "sig": "", "status": "read"})
            if f["status"] == "left_out":
                continue
            try:
                data = H.blob(x.plane, n)
                pages = pages_of(n, data)
                pairs = pairs_of(pages)
                if monthly and not f.get("doc_id"):
                    f["doc_id"] = _register(x, n, data, pairs)
            except Exception:  # noqa: BLE001
                pairs, pages = [], []
            if not pages:
                aside.append({"file": n, "title": f"{n} did not load", "text": "I could not read lines with a label and a value from this PDF. A person should read it."})
                continue
            sig, lname = layout_of(pages)
            lay = mem.get(sig)
            if not lay and (LETTER.search(lname) or not candidates(pairs, propose(pairs))):  # a letter, or no amount line: context, not a layout
                f["status"] = "context"
                H.set_status(x.plane, n, "loaded")
                continue
            if not lay or not _has_key(lay, pairs):
                aside.append({"file": n, "title": f"{n} did not load", "text": "I have not seen this layout before. Open the thread and tell me which line holds the amount."})
                continue
            t = _spec_type(x, lay)
            doc = X5._doc_id(f"documents/{n}")
            prior = _accepted(x.plane, doc)
            if prior:  # a person looked at it in the review queue and accepted it: their values are the ones that load
                values, checks, status = prior["values"], prior["checks"], "ok"
            else:
                values, checks, status = read_values(x.plane, lay, pairs)
                if status == "ok" and is_picture(data):
                    checks.append({"kind": "quoted", "field": lay["key"], "detail": "", "ok": False, "why": "it was read from a picture, so a person confirms it"})
                    status = "review"
            rec = {"doc_id": doc, "file": f"documents/{n}", "intent_id": x.th.get("iid"), "type": (t or {}).get("id"), "type_name": lay["name"],
                   "version": (t or {}).get("version", 1), "values": values, "checks": checks, "status": status,
                   "failed_first": [f"{c['field']}:{c['kind']}" for c in checks if not c["ok"]], "at": H.now()}
            if status == "ok":  # quoted from the page and every check passes: Harbor confirms for the signer, and says so
                rec.update(confirmed_by=f"Harbor, for {who}", confirmed_why="each value is quoted from the page and passes the layout's checks")
            if t:
                from sh_platform.jsonfile import write_json_atomic
                p = X5._rec_path(x.plane, doc)
                p.parent.mkdir(parents=True, exist_ok=True)
                write_json_atomic(p, rec)
            if status != "ok":
                bad = "; ".join(f"{c['field']} {c['why']}" for c in checks if not c["ok"])[:160]
                aside.append({"file": n, "title": f"{n} needs a look", "text": f"I did not load it because {bad}. It waits in the review queue."})
                continue
            by_layout.setdefault(sig, []).append({"file": n, "values": values})
            done.append(n)
        for sig, rows in by_layout.items():
            lay = mem[sig]
            fx = _fx_roles(lay)
            if fx:  # an FX confirmation: one row per confirmation into fx_confirmations
                text, name = _fx_csv(lay, fx, rows, {n: (st["files"].get(n) or {}).get("doc_id") for n in done})
                try:
                    _into_rows(x, name, text)
                except Exception as e:  # noqa: BLE001 - the documents and their values are kept; the person is told the rows did not reach a table
                    aside.append({"file": None, "title": f"Rows from {lay['name']} did not reach a table", "text": str(getattr(e, "text", e))[:200]})
                continue
            if not _roles(lay):  # the model has no table for this kind of document: the values stay in the review records, and the person is told
                aside.append({"file": None, "title": f"{lay['name']}: read, but not in a table", "text": f"{len(rows)} file(s) read, each value with its page and quote. The model has no table for this kind of document yet; ask your data engineer to add one."})
                continue
            valued.update(r["file"] for r in rows)
            text, name = _csv(lay, rows)
            try:
                _into_rows(x, name, text)
            except Exception as e:  # noqa: BLE001 - the documents and their values are kept; the person is told the rows did not reach a table
                aside.append({"file": None, "title": f"Rows from {lay['name']} did not reach a table", "text": str(getattr(e, "text", e))[:200]})
    from sh_platform.v1 import e2_intake as E
    unmatched = {d["original_filename"] for d in E.listing(x.plane) if d["instrument_id"] is None}
    left = [n for n in done if n in unmatched and n in valued]
    if left:
        aside.append({"file": None, "title": f"{len(left)} statement(s) not matched to a fund", "text": "Open Evidence and match the fund names. " + ", ".join(left[:3])})
    for n in done:
        H.set_status(x.plane, n, "loaded")
    for a in aside:
        if a["file"]:
            H.set_status(x.plane, a["file"], "question")
    from sh_platform.v1 import v3_expected as EX
    EX.fill(x)  # every load, monthly ones too: the schedule of expected statements follows what is now in the warehouse
    return len(done), aside


def load(x) -> tuple[int, list[dict]]:
    """b_load: every PDF of the thread that was not left out by the person."""
    st = (x.th.get("pdf") or {}).get("files") or {}
    return load_files(x, [n for n in (x.th.get("intake") or {}) if is_pdf(n) and (st.get(n) or {}).get("status") not in ("left_out", "figures", "context")])  # figures: v3_loads
