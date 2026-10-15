"""M3-INT: module 3 end to end through the API, on the demo office's files (packs/family_office/1/demo_module3, README = answer key).

A real signed module 2 baseline (module 2's own routes, as m3_kit does), then its catalogue and measures are replaced in the test by the demo's
(synthetic; test code only): field names are the office's own spaced ones; the pack's synonyms and rule hints must resolve them (no special case).
Steps: create, score, request, upload (organiser and one owner link), benchmarks, compile (pack hints, model stubbed out), run the trial,
decide every risk, draft the plan, sponsor then head of data sign, read the outcome, then every write is refused (the guest link too)."""
import base64
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

M3_TESTS = Path(__file__).resolve().parents[1] / "modules" / "m3_connect" / "tests"
sys.path.insert(0, str(M3_TESTS))

from m3_kit import BASE, BID, World3, person, signed_baseline  # noqa: E402
from m3_trial_kit import DEMO, pack_kpis  # noqa: E402

CO = "m3-fo"
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc).timestamp()
SOURCES = [("S01", "Performance workbook", "performance_workbook.xlsx"), ("S02", "Northgate Custody daily file", "custody_daily_positions.csv"),
           ("S03", "Capital-calls mailbox", "capital_calls_export.json"), ("S04", "Index provider feed", "index_levels.csv"),
           ("S05", "Exposure workbook", "exposure_workbook.csv")]
FIELDS = {  # table -> [(field name as the office writes it, measures it feeds)]: a real catalogue's own spaced names, not the pack hints' names
    "T01": [("Fund / Manager", "K10, K15"), ("Asset Cls", "K10"), ("Opening Value (SGD)", "K15"), ("Closing Value (SGD)", "K10, K15"), ("Net Flows", "K15"),
            ("Fees Charged", "K15"), ("Period Return %", "K16")],
    "T02": [("Val Date", "K12"), ("Acct", "K12"), ("Security", "K12"), ("Mkt Value", "K12")],
    "T03": [("notice_ref", "K04"), ("amt", "K04"), ("status", "K04"), ("replaces", "K04")],
    "T04": [("Date", "K16"), ("Index", "K16"), ("Level", "K16")],
    "T05": [("Issuer", "K09"), ("Exposure Value (SGD)", "K09")]}
MEASURES = ("K04", "K09", "K10", "K12", "K15", "K16", "K18")


def cell(v):
    return {"value": v, "mark": "stated", "by": "Test Data Dan"}


def catalogue() -> dict:
    kp = {k["id"]: k for k in pack_kpis()}
    fields = [{"Field ID": cell(f"F-{t}-{i}"), "Item ID": cell(t), "Field name as in the source": cell(n), "Business meaning": cell(f"What {n} holds"),
               "Data type": cell("decimal"), "Feeds KPI": cell(f), "Personal data class": cell("Neither")}
              for t, cols in FIELDS.items() for i, (n, f) in enumerate(cols)]
    return {"sources": [{"Source ID": cell(s), "Source name": cell(n), "Data owner": cell("Test Data Dan"), "Contains personal data?": cell("No"),
                         "Connection method": cell("File drop"), "Where it lands or lives": cell("A shared folder"), "How often it arrives": cell("Monthly"),
                         "Structured or unstructured": cell("Structured"), "Source type": cell("File drop")} for s, n, _ in SOURCES],
            "tables": [{"Item ID": cell(f"T0{i + 1}"), "Source ID": cell(s), "Name of table, file or document type": cell(n + " table"),
                        "Related KPIs": cell(", ".join(sorted({m for _, f in FIELDS[f'T0{i + 1}'] for m in f.split(', ')})))} for i, (s, n, _) in enumerate(SOURCES)],
            "fields": fields, "extractions": [],
            "kpis": [{"KPI ID": cell(k), "KPI name": cell(kp[k]["name"]), "Definition": cell(kp[k]["definition"]), "Priority": cell("Must")} for k in MEASURES]}


