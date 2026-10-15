"""Module 3 scaffold: start an assessment from a signed baseline, read it with its six steps, keep restricted measures restricted,
keep companies apart, honour the module switch, and keep manifest and permission table in agreement."""
import json
from pathlib import Path

import pytest

from m3_kit import BASE, copy_baseline, person, restrict, signed_baseline
from modules.m3_connect.domain import steps as S
from sh_platform.auth.permissions import load_permissions
from sh_platform.manifest import load_manifest, manifest_route_gaps

MANIFEST = Path(__file__).resolve().parents[1] / "manifest.yaml"


def start(world, company="m3-a", name="Lens Lee"):
    c = person(world, company, name)
    r = c.post(f"{BASE}/assessments")
    assert r.status_code == 201, r.text
    return c, r.json()["assessment"]


def test_create_from_a_signed_baseline_and_read_six_steps(world):
    signed_baseline(world)
    c, a = start(world)
    assert a["state"] == "draft" and a["charter_outcome_id"] == "c" * 32 and a["created_by"] == "Test Lens Lee"
    again = c.post(f"{BASE}/assessments")
    assert again.status_code == 200 and again.json()["assessment"]["id"] == a["id"]  # one assessment per signed baseline
    got = c.get(f"{BASE}/assessments/{a['id']}").json()
    assert [s["id"] for s in got["steps"]] == ["map", "request", "scan", "trial", "findings", "plan"]
    assert all(s["state"] == "not_started" and s["waiting_on"] for s in got["steps"])
    assert {m["id"] for m in got["inputs"]["measures"]} == {"K1", "K2", "K3"}
    k1 = next(m for m in got["inputs"]["measures"] if m["id"] == "K1")
    assert k1["restricted"] is False and k1["definition"] and k1["priority"] == "Must" and k1["owners"]["data"]
    assert [p["title"] for p in got["inputs"]["pain_points"]] == ["Late packs"]
    assert got["inputs"]["levers"][0]["measures"] == []
    listed = c.get(f"{BASE}/assessments").json()
    assert [x["id"] for x in listed["assessments"]] == [a["id"]] and listed["signed_baseline"] is True
    assert listed["can_start"] is False and listed["assessments"][0]["baseline_label"] == listed["baseline_label"] != ""
    assert c.get(f"{BASE}/status").json() == {"module": "m3_connect", "baselines": 1, "assessments": 1}


def test_a_newer_signed_baseline_can_be_started(world):
    signed_baseline(world)
    c, a = start(world)
    folder = world.plane("m3-a").path("intents", "m2_baseline", "outcomes")
    old = next(folder.glob("*.json"))
    newer = {**json.loads(old.read_text()), "outcome_id": "d" * 32, "signed_at": "2999-01-01T00:00:00+00:00", "title": "Second baseline"}
    (folder / f"{'d' * 32}.json").write_text(json.dumps(newer))
    listed = c.get(f"{BASE}/assessments").json()
    assert listed["can_start"] is True and listed["baseline_label"] == "Second baseline"
    assert listed["assessments"][0]["baseline_label"] != "Second baseline"
    assert c.post(f"{BASE}/assessments").status_code == 201
    assert c.get(f"{BASE}/assessments").json()["can_start"] is False


def test_no_signed_baseline_gives_409_in_plain_words_and_an_honest_empty_list(world):
    c = person(world, "m3-empty", "Empty Ed")
    assert c.get(f"{BASE}/assessments").json() == {"assessments": [], "signed_baseline": False, "can_start": False, "baseline_label": ""}
    r = c.post(f"{BASE}/assessments")
    assert r.status_code == 409 and "signed baseline" in r.json()["message"] and "/" not in r.json()["message"]
    assert c.get(f"{BASE}/status").json() == {"module": "m3_connect", "baselines": 0, "assessments": 0}


def test_an_unsigned_baseline_is_not_enough(world):
    from m3_kit import seed
    seed(world, "m3-a")  # baseline files only, nobody signed
    assert person(world, "m3-a", "Lens Lee").post(f"{BASE}/assessments").status_code == 409


