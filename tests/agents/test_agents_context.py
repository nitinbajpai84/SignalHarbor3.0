import pytest

from sh_platform.agents.context import build_context_pack
from sh_platform.packs import EmptyPack, PackLoader

FACTS = [{"id": "f1", "label": "Open items", "value": 12, "group_size": 9},
         {"id": "f2", "label": "Other", "value": 3, "group_size": 8},
         {"id": "f3", "label": "Third", "value": 4, "group_size": 8}]


def _packs(tmp_path):
    for ind, q in (("alpha", "Are deliveries late?"), ("beta", "Is stock short?")):
        d = tmp_path / ind / "1"
        d.mkdir(parents=True)
        (d / "pack.yaml").write_text(f"industry: {ind}\nversion: 1\nlabel: {ind}\n")
        (d / "problems.yaml").write_text(f"problems:\n  - id: P1\n    question: {q}\n")
    return PackLoader(tmp_path)


def test_two_industries_get_different_suggestions(tmp_path):
    loader = _packs(tmp_path)
    a = build_context_pack({"name": "A Co", "industry": "alpha"}, loader.load("alpha"), FACTS, "q", max_facts=5)
    b = build_context_pack({"name": "B Co", "industry": "beta"}, loader.load("beta"), FACTS, "q", max_facts=5)
    assert a["company"] == {"name": "A Co", "industry": "alpha"}
    assert a["suggestions"] != b["suggestions"]
    assert a["suggestions"][0]["text"] == "Are deliveries late?"
    assert "suggestion" in a["suggestions"][0]["label"]
    assert "Is stock short?" not in str(a)


def test_empty_company_gets_honest_empty_state():
    p = EmptyPack("retail")
    c = build_context_pack({"name": "C", "industry": "retail"}, p, [], "q", max_facts=5)
    assert c["suggestions"] == [] and c["empty_state"] == p.message


def test_facts_capped_and_shaped():
    c = build_context_pack({"name": "C", "industry": "x"}, EmptyPack("x"), FACTS, "why?", max_facts=2)
    assert c["facts"] == FACTS[:2] and c["question"] == "why?"
    assert set(c["facts"][0]) == {"id", "label", "value", "group_size"}


def test_documents_only_short_context_summary():
    c = build_context_pack({"name": "C", "industry": "x"}, EmptyPack("x"), [], "q", max_facts=2,
                           documents=["word " * 500])
    (d,) = c["documents"]
    assert d["kind"] == "context_summary" and len(d["text"]) <= 300
    assert "context" in d["note"].lower() and "instruction" in d["note"].lower()


def test_bad_company_refused():
    with pytest.raises(ValueError):
        build_context_pack({"name": "C"}, EmptyPack("x"), [], "q", max_facts=2)


def test_small_or_ungrouped_facts_never_carry_a_value():
    facts = [{"id": "a", "label": "small", "value": 41, "group_size": 4},
             {"id": "b", "label": "none", "value": 42},
             {"id": "c", "label": "str", "value": 43, "group_size": "9"},
             {"id": "d", "label": "bool", "value": 44, "group_size": True},
             {"id": "e", "label": "ok", "value": 45, "group_size": 5}]
    c = build_context_pack({"name": "C", "industry": "x"}, EmptyPack("x"), facts, "q", max_facts=9)
    assert [f.get("available") for f in c["facts"]] == [False] * 4 + [None]
    text = str(c)
    assert all(v not in text for v in ("41", "42", "43", "44")) and "45" in text


def test_pack_industry_must_match_company(tmp_path):
    loader = _packs(tmp_path)
    with pytest.raises(ValueError):
        build_context_pack({"name": "C", "industry": "beta"}, loader.load("alpha"), [], "q", max_facts=2)
