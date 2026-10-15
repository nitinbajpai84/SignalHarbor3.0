"""The private room's rules (M1-08, M1-10, M1-13, M1-16). Pure Python: no web, no storage, no model.

A note is a draft in the person's own words. North never rewrites it: it reads it back and a correction
replaces the text (the earlier words are kept in `history`). Industry practice comes only from the company's
pack, as a card the person adds or dismisses; the choice is recorded. Pack content is a suggestion, never
the company's own rule or figure.
"""
import re
import unicodedata
from collections.abc import Iterable

PRACTICE_LABEL = "Industry practice (suggestion)"
COMPANY_DECIDES = "Your company decides."
ROOM_STAGE = "private_rooms"
KINDS = ("note", "answer", "correction")        # a new note, an answer to North's question, a correction of a note
PRIORITIES = ("must", "should", "could", "not_this_time")   # M1-22's scale; none until the person picks one
MAX_MESSAGE_CHARS = 2000   # chosen (A-030): the contract file for text limits belongs to M1-P01
MAX_REPLY_CHARS = 900      # chosen: a short recommended draft, then one question (400 was too small for a draft)
MIN_MATCH_WORDS = 2        # chosen: how many meaningful words a note must share with a pack problem
# chosen: a shared word counts only if at most max(1, a third of the pack's problems) carry it; rarer words say more
MAX_ITEMS = 5
_CLOSED = {
    "draft": "This session has not started yet, so the private rooms are not open.",
    "lobby": "The private rooms are not open yet. Please wait for the briefing to finish.",
    "briefing": "The private rooms are not open yet. Please wait for the briefing to finish.",
    "board": "The private rooms have closed, so new notes can no longer be added.",
    "together": "The private rooms have closed, so new notes can no longer be added.",
    "signing": "The private rooms have closed, so new notes can no longer be added.",
    "closed": "This session has ended, so new notes can no longer be added.",
    "paused": "This session is paused. New notes can be added once it carries on.",
}
_STOP = frozenset("""about above after again also because been before being between both could does doing down during each
from further have having here into just like more most much only other over same should some such than that their them then
there these they this those through under until very were what when where which while who whom will with would your
ours ourselves each every
across around company companies business team teams need needs needed want wants wanted know knows make makes made
work works working time times year years month months week weeks day days often keep keeps thing things people
something anything everything really still come comes going goes many lots find found better good best help
issue issues problem problems area areas side part parts level levels way ways number numbers report reports
data information""".split())


