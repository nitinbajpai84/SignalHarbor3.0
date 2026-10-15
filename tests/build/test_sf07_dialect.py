"""SF07: warehouse target and dialect SQL. Synthetic data; the app is the real one with the two dialect routes added in the test only."""
import json

import pytest

from sh_platform.auth.permissions import Rule
from sh_platform.build import dialect
from test_runner import FAMILY, GOOD, env, land, seeded  # noqa: F401  (fixtures)

ENV, DL = "/api/company/build/environment", "/api/company/build/dialect"


@pytest.fixture
def api(env):
    login, planes = env
    c = login("company_admin")
    app = c.app
    app.router.routes[:0] = dialect.router.routes  # ahead of the catch-all
    for k in (f"GET {DL}", f"GET {DL}/download"):
        app.state.route_permissions.routes[k] = Rule(roles=frozenset({"company_admin", "analyst"}))
    return c, planes.plane_for(FAMILY)


def landed(c, plane):
    land(plane, GOOD)
    assert c.post("/api/company/build/pipelines/trades/run").status_code == 200


def test_environment_has_the_new_question_with_no_guess(api):
    c, _ = api
    q = {x["key"]: x["answer"] for x in c.get(ENV).json()["questions"]}["warehouse_target"]
    assert q["mark"] == "unknown" and q["value"] is None


def test_no_stated_target_means_nothing_to_do(api):
    c, plane = api
    landed(c, plane)
    d = c.get(DL).json()
    assert d["state"] == "none" and d["statements"] == []
    assert c.get(DL + "/download").status_code == 409


def test_unknown_answer_is_named(api):
    c, _ = api
    c.put(ENV, json={"answers": {"warehouse_target": "Our own thing"}})
    assert c.get(DL).json()["message"] == "Not available yet: Span and Flow cannot write SQL for Our own thing yet."


def test_stated_target_transpiles_every_statement_without_literals(api):
    c, plane = api
    landed(c, plane)
    c.put(ENV, json={"answers": {"warehouse_target": "Google BigQuery"}})
    d = c.get(DL).json()
    assert d["state"] == "ready" and d["dialect"] == "bigquery"
    assert [s["name"] for s in d["statements"]] == ["trades: silver", "trades: gold.aum", "trades: gold.secret_mart"]
    assert all(s["sql"] for s in d["statements"])
    gold = next(s for s in d["statements"] if s["name"].endswith("gold.aum"))
    assert gold["changed_constructs"], "strftime/double should read differently in BigQuery"
    blob = json.dumps([s["changed_constructs"] for s in d["statements"]])
    assert "%Y-%m" not in blob and "'" not in blob and "amount" not in blob and "day" not in blob
    r = c.get(DL + "/download")
    assert r.status_code == 200 and r.text.startswith("-- DRAFT.") and "attachment" in r.headers["content-disposition"]
    assert r.text.count(";") >= 3


def test_a_statement_that_fails_is_named(api, monkeypatch):
    c, plane = api
    landed(c, plane)
    c.put(ENV, json={"answers": {"warehouse_target": "Snowflake"}})
    real = dialect.sqlglot.transpile

    def boom(sql, **kw):
        if "gold.aum" in sql:
            raise dialect.sqlglot.errors.UnsupportedError("no")
        return real(sql, **kw)
    monkeypatch.setattr(dialect.sqlglot, "transpile", boom)
    d = c.get(DL).json()
    assert d["state"] == "failed" and d["failed"] == "trades: gold.aum" and len(d["statements"]) == 1


def test_nothing_landed_yet(api):
    c, _ = api
    c.put(ENV, json={"answers": {"warehouse_target": "Redshift"}})
    assert c.get(DL).json()["state"] == "empty"
