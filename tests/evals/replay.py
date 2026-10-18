"""Offline model replay: a stub provider that plays back the model replies and failures recorded in docs/test-evidence/agents/.

It sits where the internet would be: an httpx MockTransport behind the product's own model transport, so every replayed reply still passes
the real gateway (structure check, vault, figure check, egress log), the real provider adapter (Gemini or OpenRouter wire format), the
retry policy and the router's tier fall-down. Nothing is special-cased in the product and no real key or host is ever used.

A script is a list of steps, played in order, one per agent-loop model call (a call that offers tools); the last step repeats when the
script runs out. A side call that offers no tools (memory learner, talk summariser) does not use up a `say` / `call` step: it gets SIDE,
an empty JSON answer; an `http` / `drop` step fails every call, side calls too, as a provider that is down does:
  {say: "text"}                                  the model answers in words
  {call: tool, args: {...}}  or  {calls: [[tool, {...}], ...]}   the model calls tools (with optional `say`)
  {http: 402}                                    the provider answers with that status (402 no_credit, 429 rate_limited, 401 key refused)
  {drop: true}                                   the connection fails (the gateway's transport_failed)
  {repeat: n, ...one of the above}               the same step n times
A script is given as a list, or as the name of a recorded shape (SHAPES).

  with replay.install("no_credit") as r:      # in a test or the runner's --offline mode
      ...product code...
      r.seen                                    # (provider, model, tool names offered) per model call
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import threading
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "test-evidence" / "agents"
DUMMY_KEY = "replay-offline-not-a-key"  # only ever reaches the MockTransport
# ponytail: one neutral answer for every side call; give a script its own side answers if a side call's output ever matters to an item
SIDE = {"say": json.dumps({"items": []})}


# ---- recorded shapes -------------------------------------------------------------------------------------------------------------

def _recorded_change(change_id: str, transcript: str = "new-uc/B-transcript.json") -> dict:
    """A plan change exactly as Span drafted it in a recorded run (name, purpose, select, depends_on)."""
    def walk(o):
        if isinstance(o, dict):
            if o.get("id") == change_id and o.get("tables"):
                return o
            return next((x for v in o.values() if (x := walk(v))), None)
        if isinstance(o, list):
            return next((x for v in o if (x := walk(v))), None)
        return None
    full = EVIDENCE / transcript  # docs/test-evidence/ is not in git: a checkout without it reads the committed copy of the change
    src = full if full.is_file() else Path(__file__).resolve().parent / "recorded" / f"{change_id}.json"
    ch = walk(json.loads(src.read_text(encoding="utf-8")))
    if not ch:
        raise LookupError(f"{change_id} is not in {transcript}")
    t = ch["tables"][0]
    sql = re.sub(r"(?is)^\s*create\s+table\s+\S+\s+as\s+", "", t["sql"])  # the model drafts the select; the plan wraps it
    return {"name": t["name"], "purpose": t["purpose"], "sql": sql, "depends_on": list(t["depends_on"])}


def _multiline(sql: str) -> str:
    """The same select as a model writes it on several lines (NU-12: every gold request of use case B)."""
    return re.sub(r"\s+(FROM|JOIN|WHERE|GROUP BY|QUALIFY|ORDER BY)\b", r"\n\1", sql)


def qualify_sql() -> dict:
    """NU-14: ch-eb7c061c, QUALIFY written before GROUP BY; it passed the plan check and failed the sandbox run."""
    return _recorded_change("ch-eb7c061c")


def multiline_sql() -> str:
    """NU-12: a normal SELECT with line breaks (the recorded ch-eb7c061c select, QUALIFY taken out so only the line breaks are on trial)."""
    sql = re.sub(r"(?is)\s+QUALIFY\s+.*?(?=\s+GROUP BY)", "", qualify_sql()["sql"])
    return _multiline(sql)


# NU-06 (tr-north-52658793-*): ~24 propose_intent_section calls per turn, all refused as argument_check:section / content. The two shapes
# the refusal codes name: the section given as the intent's key ("kpis", not "kpi"), and the content sent as a JSON string, not an object.
_BAD_SECTION = [
    ("propose_intent_section", {"section": "kpis", "content": {"name": "Manager concentration", "unit": "percent"}}),
    ("propose_intent_section", {"section": "kpi", "content": json.dumps({"name": "Manager concentration", "unit": "percent"})}),
]

SHAPES = {
    # NU-28, AQF10-01: Gemini 402 "prepayment credits are depleted", OpenRouter refused (out of credit) on every tier and the ALT models
    "no_credit": lambda: [{"http": 402}],
    # H1-01: in Real use every first call to the manager tier failed with transport_failed
    "transport_failed": lambda: [{"drop": True}],
    # NU-06: 24 refused argument shapes in one turn, then the model gives up in words
    "refused_args_24": lambda: [{"repeat": 12, "calls": _BAD_SECTION}, {"say": "I have drafted the three figures for you to check."}],
    # NU-12: dry_run_sql with a multi-line select, then the answer
    "multiline_sql": lambda: [{"call": "dry_run_sql", "args": {"sql": multiline_sql()}}, {"say": "The select runs; I can draft it as a change."}],
    # NU-14: the recorded QUALIFY-before-GROUP-BY draft
    "qualify_sql": lambda: [{"call": "propose_plan_change", "args": qualify_sql()},
                            {"say": "I have drafted gold_exposure_by_manager_across_ent_summary for the data team to accept."}],
    # NU-25, H1-04, H1-06: the model answers in words where a tool call was required (claims a draft that was never proposed)
    "words_not_tool": lambda: [{"say": "I have drafted gold_manager_reporting_scorecard; it is awaiting approval from the data team."}],
}


def script_of(spec) -> list[dict]:
    """A script from a shape name or a list of steps, with `repeat` expanded."""
    steps = SHAPES[spec]() if isinstance(spec, str) else list(spec or [])
    if not steps:
        raise ValueError("a replay script needs at least one step")
    out = []
    for s in steps:
        s = dict(s)
        out += [s] * int(s.pop("repeat", 1))
    return out


# ---- wire formats ----------------------------------------------------------------------------------------------------------------

def _calls(step) -> list[tuple[str, dict]]:
    if step.get("call"):
        return [(step["call"], step.get("args") or {})]
    return [(n, a) for n, a in step.get("calls") or []]


def wire(provider: str, step: dict) -> dict:
    """The provider's own reply body for a `say` / `call` step (usage included, so the cost log is not estimated)."""
    text, calls = step.get("say") or "", _calls(step)
    usage_in, usage_out = 1200, max(1, len(text) // 4 + 20 * len(calls))
    if provider == "gemini":
        parts = ([{"text": text}] if text else []) + [{"functionCall": {"name": n, "args": a}} for n, a in calls]
        return {"candidates": [{"content": {"role": "model", "parts": parts or [{"text": ""}]}}],
                "usageMetadata": {"promptTokenCount": usage_in, "candidatesTokenCount": usage_out}}
    msg = {"role": "assistant", "content": text or None}
    if calls:
        msg["tool_calls"] = [{"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a, ensure_ascii=False)}}
                             for i, (n, a) in enumerate(calls)]
    return {"choices": [{"message": msg}], "usage": {"prompt_tokens": usage_in, "completion_tokens": usage_out}}


# ---- the stub provider -----------------------------------------------------------------------------------------------------------

class Replay:
    """One script, played across every model call of every provider. Thread safe (the product holds two calls in flight)."""

    def __init__(self, spec="no_credit"):
        self._lock = threading.Lock()
        self.load(spec)

    def load(self, spec) -> None:
        with self._lock:
            self.spec, self.steps, self.i, self.seen = spec, script_of(spec), 0, []

    def _next(self, loop_call: bool) -> dict:
        with self._lock:
            step = self.steps[min(self.i, len(self.steps) - 1)]
            if not loop_call and not (step.get("http") or step.get("drop")):
                return SIDE
            self.i += 1
            return step

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        provider = "gemini" if host.endswith("googleapis.com") else "openrouter" if host == "openrouter.ai" else None
        if provider is None:  # the product never sends anything else to a model transport; refuse loudly
            raise httpx.ConnectError(f"replay: no provider at {host}", request=request)
        body = json.loads(request.content or b"{}")
        model = body.get("model") or (re.search(r"/models/([^/:]+)", request.url.path) or [None, None])[1]
        tools = [t.get("function", t).get("name") for t in body.get("tools") or []] if provider == "openrouter" else \
            [d.get("name") for t in body.get("tools") or [] for d in t.get("functionDeclarations") or []]
        step = self._next(bool(tools))
        self.seen.append({"provider": provider, "model": model, "tools": tools, "step": "side" if step is SIDE else next(iter(step))})
        if step.get("drop"):
            raise httpx.ConnectError("replay: connection dropped", request=request)
        if step.get("http"):
            return httpx.Response(int(step["http"]), json={"error": {"code": int(step["http"]), "message": "replayed provider refusal"}},
                                  request=request)
        return httpx.Response(200, json=wire(provider, step), request=request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler), follow_redirects=False)


MODEL_ENV = ("SH_MODEL_PROVIDER", "GOOGLE_API_KEY", "OPENROUTER_API_KEY")


@contextlib.contextmanager
def install(spec="no_credit", env=None):
    """Route every model call of this process to a Replay. `env` (default os.environ) gets a provider and dummy keys so the product
    builds its model clients as it does in production; the old values are put back on exit."""
    from sh_platform.egress import gateway
    from sh_platform.egress import providers as P
    env = os.environ if env is None else env
    r = Replay(spec)
    real = P.make_httpx_transport

    def via_replay(*a, client=None, **kw):
        return real(*a, client=client if client is not None else r.client(), **kw)

    old_env = {k: env.get(k) for k in MODEL_ENV}
    old_sleep = gateway._sleep
    # the tiers keep their providers (model_modes.yaml, .env); this only makes sure the model is on and both providers have a "key"
    env.update({"SH_MODEL_PROVIDER": "openrouter", "GOOGLE_API_KEY": DUMMY_KEY, "OPENROUTER_API_KEY": DUMMY_KEY})
    P.make_httpx_transport, gateway._sleep = via_replay, (lambda s: None)
    try:
        yield r
    finally:
        P.make_httpx_transport, gateway._sleep = real, old_sleep
        for k, v in old_env.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
