"""B29 (12, 20, 21): past timeline, links and the chain, Intent nodes on the map, the backlog. Synthetic people only."""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import backlog as B
from sh_platform.intents import lifecycle as L
from sh_platform.intents import links as K
from sh_platform.intents import past as P
from sh_platform.intents import store as S
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store
from sh_platform.profile.view import Viewer

CO = "ardmore"
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "aaron": ("Aaron Lyle", ["participant"]), "harvey": ("Harvey Rowley", ["owner"]),
         "zed": ("Zed Lee", ["participant"])}
TEAMS = {"janet": "Strategy", "aaron": "Treasury", "harvey": "Operations", "zed": "Legal"}


def V(aid):
    return Viewer(ACCTS[aid][0], frozenset(ACCTS[aid][1]), False, aid)


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, _):
        return [{"account_id": a, "display_name": n, "roles": r} for a, (n, r) in ACCTS.items()]


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    profile_store.mutate(plane, lambda d: d["people"].update(
        {a: {"name": c(ACCTS[a][0]), "team": c(TEAMS[a]), "areas": c([TEAMS[a]]), "account_id": c(a)} for a in ACCTS}))
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    for r in (P.router, K.router, B.router):
        app.include_router(r)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)
    return SimpleNamespace(plane=plane, c=TestClient(app))


def make(env, type_="brainstorm", state="closed", areas=("Treasury",), at="2026-09-10T09:00:00+00:00", title="Custody ideas", **kw):
    rec = L.new_record(type_, CO, L.person("janet", "Janet Shaw"), "2026-09-01T09:00:00+00:00", title=title, purpose="Lower custody fees",
                       areas=list(areas))
    rec["state"] = state
    if state in ("closed", "cancelled"):
        rec["closure"].update(closed_by="janet", closed_at=at)
    if state == "closed":
        rec["closure"].update(what_came_out="One checklist for all funds. Then more.", next=kw.pop("next", []))
    if state == "cancelled":
        rec["closure"]["cancel_reason"] = "Overtaken by the audit."
    for k, v in kw.items():
        rec[k] = v
    return S.create_intent(env.plane, rec)


def call(env, who, method, path, body=None):
    return env.c.request(method, path, json=body or {}, headers={"x-who": who})


# ---- 12: past ----------------------------------------------------------------------------------------------------------------

def test_timeline_by_month_and_area(env):
    make(env, at="2026-09-10T09:00:00+00:00", areas=("Treasury", "Operations"))
    make(env, type_="problem", at="2026-10-02T09:00:00+00:00", areas=("Operations",), title="Late statement file")
    make(env, state="open", title="Still running")
    out = P.past_list(env.plane, V("janet"), {})
    assert [m["month"] for m in out["months"]] == ["2026-10", "2026-09"]
    sep = out["months"][1]
    assert sep["count"] == 1 and [b["area"] for b in sep["bands"]] == ["Operations", "Treasury"]
    also = {b["area"]: b["cards"][0] for b in sep["bands"]}
    assert also["Treasury"]["first"] and also["Operations"]["also_in"] == ["Treasury"]  # once in counts, marked in the other band
    assert out["count"] == 2 and out["types"]["problem"] == 1
    card = out["months"][0]["bands"][0]["cards"][0]
    assert card["outcome_line"] == "One checklist for all funds." and card["organiser"] == "Janet Shaw"
    assert P.past_list(env.plane, V("janet"), {"area": "Treasury"})["count"] == 1
    assert P.past_list(env.plane, V("janet"), {"q": "statement"})["similar"] == {"count": 1, "term": "statement"}


def test_cancelled_shown_with_reason_and_drafts_never(env):
    make(env, state="cancelled", at="2026-09-12T09:00:00+00:00")
    make(env, state="draft", title="My draft")
    out = P.past_list(env.plane, V("janet"), {"outcome": "cancelled"})
    c = out["months"][0]["bands"][0]["cards"][0]
    assert c["state"] == "cancelled" and c["cancel_reason"] == "Overtaken by the audit."
    assert out["counters"]["cancelled"] == 1 and out["outcomes"]["cancelled"] == 1
    assert all(c["title"] != "My draft" for m in out["months"] for b in m["bands"] for c in b["cards"])


