"""CS1 Daily key numbers: every figure of the band is checked against docs/test/10UC-ANSWER-KEY.md (P01-P07, P14, P16, P21-P22), on the
seeded Evergreen universe (synthetic). Access, the six roles and the route are checked too."""
import json
from datetime import date, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_access, k9_daily, k9_routes, wh
from tools import seed_10uc as S

AS_OF = date(2026, 10, 9)
Q4 = D("0.0001")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("shk9")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    V = S.viewers(ids)
    yield {"plane": plane, "V": V, "usd": k9_daily.daily(plane, V["Daniel Foo"], "USD", AS_OF), "sgd": k9_daily.daily(plane, V["Daniel Foo"], "SGD", AS_OF)}
    mp.undo()


def test_nav_total_and_by_entity(world):
    n = world["usd"]["nav"]
    by = {e["name"]: e["value"] for e in n["by_entity"]}
    assert by["Evergreen Holdings"] == D("16580000") and by["Entity B"] == D("22875000")        # P03, P04: the investment view
    assert n["total"] == sum(by.values()) == D("103405000") and not n["partial"]
    assert n["status"] == "Stale"                                                                # P07: two Cedarpoint funds are stale, the weakest line wins


def test_issued_against_known_now_in_both_currencies(world):
    u, s = world["usd"]["issued"], world["sgd"]["issued"]
    assert (u["issued"], u["known_now"], u["difference"], u["status"]) == (D("57600000"), D("57780000"), D("180000"), "Revised")   # P01, P02
    # the same instant on any machine: DuckDB hands TIMESTAMPTZ back in the host's zone (18:30 in Singapore, 17:30 in Bangkok)
    assert u["issued_at"].astimezone(timezone.utc).isoformat().startswith("2026-10-03T10:30") and "CASE-0001" in u["banner"]
    assert (s["issued"], s["known_now"]) == (D("77253120.00"), D("77494536.00"))                  # P01, P02, P16
    assert u["brief_link"].startswith("/centre/consume/brief/")


def test_month_return_against_the_signed_benchmark(world):
    m = world["usd"]["returns"]["periods"][0]
    assert [x.quantize(Q4) for x in (m["portfolio"], m["benchmark"], m["difference"])] == [D("4.1667"), D("2.7072"), D("1.4595")] and m["certified"]   # P14
    assert world["usd"]["returns"]["benchmark_code"] == "EG-OFFICE-BLEND" and world["usd"]["returns"]["status"] == "Certified"
    ytd = world["usd"]["returns"]["periods"][1]
    assert ytd["start"] == date(2025, 12, 31) and ytd["end"] == date(2026, 9, 30) and ytd["portfolio"] is not None and ytd["benchmark"] is not None
    sgd_ytd = world["sgd"]["returns"]["periods"][1]                    # no signed rate for 31 Dec 2025: said, never guessed
    assert sgd_ytd["portfolio"] is None and sgd_ytd["problems"] and not sgd_ytd["certified"]
    assert "fx_fixing" not in sgd_ytd["message"] and "exchange rate" in sgd_ytd["message"]       # plain words on screen


def test_levers_split_the_liquid_book_move_and_the_movers(world):
    lv = world["usd"]["levers"]
    parts = {p["code"]: p["amount"] for p in lv["parts"]}
    assert parts == {"price": D("1648000"), "trades": 0, "revisions": 0, "fx": 0}                 # P06: the liquid book's own move, not the NAV bridge (UC1-C2-02)
    sp = {p["code"]: p["amount"] for p in world["sgd"]["levers"]["parts"]}
    assert sp["fx"].quantize(D("0.01")) == D("613880.00") and sp["revisions"] == 0 and sum(sp.values()) == world["sgd"]["levers"]["change"]   # P16
    assert [(m["name"], m["amount"]) for m in lv["movers"][:2]] == [("Northwind Logistics", D("132000")), ("Silverpine Software", D("130400"))]   # P06
    assert (lv["change"], lv["percent"], lv["status"]) == (D("1648000"), D("4.1667"), "Fully explained")


