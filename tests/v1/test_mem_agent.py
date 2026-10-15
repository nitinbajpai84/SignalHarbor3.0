"""Agent memory: Lumen follow-ups edit the focus tile, preferences persist across sessions, people and companies never see each other's memory,
forgetting removes an item from recall, and the model sees memory only through the egress path (a stub model behind run_agent)."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.rows import json_findings
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import mem_agent as M
from sh_platform.v1 import p1_project, wh
from sh_platform.v1.p1_project import Refused

ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
ANA = Viewer(name="Ana", roles=frozenset({"analyst"}), account_id="acc-ana")
BOB = Viewer(name="Bob", roles=frozenset({"participant"}), account_id="acc-bob")
GOLD = "gold_monthly_report_holdings"


def seed(plane, name="Monthly report"):
    pid = p1_project.create_project(plane, "int-1", name, "Nitin")["id"]
    with wh.connect(plane) as con:
        con.execute(f"create table {GOLD} (day date, entity varchar, net_worth decimal(18,2), net_worth_sgd decimal(18,2))")
        con.execute(f"insert into {GOLD} values ('2026-07-15','Fund A',90,120),('2026-08-10','Fund A',100,133),('2026-08-20','Fund B',50,66),"
                    "('2026-09-05','Fund A',130,173),('2026-09-25','Fund B',45,60)")
    cat.register_gold(plane, pid, "monthly_report", "holdings", [{"name": "day", "type": "date"}])
    return pid


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    return plane, seed(plane)


def tiles(plane, pid, did):
    return D.get(plane, ADMIN, pid, did)["tiles"]


def test_dots_then_blue_then_monthly_edit_the_last_tile(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    first = L.ask(plane, ADMIN, pid, d["id"], "show net worth per day")["proposals"][0]
    assert first["spec"]["mark"]["type"] == "line" and "date_trunc('month'" not in first["sql"]
    out = L.ask(plane, ADMIN, pid, d["id"], "can you change the able chart as dots")
    t = out["proposals"][0]
    assert out["edited"] and t["spec"]["mark"]["type"] == "point" and "could not match" not in out["reply"]
    assert [x["id"] for x in tiles(plane, pid, d["id"])] == [t["id"]]  # the proposed old version was replaced, not left beside it
    out = L.ask(plane, ADMIN, pid, d["id"], "can you show monthly rather than daily and line graph in blue")
    t = out["proposals"][0]
    assert t["spec"]["mark"]["type"] == "line" and t["spec"]["mark"]["color"] == M.COLORS["blue"]
    assert "date_trunc('month'" in t["sql"] and t["title"].endswith("per month")
    rows = D.tile_data(plane, ADMIN, pid, d["id"], t["id"])["rows"]
    assert len(rows) == 3  # Jul, Aug, Sep, summed by the program
    assert "I will remember" in out["reply"]


def test_accepting_a_new_version_replaces_the_accepted_old_one(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    a = L.ask(plane, ADMIN, pid, d["id"], "net worth per month")["proposals"][0]
    D.decide(plane, ADMIN, pid, d["id"], a["id"], True)
    b = L.ask(plane, ADMIN, pid, d["id"], "make it bars")["proposals"][0]
    assert b["replaces"] == a["id"] and len(tiles(plane, pid, d["id"])) == 2  # the accepted one stays until the new version is accepted
    D.decide(plane, ADMIN, pid, d["id"], b["id"], True)
    got = tiles(plane, pid, d["id"])
    assert [x["id"] for x in got] == [b["id"]] and got[0]["spec"]["mark"]["type"] == "bar"


def test_by_entity_range_and_currency_follow_ups(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month")
    t = L.ask(plane, ADMIN, pid, d["id"], "now by entity")["proposals"][0]
    assert t["spec"]["encoding"]["color"]["field"] == "entity"
    t = L.ask(plane, ADMIN, pid, d["id"], "last 2 months")["proposals"][0]
    assert "interval 2 month" in t["sql"] and len(D.tile_data(plane, ADMIN, pid, d["id"], t["id"])["rows"]) > 0
    out = L.ask(plane, ADMIN, pid, d["id"], "in SGD")
    t = out["proposals"][0]
    assert out["edited"] and t["spec"]["encoding"]["y"]["field"] == "net_worth_sgd" and "net_worth_sgd" in t["sql"]


def test_a_question_is_still_answered_in_words(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month")
    out = L.ask(plane, ADMIN, pid, d["id"], "what figures do you have?")
    assert out["proposals"] == [] and "net worth" in out["reply"].lower() and "net_worth" not in out["reply"]  # EVT-12: plain words


def test_a_preference_persists_across_sessions_and_new_tiles_use_it(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month")
    L.ask(plane, ADMIN, pid, d["id"], "line in blue")
    L.ask(plane, ADMIN, pid, d["id"], "in SGD")
    again = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")  # signed out and back in
    assert M.preferences(plane, again) == {"lumen.color": "blue", "lumen.currency": "SGD"}
    out = L.ask(plane, again, pid, None, "net worth per month")
    t = out["proposals"][0]
    assert t["spec"]["mark"]["color"] == M.COLORS["blue"] and t["kpi"] == "net_worth_sgd"
    assert "blue" in out["reply"] and "SGD" in out["reply"]


def test_a_mark_is_kept_only_when_said_to_be_lasting(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month")
    L.ask(plane, ADMIN, pid, d["id"], "as dots")
    assert "lumen.mark" not in M.preferences(plane, ADMIN)
    out = L.ask(plane, ADMIN, pid, d["id"], "from now on use bars for charts")
    assert M.preferences(plane, ADMIN)["lumen.mark"] == "bar" and "I will remember" in out["reply"]


def test_person_a_never_sees_person_b(env):
    plane, pid = env
    M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue", "lumen.color", "blue")
    M.remember(plane, ADMIN, "north", "fact", "Works on the monthly board pack")
    assert M.mine(plane, BOB) == [] and M.preferences(plane, BOB) == {}
    r = M.recall(plane, "lumen", BOB, {"text": "board pack blue"})
    assert r["items"] == [] and r["preferences"] == {} and M.lines(plane, "lumen", BOB, {"text": "board pack"}) == []
    mine = M.recall(plane, "lumen", ADMIN, {"text": "board pack"})
    assert any(i["text"].startswith("Works on") for i in mine["items"])  # one memory: Lumen sees what North was told


def test_another_company_never_sees_it(env, tmp_path):
    plane, _ = env
    other = PlaneStore(tmp_path / "data").create("globex")
    M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue", "lumen.color", "blue")
    M.remember_company(plane, ADMIN, "Our fiscal year ends in March")
    assert M.mine(other, ADMIN) == [] and M.company_items(other) == [] and M.preferences(other, ADMIN) == {}
    assert M.recall(other, "lumen", ADMIN, {})["company"] == []


def test_forget_removes_it_from_recall_and_blanks_the_words(env):
    plane, _ = env
    item, _new = M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue for chart lines", "lumen.color", "blue")
    assert M.preferences(plane, ADMIN) == {"lumen.color": "blue"}
    M.forget(plane, ADMIN, item["id"])
    assert M.preferences(plane, ADMIN) == {} and M.mine(plane, ADMIN) == [] and M.recall(plane, "lumen", ADMIN, {"text": "blue"})["items"] == []
    folder = plane.path("memory", "v1", "people")
    raw = "".join(p.read_text(encoding="utf-8") for p in folder.iterdir())
    assert "blue" not in raw  # the words are gone from the file, not just hidden
    with pytest.raises(Refused):
        M.forget(plane, ADMIN, item["id"])


def test_a_change_supersedes_and_keeps_the_history(env):
    plane, _ = env
    a, _n = M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue", "lumen.color", "blue")
    b, new = M.remember(plane, ADMIN, "lumen", "preference", "Prefers: red", "lumen.color", "red")
    assert new and b["supersedes"] == a["id"] and M.preferences(plane, ADMIN) == {"lumen.color": "red"}
    again, new = M.remember(plane, ADMIN, "lumen", "preference", "Prefers: red", "lumen.color", "red")
    assert not new and again["id"] == b["id"]
    fixed = M.correct(plane, ADMIN, b["id"], "I like green")
    assert fixed["supersedes"] == b["id"] and M.preferences(plane, ADMIN) == {"lumen.color": "green"}
    assert fixed["source"]["corrected_by"] == "acc-admin" and fixed["sure"] == "said"


def test_corrections_and_lasting_words_are_learned_by_rules_but_figures_are_not(env):
    plane, _ = env
    assert M.learn(plane, ADMIN, "north", "No, I meant the committee, not the board", "int-1")
    assert M.learn(plane, ADMIN, "span", "Always show the fund name in full", "int-1")
    assert M.learn(plane, ADMIN, "span", "Remember that our hurdle is 8%", "int-1") == []
    assert M.learn(plane, ADMIN, "span", "always write to me at a@b.com", "int-1") == []
    assert sorted(i["kind"] for i in M.mine(plane, ADMIN)) == ["correction", "preference"]  # AQ1 NM-4: a lasting instruction is a preference
    for i in M.mine(plane, ADMIN):
        assert i["source"]["said"] and i["agent"] in M.AGENTS and i["at"] and i["sure"] == "said"


def test_short_term_keeps_the_last_turns_and_the_focus(env):
    plane, _ = env
    for n in range(M.TURNS + 5):
        M.note(plane, ADMIN, "tally", "case-1", "person", f"turn {n}", {"case": "case-1"} if n == 3 else None)
    c = M.convo(plane, ADMIN, "tally", "case-1")
    assert len(c["turns"]) == M.TURNS and c["turns"][-1]["text"] == f"turn {M.TURNS + 4}" and c["focus"] == {"case": "case-1"}
    assert M.convo(plane, BOB, "tally", "case-1")["turns"] == [] and M.convo(plane, ADMIN, "lumen", "case-1")["turns"] == []


def test_company_memory_rights_and_k2_links(env):
    plane, _ = env
    item = M.remember_company(plane, ANA, "Report in USD unless asked")
    with pytest.raises(Refused) as e:
        M.remember_company(plane, BOB, "I should not write this")
    assert e.value.status == 403
    t = M.remember_company(plane, ADMIN, term="AUM", concept_id="concept:aum")
    assert t["value"] == "concept:aum" and t["key"] == "term:aum"  # a link to the K2 concept, not a copy of its definition
    assert {i["id"] for i in M.company_items(plane)} == {item["id"], t["id"]}  # everyone in the company reads them
    assert M.recall(plane, "north", BOB, {"text": "usd"})["company"][0]["text"].startswith("Report in USD")
    with pytest.raises(Refused):
        M.forget(plane, BOB, item["id"], company=True)


class Stub:
    def __init__(self):
        self.seen = []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text="no json here")


def user_body(messages) -> str:
    return next(m for m in messages if m["role"] == "user")["content"]


def test_the_model_sees_memory_only_through_run_agent_and_in_a_shape_egress_allows(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue for chart lines", "lumen.color", "blue")
    M.remember(plane, ADMIN, "north", "fact", "Reports to the family council")
    stub = Stub()
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month", model=stub)
    assert stub.seen, "the model call goes through run_agent and so through the egress client"
    body = user_body(stub.seen[0])
    assert "Prefers: blue" in body and "Reports to the family council" in body
    assert json_findings(body) == (None, [])  # no list of records, no figure: the gateway's own row guard passes it
    other = Stub()
    L.ask(plane, BOB, pid, None, "net worth per month", model=other)
    assert "blue" not in user_body(other.seen[0])  # Bob's call carries none of Admin's memory


def test_a_model_proposed_item_goes_through_the_gateway_and_is_shown(env, monkeypatch):
    plane, _ = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")

    class Proposer(Stub):
        def complete(self, module_id, messages, tools=None):
            self.seen.append(messages)
            return ModelReply(text=json.dumps({"items": [{"kind": "preference", "text": "Likes the committee summary first"}]}))
    p = Proposer()
    shown = M.learn(plane, ADMIN, "north", "I usually want the committee summary first", "int-1", model=p)
    assert shown == ["Likes the committee summary first"]  
    assert p.seen and json_findings(user_body(p.seen[0])) == (None, [])
    assert M.mine(plane, ADMIN)[0]["sure"] == "model"
    assert "I will remember: Likes the committee" in M.remember_line(shown)
    p.seen.clear()
    p.complete = lambda module_id, messages, tools=None: ModelReply(text=json.dumps({"items": [{"kind": "fact", "text": "Fund holds 12 positions"}]}))
    assert M.learn(plane, ADMIN, "north", "We usually review the fund every week", "int-1", model=p) == []  # a figure in the reply: nothing is kept


from tests.v1.test_b6 import ENG, world  # noqa: E402,F401 - Span's build plan, for the Span hook below
from sh_platform.v1 import b6_span as S  # noqa: E402


def test_span_in_build_writes_and_reads_the_shared_memory(world):
    plane, pid = world
    S.propose_plan(plane, ENG, pid)
    got = S.chat(plane, ENG, pid, "Always keep answers short. Add a weekly gold table by currency")
    assert "I will remember: you like short answers" in got["turns"][-1]["text"]
    assert any("short answers" in x for x in M.lines(plane, "lumen", ENG, {"convo": pid}))  # Lumen reads what Span was told
    assert M.focus(plane, ENG, "span", pid)["project"] == pid


# ---- security review (adversarial) ----------------------------------------------------------------------------------------------------

def test_review_forget_blanks_every_earlier_version_and_leaves_the_prompt(env):
    plane, _ = env
    a, _n = M.remember(plane, ADMIN, "north", "fact", "Works on the quarterly committee pack")
    b = M.correct(plane, ADMIN, a["id"], "Works on the monthly committee pack")
    assert any("committee" in s for s in M.lines(plane, "lumen", ADMIN, {"text": "committee"}))
    M.forget(plane, ADMIN, b["id"])
    assert M.lines(plane, "lumen", ADMIN, {"text": "committee"}) == []
    raw = "".join(p.read_text(encoding="utf-8") for p in plane.path("memory", "v1", "people").iterdir())
    assert "committee" not in raw  # the corrected-away version is blanked too, not only the live one


def test_review_twin_names_without_an_account_never_share_a_memory(env):
    plane, _ = env
    twin = Viewer(name="Nitin", roles=frozenset({"participant"}), shared_name=True)
    M.remember(plane, Viewer(name="Nitin", roles=frozenset({"participant"})), "north", "fact", "Works late")
    with pytest.raises(Refused):
        M.mine(plane, twin)
    assert M.preferences(plane, twin) == {} and M.learn(plane, twin, "north", "Always keep it short") == []


def test_review_another_person_cannot_correct_or_forget_my_item_and_others_cannot_write_company(env):
    plane, _ = env
    item, _n = M.remember(plane, ADMIN, "north", "fact", "Reads on a tablet")
    for fn in (lambda: M.correct(plane, BOB, item["id"], "Reads on paper"), lambda: M.forget(plane, BOB, item["id"]),
               lambda: M.correct(plane, ANA, item["id"], "Reads on paper")):
        with pytest.raises(Refused) as e:
            fn()
        assert e.value.status == 404
    co = M.remember_company(plane, ANA, "Our year ends in March")
    for fn in (lambda: M.remember_company(plane, BOB, "Our year ends in June"), lambda: M.forget(plane, BOB, co["id"], company=True),
               lambda: M.correct(plane, BOB, co["id"], "Our year ends in June", company=True)):
        with pytest.raises(Refused) as e:
            fn()
        assert e.value.status == 403
    assert M.mine(plane, ADMIN)[0]["text"] == "Reads on a tablet" and M.company_items(plane)[0]["text"] == "Our year ends in March"


def test_review_a_figure_in_the_message_is_not_kept_as_the_source_of_a_preference(env):
    plane, _ = env
    assert M.learn(plane, ADMIN, "lumen", "From now on in blue please, net worth was 4.2m last month", "p1")
    raw = "".join(p.read_text(encoding="utf-8") for p in plane.path("memory", "v1", "people").iterdir())
    assert "4.2" not in raw and M.preferences(plane, ADMIN)["lumen.color"] == "blue"


def test_review_nothing_free_is_kept_when_restricted_names_cannot_be_read(env, monkeypatch):
    plane, _ = env
    from sh_platform.memory import filters
    monkeypatch.setattr(filters, "restricted_terms", lambda p: (_ for _ in ()).throw(ValueError("broken profile")))
    assert M.learn(plane, ADMIN, "north", "Always copy the family council on the pack") == []
    with pytest.raises(Refused):
        M.remember_company(plane, ADMIN, "The council reads it")
