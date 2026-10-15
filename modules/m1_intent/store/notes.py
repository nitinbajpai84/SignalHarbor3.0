"""Submitted notes, their authors (kept APART), and retention (M1-11, M1-12, M1-29).

All in the company's own plane, under intents/m1_intent/:
  notes/<session id>.json           the PUBLIC records of submitted notes. No author field of any kind, no time.
  note_authors/<session id>.json    note id -> seat id, and the seats that ever chose anonymous. Read only by
                                    `NoteStore.board(viewer=...)` (to tell a person which notes are theirs) and by
                                    the code that enforces D-016 (`has_anonymous`). No route returns it.
`board()` is the ONE function a board, wall, charter or export may read notes through (later packages): it returns
the public records only, in the order of their random ids (so the order says nothing about who wrote what or when).
Strict reads, atomic writes, one lock per plane. Nothing here logs a note, a name or a seat.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from modules.m1_intent.domain import notes as N
from modules.m1_intent.store.files import NOT_SAVED, UNREADABLE, StoreError, lock_for, read_json, write_json
from modules.m1_intent.store.sessions import SessionStore
from modules.m1_intent.store.transcripts import TranscriptStore
from sh_platform.plane import CompanyPlane
from sh_platform.profile import record_card, store as profile_store
from sh_platform.profile.cards import ANON

log = logging.getLogger(__name__)
_HEX = re.compile(r"[0-9a-f]{32}")
_KINDS = ("transcripts", "notes", "requests")


def _hex(v) -> bool:
    return isinstance(v, str) and _HEX.fullmatch(v) is not None


class NoteStore:
    def __init__(self, plane: CompanyPlane, fields: N.NoteFields | None = None, clock=None):
        self._plane, self._fields = plane, fields or N.load_fields()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _lock(self):
        return lock_for(self._plane.root / ".m1_notes")

    def _path(self, folder: str, session_id):
        if not _hex(session_id):
            raise StoreError(NOT_SAVED)
        return self._plane.path("intents", "m1_intent", folder, f"{session_id}.json")

    def _read(self, folder: str, session_id, key: str, empty):
        data = read_json(self._path(folder, session_id))
        if data is None:
            return {"session_id": session_id, key: empty, "updated_at": None}
        if not (isinstance(data, dict) and data.get("session_id") == session_id and isinstance(data.get(key), type(empty))):
            raise StoreError(UNREADABLE)
        return data

    def _write(self, folder: str, data: dict) -> None:
        write_json(self._path(folder, data["session_id"]), {**data, "updated_at": self._clock().isoformat()})

    # ---- the authors, apart from the notes
    def _authors(self, sid) -> dict:
        d = self._read("note_authors", sid, "authors", {})
        d.setdefault("anonymous_seats", [])
        return d

    def mark_anonymous(self, sid: str, seat: str) -> None:
        """A one-way flag: once a seat has chosen anonymous on any note, an admin can never read its transcript."""
        with self._lock():
            d = self._authors(sid)
            if seat not in d["anonymous_seats"]:
                self._write("note_authors", {**d, "anonymous_seats": [*d["anonymous_seats"], seat]})

    def has_anonymous(self, sid: str, seat: str) -> bool:
        with self._lock():
            return seat in self._authors(sid)["anonymous_seats"]

    # ---- submitting and reading
    def submit(self, sid: str, seat: str, drafts: list[dict]) -> int:
        """Copies the public record of each draft (once: a note already submitted is skipped). Returns how many."""
        with self._lock():
            shared, authors = self._read("notes", sid, "notes", []), self._authors(sid)
            have = {n["id"] for n in shared["notes"]}
            new = [d for d in drafts if d["id"] not in have]
            if not new:
                return 0
            anon = set(authors["anonymous_seats"]) | ({seat} if any(d.get("anonymous") for d in new) else set())
            records = sorted([*shared["notes"], *(N.public_record(self._fields, d) for d in new)], key=lambda r: r["id"])
            self._write("note_authors", {**authors, "authors": {**authors["authors"], **{d["id"]: seat for d in new}},
                                         "anonymous_seats": sorted(anon)})
            self._write("notes", {**shared, "notes": records})
            return len(new)

    def contributors(self, sid: str) -> int:
        """How many seats have submitted a note: a number only."""
        with self._lock():
            return len(set(self._authors(sid)["authors"].values()))

    def board(self, sid: str, viewer: str | None = None) -> list[dict]:
        """The submitted notes of the session as everyone in the room may see them, each with `mine`: true only for
        the viewer's own notes (so an author sees theirs, anonymous ones included, marked). The one read for boards,
        walls, charters and exports."""
        with self._lock():
            shared, authors = self._read("notes", sid, "notes", []), self._authors(sid)["authors"]
        hide = N.names_rule((SessionStore(self._plane).get(sid) or {}).get("preparation")) == "anonymous"
        rows = [{**{k: n[k] for k in ("id", "text", "priority", "anonymous", "fields", "author_name", "restricted") if k in n},
                 "kind": N.kind_of(n),  # a note stored before kinds existed is an intent
                 "mine": viewer is not None and authors.get(n["id"]) == viewer} for n in shared["notes"]]
        # an "anonymous" session shows no name anywhere, even on a stored note that carries one
        return [{**{k: v for k, v in r.items() if k != "author_name"}, "anonymous": True} for r in rows] if hide else rows


# ---- submitting a person's drafts (the person's act, or the rooms ending)
_norm = N.norm_text  # one definition of "the same note", shared with the unsent count


# ponytail: the order of the four kinds against the four lanes; no contract names the pairing yet (see the report)
LANE_OF = {"intent": "tracking", "pain_point": "missing", "future_signal": "watch", "lever": "levers"}


def _quarter(c):
    """A note's quarter `{text, mark, from}` as the card cell `record_card` reads, `{value, mark}`; an unanswered one is left out."""
    if not isinstance(c, dict):
        return c
    return {"value": c["text"], "mark": c.get("mark") if c.get("mark") in ("stated", "guessed") else "stated"} if c.get("text") and c.get("mark") != "unknown" else None


