"""E6b: the evaluation runner works with stubbed cards; missing cards are 'not built'; a failing built suite blocks the gate."""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import eval_v2 as E  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from sh_platform.v1.e1_write import org_id  # noqa: E402

FUND = "00000000-0000-0000-0000-00000000000a"
LE = "00000000-0000-0000-0000-0000000000e1"
PF = "00000000-0000-0000-0000-0000000000b1"
SRC = "00000000-0000-0000-0000-0000000000c1"


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    p = PlaneStore(tmp_path).create("evalco")
    with wh.connect(p) as con:
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?, ?, 'Evergreen Growth I', 'fund', now())",
                    [FUND, org_id(p)])
    return p


def stub(monkeypatch, name, **fns):
    m = types.ModuleType(f"sh_platform.v1.{name}")
    m.__dict__.update(fns)
    monkeypatch.setitem(sys.modules, f"sh_platform.v1.{name}", m)


def hide(monkeypatch, *names):
    for n in names:
        monkeypatch.setitem(sys.modules, f"sh_platform.v1.{n}", None)  # import raises ImportError with name set


def guard(refuse_all=False):
    cases = E.fixture("safety_requests.json")
    bad = set(cases["refused"])
    return dict(check_request=lambda t: {"refused": True} if (t in bad or refuse_all) else None,
                check_action=lambda a, t: {"refused": True})


def test_missing_cards_are_not_built(plane, monkeypatch):
    hide(monkeypatch, "e3_calc", "e1_asof", "e5_brief", "e3_recon", "e2_extract", "e2_match", "e4_guard")
    res = E.run(plane, out=lambda *_: None)
    assert {r["status"] for r in res.values()} == {"not built"}
    assert E.gate(res, out=lambda *_: None) == 0


def test_safety_passes_with_a_good_guard(plane, monkeypatch):
    stub(monkeypatch, "e4_guard", **guard())
    stub(monkeypatch, "e2_intake", register=lambda p, path, v: path)  # the injection statement is read; it must change nothing
    stub(monkeypatch, "e2_extract", extract=lambda p, doc, v: [])
    res = E.run(plane, ["safety"], out=lambda *_: None)
    assert res["safety"]["status"] == "pass" and len(res["safety"]["cases"]) >= 41


def test_over_refusing_guard_blocks_the_gate(plane, monkeypatch):
    stub(monkeypatch, "e4_guard", **guard(refuse_all=True))
    res = E.run(plane, ["safety"], out=lambda *_: None)
    assert res["safety"]["status"] == "fail"
    assert E.gate(res, out=lambda *_: None) == 1


def test_identity_with_stub(plane, monkeypatch):
    table = {"EG Growth Fund I": ("approved", FUND), "evergreen growth i.": ("proposed", FUND), "Evergreen Growth 1": ("proposed", FUND),
             "Evergreen Growth I LP Class I": ("proposed", FUND), "Evergreen Growth II": ("unknown", None), "Harbour Quarry Partners": ("unknown", None)}
    with wh.connect(plane) as con:
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type) values (?, ?, 'manager_email', 'Manager email', 'manager')",
                    [SRC, org_id(plane)])
    stub(monkeypatch, "e2_match", resolve=lambda p, n, s: {"status": table[n][0], "instrument_id": table[n][1], "candidates": []})
    res = E.run(plane, ["identity"], out=lambda *_: None)
    assert res["identity"]["status"] == "pass", res["identity"]["cases"]


def test_calculation_totals_with_stub(plane, monkeypatch):
    with wh.connect(plane) as con:
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?, ?, 'E1', 'E', 'USD')", [LE, org_id(plane)])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?, ?, ?, 'P1', 'P', 'USD')", [PF, org_id(plane), LE])
    from datetime import datetime
    stub(monkeypatch, "e3_calc", CALC_VERSION="v1",
         portfolio_value=lambda p, pid, d, cutoff, ccy: {"total": 57600000 if cutoff.year == 2026 and cutoff.month == 10 and cutoff.day == 3 else 57780000})
    res = E.run(plane, ["calculation"], out=lambda *_: None)
    assert res["calculation"]["status"] == "pass", res["calculation"]["cases"]


def test_crashing_suite_is_a_failure(plane, monkeypatch):
    stub(monkeypatch, "e4_guard", check_request=lambda t: 1 / 0, check_action=lambda a, t: None)
    assert E.run(plane, ["safety"], out=lambda *_: None)["safety"]["status"] == "fail"


def test_extraction_reads_the_real_e2e_expected_shape(plane, monkeypatch):
    fields = {"nav": {"field_name": "nav", "value_text": "10180000.00", "value_numeric": 10180000.0, "page_number": 2},
              "units": {"field_name": "units", "value_text": "98431.2", "value_numeric": 98431.2, "page_number": 2},
              "status_label": {"field_name": "status_label", "value_text": "final", "value_numeric": None, "page_number": 2},
              "call_amount": {"field_name": "call_amount", "value_text": "500000.00", "value_numeric": 500000.0, "page_number": 1},
              "currency": {"field_name": "currency", "value_text": "USD", "value_numeric": None, "page_number": 1}}
    stub(monkeypatch, "e2_intake", register=lambda p, path, v: path)
    stub(monkeypatch, "e2_extract", extract=lambda p, doc, v: list(fields))
    monkeypatch.setattr(E, "_field", lambda p, fid: fields[fid])
    cases = E.suite_extraction(plane)
    names = {c[0] for c in cases}
    assert "fund_a_statement_30_sep_final: nav" in names and "capital_call_notice: call_amount" in names
    final = {c[0]: c[1] for c in cases if c[0].startswith("fund_a_statement_30_sep_final")}
    assert final == {"fund_a_statement_30_sep_final: nav": True, "fund_a_statement_30_sep_final: units": True,
                     "fund_a_statement_30_sep_final: status_label": True}


def test_retrieval_maps_names_to_keys_and_absent_line_says_so(plane, monkeypatch):
    with wh.connect(plane) as con:
        con.execute("insert into reports (id, organization_id, report_code, report_name) values (?, ?, 'r', 'R')", [FUND, org_id(plane)])
        con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status, issued_at)"
                    " values (?, ?, ?, ?, '2026-09-30', now(), 'issued', now())", [PF, org_id(plane), FUND, LE])

    def explain(p, v, rv, key):
        if key != "holding_value|pf|a":
            raise LookupError("This line is not in the report, or you may not see it.")
        return {"answer": "The amended statement: 10,000,000.00 USD then, 10,180,000.00 USD now."}

    stub(monkeypatch, "e5_brief", brief=lambda p, v, rv: {"lines": [{"label": "Evergreen Growth I", "line_key": "holding_value|pf|a"}]}, explain=explain)
    res = E.run(plane, ["retrieval"], out=lambda *_: None)
    assert res["retrieval"]["status"] == "pass", res["retrieval"]["cases"]


def test_default_is_a_temp_copy_and_live_needs_the_flag(tmp_path, plane):
    root = plane.root.parent
    (plane.root / "marker.txt").write_text("x")
    copy, cleanup = E.working_copy(root, "evalco")
    assert copy.root != plane.root and (copy.root / "marker.txt").exists()
    (copy.root / "changed.txt").write_text("y")
    assert not (plane.root / "changed.txt").exists()
    cleanup()
    assert not copy.root.exists()
    live, _ = E.working_copy(root, "evalco", allow_live=True)
    assert live.root == plane.root
