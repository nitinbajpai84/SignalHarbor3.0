"""A local document index per company: what the agents search and read, the way a coding agent searches a repository.

A file's text is read once on this machine (`context_docs.reader.read_segments`: text, Office, PDF, pictures through the local picture
reader), cleaned into numbered lines exactly as the source viewer numbers them (`x5_extract._lines`), split into passages of about
800 to 1,200 characters (a heading starts a new one) and stored in SQLite FTS5 at `data/<company>/index/docs.sqlite`: keyword search,
BM25 order, standard library only, nothing leaves the machine. `ensure` is idempotent: a file whose size and time have not changed is
not read again; a changed file is re-indexed.

Who may see which file is NOT decided here. The tools (`doc_tools`) pass only the paths of files ticked for the conversation that the
person may read (C4 `selected`, K1, G1).
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from sh_platform.context_docs import reader
from sh_platform.jsonfile import lock_for
from sh_platform.v1 import doc_embed

log = logging.getLogger(__name__)
PASSAGE_MIN, PASSAGE_MAX, HEAD_MIN = 800, 1200, 300
_HEAD = re.compile(r"#{1,6}\s")
_JUNK = re.compile(r"[\s|:\-]+")
_SCHEMA = """
create table if not exists files(path text primary key, sig text, name text, nlines integer, pages integer, heads text);
create table if not exists lines(path text, n integer, text text, primary key(path, n)) without rowid;
create virtual table if not exists passages using fts5(text, path unindexed, l1 unindexed, l2 unindexed, tokenize='porter unicode61');
create table if not exists vectors(path text, l1 integer, l2 integer, vec blob);
create index if not exists vectors_path on vectors(path);
create table if not exists vec_files(path text primary key, sig text);
"""


def _db(plane) -> sqlite3.Connection:
    folder = plane.path("index")
    folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(folder / "docs.sqlite", timeout=30)
    con.executescript(_SCHEMA)
    return con


def _sig(p) -> str:
    st = p.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def read_lines(name: str, data: bytes) -> tuple[list[str], int | None]:
    """(numbered-line texts, pages or slides) with the same cleaning as the source viewer, so line numbers agree."""
    segs = reader.read_segments(name, data)
    text = "\n".join(t for _, t in segs)
    lines = [ln for ln in (re.sub(r"[*_`]", "", raw).strip() for raw in text.splitlines()) if ln and not _JUNK.fullmatch(ln)]
    paged = len(segs) if segs and str(segs[0][0] or "").startswith(("p.", "slide")) else None
    return lines, paged


def passages(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first line, last line, text): lines are gathered up to PASSAGE_MAX characters; a heading closes the passage once it holds HEAD_MIN."""
    out, cur, size = [], [], 0

    def flush():
        nonlocal cur, size
        if cur:
            out.append((cur[0][0], cur[-1][0], " ".join(t for _, t in cur)))
        cur, size = [], 0
    for n, t in enumerate(lines, 1):
        t = t[:PASSAGE_MAX]  # ponytail: one very long line is cut for search; read_document still gives it whole (up to its cap)
        if cur and (size + len(t) > PASSAGE_MAX or (_HEAD.match(t) and size >= HEAD_MIN)):
            flush()
        cur.append((n, t))
        size += len(t) + 1
        if size >= PASSAGE_MIN and not t.endswith((",", ":", ";")):
            flush()
    flush()
    return out


def _fresh(plane, path: str) -> bool:
    p = plane.path(*path.replace("\\", "/").split("/"))
    if not p.is_file():
        return False
    con = _db(plane)
    try:
        row = con.execute("select sig from files where path=?", (path,)).fetchone()
    finally:
        con.close()
    return bool(row and row[0] == _sig(p))


