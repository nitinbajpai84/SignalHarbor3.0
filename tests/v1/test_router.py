"""R1 router: tiers by rules, the Testing / Real use mode (default, who may flip), the model per tier per mode, the per-tier provider,
retry up and the cost log. No live model: clients are built but never called, and the routed calls use stubs."""
import json
import secrets
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.egress.model import ModelReply
from sh_platform.app import create_app
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.providers import build_model_client, select_provider, usage
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import router as R
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (SEED / "neera").is_dir(), reason="no seeded demo data")
FAKE = "fake-key-not-real"
BASE = {"SH_MODEL_PROVIDER": "openrouter", "OPENROUTER_API_KEY": FAKE, "GOOGLE_API_KEY": FAKE,
        "SH_MODEL_FAST": "anthropic/claude-haiku-5.5", "SH_MODEL_SPECIALIST": "anthropic/claude-sonnet-5.5",
        "SH_MODEL_MANAGER": "anthropic/claude-opus-5.5", "SH_MODEL_FAST_ALT": "openai/gpt-6-luna"}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")  # the real .env holds keys: never a live model call
    data = tmp_path / "data"
    for part in ("_control", "neera"):
        shutil.copytree(SEED / part, data / part)
    (data / "neera" / "settings" / "model_mode.json").unlink(missing_ok=True)  # the live company may have flipped; tests start from the default
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    return app, PlaneStore(data).plane_for("neera"), secrets.token_urlsafe(16)


