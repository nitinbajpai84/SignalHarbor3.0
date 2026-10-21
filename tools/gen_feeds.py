"""Synthetic sample files of the four feed formats, written from the six-month office (tests/v1/fixtures/office6m) so the figures tie out with the bank
statements and the custody data already there.

    python -m tools.gen_feeds [--office tests/v1/fixtures/office6m] [--out tests/v1/fixtures/feeds]

  swift_mt940 / iso_camt053 / bai2   the June 2026 statements of three accounts (lines from the xlsx statement, balances from its Daily balances sheet)
  swift_mt535                        the custodian's positions of 30 June 2026 (positions_20260630.csv), ISIN from the security master
  swift_mt536                        the custodian's buys and sells of June 2026 (transactions_2026-06.csv; income lines are not settlements and are left out)

Deterministic (no clock). Synthetic data only: every bank, name and figure is invented."""
from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
MONTH, MONTH_END = "2026-06", date(2026, 6, 30)
CODE = {"interest": "NINT", "bank_fee": "NCHG", "fee": "NCHG", "fx_conversion": "NFEX", "internal_transfer": "NTRF", "intercompany_transfer": "NTRF", "distribution": "NDIV",
        "trade_settlement": "NSEC"}
MT940 = ("HB-HOLD-USD", "HB-TRUST-USD")
CAMT = ("HB-HOLD-SGD",)
BAI2 = ("TCB-HOLD-USD",)


def d(x) -> Decimal:
    return Decimal(str(x))


def num(x: Decimal, places: int = 2) -> str:
    """SWIFT amount: comma for the decimal point, never a minus."""
    s = f"{abs(x):.{places}f}".replace(".", ",")
    return s


def statement(office: Path, account: str):
    """(number, ccy, lines, daily) of the June statement of an account. lines: dicts; daily: [(date, opening, closing)]."""
    f = next(office.glob(f"20??-??/bank_statements/{account.replace('-', '_')}_{MONTH}.xlsx"))
    wb = openpyxl.load_workbook(f, read_only=True)
    tx = [r for r in wb["Transactions"].iter_rows(values_only=True)][1:]
    daily = [r for r in wb["Daily balances"].iter_rows(values_only=True)][1:]
    lines = [dict(date=date.fromisoformat(r[0]), ref=r[1], type=r[2], desc=r[3], cp=r[4], amount=d(r[5]), ccy=r[6]) for r in tx]
    return daily[0][1], daily[0][2], lines, [(date.fromisoformat(r[0]), d(r[3]), d(r[5])) for r in daily]


def wrap(tag: str, text: str, width: int = 65) -> str:
    return "\n".join([f":{tag}:{text[:width]}", *(text[i:i + width] for i in range(width, len(text), width))])


def bal(tag: str, amount: Decimal, day: date, ccy: str) -> str:
    return f":{tag}:{'C' if amount >= 0 else 'D'}{day:%y%m%d}{ccy}{num(amount)}"


def mt940(number, ccy, lines, daily) -> str:
    opening_day = daily[0][0] - timedelta(days=1)
    out = ["{1:F01HARBSGSGAXXX0000000000}{2:O9400000000000HARBSGSGAXXX00000000002606300000N}{4:", f":20:ST{MONTH_END:%Y%m%d}", f":25:{number}", ":28C:1/1",
           bal("60F", daily[0][1], opening_day, ccy)]
    for ln in lines:
        out.append(f":61:{ln['date']:%y%m%d}{'C' if ln['amount'] >= 0 else 'D'}{num(ln['amount'])}{CODE.get(ln['type'], 'NMSC')}NONREF//{ln['ref']}")
        out.append(wrap("86", f"/NAME/{ln['cp']}/REMI/{ln['desc']}"))
    out += [bal("62F", daily[-1][2], daily[-1][0], ccy), "-}"]
    return "\n".join(out) + "\n"


