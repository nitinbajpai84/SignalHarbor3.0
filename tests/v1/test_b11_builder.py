"""V6-builder: connect each source as the pack says, confirm against the intent's system record (a mismatch once), run on a copy by itself, ask for a
benchmark, variance line by line (explained vs unexplained), go live or send back to the architect, pack version 2, rerun by itself. No model; the
connection calls are stubbed (the real ones are in test_c5_connect)."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from test_k7 import ORG, plane, wh  # noqa: F401  (plane is the fixture)

from sh_platform.agents import handoff as H
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b9_verify as V
from sh_platform.v1 import b11_builder as BU
from sh_platform.v1 import b11_routes as RT
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused

LEO = Viewer("Leo Park", frozenset({"analyst"}), False, "acc-leo")
ANITA = Viewer("Anita Rao", frozenset({"analyst", "head_of_data"}), False, "acc-anita")
GUEST = Viewer("Gus", frozenset({"participant"}), False, "acc-gus")
REPORT = ("Total holdings, 30 Sep 57,600,000\nFund A 10,000,000\nPortfolio return 4.17%\nBenchmark return 2.71%\n"
          "Global equity index 42%\nGlobal bond index 28%\nGlobal equity index plus a spread 30%\nPages in this report 4\n")
WEIGHTS = {"eq": "42.0000", "bd": "28.0000", "pe": "28.0000"}  # the pack's private sleeve weight; version 2 sets 30
def gold(pid):
    return f"gold_{E.slug_of(pid)}_holdings"


def gold_sql(pid):
    return f"create table {gold(pid)} as select fund, sum(amount) as amount from bronze_pos group by fund"
UPLOAD = {"code": "admin", "name": "Fund administrator positions", "kind": "structured", "files": [], "owner": "Mei Chen", "arrives": {"how": "upload", "file": "positions_*.csv"}}
SFTP = {"code": "sftp", "name": "Trading export", "kind": "structured", "files": [], "owner": "Raj", "arrives": {"how": "sftp", "connector": "nope"}}


@pytest.fixture()
def prj(plane, monkeypatch):
    with wh.connect(plane) as con:
        con.execute("create table bronze_pos (fund varchar, amount integer)")
        con.execute("insert into bronze_pos values ('Fund A', 10180000), ('Fund B', 47600000)")
        for v in (LEO, ANITA):
            con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), org_id(plane), v.account_id, v.name, v.account_id + "@example.test", True, wh.now()])
    monkeypatch.setattr("sh_platform.v1.k1_access.directory", lambda p: {
        "acc-leo": {"name": "Leo Park", "disabled": False, "roles": ["analyst"]}, "acc-anita": {"name": "Anita Rao", "disabled": False, "roles": ["company_admin"]}})
    pid = P1.create_project(plane, "intent-1", "Monthly performance", "Leo Park", "acc-leo")["id"]
    P1.set_person(plane, pid, "head_of_data", "Anita Rao")
    return pid


def write_pack(plane, pid, sources, version=1, state="approved"):
    plan = {"project_id": pid, "version": version, "state": state, "sources": sources, "schedule": {"freq": "daily", "at": "06:00", "day": None},
            "tables": [{"name": "bronze_pos", "layer": "bronze", "sql": "", "depends_on": [], "columns": [{"name": "fund", "type": "varchar"}, {"name": "amount", "type": "integer"}]},
                       {"name": gold(pid), "layer": "gold", "depends_on": ["bronze_pos"], "sql": gold_sql(pid)}],
            "key_figures": [{"label": "Total holdings", "table": gold(pid), "column": "amount", "agg": "sum"},
                            {"label": "Fund", "table": gold(pid), "column": "amount", "agg": "sum", "by": "fund"}],
            "benchmark": {"portfolio": "EG", "code": "OFFICE", "month": "2026-09"}, "approved_by": "Anita Rao"}
    f = plane.path("build", pid, f"plan-v{version}.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(plan), encoding="utf-8")


@pytest.fixture()
def fake_cmp(monkeypatch):
    weights = dict(WEIGHTS)

    def comparison(plane, viewer, pid, review):
        pe = weights["pe"]
        rows = [{"component": "IDX:GLEQ:SYN", "label": "Global equity index", "used_weight_pct": weights["eq"]},
                {"component": "IDX:GLBD:SYN", "label": "Global bond index", "used_weight_pct": weights["bd"]},
                {"component": "IDX:GLEQ:SYN plus spread", "label": "Global equity index plus a spread", "used_weight_pct": pe}]
        ok = pe == "30.0000"
        return {"portfolio_pct": "4.1700", "benchmark_run_pct": "2.7100" if ok else "2.6300", "difference_run_pts": "1.4600" if ok else "1.5400", "rows": rows}
    monkeypatch.setattr(V, "comparison", comparison)
    return weights


@pytest.fixture()
def revs(monkeypatch):
    when = datetime(2026, 10, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(BU, "_revisions", lambda plane: [{"name": "Fund A", "delta": Decimal("180000"), "when": when, "trail": {"kind": "valuation", "id": "v1"}}])


def land(plane, name="positions_sep.csv", source="admin"):
    L.receive(plane, b"fund,amount\nFund A,1\n", name, "Leo Park", source)


def test_nothing_starts_before_the_pack_is_approved_and_only_the_data_engineer_starts(plane, prj):
    with pytest.raises(Refused) as e:
        BU.start(plane, LEO, prj)
    assert e.value.status == 409 and BU.view(plane, LEO, prj)["waiting"]
    write_pack(plane, prj, [UPLOAD], state="proposed")
    assert BU.view(plane, LEO, prj)["pack"] is None  # a proposed version is not the pack
    write_pack(plane, prj, [UPLOAD])
    with pytest.raises(Refused) as e:
        BU.start(plane, GUEST, prj)
    assert e.value.status == 403


def test_connect_and_run_by_itself_once_per_pack_version(plane, prj, fake_cmp):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    r = BU.start(plane, LEO, prj)
    assert r["state"] == "ran" and r["connections"][0]["status"] == "connected" and r["run"]["status"] == "ok"
    assert r["run"]["tables"] == {"bronze": 1, "silver": 0, "gold": 1} and r["run"]["gold_rows"] == 2 and r["run"]["pack_version"] == 1
    assert BU.start(plane, LEO, prj) == r  # the second call finds the round
    assert len(BU.load(plane, prj)["rounds"]) == 1
    v = BU.view(plane, LEO, prj)
    assert v["can"]["benchmark"] and not v["can"]["start"] and v["thread"][0]["who"] == "Span the builder"


def test_a_failed_connection_and_a_missing_sample_are_the_only_action_items(plane, prj, monkeypatch):
    write_pack(plane, prj, [UPLOAD, SFTP])  # no sample landed, and the connector is not set up
    r = BU.start(plane, LEO, prj)
    st = {c["code"]: c["status"] for c in r["connections"]}
    assert st == {"admin": "needs_sample", "sftp": "failed"} and r["state"] == "blocked" and r["run"] is None  # nothing ran on a half-connected pack
    needs = {n["kind"]: n for n in BU.load(plane, prj)["needs"]}
    assert needs["connection_failed"]["to"] == ["Anita Rao"] and needs["missing_sample"]["to"] == ["Mei Chen"]
    cards = BU.pulse_cards(plane, None, None)
    assert len(cards) == 1 and cards[0]["headline"].startswith("Connection failed")  # Mei has no user row in this company, so no card for her
    land(plane)
    monkeypatch.setattr(BU.C5S, "get", lambda plane, cid: {"id": "c", "kind": "sftp", "host": "sftp.example.test"})
    monkeypatch.setattr(BU.C5, "test", lambda plane, spec, F=None: {"ok": True})
    monkeypatch.setattr(BU.C5, "dry_run", lambda plane, spec, F=None: {"ok": True, "would_arrive": [{"name": "trades.csv", "size": 3}]})
    r = BU.recheck(plane, LEO, prj)
    assert r["state"] == "ran" and BU.load(plane, prj)["needs"] == []  # fixed, so the items close
    assert "Reused the connection" in r["connections"][1]["detail"] and r["connections"][1]["seen"]["host"] == "sftp.example.test"


def test_a_blocked_address_is_a_failure_with_words(plane, prj, monkeypatch):
    write_pack(plane, prj, [SFTP])
    monkeypatch.setattr(BU.C5S, "get", lambda plane, cid: {"id": "c", "kind": "sftp", "host": "sftp.example.test"})
    monkeypatch.setattr(BU.C5, "test", lambda plane, spec, F=None: {"ok": False, "code": "destination_not_allowed", "message": "That address is not allowed. An administrator can allow it."})
    r = BU.start(plane, LEO, prj)
    assert r["connections"][0]["status"] == "failed" and "administrator" in r["connections"][0]["detail"]


def test_a_mismatch_is_raised_once_with_the_intent_value_and_the_fix_updates_both_records(plane, prj, fake_cmp):
    write_pack(plane, prj, [UPLOAD])
    land(plane, "positions_sep.csv")
    plane.path("build", prj, "systems.json").write_text(json.dumps({"admin": {"file": "admin_positions.xlsx", "columns": ["Fund", "Amount"]}}), encoding="utf-8")
    r = BU.start(plane, LEO, prj)
    c = r["connections"][0]
    assert r["state"] == "blocked" and c["status"] == "mismatch" and c["mismatches"] == [{"field": "file", "pack": "positions_*.csv", "intent": "admin_positions.xlsx", "seen": "positions_sep.csv"}]
    assert BU.load(plane, prj)["needs"] == []  # a mismatch is for the builder's screen, not an Action item
    r = BU.resolve(plane, LEO, prj, {"source": "admin", "field": "file", "value": "positions_*.csv"})
    assert r["state"] == "ran" and r["connections"][0]["status"] == "connected"
    assert json.loads(plane.path("build", prj, "systems.json").read_text())["admin"]["file"] == "positions_*.csv"  # the intent's system map
    plan = B.get(plane, prj, 1)
    assert plan["sources"][0]["arrives"]["file"] == "positions_*.csv" and plan["corrections"][0]["by"] == "Leo Park" and plan["version"] == 1  # and the pack, logged
    assert BU.start(plane, LEO, prj)["state"] == "ran"  # not raised again
    with pytest.raises(Refused):
        BU.resolve(plane, GUEST, prj, {"source": "admin", "field": "file", "value": "x"})


def test_variance_explained_and_unexplained_then_send_back_to_the_architect(plane, prj, fake_cmp, revs):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    v = BU.set_benchmark(plane, LEO, prj, {"name": "September report as issued.csv", "text": REPORT})
    var = v["round"]["variance"]
    by = {x["figure"]: x for x in var["lines"] + var["legs"]}
    tot = by["Total holdings, 30 Sep"]
    assert tot["status"] == "explained" and tot["diff"] == "180000" and tot["evidence"][0]["text"] == "Fund A amended 7 Oct" and tot["evidence"][0]["trail"]["id"] == "v1"
    assert by["Fund A"]["status"] == "explained" and by["Portfolio return"]["status"] == "matches" and by["Global equity index"]["status"] == "matches"
    leg = by["Global equity index plus a spread"]
    assert leg["status"] == "unexplained" and leg["run"] == "28.0000" and leg["report"] == "30"  # a plain name, never IDX:GLEQ:SYN
    assert by["Benchmark return"]["status"] == "unexplained" and var["summary"]["unexplained"] == 2 and var["headline"] == "2 unexplained variances"  # the leg, and the benchmark it moves
    assert [u["label"] for u in var["unmatched"]] == ["Pages in this report"]  # shown, not counted
    assert v["can"]["send_back"] and v["can"]["go_live"]
    with pytest.raises(Refused) as e:  # going live over an unexplained variance needs the person to say so
        BU.go_live(plane, LEO, prj, {})
    assert e.value.status == 409
    out = BU.send_back(plane, LEO, prj, "")
    (h,) = H.all_(plane, prj)
    assert h["state"] == "pending" and h["from"] == "builder" and h["what"] == "variance" and any("plus a spread: this run 28.00%, the report 30.00%" in f for f in h["facts"])
    assert out["round"]["state"] == "sent_back" and out["thread"][-1]["who"] == "Span the builder"
    assert H.timeline(plane, prj)[0]["text"].startswith("Span the builder suggested asking Span for a change to the design pack")
    with pytest.raises(Refused):  # the same variance is not filed twice
        BU.send_back(plane, LEO, prj, "")


def test_architect_issues_version_2_and_the_builder_reruns_by_itself(plane, prj, fake_cmp, revs):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    BU.set_benchmark(plane, LEO, prj, {"name": "Sep.csv", "text": REPORT})
    BU.send_back(plane, LEO, prj, "")
    hid = H.all_(plane, prj)[0]["id"]
    with pytest.raises(Refused) as e:
        BU.issue_version(plane, GUEST, prj, {"changes": []})
    assert e.value.status == 403
    new = BU.issue_version(plane, LEO, prj, {"changes": [{"table": gold(prj), "sql": gold_sql(prj) + " order by fund", "why": "private sleeve is 30"}], "handoff_id": hid})
    assert new["version"] == 2 and new["state"] == "proposed" and new["changes"][0]["before"].endswith("group by fund")
    assert H.all_(plane, prj)[0]["state"] == "accepted"
    v = BU.view(plane, LEO, prj)
    assert v["pack"]["version"] == 1 and v["newer"]["version"] == 2  # still version 1 until it is approved
    assert BU.start(plane, LEO, prj)["pack_version"] == 1
    with pytest.raises(Refused):
        B.approve(plane, LEO, prj, 2)  # only the head of data approves, and never the proposer
    B.approve(plane, ANITA, prj, 2)
    fake_cmp["pe"] = "30.0000"
    r = BU.start(plane, LEO, prj)  # no click on a run: the new approved version starts a new round
    assert r["pack_version"] == 2 and r["state"] == "checked" and r["variance"]["summary"]["unexplained"] == 0 and r["variance"]["headline"].startswith("Matches")
    v = BU.view(plane, LEO, prj)
    assert [x["pack_version"] for x in v["rounds"]] == [1, 2] and v["pack"]["change_from"]["version"] == 1
    assert [t["who"] for t in v["thread"]].count("Span the architect") == 1 and "variance is cleared" in v["thread"][-1]["text"]
    live = BU.go_live(plane, LEO, prj, {})
    assert live["round"]["state"] == "live" and live["round"]["outcome"]["kind"] == "live" and B.get(plane, prj, 2)["state"] == "live"
    assert "pack schedule" in live["thread"][-1]["text"]


def test_no_benchmark_means_no_go_live_unless_said(plane, prj, fake_cmp):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    with pytest.raises(Refused) as e:
        BU.go_live(plane, LEO, prj, {})
    assert e.value.status == 409
    assert BU.go_live(plane, LEO, prj, {"no_benchmark": True})["round"]["state"] == "live"


def test_the_report_reader_and_bad_uploads(plane, prj):
    lines = BU.parse_report(REPORT)
    assert [(x["label"], x["value"], x["unit"]) for x in lines][:3] == [("Total holdings, 30 Sep", "57600000", "money"), ("Fund A", "10000000", "money"), ("Portfolio return", "4.17", "pct")]
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    with pytest.raises(Refused) as e:
        BU.set_benchmark(plane, LEO, prj, {"name": "empty.csv", "text": "nothing numeric here"})
    assert e.value.status == 422 and "could not find any figures" in e.value.message
    with pytest.raises(Refused):
        BU.set_benchmark(plane, GUEST, prj, {"name": "a.csv", "text": REPORT})
    assert BU._revisions(plane) == []  # the revision query runs against the real tables


def test_series_keys_read_as_plain_names_and_the_review_form_prefills_from_the_pack(plane, prj):
    assert V.plain_name("IDX:GLEQ:SYN") == "Global equity index" and V.plain_name("IDX:GLEQ:SYN plus spread") == "Global equity index plus a spread"
    assert V.plain_name("UNKNOWN:KEY") == "UNKNOWN:KEY"
    write_pack(plane, prj, [UPLOAD])
    s = V.suggest(plane, LEO, prj)  # WALK 9: the data engineer sees no portfolio, yet the form is not empty
    assert (s["portfolio"], s["code"], s["month"]) == ("EG", "OFFICE", "2026-09")


def test_every_route_is_declared():
    table = yaml.safe_load(Path(BU.__file__).with_name("b11.permissions.yaml").read_text())["routes"]
    assert {f"{m} {r.path}" for r in RT.router.routes for m in r.methods} == set(table)


def test_on_approved_runs_without_a_viewer_and_the_page_checks_the_benchmark(plane, prj, fake_cmp, revs):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    BU.set_benchmark(plane, LEO, prj, {"name": "Sep.csv", "text": REPORT})
    BU.send_back(plane, LEO, prj, "")
    BU.issue_version(plane, LEO, prj, {"changes": [{"table": gold(prj), "sql": gold_sql(prj) + " order by fund", "why": "x"}]})
    B.approve(plane, ANITA, prj, 2)
    fake_cmp["pe"] = "30.0000"
    r = BU.on_approved(plane, prj)  # at approval: no viewer, so it runs but does not read figures
    assert r and r["pack_version"] == 2 and r["state"] == "ran" and r["variance"] is None
    r = BU.start(plane, LEO, prj)  # the page opens: the benchmark check happens once, as the data engineer
    assert r["state"] == "checked" and r["variance"]["summary"]["unexplained"] == 0
    assert BU.start(plane, LEO, prj)["state"] == "checked" and "variance is cleared" in BU.view(plane, LEO, prj)["thread"][-1]["text"]


def test_a_report_none_of_whose_figures_the_run_holds_is_not_cleared(plane, prj, fake_cmp):
    write_pack(plane, prj, [UPLOAD])
    land(plane)
    BU.start(plane, LEO, prj)
    BU.set_benchmark(plane, LEO, prj, {"name": "last.txt", "text": "Net worth by entity 52,400,000\nTime-weighted return 4.17%\n"})
    var = BU.view(plane, LEO, prj)["round"]["variance"]
    assert var["summary"]["unexplained"] == 2 and not var["unmatched"] and all(x["run"] is None for x in var["lines"])
    with pytest.raises(Refused) as e:
        BU.go_live(plane, LEO, prj, {})
    assert e.value.status == 409
    assert BU.send_back(plane, LEO, prj)["round"]["state"] == "sent_back"


def test_h3_a_person_marks_a_sample_less_source_not_needed_and_the_build_runs(plane, prj, fake_cmp):
    phantom = {**UPLOAD, "code": "ghost", "name": "Closing cash figure", "arrives": {"how": "upload", "file": "ghost_*.csv"}}
    write_pack(plane, prj, [UPLOAD, phantom])
    land(plane)  # the real file lands; the phantom never gets one
    r = BU.start(plane, LEO, prj)
    assert {c["code"]: c["status"] for c in r["connections"]}["ghost"] == "needs_sample" and r["state"] == "blocked"
    assert BU.view(plane, LEO, prj)["can"]["not_needed"]
    with pytest.raises(Refused) as e:  # not silent and not for anyone: only the data engineer, only a source waiting for a sample
        BU.set_not_needed(plane, GUEST, prj, {"source": "ghost"})
    assert e.value.status == 403
    with pytest.raises(Refused) as e:
        BU.set_not_needed(plane, LEO, prj, {"source": "admin"})  # it has its sample
    assert e.value.status == 409
    r = BU.set_not_needed(plane, LEO, prj, {"source": "ghost", "reason": "a figure, not a feed"})
    assert {c["code"]: c["status"] for c in r["connections"]}["ghost"] == "not_needed" and r["state"] == "ran"
    rec = BU.load(plane, prj)
    assert rec["needs"] == [] and rec["not_needed"][0]["by"] == "Leo Park" and any("marked Closing cash figure as not needed" in m["text"] for m in rec["thread"])
    assert BU.view(plane, LEO, prj)["not_needed"][0]["code"] == "ghost"
