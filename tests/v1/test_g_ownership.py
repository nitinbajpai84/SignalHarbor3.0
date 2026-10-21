"""W3 ownership look-through (assumption A61): the entity_ownership table, the register reader, the rule checks and the recipe ownership_lookthrough.

Real: the six-month office loaded through the real loader (as test_w1b_hold.py), the recipe and its tie-out. Expected numbers come from answer_keys.yaml (uc-101-ownership),
never typed here. The cases that change the data edit the warehouse inside a transaction that is rolled back. The checks (sums, overlap, circle) are also run on small
registers written in the test. Synthetic data only."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import v3_pack_readers_family as F
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh
from tests.v1 import test_w2_loader as W

CARD = "uc-101-ownership"
TODAY = date(2026, 10, 13)
D = date


@pytest.fixture(scope="module")
def office(tmp_path_factory) -> W.Loaded:
    tmp = tmp_path_factory.mktemp("gown")
    box = W.office_dropbox(tmp)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    o = W.Loaded(plane, L.load_plane(plane, box))
    yield o
    o.con.close()


def k() -> dict:
    return W.key(CARD)


def pick(rows, holder, instrument, asset_type="commitment", as_at=TODAY):
    return [r for r in rows if r["holder"] == holder and r["instrument"] == instrument and r["asset_type"] == asset_type and r["as_at"] == as_at]


def row(owner, owned, pct, vf, vt=None):
    return dict(owner=owner, owned=owned, pct=Decimal(pct), valid_from=vf, valid_to=vt)


def types(problems):
    return sorted(t for t, _, _ in problems)


# ---- the model and the reader ------------------------------------------------------------------------------------------------------------

def test_the_register_is_loaded_one_row_per_period_and_the_clean_one_raises_nothing(office):
    assert office.report["ownership_register"]["rows"] == 9 and not office.report["ownership_register"]["flagged"]
    got = office.rows("select owner_kind, ownership_pct, valid_from, valid_to, owned_entity_id, owner_entity_id, owner_family_member_id from entity_ownership")
    assert len(got) == 9 and {r["owner_kind"] for r in got} == {"entity", "family_member"}
    assert all((r["owner_entity_id"] is None) == (r["owner_kind"] == "family_member") and (r["owner_family_member_id"] is None) == (r["owner_kind"] == "entity") for r in got)
    assert office.one("select count(*) from exceptions where exception_type like 'ownership%'") == 0
    assert office.one("select count(*) from family_members where member_name = 'Mei Chen'") == 1  # the principal is no allowance holder: the register adds her
    assert office.one("select count(*) from entity_ownership where source_document_id is null") == 0


def test_the_register_agrees_with_the_trust_deed(office):
    deed = {r["value_text"]: float(r["value_numeric"]) * 100 for r in office.rows(
        "select f.value_text, f.value_numeric from documents d join extracted_fields f on f.document_id = d.id where d.document_type = 'trust_deed' and f.field_name = 'beneficiary_share'")}
    reg = {r["member_name"]: float(r["ownership_pct"]) for r in office.rows(
        "select m.member_name, o.ownership_pct from entity_ownership o join family_members m on m.id = o.owner_family_member_id join legal_entities e on e.id = o.owned_entity_id "
        "where e.entity_code = 'EG-TRUST'")}
    assert reg == deed and sum(reg.values()) == 100


# ---- the recipe: the multiplication ------------------------------------------------------------------------------------------------------

def test_the_recipe_is_built_and_its_tie_out_holds(office):
    r = R.recipe("ownership_lookthrough")
    assert r["status"] == "ready" and r["tie_out"] and R.recipe("lookthrough_exposure")["cards"] == [69]  # card 69's recipe keeps its name
    rows = office.run("ownership_lookthrough")  # renders, checks the tables it reads, builds, runs the tie-out
    assert rows and {x["holder_kind"] for x in rows} == {"family_member", "entity"}


def test_a_persons_share_is_the_percentages_multiplied_down_the_chain(office):
    e, rows = k()["fund"], office.run("ownership_lookthrough")
    x = k()
    mei = pick(rows, "Mei Chen", e)[0]
    assert float(mei["effective_pct"]) == x["mei_effective_pct"] and float(mei["share_value"]) == x["mei_share"] and float(mei["value"]) == x["commitment"]
    assert mei["held_in"] == x["held_by"] and mei["chain"] == "Mei Chen > Evergreen Holdings" and mei["hops"] == 1 and mei["indirect"]
    for b in x["trust_beneficiaries"]:  # 60 percent of Holdings, times the deed's share of the Trust
        r = pick(rows, b["person"], e)[0]
        assert (float(r["effective_pct"]), float(r["share_value"])) == (b["effective_pct"], b["share"])
        assert r["chain"] == f"{b['person']} > Evergreen Family Trust > Evergreen Holdings" and r["hops"] == 2


def test_what_the_trust_holds_indirectly(office):
    x, rows = k(), office.run("ownership_lookthrough")
    t = pick(rows, "Evergreen Family Trust", x["fund"])[0]
    assert (float(t["effective_pct"]), float(t["share_value"]), t["indirect"]) == (x["trust_effective_pct_of_holdings"], x["trust_share"], True)
    own = pick(rows, "Evergreen Holdings", x["fund"])[0]  # the entity's own asset is not indirect and counts in full
    assert float(own["effective_pct"]) == 100 and not own["indirect"] and own["hops"] == 0
    behind_b = {r["holder"] for r in rows if r["held_in"] == "Entity B" and r["as_at"] == TODAY}  # Holdings owns all of Entity B: every owner above it reaches it
    assert behind_b == set(x["holders_of_entity_b"]) | {"Entity B"}
    one = [r for r in rows if r["holder"] == "Evergreen Holdings" and r["held_in"] == "Entity B" and r["as_at"] == TODAY]
    assert one and all(float(r["effective_pct"]) == 100 and r["hops"] == 1 for r in one)


def test_positions_commitments_and_cash_all_follow_the_chain(office):
    rows = [r for r in office.run("ownership_lookthrough") if r["as_at"] == TODAY]
    assert {r["asset_type"] for r in rows} == {"position", "cash", "commitment"}
    for a in ("position", "cash", "commitment"):  # a person's rows add to the entity's assets times what the person holds of it
        for who, pct in (("Mei Chen", 0.40), ("Lin Chen", 0.24)):
            mine = [r for r in rows if r["holder"] == who and r["asset_type"] == a and r["held_in"] == "Evergreen Holdings"]
            assert mine and all(float(r["share_value"]) == pytest.approx(float(r["value"]) * pct, abs=0.006) for r in mine)


# ---- the recipe: as at a date ----------------------------------------------------------------------------------------------------------------

def test_as_at_the_end_of_june_the_shares_were_the_earlier_ones(office):
    x, rows = k(), office.run("ownership_lookthrough")
    june = pick(rows, "Mei Chen", x["fund"], as_at=D(2026, 6, 30))[0]
    assert (float(june["effective_pct"]), float(june["share_value"])) == (x["mei_effective_pct_at_30_jun"], x["mei_share_at_30_jun"])
    assert float(pick(rows, "Evergreen Family Trust", x["fund"], as_at=D(2026, 6, 30))[0]["effective_pct"]) == 55
    assert float(pick(rows, "Lin Chen", x["fund"], as_at=D(2026, 6, 30))[0]["effective_pct"]) == pytest.approx(22)  # 55 percent times 40


def test_the_answer_line_says_the_latest_date(office):
    from sh_platform.v1 import v3_figures as FG
    said = FG.say(R.recipe("ownership_lookthrough"), [r for r in office.run("ownership_lookthrough") if r["holder"] == "Mei Chen" and r["asset_type"] == "commitment"])
    assert said and "13 Oct 2026" in said and "Mei Chen" in said and "Evergreen Holdings" in said and "30 Jun" not in said


# ---- the recipe: a circle and a gap in the warehouse (rolled back) ---------------------------------------------------------------------------------

def _plant(con, owner_code, owned_code, pct, vf="2026-07-01", vt=None):
    con.execute("insert into entity_ownership select uuid()::varchar, organization_id, source_record_id, source_document_id, source_page, received_at, recorded_at, null, 'entity', "
                "(select id from legal_entities where entity_code = ?), null, (select id from legal_entities where entity_code = ?), ?, ?::date, ?::date "
                "from entity_ownership limit 1", [owner_code, owned_code, pct, vf, vt])


def test_a_circle_does_not_loop_the_recipe_and_the_checks_name_it(office):
    con = office.con
    con.execute("begin")
    try:
        _plant(con, "EG-B", "EG-HOLD", 10)  # Holdings owns Entity B, Entity B owns 10 percent of Holdings
        rows = office.run("ownership_lookthrough")
        assert rows and max(r["hops"] for r in rows) <= 8
        reg = [row(r["o"], r["w"], r["p"], r["f"], r["t"]) for r in office.rows(
            "select coalesce(m.member_name, a.entity_name) o, b.entity_name w, x.ownership_pct p, x.valid_from f, x.valid_to t from entity_ownership x join legal_entities b on b.id = x.owned_entity_id "
            "left join legal_entities a on a.id = x.owner_entity_id left join family_members m on m.id = x.owner_family_member_id")]
        problems = F.ownership_problems(reg, TODAY)
        assert "ownership_cycle" in types(problems) and "ownership_gap" in types(problems)  # the circle, and Holdings now adds to 110 percent
        assert any("Evergreen Holdings > Entity B > Evergreen Holdings" in t or "Entity B > Evergreen Holdings > Entity B" in t for _, t, _ in problems)
    finally:
        con.execute("rollback")


def test_a_period_that_ends_before_the_date_is_not_counted(office):
    con = office.con
    con.execute("begin")
    try:
        _plant(con, "EG-B", "EG-HOLD", 10, "2026-07-01", "2026-07-31")  # ended: neither at the end of June nor at 13 Oct
        x, rows = k(), office.run("ownership_lookthrough")
        assert float(pick(rows, "Mei Chen", x["fund"])[0]["share_value"]) == x["mei_share"]
        assert not [r for r in rows if r["holder"] == "Entity B" and r["held_in"] == "Evergreen Holdings" and r["as_at"] == TODAY]
    finally:
        con.execute("rollback")


# ---- the rule checks -----------------------------------------------------------------------------------------------------------------------------

def test_the_owners_of_an_entity_add_to_one_hundred_or_the_gap_is_flagged():
    ok = [row("A", "X", "60", D(2020, 1, 1)), row("B", "X", "40", D(2020, 1, 1))]
    assert F.ownership_problems(ok, TODAY) == []
    gap = F.ownership_problems([row("A", "X", "60", D(2020, 1, 1)), row("B", "X", "30", D(2020, 1, 1))], TODAY)
    assert types(gap) == ["ownership_gap"] and "90 percent" in gap[0][1] and "10 percent has no owner" in gap[0][2]
    over = F.ownership_problems([row("A", "X", "60", D(2020, 1, 1)), row("B", "X", "50", D(2020, 1, 1))], TODAY)
    assert types(over) == ["ownership_gap"] and "110 percent" in over[0][1]


def test_the_sum_is_as_at_the_date_so_a_handover_inside_one_day_is_not_a_gap():
    swap = [row("A", "X", "60", D(2020, 1, 1), D(2026, 6, 30)), row("A", "X", "50", D(2026, 7, 1)), row("B", "X", "40", D(2020, 1, 1), D(2026, 6, 30)), row("B", "X", "50", D(2026, 7, 1))]
    assert F.ownership_problems(swap, TODAY) == [] and F.ownership_problems(swap, D(2026, 6, 30)) == []
    hole = swap[:1] + swap[2:]  # nothing in force on 13 Oct for A
    assert [t for t, _, _ in F.ownership_problems(hole, TODAY)] == ["ownership_gap"]


def test_circular_ownership_is_found_whatever_its_length():
    two = [row("A", "B", "100", D(2020, 1, 1)), row("B", "A", "100", D(2020, 1, 1))]
    assert "ownership_cycle" in types(F.ownership_problems(two, TODAY))
    three = [row("A", "B", "100", D(2020, 1, 1)), row("B", "C", "100", D(2020, 1, 1)), row("C", "A", "100", D(2020, 1, 1))]
    cyc = [p for p in F.ownership_problems(three, TODAY) if p[0] == "ownership_cycle"]
    assert len(cyc) == 1 and "A > B > C > A" in cyc[0][1]  # said once, not once for each of its members
    chain = [row("A", "B", "100", D(2020, 1, 1)), row("B", "C", "100", D(2020, 1, 1))]
    assert "ownership_cycle" not in types(F.ownership_problems(chain, TODAY))
    later = [row("A", "B", "100", D(2020, 1, 1)), row("B", "A", "100", D(2030, 1, 1))]  # a circle that only starts in 2030 is not one today, but the register has it
    assert "ownership_cycle" in types(F.ownership_problems(later, TODAY))
    gone = [row("A", "B", "100", D(2020, 1, 1)), row("B", "A", "100", D(2020, 1, 1), D(2020, 12, 31))]
    assert "ownership_cycle" in types(F.ownership_problems(gone, TODAY))  # it ended in 2020 and was still a circle in 2020: said, so the register is corrected


def test_two_periods_of_one_holder_must_not_overlap():
    over = [row("A", "X", "50", D(2020, 1, 1), D(2026, 7, 31)), row("A", "X", "60", D(2026, 7, 1))]
    got = [p for p in F.ownership_problems(over, TODAY) if p[0] == "ownership_overlap"]
    assert len(got) == 1 and "A in X" in got[0][1]
    clean = [row("A", "X", "50", D(2020, 1, 1), D(2026, 6, 30)), row("A", "X", "60", D(2026, 7, 1))]
    assert "ownership_overlap" not in types(F.ownership_problems(clean, TODAY))
    assert "ownership_overlap" not in types(F.ownership_problems([row("A", "X", "50", D(2020, 1, 1)), row("A", "Y", "50", D(2020, 1, 1))], TODAY))


# ---- the reader raises the checks as exceptions (cards) --------------------------------------------------------------------------------------------

class Fake:
    """Just enough of the Office for fam_ownership_register: its own rows and exceptions, the real note/exception methods."""
    note, exception = PK.Office.note, PK.Office.exception

    def __init__(self, root: Path):
        self.root, self.today, self.report, self.rows = root, TODAY, {}, {}
        self.con = duckdb.connect(":memory:")
        self.con.execute("create table entity_ownership (id varchar)")
        self.ent = {"EG-HOLD": "ent-hold", "EG-TRUST": "ent-trust", "EG-B": "ent-b"}
        self.md = {"entities": {"EG-HOLD": "Evergreen Holdings", "EG-TRUST": "Evergreen Family Trust", "EG-B": "Entity B"}}
        self.n = 0

    def add(self, table, **kw):
        self.n += 1
        self.rows.setdefault(table, []).append({"id": f"{table}-{self.n}", **kw})
        return f"{table}-{self.n}"

    def doc(self, *a, **kw):
        return "doc-1"

    def record(self, *a, **kw):
        return "rec-1"


def _register(tmp_path, lines) -> Fake:
    (tmp_path / "reference").mkdir()
    with open(tmp_path / "reference" / "ownership_register.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["owner_kind", "owner", "owned_entity", "ownership_pct", "valid_from", "valid_to", "source"])
        w.writerows(lines)
    fake = Fake(tmp_path)
    F.fam_ownership_register(fake)
    return fake


def test_the_reader_turns_a_gap_a_circle_and_an_overlap_into_exceptions(tmp_path):
    fake = _register(tmp_path, [
        ["entity", "Evergreen Family Trust", "Evergreen Holdings", "55", "2021-03-15", "", "register"],
        ["family_member", "Mei Chen", "Evergreen Holdings", "35", "2021-03-15", "", "register"],  # with the 5 percent below: Holdings adds to 95
        ["entity", "Evergreen Holdings", "Entity B", "100", "2021-03-15", "", "register"],
        ["entity", "Entity B", "Evergreen Holdings", "5", "2021-03-15", "", "register"],  # a circle
        ["entity", "Evergreen Holdings", "Entity B", "100", "2026-01-01", "", "register"]])  # overlaps the first period (and Entity B now adds to 200)
    assert sorted(e["exception_type"] for e in fake.rows["exceptions"]) == ["ownership_cycle", "ownership_gap", "ownership_gap", "ownership_overlap"]  # Holdings 95, Entity B 200
    assert len(fake.rows["entity_ownership"]) == 5 and fake.report["ownership_register"]["flagged"]
    assert all(e["title"] and e["description"] for e in fake.rows["exceptions"])


def test_the_reader_sets_aside_an_owner_the_office_does_not_know_and_writes_standing_data_once(tmp_path):
    fake = _register(tmp_path, [["entity", "Phantom Ltd", "Evergreen Holdings", "10", "2021-03-15", "", "register"], ["family_member", "Mei Chen", "Nowhere Inc", "10", "2021-03-15", "", "r"],
                                ["family_member", "Mei Chen", "Evergreen Holdings", "ten", "2021-03-15", "", "r"], ["family_member", "Mei Chen", "Evergreen Holdings", "100", "2021-03-15", "", "r"]])
    assert len(fake.rows["entity_ownership"]) == 1 and len(fake.report["ownership_register"]["flagged"]) == 3
    fake.con.execute("insert into entity_ownership values ('x')")  # already on record: not written again
    before = len(fake.rows["entity_ownership"])
    F.fam_ownership_register(fake)
    assert len(fake.rows["entity_ownership"]) == before and any("already on record" in f for f in fake.report["ownership_register"]["flagged"])
