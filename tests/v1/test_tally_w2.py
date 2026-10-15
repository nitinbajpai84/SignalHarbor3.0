"""Agent quality Wave 2, package T (offline): H1-09, DG-4, the ask_finance decision and the H1-03 owner seat. Seeded Evergreen warehouse
(synthetic), model off or a stub loop that replays the recorded finished-loop shapes (docs/test-evidence/agents/cycle-1/H-aqf15/testing-3,
trace tr-tally-b24c5af1-9690b486: get_recon_run -> find_matching_items -> 146 tokens out, guard 0, yet a rules reply). Live proof: tests/evals/tally_w2.yaml."""
from types import SimpleNamespace

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e4_cases, e6_trace, n1_tally as T, wh
from tools import seed_10uc as S


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("tallyw2")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    from sh_platform.auth.accounts import AccountStore
    helen = AccountStore(root).get_by_email(S.EG.email_of(S.OWNER[0]))
    V = S.viewers(ids)
    V["Helen Foo"] = Viewer("Helen Foo", frozenset({"owner"}), False, helen["account_id"])
    yield {"plane": plane, "V": V, "root": root}
    mp.undo()


@pytest.fixture(autouse=True)
def fresh_wording(world):
    T._cache_path(world["plane"]).unlink(missing_ok=True)


def cid(world, startswith, contains=""):
    return next(c["id"] for c in e4_cases.listing(world["plane"], world["V"]["Grace Ong"]) if c["title"].startswith(startswith) and contains in c["title"])


def ask(world, startswith, contains, q, who="Mei Chen"):
    return T.explain(world["plane"], world["V"][who], cid(world, startswith, contains), q)


def loop_says(monkeypatch, text, status="done", tool_facts=(), numbers_replaced=0, seen=None):
    """A stub loop: what run_agent returned on the recorded finished loop (status done, guard 0), with the tool figures it read."""
    import sh_platform.agents.loop as loop
    import sh_platform.build.agents.runtime as rt
    monkeypatch.setattr(rt, "runtime_for_plane", lambda plane: SimpleNamespace(model=object()))
    monkeypatch.setattr("sh_platform.v1.router.route", lambda model, *a, **k: model)

    def run(*a, **k):
        if seen is not None:
            seen.append(k)
        return SimpleNamespace(status=status, text=text, proposals=[], numbers_replaced=numbers_replaced, tool_facts=list(tool_facts))
    monkeypatch.setattr(loop, "run_agent", run)


def rules_reasons(plane, tid):
    return [s.get("reason") for t in e6_trace.steps_for(plane, tid) for s in (t.get("steps") or []) if s.get("kind") == "rules"]


# ---- H1-09: a finished loop's answer is shown; when it is not, the trace says why ---------------------------------------------------------

Q = "Why does Entity B's cash differ from the administrator, and by how much?"


@pytest.mark.parametrize("said", [
    # prose with placeholders (no JSON object): was json.loads of "{timing_line} ... {difference}" -> error -> silent rules reply
    "{timing_line} The two sides differ by {difference}.",
    # the run date as the tool printed it (2026-10-08): was a "figure no tool returned" for the digit scan
    '{"answer": "On 2026-10-08 the sides differ by {difference}. {candidate_line}"}',
    # a fenced object with a line break inside the string
    '```json\n{"answer": "{candidate_line}\n{difference_line}"}\n```',
    # a figure the tool returned, written out (find_matching_items: 12,400 USD)
    '{"answer": "The 12,400 USD wire equals the difference. {timing_line}"}',
])
def test_h109_a_finished_loop_answer_is_shown(world, monkeypatch, said):
    loop_says(monkeypatch, said, tool_facts=[{"id": "tool:find_matching_items", "label": "text", "value": "12,400", "group_size": 5}])
    got = ask(world, "Cash differs", "Entity B", Q)
    assert got["answer_worded_by"] == "model" and not got["answer"].startswith("Rules-only reply"), got["answer"]
    assert "{" not in got["answer"] and "12,400 USD" in got["answer"]


@pytest.mark.parametrize("said,status,replaced,reason", [
    ('{"answer": "The difference is 99,999 USD."}', "done", 0, "invented_figure"),      # a figure neither the case nor a tool holds
    ('{"answer": "{difference}"}', "done", 1, "invented_figure"),                        # the loop's guard replaced one
    ('{"answer": "{secret_line}"}', "done", 0, "placeholder_not_offered"),
    ('{"answer": ', "done", 0, "unreadable_reply"),
    ('{"answer": ""}', "done", 0, "no_answer"),
    ("I could not reach the model just now.", "error", 0, "loop_error"),                # the 402 no_credit shape: the loop ends in error
])
def test_h109_a_dropped_answer_leaves_its_reason_on_the_trace(world, monkeypatch, said, status, replaced, reason):
    loop_says(monkeypatch, said, status=status, numbers_replaced=replaced)
    got = ask(world, "Cash differs", "Entity B", Q)
    assert got["answer_worded_by"] == "rules" and got["answer"].startswith("Rules-only reply")
    assert reason in rules_reasons(world["plane"], got["trace_id"])


