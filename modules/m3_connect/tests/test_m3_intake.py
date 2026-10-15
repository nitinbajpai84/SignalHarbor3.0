"""M3-P02 intake: the request from the catalogue, the five demo files read and profiled, the benchmark file, bad files, companies kept apart,
the upload link. Demo files are the illustrative ones in packs/family_office/1/demo_module3/ (the README is the answer key)."""
import base64
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from m3_kit import BASE, BID, person, signed_baseline
from modules.m3_connect.domain import tabular as T

DEMO = Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1" / "demo_module3"
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc).timestamp()
SOURCES = [("S01", "Performance workbook", "performance_workbook.xlsx"), ("S02", "Northgate Custody daily file", "custody_daily_positions.csv"),
           ("S03", "Capital-calls mailbox", "capital_calls_export.json"), ("S04", "Index provider feed", "index_levels.csv"),
           ("S05", "Exposure workbook", "exposure_workbook.csv")]
MEASURES = {"K04": "Known obligations due", "K09": "Single-issuer concentration", "K10": "Private-market allocation", "K12": "Stale-valuation share",
            "K15": "Manager performance versus benchmark", "K16": "Excess return versus benchmark (alpha)"}
FIELDS = {  # table -> [(column as the office names it, the measures it feeds)]
    "T01": [("Fund / Manager", "K10, K15"), ("Asset Cls", "K10"), ("Opening Value (SGD)", "K15"), ("Closing Value (SGD)", "K10, K15"),
            ("Net Flows", "K15"), ("Fees Charged", "K15"), ("Period Return %", "K16")],
    "T02": [("Val Date", "K12"), ("Acct", "K12"), ("Security", "K12"), ("Qty", "K12"), ("Price", "K12"), ("Mkt Value", "K12")],
    "T03": [("notice_ref", "K04"), ("fund", "K04"), ("notice_dt", "K04"), ("due_dt", "K04"), ("amt", "K04"), ("status", "K04")],
    "T04": [("Date", "K16"), ("Index", "K16"), ("Level", "K16")],
    "T05": [("Issuer", "K09"), ("Country", "K09"), ("Sector", "K09"), ("Exposure Value (SGD)", "K09")]}


def cell(v):
    return {"value": v, "mark": "stated", "by": "Test Data Dan"}


def catalogue(extra_field=None):
    fields = []
    for tid, cols in FIELDS.items():
        for i, (name, feeds) in enumerate(cols):
            fields.append({"Field ID": cell(f"F-{tid}-{i}"), "Item ID": cell(tid), "Field name as in the source": cell(name), "Business meaning": cell(f"What {name} holds"),
                           "Data type": cell("decimal"), "Feeds KPI": cell(feeds), "Personal data class": cell("Neither")})
    fields += extra_field or []
    return {"sources": [{"Source ID": cell(s), "Source name": cell(n), "Data owner": cell("Owen Owner (illustrative)"), "Contains personal data?": cell("No")} for s, n, _ in SOURCES],
            "tables": [{"Item ID": cell(f"T0{i + 1}"), "Source ID": cell(s), "Name of table, file or document type": cell(n + " table"),
                        "Related KPIs": cell(", ".join(sorted({m for _, f in FIELDS[f"T0{i + 1}"] for m in f.split(", ")})))} for i, (s, n, _) in enumerate(SOURCES)],
            "fields": fields, "extractions": [],
            "kpis": [{"KPI ID": cell(k), "KPI name": cell(n), "Definition": cell(f"{n}, as the office defines it"), "Priority": cell("Must")} for k, n in MEASURES.items()]}


def demo_world(world, extra_field=None, company="m3-a", who="Lens Lee"):
    """A signed baseline whose catalogue is the demo office's, for company `company`. Returns (client, assessment id)."""
    signed_baseline(world, company) if company == "m3-a" else None
    plane = world.plane(company)
    out = next(plane.path("intents", "m2_baseline", "outcomes").glob("*.json"))
    doc = json.loads(out.read_text())
    doc["catalogue"] = catalogue(extra_field)
    out.write_text(json.dumps(doc))
    kp = plane.path("intents", "m2_baseline", BID, "kpis.json")
    kpis = json.loads(kp.read_text())
    kpis += [{"id": k, "name": n, "problem_ids": ["c1"], "governance": {"personal": "no", "sensitive": False, "may_see": []}} for k, n in MEASURES.items()]
    kp.write_text(json.dumps(kpis))
    world.app.state.m3_clock = lambda: NOW
    c = person(world, company, who)
    return c, c.post(f"{BASE}/assessments").json()["assessment"]["id"]


