"""MEM2a: conversation summaries, the context map, memory vectors and context_for. Summaries by rules and (stub) model through the egress path, graph
edges, recall by meaning (a stub embedder), access across people and projects, the forget cascade, no figures anywhere, the Map route."""
import json
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.rows import json_findings
from sh_platform.graph import models
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import doc_embed, doc_index, g1_access, p1_project
from sh_platform.v1 import mem_agent as MEM
from sh_platform.v1 import mem_context as C
from sh_platform.v1 import mem_graph as G
from sh_platform.v1 import mem_graph_routes as R
from sh_platform.v1 import mem_summary as S
from sh_platform.v1.p1_project import Refused

ANA = Viewer(name="Ana", roles=frozenset({"analyst"}), account_id="acc-ana")
BOB = Viewer(name="Bob", roles=frozenset({"participant"}), account_id="acc-bob")
CAROL = Viewer(name="Carol", roles=frozenset({"participant"}), account_id="acc-carol")
TABLE = "gold_monthly_report_holdings"
GROUPS = [{"holdings", "positions", "portfolio"}, {"dinner", "restaurant", "booking"}, {"board", "committee"}, {"fees", "charges"}]


def stub_embed(texts, query=False):
    """Words of one meaning share a dimension, so 'positions' finds 'holdings' without sharing a word."""
    rows = []
    for t in texts:
        w = set(re.findall(r"[a-z]+", t.lower()))
        rows.append([float(len(w & g)) for g in GROUPS] + [0.05])
    v = np.array(rows, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setattr(doc_embed, "embed", stub_embed)
    monkeypatch.setattr(doc_index, "_submit", lambda fn, *a: None)  # no background embedding in tests
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Board pack", "Ana", "acc-ana")["id"]  # Internal by default: Ana (raiser) full, others preview
    monkeypatch.setattr(G, "known_tables", lambda plane: {TABLE})  # SS-2: only the company's own tables become nodes; this one is in its model
    return plane, pid


def talk(plane, viewer, convo, lines, agent="north", focus=None, model=None):
    for text, reply in lines:
        C.after_turn(plane, agent, viewer, convo, text, reply, focus, model=model)


BOARD = [("Let's go with " + TABLE + " for the board pack.", "Good, I will use it."),
         ("We agreed to send it on Friday.", "Noted."),
         ("Always keep answers short.", "Understood."),
         ("Which entity comes first?", "Do you want it by entity?")]


def summaries(plane, viewer):
    return S.visible_items(plane, viewer)


def test_a_long_talk_is_summarised_by_rules_with_edges_and_no_model(env):
    plane, pid = env
    talk(plane, ANA, "c1", BOARD, focus={"project": pid})
    got = summaries(plane, ANA)
    assert len(got) == 1
    s = got[0]
    assert s["agent_name"] == "North" and s["who"] == "Ana" and "Monthly report holdings" in s["about"] and s["topics"] == []  # topics are the model's, none with it off
    assert any("agreed to send it on Friday" in d for d in s["decisions"]) and any("by entity" in q for q in s["open"])
    assert any("short answers" in p or "short" in p for p in s["prefs"])
    assert s["source"]["turns"] == 8 and s["source"]["agent"] == "north" and s["source"]["talk"]
    v = G.view(plane, ANA)
    by = {n["id"]: n for n in v["nodes"]}
    kinds = {(by[e["from"]]["type"], e["type"], by[e["to"]]["type"]) for e in v["edges"]}
    for edge in [("person", "talked_with", "agent"), ("summary", "about", "project"), ("summary", "mentions", "table"), ("summary", "decided", "decision"),
                 ("summary", "asked", "question"), ("summary", "refers_to", "conversation"), ("conversation", "mentions", "table")]:
        assert edge in kinds, edge
    assert G.table_id(TABLE) in by  # the company map's own table id
    S.maybe(plane, ANA, "north", "c1")
    assert len(summaries(plane, ANA)) == 1  # no new turns: no second summary


def test_a_quiet_talk_is_summarised_and_a_later_one_supersedes(env):
    plane, pid = env
    talk(plane, ANA, "c2", [("Which gold tables exist for " + TABLE + "?", "Only one.")], focus={"project": pid})
    t0 = datetime.now(timezone.utc)
    assert S.sweep(plane, now=t0 + timedelta(minutes=29)) == []
    first = S.sweep(plane, now=t0 + timedelta(minutes=31))
    assert len(first) == 1
    talk(plane, ANA, "c2", [("We decided to keep it monthly.", "Ok.")], focus={"project": pid})
    second = S.sweep(plane, now=t0 + timedelta(minutes=70))
    # AQ1 lumen-memory-04: the decision turn was summarised at once (it replaced the first); the quiet sweep then replaces that one
    chain = {i["id"]: i for i in S.visible_items(plane, ANA, latest_only=False)}
    assert len(second) == 1 and chain[second[0]["replaces"]]["superseded"] and first[0]["id"] in chain
    assert any("keep it monthly" in d for d in chain[second[0]["replaces"]]["decisions"])
    assert [x["id"] for x in summaries(plane, ANA)] == [second[0]["id"]]  # recall sees the latest
    v = G.view(plane, ANA)  # AQF10-07: the map draws the latest summary of the talk only; the file keeps the supersedes chain for history
    assert [n["id"] for n in v["nodes"] if n["type"] == "summary"] == ["summary:" + second[0]["id"]]
    assert any(e["type"] == "supersedes" for e in G._load(plane)["edges"])


def test_no_figures_reach_a_summary_the_graph_or_the_vectors(env):
    plane, pid = env
    talk(plane, ANA, "c3", [("Net worth was 4.2m in July and we agreed to report 4.2m.", "Ok."),
                            ("Mail me at ana@example.test, we decided to use " + TABLE + ".", "Ok."),
                            ("Which fee was 1.9 percent?", "Not sure."), ("Fine.", "Ok.")], focus={"project": pid})
    s = summaries(plane, ANA)[0]
    blob = json.dumps(s)
    assert not re.search(r"4\.2|1\.9|@", blob)
    for f in ("graph.json", "summaries.json"):
        raw = (plane.path("memory", "v1", "ctx", f)).read_text(encoding="utf-8")
        assert not re.search(r"4\.2|1\.9|ana@", raw), f
    assert not re.search(r"4\.2|1\.9", C.context_for(plane, "north", ANA, "net worth", focus={"project": pid}, convo="c3")["recall"].__str__())


class Stub:
    def __init__(self, reply):
        self.seen, self.reply = [], reply

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text=json.dumps(self.reply))


