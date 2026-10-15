"""IC-5a control panel routes. Synthetic ids only; no industry wording."""
import json

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.egress.policy import EgressPolicy
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings


class World:
    def __init__(self, tmp_path):
        self.root = tmp_path / "data"
        self.app = create_app(Settings(mode="dev", data_root=str(self.root), session_secret="fake-test-secret-not-real"),
                              dist_dir=tmp_path / "dist")
        self.es, self.accounts = self.app.state.entitlements, self.app.state.account_store
        self.es.create_company("co-a", "Company A", "industry_a", package="build")
        self.es.create_company("co-b", "Company B", "industry_b", package="discover")
        self.es.create_company("co-empty", "Company Empty", "industry_a")

    def login(self, name, company, role):
        acct, pw = make_test_account(self.accounts, name, company, [role])
        c = TestClient(self.app)
        assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
        c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
        return c

    def plane(self, company):
        return PlaneStore(self.root).plane_for(company)


@pytest.fixture
def w(tmp_path):
    return World(tmp_path)


@pytest.fixture
def sa(w):
    return w.login("sa", None, "super_admin")


@pytest.fixture
def ca(w):
    return w.login("ca-a", "co-a", "company_admin")


CONTROL = [("get", "/api/control/companies"), ("get", "/api/control/catalogue"), ("get", "/api/control/providers"),
           ("post", "/api/control/companies"), ("put", "/api/control/providers"),
           ("put", "/api/control/companies/co-a/centres/intent"), ("put", "/api/control/companies/co-a/modules/m1_intent")]
COMPANY = [("get", "/api/company/settings"), ("put", "/api/company/settings/egress"), ("get", "/api/company/egress-log")]


@pytest.mark.parametrize("who", ["participant", "company_admin", "sponsor"])
@pytest.mark.parametrize("method,path", CONTROL)
def test_control_routes_are_super_admin_only(w, who, method, path):
    c = w.login(who, "co-a", who)
    assert getattr(c, method)(path, **({"json": {}} if method != "get" else {})).status_code == 403


@pytest.mark.parametrize("method,path", COMPANY)
def test_company_routes_refuse_participant_and_super_admin(w, sa, method, path):
    assert getattr(sa, method)(path, **({"json": {}} if method != "get" else {})).status_code == 403
    assert getattr(w.login("p", "co-a", "participant"), method)(path, **({"json": {}} if method != "get" else {})).status_code == 403


def test_anonymous_refused(w):
    c = TestClient(w.app)
    assert c.get("/api/control/companies").status_code in (401, 403)
    assert c.get("/api/company/settings").status_code in (401, 403)


def test_company_admin_on_another_company_is_404(ca):
    assert ca.get("/api/company/settings?company_id=co-b").status_code == 404
    assert ca.get("/api/company/egress-log?company_id=co-b").status_code == 404
    assert ca.put("/api/company/settings/egress?company_id=co-b", json={"internet": True}).status_code == 404
    assert ca.get("/api/company/settings?company_id=co-a").status_code == 200


def test_list_companies_has_counts_and_no_plane_content(w, sa):
    w.login("pp", "co-a", "participant")
    (w.plane("co-a").area("context") / "secret.txt").write_text("PLANE-CONTENT", encoding="utf-8")
    r = sa.get("/api/control/companies")
    rows = {c["id"]: c for c in r.json()["companies"]}
    assert rows["co-a"]["display"] == "Company A" and rows["co-a"]["industry"] == "industry_a"
    assert rows["co-a"]["modules_on"] == ["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight"]
    assert rows["co-a"]["centres_on"] == ["intent", "build", "consume"]
    assert rows["co-a"]["accounts"] == {"total": 1, "active": 1}
    assert rows["co-a"]["email_domains"] == []
    assert rows["co-b"]["modules_on"] == ["m1_intent", "m2_baseline", "m3_connect"]
    assert rows["co-empty"]["modules_on"] == [] and rows["co-empty"]["accounts"] == {"total": 0, "active": 0}
    assert "PLANE-CONTENT" not in r.text and "password" not in r.text


def test_create_company_then_duplicate_and_invalid(w, sa):
    r = sa.post("/api/control/companies", json={"id": "co-new", "display": "New Co", "industry": "industry_c"})
    assert r.status_code == 201 and r.json()["id"] == "co-new"
    assert w.plane("co-new")  # plane exists, empty
    assert sa.post("/api/control/companies", json={"id": "co-new", "display": "x", "industry": "y"}).status_code == 409
    for bad in ({}, {"id": "../x", "display": "x", "industry": "y"}, {"id": "_control", "display": "x", "industry": "y"},
                {"id": "co-z", "display": 5, "industry": "y"}, {"id": "co-z", "display": "x", "industry": "a/b"},
                {"id": "co-z", "display": "", "industry": "y"}):
        assert sa.post("/api/control/companies", json=bad).status_code == 400, bad
    assert sa.post("/api/control/companies", content="not json", headers={"content-type": "application/json"}).status_code == 400
    assert not (w.root / "co-z").exists()


