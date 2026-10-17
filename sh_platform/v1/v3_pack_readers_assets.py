"""Harbor 3.0, cards 51 to 100: the pack readers of the "assets" kinds (what the office owns and insures, and what the custodian holds for it).

  property_valuations  appraisal PDF           -> documents + fields, one `real_assets` row per appraisal (a newer appraisal of the asset supersedes the older)
  title_deeds          certificate of title    -> document + fields; the registered proprietor becomes `real_assets.title_holder_name`
  insurance_schedule   broker's policy list    -> `vendor_contracts` rows, contract_kind insurance, sum_insured, covered_asset_ref (A37)
  custody_statements   safekeeping statement   -> a document whose `extracted_fields` are custody_quantity / custody_value per holding (value_text the
                                                 security, line_number the holding) and custodian_note per note (A46). NOT position_snapshots: a second
                                                 custodian snapshot of 30 Sep has the key of the daily file's, every total and tie-out picks the newer one
                                                 and moves cards 1 to 50 (tried, view_type 'custody' too).

Planted mess handled: appraisals arrive out of order (the latest by date is the value); the owner of record is a name ("Entity B") the entity table
spells the same way, and a title deed naming someone else (a person) is kept as the title holder and raised as an exception (M29); an appraisal older
than a year is flagged (M28); a policy with no renewal notice inside 60 days and a notice whose premium currency differs from the schedule's are
exceptions; a security name cut off at the PDF column width is matched by its start; lines whose quantity times price does not give the value are flagged.

Registered into Office by `register(module)` at the bottom of v3_pack_readers.py. Imports of the parent are lazy: either module may be imported first.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

KINDS = ("property_valuations", "title_deeds", "insurance_schedule", "custody_statements")
STALE_DAYS = 365       # an appraisal older than this is flagged (card 66's line)
NOTICE_WINDOW = 60     # a renewal inside this many days with no notice on record is an exception (card 52); ponytail: a signed rule when the card is built
NAMES = {
    "property_valuations": ("property valuation", "data.read-property-valuation", "real assets"),
    "title_deeds": ("title deed", "data.read-title-deed", "documents and the title holder of real assets"),
    "insurance_schedule": ("insurance schedule", "data.read-insurance-schedule", "insurance policies (vendor contracts)"),
    "custody_statements": ("custody statement", "data.read-custody-statement", "the custodian's quantities and notes"),
}
PDF_MARKS = [("VALUATION REPORT", "property_valuations"), ("CERTIFICATE OF TITLE", "title_deeds"), ("SCHEDULE OF POLICIES", "insurance_schedule"),
             ("SAFEKEEPING STATEMENT", "custody_statements")]


def register(m) -> None:
    """Hook the four kinds into the parent module `m`: recognition, plain names and skills, and the reader as a second half of the insurance step."""
    m.PDF_KINDS.extend(PDF_MARKS)
    m.KINDS.update(NAMES)
    m.STEP_KINDS["insurance_and_property"] = [*m.STEP_KINDS["insurance_and_property"], *KINDS]
    if "real_assets" not in m.FLUSH_ORDER:
        m.FLUSH_ORDER.append("real_assets")
    first = m.Office.insurance_and_property

    def insurance_and_property(self) -> None:
        first(self)
        assets(self)
    insurance_and_property.__name__ = "insurance_and_property"
    m.Office.insurance_and_property = insurance_and_property


def assets(o) -> None:
    deeds(o)
    valuations(o)
    schedule(o)
    statements(o)


# ---- helpers -----------------------------------------------------------------------------------------------------------------------

def _db(o, sql: str, *a) -> list:
    try:
        return o.con.execute(sql, list(a)).fetchall()
    except Exception:  # noqa: BLE001 - a warehouse without the table has nothing on record
        return []


def _line(t: str, label: str) -> str | None:
    m = re.search(rf"{label}\s*(.+)", t)
    return m[1].strip() if m else None


def _head(o, table: str, key: str, ref: str, where: str = "") -> dict | None:
    """The newest row of the asset or policy: on record already, or staged in this run (None when neither)."""
    cols = ["id", "asset_ref", "appraised_on", "appraised_value", "title_holder_name", "legal_entity_id", "asset_name", "asset_type", "currency", "appraiser"] if table == "real_assets" \
        else ["id", "next_renewal_date", "annual_cost", "sum_insured", "currency"]
    order = "appraised_on" if table == "real_assets" else "next_renewal_date"
    db = _db(o, f"select {', '.join(cols)} from {table} where {key} = ? {where} and id not in (select supersedes_{table[:-1]}_id from {table} where supersedes_{table[:-1]}_id is not null) "
                f"order by {order} desc limit 1", ref)
    staged = [r for r in o.rows.get(table, []) if r.get(key) == ref]
    cand = ([dict(zip(cols, db[0]))] if db else []) + staged
    return max(cand, key=lambda r: r.get(order) or date.min) if cand else None


def _entity(o, owner: str) -> tuple[str | None, str | None]:
    """(entity id, entity name) for the owner of record: by name or by code; (None, None) when the owner is not one of the office's entities."""
    for code, name in o.md["entities"].items():
        if owner.strip().lower() in (name.lower(), code.lower()):
            return o.ent[code], name
    return None, None


