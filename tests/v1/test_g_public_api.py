"""W6 public API (sh_platform/v1/v3_public_api.py, docs/v3/API.md): keys per company, scopes, entity limits, rate limit, the call log, cross-company refusal,
signed webhooks through the egress gateway, the OpenAPI schema. Real: the app, the routes, the permissions, the stores, the gateway. Stubbed: the
answer worker (Lumen), the document rows and the HTTP post of a webhook."""
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.egress.policy import EgressPolicy  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import e2_screen as S, v3_board_routes as B, v3_figstore as FS, v3_public_api as A, v3_signals as SG  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"
BASE = "/api/public/v1"
ADMIN = "boss@evergreen.example.test"


def figure_rec(fid, name, entity=None):
    rec = {"id": fid, "name": name, "definition": f"{name} as the office defines it", "grain": ["entity"], "current_v": 1, "used_by": [{"thread": "t1", "person": "Daniel Foo"}],
           "versions": [{"v": 1, "status": "verified", "built_from": "cash_break", "reads": ["cash_movements"], "sql_hash": "abc123abc123", "model": None, "prompt_hash": None,
                         "assumptions": [{"text": "Money in is positive"}], "tie_out": {"rule": "ties to the bank", "ok": True, "at": "2026-10-01T00:00:00Z"},
                         "approved_by": "Daniel Foo", "approved_at": "2026-10-01T00:00:00Z", "runs": [{"run_id": "r1", "at": "2026-10-02T00:00:00Z", "ok": True, "rows": 3}]}]}
    return rec | ({"entity_ids": [entity]} if entity else {})


def card(cid, entity=None, status="open"):
    return {"id": cid, "signal": "uc01-call-arrives", "title": "A call arrives", "subject": "Call 7", "severity": "high", "route_to": "decision_maker", "role_title": "Principal",
            "person": {"email": "mei@evergreen.example.test", "name": "Mei Chen"}, "action": {"verb": "Approve"}, "status": status, "at": "2026-10-20T08:00:00Z",
            "message": "A call of 100 is due", "evidence": [{"label": "Commitments", "v": 3}], "values": {"secret": "1"}, "event": {"doc": "raw"}, "hold": None} | ({"entity_id": entity} if entity else {})


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    es = EntitlementStore(data)
    es.create_company("birch", "Birch Office", "family_office", modules=es.catalogue.ids)
    st = AccountStore(data)
    st.create(ADMIN, PW, "Bo Boss", "evergreen", ["company_admin"])
    st.create("sam@evergreen.example.test", PW, "Sam Lee", "evergreen", ["participant"])
    st.create("bia@birch.example.test", PW, "Bia Birch", "birch", ["company_admin"])
    eg = PlaneStore(str(data)).plane_for("evergreen").ensure()
    bi = PlaneStore(str(data)).plane_for("birch").ensure()
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    A._HITS.clear()
    return app, eg, bi


def login(app, email) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def make(admin, label="tool", scopes=("figures", "ask", "signals", "documents"), **extra):
    r = admin.post("/api/v3/api-keys", json={"label": label, "scopes": list(scopes), **extra})
    assert r.status_code == 200, r.text
    return r.json()


def api(app, key=None):
    c = TestClient(app)  # no cookie: only the key identifies the caller
    if key:
        c.headers["Authorization"] = f"Bearer {key}"
    return c


# ---- keys -----------------------------------------------------------------------------------------------------------------------------

def test_key_is_shown_once_and_stored_hashed(env):
    app, eg, _ = env
    admin = login(app, ADMIN)
    k = make(admin)
    secret = k["key"].split(".", 3)[3]
    stored = (eg.path("v3", "api") / "keys.json").read_text(encoding="utf-8")
    assert secret not in stored and "hash" in stored
    listed = admin.get("/api/v3/api-keys").json()
    assert secret not in json.dumps(listed) and listed["keys"][0]["id"] == k["id"]


def test_only_an_office_admin_makes_keys(env):
    app, _, _ = env
    sam = login(app, "sam@evergreen.example.test")
    assert sam.get("/api/v3/api-keys").status_code == 403
    assert sam.post("/api/v3/api-keys", json={"label": "x", "scopes": ["figures"]}).status_code == 403
    assert TestClient(app).get("/api/v3/api-keys").status_code == 401


