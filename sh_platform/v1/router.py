"""R1 the model router: which tier each agent call uses, the Testing / Real use mode, retries up and the cost log.

- `pick_tier(agent, task, signals)`: rules only, no model call. `ambiguous()` is the one hook where a typed classifier could go later.
- `route(model, agent, task, intent_id, plane=None, **signals)`: the model an engine passes to `run_agent`. A real client (one built
  by `build_model_client` from the settings, so it carries `route_env`) becomes a `RoutedModel` that resolves the tier's model from the
  company's current mode on every call (no restart). A test stub or an injected client is returned as it is: tests never reach a model.
- Retry up, never down: an unusable reply (empty, not the asked JSON, or a figure the reply guard would rewrite) is asked once more on
  the next tier; a failed provider call goes to the tier's `_ALT` model (Real use) or, with none, to the next tier (Testing: the free
  Google key at its limit falls to the specialist silently). Every step is a line in `context/model_costs.jsonl`.
  AQ1: when the tier above cannot be reached (no credit, provider down), the reply already in hand is returned (the loop's guard checks
  it), an empty first reply is asked once more on its own tier, and a manager-first call that cannot be reached tries the specialist once
  ("fallback_down", the only step down: availability, never quality). A gateway refusal is logged as an attempt before it is raised.
  RC2-2: a retry up to a tier whose model in this mode is the same model (Testing keeps the cheap models: specialist and manager are both
  gemini-2.5-flash) is never made: the same model fails the same way. The attempt says so ("no stronger model in this mode") and the reply in
  hand goes to the loop's guard.
- `SH_ROUTER=off` pins every call to the settings' specialist model (the pre-router behaviour).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from sh_platform.agents.guard import check_numbers
from sh_platform.agents.loop import OUTSIDE_MARKER, _figures
from sh_platform.demo_limits import over_cap, real_mode_allowed
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import ROUTED, last_masked, provider_down
from sh_platform.egress.providers import TIERS, ProviderError, build_model_client, select_provider
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
UP = {"fast": "specialist", "specialist": "manager", "manager": None}
DOWN = {"manager": "specialist", "specialist": "fast", "fast": None}  # availability only (provider out of credit or down), never quality
MODES = ("testing", "real")
COST_LOG = "model_costs.jsonl"
# the provider call itself failed (any other refusal is the gateway's). TAQ-S2: in the order the final refusal names them, the cause an
# administrator can fix first, so a turn where every model was out of credit says no_credit, never transport_failed
BILLING_REFUSED = ("no_credit", "provider_key_refused")  # NM1: retrying another model of the same provider cannot help
PROVIDER_FAILED = ("no_credit", "provider_key_refused", "model_unknown", "no_credential", "rate_limited", "provider_bad_request", "transport_failed")
FAST_TASKS = frozenset({"extraction", "doc_read", "cleanup", "summary"})
MANAGER_TASKS = frozenset({"formula_sql", "closing", "design_approval", "redraft"})
_ACK = re.compile(r"\s*(yes|yep|yeah|ok(ay)?|sure|agreed|correct|right|fine|good|great|perfect|thanks?( you)?|go ahead|"
                  r"(that'?s|that is|it'?s|looks) (right|correct|fine|good)|[a-z ]{1,30} (is|are|looks) (right|correct|fine|good))[.!\s]*",
                  re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def router_on() -> bool:
    return (os.environ.get("SH_ROUTER") or "").strip().lower() != "off"


# ---- the tier ----------------------------------------------------------------------------------------------------------

def ambiguous(agent: str, task: str, signals: dict) -> str | None:
    """V5W-7: a short lookup question goes to the fast tier (chat_fastpath rules, then Jev when SH_JEV_API_KEY is set). Returns a tier or None."""
    if task != "answer" or not signals.get("text"):
        return None
    from sh_platform.v1.chat_fastpath import tier_for
    return tier_for(str(signals["text"]), bool(signals.get("files")))


def canonical_agent(agent: str) -> str:
    """G1: the router key of the three agents (north, span, lumen) for any old key; an unknown key stays as it is."""
    for key, olds in (modes().get("agents") or {}).items():
        if agent in olds:
            return key
    return agent


def pick_tier(agent: str, task: str, signals: dict | None = None) -> str:
    s = signals or {}
    if s.get("retry") or s.get("check_failed") or s.get("contradictions") or s.get("closing") or task in MANAGER_TASKS:
        return "manager"
    if task in FAST_TASKS:
        return "fast"
    text = str(s.get("text") or "")
    if text and len(text) <= 80 and not s.get("files") and _ACK.fullmatch(text):
        return "fast"  # a short acknowledgement: "yes", "that's right", "process map is right"
    return ambiguous(agent, task, s) or "specialist"


# ---- the mode ----------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def modes() -> dict:
    return yaml.safe_load((Path(__file__).with_name("model_modes.yaml")).read_text(encoding="utf-8"))


def _mode_path(plane) -> Path:
    return plane.path("settings", "model_mode.json")


def mode_of(plane) -> dict:
    """{mode, by, at}; the default (testing) when nothing is saved or the file cannot be read."""
    try:
        got = read_json_strict(_mode_path(plane), dict)
    except (OSError, ValueError):
        got = None
    if not got or got.get("mode") not in MODES:
        return {"mode": modes()["default"], "by": None, "at": None}
    if got["mode"] == "real" and not real_mode_allowed():  # the public demo stays on the cheap models
        return {"mode": "testing", "by": None, "at": None}
    return {"mode": got["mode"], "by": got.get("by"), "at": got.get("at")}


def set_mode(plane, mode: str, by: str) -> dict:
    if mode not in MODES:
        raise ValueError("mode must be testing or real")
    rec = {"mode": mode, "by": by, "at": _now()}
    with lock_for(_mode_path(plane)):
        write_json_atomic(_mode_path(plane), rec)
    return rec


def mode_env(base: dict, mode: str, tier: str, alt: bool = False) -> dict | None:
    """The settings one call uses for `tier` in `mode`; None when the mode has no alternate for that tier."""
    env, T = dict(base), tier.upper()
    spec = (modes()["modes"].get(mode) or {}).get(tier)
    if spec:
        if alt and not spec.get("alt"):
            return None
        env[f"SH_MODEL_{T}_PROVIDER"], env[f"SH_MODEL_{T}"] = spec["provider"], spec["alt"] if alt else spec["model"]
    elif alt:
        if not (base.get(f"SH_MODEL_{T}_ALT") or "").strip():
            return None
        env[f"SH_MODEL_{T}"] = base[f"SH_MODEL_{T}_ALT"]
    return env


# ---- the cost log ------------------------------------------------------------------------------------------------------

def price_of(model: str | None, tier: str | None = None) -> tuple[dict | None, bool]:
    """({in, out} USD per million tokens, estimated). RC-5: a model missing from the list is priced at its tier's default and marked
    estimated, so no call goes unbilled; None only when neither is known."""
    m = modes()
    p = (m.get("prices") or {}).get(model or "")
    if p:
        return p, bool(p.get("estimated"))
    t = (m.get("tier_prices") or {}).get(tier or "")
    return (t, True) if t else (None, False)


def price_usd(model: str | None, tokens_in, tokens_out, tier: str | None = None) -> float | None:
    """INT3: the call's cost from the price table in model_modes.yaml (USD per million tokens); the tier default for an unlisted model."""
    p, _ = price_of(model, tier)
    if not p:
        return None
    return round(((tokens_in or 0) * p["in"] + (tokens_out or 0) * p["out"]) / 1e6, 6)


