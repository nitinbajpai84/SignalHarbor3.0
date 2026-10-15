import pytest

from sh_platform.egress.aggregates import MIN_GROUP, filter_facts
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.minimiser import MAX_SUMMARY_CHARS, minimise
from sh_platform.egress.vault import NameVault


def test_tokenise_case_insensitive_longest_first_whole_words(plane):
    v = NameVault(plane)
    v.register("company", "Acme")
    v.register("company", "Acme Holdings")
    v.register("person", "Jo Park")
    out = v.tokenise("ACME HOLDINGS and acme met jo park; Acmeville stays. Jo Parker too")
    assert "HOLDINGS" not in out and "jo park" not in out
    assert "Acmeville" in out and "Jo Parker" in out
    assert out.count("COMPANY_") == 2 and "PERSON_001" in out
    assert v.tokenise("acme") == v.tokenise("ACME")  # stable token


def test_kind_validated(plane):
    with pytest.raises(ValueError):
        NameVault(plane).register("planet", "Mars")


def test_patterns_tokenised_and_round_trip(plane):
    v = NameVault(plane)
    v.register("person", "Jo Park")
    text = "Mail jo@corp.example or call +65 6123 4567, acct 123456789012, Jo Park."
    out = v.tokenise(text)
    for leak in ("jo@corp.example", "6123 4567", "123456789012", "Jo Park"):
        assert leak not in out
    assert v.detokenise(out) == text
    assert v.contains_name(text) and not v.contains_name(out)


def test_contains_name_catches_glued_and_zero_width(plane):
    v = NameVault(plane)
    v.register("company", "Northwind Traders")
    assert v.contains_name("x NorthwindTraders1")
    assert v.contains_name("north​wind traders")
    assert not v.contains_name("nothing here")


def test_vault_persists_in_plane_only(plane, store):
    v = NameVault(plane)
    v.register("fund", "Blue Fund")
    assert (plane.area("context") / "name_vault.json").is_file()
    assert NameVault(plane).tokenise("Blue Fund") == v.tokenise("Blue Fund")
    assert NameVault(store.create("beta-co")).contains_name("Blue Fund") is False


def test_group_of_five_passes_four_suppressed():
    allowed, sup = filter_facts([
        {"label": "a", "value": 10, "group_size": MIN_GROUP},
        {"label": "b", "value": 1234.5, "group_size": 4},
        {"label": "c", "value": 3},
        {"label": "d", "value": 3, "group_size": 9.0},
        {"label": "e", "value": 3, "group_size": True},
    ])
    assert [f["label"] for f in allowed] == ["a"]
    assert len(sup) == 4 and sup.appears_in("it was 1,234.5 units") and not sup.appears_in("12345")


def test_minimise_keeps_only_allowed():
    payload, sup = minimise("How many?", [
        {"label": "orders", "value": 40, "group_size": 8},
        {"label": "secret", "value": 99.5, "group_size": 8},
        {"label": "small", "value": 7.25, "group_size": 2},
    ], allowed_fields={"orders", "small"})
    assert payload == {"question": "How many?", "facts": [{"label": "orders", "value": 40, "group_size": 8}]}
    assert sup.appears_in("99.5") and sup.appears_in("7.25")


def test_minimise_refuses_rows_and_long_summary():
    for bad in ([{"id": 1, "name": "x"}], ["a,b,c"]):
        with pytest.raises(EgressBlocked) as e:
            minimise("q", bad, allowed_fields={"x"})
        assert e.value.reason_code in ("raw_rows", "bad_fact")
    with pytest.raises(EgressBlocked) as e:
        minimise('see [{"a": 1}, {"a": 2}]', [], allowed_fields=set())
    assert e.value.reason_code == "raw_rows"
    with pytest.raises(EgressBlocked) as e:
        minimise("q", [], set(), summary="x" * (MAX_SUMMARY_CHARS + 1))
    assert e.value.reason_code == "summary_too_long"
    p, _ = minimise("q", [], set(), summary="x" * MAX_SUMMARY_CHARS)
    assert len(p["summary"]) == MAX_SUMMARY_CHARS
