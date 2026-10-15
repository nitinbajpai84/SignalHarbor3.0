"""M2-AGENTS: the pre-read checklist ("Give Lens what you already have") and Nira, the guide, in module 2."""
import json

from m2_kit import BASE, login
from test_m2_lens import Stub, with_doc
from test_m2_lens_first_move import lens_url, model
from test_m2_worklist import confirm, kpi_url, seed_charter, start

from sh_platform.context_docs.store import DocStore


def pre(v, tail=""):
    return f"{BASE}/baselines/{v['baseline']['id']}/preread{tail}"


def nira(c, v, **body):
    return c.post(f"{BASE}/baselines/{v['baseline']['id']}/nira", json=body)


# ---- the pre-read checklist is a view over the company's own documents

def test_the_checklist_lists_the_kinds_and_tags_the_companys_own_documents(world):
    with_doc(world)
    c = login(world, "co-a")
    v = start(c, seed_charter(world))
    got = c.get(pre(v)).json()
    assert [k["key"] for k in got["kinds"]][:2] == ["glossary", "definitions"] and len(got["kinds"]) == 6
    doc = got["documents"][0]
    assert doc["title"] == "Funding calls note" and got["can_upload"] is True
    after = c.put(pre(v, "/glossary"), json={"docs": [doc["doc_id"]]}).json()
    assert after["kinds"][0]["docs"] == [{"doc_id": doc["doc_id"], "title": "Funding calls note"}]
    after = c.put(pre(v, "/definitions"), json={"none": True}).json()
    assert after["kinds"][1]["none"] is True and after["kinds"][1]["docs"] == []
    assert c.put(pre(v, "/glossary"), json={"docs": ["f" * 12]}).status_code == 400  # not on file
    assert c.put(pre(v, "/nothing"), json={}).status_code == 404


def test_a_restricted_document_is_not_offered_to_someone_who_may_not_see_it(world):
    DocStore(world.plane("co-a")).upload("lens", "a", "pay.md", b"Pay bands by grade.", title="Pay bands", restricted=True)
    admin, other = login(world, "co-a"), login(world, "co-a", "Rae Other", ("analyst",))
    v = start(admin, seed_charter(world))
    assert [d["title"] for d in admin.get(pre(v)).json()["documents"]] == ["Pay bands"]
    seen = other.get(pre(v)).json()
    assert seen["documents"] == [] and seen["can_upload"] is False and "Pay bands" not in json.dumps(seen)


def test_nothing_uploaded_and_no_pack_lens_says_so_and_falls_back_to_asking(world):
    c = login(world, "co-none")
    v = start(c, seed_charter(world, "co-none"))
    assert c.get(pre(v)).json()["pack"]["available"] is False
    did = c.get(lens_url(v)).json()["say"]["did"]
    assert "no industry knowledge" in did and "no documents" in did and "ask you" in did


# ---- Nira in module 2

def test_nira_says_where_you_are_and_what_is_next_from_the_state(world):
    c = login(world, "co-a")
    v = start(c, seed_charter(world))
    r = nira(c, v, kind="welcome", step="baselines").json()
    assert r["name"] == "Nira" and r["role"] == "the guide" and "step 1 of 5" in r["text"] and "Confirm the measures" in r["text"]
    v = confirm(c, v, name="Calls due, by date")
    assert "Name the business, data and process owner" in nira(c, v, kind="now", step="baselines").json()["text"]
    assert "step 3 of 5" in nira(c, v, kind="welcome", step="process-map").json()["text"]


def test_nira_facts_match_the_baselines_state_and_name_who_has_not_answered(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), name="Calls due, by date")
    kid = v["kpis"][0]["id"]
    for role in ("business", "data", "process"):
        c.put(kpi_url(v, kid, "/owners"), json={role: {"name": "Mei Tan"}})
    c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Unpaid notices", "mark": "stated"}})
    s = c.post(f"{BASE}/baselines/{v['baseline']['id']}/requests", json={})
    assert s.status_code in (200, 201), s.text
    facts = nira(c, v, kind="welcome", step="requests").json()
    f = facts["facts"]
    assert "1 measures are on the work list; 1 have all three owners named; 1 have a definition" in f
    assert "1 requests to owners have been sent; 0 are answered" in f and "Still waiting for an answer from: Mei Tan" in f
    assert "Mei Tan" in facts["text"]


def test_nira_answers_a_question_from_the_facts_with_the_model_and_says_when_it_has_none(world):
    stub = Stub("You are on the work list.")
    model(world, stub)
    c = login(world, "co-a")
    v = start(c, seed_charter(world))
    r = nira(c, v, kind="ask", step="baselines", question="Where am I?").json()
    assert r["text"] == "You are on the work list." and r["available"] is True
    ctx = json.loads(stub.sent[0][1]["content"])["context"]
    assert "step 1: the work list" in ctx["session_facts"] and "suggestions" in ctx
    model(world, None)
    r = nira(c, v, kind="ask", step="baselines", question="Where am I?").json()
    assert r["available"] is False and "no model" in r["text"]
    assert nira(c, v, kind="ask", question=" ").status_code == 400
    assert nira(c, v, kind="dance").status_code == 422


def test_nira_does_not_count_or_name_what_the_asker_may_not_see(world):
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0")
    admin.put(kpi_url(v, "K0", "/owners"), json={"business": {"name": "Mei Tan"}})
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "yes", "may_see": ["Test Wei Lim"]})
    outsider = login(world, "co-a", "Sam Outsider", ("analyst",))
    f = nira(outsider, v, kind="welcome").json()["facts"]
    assert "0 measures are on the work list" in f and "Mei Tan" not in f
    assert "1 measures are on the work list" in nira(admin, v, kind="welcome").json()["facts"]


def test_the_conversations_still_work_when_the_baseline_is_signed(world):
    c = login(world, "co-a")
    v = start(c, seed_charter(world))
    path = world.plane("co-a").path("intents", "m2_baseline", v["baseline"]["id"], "baseline.json")
    path.write_text(json.dumps({**v["baseline"], "state": "signed"}))
    r = nira(c, v, kind="now").json()
    assert "read-only" in r["text"]
