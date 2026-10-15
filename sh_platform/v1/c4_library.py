"""C4 The context library: one folder, one index, everything North, Span, Flow and Lumen may read.

`library/files/<id>__<name>` plus `library/index.json` (a list of items, see V1-BUILD Round 5). An item is the uploader's own
(`private`) until they share it with the company. The first read imports the company's `documents/*` files and `landing/<folder>`
sample folders once, as `company` items uploaded by "Seeded" (a folder item points at the folder; nothing is copied).
Each conversation ticks the items it may use in `intents/<iid>/context.json` {library_ids, by, at}; the agents read only
`selected(plane, iid, viewer)`, which never returns an item the viewer may not see, whatever ids the list holds.
Upload checks are I2's (`i2_north.checked_name`); previews are `file_context.preview_for_agent`.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

from sh_platform.context_docs import reader
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import i2_north as N

Refused = N.Refused
SEEDED = "Seeded"
KINDS = ("sample", "document", "external", "picture")
EXTERNAL = re.compile(r"\b(?:external|third[- ]party|market|benchmark)\b", re.I)
_STOP = {"the", "a", "an", "and", "of", "for", "to", "in", "on", "file", "files", "this", "that", "is", "it", "my", "our",
         "csv", "xlsx", "tsv", "md", "txt", "pdf", "docx", "sample", "data", "document", "what", "with", "from"}
MAX_SUGGEST = 5
MAX_NOTE = 300
NOT_FOUND = "We could not find that file in the library."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _index_path(plane):
    return plane.path("library", "index.json")


def _words(text: str) -> set[str]:
    """Letters only: dates and numbers drop out, so 'pack-2026-08.xlsx' and 'Pack 2025 07.xlsx' share a stem."""
    return {w for w in re.findall(r"[a-z]+", str(text or "").lower()) if len(w) > 1 and w not in _STOP}


def _stem(name: str) -> set[str]:
    return _words(name.rsplit(".", 1)[0] if "." in name else name)


def _seed(plane) -> list[dict]:
    """The one-time import: documents become company documents, landing folders company samples (the loader's `_b4_` files skipped)."""
    items = []
    docs, land = plane.path("documents"), plane.path("landing")
    for p in sorted(docs.iterdir()) if docs.is_dir() else []:
        if p.is_file() and not p.name.startswith("."):
            data = p.read_bytes()
            items.append(_item(p.name, "document", "", SEEDED, "", hashlib.sha256(data).hexdigest(), len(data), "company", f"documents/{p.name}"))
    for d in sorted(land.iterdir()) if land.is_dir() else []:
        if d.is_dir() and not d.name.startswith(("_", ".")):
            size = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
            items.append(_item(d.name.replace("_", " "), "sample", "", SEEDED, "", "", size, "company", f"landing/{d.name}"))
    return items


def _item(name, kind, note, by, by_id, sha, size, visibility, path) -> dict:
    return {"id": f"lib_{secrets.token_hex(6)}", "name": name, "kind": kind, "note": note, "uploaded_by": by,
            "uploaded_by_id": by_id, "at": _now(), "sha256": sha, "size": size, "visibility": visibility, "path": path, "tags": []}


def _index(plane) -> list[dict]:
    """The index, imported on first read (idempotent: the import runs only while there is no index file)."""
    path = _index_path(plane)
    got = read_json_strict(path, list)
    if got is not None:
        return got
    with lock_for(path):
        got = read_json_strict(path, list)
        if got is None:
            got = _seed(plane)
            write_json_atomic(path, got)
    return got


def ensure(plane) -> None:
    _index(plane)


def _admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


def _mine(item: dict, viewer) -> bool:
    return bool(viewer is not None and getattr(viewer, "account_id", None) and item.get("uploaded_by_id") == viewer.account_id)


def visible(item: dict, viewer) -> bool:
    """The uploader sees their own; everyone sees what is shared with the company. No viewer: shared items only."""
    if item.get("visibility") == "project":  # G1: a restricted project's file is there only for its team and grantees
        from sh_platform.v1 import k1_access as K
        return _mine(item, viewer) or K.granted(item, viewer)
    return item.get("visibility") == "company" or _mine(item, viewer)


def may_change(item: dict, viewer) -> bool:
    return visible(item, viewer) and (_mine(item, viewer) or _admin(viewer))


def readable(item: dict, viewer) -> bool:
    """K1: visible and (mine, open or granted). Agents and ticks go through this, not `visible`."""
    from sh_platform.v1 import k1_access as K
    return visible(item, viewer) and K.can_read(item, viewer)


def shown(item: dict, viewer, plane=None) -> dict:
    from sh_platform.v1 import k1_access as K  # K1: sensitivity, topic, the viewer's access state; a locked item is cut to its preview
    out = {k: v for k, v in item.items() if k not in ("uploaded_by_id", "pii", "grants")}
    out["mine"], out["can_change"] = _mine(item, viewer), may_change(item, viewer)
    out.update(K.fields(item, viewer, K.requests(plane) if plane is not None else None))
    return out if K.can_read(item, viewer) else K.lock(out)


def listing(plane, viewer, q: str = "") -> list[dict]:
    words = str(q or "").lower().split()

    def hay(i):  # the note of an item the viewer cannot read is not searched (it would leak through the results)
        parts = [i["name"], " ".join(i.get("topic") or []), i.get("uploaded_by") or ""]
        return " ".join(parts + [i.get("note") or ""] if readable(i, viewer) else parts).lower()
    return [shown(i, viewer, plane) for i in _index(plane) if visible(i, viewer) and all(w in hay(i) for w in words)]


def path_ok(plane, rel: str, viewer=None, check: bool = False) -> bool:
    """A stored path under library/ or projects/<p>/files/ is only good while an index row owns it (and, with `check`, the viewer may read
    that row): a path left behind by a deleted upload opens nothing. Other paths (documents/, landing/, the intent's own) are not judged here."""
    from sh_platform.v1 import l3_library as F
    parts = str(rel).replace("\\", "/").split("/")
    if not (parts[0] == "library" or (parts[0] == "projects" and len(parts) >= 4 and parts[2] == "files")):
        return True
    now = F.alias(plane.root, rel)
    row = next((i for i in _index(plane) if i.get("path") in (rel, now)), None)
    return row is not None and (not check or readable(row, viewer))


def _find(plane, item_id: str, viewer) -> dict:
    item = next((i for i in _index(plane) if i["id"] == item_id), None)
    if item is None or not visible(item, viewer):
        raise Refused(404, NOT_FOUND)  # someone else's private item is not there, as far as this viewer knows
    return item


def _kind(name: str, kind: str | None, note: str) -> str:
    if reader.ext_of(name) in reader.PICTURE_TYPES:
        return "picture"
    if kind == "external" or EXTERNAL.search(note):
        return "external"
    if kind in ("sample", "document"):
        return kind if kind == "document" or reader.ext_of(name) in N.SAMPLE_EXT else "document"
    return "sample" if reader.ext_of(name) in N.SAMPLE_EXT else "document"


def _note(note) -> str:
    return " ".join(str(note or "").split())[:MAX_NOTE]


def upload(plane, viewer, filename: str, data: bytes, *, kind: str | None = None, note: str = "", share: bool = False,
           iid: str | None = None, force: bool = False, sensitivity: str | None = None, topic: list | None = None,
           reviewed: bool = False, model=None, folder: str | None = None, folder_by: str | None = None) -> dict:
    """{item} when stored; {duplicate} when a visible item has the same bytes (nothing stored); {similar: [...]} when a visible
    item has a similar name or note (nothing stored in either case until the person says upload anyway: `force`)."""
    name = N.checked_name(filename, data)
    note = _note(note)
    if iid:
        _context_path(plane, iid)  # the conversation must exist before anything is stored for it
    sha = hashlib.sha256(data).hexdigest()
    seen = [i for i in _index(plane) if visible(i, viewer) and readable(i, viewer)]  # K1: a locked item is never matched (no oracle)
    if not force:
        dup = next((i for i in seen if i.get("sha256") == sha), None)
        if dup is not None:
            return {"duplicate": {k: dup[k] for k in ("id", "name", "uploaded_by", "at")}}
        stem, nw = _stem(name), _words(note)
        similar = [i for i in seen if (stem and _stem(i["name"]) == stem) or (nw and _words(i.get("note")) == nw)]
        if similar:
            return {"similar": [{**{k: i[k] for k in ("id", "name", "uploaded_by", "at")}, "note": i["note"] if readable(i, viewer) else ""}
                                for i in similar[:MAX_SUGGEST]]}
    item = _item(name, _kind(name, kind, note), note, viewer.name or "A team member", viewer.account_id, sha, len(data),
                 "company" if share else "private", "")
    item["path"] = f"library/files/{item['id']}__{name}"
    from sh_platform.v1 import k1_access as K  # K1: owner's sensitivity and topic; personal data forces Restricted
    K.stamp(plane, item, viewer, name, data, note, sensitivity, topic, reviewed, model)
    from sh_platform.v1 import l3_library as F  # L3: the folder (the person's choice or the rules'), and the path inside it
    F.stamp(plane, item, name, note, folder, folder_by)
    p = plane.path(*item["path"].split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    with lock_for(_index_path(plane)):
        rows = _index(plane)
        rows.append(item)
        write_json_atomic(_index_path(plane), rows)
    from sh_platform.v1 import doc_index
    doc_index.index_later(plane, item["path"])  # a scan or a picture is read for search now, in the background, not inside a reply
    if iid:
        tick(plane, iid, viewer, [item["id"]])
    out = {"item": shown(item, viewer, plane)}
    if unread_text(name, data):
        out["message"] = "Stored. " + reader.NO_READER_MSG
    return out


def unread_text(name: str, data: bytes) -> bool:
    """A picture or PDF whose text cannot be read on this machine (no picture reader): stored by name only."""
    if reader.ext_of(name) not in reader.PICTURE_TYPES | {"pdf"}:
        return False
    try:
        reader.read_segments(name, data, ocr_pages=1, ocr_seconds=2.0)
    except reader.Refusal as e:
        return reader.NO_READER_MSG in str(e)
    return False


def change(plane, viewer, item_id: str, body: dict) -> dict:
    """The uploader (or a company admin) edits the note, the kind or the visibility."""
    with lock_for(_index_path(plane)):
        rows = _index(plane)
        item = _find(plane, item_id, viewer)
        if not may_change(item, viewer):
            raise Refused(403, "Only the person who added this file can change it.")
        item = next(i for i in rows if i["id"] == item_id)
        if "note" in body:
            item["note"] = _note(body["note"])
        if body.get("kind") in KINDS:
            item["kind"] = body["kind"]
        if "visibility" in body:
            if body["visibility"] not in ("private", "company"):
                raise Refused(400, "Choose private or shared with the company.")
            if body["visibility"] == "private" and not item.get("uploaded_by_id"):
                raise Refused(409, "This file came with the company's own documents and stays shared.")
            item["visibility"] = body["visibility"]
        if "sensitivity" in body or "topic" in body:  # K1: the owner's call
            from sh_platform.v1 import k1_access as K
            K.edit(item, viewer, body)
        write_json_atomic(_index_path(plane), rows)
    return shown(item, viewer, plane)


def delete(plane, viewer, item_id: str) -> None:
    """Removes the index row and the library's own copy; files in `documents/` or `landing/` (which scans and loads read) stay."""
    with lock_for(_index_path(plane)):
        rows = _index(plane)
        item = _find(plane, item_id, viewer)
        if not may_change(item, viewer):
            raise Refused(403, "Only the person who added this file can delete it.")
        write_json_atomic(_index_path(plane), [i for i in rows if i["id"] != item_id])
    from sh_platform.v1 import l3_library as F  # L3: the library's own files sit in folders now
    if F._owned(item) and item["path"].startswith("library/"):
        plane.path(*item["path"].split("/")).unlink(missing_ok=True)
        from sh_platform.v1 import doc_index
        doc_index.forget(plane, item["path"])


# ---- the selection per conversation ------------------------------------------------------------------------------------------------

def _context_path(plane, iid: str):
    if not S.ID_RE.fullmatch(str(iid)) or not plane.path("intents", iid).is_dir():
        raise Refused(404, S.NOT_FOUND)
    return plane.path("intents", iid, "context.json")


def _ids(plane, iid: str) -> list[str]:
    """The ticked ids. L3: nothing is ticked for the person; a conversation reads what was uploaded in it or ticked."""
    if not S.ID_RE.fullmatch(str(iid)):
        return []  # no conversation of that name: nothing ticked
    rec = read_json_strict(plane.path("intents", iid, "context.json"), dict)
    return [str(x) for x in (rec or {}).get("library_ids") or []]


def selected(plane, iid: str, viewer) -> list[dict]:
    """The items ticked for this conversation that the viewer may see; nothing else, whatever ids the list holds."""
    ids = _ids(plane, iid)
    rows = {i["id"]: i for i in _index(plane)}
    return [rows[x] for x in dict.fromkeys(ids) if x in rows and readable(rows[x], viewer)]


def save_ids(plane, iid: str, viewer, ids: list) -> list[dict]:
    """Replaces the viewer's part of the list: ids the viewer cannot see (someone else's private ticks) are kept as they were."""
    path = _context_path(plane, iid)
    with lock_for(path):
        rows = {i["id"]: i for i in _index(plane)}
        hidden = [x for x in _ids(plane, iid) if x in rows and not readable(rows[x], viewer)]
        mine = [str(x) for x in ids if str(x) in rows and readable(rows[str(x)], viewer)]
        write_json_atomic(path, {"library_ids": list(dict.fromkeys(hidden + mine)), "by": viewer.name, "at": _now()})
    return [shown(i, viewer, plane) for i in selected(plane, iid, viewer)]


def tick(plane, iid: str, viewer, ids: list[str]) -> None:
    save_ids(plane, iid, viewer, [i["id"] for i in selected(plane, iid, viewer)] + list(ids))


def suggestions(plane, iid: str, viewer) -> list[dict]:
    """Up to five visible, unticked items whose name or note shares a word with the intent's goal. Never ticked here."""
    sow = read_json_strict(_context_path(plane, iid).with_name("sow.json"), dict) or {}
    goal = sow.get("goal") or {}
    words = _words(" ".join(str(x or "") for x in (sow.get("title"), goal.get("line"), goal.get("why"))))
    ticked = {i["id"] for i in selected(plane, iid, viewer)}
    hits = [(len(words & _words(f"{i['name']} {i.get('note')}")), n, i) for n, i in enumerate(_index(plane))
            if readable(i, viewer) and i["id"] not in ticked]
    return [shown(i, viewer, plane) for k, _, i in sorted((h for h in hits if h[0]), key=lambda h: (-h[0], h[1]))[:MAX_SUGGEST]]


# ---- what the agents read ----------------------------------------------------------------------------------------------------------

def as_files(plane, items: list[dict]) -> list[dict]:
    """File records ({name, path, kind}) for the previews and the scan. A sample folder reads as its first table file."""
    out = []
    for i in items:
        p = plane.path(*i["path"].split("/"))
        if p.is_dir():
            first = next((f for f in sorted(p.iterdir()) if f.is_file() and reader.ext_of(f.name) in N.SAMPLE_EXT
                          and not f.name.startswith("_")), None)
            if first is None:
                continue
            out.append({"name": first.name, "path": f"{i['path']}/{first.name}", "kind": "sample"})
        else:
            out.append({"name": i["name"], "path": i["path"],
                        "kind": "sample" if reader.ext_of(i["name"]) in N.SAMPLE_EXT else "document"})
    return out


def lines(plane, iid: str, viewer) -> list[str]:
    """One flat line per ticked item the viewer may see (file_context's preview), with what the person said it is."""
    from sh_platform.v1.file_context import preview_for_agent
    out = []
    for item in selected(plane, iid, viewer):
        for line in preview_for_agent(plane, iid, as_files(plane, [item])):
            out.append(f"{item['note']}. {line}" if item.get("note") else line)
    return out
