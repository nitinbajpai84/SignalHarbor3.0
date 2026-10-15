"""V5W-7 fast, cheap replies for every agent chat.

The classifier picks one of five routes for a message, cheapest first:
  fixed   greetings, thanks, help, who-are-you: a written reply per agent, no model.
  cache   the same question (normalised) with the same data version and the same access scope, answered before.
  figure  a data question whose recorded facts already hold the figure: the program states it, no model.
  fast    a short lookup: the router's fast tier.
  strong  anything else (long, analytic, a change, files): the router's usual tier.
Rules decide first; the Jev client (SH_JEV_API_KEY set, and not wired live until it goes through platform/egress) only breaks the tie for a question the rules cannot place, sees the question
with its digits and addresses masked and cut short, and can only answer fast or strong. Never fixed, cache or figure: those stay code.

Hooks: `begin()`/`Pending.store()` in agents/loop.run_agent (every agent goes through it), `tier_for()` in v1/router.ambiguous, and
`ChatStreamMiddleware` (a client that sends `Accept: text/event-stream` gets the same JSON as server-sent events; any other client
is untouched). The guard, the egress gateway and the entitlement check all still run: a fixed or cached reply is only served when the
module is enabled for the company, a cached reply was checked by the number guard when it was made, and the cache key holds the access scope.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from sh_platform import mode as _mode
from sh_platform.state import kv

log = logging.getLogger(__name__)

KINDS = ("fixed", "cache", "figure", "fast", "strong")
CACHE_MAX, CACHE_TTL_S = 400, 15 * 60
JEV_CONFIDENCE = 0.6
STREAM_PATH = re.compile(r"^/api/v1/.+/(chat|ask)$")

# ---- fixed replies (plain words; no figures, so nothing for the guard to check) ------------------------------------------------
ROLES = {
    "north": "the industry expert. I help you say what you want from your data and write it up as an intent of work",
    "span": "the architect. I turn a signed intent of work into a design for your data and check it with you",
    "lumen": "the analyst. I help you read your figures and build dashboards from them",
    "flow": "the data engineer. I build and run the pipelines that bring your data in",
    "tally": "the finance checker. I look at cases and breaks and explain what they show",
}
HELP = {
    "north": "Tell me what you want to know or decide, or drop in a file, and I will draft it with you.",
    "span": "Ask about the design, the tables or the plan, or tell me what to change and I will suggest it.",
    "lumen": "Ask about a figure or a dashboard, or say what you want to see and I will suggest a tile.",
    "flow": "Ask about a pipeline or a run, or say what should change and I will suggest it.",
    "tally": "Ask about a case, a break or a total, and I will explain what the records show.",
}
_NAMES = "(?:" + "|".join(ROLES) + ")"
_TAIL = rf"(?: there| {_NAMES})?"
FIXED_RULES = (
    ("greeting", re.compile(rf"(?:hi|hello|hey|hiya|howdy|yo|greetings|good (?:morning|afternoon|evening|day)){_TAIL}")),
    ("thanks", re.compile(rf"(?:thanks|thank you|thx|cheers|ta|many thanks|thanks a lot|thanks so much|thank you (?:so|very) much|much appreciated){_TAIL}")),
    ("help", re.compile(r"(?:help|help me|what can you do|what do you do|how can you help(?: me)?|how do you work|what can i ask(?: you)?|what can i do here)")),
    ("who", re.compile(r"(?:who are you|what are you|who is this|what is your name|what s your name|whats your name|are you (?:an? )?(?:ai|bot|robot|human|real))")),
)


def normalise(text) -> str:
    """Lower case, words only, one space: 'What is the NAV?!' and 'what is the nav' are the same question."""
    return " ".join(re.sub(r"[^a-z0-9%.]+", " ", str(text or "").lower().replace("'", " ")).replace(". ", " ").strip(" .").split())


def fixed_reply(agent: str, text: str) -> str | None:
    a, q = str(agent or "").lower(), normalise(text)
    if a not in ROLES or not q or len(q) > 60:
        return None
    for kind, rx in FIXED_RULES:
        if rx.fullmatch(q):
            name = a.capitalize()
            return {"greeting": f"Hello. I am {name}, {ROLES[a]}. {HELP[a]}",
                    "thanks": "You are welcome. Ask me anything else when you are ready.",
                    "help": f"I am {name}, {ROLES[a]}. {HELP[a]}",
                    "who": f"I am {name}, {ROLES[a]}. I am an AI assistant, and I only use what your company's records show."}[kind]
    return None


# ---- the tier ---------------------------------------------------------------------------------------------------------------
_STRONG = re.compile(r"\b(why|explain|compare|recommend|draft|design|plan|reconcile|analy[sz]e|forecast|should|propose|build|change|create|write|"
                     r"summari[sz]e|improve|fix|add|remove|rename|update|because|and then)\b", re.I)
_LOOKUP = re.compile(r"^(what|how many|how much|show|list|which|when|who|where|is|are|do|does|has|have)\b", re.I)
_FOLLOW_UP = re.compile(r"^(and|also|but|so|then|what about|how about|those|that|it|they|them|this|these|the same|same)\b")


def rules_tier(text: str, files: bool = False) -> str | None:
    """'fast' | 'strong' | None (the rules cannot place it)."""
    t = str(text or "")
    words = len(t.split())
    if files or words > 30 or _STRONG.search(t):
        return "strong"
    if words <= 14 and _LOOKUP.search(t.strip()):
        return "fast"
    return None


def _mask(text: str) -> str:
    t = re.sub(r"\S+@\S+", "x", str(text))
    return re.sub(r"\d", "#", t)[:200]


def jev_key() -> str:
    """SH_JEV_API_KEY from the process or .env; never printed or logged."""
    if os.environ.get("SH_JEV_API_KEY"):
        return os.environ["SH_JEV_API_KEY"].strip()
    from sh_platform.settings import _read_env_file
    return _read_env_file(Path(".env"), lambda n: n == "SH_JEV_API_KEY").get("SH_JEV_API_KEY", "")


_JEV_SEEN: OrderedDict = OrderedDict()  # normalised question -> verdict, so a repeated question never asks twice


def jev_tier(text: str, client=None) -> str | None:
    """Ask Jev only: is this a quick lookup (fast) or work that needs the stronger model (strong)? None when no key, an error or low confidence."""
    key = normalise(text)
    if key in _JEV_SEEN:
        return _JEV_SEEN[key]
    own, verdict = client is None, None
    try:
        if own:
            k = jev_key()
            if not k:
                return None
            from typesafe_sdk import TypeSafeClient
            client = TypeSafeClient(api_key=k, timeout=3.0)
        from typesafe_sdk import Choice
        q = {"tier": Choice(instructions="Is `question` a quick lookup of one fact (fast) or work that needs careful reasoning, a change or a long answer (strong)?",
                            criteria={"fast": {"what": "one fact or a short list read back from records", "examples": ["what is the cash balance", "list the open cases"]},
                                      "strong": {"what": "analysis, a recommendation, a draft or a change", "examples": ["why did returns fall", "draft a plan for the pipeline"]},
                                      "other": None})}
        r = client.system_one(state={"question": _mask(text)}, questions=q).choices["tier"]
        verdict = r.choice if r.choice in ("fast", "strong") and r.confidence >= JEV_CONFIDENCE else None
    except Exception as e:  # noqa: BLE001 - Jev down or slow: the rules' default stands
        log.warning("Jev tier skipped: %s", type(e).__name__)
        return None
    finally:
        if own and client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
    _JEV_SEEN[key] = verdict
    while len(_JEV_SEEN) > 500:
        _JEV_SEEN.popitem(last=False)
    return verdict


_FLUFF = frozenset("many much there number count currently current today please right".split())  # question words that carry no subject


# ---- the figure from recorded facts -----------------------------------------------------------------------------------------
def figure_answer(text: str, facts) -> str | None:
    """A data question whose answer is one recorded figure: every content word of the question is in that fact's label, and only one
    fact fits. The figure is the record's own, so the guard passes it. Anything less certain goes to the model."""
    from sh_platform.agents.groups import group_ok, is_figure
    from sh_platform.agents.loop import _words, is_data_question
    if not is_data_question(text):
        return None
    want = _words(text) - _FLUFF
    found = {}
    for f in facts or []:
        if (isinstance(f, dict) and group_ok(f.get("group_size")) and f.get("label") not in (None, "", "text")
                and is_figure("value", f.get("value")) and want and want <= _words(f.get("label"))):
            found[(str(f["label"]), str(f["value"]))] = f
    if len(found) != 1:
        return None
    (label, value), f = next(iter(found.items()))
    return f"{label}: {value}{(' ' + str(f['unit'])) if isinstance(f.get('unit'), str) and f['unit'] else ''}."


