"""Build the synthetic Neera landing files from the Neera warehouse (read-only).

Writes data/neera/landing/<source>/ and a copy at tools/samples/neera/.
Run: python tools/make_samples_neera.py
"""
import csv
import random
import shutil
from pathlib import Path

import duckdb
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
LAND = ROOT / "data" / "neera" / "landing"
COPY = ROOT / "tools" / "samples" / "neera"
SOURCES = ["custodian_positions", "custodian_transactions", "custodian_fees", "bank_cash", "ledger", "benchmark", "clients"]
CUSTODIANS = {"C1": "Harbourline Custody", "C2": "Meridian Trust Services", "C3": "Strait Custodial Bank"}

db = duckdb.connect(str(ROOT / "data/neera/warehouse/company.duckdb"), read_only=True)


def rows(sql):
    cur = db.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def write(path, header, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)


# 1. Custodian positions, one file per month (13).
# Quirks: price_local renamed unit_price from 2026-02; no currency column in 2026-01; one duplicate row in 2025-12.
_, pos = rows("""select p.period, p.holding_id, h.name, h.custodian_id, p.quantity, p.price_local, p.currency,
  p.market_value_local, p.valuation_date from silver.valuations_positions_monthly p
  join silver.master_holdings h using (holding_id) order by p.period, p.holding_id""")
periods = sorted({r[0] for r in pos})
for per in periods:
    body = [list(r[1:]) for r in pos if r[0] == per]
    head = ["holding_id", "holding_name", "custodian_id", "quantity", "price_local", "currency", "market_value_local", "valuation_date"]
    if per >= "2026-02":
        head[head.index("price_local")] = "unit_price"
    if per == "2026-01":
        i = head.index("currency")
        head.pop(i)
        for b in body:
            b.pop(i)
    if per == "2025-12":
        body.insert(6, list(body[5]))
    write(LAND / "custodian_positions" / f"positions_{per}.csv", head, body)

# 2. Transactions: all months in one file.
_, trd = rows("""select t.trade_date, t.holding_id, h.custodian_id, t.side, t.units, m.close_price_local, h.currency
  from silver.valuations_trades_monthly t join silver.master_holdings h using (holding_id)
  join silver.valuations_month_end_prices m on m.period = t.period and m.holding_id = t.holding_id
  order by t.trade_date, t.holding_id""")
write(LAND / "custodian_transactions" / "transactions_2025-10_to_2026-09.csv",
      ["trade_date", "holding_id", "custodian_id", "side", "units", "price_local", "currency", "gross_amount_local"],
      [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], round(r[4] * r[5], 2)] for r in trd])

# 3. Fee schedule (what the custody fee accruals imply) and monthly invoices.
_, fees = rows("select distinct custodian_id, tier, rate_bp_annual from silver.custody_daily_fee_accruals order by 1")
write(LAND / "custodian_fees" / "fee_schedule.csv",
      ["custodian_id", "custodian_name", "tier", "rate_bp_annual", "assets_to_sgd", "effective_from"],
      [[c, CUSTODIANS[c], t, bp, "400000000" if t == "below 400m" else "", "2025-09-01"] for c, t, bp in fees])
_, inv = rows("select invoice_no, custodian_id, period, issue_date, days, mean_assets_sgd, fee_sgd, other_charges_sgd, invoice_total_sgd from silver.custody_monthly_invoices order by period, custodian_id")
write(LAND / "custodian_fees" / "invoices_2025-09_to_2026-09.csv",
      ["invoice_no", "custodian_id", "period", "issue_date", "days", "mean_assets_sgd", "fee_sgd", "other_charges_sgd", "invoice_total_sgd"], inv)

# 4. Bank cash balances, month end (statement basis to 2026-06, daily-derived from 2026-07).
_, cash = rows("select period, account_id, entity_id, currency, month_end_balance, basis from silver.treasury_monthly_cash_balances order by period, account_id")
write(LAND / "bank_cash" / "cash_balances_2025-09_to_2026-09.csv",
      ["period", "account_id", "entity_id", "currency", "month_end_balance", "basis"], cash)

