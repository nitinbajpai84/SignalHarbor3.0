"""L3 The library sorts itself into folders: on screen and on disk.

Jev here is the classification step of K1 (`k1_classify`): rules first (`classify`), then the fast model tier through the router
(`k1_classify.ask_topic`, a digit-free prompt and a fixed answer list the program validates) only for what the rules leave unclear.
Each library row gets `folder`, `folder_by` (rules | Jev | owner), `subfolder` (a year, when the name has one) and, while the
background batch has not answered, `sorting: true`. The owner may move an item (`move`, recorded in `folder_log`).

On disk, files the library owns live at `library/<folder>/<id>__<name>` and a project's uploads at `projects/<pid>/files/<folder>/<id>__<name>`.
The company's own source folders (`documents/`, `landing/`) are read by the scans, the loader and the extractor, so those stay where
they are and are only shown in a folder. A move writes `library/aliases.json` {old path: new path}; `CompanyPlane.path` falls back to
it when an old path no longer exists, so every reader that holds a stored path (an intent of work's sources, an extraction, a
dashboard note) keeps working while the index stays the one truth.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from sh_platform.context_docs import reader
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import k1_classify as C

log = logging.getLogger(__name__)
Refused = L.Refused

FOLDERS = ("Process maps", "Reports and packs", "Benchmarks and targets", "Policies and rules", "Data samples", "Statements and invoices",
           "Capital calls and distributions", "Emails and notes", "Minutes and decisions", "External and market", "Pictures and scans", "Other")
ICONS = {"Process maps": "process", "Reports and packs": "report", "Benchmarks and targets": "target", "Policies and rules": "policy",
         "Data samples": "table", "Statements and invoices": "statement", "Capital calls and distributions": "capital",
         "Emails and notes": "mail", "Minutes and decisions": "minutes", "External and market": "market", "Pictures and scans": "picture",
         "Other": "other"}
BY = ("rules", "Jev", "owner")
# K1's topics that are not folders yet
_TOPIC_TO_FOLDER = {"Finance": "Statements and invoices", "Reporting": "Reports and packs", "General ledger": "Data samples",
                    "Pictures": "Pictures and scans"}
# two rules score the same: the more specific folder wins
_PRIORITY = ("Capital calls and distributions", "Minutes and decisions", "Emails and notes", "Statements and invoices", "Policies and rules",
             "Process maps", "Benchmarks and targets", "Reports and packs", "External and market", "Finance", "Reporting", "General ledger")
_YEAR = re.compile(r"(?<!\d)(20\d\d|19\d\d)(?!\d)")
_TABLE = ("csv", "tsv", "xlsx")
HEAD_BYTES = 4_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def folder_of_topic(topic: str) -> str:
    topic = _TOPIC_TO_FOLDER.get(topic, topic)
    return topic if topic in FOLDERS else "Other"


# ---- classification ------------------------------------------------------------------------------------------------------------------

def _best(text: str) -> str | None:
    """The folder whose K1 rule scores highest on `text` (ties: the more specific folder)."""
    score = {t: len(rx.findall(text)) for t, rx in C._RULES.items()}
    top = max(score.values(), default=0)
    if not top:
        return None
    tied = [t for t, n in score.items() if n == top]
    return folder_of_topic(min(tied, key=lambda t: _PRIORITY.index(t) if t in _PRIORITY else 99))


def classify(name: str, head_text: str = "", columns: list[str] | None = None, note: str = "") -> dict:
    """{folder, confidence, by, sure, subfolder}. Rules only: the file's name first, then its note, column names and first heading."""
    stem = name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    ext = reader.ext_of(name)
    year = _YEAR.search(stem)
    sub = year.group(1) if year else ""
    if ext in C.PICTURES:
        return {"folder": "Pictures and scans", "confidence": "high", "by": "rules", "sure": True, "subfolder": sub}
    got = _best(stem)
    if got:
        return {"folder": got, "confidence": "high", "by": "rules", "sure": True, "subfolder": sub}
    got = _best(" ".join([note or "", " ".join(columns or []), head_text or ""]))
    if got:
        return {"folder": got, "confidence": "medium", "by": "rules", "sure": True, "subfolder": sub}
    if ext in _TABLE:
        return {"folder": "Data samples", "confidence": "medium", "by": "rules", "sure": True, "subfolder": sub}
    return {"folder": "Other", "confidence": "low", "by": "rules", "sure": False, "subfolder": sub}


