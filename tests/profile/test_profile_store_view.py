"""The profile store (provenance cells, a draft never replaces a person) and `read(plane, viewer)` (module 2's governance rules, copied)."""
import pytest

from sh_platform.profile import Viewer, read, record

SRC = "People list, sheet 1"
LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": SRC}
ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
SPONSOR = Viewer("Sue Sponsor", frozenset({"sponsor"}))
TOM = Viewer("Tom Ng", frozenset({"analyst"}))
LENA = Viewer("Lena Ho", frozenset({"analyst"}))


def rule(plane, fid, personal, sensitive, names, **extra):
    record(plane, f"governance.field_rules.{fid}.field", fid, LENS)
    record(plane, f"governance.field_rules.{fid}.personal", personal, LENS)
    record(plane, f"governance.field_rules.{fid}.sensitive", sensitive, LENS)
    record(plane, f"governance.field_rules.{fid}.may_see", names, LENS)
    for k, v in extra.items():
        record(plane, f"governance.field_rules.{fid}.{k}", v, LENS)


def fields(plane, viewer):
    return set(read(plane, viewer)["governance"]["field_rules"])


def test_a_cell_has_module_twos_shape_and_an_unknown_has_no_value(plane):
    c = record(plane, "people.mei-tan.role", "Head of finance", {**LENS, "ref": {"kind": "document", "id": "a1", "page": "sheet 1"}})
    assert set(c) == {"value", "mark", "by", "at", "from", "ref", "agent"} and c["from"] == SRC and c["ref"] == {"kind": "document", "id": "a1", "page": "sheet 1"}
    plain = record(plane, "people.mei-tan.team", "Finance", {"mark": "stated", "by": "Mei Tan", "from": "Interview with Mei Tan"})
    assert set(plain) == {"value", "mark", "by", "at", "from"}  # the module 2 shape: ref and agent are optional
    u = record(plane, "people.mei-tan.team", "Finance", {"mark": "unknown", "by": "Lens", "from": SRC})
    assert u["value"] is None and u["mark"] == "unknown"
    assert read(plane, ADMIN)["people"]["mei-tan"]["role"]["value"] == "Head of finance"


@pytest.mark.parametrize("path,prov", [("people.x", LENS), ("nowhere.x.y", LENS), ("people.X.y", LENS), ("governance.other.x.y", LENS),
                                       ("people.x.y", {**LENS, "mark": "sure"}), ("people.x.y", {**LENS, "by": ""}),
                                       ("people.x.y", {**LENS, "from": {"kind": "person", "ref": "a"}}), ("people.x.y", {**LENS, "from": ""}),
                                       ("people.x.y", {**LENS, "ref": {"kind": "rumour", "id": "a"}}), ("people.x.y", {**LENS, "ref": {"kind": "person"}}),
                                       ("people.x.y", {**LENS, "agent": "mallory"})])
def test_bad_paths_and_provenance_are_refused(plane, path, prov):
    with pytest.raises(ValueError):
        record(plane, path, "v", prov)


def test_a_draft_never_replaces_a_person_but_a_person_replaces_a_draft(plane):
    record(plane, "people.mei-tan.role", "Head of finance", LENS)
    mine = {"mark": "stated", "by": "Mei Tan", "from": "Interview with Mei Tan", "ref": {"kind": "interview", "id": "q7"}}
    assert record(plane, "people.mei-tan.role", "CFO", mine)["value"] == "CFO"
    assert record(plane, "people.mei-tan.role", "Head of finance again", LENS) is None
    got = read(plane, ADMIN)["people"]["mei-tan"]["role"]
    assert got["value"] == "CFO" and got["by"] == "Mei Tan" and got["ref"]["kind"] == "interview" and got["from"] == "Interview with Mei Tan"


# ---- the same cases as module 2's governance tests ----------------------------------------------------------------------

def test_an_open_field_is_seen_by_everyone(plane):
    rule(plane, "capital_called", "no", False, [])
    assert fields(plane, TOM) == fields(plane, ADMIN) == {"capital_called"}


def test_a_personal_field_is_seen_by_the_named_only_the_admin_too_once_nobody_is_named(plane):
    rule(plane, "pay", "yes", True, ["Lena Ho"])
    assert fields(plane, LENA) == {"pay"} and fields(plane, ADMIN) == set()  # A-069: named, so the admin is outside
    assert fields(plane, TOM) == set() and fields(plane, SPONSOR) == set()  # the sponsor passes only when named


