"""The four wall questions on a note card, and North's suggestion cards (A-055, A-056). Pure Python: no web, storage or model.

A card carries `quarters: {q1..q4: {text, mark: stated|guessed|unknown, from}}`. What the person typed is `stated`; a draft North
filled from a document is `guessed` with the document named; the rest is `unknown`. North's drafts wait in `quarter_drafts` until
the person keeps or changes them. A card without `quarters` (older notes) is not checked.
"""
import hashlib
import re
from dataclasses import dataclass

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.private_room import RoomError, check_text

IDS = ("q1", "q2", "q3", "q4")
_DONT_KNOW = re.compile(r"^\W*(?:i\s*(?:do\s*not|don.?t)\s*know|no idea|not sure|unknown|dk)\W*$", re.I)


@dataclass(frozen=True)
class WallQuestions:
    questions: tuple[dict, ...]
    min_answered: int
    max_suggestions: int
    words: dict[str, str]

    def get(self, q: str) -> dict:
        return next(x for x in self.questions if x["id"] == q)


def load(folder=None) -> WallQuestions:
    name = "wall_questions.yaml"
    d = C._read(folder, name)
    try:
        qs = tuple({"id": str(r["id"]), "lead": str(r["lead"]), "fills": [str(f) for f in r["fills"]], "unknown_ok": r.get("unknown_ok") is True}
                   for r in d["questions"])
        if tuple(q["id"] for q in qs) != IDS:
            raise ValueError("the four questions must be q1 to q4, in order")
        words = {k: str(d["words"][k]) for k in ("draft_lead", "too_few", "suggested_label")}
        return WallQuestions(qs, C._int(d["min_answered"], "the least answered", 1),
                             C._int(d["max_suggestions_per_lane"], "the most suggestions", 0), words)
    except (KeyError, ValueError, TypeError) as e:
        raise C.ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None


def blank() -> dict:
    return {q: {"text": "", "mark": "unknown", "from": None} for q in IDS}


def quarters_of(note: dict) -> dict:
    return note.get("quarters") or blank()


def answered(note: dict) -> int:
    return sum(1 for c in quarters_of(note).values() if c["mark"] != "unknown" and c["text"])


def next_open(note: dict) -> str | None:
    """The first question not yet answered or closed, or None. A quarter the person said they do not know is closed."""
    q = quarters_of(note)
    return next((i for i in IDS if q[i]["mark"] == "unknown" and not q[i].get("closed")), None)


def lead(spec: WallQuestions, note: dict, q: str) -> str:
    """How North puts the question: the draft and its source when one waits, else the question."""
    d = (note.get("quarter_drafts") or {}).get(q)
    return spec.words["draft_lead"].format(**{"from": d["from"], "text": d["text"]}) if d else spec.get(q)["lead"]


def start(note: dict, drafts: dict | None = None) -> dict:
    """The note with its four empty quarters. `drafts`: {q: {text, from, source: interview|document}} already known to answer a
    question (the interview's prefill, or a document the person shared). A draft only shows until the person keeps or changes it."""
    ok = {q: {"text": " ".join(str(d["text"]).split()), "from": str(d["from"]), "source": d.get("source", "document")}
          for q, d in (drafts or {}).items() if q in IDS and str(d.get("text") or "").strip() and d.get("from")}
    return {**note, "quarters": blank(), "quarter_drafts": ok}


