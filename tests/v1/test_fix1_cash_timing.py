"""FIX1: the cash check carries Tally's timing reading as the break's cause (so Action offers "Close as timing"), and a case closed that way
counts as closed today on the company's day (demo_today), wherever it was closed. Seeded Evergreen warehouse, synthetic."""
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e3_recon, e4_cases, wh
from tools import seed_10uc as S


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("fix1cash")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    yield {"plane": plane, "V": S.viewers(ids)}
    mp.undo()


def test_cash_break_carries_its_timing_cause_and_closing_it_counts_today(world):
    plane, V = world["plane"], world["V"]
    run = next(r for r in e3_recon.last_runs(plane) if r["recon_code"] == "cash_by_entity")
    brk = next(x for x in run["results"] if x["breached"] and x.get("case_id"))
    assert "timing difference" in brk["cause"] and "12,400 USD" in brk["cause"]
    cid = brk["case_id"]
    who = next(v for v in V.values() if e4_cases.get(plane, cid, v)["can"].get("dismiss"))
    e4_cases.dismiss(plane, cid, who, "A timing difference that clears by itself.")
    row = next(c for c in e4_cases.listing(plane, who) if c["id"] == cid)
    assert row["state"] == "rejected" and row["closed_today"] is True
