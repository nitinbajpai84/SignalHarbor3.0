"""B58: Proving (spec 58) on a temporary copy of the seeded Ardmore plane (synthetic). The four seeded Initiatives prove out as
working, working, partly and too early from the warehouse; the organiser confirms, the sponsor confirms the review; a restricted
measure's figures never reach a viewer outside its access list, the panel or the sponsor's Pulse line."""
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import proving as P, store as S
from sh_platform.plane import PlaneStore

SRC = Path(__file__).resolve().parents[2] / "data" / "ardmore"
T1, T2, T3, T4 = ("ini-37c78119f8a10a2611a942f7fdb17551", "ini-125df0d379f2b7067ac933483ec57107",
                  "ini-985f04a8992c2d8ef06b91970a0872f9", "ini-a85927768bfe1f9c797248165efcdf89")
JANET, DANIEL, OUT = "ab11d18a55444cbd9bfac75224615554", "af17e8cae68044069a2c9226e31133ba", "ffffffffffffffffffffffffffffffff"
NAMES = {JANET: "Janet Shaw", DANIEL: "Daniel Kerr", OUT: "Nobody Here"}
TODAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 4, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(not (SRC / "intents" / "hypotheses").is_dir(), reason="the seeded Ardmore plane is not loaded")


@pytest.fixture
def world(tmp_path, monkeypatch):
    dst = tmp_path / "ardmore"
    for part in ("intents/hypotheses", *(f"intents/{i}" for i in (T1, T2, T3, T4)), "profile", "settings"):
        shutil.copytree(SRC / part, dst / part)
    for f in ("intents/_index.json", "warehouse/company.readonly.duckdb", "build/blueprint.json", "build/prove.json", "build/alerts.json"):
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SRC / f, dst / f)
    plane = PlaneStore(tmp_path).plane_for("ardmore")
    monkeypatch.setattr(P, "_today", lambda pl, now: TODAY)
    monkeypatch.setattr(P, "_plane", lambda r: plane)
    monkeypatch.setattr(P, "_viewer", lambda r: SimpleNamespace(name=NAMES[r.headers["x-as"]], roles=frozenset(), account_id=r.headers["x-as"],
                                                                shared_name=False))
    app = FastAPI()
    app.include_router(P.router)
    P.seed(plane, NOW)
    return plane, TestClient(app)


def latest(plane, iid):
    pv = P.read_proving(plane, iid)
    return pv, P.read_report(plane, iid, pv["reports"][-1])


def test_seeded_verdicts_come_from_the_data(world):
    plane, _ = world
    got = {iid: latest(plane, iid) for iid in (T1, T2, T3, T4)}
    assert [got[i][1]["verdict"] for i in (T1, T2, T3, T4)] == ["working", "working", "partly", "too_early"]
    assert [got[i][0]["state"] for i in (T1, T2, T3, T4)] == ["reviewing", "reviewing", "reviewing", "proving"]  # review dates 30 Sep, 30 Sep, 6 Oct, 30 Nov
    assert got[T1][1]["week_key"] == "2026-W40" and got[T1][1]["now"]["period"] == "2026-09"
    assert "group" in got[T3][1]["rule"] and any("did not" in n["text"] for n in got[T3][1]["notes"])  # the next generation moved, the elders did not
    assert P.seed(plane, NOW)[0]["reports"] == ["2026-W40"]  # idempotent: one report a week


def test_restricted_figures_stay_with_the_access_list(world):
    plane, c = world
    bp = json.loads(plane.path("build", "blueprint.json").read_text())
    next(a for a in bp["access"] if a["mart"] == "gold.k03")["may_see"] = ["Daniel Kerr"]
    plane.path("build", "blueprint.json").write_text(json.dumps(bp))
    janet = c.get(f"/api/intents/{T2}/proving", headers={"x-as": JANET}).json()
    assert janet["figures"] is False and "now" not in janet["latest"] and janet["latest"]["notes"] is None and janet["hypothesis"]["target"] is None
    assert janet["latest"]["verdict_word"] == "Working"
    assert c.get(f"/api/intents/{T2}/proving", headers={"x-as": DANIEL}).json()["latest"]["now"]["value"] == 32.75
    assert c.get(f"/api/intents/{T2}/proving", headers={"x-as": OUT}).status_code == 404
    wk = janet["latest"]["week_key"]
    assert c.post(f"/api/intents/{T2}/proving/reports/{wk}/confirm", json={}, headers={"x-as": DANIEL}).status_code == 403
    assert c.post(f"/api/intents/{T2}/proving/reports/{wk}/confirm", json={}, headers={"x-as": JANET}).status_code == 200
    watch = P.pulse_lines(plane, SimpleNamespace(name="Daniel Kerr", roles=frozenset(), account_id=DANIEL, shared_name=False), NOW)["watch"]
    line = next(x for x in watch if x["id"] == f"proving:{T2}:uplift")
    assert line["title"].endswith(": Working") and "32" not in json.dumps(line)


def test_review_keep_and_send_back(world):
    plane, c = world
    for iid in (T1, T3):
        wk = P.read_proving(plane, iid)["reports"][-1]
        assert c.post(f"/api/intents/{iid}/proving/reports/{wk}/confirm", json={}, headers={"x-as": JANET}).status_code == 200
    body = c.get(f"/api/intents/{T1}/proving", headers={"x-as": JANET}).json()
    assert body["review"]["proposed"] == "keep" and body["can"]["review"]
    assert c.post(f"/api/intents/{T1}/proving/review", json={"action": "keep"}, headers={"x-as": DANIEL}).status_code == 403
    assert c.post(f"/api/intents/{T1}/proving/review", json={"action": "keep"}, headers={"x-as": JANET}).json()["review"]["sent"] is True
    assert c.post(f"/api/intents/{T1}/proving/review/confirm", json={}, headers={"x-as": DANIEL}).json()["state"] == "proved"
    assert S.read_intent(plane, T1)["outcome_used"]["answer"] == "yes"
    assert c.post(f"/api/intents/{T3}/proving/review", json={"action": "send_back"}, headers={"x-as": JANET}).status_code == 422  # learning required
    proposed = c.get(f"/api/intents/{T3}/proving", headers={"x-as": JANET}).json()["review"]
    assert proposed["proposed"] == "send_back" and proposed["learning"]
    c.post(f"/api/intents/{T3}/proving/review", json={"action": "send_back", "learning": proposed["learning"]}, headers={"x-as": JANET})
    out = c.post(f"/api/intents/{T3}/proving/review/confirm", json={}, headers={"x-as": DANIEL}).json()
    assert out["state"] == "returned" and out["returned_to"].startswith("opp-")
    opp = json.loads(plane.path("intents", "opportunities", f"{out['returned_to']}.json").read_text())
    assert opp["state"] == "under_review" and opp["origin"] == {"kind": "initiative", "ref": T3}
    assert S.read_intent(plane, T3)["outcome_used"]["answer"] == "partly"
    assert json.loads(plane.path("intents", "hypotheses", "hyp-ini-0003-one-page-summary.json").read_text())["versions"][-1]["learning"]


def test_change_start_redraws(world):
    plane, c = world
    r = c.post(f"/api/intents/{T4}/proving/start", json={"at": "2026-08-01", "reason": "first chase went out then"}, headers={"x-as": JANET})
    assert r.status_code == 200 and r.json()["start"]["changed"]["by"] == "Janet Shaw"
    assert latest(plane, T4)[1]["periods_since_start"] == 2  # August and September now count
