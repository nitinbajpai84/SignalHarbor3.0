import os
import shutil

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import load_settings

# The live server keeps data/<company>/warehouse/*.duckdb open, so copying the
# demo data folder fails on Windows (Errno 13). Every fixture that copies data/
# goes through shutil.copytree; skip only the files that cannot be read right
# now. Runs in every xdist worker (a patch in the launcher does not).
_copytree = shutil.copytree


def _locked(path: str) -> bool:
    try:
        with open(path, "rb"):
            return False
    except PermissionError:
        return True


def _skip_locked(ignore):
    def _ignore(src, names):
        out = set(ignore(src, names)) if ignore else set()
        return out | {n for n in names if n.endswith((".duckdb", ".duckdb.wal")) and _locked(os.path.join(src, n))}
    return _ignore


def _copytree_skip_locked(src, dst, symlinks=False, ignore=None, *a, **k):
    return _copytree(src, dst, symlinks, _skip_locked(ignore), *a, **k)


shutil.copytree = _copytree_skip_locked


@pytest.fixture
def client(tmp_path) -> TestClient:
    return TestClient(create_app(load_settings({}, env_file=tmp_path / "none.env")))


@pytest.fixture(autouse=True)
def _closed_outage_breaker():
    """CB1's outage breaker is process-wide by design; one test's 402 must not refuse the next test's calls in the same worker."""
    from sh_platform.egress import gateway
    gateway._breaker.clear()
    yield
    gateway._breaker.clear()
