"""Shared pytest settings for the whole repo."""
import os

# Test scratch goes to drive D (C filled up on 9 Oct: 46 GB of pytest temp folders). Override with PYTEST_DEBUG_TEMPROOT.
if os.path.isdir("D:/Temp"):
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", "D:/Temp")


def pytest_make_parametrize_id(config, val, argname):
    """Binary test inputs are named by their length, not their bytes: zips built at collection time carry the clock,
    which gives each parallel worker a different test name."""
    if isinstance(val, (bytes, bytearray)):
        return f"{argname}{len(val)}b"
    return None


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_embedding_model(monkeypatch):
    """Tests never load the real embedding model (search falls back to words) and embedding jobs run inline; test_vectors.py installs its own stub."""
    from sh_platform.v1 import doc_embed, doc_index

    def off(texts, query=False):
        raise doc_embed.Unavailable("off in tests")
    monkeypatch.setattr(doc_embed, "embed", off)
    monkeypatch.setattr(doc_index, "_submit", lambda fn, *a: fn(*a))  # no background embedding job outlives the test
