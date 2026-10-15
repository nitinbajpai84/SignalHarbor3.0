"""B1: Build centre home. Synthetic data only."""
import json
from datetime import date

from sh_platform.build import home
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

V = Viewer("Ann Lee", frozenset({"company_admin"}))
TODAY = date(2026, 10, 6)


def put(plane, rel, data):
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def test_states_from_records(tmp_path):
    plane = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    put(plane, "warehouse/environment.json", {"answers": {"scheduler": {"value": "cron", "mark": "stated", "by": "Ann", "from": "x"}}})
    put(plane, "build/blueprint.json", {"state": "signed", "signed_by": [{"name": "Ann Lee", "role": "x", "at": "t"}]})
    put(plane, "build/pipelines/custody.json", {"source": "custody", "owner": "Sara"})
    put(plane, "warehouse/runs.json", {"runs": [{"source": "custody", "started": "2026-10-06T08:00:00+00:00", "on_time": False, "status": "late", "rules": []}]})
    put(plane, "build/prove.json", {"measures": [
        {"code": "A", "periods": [{"result": "match"}], "uat": {"state": "signed"}},
        {"code": "B", "periods": [{"result": "match"}, {"result": "gap"}], "uat": {"state": "pending"}},
        {"code": "C", "periods": []}], "release": {"state": "signed"}})
    r = {x["room"]: x for x in home.build(plane, V, TODAY)["rooms"]}
    assert r[1]["environment"] == {"confirmed": 1, "of": 6} and r[1]["blueprint"] == {"state": "signed", "signed_by": ["Ann Lee"], "signed_at": "t"}
    assert r[2]["state"] == "next" and r[2]["pipelines"] == {"sources": 1, "last_run": {"ok": 0, "late": 1, "failed": 0}}
    assert r[2]["proven"] == {"match": 1, "gap": 1, "not_yet": 1, "uat_signed": 1} and r[2]["release"] == "signed"
    assert r[3]["state"] == "open" and r[3]["today"] == {"late": 1, "failed": 0, "open_alerts": 1}


def test_empty_company_is_honest_zeros(tmp_path):
    plane = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    r = {x["room"]: x for x in home.build(plane, V, TODAY)["rooms"]}
    assert r[1]["state"] == "open" and r[1]["environment"]["confirmed"] == 0 and r[1]["blueprint"] == {"state": "none", "signed_by": [], "signed_at": None}
    assert r[2]["state"] == "locked" and r[2]["pipelines"]["sources"] == 0 and r[2]["release"] == "none"
    assert r[3]["state"] == "locked" and r[3]["today"] == {"late": 0, "failed": 0, "open_alerts": 0}


def test_detail_lines_say_what_waits(tmp_path):
    plane = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    put(plane, "build/blueprint.json", {"state": "signed", "signed_by": [{"name": "Ann Lee", "role": "x", "at": "2026-06-12T09:00:00"}]})
    put(plane, "build/pipelines/custody.json", {"source": "custody", "owner": "Sara"})
    put(plane, "warehouse/runs.json", {"runs": [{"source": "custody", "started": "2026-10-06T08:00:00+00:00", "on_time": False, "status": "late", "rules": []}]})
    put(plane, "build/prove.json", {"measures": [{"code": "B", "periods": [{"result": "gap"}]}], "release": {"state": "draft"}})
    r = {x["room"]: x for x in home.build(plane, V, TODAY)["rooms"]}
    assert any("signed by Ann Lee on 12 June 2026" in d for d in r[1]["detail"]) and any("6 environment answers wait" in d for d in r[1]["detail"])
    assert "Custody: late, source owner Sara" in r[2]["detail"] and "Measure B: gap" in r[2]["detail"]
    assert r[3]["detail"] == ["Custody: file late, source owner Sara, open since 6 October 2026"]


def test_one_alert_per_id_when_two_sources_feed_a_measure(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    a = {"id": "gold.k02:range", "kind": "outside_range", "measure": "k02", "owner": "Marcus Todd", "opened": "2026-09-09", "state": "open"}
    monkeypatch.setattr(home.ops, "build", lambda *_: {"alerts": [{**a, "source": "custodian_daily_file"}, {**a, "source": "fund_administrator_statements"}]})
    r3 = home.build(plane, V, TODAY)["rooms"][2]
    assert r3["today"]["open_alerts"] == 1
    assert r3["detail"] == ["K02: outside its usual range, owner Marcus Todd, open since 9 September 2026"]
