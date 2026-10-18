"""L3 The library sorts itself into folders: classification by rules, the Jev path with a stub model, the one-time idempotent migration
with every reader still finding its file, folder counts that respect visibility, the owner's recorded move, nothing auto-ticked."""
import base64
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.jsonfile import lock_for, write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import catalogue_scan
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import k1_classify as C
from sh_platform.v1 import l3_library as F
from sh_platform.v1 import x5_extract as X
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
CSV = b"as_of,portfolio,market_value\n2026-08-31,Core,100\n"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("l3") / "data"
    shutil.copytree(SEED, data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    plane = PlaneStore(data).plane_for("neera")
    acc = app.state.account_store.get_by_email(ARJUN)  # the seed starts with no intents: Arjun raises one for the readers below
    N.create(plane, Viewer(acc["display_name"], frozenset(acc.get("roles") or ["company_admin"]), False, acc["account_id"]), "Monthly committee pack")
    yield app, plane
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def up(c, name, data, **kw):
    return c.post("/api/v1/library", json={"name": name, "data": base64.b64encode(data).decode(), **kw})


def test_classification_by_rules():
    by = lambda n, **k: F.classify(n, **k)["folder"]
    assert by("04-capital-call-notice-orchard-growth-partners-i.md") == "Capital calls and distributions"
    assert by("16-committee-minutes-2026-02-19.md") == "Minutes and decisions"
    assert by("07-email-benchmark-question.txt") == "Emails and notes"  # the more specific folder wins a tie
    assert by("05-custodian-statement-northgate-2026-08.txt") == "Statements and invoices"
    assert by("13-access-policy.md") == "Policies and rules"
    assert by("scan.png") == "Pictures and scans" and by("positions.csv") == "Data samples"
    assert by("qwerty.txt") == "Other" and not F.classify("qwerty.txt")["sure"]
    assert by("x.txt", head_text="Month-end process: steps for the team") == "Process maps"  # the first heading counts
    assert F.classify("pack-2026-08.xlsx", columns=["a"])["subfolder"] == "2026"
    assert F.folder_of_topic("Finance") == "Statements and invoices" and F.folder_of_topic("nonsense") == "Other"
    assert len(F.FOLDERS) == 12 and {"Capital calls and distributions", "Minutes and decisions"} <= set(C.TOPICS)


def old_row(plane, name, body):
    """A row as it was before L3: no folder, the file in library/files."""
    row = L._item(name, "document", "", "Old Uploader", "acct-x", "", len(body), "company", "")
    row["path"] = f"library/files/{row['id']}__{name}"
    p = plane.path(*row["path"].split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        rows.append(row)
        write_json_atomic(L._index_path(plane), rows)
    return row


def test_migration_is_idempotent_and_every_reader_finds_the_file(world):
    app, plane = world
    row = old_row(plane, "02-board-minutes-2026-05.md", b"# Minutes\nDecisions taken by the committee\n")
    old = row["path"]
    assert F.ensure(plane, None) is False
    got = next(i for i in L._index(plane) if i["id"] == row["id"])
    assert got["folder"] == "Minutes and decisions" and got["folder_by"] == "rules" and got["subfolder"] == "2026"
    assert got["path"] == f"library/Minutes and decisions/{row['id']}__02-board-minutes-2026-05.md" and got["was"] == old
    assert plane.path(*got["path"].split("/")).is_file() and not (plane.root / old).exists()
    assert all(r.get("folder") and not r.get("sorting") for r in L._index(plane))  # seeded items sorted too
    seeded = next(i for i in L._index(plane) if i["path"].startswith("documents/"))
    assert plane.path(*seeded["path"].split("/")).is_file()  # the company's own documents/ stay where the scans read them

    before = (plane.path("library", "index.json").read_bytes(), plane.path("library", "aliases.json").read_bytes())
    F.ensure(plane, None)  # a second run changes nothing
    assert before == (plane.path("library", "index.json").read_bytes(), plane.path("library", "aliases.json").read_bytes())

    # readers that hold the old stored path still find the file; readers that go through the index use the new one
    assert "Decisions taken" in N.file_preview(plane, "x", {"name": got["name"], "path": old})
    assert any("Decisions taken" in ln for ln in X._lines(plane, old))
    assert "Decisions taken" in N.file_preview(plane, "x", L.as_files(plane, [got])[0])
    iid = next(p.name for p in plane.path("intents").iterdir() if p.name.startswith("ini-"))
    write_json_atomic(plane.path("intents", iid, "context.json"), {"library_ids": [got["id"]], "by": "t", "at": "t"})
    files, _ = catalogue_scan._folder_documents(plane, iid, None)
    assert files == [got["path"]]  # the scan reads the path the index holds


def test_the_owner_moves_an_item_and_it_is_recorded(world):
    app, plane = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "notes-on-fees.txt", b"Fee notes", share=True).json()["item"]
    assert item["folder"] == "Emails and notes" and item["folder_by"] == "rules"
    assert leela.put(f"/api/v1/library/{item['id']}/folder", json={"folder": "Other"}).status_code == 403
    assert arjun.put(f"/api/v1/library/{item['id']}/folder", json={"folder": "Nowhere"}).status_code == 400
    moved = arjun.put(f"/api/v1/library/{item['id']}/folder", json={"folder": "Policies and rules"}).json()
    assert moved["folder"] == "Policies and rules" and moved["folder_by"] == "owner"
    row = next(i for i in L._index(plane) if i["id"] == item["id"])
    assert row["folder_log"][-1]["from"] == "Emails and notes" and row["folder_log"][-1]["by"] == "Arjun Mehta"
    assert plane.path("library", "Policies and rules", f"{item['id']}__notes-on-fees.txt").read_bytes() == b"Fee notes"
    assert not (plane.root / "library" / "Emails and notes" / f"{item['id']}__notes-on-fees.txt").exists()  # (plane.path would follow the alias)
    assert "Fee notes" in N.file_preview(plane, "x", {"name": "notes-on-fees.txt", "path": item["path"]})  # the old path still opens


def test_upload_goes_where_the_person_chose_and_the_duplicate_check_stays(world):
    app, plane = world
    arjun = client(app, ARJUN)
    got = up(arjun, "quarter.csv", CSV, folder="Benchmarks and targets", folder_by="Jev").json()["item"]
    assert got["folder"] == "Benchmarks and targets" and got["folder_by"] == "Jev"
    assert got["path"] == f"library/Benchmarks and targets/{got['id']}__quarter.csv"
    assert up(arjun, "other-name.csv", CSV, folder="Other").json()["duplicate"]["id"] == got["id"]  # same bytes: C4's check still answers
    bad = up(arjun, "weird.csv", CSV + b"2026-09-30,Core,5\n", folder="../etc").json()["item"]
    assert bad["folder"] == "Data samples" and bad["path"].startswith("library/Data samples/")  # an unknown folder is ignored
    prop = arjun.post("/api/v1/library/proposal", json={"name": "invoice-custody-2026.md", "data": base64.b64encode(b"x").decode()}).json()
    assert prop["folder"] == "Statements and invoices" and prop["folder_by"] == "rules" and "Policies and rules" in prop["folders"]


def test_folder_counts_respect_visibility(world):
    app, plane = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "private-statement-2026.md", b"Statement of private holdings").json()["item"]
    mine = {f["folder"]: f for f in arjun.get("/api/v1/library/folders").json()["folders"]}
    theirs = {f["folder"]: f for f in leela.get("/api/v1/library/folders").json()["folders"]}
    assert item["id"] in {i["id"] for i in mine["Statements and invoices"]["items"]}
    assert item["id"] not in json.dumps(theirs)  # a private item is in nobody else's items, and not in their counts
    assert mine["Statements and invoices"]["count"] == theirs["Statements and invoices"]["count"] + 1
    assert all(f["count"] == len(f["items"]) for f in theirs.values())
    r = arjun.put(f"/api/v1/library/{item['id']}", json={"visibility": "company"})
    assert r.status_code == 200, r.text
    again = {f["folder"]: f for f in leela.get("/api/v1/library/folders").json()["folders"]}
    assert again["Statements and invoices"]["count"] == mine["Statements and invoices"]["count"]
    hit = leela.get("/api/v1/library/folders?q=private-statement").json()["folders"]  # search across all folders
    assert [f["count"] for f in hit] == [1]