class RoomError(ValueError):
    """The request cannot be accepted; `message` is plain words for the screen."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RoomClosed(RoomError):
    """The session is not in the private rooms stage (M1-16): the API answers 409."""


def check_stage(state: str) -> None:
    if state != ROOM_STAGE:
        raise RoomClosed(_CLOSED.get(state, "The private rooms are not open right now."))


def stage_message(state: str) -> str | None:
    return None if state == ROOM_STAGE else _CLOSED.get(state, "The private rooms are not open right now.")


def check_text(v) -> str:
    if not isinstance(v, str) or not v.strip():
        raise RoomError("Please write something first.")
    v = v.strip()
    if len(v) > MAX_MESSAGE_CHARS:
        raise RoomError(f"That is too long. Please keep it under {MAX_MESSAGE_CHARS} characters.")
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Zl", "Zp") and c not in "\n\t" for c in v):
        raise RoomError("That has a character that cannot be saved.")
    return v


# ---- the guards on North's reply. Copied from the earlier North (emitters/catalogue_chat.py `_limit_to_one_question`
# 505-527 and `_guard_labels` 613-679), in code and not only in the prompt, so a model that ignores the prompt
# still reaches the person with one question and a labelled suggestion.
_SENTENCE_END = re.compile(r"(?<=[.?!])(\s+)")
_PROTECTED = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"|https?://\S+")
_MASK = re.compile(r"\x00(\d+)\x00")
_FROM_YOUR_DATA = re.compile(r"^(\s*(?:[-*]\s+)?)from your data:\s*", re.IGNORECASE)
_DECIDES = re.compile(r"[ \t]*Your company decides\.(?=\s|$)", re.IGNORECASE)
_PRACTICE_HINT =re.compile(r"\bindustry practice\b", re.IGNORECASE)


def limit_to_one_question(text: str) -> str:
    """Keeps the first question and turns every later question into a statement (trailing "?" becomes ".")."""
    spans: list[str] = []

    def mask(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    seen, out = False, []
    for seg in _SENTENCE_END.split(_PROTECTED.sub(mask, text)):
        if seg.strip().endswith("?"):
            if seen:
                seg = seg.rstrip()[:-1] + "."
            seen = True
        out.append(seg)
    return _MASK.sub(lambda m: spans[int(m.group(1))], "".join(out))


def guard_labels(text: str) -> str:
    """A line that talks about industry practice always carries the exact label. There is no company data in a
    private room, so a "From your data" line is never a real source here and is relabelled as a suggestion."""
    out = []
    for line in text.splitlines():
        m = _FROM_YOUR_DATA.match(line)
        if m:
            line = f"{m.group(1)}{PRACTICE_LABEL}: {line[m.end():]}"
        elif _PRACTICE_HINT.search(line) and PRACTICE_LABEL not in line:
            line = f"{PRACTICE_LABEL}: {line.strip()}"
        out.append(line)
    return "\n".join(out)


NOTED = "Understood, I have noted that as something to check later."


_DECIDES_ASK = re.compile(r"\bYour company decides:\s*", re.IGNORECASE)  # "Your company decides: Which ...?" is only the question
SAME_REPLY = 0.9     # chosen: this share of the words in common is "the same reply" (see same_reply)
READ_BACK_CHARS = 200


def tidy_reply(text: str, said_before: bool = False) -> str:
    """North's reply as the person sees it: labelled, one question at most, short, and "Your company decides." said
    once, at the end, only when the reply gave a labelled suggestion and this chat has not said it yet (`said_before`).
    "Your company decides: <question>" keeps only the question. Otherwise the code never deletes a sentence of the
    model's answer: that North does not approve the company's choices, and does not ask for what the person said they
    lack, is a rule in north_rules.yaml."""
    original = (text or "").strip()
    text = re.sub(r"\n{3,}", "\n\n", guard_labels(original))
    text = limit_to_one_question(_DECIDES_ASK.sub("", text))
    if len(text) > MAX_REPLY_CHARS:
        cut = text[:MAX_REPLY_CHARS - 3]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("\n"))
        text = cut[:end + 1].rstrip() if end > 0 else cut.rsplit(" ", 1)[0] + "..."
    text = _DECIDES.sub("", text).strip()  # said once, at the end, never on every line
    if not text and original.strip("\n "):
        return NOTED  # the reply was only "Your company decides."
    if PRACTICE_LABEL in text and not said_before:
        text += f"\n{COMPANY_DECIDES}"
    return text


def said_decides(replies: Iterable[str]) -> bool:
    return any("company decides" in r.lower() for r in replies)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", (text or "").lower()))


def same_reply(a: str, b: str) -> bool:
    """True when two replies share 90% or more of their words (measured against the longer one)."""
    x, y = _tokens(a), _tokens(b)
    return bool(x and y) and len(x & y) / max(len(x), len(y)) >= SAME_REPLY


def read_back(message: str) -> str:
    """A short read-back of the person's own message: North's fallback when the model keeps repeating itself."""
    said = " ".join((message or "").split())
    if not said:
        return NOTED
    if len(said) > READ_BACK_CHARS:
        cut = said[:READ_BACK_CHARS]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        said = (cut[:end] if end > 40 else cut.rsplit(" ", 1)[0]).rstrip(".?! ") + "..."
    return f"So you are saying: {said.rstrip('.')}. Did I get that right?"


def clean_priority(v) -> str | None:
    if v is None:
        return None
    if v not in PRIORITIES:
        raise RoomError("Please choose must, should, could or not this time.")
    return v


def new_note(text: str, now: str, note_id: str, source: dict | None = None, priority: str | None = None) -> dict:
    return {"id": note_id, "text": text, "state": "draft", "source": source or {"kind": "typed"},
            "priority": priority, "created_at": now, "updated_at": now, "history": [],
            "practice": None, "practice_added": []}


def correct_note(note: dict, text: str, now: str) -> dict:
    if text == note["text"]:
        return note
    return {**note, "text": text, "updated_at": now, "history": [*note["history"], {"text": note["text"], "at": now}]}


def _words(text: str) -> set[str]:
    # a 2-3 letter ALL-CAPS token is an acronym (APE, AUM) and counts; ponytail: a shouted "THE" counts too
    acronyms = re.findall(r"\b[A-Z]{2,3}\b", text or "")
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) + [a.lower() for a in acronyms] if w not in _STOP}


def _items(problem: dict) -> list[str]:
    ta = problem.get("typical_actions")
    items = ta.get("items") if isinstance(ta, dict) else None
    return [i.strip() for i in items if isinstance(i, str) and i.strip()][:MAX_ITEMS] if isinstance(items, list) else []


def match_practice(problems: list, text: str) -> dict | None:
    """The best pack problem that shares enough words with the note and has practice to show, as an offered
    card; None when nothing matches (no card, no error). Nothing here comes from the model."""
    mine = _words(text)
    pack = [p for p in problems if isinstance(p, dict)] if isinstance(problems, list) else []
    words = {id(p): _words(" ".join(str(p.get(k) or "") for k in ("question", "decision")) + " "
                           + " ".join(x for x in (p.get("breakdowns") or []) if isinstance(x, str))) for p in pack}
    cap = max(1, len(pack) // 3)
    common = {w for w in mine if sum(w in ws for ws in words.values()) > cap}  # in too many problems to tell them apart
    best, best_score = None, 0
    for p in pack:
        if not isinstance(p.get("id"), str) or not _items(p):
            continue
        score = len((mine - common) & words[id(p)])
        if score > best_score:
            best, best_score = p, score
    if best is None or best_score < MIN_MATCH_WORDS:
        return None
    return {"problem_id": best["id"], "label": PRACTICE_LABEL, "company_decides": COMPANY_DECIDES,
            "items": _items(best), "decision": "offered"}


def set_practice(note: dict, card: dict | None) -> dict:
    """Attach a card unless the person already decided on one (that choice is never replaced)."""
    if card is None or (note["practice"] and note["practice"]["decision"] != "offered"):
        return note
    return {**note, "practice": card}


def decide_practice(note: dict, action: str, now: str) -> dict:
    card = note["practice"]
    if action not in ("add", "dismiss"):
        raise RoomError("Please choose Add or Dismiss.")
    if not card:
        raise RoomError("There is no industry practice on this note.")
    if card["decision"] != "offered":
        raise RoomError("You have already decided on this suggestion.")
    added = action == "add"
    return {**note, "practice": {**card, "decision": "added" if added else "dismissed", "decided_at": now},
            "practice_added": list(card["items"]) if added else note["practice_added"], "updated_at": now}


def library_list(problems: list) -> list[dict]:
    """The packs's common problems as {id, text}: the pack's own wording, offered as a suggestion."""
    return [{"id": p["id"], "text": p["question"].strip()} for p in problems if isinstance(p, dict)
            and isinstance(p.get("id"), str) and p["id"] and isinstance(p.get("question"), str) and p["question"].strip()]


# ---- what the pack's KPI tree, defaults and glossary offer for what the person said. Words only, from the pack.
MAX_KPIS = 3
MAX_TERMS = 3
MIN_KPI_SCORE = 2   # chosen: one word of a KPI's name, or two words of its definition, levers or breakdowns
_SUFFIXES = ("ings", "ing", "ed", "es", "s")
_ID_TOKEN = re.compile(r"\b[A-Z]{1,3}\d{1,3}\b:?\s*")


def _stems(text: str) -> set[str]:
    def stem(w: str) -> str:
        return next((w[:-len(s)] for s in _SUFFIXES if w.endswith(s) and len(w) - len(s) >= 3), w)
    return {stem(w) for w in _words(text)}


def plain(text) -> str:
    """Pack wording for the model: ids removed. A pack figure stays (it is the industry's, never the company's own;
    `figures` tells the number guard it may be repeated)."""
    return _ID_TOKEN.sub("", " ".join(text.split())) if isinstance(text, str) else ""


_NUMBER_WORDS = {w: str(i) for i, w in enumerate("one two three four five six seven eight nine ten eleven twelve".split(), 1)}
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?|\b(?:" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def figures(*texts: str) -> list[dict]:
    """The figures in the text the model was given (pack wording, the person's words), as facts for the number
    guard; "six" counts as 6. The guard needs a group size of 5 or more, so these carry the smallest that passes:
    they are not company figures, only figures the model may repeat from what it was shown."""
    seen = {_NUMBER_WORDS.get(m.group().lower(), m.group().rstrip(",")) for m in _FIGURE.finditer(" ".join(t for t in texts if t))}
    return [{"id": "shown", "label": "figure in the text shown", "value": v, "group_size": 5} for v in sorted(seen)]


def _variant(entry: dict) -> str:
    """The pack's own plain statement of how the industry defines the KPI: the first variant that is not the
    pack's data-shaped one ("This pack: ...", which names columns)."""
    for v in entry.get("definition_variants") or []:
        t = v.get("variant") if isinstance(v, dict) else None
        if isinstance(t, str) and not t.startswith("This pack"):
            return plain(re.sub(r"^Industry practice:\s*", "", t))
    return ""


def _practice(entry: dict) -> list[str]:
    """The pack's short lines on what the industry usually does (who approves, how often, the usual range in words)."""
    rows = entry.get("usual_practice") or []
    return [t for t in (plain(r.get("text") if isinstance(r, dict) else r) for r in rows) if t]


def kpi_offers(kpis: list, defaults: dict, texts: Iterable[str]) -> list[dict]:
    """Up to MAX_KPIS KPIs from the pack's KPI tree that match what the person said, each with the pack's own
    industry-practice entry. Nothing here comes from the model."""
    mine = _stems(" ".join(texts))
    rows = [k for k in kpis if isinstance(k, dict) and isinstance(k.get("name"), str)]
    hay = {}
    for k in rows:
        d = defaults.get(k.get("id"), {})
        extra = " ".join(str(x) for x in [k.get("definition", ""), _variant(d), *_practice(d), *(d.get("levers") or []), *(d.get("breakdowns") or [])])
        hay[id(k)] = (_stems(k["name"]), _stems(extra))
    cap = max(1, len(rows) // 3)
    # a word in too many KPIs' names, or in too many KPIs' other text, cannot tell them apart
    common_n = {w for w in mine if sum(w in n for n, _ in hay.values()) > cap}
    common_e = {w for w in mine if sum(w in e for _, e in hay.values()) > cap}
    scored = []
    for k in rows:
        n, e = hay[id(k)]
        score = 2 * len((mine - common_n) & n) + len((mine - common_e) & (e - n))
        if score >= MIN_KPI_SCORE:
            scored.append((-score, len(scored), k))
    out = []
    for _, _, k in sorted(scored, key=lambda s: s[:2])[:MAX_KPIS]:
        d = defaults.get(k.get("id"), {})
        ask = [plain(c.get("question")) for c in d.get("customer_decides") or [] if isinstance(c, dict)]
        out.append({"id": k.get("id"), "name": k["name"], "usual_practice": _practice(d),  # first: it answers "how do others do it"
                    "means": _variant(d) or plain(k.get("definition")),
                    "usually_refreshed": plain(d.get("cadence")),
                    "usually_split_by": [str(b).replace("_", " ") for b in d.get("breakdowns") or []][:6],
                    "usual_levers": [v for v in (plain(str(x).replace("lever:", "").replace("_", " ")) for x in d.get("levers") or []) if v][:4],
                    "your_company_decides": [q for q in ask if q][:3], "watch_out": plain(d.get("caveat"))})
    return out


def term_offers(terms: list, texts: Iterable[str]) -> list[dict]:
    """Glossary entries whose term (or a synonym) the person used."""
    text = " ".join(texts).lower()
    out = []
    for t in terms:
        names = [t.get("term"), *(t.get("synonyms") or [])] if isinstance(t, dict) else []
        if any(isinstance(n, str) and len(n) >= 3 and re.search(rf"\b{re.escape(n.lower())}s?\b", text) for n in names) and plain(t.get("definition")):
            out.append({"term": t["term"], "definition": plain(t["definition"])})
    return out[:MAX_TERMS]