def url(aid, tail):
    return f"{BASE}/assessments/{aid}/intake{tail}"


def payload(name, data=None):
    data = (DEMO / name).read_bytes() if data is None else data
    return {"filename": name, "data": base64.b64encode(data).decode()}


def upload(c, aid, sid, name, data=None):
    return c.post(url(aid, f"/sources/{sid}/upload"), json=payload(name, data))


def intake_dir(world, aid, sid="S01", company="m3-a"):
    return world.plane(company).path("intents", "m3_connect", "assessments", aid, "intake", sid)


def visitor(world, token=None):
    c = TestClient(world.app)
    if token:
        c.headers["x-session-token"] = token
    return c


def col(profile, table, name):
    return next(c for t in profile["tables"] if t["file"].endswith("_" + table) for c in t["columns"] if c["name"] == name)


# ---- the automatic request --------------------------------------------------------------------------------------------------------

def test_the_request_lists_tables_columns_period_and_benchmark_from_the_catalogue(world):
    c, aid = demo_world(world)
    made = c.post(url(aid, "/requests"))
    assert made.status_code == 200 and made.json()["new"] == 5
    first = next(s for s in made.json()["sent"] if s["source_id"] == "S01")
    req = first["request"]
    assert req["period"]["label"] == "September 2026" and req["period"]["to"] == "2026-09-30"
    cols = {x["name"]: x for x in req["tables"][0]["columns"]}
    assert set(cols) == {n for n, _ in FIELDS["T01"]}
    assert [m["name"] for m in cols["Asset Cls"]["measures"]] == ["Private-market allocation"] and "What Asset Cls holds" == cols["Asset Cls"]["meaning"]
    assert {b["measure_name"] for b in req["benchmarks"]} == {MEASURES[k] for k in ("K10", "K15", "K16")}
    assert req["benchmarks"][0]["ask"].startswith("Your own reported figure for ") and req["benchmarks"][0]["ask"].endswith("same period (September 2026)")
    mail = first["email"]
    assert first["link_path"] in mail["body"] or first["link_path"].split("/intake/")[1] in mail["body"]
    assert "Asset Cls" in mail["body"] and "Nira" in mail["body"]
    again = c.post(url(aid, "/requests")).json()  # asking twice gives no second link
    assert again["new"] == 0
    listed = c.get(url(aid, "/requests")).json()
    assert listed["summary"] == {"asked": 5, "arrived": 0} and listed["not_yet_asked"] == []
    text = json.dumps(listed)
    assert "token" not in text and "di-" not in text
    steps = {s["id"]: s for s in c.get(f"{BASE}/assessments/{aid}").json()["steps"]}
    assert steps["request"]["state"] == "in_progress" and "Waiting for" in steps["request"]["waiting_on"] and steps["scan"]["state"] == "not_started"


def test_only_sources_in_zones_p1_and_p2_are_asked_when_the_source_map_is_there(world):
    c, aid = demo_world(world)
    folder = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    (folder / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "zone": "p1"}, {"id": "S02", "zone": "p2"}, {"id": "S03", "zone": "identify"}]}))
    sent = c.post(url(aid, "/requests")).json()["sent"]
    assert sorted(s["source_id"] for s in sent) == ["S01", "S02"]


# ---- the five demo files ------------------------------------------------------------------------------------------------------------