def body(messages):
    return next(m for m in messages if m["role"] == "user")["content"]


def test_the_model_summarises_and_proposes_topics_only_through_egress(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    stub = Stub({"about": "the board pack", "decisions": ["Send monthly"], "open": ["Who signs?"], "preferences": ["Likes it short"], "topics": ["Board reporting", "Fees"]})
    lines = [("Net worth was 4.2m last month, " + TABLE + " is the source.", "Ok."), ("We agreed to send it monthly.", "Noted."), ("Who signs?", "Not decided."),
             ("Keep it short.", "Ok.")]
    talk(plane, ANA, "c4", lines, focus={"project": pid}, model=stub)
    assert stub.seen, "the summary call goes through run_agent and so through the egress client"
    sent = [body(m) for m in stub.seen]
    assert all(json_findings(b) == (None, []) for b in sent)
    assert not any("4.2m" in b for b in sent), "a turn that states a figure is not sent"
    s = summaries(plane, ANA)[0]
    assert s["about"] == "the board pack" and s["topics"] == ["Board reporting", "Fees"] and s["decisions"] == ["Send monthly"]
    v = G.view(plane, ANA)
    assert {"topic:board-reporting", "topic:fees"} <= {n["id"] for n in v["nodes"]}


def test_a_model_reply_with_a_figure_falls_back_to_rules(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    stub = Stub({"about": "a 4.2m review", "decisions": ["Send 4.2m"], "open": [], "preferences": [], "topics": ["Fees"]})
    talk(plane, ANA, "c5", [("We agreed to send it on Friday.", "Ok.")] * 4, focus={"project": pid}, model=stub)
    s = summaries(plane, ANA)[0]
    assert stub.seen and s["topics"] == [] and not re.search(r"4\.2", json.dumps(s))


def test_recall_by_meaning_finds_a_summary_with_no_shared_word(env):
    plane, pid = env
    talk(plane, ANA, "c6", [("Review the fund positions each week.", "Ok."), ("Also the dinner booking.", "Ok.")] * 2)
    s = summaries(plane, ANA)[0]
    ok = lambda o, p, k: True  # noqa: E731
    hit = G.search(plane, "holdings portfolio", ok)
    assert hit and hit[0]["id"] == s["id"] and hit[0]["how"] == "meaning"
    assert G.search(plane, "committee charges", ok) == []  # unrelated: below the meaning threshold
    got = C.context_for(plane, "lumen", ANA, "holdings portfolio?")
    assert any("positions" in x for x in got["recall"]) and got["trace"]["summaries"] == [s["id"]]


def test_memory_items_are_embedded_and_found_by_meaning(env):
    plane, _ = env
    MEM.remember(plane, ANA, "north", "fact", "The board wants the portfolio summary first")
    got = C.context_for(plane, "north", ANA, "the committee agenda")
    assert any("portfolio summary" in x for x in got["recall"])  # same board/committee group: by meaning, not words
    assert got["trace"]["memory"]


def test_access_across_people_and_projects(env):
    plane, pid = env
    talk(plane, ANA, "p1", BOARD, focus={"project": pid})                               # a talk in the project
    talk(plane, ANA, "private", [("My own holdings positions worry me.", "I see.")] * 4)  # a private talk, no project
    MEM.remember(plane, ANA, "north", "fact", "Ana likes portfolio views first")
    q = "holdings positions and the " + TABLE
    assert len(summaries(plane, ANA)) == 2
    for who in (BOB, CAROL):  # neither is on the project: Internal gives a preview, not the talk
        got = C.context_for(plane, "north", who, q, focus={"project": pid})
        assert not [x for x in got["recall"] + got["graph"] if "Ana" in x or "earlier talk" in x or "Monthly report" in x], who.name
        assert G.view(plane, who)["nodes"] == [] and S.visible_items(plane, who) == []
    g1_access.join(plane, pid, "Carol", "member", "acc-carol")
    got = C.context_for(plane, "north", CAROL, q, focus={"project": pid})
    texts = got["recall"]
    assert any("Ana's earlier talk with North" in x and "Monthly report holdings" in x for x in texts)  # the project talk, and whose (c1-03)
    assert not any("positions worry" in x or "worry" in x for x in texts)      # not the private one
    assert not any("Ana likes portfolio" in x for x in texts)                 # not Ana's private item
    assert any("Ana" in g for g in got["graph"])                                 # the project's graph is shared
    assert len(summaries(plane, CAROL)) == 1 and G.view(plane, CAROL)["nodes"]
    assert any(n["type"] == "summary" for n in G.view(plane, ANA)["nodes"])
    # a project id Carol cannot read is not even recognised as an entity in her words
    other = p1_project.create_project(plane, "int-2", "Secret pack", "Ana", "acc-ana")["id"]
    assert not any(e["type"] == "project" for e in G.entities(plane, other, CAROL))
    assert any(e["id"] == f"project:{other}" for e in G.entities(plane, other, ANA))


def test_documents_the_caller_allows_are_searched_and_the_short_term_turns_are_returned(env):
    plane, pid = env
    d = plane.path("docs")
    d.mkdir(parents=True, exist_ok=True)
    (d / "note.txt").write_text("The family committee reviews holdings and positions every quarter.\nPlans for the dinner are separate.", encoding="utf-8")
    talk(plane, ANA, "c7", [("What does the note say about the committee?", "It covers holdings."), ("Net worth was 4.2m", "Ok.")])
    got = C.context_for(plane, "north", ANA, "committee holdings", paths=["docs/note.txt"], convo="c7")
    assert any(x.startswith("note.txt, lines 1-") for x in got["passages"]) and got["documents"] == ["note.txt"]
    assert got["trace"]["passages"][0]["path"] == "docs/note.txt"
    assert any("said: What does the note say" in x for x in got["recall"])
    assert not any("4.2m" in x for x in got["recall"])  # a turn that states a figure is not returned
    assert all(isinstance(x, str) for k in ("recall", "graph", "passages", "documents") for x in got[k])
    none = C.context_for(plane, "north", ANA, "committee holdings", convo="c7")  # no paths given: no document is read
    assert none["passages"] == [] and none["documents"] == []


def test_the_result_is_size_capped_and_says_so(env):
    plane, pid = env
    for i in range(6):
        MEM.remember(plane, ANA, "north", "fact", f"The committee likes holdings view number {i} " + "x" * 200)
    got = C.context_for(plane, "north", ANA, "committee holdings", cap=300)
    assert sum(len(x) for k in ("recall", "graph", "passages", "documents") for x in got[k]) <= 300
    assert got["trace"]["capped"] is True


def test_forget_cascades_to_the_record_the_vectors_and_the_edges(env):
    plane, pid = env
    monkey_model = None
    talk(plane, ANA, "c8", BOARD, focus={"project": pid}, model=monkey_model)
    s = summaries(plane, ANA)[0]
    assert s["id"] in G.indexed(plane, "summary")  # AQ1: decision turns wrote earlier versions of the same talk's summary too
    with pytest.raises(Refused):
        S.forget(plane, BOB, s["id"])  # only the person who had the talk
    C.forget(plane, ANA, s["id"])
    assert summaries(plane, ANA) == [] and G.indexed(plane, "summary") == set()
    raw = json.loads(plane.path("memory", "v1", "ctx", "graph.json").read_text(encoding="utf-8"))
    assert not any(s["id"] in json.dumps(x) for x in (raw["edges"], list(raw["nodes"]), raw["scopes"]))
    assert not any(n["type"] in ("decision", "question") for n in raw["nodes"].values())
    assert not any(n["type"] == "summary" for n in raw["nodes"].values())
    got = C.context_for(plane, "north", ANA, "agreed Friday " + TABLE, focus={"project": pid})
    assert not any("earlier talk" in x for x in got["recall"]) and got["trace"]["summaries"] == []
    # an item forgotten here, or directly in mem_agent, is never returned
    a, _ = MEM.remember(plane, ANA, "north", "fact", "Committee wants the holdings view monthly")
    b, _ = MEM.remember(plane, ANA, "north", "fact", "Dinner booking is at the club")
    assert C.context_for(plane, "north", ANA, "committee holdings")["trace"]["memory"] == [a["id"]]
    C.forget(plane, ANA, a["id"])
    assert a["id"] not in G.indexed(plane, "item") and b["id"] in G.indexed(plane, "item")
    MEM.forget(plane, ANA, b["id"])  # the other route: the index still holds it, the live check does not return it
    got = C.context_for(plane, "north", ANA, "dinner restaurant booking")
    assert not any("Dinner booking" in x for x in got["recall"]) and b["id"] not in G.indexed(plane, "item")


def test_people_names_are_recognised_but_not_restricted_ones(env, monkeypatch):
    plane, _ = env
    from sh_platform.memory import filters
    monkeypatch.setattr(filters, "person_names", lambda p: {"Leela Raman", "Hidden Person"})
    monkeypatch.setattr(filters, "restricted_terms", lambda p: {"hidden person"})
    got = G.entities(plane, "Ask Leela Raman and Hidden Person about it", ANA)
    assert [e["id"] for e in got] == ["named:leela-raman"]


def test_the_company_maps_own_labels_are_recognised_and_a_restricted_one_is_not(env):
    plane, _ = env
    gdir = plane.path("graph")
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / "company.json").write_text(json.dumps({"nodes": [
        {"id": "measure:NW", "type": "Measure", "label": "Net worth", "restricted_to": None},
        {"id": "measure:SECRET", "type": "Measure", "label": "Secret margin", "restricted_to": ["Zed"]}], "edges": []}), encoding="utf-8")
    got = G.entities(plane, "Is net worth right? And the secret margin?", ANA)
    assert [(e["id"], e["type"]) for e in got] == [("measure:NW", "definition")]


def test_the_hook_for_the_company_graph_adds_only_agents_and_topics(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    talk(plane, ANA, "c9", [("We agreed to send it on Friday.", "Ok.")] * 4, focus={"project": pid},
         model=Stub({"about": "board", "decisions": [], "open": [], "preferences": [], "topics": ["Fees"]}))
    g = models.Graph()
    G.add_conversation_nodes(g, plane)
    assert {n["type"] for n in g.nodes.values()} == {"Agent", "Topic"}


def test_the_map_route_filters_per_viewer_and_a_person_forgets_a_summary(env, monkeypatch):
    plane, pid = env
    talk(plane, ANA, "c10", BOARD, focus={"project": pid})
    who = {"v": ANA}
    monkeypatch.setattr(R, "_plane", lambda req: plane)
    monkeypatch.setattr(R, "viewer_of", lambda req: who["v"])
    app = FastAPI()
    app.include_router(R.router)
    c = TestClient(app)
    doc = c.get("/api/v1/memory/graph").json()
    s = next(n for n in doc["nodes"] if n["type"] == "summary" and not n["summary"]["superseded"])  # AQ1: decision versions come first
    assert s["summary"]["agent_name"] == "North" and s["summary"]["decisions"] and s["summary"]["source"]["turns"] == 8
    who["v"] = BOB
    assert c.get("/api/v1/memory/graph").json()["nodes"] == []
    assert c.delete(f"/api/v1/memory/summaries/{s['summary']['id']}").status_code == 404
    who["v"] = ANA
    assert c.delete(f"/api/v1/memory/summaries/{s['summary']['id']}").json() == {"forgotten": s["summary"]["id"]}
    assert not [n for n in c.get("/api/v1/memory/graph").json()["nodes"] if n["type"] == "summary"]


# ---- MEM2a review: adversarial checks --------------------------------------------------------------------------------------------

def test_review_a_project_title_the_viewer_cannot_read_does_not_leak_through_a_shared_talk(env):
    plane, pid = env
    secret = p1_project.create_project(plane, "int-2", "Secret pack", "Ana", "acc-ana")["id"]
    talk(plane, ANA, "x1", [(f"Compare with {secret} and " + TABLE + ".", "Ok."), ("We agreed to keep both.", "Ok.")] * 2, focus={"project": pid})
    g1_access.join(plane, pid, "Carol", "member", "acc-carol")
    assert any("Secret pack" in json.dumps(n) for n in G.view(plane, ANA)["nodes"])  # Ana may read it
    v = G.view(plane, CAROL)
    assert v["nodes"] and not any(secret in json.dumps(x) or "Secret pack" in json.dumps(x) for x in v["nodes"] + v["edges"])
    assert not any("Secret pack" in json.dumps(s) for s in S.visible_items(plane, CAROL))
    got = C.context_for(plane, "north", CAROL, "the " + TABLE, focus={"project": pid})
    assert not any("Secret pack" in x or secret in x for k in ("recall", "graph") for x in got[k])


def test_review_a_persons_preferences_are_not_shown_to_the_rest_of_the_project(env):
    plane, pid = env
    talk(plane, ANA, "x2", BOARD, focus={"project": pid})
    g1_access.join(plane, pid, "Carol", "member", "acc-carol")
    assert S.visible_items(plane, ANA)[0]["prefs"]
    s = S.visible_items(plane, CAROL)[0]
    assert s["prefs"] == [] and "short" not in s["text"].lower()
    got = C.context_for(plane, "north", CAROL, "board pack " + TABLE, focus={"project": pid})
    assert not any("short" in x.lower() for x in got["recall"])


def test_review_forgetting_the_latest_summary_does_not_bring_back_the_one_it_replaced(env):
    plane, pid = env
    talk(plane, ANA, "x3", [("We decided to keep " + TABLE + " monthly.", "Ok.")])
    t0 = datetime.now(timezone.utc)
    first = S.sweep(plane, now=t0 + timedelta(minutes=31))[0]
    talk(plane, ANA, "x3", [("We decided to send it on Friday.", "Ok.")])
    second = S.sweep(plane, now=t0 + timedelta(minutes=70))[0]
    assert second["replaces"] and first["id"] in {i["id"] for i in S.visible_items(plane, ANA, latest_only=False)}  # AQ1: via the decision version
    C.forget(plane, ANA, second["id"])
    assert S.visible_items(plane, ANA, latest_only=False) == [] and G.indexed(plane, "summary") == set()
    assert not any(n["type"] == "summary" for n in G.view(plane, ANA)["nodes"])


def test_review_nothing_crosses_companies(env, tmp_path):
    plane, pid = env
    talk(plane, ANA, "x4", BOARD, focus={"project": pid})
    MEM.remember(plane, ANA, "north", "fact", "Ana likes portfolio views first")
    other = PlaneStore(tmp_path / "data").create("globex")
    assert G.view(other, ANA)["nodes"] == [] and S.visible_items(other, ANA) == []
    got = C.context_for(other, "north", ANA, "holdings portfolio " + TABLE, focus={"project": pid})
    assert not any("earlier talk" in x or "portfolio views" in x for x in got["recall"]) and got["graph"] == []


def test_review_a_viewer_with_no_key_of_their_own_writes_and_reads_nothing(env):
    plane, pid = env
    anon = Viewer(name="", roles=frozenset({"analyst"}), account_id=None)
    talk(plane, ANA, "x5", BOARD)  # Ana's private talk
    talk(plane, anon, "x5", BOARD)
    assert S.visible_items(plane, anon) == [] and G.view(plane, anon)["nodes"] == []
    assert len(S.visible_items(plane, ANA)) == 1


def test_review_the_routes_are_declared_for_the_six_roles_and_nothing_else():
    import yaml
    from pathlib import Path
    doc = yaml.safe_load((Path(G.__file__).parent / "mem_graph.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    six = {"company_admin", "sponsor", "analyst", "owner", "approver", "participant"}
    assert set(doc) == {"GET /api/v1/memory/graph", "DELETE /api/v1/memory/summaries/{sid}"}
    assert all(set(v["roles"]) == six for v in doc.values())
    assert {(m, r.path) for r in R.router.routes for m in r.methods} == {("GET", "/api/v1/memory/graph"), ("DELETE", "/api/v1/memory/summaries/{sid}")}


def test_review_the_new_modules_reach_a_model_only_through_the_egress_client():
    from pathlib import Path
    src = "".join((Path(G.__file__).parent / f).read_text(encoding="utf-8") for f in ("mem_graph.py", "mem_summary.py", "mem_context.py", "mem_graph_routes.py"))
    assert not re.search(r"\b(?:import|from)\s+(?:httpx|requests|urllib|anthropic|openai|socket)\b", src)
