"""B57: the opportunity radar and the hypothesis record (spec 57, rulings C2 to C9). Synthetic data in a temporary company space;
North's model judgement is stubbed (the rules decide)."""
import json
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.build import opportunity_watch as watch
from sh_platform.context_docs.store import DocStore
from sh_platform.intents import hypotheses as H
from sh_platform.intents import opportunities as opp
from sh_platform.intents import radar
from sh_platform.plane import PlaneStore
from sh_platform.profile import areas as areas_store

ACCTS = {"harvey": {"display_name": "Harvey Rowley"}, "katie": {"display_name": "Katie"}, "janet": {"display_name": "Janet Shaw"},
         "mei": {"display_name": "Mei Ling"}, "aaron": {"display_name": "Aaron Lyle"}, "root": {"display_name": "Platform"}}
ROLES = {"harvey": "owner", "katie": "analyst", "janet": "company_admin", "mei": "participant", "aaron": "participant", "root": "super_admin"}
KPIS = [{"id": "K90", "name": "Pack preparation effort", "unit": "hours", "keywords": ["pack", "effort", "hours"], "owner_role": "Operations"},
        {"id": "K91", "name": "Custody fees", "unit": "basis points", "keywords": ["custody", "fee"], "owner_role": "Operations"}]
MONTHS = [f"2025-{m:02d}" for m in range(9, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
HOURS = [48.75, 50, 50.75, 51.5, 48.5, 52, 55.5, 55, 53, 52, 51, 30, 50]  # a K90 series with no shift or drift
VOL = [17.2, 16.4, 15.8, 16.9, 18.3, 20.1, 31.8, 29.4, 20, 19, 18, 30.7, 19]
FEES = [6, 6, 6, 6, 6, 6, 9.5, 9.5, 9.5, 9.5, 9.5, 9.5, 9.5]
NOTE = "Pack effort and market conditions\n\n| Month | Pack hours (effort log) | Market volatility index |\n|---|---|---|\n" + "".join(
    f"| {m} | {h} | {v} |\n" for m, h, v in zip(MONTHS[:8], HOURS[:8], VOL[:8])) + "\nThe two move together closely (correlation about 0.9).\n"


def warehouse(plane):
    plane.path("warehouse").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(plane.path("warehouse", "company.readonly.duckdb")))
    con.execute("create schema gold; create schema silver")
    con.execute("create table gold.k90 (period varchar, value double)")
    con.executemany("insert into gold.k90 values (?, ?)", list(zip(MONTHS, HOURS)))
    con.execute("create table gold.k91 (period varchar, custodian_id varchar, value double)")
    con.executemany("insert into gold.k91 values (?, 'C2', ?)", list(zip(MONTHS, FEES)))
    con.execute("create table silver.valuations_volatility_monthly (period varchar, market_volatility_index double)")
    con.executemany("insert into silver.valuations_volatility_monthly values (?, ?)", list(zip(MONTHS, VOL)))
    con.execute("create table silver.reporting_effort_log (period varchar, cause varchar, hours double)")
    rows = [(m, "late_statement", h - 40) for m, h in zip(MONTHS, HOURS)] + [(m, "reformat", 40.0) for m in MONTHS]
    con.executemany("insert into silver.reporting_effort_log values (?, ?, ?)", rows)
    con.close()


def week(plane, items):
    d = plane.path("intents", "pul-" + "a" * 32, "weeks")
    d.mkdir(parents=True, exist_ok=True)
    (d / "2026-W40.json").write_text(json.dumps({"week_key": "2026-W40", "opens": "2026-09-28", "items": items}))


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("acme")
    app = FastAPI()
    radar.install(app)
    app.include_router(opp.router)
    pack = SimpleNamespace(section=lambda n: {"kpis": KPIS})
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = SimpleNamespace(get=ACCTS.get, in_company=lambda c: [])
    app.state.entitlements = SimpleNamespace(company=lambda c: {"industry": "x"})
    app.state.packs = SimpleNamespace(load=lambda i: pack)

    @app.middleware("http")
    async def who(request, call_next):
        acct = request.headers.get("x-acct", "harvey")
        request.state.account_id, request.state.roles, request.state.company_id = acct, [ROLES[acct]], "acme"
        return await call_next(request)
    monkeypatch.setattr(opp, "judge", lambda request, plane, rec: None)  # the model is out: the rules decide
    monkeypatch.setattr(watch, "thresholds", lambda plane: {k: None for k in watch.KEYS})
    warehouse(plane)
    DocStore(plane).upload("north", "Janet", "note.md", NOTE.encode(), title="Aaron's note on pack effort", visibility="shared")
    DocStore(plane).upload("north", "Janet", "pay.md", b"custody fee pay review custody fees", title="Pay", visibility="shared", restricted=True)
    wish = "One list of all commitments and capital calls would end the chasing."
    week(plane, [{"id": f"i{i}", "kind": "thought", "by": by, "anonymous": by == "anonymous", "text": wish, "state": "active"}
                 for i, by in enumerate(["mei", "mei", "aaron", "anonymous", "anonymous"])]
         + [{"id": "f1", "kind": "broke", "by": "harvey", "text": "Custody fees at Meridian look higher; the fee tier changed.", "state": "active"}])
    return plane, pack, TestClient(app)


def X(who):
    return {"x-acct": who}


def scanned(world):
    plane, pack, c = world
    return radar.scan(plane, pack), {r["pattern"]["key"]: r for r in opp.all_records(plane)}


def test_hypothesis_versions_never_change_in_place(tmp_path):
    plane = PlaneStore(tmp_path).create("acme")
    h = H.create(plane, {"kind": "opportunity", "ref": "opp-0001"}, {"belief": "b", "lens": "risk", "frozen_by": "charter:x v1"}, "north")
    H.add_version(plane, h["id"], {"lens": "retention"}, "katie")
    rec = H.get(plane, h["id"])
    assert [v["lens"] for v in rec["versions"]] == ["risk", "retention"] and rec["versions"][0]["frozen_by"] == "charter:x v1" and rec["versions"][1]["frozen_by"] is None
    assert H.uplift_gap({"value": 9.5, "unit": "bp", "trace": {}}, {"value": 6}) ["value"] == 3.5
    assert H.missing_uplift({"measure": None}) == "Not available yet: no measure for this theme"


def test_scan_finds_a_shift_rejects_the_broken_claim_and_groups_one_theme(world):
    res, by_key = scanned(world)
    fees = by_key["measure:K91"]
    assert fees["state"] == "proposed" and fees["areas"] == []
    hf = H.latest(H.get(world[0], fees["hypothesis_ref"]["id"]))
    assert hf["lens"] == "process_cost" and hf["baseline"]["value"] == {"C2": 9.5} and hf["counter_check"]["verdict"] == "holds" and hf["target"] is None
    assert all(e["trace"]["ref"] != "pay" for e in hf["evidence"])  # a restricted document is never read
    claim = next(r for k, r in by_key.items() if k.startswith("claim:"))
    assert claim["state"] == "rejected" and "2026-08" in claim["rejected"]["why"] and "late_statement" in claim["rejected"]["why"]
    theme = next(r for k, r in by_key.items() if k.startswith("theme:"))
    ht = H.latest(H.get(world[0], theme["hypothesis_ref"]["id"]))
    assert ht["theme"]["voices"] == 4  # Mei once, Aaron once, each anonymous item once (C6)
    assert H.missing_uplift(ht) == "Not available yet: no measure for this theme"
    assert radar.scan(world[0], world[1])["made"] == []  # never a second record for a pattern on file
    assert len(radar.last_scan(world[0])) and world[0].path("intents", "radar", "scans.jsonl").read_text().count("\n") == 6


def test_radar_view_tiers_and_roles(world):
    plane, pack, c = world
    radar.scan(plane, pack)
    full = c.get("/api/intents/radar?scope=lens", headers=X("harvey")).json()
    card = next(o for o in full["opportunities"] if o["title"].startswith("Custody fees"))
    assert card["lens"] == "process_cost" and card["evidence_mix"]["data"] >= 1 and card["target_missing"] and card["uplift_missing"] == "Not available yet: no target"
    assert any("2026-08" in r["why"] for r in full["rejected"]) and full["scan"]["last_at"] and full["can_set_thresholds"] is False
    thin = c.get("/api/intents/radar", headers=X("mei")).json()["opportunities"]
    assert thin and all(set(o) <= {"id", "title", "lens", "confidence", "state", "dashed", "theme", "href"} for o in thin)  # C2 card tier
    assert c.get("/api/intents/radar", headers=X("root")).status_code == 403
    assert c.post("/api/intents/radar/scan", headers=X("harvey")).status_code == 403
    assert c.post("/api/intents/radar/scan", headers=X("janet")).status_code == 200


def test_hypothesis_edit_think_through_and_anonymous_voices(world):
    plane, pack, c = world
    _, by_key = scanned(world)
    fid = by_key["measure:K91"]["id"]
    assert c.post(f"/api/intents/opportunities/{fid}/state", json={"action": "think_through"}, headers=X("harvey")).status_code == 409  # no review date yet
    assert c.post(f"/api/intents/opportunities/{fid}/hypothesis", json={"lens": "risk"}, headers=X("mei")).status_code == 403
    r = c.post(f"/api/intents/opportunities/{fid}/hypothesis", json={"review_date": "2026-12-31", "target": {"value": 6, "by": "2026-12-31"}}, headers=X("katie"))
    assert r.status_code == 200 and r.json()["hypothesis_ref"]["version"] == 2
    assert c.post(f"/api/intents/opportunities/{fid}/state", json={"action": "think_through"}, headers=X("mei")).status_code == 403  # C3: participants only feel it
    done = c.post(f"/api/intents/opportunities/{fid}/state", json={"action": "think_through"}, headers=X("katie")).json()
    assert done["state"] == "picked_up" and done["picked_up_as"] == "brainstorm" and done["think_href"].endswith(f"type=brainstorm&from={fid}")
    theme = next(r for k, r in by_key.items() if k.startswith("theme:"))
    h = c.get(f"/api/intents/hypotheses/{theme['hypothesis_ref']['id']}", headers=X("katie")).json()
    assert h["versions"] and "Someone, anonymously" in {e["by"] for e in h["latest"]["evidence"]} and "anonymous" not in json.dumps(h["voices_named"])


def test_evidence_goes_to_the_one_list_and_restricted_areas_hide(world, monkeypatch):
    plane, pack, c = world
    _, by_key = scanned(world)
    fid = by_key["measure:K91"]["id"]
    r = c.post(f"/api/intents/opportunities/{fid}/evidence", json={"text": "Meridian moved us to a higher tier", "kind": "supports",
                                                                   "source": {"kind": "document", "ref": "d1"}}, headers=X("katie")).json()
    assert opp.get(plane, fid)["evidence"] == [] and r["evidence"][-1]["record_kind"] == "document"  # C7
    aid = areas_store.add(plane, "Treasury", "operations_area", "t")
    rec = opp.get(plane, fid)
    rec["areas"] = [aid]
    opp._save(plane, rec)
    monkeypatch.setattr(areas_store, "areas_of_account", lambda doc, a: frozenset({aid}) if a == "katie" else frozenset())
    assert c.get(f"/api/intents/hypotheses/{rec['hypothesis_ref']['id']}", headers=X("harvey")).status_code == 404
    assert c.get(f"/api/intents/hypotheses/{rec['hypothesis_ref']['id']}", headers=X("katie")).status_code == 200


def test_a_seeded_hex_id_record_gets_a_hypothesis_and_does_not_stop_the_scan(world):
    plane, pack, c = world
    d = plane.path("intents", "opportunities")
    d.mkdir(parents=True, exist_ok=True)
    old = {"id": "opp-a66189d0c3b7ab13", "title": "Custody fees look higher", "state": "under_review", "noticed_by": "watcher", "noticed_at": "2026-10-01",
           "areas": [], "touches": {"measures": ["k91"], "processes": [], "sources": []}, "pattern": {"text": "Fees rose.", "periods": [], "numbers": []},
           "evidence": [], "judgement": None, "picked_up_by": None, "picked_up_at": None, "became": None, "parked": None, "dismissed": None, "history": []}
    (d / "opp-a66189d0c3b7ab13.json").write_text(json.dumps(old))
    assert radar.scan(plane, pack)["made"]
    rec = opp.get(plane, "opp-a66189d0c3b7ab13")
    assert rec and H.latest(H.get(plane, rec["hypothesis_ref"]["id"]))["lens"] == "process_cost"