def wait_sorted(plane, item_id):
    for _ in range(100):
        got = next(i for i in L._index(plane) if i["id"] == item_id)
        if not got.get("sorting"):
            break
        time.sleep(0.05)
    return got


def test_unclear_items_go_to_jev_in_a_batch_and_the_list_says_sorting_until_done(world, monkeypatch):
    app, plane = world
    row = old_row(plane, "qwerty-zzz.txt", b"Some plain words")
    asked = []
    monkeypatch.setattr(C, "ask_topic", lambda model, pl, name, cols, head: (asked.append(name), "Policies and rules")[1])
    F.ensure(plane, model=object())
    got = wait_sorted(plane, row["id"])
    assert asked == ["qwerty-zzz.txt"]
    assert got["folder"] == "Policies and rules" and got["folder_by"] == "Jev" and not got.get("sorting")
    assert plane.path("library", "Policies and rules", f"{row['id']}__qwerty-zzz.txt").is_file()
    # an answer off the list (None) leaves the rules' folder and still clears "sorting"
    row2 = old_row(plane, "asdf-yyy.txt", b"Other words")
    monkeypatch.setattr(C, "ask_topic", lambda *a: None)
    F.ensure(plane, model=object())
    got = wait_sorted(plane, row2["id"])
    assert got["folder"] == "Other" and got["folder_by"] == "rules" and not got.get("sorting")
    # while the batch has not answered, the row shows as sorting
    row3 = old_row(plane, "hjkl-xxx.txt", b"More words")
    monkeypatch.setattr(F, "settle", lambda *a: None)
    F.ensure(plane, model=object())
    time.sleep(0.2)
    assert next(i for i in L._index(plane) if i["id"] == row3["id"])["sorting"] is True
    assert F.folders(plane, None)["sorting"] is True  # the list says "sorting…" for the viewer who can see the row


