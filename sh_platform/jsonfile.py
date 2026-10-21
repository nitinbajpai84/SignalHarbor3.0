"""JSON files for the stores: a strict read, an atomic write, one process-wide lock per file.

Each store keeps its own plain-words errors and its own path checks; this holds only the file handling.
The lock covers threads in one process only; a second writer process needs a file lock first (the name
vault has one).

Production mode: `ROUTE` (set by sh_platform/state/routing.py at start-up) sends the documents of a company plane to the state store
and makes lock_for a Postgres advisory lock; see that module. In simple mode ROUTE is None and nothing here changes.
"""
import json
import os
import secrets
import threading
import time
from contextlib import suppress
from pathlib import Path

_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()
ROUTE = None  # production mode: sh_platform.state.routing.Route


def reset_locks() -> None:
    with _GUARD:
        _LOCKS.clear()


def lock_for(path: Path) -> threading.RLock:
    """The one lock for this file, however many store objects point at it."""
    with _GUARD:
        name = os.path.normcase(str(Path(path).resolve()))
        if name not in _LOCKS:
            adv = None
            if ROUTE:
                from sh_platform.state import routing
                adv = routing.lock_name(ROUTE, path)
            _LOCKS[name] = routing.PgLock(ROUTE, adv) if adv else threading.RLock()
        return _LOCKS[name]


def read_json_strict(path: Path, kind: type | None = None) -> object:
    """The parsed file, or None when it does not exist. A file that cannot be read raises OSError; one that
    is not valid JSON, or not of type `kind`, raises ValueError. The caller must never overwrite it."""
    k = ROUTE and ROUTE.key(path)
    if k:
        data, _ = ROUTE.store.get(*k)
        if data is None:
            return None
        if kind is not None and not isinstance(data, kind):
            raise ValueError("the file has the wrong shape")
        return data
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except RecursionError:
        raise ValueError("nesting too deep") from None
    if kind is not None and not isinstance(data, kind):
        raise ValueError("the file has the wrong shape")
    return data


def write_json_atomic(path: Path, obj: object) -> None:
    """Write via a unique temp file, fsync, os.replace: the file is whole before or whole after, never half."""
    if k := ROUTE and ROUTE.key(path):
        ROUTE.store.put(*k, obj)
        return
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: a scanner may briefly hold the target
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        with suppress(OSError):  # cleanup must never replace the real error
            tmp.unlink(missing_ok=True)


def claim_new(path: Path) -> None:
    """Create the file `path` only if nobody has (raises FileExistsError otherwise): the claim on a number. In production a placeholder
    document is stored with expected version 0, so two processes cannot both win."""
    if k := ROUTE and ROUTE.key(path):
        from sh_platform.state import Conflict
        try:
            ROUTE.store.put(*k, {}, expected="0")
        except Conflict:
            raise FileExistsError(str(path)) from None
        return
    os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
