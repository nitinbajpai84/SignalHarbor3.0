"""Simple or production mode (docs/architecture/sh-local-vs-production.json). Production when DATABASE_URL and REDIS_URL are both set,
simple when neither is. Only one set is a mistake, and the server refuses to start rather than guess which store holds the data."""
import os


class ModeError(RuntimeError):
    pass


def _set(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def check() -> str:
    """The mode, or ModeError when exactly one of the two is set. Call at start-up."""
    db, rd = _set("DATABASE_URL"), _set("REDIS_URL")
    if db != rd:
        raise ModeError(f"{'DATABASE_URL' if db else 'REDIS_URL'} is set but {'REDIS_URL' if db else 'DATABASE_URL'} is not. "
                        "Set both for production mode, or neither for simple mode.")
    return "production" if db else "simple"


def mode() -> str:
    return check()


def production() -> bool:
    return check() == "production"