def proposal(name: str, prop: dict, note: str = "") -> dict:
    """The upload row's "Goes to: …" from K1's proposal: its model topic when Jev answered, the rules otherwise."""
    out = prop.get("outline") or {}
    c = classify(name, out.get("heading") or "", out.get("columns"), note)
    if prop.get("by") == "model" and prop.get("topics"):
        return {"folder": folder_of_topic(prop["topics"][0]), "folder_by": "Jev", "subfolder": c["subfolder"], "folders": list(FOLDERS)}
    return {"folder": c["folder"], "folder_by": "rules", "subfolder": c["subfolder"], "folders": list(FOLDERS)}


def _shape(plane, item: dict, ocr: bool = True) -> tuple[list[str] | None, str]:
    """(column names, first heading) of a stored item, read on this machine; never a value. `ocr` False: pictures and PDFs are not read
    (the first sort runs in a request; their text is read later, in the background batch)."""
    if not ocr and reader.ext_of(str(item.get("name") or "")) in reader.PICTURE_TYPES | {"pdf"}:
        return None, ""
    p = plane.path(*item["path"].split("/"))
    try:
        if p.is_dir():
            p = next((f for f in sorted(p.iterdir()) if f.is_file() and reader.ext_of(f.name) in _TABLE and not f.name.startswith("_")), None)
            if p is None:
                return None, ""
        if not p.is_file() or p.stat().st_size > HEAD_BYTES:
            return None, ""
        o = C.outline(p.name, p.read_bytes())
        return o.get("columns"), o.get("heading") or ""
    except Exception:  # noqa: BLE001 - a file that cannot be read is sorted by its name
        log.warning("a library file could not be read for sorting")
        return None, ""


def _classify_item(plane, item: dict) -> dict:
    cols, head = _shape(plane, item, ocr=False)
    return classify(item.get("name") or "", head, cols, item.get("note") or "")


# ---- the disk ------------------------------------------------------------------------------------------------------------------------

def _aliases_path(root: Path) -> Path:
    return root / "library" / "aliases.json"


_alias_cache: dict[str, tuple[float, dict]] = {}


def alias(root: Path, rel: str) -> str | None:
    """Where a moved file now is: the new plane-relative path for an old one, else None. Called by `CompanyPlane.path` for a missing path."""
    p = _aliases_path(root)
    try:
        m = p.stat().st_mtime
    except OSError:
        return None
    hit = _alias_cache.get(str(p))
    if hit is None or hit[0] != m:
        got = read_json_strict(p, dict) or {}
        hit = _alias_cache[str(p)] = (m, got)
    return hit[1].get(rel)


def _record_move(plane, old: str, new: str) -> None:
    p = _aliases_path(plane.root)
    with lock_for(p):
        m = read_json_strict(p, dict) or {}
        m = {k: (new if v == old else v) for k, v in m.items()}
        m[old] = new
        m.pop(new, None)  # a path that exists again must not alias (no self-alias, no loop)
        write_json_atomic(p, m)


def _base(item: dict) -> str:
    return f"projects/{item['project']}/files" if item.get("project") else "library"


def _owned(item: dict) -> bool:
    """A file the library (or a project folder) owns, as opposed to the company's own documents/ and landing/."""
    parts = PurePosixPath(str(item.get("path") or "")).parts
    return bool(parts) and (parts[0] == "library" or (parts[0] == "projects" and len(parts) >= 4 and parts[2] == "files"))


def rel_path(plane, item: dict, folder: str) -> str:
    """`library/<folder>/<id>__<name>`: the item id stays in the name, so a stored path can never open a later, different upload."""
    name = Path(str(item.get("name") or "file")).name
    return f"{_base(item)}/{folder}/{item['id']}__{name}"


def _raw(plane, rel: str) -> Path:
    """The path as written, never through an alias (an old path must not stand in for a new one)."""
    return plane.root.joinpath(*rel.split("/"))


def _place(plane, item: dict, folder: str) -> None:
    """Set the folder on the row and, for a file the library owns, move it there (and leave an alias for the old path)."""
    item["folder"] = folder
    if not _owned(item):
        return
    new, old = rel_path(plane, item, folder), item["path"]
    if new == old:
        return
    src, dst = _raw(plane, old), _raw(plane, new)
    if src.is_file() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        _record_move(plane, old, new)
        item.setdefault("was", old)
    elif not dst.is_file():  # neither is there (e.g. unreadable): the row keeps its path
        return
    item["path"] = new  # (dst already there and src gone: an interrupted earlier run moved it)


# ---- stamping a new upload -----------------------------------------------------------------------------------------------------------

