"""V6B: the benchmark story of the V6 walk, played on a seeded company through the product's own functions (no model, no figure typed into product code).

Usage: python tools/seed_walk_benchmark.py [--data-root PATH]      (after tools/seed_10uc.py has seeded that root)
The story (docs/plan/BUILD-FLOW-V6.md, designs H4 to H9): the architect drafts the design pack from a signed intent; the pack names the portfolio, the signed
benchmark and the month; the data engineer corrects one line (the private-markets sleeve's weight is read as the smallest weight in the benchmark, a mapping
slip); the head of data approves; the builder runs on a copy, reads the report as issued, and finds the benchmark return differs from the report's. It hands the
variance back, the architect corrects the line to read the signed weight, pack version 2 is approved, the builder reruns by itself and the variance clears.
The only typed numbers are the report as issued (an input, as a person would upload it). Every other figure is worked out by the product from the seeded records.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.jsonfile import write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import b6_plan as B  # noqa: E402
from sh_platform.v1 import b10_pack as K  # noqa: E402
from sh_platform.v1 import b11_builder as BU  # noqa: E402
from sh_platform.v1 import p1_project as P1  # noqa: E402

IID = "ini-" + "b6" * 16
SOW = {"state": "signed", "title": "Monthly performance against the benchmark",
       "goal": {"line": "One page a month on how the liquid portfolio did against the family benchmark", "readers": ["Family council"], "needed_by": "5th business day"},
       "process": {"steps": [{"name": "Check totals", "control": "Administrator total equals the file footer"}]},
       "sources": [],
       "kpis": [{"code": "K1", "name": "Net worth", "definition": "Holdings plus cash less loans, by entity, at month end", "formula": "", "unit": "USD", "period": "monthly",
                 "owner": "Daniel Foo", "sources": [], "benchmark_by": ["entity"]},
                {"code": "K2", "name": "Return net of fees", "definition": "Closing value less opening value less net flows, over opening value; month end to month end",
                 "formula": "", "unit": "%", "period": "monthly", "owner": "Mei Chen", "sources": [], "benchmark_by": ["month"]},
                {"code": "K3", "name": "Return against benchmark", "definition": "Portfolio return less the return of the signed family benchmark EG-OFFICE-BLEND",
                 "formula": "", "unit": "%", "period": "monthly", "owner": "Mei Chen", "sources": [], "benchmark_by": ["month"]}],
       "governance": []}
# The returns and weights of the September report as issued (an input, like a file a person uploads). The sleeve line is the weight the signed benchmark gives it.
# The holdings line is read from the report the company issued on 3 Oct (e1_reports), so no holdings figure is typed here.
REPORT = "Portfolio 4.17%\nOffice blend 2.71%\nDifference 1.46%\nGlobal equity index 42%\nBond index 28%\nPrivate-markets sleeve 30%\n"
HELD = "Evergreen Growth I"
# The mapping slip of pack version 1: the sleeve's weight is read as the smallest weight in the benchmark (the bond leg's) instead of its own row.
SLIP = ("cast(case when coalesce(c.spread_bps, 0) <> 0 then min(c.component_weight) over (partition by c.benchmark_definition_id, lv.month) "
        "else c.component_weight end as decimal(9,6))")
FIXED = "cast(c.component_weight as decimal(9,6))"


def play(plane, eng, head, iid: str = IID, sow: dict | None = None) -> dict:
    """Run the story; returns what happened at each step (the test asserts on it). `iid` and `sow`: an intent made the usual way (the demo-ready seed
    signs it as Daniel Foo first); the defaults write the bare signed intent of the walk."""
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow or SOW)
    pid = P1.create_project(plane, iid, "Monthly performance against the benchmark", eng.name, eng.account_id)["id"]
    P1.set_person(plane, pid, "head_of_data", head.name)
    out = {"project_id": pid}
    K.accept_all(plane, eng, pid)
    pack = K.generate(plane, eng, pid)
    weights = next(g["name"] for g in pack["target"]["gold"] if g["name"].endswith("_benchmark_weights"))
    out["pack_drawn"] = pack
    K.edit(plane, eng, pid, "gold_column", f"{weights}.component_weight", {"expr": SLIP}, "the sleeve weight as the benchmark sheet lists it")
    for m in K.open_rows(K.get(plane, pid)):
        K.edit(plane, eng, pid, "mapping", m["id"], {"resolve": True}, "settled by the data engineer")
    K.submit(plane, eng, pid)
    K.approve(plane, head, pid)
    plan1 = K.apply_to_plan(plane, eng, pid)
    B.approve(plane, head, pid, plan1["version"], "Plan from pack version 1")
    out["round1"] = BU.start(plane, eng, pid)
    from sh_platform.v1 import e1_reports
    issued = {x["label"]: x["value"] for x in e1_reports.as_issued(plane, BU.signed_reports(plane)[0]["id"])}
    out["report"] = f"{HELD} {issued[HELD]:,.0f}\n" + REPORT
    v = BU.set_benchmark(plane, eng, pid, {"name": "September report as issued.csv", "text": out["report"]})
    out["variance1"] = v["round"]["variance"]
    BU.send_back(plane, eng, pid, "The benchmark return is not the report's. Please check the weights.")
    K.edit(plane, eng, pid, "gold_column", f"{weights}.component_weight", {"expr": FIXED}, "read the signed weight of each leg")
    K.submit(plane, eng, pid)
    K.approve(plane, head, pid)
    plan2 = K.apply_to_plan(plane, eng, pid)
    B.approve(plane, head, pid, plan2["version"], "Plan from pack version 2")
    out["round2"] = BU.start(plane, eng, pid)
    out["variance2"] = out["round2"]["variance"]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    root = Path(ap.parse_args().data_root)
    from tools import seed_10uc as S
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    V = S.viewers(ids)
    got = play(plane, V["Leo Park"], V["Anita Rao"])
    for k in ("variance1", "variance2"):
        print(k, got[k]["headline"], [(x["figure"], x["run"], x["report"], x["status"]) for x in got[k]["lines"] + got[k]["legs"]])
