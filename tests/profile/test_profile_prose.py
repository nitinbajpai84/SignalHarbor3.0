"""Lens reads prose documents (IC-0b) and derives restricted areas from the classification policy (IC-0c). The model is a fixed-reply stub."""
import json

from pf_kit import PEOPLE, StubModel
from sh_platform.profile import Viewer, read, reader, store

ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
TOM = Viewer("Tom Ng", frozenset())
HEAD = Viewer("Hana Lee", frozenset())
SUE = Viewer("Sue Sponsor", frozenset({"sponsor"}))
HR = Viewer("HR", frozenset({"hr"}))
FINANCE = Viewer("Finance", frozenset({"finance"}))
PAPER = (b"# Strategy\n\nThe office wants to move to one reporting view by next year. Ops staff re-key the custody feed every month end, "
         b"which wastes time. The custody feed is the main source of positions for the office.\n")
POLICY = (b"# Classification policy\n\nPay and HR records are restricted. Only the head of people may see them. "
          b"Compensation data is confidential and nobody outside payroll may open it.\n")
IDEAS = {"people": [{"name": "Sue Lim", "role": "Sponsor", "team": "Investment", "passage": "Sue sponsors it"},
                    {"name": "[a name]", "role": "x", "passage": "p"}],
         "systems": [{"name": "Custody feed", "kind": "feed", "passage": "main source of positions"}],
         "pains": [{"what": "Re-keying the custody feed", "who": "Ops staff", "how_often": "every month end", "passage": "re-key the custody feed"}],
         "signals": [{"what": "One reporting view", "passage": "move to one reporting view"}]}
AREAS = {"restricted": [{"area": "Pay", "may_see": ["Hana Lee"], "passage": "Pay and HR records are restricted"},
                        {"area": "Compensation", "may_see": [], "passage": "Compensation data is confidential"}]}


def model(**d):
    return StubModel(json.dumps(d))


def up(plane, gid, name, data, m):
    return reader.add_upload(plane, gid, "Mei Tan", name, data, m)


def stated(plane, cells):
    store.mutate(plane, lambda d: [store.set_cell(d, p, v, {"mark": "stated", "by": "Dan", "from": "Interview with Dan"})
                                   for p, v in cells.items()])


def test_prose_gives_guessed_people_systems_and_findings_with_the_passage(plane):
    m = model(**IDEAS)
    out = up(plane, 2, "strategy.md", PAPER, m)
    assert out["results"][0]["result"] == "read" and "BEGIN QUOTED DOCUMENT TEXT" in m.everything
    prof = read(plane, ADMIN)
    c = prof["people"]["sue-lim"]["role"]
    assert (c["value"], c["mark"], c["agent"], c["by"]) == ("Sponsor", "guessed", "lens", "Lens") and c["from"].startswith("strategy.md: ")
    assert list(prof["people"]) == ["sue-lim"]  # a masked name is never filed
    assert prof["systems"]["custody-feed"]["kind"]["mark"] == "guessed"
    f = prof["inputs"]["g2"]["findings"]
    assert f["mark"] == "guessed" and f["agent"] == "lens" and {x["kind"] for x in f["value"]} == {"pain", "signal"}
    pain = next(x for x in f["value"] if x["kind"] == "pain")
    assert (pain["text"], pain["who"], pain["how_often"]) == ("Re-keying the custody feed", "Ops staff", "every month end")
    assert pain["from"].startswith("strategy.md: ")


def test_a_draft_never_replaces_what_is_already_there(plane):
    up(plane, 1, "people.csv", PEOPLE, StubModel())
    stated(plane, {"people.sue-lim.role": "Chair", "systems.custody-feed.kind": "file drop"})
    up(plane, 2, "strategy.md", PAPER, model(**IDEAS))
    prof = read(plane, ADMIN)
    assert prof["people"]["sue-lim"]["role"]["value"] == "Chair" and prof["systems"]["custody-feed"]["kind"]["value"] == "file drop"
    assert prof["people"]["sue-sponsor"]["is_sponsor"]["mark"] == "stated"  # the table's person is untouched