def _title(s: str) -> str:
    return re.sub(r"\s*\(SYNTHETIC\)", "", s, flags=re.I).strip().title()


# ---- title deeds, then valuations (a deed read first lets each appraisal carry its title holder) --------------------------------------------

def deeds(o) -> None:
    o.deed_holder = getattr(o, "deed_holder", {})
    for p in o.files("title_deeds"):
        from sh_platform.v1.v3_pack_readers import pdf_text
        t = pdf_text(str(p))
        ref = re.search(r"Property: .+\((RA-\d+)\)", t)[1]
        holder = _line(t, "Registered proprietor:")
        o.deed_holder[ref] = holder
        o.doc(p, "title_deed", p.stem, received=o.arrival(p), fields=[("asset_ref", ref), ("registered_proprietor", holder), ("tenure", _line(t, "Tenure:"))])
        o.note("title_deeds", files=1, rows=1)
        late = _head(o, "real_assets", "asset_ref", ref)  # the appraisal came first and is on record: a new row of it carries the deed's holder
        if late and late.get("title_holder_name") != holder and late["id"] not in {r["id"] for r in o.rows.get("real_assets", [])}:
            _asset_row(o, late, holder=holder, recv=o.arrival(p), doc=next(d["id"] for d in o.rows["documents"] if d["original_filename"] == p.name), status="appraised")
            o.note("title_deeds", flag=f"{ref}: the deed names {holder}, the appraisal on record is carried forward with that title holder")
    o.note("title_deeds", rows=0)


def _asset_row(o, base: dict, *, holder, recv: date, doc: str, status: str, supersedes: str | None = None, **kw) -> str:
    did = next(d for d in o.rows["documents"] if d["id"] == doc)
    return o.add("real_assets", source_record_id=did["source_record_id"], source_document_id=doc, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv),
                 supersedes_real_asset_id=supersedes if supersedes is not None else base["id"], title_holder_name=holder, status=status,
                 **{k: base.get(k) for k in ("asset_ref", "asset_name", "asset_type", "legal_entity_id", "currency", "appraised_value", "appraised_on", "appraiser")} | kw)


def stamp(d):
    from sh_platform.v1.v3_pack_readers import stamp as s
    return s(d)


