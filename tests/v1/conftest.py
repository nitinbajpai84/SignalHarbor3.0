import copy

import pytest

from sh_platform.v1 import router


@pytest.fixture()
def two_provider_testing_mode(monkeypatch):
    """Testing mode with the manager on OpenRouter (the shape before 10 Oct, when Nitin moved every Testing tier to Gemini).
    The cross-provider walk (NM1, H1-01, TAQ-S2) needs two providers to be tested; the shipped yaml is checked in test_router."""
    m = copy.deepcopy(router.modes())
    m["modes"]["testing"]["manager"] = {"provider": "openrouter", "model": "anthropic/claude-sonnet-5.5"}
    m["modes"]["testing"]["fast"] = {"provider": "gemini", "model": "gemini-2.5-flash-lite"}  # since 10 Oct 11:50 the shipped Testing set is OpenRouter only
    m["modes"]["testing"]["specialist"] = {"provider": "gemini", "model": "gemini-2.5-flash"}
    monkeypatch.setattr(router, "modes", lambda: m)
    return m
