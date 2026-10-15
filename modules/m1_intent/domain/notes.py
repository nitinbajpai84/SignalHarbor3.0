"""The note form and what a note shows to others (M1-11, M1-12). Pure Python: no web, no storage, no model.

A note starts as a draft in its author's private transcript (the draft model of domain/private_room.py, extended
here with the form fields). Submitting copies its PUBLIC record to the shared notes, and nothing else: the public
record is built from an allow-list and has no author of any kind for an anonymous note: no seat, account, guest
id, name, time or position. The author of every note is kept apart (store/notes.py). By name is the default; the
choice can change on a draft, never after submitting (a submitted note is read-only).
"""
import math
from dataclasses import dataclass

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.preparation import NAMES
from modules.m1_intent.domain.private_room import RoomError, check_text, clean_priority


class NamesRule(RoomError):
    """The note's anonymity contradicts the organiser's rule for the session: the API answers 409."""


def names_rule(prep: dict | None) -> str:
    """The session's names rule from Prepare: "named", "choice" or "anonymous". A session without one is "choice"."""
    v = (prep or {}).get("names")
    return v if v in NAMES else "choice"


def apply_names(names: str, wanted):
    """The one place the organiser's rule meets a note's (or a comment's) anonymity. `wanted` is what the person asked
    for (True, False or None for no choice). "choice" returns it as it is; otherwise the rule's value, and NamesRule
    when the person asked for the opposite."""
    if names == "choice":
        return wanted
    forced = names == "anonymous"
    if wanted is not None and wanted != forced:
        raise NamesRule("The organiser has set this session so that notes are anonymous, and a name cannot be shown."
                        if forced else
                        "The organiser has set this session so that every note shows its author's name, and a note cannot be anonymous.")
    return forced


SUBMITTED = "You have already submitted this note, so it can no longer be changed."
KINDS = ("text", "number", "labels")
DEFAULT_KIND = "intent"   # a note saved before kinds existed has none: it is an intent
NOTE_KINDS = ("intent", "pain_point", "future_signal", "lever")
BAD_KIND = "Please choose what kind of note this is."


def kind_of(note: dict) -> str:
    """The kind of a note or a public record; an old one with none is an intent."""
    k = note.get("kind")
    return k if k in NOTE_KINDS else DEFAULT_KIND


@dataclass(frozen=True)
class NoteFields:
    fields: tuple[dict, ...]
    field_chars: int
    labels_max: int
    label_chars: int
    kinds: tuple[dict, ...] = ()   # {id, label, heading, ask, fields}: contracts/note_fields.yaml `kinds`

    def kind_ids(self) -> tuple[str, ...]:
        return tuple(k["id"] for k in self.kinds) or (DEFAULT_KIND,)

    def heading(self, kind: str) -> str:
        return next((k["heading"] for k in self.kinds if k["id"] == kind), kind)

    def _kind_fields(self) -> tuple[dict, ...]:
        return tuple(f for k in self.kinds for f in k["fields"])

    def extra(self, kind: str | None = None) -> tuple[dict, ...]:
        """The fields besides the problem (the note's own words). With a `kind`: only those that kind can hold, its own
        details included. Without: every field of the contract."""
        base = tuple(f for f in self.fields if f["id"] != "problem")
        if kind is None:
            return base + self._kind_fields()
        own = next((k["fields"] for k in self.kinds if k["id"] == kind), ())
        return tuple(f for f in base if not f["kinds"] or kind in f["kinds"]) + tuple(own)

    def get(self, field_id: str) -> dict | None:
        return next((f for f in self.fields + self._kind_fields() if f["id"] == field_id), None)

    def holds(self, kind: str, field_id: str) -> bool:
        return any(f["id"] == field_id for f in self.extra(kind))


def _field(r) -> dict:
    if not (isinstance(r, dict) and isinstance(r["id"], str) and r["id"] and isinstance(r["label"], str)
            and r["kind"] in KINDS and isinstance(r.get("ask", ""), str)):
        raise ValueError("a field needs an id, a label and a kind (text, number or labels)")
    return {"id": r["id"], "label": r["label"], "kind": r["kind"], "ask": r.get("ask", ""),
            "required": r.get("required") is True, "person_only": r.get("person_only") is True,
            "guess": r.get("guess") is True, "kinds": [k for k in r.get("kinds") or [] if k in NOTE_KINDS]}