def test_nothing_found_reads_with_the_reason(plane):
    r = up(plane, 2, "strategy.md", PAPER, model())["results"][0]
    assert r["result"] == "read" and r["reason"] == "Read; nothing new for the profile."
    assert "findings" not in read(plane, ADMIN)["inputs"]["g2"]


def test_a_restricted_document_is_never_read(plane):
    m = model(**IDEAS)
    r = reader.add_upload(plane, 2, "Mei Tan", "pay.md", PAPER, m, restricted=True)["results"][0]
    assert r["result"] == "held" and m.sent == [] and read(plane, ADMIN)["people"] == {}


def test_a_second_industry_and_an_empty_company(plane, other_plane):
    assert read(plane, ADMIN)["governance"]["restricted_areas"] == {}
    body = b"# Plan\n\nThe distributor wants one stock view across warehouses by next year. Pickers re-count bins every week.\n"
    up(other_plane, 2, "strategy.md", body, model(pains=[{"what": "Bin recounts", "who": "Pickers", "how_often": "weekly", "passage": "re-count bins"}]))
    assert read(other_plane, ADMIN)["inputs"]["g2"]["findings"]["value"][0]["text"] == "Bin recounts"
    assert "g2" not in read(plane, ADMIN)["inputs"]


def test_a_policy_gives_guessed_restricted_areas_hidden_from_outsiders(plane):
    stated(plane, {"people.hana-lee.name": "Hana Lee"})
    up(plane, 7, "classification.md", POLICY, model(**AREAS))
    areas = read(plane, HEAD)["governance"]["restricted_areas"]  # A-069: the admin passes only an area nobody is named on
    assert areas["pay"]["may_see"]["value"] == ["Hana Lee"] and read(plane, ADMIN)["governance"]["restricted_areas"]["compensation"]["may_see"]["value"] == []
    assert "pay" not in read(plane, ADMIN)["governance"]["restricted_areas"]
    assert areas["pay"]["area"]["mark"] == "guessed" and areas["pay"]["area"]["from"].startswith("classification.md: ")
    stated(plane, {"systems.pay-engine.name": "Pay engine", "systems.pay-engine.area": "Pay", "reported_figures.pay.measure": "Pay",
                   "reported_figures.pay.figure": 5, "systems.custody-feed.name": "Custody feed"})
    tom, named = read(plane, TOM), read(plane, HEAD)
    assert "pay-engine" not in tom["systems"] and tom["reported_figures"] == {} and "custody-feed" in tom["systems"]
    assert tom["governance"]["restricted_areas"] == {}
    assert "pay-engine" in named["systems"] and "pay" in named["governance"]["restricted_areas"]
    assert "compensation" not in named["governance"]["restricted_areas"]  # nobody is named for it


def test_a_reread_drops_a_guessed_area_the_policy_no_longer_names_but_keeps_a_stated_one(plane):
    stated(plane, {"people.hana-lee.name": "Hana Lee"})
    m = model(**AREAS)
    up(plane, 7, "classification.md", POLICY, m)
    store.mutate(plane, lambda d: store.set_cell(d, "governance.restricted_areas.compensation.area", "Compensation",
                                                 {"mark": "stated", "by": "Mei Tan", "from": "Told by Mei Tan"}))
    m.text = json.dumps({"restricted": [{"area": "Pay", "may_see": ["Hana Lee"], "passage": "Pay is restricted"}]})
    reader.read_all(plane, m)
    got = {**read(plane, HEAD)["governance"]["restricted_areas"], **read(plane, ADMIN)["governance"]["restricted_areas"]}
    assert set(got) == {"pay", "compensation"} and got["compensation"]["area"]["mark"] == "stated"
    m.text = "none"
    reader.read_all(plane, m)
    assert set(read(plane, ADMIN)["governance"]["restricted_areas"]) == {"compensation"}


def test_a_table_in_group_seven_still_takes_the_table_path(plane):
    m = model(**AREAS)
    up(plane, 7, "areas.csv", b"Area,Who may see\nHR,Mei Tan\n", m)
    assert m.sent == [] and read(plane, ADMIN)["governance"]["restricted_areas"]["hr"]["area"]["mark"] == "stated"