def client(world, who):
    app, _, pw = world
    c = TestClient(app)
    email = f"{who}.neera@example.test"
    app.state.account_store.set_password(email, pw)
    assert c.post("/api/auth/login", json={"email": email, "password": pw}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_tiers_by_rules():
    assert R.pick_tier("north", "reply", {"text": "yes"}) == "fast"
    assert R.pick_tier("north", "reply", {"text": "Process map is right."}) == "fast"
    assert R.pick_tier("north", "reply", {"text": "yes", "files": True}) == "specialist"
    assert R.pick_tier("north", "reply", {"text": "We report net worth monthly to the family."}) == "specialist"
    assert R.pick_tier("north", "extraction") == "fast"
    assert R.pick_tier("flow", "formula_sql") == "manager"
    assert R.pick_tier("north", "reply", {"text": "yes", "closing": True}) == "manager"


def test_mode_default_and_only_the_decision_maker_flips(world):  # NA-4 (10 Oct): only company_admin and sponsor switch; Real use costs money
    arjun, leela, dev = client(world, "arjun.mehta"), client(world, "leela.raman"), client(world, "dev.sharma")  # admin, analyst, participant
    got = dev.get("/api/v1/router/mode").json()
    assert got["mode"] == "testing"
    assert leela.post("/api/v1/router/mode", json={"mode": "real"}).status_code == 403
    assert dev.post("/api/v1/router/mode", json={"mode": "testing"}).status_code == 403
    r = arjun.post("/api/v1/router/mode", json={"mode": "real"})
    assert r.status_code == 200 and r.json()["mode"] == "real" and r.json()["by"] == "Arjun Mehta"
    assert dev.get("/api/v1/router/mode").json()["mode"] == "real"
    assert arjun.post("/api/v1/router/mode", json={"mode": "cheap"}).status_code == 400
    assert arjun.post("/api/v1/router/mode", json={"mode": "testing"}).status_code == 200


def test_model_per_tier_per_mode_and_per_tier_provider(world):
    _, plane, _ = world
    def picked(mode, tier, alt=False):
        m = build_model_client(plane, R.mode_env(BASE, mode, tier, alt), tier)  # built, never called
        return m.gateway.model_allowlist[0], m.model_id
    assert picked("testing", "fast") == ("openrouter.ai", "qwen/qwen3.7-flash")
    assert picked("testing", "specialist") == ("openrouter.ai", "openai/gpt-oss-120b")
    assert picked("testing", "manager") == ("openrouter.ai", "openai/gpt-oss-120b")  # Nitin 10 Oct 11:50: cheapest OpenRouter models
    assert picked("real", "fast") == ("openrouter.ai", "anthropic/claude-haiku-5.5")
    assert picked("real", "fast", alt=True) == ("openrouter.ai", "openai/gpt-6-luna")
    assert R.mode_env(BASE, "testing", "fast", alt=True) is None and R.mode_env(BASE, "real", "manager", alt=True) is None
    # the per-tier provider; without it the one-provider behaviour stays, and off stays off
    env = {**BASE, "SH_MODEL_FAST_PROVIDER": "gemini", "SH_MODEL_FAST": "gemini-2.5-flash"}
    assert select_provider(env, "fast").adapter.name == "gemini" and select_provider(env, "specialist").adapter.name == "openrouter"
    assert select_provider(BASE, "fast").adapter.name == "openrouter"
    assert select_provider({**env, "SH_MODEL_PROVIDER": "off"}, "fast") is None


class Stub:
    def __init__(self, model_id, reply=None, fail=False):
        self.model_id, self.reply, self.fail, self.calls = model_id, reply, fail, 0

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.calls += 1
        if self.fail:
            raise EgressBlocked("transport_failed")
        return self.reply


def test_free_tier_failure_falls_up_then_unusable_retries_up_and_costs_log(world):
    _, plane, _ = world
    stubs = {"fast": Stub("free", fail=True), "specialist": Stub("spec", ModelReply("not json at all")),
             "manager": Stub("mgr", ModelReply('{"reply": "Done"}', usage={"tokens_in": 120, "tokens_out": 9}))}
    m = R.RoutedModel(object(), plane, "north", "reply", "fast", "i-1", want_json=True, build=lambda mode, tier, alt: None if alt else stubs[tier])
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": json.dumps({"context": {"facts": []}, "question": "q"})}]
    assert m.complete("m1_intent", msgs).text == '{"reply": "Done"}'
    rows = R.costs(plane, "i-1")["rows"]
    assert [(r["tier"], r["step"], r["ok"]) for r in rows] == [
        ("fast", "first", "transport_failed"), ("specialist", "fallback", "not_json"), ("manager", "retry_up", "ok")]
    assert rows[-1]["tokens_in"] == 120 and not rows[-1]["estimated"] and rows[1]["estimated"] and rows[0]["mode"] == "testing"
    # INT3: usd per call from the list-price table (an unpriced model logs None) and latency per call
    # AQ1 RC-5: an unlisted model is priced at its tier's default (estimated), never null; Sonnet 5.5 at its list price 2/10
    assert rows[0]["cost_usd"] == 0.0 and rows[-1]["cost_usd"] == round((120 * 4 + 9 * 20) / 1e6, 6) and all(isinstance(r["latency_ms"], int) for r in rows)
    assert R.price_usd("anthropic/claude-sonnet-5.5", 1_000_000, 1_000_000) == 12.0 and R.price_usd("nope", 5, 5) is None
    priced = R.RoutedModel(object(), plane, "north", "reply", "fast", "i-2",
                           build=lambda *a: Stub("gemini-2.5-flash", ModelReply("ok", usage={"tokens_in": 1000, "tokens_out": 100})))
    priced.complete("m1_intent", msgs)
    c = R.costs(plane, "i-2")
    assert c["cost_usd"] == 0.00055 and c["priced_all"] and c["avg_latency_ms"] is not None and priced.attempts[0]["cost_usd"] == 0.00055
    # a gateway refusal is never retried on another model
    refuse = Stub("x")
    refuse.complete = lambda *a, **k: (_ for _ in ()).throw(EgressBlocked("vault_name"))
    with pytest.raises(EgressBlocked):
        R.RoutedModel(object(), plane, "north", "reply", "fast", build=lambda *a: refuse).complete("m1_intent", msgs)


def test_stubs_pass_through_and_router_off(world, monkeypatch):
    _, plane, _ = world
    stub = Stub("s", ModelReply("hi"))
    assert R.route(stub, "north", "reply") is stub and R.route(None, "north", "reply") is None
    real = build_model_client(plane, BASE, "specialist")
    real.route_env = BASE  # what build_model_client attaches when it builds from the settings
    assert isinstance(R.route(real, "north", "reply", text="yes"), R.RoutedModel)
    monkeypatch.setenv("SH_ROUTER", "off")
    assert R.route(R.RoutedModel(real, plane, "", "", "specialist"), "north", "reply") is real


def test_usage_from_both_providers():
    assert usage(json.dumps({"usage": {"prompt_tokens": 10, "completion_tokens": 3}})) == {"tokens_in": 10, "tokens_out": 3}
    assert usage(json.dumps({"usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2}})) == {"tokens_in": 7, "tokens_out": 2}
    assert usage("{}") is None and usage("not json") is None


def test_fixd_a_timed_out_model_is_not_asked_again_as_the_next_tier(world):
    """FIXD: in Testing mode the specialist and the manager are one model; after it times out the turn does not wait for it a second time."""
    _, plane, _ = world
    same, fast = Stub("oss", fail=True), Stub("flash", ModelReply('{"reply": "Done"}'))
    stubs = {"specialist": same, "manager": same, "fast": fast}
    m = R.RoutedModel(object(), plane, "north", "reply", "specialist", "i-9", build=lambda mode, tier, alt: None if alt else stubs[tier])
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": json.dumps({"context": {"facts": []}, "question": "q"})}]
    assert m.complete("m1_intent", msgs).text == '{"reply": "Done"}'
    assert same.calls == 1 and [r["ok"] for r in R.costs(plane, "i-9")["rows"]] == ["transport_failed", "same_model_failed", "ok"]
