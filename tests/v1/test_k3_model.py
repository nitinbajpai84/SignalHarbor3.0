"""DM1 The Map's Data model view: layers, prefixed names, row counts, lineage ("if this table changes"), access, and the warehouse aliases."""
import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import k3_model as M
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import wh
from sh_platform.jsonfile import write_json_atomic
from tests.v1.test_k3 import ADMIN, OUT, build

ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
GOLD = "gold_monthly_report_valuation_monthly"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    from sh_platform.v1 import k2_map
    monkeypatch.setattr(k2_map, "_model", lambda plane: None)
    monkeypatch.setattr(k2_map, "_kick", lambda *a, **k: None)
    monkeypatch.setattr(k2_map, "_groups", lambda plane: [])
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    w = build(plane)
    E.register_bronze(plane, "administrator_export", "valuations", [{"name": "isin", "type": "text"}], [w["pid"]])
    E.register_gold(plane, w["pid"], "monthly_report", "valuation_monthly", [{"name": "month", "type": "date"}])
    with wh.connect(plane) as con:
        con.execute(f"create table {GOLD} (month date)")
        con.execute(f"insert into {GOLD} values (date '2026-09-01'), (date '2026-10-01')")
        E.alias_layers(con, {t["name"] for t in E.current(plane)["tables"]})
    yield plane, w
    wh.reset_cache()


def by_id(m, tid):
    return next(t for t in m["tables"] if t["id"] == tid)


def test_three_layers_with_prefixed_names_and_counts(world):
    plane, w = world
    m = M.model(plane, ADMIN)
    assert set(m["layers"]) == {"bronze", "silver", "gold"} and all(v["meaning"] for v in m["layers"].values())
    assert {t["layer"] for t in m["tables"]} == {"bronze", "silver", "gold"}
    assert by_id(m, f"gold.{GOLD[5:]}")["rows"] == 2 and by_id(m, "bronze.administrator_export")["rows"] is None
    pos = by_id(m, "silver.valuation_observations")
    assert pos["rows"] == 3 and pos["group_label"] == "Observations" and pos["columns"] and all("type" in c for c in pos["columns"])
    assert m["counts"]["loaded"] < m["counts"]["whole"] == len(m["tables"])
    assert not [t for t in m["tables"] if t["loaded"] and not t["rows"]]


def test_if_this_table_changes_names_what_reads_it_and_gold_names_what_it_reads(world):
    plane, w = world
    m = M.model(plane, ADMIN)
    f = by_id(m, "silver.valuation_observations")["feeds"]
    assert {"kind": "table", "id": f"gold.{GOLD[5:]}", "label": f"gold.{GOLD[5:]}", "project": "Monthly investment report"} in f
    assert [x for x in f if x["kind"] in ("dashboard", "report") and x["label"] == "Net worth by month"]
    g = by_id(m, f"gold.{GOLD[5:]}")
    assert "silver.valuation_observations" in g["reads"] and "bronze.administrator_export_valuations" in g["reads"]
    assert g["project"] == "Monthly investment report" and g["owner"] == "Leela Raman"
    assert by_id(m, "bronze.administrator_export")["source"] == "Fund administrator"


def test_a_company_addition_sits_in_its_own_group_and_is_counted(world):
    plane, w = world
    E.propose(plane, ENG, add_table={"name": "manager_contacts", "note": "Who we call", "columns": [{"name": "id", "type": "uuid", "null": False}]})
    E.approve(plane, Viewer("Ada", frozenset({"company_admin"}), False, "acc-a"), 2)
    m = M.model(plane, ADMIN)
    t = by_id(m, "silver.manager_contacts")
    assert t["added"] and t["group"] == "added" and t["group_label"] == "Added for this office"
    assert m["additions"] == 1 and m["version"] == 2 and "plus 1 approved addition" in m["intro"]


def test_someone_without_the_project_sees_no_table_of_it_and_no_raw_layers(world):
    plane, w = world
    rec = P.read(plane, w["pid"])
    rec.update(sensitivity="restricted", team=[])
    write_json_atomic(P._ppath(plane, w["pid"]), rec)
    assert M.model(plane, OUT)["tables"] == []
    write_json_atomic(P._ppath(plane, w["pid"]), {**rec, "sensitivity": "open"})
    seen = M.model(plane, OUT)
    assert {t["layer"] for t in seen["tables"]} == {"gold"} and seen["team"] is False
    assert not [x for t in seen["tables"] for x in t["feeds"] if x["label"] == "Net worth by month"]  # not on that dashboard's audience


def test_aliases_are_views_over_the_real_tables_and_are_idempotent(world):
    plane, w = world
    with wh.connect(plane) as con:
        n = E.alias_layers(con, {t["name"] for t in E.current(plane)["tables"]})
        assert n >= 40
        assert con.execute(f"select count(*) from gold.{GOLD[5:]}").fetchone()[0] == 2
        assert con.execute("select count(*) from silver.valuation_observations").fetchone()[0] == 3
        kinds = {r[0] for r in con.execute("select table_type from information_schema.tables where table_schema in ('bronze','silver','gold')").fetchall()}
        assert kinds == {"VIEW"}
        assert con.execute(f"select count(*) from main.{GOLD}").fetchone()[0] == 2  # the real table keeps its name
        con.execute(f"drop table {GOLD}")
        E.alias_layers(con, {t["name"] for t in E.current(plane)["tables"]})
        assert con.execute("select count(*) from information_schema.tables where table_schema = 'gold'").fetchone()[0] == 0  # a vanished table loses its view


