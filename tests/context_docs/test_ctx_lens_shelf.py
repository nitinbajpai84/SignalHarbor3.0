"""CTX-LENS: Lens has its own shelf; one rule (documents_for) says who reads what."""
import json

from sh_platform.context_docs import context_passages, documents_for
from sh_platform.context_docs.store import DocStore
from test_ctx_routes import csrf, body

N = b"The north zebra framework governs allocation drift limits for every quarter."
L = b"The lens quokka glossary defines a net revenue figure for every quarter."


def titles(plane, agent, **kw):
    return {d["filename"] for d in documents_for(plane, agent, **kw)}


def put(s, agent, name, data, **kw):
    return s.upload(agent, "a", name, data, **kw)["doc_id"]


def test_private_documents_stay_with_their_agent(plane):
    s = DocStore(plane)
    put(s, "north", "n.md", N)
    put(s, "lens", "l.md", L)
    assert titles(plane, "north") == {"n.md"} and titles(plane, "lens") == {"l.md"}
    assert "quokka" not in context_passages(plane, "north", "quokka glossary net revenue")
    assert "zebra" not in context_passages(plane, "lens", "zebra framework allocation drift")


def test_shared_gives_others_the_summary_only_and_shared_full_the_text(plane):
    s = DocStore(plane)
    nid = put(s, "north", "n.md", N, visibility="shared")
    put(s, "lens", "l.md", L, visibility="shared_full")
    assert titles(plane, "lens") == {"l.md"}  # shared without a summary reaches nobody
    s.publish_summary("north", nid, "North's framework limits drift.")
    lens_view = documents_for(plane, "lens")
    assert next(d for d in lens_view if d["filename"] == "n.md")["chunks"] == []
    assert "zebra" not in context_passages(plane, "lens", "zebra framework allocation drift")
    assert "limits drift" in context_passages(plane, "lens", "framework drift summary")
    assert "quokka" in context_passages(plane, "north", "quokka glossary net revenue")


def test_shared_full_is_never_a_default_and_publishing_keeps_it(plane):
    s = DocStore(plane)
    doc_id = put(s, "north", "n.md", N)
    assert s.get("north", doc_id)["visibility"] == "private"
    s.set_visibility("north", doc_id, "shared_full")
    s.publish_summary("north", doc_id, "x")
    assert s.get("north", doc_id)["visibility"] == "shared_full" and "zebra" in context_passages(plane, "lens", "zebra framework")


def test_restricted_documents_only_with_restricted_ok(plane):
    s = DocStore(plane)
    put(s, "north", "n.md", N, visibility="shared_full", restricted=True)
    put(s, "lens", "l.md", L, visibility="shared_full", restricted=True)
    assert titles(plane, "north") == titles(plane, "lens") == set()
    assert titles(plane, "lens", restricted_ok=True) == {"n.md", "l.md"}


def test_an_old_document_keeps_its_stored_visibility_and_a_missing_one_is_private(plane):
    s = DocStore(plane)
    doc_id = put(s, "north", "old.md", N)
    path = s._file("north", doc_id)
    d = json.loads(path.read_text(encoding="utf-8"))
    del d["visibility"]
    path.write_text(json.dumps(d), encoding="utf-8")
    assert titles(plane, "lens") == set() and "zebra" in context_passages(plane, "north", "zebra framework")
    s.set_visibility("north", doc_id, "shared_full")
    assert titles(plane, "lens") == {"old.md"}


def test_routes_work_for_lens_and_stay_inside_the_company(env):
    from ctx_const import FAMILY, OTHER
    fam, oth = env.login("company_admin", FAMILY), env.login("company_admin", OTHER)
    base = "/api/agents/lens/docs"
    r = fam.post(base, json=body("l.md", L, visibility="shared_full"), headers=csrf(fam))
    assert r.status_code == 200 and r.json()["visibility"] == "shared_full"
    assert len(fam.get(base).json()["documents"]) == 1
    assert oth.get(base).json()["documents"] == [] and oth.get("/api/agents/north/docs").json()["documents"] == []
    assert fam.get("/api/agents/lens/pending-memories").status_code == 200
    assert fam.post(f"{base}/{r.json()['doc_id']}/publish-summary", json={"summary": "s"}, headers=csrf(fam)).status_code == 200
