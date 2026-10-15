"""STUDIO2 card D: a sketch read on this machine and mapped to the gold tables. Synthetic labels; one real-picture test when a reader is installed."""
import base64
import io
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient


from sh_platform.v1 import b7_routes, b7s_routes, ocr_local
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7s_sketch as K
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import wh
from sh_platform.v1 import t2_tickets
from tests.v1.test_b7_studio import READER
from tests.v1.test_cx import ADMIN, env  # noqa: F401 - env is a fixture

LABELS = ["Net worth", "Cash runway", "Top managers performance", "Capital calls", "Commitments", "Uncalled commitments", "Weather in Paris"]


@pytest.fixture()
def world(env):
    plane, pid = env
    with wh.connect(plane) as con:
        con.execute("create table gold_monthly_report_cash (month date, cash_balance decimal(18,2))")
        con.execute("insert into gold_monthly_report_cash values ('2026-08-31', 40), ('2026-09-30', 35)")
        con.execute("create table gold_monthly_report_managers (manager varchar, ytd_return double, month_return double)")
        con.execute("insert into gold_monthly_report_managers values ('A', 0.1, 0.01), ('B', 0.2, 0.02)")
        con.execute("create table gold_monthly_report_commitments (fund varchar, commitment decimal(18,2))")
        con.execute("insert into gold_monthly_report_commitments values ('F1', 10), ('F2', 20)")
    for n in ("cash", "managers", "commitments"):
        cat.register_gold(plane, pid, "monthly_report", n, [{"name": "x", "type": "int"}])
    return plane, pid


def by_label(boxes):
    return {b["label"]: b for b in boxes}


def test_labels_map_to_tables_with_the_right_status(world):
    plane, pid = world
    b = by_label(K.read_sketch(plane, pid, {"name": "Board", "labels": LABELS})["boxes"])
    assert b["Net worth"]["status"] == "possible" and b["Net worth"]["maps_to"]["table"] == "gold_monthly_report_holdings" and b["Net worth"]["maps_to"]["measure"] == "net_worth"
    assert b["Cash runway"]["status"] == "possible" and b["Cash runway"]["maps_to"] == {"table": "gold_monthly_report_cash", "measure": "cash_balance", "kind": "line"}
    top = b["Top managers performance"]
    assert top["status"] == "needs_definition" and top["question"] == "Rank by month or year to date?" and top["maps_to"]["table"] == "gold_monthly_report_managers"
    assert b["Commitments"]["status"] == "possible" and b["Commitments"]["maps_to"]["measure"] == "commitment"
    cc = b["Capital calls"]
    assert cc["status"] == "not_possible" and "notices" in cc["needs"] and "maps_to" not in cc
    assert b["Weather in Paris"]["status"] == "not_possible" and "ask the data team" in b["Weather in Paris"]["needs"]
    assert b["Uncalled commitments"]["status"] == "needs_definition" and "uncalled" in b["Uncalled commitments"]["question"]


def test_fuzzy_spelling_and_a_named_period_means_no_rank_question(world):
    plane, pid = world
    b = by_label(K.read_sketch(plane, pid, {"labels": ["Comitments", "Top managers performance this month"]})["boxes"])
    assert b["Comitments"]["status"] == "possible"
    assert "Rank by" not in b["Top managers performance this month"].get("question", "")


def test_positions_set_layout_order_and_the_largest_box_is_the_headline(world):
    plane, pid = world
    boxes = [{"label": "Cash runway", "x": 0, "y": 200, "w": 100, "h": 30}, {"label": "Net worth", "x": 100, "y": 10, "w": 400, "h": 160},
             {"label": "Commitments", "x": 300, "y": 200, "w": 100, "h": 30}]
    out = K.read_sketch(plane, pid, {"labels": boxes})["boxes"]
    assert [b["label"] for b in out] == ["Net worth", "Cash runway", "Commitments"]
    assert [(b["row"], b["col"]) for b in out] == [(0, 0), (1, 0), (1, 1)] and [b["headline"] for b in out] == [True, False, False]
    assert out[0]["maps_to"]["kind"] == "figure"
    typed = K.read_sketch(plane, pid, {"labels": ["a1", "Net worth", "c3"]})["boxes"]  # no positions: three to a row, the middle one leads
    assert [b["headline"] for b in typed] == [False, True, False]


def test_nothing_to_read_is_a_clear_refusal(world, monkeypatch):
    plane, pid = world
    with pytest.raises(K.Refused) as e:
        K.read_sketch(plane, pid, {})
    assert e.value.status == 400
    monkeypatch.setattr(ocr_local, "available", lambda: False)
    with pytest.raises(K.Refused) as e:
        K.read_sketch(plane, pid, {"data": base64.b64encode(b"x").decode()})
    assert e.value.status == 409 and "Type the box labels" in e.value.message
    assert K.read_sketch(plane, pid, {"data": "ignored", "labels": ["Net worth"]})["boxes"]  # typed labels need no reader


