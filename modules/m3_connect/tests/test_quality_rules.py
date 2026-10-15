"""IC-0d: scan facts become quality rules on the measure's catalogue entry, as proposals beside the signed catalogue.
Two industries, an empty company, a restricted source. Synthetic data only."""
import json

import pytest
from datetime import date, timedelta

from m3_kit import CHARTER, person, restrict, signed_baseline
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import profile as P
from modules.m3_connect.domain import quality_rules as Q
from modules.m3_connect.domain import sources as S

AT = "2026-10-06T09:00:00+00:00"
PERIOD = {"from": "2026-09-01", "to": "2026-09-30", "label": "September 2026"}
ADMIN = I.Viewer("Head Test", frozenset({"company_admin"}))
OUTSIDER = I.Viewer("Outsider Test", frozenset({"analyst"}))


def scan_profile(measure="K01"):
    """40 funds, 20 with no fees, the file stopping on 22 September while the period ends on the 30th."""
    start = date(2026, 9, 1)
    rows = [[f"Fund {i}", "" if i % 2 else "1.5", (start + timedelta(days=i % 22)).isoformat()] for i in range(40)]
    prof = P.profile_table(["Fund", "Fees Charged", "As at"], rows)
    prof["columns"][1]["field_id"] = "F001"
    table = {"file": "ab12cd34_custodian.csv", "table_id": "T01", "name": "Custodian file", **prof}
    gaps = P.gaps_for("S01", [table], [{"field_id": "F001", "name": "Fees Charged", "table_id": "T01", "measures": [measure]}], PERIOD)
    return {"tables": [table], "gaps": gaps, "period": PERIOD}


class Plane:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return self.root.joinpath(*parts)


BID = "b" * 32


def test_scan_facts_become_rules_with_provenance():
    rules = Q.rules_for_source(scan_profile(), "S01", PERIOD, AT)["K01"]
    fill = next(r for r in rules if r["kind"] == Q.FILL)
    assert fill["column"] == "Fees Charged" and fill["figure"] == {"fill": 0.5, "empty": 20, "of": 40}
    assert "50%" in fill["text"] and fill["provenance"] == {"from": "the scan of custodian.csv", "at": AT}
    gap = next(r for r in rules if r["kind"] == Q.PERIOD)
    assert gap["figure"] == {"data_to": "2026-09-22", "period_to": "2026-09-30"} and gap["by"] == "Lens" and gap["state"] == "proposal"


def test_benchmark_missing_is_a_rule_and_a_given_one_is_not():
    got = Q.benchmark_rules({"file": None, "measures": {"K02": {"figure": 1}}}, ["K01", "K02"], AT)
    assert list(got) == ["K01"] and got["K01"][0]["kind"] == Q.BENCHMARK and got["K01"][0]["source_id"] is None


def test_scan_again_replaces_lens_never_a_person(tmp_path):
    plane = Plane(tmp_path)
    Q.replace(plane, BID, "S01", Q.rules_for_source(scan_profile(), "S01", PERIOD, AT))
    doc = Q.read(plane, BID)
    doc["K01"][0] = {**doc["K01"][0], "state": "edited", "by": "Mei Test", "text": "Fees are optional here"}
    (tmp_path / "intents" / "m2_baseline" / BID / "quality_rules.json").write_text(json.dumps({"rules": doc}))
    Q.replace(plane, BID, "S01", {})  # the next scan finds nothing wrong
    left = Q.read(plane, BID)["K01"]
    assert [r["by"] for r in left] == ["Mei Test"] and left[0]["text"] == "Fees are optional here"
    Q.replace(plane, BID, "S01", Q.rules_for_source(scan_profile(), "S01", PERIOD, AT))  # and again with faults: Lens's are not doubled
    assert sorted(r["by"] for r in Q.read(plane, BID)["K01"]).count("Lens") == 2


@pytest.mark.parametrize("company", ["m3-a", "m3-b"])  # two industries
def test_rules_follow_the_measures_a_source_feeds(world, company):
    signed_baseline(world, company)
    plane = world.plane(company)
    outcome = I.latest_signed_baseline(plane)
    full = I.read_inputs(plane, outcome, CHARTER, ADMIN)
    sid = I._t(full["sources"][0].get("Source ID"))
    full["tables"] = [{"Item ID": {"value": "T01", "mark": "stated"}, "Source ID": {"value": sid, "mark": "stated"}, "Related KPIs": {"value": "K1, K2", "mark": "stated"}}]  # the seeded catalogue has a source and no table yet
    fed = S.measures_fed(full, sid)
    assert Q.record_scan(plane, outcome, sid, scan_profile(fed[0]), AT) >= 2
    rules = Q.read(plane, outcome["baseline_id"])
    assert set(Q.visible(rules, full)) == set(rules)
    restrict(world, company, fed[0], ["Somebody Else"])  # now personal: only the named person sees it (A-069: the admin passes only while nobody is named)
    assert fed[0] not in Q.visible(rules, I.read_inputs(plane, outcome, CHARTER, OUTSIDER))
    assert fed[0] not in Q.visible(rules, I.read_inputs(plane, outcome, CHARTER, ADMIN))
    assert fed[0] in Q.visible(rules, I.read_inputs(plane, outcome, CHARTER, I.Viewer("Somebody Else", frozenset({"analyst"}))))


def test_an_empty_company_gets_no_rules(world):
    assert Q.record_scan(world.plane("m3-empty"), I.latest_signed_baseline(world.plane("m3-empty")), "S01", scan_profile(), AT) == 0


def test_a_restricted_source_gives_no_rule_to_someone_outside_its_list():
    rules = {"K1": [{"source_id": "S01", "text": "a"}, {"source_id": None, "text": "b"}]}
    seen = {"measures": [{"id": "K1", "restricted": False}], "sources": []}  # read_inputs left S01 out for this reader
    assert Q.visible(rules, seen) == {"K1": [{"source_id": None, "text": "b"}]}
    assert Q.visible(rules, {**seen, "sources": [{"Source ID": {"value": "S01", "mark": "stated"}}]}) == rules


def test_an_upload_records_rules_the_screen_and_the_catalogue_show(world):
    from m3_kit import BASE, BID
    from modules.m2_baseline.domain import catalogue as C
    from modules.m2_baseline.store import catalogue as SC
    from test_m3_intake import SOURCES, demo_world, upload, url
    c, aid = demo_world(world)
    c.post(url(aid, "/requests"))
    for sid, _, name in SOURCES[:2]:
        assert upload(c, aid, sid, name).status_code == 200
        assert upload(c, aid, sid, name).status_code == 200  # again: replaced, never doubled
    plane = world.plane("m3-a")
    rules = Q.read(plane, BID)
    assert [r["figure"] for r in rules["K15"]] == [{"fill": 0.5, "empty": 20, "of": 40}] and rules["K15"][0]["source_id"] == "S01"
    assert [(r["kind"], r["figure"]["data_to"]) for r in rules["K12"]] == [(Q.PERIOD, "2026-09-22")] and len(rules["K10"]) == 1
    shown = c.get(f"{BASE}/assessments/{aid}/intake/sources/S01/profile").json()
    assert set(shown["quality_rules"]) == {"K15", "K10"}
    # module 2 reads the same file beside the signed catalogue and shows it under the measure
    Q.replace(plane, BID, "S01", {"K1": [{**rules["K15"][0], "id": "x"}]})
    cat = SC.read_catalogue(plane, BID)
    row = next(r for r in cat["kpis"] if C.row_id("kpis", r) == "K1")
    assert "Fees Charged" in C.text_of(row[C.QUALITY_RULES])
