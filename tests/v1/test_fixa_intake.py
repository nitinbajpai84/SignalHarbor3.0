"""FIXA: intake load. The model-targets crash, ISO dates and money columns, the editable mapping, fund approval on the file page,
an honest result when nothing is written. Real landing, mapping records, matching and writer on a tmp company; no model calls."""
import types

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e0b_mappings, e0b_tools, e0c_landing as L, e0c_load, e2_match, wh
from sh_platform.v1.e1_write import org_id

ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
HEAD = Viewer("Anita Rao", frozenset({"analyst"}), False, "acc-anita")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(plane)
    with wh.connect(plane) as con:
        ent = wh.new_id()
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,'EG-HOLD','Holdings','USD')", [ent, org])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,'EG-GROWTH','g','USD')",
                    [wh.new_id(), org, ent])
        for name, kind in (("Cash", "cash"), ("Cedar Ridge Growth Fund LP", "private_fund")):
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, currency, created_at) values (?,?,?,?,'USD',?)",
                        [wh.new_id(), org, name, kind, wh.now()])

    def go(name, text, viewer=ENG):
        fid = L.receive(plane, text.encode(), name, "Leela", source_code="src")["file_id"]
        L.profile(plane, fid)
        return fid, L.load(plane, fid, viewer)["last_load"]

    def approve(fid):
        L.load(plane, fid, ENG)
        m = L.detail(plane, fid, ENG)["mapping"]
        e0b_mappings.approve(plane, m["id"], HEAD)
        return m

    return types.SimpleNamespace(plane=plane, go=go, approve=approve)


def one(plane, sql, *a):
    with wh.connect(plane) as con:
        return con.execute(sql, list(a)).fetchone()[0]


def test_model_targets_reads_the_columns_not_the_table_list(env, monkeypatch):  # B1: KeyError 'columns'
    import sh_platform.agents.loop as loop
    import sh_platform.v1.router as router
    seen = {}
    monkeypatch.setattr(router, "route", lambda *a, **k: object())
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: (seen.update(ctx=a[6]), types.SimpleNamespace(status="done", text='{"Venue": null}'))[1])
    prof = {"purpose": "cash", "column_info": [{"name": "Venue", "kind": "text"}]}
    assert e0b_tools._model_targets(env.plane, object(), prof, ["Venue"], []) == {"Venue": None}
    assert "cash_movements" in str(seen["ctx"])


ADMIN = 'as_of_date,entity_code,portfolio_code,currency,administrator_closing_cash\n2026-07-30,EG-HOLD,EG-GROWTH,USD,"2,294,786.02"\n2026-07-31,EG-HOLD,EG-GROWTH,USD,"2,305,906.48"\n'


def test_rules_read_iso_dates_and_money_and_the_cash_lands(env):  # B2 + the cash instrument
    fid, first = env.go("admin_cash_2026-07.csv", ADMIN)
    assert first["status"] == "waiting_for_mapping"
    cols = {c["source_column"]: c for c in L.detail(env.plane, fid, ENG)["mapping"]["columns"]}
    assert cols["administrator_closing_cash"]["target_field"] == "source_market_value" and cols["as_of_date"]["date_format"] == "%Y-%m-%d"
    env.approve(fid)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "loaded" and r["rows_loaded"] == 2 and "2 of 2" in r["message"]
    assert one(env.plane, "select sum(source_market_value) from position_snapshots") == pytest.approx(4600692.50)
    assert one(env.plane, "select count(*) from position_snapshots p join instruments i on i.id = p.instrument_id where i.instrument_type = 'cash'") == 2


def test_the_engineer_corrects_a_line_and_the_next_file_loads_with_it(env):  # B2 editable review, remembered per source
    text = "value date,portfolio,currency,Balance\n2026-07-31,EG-GROWTH,USD,\"1.234,50\"\n"
    fid, _ = env.go("cash_bank_2026-07.csv", text)
    m = L.detail(env.plane, fid, ENG)["mapping"]
    assert m["can_edit"] and next(c for c in m["columns"] if c["source_column"] == "Balance")["target_table"] == "ignore"
    with pytest.raises(Exception):
        e0b_mappings.edit(env.plane, m["id"], ENG, [{"source": "Balance", "target": "cash_movements.not_a_column"}])
    e0b_mappings.edit(env.plane, m["id"], ENG, [{"source": "Balance", "target": "cash_movements.amount", "decimal": ","}])
    e0b_mappings.approve(env.plane, m["id"], HEAD)
    assert L.load(env.plane, fid, ENG)["last_load"]["status"] == "loaded"
    assert one(env.plane, "select amount from cash_movements") == pytest.approx(1234.50)
    nxt = e0b_mappings.get_approved(env.plane, "cash_bank_2026-08.csv", "cash_bank_2026-08")
    assert nxt and nxt["id"] == m["id"]  # the corrected mapping is the one remembered for the next month's file


