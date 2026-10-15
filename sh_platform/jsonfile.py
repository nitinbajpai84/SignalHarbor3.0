"""JSON files for the stores: a strict read, an atomic write, one process-wide lock per file.

Each store keeps its own plain-words errors and its own path checks; this holds only the file handling.
The lock covers threads in one process only; a second writer process needs a file lock first (the name
vault has one).
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


def lock_for(path: Path) -> threading.RLock:
    """The one lock for this file, however many store objects point at it."""
    with _GUARD:
        return _LOCKS.setdefault(os.path.normcase(str(Path(path).resolve())), threading.RLock())


def read_json_strict(path: Path, kind: type | None = None) -> object:
    """The parsed file, or None when it does not exist. A file that cannot be read raises OSError; one that
    is not valid JSON, or not of type `kind`, raises ValueError. The caller must never overwrite it."""
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