@pytest.mark.parametrize("body", [{"label": "", "scopes": ["figures"]}, {"label": "x", "scopes": []}, {"label": "x", "scopes": ["write"]},
                                  {"label": "x", "scopes": ["figures"], "kind": "family"},
                                  {"label": "x", "scopes": ["figures", "ask"], "kind": "family", "entity_ids": ["E1"]},
                                  {"label": "x", "scopes": ["ask"], "entity_ids": ["E1"]}, {"label": "x", "scopes": ["figures"], "rate_per_min": 0}])
def test_bad_key_requests_are_refused(env, body):
    app, _, _ = env
    assert login(app, ADMIN).post("/api/v3/api-keys", json=body).status_code == 400


def test_no_key_a_wrong_key_and_a_revoked_key_are_401(env):
    app, _, _ = env
    admin = login(app, ADMIN)
    k = make(admin)
    assert api(app).get(f"{BASE}/figures").status_code == 401
    assert api(app, "nonsense").get(f"{BASE}/figures").status_code == 401
    assert api(app, k["key"][:-3] + "xxx").get(f"{BASE}/figures").status_code == 401
    assert api(app, k["key"]).get(f"{BASE}/figures").status_code == 200
    assert admin.delete(f"/api/v3/api-keys/{k['id']}").status_code == 200
    assert api(app, k["key"]).get(f"{BASE}/figures").status_code == 401


def test_a_scope_not_granted_is_403(env):
    app, _, _ = env
    k = make(login(app, ADMIN), scopes=["figures"])
    c = api(app, k["key"])
    assert c.get(f"{BASE}/figures").status_code == 200
    for r in (c.get(f"{BASE}/signals"), c.get(f"{BASE}/documents"), c.post(f"{BASE}/ask", json={"text": "cash?"})):
        assert r.status_code == 403 and r.json()["detail"]["error"] == "scope_not_granted"


# ---- figures, signals, documents ----------------------------------------------------------------------------------------------------

def test_figures_list_and_detail_with_receipts(env):
    app, eg, _ = env
    FS._save(eg, figure_rec("fig-cash-break", "Cash break"))
    c = api(app, make(login(app, ADMIN))["key"])
    rows = c.get(f"{BASE}/figures").json()["figures"]
    assert [r["id"] for r in rows] == ["fig-cash-break"] and rows[0]["status"] == "verified"
    d = c.get(f"{BASE}/figures/fig-cash-break").json()
    assert d["receipts"]["sql_hash"] == "abc123abc123" and d["receipts"]["runs"][0]["run_id"] == "r1" and d["receipts"]["tie_out"]["ok"]
    assert "Daniel Foo" not in json.dumps(d) and "used_by" not in d  # who asked for it stays inside
    assert c.get(f"{BASE}/figures/fig-nope").status_code == 404


def test_signals_show_the_card_without_the_person_or_the_event(env):
    app, eg, _ = env
    SG._put(eg, card("sg-1"))
    SG._put(eg, card("sg-2", status="acted"))
    c = api(app, make(login(app, ADMIN))["key"])
    body = c.get(f"{BASE}/signals").json()["signals"]
    assert {r["id"] for r in body} == {"sg-1", "sg-2"}
    text = json.dumps(body)
    assert "mei@evergreen" not in text and "Mei Chen" not in text and "raw" not in text and "secret" not in text
    assert [r["id"] for r in c.get(f"{BASE}/signals?status=acted").json()["signals"]] == ["sg-2"]


def test_documents_are_metadata_only(env, monkeypatch):
    app, _, _ = env
    monkeypatch.setattr(S, "rows", lambda plane, viewer, i=None: [{"id": "d1", "title": "Statement Oct", "document_type": "statement", "original_filename": "oct.pdf",
                        "original_uri": "evidence/oct.pdf", "instrument_name": "Fund A", "label": "Current", "document_status": "read", "valuation_date": "2026-09-30",
                        "received_at": "2026-10-05", "processing_status": "done"}])
    got = api(app, make(login(app, ADMIN))["key"]).get(f"{BASE}/documents").json()["documents"]
    assert got[0]["title"] == "Statement Oct" and got[0]["original_filename"] == "oct.pdf"
    assert "original_uri" not in got[0] and "evidence/" not in json.dumps(got)


# ---- ask ------------------------------------------------------------------------------------------------------------------------------