POS = "Fund name,Portfolio,Position date,Units,Market value,Currency\nCedar Ridge Growth Fund LP,EG-GROWTH,2026-07-31,10,500.5,USD\nCedar Ridge Growth Fund LP,NOPE,2026-07-31,1,1,USD\n"


def test_unapproved_fund_is_listed_with_an_approve_action_then_the_load_proceeds(env):  # B3 + honest result
    fid, _ = env.go("pos_2026-07.csv", POS)
    env.approve(fid)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "nothing_loaded" and r["rows_loaded"] == 0 and r["message"].startswith("Nothing was loaded")  # never "loaded" with 0 rows
    assert not all(c["passed"] for c in r["control_totals"]) and L.get(env.plane, fid)["state"] == "nothing_loaded"
    need = L.detail(env.plane, fid, ENG)["needs_approval"]
    fund = need["funds"][0]
    assert fund["name"] == "Cedar Ridge Growth Fund LP" and fund["identifier_id"] and need["can_approve"] and need["portfolios"] == ["NOPE"]
    e2_match.approve_alias(env.plane, fund["identifier_id"], ENG)
    assert L.detail(env.plane, fid, ENG)["needs_approval"]["funds"] == []
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "loaded" and r["rows_loaded"] == 1 and len(r["held_back"]) == 1  # the unknown portfolio stays held back, said plainly
    assert "portfolio not approved" in r["held_back"][0]["reason"]


def test_a_header_only_file_is_not_called_loaded(env):
    fid, _ = env.go("empty_2026-07.csv", "Fund name,Portfolio,Position date,Units,Market value,Currency\n")
    env.approve(fid)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "nothing_loaded" and "no data rows" in r["message"]


# ---- round 2 ----------------------------------------------------------------------------------------------------------------------

def _add_portfolio(plane, code, entity="EG-HOLD"):
    with wh.connect(plane) as con:
        eid = con.execute("select id from legal_entities where entity_code = ?", [entity]).fetchone()[0]
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,'USD')",
                    [wh.new_id(), org_id(plane), eid, code, code])


BANK = "value date,entity code,currency,net movement\n2026-07-01,EG-HOLD,USD,10.5\n2026-07-02,EG-HOLD,USD,-3\n"


def test_a_fixed_portfolio_for_the_whole_file_is_asked_for_kept_and_used(env):  # round 2, 1
    _add_portfolio(env.plane, "EG-OTHER")  # EG-HOLD now has two portfolios: the file does not say which
    fid, _ = env.go("cash_bank_EG-HOLD_2026-07.csv", BANK)
    env.approve(fid)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "nothing_loaded" and "Choose one" in r["held_back"][0]["reason"]
    ask = L.detail(env.plane, fid, ENG)["needs_approval"]["choose_portfolio"]
    assert ask == [{"entity": "EG-HOLD", "options": ["EG-GROWTH", "EG-OTHER"]}]
    mid = L.detail(env.plane, fid, ENG)["mapping"]["id"]
    with pytest.raises(Exception):
        e0b_mappings.edit(env.plane, mid, ENG, [], {"portfolios.not_a_column": "x"})
    e0b_mappings.edit(env.plane, mid, ENG, [], {"portfolios.portfolio_code": "EG-OTHER"})  # allowed on an approved mapping, columns are not
    assert L.detail(env.plane, fid, ENG)["mapping"]["fixed"] == {"portfolios.portfolio_code": "EG-OTHER"}
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["status"] == "loaded" and r["rows_loaded"] == 2
    assert one(env.plane, "select count(*) from cash_movements c join portfolios p on p.id = c.portfolio_id where p.portfolio_code = 'EG-OTHER'") == 2