def load_fields(folder=None) -> NoteFields:
    name = "note_fields.yaml"
    d = C._read(folder, name)
    try:
        rows, lim = d["fields"], d["limits"]
        out = [_field(r) for r in rows]
        kinds = []
        for k in d["kinds"]:
            if not (k["id"] in NOTE_KINDS and isinstance(k["label"], str) and isinstance(k["heading"], str)):
                raise ValueError("a kind needs a known id, a label and a heading")
            kinds.append({"id": k["id"], "label": k["label"], "heading": k["heading"], "ask": str(k.get("ask", "")),
                          "fields": tuple(_field(r) for r in k.get("fields") or [])})
        ids = [f["id"] for f in out] + [f["id"] for k in kinds for f in k["fields"]]
        if len(set(ids)) != len(ids) or ids[:1] != ["problem"]:
            raise ValueError("field ids must be unique and the first field must be the problem")
        if [k["id"] for k in kinds][:1] != [DEFAULT_KIND] or len({k["id"] for k in kinds}) != len(kinds):
            raise ValueError("the kinds must be unique and start with intent")
        return NoteFields(tuple(out), C._int(lim["field_chars"], "field limit"),
                          C._int(lim["labels_max"], "labels limit"), C._int(lim["label_chars"], "label limit"), tuple(kinds))
    except (KeyError, ValueError, TypeError) as e:
        raise C.ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None


def cluster_kind(kinds: list[str]) -> str:
    """The kind a group of notes is listed under: the most common among its notes, a tie going to the earlier kind."""
    return max(NOTE_KINDS, key=lambda k: (kinds.count(k), -NOTE_KINDS.index(k))) if kinds else DEFAULT_KIND


def details(spec: NoteFields, kind: str, records: list[dict]) -> list[dict]:
    """What the notes of one kind said in that kind's own details (who is affected, how often, the KPIs a lever moves...),
    as [{label, values}] with each value once. Public records only: no author, and nothing a person marked anonymous
    leads back to them."""
    own = next((k["fields"] for k in spec.kinds if k["id"] == kind), ())
    out = []
    for f in own:
        seen: dict[str, str] = {}
        for r in records:
            v = r.get("fields", {}).get(f["id"]) if kind_of(r) == kind else None
            if isinstance(v, str) and v.strip():
                seen.setdefault(norm_text(v), v.strip())
        if seen:
            out.append({"label": f["label"], "values": list(seen.values())})
    return out


def norm_text(text: str) -> str:
    return " ".join(text.lower().split())


def unsent(notes: list[dict], names: str = "choice") -> dict:
    """The person's saved-but-unsent notes, which the rooms' end submits for them (store/notes.py submit_drafts):
    {count, named, message}. `named` are the ones that go under the person's name: only in a "named" session, because a
    person who never sent a note never confirmed their name (A-045): in "choice" and "anonymous" sessions they go
    anonymously. `message` is None when there are none."""
    seen, drafts = {norm_text(n.get("text", "")) for n in notes if n.get("state") == "submitted"}, []
    for n in notes:  # the rooms' end skips a repeat of a sent note and the second of two equal drafts
        if n.get("state") == "draft" and n.get("confirmed", True) and norm_text(n.get("text", "")) not in seen:
            seen.add(norm_text(n.get("text", "")))
            drafts.append(n)
    named = len(drafts) if names == "named" else 0
    return {"count": len(drafts), "named": named, "message": unsent_text(len(drafts), names)}


def unsent_text(count: int, names: str = "choice") -> str | None:
    if count < 1:
        return None
    them, notes, goes = ("it", "note", "goes") if count == 1 else ("they", "notes", "go")
    head = f"You have {count} {notes} not yet sent."
    if names == "named":
        return f"{head} When time ends {them} {goes} to the board under your name."
    if names == "anonymous":
        return f"{head} When time ends {them} {goes} to the board without your name."
    return f"{head} If you do not send {'it' if count == 1 else 'them'}, {them} {goes} to the board anonymously."


def form_view(spec: NoteFields) -> list[dict]:
    """The field list the screen draws (everything from the contract, nothing about any person)."""
    return [dict(f) for f in spec.fields]


def kinds_view(spec: NoteFields) -> list[dict]:
    """The kinds the screen offers, each with its own details."""
    return [{**k, "fields": [dict(f) for f in k["fields"]]} for k in spec.kinds]


def _value(spec: NoteFields, f: dict, v):
    """A cleaned value, or None for "cleared". Raises RoomError in plain words."""
    if v is None:
        return None
    if f["kind"] == "number":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e12:
            raise RoomError(f"Please give a number for \"{f['label']}\".")
        return v
    if f["kind"] == "labels":
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise RoomError("Please choose labels from the list.")
        labels = list(dict.fromkeys(" ".join(x.split()) for x in v if x.strip()))
        if len(labels) > spec.labels_max or any(len(x) > spec.label_chars for x in labels):
            raise RoomError(f"Please use at most {spec.labels_max} labels of {spec.label_chars} characters.")
        return labels or None
    if not isinstance(v, str):
        raise RoomError(f"Please write \"{f['label']}\" as text.")
    v = " ".join(v.split())
    if len(v) > spec.field_chars:
        raise RoomError(f"\"{f['label']}\" is too long. Please keep it under {spec.field_chars} characters.")
    return v or None


def start(note: dict, author_name: str, names: str = "choice") -> dict:
    """A private-room draft as a form note: no fields yet, by name (anonymous when the session's rule says so)."""
    anon = names == "anonymous"
    return {**note, "kind": DEFAULT_KIND, "fields": {}, "labels_suggested": [], "anonymous": anon, "author_name": None if anon else author_name}


