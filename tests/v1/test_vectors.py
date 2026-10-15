"""V1 meaning search: a stub embedder (no model download) in place of the local model. A synonym query finds the passage word search
misses, the two lists are fused by reciprocal rank, the search falls back to words when the model fails, a changed file is
re-embedded, and vectors are only ever looked at for the paths passed in."""
import logging
import sys
import types

import numpy as np
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import doc_embed
from sh_platform.v1 import doc_index as DI

REAL_EMBED = doc_embed.embed  # the conftest switches the module attribute off during each test
CONCEPTS = [("net worth", "total wealth"), ("custody", "safekeeping"), ("salary", "pay")]


def stub(texts, query=False):
    out = np.zeros((len(texts), len(CONCEPTS) + 1), np.float32)
    for i, t in enumerate(texts):
        low = t.lower()
        for j, words in enumerate(CONCEPTS):
            out[i, j] = any(w in low for w in words)
        out[i, -1] = 0.01
    return out / np.linalg.norm(out, axis=1, keepdims=True)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setattr(doc_embed, "embed", stub)
    monkeypatch.setattr(DI, "_submit", lambda fn, *a: fn(*a))  # background jobs run inline
    monkeypatch.setattr(DI, "_warned", False)
    d = tmp_path / "co" / "documents"
    d.mkdir(parents=True)
    (d / "policy.md").write_text("# Policy\n\nNo issuer may exceed ten percent of net worth at month end.\n", encoding="utf-8")
    (d / "other.md").write_text("# Other\n\nThe auditors review safekeeping arrangements yearly.\n", encoding="utf-8")
    (d / "secret.md").write_text("# Secret\n\nSalary pool and net worth of the chair.\n", encoding="utf-8")
    return PlaneStore(tmp_path).plane_for("co")


P, O, S = "documents/policy.md", "documents/other.md", "documents/secret.md"


def test_synonym_found_by_meaning_only(plane):
    hit = DI.search(plane, [P, O], "total wealth")[0]
    assert hit["path"] == P and hit["how"] == "meaning"  # no word of the query is in the passage


def test_words_and_meaning_agree_is_both_and_fusion_ranks_it_first(plane):
    hits = DI.search(plane, [P, O], "net worth custody")
    assert {h["path"] for h in hits} == {P, O}
    hits = DI.search(plane, [P, O], "safekeeping")
    assert hits[0]["path"] == O and hits[0]["how"] in ("both", "meaning")
    both = DI.search(plane, [P], "net worth")[0]
    assert both["how"] == "both" and set(both) == {"path", "from", "to", "text", "how"}


def test_fusion_order(plane):
    # words rank: O first (only O has 'safekeeping' as a word); meaning rank: P first (net worth). RRF: both lists contribute.
    (plane.path("documents") / "third.md").write_text("# Third\n\nSafekeeping and net worth notes.\n", encoding="utf-8")
    hits = DI.search(plane, [P, O, "documents/third.md"], "safekeeping net worth")
    assert hits[0]["path"] == "documents/third.md" and hits[0]["how"] == "both"  # in both lists, so it beats those in one


def test_fallback_when_the_model_fails(plane, monkeypatch, caplog):
    def boom(texts, query=False):
        raise doc_embed.Unavailable("no model")
    monkeypatch.setattr(doc_embed, "embed", boom)
    with caplog.at_level(logging.WARNING):
        a = DI.search(plane, [P], "net worth")
        b = DI.search(plane, [P], "net worth")
    assert a and a[0]["how"] == "words" and b == a
    assert sum("embedding model is not available" in r.message for r in caplog.records) == 1
    assert DI.search(plane, [P], "total wealth") == []  # no words, no meaning: honest nothing


def test_changed_file_is_re_embedded(plane):
    assert DI.search(plane, [O], "total wealth") == [] or DI.search(plane, [O], "total wealth")[0]["how"] == "meaning"
    f = plane.path("documents", "other.md")
    f.write_text("# Other\n\nThe fund reports total wealth quarterly, with a lot more text so the size differs.\n", encoding="utf-8")
    hit = DI.search(plane, [O], "net worth")[0]
    assert hit["path"] == O and hit["how"] == "meaning"
    con = DI._db(plane)
    assert con.execute("select count(*) from vectors where path=?", (O,)).fetchone()[0] == 1
    con.close()


def test_vectors_never_returned_for_paths_not_passed_in(plane):
    DI.search(plane, [P, O, S], "net worth")  # all three have vectors now
    hits = DI.search(plane, [P], "net worth salary")
    assert {h["path"] for h in hits} == {P}
    assert DI.search(plane, [O], "salary pay") == [] or {h["path"] for h in DI.search(plane, [O], "salary pay")} == {O}


def test_backfill_embeds_old_indexed_files_on_first_search(plane):
    DI.ensure(plane, P)
    con = DI._db(plane)
    with con:
        con.execute("delete from vectors")
        con.execute("delete from vec_files")  # an index made before vectors existed
    con.close()
    DI.search(plane, [P], "total wealth")  # words find nothing and no vectors yet: this search queues the backfill
    assert DI.search(plane, [P], "total wealth")[0]["how"] == "meaning"


# ---- fixes after review ---------------------------------------------------------------------------------------------------------

