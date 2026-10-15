"""The charter's files in the company plane (M1-24 to M1-27, M1-30).

intents/m1_intent/charters/<session id>.json   every version of the charter, and the approver links (hashes only)
intents/m1_intent/outcomes/<outcome id>.json   the outcome record module 2 reads (written once, at sign-off)
intents/m1_intent/together/<session id>.json   STAND-IN for M1-P07's together-stage result: see together_result()

An approver link is "ap-<session id>-<secret>" (no dots: the page address /approve/<link> must not look like a file name to the web server). Only its SHA-256 hash is stored. It belongs to one session and one
version, expires, and is used up by the approver's decision (approve or decline). Nothing here logs or raises a token.
Locks are the module's own directory lock, so a charter move and its session move happen together (one process, A-015).
"""
import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import handoff as H
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import notes as N
from modules.m1_intent.store.files import UNREADABLE, StoreError, WrongState, lock_for, read_json, write_json
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.process_record import ProcessRecordError, ProcessRecords

log = logging.getLogger(__name__)
_HEX32 = re.compile(r"[0-9a-f]{32}")
TOKEN = re.compile(r"ap-([0-9a-f]{32})-([A-Za-z0-9_-]{43})")
_DOC_KEYS = {"session_id", "versions", "links"}
_LINK_KEYS = {"hash", "version", "issued_at", "expires_at", "state"}
_LINK_STATES = ("open", "used", "revoked")
_GONE = {"used": "This link has already been used.", "revoked": "This link was withdrawn. Please ask for a new one.",
         "expired": "This link has expired. Please ask for a new one.", "replaced": "This link is for an earlier draft. Please ask for a new one."}


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def together_result(plane, session_id):
    """The room's result for this session in the contracts/charter.yaml `together_result` shape, or None before the
    together stage has a board. Reads M1-P07's read_together_result and maps it: ticked clusters carry their vote
    tally's priority; carried ones go in unticked (they are the problems left for later)."""
    if not (isinstance(session_id, str) and _HEX32.fullmatch(session_id)):
        return None
    from modules.m1_intent.domain.together import read_together_result  # M1-P07; imported here to keep the store light
    r = read_together_result(plane, session_id)
    if not r["ticked"] and not r["carried"] and not r.get("parked"):
        return None
    from modules.m1_intent.store.notes import NoteStore
    records = {n["id"]: n for n in B.mask_sealed(plane, NoteStore(plane).board(session_id))}
    spec = N.load_fields()

    def kind_and_details(c: dict) -> dict:
        notes = [records[i] for i in c.get("note_ids", []) if i in records]
        kind = N.cluster_kind([N.kind_of(n) for n in notes])  # a group of one kind is listed under it; the kinds are never merged
        return {"kind": kind, "details": N.details(spec, kind, notes)}
    ticked = [{"id": c["id"], "title": c["name"], "priority": c["priority"], "note_count": c["note_count"],
               "agree_count": c["agree_count"], "ticked": True, "votes": c["votes"], **kind_and_details(c)} for c in r["ticked"]]
    carried = [{"id": c["id"], "title": c["name"], "priority": None, "note_count": c["note_count"],
                "agree_count": 0, "ticked": False} for c in r["carried"]]
    return {"clusters": ticked + carried}


def cluster_notes(plane, session_id) -> dict[str, list[str]]:
    """The words of the notes in each ticked cluster (public records only: no author), by cluster id."""
    if not (isinstance(session_id, str) and _HEX32.fullmatch(session_id)):
        return {}
    from modules.m1_intent.domain.together import read_together_result
    from modules.m1_intent.store.notes import NoteStore
    try:
        text = {n["id"]: n["text"] for n in B.mask_sealed(plane, NoteStore(plane).board(session_id))}
        return {c["id"]: [text[i] for i in c["note_ids"] if i in text] for c in read_together_result(plane, session_id)["ticked"]}
    except StoreError:  # no readable board: nothing to draft from; the charter itself is drafted from the result as before
        return {}


def notes_on_their_own(plane, session_id) -> list[dict]:
    """The submitted notes that sit in no group on the board, for "Left for later" on the charter: {"text"}, with text
    None for an anonymous note (the charter shows a count only; never a name of anyone)."""
    if not (isinstance(session_id, str) and _HEX32.fullmatch(session_id)):
        return []
    from modules.m1_intent.store.board import BoardStore
    from modules.m1_intent.store.notes import NoteStore
    try:
        inside = {i for c in BoardStore(plane).get(session_id)["clusters"] for i in c["note_ids"]}
        return [{"text": None if n.get("anonymous") and not n.get("sealed") else n["text"], "kind": n["kind"],
                 **({"author_name": n["author_name"]} if not n.get("anonymous") and n.get("author_name") else {})}
                for n in B.mask_sealed(plane, NoteStore(plane).board(session_id)) if n["id"] not in inside]
    except StoreError:
        return []