def test_ask_uses_the_consume_answer_path_as_the_least_seat(env, monkeypatch):
    app, _, _ = env
    seen = []

    def fake(plane, viewer, text, pid):
        seen.append((plane.company_id, viewer, text))
        return {"answer": "Cash is 100.", "figure": {"label": "Cash", "value": "100"}, "trace": [], "used": []}
    monkeypatch.setattr(B, "_ask", fake)
    key = make(login(app, ADMIN))["key"]
    r = api(app, key).post(f"{BASE}/ask", json={"text": "How much cash do we have?"})
    assert r.status_code == 200 and r.json()["answer"] == "Cash is 100." and r.json()["cached"] is False
    assert api(app, key).post(f"{BASE}/ask", json={"text": "How much cash do we have?"}).json()["cached"] is True  # kept per question, as on the Consume page
    company, viewer, _ = seen[0]
    assert company == "evergreen" and viewer.roles == frozenset({"participant"}) and viewer.account_id.startswith("apikey-") and len(seen) == 1
    assert api(app, key).post(f"{BASE}/ask", json={"text": ""}).status_code == 422
    assert api(app, key).post(f"{BASE}/ask", json={}).status_code == 422


def test_ask_with_no_build_live_answers_plainly(env):
    app, _, _ = env
    r = api(app, make(login(app, ADMIN))["key"]).post(f"{BASE}/ask", json={"text": "What is our total cash balance?"})
    assert r.status_code == 200 and r.json()["answer"]


# ---- family-member and entity-limited keys -----------------------------------------------------------------------------------------------

def test_a_family_key_sees_only_its_own_share(env):
    app, eg, _ = env
    FS._save(eg, figure_rec("fig-a", "Holdings A", "ENT-A"))
    FS._save(eg, figure_rec("fig-b", "Holdings B", "ENT-B"))
    FS._save(eg, figure_rec("fig-all", "Whole office"))
    SG._put(eg, card("sg-a", "ENT-A"))
    SG._put(eg, card("sg-b", "ENT-B"))
    SG._put(eg, card("sg-n"))
    admin = login(app, ADMIN)
    k = make(admin, "Ann", scopes=["figures", "signals"], kind="family", member="Ann Lee", entity_ids=["ENT-A"])
    c = api(app, k["key"])
    assert [r["id"] for r in c.get(f"{BASE}/figures").json()["figures"]] == ["fig-a"]
    assert c.get(f"{BASE}/figures/fig-b").status_code == 404 and c.get(f"{BASE}/figures/fig-all").status_code == 404
    assert c.get(f"{BASE}/figures/fig-a").status_code == 200
    assert [r["id"] for r in c.get(f"{BASE}/signals").json()["signals"]] == ["sg-a"]
    whole = api(app, make(admin, "Whole", scopes=["figures", "signals"])["key"])
    assert len(whole.get(f"{BASE}/figures").json()["figures"]) == 3 and len(whole.get(f"{BASE}/signals").json()["signals"]) == 3


def test_a_family_key_takes_its_entities_from_the_signed_rules(env, monkeypatch):
    app, _, _ = env
    monkeypatch.setattr(A, "family_entities", lambda plane, member: ["ENT-A", "ENT-C"] if member == "Ann Lee" else [])
    admin = login(app, ADMIN)
    assert make(admin, "Ann", scopes=["figures"], kind="family", member="Ann Lee")["entity_ids"] == ["ENT-A", "ENT-C"]
    assert admin.post("/api/v3/api-keys", json={"label": "Zed", "scopes": ["figures"], "kind": "family", "member": "Zed Nobody"}).status_code == 400


def test_family_entities_with_no_rules_is_empty(env):
    _, eg, _ = env
    assert A.family_entities(eg, "Ann Lee") == []


# ---- the company wall ---------------------------------------------------------------------------------------------------------------------

