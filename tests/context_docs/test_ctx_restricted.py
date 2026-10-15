"""CRITIC-M1 defect 7: a quote is cut at sentence boundaries, carries no figure the guard would garble, and a
restricted (pay, HR) document is never read by an agent."""
from ctx_const import FAMILY
from ctx_seed import seed
from sh_platform.context_docs import context_passages, retrieval
from sh_platform.context_docs.store import DocStore
from sh_platform.plane import PlaneStore
from test_ctx_routes import BASE, csrf, upload


def test_a_passage_is_cut_at_sentence_boundaries_never_mid_word():
    torn = ("ing is how far a fund is ahead of its benchmark. The committee approves the benchmark once a year. "
            "A manager behind its benchmark for two reviews goes on a watch list. It is a fund or ch")
    out = retrieval.whole_sentences(torn)
    assert out.startswith("The committee") and out.endswith("watch list.")
    assert "or ch" not in out and "ahead of" not in out


def test_a_sentence_with_a_figure_the_guard_would_replace_is_dropped_not_garbled():
    text = "The seat has been vacant for 7 months. Its share is not paid out. The committee decides the benchmark each year."
    out = retrieval.whole_sentences(text)
    assert "7" not in out and "Its share is not paid out." in out and "benchmark each year." in out
    assert "7 months" in retrieval.whole_sentences(text, "Is it really 7 months?")  # the person's own figure stays


def test_a_restricted_document_is_never_returned_whatever_the_question(plane):
    s = DocStore(plane)
    s.upload("north", "a", "bonus.md", b"The bonus pool rewards excess return against the benchmark. The Head of Investments approves the bonus.",
             restricted=True)
    s.upload("north", "a", "policy.md", b"The committee reviews each benchmark once a year. The committee approves the benchmark.")
    assert s.own_chunks("north") and all("bonus" not in c["text"].lower() for c in s.own_chunks("north"))
    out = context_passages(plane, "north", "who approves the bonus and the benchmark")
    assert "bonus" not in out.lower() and "committee" in out
    doc = next(d for d in s.documents("north") if d["filename"] == "bonus.md")
    assert doc["restricted"] is True
    s.set_restricted("north", doc["doc_id"], False)
    assert "bonus" in context_passages(plane, "north", "who approves the bonus").lower()
    s.set_restricted("north", doc["doc_id"], True)
    assert "bonus" not in context_passages(plane, "north", "who approves the bonus").lower()


def test_the_admin_can_restrict_a_document_on_upload_and_later(env):
    admin = env.login("company_admin")
    doc = upload(admin, title="Pay workbook").json()
    assert doc["restricted"] is False
    r = admin.post(f"{BASE}/{doc['doc_id']}/visibility", json={"restricted": True}, headers=csrf(admin))
    assert r.status_code == 200 and r.json()["restricted"] is True
    assert {d["doc_id"]: d["restricted"] for d in admin.get(BASE).json()["documents"]}[doc["doc_id"]] is True
    assert admin.post(f"{BASE}/{doc['doc_id']}/visibility", json={}, headers=csrf(admin)).status_code == 422  # neither field
    assert upload(admin, name="pay.md", data=b"Pay bands are reviewed each year.", restricted=True).json()["restricted"] is True


def test_the_seed_marks_the_bonus_policy_restricted_and_north_never_quotes_it(seeded):
    root, _ = seeded
    plane = PlaneStore(root).plane_for(FAMILY)
    docs = {d["filename"]: d for d in DocStore(plane).documents("north")}
    assert docs["14_bonus_policy_extract.md"]["restricted"] is True
    assert docs["02_investment_policy.md"]["restricted"] is False
    assert seed.is_restricted("pay_workbook.xlsx") and not seed.is_restricted("manager_list.md")
    out = context_passages(plane, "north", "who approves the bonus pool and the benchmark for each manager review")
    assert "bonus pool" not in out.lower() and "Compensation Policy" not in out
