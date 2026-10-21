"""Pack readers of the file-format feeds (W1, docs/v3/PROGRAM-GAPS.md): the files banks and custodians send every day, read into tables that already exist
(ASSUMPTIONS A12, A22). v3_pack_readers calls `install(module)` once; the readers are methods of its Office and run inside the step `invest` (no new step).

  swift_mt940   SWIFT MT940 bank statement     -> cash_movements (one per :61: line), the closing balance as a position_snapshot of the account's cash, a bank_statement document
  iso_camt053   ISO 20022 camt.053 statement   -> the same
  bai2          BAI2 statement (US banks)      -> the same
  swift_mt535   SWIFT MT535 custody holdings   -> position_snapshots (one per held security), a custody_statement document
  swift_mt536   SWIFT MT536 custody settlements-> transactions (one per settled buy or sell; a desk trade still 'executed' is superseded by the custodian's settlement)

Receipts: every row has a source_record whose raw_payload_uri is the file, sheet_name the tag it came from (':61:', 'Ntry', '16', ':16R:FIN', ':16R:SETTRAN')
and row_number the line of the file. A line already on record (same account, reference, date, amount: whether it came from this feed, another file or the
office's xlsx statement) is not written twice; a file read before (same content) is skipped by read_files. Synthetic data only."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

try:
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover - defusedxml is in the venv; the stdlib parser is the fallback
    from xml.etree import ElementTree as ET

P = None  # the pack readers module, set by install()
KINDS = {
    "swift_mt940": ("SWIFT MT940 bank statement", "data.read-swift-mt940", "bank lines (cash movements), closing balance"),
    "iso_camt053": ("ISO 20022 camt.053 bank statement", "data.read-iso-camt053", "bank lines (cash movements), closing balance"),
    "bai2": ("BAI2 bank statement", "data.read-bai2", "bank lines (cash movements), closing balance"),
    "swift_mt535": ("SWIFT MT535 custody holdings", "data.read-swift-mt535", "position snapshots"),
    "swift_mt536": ("SWIFT MT536 custody settlements", "data.read-swift-mt536", "transactions"),
}
CLASS = {"NINT": "interest", "NCHG": "fee", "NFEX": "fx_conversion", "NTRF": "transfer", "NDIV": "distribution", "NSEC": "settlement"}
BANK_KINDS = ("swift_mt940", "iso_camt053", "bai2")


# ------------------------------------------------------------------------------------------------------------------------------ small readers
def _amt(s: str) -> Decimal:
    return Decimal(s.strip().replace(",", ".").rstrip(".") or "0")


def _yymmdd(s: str) -> date:
    return date(2000 + int(s[:2]), int(s[2:4]), int(s[4:6]))


def _ymd(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _class(code: str, amount: Decimal, text: str = "") -> str:
    """The movement type of a line: from the bank's transaction code where it gives one, else (BAI2, which has no such code) from the words of the line."""
    if t := CLASS.get(code):
        return t
    low = text.lower()
    if code == "698":
        return "fee"
    for word, t in (("interest", "interest"), ("bought ", "fx_conversion"), ("transfer", "transfer"), ("distribution", "distribution")):
        if word in low:
            return t
    return "payment" if amount < 0 else "receipt"


# ------------------------------------------------------------------------------------------------------------------------------ SWIFT fields
TAG = re.compile(r"^:(\d{2}[A-Z]?):(.*)$")


def swift_fields(text: str) -> list[list]:
    """[[tag, value, line number]] of a SWIFT message; a line that is not a tag continues the field before it."""
    out: list[list] = []
    for n, line in enumerate(text.split("\n"), 1):
        if m := TAG.match(line):
            out.append([m[1], m[2], n])
        elif out and line.strip() and not line.startswith(("-}", "{")):
            out[-1][1] += "\n" + line
    return out


BAL = re.compile(r"^([CD])(\d{6})([A-Z]{3})([\d,]+)$")
L61 = re.compile(r"^(\d{6})(?:\d{4})?(RC|RD|C|D)[A-Z]?([\d,]+)N([A-Z0-9]{3})([^/\n]*)(?://([^\n]*))?")


def _balance(value: str, line: int) -> tuple[Decimal, date, str]:
    m = BAL.match(value.strip())
    if not m:
        raise ValueError(f"line {line}: balance '{value.strip()}' is not readable")
    a = _amt(m[4])
    return (a if m[1] == "C" else -a), _yymmdd(m[2]), m[3]