def test_a_key_of_one_company_never_reads_another(env):
    app, eg, bi = env
    FS._save(eg, figure_rec("fig-eg", "Evergreen only"))
    FS._save(bi, figure_rec("fig-bi", "Birch only"))
    SG._put(eg, card("sg-eg"))
    ek = make(login(app, ADMIN))
    bk = make(login(app, "bia@birch.example.test"))
    b = api(app, bk["key"])
    assert [r["id"] for r in b.get(f"{BASE}/figures").json()["figures"]] == ["fig-bi"]
    assert b.get(f"{BASE}/figures/fig-eg").status_code == 404
    assert b.get(f"{BASE}/signals").json()["signals"] == []
    _, _, kid, secret = bk["key"].split(".", 3)  # birch's key id and secret, said to be evergreen's: that key id is not in evergreen's plane
    assert api(app, f"shpub.evergreen.{kid}.{secret}").get(f"{BASE}/figures").status_code == 401
    _, _, ekid, esecret = ek["key"].split(".", 3)  # evergreen's key id with birch's name on it
    assert api(app, f"shpub.birch.{ekid}.{esecret}").get(f"{BASE}/figures").status_code == 401
    assert api(app, f"shpub.../evergreen.{kid}.{secret}").get(f"{BASE}/figures").status_code == 401  # a path trick in the company part
    birch_admin = login(app, "bia@birch.example.test")  # the admin page of one company lists only its own keys and calls
    page = birch_admin.get("/api/v3/api-keys").json()
    assert [x["id"] for x in page["keys"]] == [bk["id"]] and all(c["key"] == bk["id"] for c in page["calls"])
    assert birch_admin.delete(f"/api/v3/api-keys/{ek['id']}").status_code == 404 and birch_admin.get(f"/api/v3/api-keys/{ek['id']}/calls").json()["calls"] == []
    assert api(app, ek["key"]).get(f"{BASE}/figures").status_code == 200  # birch's admin could not revoke it


# ---- rate limit and the call log -----------------------------------------------------------------------------------------------------

def test_rate_limit_per_key_and_every_call_logged(env):
    app, _, _ = env
    admin = login(app, ADMIN)
    k = make(admin, "slow", scopes=["figures"], rate_per_min=2)
    other = make(admin, "other", scopes=["figures"], rate_per_min=2)
    c = api(app, k["key"])
    assert c.get(f"{BASE}/figures").status_code == 200 and c.get(f"{BASE}/figures/fig-x").status_code == 404
    r = c.get(f"{BASE}/figures")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    assert api(app, other["key"]).get(f"{BASE}/figures").status_code == 200  # another key has its own minute
    assert c.get(f"{BASE}/signals").status_code == 403  # the scope is checked before the rate, so this one does not count
    log = admin.get(f"/api/v3/api-keys/{k['id']}/calls").json()["calls"]
    assert [(x["route"], x["status"]) for x in reversed(log)] == [("GET /api/public/v1/figures", 200), ("GET /api/public/v1/figures/{figure_id}", 404),
                                                                  ("GET /api/public/v1/figures", 429), ("GET /api/public/v1/signals", 403)]
    assert all(x["key"] == k["id"] and x["at"].endswith("Z") for x in log)


def test_a_wrong_secret_for_a_known_key_is_logged_and_an_unknown_key_is_not(env):
    app, eg, _ = env
    k = make(login(app, ADMIN))
    api(app, k["key"][:-2] + "zz").get(f"{BASE}/figures")
    api(app, "shpub.evergreen.deadbeef0000.nope").get(f"{BASE}/figures")
    assert [(x["key"], x["status"]) for x in A.calls(eg)] == [(k["id"], 401)]


def test_sliding_window(env):
    _, eg, _ = env
    rec = {"id": "k1", "rate_per_min": 2}
    assert A.allow(eg, rec, 0.0) and A.allow(eg, rec, 1.0) and not A.allow(eg, rec, 2.0)
    assert A.allow(eg, rec, 60.5) and A.allow(eg, rec, 61.5) and not A.allow(eg, rec, 62.0)  # the call at 0.0 and then the one at 1.0 each leave the minute
    assert A.allow(eg, rec, 121.0)


# ---- webhooks -----------------------------------------------------------------------------------------------------------------------------