def _card(note: dict, sid: str, topic: str | None = None) -> dict:
    """A submitted note as a wall card. Quarters come from the note's `quarters` when it has them, else q1 is its text. An anonymous
    card's key is made from the note's own random id, so nothing links it to a seat."""
    anon = note.get("anonymous") is True
    q = note.get("quarters") if isinstance(note.get("quarters"), dict) else {"q1": note["text"]}
    src = note.get("source") or {}
    name = re.sub(r"[^a-z0-9]+", "-", str(note.get("author_name") or "").lower()).strip("-")
    return {"id": note["id"], "lane": LANE_OF[N.kind_of(note)], "sealed": note.get("restricted") is True, "anonymous": anon,
            **({"anon_key": f"anon-{note['id']}"} if anon else {"author": name or "unnamed"}),
            **{k: _quarter(q.get(k)) for k in ("q1", "q2", "q3", "q4")},
            "from_interview": src.get("q") if src.get("kind") == "interview" else None, "room": sid, "topic": topic}


def _write_cards(drafts: list[dict], sid: str, plane: CompanyPlane) -> None:
    topic = ((SessionStore(plane).get(sid) or {}).get("preparation") or {}).get("topic")
    for n in drafts:
        try:
            c = _card(n, sid, topic)
            by = n.get("author_name") or "a participant"
            record_card(plane, c, by=by, source="A note in the private room")
            if topic:  # record_card (platform) does not know `topic`: the same provenance, one more cell, so the wall and Define can group by it
                profile_store.record(plane, f"cards.{c['id']}.topic", topic,
                                     {"mark": "stated", "by": ANON if c["anonymous"] else by, "from": "A note in the private room"})
        except (ValueError, OSError):  # the note is already kept: a card that cannot be written never undoes a submit
            log.warning("a submitted note could not be written to the wall")