def test_two_industries_each_start_from_their_own_baseline(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-b")
    (_, a), (cb, b) = start(world, "m3-a"), start(world, "m3-b", "Lens Bo")
    assert a["id"] != b["id"]
    assert [x["id"] for x in cb.get(f"{BASE}/assessments").json()["assessments"]] == [b["id"]]


def test_one_person_without_module_1_still_starts(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-solo", with_charter=False)
    c, a = start(world, "m3-solo", "Solo Sam")
    got = c.get(f"{BASE}/assessments/{a['id']}").json()
    assert got["inputs"]["pain_points"] == [] and len(got["inputs"]["measures"]) == 3  # no charter: nothing invented


def test_restricted_measure_is_reduced_for_someone_not_named(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    _, a = start(world)
    def measure(client):
        got = client.get(f"{BASE}/assessments/{a['id']}").json()["inputs"]
        return next(m for m in got["measures"] if m["id"] == "K2"), got
    outsider, inputs = measure(person(world, "m3-a", "Other Olly"))
    assert outsider == {"id": "K2", "name": "A restricted measure", "restricted": True}
    assert "Exposure concentration" not in json.dumps(inputs)
    named, _ = measure(person(world, "m3-a", "Reader Rae"))
    assert named["name"] == "Exposure concentration" and named["definition"]
    admin, _ = measure(person(world, "m3-a", "Head Hal", ("company_admin",)))
    assert admin == outsider  # A-069: once somebody is named, the head of data is outside the list like anyone else


def test_another_companys_assessment_is_unreachable(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-b")
    _, a = start(world, "m3-a")
    other = person(world, "m3-b", "Lens Bo")
    assert other.get(f"{BASE}/assessments/{a['id']}").status_code == 404
    assert other.get(f"{BASE}/assessments/..%2F..%2Fx").status_code in (403, 404)
    assert other.get(f"{BASE}/assessments").json()["assessments"] == []


def test_a_company_without_module_3_is_refused(world):
    c = person(world, "m3-off", "Off Olga")
    for method, tail in (("get", "/status"), ("get", "/assessments"), ("post", "/assessments")):
        assert getattr(c, method)(BASE + tail).status_code in (403, 404)


def test_a_role_outside_the_three_is_refused(world):
    signed_baseline(world)
    assert person(world, "m3-a", "Guest Gus", ("participant",)).get(f"{BASE}/assessments").status_code == 403


def test_a_package_can_report_its_step(world):
    signed_baseline(world)
    c, a = start(world)
    S.register("map", lambda d: {"state": "in_progress", "waiting_on": "Lens is scoring."})
    S.register("request", lambda d: {"state": "done"})
    try:
        got = c.get(f"{BASE}/assessments/{a['id']}").json()["steps"]
    finally:
        S._registry.clear()
    assert (got[0]["state"], got[0]["waiting_on"]) == ("in_progress", "Lens is scoring.")
    assert (got[1]["state"], got[1]["waiting_on"]) == ("done", "")
    with pytest.raises(ValueError):
        S.register("nope", lambda d: {})


def _edit_outcome(world, company, change):
    path = next(world.plane(company).path("intents", "m2_baseline", "outcomes").glob("*.json"))
    rec = json.loads(path.read_text())
    change(rec)
    path.write_text(json.dumps(rec))


def test_a_gap_naming_a_restricted_source_is_not_shown_to_someone_outside_its_list(world):
    signed_baseline(world)

    def add(rec):
        rec["catalogue"]["sources"][0]["Contains personal data?"] = {"value": "Yes", "mark": "stated", "by": "x", "at": "", "from": ""}  # module 2: "No" is open to all
        rec["catalogue"]["sources"][0]["Who may see it"] = {"value": "Test Reader Rae", "mark": "stated", "by": "x", "at": "", "from": ""}
        rec["gaps"].append({"id": "G9", "type": "personal_undecided", "kpi_id": None, "where": "sources S01: Contains personal data?"})
    _edit_outcome(world, "m3-a", add)
    _, a = start(world)

    def gaps(client):
        return client.get(f"{BASE}/assessments/{a['id']}").json()["inputs"]["gaps"]
    assert all("S01" not in g["where"] for g in gaps(person(world, "m3-a", "Other Olly")))
    assert any("S01" in g["where"] for g in gaps(person(world, "m3-a", "Reader Rae")))


def test_an_unsigned_outcome_file_is_refused(world):
    signed_baseline(world)
    _edit_outcome(world, "m3-a", lambda rec: rec.update(signatures=[], signed_at=""))
    c = person(world, "m3-a", "Lens Lee")
    assert c.get(f"{BASE}/status").json()["baselines"] == 0
    assert c.get(f"{BASE}/assessments").json()["signed_baseline"] is False
    assert c.post(f"{BASE}/assessments").status_code == 409


def test_manifest_and_permission_table_agree():
    m = load_manifest(MANIFEST)
    assert m.id == "m3_connect" and m.agent == "Lens" and m.name == "Assess and plan"
    assert manifest_route_gaps(m, load_permissions()) == []
    perms = load_permissions()
    assert {k for k in perms.routes if "/m3_connect/" in k} == {f"{r.method} {r.path}" for r in m.routes}  # no route only on one side
    organiser = {"company_admin", "sponsor", "analyst"}
    # every route is for the organiser roles, except the owner's upload link (M3-P02): a guest `entry` route, its handler checks the token
    assert all(set(r.roles) == organiser or r.path.startswith("/api/modules/m3_connect/intake/link/") for r in m.routes)