def test_webhook_is_signed_and_goes_through_the_allow_list(env):
    app, eg, _ = env
    admin = login(app, ADMIN)
    k = make(admin, "hook", scopes=["signals"])
    assert admin.post(f"/api/v3/api-keys/{k['id']}/webhook", json={"url": "http://hooks.example.test/x"}).status_code == 400  # https only
    hook = admin.post(f"/api/v3/api-keys/{k['id']}/webhook", json={"url": "https://hooks.example.test/harbor"}).json()
    assert hook["allowed"] is False and len(hook["secret"]) >= 32
    assert hook["secret"] not in json.dumps(admin.get("/api/v3/api-keys").json())
    sent = []

    def post(url, body, headers):
        sent.append((url, body, headers))
        return "ok"
    c = card("sg-1")
    assert A.notify_signal(eg, c, post) == [{"key": k["id"], "ok": False, "why": "destination_not_allowed"}] and not sent  # the host is not on the list yet
    EgressPolicy(eg).set_webhook_hosts(["hooks.example.test"])
    assert A.notify_signal(eg, c, post) == [{"key": k["id"], "ok": True}]
    url, body, headers = sent[0]
    assert url == "https://hooks.example.test/harbor" and headers["x-harbor-event"] == "signal.fired"
    assert headers["x-harbor-signature"] == "sha256=" + hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
    payload = json.loads(body)
    assert payload["event"] == "signal.fired" and payload["signal"]["id"] == "sg-1" and "mei@" not in body.decode() and "values" not in payload["signal"]
    assert "hooks.example.test" in (eg.area("context") / "egress_log.jsonl").read_text(encoding="utf-8")  # the gateway logged the host


def test_webhook_needs_the_signals_scope_a_live_key_and_the_entity(env):
    app, eg, _ = env
    admin = login(app, ADMIN)
    plain = make(admin, "figs", scopes=["figures"])
    assert admin.post(f"/api/v3/api-keys/{plain['id']}/webhook", json={"url": "https://hooks.example.test/a"}).status_code == 400
    fam = make(admin, "fam", scopes=["signals"], kind="family", member="Ann", entity_ids=["ENT-A"])
    gone = make(admin, "gone", scopes=["signals"])
    for kid in (fam["id"], gone["id"]):
        assert admin.post(f"/api/v3/api-keys/{kid}/webhook", json={"url": "https://hooks.example.test/b"}).status_code == 200
    admin.delete(f"/api/v3/api-keys/{gone['id']}")
    EgressPolicy(eg).set_webhook_hosts(["hooks.example.test"])
    sent = []

    def post(url, body, headers):
        sent.append(url)
        return "ok"
    assert A.notify_signal(eg, card("sg-b", "ENT-B"), post) == [] and not sent
    assert A.notify_signal(eg, card("sg-n"), post) == []  # untagged is withheld from a limited key
    assert A.notify_signal(eg, card("sg-a", "ENT-A"), post) == [{"key": fam["id"], "ok": True}]


def test_a_failing_webhook_never_raises(env):
    app, eg, _ = env
    admin = login(app, ADMIN)
    k = make(admin, "hook", scopes=["signals"])
    admin.post(f"/api/v3/api-keys/{k['id']}/webhook", json={"url": "https://hooks.example.test/harbor"})
    EgressPolicy(eg).set_webhook_hosts(["hooks.example.test"])

    def boom(url, body, headers):
        raise OSError("down")
    assert A.notify_signal(eg, card("sg-1"), boom) == [{"key": k["id"], "ok": False, "why": "transport_failed"}]


def test_a_signal_that_fires_tells_the_webhooks(env, monkeypatch):
    _, eg, _ = env
    told = []
    monkeypatch.setattr(A, "announce", lambda plane, c: told.append(c["id"]))
    SG._announce(eg, card("sg-9"))
    assert told == ["sg-9"]
    monkeypatch.setattr(A, "announce", lambda plane, c: 1 / 0)
    SG._announce(eg, card("sg-9"))  # a broken hook never stops a signal


# ---- the schema -------------------------------------------------------------------------------------------------------------------------

def test_openapi_schema_lists_the_public_routes_only(env):
    app, _, _ = env
    r = TestClient(app).get(f"{BASE}/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert set(spec["paths"]) == {f"{BASE}/figures", f"{BASE}/figures/{{figure_id}}", f"{BASE}/ask", f"{BASE}/signals", f"{BASE}/documents"}
    assert "post" in spec["paths"][f"{BASE}/ask"] and all(set(v) == {"get"} for p, v in spec["paths"].items() if p != f"{BASE}/ask")
    assert "HTTPBearer" in spec["components"]["securitySchemes"] and "api-keys" not in json.dumps(spec)


def test_the_public_routes_are_declared_and_the_admin_ones_are_not_open(env):
    app, _, _ = env
    perms = app.state.route_permissions.routes
    for k in [f"GET {BASE}/figures", f"POST {BASE}/ask", f"GET {BASE}/documents"]:
        assert perms[k].public
    assert perms["POST /api/v3/api-keys"].roles == {"company_admin"} and not perms["POST /api/v3/api-keys"].public