def valuations(o) -> None:
    from sh_platform.v1.v3_pack_readers import money, parse_date, pdf_text
    items = []
    for p in o.files("property_valuations"):
        t = pdf_text(str(p))
        ref = re.search(r"Asset: .+\((RA-\d+)\)", t)[1]
        v = re.search(r"Appraised value: ([A-Z]{3}) ([\d,\.]+)", t)
        items.append(dict(p=p, t=t, ref=ref, name=re.search(r"Asset: (.+?) \(RA-", t)[1], kind=re.search(r"Type: (.+)", t)[1].strip(), owner=_line(t, "Owner of record:"),
                          on=parse_date(_line(t, "Valuation date:")), ccy=v[1], value=money(v[2]), appraiser=_title(t.splitlines()[0])))
    n = 0
    for it in sorted(items, key=lambda i: (i["ref"], i["on"])):  # oldest first within an asset, whatever order the files arrived in
        recv = o.arrival(it["p"])
        did = o.doc(it["p"], "property_valuation", it["p"].stem, received=recv, date_=it["on"], valuation=it["on"],
                    fields=[("asset_ref", it["ref"]), ("appraised_value", None, it["value"], it["ccy"]), ("valuation_date", it["on"].isoformat()), ("owner_of_record", it["owner"])])
        eid, ename = _entity(o, it["owner"] or "")
        if eid is None:
            o.note("property_valuations", flag=f"{it['ref']}: owner of record '{it['owner']}' is not one of the office's entities; the appraisal is kept with no entity")
        head = _head(o, "real_assets", "asset_ref", it["ref"])
        holder = o.deed_holder.get(it["ref"]) or (head or {}).get("title_holder_name") or it["owner"]  # no deed (art, wine, a vessel): the owner of record holds it
        status, sup = "appraised", None
        if head and head["appraised_on"] and head["appraised_on"] >= it["on"]:
            same = head["appraised_on"] == it["on"] and Decimal(head["appraised_value"]) == it["value"]
            o.note("property_valuations", flag=f"{it['ref']}: the appraisal of {it['on']} is {'already on record' if same else 'older than the one on record'}; kept as history, not as the value")
            status = "historic"
        elif head:
            sup = head["id"]
        o.add("real_assets", source_record_id=o.doc_record(did), source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv), supersedes_real_asset_id=sup,
              asset_ref=it["ref"], asset_name=it["name"], asset_type=it["kind"], legal_entity_id=eid, title_holder_name=holder, currency=it["ccy"], appraised_value=it["value"],
              appraised_on=it["on"], appraiser=it["appraiser"], status=status)
        n += 1
        o.note("property_valuations", files=1)
    o.note("property_valuations", rows=n)
    for ref in sorted({i["ref"] for i in items} | set(getattr(o, "deed_holder", {}))):  # the value now: title and age checked on the newest row of each asset
        h = _head(o, "real_assets", "asset_ref", ref)
        if not h:
            continue
        ent_name = next((nm for c, nm in o.md["entities"].items() if o.ent[c] == h["legal_entity_id"]), None)
        if h.get("title_holder_name") and ent_name and h["title_holder_name"].lower() != ent_name.lower():
            o.exception("title_mismatch", f"{h['asset_name']}: title is in the name of {h['title_holder_name']}, not {ent_name}",
                        f"{ref} is held by {ent_name} but the certificate of title names {h['title_holder_name']}.", o.today, legal_entity_id=h["legal_entity_id"], external_ref=ref)
            o.note("title_deeds" if ref in o.deed_holder else "property_valuations", flag=f"{ref}: title in the name of {h['title_holder_name']}, not {ent_name} (M29)")
        if h.get("appraised_on") and (o.today - h["appraised_on"]).days > STALE_DAYS:
            o.note("property_valuations", flag=f"{ref}: last appraised {h['appraised_on']}, {(o.today - h['appraised_on']).days} days before {o.today} (M28)")


# ---- the insurance schedule ---------------------------------------------------------------------------------------------------------------

POLICY = re.compile(r"^(POL-[\w-]+) \| (.+?) \| asset (\S+) \| sum insured ([A-Z]{3}) ([\d,\.]+) \| premium ([A-Z]{3}) ([\d,\.]+) \| next renewal (\S+)\s*$", re.M)