@dataclass
class Route:
    kind: str
    reply: str | None = None
    by: str = "rules"


def classify(agent: str, text: str, *, facts=None, cached: bool = False, files: bool = False, use_jev: bool = True, jev=None) -> Route:
    fx = fixed_reply(agent, text)
    if fx:
        return Route("fixed", fx)
    if cached:
        return Route("cache")
    fig = figure_answer(text, facts)
    if fig:
        return Route("figure", fig)
    t = rules_tier(text, files)
    if t:
        return Route(t)
    v = (jev or jev_tier)(text) if use_jev else None
    return Route(v or "strong", by="Jev" if v else "rules")


def tier_for(text: str, files: bool = False) -> str | None:
    """The router's hook: 'fast' when the question is a short lookup, else None (the router keeps its own default)."""
    # Review V5W-7: rules only. A direct Jev call would send the person's words (names not tokenised) past platform/egress, the
    # only exit (.claude/rules/egress.md). Wire `use_jev=True` back once Jev goes through the gateway: allowlisted host, vault check, log.
    r = classify("", text, files=files, use_jev=False)
    return "fast" if r.kind == "fast" else None


# ---- the answer cache -------------------------------------------------------------------------------------------------------
_LOCK = threading.Lock()
_CACHE: OrderedDict = OrderedDict()
_BUMPS: dict[str, int] = {}


