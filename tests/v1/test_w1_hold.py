"""W1 hold: the recipes of the six "Hold and maintain" cards of the top 50 (13, 17, 21, 31, 38, 43), run on the Evergreen office6m files and compared with answer_keys.yaml.

Real: the recipes file, the model's DuckDB tables (docs/v2/evidence-to-action-mvp.duckdb.sql), the office6m files, the answer keys.
Stubbed: the loader. The files are read here by a few small readers (xlsx, csv, pdf text) and written into the model's tables; the real loaders (b4/e0c, v3_pdf) are
not called (see Needs in docs/v3/w1/build-hold.md). Also checks the signal yaml and the builds yaml of the six cards.
"""
import ast
import csv
import glob
import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import duckdb
import openpyxl
import pypdf
import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as S

REPO = Path(__file__).resolve().parents[2]
FX = REPO / "tests" / "v1" / "fixtures" / "office6m"
PACK = REPO / "packs" / "family_office" / "1"
KEYS = yaml.safe_load((FX / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
MASTER = json.loads((FX / "reference" / "master_data.json").read_text(encoding="utf-8"))
ORG = "org-1"
CARDS = ["uc-013-secgaps", "uc-017-liab", "uc-021-stale", "uc-031-alloc", "uc-038-navroll", "uc-043-liquidpnl"]
LISTED = ("listed_equity", "bond", "convertible")
# the generator's own map (tools/gen_office6m/keys.py): the liquid portfolio belongs to the Trust; the funds' portfolios are in master_data.json
PORTFOLIO_ENTITY = {**{f["portfolio"]: f["entity"] for f in MASTER["funds"].values()}, "EG-LIQUID": "EG-TRUST"}


# ---- a small DuckDB with the model's tables ---------------------------------------------------------------------------------------------

DEFAULT = {"VARCHAR": "x", "DATE": date(2026, 10, 13), "BOOLEAN": False}


def new_db():
    con = duckdb.connect()
    con.execute((REPO / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql").read_text(encoding="utf-8"))
    return con


def ins(con, table, rows):
    """Insert dict rows (same keys in each); every other NOT NULL column gets a plain default."""
    if not rows:
        return
    have = list(rows[0])
    extra = []
    for name, typ in con.execute("select column_name, data_type from information_schema.columns where table_name = ? and is_nullable = 'NO'", [table]).fetchall():
        if name not in have:
            extra.append((name, datetime(2026, 10, 13) if typ.startswith("TIMESTAMP") else 0 if typ.startswith(("DECIMAL", "INT", "BIGINT")) else DEFAULT.get(typ, "x")))
    cols = have + [n for n, _ in extra]
    con.executemany(f"insert into {table} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})", [[r[c] for c in have] + [v for _, v in extra] for r in rows])


def d(s):
    return date.fromisoformat(str(s)[:10])


def iso(x):
    return x.date().isoformat() if isinstance(x, datetime) else str(x)[:10]


# ---- readers of the office6m files -------------------------------------------------------------------------------------------------------

def files(pattern):
    return sorted(Path(p) for p in glob.glob(str(FX / pattern)))


def load_master(con):
    """Entities, portfolios, instruments (the security master) and their identifiers."""
    ins(con, "legal_entities", [{"id": k, "organization_id": ORG, "entity_code": k, "entity_name": v, "base_currency": "USD"} for k, v in MASTER["entities"].items()])
    ins(con, "portfolios", [{"id": p, "organization_id": ORG, "legal_entity_id": e, "portfolio_code": p, "portfolio_name": p, "base_currency": "USD"} for p, e in PORTFOLIO_ENTITY.items()])
    wb = openpyxl.load_workbook(FX / "reference" / "EG_security_master_20261008.xlsx", data_only=True)
    rows = [r for r in wb["Security master"].iter_rows(min_row=5, values_only=True) if r[0] and str(r[0]).startswith(("SEC-", "FND-"))]
    ins(con, "instruments", [{"id": r[0], "organization_id": ORG, "canonical_name": r[2], "instrument_type": r[3], "asset_class": r[4], "manager_name": r[9], "currency": r[5],
                              "created_at": datetime(2026, 10, 8)} for r in rows])
    ins(con, "instrument_identifiers", [{"id": f"id-{r[0]}", "organization_id": ORG, "instrument_id": r[0], "source_system_id": "master", "identifier_type": "isin",
                                         "identifier_value": r[1], "mapping_status": "approved"} for r in rows if r[1]])
    # the security master leaves out three private funds (Evergreen Growth II, Evergreen Credit III, Saltmarsh Renewables I); their class is in master_data.json
    named = {r[2] for r in rows}
    extra = [{"id": f"FND-{k}", "organization_id": ORG, "canonical_name": f["name"], "instrument_type": "private_fund", "asset_class": f["asset_class"], "manager_name": f["manager"],
              "currency": "USD", "created_at": datetime(2026, 10, 8)} for k, f in MASTER["funds"].items() if f["name"] not in named]
    ins(con, "instruments", extra)
    return {**{r[2]: r[0] for r in rows}, **{x["canonical_name"]: x["id"] for x in extra}}, {r[6]: r[0] for r in rows if r[6]}  # by name, by trading code


def position(n, pf, inst, day, qty, mv, status, src):
    return {"id": f"{src}-{n}", "organization_id": ORG, "source_record_id": src, "portfolio_id": pf, "instrument_id": inst, "position_date": d(day), "quantity": qty,
            "source_market_value": mv, "currency": "USD", "view_type": "operational", "data_status": status, "as_of_at": datetime(2026, 10, 13), "received_at": datetime(2026, 10, 13),
            "recorded_at": datetime(2026, 10, 13)}


def load_admin(con, by_name, pattern="*/administrator_nav/administrator_export_2026-09.xlsx"):
    """Administrator packs: the Positions sheet, dated by the pack's NAV sheet (the column 'Market Value' is 'Valuation Amount (USD)' in June, M18)."""
    out, codes = [], {}
    for f in files(pattern):
        wb = openpyxl.load_workbook(f, data_only=True)
        pack_date = list(wb["NAV by portfolio"].iter_rows(min_row=2, max_row=2, values_only=True))[0][2]
        rows = list(wb["Positions"].iter_rows(values_only=True))
        head = [str(h).lower() for h in rows[0]]
        mv = next(i for i, h in enumerate(head) if "market value" in h or "valuation amount" in h)
        for n, r in enumerate(rows[1:]):
            out.append(position(n, r[0], by_name[r[2]], pack_date, r[3], r[mv], r[7], f"admin-{f.stem}"))
            codes[(by_name[r[2]], str(r[1]))] = r[1]
    ins(con, "position_snapshots", out)
    # the administrator code is an identifier too (approved): it is the only one the three funds missing from the security master have
    have = {x[0] for x in con.execute("select id from instrument_identifiers").fetchall()}
    ins(con, "instrument_identifiers", [{"id": f"adm-{i}-{c}", "organization_id": ORG, "instrument_id": i, "source_system_id": "administrator", "identifier_type": "administrator_code",
                                         "identifier_value": c, "mapping_status": "approved"} for (i, c) in codes if f"adm-{i}-{c}" not in have])


def load_custodian(con, pattern):
    out = []
    for f in files(pattern):
        for n, r in enumerate(csv.DictReader(open(f, encoding="utf-8"))):
            out.append(position(n, r["portfolio"], r["security_id"], r["as_of"], float(r["quantity"]), float(r["market_value"]), "Final", f"cust-{f.stem}"))
    ins(con, "position_snapshots", out)


def num(t, label):
    m = re.search(re.escape(label) + r"\s+(-?[\d,]+\.\d\d)", t)
    return float(m.group(1).replace(",", "")) if m else None


@lru_cache(maxsize=1)
def statements():
    """Every manager statement pdf: fund, period end, issued, status, closing balance, net gain."""
    out = []
    for f in files("*/manager_statements/*.pdf"):
        t = pypdf.PdfReader(f).pages[0].extract_text()
        g = lambda k: re.search(k + r": (.*)", t).group(1).strip()
        out.append({"id": f.stem, "fund": g("Fund"), "period_end": datetime.strptime(g(r"Statement date \(period end\)"), "%d %B %Y").date(),
                    "issued": datetime.strptime(g("Issued"), "%d %B %Y"), "status": g("Status"), "closing": num(t, "Closing capital account balance"), "gain": num(t, "Net gain / (loss)")})
    return out


def load_statements(con, by_name):
    """valuation_observations: one per statement; a later statement of the same fund and period supersedes the earlier. The net gain line is an extracted field."""
    rows, fields, last = [], [], {}
    for s in sorted(statements(), key=lambda s: (s["fund"], s["period_end"], s["issued"])):
        k = (s["fund"], s["period_end"])
        rows.append({"id": s["id"], "organization_id": ORG, "instrument_id": by_name[s["fund"]], "valuation_date": s["period_end"], "recorded_at": s["issued"],
                     "value_amount": s["closing"], "currency": "USD", "valuation_type": "statement", "approval_status": s["status"].lower(),
                     "evidence_document_id": s["id"], "supersedes_valuation_id": last.get(k), "received_at": s["issued"]})
        fields.append({"id": f"f-{s['id']}", "organization_id": ORG, "document_id": s["id"], "field_name": "net_gain_loss", "value_numeric": s["gain"], "confidence": "high",
                       "review_status": "read"})
        last[k] = s["id"]
    ins(con, "valuation_observations", rows)
    ins(con, "extracted_fields", fields)


def load_flows(con, by_name):
    """cash_movements: the capital calls and distributions the bank statements show (what actually moved), confirmed."""
    fund_port = {f["name"]: f["portfolio"] for f in MASTER["funds"].values()}
    rows = []
    for f in files("*/bank_statements/*.xlsx"):
        for r in list(openpyxl.load_workbook(f, data_only=True)["Transactions"].iter_rows(values_only=True))[1:]:
            if r and r[2] in ("capital_call", "distribution"):
                fund = max((n for n in fund_port if n in r[3]), key=len)  # "Evergreen Growth I" is inside "Evergreen Growth II"
                rows.append({"id": f"{f.stem}-{r[1]}", "organization_id": ORG, "portfolio_id": fund_port[fund], "instrument_id": by_name[fund],
                             "movement_type": "call" if r[2] == "capital_call" else "distribution", "effective_date": d(r[0]), "amount": abs(r[5]), "currency": r[6],
                             "confirmation_status": "confirmed"})
    ins(con, "cash_movements", rows)


def load_loans(con, keep_sign=False):
    rows = []
    for f in files("*/loan_statements/loan_statement_TL-B-01_*.xlsx"):
        r = list(openpyxl.load_workbook(f, data_only=True).worksheets[0].iter_rows(min_row=2, values_only=True))[0]
        y, m = map(int, r[1].split("-"))
        end = date(y + (m == 12), m % 12 + 1, 1).toordinal() - 1  # the statements show amounts negative (M12): the model holds the amount owed
        rows.append({"id": f"loan-{r[1]}", "organization_id": ORG, "facility_ref": "TL-B-01", "legal_entity_id": "EG-B", "lender": "Harbour Bank (synthetic)",
                     "facility_type": "term_loan", "currency": "USD", "drawn_amount": r[5] if keep_sign else abs(r[5]), "as_at": date.fromordinal(end), "status": "active"})
    ins(con, "credit_facilities", rows)


def load_trades(con, by_code, pattern):
    rows = []
    for f in files(pattern):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r["instrument_code"] in by_code:  # the FX forward is not a listed instrument
                rows.append({"id": r["external_trade_id"], "organization_id": ORG, "portfolio_id": r["portfolio"], "instrument_id": by_code[r["instrument_code"]],
                             "transaction_type": r["side"], "trade_date": d(r["trade_date"]), "effective_date": d(r["trade_date"]), "settlement_date": d(r["settle_date"]),
                             "cash_amount": float(r["amount"]), "currency": r["currency"], "status": r["status"]})
    ins(con, "transactions", rows)


def run(con, rid, name="gold_t", dims=None):
    r = R.recipe(rid)
    assert r and r["status"] == "ready"
    sql = R.render(r, name, R.dims_for(r, {}) if dims is None else dims)
    assert R.refusal(r, sql) is None, "the recipe reads a table outside may_read or one in never_read"
    assert R.tables_read(sql) <= set(r["may_read"])
    con.execute(sql)
    t = R.tie_out(con, r, name)
    return r, t


def rows(con, sql, *a):
    cur = con.execute(sql, list(a))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, x)) for x in cur.fetchall()]


def key(card):
    return next(iter(KEYS[card]["questions"].values()))["expected"]


ENGINE_FUNCS = {"abs": abs, "min": min, "max": max, "round": round, "last4": S.last4, "num": S.num}


def fire(sig_id, tables, doc=None, rules=None):
    """The signal's own yaml run over recipe rows the way the engine does (same parse, same condition language). -> None when an input is missing (skipped),
    False when the condition is false, else the rendered message."""
    sig = yaml.safe_load((PACK / "signals" / f"{sig_id}.yaml").read_text(encoding="utf-8"))
    ns = {"doc": {}}
    try:
        for i in sig.get("inputs", []):
            if i["kind"] == "doc":
                for f in i["fields"]:
                    if (doc or {}).get(f) in (None, ""):
                        raise S.Missing(f"doc.{f}")
                    ns["doc"][f] = doc[f]
            elif i["kind"] == "figure":
                want = {c: (ns["doc"][v.split(".")[1]] if isinstance(v, str) and v.startswith("doc.") else v) for c, v in (i.get("by") or {}).items()}
                hit = [r for r in tables[i["recipe"]] if all(r.get(c) == w for c, w in want.items())]
                if len(hit) != 1:
                    raise S.Missing(i["id"])
                ns[i["as"]] = {k: S._dec(v) for k, v in hit[0].items()}
            elif i["kind"] == "rule":
                if not (rules or {}).get(i["id"]):
                    raise S.Missing(i["id"])
                ns[i["as"]] = rules[i["id"]]
        for n, e in (sig.get("let") or {}).items():
            ns[n] = S.calc(e, ns, ENGINE_FUNCS)
        if not S.calc(sig["condition"], ns, ENGINE_FUNCS):
            return False
    except S.Missing:
        return None
    return S.render(sig["message"], ns)


def table(con, name="gold_t"):
    return rows(con, f"select * from {name}")


def leaves(x):
    """Every number and text in a part of the answer key, dict keys included."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(k)
            yield from leaves(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from leaves(v)
    else:
        yield x


# ---- card 13: securities with no asset class or identifier -----------------------------------------------------------------------------------

def gaps_db():
    con = new_db()
    by_name, _ = load_master(con)
    load_custodian(con, "*/custodian_positions/positions_20260930.csv")
    load_admin(con, by_name)
    return con, by_name


def test_13_identifier_gaps():
    con, _ = gaps_db()
    r, t = run(con, "identifier_gaps")
    assert t and t["ok"], t
    k = key("uc-013-secgaps")
    nav = key("uc-017-liab")["all_portfolios_nav"]
    gaps = rows(con, "select * from gold_t where has_gap")
    assert len(gaps) == k["count"]
    assert [g["instrument"] for g in gaps] == k["instruments"]
    assert float(gaps[0]["gap_value"]) == k["value"]
    assert gaps[0]["no_class"] and not gaps[0]["no_identifier"]
    one = rows(con, "select * from gold_t where first_row")
    assert len(one) == 1
    one = one[0]
    assert one["gap_count"] == k["count"] and float(one["gap_value_total"]) == k["value"] and float(one["net_worth"]) == nav
    assert float(one["gap_pct_of_net_worth"]) == pytest.approx(100 * k["value"] / nav, abs=1e-4) and not one["mixed_dates"]
    tables = {"identifier_gaps": table(con)}
    assert fire("uc-013-secgaps-found", tables).startswith(k["instruments"][0])
    assert fire("uc-013-secgaps-over-one-percent", tables) and fire("uc-013-secgaps-completed", tables) is False


def test_13_an_instrument_not_held_is_not_a_gap():
    """In the master only, or sold out (a zero position): no class and no identifier, but nothing is held, so it is no gap and does not change the counts."""
    con, _ = gaps_db()
    ins(con, "instruments", [{"id": i, "organization_id": ORG, "canonical_name": n, "instrument_type": "bond", "asset_class": None, "currency": "USD", "created_at": datetime(2026, 10, 8)}
                             for i, n in (("X-MASTER-ONLY", "Master only note"), ("X-SOLD", "Sold out note"))])
    ins(con, "position_snapshots", [position(0, "EG-LIQUID", "X-SOLD", "2026-09-30", 0, 0, "Final", "x-sold")])
    run(con, "identifier_gaps")
    assert not rows(con, "select * from gold_t where instrument in ('Master only note', 'Sold out note')")
    assert rows(con, "select * from gold_t where first_row")[0]["gap_count"] == key("uc-013-secgaps")["count"]


def test_13_a_position_after_the_month_end_does_not_move_the_figure():
    """Limits and allocation are measured at the month end (policy section 3): a 13 Oct custodian file is loaded but the figure stays at 30 Sep."""
    con, by_name = gaps_db()
    load_custodian(con, "*/custodian_positions/positions_20261013.csv")
    r, t = run(con, "identifier_gaps")
    assert t and t["ok"], t
    one = rows(con, "select * from gold_t where first_row")[0]
    assert not one["mixed_dates"] and str(one["as_of_min"]) == "2026-09-30" and str(one["as_of_max"]) == "2026-09-30"
    gaps = rows(con, "select * from gold_t where has_gap")
    assert [g["instrument"] for g in gaps] == key("uc-013-secgaps")["instruments"] and float(gaps[0]["gap_value"]) == key("uc-013-secgaps")["value"]
    assert "2026-09-30" in fire("uc-013-secgaps-found", {"identifier_gaps": table(con)})


# ---- card 17: net worth after debt ----------------------------------------------------------------------------------------------------------

def test_17_net_worth_after_debt():
    con = new_db()
    by_name, _ = load_master(con)
    load_admin(con, by_name, "*/administrator_nav/administrator_export_2026-*.xlsx")
    load_loans(con, keep_sign=True)  # as the statement shows it, negative (M12): the recipe takes the amount owed
    r, t = run(con, "net_worth_after_debt")
    assert t and t["ok"], t
    k = key("uc-017-liab")
    sept = rows(con, "select * from gold_t where position_date = date '2026-09-30'")
    assert sum(float(x["net_worth"]) for x in sept) == k["all_portfolios_nav"]
    assert sum(float(x["debt"]) for x in sept) == k["principal_outstanding"] == -k["loan_balance_as_shown_negative"]
    assert sum(float(x["net_worth_after_debt"]) for x in sept) == k["all_portfolios_less_debt"]
    debt = {x["entity"]: float(x["debt"]) for x in sept}
    assert debt.pop("Entity B") == k["principal_outstanding"] and not any(debt.values())  # the loan is Entity B's and nobody else's
    one = rows(con, "select * from gold_t where is_latest")
    assert len(one) == 1 and float(one[0]["family_net_worth_after_debt"]) == k["all_portfolios_less_debt"] and float(one[0]["family_debt"]) == k["principal_outstanding"]
    for month, bal in k["by_month"].items():  # the balance at each month end, as the latest statement at or before the date
        end = rows(con, "select debt from gold_t where entity = 'Entity B' and strftime(position_date, '%Y-%m') = ?", month)
        assert [float(x["debt"]) for x in end] == [-bal], month
    # the issued report counts Growth I, Income II and the liquid book; less the loan it is report_less_debt
    issued = float(con.execute("select sum(v) from (select max(source_market_value) v from position_snapshots where position_date = date '2026-09-30' and "
                               "(portfolio_id = 'EG-LIQUID' or instrument_id in ('FND-A', 'FND-B')) group by portfolio_id, instrument_id)").fetchone()[0])
    assert issued == k["report_total"] and issued - k["principal_outstanding"] == k["report_less_debt"]
    assert "owe" in fire("uc-017-liab-owed", {"net_worth_after_debt": table(con)})


def facility(ref, as_at, drawn, status="active", limit=None):
    return {"id": f"{ref}-{as_at}", "organization_id": ORG, "facility_ref": ref, "legal_entity_id": "EG-B", "lender": "Harbour Bank (synthetic)", "facility_type": "term_loan",
            "currency": "USD", "drawn_amount": drawn, "limit_amount": limit, "as_at": d(as_at), "status": status}


def test_17_facility_headroom_is_empty_when_the_agreement_states_no_limit():
    """The loan agreement names a principal, not a limit or a covenant: the headroom stays empty, the covenant signal waits for a signed line, and a signal asks for the limit."""
    con = new_db()
    load_master(con)
    load_loans(con, keep_sign=True)
    run(con, "facility_headroom")
    k = key("uc-017-liab")
    row = rows(con, "select * from gold_t")[0]
    assert row["facility_ref"] == "TL-B-01" and row["entity"] == "Entity B" and float(row["drawn_amount"]) == k["principal_outstanding"] and str(row["as_at"]) == "2026-09-30"
    assert row["limit_amount"] is None and row["headroom"] is None and row["first_row"] and row["limit_missing"]
    tables = {"facility_headroom": table(con)}
    assert fire("uc-017-liab-headroom", tables, rules={"facility_headroom_line": {"amount": 1000000}}) is None  # no limit, so no headroom: skipped, never guessed
    assert "TL-B-01" in fire("uc-017-liab-no-limit-on-record", tables)
    assert fire("uc-017-liab-drawdown", tables) is False  # the balance went down from August to September


def test_17_closed_facility_owes_nothing_and_every_facility_is_checked():
    con = new_db()
    by_name, _ = load_master(con)
    load_admin(con, by_name)
    load_loans(con)
    ins(con, "credit_facilities", [facility("TL-C", "2026-09-01", 100000, "closed"),  # closed: owes nothing whatever its last drawn figure says
                                   facility("TL-D", "2026-08-31", -400000, limit=1000000),  # a second facility, negative as a statement shows it
                                   facility("TL-D", "2026-09-30", -900000, limit=1000000)])
    r, t = run(con, "net_worth_after_debt")
    assert t and t["ok"], t
    k = key("uc-017-liab")
    one = rows(con, "select * from gold_t where is_latest")[0]
    assert float(one["family_debt"]) == k["principal_outstanding"] + 900000
    run(con, "facility_headroom", "gold_h")
    fac = rows(con, "select * from gold_h order by facility_ref")
    assert [f["facility_ref"] for f in fac] == ["TL-B-01", "TL-D"]  # the closed one is not listed
    top = rows(con, "select * from gold_h where first_row")
    assert len(top) == 1 and top[0]["facility_ref"] == "TL-D" and float(top[0]["headroom"]) == 100000  # not the latest-dated: the tightest, a limit before none
    assert top[0]["facilities_without_limit"] == 1 and top[0]["no_limit_facilities"] == "TL-B-01"
    assert float(top[0]["drawdown_total"]) == 500000 and top[0]["drawdown_facilities"] == "TL-D"
    tables = {"facility_headroom": table(con, "gold_h")}
    msg = fire("uc-017-liab-headroom", tables, rules={"facility_headroom_line": {"amount": 250000}})
    assert msg and "TL-D" in msg and "short of the line by 150,000" in msg
    assert fire("uc-017-liab-headroom", tables, rules={"facility_headroom_line": {"amount": 50000}}) is False
    assert fire("uc-017-liab-headroom", tables) is None  # no signed line on record: skipped
    assert "TL-D" in fire("uc-017-liab-drawdown", tables) and "TL-B-01" in fire("uc-017-liab-no-limit-on-record", tables)


# ---- card 21: valuations that are stale ------------------------------------------------------------------------------------------------------

def test_21_value_age_days():
    con = new_db()
    by_name, _ = load_master(con)
    load_statements(con, by_name)
    load_admin(con, by_name)
    load_custodian(con, "*/custodian_positions/positions_20261013.csv")  # the day's load: the latest position date is the as-of date, 13 Oct
    r, t = run(con, "value_age_days")
    assert t and t["ok"], t
    k = key("uc-021-stale")
    got = {x["fund"]: x for x in rows(con, "select * from gold_t")}
    for fund, e in k["by_fund"].items():
        assert str(got[fund]["valuation_date"]) == e["valuation_date"], fund
        assert got[fund]["age_days"] == e["age_days"], fund
        assert got[fund]["stale"] is e["stale"], fund
    assert sorted(f for f, x in got.items() if x["stale"]) == sorted(k["stale"])
    one = rows(con, "select * from gold_t where first_row")
    assert len(one) == 1 and one[0]["stale_count"] == len(k["stale"])
    assert one[0]["fund"] == one[0]["stalest_fund"] == max(k["by_fund"], key=lambda f: k["by_fund"][f]["age_days"])
    assert set(one[0]["stale_names"].split(", ")) == set(k["stale"])
    # an estimate is said to be one: the funds whose latest statement is only an estimate, worked out from the statement files
    st = statements()
    latest = {f: max(x["period_end"] for x in st if x["fund"] == f) for f in {x["fund"] for x in st}}
    only_estimate = {f for f, pe in latest.items() if all(x["status"].lower() == "estimate" for x in st if x["fund"] == f and x["period_end"] == pe)}
    assert only_estimate and {f for f, x in got.items() if x["is_estimate"]} == only_estimate
    assert one[0]["estimate_count"] == len(only_estimate) and set(one[0]["estimate_names"].split(", ")) == only_estimate
    assert not got["Evergreen Growth I"]["is_estimate"]  # an estimate and a later amended statement of the same date: the amended one counts
    tables = {"value_age_days": table(con)}
    found = fire("uc-021-stale-found", tables)
    assert found and all(f in found for f in k["stale"]) and "Label them stale" in found
    est = fire("uc-021-stale-estimate-only", tables)
    assert est and all(f in est for f in only_estimate)
    # the breach reads the largest stale value; the limit is the signed single-name rule
    big = max(k["stale"], key=lambda f: float(got[f]["held_pct"]))
    msg = fire("uc-021-stale-breach-on-stale", tables, rules={"single_name_limit_pct": {"value": 5}})
    assert msg and msg.startswith(big)
    assert fire("uc-021-stale-breach-on-stale", tables, rules={"single_name_limit_pct": {"value": 50}}) is False
    assert fire("uc-021-stale-breach-on-stale", tables) is None
    # a fresh statement takes a fund off the list only when it was on it
    assert fire("uc-021-stale-fresh", tables, {"fund": "Cedarpoint Ventures III"}) is False  # still stale
    assert fire("uc-021-stale-fresh", tables, {"fund": "Evergreen Growth I"}) is False  # its earlier value was not stale when this one arrived
    assert fire("uc-021-stale-fresh", tables, {"fund": "Evergreen Credit III"})  # its June value was past 90 days when the September one arrived


# ---- card 31: allocation by asset class and entity ------------------------------------------------------------------------------------------

def test_31_allocation():
    con = new_db()
    by_name, _ = load_master(con)
    load_admin(con, by_name)
    r, t = run(con, "allocation")
    assert t and t["ok"], t
    k = key("uc-031-alloc")
    total = float(con.execute("select sum(market_value) from gold_t").fetchone()[0])
    assert total == k["total"]
    for cls, v in k["by_class"].items():
        row = rows(con, "select sum(market_value) mv, sum(share_pct) p from gold_t where asset_class = ?", cls)[0]
        assert float(row["mv"]) == v, cls
        assert float(row["p"]) == pytest.approx(k["by_class_pct"][cls], abs=0.02), cls
    for ent, p in k["by_entity_pct"].items():
        assert float(rows(con, "select sum(share_pct) p from gold_t where entity = ?", ent)[0]["p"]) == pytest.approx(p, abs=0.02), ent
    assert float(rows(con, "select sum(share_pct) p from gold_t")[0]["p"]) == pytest.approx(100, abs=0.05)
    one = rows(con, "select * from gold_t where first_row")
    assert len(one) == 1 and float(one[0]["total_value"]) == float(one[0]["positions_total"]) == k["total"] and float(one[0]["unclassified_value"]) == k["by_class"]["unclassified"]
    tables = {"allocation": table(con)}
    assert fire("uc-031-alloc-ready", tables) and fire("uc-031-alloc-unclassified", tables) and fire("uc-031-alloc-not-adding-up", tables) is False
    # a position whose portfolio is unknown drops out of the join: the parts no longer add up, and the exception fires with the difference
    ins(con, "position_snapshots", [position(0, "NO-SUCH-PORTFOLIO", by_name["Evergreen Growth I"], "2026-09-30", 1, 500000, "Final", "lost")])
    run(con, "allocation", "gold_t2")
    tables = {"allocation": table(con, "gold_t2")}
    assert "500,000.00" in fire("uc-031-alloc-not-adding-up", tables) and fire("uc-031-alloc-ready", tables) is False


# ---- card 38: private fund value roll-forward ------------------------------------------------------------------------------------------------

def statement_of(fund, period_end):
    """The statement the roll-forward should rest on: not an estimate when another exists, the latest issued."""
    c = [x for x in statements() if x["fund"] == fund and x["period_end"] == period_end]
    return max([x for x in c if x["status"].lower() != "estimate"] or c, key=lambda x: x["issued"])


def quarter_gain(fund, start, end):
    """The manager's gain over (start, end]: the net gain lines of the statements dated in it. A monthly statement covers its month only."""
    months = sorted({x["period_end"] for x in statements() if x["fund"] == fund and start < x["period_end"] <= end})
    return sum(statement_of(fund, m)["gain"] for m in months)


def test_38_nav_rollforward():
    con = new_db()
    by_name, _ = load_master(con)
    load_statements(con, by_name)
    load_flows(con, by_name)
    r, t = run(con, "nav_rollforward")
    assert t and t["ok"], t
    exp = key("uc-038-navroll")["rows"]
    got = {(x["fund"], f"{x['period_start']} to {x['period_end']}"): x for x in rows(con, "select * from gold_t")}
    assert set(got) == {(e["fund"], e["quarter"]) for e in exp}
    for e in exp:
        x = got[(e["fund"], e["quarter"])]
        assert (float(x["prior_value"]), float(x["calls"]), float(x["distributions"]), float(x["closing_value"]), float(x["implied_gain"])) == \
               (e["prior"], e["calls"], e["distributions"], e["new"], e["implied_gain"]), e
        rep = quarter_gain(x["fund"], date.fromisoformat(str(x["period_start"])), date.fromisoformat(str(x["period_end"])))  # read from the statement files themselves
        assert float(x["reported_gain"]) == rep and not x["gain_unreadable"] and not x["on_estimate"], e
        assert float(x["unexplained"]) == pytest.approx(float(x["closing_value"]) - (float(x["prior_value"]) + float(x["calls"]) - float(x["distributions"]) + rep))
    assert {x["fund"] for x in rows(con, "select fund from gold_t where latest")} == {e["fund"] for e in exp}
    assert len(rows(con, "select * from gold_t where latest and fund = 'Evergreen Growth I'")) == 1
    # one of the two exception signals fires for each fund's latest quarter, the one the difference decides
    tables = {"nav_rollforward": table(con)}
    for x in rows(con, "select * from gold_t where latest"):
        doc = {"fund": x["fund"]}
        ties, unexplained = fire("uc-038-navroll-ties", tables, doc), fire("uc-038-navroll-unexplained", tables, doc)
        assert bool(ties) != bool(unexplained) and bool(unexplained) == (abs(float(x["unexplained"])) > 0.01), x["fund"]
        assert fire("uc-038-navroll-gain-unreadable", tables, doc) is False
        assert f"{float(x['implied_gain']):,.0f}" in fire("uc-038-navroll-statement", tables, doc)
    assert any(abs(float(x["unexplained"])) > 0.01 for x in got.values()) and any(abs(float(x["unexplained"])) <= 0.01 for x in got.values())
    # the tie-out compares the table with the cash movements, so it fails when the table is wrong
    con.execute("update gold_t set calls = calls + 1")
    assert not R.tie_out(con, r, "gold_t")["ok"]


def test_38_an_unread_or_doubled_gain_line_is_flagged_not_silent():
    con = new_db()
    by_name, _ = load_master(con)
    load_statements(con, by_name)
    load_flows(con, by_name)
    a, b, c = (statement_of(f, date(2026, 9, 30))["id"] for f in ("Evergreen Growth II", "Evergreen Credit III", "Saltmarsh Infrastructure Fund II"))
    ins(con, "extracted_fields", [{"id": "re-a", "organization_id": ORG, "document_id": a, "field_name": "net_gain_loss", "value_numeric": con.execute(
        "select value_numeric from extracted_fields where document_id = ?", [a]).fetchone()[0], "confidence": "high", "review_status": "read"},  # the same figure read twice
        {"id": "re-b", "organization_id": ORG, "document_id": b, "field_name": "net_gain_loss", "value_numeric": 1, "confidence": "high", "review_status": "read"}])  # a different one
    con.execute("delete from extracted_fields where document_id = ?", [c])  # not read at all
    r, t = run(con, "nav_rollforward")
    assert t and t["ok"], t
    assert len(table(con)) == len(key("uc-038-navroll")["rows"])  # a second reading does not double a quarter
    x = {f: rows(con, "select * from gold_t where fund = ? and period_end = date '2026-09-30'", f)[0]
         for f in ("Evergreen Growth II", "Evergreen Credit III", "Saltmarsh Infrastructure Fund II")}
    assert not x["Evergreen Growth II"]["gain_unreadable"] and float(x["Evergreen Growth II"]["reported_gain"]) == statement_of("Evergreen Growth II", date(2026, 9, 30))["gain"]
    tables = {"nav_rollforward": table(con)}
    for f in ("Evergreen Credit III", "Saltmarsh Infrastructure Fund II"):
        assert x[f]["gain_unreadable"] and x[f]["unexplained"] is None
        doc = {"fund": f}
        assert f in fire("uc-038-navroll-gain-unreadable", tables, doc)
        assert fire("uc-038-navroll-ties", tables, doc) is None and fire("uc-038-navroll-unexplained", tables, doc) is None


def test_38_a_quarter_on_an_estimate_is_marked_and_does_not_tie():
    con = new_db()
    by_name, _ = load_master(con)
    load_statements(con, by_name)
    load_flows(con, by_name)
    fund = "Evergreen Growth II"  # a quarterly statement: its quarter is the one statement of the quarter-end
    run(con, "nav_rollforward", "gold_before")
    prior = float(rows(con, "select closing_value from gold_before where fund = ? and period_end = date '2026-09-30'", fund)[0]["closing_value"])

    def obs(i, kind, value, recorded):
        return {"id": i, "organization_id": ORG, "instrument_id": by_name[fund], "valuation_date": date(2026, 12, 31), "recorded_at": datetime(*recorded), "received_at": datetime(*recorded),
                "value_amount": value, "currency": "USD", "valuation_type": "statement", "approval_status": kind, "evidence_document_id": i, "supersedes_valuation_id": None}

    ins(con, "valuation_observations", [obs("q4-est", "estimate", prior + 100000, (2026, 10, 13))])
    ins(con, "extracted_fields", [{"id": "q4-est-f", "organization_id": ORG, "document_id": "q4-est", "field_name": "net_gain_loss", "value_numeric": 100000, "confidence": "high", "review_status": "read"}])
    run(con, "nav_rollforward", "gold_est")
    q4 = rows(con, "select * from gold_est where fund = ? and latest", fund)[0]
    assert q4["on_estimate"] and q4["closing_status"] == "estimate" and abs(float(q4["unexplained"])) <= 0.01
    tables = {"nav_rollforward": table(con, "gold_est")}
    assert fire("uc-038-navroll-ties", tables, {"fund": fund}) is False  # it adds up, but on an estimate it is not said to tie
    # a final of the same date, recorded earlier, is preferred to the estimate
    ins(con, "valuation_observations", [obs("q4-fin", "final", prior + 100000, (2026, 10, 10))])
    ins(con, "extracted_fields", [{"id": "q4-fin-f", "organization_id": ORG, "document_id": "q4-fin", "field_name": "net_gain_loss", "value_numeric": 100000, "confidence": "high", "review_status": "read"}])
    run(con, "nav_rollforward", "gold_fin")
    q4 = rows(con, "select * from gold_fin where fund = ? and latest", fund)[0]
    assert not q4["on_estimate"] and q4["closing_status"] == "final"
    assert fire("uc-038-navroll-ties", {"nav_rollforward": table(con, "gold_fin")}, {"fund": fund})


# ---- card 43: liquid book gain or loss this month ------------------------------------------------------------------------------------------

def liquid_db(extra_positions=()):
    con = new_db()
    by_name, by_code = load_master(con)
    load_custodian(con, "*/custodian_positions/positions_2026093*.csv")
    load_custodian(con, "*/custodian_positions/positions_202610*.csv")  # every October day on file, so 13 Oct is not the first of the month
    load_trades(con, by_code, "*/trading_export/trading_export_2026100*.csv")
    return con, by_name


def test_43_liquid_pnl_mtd():
    con, _ = liquid_db()
    r, t = run(con, "liquid_pnl_mtd")
    assert t and t["ok"], t
    k = key("uc-043-liquidpnl")
    row = rows(con, "select * from gold_t")
    assert len(row) == 1
    row = row[0]
    assert row["portfolio"] == "EG-LIQUID" and str(row["position_date"]) == "2026-10-13" and str(row["month_end_date"]) == "2026-09-30"
    assert float(row["value_month_end"]) == k["value_30_sep"]
    assert float(row["value_today"]) == k["value_13_oct"]
    assert float(row["net_trades"]) == k["net_trades_settled"]
    assert float(row["gain_loss"]) == k["gain_loss_mtd"]
    assert float(row["gain_pct"]) == pytest.approx(k["gain_pct"], abs=1e-4) and row["first_row"]
    assert row["books"] == 1 and row["books_without_start"] == 0 and float(row["total_gain_loss"]) == k["gain_loss_mtd"] and not row["new_month"]
    tables = {"liquid_pnl_mtd": table(con)}
    assert f"{k['gain_loss_mtd']:,.0f}" in fire("uc-043-liquidpnl-daily", tables)
    assert fire("uc-043-liquidpnl-month-start", tables) is False  # 13 Oct is not the first position date of October


def test_43_every_book_counts_and_one_with_no_month_start_is_said_so():
    con, by_name = liquid_db()
    bond = con.execute("select id from instruments where instrument_type = 'bond' limit 1").fetchone()[0]
    other = next(f["portfolio"] for f in MASTER["funds"].values())
    ins(con, "position_snapshots", [position(0, other, bond, "2026-10-13", 10, 500000, "Final", "book2")])  # a second listed book that opened this month
    r, t = run(con, "liquid_pnl_mtd")
    assert t and t["ok"], t
    k = key("uc-043-liquidpnl")
    one = rows(con, "select * from gold_t where first_row")[0]
    assert one["portfolio"] == "EG-LIQUID" and one["books"] == 2 and one["books_without_start"] == 1
    assert float(one["total_value_today"]) == k["value_13_oct"] + 500000 and float(one["total_gain_loss"]) == k["gain_loss_mtd"]
    new = rows(con, "select * from gold_t where portfolio = ?", other)[0]
    assert new["no_month_start"] and new["gain_loss"] is None and float(new["value_today"]) == 500000
    msg = fire("uc-043-liquidpnl-daily", {"liquid_pnl_mtd": table(con)})
    assert msg.startswith("The 2 listed book(s)") and "1 book(s) have no month-end value" in msg


def test_43_the_month_start_signal_fires_on_the_first_position_date_of_the_month_only():
    con = new_db()
    load_master(con)
    load_custodian(con, "*/custodian_positions/positions_2026093*.csv")
    load_custodian(con, "*/custodian_positions/positions_20261001.csv")
    run(con, "liquid_pnl_mtd")
    row = rows(con, "select * from gold_t")[0]
    assert str(row["position_date"]) == "2026-10-01" and str(row["month_end_date"]) == "2026-09-30" and row["new_month"]
    assert f"{float(row['value_month_end']):,.0f}" in fire("uc-043-liquidpnl-month-start", {"liquid_pnl_mtd": table(con)})


def test_43_price_move_flags_nothing_here():
    """The 10 percent row of the card: no price in the 140 custodian days moved that much, so nothing is held for review."""
    con = new_db()
    load_master(con)
    load_custodian(con, "*/custodian_positions/positions_*.csv")
    run(con, "liquid_price_move")
    n, worst = con.execute("select count(*), max(abs(move_pct)) from gold_t").fetchone()
    assert n > 2000 and float(worst) < 10
    top = rows(con, "select * from gold_t where top_move")
    assert len(top) == 1 and abs(float(top[0]["move_pct"])) == float(worst) and top[0]["jump_count"] == 0
    assert con.execute("select count(*) from gold_t where abs(move_pct) > 10").fetchone()[0] == 0
    assert fire("uc-043-liquidpnl-price-jump", {"liquid_price_move": table(con)}) is False


def test_43_every_jump_is_found_not_only_the_largest_of_the_last_day():
    con = new_db()
    load_master(con)
    load_custodian(con, "*/custodian_positions/positions_20260930.csv")
    ins(con, "instruments", [{"id": "X-JUMP", "organization_id": ORG, "canonical_name": "Jumpy Corp (synthetic)", "instrument_type": "listed_equity", "currency": "USD", "created_at": datetime(2026, 10, 8)}])
    ins(con, "position_snapshots", [position(n, "EG-LIQUID", "X-JUMP", day, 1, mv, "Final", f"jump-{n}")
                                    for n, (day, mv) in enumerate([("2026-04-01", 100), ("2026-04-02", 150), ("2026-10-12", 150), ("2026-10-13", 127.5)])])
    r, t = run(con, "liquid_price_move")
    top = rows(con, "select * from gold_t where top_move")
    assert len(top) == 1 and top[0]["instrument"] == "Jumpy Corp (synthetic)" and str(top[0]["position_date"]) == "2026-04-02"  # the earlier, larger move is the one shown
    assert top[0]["jump_count"] == 2 and "2026-10-13" in top[0]["jump_names"] and "2026-04-02" in top[0]["jump_names"]  # and the one of the last day is named too
    msg = fire("uc-043-liquidpnl-price-jump", {"liquid_price_move": table(con)})
    assert msg.startswith("2 price move(s) over 10 percent") and "Jumpy Corp" in msg


# ---- the signals and the builds of the six cards --------------------------------------------------------------------------------------------

ROLES = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
FUNCS = {"abs", "min", "max", "round", "last4", "num", "same_fund"}


def signal_files():
    return sorted((PACK / "signals").glob("uc-0*.yaml"))


@pytest.mark.parametrize("card", CARDS)
def test_signals_of_the_card_are_well_formed(card):
    mine = [p for p in signal_files() if p.name.startswith(card + "-")]
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in mine]
    assert len(docs) >= 3
    assert any(s["severity"] != "info" and s.get("hold") for s in docs), "every card has at least one exception signal with a hold"
    for p, s in zip(mine, docs):
        assert s["id"] == p.stem and s["suggestion"] is True
        for kf in ("id", "title", "trigger", "condition", "severity", "route_to", "action", "message"):
            assert s.get(kf), (p.name, kf)
        trig = s["trigger"]
        assert (trig.get("on") or trig.get(True)) in {"file_arrived", "figure_changed", "date_passed", "schedule", "run", "action_done"}
        assert s["severity"] in {"info", "needs", "problem"} and s["route_to"] in ROLES
        assert s["action"]["verb"] in {"log", "record", "approve", "call_back", "see"}
        names = {n.id for n in ast.walk(ast.parse(str(s["condition"]), mode="eval")) if isinstance(n, ast.Name)}
        inputs = {i["as"] for i in s.get("inputs", []) if i.get("as")} | {"doc"} | set(s.get("let") or {})
        assert names - FUNCS <= inputs, (p.name, names - FUNCS - inputs)
        for i in s.get("inputs", []):
            if i.get("recipe"):
                assert R.recipe(i["recipe"]), (p.name, i["recipe"])


def test_builds_carry_the_exact_answer_keys():
    b = yaml.safe_load((PACK / "builds" / "hold.yaml").read_text(encoding="utf-8"))
    builds = {x["id"]: (r["id"], x) for r in b["roles"] for x in r["builds"]}
    assert set(builds) == set(CARDS)
    for card, (role, x) in builds.items():
        assert role in ROLES and x["say"] and x["files"] and x["check"]["ask"]
        assert all(f.startswith("office6m:") and glob.glob(str(FX / f[9:])) for f in x["files"]), card
        have = list(leaves(KEYS[card]["questions"]))  # this card's own block of the key, not the whole file
        numbers = [float(v) for v in have if isinstance(v, (int, float)) and not isinstance(v, bool)]
        names = {str(v) for v in have if isinstance(v, str)}
        for e in x["check"]["expect"]:
            try:
                f = float(e.replace(",", ""))
            except ValueError:
                assert e in names, (card, e)  # a name is a whole name of the key
            else:
                assert any(abs(f - v) < 1e-9 for v in numbers), (card, e)  # a number is a number of the key, sign included
        assert x["check"]["expect"], card
