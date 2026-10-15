"""P1: the pulse is built from records only. Synthetic data; planes are written by path, as the modules write them."""
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.pulse import build
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "lakeside-family-office"
SARA = Viewer("Sara Lim", frozenset({"owner"}), False, "acct-sara")
WEI = Viewer("Wei Chen", frozenset({"participant"}), False, "acct-wei")
OPS = Viewer("Dev Rao", frozenset({"analyst", "owner"}), False, "acct-dev")
AARON = Viewer("Aaron Lyle", frozenset({"company_admin"}), False, "acct-aaron")


def put(plane, rel: str, data) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def wall(plane, sid: str, account: str) -> None:
    put(plane, f"intents/m1_intent/sessions/{sid}.json", {"id": sid, "state": "board", "updated_at": "2026-10-05T09:00:00+00:00",
                                                          "preparation": {"topic": f"Wall {sid}", "wall_window_days": None}})
    put(plane, f"intents/m1_intent/rooms/{sid}.json", {"session_id": sid, "seats": [{"n": 1, "state": "taken", "account_id": account}]})


def measure(plane, bid: str, kid: str, owner: str) -> None:
    put(plane, f"intents/m2_baseline/{bid}/kpis.json", [{"id": kid, "name": f"Measure {kid}"}])
    put(plane, f"intents/m2_baseline/{bid}/governed_state.json", {kid: {"owners": {"mark": "guessed", "value": {"business": owner}}}})


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path / "planes").create(FAMILY)


def keys(pulse: dict) -> dict:
    return {s["key"]: s["lines"] for s in pulse["strips"]}


def test_an_invite_shows_for_the_seated_person_only(plane):
    wall(plane, "s1", "acct-sara")
    mine = keys(build(plane, SARA))["invited"]
    assert [x["href"] for x in mine] == ["/centre/intent/wall/s1"] and mine[0]["kind"] == "invite"
    assert build(plane, WEI)["strips"] == []


def test_an_unconfirmed_owner_gets_a_decision_line(plane):
    measure(plane, "b1", "m1", "Sara Lim")
    got = keys(build(plane, SARA))["decide"]
    assert got[0]["kind"] == "decision" and got[0]["href"] == "/centre/intent/baseline/b1" and got[0]["title"] == "Measure m1"
    assert "decide" not in keys(build(plane, WEI))


def test_seven_lines_at_most_and_the_last_strip_goes_first(plane):
    for i in range(3):
        wall(plane, f"s{i}", "acct-dev")
        measure(plane, f"b{i}", f"m{i}", "Dev Rao")
    put(plane, "intents/m2_baseline/b0/requests.json", [{"id": f"r{i}", "owner_name": "Dev Rao", "state": "sent", "kpi_ids": ["m0"]} for i in range(2)])
    put(plane, "warehouse/runs.json", {"runs": [{"id": "x", "source": "custody", "status": "late", "owner": "Nobody"}]})
    full = build(plane, OPS)  # the data team: the ops report comes first
    assert full["layout"] == "data" and sum(len(s["lines"]) for s in full["strips"]) == 7
    assert [s["key"] for s in full["strips"]] == ["ops", "invited", "decide"]  # 1 + 3 + 3; Give is dropped
    assert full["panels"]["ops_report"][1] == {"label": "Late", "value": "1", "note": None}


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("pulse_seeded") / "data"
    spec = importlib.util.spec_from_file_location("pulse_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {}
    for ln in result["path"].read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.startswith("#"):
            email, password = ln.split()[:2]
            pw[email] = password
    return root, pw


def test_an_empty_company_gives_empty_strips(seeded, tmp_path):
    root, pw = seeded
    shutil.copytree(root, tmp_path / "data")
    app = create_app(load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-pulse-secret-0123456789-abcdefghij"},
                                   env_file=tmp_path / "none.env"), dist_dir=tmp_path)
    c, email = TestClient(app), f"participant.{FAMILY}@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    r = c.get("/api/pulse")
    assert r.status_code == 200 and r.json()["map"] == {"new_this_week": [], "owned_changes": 0, "owned_new": 0}
    assert r.json()["strips"] == []  # no records, and a participant has no Consume centre to read the pack's market brief in


def test_each_line_carries_its_minutes_and_the_day_sums_them(plane):
    wall(plane, "s1", "acct-sara")
    measure(plane, "b1", "m1", "Sara Lim")
    put(plane, "intents/m3_connect/assessments/a1/requests.json", [{"id": "r1", "owner": "Sara Lim", "state": "sent", "source_name": "Custodian"}])
    got = build(plane, SARA)
    assert {x["kind"]: x["minutes"] for s in got["strips"] for x in s["lines"]} == {"invite": 5, "decision": 3, "request": 5}
    assert got["minutes"] == 13 and got["layout"] == "participant"


