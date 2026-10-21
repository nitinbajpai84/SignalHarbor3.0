"""G5: the family portal (access above all), Web Push and the morning email in the dev outbox. Synthetic data only (Evergreen seed)."""
import base64
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import g5_portal as G  # noqa: E402
from sh_platform.v1 import g5_push as P  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

SOFIA, MEI = "Sofia Reyes", "Mei Chen"  # both have accounts in the seed; Raj Patel (approver) and Grace Ong (admin) are not family
GOOD = "https://fcm.googleapis.com/fcm/send/abc123"


def _login(data, pw, name):
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = EG.email_of(name)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def _family(plane):
    """Sofia: Holdings full, Trust summary, Entity B none. Mei: Trust full, nothing else. One document each."""
    with wh.connect(plane) as con:
        org = con.execute("select id from organizations").fetchone()[0]
        rec = con.execute("select id from source_records limit 1").fetchone()[0]
        usr = con.execute("select id from users limit 1").fetchone()[0]
        sysid = con.execute("select id from source_systems limit 1").fetchone()[0]
        when = datetime(2026, 10, 1, tzinfo=timezone.utc)
        for n in (SOFIA, MEI):
            EG.put(con, "family_members", dict(organization_id=org, source_record_id=rec, received_at=when, recorded_at=when, member_name=n))
            gid = EG.put(con, "access_groups", dict(organization_id=org, group_name="family:" + n))
            EG.put(con, "documents", dict(organization_id=org, source_system_id=sysid, access_group_id=gid, document_type="trust_letter", title=f"Letter for {n.split()[0]}",
                                          original_uri="seed://x", content_hash=n, received_at=when, recorded_at=when, document_status="final", processing_status="done",
                                          document_date=date(2026, 9, 30)))
        for who, code, level in [(SOFIA, "EG-HOLD", "full"), (SOFIA, "EG-TRUST", "summary"), (SOFIA, "EG-B", "none"), (MEI, "EG-TRUST", "full")]:
            rid = EG.put(con, "business_rules", dict(organization_id=org, rule_code=f"family_access_{G.slug(who)}_{G.slug(code)}", rule_type="family_access", owner_user_id=usr))
            EG.put(con, "rule_versions", dict(organization_id=org, business_rule_id=rid, version_number=1, definition_text=f"{who} sees {code} at {level}",
                                              parameters='{"level": "%s"}' % level, effective_from=date(2026, 1, 1), approval_status="approved"))


class _Clients(dict):
    """Signed-in clients made on first use and kept for the module (a login costs a whole app)."""
    _kept: dict = {}

    def __init__(self, data, pw):
        super().__init__()
        self.data, self.pw = data, pw

    def __missing__(self, name):
        key = (str(self.data), name)
        if key not in self._kept:
            self._kept[key] = _login(self.data, self.pw, name)
        return self._kept[key]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    import os
    os.environ["SH_MODEL_PROVIDER"] = "off"
    os.environ["SH_V3_SCAN"] = "off"
    data = tmp_path_factory.mktemp("g5") / "data"
    data.mkdir()
    EG.seed(data)
    plane = PlaneStore(data).plane_for("evergreen")
    _family(plane)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    return data, plane, pw


@pytest.fixture()
def w(world):
    data, plane, pw = world
    shutil.rmtree(plane.path("portal"), ignore_errors=True)  # each test starts with no approvals, subscriptions or sent mail
    shutil.rmtree(plane.path("outbox"), ignore_errors=True)
    return data, plane, _Clients(data, pw)


def names(share):
    return {l["entity"] for l in share["lines"]}


# ---- access: a member never sees another member's data ------------------------------------------------------------------------------

def test_a_member_sees_only_the_entities_their_own_rules_allow(w):
    _, _, c = w
    s, m = c[SOFIA].get("/api/v3/portal").json(), c[MEI].get("/api/v3/portal").json()
    assert s["member"] == SOFIA and names(s["share"]) == {"Evergreen Holdings", "Evergreen Family Trust"}
    assert m["member"] == MEI and names(m["share"]) == {"Evergreen Family Trust"}
    levels = {l["entity"]: l["level"] for l in s["share"]["lines"]}
    assert levels == {"Evergreen Holdings": "full", "Evergreen Family Trust": "summary"}
    assert "portfolios" in next(l for l in s["share"]["lines"] if l["level"] == "full") and "portfolios" not in next(l for l in s["share"]["lines"] if l["level"] == "summary")
    assert "Entity B" not in str(s) and "Holdings" not in str(m) and "Entity B" not in str(m)  # nothing leaks into any part of the payload