def test_not_sure_counts_as_personal_and_so_does_nothing_said(plane):
    rule(plane, "holding", "not_sure", False, ["Lena Ho"])
    record(plane, "governance.field_rules.silent.field", "silent", LENS)
    assert fields(plane, TOM) == set() and fields(plane, LENA) == {"holding"} and fields(plane, ADMIN) == {"silent"}  # A-069


def test_sensitive_is_closed_even_when_not_personal(plane):
    rule(plane, "deal", "no", True, ["Lena Ho"])
    assert fields(plane, TOM) == set() and fields(plane, LENA) == {"deal"}


def test_where_nobody_is_named_only_the_admin_sees_it(plane):
    rule(plane, "pay", "yes", False, [])
    assert fields(plane, ADMIN) == {"pay"} and fields(plane, SPONSOR) == fields(plane, LENA) == set()


def test_a_name_another_account_shares_does_not_match_by_name(plane):
    rule(plane, "pay", "yes", False, ["Lena Ho"])
    assert fields(plane, Viewer("Lena Ho", frozenset({"analyst"}), shared_name=True)) == set()


def test_a_name_bound_to_an_account_matches_the_account_not_the_name(plane):
    rule(plane, "pay", "yes", False, ["Lena Ho"], may_see_accounts={"Lena Ho": ["acc-1"]})
    assert fields(plane, Viewer("Someone Else", frozenset({"analyst"}), account_id="acc-1")) == {"pay"}
    assert fields(plane, Viewer("Lena Ho", frozenset({"analyst"}), account_id="acc-9")) == set()  # a rename cannot let someone else in
    assert "may_see_accounts" not in str(read(plane, ADMIN))  # account ids stay on the server


def test_a_fields_own_list_adds_a_limit_the_admin_and_sponsor_pass(plane):
    rule(plane, "bonus", "no", False, [], field_may_see=["Lena Ho"])
    assert fields(plane, LENA) == fields(plane, ADMIN) == fields(plane, SPONSOR) == {"bonus"} and fields(plane, TOM) == set()  # the admin and sponsor pass by role marker, as before


# ---- restricted areas hide what sits in them -----------------------------------------------------------------------------

def test_a_restricted_area_hides_its_people_systems_figures_and_files(plane):
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", [], LENS)
    record(plane, "people.ann-hr.name", "Ann Hr", LENS)
    record(plane, "people.ann-hr.team", "HR", LENS)
    record(plane, "people.ann-hr.account_id", "acc-7", {"mark": "stated", "by": "Mei Tan", "from": "Linked by Mei Tan"})
    record(plane, "people.bob-fin.name", "Bob Fin", LENS)
    record(plane, "people.bob-fin.team", "Finance", LENS)
    record(plane, "people.bob-fin.account_id", "acc-8", {"mark": "stated", "by": "Mei Tan", "from": "Linked by Mei Tan"})
    record(plane, "systems.payroll.name", "Payroll", LENS)
    record(plane, "systems.payroll.area", "HR", LENS)
    record(plane, "reported_figures.headcount.area", "hr", LENS)
    record(plane, "inputs.g1.documents", [{"id": "d0", "name": "org.csv"}, {"id": "d1", "name": "pay.csv", "restricted": True}],
           {"mark": "stated", "by": "Mei Tan", "from": "Mei Tan"})
    admin, tom = read(plane, ADMIN), read(plane, TOM)
    assert set(admin["people"]) == {"ann-hr", "bob-fin"} and "payroll" in admin["systems"] and "hr" in admin["governance"]["restricted_areas"]
    assert admin["people"]["ann-hr"]["account_id"]["value"] == "acc-7"
    assert set(tom["people"]) == {"bob-fin"} and "account_id" not in tom["people"]["bob-fin"]
    assert tom["systems"] == {} and tom["reported_figures"] == {} and tom["governance"]["restricted_areas"] == {}
    assert [d["name"] for d in tom["inputs"]["g1"]["documents"]["value"]] == ["org.csv"]
    assert "Ann Hr" not in str(tom) and "pay.csv" not in str(tom)


def test_a_named_viewer_sees_the_area(plane):
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", ["Tom Ng"], LENS)
    record(plane, "people.ann-hr.team", "HR", LENS)
    assert "ann-hr" in read(plane, TOM)["people"] and "ann-hr" not in read(plane, LENA)["people"]


def test_another_company_is_unreachable(plane, other_plane):
    record(plane, "people.mei-tan.name", "Mei Tan", LENS)
    assert read(other_plane, ADMIN)["people"] == {}
    assert not (other_plane.path("context", "profile") / "profile.json").exists()


