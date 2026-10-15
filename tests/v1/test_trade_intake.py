"""Trade intake: trading export + administrator file into silver transactions (loader, signs, lineage, replace / append, amendment, held back,
totals) on a small synthetic company, and the UC8 July acceptance on the clean Evergreen seed (trade check compares 4, matches 4)."""
import io
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e0c_landing, e1_asof, trade_intake, wh
from sh_platform.v1.e1_write import org_id

ROOT = Path(__file__).resolve().parents[2]
JULY = ROOT / "docs" / "demo" / "uc8" / "sources" / "2026-07"
V = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")
HEAD = "external_trade_id,trade_date,settle_date,portfolio,side,instrument_code,isin,instrument_name,instrument_type,quantity,price,amount,currency,counterparty,status,source_system\n"
ADMIN_HEAD = ["Client Reference", "Row Type", "Trade Date", "Settle Date", "Portfolio", "Administrator Code", "Security", "Buy/Sell", "Quantity", "Price",
              "Gross Amount", "Currency", "Counterparty", "Status", "Booked On", "Comment"]


def csv_file(*rows):
    return (HEAD + "".join(f"{t},{d},{d},EG-LIQUID,{s},{c},,,listed_equity,{q},1,{a},USD,B,executed,OMS\n" for t, d, s, c, q, a in rows)).encode()


def admin_file(rows, total=None, count=None, period="Period: 1 July 2026 to 31 July 2026"):
    wb = Workbook()
    ws = wb.active
    ws.append(["Admin"])
    ws.append([period])
    ws.append([])
    ws.append(ADMIN_HEAD)
    for kind, tid, d, code, side, q, a in rows:
        ws.append([tid, kind, d, d, "EG-LIQUID", code, "Security", side, str(q), "1", str(a), "USD", "B", "Booked", d, None])
    ws.append([])
    ws.append(["Total gross amount, USD trades"] + [None] * 9 + [str(total if total is not None else sum(Decimal(str(r[6])) for r in rows if r[0] == "Trade"))])
    ws.append(["Trade rows"] + [None] * 9 + [count if count is not None else sum(1 for r in rows if r[0] == "Trade")])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def env(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(plane)
    with wh.connect(plane) as con:
        sys = {}
        for code, typ in (("trading_export", "OMS"), ("administrator", "administrator")):
            sys[code] = wh.new_id()
            con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?,?,?,?,?,true)", [sys[code], org, code, code, typ])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,'USD')",
                    [wh.new_id(), org, wh.new_id(), "EG-LIQUID", "Liquid"])
        for name, tick, adm in (("Meridian Foods", "MRF", "5004"), ("Bay Street Utilities", "BSU", "5003")):
            iid = wh.new_id()
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,'listed_equity',?)", [iid, org, name, wh.now()])
            for s, v in (("trading_export", tick), ("administrator", adm)):
                con.execute("insert into instrument_identifiers (id, organization_id, instrument_id, source_system_id, identifier_type, identifier_value, mapping_status) "
                            "values (?,?,?,?,'code',?,'approved')", [wh.new_id(), org, iid, sys[s], v])

    def load(data, name, mode=None):
        rec = e0c_landing.receive(plane, data, name, "ops@test")
        if mode:
            e0c_landing.set_state(plane, rec["file_id"], rec["state"], trade_mode=mode)
        return e0c_landing.load(plane, rec["file_id"], V)["last_load"]

    def rows():
        return e1_asof.snapshot(plane, "transactions", {}, None)

    return type("E", (), {"plane": plane, "load": staticmethod(load), "rows": staticmethod(rows)})


def test_trading_csv_loads_signed_rows_with_lineage(env):
    data = csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 3000), ("T-2", "2026-07-06", "sell", "BSU", 50, 900))
    r = env.load(data, "trading_export_20260706.csv")
    assert r["status"] == "loaded" and r["rows_loaded"] == 2
    t = {x["external_trade_id"]: x for x in env.rows()}
    assert (t["T-1"]["quantity_delta"], t["T-1"]["cash_amount"]) == (Decimal(100), Decimal(-3000))
    assert (t["T-2"]["quantity_delta"], t["T-2"]["cash_amount"]) == (Decimal(-50), Decimal(900))
    with wh.connect(env.plane, read_only=True) as con:  # silver row -> record (sheet, row) -> batch -> system (OMS) and the file's hash
        got = con.execute("select t.external_trade_id, r.row_number, b.id, b.content_hash, s.source_type from transactions t "
                          "join source_records r on r.id = t.source_record_id join source_batches b on b.id = r.source_batch_id "
                          "join source_systems s on s.id = b.source_system_id order by r.row_number").fetchall()
    assert [g[0] for g in got] == ["T-1", "T-2"] and [g[1] for g in got] == [2, 3] and got[0][4] == "OMS" and str(got[0][2]) == str(r["batch_id"])
    assert got[0][3] == e0c_landing.get(env.plane, r["file_id"])["sha256"]
    assert env.load(data, "trading_export_20260706.csv")["status"] == "already_loaded"