def stamp(plane, item: dict, name: str, note: str, folder=None, folder_by=None) -> None:
    """At upload: the folder (the person's choice or the rules'), recorded and set as the file's path. The file is written by the caller."""
    prev = item.get("preview") or {}
    c = classify(name, prev.get("heading") or "", prev.get("columns"), note)
    if folder in FOLDERS and folder != c["folder"]:
        by = folder_by if folder_by in BY else "owner"
        item.update(folder=folder, folder_by="owner" if by == "rules" else by)
    else:
        item.update(folder=c["folder"], folder_by=c["by"])
    item["subfolder"] = c["subfolder"]
    item["path"] = rel_path(plane, item, item["folder"])


def move(plane, viewer, item_id: str, folder: str) -> dict:
    """The owner (or a company admin) moves an item to another folder; the move is recorded on the row."""
    if folder not in FOLDERS:
        raise Refused(400, "Choose one of the library's folders.")
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        item = L._find(plane, item_id, viewer)
        if not L.may_change(item, viewer):
            raise Refused(403, "Only the person who added this file can move it.")
        item = next(i for i in rows if i["id"] == item_id)
        if item.get("folder") != folder:
            before = item.get("folder") or ""
            _place(plane, item, folder)
            item.update(folder_by="owner", sorting=False)
            item.setdefault("folder_log", []).append({"from": before, "to": folder, "by": viewer.name, "at": _now()})
            write_json_atomic(L._index_path(plane), rows)
    return L.shown(item, viewer, plane)


# ---- the one-time sort of what is already there ---------------------------------------------------------------------------------------

_running: set[str] = set()
_guard = threading.Lock()


def ensure(plane, model=None) -> bool:
    """Sort every row without a folder (rules now; the unclear ones are `sorting` until Jev answers in a background batch) and move the
    files the library owns into their folders. Idempotent: a second call finds nothing to do. True while a batch is still running."""
    if all(r.get("folder") for r in L._index(plane)) and not any(r.get("sorting") for r in L._index(plane)):
        return False
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        todo = [r for r in rows if not r.get("folder")]
        for r in todo:
            c = _classify_item(plane, r)
            _place(plane, r, c["folder"])
            r.update(folder_by="rules", subfolder=c["subfolder"])
            if not c["sure"] and model is not None:
                r["sorting"] = True  # the list says "sorting…" until the background batch has answered
        if todo:
            write_json_atomic(L._index_path(plane), rows)
        pending = [r["id"] for r in rows if r.get("sorting")]
    if not pending:
        return False
    if model is None:
        settle(plane, None, pending)
        return False
    with _guard:
        key = str(plane.root)
        if key in _running:
            return True
        _running.add(key)
    threading.Thread(target=_batch, args=(plane, model, pending, key), daemon=True, name="l3-sort").start()
    return True


def _batch(plane, model, ids: list[str], key: str) -> None:
    try:
        settle(plane, model, ids)
    finally:
        with _guard:
            _running.discard(key)


def settle(plane, model, ids: list[str]) -> None:
    """Ask Jev (the fast tier) about each unclear row; an answer off the list or no model leaves the rules' folder. Clears `sorting`."""
    for iid in ids:
        row = next((r for r in L._index(plane) if r["id"] == iid), None)
        if row is None:
            continue
        cols, head = _shape(plane, row)
        topic = C.ask_topic(model, plane, str(row.get("name") or ""), cols, head) if model is not None else None
        with lock_for(L._index_path(plane)):
            rows = L._index(plane)
            r = next((x for x in rows if x["id"] == iid), None)
            if r is None or not r.get("sorting"):
                continue
            if topic and r.get("folder_by") == "rules":  # a person's move in the meantime stands
                _place(plane, r, folder_of_topic(topic))
                r["folder_by"] = "Jev"
            r["sorting"] = False
            write_json_atomic(L._index_path(plane), rows)


# ---- the folder view -----------------------------------------------------------------------------------------------------------------

def folders(plane, viewer, q: str = "") -> dict:
    """Folders with the counts of the items this viewer may see (the C4 listing: private items of others are not there), items inside."""
    by: dict[str, list] = {}
    sorting = False
    for i in L.listing(plane, viewer, q):
        sorting = sorting or bool(i.get("sorting"))
        by.setdefault(i.get("folder") if i.get("folder") in FOLDERS else "Other", []).append(i)
    out = [{"folder": f, "topic": f, "icon": ICONS[f], "count": len(by[f]), "items": by[f]} for f in FOLDERS if f in by]
    return {"folders": out, "sorting": sorting, "all": list(FOLDERS)}