def log_cost(plane, row: dict) -> None:
    path = plane.area("context") / COST_LOG
    try:
        with lock_for(path), open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        log.warning("the cost log could not be written")


def costs(plane, intent_id: str | None = None) -> dict:
    rows = []
    try:
        for line in (plane.area("context") / COST_LOG).read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and (not intent_id or r.get("intent_id") == intent_id):
                rows.append(r)
    except OSError:
        pass
    tokens = lambda r: (r.get("tokens_in") or 0) + (r.get("tokens_out") or 0)  # noqa: E731
    total = sum(tokens(r) for r in rows)
    by_tier = {t: sum(tokens(r) for r in rows if r.get("tier") == t) for t in TIERS}
    priced = [r["cost_usd"] for r in rows if isinstance(r.get("cost_usd"), (int, float))]
    ms = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))]
    return {"cost_usd": round(sum(priced), 6) if priced else None, "priced_all": len(priced) == len(rows),
            "avg_latency_ms": round(sum(ms) / len(ms)) if ms else None, "intent_id": intent_id, "calls": len(rows), "tokens": total, "by_tier": by_tier,
            "fast_share": round(100 * by_tier["fast"] / total) if total else 0,
            "estimated": any(r.get("estimated") for r in rows), "rows": rows[-50:]}