def test_a_load_again_writes_only_the_rows_not_yet_in(env):  # round 2, 3: idempotent
    with wh.connect(env.plane) as con:
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, currency, created_at) values (?,?,'Northgate Credit Opportunities','private_fund','USD',?)",
                    [wh.new_id(), org_id(env.plane), wh.now()])
    text = POS.splitlines()[0] + "\nCedar Ridge Growth Fund LP,EG-GROWTH,2026-07-31,10,500.5,USD\nNorthgate Credit Opportunities,EG-GROWTH,2026-07-31,2,70,USD\n"
    fid, _ = env.go("pos_2026-07.csv", text)
    env.approve(fid)
    L.load(env.plane, fid, ENG)
    for f in L.detail(env.plane, fid, ENG)["needs_approval"]["funds"]:
        if f["name"].startswith("Cedar"):
            e2_match.approve_alias(env.plane, f["identifier_id"], ENG)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["rows_loaded"] == 1 and len(r["held_back"]) == 1  # Cedar in, Northgate waiting
    for f in L.detail(env.plane, fid, ENG)["needs_approval"]["funds"]:
        e2_match.approve_alias(env.plane, f["identifier_id"], ENG)
    r = L.load(env.plane, fid, ENG)["last_load"]
    assert r["rows_loaded"] == 1 and "already in" in r["message"]  # only the missing one, the first is not written twice
    assert one(env.plane, "select count(*) from position_snapshots") == 2
    assert L.load(env.plane, fid, ENG)["last_load"]["status"] == "already_loaded" and one(env.plane, "select count(*) from position_snapshots") == 2


def test_uncalled_uses_the_commitments_file_until_confirmed_calls_exist(env):  # round 2, 2
    from sh_platform.v1 import k6_liquidity as K
    text = "Fund name,Legal entity,Currency,Committed on,Commitment,Called to date,Uncalled\nCedar Ridge Growth Fund LP,EG-HOLD,USD,2021-03-15,\"1,000\",\"750\",250\n"
    fid, _ = env.go("commitments_2026-07-31.csv", text)
    env.approve(fid)
    L.load(env.plane, fid, ENG)
    for f in L.detail(env.plane, fid, ENG)["needs_approval"]["funds"]:
        e2_match.approve_alias(env.plane, f["identifier_id"], ENG)
    assert L.load(env.plane, fid, ENG)["last_load"]["status"] == "loaded"
    assert one(env.plane, "select called_to_date from commitments") == 750 and one(env.plane, "select called_as_at from commitments") is None  # UC6 G: kept on the commitment
    (c,) = K.commitments(env.plane)
    assert c["commitment_amount"] == 1000 and c["called"] == 750 and c["uncalled"] == 250 and "commitments file" in c["called_note"]
    from sh_platform.v1 import e1_write
    with wh.connect(env.plane) as con:
        pid = con.execute("select id from portfolios limit 1").fetchone()[0]
    e1_write.record(env.plane, "cash_movements", {"source_record_id": c["source_record_id"], "portfolio_id": str(pid), "instrument_id": c["instrument_id"], "commitment_id": c["id"], "movement_type": "call",
                                                  "notice_kind": "call", "confirmation_status": "confirmed", "amount": 100, "currency": "USD",
                                                  "effective_date": "2026-07-20", "due_date": "2026-07-20", "received_at": wh.now()})
    (c,) = K.commitments(env.plane)
    assert c["called"] == 100 and c["uncalled"] == 900 and "says 750.00 called; confirmed calls add up to 100.00" in c["called_note"]  # confirmed win


def test_a_month_of_files_loads_in_one_action(env):  # round 2, 4
    trade = ("external_trade_id,trade_date,settle_date,portfolio,side,instrument_code,isin,instrument_name,instrument_type,quantity,price,amount,currency,"
             "counterparty,status,source_system\nT1,2026-07-01,2026-07-03,EG-GROWTH,buy,ZZZ,,,listed_equity,1,1,1,USD,B,executed,OMS\n")
    out = L.load_month(env.plane, [("trades_2026-07-01.csv", trade.encode()), ("administrator_cash_2026-07.csv", ADMIN.encode())], ENG)
    assert out["trade_files"] == 1 and out["other_files"] == 1 and set(out["files"]) == {"trades_2026-07-01.csv", "administrator_cash_2026-07.csv"}
    assert out["files"]["administrator_cash_2026-07.csv"]["state"] == "waiting_for_mapping" and out["files"]["administrator_cash_2026-07.csv"]["file_id"]
    assert out["files"]["trades_2026-07-01.csv"]["state"] in ("loaded", "nothing_loaded", "quarantined") or out["files"]["trades_2026-07-01.csv"]["message"]
