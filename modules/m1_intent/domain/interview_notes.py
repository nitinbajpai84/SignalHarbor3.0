"""Note drafts for the private room from a person's one interview, and the note cards North writes from the conversation (LI-M1).
Pure Python: no web, no storage, no model. The interview's answers come in as plain dicts, already limited to the one person.

A draft is a note the person has not yet confirmed (`confirmed: False`): Keep, Change or Anonymous confirms it, and only a confirmed
note is sent to the board when the rooms close (store/notes.py). Nothing here leaves the person's own transcript.
"""
from dataclasses import dataclass

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain import notes as N


@dataclass(frozen=True)
class InterviewNotes:
    kinds: dict[str, str]
    max_cards: int
    words: dict[str, str]


def load(folder=None) -> InterviewNotes:
    name = "interview_notes.yaml"
    d = C._read(folder, name)
    try:
        kinds = {str(q).upper(): str(k) for q, k in d["kinds"].items()}
        if not kinds or any(k not in N.NOTE_KINDS for k in kinds.values()):
            raise ValueError("every question must become a known kind of note")
        words = {k: str(d[k]) for k in ("from_label", "cards_label", "intro", "no_gaps", "no_cards_model", "no_cards_found")}
        return InterviewNotes(kinds, C._int(d["max_cards"], "most cards"), words)
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        raise C.ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None


def answers(interview: dict) -> list[tuple[str, str]]:
    """(question id, answer) for the person's answers that may become a draft, in question order. An empty answer, and an
    answer the interview marked restricted (a topic it did not probe), make none."""
    out = []
    for key in sorted(interview, key=lambda k: (len(k), k)):
        cell = interview[key] if isinstance(interview.get(key), dict) else {}
        v = cell.get("value") if cell.get("mark") != "unknown" else None
        text = " ".join(str(v.get("answer") or "").split()) if isinstance(v, dict) and not v.get("restricted") else ""
        if text:
            out.append((key.upper(), text))
    return out


def draft_note(base: dict, kind: str, q: str, label: str) -> dict:
    """A room draft (domain/notes.start) made from an interview answer: its kind set, not yet confirmed, its source named."""
    return {**base, "kind": kind, "kind_chosen": True, "confirmed": False, "source": {"kind": "interview", "q": q, "from": label}}


def gaps(spec: N.NoteFields, notes: list[dict]) -> list[dict]:
    """The kinds of note the person has no note of yet, with North's question for each: all North asks after the drafts."""
    have = {N.kind_of(n) for n in notes}
    return [{"kind": k["id"], "ask": k["ask"]} for k in spec.kinds if k["id"] not in have]


def intro(words: dict, count: int, gap: list[dict]) -> str:
    what = f"{count} note" + ("" if count == 1 else "s")
    return f"{words['intro'].format(count=what)} {gap[0]['ask'] if gap else words['no_gaps']}"


def card_note(base: dict, spec: N.NoteFields, proposal: dict, now: str, label: str) -> dict | None:
    """A note card from one proposal of North: {text, kind, fields}. The kind must be known and the fields only those that kind holds,
    each cleaned like a typed one; a person-only field is never filled. None when the proposal has no usable text."""
    text = " ".join(str(proposal.get("text") or "").split())
    kind = proposal.get("kind") if proposal.get("kind") in spec.kind_ids() else N.DEFAULT_KIND
    if not text:
        return None
    note = {**base, "text": text, "kind": kind, "kind_chosen": True, "confirmed": False, "source": {"kind": "north", "from": label}}
    values = proposal.get("fields") if isinstance(proposal.get("fields"), dict) else {}
    own = {f["id"]: f for f in spec.extra(kind) if not f["person_only"] and f["kind"] == "text"}
    note["fields"] = {k: " ".join(v.split())[:spec.field_chars] for k, v in values.items() if k in own and isinstance(v, str) and v.strip()}
    return {**note, "updated_at": now}
