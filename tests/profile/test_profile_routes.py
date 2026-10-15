"""The profile routes: who may use them, the viewer's filtered view, upload, re-read, readiness with asks, and company separation."""
import base64

from pf_kit import FAMILY, GOV, OTHER, PACK, PEOPLE, SYSTEMS
from sh_platform.plane import PlaneStore


def put(c, gid, name, data, **extra):
    return c.post(f"/api/profile/inputs/{gid}/upload", json={"filename": name, "data": base64.b64encode(data).decode(), **extra})


def test_only_the_organiser_roles_reach_the_profile(env):
    for role in ("participant", "approver", "owner"):
        c = env.login(role)
        assert c.get("/api/profile").status_code == 403
        assert c.get("/api/profile/readiness").status_code == 403
        assert c.post("/api/profile/read").status_code == 403
        assert put(c, 1, "p.csv", PEOPLE).status_code == 403
    for role in ("company_admin", "sponsor", "analyst"):
        assert env.login(role).get("/api/profile").status_code == 200


def test_upload_read_and_readiness_end_to_end(env):
    admin = env.login("company_admin")
    assert admin.get("/api/profile/readiness").json()["percent"] == 0
    r = put(admin, 1, "people.csv", PEOPLE)
    assert r.status_code == 200 and r.json()["state"] == "read"
    assert put(admin, 3, "pack.csv", PACK).json()["state"] == "read"
    assert put(admin, 6, "systems.csv", SYSTEMS).status_code == 200
    ready = admin.get("/api/profile/readiness").json()
    assert ready["percent"] == 40 and ready["sentence"] == "Lens can draft about 40% of the baseline."
    assert {a["group"] for a in ready["asks"]} == {2, 7, 8} and all(a["holder"] for a in ready["asks"])
    again = admin.post("/api/profile/read").json()
    assert [x["state"] for x in again["results"]] == ["read", "read", "read"]
    assert set(admin.get("/api/profile").json()["people"]) == {"mei-tan", "sue-sponsor", "dan-data"}
    assert env.stub.sent == []


def test_a_bad_group_file_or_body_gets_a_plain_refusal(env):
    admin = env.login("company_admin")
    assert put(admin, 12, "x.csv", PEOPLE).status_code == 404
    assert put(admin, 8, "notes.md", b"free text").status_code == 422 or put(admin, 8, "notes.md", b"free text").status_code == 400
    assert admin.post("/api/profile/inputs/1/upload", json={"filename": "p.csv", "data": "***"}).status_code == 400


def test_the_ask_route_gives_text_to_copy_with_a_link_and_sends_nothing(env):
    admin = env.login("company_admin")
    put(admin, 1, "people.csv", PEOPLE)
    out = admin.post("/api/profile/inputs/3/ask").json()
    assert out["holder"]["name"] == "Mei Tan" and out["email"]["link"].startswith("/company/bring?ask=pf-")
    assert out["email"]["link"] in out["email"]["body"] and "{link}" not in out["email"]["body"]


def test_the_viewer_filter_applies_on_the_route(env):
    admin = env.login("company_admin")
    put(admin, 7, "access.csv", GOV)
    put(admin, 1, "people.csv", PEOPLE + b"Ann Hr,Payroll officer,HR,ann@example.test,,\n")
    assert "pay" in admin.get("/api/profile").json()["governance"]["field_rules"]
    analyst = env.login("analyst").get("/api/profile").json()
    assert "pay" not in analyst["governance"]["field_rules"] and "capital-called" in analyst["governance"]["field_rules"]
    assert "hr" not in analyst["governance"]["restricted_areas"] and "ann-hr" not in analyst["people"]  # HR is closed to its unnamed
    assert "ann-hr" not in str(analyst)


def test_another_company_is_unreachable(env):
    a, b = env.login("company_admin", FAMILY), env.login("company_admin", OTHER)
    put(a, 1, "people.csv", PEOPLE)
    assert b.get("/api/profile").json()["people"] == {} and b.get("/api/profile/readiness").json()["percent"] == 0
    other = PlaneStore(env.app.state.settings.data_root).plane_for(OTHER)
    assert not (other.path("context", "profile") / "profile.json").exists()