def test_centre_switch_takes_effect_next_request(w, sa):
    ca = w.login("ca-a", "co-a", "company_admin")
    assert ca.get("/api/modules").json()
    assert sa.put("/api/control/companies/co-a/centres/intent", json={"on": False}).status_code == 200
    assert w.es.is_enabled("co-a", "m1_intent") is False
    assert ca.get("/api/modules/m1_intent/sessions").status_code == 403  # module gate, next request
    assert w.es.is_enabled("co-b", "m1_intent") is True  # other company untouched
    assert sa.put("/api/control/companies/co-a/centres/intent", json={"on": True}).status_code == 200
    assert w.es.is_enabled("co-a", "m1_intent") is True


def test_module_switch_and_write_validation(w, sa):
    assert sa.put("/api/control/companies/co-empty/modules/m1_intent", json={"on": True}).status_code == 200
    assert w.es.is_enabled("co-empty", "m1_intent")
    for path, body, code in [("/api/control/companies/co-a/modules/nope", {"on": True}, 404),
                             ("/api/control/companies/co-a/centres/nope", {"on": True}, 404),
                             ("/api/control/companies/ghost/modules/m1_intent", {"on": True}, 404),
                             ("/api/control/companies/co-a/modules/m1_intent", {"on": "yes"}, 400),
                             ("/api/control/companies/co-a/modules/m1_intent", {"on": 1}, 400),
                             ("/api/control/companies/co-a/centres/intent", {}, 400)]:
        assert sa.put(path, json=body).status_code == code, (path, body)
    assert w.es.is_enabled("co-a", "m1_intent")  # nothing changed


def test_catalogue(sa):
    j = sa.get("/api/control/catalogue").json()
    assert j["centres"][0]["id"] == "intent" and len(j["modules"]) == 6


def test_providers_fixed_list_validated_and_no_key(w, sa):
    allowed = sa.get("/api/control/providers").json()["allowed"]
    prov = next(iter(allowed))
    model = allowed[prov][0]
    ok = {"company_id": "co-a", "provider": prov, "model": model}
    assert sa.put("/api/control/providers", json=ok).status_code == 200
    got = sa.get("/api/control/providers").json()["companies"]
    assert got["co-a"] == {"provider": prov, "model": model} and got["co-b"] is None
    for bad in ({**ok, "model": "other"}, {**ok, "provider": "x"}, {"company_id": "co-a", "provider": prov},
                {**ok, "provider": 1, "model": 2}):
        assert sa.put("/api/control/providers", json=bad).status_code == 400
    assert sa.put("/api/control/providers", json={**ok, "company_id": "ghost"}).status_code == 404
    assert "key" not in json.dumps(got).lower()


def test_egress_defaults_off_and_internet_toggle_drives_policy(w, ca):
    s = ca.get("/api/company/settings").json()
    assert s["egress"] == {"internet": False, "connectors": False, "cloud_push": False, "cloud_push_requested": False}
    assert s["centres"] == ["intent", "build", "consume"]
    assert EgressPolicy(w.plane("co-a")).is_internet_allowed("m1_intent") is False
    assert ca.put("/api/company/settings/egress", json={"internet": True}).json()["egress"]["internet"] is True
    assert EgressPolicy(w.plane("co-a")).is_internet_allowed("m1_intent")  # fresh read: no cache
    assert EgressPolicy(w.plane("co-b")).is_internet_allowed("m1_intent") is False  # isolated
    ca.put("/api/company/settings/egress", json={"internet": False})
    assert EgressPolicy(w.plane("co-a")).is_internet_allowed("m1_intent") is False


def test_internet_on_then_off_with_allowlisted_host(w, ca):
    EgressPolicy(w.plane("co-a")).set_internet_hosts(["example.org"])
    ca.put("/api/company/settings/egress", json={"internet": True})
    p = EgressPolicy(w.plane("co-a"))
    assert p.is_internet_allowed("m2_baseline") and p.internet_hosts() == ["example.org"]
    ca.put("/api/company/settings/egress", json={"internet": False})
    assert EgressPolicy(w.plane("co-a")).is_internet_allowed("m2_baseline") is False