def test_documents_are_only_the_ones_filed_for_the_member(w):
    _, _, c = w
    assert [d["title"] for d in c[SOFIA].get("/api/v3/portal").json()["documents"]] == ["Letter for Sofia"]
    assert [d["title"] for d in c[MEI].get("/api/v3/portal").json()["documents"]] == ["Letter for Mei"]


def test_staff_who_are_not_family_are_refused_and_the_admin_can_preview(w):
    _, _, c = w
    assert c["Raj Patel"].get("/api/v3/portal").status_code == 403
    assert c["Raj Patel"].get("/api/v3/portal", params={"member": SOFIA}).status_code == 403  # the preview is the admin's only
    assert c["Grace Ong"].get("/api/v3/portal").status_code == 403
    assert c["Grace Ong"].get("/api/v3/portal", params={"member": SOFIA}).json()["member"] == SOFIA
    assert c["Grace Ong"].get("/api/v3/portal", params={"member": "Nobody"}).status_code == 404
    assert c[MEI].get("/api/v3/portal", params={"member": SOFIA}).json()["member"] == MEI  # a member cannot ask for someone else's view


def test_the_ask_box_answers_from_the_members_own_data_only(w):
    _, _, c = w
    ask = lambda who, q, **kw: c[who].post("/api/v3/portal/ask", json={"text": q, **kw}).json()["answer"]  # noqa: E731
    a = ask(MEI, "How much is Evergreen Holdings worth?")  # Mei has no right to Holdings
    assert "Holdings" not in a and "16" not in a and "Family Trust" in a  # answered from what she may see, naming nothing hidden
    assert "Letter for Mei" in ask(MEI, "show my documents") and "Sofia" not in ask(MEI, "show my documents")
    assert "Sofia" not in ask(MEI, "what does Sofia Reyes own?") and "Holdings" not in ask(MEI, "what does Sofia Reyes own?", member=SOFIA)
    assert ask(SOFIA, "tell me a joke") == G.HELP
    assert c["Raj Patel"].post("/api/v3/portal/ask", json={"text": "my share"}).status_code == 403
    assert c[SOFIA].post("/api/v3/portal/ask", json={"text": "  "}).status_code == 400


def test_the_signed_rule_is_capped_by_the_members_access_group(w):
    _, plane, c = w
    with wh.connect(plane) as con:
        org = con.execute("select id from organizations").fetchone()[0]
        gid = con.execute("select id from access_groups where group_name = ?", ["family:" + SOFIA]).fetchone()[0]
        EG.put(con, "access_group_scopes", dict(organization_id=org, access_group_id=gid, scope_type="entity", scope_value="EG-HOLD", access_level="preview"))
    try:
        assert G.levels(plane, SOFIA) == {"EG-HOLD": "summary"}  # rule says full, the group grants preview; the trust has no scope in the group, so none
    finally:
        with wh.connect(plane) as con:
            con.execute("delete from access_group_scopes where access_group_id = ?", [gid])


# ---- approvals addressed to a member ------------------------------------------------------------------------------------------------

def test_an_approval_is_addressed_to_one_member_and_only_they_decide(w):
    _, _, c = w
    made = c["Raj Patel"].post("/api/v3/portal/approvals", json={"member": SOFIA, "title": "Approve the school fee distribution", "amount": "12000"})
    assert made.status_code == 200
    aid = made.json()["id"]
    assert [a["id"] for a in c[SOFIA].get("/api/v3/portal").json()["approvals"]] == [aid]
    assert c[MEI].get("/api/v3/portal").json()["approvals"] == []
    assert c[MEI].post(f"/api/v3/portal/approvals/{aid}/decide", json={"approve": True}).status_code == 404  # not hers
    assert c["Grace Ong"].post(f"/api/v3/portal/approvals/{aid}/decide", json={"approve": True, "member": SOFIA}).status_code == 403  # the preview cannot decide
    assert c[SOFIA].post(f"/api/v3/portal/approvals/{aid}/decide", json={"approve": True, "note": "ok"}).json()["status"] == "approved"
    assert c[SOFIA].post(f"/api/v3/portal/approvals/{aid}/decide", json={"approve": False}).status_code == 409
    assert c[SOFIA].post("/api/v3/portal/approvals", json={"member": SOFIA, "title": "x"}).status_code == 403  # a member cannot raise one
    assert c["Raj Patel"].post("/api/v3/portal/approvals", json={"member": "Nobody", "title": "x"}).status_code == 400