def read_outcome(plane, outcome_id) -> dict | None:
    """What module 2 calls: the outcome record of a signed charter, or None."""
    if not (isinstance(outcome_id, str) and _HEX32.fullmatch(outcome_id)):
        return None
    return read_json(plane.path("intents", "m1_intent", "outcomes", f"{outcome_id}.json"))


class CharterStore:
    def __init__(self, plane, clock=time.time, contracts_dir=None):
        self._plane, self._clock, self._contracts = plane, clock, contracts_dir
        self.sessions = SessionStore(plane, clock)

    # ---- files
    def _lock(self):
        return lock_for(self._plane.path("intents", "m1_intent"))  # the same lock the session and room stores use

    def _path(self, session_id: str):
        return self._plane.path("intents", "m1_intent", "charters", f"{session_id}.json")

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def read(self, session_id) -> dict | None:
        if not (isinstance(session_id, str) and _HEX32.fullmatch(session_id)):
            return None
        doc = read_json(self._path(session_id))
        if doc is None:
            return None
        vs, links = doc.get("versions"), doc.get("links")
        if not (set(doc) == _DOC_KEYS and doc["session_id"] == session_id and isinstance(vs, list) and vs
                and all(isinstance(v, dict) and v.get("status") in C.STATUSES and v.get("version") == i
                        for i, v in enumerate(vs, 1))
                and isinstance(links, list) and all(isinstance(l, dict) and set(l) == _LINK_KEYS
                                                    and l["state"] in _LINK_STATES for l in links)):
            raise StoreError(UNREADABLE)
        return doc

    def _save(self, doc: dict) -> None:
        write_json(self._path(doc["session_id"]), doc)

    def _mine(self, session_id, organiser_id) -> dict:
        s = self.sessions.get(session_id)
        if s is None or s["organiser_account_id"] != organiser_id:
            raise LookupError("no session")
        return s

    @staticmethod
    def _replace_latest(doc: dict, version: dict, links: list | None = None) -> dict:
        return {**doc, "versions": [*doc["versions"][:-1], version], "links": doc["links"] if links is None else links}

    # ---- drafting (M1-24) and editing
    def draft(self, session_id, organiser_id: str, make: Callable[[dict | None, int], dict]) -> dict:
        """Together stage -> signing, with a new draft. `make(earlier, number)` builds the version (domain/charter.py)."""
        with self._lock():
            s = self._mine(session_id, organiser_id)
            if s["state"] != "together":
                raise WrongState("The charter is drafted from the together stage. This session is not at that stage.")
            doc = self.read(session_id) or {"session_id": session_id, "versions": [], "links": []}
            latest = doc["versions"][-1] if doc["versions"] else None
            if latest is not None and latest["status"] != "returned":
                raise WrongState("This session already has a charter draft.")
            version = make(latest, len(doc["versions"]) + 1)
            self._save({**doc, "versions": [*doc["versions"], version]})
            self.sessions.transition(session_id, "signing")
            return version

    def edit(self, session_id, organiser_id: str, change: Callable[[dict], dict]) -> dict:
        with self._lock():
            s, doc = self._mine(session_id, organiser_id), self.read(session_id)
            if doc is None or s["state"] != "signing":
                raise LookupError("no charter")
            version = change(doc["versions"][-1])
            self._save(self._replace_latest(doc, version))
            return version

    # ---- signing in the room (M1-25)
    def sign(self, session_id, signer: dict, needed: int) -> dict:
        with self._lock():
            s, doc = self.sessions.get(session_id), self.read(session_id)
            if s is None or doc is None or s["state"] != "signing":
                raise LookupError("no charter")
            version = C.sign_in_room(doc["versions"][-1], signer, needed, self._now())
            return self._keep(s, doc, version)

    def _keep(self, s: dict, doc: dict, version: dict, links: list | None = None) -> dict:
        """Saves the latest version. A signed one also writes the outcome record and closes the session with its outcome
        (D-026). Order: record, charter, session. ponytail: no rollback if the last step fails; one process, small files."""
        if version["status"] != "signed":
            self._save(self._replace_latest(doc, version, links))
            return version
        record = H.build_outcome(H.load_outcome_contract(self._contracts), outcome_id=s["outcome_id"], session_id=s["id"], version=version)
        write_json(self._plane.path("intents", "m1_intent", "outcomes", f"{s['outcome_id']}.json"), record)
        self._save(self._replace_latest(doc, version, links))
        self.sessions.transition(s["id"], "closed")  # also completes the session side of the process record
        try:
            ProcessRecords(self._plane, self._clock).complete_outcome(s["outcome_id"])
        except ProcessRecordError as e:
            raise StoreError(str(e)) from None
        return version

    # ---- the approver (M1-26)
    def send(self, session_id, organiser_id: str, token: str, hours: int) -> tuple[dict, str]:
        """Makes the one open link for the latest draft (earlier ones stop working). Returns (version, expires_at)."""
        with self._lock():
            s, doc = self._mine(session_id, organiser_id), self.read(session_id)
            if doc is None or s["state"] != "signing":
                raise LookupError("no charter")
            v = doc["versions"][-1]
            if v["status"] != "draft" or v["signatures"]:
                raise WrongState("This charter cannot be sent to an approver now: it is already with one, signed, or being signed in the room.")
            if not v["problems"]:
                raise C.CharterError("empty", C.EMPTY)
            if any(p.get("so_that_draft") for p in v["problems"]):
                raise C.CharterError("unchecked_lines", C.UNCHECKED)  # an approver signs what the room has checked
            if not s["preparation"]["approver_name"]:
                raise WrongState("No approver is named for this session. Sign it in the room, or name an approver in Prepare before the session starts.")
            now = datetime.fromtimestamp(self._clock(), timezone.utc)
            link = {"hash": digest(token), "version": v["version"], "issued_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=hours)).isoformat(), "state": "open"}
            links = [{**l, "state": "revoked"} if l["state"] == "open" else l for l in doc["links"]]
            version = {**v, "status": "awaiting_approver"}
            self._save(self._replace_latest(doc, version, [*links, link]))
            return version, link["expires_at"]

    def revoke(self, session_id, organiser_id: str) -> dict:
        with self._lock():
            s, doc = self._mine(session_id, organiser_id), self.read(session_id)
            if doc is None or s["state"] != "signing":
                raise LookupError("no charter")
            v = doc["versions"][-1]
            if v["status"] != "awaiting_approver":
                raise WrongState("There is no link out for this charter.")
            links = [{**l, "state": "revoked"} if l["state"] == "open" else l for l in doc["links"]]
            version = {**v, "status": "draft"}
            self._save(self._replace_latest(doc, version, links))
            return version

    def _match(self, doc: dict, token_hash: str) -> dict | None:
        found = None
        for l in doc["links"]:  # compare every one: the time taken does not depend on which matched
            if hmac.compare_digest(l["hash"], token_hash):
                found = l
        return found

    def _approver_ground(self, session_id, token: str) -> tuple[dict, dict, dict, dict]:
        """(session, doc, link, version) for a token that is good right now. Raises CharterError: `link_invalid` when
        nothing matches, `link_gone` (with the reason in words) when the link matched but is used, withdrawn, expired
        or for an earlier draft. Only a holder of the real secret can see which."""
        s, doc = self.sessions.get(session_id), self.read(session_id)
        link = self._match(doc, digest(token)) if doc else None
        if s is None or link is None:
            raise C.CharterError("link_invalid", "This link is not working. Please ask for a new one.")
        v = doc["versions"][-1]
        why = (link["state"] if link["state"] != "open" else
               "expired" if datetime.fromisoformat(link["expires_at"]) <= datetime.fromtimestamp(self._clock(), timezone.utc) else
               "replaced" if link["version"] != v["version"] or v["status"] != "awaiting_approver" or s["state"] != "signing" else None)
        if why:
            raise C.CharterError("link_gone", _GONE[why])
        return s, doc, link, v

    def approver_view(self, session_id, token: str) -> tuple[dict, dict]:
        with self._lock():
            s, _, link, v = self._approver_ground(session_id, token)
            return v, {"approver_name": s["preparation"]["approver_name"], "expires_at": link["expires_at"]}

    def approver_decide(self, session_id, token: str, decision: str, comment: str) -> dict:
        """Approve (signs with the approver's name and the time; hands on) or decline (the earlier draft stays as a
        version and the together stage reopens). The link is used up either way."""
        with self._lock():
            s, doc, link, v = self._approver_ground(session_id, token)
            now = self._now()
            links = [{**l, "state": "used"} if l is link else l for l in doc["links"]]
            if decision == "approve":
                return self._keep(s, doc, C.approve(v, s["preparation"]["approver_name"], now), links)
            version = C.decline(v, comment, s["preparation"]["approver_name"], now)
            self._save(self._replace_latest(doc, version, links))
            self.sessions.transition(session_id, "together")
            return version


def new_token(session_id: str) -> str:
    return f"ap-{session_id}-{secrets.token_urlsafe(32)}"
