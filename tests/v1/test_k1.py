"""K1 sensitivity, topic and access: personal data found by rules (kinds and places, never a value), the model path with a stub (a
digit-free prompt, a fixed list, the program validates), the preview of a locked item never holds a value or a note, request / approve /
revoke, an agent never reads a restricted item without mine or a grant, mine needs no request, a private item stays invisible,
a company admin answers when the owner has left."""
import base64
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from tests.v1.team import on_team
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import i6_chat
from sh_platform.v1 import k1_access as K
from sh_platform.v1 import k1_classify as C
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN, LEELA, PRIYA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test", "priya.nair.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
EMAIL, PHONE, NAME = "zed.quill@example.test", "+65 6123 4567", "Zed Quill"
CLIENTS = f"client_name,client_id,email,phone,balance\n{NAME},C-1001,{EMAIL},{PHONE},500\nAva Marsh,C-1002,ava.m@example.test,+65 6123 4568,700\n".encode()
PLAIN = b"as_of,portfolio,market_value\n2026-08-31,Core,100\n"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("k1") / "data"
    shutil.copytree(SEED, data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    accounts = json.loads((data / "_control" / "accounts.json").read_text(encoding="utf-8"))
    ids = {r["display_name"]: r["account_id"] for r in accounts if r.get("company_id") == "neera"}
    yield app, PlaneStore(data).plane_for("neera"), ids
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def up(c, name, data, **kw):
    return c.post("/api/v1/library", json={"name": name, "data": base64.b64encode(data).decode(), **kw})


def row(c, item_id):
    return next((i for i in c.get("/api/v1/library").json() if i["id"] == item_id), None)


def test_personal_data_found_by_rules_stores_no_value_and_forces_restricted(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    prop = arjun.post("/api/v1/library/proposal", json={"name": "zq-people.csv", "data": base64.b64encode(CLIENTS).decode()}).json()
    assert prop["sensitivity"] == "restricted" and prop["pii"]["found"]
    assert {"email addresses", "phone numbers", "names with ids"} <= set(prop["pii"]["kinds"])
    assert "column 3 (email)" in prop["pii"]["where"]
    assert "Keep as Restricted?" in prop["message"] and "email addresses in column 3" in prop["message"]
    for v in (EMAIL, PHONE, NAME, "ava.m@"):
        assert v not in json.dumps(prop)

    # the owner asked for Open; personal data forces Restricted until they say it is not personal
    got = up(arjun, "zq-people.csv", CLIENTS, share=True, sensitivity="open", note="client list for the board").json()
    assert "item" in got, got
    item = got["item"]
    assert item["sensitivity"] == "restricted" and item["mine"] and item["access"] == "mine"
    index = plane.path("library", "index.json").read_text(encoding="utf-8")
    for v in (EMAIL, PHONE, NAME, "ava.m@"):
        assert v not in index  # kinds and places only

    seen = row(leela, item["id"])  # shared with the company: Leela sees a lock and a preview, never the file
    assert seen["locked"] and seen["access"] == "request"
    assert set(seen) <= set(K.PREVIEW) | {"locked"}
    assert "note" not in seen and "path" not in seen and "sha256" not in seen
    assert seen["preview"]["contains_personal_data"] and "email addresses" in seen["preview"]["kinds"]
    assert "columns" not in seen["preview"]  # personal data: the kinds only
    blob = json.dumps(seen)
    for v in (EMAIL, PHONE, NAME, "client list for the board", "C-1001"):
        assert v not in blob
    assert item["id"] not in {i["id"] for i in leela.get("/api/v1/library?q=board").json()}  # the note of a locked item is not searchable

    # restricted by the owner's word, no personal data: the preview names the columns, no value
    plain = up(arjun, "positions.csv", PLAIN, share=True, sensitivity="restricted", note="private note").json()["item"]
    locked = row(leela, plain["id"])
    assert locked["preview"]["columns"] == ["as_of", "portfolio", "market_value"] and not locked["preview"]["contains_personal_data"]
    assert "2026-08-31" not in json.dumps(locked) and "Core" not in json.dumps(locked) and "private note" not in json.dumps(locked)


def test_topic_rules_then_the_model_with_a_digit_free_prompt(world):
    app, plane, _ = world
    assert C.topics_for("custodian-statement-2026-08.csv")[0][0] == "Statements and invoices"
    assert C.topics_for("ledger.xlsx", columns=["journal", "account"])[0][0] == "General ledger"
    assert C.topics_for("zzz.csv") == (["Data samples"], False)
    seen = []

    class Stub:
        def __init__(self, text):
            self.text = text

        def complete(self, module_id, messages, tools=None, suppressed=None):
            seen.append(messages)
            return ModelReply(text=self.text)
    ugly = b"Zorb 7,Quux 9\n1,2\n"
    got = C.propose("zzz 2026 q3.csv", ugly, model=Stub('{"topic": "reporting"}'), plane=plane)
    assert got["topics"] == ["Reporting"] and got["by"] == "model"
    sent = seen[0][1]["content"]
    assert not any(ch.isdigit() for ch in sent) and "Reporting" in sent  # digit-free; the fixed list goes with it
    assert C.propose("zzz.csv", ugly, model=Stub('{"topic": "Bananas"}'), plane=plane)["topics"] == ["Data samples"]  # off the list: ignored
    assert C.propose("zzz.csv", ugly, model=None)["by"] == "rules"
    n = len(seen)
    assert C.propose("policy.md", b"# Access policy\n", model=Stub('{"topic": "Finance"}'), plane=plane)["topics"] == ["Policies and rules"]
    assert len(seen) == n  # rules were sure: the model was not asked


def test_request_approve_revoke_and_what_an_agent_reads(world):
    app, plane, ids = world
    arjun, leela, priya = client(app, ARJUN), client(app, LEELA), client(app, PRIYA)
    l_v = Viewer("Leela Raman", frozenset({"analyst"}), False, ids["Leela Raman"])
    a_v = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, ids["Arjun Mehta"])
    item = up(arjun, "custodian-statements.csv", PLAIN + b"2026-07-31,Core,90\n", share=True, sensitivity="restricted",
              note="custodian statements for August").json()["item"]
    iid = i6_chat.create(plane, a_v, "Monthly performance for the custodian statements")
    on_team(app, iid, "Leela Raman")  # G1: Internal is the team's alone

    # a locked item cannot be ticked, and a hidden tick is never read
    assert leela.put(f"/api/v1/intents/{iid}/context", json={"library_ids": [item["id"]]}).json()["library_ids"] == []
    write_json_atomic(plane.path("intents", iid, "context.json"), {"library_ids": [item["id"]], "by": "x", "at": "x"})
    assert "market_value" not in " ".join(L.lines(plane, iid, l_v)) and L.selected(plane, iid, l_v) == []
    assert any("market_value" in x for x in L.lines(plane, iid, a_v))  # mine: always full access

    assert arjun.post(f"/api/v1/library/{item['id']}/access", json={}).status_code == 409  # mine needs no request
    req = leela.post(f"/api/v1/library/{item['id']}/access", json={"reason": "August reporting", "iid": iid}).json()
    assert req["state"] == "requested" and req["to"] == "Arjun Mehta"
    assert leela.post(f"/api/v1/library/{item['id']}/access", json={}).json()["id"] == req["id"]  # asking twice is one request
    assert row(leela, item["id"])["access"] == "requested"

    cards = arjun.get("/api/v1/library/pulse").json()["needs_you"]
    assert len(cards) == 1 and "Leela Raman asks to use custodian-statements.csv" in cards[0]["text"] and cards[0]["action"] == "Approve"
    assert leela.get("/api/v1/library/pulse").json()["needs_you"] == []
    assert leela.post(f"/api/v1/library/access/{req['id']}", json={"approve": True}).status_code == 404  # not Leela's to answer
    assert priya.post(f"/api/v1/library/access/{req['id']}", json={"approve": True}).status_code == 404

    done = arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": True, "note": "for the board"}).json()
    assert done["state"] == "granted" and done["decided_by"] == "Arjun Mehta" and done["expires"]
    assert arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": True}).status_code == 409
    mine = row(leela, item["id"])
    assert mine["access"] == "granted" and not mine.get("locked") and mine["note"] == "custodian statements for August"
    assert any("approved your request" in c["text"] for c in leela.get("/api/v1/library/pulse").json()["worth_a_look"])
    grant = next(g for g in row(arjun, item["id"])["grants"] if g["name"] == "Leela Raman")
    assert grant["why"] == "August reporting"
    assert leela.put(f"/api/v1/intents/{iid}/context", json={"library_ids": [item["id"]]}).json()["library_ids"] == [item["id"]]
    assert any("market_value" in x for x in L.lines(plane, iid, l_v))  # granted: the agent reads it

    assert leela.delete(f"/api/v1/library/{item['id']}/grants/{ids['Leela Raman']}").status_code == 403  # only the owner revokes
    back = arjun.delete(f"/api/v1/library/{item['id']}/grants/{ids['Leela Raman']}").json()
    assert back["grants"] == []
    assert row(leela, item["id"])["locked"] and L.selected(plane, iid, l_v) == []  # revoked: locked again, ticks no longer read
    assert "market_value" not in " ".join(L.lines(plane, iid, l_v))

    # an expired grant is no grant; a refusal is shown to the requester
    stored = next(i for i in L._index(plane) if i["id"] == item["id"])
    K._add_grant(stored, ids["Leela Raman"], "Leela Raman", "t", None, "x", None)
    stored["grants"][0]["expires"] = "2020-01-01T00:00:00+00:00"
    assert not K.can_read(stored, l_v)
    r2 = leela.post(f"/api/v1/library/{item['id']}/access", json={}).json()
    no = arjun.post(f"/api/v1/library/access/{r2['id']}", json={"approve": False, "note": "not this month"}).json()
    assert no["state"] == "denied" and row(leela, item["id"])["access"] == "denied"
    assert any("not this month" in c["text"] for c in leela.get("/api/v1/library/pulse").json()["worth_a_look"])


def test_private_stays_invisible_and_the_owner_names_people(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "private-restricted.csv", PLAIN + bytes([50, 10]), sensitivity="restricted", note="mine only").json()["item"]
    assert item["visibility"] == "private"
    assert row(leela, item["id"]) is None and leela.post(f"/api/v1/library/{item['id']}/access", json={}).status_code == 404
    assert item["id"] not in json.dumps(leela.get("/api/v1/library/folders").json())

    arjun.put(f"/api/v1/library/{item['id']}", json={"visibility": "company", "sensitivity": "internal"})
    assert row(leela, item["id"])["locked"]
    assert leela.post(f"/api/v1/library/{item['id']}/grants", json={"account_id": ids["Leela Raman"]}).status_code == 403
    named = arjun.post(f"/api/v1/library/{item['id']}/grants", json={"account_id": ids["Leela Raman"], "days": 7}).json()
    assert named["grants"][0]["expires"] and row(leela, item["id"])["access"] == "granted"
    assert {p["name"] for p in arjun.get("/api/v1/library/people").json()} >= {"Leela Raman", "Arjun Mehta"}


def test_owner_edits_sensitivity_and_topic_and_folders_search(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "staff-contacts.csv", CLIENTS.replace(b"client_", b"staff_"), share=True).json()["item"]
    assert item["sensitivity"] == "restricted"
    url = f"/api/v1/library/{item['id']}"
    assert leela.put(url, json={"topic": ["x"]}).status_code == 403
    assert arjun.put(url, json={"sensitivity": "open"}).status_code == 409  # personal data, not yet marked reviewed
    ok = arjun.put(url, json={"sensitivity": "open", "reviewed": True, "topic": ["Finance", "payroll", "a", "b"]}).json()
    assert ok["sensitivity"] == "open" and ok["topic"] == ["Finance", "payroll", "a"] and ok["pii"]["reviewed"]
    stored = next(i for i in L._index(plane) if i["id"] == item["id"])
    assert stored["pii"]["reviewed"]["by"] == "Arjun Mehta"  # recorded
    folders = {f["topic"]: f for f in leela.get("/api/v1/library/topics").json()["folders"]}
    assert item["id"] in {i["id"] for i in folders["payroll"]["items"]} and folders["payroll"]["count"] == 1
    assert any(f["topic"] == "Policies and rules" for f in folders.values())  # seeded items sit in a topic too
    assert leela.get("/api/v1/library?q=payroll").json()[0]["id"] == item["id"]
    assert leela.get("/api/v1/library?q=arjun").json()  # by owner


def test_company_admin_answers_when_the_owner_has_left(world, monkeypatch):
    app, plane, ids = world
    arjun, leela, priya = client(app, ARJUN), client(app, LEELA), client(app, PRIYA)
    item = up(leela, "leavers-pack.csv", PLAIN + b"2026-06-30,Core,80" + bytes([10]), share=True, sensitivity="restricted").json()["item"]
    real = K.directory(plane)
    gone = {i: {**p, "disabled": True} if i == ids["Leela Raman"] else p for i, p in real.items()}
    monkeypatch.setattr(K, "directory", lambda plane_: gone)
    req = priya.post(f"/api/v1/library/{item['id']}/access", json={"reason": "handover"}).json()
    assert req["owner_left"] and req["to"] in {p["name"] for p in gone.values() if "company_admin" in p["roles"]}
    assert [r["id"] for r in arjun.get("/api/v1/library/access").json()["incoming"]] == [req["id"]]
    assert arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": True, "days": 0}).json()["expires"] is None  # until revoked
    assert arjun.put(f"/api/v1/library/{item['id']}/owner", json={"account_id": ids["Arjun Mehta"]}).json()["mine"]
    assert leela.put(f"/api/v1/library/{item['id']}/owner", json={"account_id": ids["Leela Raman"]}).status_code in (403, 404)


# ---- review fixes (REVIEW-K1) -----------------------------------------------------------------------------------------------------------

def test_b1_headerless_table_keeps_no_value(world):
    app, plane, _ = world
    raw = f"{NAME},C-1001,{EMAIL},{PHONE},500\n".encode()
    for data in (raw, raw + f"Ava Marsh,C-1002,ava.m@example.test,{PHONE},700\n".encode()):
        prop = C.propose("export.csv", data, plane=plane)
        assert prop["pii"]["found"] and prop["sensitivity"] == "restricted" and prop["outline"]["columns"] is None
        for v in (NAME, EMAIL, PHONE, "C-1001", "ava.m@"):
            assert v not in json.dumps(prop)
    assert "column 3" in C.propose("export.csv", raw, plane=plane)["pii"]["where"]
    assert C.outline("plain.csv", PLAIN)["columns"] == ["as_of", "portfolio", "market_value"]  # real headers still shown


def test_s7_names_only_table_keeps_no_column_name(world):
    app, plane, _ = world
    # A names-only CSV: row 1 and row 2 both have the same shape and look like names
    names_csv = b"Zed Quill\nAva Marsh\n"
    prop = C.propose("people.csv", names_csv, plane=plane)
    assert prop["outline"]["columns"] is None  # names-only table is headerless
    assert "Zed Quill" not in json.dumps(prop)  # the name is not stored or shown


def test_b2_first_line_of_a_text_is_not_sent_or_shown(world):
    app, plane, _ = world
    sent = []

    class Stub:
        def complete(self, module_id, messages, tools=None, suppressed=None):
            sent.append(messages)
            return ModelReply(text='{"topic": "Finance"}')
    memo = b"Dear Mr Zed Quill, NRIC S1234567A\nplease keep this\n"
    prop = C.propose("zzz.txt", memo, model=Stub(), plane=plane)
    assert sent == [] and prop["sensitivity"] == "restricted" and prop["outline"]["heading"] is None  # restricted: rules only
    assert C.outline("m.txt", b"Re: Zed Quill termination\nbody")["heading"] is None  # a name-like first line is not kept
    assert C.outline("m.md", b"# Access policy\nbody")["heading"] == "Access policy"
    # B4: a markdown heading with personal data is not kept
    assert C.outline("m.md", b"# Letter to Zed Quill, NRIC S1234567A\nbody")["heading"] is None


def test_b3_a_declined_request_cannot_be_asked_again_for_a_week(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "decline-me.csv", PLAIN + b"2026-05-31,Core,70\n", share=True, sensitivity="restricted").json()["item"]
    req = leela.post(f"/api/v1/library/{item['id']}/access", json={}).json()
    arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": False})
    again = leela.post(f"/api/v1/library/{item['id']}/access", json={}).json()
    assert again["id"] == req["id"] and again["state"] == "denied"
    assert [r["item_id"] for r in K.requests(plane)].count(item["id"]) == 1
    assert row(leela, item["id"])["access"] == "denied"
    stored = K.requests(plane)
    next(r for r in stored if r["id"] == req["id"])["decided_at"] = "2020-01-01T00:00:00+00:00"  # a week has passed
    write_json_atomic(K._apath(plane), stored)
    assert row(leela, item["id"])["access"] == "request"
    assert leela.post(f"/api/v1/library/{item['id']}/access", json={}).json()["id"] != req["id"]


def test_s1_s2_s3_admin_cannot_approve_own_request_bad_iid_dropped(world, monkeypatch):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(leela, "orphan-pack.csv", PLAIN + b"2026-04-30,Core,60\n", share=True, sensitivity="restricted").json()["item"]
    real = K.directory(plane)
    gone = {i: {**p, "disabled": True} if i == ids["Leela Raman"] else p for i, p in real.items()}
    monkeypatch.setattr(K, "directory", lambda plane_: gone)
    before = set(p.name for p in plane.path("projects").iterdir()) if plane.path("projects").is_dir() else set()
    req = arjun.post(f"/api/v1/library/{item['id']}/access", json={"iid": "int_doesnotexist1"}).json()
    assert req["iid"] is None and req["p1"] is None  # S2: an intent that is not there is dropped
    after = set(p.name for p in plane.path("projects").iterdir()) if plane.path("projects").is_dir() else set()
    assert before == after  # and no project was made for it
    assert arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": True}).status_code == 409  # S1: not their own


def test_s3_admin_answers_the_p1_comment_as_themselves(world, monkeypatch):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    a_v = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, ids["Arjun Mehta"])
    iid = i6_chat.create(plane, a_v, "Quarterly attribution for the orphan pack")
    item = up(leela, "orphan-two.csv", PLAIN + b"2026-03-31,Core,50\n", share=True, sensitivity="restricted").json()["item"]
    real = K.directory(plane)
    gone = {i: {**p, "disabled": True} if i == ids["Leela Raman"] else p for i, p in real.items()}
    monkeypatch.setattr(K, "directory", lambda plane_: gone)
    seen = []
    from sh_platform.v1 import p1_project as P1
    real_answer = P1.answer
    monkeypatch.setattr(P1, "answer", lambda plane_, pid, cid, who, text: (seen.append(who), real_answer(plane_, pid, cid, who, text))[1])
    priya = client(app, PRIYA)
    req = priya.post(f"/api/v1/library/{item['id']}/access", json={"iid": iid}).json()
    arjun.post(f"/api/v1/library/access/{req['id']}", json={"approve": True})
    assert req["p1"] and seen == ["Arjun Mehta"]  # the admin who decided, not the departed owner


