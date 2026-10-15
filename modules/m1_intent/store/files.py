"""M1's plain-words wrapper over sh_platform/jsonfile.py: a damaged file is refused (StoreError) and never
overwritten; a failed write says so in one sentence. Locks cover threads in one process only (A-015)."""
from pathlib import Path

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic  # lock_for: re-exported for the api, domain and store modules

UNREADABLE = "These records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


class WrongState(StoreError):
    """The session is not in a stage that allows this."""


def read_json(path: Path):
    """The parsed object, or None when the file does not exist. One that cannot be read, parsed or is not an object raises StoreError."""
    try:
        return read_json_strict(path, dict)
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None


def write_json(path: Path, data) -> None:
    try:
        write_json_atomic(path, data)
    except OSError:
        raise StoreError(NOT_SAVED) from None
