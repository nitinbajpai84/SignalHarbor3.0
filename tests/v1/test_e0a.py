"""E0a: the core model seeds as version 1; describe and has_field; a broken script is refused with its line; a core change is refused;
an extension makes a proposal with a plain diff; the proposer cannot approve; approval switches current and builds the DuckDB tables;
a breaking change is flagged; the routes check seats."""
import json
import shutil
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1.i2_north import Refused

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
HEAD = Viewer("Ravi Head", frozenset({"analyst", "head_of_data"}), False, "acc-ravi")
ADMIN = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "acc-arjun")
READER = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-priya")
NEW_TABLE = "Table office_notes {\n  id uuid [pk]\n  organization_id uuid [not null]\n  body text\n}\nRef: office_notes.organization_id > organizations.id\n"


@pytest.fixture()
def plane(tmp_path):
    return PlaneStore(tmp_path / "data").create("acme")


def names_in(plane, sql):
    con = duckdb.connect(str(plane.path("warehouse", "evidence.duckdb")), read_only=True)
    try:
        return {r[0] for r in con.execute(sql).fetchall()}
    finally:
        con.close()


def test_core_seeds_as_version_one_and_is_described(plane):
    assert E.version_of(plane) == 1
    cat = E.current(plane)
    assert cat["version"] == 1 and len(cat["tables"]) == 60 and all(t["layer"] == "core" for t in cat["tables"])
    assert plane.path("model", "versions", "1", "model.dbml").read_text(encoding="utf-8").startswith("Project investment_evidence_to_action")
    assert E.has_field(plane, "organizations", "id") and not E.has_field(plane, "organizations", "nope") and not E.has_field(plane, "nope", "id")
    d = E.describe(plane, "users")
    assert d["columns"][0]["pk"] and any(r["to"]["table"] == "organizations" for r in d["refs"]) and E.describe(plane, "nope") is None
    assert {t["name"] for t in E.tables(plane)} == {t["name"] for t in cat["tables"]}
    ddl = E.ddl(cat)
    assert len(ddl) == 60 and "FLOAT[384]" in "".join(ddl) and "TIMESTAMPTZ" in "".join(ddl) and "tsvector" not in "".join(ddl)


def test_a_broken_script_is_refused_with_its_line(plane):
    with pytest.raises(Refused) as e:
        E.propose(plane, ENG, dbml="Table a {\n  id int\n  b\n}\nTable c { x int ")
    assert "line 3" in e.value.message


def test_a_core_change_is_refused(plane):
    with pytest.raises(Refused) as e:
        E.propose(plane, ENG, dbml="Table organizations {\n  id int [pk]\n}\n")
    assert "product release" in e.value.message
    with pytest.raises(Refused):
        E.propose(plane, ENG, add_table={"name": "users", "columns": [{"name": "x", "type": "text"}]})
    with pytest.raises(Refused):
        E.propose(plane, ENG, add_column={"table": "users", "name": "x", "type": "wibble"})


def test_an_extension_makes_a_proposal_with_a_plain_diff(plane):
    p = E.propose(plane, ENG, dbml=NEW_TABLE)
    assert p["version"] == 2 and p["state"] == "proposed" and p["sandbox"]["ok"]
    assert p["diff"]["tables_added"] == [{"table": "office_notes", "columns": 3}]
    assert p["diff"]["words"] == ["Adds the table office_notes with 3 columns."]
    assert E.version_of(plane) == 1 and not E.has_field(plane, "office_notes", "body")      # only approved versions are read
    q = E.propose(plane, ENG, add_column={"table": "users", "name": "nickname", "type": "varchar(50)", "note": "What people call them"})
    assert q["diff"]["words"] == ["Adds the column nickname (varchar(50)) to users."]
    with pytest.raises(Refused):
        E.propose(plane, ENG, add_column={"table": "users", "name": "must_have", "type": "text", "null": False})   # a required column cannot be added
    with pytest.raises(Refused):
        E.propose(plane, READER, dbml=NEW_TABLE)


