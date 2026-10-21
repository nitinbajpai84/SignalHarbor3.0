"""Production mode: the JSON documents of a company plane live in the state store (Postgres), not on the volume.

Everything the running app reads or writes goes through one of three choke points, so no caller changes:
  1. sh_platform/jsonfile.py: read_json_strict, write_json_atomic and lock_for ask `ROUTE` (set by `configure`) before touching a file.
  2. `StatePath`: the Path that the company plane (sh_platform/plane.py) hands out in production. read_text, write_text, open, exists, is_file,
     is_dir, stat, glob, rglob, iterdir, unlink, rename and replace on a ".json" path under an area go to the store; everything else is a normal file.
  3. lock_for: a read-modify-write under it is serialised across processes by a Postgres advisory lock, so two web copies and the worker
     see one truth (this replaces a version check plus retry for those callers; `update()` in state/__init__.py does the version check).

Key scheme (the same as tools/migrate_to_postgres.py): kind = the area folder, key = "<company>/<path inside the area>".

Also state: <data root>/_control/*.json (accounts, providers, indexes), kind "control".

Stays on the volume: the DuckDB warehouse, raw dropped and uploaded files (dropbox, documents, landing/originals, projects/<id>/files),
the doc index (sqlite), .jsonl logs, markdown, csv and every other non-.json file, and anything at the top of the data root or of a company folder.
Simple mode never imports this module: `ROUTE` stays None and every file behaves exactly as before.
"""
from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import os
import re
import stat as _stat
import threading
from pathlib import Path

from sh_platform import jsonfile
from sh_platform.state import PgStore

_KIND = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
RAW_AREAS = frozenset({"dropbox", "warehouse", "documents", "index"})


def on_volume(area: str, rest: list[str]) -> bool:
    """True when a document under company/<area>/<rest> is not a state document (raw files and non-kinds)."""
    return (area in RAW_AREAS or not _KIND.match(area) or "originals" in rest
            or (area == "projects" and len(rest) >= 2 and rest[1] == "files"))


def doc_key(area: str, rest: list[str]):
    """(kind, inner path) for a state document, else None. `rest` is the path inside the area."""
    if not rest or on_volume(area, rest) or not rest[-1].endswith(".json") or ".tmp" in rest[-1]:
        return None
    return area, "/".join(rest)


def key_of_parts(parts: list[str]):
    """(kind, key) for the path parts [company, area, *rest] under the data root, else None. The platform's own <root>/_control/<name>.json
    (accounts, providers, indexes) are state too: kind "control", key "_control/<name>.json"."""
    if len(parts) == 2 and parts[0] == "_control" and parts[1].endswith(".json") and ".tmp" not in parts[1]:
        return "control", "/".join(parts)
    if len(parts) < 3:
        return None
    k = doc_key(parts[1], parts[2:])
    return None if k is None else (k[0], f"{parts[0]}/{k[1]}")


def _norm(p) -> str:
    s = os.path.abspath(str(p))
    if s.startswith("\\\\?\\"):
        s = s[4:]
    return os.path.normcase(s)


class Route:
    def __init__(self, data_root, store):
        self.store = store
        self.roots = {_norm(data_root), _norm(Path(data_root).resolve())}

    def parts(self, path):
        """[company, area, *rest] when the path is under the data root, else None."""
        s = _norm(path)
        for r in self.roots:
            if s == r or s.startswith(r + os.sep):
                return [x for x in s[len(r):].split(os.sep) if x]
        return None

    def key(self, path):
        """(kind, "<company>/<inner>") when `path` is a state document."""
        ps = self.parts(path)
        return ps and key_of_parts(ps)

    def prefix(self, path):
        """(kind, "<company>/<inner>/") for a folder inside an area where documents may live, else None."""
        ps = self.parts(path)
        if not ps or len(ps) < 2 or on_volume(ps[1], ps[2:]):
            return None
        return ps[1], "/".join([ps[0], *ps[2:], ""])

    def children(self, path) -> list[str] | None:
        """Paths (relative, "/"-joined) of every document below a folder; None when it is not a state folder."""
        pre = self.prefix(path)
        if pre is None:
            return None
        return [k[len(pre[1]):] for k in self.store.keys(pre[0], pre[1])]


def configure(data_root=None, store=None):
    """Install (production) or remove (simple) the routing. Call once at start-up, in the web app and in the worker."""
    from sh_platform import mode
    if not mode.production() and store is None:
        jsonfile.ROUTE = None
        return None
    if data_root is None:
        from sh_platform.settings import load_settings
        data_root = load_settings().data_root
    jsonfile.ROUTE = Route(data_root, store or PgStore(os.environ["DATABASE_URL"]))
    jsonfile.reset_locks()
    return jsonfile.ROUTE


def release():
    jsonfile.ROUTE = None
    jsonfile.reset_locks()


