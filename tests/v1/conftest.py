import copy
import os
import shutil
import tempfile
from pathlib import Path

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


def pytest_configure(config):
    """Seed the demo data root once per run (tools/seed_v1.py into a temp folder) and name it in SH_TEST_SEED_ROOT. The xdist workers
    inherit the variable from the controller; a worker started without it seeds its own. The repo's data/ is never read or written."""
    if os.environ.get("SH_TEST_SEED_ROOT"):
        return
    from tools import seed_v1
    base = Path(tempfile.mkdtemp(prefix="sh-seed-", dir=os.environ.get("PYTEST_DEBUG_TEMPROOT")))
    seed_v1.seed_all(base / "data")
    os.environ["SH_TEST_SEED_ROOT"] = str(base / "data")
    config._sh_seed_base = base


def pytest_unconfigure(config):
    base = getattr(config, "_sh_seed_base", None)
    if base:
        shutil.rmtree(base, ignore_errors=True)
        os.environ.pop("SH_TEST_SEED_ROOT", None)
