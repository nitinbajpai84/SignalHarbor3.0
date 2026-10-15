"""W02: the case view says is_owner; Tally's trade-break, revision and capital-call tools are as deep as the cash path."""
import re

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e4_cases
from sh_platform.v1 import n1_tally as T
from sh_platform.v1 import tally_tools as TT
from sh_platform.v1 import wh
from sh_platform.v1.agent_tools import tools_for
from tools import seed_10uc as S


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("w02")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    yield {"plane": plane, "V": S.viewers(ids)}
    mp.undo()


def reg(world, start, contains=""):
    V, plane = world["V"], world["plane"]
    cid = next(c["id"] for c in e4_cases.listing(plane, V["Grace Ong"]) if c["title"].startswith(start) and contains in c["title"])
    b = T.build(plane, T._exc(plane, cid))
    b["case_id"] = cid
    r = tools_for(plane, V["Mei Chen"], "tally", module_id=TT.MODULE)
    TT.register(r, plane, V["Mei Chen"], cid, b)
    return lambda name, **a: r.call("evergreen", TT.MODULE, name, a)


def test_is_owner_is_explicit_and_an_admin_who_is_not_owner_gets_false(world):
    plane, V = world["plane"], world["V"]
    cid = next(c["id"] for c in e4_cases.listing(plane, V["Grace Ong"]) if c["title"].startswith("Trade not matched"))
    assert e4_cases.get(plane, cid, V["Mei Chen"])["is_owner"] is False          # nobody owns it yet
    e4_cases.take(plane, cid, V["Mei Chen"])
    assert e4_cases.get(plane, cid, V["Mei Chen"])["is_owner"] is True
    assert e4_cases.get(plane, cid, V["Grace Ong"])["is_owner"] is False         # an administrator who is not the owner


def test_trade_break_tool_shows_both_rows_the_differing_field_and_the_money(world):
    got = reg(world, "Trade differs", "Northwind")("get_trade_rows")
    assert len(got["two_sides"]) == 2 and got["two_sides"][0].startswith("trading export amount:") and got["two_sides"][1].startswith("administrator amount:")
    assert any(x.startswith("Quantity: trading export 12,000 shares, administrator 10,200 shares") for x in got["differing_fields"])
    assert "75,870 USD" in " ".join(got["money_impact"])
    gone = reg(world, "Trade not matched")("get_trade_rows")
    assert "two_sides" not in gone and "no matching trade at the administrator" in gone["side_note"][0]


def test_revision_tool_gives_the_statement_chain_old_to_new_with_dates(world):
    got = reg(world, "Investigate the 180,000")("get_statement_chain")
    chain = got["old_to_new"]
    assert len(chain) >= 2 and all(re.search(r"recorded \d{1,2} [A-Z][a-z]{2} 20\d\d", x) and "status" in x and "(final) (final)" not in x for x in chain)
    assert chain.index(next(x for x in chain if "10,000,000 USD" in x)) < chain.index(next(x for x in chain if "10,180,000 USD" in x))
    assert any("180,000 USD" in x for x in got["bridge"])


def test_capital_call_tool_gives_notice_due_date_and_cash_after_the_call(world):
    got = reg(world, "Fund the capital call")("get_call_notice")
    assert "450,000 USD" in got["notice"][0] and "20 Oct 2026" in got["due"]
    assert any("1,950,000 USD still uncalled" in x for x in got["commitment"])
    assert got["after_call_cash"][0].startswith("cash after calls due by") or got["after_call_cash"][0].startswith("Not shown")


def test_each_tool_says_so_on_the_wrong_kind_of_case(world):
    c = reg(world, "Cash differs")
    assert all("not a" in c(n)["note"] for n in ("get_trade_rows", "get_statement_chain", "get_call_notice"))


def test_filing_a_tally_proposal_is_for_the_owner_or_an_admin_only_viewing_and_asking_stay_open(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e4a_routes as R
    plane, V = world["plane"], world["V"]
    cid = next(c["id"] for c in e4_cases.listing(plane, V["Grace Ong"]) if c["title"].startswith("Trade not matched"))
    owner = "Mei Chen"
    if not e4_cases.get(plane, cid, V[owner])["is_owner"]:
        e4_cases.take(plane, cid, V[owner])
    admin = next(n for n, v in V.items() if "company_admin" in v.roles and n != owner)
    other = next(n for n, v in V.items() if n != owner and "company_admin" not in v.roles)
    who = {"v": V[other]}
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: plane)
    monkeypatch.setattr(R, "viewer_of", lambda req: who["v"])
    c = TestClient(app)
    r = c.post(f"/api/v1/cases/{cid}/explain")
    assert r.status_code == 403 and "owns this case" in r.json()["detail"]["message"]
    assert c.get(f"/api/v1/cases/{cid}/tally").status_code == 200
    assert c.post(f"/api/v1/cases/{cid}/ask", json={"question": "why?"}).status_code == 200
    for n in (owner, admin):
        who["v"] = V[n]
        assert c.post(f"/api/v1/cases/{cid}/explain").status_code == 200
