"""Company context routes over the real app and the seeded synthetic companies: roles, CSRF, default deny, isolation,
size cap and refusals."""
import base64

import pytest

import ctx_files as F
from ctx_const import FAMILY, OTHER
from sh_platform.auth.permissions import load_permissions
from sh_platform.context_docs import api, reader
from sh_platform.context_docs.store import DocStore
from sh_platform.plane import PlaneStore

BASE = "/api/agents/north/docs"


def csrf(c):
    return {"X-CSRF-Token": c.cookies["sh_csrf"]}


def body(name: str, data: bytes, **extra) -> dict:
    return {"filename": name, "data": base64.b64encode(data).decode(), **extra}


def upload(c, name="investment-policy.md", data=F.POLICY, **extra):
    return c.post(BASE, json=body(name, data, **extra), headers=csrf(c))


def test_every_route_is_declared_with_the_right_roles():
    perms = load_permissions()
    admin_only = ["POST /api/agents/{slug}/docs", "POST /api/agents/{slug}/docs/{doc_id}/visibility",
                  "POST /api/agents/{slug}/docs/{doc_id}/publish-summary", "DELETE /api/agents/{slug}/docs/{doc_id}",
                  "GET /api/agents/{slug}/pending-memories", "POST /api/agents/{slug}/pending-memories/{pending_id}/decide"]
    for key in admin_only:
        assert perms.routes[key].roles == {"company_admin"} and not perms.routes[key].public and not perms.routes[key].guest
    listing = perms.routes["GET /api/agents/{slug}/docs"]
    assert "company_admin" in listing.roles and "participant" in listing.roles and "super_admin" not in listing.roles
    assert not listing.public and not listing.guest


def test_the_company_admin_uploads_lists_and_deletes(env):
    admin = env.login("company_admin")
    r = upload(admin, title="Investment policy", description="Target allocation", visibility="shared")
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "ready" and doc["title"] == "Investment policy" and "chunks" not in doc
    listed = admin.get(BASE).json()
    assert [d["doc_id"] for d in listed["documents"]] == [doc["doc_id"]]
    assert "docx" in listed["accepted"] and "png" not in listed["accepted"] and listed["max_mb"] == 15
    assert admin.delete(f"{BASE}/{doc['doc_id']}", headers=csrf(admin)).json() == {"deleted": True}
    assert admin.get(BASE).json()["documents"] == []
    assert admin.delete(f"{BASE}/{doc['doc_id']}", headers=csrf(admin)).status_code == 404


def test_the_document_lands_in_the_company_plane_and_nowhere_else(env):
    admin = env.login("company_admin")
    doc = upload(admin).json()
    own = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    assert [d["doc_id"] for d in DocStore(own).documents("north")] == [doc["doc_id"]]
    other = PlaneStore(env.app.state.settings.data_root).plane_for(OTHER)
    assert DocStore(other).documents("north") == []


def test_other_company_members_can_list_but_not_change(env):
    admin = env.login("company_admin")
    doc = upload(admin).json()
    for role in ("sponsor", "analyst", "participant", "approver", "owner"):
        c = env.login(role)
        assert [d["doc_id"] for d in c.get(BASE).json()["documents"]] == [doc["doc_id"]]
        assert upload(c).status_code == 403
        assert c.delete(f"{BASE}/{doc['doc_id']}", headers=csrf(c)).status_code == 403
        assert c.post(f"{BASE}/{doc['doc_id']}/publish-summary", json={"summary": "x"}, headers=csrf(c)).status_code == 403
        assert c.post(f"{BASE}/{doc['doc_id']}/visibility", json={"visibility": "shared"}, headers=csrf(c)).status_code == 403
        assert c.get("/api/agents/north/pending-memories").status_code == 403
        assert c.post("/api/agents/north/pending-memories/1/decide", json={"decision": "accept"}, headers=csrf(c)).status_code == 403
    assert len(admin.get(BASE).json()["documents"]) == 1  # nothing was changed


def test_a_signed_out_person_and_a_super_admin_are_refused(env):
    from fastapi.testclient import TestClient
    anon = TestClient(env.app)
    assert anon.get(BASE).status_code == 401
    assert anon.post(BASE, json=body("a.md", F.POLICY)).status_code in (401, 403)
    platform = TestClient(env.app)
    email = "platform@example.test"
    r = platform.post("/api/auth/login", json={"email": email, "password": env._passwords[email]})
    assert r.status_code == 200
    assert platform.get(BASE).status_code == 403  # a super admin has no company and does not act for one
    assert platform.post(BASE, json=body("a.md", F.POLICY), headers=csrf(platform)).status_code == 403


def test_a_change_without_the_csrf_token_is_refused(env):
    admin = env.login("company_admin")
    assert admin.post(BASE, json=body("a.md", F.POLICY)).status_code == 403
    assert admin.get(BASE).json()["documents"] == []


def test_a_company_never_sees_or_deletes_another_companys_document(env):
    family = env.login("company_admin", FAMILY)
    doc = upload(family).json()
    other = env.login("company_admin", OTHER)
    assert other.get(BASE).json()["documents"] == []
    assert other.delete(f"{BASE}/{doc['doc_id']}", headers=csrf(other)).status_code == 404
    assert other.post(f"{BASE}/{doc['doc_id']}/publish-summary", json={"summary": "x"}, headers=csrf(other)).status_code == 404
    assert len(family.get(BASE).json()["documents"]) == 1