def submit_drafts(plane: CompanyPlane, sid: str, seat: str, only: str | None = None, rooms_end: bool = False) -> None:
    """Submits the seat's draft notes (or just `only`): the transcript note becomes `submitted` and its public
    record goes to the shared notes. Idempotent. Needs the author's seat id. With `rooms_end` (the person did not
    submit) every note goes except a repeat of a note already submitted or sent in this pass (a retried turn). A note with no anonymity choice yet follows the session's names rule."""
    notes = NoteStore(plane)
    rule = N.names_rule((SessionStore(plane).get(sid) or {}).get("preparation"))  # the organiser's rule wins over any draft
    counters = {"cards_new": 0, "cards_sealed": 0}

    def change(t: dict) -> None:
        drafts = [n for n in t["notes"] if n["state"] == "draft" and n.get("confirmed", True) and (only is None or n["id"] == only)]  # North's drafts wait for the person
        if rule != "choice":
            anon = rule == "anonymous"
            # a draft with no name kept stays as it is: a name is never made up
            drafts = [{**n, "anonymous": anon, "author_name": None} if anon else
                      {**n, "anonymous": False} if n.get("author_name") else n for n in drafts]
        if rooms_end:
            seen, keep = {_norm(n["text"]) for n in t["notes"] if n["state"] == "submitted"}, []
            for n in drafts:
                if _norm(n["text"]) not in seen:
                    seen.add(_norm(n["text"]))
                    keep.append({**n, "anonymous": True, "author_name": None} if rule == "choice" else n)  # A-045: never sent, never confirmed
            drafts = keep
        notes.submit(sid, seat, drafts)
        _write_cards(drafts, sid, plane)
        if any(not d.get("anonymous") for d in drafts):  # an anonymous card never shows who put it up, so it marks nobody
            from sh_platform.intents.wall import person_contributed
            person_contributed(plane, sid, seat)
        sent = {n["id"]: n for n in drafts}
        counters["cards_new"] = len(drafts)
        counters["cards_sealed"] = sum(1 for n in drafts if n.get("restricted") is True)
        t["notes"] = [{**sent[n["id"]], "state": "submitted"} if n["id"] in sent else n for n in t["notes"]]

    TranscriptStore(plane).update(sid, seat, change)
    SessionStore(plane).count(sid, cards_new=counters["cards_new"], cards_sealed=counters["cards_sealed"])


class SuggestionStore:
    """North's suggestion cards for one session's rooms (A-056): {seat id: [suggestion]}, in intents/m1_intent/wall_suggestions/.
    Not notes and never counted; the file goes when the rooms close (`submit_all`)."""

    def __init__(self, plane: CompanyPlane):
        self._plane = plane

    def _path(self, sid):
        if not _hex(sid):
            raise StoreError(NOT_SAVED)
        return self._plane.path("intents", "m1_intent", "wall_suggestions", f"{sid}.json")

    def _all(self, sid) -> dict:
        data = read_json(self._path(sid))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise StoreError(UNREADABLE)
        return data

    def get(self, sid, seat) -> list[dict] | None:
        """The seat's suggestions, or None when none were ever made for it (so a person with none is not asked again)."""
        with lock_for(self._plane.root / ".m1_suggestions"):
            return self._all(sid).get(seat)

    def put(self, sid, seat, rows: list[dict]) -> None:
        with lock_for(self._plane.root / ".m1_suggestions"):
            write_json(self._path(sid), {**self._all(sid), seat: rows})

    def take(self, sid, seat, suggestion_id: str) -> dict | None:
        """Removes and returns one suggestion (a person picked it up), or None."""
        with lock_for(self._plane.root / ".m1_suggestions"):
            data = self._all(sid)
            rows = data.get(seat) or []
            got = next((r for r in rows if r.get("id") == suggestion_id), None)
            if got:
                write_json(self._path(sid), {**data, seat: [r for r in rows if r is not got]})
            return got

    def drop(self, sid) -> None:
        with lock_for(self._plane.root / ".m1_suggestions"):
            self._path(sid).unlink(missing_ok=True)


def submit_all(plane: CompanyPlane, sid: str) -> None:
    """The rooms end (M1-14): the notes written so far are submitted, each keeping its anonymity (see submit_drafts).
    Suggestions nobody picked up are dropped here, for every close (organiser or everyone done)."""
    try:
        SuggestionStore(plane).drop(sid)
    except (StoreError, OSError):
        log.warning("wall suggestions could not be removed at the end of the rooms")
    for seat in TranscriptStore(plane).seats(sid):
        try:
            submit_drafts(plane, sid, seat, rooms_end=True)
        except StoreError:  # one damaged transcript must not hold the stage change; its notes stay unsubmitted
            log.warning("a transcript could not be read at the end of the rooms; its notes were not submitted")


# ---- retention (D-017): a plan first, a purge only on explicit approval
class NotApproved(Exception):
    """The plan was not approved (or has changed since it was shown)."""


