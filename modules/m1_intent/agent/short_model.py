"""A model client for short structured tasks (prefill, the "So that" lines, grouping): the same gateway, vault and
policy as sh_platform.egress.providers.build_model_client, but Gemini gets a small thinking budget so a one-shot
JSON or line reply takes seconds, not a minute. North's conversation keeps Gemini's default. Other providers are
unchanged (they have no such setting)."""
from collections.abc import Mapping
from dataclasses import replace

from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.providers import Choice, model_transport, select_provider
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.vault import NameVault

THINKING_BUDGET = 512  # chosen: enough to follow the instruction, far below the default's thousands of thinking tokens


def build_short_client(plane, env: Mapping[str, str], budget: int = THINKING_BUDGET) -> EgressModelClient | None:
    """None when no key is set up. Raises ProviderError for a bad setting, like build_model_client."""
    choice = select_provider(env)
    if choice is None:
        return None
    if isinstance(choice.adapter, GeminiAdapter):
        choice = Choice(replace(choice.adapter, thinking_budget=budget), choice.model)
    vault = NameVault(plane)
    gateway = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=[choice.adapter.host],
                            model_url=f"https://{choice.adapter.host}",
                            transport=model_transport(choice, final_check=vault.contains_name, env=env))
    return EgressModelClient(gateway)