# 5. General ledger trial balance, one XLSX, two sheets.
_, inv_cls = rows("""select p.period, h.asset_class, sum(p.market_value_sgd) from silver.valuations_positions_monthly p
  join silver.master_holdings h using (holding_id) group by 1,2 order by 1,2""")
_, cashsgd = rows("""select c.period, sum(c.month_end_balance * coalesce(f.fx, 1)) from silver.treasury_monthly_cash_balances c
  left join (select 'USD' cur, period, usd_sgd fx from silver.fx_month_end_rates
   union all select 'EUR', period, eur_sgd from silver.fx_month_end_rates) f on f.cur = c.currency and f.period = c.period
  group by 1 order by 1""")
accts = {"Listed equity": ("1110", "Investments: listed equity"), "Bond fund": ("1120", "Investments: bond funds"),
         "Private market fund": ("1130", "Investments: private market funds"), "Money market fund": ("1140", "Investments: money market funds")}
wb = openpyxl.Workbook()
tb = wb.active
tb.title = "Trial balance"
tb.append(["period", "account_code", "account_name", "debit_sgd", "credit_sgd"])
fee_by = dict(db.execute("select period, sum(invoice_total_sgd) from silver.custody_monthly_invoices group by 1").fetchall())
cash_by = dict(cashsgd)
for per in periods:
    lines = [(accts[a][0], accts[a][1], round(v, 2), 0.0) for p, a, v in inv_cls if p == per]
    lines.append(("1010", "Bank and cash", round(cash_by[per], 2), 0.0))
    lines.append(("5100", "Custody fees expense", round(fee_by[per], 2), 0.0))
    lines.append(("2100", "Accrued custody fees", 0.0, round(fee_by[per], 2)))
    lines.append(("3900", "Net assets of the family", 0.0, round(sum(x[2] for x in lines) - sum(x[3] for x in lines), 2)))
    for code, name, d, c in lines:
        tb.append([per, code, name, d, c])
coa = wb.create_sheet("Chart of accounts")
coa.append(["account_code", "account_name", "type", "reporting_use"])
for r in [("1010", "Bank and cash", "asset", "cash balance and cash drag"), ("1110", "Investments: listed equity", "asset", "market value"),
          ("1120", "Investments: bond funds", "asset", "market value"), ("1130", "Investments: private market funds", "asset", "market value, stale valuation"),
          ("1140", "Investments: money market funds", "asset", "market value, cash drag"), ("2100", "Accrued custody fees", "liability", "fee ratio"),
          ("3900", "Net assets of the family", "equity", "balancing line"), ("5100", "Custody fees expense", "expense", "fee ratio")]:
    coa.append(list(r))
(LAND / "ledger").mkdir(parents=True, exist_ok=True)
wb.save(LAND / "ledger" / "trial_balance_2025-09_to_2026-09.xlsx")

# 6. Benchmark prices: month-end index levels (synthetic, seeded).
rnd = random.Random(7)
lv = {"NEERA-EQ": 1000.0, "NEERA-BOND": 1000.0, "NEERA-CASH": 1000.0}
drift = {"NEERA-EQ": (0.008, 0.03), "NEERA-BOND": (0.003, 0.01), "NEERA-CASH": (0.0025, 0.0005)}
bm = []
for per in periods:
    for k in lv:
        if per != periods[0]:
            lv[k] *= 1 + rnd.gauss(*drift[k])
        bm.append([per, k, round(lv[k], 2), "SGD"])
write(LAND / "benchmark" / "benchmark_prices_2025-09_to_2026-09.csv", ["period", "index_code", "close_level", "currency"], bm)

# 7. Client list: the family readers.
_, cl = rows("select reader_id, name, relation, generation, receives_report from silver.master_family_readers order by 1")
write(LAND / "clients" / "client_list.csv", ["reader_id", "name", "relation", "generation", "receives_report"], cl)

# Copy for seeds.
for s in SOURCES:
    shutil.copytree(LAND / s, COPY / s, dirs_exist_ok=True)
print("ok", sum(1 for p in COPY.rglob("*") if p.is_file()), "files")