# ---- my share and the look-through ---------------------------------------------------------------------------------------------------

def test_without_the_ownership_table_the_view_stays_at_entity_level(w):
    _, _, c = w
    s = c[SOFIA].get("/api/v3/portal").json()["share"]
    assert s["basis"] == "entity" and s["total"] is None and all(l["your_pct"] is None for l in s["lines"])
    assert "not your percentage" in s["note"]


def test_the_look_through_multiplies_the_chain_and_hides_what_is_not_shared(w):
    _, plane, c = w
    with wh.connect(plane) as con:
        org = con.execute("select id from organizations").fetchone()[0]
        con.execute("create table entity_ownership (id varchar primary key, organization_id varchar, owner_member_name varchar, owner_entity_id varchar, owned_entity_id varchar,"
                    " ownership_pct decimal(9,4), valid_from date, valid_to date)")
        ids = {r[0]: str(r[1]) for r in con.execute("select entity_code, id from legal_entities").fetchall()}
        rows = [(SOFIA, None, "EG-TRUST", 50), (None, "EG-TRUST", "EG-HOLD", 60), (None, "EG-HOLD", "EG-TRUST", 10),  # the last closes a circle
                (MEI, None, "EG-TRUST", 25), (SOFIA, None, "EG-B", 99)]
        for i, (mem, own, owned, pct) in enumerate(rows):
            con.execute("insert into entity_ownership values (?,?,?,?,?,?,?,?)", [f"o{i}", org, mem, ids[own] if own else None, ids[owned], pct, date(2026, 1, 1), None])
    try:
        s = c[SOFIA].get("/api/v3/portal").json()["share"]
        by = {l["code"]: l for l in s["lines"]}
        assert s["basis"] == "lookthrough" and set(by) == {"EG-TRUST", "EG-HOLD"}  # Entity B is in the chain but Sofia has no right to it
        assert float(by["EG-TRUST"]["your_pct"]) == pytest.approx(50.0) and float(by["EG-HOLD"]["your_pct"]) == pytest.approx(30.0)
        assert float(by["EG-HOLD"]["your_value"]) == pytest.approx(0.30 * 16_400_000) and float(by["EG-TRUST"]["your_value"]) == pytest.approx(0.50 * 41_200_000)
        assert float(s["total"]) == pytest.approx(0.30 * 16_400_000 + 0.50 * 41_200_000) and "1 more in the chain is not shared" in s["note"]
        m = c[MEI].get("/api/v3/portal").json()["share"]
        assert float(m["lines"][0]["your_pct"]) == pytest.approx(25.0) and len(m["lines"]) == 1
    finally:
        with wh.connect(plane) as con:
            con.execute("drop table entity_ownership")


# ---- push --------------------------------------------------------------------------------------------------------------------------

def test_dev_vapid_keys_land_in_the_data_root_and_the_token_verifies(w):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    data, plane, c = w
    cfg = c[SOFIA].get("/api/v3/push/config").json()
    assert cfg["enabled"] and cfg["subscribed"] is False and (data / "_control" / "vapid_dev.json").is_file()
    keys = P.vapid(plane)
    head, body, sig = P._token(keys, GOOD).split(".")
    raw = P._unb64(sig)
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), P._unb64(keys["public"]))
    pub.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
    assert b'"aud": "https://fcm.googleapis.com"' in base64.urlsafe_b64decode(body + "==")
    assert ROOT not in (data / "_control" / "vapid_dev.json").parents  # never in the repo


def test_env_keys_win_over_the_dev_pair(w, monkeypatch):
    _, plane, _ = w
    monkeypatch.setenv(P.ENV_PUB, "PUB")
    monkeypatch.setenv(P.ENV_PRIV, "PRIV")
    monkeypatch.setenv(P.ENV_SUB, "mailto:a@example.test")
    assert P.vapid(plane) == {"public": "PUB", "private": "PRIV", "subject": "mailto:a@example.test"}


def test_subscribe_toggle_and_the_address_check(w):
    _, plane, c = w
    ok = c[SOFIA].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD, "keys": {}}})
    assert ok.status_code == 200 and c[SOFIA].get("/api/v3/push/config").json()["subscribed"] is True
    assert c[MEI].get("/api/v3/push/config").json()["subscribed"] is False  # per account
    for bad in ("http://fcm.googleapis.com/x", "https://169.254.169.254/latest", "https://evil.example.test/push", "https://fcm.googleapis.com.evil.test/x", ""):
        assert c[SOFIA].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": bad}}).status_code == 400
    assert c[SOFIA].post("/api/v3/push/unsubscribe", json={}).json() == {"subscribed": False}