def test_the_organiser_strips_come_from_records(plane):
    now = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
    put(plane, "pulse/messages.json", {"messages": [{"id": "m1", "kind": "sponsor_ask", "subject": "A note from Mei Tan", "state": "draft",
                                                     "organiser_account_id": "acct-aaron"}]})
    for sid, state in (("s1", "board"), ("s2", "closed"), ("s3", "closed")):
        put(plane, f"intents/m1_intent/sessions/{sid}.json", {"id": sid, "state": state, "organiser_account_id": "acct-aaron", "outcome_id": f"o{sid}",
                                                              "updated_at": "2026-10-02T09:00:00+00:00",
                                                              "preparation": {"topic": f"Wall {sid}", "approver_name": "Mei Tan"}})
    put(plane, "intents/m1_intent/rooms/s1.json", {"seats": [{"n": i, "state": "taken", "account_id": f"a{i}"} for i in range(8)]})
    put(plane, "intents/m1_intent/note_authors/s1.json", {"authors": {"n1": "seat-1", "n2": "seat-1", "n3": "seat-2", "n4": "seat-3"}, "anonymous_seats": []})
    put(plane, "intents/m1_intent/charters/s3.json", {"versions": [{"version": 0, "status": "signed", "created_at": "2026-10-03T09:00:00+00:00"}]})
    measure(plane, "b1", "m1", "Olga")
    put(plane, "intents/m2_baseline/b1/requests.json", [{"id": "q1", "owner_name": "Olga", "state": "sent", "sent_at": "2026-10-01T09:00:00+00:00"},
                                                        {"id": "q2", "owner_name": "Dan", "state": "sent", "sent_at": "2026-10-06T09:00:00+00:00"}])
    got = build(plane, AARON, now=now)
    k = keys(got)
    assert got["layout"] == "organiser" and [s["key"] for s in got["strips"]][:3] == ["start", "running", "waiting"]
    assert k["start"][0]["title"] == "A note from Mei Tan" and k["start"][0]["href"] == "/centre/intent"
    assert [(x["title"], x["href"]) for x in k["running"]] == [("Wall s1: 5 of 8 have not written a card", "/centre/intent/wall/s1"),
                                                               ("Wall s2 closed with no charter yet", "/centre/intent/define/s2")]
    assert [x["detail"] for x in k["waiting"]] == ["Asked: Olga."]  # Dan was asked yesterday: not yet three days
    assert got["panels"]["quarter"] == [{"label": "Walls run", "value": "3", "note": None}, {"label": "Charters signed", "value": "1", "note": None},
                                        {"label": "Measures governed", "value": "0 of 1", "note": None},
                                        {"label": "Your time so far", "value": None, "note": "Not available yet"}]
    assert got["panels"]["drafts"] == {"sponsor_ask": 1}


def test_the_sponsor_is_asked_to_sign_first_and_to_release_a_draft(plane):
    boss = Viewer("Mei Tan", frozenset({"sponsor"}), False, "acct-mei")
    put(plane, "intents/m2_baseline/b1/signoff.json", {"versions": [{"status": "open", "countersign": [], "created_at": "2026-10-05T09:00:00+00:00"}]})
    put(plane, "build/prove.json", {"measures": [{"code": "NAV", "periods": [], "release_ready": True}], "release": {"state": "draft"}})
    assert [x["id"] for x in keys(build(plane, boss)).get("decide", [])] == ["sign:release"]  # parts not yet confirmed: no early ask to sign the baseline
    put(plane, "intents/m2_baseline/b1/governed_state.json", {"k1": {"owners": {"mark": "stated", "value": {"business": "Olga"}}}})
    ids = [x["id"] for x in keys(build(plane, boss))["decide"]]
    assert ids == ["sign:release", "sign:baseline:b1"] or sorted(ids) == ["sign:baseline:b1", "sign:release"]
    assert "decide" not in keys(build(plane, WEI))
    put(plane, "build/prove.json", {"measures": [{"code": "NAV", "periods": [], "release_ready": True}], "release": {"state": "signed"}})
    assert [x["id"] for x in keys(build(plane, boss))["decide"]] == ["sign:baseline:b1"]


def test_new_this_week_never_names_a_restricted_node(plane):
    now = datetime.now(timezone.utc).isoformat()
    put(plane, "graph/company.json", {"version": 1, "built_at": now, "edges": [], "nodes": [
        {"id": "m1", "type": "Measure", "label": "Fees Charged"},
        {"id": "m2", "type": "Measure", "label": "Secret Margin", "restricted_to": ["Olga Petrova"]}]})
    put(plane, "graph/versions.json", {"m1": [{"v": 1, "at": now}], "m2": [{"v": 1, "at": now}]})
    got = build(plane, WEI)["map"]["new_this_week"]
    assert got == ["Fees Charged"]


def test_a_comment_line_uses_the_right_article(plane):
    from sh_platform.pulse import lines as L
    put(plane, "graph/company.json", {"version": 1, "built_at": None, "nodes": [{"id": "m1", "type": "Measure", "label": "Fees Charged"},
                                                                                  {"id": "p1", "type": "Person", "label": "Wei Chen"}],
                                      "edges": [{"from": "m1", "to": "p1", "type": "owned_by"}]})
    put(plane, "graph/comments.json", {"m1": [{"id": "c1", "kind": "ambiguity", "text": "t", "state": "open", "at": "2026-10-05T09:00:00+00:00"},
                                              {"id": "c2", "kind": "suggestion", "text": "t", "state": "open", "at": "2026-10-05T09:00:00+00:00"}]})
    titles = sorted(x["title"] for x in L.suggestions(plane, WEI, datetime.now(timezone.utc)))
    assert titles == ["A suggestion on Fees Charged", "An ambiguity on Fees Charged"]
