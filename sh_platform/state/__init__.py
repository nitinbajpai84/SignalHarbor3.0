"""State adapter. `StateStore` holds JSON documents by (kind, key) with a version and compare-and-set.

- simple: `FileStore`, today's JSON files (atomic write, one lock per file). The version is a hash of the file, so the files on disk keep
  exactly the shape they have today.
- production: `PgStore` (Postgres via psycopg): one table per kind, JSONB document, bigint version, transactions.

kind = the company-folder area ("intents", "build", ...); key = "<company>/<path inside the area>", e.g. "acme/p1/plan-v1.json".
`version` is an opaque string; "0" means the document does not exist. `put(..., expected=v)` raises Conflict when the stored version is not v.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from sh_platform import mode as _mode
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic


class Conflict(Exception):
    """The document changed since it was read."""


_KIND = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


def _key_parts(key: str) -> tuple[str, str]:
    company, _, rest = key.partition("/")
    if not company or not rest or ".." in key.split("/") or key.startswith("/") or "\\" in key or ":" in key:
        raise ValueError("a key is '<company>/<path>' with no '..'")
    return company, rest


def _kind(kind: str) -> str:
    if not _KIND.match(kind or ""):
        raise ValueError("bad kind")
    return kind


def _version_of(doc) -> str:
    return hashlib.sha1(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]


class FileStore:
    def __init__(self, data_root):
        self.root = Path(data_root)

    def _path(self, kind: str, key: str) -> Path:
        company, rest = _key_parts(key)
        return self.root / company / _kind(kind) / rest

    def get(self, kind: str, key: str):
        """(document, version); (None, "0") when absent."""
        doc = read_json_strict(self._path(kind, key))
        return (None, "0") if doc is None else (doc, _version_of(doc))

    def put(self, kind: str, key: str, doc, expected: str | None = None) -> str:
        p = self._path(kind, key)
        with lock_for(p):
            if expected is not None and self.get(kind, key)[1] != expected:
                raise Conflict(key)
            write_json_atomic(p, doc)
        return _version_of(doc)

    def delete(self, kind: str, key: str) -> None:
        p = self._path(kind, key)
        with lock_for(p):
            p.unlink(missing_ok=True)

    def keys(self, kind: str, prefix: str = "") -> list[str]:
        out = []
        for c in sorted(d for d in self.root.iterdir() if d.is_dir()) if self.root.is_dir() else []:
            base = c / _kind(kind)
            for f in sorted(base.rglob("*.json")) if base.is_dir() else []:
                k = f"{c.name}/{f.relative_to(base).as_posix()}"
                if k.startswith(prefix):
                    out.append(k)
        return out


def _like(prefix: str) -> str:
    """A LIKE pattern start that matches the prefix literally."""
    return re.sub(r"([\\%_])", r"\\\1", prefix)


_NUL, _NUL_MARK = chr(0), chr(0xE000)  # ponytail: jsonb cannot hold U+0000 (the role guard prefix, profile/view.py); a private-use mark stands in


def _swap(doc, a: str, b: str):
    """Every string (keys too) with a replaced by b, at any depth."""
    if isinstance(doc, str):
        return doc.replace(a, b)
    if isinstance(doc, dict):
        return {_swap(k, a, b): _swap(v, a, b) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_swap(v, a, b) for v in doc]
    return doc


class PgStore:
    """ponytail: one short connection per call; psycopg_pool when the web service needs it. Tables are made on first use."""

    def __init__(self, url: str):
        self.url, self._made = url, set()

    def connect(self):
        import psycopg
        return psycopg.connect(self.url)

    def _table(self, kind: str, conn) -> str:
        t = "sh_state_" + re.sub(r"[^a-z0-9]", "_", _kind(kind))
        if t not in self._made:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {t} (key text PRIMARY KEY, doc jsonb NOT NULL, "
                         "version bigint NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now())")
            self._made.add(t)
        return t

    def get(self, kind: str, key: str, conn=None):
        _key_parts(key)
        with _maybe(self, conn) as c:
            row = c.execute(f"SELECT doc, version FROM {self._table(kind, c)} WHERE key = %s", (key,)).fetchone()
        return (None, "0") if row is None else (_swap(row[0], _NUL_MARK, _NUL), str(row[1]))

    def put(self, kind: str, key: str, doc, expected: str | None = None, conn=None) -> str:
        from psycopg.types.json import Jsonb
        _key_parts(key)
        doc = _swap(doc, _NUL, _NUL_MARK)
        with _maybe(self, conn) as c:
            t = self._table(kind, c)
            if expected is None:
                sql, args = (f"INSERT INTO {t} AS s (key, doc) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE "
                             "SET doc = EXCLUDED.doc, version = s.version + 1, updated_at = now() RETURNING version"), (key, Jsonb(doc))
            elif expected == "0":
                sql, args = f"INSERT INTO {t} (key, doc) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING RETURNING version", (key, Jsonb(doc))
            else:
                sql, args = (f"UPDATE {t} SET doc = %s, version = version + 1, updated_at = now() WHERE key = %s AND version = %s "
                             "RETURNING version"), (Jsonb(doc), key, int(expected))
            row = c.execute(sql, args).fetchone()
        if row is None:
            raise Conflict(key)
        return str(row[0])

    def delete(self, kind: str, key: str, conn=None) -> None:
        with _maybe(self, conn) as c:
            c.execute(f"DELETE FROM {self._table(kind, c)} WHERE key = %s", (key,))

    def keys(self, kind: str, prefix: str = "") -> list[str]:
        with _maybe(self, None) as c:
            rows = c.execute(f"SELECT key FROM {self._table(kind, c)} WHERE key LIKE %s ORDER BY key",
                             (_like(prefix) + "%",)).fetchall()
        return [r[0] for r in rows]


class _maybe:
    """Use the caller's connection (its transaction, committed by the caller) or open one and commit it."""

    def __init__(self, store, conn):
        self.store, self.conn = store, conn

    def __enter__(self):
        if self.conn is not None:
            return self.conn
        self.own = self.store.connect()
        self.own.__enter__()
        return self.own

    def __exit__(self, *exc):
        if self.conn is None:
            return self.own.__exit__(*exc)


def update(store, kind: str, key: str, fn: Callable, tries: int = 8):
    """Read, change with fn(doc_or_None) -> doc, write if nobody else changed it; retry on a clash."""
    for _ in range(tries):
        doc, ver = store.get(kind, key)
        new = fn(doc)
        try:
            store.put(kind, key, new, expected=ver)
            return new
        except Conflict:
            continue
    raise Conflict(key)


def store_for(data_root):
    """The store for this mode."""
    import os
    return PgStore(os.environ["DATABASE_URL"]) if _mode.production() else FileStore(data_root)