def test_nothing_is_ticked_by_default(world):
    app, plane = world
    arjun = client(app, ARJUN)
    iid = next(p.name for p in plane.path("intents").iterdir() if p.name.startswith("ini-"))
    plane.path("intents", iid, "context.json").unlink(missing_ok=True)
    write_json_atomic(plane.path("intents", iid, "sow.json"), {"sources": [{"sample_path": "documents/13-access-policy.md"}]})  # the old fallback ticked this
    assert L._ids(plane, iid) == []
    assert arjun.get(f"/api/v1/intents/{iid}/context").json()["library_ids"] == []


def raw_aliases(plane):
    p = plane.root / "library" / "aliases.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def test_move_back_keeps_the_path_and_the_disk_name(world):
    app, plane = world
    arjun = client(app, ARJUN)
    item = up(arjun, "move-back-note.txt", b"Back and forth", share=True).json()["item"]
    first = item["path"]
    for folder in ("Policies and rules", item["folder"]):
        assert arjun.put(f"/api/v1/library/{item['id']}/folder", json={"folder": folder}).status_code == 200
    row = next(i for i in L._index(plane) if i["id"] == item["id"])
    assert row["path"] == first and (plane.root / first).read_bytes() == b"Back and forth"  # same name: no id suffix, no rename
    assert first not in raw_aliases(plane) and all(k != v for k, v in raw_aliases(plane).items())
    assert plane.path(*first.split("/")).is_file()  # and path() cannot loop


def test_an_interrupted_migration_is_not_renamed_on_the_rerun(world):
    app, plane = world
    row = old_row(plane, "09-interrupted-minutes-2026-01.md", b"# Notes\nHalf-moved\n")
    old = row["path"]
    new = F.rel_path(plane, row, "Minutes and decisions")
    (plane.root / new).parent.mkdir(parents=True, exist_ok=True)
    (plane.root / old).replace(plane.root / new)  # the file moved and the alias written, the index not yet
    F._record_move(plane, old, new)
    F.ensure(plane, None)
    got = next(i for i in L._index(plane) if i["id"] == row["id"])
    assert got["path"] == new and (plane.root / new).read_bytes().endswith(b"Half-moved\n")
    assert [p.name for p in (plane.root / "library" / got["folder"]).glob(f"*{row['id']}*")] == [new.rsplit("/", 1)[1]]


def test_a_stale_path_never_opens_a_later_upload(world):
    app, plane = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    ann = up(arjun, "stale-reuse.md", b"# Shared\nAnn's shared text\n", share=True).json()["item"]
    stale = ann["path"]
    assert arjun.delete(f"/api/v1/library/{ann['id']}").status_code in (200, 204)
    bob = up(leela, "stale-reuse.md", b"# Private\nBob's private text\n").json()["item"]  # same name, later, private
    assert bob["path"] != stale
    assert L.path_ok(plane, stale) is False and L.path_ok(plane, bob["path"], None, check=True) is False  # no row / not readable by "nobody"
    assert N.file_preview(plane, "x", {"name": "stale-reuse.md", "path": stale}) == ""
    sow = {"sources": [{"id": "s1", "kind": "document", "sample_path": stale}]}
    assert catalogue_scan._files(plane, "x", sow) == {}  # the scan drops a library path no row owns