def test_restricted_never_reaches_outside_viewer(env):
    rec = make(env, areas=("Treasury",), title="Treasury only")
    assert P.past_list(env.plane, V("zed"), {})["count"] == 0  # Legal, not named: sees nothing, not even a count
    assert P.past_list(env.plane, V("aaron"), {})["count"] == 1  # tagged to Treasury: the card
    assert K.chain(env.plane, V("zed"), rec["id"]) is None
    assert call(env, "zed", "GET", f"/api/intents/{rec['id']}/chain").status_code == 404


def test_history_note_and_share_request(env):
    rec = make(env)
    assert call(env, "aaron", "POST", f"/api/intents/{rec['id']}/history-notes", {"text": "x"}).status_code == 403
    r = call(env, "janet", "POST", f"/api/intents/{rec['id']}/history-notes", {"text": "The fee dropped in November."})
    assert r.status_code == 200 and S.read_intent(env.plane, rec["id"])["history"][-1]["note"] == "The fee dropped in November."
    assert call(env, "aaron", "POST", f"/api/intents/{rec['id']}/share-request").status_code == 200
    assert call(env, "janet", "POST", f"/api/intents/{rec['id']}/share-request").status_code == 409


# ---- 20: links, chain, pre-fill, graph -------------------------------------------------------------------------------------

def test_turn_into_writes_both_records(env):
    src = make(env, outcome={**L.empty_outcome("brainstorm"), "chosen": {"idea": "One custody checklist for all four funds"}})
    body = {"version": src["version"], "to_kind": "initiative", "title": "", "carry": {"people": ["Janet Shaw"]}}
    assert call(env, "aaron", "POST", f"/api/intents/{src['id']}/links", body).status_code in (403, 404)
    assert call(env, "janet", "POST", f"/api/intents/{src['id']}/links", {**body, "to_kind": "pulse"}).status_code == 422
    assert call(env, "janet", "POST", f"/api/intents/{src['id']}/links", {**body, "version": 99}).status_code == 409
    r = call(env, "janet", "POST", f"/api/intents/{src['id']}/links", body)
    assert r.status_code == 201, r.text
    tid = r.json()["target"]["id"]
    s, t = S.read_intent(env.plane, src["id"]), S.read_intent(env.plane, tid)
    assert s["links"]["to"] == [tid] and t["links"]["from"] == src["id"] and t["state"] == "draft"
    assert [x["dir"] for x in K.log_of(s)] == ["to"] and [x["dir"] for x in K.log_of(t)] == ["from"]
    goal = t["start_answers"]["goal"]  # file 22's cell: the line pre-filled, the why left for the person, marked as North's copy
    assert goal["value"] == {"line": "One custody checklist for all four funds", "why": ""} and goal["mark"] == "guessed"
    assert "link_log" in t and "log" not in t["links"]  # the link log is a top-level store key, kept once
    assert K.link_intents(env.plane, src["id"], tid, "initiative") == r.json()["link_id"]  # idempotent repair
    assert len(K.log_of(S.read_intent(env.plane, src["id"]))) == 1
    assert call(env, "aaron", "GET", f"/api/intents/{tid}/chain").status_code == 404  # a draft: only its creator


