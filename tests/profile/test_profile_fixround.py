"""LI-PROFILE fix round: a restricted file's name never reaches a non-admin, the provenance shape, the drafter flag, the asks cap."""
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from pf_kit import PACK, PEOPLE, SYSTEMS
from sh_platform.profile import Viewer, asks, read, reader, record, store

ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
TOM = Viewer("Tom Ng", frozenset({"analyst"}))


def put(c, gid, name, data, **extra):
    return c.post(f"/api/profile/inputs/{gid}/upload", json={"filename": name, "data": base64.b64encode(data).decode(), **extra})


def test_a_restricted_files_name_reaches_no_non_admin_route(env):
    admin = env.login("company_admin")
    assert put(admin, 6, "SECRETSYS.csv", SYSTEMS, restricted=True).status_code == 200
    seen = admin.get("/api/profile").text
    assert "SECRETSYS" in seen  # the admin still sees it
    for role in ("analyst", "sponsor"):
        c = env.login(role)
        assert "SECRETSYS" not in c.get("/api/profile").text
        assert "SECRETSYS" not in c.get("/api/profile/readiness").text


def test_results_and_documents_hide_only_the_restricted_entries(plane, stub):
    reader.add_upload(plane, 6, "Mei Tan", "open.csv", SYSTEMS, stub)
    reader.add_upload(plane, 6, "Mei Tan", "SECRETSYS.csv", SYSTEMS, stub, restricted=True)
    g = read(plane, TOM)["inputs"]["g6"]
    assert [d["name"] for d in g["documents"]["value"]] == ["open.csv"] and [r["name"] for r in g["results"]["value"]] == ["open.csv"]
    assert {d["name"] for d in read(plane, ADMIN)["inputs"]["g6"]["results"]["value"]} == {"open.csv", "SECRETSYS.csv"}


def test_from_is_a_plain_label_with_no_id_and_ref_carries_the_machine_pointer(plane, stub):
    reader.add_upload(plane, 3, "Mei Tan", "pack.csv", PACK, stub)
    f = read(plane, ADMIN)["reported_figures"]["single-issuer-concentration@2026-09-30"]["figure"]
    assert f["from"] == "Investment committee pack, page 4"
    assert f["ref"]["kind"] == "document" and f["ref"]["id"] not in f["from"]
    assert f["agent"] == "lens"


def test_a_sample_is_labelled_as_a_sample_file(plane, stub):
    reader.add_upload(plane, 8, "Mei Tan", "sept.csv", b"a,b\n1,2\n3,4\n", stub)
    c = read(plane, ADMIN)["samples"]["sept-csv"]["file"]
    assert c["from"] == "Sample file sept.csv" and c["ref"]["kind"] == "sample"


def test_a_cell_pointing_at_a_document_the_viewer_may_not_see_is_blanked(plane):
    record(plane, "inputs.g1.documents", [{"id": "d1", "name": "pay.csv", "restricted": True}],
           {"mark": "stated", "by": "Mei Tan", "from": "Uploaded by Mei Tan"})
    record(plane, "people.ann.name", "Ann", {"mark": "stated", "by": "Lens", "agent": "lens", "from": "pay.csv, sheet 1",
                                            "ref": {"kind": "document", "id": "d1", "page": "sheet 1"}})
    mine = read(plane, ADMIN)["people"]["ann"]["name"]
    assert mine["from"] == "pay.csv, sheet 1" and mine["ref"]["id"] == "d1"
    seen = read(plane, TOM)["people"]["ann"]["name"]
    assert seen["from"] == "a restricted document" and "ref" not in seen and seen["value"] == "Ann"
    assert "pay.csv" not in json.dumps(read(plane, TOM))


def test_a_person_called_lens_is_a_person_not_an_agent(plane):
    person = {"mark": "stated", "by": "Lens", "from": "Interview with Lens", "ref": {"kind": "interview", "id": "q1"}}
    record(plane, "people.x.role", "Analyst", person)
    draft = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "people.csv"}
    assert record(plane, "people.x.role", "Draft", draft) is None  # a person's cell is kept even though both are called Lens
    assert record(plane, "people.y.role", "A", draft)["agent"] == "lens"
    assert record(plane, "people.y.role", "B", person)["value"] == "B"
    assert "agent" not in read(plane, ADMIN)["people"]["x"]["role"]
    assert store.is_agent({"by": "Nira"}) is False  # the display name alone decides nothing


def test_asks_keep_the_latest_per_group_and_person_and_drop_expired(plane):
    now = datetime.now(timezone.utc)
    first = asks.mint(plane, 3, now - timedelta(hours=400), person="Mei Tan")  # expired by now
    old = asks.mint(plane, 3, now - timedelta(hours=2), person="Mei Tan")
    other = asks.mint(plane, 3, now, person="Dan Data")
    new = asks.mint(plane, 3, now, person="Mei Tan")
    rows = json.loads(plane.path("context", "profile", "asks.json").read_text(encoding="utf-8"))
    assert len(rows) == 2 and {r["person"] for r in rows} == {"Mei Tan", "Dan Data"}
    assert asks.check(plane, new) == 3 and asks.check(plane, other) == 3
    assert asks.check(plane, old) is None and asks.check(plane, first) is None  # an older ask stops working
    asks.mint(plane, 6, now)  # a different group is kept
    assert len(json.loads(plane.path("context", "profile", "asks.json").read_text(encoding="utf-8"))) == 3