def test_h109_a_planted_part_of_a_recorded_figure_is_still_refused(world, monkeypatch):
    loop_says(monkeypatch, '{"answer": "The difference is 12 USD. {difference}"}')       # 12 is not 12,400
    assert ask(world, "Cash differs", "Entity B", Q)["answer_worded_by"] == "rules"


def test_h109_every_turn_with_tools_must_read_the_case(world, monkeypatch):
    """The second turn (earlier-turn facts in ctx) once answered without a tool: the tool is now required whenever the tools are there."""
    seen = []
    loop_says(monkeypatch, '{"answer": "{who_line}"}', seen=seen)
    ask(world, "Cash differs", "Entity B", Q)
    ask(world, "Cash differs", "Entity B", "Who should I ask?")
    assert seen and all(k.get("require_tool") is True for k in seen)


def test_h109_model_off_says_so_on_the_trace(world):
    got = ask(world, "Cash differs", "Entity B", Q)
    assert "model_off" in rules_reasons(world["plane"], got["trace_id"])


# ---- DG-4: the three thin follow-ups, answered with the case's figures (rules wording; the model gets the same placeholders as its hint) ----

def test_dg4_why_did_the_total_change_on_the_revision(world):
    a = ask(world, "Investigate the 180,000", "", "Why did the total change since the September report?")["answer"]
    assert "10,180,000 USD" in a and "10,000,000 USD" in a and "180,000 USD" in a and "not something these records answer" not in a


def test_dg4_when_is_it_due_and_is_it_confirmed(world):
    c = cid(world, "Fund the capital call")
    plane = world["plane"]
    b = T.build(plane, T._exc(plane, c))
    assert {"due_line", "confirm_line"} <= set(T._topic_keys(b, "When is this due and is it confirmed?"))
    a = T.explain(plane, world["V"]["Mei Chen"], c, "When is this due and is it confirmed?")["answer"]
    assert b["have"]["due"] in a and "confirmed" in a.split(b["have"]["due"], 1)[1]


def test_dg4_is_this_over_the_allowance_on_the_fx_forward(world):
    got = ask(world, "Trade", "FXF-2026-002", "Is this over the allowance?")
    a = got["answer"]
    assert "1,050.19 USD over it" in a and "5,000 USD" in a and "missing" not in a.lower()


def test_dg4_a_one_part_question_still_gets_one_topic(world):
    b = T.build(world["plane"], T._exc(world["plane"], cid(world, "Cash differs", "Entity B")))
    assert T._topic_keys(b, "Is this timing?") == ["timing_line", "movement_line"]


# ---- ask_finance decision: a participant may ask Finance (a request, not an act) -----------------------------------------------------------

def test_a_participant_may_ask_finance_but_not_act(world):
    plane, V = world["plane"], world["V"]
    part = next(v for v in V.values() if "participant" in v.roles)
    seen = e4_cases.listing(plane, part)
    assert seen, "the seeded participant sees no case"
    with wh.connect(plane, read_only=True) as con:
        pf = con.execute("select portfolio_id from exceptions where id = ?", [seen[0]["id"]]).fetchone()[0]
    c = e4_cases.open(plane, {"exception_type": "break", "title": "Cash differs · test · accounting", "portfolio_id": str(pf), "accounting_view_affected": True})
    assert e4_cases.get(plane, c, part)["can"]["ask_finance"] and not e4_cases.get(plane, c, part)["can"]["take"]
    assert e4_cases.ask_finance(plane, c, part, "Grace Ong")["id"] == c
    with pytest.raises(e4_cases.Refused):
        e4_cases.take(plane, c, part)


# ---- H1-03: the owner seat asks Tally like any other role ----------------------------------------------------------------------------------

def test_h103_the_owner_may_read_and_ask_tally(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.auth.permissions import load_permissions
    from sh_platform.v1 import e4a_routes as R
    perms = load_permissions()
    for key in ("GET /api/v1/cases/{cid}/tally", "POST /api/v1/cases/{cid}/ask", "GET /api/v1/cases/{cid}"):
        assert "owner" in perms.rule_for(*key.split(" ", 1)).roles, key
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: world["plane"])
    monkeypatch.setattr(R, "viewer_of", lambda req: world["V"]["Helen Foo"])
    c = TestClient(app)
    case = cid(world, "Cash differs", "Entity B")
    # The cycle-1 403 was E1d, not the role: the seeded owner seat (tools/seed_10uc._owner) belongs to no access group, so she sees no case.
    first = c.get(f"/api/v1/cases/{case}/tally")
    if first.status_code == 403:
        assert "access to this case" in first.text
        from sh_platform.v1 import e1_access
        plane = world["plane"]
        with wh.connect(plane, read_only=True) as con:
            gid = con.execute("select id from access_groups where group_name = 'Investment office'").fetchone()[0]
            uid = e1_access.user_id_of(con, world["V"]["Helen Foo"])
        e1_access.add_member(plane, world["V"]["Grace Ong"], str(gid), str(uid))
    assert c.get(f"/api/v1/cases/{case}/tally").status_code == 200
    r = c.post(f"/api/v1/cases/{case}/ask", json={"question": "Why does Entity B's cash differ?"})
    assert r.status_code == 200 and "12,400 USD" in r.json()["answer"]
