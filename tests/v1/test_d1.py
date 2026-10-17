"""D1: layers in the catalogue. layer_of, tables_for_project, columns_of, bronze and gold registration, the demo bronze start, the routes."""
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1.i2_north import Refused


@pytest.fixture()
def plane(tmp_path):
    return PlaneStore(tmp_path / "data").create("acme")


def test_silver_is_the_core_model_and_unknown_is_none(plane):
    assert E.layer_of(plane, "organizations") == "silver" and E.layer_of(plane, "nope") is None
    assert len(E.tables_for_project(plane, "prj-1")["silver"]) == 60
    assert E.tables_for_project(plane, "prj-1")["bronze"] == [] and E.tables_for_project(plane, "prj-1")["gold"] == []


def test_bronze_naming_layer_and_project_link(plane):
    r = E.register_bronze(plane, "administrator", "export", [{"name": "isin", "type": "text"}], project_ids=["prj-1"])
    assert r["name"] == "bronze_administrator_export" and E.layer_of(plane, r["name"]) == "bronze"
    E.register_bronze(plane, "administrator", "export", project_ids=["prj-2"])  # merges, keeps columns
    assert E.columns_of(plane, "bronze_administrator_export") == ["isin"]
    assert E.tables_for_project(plane, "prj-2")["bronze"] == ["bronze_administrator_export"] == E.tables_for_project(plane, "prj-1")["bronze"]
    assert E.tables_for_project(plane, "prj-3")["bronze"] == []
    with pytest.raises(Refused):
        E.register_bronze(plane, "Bad Code", "export")


def test_gold_belongs_to_one_project(plane):
    E.register_gold(plane, "prj-1", "evergreen_report", "holdings_monthly", [{"name": "entity", "type": "text"}])
    n = "gold_evergreen_report_holdings_monthly"
    assert E.layer_of(plane, n) == "gold" and E.tables_for_project(plane, "prj-1")["gold"] == [n]
    assert E.tables_for_project(plane, "prj-2")["gold"] == []
    assert E.columns_of(plane, n) == ["entity"] and E.columns_of(plane, "organizations")[0] == "id" and E.columns_of(plane, "nope") is None
    with pytest.raises(Refused):
        E.register_gold(plane, "prj-1", "evergreen_report", "bad name")
    with pytest.raises(Refused):  # same table name cannot be taken over by a project with another short name
        E._register(plane, n, {"layer": "gold", "project_slug": "other", "project_ids": ["prj-9"], "columns": []})


def test_slug_and_demo_bronze_and_view(plane):
    assert E.slug_of("Monthly investment report in USD & SGD!") == "monthly_investment_report_in_u"
    names = E.seed_demo_bronze(plane)
    assert names == ["bronze_administrator_export", "bronze_trading_export_export", "bronze_manager_email_statement"]
    E.seed_demo_bronze(plane)  # idempotent
    v = E.catalogue_view(plane)["layers"]
    assert [t["name"] for t in v["bronze"]] == sorted(names) and v["silver"]["tables"] == 60 and v["gold"] == []