def fake_fastembed(monkeypatch, tmp_path, fail=False):
    """A fastembed module that counts model loads; the real one is never imported."""
    calls = {"loads": 0, "batches": []}

    class TextEmbedding:
        def __init__(self, *a, **k):
            calls["loads"] += 1
            if fail:
                raise OSError("no route to huggingface.co")

        def embed(self, texts):
            calls["batches"].append(len(texts))
            return [[1.0, 2.0, 3.0]] * len(texts)
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=TextEmbedding))
    monkeypatch.setattr(doc_embed, "CACHE", tmp_path / "models")
    monkeypatch.setattr(doc_embed, "_model", None)
    monkeypatch.setattr(doc_embed, "_failed", None)
    monkeypatch.setattr(doc_embed, "embed", REAL_EMBED)
    return calls


def test_failed_model_load_is_remembered_and_retried_only_after_ten_minutes(monkeypatch, tmp_path):
    calls = fake_fastembed(monkeypatch, tmp_path, fail=True)
    for _ in range(3):
        with pytest.raises(doc_embed.Unavailable):
            doc_embed.embed(["a"])
    assert calls["loads"] == 1  # one attempt, not one per call
    monkeypatch.setattr(doc_embed, "_failed", doc_embed.time.monotonic() - doc_embed.RETRY_AFTER - 1)
    with pytest.raises(doc_embed.Unavailable):
        doc_embed.embed(["a"])
    assert calls["loads"] == 2


def test_embedding_jobs_never_reach_a_pool_under_the_conftest(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(DI._bg, "submit", lambda *a, **k: sent.append(a))
    d = tmp_path / "co" / "documents"
    d.mkdir(parents=True)
    (d / "a.md").write_text("# A\n\nSome text about net worth.\n", encoding="utf-8")
    plane = PlaneStore(tmp_path).plane_for("co")
    assert DI.ensure(plane, "documents/a.md") and DI.search(plane, ["documents/a.md"], "net worth")
    assert sent == []  # the autouse fixture runs the job inline (and the model is off there)


def test_query_embedding_can_slip_between_file_batches(monkeypatch, tmp_path):
    calls = fake_fastembed(monkeypatch, tmp_path)

    class Counting:
        n = 0
        def __enter__(self): Counting.n += 1
        def __exit__(self, *a): pass
    monkeypatch.setattr(doc_embed, "_enc", Counting())
    out = doc_embed.embed(["x"] * 150)
    assert out.shape == (150, 3) and calls["batches"] == [64, 64, 22] and Counting.n == 3  # lock taken per batch, not per file


def test_dimension_mismatch_costs_only_the_meaning_half_and_heals(plane):
    DI.search(plane, [P], "net worth")
    con = DI._db(plane)
    with con:
        con.execute("update vectors set vec=zeroblob(8) where path=?", (P,))  # a vector of another model's size
    con.close()
    hits = DI.search(plane, [P], "net worth")  # must not raise
    assert hits and hits[0]["how"] == "words"
    assert DI.search(plane, [P], "total wealth")[0]["how"] == "meaning"  # re-embedded


def test_switching_the_model_re_embeds_by_itself(plane, monkeypatch):
    DI.search(plane, [P], "net worth")
    monkeypatch.setattr(doc_embed, "MODEL", "other/model")
    DI.search(plane, [P], "net worth")
    con = DI._db(plane)
    assert con.execute("select sig from vec_files where path=?", (P,)).fetchone()[0].startswith("other/model|")
    con.close()


def test_file_changed_during_embedding_is_queued_again(plane, monkeypatch):
    once = []

    def edit_midway(texts, query=False):
        if not once:
            once.append(1)
            plane.path("documents", "other.md").write_text("# Other\n\nTotal wealth is reported, and this text is longer than before.\n", encoding="utf-8")
            DI.ensure(plane, O)  # its own embed job finds the first one still busy
        return stub(texts, query)
    monkeypatch.setattr(doc_embed, "embed", edit_midway)
    DI.ensure(plane, O)
    con = DI._db(plane)
    f, v = con.execute("select f.sig, v.sig from files f join vec_files v on v.path=f.path where f.path=?", (O,)).fetchone()
    con.close()
    assert v == DI._vsig(f)  # the new version has its vectors without waiting for a search


def test_query_with_no_ascii_word_still_goes_to_meaning_search(plane, monkeypatch):
    monkeypatch.setattr(doc_embed, "embed", lambda texts, query=False: stub([t.replace("财富", "total wealth") for t in texts], query))
    hits = DI.search(plane, [P], "总财富")
    assert hits and hits[0]["path"] == P and hits[0]["how"] == "meaning"
    assert DI.search(plane, [P], "   ") == []


def test_forget_removes_every_row_of_a_file(plane):
    DI.search(plane, [P, O], "net worth")
    DI.forget(plane, P)
    con = DI._db(plane)
    for t in ("files", "lines", "passages", "vectors", "vec_files"):
        assert con.execute(f"select count(*) from {t} where path=?", (P,)).fetchone()[0] == 0
    assert con.execute("select count(*) from vectors where path=?", (O,)).fetchone()[0] == 1
    con.close()


def test_model_in_cache_switches_the_hub_to_offline(monkeypatch, tmp_path):
    fake_fastembed(monkeypatch, tmp_path)
    (tmp_path / "models" / "models--Qdrant--x" / "snapshots" / "abc").mkdir(parents=True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.delenv("HF_HUB_OFFLINE")
    doc_embed.embed(["a"])
    assert doc_embed.os.environ["HF_HUB_OFFLINE"] == "1"