# ---- the routed model --------------------------------------------------------------------------------------------------

def _unusable(messages: list, reply, want_json: bool) -> str | None:
    text = (getattr(reply, "text", "") or "").strip()
    if getattr(reply, "tool_calls", None):
        return None  # a tool step: the loop goes on
    if not text:
        return "empty"
    if want_json:
        a, b = text.find("{"), text.rfind("}")
        try:
            json.loads(text[a:b + 1] if 0 <= a < b else "")
        except ValueError:
            return "not_json"
    try:  # the reply guard run_agent applies: the recorded facts plus this run's tool figures
        first = json.loads(messages[1]["content"])
        ctx = first.get("context")
        facts = list(ctx.get("facts") or []) if isinstance(ctx, dict) else None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        facts = None
    if facts is None:
        return None  # a context of plain lines: the engine's own check decides
    for m in messages:
        if m.get("role") == "tool" and not str(m.get("content", "")).startswith(OUTSIDE_MARKER):
            try:
                _figures(str(m.get("name") or ""), json.loads(m["content"]), facts)
            except ValueError:
                pass
    return "number_guard" if check_numbers(text, facts, str(first.get("question") or "")).replaced else None


class RoutedModel:
    """`complete()` like an EgressModelClient, but the model is picked per call from the tier and the company's current mode."""

    def __init__(self, base, plane, agent: str, task: str, tier: str, intent_id: str = "", want_json: bool = False, build=None):
        self.base, self.plane, self.agent, self.task, self.tier = base, plane, canonical_agent(agent), task, tier
        self.intent_id, self.want_json = intent_id, want_json
        self.build = build or self._build
        self.module_id, self._named, self.refused = "", False, {}  # refused: provider host -> code, for this call
        self.attempts: list[dict] = []  # the model calls of the latest complete(): the loop's per-step trace reads them

    def _build(self, mode: str, tier: str, alt: bool):
        env = mode_env(self.base.route_env, mode, tier, alt)
        try:
            return build_model_client(self.plane, env, tier) if env is not None else None
        except ProviderError:
            log.warning("the %s model setting is not valid", tier)
            return None

    def _register_names(self) -> None:
        """ER-02: the company's own names (entities, portfolios, funds, managers, people) are in the vault before any call leaves. NM1: done
        once, just before the first call that can leave (a walk where every provider refuses never pays for it)."""
        if self._named:
            return
        self._named = True
        try:
            from sh_platform.build.agents.runtime import register_company_names
            register_company_names(self.plane)
        except Exception:  # noqa: BLE001 - registration never stops a call; the gateway still refuses an unmasked registered name
            log.warning("the company names could not be registered", exc_info=True)

    def _model_name(self, mode: str, tier: str) -> str | None:
        """RC2-2: the model id `tier` uses in `mode` (None for a test's injected client: no settings to read)."""
        base_env = getattr(self.base, "route_env", None)
        env = mode_env(base_env, mode, tier) if base_env is not None else None
        return (env.get(f"SH_MODEL_{tier.upper()}") or None) if env else None

    def _host(self, mode: str, tier: str, alt: bool) -> str | None:
        base_env = getattr(self.base, "route_env", None)  # a test's injected `build` has a bare base: no provider to name
        env = mode_env(base_env, mode, tier, alt) if base_env is not None else None
        try:
            choice = select_provider(env, tier) if env is not None else None
        except ProviderError:
            return None
        return choice.adapter.host if choice else None

    def _down(self, mode: str, tier: str, alt: bool) -> str | None:
        """NM1: the refusal code when the provider this call would use has refused for credit or key (here, or in the gateway's breaker window):
        no client is built and nothing is prepared or sent, so one refusal ends the walk for that provider."""
        host = self._host(mode, tier, alt)
        return (self.refused.get(host) or provider_down(host)) if host else None

    def _log(self, mode, tier, client, reply, messages, step, ok, ms: int | None = None) -> None:
        used = getattr(reply, "usage", None) if reply is not None else None
        est = not used
        if est:
            sent = sum(len(str(m.get("content") or "")) for m in messages)
            used = {"tokens_in": sent // 4, "tokens_out": len(getattr(reply, "text", "") or "") // 4 if reply is not None else 0}
        model = getattr(client, "model_id", None)
        price_est = False
        if reply is None:
            used, usd = {"tokens_in": 0, "tokens_out": 0}, 0.0  # no reply, no bill (a refused or failed call sent nothing billable)
        else:
            usd = price_usd(model, used.get("tokens_in"), used.get("tokens_out"), tier)
            price_est = price_of(model, tier)[1]
        # RC-7: every attempt with its model, mode and outcome ("ok", "empty", "number_guard", "vault_name", "transport_failed", ...)
        self.attempts.append({"tier": tier, "model": model, "mode": mode, "step": step, "tokens_in": used.get("tokens_in"),
                              "tokens_out": used.get("tokens_out"), "ok": ok, "cost_usd": usd, "estimated": est or price_est, "ms": ms})
        if client is not None:
            self.attempts[-1]["masked"] = last_masked()  # TS1c-05: names the gateway swapped for tokens in this call (a count)
        log_cost(self.plane, {"at": _now(), "agent": self.agent or self.module_id, "task": self.task, "tier": tier,
                              "model": model, "tokens_in": used.get("tokens_in"),
                              "tokens_out": used.get("tokens_out"), "retried": step != "first", "intent_id": self.intent_id,
                              "estimated": est, "price_estimated": price_est, "mode": mode, "step": step, "ok": ok, "cost_usd": usd,
                              "latency_ms": ms})

    def complete(self, module_id, messages, tools=None, suppressed=None):
        if over_cap(self.plane.area("context") / COST_LOG):  # the day's model allowance is used up: nothing is sent, the agents carry on by rules
            raise EgressBlocked("daily_cap")
        mode, self.module_id = mode_of(self.plane)["mode"], module_id
        self.attempts = []
        tier, step, alt, bumped, tries = self.tier, "first", False, False, 0
        best, again, down, got = None, False, False, False  # best reply so far; first tier asked again; going down; any reply at all
        timed_out: set = set()  # FIXD: model ids that just failed in transport (a timeout): the next tier is not that same model again
        nxt = lambda t: DOWN[t] if down else UP[t]  # noqa: E731 - once going down for availability, never back up
        while tries < 9:
            if not tier:
                # AQ1 (RC-6/EVT-05): the escalation could not be reached (no credit, provider down). Never drop to the rules for that:
                # hand back the reply already in hand (the loop's guard checks its figures), or ask the first tier once more (an empty
                # reply is usually a passing hiccup of that model).
                if best is not None:
                    return best
                if bumped and got and not again:
                    tier, alt, step, again = self.tier, False, "retry_same", True
                    continue
                if not got and not down and DOWN[self.tier]:
                    # the first tier and every tier above are unreachable (no credit at the provider): the tiers below, one by one
                    # (manager -> specialist -> fast), logged as "fallback_down"; the guard still checks the answer
                    tier, alt, step, down = DOWN[self.tier], False, "fallback_down", True
                    continue
                break
            tries += 1
            if (code := self._down(mode, tier, alt)) is not None:
                self._log(mode, tier, None, None, messages, step, code)
                if alt:
                    tier, alt, step = nxt(tier), False, "fallback_down" if down else "fallback"
                else:
                    alt, step = True, "alt"
                continue
            client = self.build(mode, tier, alt)
            if client is None:  # no alternate for this tier, or no key (the free Google key unset): the next tier up
                if not alt:
                    self._log(mode, tier, None, None, messages, step, "no_key")
                tier, alt, step = nxt(tier), False, "fallback_down" if down else "fallback"
                continue
            if getattr(client, "model_id", None) in timed_out:  # FIXD: the same model, after it timed out, is no other tier: not asked again
                self._log(mode, tier, None, None, messages, step, "same_model_failed")
                tier, alt, step = nxt(tier), False, "fallback_down" if down else "fallback"
                continue
            self._register_names()
            t0 = time.perf_counter()
            try:
                routed = ROUTED.set(True)  # this call's cost row is written below, not by the gateway
                try:
                    reply = client.complete(module_id, messages, tools, suppressed=suppressed)
                finally:
                    ROUTED.reset(routed)
            except EgressBlocked as e:
                if e.reason_code not in PROVIDER_FAILED:  # the gateway refused: no other model changes that. EVT-05: the trace keeps it
                    self._log(mode, tier, client, None, messages, step, e.reason_code, round((time.perf_counter() - t0) * 1000))
                    raise
                self._log(mode, tier, client, None, messages, step, e.reason_code, round((time.perf_counter() - t0) * 1000))
                if e.reason_code == "transport_failed" and getattr(client, "model_id", None):
                    timed_out.add(client.model_id)
                if e.reason_code in BILLING_REFUSED and (host := self._host(mode, tier, alt)):
                    self.refused[host] = e.reason_code  # NM1: no other tier or alternate of this provider is tried
                if alt:
                    tier, alt, step = nxt(tier), False, "fallback_down" if down else "fallback"
                else:
                    alt, step = True, "alt"  # the tier's _ALT model; with none, the next tier up
                continue
            got = True
            bad = _unusable(messages, reply, self.want_json)
            self._log(mode, tier, client, reply, messages, step, bad or "ok", round((time.perf_counter() - t0) * 1000))
            if bad and bad != "empty" and best is None:
                best = reply  # usable text that failed one check: kept in case the stronger model cannot be reached
            if bad and not bumped and UP[tier]:
                same = getattr(client, "model_id", None)
                if same and self._model_name(mode, UP[tier]) == same:
                    # RC2-2: the tier above is this very model: asking it again is not an escalation. Said on the attempt; no paid retry
                    self.attempts[-1]["note"] = "no stronger model in this mode"
                    tier, bumped = None, True  # the reply in hand is returned (an empty one is asked once more on its own tier)
                    continue
                tier, alt, step, bumped = UP[tier], False, "retry_up", True
                continue
            if bad == "empty" and best is not None:
                return best
            if bad == "empty" and step == "retry_same" and tier != "fast":
                # the same model was empty twice (a long context it spends on its own thinking): one try on the fast model, which
                # answers short, rather than no answer at all
                tier, alt, step = "fast", False, "fallback_down"
                continue
            return reply
        raise EgressBlocked(self._why_none())

    def _why_none(self) -> str:
        """TAQ-S2: the refusal when no model answered: the most telling provider failure of this call's attempts ("no_key" is no_credential)."""
        seen = {"no_credential" if a.get("ok") == "no_key" else a.get("ok") for a in self.attempts}
        return next((c for c in PROVIDER_FAILED if c in seen), "transport_failed")


def route(model, agent: str, task: str, intent_id: str = "", plane=None, want_json: bool = False, **signals):
    """The model for one engine call (one additive line at each call site). None stays None (the rule-based fallback runs)."""
    base = getattr(model, "base", model)
    if base is None or not router_on() or getattr(base, "route_env", None) is None:
        return base  # off, no model, or a test stub / injected client: unchanged
    plane = plane or base.gateway.vault.plane
    agent = canonical_agent(agent)
    return RoutedModel(base, plane, agent, task, pick_tier(agent, task, signals), intent_id, want_json)
