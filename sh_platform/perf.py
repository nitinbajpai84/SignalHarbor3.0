"""A tiny request timer: any route slower than SLOW_MS is logged at WARNING with the route and the time."""
import logging
import os
import threading
import time
from pathlib import Path

import yaml
from fastapi import FastAPI, Request

log = logging.getLogger(__name__)
SLOW_MS = 500


def _use_libyaml() -> None:
    """PyYAML's pure-Python parser takes 100-250 ms on one pack section; libyaml (same safe rules) takes about a tenth of that.
    Every `yaml.safe_load` in the product goes through here once, so no caller changes."""
    if getattr(yaml, "__with_libyaml__", False) and not getattr(yaml.safe_load, "_fast", False):
        def safe_load(stream):
            return yaml.load(stream, Loader=yaml.CSafeLoader)
        safe_load._fast = True
        yaml.safe_load = safe_load


def install_timer(app: FastAPI) -> None:
    _use_libyaml()
    @app.middleware("http")
    async def _timer(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        if ms > SLOW_MS:
            route = getattr(request.scope.get("route"), "path", None) or request.url.path
            log.warning("slow route %s %s took %.0f ms", request.method, route, ms)
        return response


_cache: dict[tuple, object] = {}  # ponytail: one entry per (company, name, viewer); a changed file replaces it, never grows with versions
_lock = threading.Lock()


def _stamp(files, ignore=()) -> tuple:
    """(path, mtime_ns, size) of every file the work reads; a directory counts all files under it; a missing file is None.
    `ignore`: names of files (or folders) under them that the work itself writes, so its own write does not undo the cache."""
    out: list = []

    def walk(d: str) -> None:
        try:
            with os.scandir(d) as it:
                for e in sorted(it, key=lambda e: e.name):
                    if e.name in ignore:
                        continue
                    if e.is_dir():
                        walk(e.path)
                    else:
                        st = e.stat()
                        out.append((e.path, st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((d, None, None))
    for f in files:
        f = Path(f)
        if f.is_dir():
            walk(str(f))
        else:
            try:
                st = f.stat()
                out.append((str(f), st.st_mtime_ns, st.st_size))
            except OSError:
                out.append((str(f), None, None))
    return tuple(out)


def cached(plane, name: str, files, fn, viewer=None, ignore=()):
    """Run fn() once per plane (company) and per viewer; serve the stored result until any file in `files` changes.
    Pass `viewer` whenever the result depends on who is asking (a tuple may add the date or any other input). `files=[plane.root]` means "anything in
    this company changed". Treat the result as read-only. Slow reads call this instead of recomputing."""
    key = (str(plane.root), name, viewer)
    stamp = _stamp(files, ignore)
    with _lock:
        hit = _cache.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (stamp, value)
    return value
