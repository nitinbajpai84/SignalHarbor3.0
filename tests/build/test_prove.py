"""BC-6 prove and release. Synthetic gold table, reported figures and blueprint; a small app with only this router."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.build.prove import router
from sh_platform.plane import PlaneStore
from sh_platform.profile import record
from sh_platform.warehouse import open_company, refresh_readonly_copy

CO = "lakeside-family-office"
PROV = {"mark": "stated", "by": "Mei", "from": "A list"}
ACCTS = {"a-admin": ("Mei Tan", ["company_admin"]), "a-owner": ("Sara Lim", ["owner"]), "a-spon": ("Priya Rao", ["sponsor"]),
         "a-out": ("Wei Chen", ["analyst"])}


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]}

    def in_company(self, cid):
        return [{"display_name": n} for n, _ in ACCTS.values()]


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path / "planes").create(CO).ensure()
    con = open_company(plane)
    con.execute("create table gold.aum (period varchar, amount double)")
    con.execute("insert into gold.aum values ('2026-08', 100.0), ('2026-08', 50.0), ('2026-09', 70.0)")  # sums 150, 70
    con.close()
    refresh_readonly_copy(plane)
    for fid, m, fig, end in (("f1", "AUM", 150.0, "2026-08-31"), ("f2", "AUM", 90.0, "2026-09-30"), ("f3", "AUM", 10.0, "2026-10-31"),
                             ("f4", "Cash", 5.0, "2026-09-30")):
        for k, v in (("measure", m), ("figure", fig), ("period_end", end), ("owner", "Sara Lim")):
            record(plane, f"reported_figures.{fid}.{k}", v, PROV)
    bp = {"band": "now", "state": "signed", "lineage": [{"measure": "AUM", "mart": "gold.aum.amount", "transform": "sum"},
                                     {"measure": "Cash", "mart": "gold.cash.amount", "transform": "sum"}],
          "access": [{"mart": "gold.aum", "may_see": ["Mei Tan", "Sara Lim", "Priya Rao"]}, {"mart": "gold.cash", "may_see": None}]}
    plane.path("build").mkdir(parents=True, exist_ok=True)
    plane.path("build", "blueprint.json").write_text(json.dumps(bp), encoding="utf-8")
    app = FastAPI()
    app.include_router(router)
    app.state.settings = type("S", (), {"data_root": tmp_path / "planes"})()
    app.state.account_store = Accounts()

    @app.middleware("http")
    async def who(request, call_next):
        request.state.company_id, request.state.account_id = CO, request.headers["x-acct"]
        request.state.roles = ACCTS[request.headers["x-acct"]][1]
        return await call_next(request)

    return TestClient(app), plane


def H(a):
    return {"x-acct": a}


def prove_json(plane):
    return json.loads(plane.path("build", "prove.json").read_text(encoding="utf-8"))


def test_match_gap_not_yet(env):
    c, _ = env
    ms = {m["code"]: m for m in c.get("/api/company/build/prove", headers=H("a-admin")).json()["measures"]}
    aum = {p["period"]: p for p in ms["AUM"]["periods"]}
    assert aum["2026-08"]["result"] == "match" and aum["2026-08"]["ours"] == 150.0
    assert aum["2026-09"]["result"] == "gap" and aum["2026-09"]["reason"]
    assert aum["2026-10"]["result"] == "not_yet"  # the mart has no October
    assert ms["Cash"]["periods"][0]["result"] == "not_yet"  # no gold.cash table at all


def test_accept_by_owner_then_release_refused_until_ready(env):
    c, plane = env
    c.get("/api/company/build/prove", headers=H("a-admin"))
    assert c.post("/api/company/build/prove/AUM/accept", json={"reason": "Custodian rounds"}, headers=H("a-out")).status_code == 403
    assert c.post("/api/company/build/prove/AUM/accept", json={"reason": "Custodian rounds"}, headers=H("a-owner")).status_code == 200
    p = {x["period"]: x for x in prove_json(plane)["measures"][0]["periods"]}
    assert p["2026-09"]["accepted_by"] == "Sara Lim" and p["2026-09"]["reason"] == "Custodian rounds"
    r = c.post("/api/company/build/release/sign", headers=H("a-spon"))
    assert r.status_code == 409 and "AUM" in r.json()["detail"] and "Cash" in r.json()["detail"]
    assert c.post("/api/company/build/release/sign", headers=H("a-admin")).status_code == 403


def test_release_signs_when_all_ready_and_uat_kept(env):
    c, plane = env
    con = open_company(plane)
    con.execute("create table gold.cash (period varchar, amount double)")
    con.execute("insert into gold.cash values ('2026-09', 5.0)")
    con.execute("update gold.aum set amount = 90.0 where period = '2026-09'")
    con.execute("insert into gold.aum values ('2026-10', 10.0)")
    con.close()
    refresh_readonly_copy(plane)
    c.post("/api/company/build/prove/recheck", json={"reason": "Mart loaded"}, headers=H("a-admin"))
    doc = prove_json(plane)
    for m in doc["measures"]:
        m["uat"] = {"state": "signed", "by": "Sara Lim", "at": "2026-10-07T09:00:00+00:00", "note": "ok"}
    plane.path("build", "prove.json").write_text(json.dumps(doc), encoding="utf-8")
    assert all(m["release_ready"] for m in c.get("/api/company/build/prove", headers=H("a-admin")).json()["measures"])
    assert c.post("/api/company/build/release/sign", headers=H("a-spon")).status_code == 200
    after = prove_json(plane)
    assert after["release"]["state"] == "signed" and after["measures"][0]["uat"]["state"] == "signed"


def test_viewer_outside_list_gets_no_figures(env):
    c, _ = env
    ms = {m["code"]: m for m in c.get("/api/company/build/prove", headers=H("a-out")).json()["measures"]}
    p = ms["AUM"]["periods"][0]
    assert p["ours"] is None and p["reported"] is None and p["result"] == "match"
    assert ms["Cash"]["periods"][0]["reported"] == 5.0  # open mart (may_see null)


def _signed(c, plane):
    """AUM's periods stored by an explicit act (the re-check), then its signature."""
    assert c.post("/api/company/build/prove/recheck", json={"reason": "First check"}, headers=H("a-admin")).status_code == 200
    doc = prove_json(plane)
    doc["measures"][0]["uat"] = {"state": "signed", "by": "Sara Lim", "at": "2026-10-07T09:00:00+00:00", "note": "ok"}
    plane.path("build", "prove.json").write_text(json.dumps(doc), encoding="utf-8")