def parse_mt940(text: str) -> list[dict]:
    out: list[dict] = []
    cur = None
    for tag, value, n in swift_fields(text):
        if tag == "20":
            cur = {"account": None, "ccy": None, "open": None, "close": None, "lines": [], "line": n}
            out.append(cur)
        elif cur is None:
            continue
        elif tag == "25":
            cur["account"] = value.strip().split("/")[-1].strip()
        elif tag in ("60F", "60M"):
            a, d, c = _balance(value, n)
            cur["open"], cur["ccy"] = (a, d), c
        elif tag in ("62F", "62M"):
            a, d, c = _balance(value, n)
            cur["close"], cur["ccy"] = (a, d), c
        elif tag == "61":
            first = value.split("\n")[0]
            m = L61.match(first)
            if not m:
                raise ValueError(f"line {n}: the statement line '{first}' is not readable")
            amount = _amt(m[3]) * (1 if m[2] in ("C", "RD") else -1)
            ref = (m[6] or "").strip() or m[5].strip()
            cur["lines"].append({"date": _yymmdd(m[1]), "amount": amount, "ref": ref, "cp": None, "desc": "", "code": "N" + m[4], "tag": ":61:", "line": n})
        elif tag == "86" and cur["lines"]:
            info = "".join(value.split("\n"))
            parts = re.split(r"/(NAME|REMI)/", info)
            kv = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
            cur["lines"][-1]["cp"], cur["lines"][-1]["desc"] = kv.get("NAME"), kv.get("REMI", info if not kv else "")
    for s in out:
        if not (s["account"] and s["close"]):
            raise ValueError(f"line {s['line']}: the statement has no account or closing balance")
    return out


# ------------------------------------------------------------------------------------------------------------------------------ camt.053
def _kid(el, *names):
    for n in names:
        el = next((c for c in el if c.tag.rsplit("}", 1)[-1] == n), None) if el is not None else None
    return el


def _kids(el, name):
    return [c for c in el if c.tag.rsplit("}", 1)[-1] == name]


def _tx(el, *names):
    k = _kid(el, *names)
    return k.text.strip() if k is not None and k.text else None


def parse_camt053(data: bytes) -> list[dict]:
    root = ET.fromstring(data)
    starts = [n for n, line in enumerate(_text(data).split("\n"), 1) if re.search(r"<Ntry[\s>]", line)]
    out, k = [], 0
    for stmt in root.iter():
        if stmt.tag.rsplit("}", 1)[-1] != "Stmt":
            continue
        acct = _kid(stmt, "Acct", "Id")
        number = (_tx(acct, "Othr", "Id") or _tx(acct, "IBAN")) if acct is not None else None
        st = {"account": number, "ccy": _tx(stmt, "Acct", "Ccy"), "open": None, "close": None, "lines": [], "line": 1}
        for b in _kids(stmt, "Bal"):
            code, amt = _tx(b, "Tp", "CdOrPrtry", "Cd"), _kid(b, "Amt")
            v = Decimal(amt.text.strip()) * (1 if _tx(b, "CdtDbtInd") == "CRDT" else -1)
            if code in ("OPBD", "PRCD"):
                st["open"] = (v, date.fromisoformat(_tx(b, "Dt", "Dt")[:10]))
            elif code in ("CLBD", "CLAV") and not st["close"]:
                st["close"], st["ccy"] = (v, date.fromisoformat(_tx(b, "Dt", "Dt")[:10])), amt.get("Ccy")
        for e in _kids(stmt, "Ntry"):
            sign = 1 if _tx(e, "CdtDbtInd") == "CRDT" else -1
            amt = _kid(e, "Amt")
            tx = _kid(e, "NtryDtls", "TxDtls")
            ref = (_tx(tx, "Refs", "AcctSvcrRef") if tx is not None else None) or _tx(e, "NtryRef") or (_tx(tx, "Refs", "EndToEndId") if tx is not None else None)
            party = ("Dbtr" if sign > 0 else "Cdtr")
            d = _tx(e, "ValDt", "Dt") or _tx(e, "BookgDt", "Dt")
            st["lines"].append({"date": date.fromisoformat(d[:10]), "amount": sign * Decimal(amt.text.strip()), "ref": ref, "cp": _tx(tx, "RltdPties", party, "Nm") if tx is not None else None,
                                "desc": (_tx(tx, "RmtInf", "Ustrd") if tx is not None else None) or "", "code": _tx(e, "BkTxCd", "Prtry", "Cd") or "", "tag": "Ntry",
                                "line": starts[k] if k < len(starts) else 1})
            k += 1
        if not (st["account"] and st["close"]):
            raise ValueError("the camt.053 statement has no account or closing balance")
        out.append(st)
    if not out:
        raise ValueError("no Stmt in the camt.053 file")
    return out