def test_a_new_approval_wakes_the_member_and_the_words_wait_in_the_inbox(w, monkeypatch):
    _, plane, c = w
    sent = []
    monkeypatch.setattr(P, "send_one", lambda pl, ep: sent.append(ep) or 201)
    accts = G.accounts_of(plane)
    c[SOFIA].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD}})
    c[MEI].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD + "-mei"}})
    assert P.tick(plane, accts) == 0 and sent == []  # the first pass only records what is there
    c["Raj Patel"].post("/api/v3/portal/approvals", json={"member": SOFIA, "title": "Approve the school fee distribution"})
    assert P.tick(plane, accts) == 1 and sent == [GOOD]  # Sofia's device only; Mei's is not told
    assert P.tick(plane, accts) == 0  # said once
    box = c[SOFIA].get("/api/v3/push/inbox").json()
    assert box[0]["title"] == "Approval for you" and "school fee" in box[0]["body"] and box[0]["url"] == "/v3/portal#approvals"
    assert c[SOFIA].get("/api/v3/push/inbox").json() == [] and c[MEI].get("/api/v3/push/inbox").json() == []


def test_a_gone_device_is_dropped(w, monkeypatch):
    _, plane, c = w
    monkeypatch.setattr(P, "send_one", lambda pl, ep: 410)
    c[SOFIA].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD}})
    assert P.notify(plane, AccountStore(plane.root.parent).get_by_email(EG.email_of(SOFIA))["account_id"], "t", "b", "/v3/desk") == 0
    assert c[SOFIA].get("/api/v3/push/config").json()["subscribed"] is False


def test_a_new_action_card_goes_to_the_admins_and_the_routed_job(w, monkeypatch):
    _, plane, c = w
    from sh_platform.v1 import v3_signals as SG
    sent, cards = [], []
    monkeypatch.setattr(P, "send_one", lambda pl, ep: sent.append(ep) or 201)
    monkeypatch.setattr(SG, "fired", lambda pl: cards)
    accts = G.accounts_of(plane)
    c["Grace Ong"].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD + "-grace"}})
    c[SOFIA].post("/api/v3/push/subscribe", json={"subscription": {"endpoint": GOOD + "-sofia"}})
    P.tick(plane, accts)
    cards.append({"id": "f1", "status": "open", "title": "A capital call is due", "route_to": "cio"})
    assert P.tick(plane, accts) == 1 and sent == [GOOD + "-grace"]  # the admin only: nobody holds the cio job yet
    from sh_platform.v1 import v3_ops as O
    O._save(plane, {**O.settings(plane), "jobs": {EG.email_of(SOFIA): "cio"}})
    try:
        cards.append({"id": "f2", "status": "open", "title": "A limit is breached", "route_to": "cio"})
        assert P.tick(plane, accts) == 2 and sorted(sent[1:]) == [GOOD + "-grace", GOOD + "-sofia"]  # the admin and whoever holds the routed job
    finally:
        O._save(plane, {k: v for k, v in O.settings(plane).items() if k != "jobs"})


# ---- the morning email -------------------------------------------------------------------------------------------------------------

def test_the_morning_note_is_written_to_the_dev_outbox_once_a_day(w, monkeypatch):
    _, plane, c = w
    monkeypatch.delenv("SH_SMTP_URL", raising=False)
    accts = G.accounts_of(plane)
    out = c["Grace Ong"].post("/api/v3/portal/morning-email", json={"force": True}).json()
    mails = {m["to"]: m["result"] for m in out["sent"]}
    assert mails[EG.email_of(SOFIA)] == "kept in the outbox" and mails[EG.email_of(MEI)] == "kept in the outbox"
    files = sorted(plane.path("outbox").glob("*.eml"))
    assert len(files) >= 2
    mei = next(t for t in (f.read_text(encoding="utf-8", errors="replace") for f in files) if f"To: {EG.email_of(MEI)}" in t)
    assert "Entity B" not in mei and "16,400,000" not in mei and "Holdings" not in mei  # Mei's own note names nothing she may not see
    assert G.send_morning(plane, accts, out["day"])["skipped"] == "already sent today"
    assert c["Raj Patel"].post("/api/v3/portal/morning-email", json={}).status_code == 403


def test_smtp_is_named_by_env_var_only():
    import sh_platform.egress.email as mail
    assert mail.SMTP_ENV == "SH_SMTP_URL" and "smtp://" not in Path(G.__file__).read_text(encoding="utf-8").replace("smtp://user", "")