# ---- locks across processes --------------------------------------------------------------------------------------------------------
class PgLock:
    """A reentrant lock: the in-process RLock plus a Postgres advisory lock held on its own connection while the outermost hold lasts."""

    def __init__(self, route: Route, name: str):
        self.t, self.route, self.depth, self.conn = threading.RLock(), route, 0, None
        self.id = int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), "big", signed=True)

    def acquire(self, blocking=True, timeout=-1):
        if not self.t.acquire(blocking, timeout):
            return False
        if self.depth == 0:
            try:
                self.conn = self.route.store.connect()
                self.conn.autocommit = True
                self.conn.execute("SELECT pg_advisory_lock(%s)", (self.id,))
            except BaseException:
                self._drop()
                self.t.release()
                raise
        self.depth += 1
        return True

    def _drop(self):
        c, self.conn = self.conn, None
        if c is not None:
            try:
                c.close()  # closing the session frees its advisory lock
            except Exception:  # noqa: BLE001
                pass

    def release(self):
        self.depth -= 1
        if self.depth == 0:
            self._drop()
        self.t.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def lock_name(route: Route, path):
    """The advisory-lock name for a file or folder in a state area (no suffix or .json); None for logs and other files, which keep the thread lock."""
    ps = route.parts(path)
    if ps and key_of_parts(ps) and len(ps) == 2:
        return "/".join(ps)
    if not ps or len(ps) < 2 or on_volume(ps[1], ps[2:]) or os.path.splitext(ps[-1])[1] not in ("", ".json"):
        return None
    return "/".join(ps)


# ---- the path ----------------------------------------------------------------------------------------------------------------------
class _Writer:
    """What open(..., 'w') gives for a state document: the text is parsed and stored when it is closed."""

    def __init__(self, route, k, binary):
        self.route, self.k, self.binary, self.buf, self.closed = route, k, binary, io.BytesIO() if binary else io.StringIO(), False

    def write(self, data):
        return self.buf.write(data)

    def flush(self):
        pass

    def fileno(self):
        raise io.UnsupportedOperation("fileno")

    def close(self):
        if not self.closed:
            self.closed = True
            raw = self.buf.getvalue()
            self.route.store.put(self.k[0], self.k[1], json.loads(raw.decode("utf-8") if self.binary else raw))

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if t is None:
            self.close()


def _match(parts, segs) -> bool:
    if not segs:
        return not parts
    if segs[0] == "**":
        return any(_match(parts[i:], segs[1:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatchcase(parts[0], segs[0]) and _match(parts[1:], segs[1:])


def _fake_stat(size: int, mtime: float, is_dir: bool):
    mode = (_stat.S_IFDIR | 0o755) if is_dir else (_stat.S_IFREG | 0o644)
    return os.stat_result((mode, 0, 0, 1, 0, 0, size, mtime, mtime, mtime))


_Base = type(Path())


class StatePath(_Base):
    """A Path whose .json documents under an area are in the store in production. Other files and folders behave as usual."""

    def _k(self):
        r = jsonfile.ROUTE
        return None if r is None else r.key(self)

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        k = self._k()
        if k is None or not (set(mode) & set("rw")) or "+" in mode or "a" in mode or "x" in mode:
            return super().open(mode, buffering, encoding, errors, newline)
        store, binary = jsonfile.ROUTE.store, "b" in mode
        if "w" in mode:
            return _Writer(jsonfile.ROUTE, k, binary)
        doc, _ = store.get(*k)
        if doc is None:
            raise FileNotFoundError(2, "No such file or directory", str(self))
        text = json.dumps(doc, indent=2)
        return io.BytesIO(text.encode("utf-8")) if binary else io.StringIO(text)

    def stat(self, *, follow_symlinks=True):
        r, k = jsonfile.ROUTE, self._k()
        if k is not None:
            doc, _ = r.store.get(*k)
            if doc is None:
                raise FileNotFoundError(2, "No such file or directory", str(self))
            return _fake_stat(len(json.dumps(doc)), r.store.mtime(*k), False)
        try:
            return super().stat()
        except FileNotFoundError:
            if r is not None and (pre := r.prefix(self)) and r.store.keys(pre[0], pre[1]):
                return _fake_stat(0, 0.0, True)  # a folder that only holds documents in the store
            raise

    lstat = stat

    def glob(self, pattern):
        r = jsonfile.ROUTE
        rels = r.children(self) if r is not None else None
        try:
            disk = list(super().glob(pattern))
        except FileNotFoundError:  # a folder that only holds documents in the store
            if not rels:
                raise
            disk = []
        seen = {str(p) for p in disk}
        yield from disk
        if not rels:
            return
        segs, found = pattern.replace("\\", "/").split("/"), set()
        for rel in rels:
            parts = rel.split("/")
            found.update("/".join(parts[:n]) for n in range(1, len(parts) + 1) if _match(parts[:n], segs))
        for f in sorted(found):
            if str(p := self / f) not in seen:
                yield p

    def rglob(self, pattern):
        return self.glob("**/" + pattern)

    def iterdir(self):
        return self.glob("*")

    def unlink(self, missing_ok=False):
        k = self._k()
        if k is None:
            return super().unlink(missing_ok)
        store = jsonfile.ROUTE.store
        had = store.get(*k)[0] is not None
        if had:
            store.delete(*k)
        _Base.unlink(self, missing_ok=True)  # a stale copy on the volume goes too
        if not had and not missing_ok:
            raise FileNotFoundError(2, "No such file or directory", str(self))

    def replace(self, target):
        r, k, t = jsonfile.ROUTE, self._k(), StatePath(target)
        tk = t._k()
        if r is None or (k is None and tk is None):
            return super().replace(target)
        if k is not None:
            doc, _ = r.store.get(*k)
            if doc is None:
                raise FileNotFoundError(2, "No such file or directory", str(self))
        else:
            doc = json.loads(_Base.read_text(self, encoding="utf-8"))
        if tk is not None:
            r.store.put(*tk, doc)
        else:
            t.parent.mkdir(parents=True, exist_ok=True)
            _Base.write_text(t, json.dumps(doc, indent=2), encoding="utf-8")
        if k is not None:
            r.store.delete(*k)
        else:
            _Base.unlink(self, missing_ok=True)
        return t

    rename = replace
