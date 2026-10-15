"""B16 (spec 29): the business glossary. Synthetic people and terms; a small app with only the glossary router."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m2_baseline.domain import ambiguities as A
from sh_platform.intents import glossary as GL
from sh_platform.intents import store as S
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

CO = "ardmore"
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "daniel": ("Daniel Kerr", ["sponsor"]), "aaron": ("Aaron Lyle", ["participant"]),
         "harvey": ("Harvey Rowley", ["owner"]), "zed": ("Zed Lee", ["participant"])}
IID = "ini-" + "a" * 32


def who(aid: str, shared: bool = False) -> Viewer:
    return Viewer(ACCTS[aid][0], frozenset(ACCTS[aid][1]), shared, aid)


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r} for a, (n, r) in ACCTS.items()]


def person(aid):
    return {"name": ACCTS[aid][0], "account_id": aid}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    S.create_intent(plane, {
        "id": IID, "type": "initiative", "title": "Fund performance reporting", "purpose": "One view of net return for the family",
        "created_by": "janet", "created_at": "2026-10-01T00:00:00Z", "company": CO, "areas": ["Finance"], "state": "open",
        "people": {"organiser": person("janet"), "sponsor": person("daniel"), "decider": None, "owner": None, "reporter": None,
                   "participants": [person("aaron"), person("harvey")], "advisers": [], "affected": [], "observers": []},
        "outcome": {"kind": "initiative", "glossary": {"baseline_id": "b1", "terms": 0, "questions_asked": {}}}})
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(GL.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        aid = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = aid, CO, ACCTS[aid][1]
        return await call_next(request)

    return SimpleNamespace(plane=plane, c=TestClient(app))


def entry(owner_by="Lens"):
    cell = lambda v, by="Lens": {"value": v, "mark": "guessed", "by": by, "from": "cards", "at": "2026-10-01"}  # noqa: E731
    return {"kpi_id": "k1", "term": cell("Net return"), "aliases": cell(None), "business_definition": cell("Return after all fees."),
            "owner": cell("Harvey Rowley", owner_by), "previous": {"value": None, "mark": "unknown"}, "change": "new", "reviewed": None}


def test_term_found_from_cards_and_anonymous_card_never_quoted():
    cards = [{"n": 12, "lane": "Operations lane", "text": "The net return in the fund pack is late"},
             {"n": 13, "text": "Our NAV is wrong", "anonymous": True}, {"n": 14, "text": "Nothing here"}]
    found = GL.terms_in_cards(cards, [{"term": "Net return"}, {"term": "Net asset value", "aliases": ["NAV"]}, {"term": "Exposure"}])
    assert found == [{"term": "Net return", "sources": ["Card 12 (Operations lane)"]}, {"term": "Net asset value", "sources": [GL.ANON]}]


def test_owner_mine_confirms_and_not_mine_releases():
    e = GL.owner_reply(entry(), who("harvey"), mine=True)
    assert e["reviewed"]["by"] == "Harvey Rowley" and e["decided"]["choice"] == "ours"
    e = GL.owner_reply(entry(), who("harvey"), mine=True, wording="Return after fees and tax.")
    assert e["business_definition"]["mark"] == "stated" and e["decided"]["choice"] == "edited"
    e = GL.owner_reply({**entry(), "reviewed": {"by": "x", "at": "y"}}, who("harvey"), mine=False, new_owner="Aaron Lyle")
    assert e["owner"]["value"] == "Aaron Lyle" and e["reviewed"] is None
    with pytest.raises(GL.Refused, match="Ask the sponsor, Daniel Kerr"):
        GL.owner_reply(entry(owner_by="Daniel Kerr"), who("harvey"), mine=False, sponsor="Daniel Kerr")
    with pytest.raises(GL.Refused):
        GL.owner_reply(entry(), who("aaron"), mine=True)  # not the owner
    with pytest.raises(GL.Refused):
        GL.owner_reply(entry(), who("harvey", shared=True), mine=True)  # a shared name holds nothing (A-044b)


def test_ambiguity_accepted_as_risk_only_by_a_settler_with_a_reason():
    kpi = {"id": "k1", "ambiguities": [A.make("other", "return has three meanings", "Which return?", "glossary", id="amb-1")]}
    with pytest.raises(GL.Refused):
        GL.accept_as_risk(kpi, "amb-1", "Known and fine", who("aaron"))
    with pytest.raises(GL.Refused, match="reason"):
        GL.accept_as_risk(kpi, "amb-1", "  ", who("janet"))
    out = GL.accept_as_risk(kpi, "amb-1", "Fund reports keep both", who("aaron"), governance_lead="aaron")
    a = out["ambiguities"][0]
    assert a["status"] == "accepted" and a["reason"] == "Fund reports keep both" and a["by"] == "Aaron Lyle"
    assert GL.ready([{**entry(), "reviewed": {"by": "h", "at": "t"}}], out["ambiguities"])


def test_one_definition_company_wide_and_a_change_is_a_version(env):
    t, how = GL.add_term(env.plane, "Net return", "Return after all fees.", "Harvey Rowley", "Janet Shaw", IID)
    assert how == "created" and t["term_id"] == "net-return"
    assert GL.add_term(env.plane, "net  RETURN", "Return after all fees", None, "Katie", IID)[1] == "reused"
    _, how = GL.add_term(env.plane, "Net return", "Return after fees and tax.", None, "Katie", IID)
    terms = GL.load_terms(env.plane)
    assert how == "proposed" and len(terms) == 1 and terms[0]["definition"] == "Return after all fees."
    pid = terms[0]["proposals"][0]["id"]
    with pytest.raises(GL.Refused):
        GL.decide_proposal(env.plane, "net-return", pid, True, who("aaron"))
    out = GL.decide_proposal(env.plane, "net-return", pid, True, who("harvey"))
    assert out["definition"] == "Return after fees and tax."
    versions = json.loads(env.plane.path("graph", "versions.json").read_text(encoding="utf-8"))["term:net-return"]
    assert [v["v"] for v in versions] == [1, 2] and versions[1]["ref"] == IID and versions[1]["by"] == "Harvey Rowley"


def test_glossary_start_lookup_and_visibility(env):
    GL.add_term(env.plane, "Net return", "Return after all fees.", "Harvey Rowley", "Janet Shaw", IID)
    GL.add_term(env.plane, "Headcount", "People on the payroll.", None, "Janet Shaw", IID)
    GL.add_term(env.plane, "Fund fees", "Secret fee basis for the fund.", None, "Janet Shaw", IID, restricted=True)
    r = env.c.get(f"/api/intents/{IID}/glossary-start", headers={"x-who": "aaron"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [t["term"] for t in body["terms"]] == ["Net return", GL.RESTRICTED]
    assert "term_id" not in body["terms"][1] and body["baseline_id"] == "b1" and body["questions_left"] == 3
    admin = env.c.get(f"/api/intents/{IID}/glossary-start", headers={"x-who": "janet"}).json()
    assert [t["term"] for t in admin["terms"]] == ["Net return", "Fund fees"]
    assert env.c.get(f"/api/intents/{IID}/glossary-start", headers={"x-who": "zed"}).status_code == 404
    assert env.c.get("/api/intents/ini-" + "b" * 32 + "/glossary-start").status_code == 404


def test_question_cap_of_three_shared_across_define(env):
    env.plane.path("intents", IID, "processes.json").write_text(json.dumps(
        {"questions": [{"state": "open", "to_person": "Harvey Rowley"}, {"state": "answered", "to_person": "Harvey Rowley"}]}), encoding="utf-8")
    rec = S.read_intent(env.plane, IID)
    assert GL.question_budget(env.plane, rec, "harvey", "Harvey Rowley") == 2  # one already open on the process map
    assert [GL.ask(env.plane, rec, "harvey", "Harvey Rowley") for _ in range(3)] == ["owner", "owner", "governance_lead"]
    assert rec["outcome"]["glossary"]["questions_asked"] == {"harvey": 2}
    assert GL.question_budget(env.plane, rec, "harvey", "Harvey Rowley") == 0
    assert GL.ask(env.plane, rec, None, "") == "governance_lead"


def test_company_term_routes_proposal_becomes_a_version_only_when_owner_confirms(env):
    GL.add_term(env.plane, "Net return", "Return after all fees.", "Harvey Rowley", "Janet Shaw", IID)
    GL.add_term(env.plane, "Fund fees", "Secret fee basis.", None, "Janet Shaw", IID, restricted=True)
    rows = env.c.get("/api/intents/glossary/terms", headers={"x-who": "aaron"}).json()["terms"]
    assert [r["term"] for r in rows] == ["Net return", GL.RESTRICTED] and "term_id" not in rows[1]
    assert env.c.get("/api/intents/glossary/terms/fund-fees", headers={"x-who": "aaron"}).status_code == 404
    base = "/api/intents/glossary/terms/net-return/proposals"
    assert env.c.post(base, json={"wording": "x", "reason": "y"}, headers={"x-who": "zed"}).status_code == 403  # in no Initiative
    r = env.c.post(base, json={"wording": "Return after fees and tax.", "reason": "Tax matters", "intent_id": IID}, headers={"x-who": "aaron"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert env.c.get("/api/intents/glossary/terms/net-return", headers={"x-who": "aaron"}).json()["proposals"] == []  # owner only
    assert env.c.post(f"{base}/{pid}/confirm", headers={"x-who": "aaron"}).status_code == 403
    assert len(env.c.get("/api/intents/glossary/terms/net-return", headers={"x-who": "harvey"}).json()["versions"]) == 1
    assert env.c.post(f"{base}/{pid}/confirm", headers={"x-who": "harvey"}).status_code == 200
    got = env.c.get("/api/intents/glossary/terms/net-return", headers={"x-who": "harvey"}).json()
    assert got["definition"] == "Return after fees and tax." and len(got["versions"]) == 2


def test_owner_and_settler_replies_write_entry_company_term_and_version(env):
    from modules.m2_baseline.domain import worklist as W
    from modules.m2_baseline.domain.provenance import prov
    from modules.m2_baseline.store import baseline as B
    from modules.m2_baseline.store import glossary as SG
    from modules.m2_baseline.store import kpis as K
    base, _ = B.start(env.plane, None)
    bid = base["id"]
    for i, name in enumerate(["Net return", "Exposure", "Drawdown"]):
        k = W.new_kpi(f"kpi-{i}", name, [], None, prov(f"{name} as the fund pack says.", "stated", "Pat", "the work list"))
        k["governance"] = {"personal": "no", "sensitive": False, "may_see": []}
        k["owners"]["business"] = prov("Harvey Rowley", "stated", "Pat", "the work list")
        K.add(env.plane, bid, k)
    SG.build(env.plane, bid, lambda k: True)
    K.change(env.plane, bid, "kpi-1", lambda k: {**k, "ambiguities": [A.make("other", "exposure to one issuer", "Which exposure?", "glossary", id="amb-1")]})
    K.change(env.plane, bid, "kpi-2", lambda k: {**k, "ambiguities": [A.make("other", "peak to trough", "Which drawdown?", "glossary", id="amb-2")]})
    rec = {**S.read_intent(env.plane, IID), "outcome": {"glossary": {"baseline_id": bid}}}
    ctx = SimpleNamespace(sees=lambda k: True, people=lambda: [{"account_id": a, "display_name": n} for a, (n, _) in ACCTS.items()])
    reply = lambda kid, who_, **b: GL._reply(ctx, env.plane, rec, who(who_), kid, b)  # noqa: E731
    ent = lambda kid: next(e for e in SG.read(env.plane, bid)["entries"] if e["kpi_id"] == kid)  # noqa: E731
    versions = lambda t: json.loads(env.plane.path("graph", "versions.json").read_text(encoding="utf-8")).get("term:" + t, [])  # noqa: E731

    with pytest.raises(GL.Refused):
        reply("kpi-0", "aaron", action="mine")  # not the owner
    assert reply("kpi-0", "harvey", action="mine", wording="Net return after fees and tax.")["company_term"] == "created"
    assert ent("kpi-0")["reviewed"]["by"] == "Harvey Rowley" and GL.load_terms(env.plane)[0]["definition"] == "Net return after fees and tax."
    assert len(versions("net-return")) == 1
    with pytest.raises(GL.Refused, match="pick someone"):
        reply("kpi-1", "harvey", action="not_mine", owner="Nobody Here")
    assert reply("kpi-1", "harvey", action="not_mine", owner="Aaron Lyle")["owner"] == "Aaron Lyle"
    assert ent("kpi-1")["owner"]["value"] == "Aaron Lyle" and not ent("kpi-1")["reviewed"] and len(versions("exposure")) == 1
    assert reply("kpi-2", "harvey", action="both_used", amb_id="amb-2", note="Both are in the board pack.")["done"] == "both_used"
    a = K.read_kpis(env.plane, bid)[2]["ambiguities"][0]
    assert a["status"] == "accepted" and a["reason"] == "Both are in the board pack." and a["asked"]["owner"] == "Harvey Rowley"
    with pytest.raises(GL.Refused):
        reply("kpi-1", "aaron", action="keep_both", amb_id="amb-1", second_term="Issuer exposure")  # not a settler
    out = reply("kpi-1", "janet", action="keep_both", amb_id="amb-1", second_term="Issuer exposure")
    assert out["second_term"] == "Issuer exposure" and {t["term"] for t in GL.load_terms(env.plane)} == {"Net return", "Issuer exposure"}
    assert K.read_kpis(env.plane, bid)[1]["ambiguities"][0]["status"] == "settled"
    reply("kpi-2", "janet", action="reopen", amb_id="amb-2", reason="The fund pack changed.")
    assert K.read_kpis(env.plane, bid)[2]["ambiguities"][0]["status"] == "open" and not ent("kpi-2")["reviewed"]
    with pytest.raises(GL.Refused, match="why you are reopening"):
        reply("kpi-0", "janet", action="reopen", reason=" ")