def test_a_read_never_writes_even_when_the_result_changes(env):
    c, plane = env
    c.get("/api/company/build/prove", headers=H("a-admin"))
    assert not plane.path("build", "prove.json").exists()  # the first read creates nothing
    _signed(c, plane)
    f = plane.path("build", "prove.json")
    before = f.read_bytes()
    con = open_company(plane)
    con.execute("update gold.aum set amount = 1.0 where period = '2026-08' and amount = 100.0")  # August match -> gap
    con.close()
    refresh_readonly_copy(plane)
    m = c.get("/api/company/build/prove", headers=H("a-admin")).json()["measures"][0]
    assert f.read_bytes() == before  # the read changed nothing
    assert m["uat"]["state"] == "signed" and m["changed"] == ["2026-08"] and not m["release_ready"] and m["waits_for"].startswith("a re-check")
    assert c.post("/api/company/build/prove/AUM/accept", json={"reason": "x"}, headers=H("a-owner")).status_code == 409


def test_recheck_needs_a_reason_and_a_named_person_and_writes_a_version_line(env):
    c, plane = env
    _signed(c, plane)
    con = open_company(plane)
    con.execute("update gold.aum set amount = 1.0 where period = '2026-08' and amount = 100.0")
    con.close()
    refresh_readonly_copy(plane)
    assert c.post("/api/company/build/prove/recheck", json={"reason": " "}, headers=H("a-admin")).status_code == 422
    assert c.post("/api/company/build/prove/recheck", json={"reason": "Mart reloaded"}, headers=H("a-owner")).status_code == 403
    r = c.post("/api/company/build/prove/recheck", json={"reason": "Mart reloaded"}, headers=H("a-admin"))
    line = r.json()["checks"][-1]
    assert line["version"] == 2 and line["by"] == "Mei Tan" and line["reason"] == "Mart reloaded" and line["voided"] == ["AUM"]
    m = prove_json(plane)["measures"][0]
    assert m["uat"]["state"] == "pending" and "re-checked" in m["uat"]["note"] and "changed" not in m
    again = c.post("/api/company/build/prove/recheck", json={"reason": "Again"}, headers=H("a-admin")).json()["checks"]
    assert len(again) == 2  # nothing moved: no new line


def test_a_move_to_a_match_keeps_the_signature(env):
    c, plane = env
    _signed(c, plane)
    con = open_company(plane)
    con.execute("update gold.aum set amount = 90.0 where period = '2026-09'")  # September gap -> match
    con.close()
    refresh_readonly_copy(plane)
    c.post("/api/company/build/prove/recheck", json={"reason": "Mart reloaded"}, headers=H("a-admin"))
    m = prove_json(plane)["measures"][0]
    assert m["uat"]["state"] == "signed" and {p["period"]: p["result"] for p in m["periods"]}["2026-09"] == "match"


def test_release_refused_without_signed_blueprint(env):
    c, plane = env
    p = plane.path("build", "blueprint.json")
    bp = json.loads(p.read_text(encoding="utf-8"))
    bp["state"] = "draft"
    p.write_text(json.dumps(bp), encoding="utf-8")
    r = c.post("/api/company/build/release/sign", headers=H("a-spon"))
    assert r.status_code == 409 and "blueprint is not signed" in r.json()["detail"]


def test_partial_release_names_released_and_held_back(env):
    c, plane = env
    con = open_company(plane)
    con.execute("create table gold.cash (period varchar, amount double)")
    con.execute("insert into gold.cash values ('2026-09', 5.0)")
    con.close()
    refresh_readonly_copy(plane)
    assert c.post("/api/company/build/release/sign", headers=H("a-spon")).status_code == 409  # nothing ready yet
    c.post("/api/company/build/prove/recheck", json={"reason": "Mart loaded"}, headers=H("a-admin"))
    doc = prove_json(plane)
    for m in doc["measures"]:
        if m["code"] == "Cash":
            m["uat"] = {"state": "signed", "by": "Sara Lim", "at": "2026-10-07T09:00:00+00:00", "note": "ok"}
    plane.path("build", "prove.json").write_text(json.dumps(doc), encoding="utf-8")
    r = c.post("/api/company/build/release/sign", headers=H("a-spon"))
    assert r.status_code == 200 and r.json()["released"] == ["Cash"] and r.json()["state"] == "signed"
    assert r.json()["held_back"] == [{"code": "AUM", "reason": "waits for its figure"}]
    assert prove_json(plane)["release"]["released"] == ["Cash"]