def seed_demo_baseline(world) -> None:
    """A signed baseline (module 2's routes) for the family-office company, then the demo's catalogue and measures in its place."""
    shutil.copytree(Path(__file__).resolve().parents[1] / "packs" / "family_office", world.packs / "family_office")
    world.app.state.entitlements.create_company(CO, "Lakeside Illustrative", "family_office", modules=["m1_intent", "m2_baseline", "m3_connect"])
    signed_baseline(world, CO)
    plane = world.plane(CO)
    out = next(plane.path("intents", "m2_baseline", "outcomes").glob("*.json"))
    doc = json.loads(out.read_text())
    doc["catalogue"] = catalogue()
    out.write_text(json.dumps(doc))
    kp = plane.path("intents", "m2_baseline", BID, "kpis.json")
    rows = [k for k in json.loads(kp.read_text()) if k["id"] not in MEASURES]
    rows += [{"id": k, "name": k, "problem_ids": ["c1"], "governance": {"personal": "yes" if k == "K18" else "no", "sensitive": False, "may_see": []}}
             for k in MEASURES]
    kp.write_text(json.dumps(rows))


def payload(name: str, **extra) -> dict:
    return {"filename": name, "data": base64.b64encode((DEMO / name).read_bytes()).decode(), **extra}


def by_measure(rows: list[dict]) -> dict:
    return {r["measure"]: r for r in rows}