def test_all_five_demo_files_upload_and_profile_with_the_deliberate_problems(world):
    c, aid = demo_world(world)
    c.post(url(aid, "/requests"))
    got = {}
    for sid, _, name in SOURCES:
        r = upload(c, aid, sid, name)
        assert r.status_code == 200, r.text
        got[sid] = r.json()["profile"]
    perf = got["S01"]
    assert perf["tables"][0]["row_count"] == 40 and perf["files"][0]["kind"] == "xlsx"
    asset, fees = col(perf, "performance_workbook.xlsx", "Asset Cls"), col(perf, "performance_workbook.xlsx", "Fees Charged")
    assert asset["nulls"] == 4 and asset["fill"] == 0.9 and fees["nulls"] == 20 and fees["fill"] == 0.5
    assert fees["type"] == "integer" and col(perf, "performance_workbook.xlsx", "Period Return %")["type"] == "decimal"
    assert col(perf, "performance_workbook.xlsx", "Fund / Manager")["type"] == "string"
    assert all(x["match"] and x["match"]["confidence"] == "high" for x in perf["tables"][0]["columns"])
    kinds = {(g["kind"], g["column"]) for g in perf["gaps"]}
    assert kinds == {("some_empty", "Asset Cls"), ("half_empty", "Fees Charged")}
    assert next(g for g in perf["gaps"] if g["column"] == "Fees Charged")["measures"] == ["K15"]
    cust = got["S02"]["tables"][0]
    assert cust["row_count"] == 287 and cust["date_range"] == {"from": "2026-08-24", "to": "2026-09-22"} and cust["date_column"] == "Val Date"
    assert [(g["kind"], g["measures"]) for g in got["S02"]["gaps"]] == [("period_short", ["K12"])] and "22 September" in got["S02"]["gaps"][0]["text"]
    calls = got["S03"]["tables"][0]
    assert calls["row_count"] == 15 and calls["duplicate_key"] == {"columns": ["notice_ref"], "duplicates": 0}
    assert [(g["kind"], g["column"], g["field_id"], g["measures"]) for g in got["S03"]["gaps"]] == [("half_empty", "replaces", None, [])]  # a column that matches no field is still a gap when it is sparse
    idx = got["S04"]
    assert idx["tables"][0]["date_range"]["to"] == "2026-09-22" and [(g["kind"], g["measures"]) for g in idx["gaps"]] == [("period_short", ["K16"])]
    assert got["S05"]["tables"][0]["row_count"] == 24 and got["S05"]["gaps"] == []
    # the rows P03 reads: typed, empty stays empty, never as zero
    rows = json.loads((intake_dir(world, aid) / "rows.json").read_text())["tables"][0]["rows"]
    assert rows[3]["Asset Cls"] is None and rows[3]["Fees Charged"] is None and rows[1]["Asset Cls"] == "Public Equity" and rows[0]["Net Flows"] == -100000 and rows[0]["Fund / Manager"] == "Lakeside Equity Fund 1"
    assert any(p.name.endswith("_performance_workbook.xlsx") for p in (intake_dir(world, aid) / "files").iterdir()) and (intake_dir(world, aid) / "profile.json").is_file()
    assert json.loads((intake_dir(world, aid, "S02") / "rows.json").read_text())["tables"][0]["rows"][0]["Val Date"] == "2026-08-24"
    steps = {s["id"]: s["state"] for s in c.get(f"{BASE}/assessments/{aid}").json()["steps"]}
    assert steps["request"] == "done" and steps["scan"] == "done"


def test_a_missing_column_and_a_file_that_has_not_arrived_are_gaps(world):
    c, aid = demo_world(world)
    assert c.get(url(aid, "/sources/S01/profile")).json() == {"profile": None}
    trimmed = b"Fund / Manager,Asset Cls,Net Flows\nA,x,1\nB,y,2\n"
    r = upload(c, aid, "S01", "partial.csv", trimmed).json()["profile"]
    missing = {g["column"] for g in r["gaps"] if g["kind"] == "missing_column"}
    assert missing == {"Opening Value (SGD)", "Closing Value (SGD)", "Fees Charged", "Period Return %"}
    assert c.get(url(aid, "/sources/S02/profile")).json() == {"profile": None}


def test_personal_columns_are_flagged_and_never_shown_in_samples(world):
    extra = [{"Field ID": cell("F-PII"), "Item ID": cell("T05"), "Field name as in the source": cell("Owner email"), "Feeds KPI": cell("K09"), "Personal data class": cell("contact")}]
    c, aid = demo_world(world, extra)
    csv = b"Issuer,Country,Sector,Exposure Value (SGD),Owner email\nAlder,Singapore,Fin,100,a@example.test\nBirch,Japan,Tech,200,b@example.test\n"
    p = upload(c, aid, "S05", "exp.csv", csv).json()["profile"]
    email, issuer = col(p, "exp.csv", "Owner email"), col(p, "exp.csv", "Issuer")
    assert email["personal"] is True and email["samples"] == [] and "example.test" not in json.dumps(p)
    assert issuer["personal"] is False and issuer["samples"] == ["Alder", "Birch"]