def test_a_guessed_policy_never_replaces_a_stated_table_area_even_from_an_agent(plane):
    up(plane, 7, "areas.csv", b"Area,Who may see\nPay,Tom Ng\n", StubModel())
    up(plane, 7, "classification.md", POLICY, model(restricted=[{"area": "Pay", "may_see": ["Sam Evil"], "passage": "Pay is restricted"}]))
    reader.read_all(plane, model(restricted=[{"area": "Pay", "may_see": ["Sam Evil"], "passage": "Pay is restricted"}]))
    pay = read(plane, TOM)["governance"]["restricted_areas"]["pay"]
    assert pay["may_see"]["value"] == ["Tom Ng"] and pay["may_see"]["mark"] == "stated" and pay["area"]["mark"] == "stated"


def test_a_policy_cannot_name_an_unknown_person_into_may_see(plane):
    stated(plane, {"people.sue.name": "Sue Sponsor"})
    up(plane, 7, "classification.md", POLICY, model(restricted=[{"area": "Pay", "may_see": ["Sue Sponsor", "Sam Evil", "head of data"], "passage": "p"}]))
    prof = read(plane, SUE)
    assert prof["governance"]["restricted_areas"]["pay"]["may_see"]["value"] == ["Sue Sponsor", "head of data"]
    assert any(f["kind"] == "names to confirm" and "Sam Evil" in f["text"] for f in prof["inputs"]["g7"]["findings"]["value"])
    assert "Sam Evil" not in str(prof["governance"])


def test_an_empty_policy_list_closes_the_area_and_a_guess_never_widens(plane):
    stated(plane, {"people.sue.name": "Sue Sponsor", "people.ann.name": "Ann Hr"})
    m = model(restricted=[{"area": "Pay", "may_see": [], "passage": "p"}])
    up(plane, 7, "classification.md", POLICY, m)
    assert read(plane, TOM)["governance"]["restricted_areas"] == {}
    m.text = json.dumps({"restricted": [{"area": "Pay", "may_see": ["Sue Sponsor"], "passage": "p"}]})
    store.mutate(plane, lambda d: store.set_cell(d, "governance.restricted_areas.pay.may_see", [], {"mark": "guessed", "by": "Dan", "from": "Dan's note"}))
    reader.read_all(plane, m)  # a guess already stands (empty, by a person): a wider one is dropped
    assert read(plane, ADMIN)["governance"]["restricted_areas"]["pay"]["may_see"]["value"] == []
    assert any(f["kind"] == "names to confirm" for f in read(plane, ADMIN)["inputs"]["g7"]["findings"]["value"])


JUNK = {"people": [{"name": "Chief Investment Officer", "role": "CIO", "passage": "the Chief Investment Officer"},
                   {"name": "Office staff", "passage": "Office staff re-key"}, {"name": "owner", "passage": "the owner"},
                   {"name": "Ann Cole", "role": "Head of data", "passage": "Ann Cole leads data"}],
        "systems": [{"name": "office machines", "passage": "office machines are old"}, {"name": "CRM", "kind": "system", "passage": "the CRM"}]}
JUNK_AREAS = {"restricted": [
    {"area": "Pay", "may_see": ["HR"], "covers": ["salaries", "bonuses", "summary figures"], "passage": "Pay is restricted to HR"},
    {"area": "Names of staff and family members", "may_see": [], "passage": "only named people"},
    {"area": "Internal", "may_see": ["Office staff", "agents"], "passage": "Internal is open to all staff"},
    {"area": "Confidential", "may_see": ["Office staff"], "passage": "all staff"},
    {"area": "summary figures", "may_see": [], "passage": "x"}]}


