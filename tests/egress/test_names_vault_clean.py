"""Why live model calls were refused: the vault held generic words ("Finance", "Market", "illustrative") that the
gateway's name check (also glued inside words) then found in nearly every business sentence. One rule decides what
is registered (sh_platform/egress/names.py); tools/vault_clean.py removes what the rule would not register. Synthetic
plane shaped like the live one; the texts are the demo story's; the transport is a stub (no network)."""
import json
import sys
from pathlib import Path

import pytest

from modules.m2_baseline.agent import lens
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.names import protected_names
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.plane import PlaneStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import vault_clean  # noqa: E402

STORY = Path(__file__).resolve().parents[2] / "packs" / "family_office" / "1" / "demo_story"
COMPANY = "Illustrative Lakeside Family Office"
PEOPLE = ["Arjun Rao", "Mei Tan (illustrative)", "Lina Ho"]
ORGS = ["Market data vendor API", "Index provider", "Northgate Custody", "Finance", "Managers"]
JUNK = ["illustrative", "Sponsor", "Lakeside", "Finance", "Officer", "Market", "data", "vendor", "API", "Index",
        "Committee", "Managers", "Payroll", "Market data vendor API"]


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


def _polluted(tmp_path):
    """A vault as the old code left it: people, their parts, and every generic word as a person."""
    (tmp_path / "data").mkdir()
    plane = PlaneStore(tmp_path / "data").create("lakeside-family-office")
    v = NameVault(plane)
    v.register("company", COMPANY)
    for n in ["Arjun Rao", "Arjun", "Rao", "Mei Tan (illustrative)", "Mei", "Tan", "email", "via", *JUNK]:
        v.register("person", n)
    return plane


def _client(plane, calls):
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test/v1", transport=lambda url, body: calls.append(body) or "Noted.")
    return EgressModelClient(gw)


def _register_by_rule(plane):
    v = NameVault(plane)
    for kind, name in protected_names(COMPANY, PEOPLE, ORGS):
        v.register(kind, name)


def _send(model):
    note = (STORY / "13_performance_review_note.md").read_text(encoding="utf-8")
    kpi = dict(company_name=COMPANY, industry="Family office", kpi_name="Manager excess return", pack="", documents=lens._plain(note))
    lens.draft_definition(model, Gate(), "co", **kpi)  # a Lens draft payload
    model.complete("m1_intent", [{"role": "system", "content": "You are North."},
                                 {"role": "user", "content": json.dumps({"note": note.replace("|", " ")})}])  # a North note


def test_the_old_vault_blocks_the_demo_story_and_the_cleaned_one_passes_with_names_still_tokens(tmp_path):
    plane = _polluted(tmp_path)
    with pytest.raises((EgressBlocked, lens.ModelUnreachable)):
        _send(_client(plane, []))
    first = vault_clean.clean(plane)
    assert first["removed"] >= len(JUNK) + 1 and first["renamed"] == 1
    assert vault_clean.clean(plane) == {"before": first["after"], "removed": 0, "renamed": 0, "after": first["after"]}  # idempotent
    assert len(list(plane.area("context").glob("name_vault.json.bak-*"))) == 1  # one backup, made only when something changed
    _register_by_rule(plane)
    calls = []
    _send(_client(plane, calls))
    assert len(calls) == 3  # the Lens draft ("Noted." is too thin, so one retry), the retry, and the North note
    for body in calls:
        text = body.decode()
        assert "PERSON_" in text and "COMPANY_" in text
        assert not any(n in text for n in ("Arjun", "Mei Tan", "Lina", "Northgate", "Lakeside"))
        assert "Finance" in text or "committee" in text.lower()  # ordinary words are left alone


def test_the_rule_registers_names_not_words():
    got = dict.fromkeys(protected_names(COMPANY, PEOPLE, ORGS))
    people = {n for k, n in got if k == "person"}
    assert {"Arjun Rao", "Arjun", "Rao", "Mei Tan", "Mei", "Tan", "Lina Ho", "Lina"} <= people
    assert ("company", "Northgate Custody") in got and ("company", COMPANY) in got
    assert not any(n.casefold() in {"illustrative", "finance", "managers", "market", "index"} for _, n in got)
    assert not any("Market data" in n or "Index provider" in n for _, n in got)
    assert protected_names("", ["Sponsor", "Finance Officer", "HR", "Payroll"]) == []


def test_a_person_with_a_stop_word_keeps_the_parts_that_are_not_stop_words():
    got = {n for k, n in protected_names("", ["Grace Bank", "Hope Finance", "Bank Finance"]) if k == "person"}
    assert {"Grace Bank", "Grace", "Hope Finance", "Hope"} <= got
    assert not {"Bank", "Finance"} & got and "Bank Finance" not in got


def test_an_organisations_first_word_is_registered_and_generic_openers_are_not():
    got = set(protected_names("", [], ["Northgate Custody", "Global Equity Fund III"]))
    assert ("company", "Northgate Custody") in got and ("company", "Northgate") in got
    assert ("company", "Global Equity Fund III") in got
    assert not any(n in {"Global", "Equity", "Fund", "III"} for _, n in got)


def test_a_who_that_looks_like_a_person_keeps_its_parts_but_a_system_does_not():
    from modules.m2_baseline.api.process_map import _names
    answer = {"owner_name": "", "upstream": [{"who": "Sam Lee"}, {"who": "Market data vendor API"}, {"who": "Finance"}]}
    people, orgs = _names([answer], [])
    got = {n for _, n in protected_names("", people, orgs)}
    assert {"Sam Lee", "Sam", "Lee"} <= got and not {"Finance", "Market data vendor API", "Market"} & got


def test_vault_clean_keeps_a_real_person_entry_and_its_token(tmp_path):
    plane = _polluted(tmp_path)
    token = NameVault(plane).register("person", "Arjun Rao")
    vault_clean.clean(plane)
    assert NameVault(plane).register("person", "Arjun Rao") == token
    assert {e["name"] for e in NameVault(plane)._parse(NameVault(plane)._read_raw()).values()} >= {"Arjun Rao", "Arjun", "Rao"}


def test_vault_clean_refuses_a_folder_that_is_not_a_company_plane(tmp_path):
    (tmp_path / "data" / "not-a-plane").mkdir(parents=True)
    assert vault_clean.main(["--data-root", str(tmp_path / "data"), "not-a-plane"]) == 1
    assert list((tmp_path / "data" / "not-a-plane").iterdir()) == []
    assert vault_clean.main(["--data-root", str(tmp_path / "data"), "missing"]) == 1
    assert not (tmp_path / "data" / "missing").exists()


def test_a_name_after_a_json_line_break_escape_is_still_swapped(tmp_path):
    # live failure (4 Oct): North's context is JSON text, so "estimate.\nArjun:" reaches the vault as the letters
    # backslash-n-Arjun; the name was not at a word boundary, went unswapped, and the final check refused the call
    import json

    from sh_platform.egress.vault import NameVault
    from sh_platform.plane import PlaneStore
    vault = NameVault(PlaneStore(tmp_path / "data").create("co"))
    vault.register("person", "Arjun Rao")
    vault.register("person", "Arjun")
    body = json.dumps({"context": "an estimate.\nArjun: the pack only shows calls\twe know"})
    out = vault.tokenise(body)
    assert "Arjun" not in out and not vault.contains_name(out)
    assert json.loads(out)["context"].startswith("an estimate.")  # still valid JSON
    escaped = "C:" + "\\" * 2 + "new folder"  # JSON for the path C:\new folder: an escaped backslash, then "new"
    assert vault.tokenise(escaped) == escaped  # an escaped backslash is left alone