def reset() -> None:
    with _LOCK:
        _CACHE.clear()
        _BUMPS.clear()
    if _mode.production():
        kv.cache_clear()
    _JEV_SEEN.clear()


def bump(company_id: str) -> None:
    """New data or a pipeline run: every cached answer of the company is stale. (The file fingerprint below also catches this.)"""
    if _mode.production():  # W3: the counter is shared, so a worker's pipeline run stales the web replicas' cache too
        kv.redis_client().incr(f"sh:bump:{company_id}")
        return
    with _LOCK:
        _BUMPS[company_id] = _BUMPS.get(company_id, 0) + 1


def data_version(company_id: str) -> str:
    """A counter plus the size and time of the warehouse files, the landing folder and the pipeline run logs."""
    parts = [str(kv.redis_client().get(f"sh:bump:{company_id}") or 0) if _mode.production() else str(_BUMPS.get(company_id, 0))]
    try:
        from sh_platform.settings import load_settings
        root = Path(load_settings().data_root) / company_id
        for rel in ("warehouse", "landing"):
            d = root / rel
            if d.is_dir():
                parts.append(f"{rel}:{d.stat().st_mtime_ns}")
                for e in sorted(os.scandir(d), key=lambda e: e.name):
                    if e.is_file():
                        s = e.stat()
                        parts.append(f"{e.name}:{s.st_mtime_ns}:{s.st_size}")
        for log_file in sorted((root / "build").glob("*/runs.jsonl")) if (root / "build").is_dir() else []:
            s = log_file.stat()
            parts.append(f"{log_file.parent.name}:{s.st_mtime_ns}:{s.st_size}")
    except OSError:
        parts.append("unreadable")  # a changing unknown never serves an old answer: the stamp below still moves with the clock bucket
        parts.append(str(int(time.time() // 5)))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def cache_key(agent, company_id, module_id, scope, question, system_prompt="") -> str:
    raw = "\x1f".join([str(agent).lower(), company_id, module_id, str(scope), data_version(company_id), normalise(question),
                       hashlib.sha256(str(system_prompt).encode()).hexdigest()[:12]])
    return hashlib.sha256(raw.encode()).hexdigest()


def cacheable_question(q: str) -> bool:
    n = normalise(q)
    return len(n.split()) >= 3 and not _FOLLOW_UP.match(n)  # a follow-up depends on the talk before it


def _get(key: str):
    if _mode.production():
        return kv.cache_get(key)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[1] <= CACHE_TTL_S:
            _CACHE.move_to_end(key)
            return hit[0]
        _CACHE.pop(key, None)
    return None


def _put(key: str, text: str) -> None:
    if _mode.production():
        return kv.cache_put(key, text, CACHE_TTL_S)
    with _LOCK:
        _CACHE[key] = (text, time.monotonic())
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)


# ---- the hook in run_agent --------------------------------------------------------------------------------------------------
@dataclass
class Pending:
    """What `begin` hands run_agent: a finished result (`done`), or nothing / a cache slot to fill with `store`."""
    done: object | None = None
    key: str | None = None

    def store(self, res) -> None:
        if (self.key and res.status == "done" and (res.text or "").strip() and not res.numbers_replaced and not res.proposals
                and not res.refusal_reasons):
            _put(self.key, res.text)


def _result(text: str, route: str, t0: float):
    from sh_platform.agents.loop import AgentResult
    return AgentResult(text, "done", steps=0, trace=[{"kind": "fast", "route": route, "ms": int((time.monotonic() - t0) * 1000)}])


def begin(registry, company_id, module_id, agent, system_prompt, context, question, fast=None) -> Pending:
    """Fixed reply, figure from the facts, or a cached answer, before any model call. `fast` = {"scope": "<who may see this>"} opts the
    caller into the cache; fixed replies and figures need no opt-in. Nothing here runs unless the module is enabled for the company."""
    t0 = time.monotonic()
    if isinstance(fast, dict) and fast.get("off"):
        return Pending()  # the evals test the model itself
    try:
        if not registry.is_enabled(company_id, module_id):
            return Pending()  # the loop refuses it in its usual words
        as_json = "JSON" in str(system_prompt)  # a caller that wants JSON gets its reply in the shape it parses
        wrap = (lambda s: json.dumps({"reply": s})) if as_json else (lambda s: s)
        fx = fixed_reply(agent, question)
        if fx:
            return Pending(_result(wrap(fx), "fixed", t0))
        if not as_json:
            fig = figure_answer(question, (context or {}).get("facts") if isinstance(context, dict) else None)
            if fig:
                return Pending(_result(fig, "figure", t0))
        scope = (fast or {}).get("scope") if isinstance(fast, dict) else None
        if scope and not as_json and cacheable_question(question):
            key = cache_key(agent, company_id, module_id, scope, question, system_prompt)
            hit = _get(key)
            if hit:
                return Pending(_result(hit, "cache", t0))
            return Pending(key=key)
    except Exception:  # noqa: BLE001 - the fast path never costs the person their answer: the model runs as before
        log.warning("fast path skipped", exc_info=True)
    return Pending()


# ---- streaming (server-sent events) -----------------------------------------------------------------------------------------
def reply_of(body) -> str:
    if not isinstance(body, dict):
        return ""
    if isinstance(body.get("reply"), str):
        return body["reply"]
    for t in reversed(body.get("turns") or []):
        if isinstance(t, dict) and t.get("by") not in ("person", "you", "user") and isinstance(t.get("text"), str):
            return t["text"]
    return ""


def chunks(text: str, n: int = 3) -> list[str]:
    w = re.findall(r"\S+\s*", text or "")
    return ["".join(w[i:i + n]) for i in range(0, len(w), n)]


def sse(event: str, data) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def wants_stream(scope) -> bool:
    if scope.get("type") != "http" or scope.get("method") != "POST" or not STREAM_PATH.match(scope.get("path", "")):
        return False
    return any(k == b"accept" and b"text/event-stream" in v for k, v in scope.get("headers", []))


class ChatStreamMiddleware:
    """Pure ASGI. A chat POST that asks for text/event-stream is answered in events: `start` at once, `delta` pieces of the reply, then
    `done` with the same JSON the plain route returns (or `error` with its status and message). The inner app, with its sign-in,
    CSRF and seat checks, runs unchanged. Real model token streaming needs a streaming model client (ponytail: the reply is cut into
    pieces once it is whole)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not wants_stream(scope):
            return await self.app(scope, receive, send)
        await send({"type": "http.response.start", "status": 200, "headers": [
            (b"content-type", b"text/event-stream; charset=utf-8"), (b"cache-control", b"no-cache"), (b"x-accel-buffering", b"no")]})
        await send({"type": "http.response.body", "body": sse("start", {}), "more_body": True})
        got = {"status": 500, "body": b""}

        async def capture(msg):
            if msg["type"] == "http.response.start":
                got["status"] = msg["status"]
            elif msg["type"] == "http.response.body":
                got["body"] += msg.get("body", b"")

        try:
            await self.app(scope, receive, capture)
            try:
                body = json.loads(got["body"] or b"{}")
            except ValueError:
                body = {}
            if got["status"] >= 400:
                out = [sse("error", {"status": got["status"], **(body if isinstance(body, dict) else {})})]
            else:
                out = [sse("delta", {"text": c}) for c in chunks(reply_of(body))] + [sse("done", body)]
        except Exception:  # noqa: BLE001
            log.warning("chat stream failed", exc_info=True)
            out = [sse("error", {"status": 500, "message": "Something went wrong. Please try again."})]
        for b in out:
            await send({"type": "http.response.body", "body": b, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