def ensure(plane, path: str) -> dict | None:
    """Index the file at `path` (plane-relative) if it is new or changed. Returns its record, or None when it cannot be read.
    The file is read outside the database lock, so a slow scan does not hold up a search of another file."""
    p = plane.path(*path.replace("\\", "/").split("/"))
    if not p.is_file():
        return None
    sig = _sig(p)
    db = plane.path("index", "docs.sqlite")
    with lock_for(db):
        con = _db(plane)
        try:
            row = con.execute("select sig, name, nlines, pages, heads from files where path=?", (path,)).fetchone()
        finally:
            con.close()
    if row and row[0] == sig:
        return {"path": path, "name": row[1], "lines": row[2], "pages": row[3], "heads": [h for h in (row[4] or "").split("\n") if h]}
    try:
        lines, pages = read_lines(p.name, p.read_bytes())
    except Exception:  # noqa: BLE001 - a file that cannot be read is remembered as empty until it changes
        log.warning("a document could not be indexed")
        lines, pages = [], None
    heads = [re.sub(r"^#+\s*", "", ln)[:80] for ln in lines if _HEAD.match(ln)][:12]
    with lock_for(db):
        con = _db(plane)
        try:
            with con:
                con.execute("delete from lines where path=?", (path,))
                con.execute("delete from passages where path=?", (path,))
                con.execute("delete from vectors where path=?", (path,))
                con.execute("delete from vec_files where path=?", (path,))
                con.execute("delete from files where path=?", (path,))
                con.executemany("insert into lines values(?,?,?)", [(path, n, t) for n, t in enumerate(lines, 1)])
                con.executemany("insert into passages(text, path, l1, l2) values(?,?,?,?)", [(t, path, a, b) for a, b, t in passages(lines)])
                con.execute("insert into files values(?,?,?,?,?,?)", (path, sig, p.name, len(lines), pages, "\n".join(heads)))
        finally:
            con.close()
    _embed_later(plane, path)
    return {"path": path, "name": p.name, "lines": len(lines), "pages": pages, "heads": heads} if lines else None


# A picture or a PDF may need OCR, which can take minutes: it is indexed in the background (at upload, or at the first search) and a
# search says "still reading" until it is done. Everything else is quick and is indexed inline.
_bg = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc-index")
_busy: set[tuple[str, str]] = set()
_busy_lock = threading.Lock()


def _slow(path: str) -> bool:
    return reader.ext_of(path) in reader.PICTURE_TYPES | {"pdf"}


def reading(plane, path: str) -> bool:
    """True while the background index of this file has not finished."""
    with _busy_lock:
        return (str(plane.root), path) in _busy


def _job(plane, path: str, key) -> None:
    try:
        ensure(plane, path)  # ensure queues the vectors behind it
    except Exception:  # noqa: BLE001 - a failed index is retried at the next question
        log.warning("a document could not be indexed in the background")
    finally:
        with _busy_lock:
            _busy.discard(key)


def index_later(plane, path: str) -> None:
    """Start indexing a picture or PDF in the background unless it is already indexed or being indexed."""
    key = (str(plane.root), path)
    if not _slow(path):
        return
    with _busy_lock:
        if key in _busy:
            return
        _busy.add(key)
    try:
        if not _fresh(plane, path):
            _bg.submit(_job, plane, path, key)
            return
    except Exception:  # noqa: BLE001 - a missing file or a closed pool: nothing to index
        log.warning("a document could not be queued for indexing")
    with _busy_lock:
        _busy.discard(key)


def _ready(plane, paths: list[str]) -> list[str]:
    """The paths that can be searched now; the slow ones not yet indexed are started in the background and left out."""
    out = []
    for p in paths:
        if _slow(p) and not _fresh(plane, p):
            index_later(plane, p)
        else:
            ensure(plane, p)
            out.append(p)
    return out


# Meaning search: each passage is also embedded by the local model and stored as float32 unit vectors beside the passages. Embedding
# runs in the background pool, never in the foreground (an upload or a question is not held up by it). A file whose vectors are not
# there yet is searched by words only and is embedded at the next question (backfill, at most BACKFILL_FILES per search).
BACKFILL_FILES, RRF_K, MIN_COS = 4, 60, 0.45  # MIN_COS: bge-small scores ~0.4 for unrelated text, 0.5+ for related
_warned = False


def _submit(fn, *a) -> None:  # the one place a background job starts (tests run it inline)
    _bg.submit(fn, *a)


def _vsig(sig: str) -> str:
    return f"{doc_embed.MODEL}|{sig}"  # vectors belong to a model too: switching SH_EMBED_MODEL re-embeds by itself