def test_proposer_cannot_approve_and_approval_builds_the_warehouse(plane):
    E.propose(plane, ENG, dbml=NEW_TABLE)
    with pytest.raises(Refused) as e:
        E.approve(plane, ENG, 2)                      # a data engineer who is also the head of data still cannot approve their own
    assert e.value.status == 403
    with pytest.raises(Refused):
        E.approve(plane, READER, 2)
    with pytest.raises(Refused) as e:                  # ROLE1: the data engineer reads and proposes; only the head of data decides
        E.approve(plane, Viewer("Other Engineer", frozenset({"analyst"}), False, "acc-other"), 2)
    assert e.value.status == 403
    done = E.approve(plane, HEAD, 2)
    assert done["state"] == "approved" and done["approved_by"] == "Ravi Head" and E.version_of(plane) == 2
    assert E.has_field(plane, "office_notes", "body") and E.describe(plane, "office_notes")["layer"] == "company"
    assert E.describe(plane, "users")["layer"] == "core"
    names = names_in(plane, "select table_name from information_schema.tables")
    assert "office_notes" in names and "organizations" in names and len(names) == 61  # 60 core tables (A47) plus office_notes
    assert [v["state"] for v in E.versions(plane)] == ["approved", "superseded"]
    E.propose(plane, ADMIN, add_column={"table": "office_notes", "name": "tag", "type": "varchar(20)"})   # a later column migrates add-only
    assert E.approve(plane, HEAD, 3)["state"] == "approved"
    assert "tag" in names_in(plane, "select column_name from information_schema.columns where table_name = 'office_notes'")
    log = json.loads(plane.path("model", "log.json").read_text(encoding="utf-8"))
    assert [r["what"] for r in log if r["by"] != "system"] == ["proposed a change", "approved a change", "proposed a change", "approved a change"]


def test_reject_keeps_the_reason_and_a_stale_proposal_is_superseded(plane):
    E.propose(plane, ENG, dbml=NEW_TABLE)
    with pytest.raises(Refused):
        E.reject(plane, HEAD, 2, " ")
    assert E.reject(plane, HEAD, 2, "Duplicates the notes table we plan")["reason"].startswith("Duplicates")
    E.propose(plane, ENG, add_column={"table": "users", "name": "a", "type": "text"})
    E.propose(plane, ENG, add_column={"table": "users", "name": "b", "type": "text"})
    E.approve(plane, HEAD, 3)
    assert E.proposal(plane, 4)["state"] == "superseded"
    with pytest.raises(Refused):
        E.approve(plane, ADMIN, 4)


def test_removing_a_column_a_sheet_mapping_uses_is_flagged_as_breaking(plane):
    E.propose(plane, ENG, dbml=NEW_TABLE)
    E.approve(plane, HEAD, 2)
    mp = plane.path("model", "mappings")
    mp.mkdir(parents=True, exist_ok=True)
    (mp / "m1.json").write_text(json.dumps({"id": "m1", "state": "approved", "file_pattern": "notes*.xlsx",
                                            "columns": [{"source_column": "Text", "target_table": "office_notes", "target_field": "body"}]}), encoding="utf-8")
    p = E.propose(plane, ENG, dbml="Table office_notes {\n  id uuid [pk]\n  organization_id uuid [not null]\n}\n")
    assert p["diff"]["columns_removed"] == [{"table": "office_notes", "column": "body"}]
    assert len(p["breaking"]) == 1 and "notes*.xlsx" in p["breaking"][0]


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_routes_check_the_seats(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c

    leela, arjun = client("leela.raman.neera@example.test"), client("arjun.mehta.neera@example.test")
    cat = leela.get("/api/v1/model/catalogue").json()
    nxt = cat["version"] + 1  # a core release that adds columns (UC6 G called_to_date) reloads the copied company to a later version
    assert cat["version"] in (1, 2) and sum(len(g["tables"]) for g in cat["groups"]) == 60
    assert leela.get("/api/v1/model/tables/users").json()["name"] == "users" and leela.get("/api/v1/model/tables/zzz").status_code == 404
    assert "Table organizations" in leela.get("/api/v1/model/script").text
    r = leela.post("/api/v1/model/proposals", json={"dbml": NEW_TABLE})
    assert r.status_code == 200 and r.json()["version"] == nxt
    assert leela.post(f"/api/v1/model/proposals/{nxt}/approve").status_code == 403           # the proposer
    assert arjun.post(f"/api/v1/model/proposals/{nxt}/approve").json()["state"] == "approved"
    assert arjun.get("/api/v1/model/proposals").json()[0]["state"] == "approved"
    assert leela.post("/api/v1/model/proposals", json={"dbml": "Table x {"}).status_code == 400
