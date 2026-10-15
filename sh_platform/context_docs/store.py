"""The per-agent document store, inside the company's own plane (D-032).

Ported from `sh_platform/context/agent_docs.py` (upload, list, visibility, publish summary, delete, pending memories).
Changed for this product: plain JSON files under `context/agent_docs/<agent>/` through the shared jsonfile helpers
instead of DuckDB tables; no embeddings (retrieval.py scores keywords); no background thread (reading is quick);
no ingest run-registry row; company admins only change things, so the earlier owner-or-admin check is gone; the
original upload is not kept, only its text.
"""
import datetime as _dt
import logging
import re
import secrets
from pathlib import Path

from sh_platform.context_docs import reader
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)

AGENTS = ("north", "lens")  # a later agent is one more name here
VISIBILITIES = ("private", "shared", "shared_full")  # shared: others read the published summary only; shared_full: others read the full text (explicit choice only)
KINDS = ("fact", "decision", "preference", "correction")  # earlier agent_memory.KINDS
_DOC_ID = re.compile(r"[0-9a-f]{12}")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "chunks"}


class DocStore:
    def __init__(self, plane: CompanyPlane):
        self.plane = plane

    # -- paths
    def _folder(self, agent: str) -> Path:
        if agent not in AGENTS:
            raise FileNotFoundError("no such agent")
        return self.plane.path("context", "agent_docs", agent)

    def _file(self, agent: str, doc_id: str) -> Path:
        if not isinstance(doc_id, str) or not _DOC_ID.fullmatch(doc_id):
            raise FileNotFoundError("no such document")
        return self._folder(agent) / f"{doc_id}.json"

    def _read(self, agent: str, doc_id: str) -> dict:
        doc = read_json_strict(self._file(agent, doc_id), dict)
        if doc is None or doc.get("status") == "deleted":
            raise FileNotFoundError("no such document")
        return doc

    def _all(self, agent: str, *, with_deleted: bool = False) -> list[dict]:
        folder = self._folder(agent)
        docs = []
        for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            if not _DOC_ID.fullmatch(p.stem):
                continue  # pending.json and anything else that is not a document
            try:
                d = read_json_strict(p, dict)
            except (OSError, ValueError):
                log.warning("a context document could not be read and was skipped")
                continue
            if d and (with_deleted or d.get("status") != "deleted"):
                docs.append(d)
        return docs

    def _update(self, agent: str, doc_id: str, change) -> dict:
        path = self._file(agent, doc_id)
        with lock_for(path):
            doc = self._read(agent, doc_id)
            change(doc)
            doc["updated_at"] = _now()
            write_json_atomic(path, doc)
        return _public(doc)

    # -- documents
    def upload(self, agent: str, uploader: str, filename: str, data: bytes, *, title: str = "",
               description: str = "", visibility: str = "private", restricted: bool = False) -> dict:
        self._folder(agent)
        if visibility not in VISIBILITIES:
            raise reader.Refusal("Choose private or shared.")
        if not data:
            raise reader.Refusal("The file is empty.")
        if len(data) > reader.MAX_UPLOAD_BYTES:
            raise reader.Refusal(f"The file is {len(data) / 1e6:.1f} MB; the limit is "
                                 f"{reader.MAX_UPLOAD_BYTES // 1_000_000} MB.", 413)
        name = reader.safe_name(filename)
        segments = reader.read_segments(name, data)
        total = sum(len(t) for _, t in segments)
        remaining, chunks = reader.MAX_TEXT_CHARS, []
        for location, text in segments:  # each page or slide is chunked on its own so a chunk keeps its location
            if remaining <= 0:
                break
            kept = text[:remaining]
            remaining -= len(kept)
            chunks += [{"no": len(chunks) + i, "text": c, "location": location}
                       for i, c in enumerate(reader.chunk(kept))]
        if not chunks:
            raise reader.Refusal("That file has no text in it to read.")
        now = _now()
        doc = {"doc_id": secrets.token_hex(6), "agent": agent, "uploader": uploader,
               "title": title.strip()[:200] or name, "description": description.strip()[:2000], "filename": name,
               "visibility": visibility, "restricted": bool(restricted), "status": "ready", "shared_summary": None,
               "chars": sum(len(c["text"]) for c in chunks), "chars_total": total, "truncated": total > reader.MAX_TEXT_CHARS,
               "uploaded_at": now, "updated_at": now, "chunks": chunks}
        write_json_atomic(self._file(agent, doc["doc_id"]), doc)
        return _public(doc)

    def documents(self, agent: str) -> list[dict]:
        return sorted((_public(d) for d in self._all(agent)), key=lambda d: d["uploaded_at"], reverse=True)

    def get(self, agent: str, doc_id: str) -> dict:
        return _public(self._read(agent, doc_id))

    def set_visibility(self, agent: str, doc_id: str, visibility: str) -> dict:
        if visibility not in VISIBILITIES:
            raise reader.Refusal("Choose private or shared.")
        return self._update(agent, doc_id, lambda d: d.update(visibility=visibility))

    def set_restricted(self, agent: str, doc_id: str, restricted: bool) -> dict:
        """A restricted document (pay, HR) is read by no agent: retrieval never returns its text or its summary."""
        return self._update(agent, doc_id, lambda d: d.update(restricted=bool(restricted)))

    def publish_summary(self, agent: str, doc_id: str, summary: str) -> dict:
        """Only this short summary crosses to the other agents, never the document's text. Also marks the document "shared"
        (summary only); a document already "shared_full" stays as it is."""
        summary = (summary or "").strip()[:1000]
        if not summary:
            raise reader.Refusal("Say what the summary is.")
        return self._update(agent, doc_id, lambda d: d.update(shared_summary=summary, **({} if d.get("visibility") == "shared_full" else {"visibility": "shared", "visibility_set_at": _now()})))

    def delete(self, agent: str, doc_id: str) -> bool:
        """The record stays (the earlier soft delete); its text and summary are removed so nothing can be read back."""
        self._update(agent, doc_id, lambda d: d.update(status="deleted", chunks=[], shared_summary=None))
        return True

    # -- what retrieval reads
    def documents_for(self, agent: str, *, restricted_ok: bool = False) -> list[dict]:
        """THE rule for who reads what. The agent's own documents in full; other agents' "shared_full" documents in
        full; other agents' "shared" documents as summary-only records (no chunks). A record without a visibility is
        private. Restricted documents (pay, HR) only with restricted_ok. Records include chunks; never send them to a screen."""
        out = []
        for a in AGENTS:
            for d in self._all(a):
                if d.get("restricted") and not restricted_ok:
                    continue
                v = d.get("visibility", "private")
                if a == agent or v == "shared_full":
                    out.append(d)
                elif v == "shared" and d.get("shared_summary"):
                    out.append({**d, "chunks": []})
        return out

    def own_chunks(self, agent: str) -> list[dict]:
        return [{"title": d["title"], "text": c["text"], "location": c.get("location"), "source": "own_document"}
                for d in self.documents_for(agent) for c in d.get("chunks", [])]

    def shared_summaries(self, agent: str) -> list[dict]:
        """Published summaries of every OTHER agent's "shared" documents."""
        return [{"title": d["title"], "text": d["shared_summary"], "location": None, "source": "shared_summary"}
                for d in self.documents_for(agent) if d["agent"] != agent and d.get("visibility") == "shared"]

    # -- pending memories: facts a conversation extracted, held until a company admin decides
    def _pending_path(self, agent: str) -> Path:
        return self._folder(agent) / "pending.json"

    def list_pending(self, agent: str, status: str | None = "pending") -> list[dict]:
        rows = read_json_strict(self._pending_path(agent), list) or []
        return [r for r in reversed(rows) if status is None or r["status"] == status]

    def stage_pending(self, agent: str, kind: str, subject: str, content: str, source: str,
                      session_id: str | None = None) -> int:
        if kind not in KINDS:
            raise reader.Refusal("That kind of memory is not known.")
        path = self._pending_path(agent)
        with lock_for(path):
            rows = read_json_strict(path, list) or []
            pid = max((r["pending_id"] for r in rows), default=0) + 1
            rows.append({"pending_id": pid, "agent": agent, "kind": kind, "subject": subject, "content": content,
                         "source": source, "session_id": session_id, "status": "pending", "created_at": _now(),
                         "decided_at": None, "decided_by": None})
            write_json_atomic(path, rows)
        return pid

    def decide_pending(self, agent: str, pending_id: int, decision: str, decided_by: str, *, subject: str | None = None,
                       content: str | None = None, kind: str | None = None) -> dict:
        """Accept (optionally editing first) or reject. An accepted memory becomes a passage retrieval can find."""
        if decision not in ("accept", "reject"):
            raise reader.Refusal("Choose accept or reject.")
        path = self._pending_path(agent)
        with lock_for(path):
            rows = read_json_strict(path, list) or []
            row = next((r for r in rows if r["pending_id"] == pending_id), None)
            if row is None:
                raise FileNotFoundError("no such memory")
            if row["status"] != "pending":
                raise reader.Refusal(f"That memory was already {row['status']}.", 409)
            if decision == "accept":
                row.update(kind=(kind or row["kind"]).strip(), subject=(subject or row["subject"]).strip(),
                           content=(content or row["content"]).strip())
                if row["kind"] not in KINDS:
                    raise reader.Refusal("That kind of memory is not known.")
            row.update(status="accepted" if decision == "accept" else "rejected", decided_at=_now(), decided_by=decided_by)
            write_json_atomic(path, rows)
        return row

    def accepted_memories(self, agent: str) -> list[dict]:
        return [{"title": r["subject"], "text": r["content"], "location": None, "source": "memory"}
                for r in self.list_pending(agent, "accepted")]


def documents_for(plane: CompanyPlane, agent: str, restricted_ok: bool = False) -> list[dict]:
    return DocStore(plane).documents_for(agent, restricted_ok=restricted_ok)