def test_prefill_table_per_type(env):
    bra = {"id": "b", "type": "brainstorm", "title": "Ideas", "areas": ["Ops"], "outcome": {"chosen": {"idea": "Idea A"}}}
    prb = {"id": "p", "type": "problem", "areas": ["Ops"], "outcome": {"what": "File late"}}
    dec = {"id": "d", "type": "decision", "areas": ["Ops"], "outcome": {"chosen": "Option B"}}
    pul = {"id": "w", "type": "pulse", "areas": ["Ops"], "outcome": {}}
    ini = K.prefill(bra, "initiative", None, None, {"ops": "operations"})  # file 22 keys and cells; area names become the picker's ids
    assert ini["goal"]["value"]["line"] == "Idea A" and ini["areas"]["value"] == ["operations"] and ini["prefilled"]["goal"]["intent_id"] == "b"
    cases = [(bra, "decision", None, "question", "Idea A"), (prb, "problem", None, "what", "File late"), (dec, "brainstorm", None, "statement", "Option B"),
             (pul, "problem", "Statement file late again", "what", "Statement file late again")]
    for src, kind, item, first, want in cases:
        out = K.prefill(src, kind, item)
        assert out[first] == want and out["areas"] == ["Ops"] and out["prefilled"][first]["intent_id"] == src["id"], (src["type"], kind)
    assert "what" not in K.prefill(pul, "problem", None)  # nothing to fill the first question from
    assert set(K.allowed("pulse")) == {"problem", "backlog"} and "build" in K.allowed("initiative")


def test_cancel_writes_on_the_other_record(env):
    from sh_platform.intents import events as EV
    a = make(env, title="Brainstorm A")
    b = make(env, type_="initiative", state="open", title="Initiative B")
    lid = K.link_intents(env.plane, a["id"], b["id"], "initiative", by=V("janet"))
    assert [e["kind"] for e in EV.read_events(env.plane, a["id"])] == ["link_created"]  # accepted after close
    rec = S.read_intent(env.plane, b["id"])
    L.cancel(rec, "janet", "Overtaken by the audit.", S.now_iso())
    S.write_intent(env.plane, rec)
    K.chain(env.plane, V("janet"), a["id"])
    K.chain(env.plane, V("janet"), b["id"])  # read twice: written once
    got = [e for e in EV.read_events(env.plane, a["id"]) if e["kind"] == "target_cancelled"]
    assert len(got) == 1 and got[0]["detail"]["link_id"] == lid and got[0]["by"]["name"] == "Janet Shaw"


def test_chain_walk_capped(env):
    ids = [make(env, type_="decision", title=f"Step {n}")["id"] for n in range(K.MAX_STEPS + 10)]
    for a, b in zip(ids, ids[1:]):
        K.link_intents(env.plane, a, b, "decision", by=V("janet"))
    out = K.chain(env.plane, V("janet"), ids[0])
    assert len(out["chain"]) <= K.MAX_STEPS and out["capped"]
    mid = K.chain(env.plane, V("janet"), ids[5])
    assert [s["dir"] for s in mid["chain"][:6]] == ["from"] * 5 + ["self"]


def test_intent_nodes_and_edges_on_graph(env):
    from sh_platform.graph.build import rebuild
    a = make(env, title="Brainstorm A")
    b = make(env, type_="initiative", state="cancelled", title="Initiative B")
    d = make(env, state="draft", title="Private draft")
    K.link_intents(env.plane, a["id"], b["id"], "initiative", by=V("janet"))
    g = rebuild(env.plane)
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes[f"intent:{a['id']}"]["type"] == "Intent" and nodes[f"intent:{a['id']}"]["room"] == "intent"
    assert f"intent:{d['id']}" not in nodes
    assert nodes[f"intent:{b['id']}"]["cancel_reason"] == "Overtaken by the audit."
    assert "aaron lyle" in nodes[f"intent:{a['id']}"]["restricted_to"] and "zed lee" not in nodes[f"intent:{a['id']}"]["restricted_to"]
    edges = {(e["from"], e["to"], e["type"]): e for e in g["edges"]}
    led = edges[(f"intent:{a['id']}", f"intent:{b['id']}", "led_to")]
    assert led["status"] == "target_cancelled" and (f"intent:{b['id']}", f"intent:{a['id']}", "came_from") in edges
    assert any(t == "owned_by" and f == f"intent:{a['id']}" for f, _, t in edges)


