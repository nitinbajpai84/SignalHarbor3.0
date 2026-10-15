"""QH: six months of illustrative operating history on a temp company. Synthetic data only."""
import importlib.util
import json
from pathlib import Path

from sh_platform.plane import PlaneStore
from sh_platform.profile import record

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hist, wh = _load("seed_demo_history"), _load("seed_demo_warehouse")
CID = "lakeside-family-office"
STATED = {"mark": "stated", "by": "Test", "from": "a list"}


def make(tmp_path: Path):
    plane = PlaneStore(tmp_path).create(CID)
    wh.seed_demo_warehouse(tmp_path, CID)
    for pid, name, flag in (("p-ann", "Ann Admin", "is_organiser"), ("p-sam", "Sam Sponsor", "is_sponsor"), ("p-ola", "Ola Owner", None)):
        record(plane, f"people.{pid}.name", name, STATED)
        if flag:
            record(plane, f"people.{pid}.{flag}", True, STATED)
    record(plane, "people.p-ola.owns", ["K12 Stale-valuation share", "K02 Reported-value evidence coverage"], STATED)
    for src, marts, rules in (("custodian_daily_file", ["gold.k02"], ["K02:holding value is not empty"]), ("fee_schedule", ["gold.k05"], []),
                              ("index_provider_feed", ["gold.k17"], [])):
        p = plane.path("build", "pipelines", f"{src}.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"source": src, "lands_at": "landing", "pattern": f"{src}*.csv", "expected": "D+1 09:00", "sla": "WD8",
                                 "schema": [], "rules": rules, "depends_on": [], "owner": "Ola Owner", "marts": marts}), encoding="utf-8")
    return plane


def seed(tmp_path: Path, **kw):
    return hist.seed(tmp_path, CID, "2026-04-01", "2026-09-30", companies_file=tmp_path / "none.yaml", **kw)


def read(plane, *parts):
    return json.loads(plane.path(*parts).read_text(encoding="utf-8"))


def test_one_run_per_source_per_month_with_june_late_and_august_failed(tmp_path):
    plane = make(tmp_path)
    seed(tmp_path)
    runs = read(plane, "warehouse", "runs.json")["runs"]
    assert len(runs) == 3 * 6
    by = {(r["started"][:7], r["source"]): r for r in runs}
    late = by[("2026-06", "custodian_daily_file")]
    assert late["status"] == "late" and late["on_time"] is False and late["marts_ready"] and late["sla_met"] is True
    bad = by[("2026-08", "fee_schedule")]
    assert bad["status"] == "failed" and bad["marts_ready"] is None and bad["sla_met"] is None
    assert [r for r in bad["rules"] if not r["passed"]] == [{"rule": "K05:fee terms are not empty", "passed": False, "count": 7}]
    others = [r for k, r in by.items() if k not in {("2026-06", "custodian_daily_file"), ("2026-08", "fee_schedule")}]
    assert all(r["status"] == "ok" and r["on_time"] and r["sla_met"] for r in others)
    assert all(r["started"][:7] == "2026-09" for r in runs[-3:])  # newest last


def test_alerts_acknowledged_and_september_range_break_open(tmp_path):
    plane = make(tmp_path)
    seed(tmp_path)
    alerts = {a["id"]: a for a in read(plane, "build", "alerts.json")["alerts"]}
    june, aug, sep = alerts["custodian_daily_file:late"], alerts["fee_schedule:failed"], alerts["gold.k02:range"]
    assert june["state"] == aug["state"] == "acknowledged" and june["by"] == aug["by"] == "Ann Admin" and june["note"] and aug["note"]
    assert june["at"].startswith("2026-06") and aug["at"].startswith("2026-08")
    assert sep["state"] == "open" and sep["opened"].startswith("2026-09") and sep["source"] == "custodian_daily_file"
    versions = read(plane, "graph", "versions.json")
    assert len(versions) == 12 and [v["v"] for v in versions["measure:K15"]] == [1, 2, 3] and len(versions["measure:K01"]) == 2
    assert versions["measure:K12"][1]["by"] == "Ola Owner" and versions["measure:K01"][0]["at"].startswith("2026-04")
    msgs = read(plane, "pulse", "messages.json")["messages"]
    assert len(msgs) == 30 and {m["state"] for m in msgs if m["drafted_at"].startswith("2026-09")} == {"draft"}
    assert all(m["state"] == "sent" and m["sent_by"] == "Ann Admin" for m in msgs if not m["drafted_at"].startswith("2026-09"))


def test_running_twice_is_idempotent_and_reset_removes_it(tmp_path):
    plane = make(tmp_path)
    files = [("warehouse", "runs.json"), ("build", "alerts.json"), ("graph", "versions.json"), ("graph", "comments.json"),
             ("pulse", "messages.json"), ("context", "memory", "north", "company.json"), ("context", "memory", "lens", "company.json"),
             ("context", "memory", "north", "people", "p-sam.json"), ("context", "egress_log.jsonl")]
    seed(tmp_path)
    first = {f: plane.path(*f).read_text(encoding="utf-8") for f in files}
    seed(tmp_path)
    assert {f: plane.path(*f).read_text(encoding="utf-8") for f in files} == first
    assert 6 <= len(read(plane, "context", "memory", "lens", "company.json")["entries"]) <= 10
    seed(tmp_path, reset=True)
    assert read(plane, "warehouse", "runs.json")["runs"] == [] and read(plane, "pulse", "messages.json")["messages"] == []
    assert not plane.path("build", "demo_history.json").exists()