def test_s4_upload_does_not_confirm_a_locked_file(world):
    app, plane, _ = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    body = PLAIN + b"2026-02-28,Core,40\n"
    first = up(arjun, "oracle-secret.csv", body, share=True, sensitivity="restricted", note="oracle note words").json()["item"]
    got = up(leela, "oracle-secret.csv", body, note="oracle note words").json()
    assert "item" in got and "duplicate" not in got and "similar" not in got and got["item"]["id"] != first["id"]
    assert "duplicate" in up(arjun, "oracle-secret.csv", body).json()  # the owner still gets the warning


def test_s5_expiry_is_enforced_on_read_from_disk(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    item = up(arjun, "expiring.csv", PLAIN + b"2026-01-31,Core,30\n", share=True, sensitivity="restricted").json()["item"]
    arjun.post(f"/api/v1/library/{item['id']}/grants", json={"account_id": ids["Leela Raman"], "days": 7})
    assert not row(leela, item["id"]).get("locked")
    rows = L._index(plane)
    next(i for i in rows if i["id"] == item["id"])["grants"][0]["expires"] = "2020-01-01T00:00:00+00:00"
    write_json_atomic(L._index_path(plane), rows)  # written to disk, read back by the route
    assert row(leela, item["id"])["locked"]


def test_s5_topic_call_goes_through_the_router_and_the_gateway(world, monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT / "tests" / "egress"))
    from egress_helpers import Transport, log_lines, make_gateway
    from sh_platform.egress.model import EgressModelClient
    from sh_platform.v1 import router
    app, plane, _ = world
    transport = Transport()
    gw, vault, _p = make_gateway(plane, transport)
    vault.register("company", "Northwind Traders")
    routed = []
    real_route = router.route
    monkeypatch.setattr(router, "route", lambda *a, **k: (routed.append(a[1:3]), real_route(*a, **k))[1])
    n = len(log_lines(plane))
    # AQ1 (ER-01): a glued name is now swapped like any other; a name split by a hyphen and a line break still cannot be, and is refused
    assert C.ask_topic(EgressModelClient(gw), plane, "x.md", None, "North-\nwindTraders review") is None
    assert routed == [("north", "doc_read")]
    assert transport.calls == []
    assert log_lines(plane)[n:][-1]["reason_code"] == "vault_name"  # the gateway blocked it; nothing left the plane