def edit(spec: NoteFields, note: dict, body: dict, author_name: str, now: str, names: str = "choice") -> dict:
    """The draft with the person's changes: text (the problem), priority, `fields` and `anonymous`. Every key must
    be in the contract, so a field the contract does not list is refused. Raises RoomError."""
    if note["state"] != "draft":
        raise RoomError(SUBMITTED)
    out = {**note}
    if "text" in body:
        text = check_text(body["text"])
        if text != note["text"]:
            out = {**out, "text": text, "history": [*note["history"], {"text": note["text"], "at": now}]}
    if "priority" in body:
        out["priority"] = clean_priority(body["priority"])
    if "kind" in body:
        if body["kind"] not in spec.kind_ids():
            raise RoomError(BAD_KIND)
        out["kind"], out["kind_chosen"] = body["kind"], True  # the person's choice: North's suggestion no longer applies
        out.pop("kind_suggested", None)
    values = body.get("fields", {})
    if not isinstance(values, dict):
        raise RoomError("Those details could not be read. Please try again.")
    for k in values:
        if k == "problem":
            raise RoomError('"problem" is the note\'s own words: send it as "text", not inside "fields".')
        if spec.get(k) is None:
            raise RoomError(f'"{str(k)[:40]}" is not a detail a note can hold. Please check the field name.')
        if values[k] is not None and not spec.holds(kind_of(out), k):
            raise RoomError(f'"{spec.get(k)["label"]}" is not asked for this kind of note. Please choose the kind first.')
    fields = {**note.get("fields", {})}
    for k, v in values.items():
        clean = _value(spec, spec.get(k), v)
        if clean is None:
            fields.pop(k, None)
        else:
            fields[k] = clean
    if "anonymous" in body:
        if not isinstance(body["anonymous"], bool):
            raise RoomError("Please choose By name or Anonymous.")
        apply_names(names, body["anonymous"])  # the organiser decided, for everyone
        out["anonymous"], out["anonymous_chosen"] = body["anonymous"], True  # a choice: the session's names rule no longer applies
        out["author_name"] = None if body["anonymous"] else author_name
    if "restricted" in body:
        if not isinstance(body["restricted"], bool):
            raise RoomError("Please choose whether to seal this note.")
        out["restricted"] = body["restricted"]  # the seal: the wall and the board show it as a silhouette (D-013)
    return {**out, "fields": fields, "updated_at": now}


def prefill(spec: NoteFields, note: dict, proposal: dict, now: str) -> dict:
    """North's pre-fill: only fields that are still empty, never a person-only one (the belief number); labels go to
    `labels_suggested` and count only once the person confirms them. A kind goes to `kind_suggested` and never changes
    the note: the person decides. Details are filled for the kind the note has, or the one suggested while the person has
    not chosen. Anything unreadable is simply left out."""
    fields, suggested = {**note.get("fields", {})}, note.get("labels_suggested", [])
    guess = proposal.get("kind") if proposal.get("kind") in spec.kind_ids() else None
    out_kind = {} if note.get("kind_chosen") or guess in (None, kind_of(note)) else {"kind_suggested": guess}
    for f in spec.extra(guess if out_kind else kind_of(note)):
        if f["person_only"] or f["id"] not in proposal or (f["id"] in fields and f["kind"] != "labels"):
            continue
        try:
            v = _value(spec, f, proposal[f["id"]])
        except RoomError:
            continue
        if v is None:
            continue
        if f["kind"] == "labels":
            suggested = v
        else:
            fields[f["id"]] = v
    return {**note, **out_kind, "fields": fields, "labels_suggested": suggested, "updated_at": now}


def missing(spec: NoteFields, note: dict) -> list[str]:
    """Ids of the fields still empty, in contract order (what North asks about)."""
    have = {"problem": bool(note["text"]), **{k: v not in (None, "", []) for k, v in note.get("fields", {}).items()}}
    return [f["id"] for f in (spec.fields[0], *spec.extra(kind_of(note))) if not have.get(f["id"])]


def public_record(spec: NoteFields, note: dict) -> dict:
    """What every person in the room may see of a submitted note. Allow-list only: nothing here is, or can lead
    to, the author of an anonymous note; no time, no position, no id of anyone."""
    anonymous = note.get("anonymous") is True
    kind = kind_of(note)
    out = {"id": note["id"], "text": note["text"], "kind": kind, "priority": note.get("priority"), "anonymous": anonymous,
           "fields": {f["id"]: note["fields"][f["id"]] for f in spec.extra(kind) if f["id"] in note.get("fields", {})}}
    if "quarters" in note:  # the wall questions' answers: words, mark and source only (A-055)
        out["quarters"] = {q: {k: c.get(k) for k in ("text", "mark", "from")} for q, c in note["quarters"].items()}
    if note.get("restricted") is True:
        out["restricted"] = True
    if not anonymous:
        out["author_name"] = note.get("author_name")
    return out
