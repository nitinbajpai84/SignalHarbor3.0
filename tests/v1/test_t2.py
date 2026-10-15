"""T2 ticket centre: sequential numbers never reused, delegation and reopen in the log, the audit export equals history, visibility and locked links,
the Watcher's ticket reaches the builder's Pulse once per source per day, migration is idempotent, and routes refuse a stranger."""
import csv
import io
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import p5_handover as P5
from sh_platform.v1 import t2_tickets as T

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
PID = "prj-0000abcd"
LEELA = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-l")
PRIYA = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-p")
DEV = Viewer("Dev Sharma", frozenset({"participant"}), False, "acc-d")
ARJUN = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "acc-a")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    neera = data / "neera"
    (neera / "tickets" / "_migrated.json").unlink(missing_ok=True)  # the live company may already have migrated; the test starts before that
    (neera / "intents" / "i-test").mkdir(parents=True, exist_ok=True)
    (neera / "intents" / "i-test" / "sow.json").write_text(json.dumps({"id": "s", "intent_id": "i-test", "sources": [{"id": "administrator_A2"}]}), encoding="utf-8")
    (neera / "projects").mkdir(exist_ok=True)
    (neera / "projects" / f"{PID}.json").write_text(json.dumps({"id": PID, "intent_id": "i-test", "title": "Test", "stage": "live", "sensitivity": "restricted",
                                                              "artefacts": [], "people": {"raiser": "Priya Nair", "builder": "Leela Raman"}}), encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    return app, PlaneStore(data).plane_for("neera"), neera


def test_numbers_delegation_reopen_and_the_audit_export(world):
    _, plane, _ = world
    a = T.raise_ticket(plane, by="flow", to="builder", title="Which column is the fee?", project=PID, stage="build")
    b = T.raise_ticket(plane, by="Priya Nair", to="Leela Raman", title="Late file", project=PID, stage="ops")
    assert (a["id"], b["id"], a["assigned_to"]) == ("TCK-0001", "TCK-0002", "Leela Raman")      # a part on the project becomes the person
    T.reassign(plane, LEELA, a["id"], "Dev Sharma", "he owns the custodian file")
    T.set_state(plane, DEV, a["id"], "resolved", "column F")
    t = T.set_state(plane, PRIYA, a["id"], "open", "still wrong")
    assert [h["action"] for h in t["history"]] == ["raised", "delegated", "resolved", "reopened"]
    assert (t["history"][1]["from"], t["history"][1]["to"]) == ("Leela Raman", "Dev Sharma")
    assert T.raise_ticket(plane, by="x", to="Leela Raman", title="third")["id"] == "TCK-0003"       # never reused
    rows = list(csv.DictReader(io.StringIO(T.log_csv(t))))
    assert [(r["at"], r["action"], r["note"]) for r in rows] == [(h["at"], h["action"], h["note"]) for h in t["history"]]
    assert rows[0]["in words"].startswith("Span raised it to Leela Raman on ") and "delegated it to Dev Sharma" in rows[1]["in words"]
    with pytest.raises(T.Refused) as e:                                                              # a stranger cannot pass it on
        T.reassign(plane, DEV, b["id"], "Dev Sharma")
    assert e.value.status == 403


def test_visibility_and_a_locked_link(world):
    app, plane, _ = world
    t = T.raise_ticket(plane, by="Priya Nair", to="Dev Sharma", title="Check the fee file", project=PID, links=[{"kind": "artefact", "ref": f"{PID}:build_pack"}])
    other = T.raise_ticket(plane, by="Priya Nair", to="Leela Raman", title="Private", project=PID)
    assert T.can_see(plane, ARJUN, other) and T.can_see(plane, LEELA, other) and not T.can_see(plane, DEV, other)
    d = T.detail(plane, DEV, t["id"])
    assert d["links"][0]["locked"] is True and d["links"][0]["href"] is None                        # restricted project, Dev not on its team
    assert [r["id"] for r in T.listing(plane, DEV)["tickets"]] == [t["id"]]
    assert T.detail(plane, LEELA, t["id"])["links"][0]["locked"] is False
    # the same through the routes
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    email = "dev.sharma.neera@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    assert c.get(f"/api/v1/tickets/{other['id']}").status_code == 403
    assert [r["id"] for r in c.get("/api/v1/tickets").json()["tickets"]] == [t["id"]]


def test_watcher_ticket_reaches_the_builders_pulse_once_per_source_per_day(world):
    _, plane, _ = world
    day = date(2026, 10, 8)
    for _ in range(2):
        P5.raise_ticket(plane, {"pid": PID, "source_id": "administrator_A2", "text": "Watcher: administrator_A2: the file arrived late."}, "watcher", day=day)
    mine = [t for t in T.all_tickets(plane) if t["raised_by"] == "watcher"]
    assert len(mine) == 1 and mine[0]["assigned_to"] == "Leela Raman" and mine[0]["stage"] == "ops"
    assert T.raise_ticket(plane, by="watcher", to="Leela Raman", title="again", project=PID, links=mine[0]["links"][:1], once=True) is None
    needs, look, lines = [], [], [{"pid": PID, "title": "Test"}]
    T.extend(plane, LEELA, needs, look, lines)
    assert lines[0]["open_tickets"] == 1
    assert not needs  # her ticket's discussion is an open comment addressed to her: that card already shows it (the ticket card would repeat it)
    # delegated to Dev, the comment is still Leela's: Dev must get the ticket card, or the work vanishes from Pulse
    T.reassign(plane, LEELA, mine[0]["id"], "Dev Sharma")
    needs, look, lines = [], [], [{"pid": PID, "title": "Test"}]
    T.extend(plane, DEV, needs, look, lines)
    assert [c["pid"] for c in needs if c["kind"] == "ticket"] == [PID]


def test_migration_is_idempotent(world):
    _, plane, neera = world
    c = P1.comment(plane, PID, "build_pack", "src_1", "watcher", "Leela Raman", "Watcher: src_1 failed.", kind="ticket")
    P1.comment(plane, PID, "build_pack", "deviation:dv_1", "flow", "Priya Nair", "Flow asks to change the source.", kind="approval")
    (neera / "templates").mkdir(exist_ok=True)
    (neera / "templates" / "requests.json").write_text(json.dumps([{"id": "REQ-0001", "kind": "template", "text": "A fee review template", "by": "Leela Raman",
                                                                    "at": "2026-10-08T10:00:00+00:00", "state": "open"}]), encoding="utf-8")
    first = T.migrate(plane)
    assert first == 3 and {t["stage"] for t in T.all_tickets(plane)} == {"ops", "design", "intent"}
    (neera / "tickets" / "_migrated.json").unlink()                                                  # run again: nothing is made twice
    assert T.migrate(plane) == 0 and len(T.all_tickets(plane)) == 3
    assert T.settle_comment(plane, c["id"], "Leela Raman", "resolved", "done") == 1