def test_cloud_push_is_stored_as_requested_never_on(w, ca):
    e = ca.put("/api/company/settings/egress", json={"cloud_push": True, "connectors": True}).json()["egress"]
    assert e["cloud_push"] is False and e["cloud_push_requested"] is True and e["connectors"] is True
    assert ca.get("/api/company/settings").json()["egress"]["cloud_push_requested"] is True


def test_egress_write_fails_closed_on_bad_values(w, ca):
    for bad in ({}, {"internet": "true"}, {"internet": 1}, {"internet": None}, {"other": True},
                {"internet": True, "other": False}, [True]):
        assert ca.put("/api/company/settings/egress", json=bad).status_code == 400, bad
    assert ca.get("/api/company/settings").json()["egress"]["internet"] is False  # a partly valid body changed nothing
    assert ca.put("/api/company/settings/egress", content="x", headers={"content-type": "text/plain"}).status_code == 415


def _log(w, company, n, payload_word="PAYLOAD-TEXT"):
    path = w.plane(company).area("context") / "egress_log.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"attempt": "a", "time": f"2026-10-06T10:{i % 60:02d}:00", "module": "m1_intent",
                                "kind": "model", "host": f"h{i}.example.org", "decision": "sent", "reason_code": "",
                                "bytes": i, "sha256": "ab" * 32, "payload": payload_word, "trace_id": f"tr-{i}"}) + "\n")
        f.write("not json\n")


def test_egress_log_never_payload_or_hash_and_capped(w, ca):
    _log(w, "co-a", 250)
    r = ca.get("/api/company/egress-log?limit=1000")
    es = r.json()["entries"]
    assert len(es) == 200 and es[0]["host"] == "h249.example.org"  # newest first
    assert set(es[0]) == {"time", "module", "kind", "host", "decision", "reason_code", "bytes", "trace_id", "masked"}  # TS1c-05: masked is a count
    assert es[0]["trace_id"] == "tr-249"  # AQF10-05: the line ties to the answer's trace (an id, never content)
    assert "PAYLOAD-TEXT" not in r.text and "abab" not in r.text
    assert len(ca.get("/api/company/egress-log?limit=3").json()["entries"]) == 3
    assert len(ca.get("/api/company/egress-log?limit=0").json()["entries"]) == 1


def test_two_companies_isolated_and_empty_company(w):
    _log(w, "co-a", 2, "A-ONLY")
    _log(w, "co-b", 1, "B-ONLY")
    a, b = w.login("ca-a", "co-a", "company_admin"), w.login("ca-b", "co-b", "company_admin")
    assert len(a.get("/api/company/egress-log").json()["entries"]) == 2
    assert len(b.get("/api/company/egress-log").json()["entries"]) == 1
    a.put("/api/company/settings/egress", json={"connectors": True})
    assert b.get("/api/company/settings").json()["egress"]["connectors"] is False
    e = w.login("ca-e", "co-empty", "company_admin")
    assert e.get("/api/company/egress-log").json() == {"entries": []}
    assert e.get("/api/company/settings").json()["egress"]["internet"] is False  # nothing owned, still answers


def test_internet_toggle_skips_modules_that_are_off(w, ca):
    w.es.set_module("co-a", "m5_foresight", False)
    ca.put("/api/company/settings/egress", json={"internet": True})
    p = EgressPolicy(w.plane("co-a"))
    assert p.is_internet_allowed("m1_intent") and p.is_internet_allowed("m5_foresight") is False
    assert ca.get("/api/company/settings").json()["egress"]["internet"] is True


def test_email_domains_stored_listed_and_validated(w, ca):
    assert ca.get("/api/company/settings").json()["email_domains"] == []
    r = ca.put("/api/company/settings/egress", json={"email_domains": ["Example.com", "b.org", "b.org"]})
    assert r.json()["email_domains"] == ["b.org", "example.com"]
    from sh_platform.egress.email import allowed_domains
    assert allowed_domains(w.plane("co-a")) == {"b.org", "example.com"}
    for bad in ({"email_domains": ["no spaces.com"]}, {"email_domains": "a.com"}, {"email_domains": [1]}):
        assert ca.put("/api/company/settings/egress", json=bad).status_code == 400
    assert ca.put("/api/company/settings/egress", json={"email_domains": []}).json()["email_domains"] == []


def test_a_role_refusal_says_who_can_act(w, ca):  # SP-C1-03: the guard names the roles and the colleagues who hold them
    r = w.login("p-a", "co-a", "participant").get("/api/company/egress-log")
    assert r.status_code == 403 and r.headers.get("x-refused-by") == "access"
    msg = r.json()["message"]
    assert r.json()["error"] == "forbidden" and msg.startswith("Only the company administrator can do this; ") and "ca-a" in msg