# ------------------------------------------------------------------------------------------------------------------------------ BAI2
def parse_bai2(text: str) -> list[dict]:
    """One statement per account. A group is one as-of day: its 03 gives the opening (010) and closing (015) ledger, its 16 records are that day's lines
    (amounts in cents; type codes 100 to 399 credit, 400 to 699 debit)."""
    sts: dict[str, dict] = {}
    day, acct, count, ends = None, None, 0, None
    for n, raw in enumerate(text.split("\n"), 1):
        rec = raw.strip().rstrip("/")
        if not rec:
            continue
        count += 1
        f = rec.split(",")
        if f[0] == "02":
            day = _yymmdd(f[4])
        elif f[0] == "03":
            ccy = f[2] or "USD"
            acct = sts.setdefault(f[1], {"account": f[1], "ccy": ccy, "open": None, "close": None, "lines": [], "line": n})
            rest = f[3:]
            for i in range(0, len(rest) - 1, 4):
                code, amount = rest[i], rest[i + 1]
                if code == "010" and amount:
                    acct["open"] = acct["open"] or (_cents(amount), day)
                elif code == "015" and amount:
                    acct["close"] = (_cents(amount), day)
        elif f[0] == "16":
            code, amount = f[1], _cents(f[2])
            text_ = ",".join(f[6:]).strip()
            cp, _, desc = text_.partition("|")
            acct["lines"].append({"date": day, "amount": amount if int(code) < 400 else -amount, "ref": f[4].strip() or f[5].strip(), "cp": cp.strip() or None, "desc": desc.strip(),
                                  "code": code, "tag": "16", "line": n})
        elif f[0] == "99":
            ends = int(f[3]) if len(f) > 3 and f[3].isdigit() else None
    if ends is not None and ends != count:
        raise ValueError(f"the file trailer counts {ends} records, the file has {count}")
    if not sts or not all(s["close"] for s in sts.values()):
        raise ValueError("the BAI2 file has no account or closing balance")
    return list(sts.values())


def _cents(s: str) -> Decimal:
    return Decimal(s) if "." in s else Decimal(s) / 100


# ------------------------------------------------------------------------------------------------------------------------------ MT535 / MT536
def _sub(value: str, qual: str) -> str | None:
    """The part of '::QUAL//rest' after the qualifier ('//' or '/..../'), else None."""
    m = re.match(rf"^:{qual}/(?:[A-Z]{{4}})?/(.*)$", value.strip().split("\n")[0])
    return m[1] if m else None


def _grab(fields: list[list], tag: str, qual: str):
    for t, v, n in fields:
        if t == tag and (r := _sub(v, qual)) is not None:
            return r, n
    return None, None


def parse_mt535(text: str) -> dict:
    f = swift_fields(text)
    out = {"date": None, "safe": None, "positions": []}
    for t, v, n in f:
        if t.startswith("98") and (r := _sub(v, "STAT")):
            out["date"] = _ymd(r[:8])
        elif t == "97A" and (r := _sub(v, "SAFE")):
            out["safe"] = r.strip()
    if not out["date"]:
        raise ValueError("the MT535 has no statement date (:98A::STAT//)")
    cur = None
    for t, v, n in f:
        if t == "16R" and v.strip() == "FIN":
            cur = {"line": n, "isin": None, "name": None, "qty": None, "price": None, "mv": None, "ccy": None}
            out["positions"].append(cur)
        elif t == "16S" and v.strip() == "FIN":
            cur = None
        elif cur is None:
            continue
        elif t == "35B":
            first, _, rest = v.partition("\n")
            cur["isin"], cur["name"] = first.replace("ISIN", "").strip(), rest.strip() or None
        elif t == "93B" and (r := _sub(v, "AGGR")):
            cur["qty"] = _amt(r.split("/")[-1])
        elif t == "90B" and (r := _sub(v, "MRKT")):
            c = r.split("/")[-1]
            cur["price"] = _amt(c[3:])
        elif t == "19A" and (r := _sub(v, "HOLD")):
            neg = r.startswith("N")
            r = r[1:] if neg else r
            cur["ccy"], cur["mv"] = r[:3], _amt(r[3:]) * (-1 if neg else 1)
    for p in out["positions"]:
        if not (p["isin"] and p["qty"] is not None and p["mv"] is not None):
            raise ValueError(f"line {p['line']}: a position has no ISIN, quantity or value")
    return out