def test_build_places_only_possible_boxes_and_records_a_step(world):
    plane, pid = world
    d = S.create(plane, ADMIN, pid, "Board")
    boxes = K.read_sketch(plane, pid, {"labels": LABELS})["boxes"]
    boxes[0]["headline"] = True  # the sketch's first box (Net worth) is the headline
    got = K.build(plane, ADMIN, pid, d["id"], {"boxes": boxes})
    poss = [b for b in boxes if b["status"] == "possible"]
    assert got["placed"] == len(poss) >= 3 and got["left_out"] == len(boxes) - len(poss) and isinstance(got["step"], int)
    items = S.view(plane, ADMIN, pid, d["id"])["layout"]["items"]
    assert len(items) == len(poss) and items[0]["size"] == "wide" and (items[0]["row"], items[0]["col"]) == (0, 0)  # the headline leads, wide
    with pytest.raises(K.Refused):
        K.build(plane, ADMIN, pid, d["id"], {"boxes": ["b1"]})  # ids alone are not enough: the sketch is not kept
    bad = [{"status": "possible", "maps_to": {"table": "gold_other_x", "measure": "a", "kind": "figure"}}]
    with pytest.raises(K.Refused):
        K.build(plane, ADMIN, pid, d["id"], {"boxes": bad})  # a client-sent mapping is checked again


def test_request_raises_one_data_team_ticket(world):
    plane, pid = world
    boxes = K.read_sketch(plane, pid, {"labels": LABELS})["boxes"]
    got = K.request(plane, ADMIN, pid, {"boxes": boxes})
    t = t2_tickets.get(plane, got["request_id"])
    assert t["project"] == pid and t["stage"] == "build" and "Capital calls" in t["body"] and "Rank by month" in t["body"] and "Net worth" not in t["body"]
    with pytest.raises(K.Refused):
        K.request(plane, ADMIN, pid, {"boxes": [b for b in boxes if b["status"] == "possible"]})


def test_routes_are_declared_makers_only_and_work(world, monkeypatch):
    plane, pid = world
    declared = yaml.safe_load((Path(b7s_routes.__file__).parent / "b7s.permissions.yaml").read_text())["routes"]
    assert {f"{m} {r.path}" for r in b7s_routes.router.routes for m in r.methods} == set(declared)
    cur = {"v": READER}
    monkeypatch.setattr(b7_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(b7_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(b7s_routes.router)
    c = TestClient(app)
    d = S.create(plane, ADMIN, pid, "Board")
    base = f"/api/v1/build/p/{pid}/studio/{d['id']}/sketch"
    assert c.post(base, json={"labels": ["Net worth"]}).status_code == 403
    cur["v"] = ADMIN
    out = c.post(base, json={"labels": LABELS}).json()
    assert {b["status"] for b in out["boxes"]} == {"possible", "needs_definition", "not_possible"}
    r = c.post(base + "/build", json={"boxes": out["boxes"]}).json()
    assert r["placed"] >= 3 and r["dashboard"]["layout"]["items"]
    assert c.post(base + "/request", json={"boxes": out["boxes"]}).json()["request_id"].startswith("TCK-")
    assert c.post(base, json={}).status_code == 400


@pytest.mark.skipif(not ocr_local.available(), reason="no local picture reader")
def test_a_real_picture_is_read_with_positions(world):
    from PIL import Image, ImageDraw, ImageFont
    plane, pid = world
    im = Image.new("RGB", (900, 500), "white")
    dr, f = ImageDraw.Draw(im), ImageFont.load_default(size=44)
    for text, xy in (("Net worth", (300, 40)), ("Cash runway", (40, 300)), ("Commitments", (500, 300))):
        dr.rectangle([xy[0] - 10, xy[1] - 10, xy[0] + 330, xy[1] + 70], outline="black", width=3)
        dr.text(xy, text, fill="black", font=f)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    out = K.read_sketch(plane, pid, {"data": base64.b64encode(buf.getvalue()).decode()})["boxes"]
    assert [b["label"] for b in out][:1] == ["Net worth"] and out[0]["row"] == 0
    assert sum(b["status"] == "possible" for b in out) >= 3


def test_the_heading_is_the_title_a_bracket_note_joins_its_box_and_currency_twins_need_no_question():
    from sh_platform.v1 import b7s_sketch as K
    boxes = [{"label": "Morning dashboard for the family", "x": 60, "y": 30, "w": 900, "h": 60},
             {"label": "Net worth trend", "x": 600, "y": 230, "w": 420, "h": 50},
             {"label": "ESG score", "x": 1060, "y": 820, "w": 220, "h": 40},
             {"label": "(maybe later?)", "x": 890, "y": 1000, "w": 250, "h": 30}]
    title, rest = K._title_of(boxes)
    assert title == "Morning dashboard for the family" and len(rest) == 3
    kept = K._attach_notes(rest)
    assert [b["label"] for b in kept] == ["Net worth trend", "ESG score"] and kept[1]["note"] == "maybe later?"
    assert K._twin("net_worth_usd", "net_worth_sgd") and not K._twin("cash_usd", "net_worth_usd")
