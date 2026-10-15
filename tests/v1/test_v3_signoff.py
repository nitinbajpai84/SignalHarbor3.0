"""Decision 1 sign-off: a person who may not sign sends the brief to the signer; the signer confirms in their own name; the record shows both."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from tests.v1.test_v3_harbor import SOW, stub_a  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

SIGNED = {"state": "signed", "version": 3, "signature": {"name": "Daniel Foo", "role": "sponsor", "at": "2026-10-15T09:30:00Z"}}


def fake_api(self, who, method, path, body=None, files=None, data=None, soft=False):
    if path == "/api/v1/intents/chat":
        return {"id": "ini-1", "turns": [{"by": "north", "text": "Here is what I understood."}], "sow": SOW}
    if path.endswith("/sow"):
        return SIGNED
    if path.endswith("/chat"):
        return {"project_id": "p-1"}
    return {}


@pytest.fixture()
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    monkeypatch.setattr(H.Ctx, "api", fake_api)
    monkeypatch.setattr(H, "_team_up", lambda x, pid: None)
    monkeypatch.setitem(H.CHAINS, "A", ([("Harbor", "Signed", H.a_sign), ("Span", "Read the files", stub_a)], "decision2"))
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))

    def login(who):
        c = TestClient(app)
        email = f"{who}.evergreen@example.test"
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
        return c
    return login


def test_non_signer_sends_signer_confirms_record_shows_both(office):
    sofia, daniel = office("sofia.reyes"), office("daniel.foo")
    t = sofia.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()
    tid = t["id"]
    assert t["signoff"]["state"] == "send" and t["signoff"]["signer"]["name"] == "Daniel Foo"
    assert sofia.get("/api/v3/desk").json()["needs"][0]["actions"][0]["label"] == "Send to Daniel Foo to confirm"
    t = sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "send_for_signature"}).json()
    assert t["stage"] == "decision1" and t["signoff"]["state"] == "waiting" and t["signoff"]["mine"]
    assert sofia.get("/api/v3/desk").json()["needs"][0]["text"] == "Waiting for Daniel Foo to confirm."
    need = daniel.get("/api/v3/desk").json()["needs"][0]  # the signer's Action card
    assert need["kind"] == "decision" and [a["answer"] for a in need["actions"]] == ["confirm", "not_yet"]
    t = daniel.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert t["stage"] == "decision2", t["events"][-1]
    r = t["record"]
    assert r["line"] == "Raised by Sofia Reyes · Confirmed and signed by Daniel Foo"
    assert r["started_at"] and r["sent_at"] and r["signed_at"]


def test_non_signer_cannot_confirm_directly(office):
    sofia = office("sofia.reyes")
    tid = sofia.post("/api/v3/threads", json={"text": "x"}).json()["id"]
    r = sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"})
    assert r.status_code == 409 and "Daniel Foo" in r.json()["detail"]
    assert sofia.get(f"/api/v3/threads/{tid}").json()["stage"] == "decision1"


def test_signer_does_not_get_a_send_button(office):
    daniel = office("daniel.foo")
    t = daniel.post("/api/v3/threads", json={"text": "x"}).json()
    assert t["signoff"]["state"] == "can_sign"
    assert daniel.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "send_for_signature"}).status_code == 409


def test_sending_to_someone_who_cannot_sign_is_refused(office):
    sofia = office("sofia.reyes")
    tid = sofia.post("/api/v3/threads", json={"text": "x"}).json()["id"]
    r = sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "send_for_signature", "to": "tom.hale.evergreen@example.test"})
    assert r.status_code == 409 and "Daniel Foo" in r.json()["detail"]


def test_a_thread_stuck_on_the_old_refusal_goes_back_to_decision_one(office):
    sofia = office("sofia.reyes")
    t = sofia.post("/api/v3/threads", json={"text": "x"}).json()
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(sofia.app.state.settings.data_root).plane_for("evergreen").ensure()
    th = H.load(plane, t["id"])
    th["brief"], th["stage"], th["decision"], th["resume"] = th["decision"]["brief"], "question", None, {"chain": "A", "i": 0, "q": []}
    H.ev(th, "question", "Only the person who raised this, or the sponsor, can do this.")
    H.save(plane, th)
    got = sofia.get(f"/api/v3/threads/{t['id']}").json()
    assert got["stage"] == "decision1" and got["signoff"]["state"] == "send"


# ---- test cycle 1: the sign-off path is never a dead end ------------------------------------------------------------------------

from sh_platform.v1 import v3_signoff as SO  # noqa: E402


@pytest.fixture()
def drafty(office, monkeypatch):
    """The intent stays a draft until the signer's POST /sow/sign; `gaps` is what signing would still refuse."""
    st = {"signed": False, "gaps": [], "filled": []}

    def api(self, who, method, path, body=None, files=None, data=None, soft=False):
        if path.endswith("/sow/sign"):
            st["signed"] = True
            return {}
        if path.endswith("/sow"):
            return SIGNED if st["signed"] else {"state": "draft", "version": 2}
        return fake_api(self, who, method, path, body, files, data, soft)
    monkeypatch.setattr(H.Ctx, "api", api)
    monkeypatch.setattr(SO, "blocking", lambda plane, iid: list(st["gaps"]))

    def fill(x, gaps):
        st["filled"].append(list(gaps))
        st["gaps"] = [g for g in st["gaps"] if g.startswith("When")]  # the usual practice covers all but a deadline (NI-3: never assumed)
        return st["gaps"]
    monkeypatch.setattr(SO, "fill", fill)
    return office, st