def test_prose_over_reading_is_cut_to_names_systems_and_areas_the_text_supports(plane):
    stated(plane, {"people.hr.name": "HR"})
    reader.add_upload(plane, 2, "Mei Tan", "strategy.md", PAPER, model(**JUNK))
    junk_areas_with_hr = {"restricted": [
        {"area": "Pay", "may_see": ["HR"], "covers": ["salaries", "bonuses", "summary figures"], "passage": "Pay is restricted to HR"},
        {"area": "Names of staff and family members", "may_see": ["HR"], "passage": "only named people"},
        {"area": "Internal", "may_see": ["Office staff", "agents"], "passage": "Internal is open to all staff"},
        {"area": "Confidential", "may_see": ["Office staff"], "passage": "all staff"},
        {"area": "summary figures", "may_see": [], "passage": "x"}]}
    reader.add_upload(plane, 7, "Mei Tan", "classification.md", POLICY, model(**junk_areas_with_hr))
    prof = read(plane, HR)
    assert sorted(prof["people"]) == ["ann-cole", "hr"] and list(prof["systems"]) == ["crm"]
    assert set(prof["governance"]["restricted_areas"]) == {"pay", "names-of-staff-and-family-members"}
    assert prof["governance"]["restricted_areas"]["pay"]["covers"]["value"] == ["salaries", "bonuses", "summary figures"]
    kinds = [x["kind"] for x in prof["inputs"]["g2"]["findings"]["value"]]
    assert kinds.count("role mentioned") == 3 and kinds.count("system mentioned") == 1


def test_areas_are_capped_and_long_fragments_become_findings(plane):
    stated(plane, {"people.hr.name": "HR"})
    many = [{"area": f"Class {n}", "may_see": ["HR"], "passage": "p"} for n in range(10)]
    many.append({"area": "relationship owner in the CRM for each of the staff", "may_see": ["HR"], "passage": "p"})
    reader.add_upload(plane, 7, "Mei Tan", "classification.md", POLICY, model(restricted=many))
    prof = read(plane, HR)
    assert len(prof["governance"]["restricted_areas"]) == 8
    assert [x["kind"] for x in prof["inputs"]["g7"]["findings"]["value"]].count("area to confirm") == 3


def test_a_reread_removes_the_earlier_guessed_junk(plane):
    # relies on drop_drafts by attachment id: junk from an attachment no longer present is not removed (known gap)
    m = model(**JUNK)
    reader.add_upload(plane, 2, "Mei Tan", "strategy.md", PAPER, m)
    att = reader.attachments(store.load(plane), 2)[0]
    junk = {"name": "Office staff", "role": "x"}  # the shape the earlier read filed
    store.mutate(plane, lambda d: [store.set_cell(d, f"people.office-staff.{f}", v, {"mark": "guessed", **reader._src(att)})
                                   for f, v in junk.items()])
    assert "office-staff" in read(plane, ADMIN)["people"]
    reader.read_all(plane, m)
    assert list(read(plane, ADMIN)["people"]) == ["ann-cole"]


def test_open_class_is_matched_by_whole_entry_and_named_roles_are_people(plane):
    areas = [{"area": a, "may_see": [w], "passage": "p"} for a, w in
             (("Pay", "Finance staff"), ("Rota", "HR office"), ("Board", "Office of the CEO"), ("Internal", "all staff"))]
    reader.add_upload(plane, 7, "Mei Tan", "classification.md", POLICY, model(restricted=areas))
    reader.add_upload(plane, 2, "Mei Tan", "strategy.md", PAPER, model(people=[{"name": "Will Head", "passage": "p"}, {"name": "Ann Owner", "passage": "p"}]))
    prof = read(plane, ADMIN)
    assert set(prof["governance"]["restricted_areas"]) == {"pay", "rota", "board"} and set(prof["people"]) == {"will-head", "ann-owner"}
    assert any(f["kind"] == "open to all" and f["text"] == "Internal" for f in prof["inputs"]["g7"]["findings"]["value"])


POLICY_PRECISION = (b"# Classification policy\n\n"
                    b"## Classes\n\n"
                    b"| Class | Meaning | Examples | Handling |\n"
                    b"|-------|---------|----------|----------|\n"
                    b"| Public | Open to all staff | Website, press releases | Read by anyone |\n"
                    b"| Internal | For office use only | Plans, budgets | Read by staff |\n"
                    b"| Confidential | Trusted insiders only | Board narratives, manager contracts | Read only by custodian and committee members |\n"
                    b"| Restricted | Named people only, never read by agents | Pay, bonus and HR data (payroll file, the payroll SOP) | Read only by HR and named Finance staff |\n\n"
                    b"## Personal data\n\n"
                    b"Names of staff and family members, emails, pay.\n\n"
                    b"## Who may see what\n\n"
                    b"Default: summary figures to the committee, rows to the owner of the source.\n")

