"""E6c shadow replay on a tmp plane with stub loader, recon and impact (E0c, E3 are not required)."""
import csv
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_write, wh

ROOT = Path(__file__).resolve().parents[2]
spec_ = importlib.util.spec_from_file_location("shadow_run", ROOT / "tools" / "shadow_run.py")
S = importlib.util.module_from_spec(spec_)
sys.modules["shadow_run"] = S
spec_.loader.exec_module(S)
WB = ROOT / "tests" / "v1" / "fixtures" / "e0d" / "workbooks"
UTC = timezone.utc
FA = wh.new_id()


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(p) as con:  # E1b refuses ids that are not in this warehouse
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?, ?, 'Evergreen Growth I', 'fund', now())",
                    [FA, e1_write.org_id(p)])
    return p


def val(amount, kind, d="2026-09-30"):
    return {"instrument_id": FA, "valuation_date": datetime.fromisoformat(d).date(), "received_at": datetime(2026, 10, 2, tzinfo=UTC),
            "value_amount": amount, "currency": "USD", "valuation_type": kind, "approval_status": "approved"}


def make(plane, extra_files=()):
    seen = {"val": None, "impacts": [], "recons": []}

    def loader(pl, path, viewer):
        if path.name == "val_mgr_estimate_dmy.xlsx":
            seen["val"] = e1_write.record(pl, "valuation_observations", val(10_000_000, "estimate"))
        elif path.name == "val_mgr_final_aug.xlsx":
            seen["val"] = e1_write.record(pl, "valuation_observations", val(10_180_000, "final"), supersedes_id=seen["val"])
        return "loaded"

    def impact(pl, vid):
        seen["impacts"].append(vid)
        e1_write.record(pl, "exceptions", {"exception_type": "revision", "title": "Fund A revised", "detected_at": wh.now(),
                                           "materiality_status": "material", "status": "new"})

    def recon(pl, code, as_of, cutoff):
        seen["recons"].append((code, cutoff))

    return seen, loader, recon, impact


SPEC = {"periods": [
    {"name": "2026-09", "cutoff": "2026-10-05", "files": [{"path": "val_mgr_estimate_dmy.xlsx", "received_at": "2026-10-02T09:00:00+00:00"}]},
    {"name": "2026-10", "cutoff": "2026-10-12", "files": [
        {"path": "val_mgr_final_aug.xlsx", "received_at": "2026-10-09T09:00:00+00:00"}]},
]}


def test_replay_findings_clock_and_reproducible(plane, tmp_path):
    seen, loader, recon, impact = make(plane)
    real_now = wh.now
    res = S.replay(plane, SPEC, loader=loader, recon=recon, impact=impact, base=WB)
    assert wh.now is real_now  # clock restored
    # recorded_at is the historical receipt, not today
    with wh.connect(plane) as con:
        rec = [r[0] for r in con.execute("select recorded_at from valuation_observations order by recorded_at").fetchall()]
    assert rec[0].date().isoformat() == "2026-10-02" and rec[1].date().isoformat() == "2026-10-09"
    # one revision finding, raised right after the 9 Oct receipt
    assert len(res["findings"]) == 1 and seen["impacts"] == [seen["val"]]
    f = res["findings"][0]
    assert f["period"] == "2026-10" and 0 <= f["seconds_to_finding"] < 60 and f["false_alert"] == ""
    # recons ran per file per code at the receipt cutoff
    assert len(seen["recons"]) == 4 and seen["recons"][0][1] == datetime(2026, 10, 2, 9, tzinfo=UTC)
    # as known at 5 Oct the figure is still the estimate, and stays so after the revision loaded
    assert all(r["reproducible"] for r in res["reproducible"])
    assert res["reproducible"][0]["at_end"]["valuation_observations"][0] == 1

    out, rep = S.write_reports(res, tmp_path / "r.csv")
    assert list(csv.DictReader(out.open()))[0]["case_opened"] == "yes"
    assert {r["reproducible"] for r in csv.DictReader(rep.open())} == {"yes"}


def test_files_replayed_in_received_order(plane):
    order = []
    spec = {"periods": [{"name": "p", "cutoff": "2026-10-31", "files": [
        {"path": "b.xlsx", "received_at": "2026-10-05T00:00:00+00:00"}, {"path": "a.xlsx", "received_at": "2026-10-01T00:00:00+00:00"}]}]}
    S.replay(plane, spec, loader=lambda pl, p, v: order.append(p.name) or "loaded", recon=lambda *a: None, impact=lambda *a: None)
    assert order == ["a.xlsx", "b.xlsx"]


def test_default_loader_uses_the_real_landing_names(plane):
    """No stubs: scan_inbox registers the file (record key file_id), the landing load runs and returns the file's state."""
    from sh_platform.v1 import e0c_landing
    state = S.default_loader(plane, WB / "cash_2026_08.xlsx", S.VIEWER)
    recs = e0c_landing.listing(plane)["files"]
    assert len(recs) == 1 and recs[0]["name"] == "cash_2026_08.xlsx" and state == recs[0]["state"] and state != "new"
    assert S.default_loader(plane, WB / "cash_2026_08.xlsx", S.VIEWER) == state  # the same bytes again: no second record
    assert len(e0c_landing.listing(plane)["files"]) == 1


def test_default_is_a_temp_copy_live_needs_the_flag(plane):
    root = plane.root.parent
    (plane.root / "marker.txt").write_text("x")
    copy, cleanup = S.working_copy(root, "acme")
    (copy.root / "changed.txt").write_text("y")
    assert copy.root != plane.root and (copy.root / "marker.txt").exists() and not (plane.root / "changed.txt").exists()
    cleanup()
    assert not copy.root.exists() and plane.root.exists()
    live, _ = S.working_copy(root, "acme", allow_live=True)
    assert live.root == plane.root
