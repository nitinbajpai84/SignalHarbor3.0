"""I1 Company page: who we are, systems, policies, documents, and when North last read it.

Who we are and systems live in the 2.0 profile store (`profile.json`, provenance cells; a person's edit is `stated`, from "Company page").
Policies are new and sit in their own file, `context/company/page.json` `{policies: [{kind, text, stated_by, at}], north_read_at}`.
Documents are the plain files in `data/<company>/documents/` (D2's folder, where North and the catalogue scan I5 read) plus North's
documents in the 2.0 context_docs store. An upload through the page is checked by the context_docs reader and saved into that folder.
I2 calls `for_north(plane)` to read the page and `mark_read(plane)` after North has read it.
"""
from datetime import datetime, timezone
from typing import Any

from sh_platform.context_docs import reader as docreader
from sh_platform.context_docs.store import DocStore
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store, view

WHO = ("name", "about", "time_zone", "currency")
SYSTEM = ("name", "kind", "owner", "lands", "frequency")
POLICY_KINDS = ("access", "retention", "approval", "other")  # the SOW governance kinds, plus other
SOURCE = "Company page"
AGENT = "north"


class Refusal(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _page_file(plane: CompanyPlane):
    return plane.path("context", "company", "page.json")


def _page(plane: CompanyPlane) -> dict:
    return read_json_strict(_page_file(plane), dict) or {"policies": [], "north_read_at": None}


def _v(c: Any) -> Any:
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _who(doc: dict) -> dict:
    co = doc.get("company") or {}
    return {k: {"value": _v(co.get(k)), "by": (co.get(k) or {}).get("by"), "at": (co.get(k) or {}).get("at")} for k in WHO}


def _systems(seen: dict) -> list[dict]:
    out = []
    for sid, s in seen.items():
        if s.get("restricted") is True and "label" in s:  # view.SHUT_SOURCE: shown as a stub, no name
            out.append({"id": sid, "restricted": True, "name": s["label"]})
        else:
            out.append({"id": sid, **{f: _v(s.get(f)) for f in SYSTEM}})
    return out


def read(plane: CompanyPlane, viewer: view.Viewer) -> dict:
    page = _page(plane)
    admin = "company_admin" in viewer.roles
    docs = _folder_docs(plane) + [{k: d.get(k) for k in ("doc_id", "title", "filename", "uploaded_at", "restricted")}
                                  for d in DocStore(plane).documents(AGENT) if admin or not d.get("restricted")]
    return {"who": _who(store.raw(plane)), "systems": _systems(view.read(plane, viewer)["systems"]),
            "policies": page["policies"], "documents": docs, "north_read_at": page.get("north_read_at"),
            "policy_kinds": list(POLICY_KINDS), "accepted": docreader.allowed_extensions(),
            "max_mb": docreader.MAX_UPLOAD_BYTES // (1024 * 1024)}


def _text(v: Any, limit: int = 2000) -> str:
    if v is not None and not isinstance(v, str):
        raise Refusal("Each value must be text.")
    return " ".join((v or "").split())[:limit]


def _slug(name: str, taken) -> str:
    base = "-".join("".join(ch if ch.isalnum() else " " for ch in name.lower()).split())[:60] or "system"
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}-{n}", n + 1
    return sid


def save(plane: CompanyPlane, by: str, body: dict) -> None:
    """Writes only what changed. A person's edit is stated; an empty value is cleared to unknown."""
    who, systems, policies = body.get("who"), body.get("systems"), body.get("policies")
    if who is not None and not isinstance(who, dict) or systems is not None and not isinstance(systems, list) \
            or policies is not None and not isinstance(policies, list):
        raise Refusal("That could not be saved. Please try again.")
    prov = {"mark": "stated", "by": by, "from": SOURCE}
    clear = {"mark": "unknown", "by": by, "from": SOURCE}

    def change(doc: dict) -> None:
        co = doc.setdefault("company", {})
        for k, v in (who or {}).items():
            if k not in WHO:
                raise Refusal("That is not part of the company page.")
            v = _text(v)
            if v != (_v(co.get(k)) or ""):
                co[k] = store.cell(v or None, prov if v else clear)
        for row in systems or []:
            if not isinstance(row, dict):
                raise Refusal("That could not be saved. Please try again.")
            sid = row.get("id")
            if sid is None:
                name = _text(row.get("name"), 200)
                if not name:
                    raise Refusal("A new system needs a name.")
                sid = _slug(name, doc["systems"])
            elif sid not in doc["systems"]:
                raise Refusal("We could not find that system.")
            item = doc["systems"].get(sid, {})
            for f in SYSTEM:
                if f not in row:
                    continue
                v = _text(row[f], 200)
                if v != (_v(item.get(f)) or ""):
                    if store.set_cell(doc, f"systems.{sid}.{f}", v or None, prov if v else clear) is None:
                        raise Refusal("That system could not be changed.")
    if who or systems:
        store.mutate(plane, change)

    if policies is not None:
        clean = []
        for p in policies:
            if not isinstance(p, dict) or p.get("kind") not in POLICY_KINDS:
                raise Refusal("Pick a kind for each policy: access, retention, approval or other.")
            text = _text(p.get("text"))
            if text:
                clean.append((p["kind"], text))
        path = _page_file(plane)
        with lock_for(path):
            page = _page(plane)
            old = {(p["kind"], p["text"]): p for p in page["policies"]}  # an unchanged line keeps who stated it and when
            page["policies"] = [old.get(k) or {"kind": k[0], "text": k[1], "stated_by": by, "at": _now()} for k in dict.fromkeys(clean)]
            write_json_atomic(path, page)


def _folder(plane: CompanyPlane):
    return plane.path("documents")


def _folder_docs(plane: CompanyPlane) -> list[dict]:
    folder = _folder(plane)
    files = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")) if folder.is_dir() else []
    return [{"doc_id": p.name, "title": p.name, "filename": p.name, "restricted": False,
             "uploaded_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()} for p in files]


def upload(plane: CompanyPlane, filename: str, data: bytes) -> dict:
    """Checked like a context_docs upload (type, size, has text), then saved whole into the documents folder. Never overwrites."""
    if not data:
        raise docreader.Refusal("The file is empty.")
    if len(data) > docreader.MAX_UPLOAD_BYTES:
        raise docreader.Refusal(f"The file is too large. The limit is {docreader.MAX_UPLOAD_BYTES // 1_000_000} MB.", 413)
    name = docreader.safe_name(filename)
    if not any(t.strip() for _, t in docreader.read_segments(name, data)):
        raise docreader.Refusal("That file has no text in it to read.")
    path = plane.path("documents", name)
    with lock_for(path):
        if path.exists():
            raise docreader.Refusal("A document with that name is already there. Rename the file and try again.", 409)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return next(d for d in _folder_docs(plane) if d["filename"] == name)


def mark_read(plane: CompanyPlane) -> str:
    """For I2: North has read the company page now."""
    path = _page_file(plane)
    with lock_for(path):
        page = _page(plane)
        page["north_read_at"] = _now()
        write_json_atomic(path, page)
    return page["north_read_at"]


def for_north(plane: CompanyPlane) -> dict:
    """For I2: the page as North may read it (no restricted systems or documents). Document text: the files in `documents/` and North's context_docs."""
    page = read(plane, view.NOBODY)
    return {k: page[k] for k in ("who", "systems", "policies", "documents")}
