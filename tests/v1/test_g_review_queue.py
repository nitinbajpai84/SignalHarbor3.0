"""G review queue (W4, W10 method 1): confidence scoring, holding below the signed minimum, confirm, correct, and the saved regression case.
Synthetic data only."""
import json

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_loads as L, v3_pdf as V, v3_review as R, wh
from sh_platform.v1.e1_write import org_id


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


PAIRS = [{"label": "Net asset value", "value": "USD 1,000.00", "page": 2, "line": 5, "quote": "Net asset value: USD 1,000.00"},
         {"label": "Units", "value": "10", "page": 2, "line": 6, "quote": "Units held 11"}]  # the second value is not in its quote


def sign(plane, minimum):
    with wh.connect(plane) as con:
        org, uid, rid = org_id(plane), wh.new_id(), wh.new_id()
        con.execute("insert into business_rules (id, organization_id, rule_code, rule_type, owner_user_id) values (?,?,?,?,?)", [rid, org, R.RULE, "policy", wh.new_id()])
        con.execute("insert into rule_versions (id, organization_id, business_rule_id, version_number, definition_text, parameters, effective_from, approval_status)"
                    " values (?,?,?,?,?,?,?,?)", [uid, org, rid, 1, "Fields below this confidence are held", json.dumps({"min": minimum}), "2026-04-01", "approved"])


def test_scoring_follows_the_three_levels():
    assert R.score(known=True) == "high" and R.score(agree=True, checks_ok=True) == "high"
    assert R.score(agree=True) == "medium" and R.score() == "medium"
    assert R.score(agree=False) == R.score(checks_ok=False) == R.score(known=True, picture=True) == "low"


def test_the_pdf_reader_scores_each_field():
    figs = {f["label"]: f["confidence"] for f in L.pdf_figures(PAIRS)}
    assert figs == {"Net asset value": "high", "Units": "low"}
    assert {f["confidence"] for f in L.pdf_figures(PAIRS[:1], picture=True)} == {"low"}
    assert L.pdf_figures(PAIRS[:1], agree={"Net asset value": False})[0]["confidence"] == "low"


def test_low_confidence_is_held_and_default_minimum_is_high(plane):
    assert R.minimum(plane) == "high"
    did = wh.new_id()
    L.write(plane, did, L.pdf_figures(PAIRS), layout="acme statement")
    with wh.connect(plane) as con:
        got = dict(con.execute("select field_name, review_status from extracted_fields where document_id = ?", [did]).fetchall())
    assert got == {"Net asset value": "confirmed", "Units": "held"}
    q = R.queue(plane)
    assert [(i["field"], i["quote"], i["page"]) for i in q] == [("Units", "Units held 11", 2)]


def test_a_signed_lower_minimum_lets_medium_through(plane):
    sign(plane, "medium")
    assert R.minimum(plane) == "medium" and R.status_for(plane, "medium") == "confirmed" and R.status_for(plane, "low") == "held"


def test_confirm_releases_and_correct_saves_a_regression_case(plane):
    did = wh.new_id()
    L.write(plane, did, L.pdf_figures(PAIRS), layout="acme statement")
    fid = R.queue(plane)[0]["id"]
    assert R.resolve(plane, fid, "Grace Tan", "11")["status"] == "corrected"
    with wh.connect(plane) as con:
        row = con.execute("select review_status, value_text, value_numeric, reviewed_by, reviewed_at from extracted_fields where id = ?", [fid]).fetchone()
    assert row[0] == "corrected" and row[1] == "11" and float(row[2]) == 11 and row[4] is not None
    log = [json.loads(x) for x in plane.path("v3", "review_log.jsonl").read_text().splitlines()]
    assert log[0]["by"] == "Grace Tan" and log[0]["status"] == "corrected" and log[0]["at"]
    case = [json.loads(x) for x in plane.path("v3", "corrections.jsonl").read_text().splitlines()]
    assert [(c["field"], c["wrong"], c["right"], c["layout"], c["by"]) for c in case] == [("Units", "10", "11", "acme statement", "Grace Tan")]
    assert R.queue(plane) == []
    with pytest.raises(KeyError):
        R.resolve(plane, fid, "Grace Tan")  # already released


def test_confirm_keeps_the_value_and_saves_no_case(plane):
    did = wh.new_id()
    L.write(plane, did, L.pdf_figures(PAIRS))
    fid = R.queue(plane)[0]["id"]
    assert R.resolve(plane, fid, "Grace Tan")["status"] == "confirmed"
    assert not plane.path("v3", "corrections.jsonl").exists()


def test_a_known_layout_read_is_high_unless_a_check_fails():
    layout = {"fields": [{"name": "nav", "format": "number", "where_usually": "NAV"}], "checks": [], "key": "nav"}
    assert R.score(known=True, checks_ok=None) == "high" and R.score(known=True, checks_ok=False) == "low"
    assert V.read_values  # the reader sets values[name]["confidence"] with this score