def _plane(c):
    from sh_platform.plane import PlaneStore
    return PlaneStore(c.app.state.settings.data_root).plane_for("evergreen").ensure()


def _acct(c, email):
    a = c.app.state.account_store.get_by_email(email)
    return a.get("account_id") or a.get("id")


def test_a_brief_with_gaps_is_never_sent_the_raiser_sees_them_named(drafty):
    office, st = drafty
    sofia = office("sofia.reyes")
    st["gaps"] = ["When it is needed and how often", "Process map: Lanes and steps"]
    t = sofia.post("/api/v3/threads", json={"text": "What changed at the manager?"}).json()
    so = t["signoff"]
    assert so["state"] == "fill" and so["gaps"] == st["gaps"] and "Process map: Lanes and steps" in so["message"] and "Daniel Foo" in so["message"]
    r = sofia.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "send_for_signature"})
    assert r.status_code == 409 and "When it is needed and how often" in r.json()["detail"]
    need = sofia.get("/api/v3/desk").json()["needs"][0]
    assert need["kind"] == "question" and "Lanes and steps" in need["text"]
    st["gaps"] = []  # the raiser answered
    assert sofia.get(f"/api/v3/threads/{t['id']}").json()["signoff"]["state"] == "send"
    assert sofia.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "send_for_signature"}).status_code == 200


def test_signer_confirm_runs_the_gap_fill_then_signs_and_record_is_filled(drafty):
    office, st = drafty
    sofia, daniel = office("sofia.reyes"), office("daniel.foo")
    tid = sofia.post("/api/v3/threads", json={"text": "Limits"}).json()["id"]
    sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "send_for_signature"})
    st["gaps"] = ["Process map: Lanes and steps"]  # opened after sending (a later edit): the signer's confirm fills it
    t = daniel.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert st["filled"] == [["Process map: Lanes and steps"]] and st["signed"]
    assert t["stage"] == "decision2", t["events"][-1]
    r = t["record"]
    assert r["line"] == "Raised by Sofia Reyes · Confirmed and signed by Daniel Foo" and r["signed_by"] == "Daniel Foo"
    assert r["signed_at"] and r["started_at"] and r["sent_at"]