# ---- a field with its own list (module 2, M2-E3) -------------------------------------------------------------------------------------

def test_a_field_limited_to_named_people_is_hidden_from_everyone_else(world):
    c, aid = demo_world(world)
    plane = world.plane("m3-a")
    out = next(plane.path("intents", "m2_baseline", "outcomes").glob("*.json"))
    doc = json.loads(out.read_text())
    next(f for f in doc["catalogue"]["fields"] if f["Field name as in the source"]["value"] == "Fees Charged")["Who may see it"] = cell("Test Fee Fran")
    out.write_text(json.dumps(doc))
    admin = person(world, "m3-a", "Admin Ada", ("company_admin",))
    analyst = person(world, "m3-a", "Analyst Abe", ("analyst",))
    fran = person(world, "m3-a", "Fee Fran", ("analyst",))
    for who in (admin, analyst, fran):
        who.post(url(aid, "/requests"))
    upload(admin, aid, "S01", "performance_workbook.xlsx")

    def seen(client):
        r = next(x for x in client.get(url(aid, "/requests")).json()["requests"] if x["source_id"] == "S01")
        return [x["name"] for x in r["tables"][0]["columns"]], r["profile"]
    cols, prof = seen(admin)
    assert "Fees Charged" in cols and col(prof, "performance_workbook.xlsx", "Fees Charged")["fill"] == 0.5
    cols, prof = seen(fran)
    assert "Fees Charged" in cols
    cols, prof = seen(analyst)
    assert "Fees Charged" not in cols and "Opening Value (SGD)" in cols
    text = json.dumps(prof)
    assert "Fees Charged" not in text and "half_empty" not in text and "A restricted column" in text
    only = analyst.get(url(aid, "/sources/S01/profile")).json()["profile"]
    assert "Fees Charged" not in json.dumps(only) and all(c.get("restricted") or c["fill"] is not None for c in only["tables"][0]["columns"])
    assert "Fees Charged" not in json.dumps(visitor(world).get(url(aid, "/requests")).json())  # and nothing at all with no session


# ---- benchmarks -----------------------------------------------------------------------------------------------------------------------

def test_the_benchmark_file_maps_to_the_six_measures(world):
    c, aid = demo_world(world)
    r = c.post(url(aid, "/benchmarks/upload"), json=payload("benchmarks_monthly_pack.csv"))
    assert r.status_code == 200, r.text
    got = r.json()
    by = {m["measure_id"]: m for m in got["measures"]}
    assert set(by) == set(MEASURES) and got["unmatched"] == [] and got["waiting_for"] == []
    k12 = by["K12"]
    assert k12["figure"] == 28.57 and k12["unit"] == "%" and k12["period_end"] == "2026-09-30" and k12["came_from"] == "Monthly investment committee pack, page 5"
    assert k12["given_by"] == "Test Lens Lee" and k12["matched"] == "auto" and by["K04"]["figure"] == 2610000 and by["K16"]["unit"] == "percentage points"
    assert by["K15"]["measure_name"] == "Manager performance versus benchmark" and by["K16"]["figure"] == 1.2
    stored = json.loads((world.plane("m3-a").path("intents", "m3_connect", "assessments", aid) / "benchmarks.json").read_text())
    assert stored["measures"]["K10"]["figure"] == 20.86 and stored["unmatched"] == []