def parse_mt536(text: str) -> dict:
    f = swift_fields(text)
    out = {"safe": None, "date": None, "ref": None, "trades": []}
    cur = None
    for t, v, n in f:
        if t == "97A" and (r := _sub(v, "SAFE")):
            out["safe"] = r.strip()
        elif t.startswith("98") and (r := _sub(v, "PREP")):
            out["date"] = _ymd(r[:8])
        elif t == "16R" and v.strip() == "SETTRAN":
            cur = {"line": n, "isin": None, "name": None, "qty": None, "amount": None, "ccy": None, "side": None, "ref": None, "trade": None, "settle": None, "price": None}
            out["trades"].append(cur)
        elif t == "16S" and v.strip() == "SETTRAN":
            cur = None
        elif cur is None:
            continue
        elif t == "35B":
            first, _, rest = v.partition("\n")
            cur["isin"], cur["name"] = first.replace("ISIN", "").strip(), rest.strip() or None
        elif t == "36B" and (r := _sub(v, "SETT")):
            cur["qty"] = _amt(r.split("/")[-1])
        elif t == "19A" and (r := _sub(v, "SETT")):
            cur["ccy"], cur["amount"] = r[:3], _amt(r[3:])
        elif t == "90B" and (r := _sub(v, "DEAL")):
            cur["price"] = _amt(r.split("/")[-1][3:])
        elif t == "22H" and (r := _sub(v, "REDE")):
            cur["side"] = {"RECE": "buy", "DELI": "sell"}.get(r.strip())
        elif t.startswith("98") and (r := _sub(v, "TRAD")):
            cur["trade"] = _ymd(r[:8])
        elif t.startswith("98") and (r := _sub(v, "SETT")):
            cur["settle"] = _ymd(r[:8])
        elif t == "20C" and (r := _sub(v, "SEME")):
            cur["ref"] = r.strip()
    for x in out["trades"]:
        if not (x["isin"] and x["qty"] is not None and x["amount"] is not None and x["side"] and x["ref"] and x["settle"]):
            raise ValueError(f"line {x['line']}: a settlement has no ISIN, quantity, amount, direction, reference or date")
    return out


# ------------------------------------------------------------------------------------------------------------------------------ kind_of
def kind_of(name: str, data: bytes):
    """(kind, name) when the content is one of the five formats, else None. Content decides, never the extension."""
    if name.lower().endswith((".pdf", ".xlsx", ".xlsm", ".eml", ".docx", ".zip")):
        return None
    head = data[:6000]
    if b"<BkToCstmrStmt" in head and b"camt.053" in head:
        return "iso_camt053", name
    t = head.decode("utf-8-sig", errors="ignore").lstrip()
    if t.startswith("01,") and re.search(r"^02,", data[:6000].decode("utf-8-sig", errors="ignore"), re.M):
        return "bai2", name
    if re.search(r"\{2:[IO]535", t) or (":16R:GENL" in t and ":16R:SUBSAFE" in data.decode("utf-8-sig", errors="ignore")):
        return "swift_mt535", name
    if re.search(r"\{2:[IO]536", t) or (":16R:GENL" in t and ":16R:SETTRAN" in data.decode("utf-8-sig", errors="ignore")):
        return "swift_mt536", name
    if re.search(r"^:20:", t, re.M) and re.search(r"^:25:", t, re.M) and re.search(r"^:60[FM]:", t, re.M) and re.search(r"^:62[FM]:", t, re.M):
        return "swift_mt940", name
    return None


# ------------------------------------------------------------------------------------------------------------------------------ the readers (methods of Office)
def _seen(self, table: str, pid: str) -> set:
    cache = self.__dict__.setdefault("_feed_seen", {})
    if (table, pid) not in cache:
        sql = {"cash_movements": "select reference, effective_date, amount, currency from cash_movements where portfolio_id = ? and reference is not null",
               "position_snapshots": "select instrument_id, position_date, quantity, source_market_value from position_snapshots where portfolio_id = ?"}[table]
        try:
            cache[(table, pid)] = {(str(r[0]), *r[1:]) if table == "position_snapshots" else tuple(r) for r in self.con.execute(sql, [pid]).fetchall()}
        except Exception:  # noqa: BLE001 - a warehouse without the table has nothing on record
            cache[(table, pid)] = set()
        for r in self.rows.get(table, []):  # rows of the same batch not yet written (the office's own statement, read a step before)
            if r.get("portfolio_id") == pid:
                cache[(table, pid)].add((r["reference"], r["effective_date"], r["amount"], r["currency"]) if table == "cash_movements"
                                        else (str(r["instrument_id"]), r["position_date"], r["quantity"], r["source_market_value"]))
    return cache[(table, pid)]