def answer(spec: WallQuestions, note: dict, given: dict) -> dict:
    """Apply `given`: {q: {"text": typed} | {"keep": true}}. Typed is stated ("I don't know" on q4 is unknown but closed); keep takes
    the waiting draft: stated when it came from the person's own interview, guessed when from a document. Raises RoomError."""
    if not isinstance(given, dict):
        raise RoomError("Those answers could not be read. Please try again.")
    quarters = {q: dict(c) for q, c in quarters_of(note).items()}
    drafts = dict(note.get("quarter_drafts") or {})
    for q, a in given.items():
        if q not in IDS or not isinstance(a, dict):
            raise RoomError("Please answer one of the four questions.")
        if a.get("keep") is True:
            d = drafts.pop(q, None)
            if d is None:
                raise RoomError("There is no draft to keep for that question.")
            quarters[q] = {"text": d["text"], "mark": "stated" if d["source"] == "interview" else "guessed", "from": d["from"]}
            continue
        text = check_text(a.get("text"))
        drafts.pop(q, None)
        if _DONT_KNOW.match(text):
            if not spec.get(q)["unknown_ok"]:
                raise RoomError("Please say a little about it, even a guess.")
            quarters[q] = {"text": "", "mark": "unknown", "from": None, "closed": True}
        else:
            quarters[q] = {"text": text, "mark": "stated", "from": "you"}
    out = {**note, "quarters": quarters, "quarter_drafts": drafts}
    if quarters["q1"]["text"]:
        out["text"] = quarters["q1"]["text"]  # the card's own words are the first answer
    return out


def mask(note: dict, fn) -> dict:
    """The note with `fn` applied to the text and the source label of every quarter and waiting draft (used to take names out of an
    anonymous card, which the wall shows)."""
    def cell(c: dict) -> dict:
        return {**c, "text": fn(c["text"]), **({"from": fn(c["from"])} if c.get("from") else {})}
    return {**note, "quarters": {q: cell(c) for q, c in quarters_of(note).items()},
            "quarter_drafts": {q: cell(d) for q, d in (note.get("quarter_drafts") or {}).items()}}


def check_placeable(spec: WallQuestions, note: dict) -> None:
    """Refuse a card with too few answered quarters, in a plain sentence. A note with no quarters is an older note: allowed."""
    if "quarters" in note and answered(note) < spec.min_answered:
        raise RoomError(spec.words["too_few"].format(min=spec.min_answered))


# ---- suggestion cards (A-056)

def suggest(spec: WallQuestions, candidates: list[dict], taken: list[dict] | None = None) -> list[dict]:
    """At most `max_suggestions` per lane (kind) from `candidates` [{kind, text, from}] (the pack's problems, the person's shared
    documents), skipping a text already a card or suggestion. Suggestions only: `suggested: true`, never counted anywhere."""
    seen = {" ".join(str(n.get("text", "")).lower().split()) for n in taken or []}
    out, count = [], {}
    for c in candidates:
        text = " ".join(str(c.get("text") or "").split())
        kind, key = c.get("kind"), text.lower()
        if not text or not c.get("from") or key in seen or count.get(kind, 0) >= spec.max_suggestions:
            continue
        seen.add(key)
        count[kind] = count.get(kind, 0) + 1
        out.append({"id": hashlib.sha1(f"{kind}|{key}".encode()).hexdigest()[:16], "text": text, "kind": kind, "suggested": True, "from": str(c["from"]),
                    "label": spec.words["suggested_label"].format(**{"from": c["from"]})})
    return out


def from_pack(by_kind: dict[str, list[str]], pack_label: str) -> list[dict]:
    """Candidates from the pack's examples (tools/pack_tools.kind_suggestions: {kind: [text]}), named by the pack."""
    return [{"kind": k, "text": t, "from": pack_label} for k, texts in by_kind.items() for t in texts]


def pick_up(suggestion: dict, base: dict) -> dict:
    """The card a person makes by picking up a suggestion: a normal unconfirmed card whose q1 is a draft naming the pack or document."""
    card = {**base, "text": suggestion["text"], "kind": suggestion["kind"], "kind_chosen": True, "confirmed": False,
            "source": {"kind": "suggestion", "from": suggestion["from"]}}
    return start(card, {"q1": {"text": suggestion["text"], "from": suggestion["from"], "source": "document"}})


def drop_untouched(room: dict) -> dict:
    """The room as it is when it closes: suggestions never picked up are gone."""
    return {k: v for k, v in room.items() if k != "suggestions"}
