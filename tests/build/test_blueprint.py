"""BC-3: the blueprint. Synthetic data only. Fixtures come from tests/build_env (the same seeded app and logins)."""
import importlib.util
import sys
from pathlib import Path

import pytest

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore

_dir = Path(__file__).resolve().parents[1] / "build_env"
sys.path.insert(0, str(_dir))
_spec = importlib.util.spec_from_file_location("be_conftest", _dir / "conftest.py")
_be = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_be)
seeded, env, stub = _be.seeded, _be.env, _be.stub
from pf_kit import FAMILY, OTHER  # noqa: E402

URL = "/api/company/build/blueprint"
BID = "a" * 32


def p(v, mark="stated"):
    return {"value": v, "mark": mark, "by": "Dan Data", "from": "test", "at": "2026-09-01T00:00:00+00:00"}


def seed_baseline(env, state="signed"):
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY).ensure()
    d = plane.path("intents", "m2_baseline", BID)
    write_json_atomic(d / "baseline.json", {"id": BID, "state": state, "created_at": "2026-09-01"})
    tech = {"sources": p("S01"), "fields": p("F001 F002"), "calculation": p("Sum of market value over total"), "grain": p("One row per account per day")}
    gov = {"personal": "no", "sensitive": False, "may_see": []}
    write_json_atomic(d / "kpis.json", [
        {"id": "K1", "name": "Total value", "technical": tech, "governance": gov},
        {"id": "K2", "name": "Pay cost", "technical": {**tech, "grain": p("One row per person per month")},
         "governance": {"personal": "yes", "sensitive": True, "may_see": ["Nobody Else"]}}])
    write_json_atomic(d / "catalogue.json", {
        "sources": [{"Source ID": p("S01"), "Source name": p("Custody feed"), "Expected arrival time or SLA": p("D+2 09:00")}],
        "tables": [{"Item ID": p("T01"), "Source ID": p("S01")}],
        "fields": [{"Field ID": p("F001"), "Item ID": p("T01"), "Field name as in the source": p("Account id"), "Feeds KPI": p("K1")},
                   {"Field ID": p("F002"), "Item ID": p("T01"), "Field name as in the source": p("Mkt Value"), "Feeds KPI": p("K1"), "Valid from": p("2026-01-01")}],
        "extractions": [], "kpis": []})
    write_json_atomic(d / "quality_rules.json", {"rules": {"K1": [{"id": "r1", "kind": "fill_rate", "text": "Market value is half empty"}]}})


def test_draft_has_facts_dimensions_lineage_and_marks(env):
    seed_baseline(env)
    r = env.login("company_admin").get(URL)
    assert r.status_code == 200
    b = r.json()
    assert b["version"] == 1 and b["state"] == "draft"
    assert {f["name"] for f in b["model"]["facts"]} == {"fact_account_day", "fact_person_month"}
    assert {"dim_account", "dim_day", "dim_person", "dim_month"} == {d["name"] for d in b["model"]["dimensions"]}
    line = next(x for x in b["lineage"] if x["measure"] == "K1")
    assert line["source"] == "Custody feed" and line["fields"] == ["Account id", "Mkt Value"] and line["mart"] == "gold.k1.total_value"
    assert any(x["from"] == "scan" for x in b["rules"]) and b["schedule"][0]["expected"] == "D+2 09:00"
    assert b["infra"] == {"warehouse": "plane", "runner": "builtin"}
    assert set(b["provenance"]) >= {"model.facts.0.grain", "lineage.0.transform", "infra.runner", "schedule.0.sla"}
    assert all(m["mark"] in ("guessed", "stated") and m["from"] for m in b["provenance"].values())


def test_sign_makes_it_read_only_and_a_later_edit_makes_version_2(env):
    seed_baseline(env)
    admin = env.login("company_admin")
    admin.get(URL)
    s = admin.post(URL + "/sign").json()
    assert s["state"] == "signed" and s["signed_by"][0]["role"] == "Company admin" and s["signed_by"][0]["name"]
    assert admin.post(URL + "/sign").status_code == 409
    r = admin.put(URL, json={"path": "infra.runner", "value": "airflow"})
    assert r.status_code == 200
    v2 = r.json()
    assert v2["version"] == 2 and v2["state"] == "draft" and v2["signed_by"] == [] and v2["infra"]["runner"] == "airflow"
    assert v2["provenance"]["infra.runner"]["mark"] == "stated" and v2["provenance"]["infra.runner"]["by"]
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    assert (plane.path("build", "blueprint.v1.json")).is_file()
    assert admin.put(URL, json={"path": "nope", "value": "x"}).status_code == 422
    assert admin.put(URL, json={"path": "rules.0.severity", "value": "loud"}).status_code == 422


def test_restricted_measure_is_hidden_from_an_analyst_not_on_its_list(env):
    seed_baseline(env)
    b = env.login("analyst").get(URL).json()
    assert any(r == {"hidden": True} for r in b["access"]) and all("K2" not in f["measures"] for f in b["model"]["facts"])
    assert env.login("analyst").put(URL, json={"path": "access.1.may_see", "value": []}).status_code == 403


def test_another_company_and_a_closed_space_get_nothing(env, monkeypatch):
    seed_baseline(env)
    env.login("company_admin").get(URL)
    assert env.login("company_admin", OTHER).get(URL).json()["state"] == "none"  # no baseline of its own: nothing of the family's
    assert env.login("sponsor").get(URL).status_code == 403
    import sh_platform.build.blueprint as bp
    monkeypatch.setattr(bp, "_plane", lambda request: (_ for _ in ()).throw(PermissionError("no company space")))
    assert env.login("company_admin").get(URL).status_code == 403


def test_drafts_from_a_draft_baseline_and_says_so(env):
    seed_baseline(env, "draft")
    admin = env.login("company_admin")
    b = admin.get(URL).json()
    assert b["basis"] == "draft baseline" and b["state"] == "draft" and len(b["model"]["facts"]) == 2


def test_sign_is_refused_until_the_baseline_is_signed_then_it_redrafts(env):
    seed_baseline(env, "draft")
    admin = env.login("company_admin")
    admin.get(URL)
    r = admin.post(URL + "/sign")
    assert r.status_code == 409 and "Sign the baseline first" in r.json()["message"]
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    write_json_atomic(plane.path("intents", "m2_baseline", BID, "baseline.json"), {"id": BID, "state": "signed", "created_at": "2026-09-01"})
    assert "basis" not in admin.get(URL).json()
    assert admin.post(URL + "/sign").json()["state"] == "signed"
