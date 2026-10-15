"""E0b2: profile_sheet finds the header row, range, units, dates and totals; propose_mapping maps by rules, drops invented targets and
uses approved examples; mapping records version on a layout change and are decided by the right person; a model-change proposal is created;
the data agent's tools are registered; the evaluation set scores clean."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import e0a_catalogue, e0b_mappings as M, e0b_tools as T
from sh_platform.v1.i2_north import Refused

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "v1" / "fixtures" / "e0d"
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
HEAD = Viewer("Ravi Head", frozenset({"analyst"}), False, "acc-ravi")
READER = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-priya")
OWNER = Viewer("Sam Owner", frozenset({"owner"}), False, "acc-sam")


def wb(name):
    return FIX / "workbooks" / name


@pytest.fixture()
def plane(tmp_path):
    return PlaneStore(tmp_path / "data").create("acme")


def proposal(plane, name, by=None, **extra):
    prof = T.profile_sheet(wb(name))
    m = T.propose_mapping(plane, prof)["mapping"]
    return M.save_proposal(plane, {**m, **({"proposed_by": by} if by else {}), **extra})


def test_profile_finds_the_shape_of_every_workbook():
    for ep in sorted((FIX / "expected").glob("*.json")):
        e = json.loads(ep.read_text(encoding="utf-8"))
        p = T.profile_sheet(wb(e["workbook"]))
        assert (p["sheet"], p["header_row"], p["first_data_row"], p["last_data_row"], p["row_count"], p["exclude_rows"], p["status"]) == (
            e["sheet"], e["header_row"], e["first_data_row"], e["last_data_row"], e["control_totals"]["row_count"], e["exclude_rows"],
            "in_progress" if e["status"] == "in_progress" else "final"), e["workbook"]
        assert p["totals_match"] is e["control_totals"].get("stated_matches_rows")


def test_profile_reads_units_dates_merged_headers_and_totals():
    assert T.profile_sheet(wb("pos_2026_09_thousands.xlsx"))["units"] == "thousands"
    assert T.profile_sheet(wb("pos_2026_09_merged.xlsx"))["merged_bands"] == ["Holding", "Valuation"]

    def fmt(n):
        return next(c for c in T.profile_sheet(wb(n))["column_info"] if c["name"] == "Valuation Date")["date_format"]

    assert fmt("val_mgr_estimate_dmy.xlsx") == "%d/%m/%Y" and fmt("val_mgr_estimate_mdy.xlsx") == "%m/%d/%Y"
    bad = T.profile_sheet(wb("cash_2026_09_bad_total.xlsx"))["totals"]
    assert bad["matches"] is False and bad["stated"]["Amount"] - bad["sums"]["Amount"] == 25000
    assert T.profile_sheet(wb("val_admin_in_progress.xlsx"))["purpose"] == "valuations"


def test_rules_map_synonyms_and_transforms(plane):
    r = T.propose_mapping(plane, T.profile_sheet(wb("pos_2026_09_custodian.xlsx")))
    assert r["columns"]["Mkt Value USD"] == "position_snapshots.source_market_value" and r["source"] == "rules" and "rules only" in r["note"]
    th = T.propose_mapping(plane, T.profile_sheet(wb("pos_2026_09_thousands.xlsx")))
    assert th["columns"]["Market Value (USD 000)"] == {"target": "position_snapshots.source_market_value", "transform": {"multiply": 1000}}
    assert th["columns"]["Units"] == "position_snapshots.quantity"
    dmy = T.propose_mapping(plane, T.profile_sheet(wb("val_mgr_estimate_dmy.xlsx")))
    assert dmy["columns"]["Valuation Date"]["transform"] == {"date_format": "%d/%m/%Y"}
    assert T.propose_mapping(plane, T.profile_sheet(wb("cash_2026_09_bad_total.xlsx")))["totals_match"] is False
    assert T.propose_mapping(plane, T.profile_sheet(wb("nav_draft_in_progress.xlsx")))["status"] == "in_progress"


def test_an_invented_target_is_rejected_and_named(plane, monkeypatch):
    monkeypatch.setitem(T.DOMAINS["nav"], "status", "nav_snapshots.made_up_field")
    r = T.propose_mapping(plane, T.profile_sheet(wb("nav_admin_2026_08.xlsx")))
    assert r["columns"]["Status"] == "ignore" and r["rejected"] == [{"column": "Status", "target": "nav_snapshots.made_up_field"}]
    assert "made_up_field" in r["note"]
    with pytest.raises(Refused) as e:
        M.save_proposal(plane, {"file_name": "x.xlsx", "sheet": "S", "columns": [{"source": "A", "target_table": "nav_snapshots", "target_field": "zzz"}]})
    assert "zzz" in e.value.message


def test_the_model_places_leftover_columns_but_only_on_real_fields(plane, monkeypatch):
    prof = T.profile_sheet(wb("market_index_levels_sep.xlsx"))
    prof = {**prof, "columns": prof["columns"] + ["Venue"], "column_info": prof["column_info"] + [{"name": "Venue", "kind": "text", "date_format": None}]}
    monkeypatch.delenv("SH_MODEL_PROVIDER", raising=False)
    monkeypatch.setattr(T, "_model_targets", lambda *a: {"Venue": "market_observations.not_a_field"})
    r = T.propose_mapping(plane, prof, model=object())
    assert r["columns"]["Venue"] == "ignore" and r["rejected"][0]["target"] == "market_observations.not_a_field" and r["source"] == "rules and model"
    monkeypatch.setattr(T, "_model_targets", lambda *a: {"Venue": "market_observations.quality_status"})
    assert T.propose_mapping(plane, prof, model=object())["columns"]["Venue"] == "market_observations.quality_status"


def test_approved_mapping_is_retrieved_and_used_as_an_example(plane):
    mid = proposal(plane, "pos_2026_08_custodian.xlsx")
    assert M.get_approved(plane, "pos_2026_08_custodian.xlsx", "Positions") is None  # proposed is not approved
    M.approve(plane, mid, ENG)
    got = M.get_approved(plane, "pos_2026_09_custodian.xlsx", "positions")  # same pattern, a later month
    assert got["id"] == mid and got["version"] == 1 and got["approved_by"] == ENG.name
    sim = T.similar_approved_mappings(plane, T.profile_sheet(wb("pos_2026_09_altnames.xlsx")))
    assert [s["id"] for s in sim] == [mid] and sim[0]["score"] > 0.9
    assert T.similar_approved_mappings(plane, T.profile_sheet(wb("nav_admin_2026_08.xlsx"))) == []


def test_a_layout_change_is_a_new_version_and_old_one_is_retired_on_approval(plane):
    v1 = proposal(plane, "nav_admin_2026_08.xlsx")
    M.approve(plane, v1, ENG)
    v2 = proposal(plane, "nav_admin_2026_09.xlsx")
    rec = M.get(plane, v2)
    assert rec["version"] == 2 and rec["layout_change"] and M.get(plane, v1)["state"] == "approved"
    M.approve(plane, v2, HEAD)
    assert M.get(plane, v1)["state"] == "retired" and M.get_approved(plane, "nav_admin_2026_09.xlsx", "NAV")["id"] == v2
    same = proposal(plane, "nav_admin_2026_09.xlsx")  # the same layout again keeps the version number
    assert M.get(plane, same)["version"] == 2 and not M.get(plane, same)["layout_change"]


def test_who_may_decide(plane):
    person = {"kind": "person", "name": ENG.name, "account_id": ENG.account_id}
    mid = proposal(plane, "cash_2026_08.xlsx", by=person, owner=OWNER.name)
    with pytest.raises(Refused) as e:
        M.approve(plane, mid, ENG)  # the proposer
    assert e.value.status == 403
    with pytest.raises(Refused):
        M.approve(plane, mid, READER)  # neither the owner nor a data engineer
    with pytest.raises(Refused):
        M.reject(plane, mid, HEAD, " ")  # a reason is needed
    assert M.approve(plane, mid, OWNER)["state"] == "approved"  # the sheet owner may
    with pytest.raises(Refused) as e:
        M.approve(plane, mid, HEAD)
    assert e.value.status == 409
    other = proposal(plane, "cash_2026_08.xlsx", by=person, owner="")
    r = M.reject(plane, other, HEAD, "Wrong currency column")
    assert r["state"] == "rejected" and r["rejected_reason"] == "Wrong currency column" and M.get_approved(plane, "cash_2026_08.xlsx", "Cash")["id"] == mid


def test_model_change_proposal_is_created(plane):
    n = T.propose_model_change(plane, ENG, "Administrator sends a fee column", "Table fee_notes {\n  id uuid [pk]\n  organization_id uuid [not null]\n}\n")
    p = e0a_catalogue.proposal(plane, int(n))
    assert p["state"] == "proposed" and p["proposed_by"] == ENG.name
    with pytest.raises(Refused):
        T.propose_model_change(plane, READER, "x", "Table y {\n  id uuid [pk]\n}\n")


def test_the_data_agent_tools_are_registered(plane):
    from sh_platform.agents.registry import ToolRefused
    from sh_platform.build.agents.runtime import OpenGate
    inbox = plane.path("landing", "inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wb("pos_2026_09_custodian.xlsx"), inbox / "pos_2026_09_custodian.xlsx")
    reg = T.registry(OpenGate(), "m3_connect", plane, ENG)
    names = {t["name"] for t in reg.tools_for(plane.company_id, "m3_connect")}
    assert names == {"list_tables", "describe_table", "profile_sheet", "similar_approved_mappings", "propose_mapping", "propose_model_change"}
    assert "position_snapshots" in reg.call(plane.company_id, "m3_connect", "list_tables", {})["tables"]
    out = reg.call(plane.company_id, "m3_connect", "profile_sheet", {"file": "pos_2026_09_custodian.xlsx", "sheet": ""})
    assert out["header_row"] == "row 4" and "Mkt Value USD" in out["columns"]
    with pytest.raises(ToolRefused):
        reg.call(plane.company_id, "m3_connect", "profile_sheet", {"file": "..\\..\\secret.xlsx", "sheet": ""})


def test_the_evaluation_set_scores_clean(plane, monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT))
    from tools import eval_data_agent as ev
    monkeypatch.setenv("SH_DATA_ROOT", str(plane.root.parent))
    r = ev.score("acme", T.profile_sheet, T.propose_mapping)
    assert r["mapping_accuracy"] == 1.0 and r["invented_targets"] == 0 and r["clean"] and r["structure_ok"] == r["files"] == 21


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_routes_check_the_seats(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c

    plane = PlaneStore(data).plane_for("neera").ensure()
    person = {"kind": "person", "name": "Leela Raman", "account_id": None}
    mid = proposal(plane, "cash_2026_08.xlsx", by=person)
    leela, arjun = client("leela.raman.neera@example.test"), client("arjun.mehta.neera@example.test")
    assert [m["id"] for m in leela.get("/api/v1/model/mappings?state=proposed").json()] == [mid]
    assert leela.get(f"/api/v1/model/mappings/{mid}").json()["columns"][0]["source"] == "Date"
    assert leela.get("/api/v1/model/mappings/nope-nope").status_code == 404
    assert leela.post(f"/api/v1/model/mappings/{mid}/reject", json={"reason": ""}).status_code == 400
    assert arjun.post(f"/api/v1/model/mappings/{mid}/approve").json()["state"] == "approved"


def test_a_wrong_approved_mapping_can_be_withdrawn(plane):
    """UC5: an approved mapping that drops a needed column steps aside on a reasoned 'not right'; the file then has no mapping."""
    mid = proposal(plane, "pos_2026_08_custodian.xlsx")
    M.approve(plane, mid, ENG)
    with pytest.raises(Refused):
        M.reject(plane, mid, HEAD, " ")
    assert M.reject(plane, mid, HEAD, "The position date is not mapped.")["state"] == "retired"
    assert M.get_approved(plane, "pos_2026_08_custodian.xlsx", "Positions") is None


def test_valuation_date_on_a_positions_sheet_is_the_position_date():
    assert T.DOMAINS["positions"]["valuation date"] == "position_snapshots.position_date"


def test_the_model_never_places_a_column_on_a_key(plane, monkeypatch):
    prof = T.profile_sheet(wb("market_index_levels_sep.xlsx"))
    prof = {**prof, "columns": prof["columns"] + ["Venue"], "column_info": prof["column_info"] + [{"name": "Venue", "kind": "text", "date_format": None}]}
    monkeypatch.delenv("SH_MODEL_PROVIDER", raising=False)
    monkeypatch.setattr(T, "_model_targets", lambda *a: {"Venue": "market_observations.source_record_id"})
    r = T.propose_mapping(plane, prof, model=object())
    assert r["columns"]["Venue"] == "ignore" and r["rejected"][0]["target"] == "market_observations.source_record_id"


def test_the_model_never_fills_a_field_a_named_column_already_fills(plane, monkeypatch):
    """UC5: 'Administrator code' placed on portfolios.portfolio_code beside 'Portfolio' made every row's portfolio a code like 4473."""
    prof = T.profile_sheet(wb("market_index_levels_sep.xlsx"))
    taken = next(v for v in T._rules({**prof, "purpose": prof.get("purpose") or T.guess_purpose(prof)}).values() if v and v != "ignore")
    prof = {**prof, "columns": prof["columns"] + ["Venue"], "column_info": prof["column_info"] + [{"name": "Venue", "kind": "text", "date_format": None}]}
    monkeypatch.delenv("SH_MODEL_PROVIDER", raising=False)
    monkeypatch.setattr(T, "_model_targets", lambda *a: {"Venue": taken})
    r = T.propose_mapping(plane, prof, model=object())
    assert r["columns"]["Venue"] == "ignore" and {"column": "Venue", "target": taken} in r["rejected"]