def test_an_unknown_agent_and_a_bad_document_id_are_not_found(env):
    admin = env.login("company_admin")
    assert admin.get("/api/agents/nobody/docs").status_code == 404
    assert admin.delete(f"{BASE}/..%2F..%2Fx", headers=csrf(admin)).status_code in (404, 405)
    assert admin.delete(f"{BASE}/zzzzzzzzzzzz", headers=csrf(admin)).status_code == 404


def test_pictures_and_pdfs_are_refused_in_plain_words(env, monkeypatch):
    admin = env.login("company_admin")
    r = upload(admin, "diagram.png", b"\x89PNG")
    assert r.status_code == 422 and "picture reader" in r.json()["message"]
    monkeypatch.setattr(reader, "pdf_reader_available", lambda: False)
    r = upload(admin, "policy.pdf", b"%PDF-1.4")
    assert r.status_code == 422 and "cannot be read on this machine yet" in r.json()["message"]
    assert upload(admin, "virus.exe", b"MZ").status_code == 422
    assert admin.get(BASE).json()["documents"] == []


def test_the_size_cap_is_enforced_at_the_route(env, monkeypatch):
    admin = env.login("company_admin")
    monkeypatch.setattr(reader, "MAX_UPLOAD_BYTES", 1000)
    monkeypatch.setattr(api, "MAX_BODY", 2000)
    r = upload(admin, "big.txt", b"x" * 1500)  # decoded size over the cap
    assert r.status_code == 413
    r = upload(admin, "huge.txt", b"x" * 5000)  # the body itself is over the cap: refused before it is read
    assert r.status_code == 413 and "too large" in r.json()["message"]
    assert admin.get(BASE).json()["documents"] == []


def test_a_chunked_upload_without_content_length_over_the_cap_is_413(env, monkeypatch):
    admin = env.login("company_admin")
    monkeypatch.setattr(api, "MAX_BODY", 2000)

    def chunks():
        for _ in range(10):
            yield b"x" * 1000

    r = admin.post(BASE, content=chunks(), headers={**csrf(admin), "Content-Type": "application/json"})
    assert r.status_code == 413 and "content-length" not in r.request.headers
    assert admin.get(BASE).json()["documents"] == []


def test_a_broken_body_is_a_plain_400(env):
    admin = env.login("company_admin")
    assert admin.post(BASE, content=b"not json", headers={**csrf(admin), "Content-Type": "application/json"}).status_code == 400
    assert admin.post(BASE, json={"filename": "a.md", "data": "***not base64***"}, headers=csrf(admin)).status_code == 400
    assert admin.post(BASE, json={"filename": "a.md", "data": ""}, headers=csrf(admin)).status_code == 422  # empty file


def test_publish_summary_visibility_and_pending_memories_through_the_routes(env):
    admin = env.login("company_admin")
    doc = upload(admin).json()
    r = admin.post(f"{BASE}/{doc['doc_id']}/publish-summary", json={"summary": "The family targets growth."}, headers=csrf(admin))
    assert r.status_code == 200 and r.json()["shared_summary"] == "The family targets growth." and r.json()["visibility"] == "shared"
    r = admin.post(f"{BASE}/{doc['doc_id']}/visibility", json={"visibility": "private"}, headers=csrf(admin))
    assert r.json()["visibility"] == "private"
    assert admin.post(f"{BASE}/{doc['doc_id']}/publish-summary", json={"summary": " "}, headers=csrf(admin)).status_code == 422

    own = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    pid = DocStore(own).stage_pending("north", "fact", "Reserve", "A reserve of six months.", "conversation")
    pending = admin.get("/api/agents/north/pending-memories").json()["pending"]
    assert [p["pending_id"] for p in pending] == [pid]
    r = admin.post(f"/api/agents/north/pending-memories/{pid}/decide", json={"decision": "accept", "content": "A reserve of nine months."}, headers=csrf(admin))
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["content"] == "A reserve of nine months."
    assert admin.post(f"/api/agents/north/pending-memories/{pid}/decide", json={"decision": "reject"}, headers=csrf(admin)).status_code == 409


def test_a_restricted_document_is_listed_only_to_the_company_admin(env):
    """CRITIC-M2 round 4, defect 5: no title, filename or uploader id of a pay or HR document reaches anyone else."""
    admin = env.login("company_admin")
    plain = upload(admin, name="policy.md", title="Investment policy").json()
    pay = upload(admin, name="bonus.md", data=b"The bonus pool is approved each year.", title="Bonus policy extract", restricted=True).json()
    assert {d["doc_id"] for d in admin.get(BASE).json()["documents"]} == {plain["doc_id"], pay["doc_id"]}
    for role in ("sponsor", "analyst", "participant", "approver", "owner"):
        r = env.login(role).get(BASE)
        assert [d["doc_id"] for d in r.json()["documents"]] == [plain["doc_id"]]
        assert "bonus" not in r.text.lower() and pay["doc_id"] not in r.text
