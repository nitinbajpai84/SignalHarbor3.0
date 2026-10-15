"""Memory routes (MEM-2): a person reads, corrects or deletes what an agent remembers about them; a company admin does the same for company memory.
Files: context/memory/<agent>/people/<pid>.json and context/memory/<agent>/company.json (docs/plan/SHAPES.md 9). The person is the profile person
linked to the signed-in account (A-043); no link, no entries. Another person's file is never named by the request, only found by the link."""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.memory import filters
from sh_platform.profile import links, store, view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
AGENTS = ("north", "lens", "nira", "span", "flow")
KINDS = ("fact", "preference", "decision", "open")
BUDGET = 4000
MAX_TEXT = 500


def _agent(agent: str) -> str:
    a = agent.lower()
    if a not in AGENTS:
        raise HTTPException(404, "We could not find that agent.")
    return a


def _open(request: Request):
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, "You cannot open this company space.") from None


def person_id(plane, account_id: str | None) -> str | None:
    """The profile person linked to this account, or None."""
    if not account_id:
        return None
    people = store.load(plane).get("people") or {}
    return next((k for k, p in people.items() if links._account_of(p) == account_id), None)


def tomb_hash(text: str) -> str:
    """The tombstone key: hash of the normalised text. Closure memory checks the same key before it writes a line."""
    return hashlib.sha1(view.norm(text).encode()).hexdigest()


def _read(path: Path) -> dict:
    try:
        doc = read_json_strict(path, dict)
    except (OSError, ValueError):
        log.warning("a memory file could not be read")
        raise HTTPException(500, "That memory could not be read.") from None
    return doc or {"entries": [], "budget": BUDGET}


def _merge(old: dict, sent: object) -> dict:
    """The sent list becomes the file: a changed or new entry is marked as the person's (never overwritten by the agent later); an entry left out is deleted."""
    if not isinstance(sent, list):
        raise HTTPException(422, "Send the list of entries.")
    before = {e.get("id"): e for e in filters.tidy([e for e in old.get("entries", []) if isinstance(e, dict)])}  # what the person was shown
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for s in sent:
        text = str(s.get("text") or "").strip()[:MAX_TEXT] if isinstance(s, dict) else ""
        if not text:
            raise HTTPException(422, "An entry cannot be empty.")
        prev = before.get(s.get("id"))
        kind = s.get("kind") if s.get("kind") in KINDS else (prev or {}).get("kind", "fact")
        if prev and prev.get("text") == text and prev.get("kind") == kind:
            out.append(prev)
        else:
            out.append({"id": (prev or {}).get("id") or uuid.uuid4().hex[:12], "kind": kind, "text": text,
                        "from": (prev or {}).get("from", []), "updated_at": now, "by": "person"})
    kept = {e["id"] for e in out}
    tombs = [*old.get("deleted", []), *({"hash": tomb_hash(e["text"]), "at": now} for i, e in before.items() if i not in kept)]
    return {**old, "entries": out, "deleted": list({t["hash"]: t for t in tombs}.values()), "budget": old.get("budget", BUDGET)}


def _save(path: Path, body: object) -> dict:
    with lock_for(path):
        doc = _merge(_read(path), (body or {}).get("entries") if isinstance(body, dict) else None)
        write_json_atomic(path, doc)
    return doc


async def _body(request: Request) -> object:
    try:
        return await request.json()
    except ValueError:
        raise HTTPException(422, "Send the list of entries.") from None


def _mine(request: Request, agent: str) -> Path | None:
    plane = _open(request)
    pid = person_id(plane, _viewer(request).account_id)
    return plane.path("context", "memory", _agent(agent), "people", f"{pid}.json") if pid else None


def _company(request: Request, agent: str) -> Path:
    if "company_admin" not in (request.state.roles or []):
        raise HTTPException(403, "Only a company admin can open the company memory.")
    return _open(request).path("context", "memory", _agent(agent), "company.json")


@router.get("/api/memory/me/{agent}")
def get_api_memory_me_agent(request: Request, agent: str):
    path = _mine(request, agent)
    doc = _read(path) if path else {"entries": [], "budget": BUDGET}
    return {**doc, "entries": filters.tidy(doc["entries"])}


@router.put("/api/memory/me/{agent}")
async def put_api_memory_me_agent(request: Request, agent: str):
    path = _mine(request, agent)
    if not path:
        raise HTTPException(404, "Your account is not linked to a person yet, so nothing is remembered about you.")
    return _save(path, await _body(request))


@router.delete("/api/memory/me/{agent}")
def delete_api_memory_me_agent(request: Request, agent: str):
    path = _mine(request, agent)
    if path:
        with lock_for(path):
            path.unlink(missing_ok=True)
    return {"entries": [], "budget": BUDGET}


@router.get("/api/company/memory/{agent}")
def get_api_company_memory_agent(request: Request, agent: str):
    return _read(_company(request, agent))


@router.put("/api/company/memory/{agent}")
async def put_api_company_memory_agent(request: Request, agent: str):
    return _save(_company(request, agent), await _body(request))