def forget(plane, path: str) -> None:
    """Drop every row of a file that has left the library."""
    db = plane.path("index", "docs.sqlite")
    if not db.is_file():
        return
    with lock_for(db):
        con = _db(plane)
        try:
            with con:
                for t in ("lines", "passages", "vectors", "vec_files", "files"):
                    con.execute(f"delete from {t} where path=?", (path,))
        finally:
            con.close()


def _embed_file(plane, path: str, key) -> None:
    """Embed the passages of one indexed file and store them, if the file is unchanged since it was indexed."""
    again = False
    try:
        db = plane.path("index", "docs.sqlite")
        con = _db(plane)
        try:
            row = con.execute("select f.sig, v.sig from files f left join vec_files v on v.path=f.path where f.path=?", (path,)).fetchone()
            if not row or (row[1] is not None and _vsig(row[0]) == row[1]):
                return
            sig = row[0]
            rows = con.execute("select l1, l2, text from passages where path=? order by rowid", (path,)).fetchall()
        finally:
            con.close()
        vecs = doc_embed.embed([t for _, _, t in rows]) if rows else []
        with lock_for(db):
            con = _db(plane)
            try:
                with con:
                    if con.execute("select sig from files where path=?", (path,)).fetchone() != (sig,):
                        again = True  # changed while embedding: queue the new version once this job is done
                    else:
                        con.execute("delete from vectors where path=?", (path,))
                        con.executemany("insert into vectors values(?,?,?,?)", [(path, a, b, v.tobytes()) for (a, b, _), v in zip(rows, vecs)])
                        con.execute("insert or replace into vec_files values(?,?)", (path, _vsig(sig)))
            finally:
                con.close()
    except doc_embed.Unavailable:
        _warn()
    except Exception:  # noqa: BLE001 - vectors are optional; retried at the next question
        log.warning("a document could not be embedded")
    finally:
        with _busy_lock:
            _busy.discard(key)
    if again:
        _embed_later(plane, path)


def _warn() -> None:
    global _warned
    if not _warned:
        _warned = True
        log.warning("the local embedding model is not available: search uses words only")


def _embed_later(plane, path: str) -> None:
    key = (str(plane.root), "vec:" + path)
    with _busy_lock:
        if key in _busy:
            return
        _busy.add(key)
    try:
        _submit(_embed_file, plane, path, key)
    except Exception:  # noqa: BLE001 - closed pool
        with _busy_lock:
            _busy.discard(key)


def _drop_vectors(plane, bad) -> None:
    with lock_for(plane.path("index", "docs.sqlite")):
        con = _db(plane)
        try:
            with con:
                for p in bad:
                    con.execute("delete from vec_files where path=?", (p,))
                    con.execute("delete from vectors where path=?", (p,))
        finally:
            con.close()
    for p in bad:
        _embed_later(plane, p)


def _vector_hits(plane, paths: list[str], query: str, limit: int) -> list[tuple]:
    """(path, l1, l2) of the passages closest in meaning, best first; [] when the model is unavailable. Only `paths` are looked at."""
    con = _db(plane)
    try:
        marks = ",".join("?" * len(paths))
        have = [p for (p,) in con.execute(f"select f.path from files f join vec_files v on v.path=f.path and v.sig=? || f.sig where f.path in ({marks})", (doc_embed.MODEL + "|", *paths))]
        rows = con.execute(f"select path, l1, l2, vec from vectors where path in ({','.join('?' * len(have))})", have).fetchall() if have else []
    finally:
        con.close()
    for p in [p for p in paths if p not in have][:BACKFILL_FILES]:
        _embed_later(plane, p)
    if not rows:
        return []
    try:
        q = doc_embed.embed([query], query=True)[0]
    except doc_embed.Unavailable:
        _warn()
        return []
    except Exception:  # noqa: BLE001 - meaning search is optional; words still answer
        log.warning("meaning search failed; using words only")
        return []
    bad = {r[0] for r in rows if len(r[3]) != q.nbytes}  # another dimension or a damaged blob: no vectors for that file, re-embedded later
    if bad:
        log.warning("vectors of %d document(s) do not fit the model; they are re-embedded", len(bad))
        _drop_vectors(plane, bad)
        rows = [r for r in rows if r[0] not in bad]
        if not rows:
            return []
    # ponytail: brute-force cosine over the candidate passages; move to DuckDB vss or sqlite-vec past ~100k passages
    sims = np.frombuffer(b"".join(r[3] for r in rows), dtype=np.float32).reshape(len(rows), -1) @ q
    return [(rows[i][0], int(rows[i][1]), int(rows[i][2])) for i in np.argsort(-sims)[:limit] if sims[i] >= MIN_COS]


