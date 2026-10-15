"""Model provider adapters (A-017): the gateway's own JSON envelope <-> a provider's wire format.

The adapter sits BEHIND the gateway as its model transport. By the time it runs, the gateway has already
checked the structure, tokenised every string (D-007), run the vault and figure checks on the final body and
written the log line. The adapter only re-shapes that payload (and the reply back); it adds no content, keeps
no copy, and the vault check runs once more on the body it builds. Internet stays off (D-006): the only host
this transport can reach is the chosen provider's, and the key is attached only for that host.

Settings (names only; values are never printed, logged or returned):
  SH_MODEL_PROVIDER   gemini | openrouter | off           (default: whichever key exists, Gemini first)
  SH_MODEL_NAME       one model id for every tier
  SH_MODEL_<TIER>     per tier (MANAGER, SPECIALIST, FAST); wins over SH_MODEL_NAME
  SH_MODEL_<TIER>_PROVIDER  per tier provider (R1b); wins over SH_MODEL_PROVIDER, except that SH_MODEL_PROVIDER=off stays off
  GOOGLE_API_KEY / OPENROUTER_API_KEY   read by name at call time by the transport, nowhere else
"""
import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urlsplit

from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import MODEL_TRIES, EgressGateway, make_httpx_transport
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.providers.openrouter import OpenRouterAdapter
from sh_platform.egress.vault import NameVault
from sh_platform.plane import CompanyPlane

ADAPTERS = {a.name: a for a in (GeminiAdapter(), OpenRouterAdapter())}
KEY_ORDER = ("gemini", "openrouter")  # the default when several keys exist (the earlier product's choice)
TIERS = ("manager", "specialist", "fast")
OFF = "off"  # SH_MODEL_PROVIDER=off: model calls are switched off


class ProviderError(ValueError):
    """A setting names something that does not exist. The message says what to fix and never holds a key."""


@dataclass(frozen=True)
class Choice:
    adapter: GeminiAdapter | OpenRouterAdapter
    model: str


def select_provider(env: Mapping[str, str] | None = None, tier: str = "specialist") -> Choice | None:
    """The provider and model for a tier, or None when no key is set up (the caller degrades honestly)."""
    env = os.environ if env is None else env
    if tier not in TIERS:
        raise ProviderError("Unknown model tier.")
    name = (env.get("SH_MODEL_PROVIDER") or "").strip().lower()
    if name == OFF:
        return None  # the explicit switch: no model call from anywhere
    name = (env.get(f"SH_MODEL_{tier.upper()}_PROVIDER") or "").strip().lower() or name  # R1b: a provider per tier
    if name and name not in ADAPTERS:
        raise ProviderError(f"SH_MODEL_PROVIDER must be one of {sorted(ADAPTERS)}.")
    name = name or next((n for n in KEY_ORDER if (env.get(ADAPTERS[n].key_env) or "").strip()), "")
    if not name or not (env.get(ADAPTERS[name].key_env) or "").strip():  # a blank key is no key
        return None
    adapter = ADAPTERS[name]
    model = (env.get(f"SH_MODEL_{tier.upper()}") or env.get("SH_MODEL_NAME") or dict(adapter.default_models)[tier]).strip()
    if not re.fullmatch(adapter.model_id, model) or ".." in model:
        raise ProviderError("The model name in the settings is not a valid model id.")
    return Choice(adapter, model)


def key_status(env: Mapping[str, str] | None = None) -> dict:
    """For the doctor: which provider would be used and the NAME of its key variable. Never a value."""
    env = os.environ if env is None else env
    try:
        choice = select_provider(env)
    except ProviderError as e:
        return {"provider": None, "key_env": None, "model": None, "problem": str(e), "off": False}
    off = (env.get("SH_MODEL_PROVIDER") or "").strip().lower() == OFF
    keys = {n: a.key_env for n, a in ADAPTERS.items()}
    return {"provider": choice.adapter.name if choice else None, "model": choice.model if choice else None,
            "key_env": choice.adapter.key_env if choice else None, "known_keys": keys, "problem": None, "off": off}


def usage(raw: str) -> dict | None:
    """{tokens_in, tokens_out} from the provider's own usage field (OpenRouter `usage`, Gemini `usageMetadata`), else None."""
    try:
        d = json.loads(raw)
        u = d.get("usage") or {}
        g = d.get("usageMetadata") or {}
        got = (u.get("prompt_tokens"), u.get("completion_tokens")) if u else (g.get("promptTokenCount"), g.get("candidatesTokenCount"))
    except (ValueError, AttributeError):
        return None
    return {"tokens_in": got[0], "tokens_out": got[1] or 0} if isinstance(got[0], int) else None


def model_transport(choice: Choice, *, client=None, final_check: Callable[[str], bool] | None = None,
                    timeout: float = 60.0, env: Mapping[str, str] | None = None):
    """The gateway's model transport for one provider. `client` is an httpx client (tests pass a MockTransport
    one). `final_check(text) -> True` refuses a final body that still holds a protected name. `env` is where the
    key is read from (default: the process environment): the same mapping the provider was chosen from."""
    a = choice.adapter
    send = make_httpx_transport(a.key_env, a.header, a.scheme, client=client, timeout=timeout, model_hosts=[a.host],
                               env=env, tries=MODEL_TRIES)

    def transport(url: str, body: bytes) -> str:
        if (urlsplit(url).hostname or "").lower() != a.host:
            raise EgressBlocked("destination_not_allowed")
        envelope = json.loads(body)  # the gateway's own, already guarded JSON; only messages and tools are mapped
        path, wire = a.format_request(choice.model, envelope.get("messages", []), envelope.get("tools"))
        wire_bytes = json.dumps(wire, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if final_check is not None and final_check(wire_bytes.decode("utf-8")):
            raise EgressBlocked("vault_name")
        raw = send(f"https://{a.host}{path}", wire_bytes)
        text, calls = a.parse_reply(raw)
        used = usage(raw)
        return json.dumps({"text": text, "model": choice.model, "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments}
                                                        for c in calls], **({"usage": used} if used else {})})
    return transport


def build_model_client(plane: CompanyPlane, env: Mapping[str, str] | None = None, tier: str = "specialist",
                       client=None) -> EgressModelClient | None:
    """A model client for one company: its own vault, policy and log. None when no key is set up.
    With no env given it reads the model settings the way the server does (.env plus the process environment), so a caller that
    does not pass the server's client still gets the model instead of a silent rules-only fallback."""
    if env is None:
        from sh_platform.settings import load_model_env
        env = load_model_env()
    choice = select_provider(env, tier)
    if choice is None:
        return None
    vault = NameVault(plane)
    gateway = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=[choice.adapter.host],
                            model_url=f"https://{choice.adapter.host}",
                            transport=model_transport(choice, client=client, final_check=vault.contains_name, env=env))
    model = EgressModelClient(gateway)
    model.model_id = choice.model  # for the router's cost log (a name, never a key)
    if client is None:
        model.route_env = dict(env)  # R1: the router rebuilds per tier and mode from the same settings; never on an injected test client
    return model
