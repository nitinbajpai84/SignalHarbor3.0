"""NM1: no model credit. North still starts the intent by rules and says so, one refusal ends the router's walk for that provider, and the
messages (North, the voice line) are the wave-2 model_trouble words for an administrator and a plain line for everyone else.
The provider is a stub that refuses every call for credit. Synthetic data only."""
import time

import pytest

from sh_platform.egress import gateway as GW
from sh_platform.egress.errors import EgressBlocked
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e6_trace
from sh_platform.v1 import g1_access
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import router as R
from sh_platform.v1 import v1_voice_routes as V

MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")
GRACE = Viewer("Grace Ong", frozenset({"company_admin"}), False, "acc-grace")
ENV = {"SH_MODEL_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "fake-key-not-real", "GOOGLE_API_KEY": "fake-key-not-real",
       "SH_MODEL_FAST": "m/fast", "SH_MODEL_SPECIALIST": "m/spec", "SH_MODEL_MANAGER": "m/mgr"}
TROUBLE = {"code": "no_credit", "providers": ["openrouter"], "at": None, "words": ""}
WORDS = "I need a monthly performance report for the investment committee"


class Base:
    route_env = ENV  # what build_model_client attaches to a client built from the settings: the router rebuilds per tier from it


@pytest.fixture()
def refusing(tmp_path, monkeypatch):
    """A plane, and a provider that refuses every call for credit; `calls` lists the models it was asked."""
    monkeypatch.setattr(g1_access, "check_agent", lambda *a, **k: None)
    monkeypatch.setattr(e6_trace, "model_trouble", lambda plane: TROUBLE)
    (tmp_path / "co").mkdir()
    calls: list[str] = []

    class Client:
        def __init__(self, model):
            self.model_id = model

        def complete(self, module_id, messages, tools=None, **kw):
            calls.append(self.model_id)
            raise EgressBlocked("no_credit")

    monkeypatch.setattr(R, "build_model_client", lambda plane, env=None, tier="specialist", client=None: Client(env[f"SH_MODEL_{tier.upper()}"]))
    GW._breaker.clear()
    yield PlaneStore(tmp_path).plane_for("co"), calls
    GW._breaker.clear()


def test_without_credit_north_starts_the_intent_by_rules_and_says_so(refusing):
    plane, calls = refusing
    t0 = time.perf_counter()
    v = C.start(plane, MEI, WORDS, model=Base())
    assert time.perf_counter() - t0 < 10  # cold process pays catalogue and vault cost once; the warm figure is in NM1.md
    iid = v["id"]
    assert P1.for_intent(plane, iid) is not None                       # the project is made
    sow = N.read_sow(plane, iid)
    assert sow["title"].startswith("Monthly performance report") and WORDS in sow["goal"]["line"]  # title and goal line from the words
    last = v["turns"][-1]
    assert last["name"] == N.FALLBACK_NAME and "changed nothing" not in last["text"]
    assert last["text"].startswith(C.OFFLINE) and last["text"].endswith("?")  # the line, then the next template question, asked plainly
    asked = v["asked"]
    assert len(calls) <= 2                                             # one refusal per provider ends the walk, not a call per tier and alternate
    # a later turn fills the section asked about, by rules
    v = C.chat(plane, iid, MEI, "Only me and the people I name", model=Base())
    assert asked in v["needs_done"] and v["asked"] != asked
    assert v["turns"][-1]["name"] == N.FALLBACK_NAME and v["turns"][-1]["text"].startswith(C.OFFLINE)


def test_an_administrator_is_told_why_and_what_to_do_everyone_else_that_it_is_offline(refusing):
    plane, _ = refusing
    admin = C.start(plane, GRACE, WORDS, model=Base())["turns"][-1]["text"]
    assert admin.startswith("The model account is out of credit (openrouter). Top it up to get model answers and voice; until then answers come from rules.")
    assert C.start(plane, MEI, WORDS, model=Base())["turns"][-1]["text"].startswith(
        "The assistant is offline for now; keep typing, your words are kept.")


def test_one_refusal_ends_the_walk_for_the_provider_and_an_open_breaker_sends_nothing(refusing, two_provider_testing_mode):
    plane, calls = refusing
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "{}"}]
    mk = lambda tier: R.RoutedModel(Base(), plane, "north", "reply", tier, "i-1")  # noqa: E731
    with pytest.raises(EgressBlocked) as e:
        mk("manager").complete("m1_intent", msgs)                      # testing mode: manager is OpenRouter, specialist and fast are Gemini
    assert e.value.reason_code == "no_credit" and len(calls) == 2      # one call per provider, none per tier or alternate
    calls.clear()
    GW._breaker["openrouter.ai"] = GW._breaker["generativelanguage.googleapis.com"] = ("no_credit", GW._clock() + 60)
    t0 = time.perf_counter()
    with pytest.raises(EgressBlocked) as e:
        mk("specialist").complete("m1_intent", msgs)
    assert e.value.reason_code == "no_credit" and calls == [] and time.perf_counter() - t0 < 1


def test_the_voice_line_gives_the_same_words(refusing, monkeypatch):
    plane, _ = refusing
    assert V._why(plane, GRACE).startswith("The model account is out of credit (openrouter). Top it up")
    assert V._why(plane, MEI) == C.OFFLINE
    monkeypatch.setattr(e6_trace, "model_trouble", lambda plane: None)
    assert V._why(plane, GRACE) == V.UNAVAILABLE
