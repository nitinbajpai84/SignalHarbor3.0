"""The rebuild hook. A record write calls `mark_dirty(plane)`; whoever reads the graph calls `rebuild_if_dirty(plane)`.

SEAM for the module stores (not wired here, a module package does it): after a module writes its own record (catalogue, glossary, process map,
trial, rules, findings, plan, signature), it calls `from sh_platform.graph.hooks import mark_dirty; mark_dirty(plane)`. Modules may import
the kernel. Only the profile store is wired in this package.
"""
import logging
import threading
from contextlib import suppress

from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)


def _flag(plane: CompanyPlane):
    return plane.path("graph", "dirty")


def mark_dirty(plane: CompanyPlane) -> None:
    """Never raises: a graph that cannot be marked must not undo the record that was just saved."""
    try:
        f = _flag(plane)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("1", encoding="utf-8")
    except OSError:
        log.warning("the company graph could not be marked for a rebuild")


_running: set[str] = set()  # graph files being rebuilt now; one rebuild per company at a time
_lock = threading.Lock()


def _rebuild_now(plane: CompanyPlane) -> None:
    from sh_platform.graph.build import rebuild
    with suppress(FileNotFoundError):
        _flag(plane).unlink()  # cleared first: a write that lands during the build marks it again
    rebuild(plane)


def _background(plane: CompanyPlane) -> None:
    key = str(_flag(plane))
    from sh_platform import mode
    if mode.production():  # W3: a worker rebuilds it; one waiting job per company
        from sh_platform.jobs import handlers as H, queue
        queue().enqueue("graph.rebuild", H.payload_of(plane), key=f"graph.rebuild:{plane.company_id}")
        return
    with _lock:
        if key in _running:
            return
        _running.add(key)

    def run() -> None:
        try:
            _rebuild_now(plane)
        except Exception:  # a failed background build must not kill the thread silently; the flag stays set for the next read
            log.exception("the company graph could not be rebuilt in the background")
            mark_dirty(plane)
        finally:
            with _lock:
                _running.discard(key)
    threading.Thread(target=run, name="graph-rebuild", daemon=True).start()


def rebuild_if_dirty(plane: CompanyPlane, wait: bool = True) -> bool:
    """Rebuilds when a record changed since the last build (or there is no graph yet). True when it rebuilt on the spot.

    wait=False (opt-in, for a read that may serve the current file): with a graph file present, a dirty flag starts a background rebuild and the
    current file is served; the next read gets the fresh one. That serves a stale, possibly more open graph after a restriction is tightened, so
    the graph routes keep wait=True (A-069, tests/graph/test_graph_probe.py). With no graph file yet it always builds on the spot."""
    f = _flag(plane)
    if not f.exists() and plane.path("graph", "company.json").exists():
        return False
    if not wait and plane.path("graph", "company.json").exists():
        _background(plane)
        return False
    _rebuild_now(plane)
    return True