def test_unmatched_benchmark_lines_are_mapped_by_hand_and_a_hand_mapping_is_kept(world):
    c, aid = demo_world(world)
    csv = (b"Measure,Figure,Unit,Period end,Where it came from\nPrivate markets allocation,20.86,%,2026-09-30,Pack p3\nMystery number,5,%,2026-09-30,Pack p9\n"
           b"No figure here,,,2026-09-30,Pack p1\n")
    got = c.post(url(aid, "/benchmarks/upload"), json=payload("b.csv", csv)).json()
    assert [m["measure_id"] for m in got["measures"]] == ["K10"] and [u["line"] for u in got["unmatched"]] == ["Mystery number", "No figure here"]
    assert got["unmatched"][1]["problem"] and {x["id"] for x in got["choices"]} == set(MEASURES)
    idx = got["unmatched"][0]["index"]
    assert c.post(url(aid, "/benchmarks/map"), json={"index": idx, "measure_id": "K99"}).status_code == 404
    assert c.post(url(aid, "/benchmarks/map"), json={"index": got["unmatched"][1]["index"], "measure_id": "K09"}).status_code == 409
    done = c.post(url(aid, "/benchmarks/map"), json={"index": idx, "measure_id": "K09"}).json()
    k9 = next(m for m in done["measures"] if m["measure_id"] == "K09")
    assert k9["figure"] == 5 and k9["matched"] == "person" and [u["line"] for u in done["unmatched"]] == ["No figure here"]
    again = c.post(url(aid, "/benchmarks/upload"), json=payload("b2.csv", b"Measure,Figure\nSingle-issuer concentration,99\n")).json()  # a file never overwrites a person's choice
    assert next(m for m in again["measures"] if m["measure_id"] == "K09")["figure"] == 5
    assert c.post(url(aid, "/benchmarks/upload"), json=payload("c.csv", b"Thing,Other\na,b\n")).status_code == 422


# ---- bad files ----------------------------------------------------------------------------------------------------------------------------

def xlsx_with(*extra):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook><sheets><sheet name="a" sheetId="1"/></sheets></workbook>')
        z.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData></sheetData></worksheet>")
        for n in extra:
            z.writestr(n, "x")
    return buf.getvalue()


@pytest.mark.parametrize("name,data,words", [
    ("evil.exe", b"MZ", "Excel"), ("macro.xlsm", xlsx_with(), "Excel"), ("notes.pdf", b"%PDF", "Excel"),
    ("empty.csv", b"", "empty"), ("fake.xlsx", b"just text", "not an Excel"), ("macros.xlsx", xlsx_with("xl/vbaProject.bin"), "macros"),
    ("dup.csv", b"a,a\n1,2\n", "once"), ("flat.json", b'{"a": 1}', "list of records"), ("broken.json", b"{not json", "could not be read"),
    ("nul.csv", b"a,b\n1,\x00\n", "could not be read"), ("header_only.csv", b"a,b\n", "no rows"),
    ("huge.csv", None, "larger"),
    ("zipbomb.xlsx", b"PK\x03\x04garbage", "damaged")])