def test_market_drivers_month_and_last_day(world):
    s = {x["name"]: x for x in world["usd"]["markets"]["series"]}
    assert s["Global equity index"]["month_change_pct"].quantize(Q4) == D("3.5002") and s["Global bond index"]["month_change_pct"].quantize(Q4) == D("0.4002")   # P14
    assert s["Global equity index"]["day_change_pct"] is None                                      # a monthly index has no last-day move
    assert s["US dollar in Singapore dollars"]["level"] == D("1.3388") and s["US dollar in Singapore dollars"]["day_change_pct"] is not None   # P16


def test_liquidity_headline_and_entity_b(world):
    lq = world["usd"]["liquidity"]
    b = next(e for e in lq["entities"] if e["name"] == "Entity B")
    assert (b["cash"], b["calls_30"], b["cash_after_confirmed"], b["cash_after_all"], b["unconfirmed"]) == (D("880400"), D("1050000"), D("430400"), D("-169600"), 1)  # P21, P22
    assert lq["calls_30"] == D("1050000") and lq["cash_after_confirmed"] == lq["cash"] - D("450000") and "Short" in lq["status"]


def test_every_figure_has_its_own_trail_id_and_a_where_block(world):
    d = world["usd"]
    ids = []
    for k in ("nav", "issued", "returns", "levers", "markets", "liquidity"):
        assert d[k]["trail_id"].startswith("k9:") and d[k]["where"]["text"]
        ids.append(d[k]["trail_id"])
    for key, sub in (("nav", "by_entity"), ("returns", "periods"), ("levers", "parts"), ("levers", "movers"), ("markets", "series"), ("liquidity", "entities")):
        for it in d[key][sub]:
            assert it["trail_id"].startswith("k9:")
            ids.append(it["trail_id"])
    assert len(ids) == len(set(ids))
    assert all(x["where"]["text"] for x in d["markets"]["series"])


def test_a_person_sees_only_their_entities(world, monkeypatch):
    plane, v = world["plane"], world["V"]["Mei Chen"]
    with wh.connect(plane, read_only=True) as con:
        pf = {str(r[0]) for r in con.execute("select p.id from portfolios p join legal_entities e on e.id = p.legal_entity_id where e.entity_code = 'EG-HOLD'").fetchall()}
        ent = {str(r[0]) for r in con.execute("select id from legal_entities where entity_code = 'EG-HOLD'").fetchall()}
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda p, x: set(pf))
    monkeypatch.setattr(e1_access, "visible_entities", lambda p, x: set(ent))
    d = k9_daily.daily(plane, v, "USD", AS_OF)
    assert d["nav"]["partial"] and d["nav"]["total"] is None and [e["name"] for e in d["nav"]["by_entity"]] == ["Evergreen Holdings"]
    assert [e["name"] for e in d["liquidity"]["entities"]] == ["Evergreen Holdings"]
    text = json.dumps(d, default=str)
    assert "Entity B" not in text and "22875000" not in text


def test_a_section_that_fails_says_so_and_the_rest_still_show(world, monkeypatch):
    monkeypatch.setattr(k9_daily, "_markets", lambda *a: 1 / 0)
    d = k9_daily.daily(world["plane"], world["V"]["Daniel Foo"], "USD", AS_OF)
    assert d["markets"] == {"available": False, "message": "Not available yet."} and d["nav"]["available"]


def test_all_six_roles_are_declared():
    cfg = yaml.safe_load((Path(k9_daily.__file__).parent / "k9.permissions.yaml").read_text(encoding="utf-8"))
    assert set(cfg["routes"]) == {"GET /api/v1/consume/daily"}
    assert set(cfg["routes"]["GET /api/v1/consume/daily"]["roles"]) == {"company_admin", "sponsor", "analyst", "owner", "approver", "participant"}


def test_the_route_sends_plain_strings_and_refuses_a_bad_currency(world, monkeypatch):
    monkeypatch.setattr(k9_routes, "viewer_of", lambda r: world["V"]["Daniel Foo"])
    monkeypatch.setattr(k9_routes, "_plane", lambda r: world["plane"])
    app = FastAPI()
    app.include_router(k9_routes.router)
    c = TestClient(app)
    r = c.get("/api/v1/consume/daily?currency=SGD&as_of=2026-10-09")
    assert r.status_code == 200 and r.json()["issued"]["issued"] == "77253120.00" and r.json()["currency"] == "SGD"
    assert "0E-" not in r.text
    assert c.get("/api/v1/consume/daily?currency=EUR").status_code == 400
