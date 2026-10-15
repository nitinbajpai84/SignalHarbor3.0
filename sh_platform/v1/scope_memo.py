"""One request asks the warehouse the same question many times (the Morning Note reads the issued report four times, the cases twice, each portfolio's value
for every period it appears in). Inside `with scope():` a function marked `@memo` is worked out once per distinct arguments and the answer reused; outside a
scope it runs as before, so tests and scripts see no change. The warehouse does not change inside one request, so the answers cannot go stale. A copy is
returned each time, so a caller that edits its answer cannot change what the next caller sees."""
from __future__ import annotations

import contextvars
import copy
import functools
from contextlib import contextmanager

_MEMO: contextvars.ContextVar[dict | None] = contextvars.ContextVar("scope_memo", default=None)


@contextmanager
def scope():
    token = _MEMO.set({})
    try:
        yield
    finally:
        _MEMO.reset(token)


def _k(x):
    if isinstance(x, (dict, list, set)):
        return repr(x)
    try:
        hash(x)
        return x
    except TypeError:
        return id(x)  # the company plane: one object per request


def memo(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        m = _MEMO.get()
        if m is None:
            return fn(*a, **k)
        key = (fn.__module__, fn.__qualname__, tuple(_k(x) for x in a), tuple(sorted((n, _k(v)) for n, v in k.items())))
        if key not in m:
            m[key] = fn(*a, **k)
        return copy.deepcopy(m[key])
    return wrapper


def store(name: str) -> dict | None:
    """A dict that lives as long as the current scope (None outside one), for lookups a function wants to remember by key."""
    m = _MEMO.get()
    return None if m is None else m.setdefault(("store", name), {})