AREAS_PRECISION = {"restricted": [
    {"area": "Restricted", "covers": ["pay", "bonus", "payroll file", "payroll sop"], "may_see": ["HR", "Finance"], "passage": "Restricted"},
    {"area": "Confidential", "covers": [], "may_see": [], "passage": "Confidential"},
    {"area": "Personal data", "covers": ["names of staff", "emails", "pay"], "may_see": [], "passage": "Personal data"},
    {"area": "Internal", "may_see": ["all staff"], "passage": "Internal"},
    {"area": "Public", "may_see": ["everyone"], "passage": "Public"},
    {"area": "summary figures", "may_see": ["committee"], "passage": "summary figures to the committee"},
    {"area": "rows", "may_see": ["owner"], "passage": "rows to the owner"}]}

PEOPLE_PRECISION = [
    {"name": "Risk Analyst", "role": "x", "passage": "the Risk Analyst"},
    {"name": "Mei Tan", "role": "CFO", "passage": "Mei Tan is CFO"}]


def test_precision_pass_on_classification_policy(plane):
    stated(plane, {"people.mei-tan.name": "Mei Tan", "people.hr.name": "HR", "people.finance.name": "Finance"})
    areas_precision_with_hr = {**AREAS_PRECISION, "restricted": [
        {"area": "Restricted", "covers": ["pay", "bonus", "payroll file", "payroll sop"], "may_see": ["HR", "Finance"], "passage": "Restricted"},
        {"area": "Confidential", "covers": [], "may_see": ["HR"], "passage": "Confidential"},
        {"area": "Personal data", "covers": ["names of staff", "emails", "pay"], "may_see": ["HR"], "passage": "Personal data"},
        {"area": "Internal", "may_see": ["all staff"], "passage": "Internal"},
        {"area": "Public", "may_see": ["everyone"], "passage": "Public"},
        {"area": "summary figures", "may_see": ["committee"], "passage": "summary figures to the committee"},
        {"area": "rows", "may_see": ["owner"], "passage": "rows to the owner"}]}
    m = model(**areas_precision_with_hr, people=PEOPLE_PRECISION)
    reader.add_upload(plane, 7, "Mei Tan", "classification.md", POLICY_PRECISION, m)
    prof = read(plane, HR)

    # Check restricted areas: should have Restricted, Confidential, Personal data (3 total)
    areas = prof["governance"]["restricted_areas"]
    assert set(areas.keys()) == {"restricted", "confidential", "personal-data"}, f"Got areas: {list(areas.keys())}"

    # Restricted area should have covers and may_see with role names
    assert areas["restricted"]["area"]["value"] == "Restricted"
    assert set(areas["restricted"]["covers"]["value"]) == {"pay", "bonus", "payroll file", "payroll sop"}
    assert set(areas["restricted"]["may_see"]["value"]) == {"HR", "Finance"}

    # Confidential and Personal data should be present
    assert areas["confidential"]["area"]["value"] == "Confidential"
    assert areas["personal-data"]["area"]["value"] == "Personal data"

    # summary figures and rows should NOT be areas, but visibility default findings
    assert "summary-figures" not in areas
    assert "rows" not in areas

    # Check findings: visibility defaults and open to all
    findings = prof["inputs"]["g7"]["findings"]["value"]
    visibility_defaults = [f for f in findings if f["kind"] == "visibility default"]
    role_mentions = [f for f in findings if f["kind"] == "role mentioned"]
    open_to_all = [f for f in findings if f["kind"] == "open to all"]

    assert len(visibility_defaults) == 2, f"Expected 2 visibility defaults, got {len(visibility_defaults)}: {visibility_defaults}"
    assert {f["text"] for f in visibility_defaults} == {"summary figures", "rows"}

    # Risk Analyst should be recorded as a role mention
    assert len(role_mentions) >= 1
    assert any("Risk Analyst" in f["text"] for f in role_mentions), f"No 'Risk Analyst' in role mentions: {role_mentions}"

    # Internal and Public should be open to all findings
    assert any(f["text"] == "Internal" for f in open_to_all)
    assert any(f["text"] == "Public" for f in open_to_all)