def test_a_gap_only_a_person_can_say_goes_back_to_the_raiser_named_never_a_loop(drafty):
    office, st = drafty
    sofia, daniel = office("sofia.reyes"), office("daniel.foo")
    tid = sofia.post("/api/v3/threads", json={"text": "Manager diligence"}).json()["id"]
    sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "send_for_signature"})
    st["gaps"] = ["When it is needed and how often", "Process map: Lanes and steps"]
    daniel.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"})
    assert not st["signed"]
    t = sofia.get(f"/api/v3/threads/{tid}").json()
    q = [e["text"] for e in t["events"] if e["kind"] == "question"][-1]
    assert q.startswith("Before Daniel Foo can sign this, I still need from Sofia Reyes: When it is needed and how often")
    assert "Lanes and steps" not in q  # the fill covered that one
    assert t["stage"] == "decision1" and t["signoff"]["state"] == "fill" and t["decision"]["gaps"] == ["When it is needed and how often"]
    st["gaps"] = []  # Sofia answers; she sends again and Daniel signs
    assert sofia.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "send_for_signature"}).status_code == 200
    t = daniel.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert st["signed"] and t["stage"] == "decision2" and t["record"]["signed_by"] == "Daniel Foo"


def test_a_participant_raisers_drafts_land_in_their_brief(office, monkeypatch):
    sofia = office("sofia.reyes")
    t = sofia.post("/api/v3/threads", json={"text": "x"}).json()
    plane = _plane(sofia)
    th = H.load(plane, t["id"])
    x = H.Ctx(sofia.app, plane, th, _acct(sofia, "sofia.reyes.evergreen@example.test"))
    got = []
    monkeypatch.setattr(H.Ctx, "api", lambda self, who, m, p, *a, **k: {"pending": [{"id": "pr1", "document": "sow"}, {"id": "pr2", "document": "design"}]} if m == "GET" else {})
    from sh_platform.v1 import l2_proposals as L2
    monkeypatch.setattr(L2, "accept", lambda plane, iid, pid, who: got.append((pid, who)))
    SO.accept_drafts(x, "ini-1")
    assert got == [("pr1", "Sofia Reyes (North's draft; confirmed when signed)")]
    th["started_by"] = "Someone Else"  # never someone else's brief
    got.clear()
    SO.accept_drafts(x, "ini-1")
    assert got == []


def test_files_dropped_before_the_sign_off_are_claimed_by_that_thread(office):
    sofia = office("sofia.reyes")
    t = sofia.post("/api/v3/threads", json={"text": "What changed at Kestrel Ridge since our last meeting?"}).json()
    plane = _plane(sofia)
    th = H.load(plane, t["id"])
    th["sources"] = ["Manager statements"]
    w = {"source": "", "thread": None, "arrived_at": "2026-10-09T00:00:00Z"}
    fs = [{"name": "kestrel_ridge_q3_2026_newsletter.pdf", "status": "waiting", **w}, {"name": "04_kestrel_ridge_onsite_2026-06-12.md", "status": "waiting", **w},
          {"name": "manager_statements_q3.pdf", "status": "question", **w}, {"name": "trading_export_20261005.csv", "status": "waiting", **w},
          {"name": "kestrel_H1_final.pdf", "status": "loaded", **w, "thread": "t-other"}]
    H._fp(plane).parent.mkdir(parents=True, exist_ok=True)
    H._fp(plane).write_text(__import__("json").dumps(fs), encoding="utf-8")
    assert SO.claim_files(H.Ctx(sofia.app, plane, th, None)) == 3
    by = {f["name"]: f for f in H.read_files(plane)}
    assert by["kestrel_ridge_q3_2026_newsletter.pdf"]["thread"] == th["id"] and by["04_kestrel_ridge_onsite_2026-06-12.md"]["status"] == "recognised"
    assert by["manager_statements_q3.pdf"]["source"] == "Manager statements"
    assert by["trading_export_20261005.csv"]["thread"] is None and by["kestrel_H1_final.pdf"]["thread"] == "t-other"
    assert len(H.my_files(H.Ctx(None, plane, th, None))) == 3