def _account(self, number: str):
    n = re.sub(r"\s", "", number or "")
    return next((a for a in self.office_acct.values() if a["number"] == n), None)


def feed_bank(self, kind: str) -> None:
    parse = {"swift_mt940": lambda d: parse_mt940(_text(d)), "iso_camt053": parse_camt053, "bai2": lambda d: parse_bai2(_text(d))}[kind]
    for p in self.files(kind):
        recv, data = self.arrival(p), p.read_bytes()
        stmts = parse(data)
        lines = skipped = 0
        for st in stmts:
            a = _account(self, st["account"])
            if a is None:
                self.note(kind, why=f"{p.name}: account {st['account']} is not one of the office's accounts")
                continue
            if st["ccy"] != a["ccy"]:
                self.note(kind, why=f"{p.name}: the statement is in {st['ccy']}, the account is in {a['ccy']}")
                continue
            close, cdate = st["close"]
            sr = self.record(kind, p, recv, effective=cdate)
            did = self.doc(p, "bank_statement", f"{p.stem} {st['account']}" if len(stmts) > 1 else p.stem, kind=kind, instrument=a["cash"], valuation=cdate, date_=cdate, received=recv, record=sr,
                           raw=data + st["account"].encode() if len(stmts) > 1 else None)
            self.field(did, "account_number", st["account"])
            self.field(did, "closing_balance", num=close, ccy=st["ccy"])
            port, seen, net = self.cashport[a["entity"]], _seen(self, "cash_movements", self.cashport[a["entity"]]), Decimal(0)
            for ln in st["lines"]:
                net += ln["amount"]
                key = (ln["ref"], ln["date"], ln["amount"], st["ccy"])
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                rec = self.record(kind, p, recv, rtype="bank_line", external=ln["ref"], sheet=ln["tag"], row=ln["line"], effective=ln["date"])
                self.add("cash_movements", source_record_id=rec, portfolio_id=port, bank_account_id=a["id"], effective_date=ln["date"], received_at=P.stamp(recv, 6), recorded_at=P.stamp(recv, 6),
                         amount=ln["amount"], currency=st["ccy"], confirmation_status="confirmed", reference=ln["ref"], payee_name=ln["cp"], movement_type=_class(ln["code"], ln["amount"], ln["desc"]))
                if ln["desc"]:
                    self.field(did, "description", ln["desc"], line=ln["line"])
                lines += 1
            if st["open"] and st["open"][0] + net != close:
                self.note(kind, flag=f"{p.name}: the opening balance {st['open'][0]} plus the lines {net} is not the closing balance {close}")
            snap = (str(a["cash"]), cdate, close, close)
            if snap not in _seen(self, "position_snapshots", port):
                _seen(self, "position_snapshots", port).add(snap)
                self.add("position_snapshots", source_record_id=sr, portfolio_id=port, instrument_id=a["cash"], position_date=cdate, as_of_at=P.stamp(cdate, 20), received_at=P.stamp(recv, 6),
                         recorded_at=P.stamp(recv, 6), quantity=close, source_market_value=close, currency=st["ccy"], data_status="Final")
        self.note(kind, files=1, rows=lines)
        if skipped:
            self.note(kind, flag=f"{p.name}: {skipped} line(s) already on record, not written again")


def _isin_map(self) -> dict:
    return {v: i for (i, t, v) in self.k_ident if t == "isin"}


def _portfolio(self, safe: str):
    return next((c for c in self.port if safe and safe.endswith(c)), None)


def _instrument(self, isin: str, name: str | None, ccy: str | None, recv: date) -> str:
    m = _isin_map(self)
    if isin in m:
        return m[isin]
    iid = self.by_name.get(name) or self.add("instruments", canonical_name=name or isin, instrument_type="unknown", currency=ccy, created_at=P.stamp(recv))
    self.ident(iid, "isin", isin, status="proposed")
    self.note("swift_mt535", flag=f"{isin} ({name}) is not in the security master: a new instrument, identifier proposed")
    return iid


