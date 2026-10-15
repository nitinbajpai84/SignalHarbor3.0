"""Off-camera steps of the Build explainer's story, played through the product's own functions on the film's seeded company
(the same story as tools/seed_walk_benchmark.py, cut into the steps a person does on camera and the steps done between shots).

    python tools/video/vid6_prep.py start | slip | plan1 | v2 | indexes | livefx          (SH_FILM_ENV picks the data root; default vid6)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import seed_walk_benchmark as W  # noqa: E402
from sh_platform.jsonfile import write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import b6_plan as B, b10_pack as K, b11_builder as BU, p1_project as P1  # noqa: E402
import seed_10uc as S  # noqa: E402

DATA = ROOT / ".sh-tmp" / "testenv" / os.environ.get("SH_FILM_ENV", "vid6") / "data"
TITLE = "Monthly performance against the benchmark"


def _who():
    plane = PlaneStore(DATA).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(DATA)
    v = S.viewers(ids)
    return plane, v["Leo Park"], v["Anita Rao"], v["Daniel Foo"]


def pid_of(plane) -> str:
    return P1.for_intent(plane, W.IID)["id"]


def start() -> str:
    plane, eng, head, sponsor = _who()
    write_json_atomic(plane.path("intents", W.IID, "sow.json"), W.SOW)
    pid = P1.create_project(plane, W.IID, TITLE, sponsor.name, sponsor.account_id)["id"]
    P1.set_person(plane, pid, "head_of_data", head.name)
    P1.set_person(plane, pid, "builder", eng.name)
    P1.set_person(plane, pid, "sponsor", sponsor.name)
    return pid


def slip() -> None:
    """Between the draft and the send: the engineer corrects one line (the slip of pack version 1) and settles the open rows."""
    plane, eng, head, _ = _who()
    pid = pid_of(plane)
    pack = K.get(plane, pid)
    weights = next(g["name"] for g in pack["target"]["gold"] if g["name"].endswith("_benchmark_weights"))
    K.edit(plane, eng, pid, "gold_column", f"{weights}.component_weight", {"expr": W.SLIP}, "the sleeve weight as the benchmark sheet lists it")
    for m in K.open_rows(K.get(plane, pid)):
        K.edit(plane, eng, pid, "mapping", m["id"], {"resolve": True}, "settled by the data engineer")


def plan1() -> None:
    """After the head of data approves version 1: the plan is drawn from the pack and approved."""
    plane, eng, head, _ = _who()
    pid = pid_of(plane)
    plan = K.apply_to_plan(plane, eng, pid)
    B.approve(plane, head, pid, plan["version"], "Plan from pack version 1")


def v2() -> None:
    """After the builder sends it back: the architect reads the signed weight, version 2 is approved, the plan too, the builder runs again."""
    plane, eng, head, _ = _who()
    pid = pid_of(plane)
    weights = next(g["name"] for g in K.get(plane, pid)["target"]["gold"] if g["name"].endswith("_benchmark_weights"))
    K.edit(plane, eng, pid, "gold_column", f"{weights}.component_weight", {"expr": W.FIXED}, "read the signed weight of each leg")
    K.submit(plane, eng, pid)
    K.approve(plane, head, pid)
    plan = K.apply_to_plan(plane, eng, pid)
    B.approve(plane, head, pid, plan["version"], "Plan from pack version 2")


def ready() -> str:
    """Server stopped: the new project taken to the builder's first run (answers accepted, pack version 1 drafted, slipped, approved, plan
    approved, the builder run on a copy). The launch film's Pipelines scene starts here."""
    plane, eng, head, _ = _who()
    pid = pid_of(plane)
    K.accept_all(plane, eng, pid)
    K.generate(plane, eng, pid)
    slip()
    K.submit(plane, eng, pid)
    K.approve(plane, head, pid)
    plan1()
    BU.start(plane, eng, pid)
    return pid


def indexes() -> int:
    """The head of data signs the proposed index for each fund (film v4, Market signals: each fund against its index)."""
    from sh_platform.v1 import k10_note as N
    plane, _, head, _ = _who()
    view = N.index_map(plane, head)
    picks = {f["fund_id"]: f["proposed_series_key"] for f in view["funds"] if f["proposed_series_key"]}
    return len(N.sign_index_map(plane, head, picks)["funds"]) if picks else 0


def livefx() -> str:
    """Film v4 (Testing env only): one live-API pull through the product's own connector, as Fetch now would run it. The company's
    connector switch is turned on for this test company and the Frankfurter USD/SGD and EUR/USD rates are fetched (no key)."""
    from sh_platform.egress.policy import EgressPolicy
    from sh_platform.v1.c5_connect import api
    plane, *_ = _who()
    EgressPolicy(plane).set_internet("c5_connect", True)
    r = api.pull(plane, api.clean_spec({"provider": "frankfurter", "series": ["USD/SGD", "EUR/USD"]}, "api-frankfurter"))
    if r["status"] != "ok":
        raise SystemExit(f"live pull failed: {r['error']}")
    return f"{r['landed']}"


def report() -> str:
    """The September report as issued (the file a person uploads), written next to the film's data; returns its path."""
    from sh_platform.v1 import e1_reports
    plane, *_ = _who()
    issued = {x["label"]: x["value"] for x in e1_reports.as_issued(plane, BU.signed_reports(plane)[0]["id"])}
    path = DATA.parent / "September report as issued.csv"
    path.write_text(f"{W.HELD} {issued[W.HELD]:,.0f}" + chr(10) + W.REPORT, encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    print(globals()[sys.argv[1]]())