def test_replace_supersedes_and_cancels_dropped(env):
    env.load(csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 3000), ("T-2", "2026-07-06", "buy", "BSU", 50, 900)), "trading_export_20260706.csv")
    r = env.load(csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 3100)), "trading_export_20260706.csv")  # re-sent: T-1 changed, T-2 gone
    assert r["counts"] == {"written": 0, "replaced": 1, "cancelled": 1, "kept": 0}
    t = {x["external_trade_id"]: x for x in env.rows()}
    assert t["T-1"]["cash_amount"] == Decimal(-3100) and t["T-2"]["status"] == "cancelled"
    with wh.connect(env.plane, read_only=True) as con:  # history kept: old versions are superseded, not deleted
        assert con.execute("select count(*) from transactions").fetchone()[0] == 4


def test_append_keeps_existing_ids_and_adds_new(env):
    env.load(csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 3000)), "trading_export_20260706.csv")
    r = env.load(csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 9999), ("T-3", "2026-07-06", "buy", "BSU", 10, 500)), "trading_export_20260706b.csv", mode="append")
    assert r["counts"] == {"written": 1, "replaced": 0, "cancelled": 0, "kept": 1}
    assert {x["external_trade_id"]: x["cash_amount"] for x in env.rows()} == {"T-1": Decimal(-3000), "T-3": Decimal(-500)}


def test_administrator_file_amendment_and_totals(env):
    rows = [("Trade", "T-1", "2026-07-06", "5004", "buy", 100, 3000), ("Trade", "T-2", "2026-07-07", "5003", "sell", 50, 900)]
    assert env.load(admin_file(rows, total=1), "admin_2026-07.xlsx")["status"] == "rejected_totals"
    assert env.rows() == []
    r = env.load(admin_file(rows), "admin_2026-07.xlsx")
    assert r["status"] == "loaded" and r["rows_loaded"] == 2 and all(c["passed"] for c in r["control_totals"])
    a = env.load(admin_file([("Amendment", "T-1", "2026-07-06", None, None, 120, 3600)], total=0, count=0, period="Period: 1 August 2026 to 31 August 2026"), "admin_2026-08.xlsx")
    assert a["counts"]["replaced"] == 1
    t = {x["external_trade_id"]: x for x in env.rows()}
    assert (t["T-1"]["quantity_delta"], t["T-1"]["cash_amount"], t["T-1"]["status"]) == (Decimal(120), Decimal(-3600), "amended")
    assert t["T-1"]["instrument_id"] and t["T-2"]["status"] == "booked"


def test_unknown_instrument_is_held_back_rest_loads(env):
    r = env.load(csv_file(("T-1", "2026-07-06", "buy", "MRF", 100, 3000), ("T-9", "2026-07-06", "buy", "ZZZ", 1, 5)), "trading_export_20260706.csv")
    assert r["status"] == "loaded" and r["rows_loaded"] == 1 and [h["row"] for h in r["held_back"]] == [3]
    with wh.connect(env.plane, read_only=True) as con:
        assert con.execute("select quality_status from source_records where row_number = 3").fetchone()[0] == "held_back"


def test_uc8_july_trade_check_compares_4_and_matches_4(tmp_path):
    """The clean Evergreen company, the whole July folder in one action, then the existing trade check."""
    from sh_platform.v1 import e3_recon
    from tools import seed_10uc as U
    from tools import seed_evergreen as EG
    wh.reset_cache()
    root = tmp_path / "data"
    EG.seed(root)
    plane = PlaneStore(root).plane_for(EG.COMPANY).ensure()
    U._static(plane, EG.accounts(root)[0])
    res = trade_intake.load_folder(plane, JULY, V)
    assert res["administrator_trade_confirmations_2026-07.xlsx"]["rows_loaded"] == 4
    with wh.connect(plane, read_only=True) as con:
        by = dict(con.execute("select s.source_type, count(*) from transactions t join source_records r on r.id = t.source_record_id "
                              "join source_batches b on b.id = r.source_batch_id join source_systems s on s.id = b.source_system_id group by 1").fetchall())
    assert by == {"OMS": 4, "administrator": 4}
    run = e3_recon.run_detail(plane, "trade_vs_admin", "2026-07-31")
    assert run["checked"] == 8 and run["breaks"] == 0 and run["opened"] == [] and run["skipped"] == []  # 4 trades each side, 4 pairs, all matched