def camt053(number, ccy, lines, daily) -> str:
    def bal_xml(code, amount, day):
        return (f"      <Bal><Tp><CdOrPrtry><Cd>{code}</Cd></CdOrPrtry></Tp><Amt Ccy=\"{ccy}\">{abs(amount):.2f}</Amt><CdtDbtInd>{'CRDT' if amount >= 0 else 'DBIT'}</CdtDbtInd>"
                f"<Dt><Dt>{day.isoformat()}</Dt></Dt></Bal>")
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">', "  <BkToCstmrStmt>",
           f"    <GrpHdr><MsgId>MSG{MONTH_END:%Y%m%d}{hashlib.sha1(number.encode()).hexdigest()[:6].upper()}</MsgId><CreDtTm>{MONTH_END}T23:00:00</CreDtTm></GrpHdr>", "    <Stmt>",
           f"      <Id>STMT-{MONTH_END:%Y%m%d}</Id>", f"      <Acct><Id><Othr><Id>{number}</Id></Othr></Id><Ccy>{ccy}</Ccy></Acct>",
           bal_xml("OPBD", daily[0][1], daily[0][0] - timedelta(days=1)), bal_xml("CLBD", daily[-1][2], daily[-1][0])]
    for ln in lines:
        cr = ln["amount"] >= 0
        out += ["      <Ntry>", f"        <NtryRef>{escape(ln['ref'])}</NtryRef>", f"        <Amt Ccy=\"{ccy}\">{abs(ln['amount']):.2f}</Amt>",
                f"        <CdtDbtInd>{'CRDT' if cr else 'DBIT'}</CdtDbtInd>", "        <Sts>BOOK</Sts>", f"        <BookgDt><Dt>{ln['date'].isoformat()}</Dt></BookgDt>",
                f"        <ValDt><Dt>{ln['date'].isoformat()}</Dt></ValDt>", f"        <BkTxCd><Prtry><Cd>{CODE.get(ln['type'], 'NMSC')}</Cd></Prtry></BkTxCd>",
                "        <NtryDtls><TxDtls>", f"          <Refs><AcctSvcrRef>{escape(ln['ref'])}</AcctSvcrRef></Refs>",
                f"          <RltdPties><{'Dbtr' if cr else 'Cdtr'}><Nm>{escape(ln['cp'])}</Nm></{'Dbtr' if cr else 'Cdtr'}></RltdPties>",
                f"          <RmtInf><Ustrd>{escape(ln['desc'])}</Ustrd></RmtInf>", "        </TxDtls></NtryDtls>", "      </Ntry>"]
    out += ["    </Stmt>", "  </BkToCstmrStmt>", "</Document>"]
    return "\n".join(out) + "\n"


def bai2(number, ccy, lines, daily) -> str:
    cents = lambda x: str(int(abs(x) * 100))  # noqa: E731
    clean = lambda s: str(s).replace(",", "").replace("/", " ").replace("|", " ")  # noqa: E731
    out = [f"01,HARBOR,SIGNALHBR,{MONTH_END:%y%m%d},2300,1,80,,2/"]
    n = 1
    for day, opening, closing in daily:
        todays = [ln for ln in lines if ln["date"] == day]
        out.append(f"02,SIGNALHBR,HARBOR,1,{day:%y%m%d},2300,{ccy},2/")
        out.append(f"03,{number},{ccy},010,{cents(opening)},,,015,{cents(closing)},,/")
        for ln in todays:
            code = "698" if ln["type"] in ("bank_fee", "fee") else ("195" if ln["amount"] >= 0 else "495")
            out.append(f"16,{code},{cents(ln['amount'])},0,{ln['ref']},,{clean(ln['cp'])}|{clean(ln['desc'])}/")
        out.append(f"49,{cents(closing)},{2 + len(todays)}/")
        out.append(f"98,{cents(closing)},1,{3 + len(todays)}/")
        n += 4 + len(todays)
    out.append(f"99,{cents(daily[-1][2])},{len(daily)},{n + 1}/")
    return "\n".join(out) + "\n"


