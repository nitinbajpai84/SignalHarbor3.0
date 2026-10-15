"""STUDIO2 B: Lumen's chart checks on synthetic dashboards. Rules only."""
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7k_checks as K
from sh_platform.v1 import b7k_routes
from tests.v1.test_cx import ADMIN, GOLD, env  # noqa: F401 - env is a fixture


def tile(tid, mark="line", view=None, kpi="net_worth", y=None, color=None):
    enc = {"y": {"field": "net_worth", "type": "quantitative", **(y or {})}} | ({"color": {"field": color}} if color else {})
    spec = {"mark": "text", "usermeta": {"view": view}, "encoding": {}} if view else {"mark": {"type": mark}, "encoding": enc}
    return {"id": tid, "title": "T " + tid, "kpi": kpi, "spec": spec, "sql": "", "state": "accepted"}


def lay(*sizes):
    items = [{"id": f"w{i}", "kind": "lumen", "tile": f"t{i}", "title": f"T t{i}", "size": s, "row": i, "col": 0} for i, s in enumerate(sizes)]
    return {"rows": len(items), "items": items}


def one(t, rows, size="medium"):
    return K.run(lay(size), [t | {"id": "t0"}], lambda _t: rows)


def kinds(cs):
    return {c["kind"] for c in cs}


def test_counted_twice_stacked_sources_fix_side_by_side():
    rows = [{"d": 1, "who": w, "net_worth": 5} for w in ("Administrator", "Trading desk")]
    cs = one(tile("t", "bar", color="who"), rows)
    c = next(c for c in cs if c["kind"] == "counted_twice")
    assert c["widget"] == "w0" and c["fix"]["patch"] == {"stack": False} and c["fix"]["tile"] == "t0"
    assert "counted_twice" not in kinds(one(tile("t", "bar", color="who", y={"stack": False}), rows))
    assert "counted_twice" not in kinds(one(tile("t", "bar", color="who"), [{"who": "Fund A", "net_worth": 1}, {"who": "Fund B", "net_worth": 2}]))  # two funds are two funds
    assert "counted_twice" in kinds(one(tile("t", "area", color="source"), [{"source": "A", "net_worth": 1}, {"source": "B", "net_worth": 2}]))


def test_flattened_trend_only_when_zero_flattens_it():
    flat = [{"net_worth": v} for v in (100, 102, 101, 103)]
    c = next(c for c in one(tile("t"), flat) if c["kind"] == "flattened_trend")
    assert c["fix"]["patch"] == {"scale_zero": False}
    assert "flattened_trend" not in kinds(one(tile("t"), [{"net_worth": v} for v in (50, 100, 150)]))
    assert "flattened_trend" not in kinds(one(tile("t", y={"scale": {"zero": False}}), flat))
    assert "flattened_trend" not in kinds(one(tile("t", "bar"), flat))


def test_space_only_for_few_rows_in_a_big_slot():
    rows = [{"a": 1}, {"a": 2}]
    c = next(c for c in one(tile("t", view="status", kpi=""), rows, "wide") if c["kind"] == "space")
    assert c["fix"]["patch"] == {"size": "small"}
    assert "space" not in kinds(one(tile("t", view="status", kpi=""), rows, "small"))
    assert "space" not in kinds(one(tile("t", view="table", kpi=""), [{"a": i} for i in range(20)], "full"))


def test_too_many_over_nine_tiles_and_notes_do_not_count():
    layout = lay(*["small"] * 10)
    tiles = [tile(f"t{i}", view="figure", kpi="") for i in range(10)]
    assert [c["kind"] for c in K.run(layout, tiles, lambda _t: [])] == ["too_many"]
    layout["items"][0]["kind"] = "note"
    assert not K.run(layout, tiles, lambda _t: [])


def test_house_style_money_percent_and_format_present():
    c = next(c for c in one(tile("t", view="figure"), []) if c["kind"] == "house_style")
    assert c["fix"]["patch"] == {"number_format": "currency"}
    assert one(tile("t", view="figure", kpi="return_pct"), [])[0]["fix"]["patch"] == {"number_format": "percent"}
    assert not one(tile("t", y={"format": "$,.0f"}), [{"net_worth": v} for v in (1, 100, 300)])
    assert not one(tile("t", view="figure", kpi="headcount"), [])


def test_end_to_end_route_reads_real_dashboard_and_is_declared(env, monkeypatch):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Board")
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "figure", "table": GOLD, "row": 0, "col": 0, "size": "small"})
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "status", "table": GOLD, "row": 1, "col": 0, "size": "wide"})
    from sh_platform.v1 import b7_routes as R
    monkeypatch.setattr(R, "viewer_of", lambda request: ADMIN)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(b7k_routes.router)
    got = TestClient(app).get(f"/api/v1/build/p/{pid}/studio/{d['id']}/checks")
    assert got.status_code == 200
    cs = got.json()["checks"]
    assert "house_style" in kinds(cs) and all(c["widget"].startswith("w-") for c in cs)
    declared = yaml.safe_load(Path(K.__file__).with_name("b7k.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    assert {f"{m} {r.path}" for r in b7k_routes.router.routes for m in r.methods} == set(declared)


def test_bars_already_side_by_side_are_not_counted_twice():
    from sh_platform.v1 import b7k_checks as K
    spec = {"mark": {"type": "bar"}, "encoding": {"x": {"field": "entity"}, "y": {"field": "cash_usd"}, "color": {"field": "view_type"}, "xOffset": {"field": "view_type"}}}
    rows = [{"entity": "B", "view_type": "administrator", "cash_usd": 1}, {"entity": "B", "view_type": "trading export", "cash_usd": 1}]
    assert K._counted_twice({"id": "w1", "title": "Cash", "tile": "t1"}, spec, rows) is None
