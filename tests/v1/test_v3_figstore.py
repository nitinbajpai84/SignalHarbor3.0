"""Figure records (sh_platform/v1/v3_figstore.py, docs/v3/STEP1-DECISION-SCHEMAS.md): made at Decision 1, reused when the person accepts, checked at Decision 3,
a run appended each live run, a held new version leaves the last verified one current, the answer names its figure, rollback is for an admin or the approver.
Real: the store, the routes, the permissions. Stubbed: the brief's figures, the pack and the warehouse copy."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import b9_verify as V, v3_figstore as FS, v3_figures as F, v3_recipes as R, v3_skills as SK  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"
KPIS = [{"name": "Cash break", "definition": "Cash the bank shows less cash the books show", "built_from": "cash_break"}]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    st = AccountStore(data)
    st.create("sam@evergreen.example.test", PW, "Sam Lee", "evergreen", ["participant"])
    st.create("boss@evergreen.example.test", PW, "Bo Boss", "evergreen", ["company_admin"])
    plane = PlaneStore(str(data)).plane_for("evergreen").ensure()
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: KPIS)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    return app, plane


def login(app, email) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def thread(tid="t1", title="Cash break every morning"):
    return {"id": tid, "title": title, "iid": "ini-1", "pid": "prj-1", "figs": {}}


def x_of(plane, th, ok=True, rows=3, reason=""):
    th["figures"] = [{"kpi": "Cash break", "table": "g", "rows": rows, "ok": ok, "reason": reason}]
    th["run_id"] = "run-" + th["id"]
    pack = {"pack": {"target": {"gold": [{"name": "g", "sql": "create table g as select * from cash_movements"}]}}}
    return SimpleNamespace(th=th, plane=plane, api=lambda *a, **k: pack)


def stub_tie(monkeypatch, ok):
    monkeypatch.setattr(V, "_copy", lambda plane: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(R, "tie_out", lambda con, r, name: {"ok": ok, "label": "Cash break ties to the bank", "a": 1.0, "b": 1.0 if ok else 2.0})


def verified(plane, monkeypatch, tid="t1", who="Daniel Foo"):
    th = thread(tid)
    FS.confirm(plane, th, who, None)
    stub_tie(monkeypatch, True)
    FS.trial(x_of(plane, th))
    return th


def test_confirm_creates_a_draft_version_with_the_recipe_and_the_person(env):
    _, plane = env
    th = thread()
    FS.confirm(plane, th, "Anita Rao", None)
    rec = FS.read(plane, "fig-cash-break")
    v = rec["versions"][0]
    assert rec["name"] == "Cash break" and rec["used_by"] == [{"thread": "t1", "brief": th["title"], "person": "Anita Rao"}]
    assert v["v"] == 1 and v["status"] == "draft" and v["built_from"] == {"kind": "recipe", "id": "cash_break"} and v["approved_by"] == "Anita Rao"
    assert v["assumptions"] and th["figs"]["Cash break"] == {"id": "fig-cash-break", "v": 1, "reused": False}
    assert any(r["skill"] == "intent.define-figure" for r in SK.runs(plane, "t1"))
    FS.confirm(plane, th, "Anita Rao", None)  # the same thread again: its draft stands
    assert len(FS.read(plane, "fig-cash-break")["versions"]) == 1


def test_trial_run_records_reads_hash_tie_out_first_run_and_verifies(env, monkeypatch):
    _, plane = env
    verified(plane, monkeypatch)
    rec = FS.read(plane, "fig-cash-break")
    v = rec["versions"][0]
    assert v["status"] == "verified" and rec["current_v"] == 1 and v["reads"] == ["cash_movements"] and len(v["sql_hash"]) == 12
    assert v["tie_out"]["ok"] and v["tie_out"]["rule"] and v["runs"][0]["rows"] == 3 and v["runs"][0]["ok"]
    assert any("credit minus debit" in a["text"] and a["source"] == "ASSUMPTIONS A5" for a in v["assumptions"])
    assert any(r["skill"] == "check.adds-up" for r in SK.runs(plane, "t1"))


def test_the_next_brief_is_offered_the_verified_figure_and_accepting_links_it_without_a_new_version(env, monkeypatch):
    _, plane = env
    verified(plane, monkeypatch)
    b = thread("t2", "Second brief")
    assert FS.reuse_for(plane, b) == [{"brief_figure": "fig-cash-break", "figure_id": "fig-cash-break", "name": "Cash break", "built_from": {"kind": "recipe", "id": "cash_break"},
                                       "verified_runs": 1, "first_used_by": "Daniel Foo", "suggest": True}]
    FS.confirm(plane, b, "Grace Ong", {"fig-cash-break": "fig-cash-break"})
    rec = FS.read(plane, "fig-cash-break")
    assert len(rec["versions"]) == 1 and [u["person"] for u in rec["used_by"]] == ["Daniel Foo", "Grace Ong"]
    assert b["figs"]["Cash break"]["reused"] is True and FS.reuse_for(plane, b) == []
    FS.trial(x_of(plane, b))  # a reused figure only gains the run
    assert len(FS.read(plane, "fig-cash-break")["versions"][0]["runs"]) == 2


def test_declining_the_offer_makes_a_new_version(env, monkeypatch):
    _, plane = env
    verified(plane, monkeypatch)
    FS.confirm(plane, thread("t2"), "Grace Ong", {"fig-cash-break": None})
    rec = FS.read(plane, "fig-cash-break")
    assert [v["v"] for v in rec["versions"]] == [1, 2] and rec["versions"][1]["status"] == "draft" and rec["current_v"] == 1


def test_a_failed_tie_out_on_a_new_version_is_held_and_the_last_verified_stays_current(env, monkeypatch):
    _, plane = env
    a = verified(plane, monkeypatch)
    b = thread("t2")
    FS.confirm(plane, b, "Grace Ong", {"fig-cash-break": None})
    stub_tie(monkeypatch, False)
    FS.trial(x_of(plane, b))
    rec = FS.read(plane, "fig-cash-break")
    assert [v["status"] for v in rec["versions"]] == ["verified", "held"] and rec["current_v"] == 1
    assert rec["versions"][1]["tie_out"]["ok"] is False and rec["versions"][1]["reason"]
    assert FS.row(rec)["status"] == "verified" and FS.row(rec)["hold"]["v"] == 2
    assert FS.thread_figures(plane, a)[0]["hold"]["v"] == 2  # every thread using the figure shows the hold
    FS.confirm(plane, thread("t3"), "Leo Park", {"fig-cash-break": None})  # a later draft does not displace v1 either
    assert FS.read(plane, "fig-cash-break")["current_v"] == 1


def test_a_figure_with_no_rows_is_held_not_stated(env, monkeypatch):
    _, plane = env
    th = thread()
    FS.confirm(plane, th, "Anita Rao", None)
    stub_tie(monkeypatch, True)
    FS.trial(x_of(plane, th, ok=False, rows=0, reason="Nothing loaded yet."))
    v = FS.read(plane, "fig-cash-break")["versions"][0]
    assert v["status"] == "held" and v["reason"] == "Nothing loaded yet."


def test_each_live_run_appends_a_run(env, monkeypatch):
    _, plane = env
    th = verified(plane, monkeypatch)
    from sh_platform.v1 import cx_dash as CD
    monkeypatch.setattr(CD, "gold_tables", lambda plane, pid: [{"name": "g", "rows": 7}])
    x = x_of(plane, th)
    x.api = lambda *a, **k: {"runs": [{"run_id": "live-1"}]}
    assert "1 figures" in FS.runs(x)
    runs = FS.read(plane, "fig-cash-break")["versions"][0]["runs"]
    assert [r["run_id"] for r in runs] == ["run-t1", "live-1"] and runs[-1]["rows"] == 7


def test_the_answer_returns_the_figure_it_came_from(env, monkeypatch):
    _, plane = env
    th = verified(plane, monkeypatch)
    assert FS.link_answer(plane, th, "Cash break") == {"id": "fig-cash-break", "name": "Cash break", "v": 1}
    assert FS.link_answer(plane, th, "Nothing") is None
    monkeypatch.setattr(F, "_answer", lambda *a: {"answer": "Cash break is 5,000.", "figure": {"label": "Cash break", "value": "5,000", "change": ""}, "kpi": "Cash break"})
    got = F.figure_answer(plane, None, "what is the cash break", "prj-1", th)
    assert got["figure"] == {"label": "Cash break", "value": "5,000", "change": "", "id": "fig-cash-break", "name": "Cash break", "v": 1} and "kpi" not in got
    assert any(r["skill"] == "consume.explain-number" for r in SK.runs(plane, "t1"))


def test_routes_list_detail_and_rollback_with_permissions(env, monkeypatch):
    app, plane = env
    verified(plane, monkeypatch)
    b = thread("t2")
    FS.confirm(plane, b, "Grace Ong", {"fig-cash-break": None})
    FS.trial(x_of(plane, b))  # v2 verified too
    sam, boss = login(app, "sam@evergreen.example.test"), login(app, "boss@evergreen.example.test")
    rows = sam.get("/api/v3/figures").json()
    assert rows[0]["id"] == "fig-cash-break" and rows[0]["current_v"] == 2 and rows[0]["used_by_count"] == 2 and rows[0]["built_from"]["kind"] == "recipe" and rows[0]["last_run_at"]
    d = sam.get("/api/v3/figures/fig-cash-break").json()
    assert {"files", "tables", "figure"} <= set(d["lineage"]) and len(d["versions"]) == 2 and [t["name"] for t in d["lineage"]["tables"]] == ["cash_movements"]
    assert sam.get("/api/v3/figures/fig-nope").status_code == 404
    assert sam.post("/api/v3/figures/fig-cash-break/rollback", json={"v": 1}).status_code == 403  # not an admin, not the approver
    r = boss.post("/api/v3/figures/fig-cash-break/rollback", json={"v": 1})
    assert r.status_code == 200 and r.json()["current_v"] == 1
    assert boss.post("/api/v3/figures/fig-cash-break/rollback", json={"v": 9}).status_code == 409
    rec = FS.read(plane, "fig-cash-break")
    rec["versions"][1]["approved_by"] = "Sam Lee"
    FS._save(plane, rec)
    assert sam.post("/api/v3/figures/fig-cash-break/rollback", json={"v": 2}).json()["current_v"] == 2  # the figure's approver may