def _system(plane, sid, name, **cells):
    LENSC = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "systems.csv"}
    for k, v in {"name": name, "owner": "Vivian Chua", "lands": "emailed extract", "tables": ["bands"], **cells}.items():
        record(plane, f"systems.{sid}.{k}", v, LENSC)


def test_a_restricted_or_personal_system_shows_only_a_restricted_source(plane):
    LENSC = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "systems.csv"}
    _system(plane, "payroll-file", "Payroll file", personal_data="Yes: names, bands", restricted=True, may_see=["Lena Ho"])
    _system(plane, "custody", "Custody feed", personal_data="Not sure (narratives)", may_see=[], owner="Harvey", lands="portal", tables=["positions"])  # not sure, nobody named: open
    _system(plane, "crm", "Client notes", personal_data="Not sure", may_see=["Lena Ho"], owner="Vivian Chua")  # not sure with names: closed, the sponsor passes
    _system(plane, "prices", "Price feed", personal_data="No", owner="Harvey", lands="portal", tables=["prices"])
    record(plane, "samples.pay-csv.system", "Payroll file", LENSC)
    record(plane, "samples.pay-csv.file", "pay.csv", LENSC)
    record(plane, "samples.px-csv.system", "Price feed", LENSC)
    record(plane, "reported_figures.bonus.system", "payroll-file", LENSC)
    record(plane, "reported_figures.bonus.figure", 1, LENSC)
    tom = read(plane, TOM)
    shut = {k: v for k, v in tom["systems"].items() if k.startswith("restricted-")}
    assert len(shut) == 2 and all(v == {"restricted": True, "label": "A restricted source"} for v in shut.values())
    assert set(tom["systems"]) - set(shut) == {"custody", "prices"}
    assert set(tom["samples"]) == {"px-csv"} and tom["reported_figures"] == {}
    text = json.dumps(tom)
    for leak in ("Payroll", "payroll", "Vivian", "bands", "emailed extract", "Client notes", "pay.csv"):
        assert leak not in text, leak
    admin = read(plane, ADMIN)  # A-069: "Yes" with a named list is shut to the admin too; "Not sure" lets the admin pass by role
    assert "crm" in admin["systems"] and "payroll-file" not in admin["systems"] and "pay-csv" not in admin["samples"] and "Payroll" not in json.dumps(admin)
    sponsor = read(plane, Viewer("Sue Sponsor", frozenset({"sponsor"})))
    assert "crm" in sponsor["systems"] and "payroll-file" not in sponsor["systems"]  # "Yes": the named and the admin only
    lena = read(plane, Viewer("Lena Ho", frozenset({"analyst"})))
    assert {"payroll-file", "crm"} <= set(lena["systems"]) and "pay-csv" in lena["samples"]


def test_a_figure_or_sample_for_a_measure_the_viewer_may_not_see_is_dropped(plane, stub):
    LENSC = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "rules.csv"}
    record(plane, "governance.field_rules.capital-called.field", "Capital called", LENSC)
    record(plane, "governance.field_rules.capital-called.personal", "yes", LENSC)
    record(plane, "governance.field_rules.capital-called.may_see", ["Mei Tan"], LENSC)
    record(plane, "governance.restricted_areas.hr.area", "HR", LENSC)
    record(plane, "governance.restricted_areas.hr.may_see", [], LENSC)
    reader.add_upload(plane, 3, "Mei Tan", "pack.csv", b"Measure,Figure,Unit,Period end\nCapital called,987654,SGD,2026-09-30\nHR,4321,n,2026-09-30\nPrivate-market allocation,24.36,%,2026-09-30\n", stub)
    reader.add_upload(plane, 8, "Mei Tan", "Capital_Called.csv", b"a,b\n1,2\n3,4\n", stub)
    reader.add_upload(plane, 8, "Mei Tan", "prices.csv", b"a,b\n1,2\n3,4\n", stub)
    tom = read(plane, TOM)
    assert [f["measure"]["value"] for f in tom["reported_figures"].values()] == ["Private-market allocation"]
    assert [s["file"]["value"] for s in tom["samples"].values()] == ["prices.csv"]
    assert {f["figure"]["value"] for f in tom["reported_figures"].values()} == {24.36} and "Capital_Called" not in json.dumps(tom)
    mei = read(plane, Viewer("Mei Tan", frozenset({"analyst"})))
    assert 987654 in {f["figure"]["value"] for f in mei["reported_figures"].values()} and len(mei["samples"]) == 2
    assert len(read(plane, ADMIN)["reported_figures"]) == 3


def test_hidden_systems_are_numbered_not_hashed(plane):
    LENSC = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "systems.csv"}
    for sid in ("payroll-file", "bonus-sheet"):
        record(plane, f"systems.{sid}.name", sid, LENSC)
        record(plane, f"systems.{sid}.restricted", True, LENSC)
    record(plane, "systems.prices.name", "Prices", LENSC)
    keys = list(read(plane, TOM)["systems"])
    assert sorted(keys) == ["prices", "restricted-1", "restricted-2"]  # in the order of the names, with nothing derived from them