def feed_mt535(self) -> None:
    for p in self.files("swift_mt535"):
        recv, d = self.arrival(p), None
        m = parse_mt535(_text(p.read_bytes()))
        code = _portfolio(self, m["safe"])
        if code is None:
            self.note("swift_mt535", why=f"{p.name}: safekeeping account {m['safe']} is not a portfolio of the office")
            continue
        d, port, n = m["date"], self.port[code], 0
        sr = self.record("swift_mt535", p, recv, effective=d)
        did = self.doc(p, "custody_statement", p.stem, kind="swift_mt535", valuation=d, date_=d, received=recv, record=sr)
        self.field(did, "safekeeping_account", m["safe"])
        seen = _seen(self, "position_snapshots", port)
        for x in m["positions"]:
            iid = _instrument(self, x["isin"], x["name"], x["ccy"], recv)
            key = (str(iid), d, x["qty"], x["mv"])
            if key in seen:
                continue
            seen.add(key)
            rec = self.record("swift_mt535", p, recv, rtype="position", external=x["isin"], sheet=":16R:FIN", row=x["line"], effective=d)
            self.add("position_snapshots", source_record_id=rec, portfolio_id=port, instrument_id=iid, position_date=d, as_of_at=P.stamp(d, 20), received_at=P.stamp(recv, 22),
                     recorded_at=P.stamp(recv, 22), quantity=x["qty"], source_market_value=x["mv"], currency=x["ccy"], data_status="Final")
            n += 1
        self.note("swift_mt535", files=1, rows=n)


def feed_mt536(self) -> None:
    for p in self.files("swift_mt536"):
        recv = self.arrival(p)
        m = parse_mt536(_text(p.read_bytes()))
        code = _portfolio(self, m["safe"])
        if code is None:
            self.note("swift_mt536", why=f"{p.name}: safekeeping account {m['safe']} is not a portfolio of the office")
            continue
        port, n = self.port[code], 0
        self.doc(p, "custody_transactions", p.stem, kind="swift_mt536", valuation=m["date"], date_=m["date"], received=recv)
        done: set = set()
        for x in m["trades"]:
            tid = re.sub(r"^CT-", "", x["ref"])
            was = self.con.execute("select t.id, t.status from transactions t where t.external_trade_id = ? and not exists (select 1 from transactions s where s.supersedes_transaction_id = t.id)",
                                   [tid]).fetchall() if tid not in done else []
            if tid in done or any(w[1] == "settled" for w in was):
                continue  # the settlement is on record
            done.add(tid)
            iid = _instrument(self, x["isin"], x["name"], x["ccy"], recv)
            sell = x["side"] == "sell"
            rec = self.record("swift_mt536", p, recv, rtype="trade", external=x["ref"], sheet=":16R:SETTRAN", row=x["line"], effective=x["trade"] or x["settle"])
            self.add("transactions", source_record_id=rec, portfolio_id=port, instrument_id=iid, external_trade_id=tid, transaction_type=x["side"], trade_date=x["trade"] or x["settle"],
                     effective_date=x["trade"] or x["settle"], settlement_date=x["settle"], quantity_delta=-x["qty"] if sell else x["qty"], cash_amount=x["amount"] if sell else -x["amount"],
                     currency=x["ccy"], recorded_at=P.stamp(recv), status="settled", **({"supersedes_transaction_id": was[0][0]} if was else {}))
            n += 1
        self.note("swift_mt536", files=1, rows=n)


def install(module) -> None:
    """Register the five kinds. They run as part of the step `invest` (the step list of Office.load stays as it is). Called at the end of v3_pack_readers."""
    global P
    P = module
    O = module.Office
    O.feed_mt940, O.feed_camt053, O.feed_bai2 = (lambda self: feed_bank(self, "swift_mt940")), (lambda self: feed_bank(self, "iso_camt053")), (lambda self: feed_bank(self, "bai2"))
    O.feed_mt535, O.feed_mt536 = feed_mt535, feed_mt536
    inner = O.invest

    def invest(self) -> None:  # named: the step's name is how STEP_KINDS finds its kinds
        inner(self)
        for fn in (O.feed_mt940, O.feed_camt053, O.feed_bai2, O.feed_mt535, O.feed_mt536):
            fn(self)
    O.invest = invest
    module.KINDS.update(KINDS)
    module.STEP_KINDS["invest"] = [*module.STEP_KINDS["invest"], *KINDS]
    plain = module.kind_of

    def kind_of_feeds(name: str, data: bytes):
        return plain(name, data) or kind_of(name, data)
    kind_of_feeds.__doc__ = plain.__doc__
    module.kind_of = kind_of_feeds