def _match(query: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", str(query))[:12]
    return " OR ".join(f'"{w}"' for w in words)


def search(plane, paths: list[str], query: str, limit: int = 5) -> list[dict]:
    """The best passages of the given files only, words (BM25) and meaning (vectors) merged by reciprocal rank fusion:
    [{path, from, to, text, how}], how = words | meaning | both. If the model is unavailable: words only."""
    q, paths = _match(query), [p for p in dict.fromkeys(paths)]
    if not (q or str(query).strip()) or not paths:
        return []
    paths = _ready(plane, paths)
    if not paths:
        return []
    limit = max(1, min(int(limit), 8))
    rows = []
    if q:  # a query with no ASCII word (Chinese, say) skips the keyword half and goes to meaning search
        con = _db(plane)
        try:
            marks = ",".join("?" * len(paths))
            rows = con.execute(f"select path, l1, l2, text from passages where passages match ? and path in ({marks}) order by bm25(passages) limit ?",
                               (q, *paths, limit * 3)).fetchall()
        finally:
            con.close()
    words = [(a, int(b), int(c)) for a, b, c, _ in rows]
    meaning = _vector_hits(plane, paths, str(query), limit * 3)
    score: dict[tuple, float] = {}
    for ranked in (words, meaning):
        for r, k in enumerate(ranked):
            score[k] = score.get(k, 0.0) + 1.0 / (RRF_K + r + 1)
    best = sorted(score, key=lambda k: -score[k])[:limit]
    texts = {(a, int(b), int(c)): t for a, b, c, t in rows}
    con = _db(plane)
    try:
        for k in best:
            if k not in texts:
                r = con.execute("select text from passages where path=? and l1=? and l2=?", k).fetchone()
                texts[k] = r[0] if r else ""
    finally:
        con.close()
    wset, mset = set(words), set(meaning)
    return [{"path": k[0], "from": k[1], "to": k[2], "text": texts[k], "how": "both" if k in wset and k in mset else "meaning" if k in mset else "words"}
            for k in best]


def read(plane, path: str, first: int, last: int, max_lines: int = 60, max_chars: int = 3000) -> list[tuple[int, str]]:
    """Numbered lines first..last of one indexed file, cut at max_lines or max_chars (whichever comes first). [] while a scan is still read."""
    if not _ready(plane, [path]):
        return []
    first = max(1, int(first))
    last = min(int(last), first + max_lines - 1)
    con = _db(plane)
    try:
        rows = con.execute("select n, text from lines where path=? and n between ? and ? order by n", (path, first, last)).fetchall()
    finally:
        con.close()
    out, used = [], 0
    for n, t in rows:
        if used + len(t) > max_chars:
            t = t[:max(0, max_chars - used)]
            if t:
                out.append((n, t))
            break
        out.append((n, t))
        used += len(t)
    return out


def digest(plane, path: str, found: list[str] | None = None) -> str:
    """One local sentence on what a file holds: its length, its headings, and what the catalogue scan found in it. No model."""
    if _slow(path) and not _fresh(plane, path):
        index_later(plane, path)
        return ""
    rec = ensure(plane, path)
    if rec is None:
        return ""
    size = f"{rec['pages']} pages" if rec["pages"] else f"{rec['lines']} lines"
    heads = [h for h in rec["heads"] if h][:4]
    bits = [f"it covers {', '.join(heads)}"] if heads else []
    bits += list(found or [])
    return f"I read {rec['name']}: {size}" + (f"; {'; '.join(bits)}" if bits else "") + "."