# ---- 21: backlog -------------------------------------------------------------------------------------------------------------

def _item(env, src, title="One custody checklist", area="Treasury", raised="harvey"):
    return B.create_item(env.plane, title=title, kind="idea", area=area, source={"intent_id": src["id"], "type": "brainstorm"},
                         raised_by=raised, why="Custody list re-keyed four times a month")


def test_backlog_open_merge_park_drop_nothing_deleted(env):
    src = make(env)
    a, b, c = _item(env, src), _item(env, src, title="Custody list checklist rekeyed"), _item(env, src, title="Fee report")
    assert B.similar(B.read_items(env.plane), B.read_items(env.plane)[1])["id"] == a["id"]
    with pytest.raises(B.Refused):
        B.act(env.plane, V("aaron"), a["id"], "park", {"reason": "later"})  # not an actor
    with pytest.raises(B.Refused):
        B.act(env.plane, V("janet"), a["id"], "drop", {"reason": " "})  # a reason is required
    parked = B.act(env.plane, V("janet"), a["id"], "park", {"reason": "After the audit", "review_date": "2027-03-01"})
    assert parked["status"] == "parked" and parked["parked"]["review_date"] == "2027-03-01" == parked["review_date"]
    B.act(env.plane, V("janet"), a["id"], "bring-back", {})
    kept = B.act(env.plane, V("janet"), a["id"], "merge", {"other": b["id"], "keep": "this", "why": "Same list, two names"})
    assert kept["merged_from"] == [b["id"]] and kept["why_it_matters"]["text"] == "Same list, two names"
    dropped = B.act(env.plane, V("janet"), c["id"], "drop", {"reason": "Covered by finance"})
    assert dropped["dropped"]["reason"] == "Covered by finance"
    opened = B.act(env.plane, V("janet"), a["id"], "open", {"type": "initiative"})
    rec = S.read_intent(env.plane, opened["intent_id"])
    assert rec["backlog_ref"] == a["id"] and rec["links"]["from"] == src["id"] and rec["state"] == "draft"
    assert opened["intent_id"] in S.read_intent(env.plane, src["id"])["links"]["to"]
    items = {i["id"]: i for i in B.read_items(env.plane)}
    assert len(items) == 3 and items[b["id"]]["status"] == "merged" and items[a["id"]]["status"] == "became_intent"
    assert [h["action"] for h in items[a["id"]]["history"]] == ["created", "parked", "brought_back", "merged_in", "opened"]
    assert call(env, "janet", "DELETE", f"/api/intents/backlog/{a['id']}").status_code == 405  # no delete route exists


def test_i_feel_this_counts(env):
    src = make(env)
    it = _item(env, src, raised="harvey")
    assert B.act(env.plane, V("aaron"), it["id"], "tap", {})["taps"][-1]["by"] == "aaron"
    assert len(B.read_items(env.plane)[0]["taps"]) == 2  # the raiser counts first
    B.act(env.plane, V("aaron"), it["id"], "tap", {})  # a second press takes it back
    assert len(B.read_items(env.plane)[0]["taps"]) == 1
    with pytest.raises(B.Refused):
        B.act(env.plane, V("zed"), it["id"], "tap", {})  # outside the area: not even seen
    r = call(env, "aaron", "GET", "/api/intents/backlog?area=Treasury")
    assert r.status_code == 200 and r.json()["items"][0]["taps"] == 1 and r.json()["items"][0]["can_tap"]
    assert call(env, "zed", "GET", "/api/intents/backlog").json()["items"] == []
    assert not r.json()["opportunities"]  # a participant is never sent to the opportunities route it would be refused
    assert call(env, "janet", "GET", "/api/intents/backlog").json()["opportunities"]