def isins(office: Path) -> dict:
    f = next(office.glob("reference/EG_security_master_*.xlsx"))
    return {r[0]: (r[1], r[2]) for r in openpyxl.load_workbook(f, read_only=True)["Security master"].iter_rows(values_only=True) if r[0] and str(r[0]).startswith(("SEC-", "FND-"))}


def mt535(office: Path) -> str:
    ids = isins(office)
    rows = list(csv.DictReader(next(office.glob("2026-06/custodian_positions/positions_20260630.csv")).open(encoding="utf-8")))
    out = ["{1:F01ANCHSGSGAXXX0000000000}{2:O5350000000000ANCHSGSGAXXX00000000002606300000N}{4:", ":16R:GENL", ":28E:1/ONLY", f":20C::SEME//HOLD{MONTH_END:%Y%m%d}", ":23G:NEWM",
           f":98A::STAT//{MONTH_END:%Y%m%d}", f":98A::PREP//{MONTH_END:%Y%m%d}", ":97A::SAFE//ANCHORAGE-EG-LIQUID", ":17B::ACTI//Y", ":16S:GENL", ":16R:SUBSAFE"]
    for r in rows:
        isin, name = ids[r["security_id"]]
        out += [":16R:FIN", f":35B:ISIN {isin}", name, f":93B::AGGR//UNIT/{num(d(r['quantity']), 0)},", f":90B::MRKT//ACTU/{r['currency']}{num(d(r['price']))}",
                f":19A::HOLD//{r['currency']}{num(d(r['market_value']))}", ":16S:FIN"]
    out += [":16S:SUBSAFE", "-}"]
    return "\n".join(out) + "\n"


def mt536(office: Path) -> str:
    ids = isins(office)
    rows = [r for r in csv.DictReader(next(office.glob("20??-??/custodian_transactions/transactions_2026-06.csv")).open(encoding="utf-8")) if r["type"] in ("buy", "sell")]
    out = ["{1:F01ANCHSGSGAXXX0000000000}{2:O5360000000000ANCHSGSGAXXX00000000002606300000N}{4:", ":16R:GENL", ":28E:1/ONLY", f":20C::SEME//SETT{MONTH_END:%Y%m%d}", ":23G:NEWM",
           f":98A::PREP//{MONTH_END:%Y%m%d}", ":97A::SAFE//ANCHORAGE-EG-LIQUID", ":16S:GENL"]
    for r in rows:
        isin, name = ids[r["security_id"]]
        out += [":16R:SETTRAN", f":35B:ISIN {isin}", name, f":36B::SETT//UNIT/{num(d(r['quantity']), 0)},", f":19A::SETT//{r['currency']}{num(d(r['amount']))}",
                f":90B::DEAL//ACTU/{r['currency']}{num(d(r['price']), 4)}", f":22H::REDE//{'RECE' if r['type'] == 'buy' else 'DELI'}", ":22H::PAYM//APMT",
                f":98A::TRAD//{r['txn_date'].replace('-', '')}", f":98A::SETT//{r['settle_date'].replace('-', '')}", f":20C::SEME//{r['reference']}", ":16S:SETTRAN"]
    out.append("-}")
    return "\n".join(out) + "\n"


def generate(office: Path, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    made = []

    def put(name: str, text: str) -> None:
        (out / name).write_bytes(text.encode("utf-8"))
        made.append(out / name)
    for kind, accounts, fn, ext in (("mt940", MT940, mt940, "sta"), ("camt053", CAMT, camt053, "xml"), ("bai2", BAI2, bai2, "bai")):
        for acct in accounts:
            put(f"{kind}_{acct}_{MONTH_END.isoformat()}.{ext}", fn(*statement(office, acct)))
    put(f"mt535_EG-LIQUID_{MONTH_END.isoformat()}.txt", mt535(office))
    put(f"mt536_EG-LIQUID_{MONTH_END.isoformat()}.txt", mt536(office))
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--office", type=Path, default=ROOT / "tests/v1/fixtures/office6m")
    ap.add_argument("--out", type=Path, default=ROOT / "tests/v1/fixtures/feeds")
    a = ap.parse_args()
    for p in generate(a.office, a.out):
        print(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