def test_bad_files_are_refused_in_plain_words_and_nothing_is_kept(world, name, data, words):
    c, aid = demo_world(world)
    data = b"a,b\n" + b"1,2\n" * (T.MAX_FILE_BYTES // 4 + 10) if data is None else data
    r = upload(c, aid, "S01", name, data)
    assert r.status_code in (400, 413, 422), r.text[:300]
    assert words.lower() in r.json()["message"].lower() and "Traceback" not in r.text
    assert not intake_dir(world, aid).exists() and c.get(url(aid, "/sources/S01/profile")).json() == {"profile": None}


def test_a_request_with_no_file_or_bad_encoding_is_refused(world):
    c, aid = demo_world(world)
    assert c.post(url(aid, "/sources/S01/upload"), json={"filename": "a.csv", "data": "***not base64***"}).status_code == 400
    assert c.post(url(aid, "/sources/S01/upload"), json={}).status_code == 400
    assert c.post(url(aid, "/sources/S99/upload"), json=payload("a.csv", b"a,b\n1,2\n")).status_code == 404
    assert c.post(url(aid, "/sources/..%2Fetc/upload"), json=payload("a.csv", b"a,b\n1,2\n")).status_code in (403, 404)


def test_the_reader_skips_a_banner_and_keeps_empty_cells_in_place():
    h, rows = T.read_table("a.csv", b'"Illustrative, synthetic. Not real."\nx,y,z\n1,,3\n')
    assert h == ["x", "y", "z"] and rows == [["1", "", "3"]]
    h, rows = T.read_table("a.json", json.dumps({"rows": [{"p": 1, "q": None}, {"p": 2, "q": "t"}]}).encode())
    assert h == ["p", "q"] and rows == [[1, None], [2, "t"]]
    h, rows = T.read_table("a.json", json.dumps([{"p": 1}]).encode())
    assert rows == [[1]]


# ---- other companies and roles -----------------------------------------------------------------------------------------------------

def test_another_company_cannot_read_or_write_the_files(world):
    c, aid = demo_world(world)
    c.post(url(aid, "/requests"))
    assert upload(c, aid, "S01", "performance_workbook.xlsx").status_code == 200
    other = person(world, "m3-b", "Other Olga")
    for r in (other.get(url(aid, "/requests")), other.get(url(aid, "/sources/S01/profile")), other.get(url(aid, "/benchmarks")),
              upload(other, aid, "S01", "performance_workbook.xlsx"), other.post(url(aid, "/requests"))):
        assert r.status_code in (403, 404), r.text
    assert not intake_dir(world, aid, company="m3-b").exists()
    assert "Fund" not in json.dumps([other.get(url(aid, "/requests")).json()])


def test_roles_and_the_module_switch(world):
    c, aid = demo_world(world)
    visitor_role = person(world, "m3-a", "Guest Gus", ("participant",))
    assert visitor_role.get(url(aid, "/requests")).status_code == 403
    assert upload(visitor_role, aid, "S01", "performance_workbook.xlsx").status_code == 403
    assert visitor(world).get(url(aid, "/requests")).status_code in (401, 403)
    off = person(world, "m3-off", "Off Ola")
    assert off.get(url(aid, "/requests")).status_code in (403, 404)


def test_an_empty_company_and_a_company_with_no_source_has_an_honest_empty_state(world):
    empty = person(world, "m3-empty", "Empty Ed")
    assert empty.get(url("a" * 32, "/requests")).status_code == 404
    c, aid = demo_world(world)
    folder = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    (folder / "sources.json").write_text(json.dumps([]))
    assert c.post(url(aid, "/requests")).json() == {"sent": [], "new": 0}
    assert c.get(url(aid, "/requests")).json()["summary"] == {"asked": 0, "arrived": 0}


def test_a_second_industry_company_gets_its_own_request(world):
    from m3_kit import copy_baseline
    c, aid = demo_world(world)
    copy_baseline(world, "m3-a", "m3-b")
    cb, bid_ = demo_world(world, company="m3-b", who="Lens Bo")
    assert cb.post(url(bid_, "/requests")).json()["new"] == 5 and bid_ != aid
    assert [r["source_id"] for r in c.get(url(aid, "/requests")).json()["requests"]] == []


# ---- the link -------------------------------------------------------------------------------------------------------------------------

def token_of(sent, sid="S01"):
    return next(s for s in sent if s["source_id"] == sid)["link_path"].removeprefix("/intake/")


def test_the_link_flow_open_upload_remind_revoke_relink(world):
    c, aid = demo_world(world)
    sent = c.post(url(aid, "/requests")).json()["sent"]
    token = token_of(sent)
    assert token.startswith("di-") and token not in json.dumps(c.get(url(aid, "/requests")).json())
    stored = (world.plane("m3-a").path("intents", "m3_connect", "assessments", aid) / "requests.json").read_text()
    assert token not in stored and "token_hash" in stored  # only the hash is kept
    form = visitor(world, token).post(f"{BASE}/intake/link/form")
    assert form.status_code == 200 and form.json()["source_name"] == "Performance workbook" and form.json()["state"] == "opened"
    assert "Northgate" not in form.text and "Val Date" not in form.text and "token" not in form.text
    up = visitor(world, token).post(f"{BASE}/intake/link/upload", json=payload("performance_workbook.xlsx"))
    assert up.status_code == 200 and up.json()["state"] == "arrived" and up.json()["profile"]["tables"][0]["row_count"] == 40
    bench = visitor(world, token).post(f"{BASE}/intake/link/upload", json={**payload("benchmarks_monthly_pack.csv"), "kind": "benchmark"})
    assert bench.status_code == 200
    figures = {m["measure_id"] for m in c.get(url(aid, "/benchmarks")).json()["measures"]}
    assert figures == {"K10", "K15", "K16"}  # the owner of this source can give only their own source's measures
    rid = form.json()["id"]
    assert c.post(url(aid, f"/requests/{rid}/remind")).status_code == 409  # files are in: nothing to remind
    r2 = next(s for s in sent if s["source_id"] == "S02")["request"]["id"]
    rem = c.post(url(aid, f"/requests/{r2}/remind")).json()
    assert "gentle reminder" in rem["email"]["body"] and len(rem["request"]["reminders"]) == 1
    t2 = token_of(sent, "S02")
    assert c.post(url(aid, f"/requests/{r2}/revoke")).json()["request"]["link"] == "revoked"
    gone = visitor(world, t2).post(f"{BASE}/intake/link/form")
    assert gone.status_code == 409 and "withdrawn" in gone.json()["message"]
    fresh = c.post(url(aid, f"/requests/{r2}/relink")).json()
    new = fresh["link_path"].removeprefix("/intake/")
    assert visitor(world, new).post(f"{BASE}/intake/link/form").status_code == 200
    assert visitor(world, t2).post(f"{BASE}/intake/link/form").status_code == 404  # the old link is dead for everyone


def test_the_link_token_is_checked_the_m2_way(world):
    c, aid = demo_world(world)
    token = token_of(c.post(url(aid, "/requests")).json()["sent"])
    v = visitor(world)
    assert v.post(f"{BASE}/intake/link/form", json={"token": token}).status_code == 404
    assert v.post(f"{BASE}/intake/link/form?token={token}").status_code == 404
    rid = token.split("-")[1]
    answers = {json.dumps([r.status_code, r.json()]) for r in (visitor(world, bad).post(f"{BASE}/intake/link/form") for bad in
               ("nonsense", f"di-{'0' * 32}-{'a' * 43}", f"di-{rid}-{'a' * 43}"))}
    assert len(answers) == 1
    wrong = visitor(world, f"di-{'0' * 32}-{'a' * 43}")
    codes = [wrong.post(f"{BASE}/intake/link/form").status_code for _ in range(6)]
    assert codes[5] == 429 and visitor(world, token).post(f"{BASE}/intake/link/form").status_code == 429


def test_an_expired_link_is_refused_with_its_reason(world):
    c, aid = demo_world(world)
    token = token_of(c.post(url(aid, "/requests")).json()["sent"])
    assert visitor(world, token).post(f"{BASE}/intake/link/form").status_code == 200
    world.app.state.m3_clock = lambda: NOW + 15 * 86400
    r = visitor(world, token).post(f"{BASE}/intake/link/form")
    assert r.status_code == 409 and "expired" in r.json()["message"]
    assert visitor(world, token).post(f"{BASE}/intake/link/upload", json=payload("a.csv", b"a,b\n1,2\n")).status_code in (409, 429)
    assert not intake_dir(world, aid).exists()


def test_a_link_cannot_reach_another_sources_files_or_the_organiser_routes(world):
    c, aid = demo_world(world)
    token = token_of(c.post(url(aid, "/requests")).json()["sent"])
    v = visitor(world, token)
    assert v.get(url(aid, "/requests")).status_code in (401, 403) and v.get(url(aid, "/sources/S02/profile")).status_code in (401, 403)
    assert v.post(url(aid, "/benchmarks/map"), json={"index": 0, "measure_id": "K10"}).status_code in (401, 403)


# ---- review fixes: module 2's source and class rules, caps, names ---------------------------------------------------------------------

def edit_catalogue(world, change):
    out = next(world.plane("m3-a").path("intents", "m2_baseline", "outcomes").glob("*.json"))
    doc = json.loads(out.read_text())
    change(doc["catalogue"])
    out.write_text(json.dumps(doc))


def seen_by(client, aid, sid):
    return next((x for x in client.get(url(aid, "/requests")).json()["requests"] if x["source_id"] == sid), None)


def test_a_source_that_holds_personal_data_is_hidden_from_anyone_not_named(world):
    c, aid = demo_world(world)

    def change(cat):
        s = next(s for s in cat["sources"] if s["Source ID"]["value"] == "S05")
        s["Contains personal data?"], s["Who may see it"] = cell("Yes"), cell("Test Fee Fran")
    edit_catalogue(world, change)
    admin, analyst, fran = person(world, "m3-a", "Admin Ada", ("company_admin",)), person(world, "m3-a", "Analyst Abe", ("analyst",)), person(world, "m3-a", "Fee Fran", ("analyst",))
    sent = admin.post(url(aid, "/requests")).json()["sent"]
    assert "S05" not in [s["source_id"] for s in sent]  # a Yes source needs a name; the head of data is not on it
    assert fran.post(url(aid, "/requests")).status_code == 200 and seen_by(fran, aid, "S05") is not None
    assert upload(fran, aid, "S05", "exposure_workbook.csv").status_code == 200
    assert seen_by(analyst, aid, "S05") is None and analyst.get(url(aid, "/sources/S05/profile")).status_code == 404
    assert upload(analyst, aid, "S05", "exposure_workbook.csv").status_code == 404
    assert "Issuer" not in json.dumps(analyst.get(url(aid, "/requests")).json())


def test_a_field_class_other_than_neither_is_for_named_people_only(world):
    c, aid = demo_world(world)

    def change(cat):
        next(f for f in cat["fields"] if f["Field name as in the source"]["value"] == "Fees Charged")["Personal data class"] = cell("Contact")
        next(f for f in cat["fields"] if f["Field name as in the source"]["value"] == "Asset Cls")["Personal data class"] = cell("Neither")
    edit_catalogue(world, change)
    admin, analyst = person(world, "m3-a", "Admin Ada", ("company_admin",)), person(world, "m3-a", "Analyst Abe", ("analyst",))
    admin.post(url(aid, "/requests"))
    upload(admin, aid, "S01", "performance_workbook.xlsx")
    mine = seen_by(admin, aid, "S01")
    fees = col(mine["profile"], "performance_workbook.xlsx", "Fees Charged")
    assert "Fees Charged" in [x["name"] for x in mine["tables"][0]["columns"]] and fees["personal"] is True and fees["samples"] == []
    assert col(mine["profile"], "performance_workbook.xlsx", "Asset Cls")["samples"]  # "Neither" is open
    r = seen_by(analyst, aid, "S01")
    assert "Fees Charged" not in [x["name"] for x in r["tables"][0]["columns"]]
    assert "Fees Charged" not in json.dumps(r["profile"]) and "half_empty" not in json.dumps(r["profile"])


def test_a_not_sure_source_makes_every_unmatched_column_personal_and_a_blank_class_follows_the_source(world):
    c, aid = demo_world(world)
    def change(cat):
        next(s for s in cat["sources"] if s["Source ID"]["value"] == "S05").update({"Contains personal data?": cell("Not sure")})
        next(f for f in cat["fields"] if f["Field name as in the source"]["value"] == "Issuer")["Personal data class"] = cell("")
    edit_catalogue(world, change)
    csv = b"Issuer,Country,Sector,Exposure Value (SGD),Mystery\nAlder,Singapore,Fin,100,zz-secret\n"
    p = upload(c, aid, "S05", "exp.csv", csv).json()["profile"]
    assert col(p, "exp.csv", "Mystery")["personal"] is True and col(p, "exp.csv", "Mystery")["samples"] == [] and "zz-secret" not in json.dumps(p)
    assert col(p, "exp.csv", "Issuer")["personal"] is True and col(p, "exp.csv", "Issuer")["samples"] == []  # blank class: the source's answer


def test_cell_count_and_json_depth_are_capped(monkeypatch):
    monkeypatch.setattr(T, "MAX_CELLS", 30)
    with pytest.raises(T.Refusal):
        T.read_table("a.csv", b"a,b,c,d,e\n" + b"1,2,3,4,5\n" * 10)
    with pytest.raises(T.Refusal):
        T.read_table("a.json", b"[" * 100000 + b"]" * 100000)
    with pytest.raises(T.Refusal):
        T.read_table("a.json", b'[{"a": ' + b"[" * 200 + b"1" + b"]" * 200 + b"}]")


def test_a_recursive_body_is_a_plain_400(world):
    c, aid = demo_world(world)
    r = c.post(url(aid, "/benchmarks/map"), content=b"[" * 100000, headers={"content-type": "application/json"})
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


def test_stored_file_names_carry_a_hash_and_unmatched_lines_are_capped(world):
    c, aid = demo_world(world)
    assert upload(c, aid, "S04", "CON.csv", (DEMO / "index_levels.csv").read_bytes()).status_code == 200
    names = [p.name for p in (intake_dir(world, aid, "S04") / "files").iterdir()]
    assert len(names) == 1 and names[0].endswith("_CON.csv") and len(names[0]) > len("_CON.csv")
    lines = b"Measure,Figure\n" + b"".join(f"Nothing {i},{i}\n".encode() for i in range(500))
    got = c.post(url(aid, "/benchmarks/upload"), json=payload("many.csv", lines)).json()
    assert len(got["unmatched"]) == 200