def test_the_layer_views_do_not_double_a_tables_columns_for_the_writers(world):
    from sh_platform.v1 import e1_asof
    plane, w = world
    with wh.connect(plane) as con:
        cols = e1_asof._columns(con, "position_snapshots")
        assert len(cols) == len(set(cols))


def test_refresh_brings_back_a_missing_view(world):
    plane, w = world
    with wh.connect(plane) as con:
        con.execute("drop view if exists gold.monthly_report_valuation_monthly")
    assert E.refresh_aliases(plane) > 0
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from gold.monthly_report_valuation_monthly").fetchone()[0] == 2


def test_the_shape_the_screen_reads_is_the_one_the_ui_fixture_holds(world):
    import json
    from pathlib import Path
    plane, _ = world
    fx = json.loads((Path(__file__).resolve().parents[2] / "ui" / "src" / "v1" / "k3" / "model.fixtures.json").read_text(encoding="utf-8"))
    m = M.model(plane, ADMIN)
    assert set(fx) == set(m) and set(fx["tables"][0]) == set(m["tables"][0]) and set(fx["tables"][0]["columns"][0]) == set(m["tables"][0]["columns"][0])
    assert set(fx["layers"]["gold"]) == set(m["layers"]["gold"])


def test_lineage_graph_has_every_kind_of_edge_and_silver_is_counted_by_project(world):
    plane, w = world
    lg = M.model(plane, ADMIN)["lineage"]
    kinds = {n["id"]: n["kind"] for n in lg["nodes"]}
    e = {(x["from"], x["to"]) for x in lg["edges"]}
    g = f"gold.{GOLD[5:]}"
    assert kinds["source:Fund administrator"] == "source" and ("source:Fund administrator", "bronze.administrator_export_valuations") in e
    assert ("bronze.administrator_export_valuations", "silver.valuation_observations") in e
    assert any(a.startswith("silver.") and b == g for a, b in e) and any(a == g and kinds[b] in ("dashboard", "report") for a, b in e)
    assert (g, f"project:{w['pid']}") in e
    assert {x["from"] for x in lg["edges"]} | {x["to"] for x in lg["edges"]} <= set(kinds)
    assert next(n for n in lg["nodes"] if n["id"] == "silver.valuation_observations")["used_by"] == 1


def test_lineage_graph_follows_access(world):
    plane, w = world
    rec = P.read(plane, w["pid"])
    write_json_atomic(P._ppath(plane, w["pid"]), {**rec, "sensitivity": "open"})
    lg = M.model(plane, OUT)["lineage"]
    assert {n["kind"] for n in lg["nodes"]} <= {"gold", "dashboard", "report", "project"}


def test_lineage_follows_what_was_loaded_with_row_counts_and_skips_empty_tables(world):
    """DM3: source -> bronze, bronze -> silver by the rows' source records; no edge for a silver table with no rows."""
    plane, w = world
    q = lambda con, sql: con.execute(sql).fetchone()[0]  # noqa: E731
    with wh.connect(plane) as con:
        org, pf, ins = q(con, "select organization_id from portfolios limit 1"), q(con, "select id from portfolios limit 1"), q(con, "select id from instruments limit 1")
        rec = q(con, "select r.id from source_records r join source_batches b on b.id = r.source_batch_id join source_systems s on s.id = b.source_system_id where s.source_code = 'administrator' limit 1")
        for i in range(2):
            con.execute("insert into position_snapshots (id, organization_id, source_record_id, portfolio_id, instrument_id, position_date, as_of_at, received_at, recorded_at, view_type, data_status) "
                        "values (?,?,?,?,?,date '2026-09-30',now(),now(),now(),'official','confirmed')", [wh.new_id(), org, rec, pf, ins])
        con.execute("insert into cash_movements (id, organization_id, source_record_id, portfolio_id, movement_type, effective_date, received_at, recorded_at, amount, currency, confirmation_status) "
                    "values (?,?,?,?,'deposit',date '2026-09-30',now(),now(),5,'USD','confirmed')", [wh.new_id(), org, rec, pf])
    lg = M.model(plane, ADMIN)["lineage"]
    e = {(x["from"], x["to"]): x.get("rows") for x in lg["edges"]}
    adm, brz = "source:Fund administrator", "bronze.administrator_export_valuations"
    assert (adm, brz) in e and e[(brz, "silver.position_snapshots")] == 2 and e[(brz, "silver.cash_movements")] == 1
    assert not any(b == "silver.transactions" for _, b in e)  # nothing loaded into it yet: no incoming edge
    assert not any(b == "silver.commitments" for _, b in e)
    with wh.connect(plane) as con:  # a trade load: a trading source, its batch and record, one transaction
        org = q(con, "select organization_id from portfolios limit 1")
        sid, bid, rid = wh.new_id(), wh.new_id(), wh.new_id()
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?,?,'trading_export','Trading system export','OMS',true)", [sid, org])
        con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, validation_status) values (?,?,?,'t1',now(),'loaded')", [bid, org, sid])
        con.execute("insert into source_records (id, organization_id, source_batch_id, record_type, received_at, recorded_at, raw_payload_uri, content_hash, quality_status) values (?,?,?,'t',now(),now(),'x','h','ok')", [rid, org, bid])
        con.execute("insert into transactions (id, organization_id, source_record_id, portfolio_id, instrument_id, transaction_type, effective_date, currency, recorded_at, status) "
                    "values (?,?,?,?,?,'buy',date '2026-09-30','USD',now(),'confirmed')", [wh.new_id(), org, rid, pf, ins])
    e = {(x["from"], x["to"]): x.get("rows") for x in M.model(plane, ADMIN)["lineage"]["edges"]}
    assert e[("source:Trading system export", "silver.transactions")] == 1