def schedule(o) -> None:
    from sh_platform.v1.v3_pack_readers import money, parse_date, pdf_text
    n = 0
    notices = {f["value_text"] for f in o.rows.get("extracted_fields", []) if f["field_name"] == "policy"} | {r[0] for r in _db(
        o, "select f.value_text from extracted_fields f join documents d on d.id = f.document_id where d.document_type = 'insurance_renewal' and f.field_name = 'policy'")}
    note_ccy = {}
    for p in o.files("insurance"):  # the renewal notices: their premium currency is checked against the schedule's
        t = pdf_text(str(p))
        if m := re.search(r"Policy: (\S+)", t):
            note_ccy[m[1]] = re.search(r"Expiring premium: ([A-Z]{3})", t)[1]
    for p in o.files("insurance_schedule"):
        t = pdf_text(str(p))
        insurer = _title(t.splitlines()[0])
        recv = o.arrival(p)
        asat = parse_date(re.search(r"as at (\d{1,2} \w+ \d{4})", t)[1])
        did = o.doc(p, "insurance_schedule", p.stem, received=recv, date_=asat, fields=[("policy", m[1]) for m in POLICY.finditer(t)])
        for m in POLICY.finditer(t):
            pol, name, asset, sccy, sum_, pccy, prem, renew = m.groups()
            renew = parse_date(renew)
            head = _head(o, "vendor_contracts", "contract_ref", pol, "and contract_kind = 'insurance'")
            if head and head["next_renewal_date"] == renew and Decimal(head["annual_cost"]) == money(prem) and Decimal(head["sum_insured"] or 0) == money(sum_):
                o.note("insurance_schedule", flag=f"{pol}: unchanged since the schedule on record; not written again")
                continue
            o.add("vendor_contracts", source_record_id=o.doc_record(did), source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv),
                  supersedes_vendor_contract_id=head["id"] if head else None, vendor_name=insurer, service=name, contract_ref=pol, start_date=renew.replace(year=renew.year - 1), end_date=renew,
                  next_renewal_date=renew, annual_cost=money(prem), currency=pccy, contract_kind="insurance", sum_insured=money(sum_), covered_asset_ref=None if asset == "none" else asset)
            n += 1
            if sccy != pccy:
                o.note("insurance_schedule", flag=f"{pol}: sum insured in {sccy}, premium in {pccy}; the sum is read in {sccy}")
            if (c := note_ccy.get(pol)) and c != pccy:
                o.note("insurance_schedule", flag=f"{pol}: the renewal notice shows the premium in {c}, the schedule in {pccy}; the schedule is kept")
                o.exception("premium_currency_mismatch", f"{pol}: premium currency differs between notice and schedule", f"Renewal notice {c}, schedule {pccy}.", recv, external_ref=pol)
            days = (renew - o.today).days
            if 0 <= days <= NOTICE_WINDOW and pol not in notices:
                o.note("insurance_schedule", flag=f"{pol}: renews in {days} days and no renewal notice has been received")
                o.exception("renewal_notice_missing", f"{pol}: renewal notice not received", f"{name} renews on {renew} ({days} days) and no renewal notice is on record.", recv, external_ref=pol)
        o.note("insurance_schedule", files=1)
    o.note("insurance_schedule", rows=n)


# ---- the custodian's safekeeping statement ------------------------------------------------------------------------------------------------

HOLDING = re.compile(r"^(.+?)\s+([\d,]+)\s+(\d+\.\d+)\s+([\d,]+\.\d\d)\s*$")


def statements(o) -> None:
    from sh_platform.v1.v3_pack_readers import money, parse_date, pdf_text
    n = 0
    for p in o.files("custody_statements"):
        t = pdf_text(str(p))
        port = re.search(r"Portfolio (\S+)", t)[1]
        d = parse_date(re.search(r"As at (\d{1,2} \w+ \d{4})", t)[1])
        recv = o.arrival(p)
        notes = [(m[1], m[2], int(m[3].replace(",", ""))) for m in re.finditer(r"^Note (\w+): (.+?) \(([+-][\d,]+) units\)\s*$", t, re.M)]
        did = o.doc(p, "custody_statement", p.stem, received=recv, date_=d, valuation=d, fields=[("portfolio", port), ("as_at", d.isoformat())])
        for line in t.splitlines():
            m = HOLDING.match(line.strip())
            if not m:
                continue
            name, qty, price, val = m[1], Decimal(m[2].replace(",", "")), Decimal(m[3]), money(m[4])
            iid = o.by_name.get(name) or next((i for k, i in o.by_name.items() if len(name) >= 20 and k.startswith(name)), None)  # a name cut at the column width
            if iid is None:
                o.note("custody_statements", flag=f"{name}: not a security the office knows; the line is not loaded")
                o.exception("unknown_security", f"{name}: on the custody statement of {d}, not in the security master", f"{qty} units, {val} on {p.name}.", recv)
                continue
            if abs(qty * price - val) > 1:
                o.note("custody_statements", flag=f"{name}: {qty} x {price} is not {val}; the statement's value is kept")
            name = next(k for k, i in o.by_name.items() if i == iid)  # the security master's spelling, not the cut-off one
            o.field(did, "custody_quantity", name, qty, line=n + 1)  # the statement's own quantity and value, one pair per holding
            o.field(did, "custody_value", name, val, "USD", line=n + 1)
            n += 1
        for code, text, delta in notes:
            iid = o.by_code.get(code) or next((i for k, i in o.by_code.items() if k.startswith(code + ".")), None)  # BSU is the ticker BSU.SYN
            who = next((k for k, i in o.by_name.items() if i == iid), code)
            o.field(did, "custodian_note", f"{who}: {text}", delta)
            o.note("custody_statements", flag=f"{who}: the custodian's note says '{text}' ({delta:+,} units)")
        o.note("custody_statements", files=1)
    o.note("custody_statements", rows=n)