def test_module_three_end_to_end_on_the_demo_files(tmp_path):
    world = World3(tmp_path)
    seed_demo_baseline(world)
    world.app.state.m3_clock = lambda: NOW
    world.app.state.lens_model_factory = lambda plane: None  # the model is stubbed out: Lens falls back to the pack's rule hints
    head = person(world, CO, "Head Henry", ("company_admin",))
    sponsor = person(world, CO, "Sponsor Sue", ("sponsor",))
    adir = lambda aid: world.plane(CO).path("intents", "m3_connect", "assessments", aid)  # noqa: E731

    # 1 create
    made = head.post(f"{BASE}/assessments")
    assert made.status_code in (200, 201), made.text
    aid = made.json()["assessment"]["id"]
    a = f"{BASE}/assessments/{aid}"

    # 2 score the sources: every source is on the map, in a zone; the five that matter are ready to scan
    scored = head.post(f"{a}/sources/score")
    assert scored.status_code == 200, scored.text
    zones = {s["id"]: s["zone"] for s in head.get(f"{a}/sources").json()["sources"]}
    assert set(zones) == {s for s, _, _ in SOURCES} and set(zones.values()) <= {"p1", "p2"}, zones

    # 3 the requests
    asked = head.post(f"{a}/intake/requests")
    assert asked.status_code == 200 and asked.json()["new"] == 5, asked.text
    links = {s["source_id"]: s["link_path"].removeprefix("/intake/") for s in asked.json()["sent"]}

    # 4 the five demo files: four by the organiser, the exposure workbook by its owner's link
    for sid, _, name in SOURCES[:4]:
        up = head.post(f"{a}/intake/sources/{sid}/upload", json=payload(name))
        assert up.status_code == 200, (sid, up.text)
    guest = TestClient(world.app)
    guest.headers["x-session-token"] = links["S05"]
    up = guest.post(f"{BASE}/intake/link/upload", json=payload("exposure_workbook.csv"))
    assert up.status_code == 200, up.text
    rows = json.loads((adir(aid) / "intake" / "S05" / "rows.json").read_text())
    assert rows["tables"][0]["columns"][0]["field_id"] and len(rows["tables"][0]["rows"]) == 24

    # 5 the benchmark pack
    bench = head.post(f"{a}/intake/benchmarks/upload", json=payload("benchmarks_monthly_pack.csv"))
    assert bench.status_code == 200, bench.text
    assert {m["measure_id"] for m in bench.json()["measures"]} >= {"K04", "K09", "K10", "K12", "K15", "K16"}

    # 6 compile (pack hints) and run the trial
    compiled = head.post(f"{a}/trial/compile")
    assert compiled.status_code == 200, compiled.text
    origins = {m["measure"]: m["rule"]["origin"] for m in compiled.json()["measures"] if m.get("rule") and m["rule"]["origin"]}
    assert origins.items() >= {"K04": "pack hint", "K16": "pack hint"}.items(), [(m["measure"], m["rule"]) for m in compiled.json()["measures"]]
    ran = head.post(f"{a}/trial/run")
    assert ran.status_code == 200, ran.text
    t = by_measure(ran.json()["measures"])

    # 7 the README's answer key, exactly
    for k, figure in (("K04", 2610000), ("K09", 12.92), ("K10", 20.86)):
        assert t[k]["result"] == "matches" and abs(t[k]["our_figure"] - figure) < 0.01, (k, t[k])
    assert t["K12"]["result"] == "gap" and abs(t["K12"]["our_figure"] - 21.43) < 0.01
    assert "The data ends on 22 Sep, but your figure is as at 30 Sep." in t["K12"]["reasons"]
    assert t["K15"]["result"] == "gap" and abs(t["K15"]["our_figure"] - 0.63) < 0.01 and abs(t["K15"]["their_figure"] - 0.67) < 0.001
    assert any("leaves out fees charged" in r.lower() for r in t["K15"]["reasons"]), t["K15"]["reasons"]
    assert t["K16"]["result"] == "cannot" and t["K16"]["our_figure"] is None and "Index levels missing after 22 Sep" in t["K16"]["missing"]
    findings = head.get(f"{a}/findings").json()
    groups = {k: v["group"] for k, v in findings["measures"].items()}
    assert groups == {"K04": "ready", "K09": "ready", "K10": "ready", "K12": "unclear", "K15": "unclear", "K16": "unknown", "K18": "unknown"}

    # 8 decide every risk: one with the opaque id a viewer without the source would be given, the rest accepted at once
    assert findings["risks"] and all(r["decision"] is None for r in findings["risks"])
    from modules.m3_connect.domain import findings as F
    first = findings["risks"][0]["id"]
    one = head.post(f"{a}/risks/{F.opaque_id(adir(aid), first)}/decision", json={"decision": "accepted", "note": "Known"})
    assert one.status_code == 200 and next(r for r in one.json()["risks"] if r["id"] == first)["state"] == "accepted", one.text
    assert head.post(f"{a}/risks/accept-all", json={}).status_code == 200
    risks = head.get(f"{a}/risks").json()
    assert risks["counts"]["open"] == 0 and len(risks["risks"]) == len(findings["risks"])

    # 9 draft the plan and check the bands
    plan = head.post(f"{a}/plan/draft")
    assert plan.status_code == 200, plan.text
    bands = plan.json()["bands"]
    ids = lambda b: sorted(m["id"] for it in bands[b] for m in it["measures"])  # noqa: E731
    assert ids("now") == ["K04", "K09", "K10"] and ids("next") == ["K12", "K15", "K16"] and ids("later") == ["K18"]  # an unknown whose source is known goes Next (contracts/plan.yaml), {b: ids(b) for b in bands}
    assert plan.json()["can_sign"] is True

    # 10 the sponsor, then the head of data, sign; 11 read the outcome
    assert head.post(f"{a}/plan/sign").status_code == 409  # the head of data cannot go first
    assert sponsor.post(f"{a}/plan/sign").status_code == 200
    done = head.post(f"{a}/plan/sign")
    assert done.status_code == 200 and done.json()["signed_at"] and [s["slot"] for s in done.json()["signatures"]] == ["sponsor", "head_of_data"], done.text
    outcome = head.get(f"{a}/outcome")
    assert outcome.status_code == 200
    out = outcome.json()
    assert out["kind"] and out["findings_summary"]["counts"] == {"ready": 3, "unclear": 2, "unknown": 2}
    assert sorted(m for it in out["plan"]["now"] for m in it["measures"]) == ["K04", "K09", "K10"]

    # 12 every write is refused now, whichever package owns the route, and so is the guest link
    writes = [("post", "/sources/score", {}), ("put", "/sources/S01/override", {"impact": 0.5, "reason": "x"}), ("post", "/intake/requests", {}),
              ("post", "/intake/sources/S01/upload", payload("performance_workbook.xlsx")), ("post", "/intake/benchmarks/upload", payload("benchmarks_monthly_pack.csv")),
              ("post", "/intake/benchmarks/map", {"index": 0, "measure_id": "K04"}), ("post", "/trial/compile", {}), ("post", "/trial/run", {}),
              ("post", "/trial/rules/K04/check", {}), ("post", "/plan/draft", {}), ("put", "/plan/item", {"key": "x", "band": "now", "reason": "x"}),
              ("post", "/risks/accept-all", {}), ("post", f"/risks/{first}/decision", {"decision": "sent_back", "reason": "x"})]
    for who in (head, sponsor):
        for method, tail, body in writes:
            r = getattr(who, method)(f"{a}{tail}", json=body)
            assert r.status_code == 409, (method, tail, r.status_code, r.text)
    late = guest.post(f"{BASE}/intake/link/upload", json=payload("exposure_workbook.csv"))
    assert late.status_code == 409 and "signed" in json.dumps(late.json()), late.text
    assert head.get(f"{a}/outcome").json() == out and head.get(f"{a}/plan").status_code == 200  # reads still work
