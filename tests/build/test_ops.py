"""BC-7 Ops: the Watcher's daily read. Synthetic data only."""
import json
from datetime import date
from pathlib import Path

from sh_platform import warehouse
from sh_platform.build import alerts, ops
from sh_platform.plane import PlaneStore
from sh_platform.profile import store
from sh_platform.profile.view import Viewer

TODAY = date(2026, 10, 6)
OWNER, OUTSIDER = Viewer("Mei Tan", frozenset({"participant"})), Viewer("Wei Chen", frozenset({"participant"}))


def put(plane, rel: str, data) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def run(source: str, status: str = "ok", rules=(), day: str = "2026-10-06") -> dict:
    return {"id": source + day, "source": source, "started": f"{day}T08:00:00+00:00", "ended": f"{day}T08:30:00+00:00", "on_time": status == "ok",
            "rows": 10, "schema_ok": True, "rules": list(rules), "marts_ready": None, "sla_met": None, "owner": "Sara Lim", "status": status}


def company(tmp_path: Path, runs: list[dict]):
    plane = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    for s in ("custody", "payroll"):
        put(plane, f"build/pipelines/{s}.json", {"source": s, "expected": "D+2 09:00", "sla": "WD8", "depends_on": [], "owner": "Sara Lim", "marts": ["gold.aum"]})
    put(plane, "warehouse/runs.json", {"runs": runs})
    return plane


def test_late_and_missing_sources_are_detected(tmp_path):
    out = ops.build(company(tmp_path, [run("custody", "late")]), OWNER, TODAY)
    assert {a["source"]: a["state"] for a in out["arrivals"]} == {"custody": "late", "payroll": "missing"}
    assert {a["kind"] for a in out["alerts"]} == {"late", "missing"} and all(a["owner"] == "Sara Lim" and a["ask"] for a in out["alerts"])


def test_failed_checks_are_listed_with_counts(tmp_path):
    out = ops.build(company(tmp_path, [run("custody", "failed", [{"rule": "no-negative-aum", "passed": False, "count": 3}, {"rule": "dates", "passed": True, "count": 0}])]), OWNER, TODAY)
    assert out["failed_checks"] == [{"source": "custody", "rule": "no-negative-aum", "count": 3}]


def test_range_break_is_flagged_but_the_figure_only_shows_to_the_access_list(tmp_path):
    plane = company(tmp_path, [run("custody"), run("payroll")])
    con = warehouse.open_company(plane)
    con.execute("create table gold.aum as select * from (values ('2026-01',100.0),('2026-02',101.0),('2026-03',99.0),('2026-04',100.0),('2026-05',102.0),('2026-06',98.0),('2026-07',160.0)) t(period, value)")
    con.close()
    warehouse.refresh_readonly_copy(plane)
    rule = {"field": {"value": "aum", "mark": "stated"}, "personal": {"value": "yes", "mark": "stated"}, "may_see": {"value": ["Mei Tan"], "mark": "stated"}}
    store.mutate(plane, lambda d: d["governance"]["field_rules"].update({"aum": rule}))
    mine, theirs = ops.build(plane, OWNER, TODAY)["range_breaks"][0], ops.build(plane, OUTSIDER, TODAY)["range_breaks"][0]
    assert mine["flag"] == theirs["flag"] == "outside_range" and mine["latest"] == 160.0
    out = ops.build(plane, OWNER, TODAY)  # two pipelines feed this mart: one break, one alert
    assert len(out["range_breaks"]) == 1 and [a["id"] for a in out["alerts"]] == ["gold.aum:range"]
    assert theirs["latest"] is None and theirs["mean"] is None and "160" not in json.dumps(theirs)


def test_ack_keeps_its_state_across_a_rebuild_and_a_new_day(tmp_path):
    plane = company(tmp_path, [run("custody")])  # payroll is missing
    first = next(a for a in ops.build(plane, OWNER, TODAY)["alerts"] if a["source"] == "payroll")
    assert first["state"] == "open" and first["opened"] == "2026-10-06"
    alerts.act(plane, first["id"], "ack", "Mei Tan", "chasing")
    again = next(a for a in ops.build(plane, OWNER, date(2026, 10, 7))["alerts"] if a["source"] == "payroll")
    assert again["id"] == first["id"] and again["state"] == "acknowledged" and again["by"] == "Mei Tan" and again["note"] == "chasing" and again["opened"] == "2026-10-06"


def test_close_removes_the_alert_from_the_list(tmp_path):
    plane = company(tmp_path, [run("custody")])
    a = ops.build(plane, OWNER, TODAY)["alerts"][0]
    alerts.act(plane, a["id"], "close", "Mei Tan", None)
    assert a["id"] not in {x["id"] for x in ops.build(plane, OWNER, TODAY)["alerts"]}


def test_with_nothing_run_today_the_report_reads_the_latest_day_on_the_log(tmp_path):
    runs = [run("custody", "late", day="2026-09-01"), run("payroll", day="2026-09-01")]
    out = ops.build(company(tmp_path, runs), OWNER, TODAY)
    assert out["date"] == "2026-09-01" and [a["kind"] for a in out["alerts"]] == ["late"]


def test_one_source_run_by_hand_today_does_not_make_the_others_missing(tmp_path):
    runs = [run("custody", day="2026-09-01"), run("payroll", day="2026-09-01"), run("custody", day="2026-10-06")]
    out = ops.build(company(tmp_path, runs), OWNER, TODAY)
    assert out["date"] == "2026-09-01" and out["alerts"] == []


def test_runs_of_a_source_with_no_current_contract_are_ignored_and_the_run_book_has_titles(tmp_path):
    plane = company(tmp_path, [run("custody"), run("payroll"), run("old_crm", "failed")])
    put(plane, "build/pipelines/custody.json", {"source": "custody", "title": "Custody file", "expected": "D+2", "sla": "WD8", "depends_on": [], "owner": "Sara Lim", "marts": []})
    out = ops.build(plane, OWNER, TODAY)
    assert {a["source"] for a in out["arrivals"]} == {"custody", "payroll"} and not any(a["source"] == "old_crm" for a in out["alerts"])
    assert {b["source"]: b["title"] for b in out["run_book"]}["custody"] == "Custody file"