def load_retention(company_id: str, folder=None) -> dict[str, int]:
    from modules.m1_intent.domain import contracts as C
    from modules.m1_intent.domain.contracts import ContractError
    d = C._read(folder, "retention.yaml")
    try:
        merged = {**d["default"], **(d.get("customers") or {}).get(company_id, {})}
        return {f"{k}_days": C._int(merged[f"{k}_days"], f"{k} days") for k in _KINDS}
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        raise ContractError(f"retention.yaml is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None


def _old(stamp, limit: datetime) -> bool:
    try:
        return datetime.fromisoformat(stamp) < limit
    except (TypeError, ValueError):
        return False  # no readable time: never removed by age


def _row_old(line: str, limit: datetime) -> bool:
    try:
        return _old(json.loads(line).get("finished"), limit)
    except (ValueError, AttributeError):
        return False


def _stale(f, limit: datetime, skipped: list) -> bool:
    try:
        return _old((read_json(f) or {}).get("updated_at"), limit)
    except StoreError:  # a damaged file is reported, never removed and never a failure
        skipped.append(f.name)
        return False


def _expired(plane: CompanyPlane, rules: dict[str, int], now: datetime, skipped: list | None = None) -> list[tuple]:
    """(kind, session id, files to delete, number of records) for everything older than its limit. Damaged files
    are added to `skipped`."""
    out, root = [], plane.path("intents", "m1_intent")
    skipped = [] if skipped is None else skipped
    cut = {k: now - timedelta(days=rules[f"{k}_days"]) for k in _KINDS}
    for folder in sorted((root / "transcripts").glob("*")) if (root / "transcripts").is_dir() else []:
        files = [f for f in sorted(folder.glob("*.json")) if _stale(f, cut["transcripts"], skipped)]
        if files:
            out.append(("transcripts", folder.name, files, len(files)))
    for f in sorted((root / "notes").glob("*.json")) if (root / "notes").is_dir() else []:
        if _stale(f, cut["notes"], skipped):
            out.append(("notes", f.stem, [f], 1))  # note_authors stays: it holds anonymous_seats until the transcripts go too
    reg = plane.area("context") / "run_registry.jsonl"
    if reg.is_file():
        rows = [r for r in reg.read_text(encoding="utf-8").splitlines() if r.strip()]
        old = [r for r in rows if _row_old(r, cut["requests"])]
        if old:
            out.append(("requests", "", [reg], len(old)))
    return out


def retention_plan(plane: CompanyPlane, rules: dict[str, int], now: datetime) -> dict:
    """What a purge would remove, as counts per kind and session (no seat, no content), and a plan id that changes
    whenever the list does. Removes nothing."""
    skipped: list = []
    found = _expired(plane, rules, now, skipped)
    pid = hashlib.sha256(json.dumps([[k, s, [f.name for f in fs], n] for k, s, fs, n in found]).encode()).hexdigest()[:32]
    return {"id": pid, "items": [{"kind": k, "session_id": s, "count": n} for k, s, _, n in found],
            "total": sum(n for *_, n in found), "skipped": len(skipped)}


def purge(plane: CompanyPlane, rules: dict[str, int], now: datetime, approved_plan: str) -> dict:
    """Deletes exactly the plan a person approved by its id. Raises NotApproved if the id is not the current plan."""
    reg = plane.area("context") / "run_registry.jsonl"
    with lock_for(plane.root / ".m1_notes"), lock_for(reg):
        plan, found = retention_plan(plane, rules, now), _expired(plane, rules, now)
        if approved_plan != plan["id"]:
            raise NotApproved
        for kind, _, files, _ in found:
            if kind == "requests":
                limit = now - timedelta(days=rules["requests_days"])
                keep = [r for r in files[0].read_text(encoding="utf-8").splitlines()
                        if r.strip() and not _row_old(r, limit)]
                tmp = files[0].with_name(files[0].name + ".tmp")
                tmp.write_text("".join(r + "\n" for r in keep), encoding="utf-8")
                os.replace(tmp, files[0])  # whole before or whole after; the registry append takes the same lock
            else:
                for f in files:
                    f.unlink(missing_ok=True)
        root = plane.path("intents", "m1_intent")
        for sid in {s for k, s, *_ in found if k != "requests"}:  # the author map goes last: with the notes AND the transcripts
            tdir = root / "transcripts" / sid
            if not (root / "notes" / f"{sid}.json").exists() and not (tdir.is_dir() and any(tdir.glob("*.json"))):
                (root / "note_authors" / f"{sid}.json").unlink(missing_ok=True)
    return plan
