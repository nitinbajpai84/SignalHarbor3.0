"""QP: the nine read routes answer fast, a GET never rebuilds the graph on its own thread, and the per-viewer graph cache keeps viewers apart.
Runs on the smoke fixtures (the seeded synthetic companies)."""
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest

SMOKE = Path(__file__).resolve().parents[1] / "smoke"
sys.path.insert(0, str(SMOKE))  # smoke_helpers
_spec = importlib.util.spec_from_file_location("smoke_conftest_for_perf", SMOKE / "conftest.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
seeded, env, no_network = _mod.seeded, _mod.env, _mod.no_network  # the smoke fixtures, reused as they are

from smoke_helpers import PEOPLE  # noqa: E402

LIMIT_MS = 300


def _admin(env):
    p = next(x for x in PEOPLE if x["company"] == "harbor-mutual" and "company_admin" in x["roles"])
    return env.login(p["email"]), p["company"]


def test_nine_routes_under_300_ms(env):
    c, _ = _admin(env)
    nodes = c.get("/api/company/graph?view=map").json()["nodes"]
    node = next((n["id"] for n in nodes if n["type"] == "Measure"), "measure:none")
    urls = ["/api/pulse", "/api/company/graph?view=map", f"/api/company/graph/node/{node}", "/api/company/feeds", "/api/company/feeds/K02",
            "/api/company/build/home", "/api/company/build/ops", "/api/company/register", "/api/company/market"]
    for u in urls:
        c.get(u)  # warm: imports and file caches, as a running server has them
        t = time.perf_counter()
        r = c.get(u)
        ms = (time.perf_counter() - t) * 1000
        assert r.status_code in (200, 404) and ms < LIMIT_MS, f"{u}: {r.status_code} in {ms:.0f} ms"


def test_non_waiting_read_never_rebuilds_on_the_request_thread(env, monkeypatch):
    """The opt-in `wait=False` read: the rebuild runs on its own thread and the current file is served. (The graph routes keep wait=True: see hooks.)"""
    from sh_platform.graph import build as graph_build
    from sh_platform.graph import hooks
    c, company = _admin(env)
    assert c.get("/api/company/graph?view=map").status_code == 200  # no graph yet: the first read builds it
    plane = env.planes.plane_for(company)
    hooks.mark_dirty(plane)
    seen: list[str] = []
    done = threading.Event()
    real = graph_build.rebuild

    def spy(p):
        seen.append(threading.current_thread().name)
        real(p)
        done.set()
    monkeypatch.setattr(graph_build, "rebuild", spy)
    assert hooks.rebuild_if_dirty(plane, wait=False) is False
    assert done.wait(10), "the background rebuild never ran"
    assert seen == ["graph-rebuild"], seen  # not the request thread
    assert not hooks._flag(plane).exists()


def test_graph_cache_keeps_viewers_apart(env):
    from sh_platform.graph import read
    from sh_platform.profile.view import Viewer
    c, company = _admin(env)
    plane = env.planes.plane_for(company)
    node = {"id": "measure:secret", "type": "Measure", "label": "Secret"}
    doc = {"version": 1, "built_at": "2026-01-01T00:00:00Z", "nodes": [node, {"id": "measure:open", "type": "Measure", "label": "Open"}], "edges": []}
    node["restricted_to"] = ["someone else"]  # the first node is shut to everyone but a named person
    node["restricted_bound"] = {}
    plane.path("graph", "company.json").write_text(json.dumps(doc), encoding="utf-8")
    nobody = Viewer(name="Nobody", roles=frozenset({"participant"}))
    other = Viewer(name="Other", roles=frozenset({"participant"}))
    first = read.graph_for(plane, nobody)
    assert node["id"] not in {n["id"] for n in first["nodes"]}  # a silhouette for this viewer
    named = Viewer(name="Someone Else", roles=frozenset({"participant"}))
    allowed = read.graph_for(plane, named)
    assert allowed is not first and node["id"] in {n["id"] for n in allowed["nodes"]}  # same file version, other viewer: not served the first one
    assert read.graph_for(plane, nobody) is first  # the same viewer does hit the cache
    assert read.graph_for(plane, other) is not first


def test_cached_keys_on_files_company_and_viewer(tmp_path):
    from types import SimpleNamespace
    from sh_platform.perf import cached
    a, b = SimpleNamespace(root=tmp_path / "a"), SimpleNamespace(root=tmp_path / "b")
    f = tmp_path / "f.txt"
    f.write_text("1")
    calls = []

    def fn():
        calls.append(1)
        return len(calls)
    assert cached(a, "k", [f], fn) == cached(a, "k", [f], fn) == 1  # second call served from the store
    assert cached(b, "k", [f], fn) == 2  # another company never shares it
    assert cached(a, "k", [f], fn, viewer="x") == 3 and cached(a, "k", [f], fn, viewer="y") == 4  # nor another viewer
    f.write_text("22")
    assert cached(a, "k", [f], fn) == 5  # a changed file misses


def test_yaml_safe_load_uses_libyaml_and_reads_the_same():
    import yaml
    from fastapi import FastAPI
    from sh_platform.perf import install_timer
    text = "a: [1, 2.5, 'x']\nb: {c: null, d: true}\nwhen: 2026-10-07\n"
    before = yaml.safe_load(text)
    install_timer(FastAPI())
    install_timer(FastAPI())  # twice is harmless
    assert yaml.safe_load(text) == before
    assert getattr(yaml.safe_load, "_fast", False) == getattr(yaml, "__with_libyaml__", False)