def test_review_reminder_line(env):
    src = make(env)
    it = _item(env, src)
    B.act(env.plane, V("aaron"), it["id"], "tap", {})
    B.act(env.plane, V("janet"), it["id"], "edit", {"review_date": "2026-10-01"})
    lines = B.remind_due(env.plane, date(2026, 10, 7))
    assert lines == [{"to": "company_admin", "text": "Review: One custody checklist. 2 people feel this. Open an intent, park it again, or drop it.",
                      "note": "No lead named for Treasury.", "href": f"/centre/intent/backlog?item={it['id']}", "due": "2026-10-01", "raiser": "harvey"}]
    assert B.remind_due(env.plane, date(2026, 10, 8)) == []  # weekly, not daily
    assert len(B.remind_due(env.plane, date(2026, 10, 15))) == 1


# ---- F18: link lines at cancel time, and the chain sentence as branches ------------------------------------------------------

def _cancel_events(env, via):
    from sh_platform.intents import events as EV
    a = make(env, title="Brainstorm A")
    b = make(env, type_="initiative", state="open", title="Initiative B")
    lid = K.link_intents(env.plane, a["id"], b["id"], "initiative", by=V("janet"))
    rec = S.read_intent(env.plane, b["id"])
    via(rec, b["id"])
    kinds = [e["kind"] for e in EV.read_events(env.plane, a["id"])]  # no chain read in between
    return lid, kinds, [e for e in EV.read_events(env.plane, a["id"]) if e["kind"] == "target_cancelled"]


def test_cancel_route_writes_the_link_line_at_once(env):
    from sh_platform.intents import records as R
    app = FastAPI()
    app.state.settings = env.c.app.state.settings
    app.state.account_store = Accounts()
    app.include_router(R.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        request.state.account_id, request.state.company_id, request.state.roles = "janet", CO, ["company_admin"]
        return await call_next(request)
    api = TestClient(app)
    lid, kinds, got = _cancel_events(env, lambda rec, iid: api.post(
        f"/api/intents/{iid}/cancel", json={"version": rec["version"], "cancel_reason": "Overtaken by the audit."}))
    assert len(got) == 1 and got[0]["detail"]["link_id"] == lid and got[0]["by"]["name"] == "Janet Shaw"


def test_admin_cancel_writes_the_link_line_at_once(env):
    from sh_platform.intents import admin as AD
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(account_store=Accounts())), state=SimpleNamespace(account_id="janet", company_id=CO, roles=["company_admin"]))
    lid, _, got = _cancel_events(env, lambda rec, iid: AD.admin_cancel(req, env.plane, iid, "Stuck for a month."))
    assert len(got) == 1 and got[0]["detail"]["link_id"] == lid


def test_chain_sentence_lists_sibling_branches(env):
    a = make(env, title="Custody ideas")
    b = make(env, type_="initiative", state="open", title="Fix the feed")
    c = make(env, type_="problem", state="open", title="Late statements")
    K.link_intents(env.plane, a["id"], b["id"], "initiative", by=V("janet"))
    K.link_intents(env.plane, a["id"], c["id"], "problem", by=V("janet"))
    s = K.chain(env.plane, V("janet"), a["id"])["sentence"]
    assert "led to the initiative 'Fix the feed'" in s and " and, separately, the problem 'Late statements'" in s and ", then" not in s
    one = K.chain(env.plane, V("janet"), b["id"])["sentence"]
    assert one.startswith("This began as the brainstorm 'Custody ideas'") and ", then the initiative 'Fix the feed'" in one


def test_reminder_is_stamped_only_for_lines_shown(env):  # F35
    src = make(env)
    it = _item(env, src)
    B.act(env.plane, V("janet"), it["id"], "edit", {"review_date": "2026-10-01"})
    today = date(2026, 10, 7)
    assert len(B.remind_due(env.plane, today, peek=True)) == 1 and len(B.remind_due(env.plane, today, peek=True)) == 1  # a peek writes nothing
    assert B.remind_due(env.plane, today, only={"other"}) == []  # shown elsewhere: not this item
    assert len(B.remind_due(env.plane, today, only={it["id"]})) == 1
    assert B.remind_due(env.plane, today, peek=True) == []  # now stamped for a week