def test_an_interview_goes_with_its_hidden_person_and_question_keys_ignore_case(plane):
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", [], LENS)
    record(plane, "people.ann-hr.team", "HR", LENS)
    record(plane, "people.bob-fin.team", "Finance", LENS)
    say = {"mark": "stated", "by": "Ann Hr", "from": "Interview with Ann Hr"}
    record(plane, "interviews.ann-hr.Q3", {"answer": "payroll runs late"}, say)
    record(plane, "interviews.bob-fin.q3", {"answer": "close takes 9 days"}, say)
    record(plane, "interviews.anon-1.q14", {"answer": "a note"}, say)  # an anonymous note has no person behind it
    assert set(read(plane, TOM)["interviews"]) == {"bob-fin", "anon-1"} and "payroll runs late" not in str(read(plane, TOM))
    assert read(plane, ADMIN)["interviews"]["ann-hr"]["q3"]["value"] == {"answer": "payroll runs late"}


def test_a_guess_never_replaces_a_stated_value_and_a_system_named_like_a_hidden_area_is_shut(plane):
    record(plane, "governance.restricted_areas.pay.may_see", ["Tom Ng"], LENS)
    assert record(plane, "governance.restricted_areas.pay.may_see", ["Sam Evil"], {**LENS, "mark": "guessed"}) is None
    assert read(plane, TOM)["governance"]["restricted_areas"]["pay"]["may_see"]["value"] == ["Tom Ng"]
    record(plane, "governance.restricted_areas.pay.area", "Pay", LENS)
    record(plane, "governance.restricted_areas.pay.may_see", ["Sue Sponsor"], LENS)
    record(plane, "systems.pay.name", "Pay", LENS)
    tom = read(plane, TOM)["systems"]
    assert "pay" not in tom and "Pay" not in str(tom)


# ---- A-069: the admin passes only while nobody is named -------------------------------------------------------------------

def _hr(plane, may_see):
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", may_see, LENS)
    record(plane, "people.ann-hr.team", "HR", LENS)
    record(plane, "systems.payroll.area", "HR", LENS)
    record(plane, "reported_figures.headcount.area", "hr", LENS)
    record(plane, "inputs.g1.documents", [{"id": "d0", "name": "org.csv"}, {"id": "d1", "name": "pay.csv", "restricted": True}, {"id": "d2", "name": "HR.csv"}],
           {"mark": "stated", "by": "Mei Tan", "from": "Mei Tan"})


def test_an_area_nobody_is_named_on_is_for_the_admin_only(plane):
    _hr(plane, [])
    assert "hr" in read(plane, ADMIN)["governance"]["restricted_areas"] and "ann-hr" in read(plane, ADMIN)["people"]
    assert "hr" not in read(plane, TOM)["governance"]["restricted_areas"] and "ann-hr" not in read(plane, TOM)["people"]


def test_once_somebody_is_named_the_admin_gets_the_silhouette_like_an_outsider(plane):
    _hr(plane, ["Tom Ng"])
    tom, admin = read(plane, TOM), read(plane, ADMIN)
    assert "ann-hr" in tom["people"] and "hr" in tom["governance"]["restricted_areas"]
    assert "ann-hr" not in admin["people"] and admin["governance"]["restricted_areas"] == {}
    assert admin["reported_figures"] == {} and admin["systems"] == {}
    assert [d["name"] for d in admin["inputs"]["g1"]["documents"]["value"]] == ["org.csv", "pay.csv"] and "HR.csv" not in str(admin) and "HR.csv" not in str(read(plane, LENA))
    assert admin["systems"] == read(plane, LENA)["systems"]


def test_a_role_word_on_the_list_passes_the_admin_by_role(plane):
    _hr(plane, ["\x00company_admin"])
    assert "ann-hr" in read(plane, ADMIN)["people"] and "ann-hr" not in read(plane, TOM)["people"]


def test_a_personal_source_with_a_named_list_is_shut_to_an_admin_outside_it(plane):
    record(plane, "systems.payroll.name", "Payroll", LENS)
    record(plane, "systems.payroll.personal_data", "yes", LENS)
    record(plane, "systems.payroll.may_see", ["Tom Ng"], LENS)
    assert read(plane, TOM)["systems"]["payroll"]["name"]["value"] == "Payroll"
    assert read(plane, ADMIN)["systems"] == {"restricted-1": {"restricted": True, "label": "A restricted source"}}
    record(plane, "systems.payroll.may_see", [], LENS)
    assert "payroll" in read(plane, ADMIN)["systems"] and "payroll" not in read(plane, TOM)["systems"]
