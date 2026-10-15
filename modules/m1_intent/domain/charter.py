"""The charter (M1-24, M1-27, D-022): drafted from the room's ticked problems, signed in the room or by an approver.

Pure Python, no storage. Limits, priorities and who signs come from contracts/charter.yaml; the templates (which
columns a line shows) from contracts/charter_templates.yaml. Nothing is invented: a problem with no vote shows no
priority, a problem the room gave no purpose shows an empty purpose line, and a picture link exists only where the
company's own industry pack names it.
"""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from modules.m1_intent.domain.contracts import DEFAULT_DIR, ContractError
from modules.m1_intent.domain.notes import NOTE_KINDS

_BAD = ("Cc", "Cf", "Cs", "Zl", "Zp")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
UNCHECKED = "Check the drafted 'So that' lines first."
EMPTY = "Tick at least one problem before signing."
STATUSES = ("draft", "awaiting_approver", "signed", "returned")


class CharterError(Exception):
    """A plain-words refusal. `code` picks the status the route answers with."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class CharterSettings:
    priorities: tuple[tuple[str, str], ...]   # (id, label), in listing order
    signers_required: int
    signers_required_solo: int
    sign_roles: frozenset[str]
    link_hours: int
    comment_max: int
    so_that_max: int

    def label(self, priority_id) -> str | None:
        return next((lbl for pid, lbl in self.priorities if pid == priority_id), None)

    def rank(self, priority_id) -> int:
        ids = [pid for pid, _ in self.priorities]
        return ids.index(priority_id) if priority_id in ids else len(ids)


def load_charter_settings(folder=None) -> CharterSettings:
    name = "charter.yaml"
    try:
        d = yaml.safe_load((Path(folder or DEFAULT_DIR) / name).read_text(encoding="utf-8"))
        pri = tuple((str(p["id"]), str(p["label"])) for p in d["priority_options"])
        sg, link, lim = d["signing"], d["approver_link"], d["text_limits"]
        s = CharterSettings(pri, sg["signers_required"], sg["signers_required_solo"],
                            frozenset(str(r) for r in sg["sign_roles"]), link["hours_valid"],
                            link["comment_max_chars"], lim["so_that"])
        ints = (s.signers_required, s.signers_required_solo, s.link_hours, s.comment_max, s.so_that_max)
        if not pri or not s.sign_roles or any(type(n) is not int or n < 1 for n in ints):
            raise ValueError("a setting is missing or not a whole number")
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError):
        raise ContractError(f"{name} is not valid.") from None
    return s


def sentence_case(title: str) -> str:
    """A title as a sentence: first letter capital, the rest as written (an acronym or a name keeps its capitals),
    no trailing full stop."""
    t = " ".join(title.split()).rstrip(". ")
    return t[:1].upper() + t[1:]


_SO_THAT = re.compile(r"^\s*so that\b[\s:,-]*", re.IGNORECASE)
_LEADING_WORDS = frozenset("""we our the a an it its this that there everyone nobody no each every all people staff they i you your
what when how someone anyone""".split())


def with_so_that(text: str) -> str:
    """A purpose line as a full sentence that starts "So that ", whether or not the writer typed the words: the
    first word goes lower case when it is an ordinary sentence opener (a name or an acronym keeps its capitals) and a
    full stop ends it. "" for an empty line."""
    body = _SO_THAT.sub("", text.strip()).strip().rstrip(".").strip()
    if not body:
        return ""
    first = body.split(" ", 1)[0]
    if first.lower() in _LEADING_WORDS:
        body = body[:1].lower() + body[1:]
    return f"So that {body}."


# ---- the room's result (the input)
def _text(v, limit: int = 400) -> str | None:
    if not isinstance(v, str) or not v.strip() or len(v) > limit:
        return None
    return None if any(unicodedata.category(c) in _BAD and c not in "\n\t" for c in v) else v.strip()


def tied_options(votes, priority, s: CharterSettings) -> list[str]:
    """The options level at the top of the vote when it has no winner (D-020: the tally is the priority), else []."""
    if priority is not None or not isinstance(votes, dict):
        return []
    top = max((votes.get(pid, 0) for pid, _ in s.priorities), default=0)
    leaders = [pid for pid, _ in s.priorities if votes.get(pid, 0) == top]
    return leaders if top > 0 and len(leaders) > 1 else []


def tie_text(votes: dict, s: CharterSettings) -> str:
    """"Tied: must 1 · should 2 · could 2. The room decides." (only the options that got a vote)"""
    tally = " · ".join(f"{(s.label(pid) or pid).lower()} {votes[pid]}" for pid, _ in s.priorities if votes.get(pid))
    return f"Tied: {tally}. The room decides."


def clean_details(raw) -> list[dict]:
    """[{label, values}] as the room's result gives them (what the notes of a kind said in their own details); anything
    else is left out, so a drifting producer shows nothing instead of a broken screen."""
    out = []
    for d in raw if isinstance(raw, list) else []:
        label = _text(d.get("label"), 80) if isinstance(d, dict) else None
        values = [v for v in (_text(x) for x in d.get("values") or []) if v] if label and isinstance(d.get("values"), list) else []
        if label and values:
            out.append({"label": label, "values": values})
    return out


def lists(headings: list[tuple[str, str]], problems: list[dict]) -> list[dict]:
    """The charter's four lists, always all four in this order: [{kind, heading, ids}]. A problem with no kind (a charter
    drafted before kinds existed) is a problem to solve now."""
    return [{"kind": k, "heading": h, "ids": [p["id"] for p in problems if p.get("kind", "intent") == k]} for k, h in headings]


def clean_together(raw, s: CharterSettings) -> list[dict]:
    """The clusters of the room's result in the shape contracts/charter.yaml describes; anything else is refused,
    so a drifting producer fails loudly here and not on a screen."""
    rows = raw.get("clusters") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        raise CharterError("no_result", "The room's result could not be read. Please go back to the together stage.")
    out, seen = [], set()
    for r in rows:
        if not isinstance(r, dict):
            raise CharterError("no_result", "The room's result could not be read. Please go back to the together stage.")
        cid, title = r.get("id"), _text(r.get("title"))
        title = sentence_case(title) if title else title
        pri = r.get("priority")
        ok = (isinstance(cid, str) and _ID.fullmatch(cid) and cid not in seen and title
              and (pri is None or s.label(pri) is not None)
              and all(type(r.get(k)) is int and r[k] >= 0 for k in ("note_count", "agree_count"))
              and type(r.get("ticked")) is bool)
        if not ok:
            raise CharterError("no_result", "The room's result could not be read. Please go back to the together stage.")
        seen.add(cid)
        kind = r.get("kind", "intent")  # a result from before kinds existed has none: an intent
        if kind not in NOTE_KINDS:
            raise CharterError("no_result", "The room's result could not be read. Please go back to the together stage.")
        so_that, lib, votes = r.get("so_that"), r.get("library_problem_id"), r.get("votes")
        votes = ({k: v for k, v in votes.items() if s.label(k) is not None and type(v) is int and v >= 0}
                 if isinstance(votes, dict) else None)
        out.append({"id": cid, "title": title, "kind": kind, "details": clean_details(r.get("details")),
                    "priority": pri, "votes": votes, "note_count": r["note_count"],
                    "agree_count": r["agree_count"], "ticked": r["ticked"],
                    "so_that": _text(so_that, s.so_that_max) if so_that is not None else None,
                    "so_that_draft": r.get("so_that_draft") is True,
                    "library_problem_id": lib if isinstance(lib, str) and _ID.fullmatch(lib) else None})
    return out


# ---- drafting
def build_version(clusters: list[dict], template, s: CharterSettings, *, number: int, by: str, now: str,
                  date: str, participants: int, earlier: dict | None, alone: list[dict] | None = None) -> dict:
    """A new draft from the ticked clusters. A purpose line a person edited in the earlier version is kept; if the room's
    result now says something else, that is recorded beside it as a proposal and never replaces it (rule 7)."""
    earlier_by_id = {p["id"]: p for p in (earlier or {}).get("problems", [])}
    kept = {k: p for k, p in earlier_by_id.items() if p["so_that_edited"]}
    problems = []
    for c in sorted((c for c in clusters if c["ticked"]), key=lambda c: s.rank(c["priority"])):
        mine, was = kept.get(c["id"]), earlier_by_id.get(c["id"], {})
        tied = tied_options(c.get("votes"), c["priority"], s)
        chosen = was.get("priority") if was.get("priority_edited") and was.get("priority") in tied else None  # the organiser's choice stays (rule 7)
        problems.append({
            "id": c["id"], "title": c["title"], "kind": c.get("kind", "intent"), "details": c.get("details", []),
            "priority": chosen or c["priority"], "note_count": c["note_count"],
            "votes": c.get("votes"), "tied_options": tied, "priority_edited": chosen is not None,
            "library_problem_id": c["library_problem_id"],
            "so_that": mine["so_that"] if mine else c["so_that"], "so_that_edited": mine is not None,
            "so_that_draft": bool(c["so_that"]) and c["so_that_draft"] and mine is None,  # North's draft, labelled until a person edits it
            "so_that_proposal": (c["so_that"] if mine and c["so_that"] and not c["so_that_draft"] and c["so_that"] != mine["so_that"]
                                 else None)})
    later = [{"id": c["id"], "title": c["title"]} for c in clusters if not c["ticked"]]
    return {"version": number, "status": "draft", "created_at": now, "created_by": by, "edited_at": None, "edited_by": None,
            "template": {"id": template.id, "name": template.name, "columns": list(template.columns)},
            "problems": problems, "later": later, "alone": alone or [],  # alone: notes in no group, "Left for later"
            "footer": {"date": date, "participants": participants,
                       "notes": sum(c["note_count"] for c in clusters), "later": len(later)},
            "signatures": [], "returned": None}


def edit_purposes(version: dict, edits, s: CharterSettings, by: str, now: str) -> dict:
    """The purpose lines a person wrote ("So that ..."). Only a draft nobody has signed yet can change."""
    if version["status"] != "draft" or version["signatures"]:
        raise CharterError("read_only", "This charter can no longer be changed. A signed charter changes only through a new sign-off.")
    if not isinstance(edits, dict) or not edits:
        raise CharterError("invalid", "Those details could not be read. Please try again.")
    known = {p["id"] for p in version["problems"]}
    clean: dict[str, str] = {}
    for pid, text in edits.items():
        if pid not in known:
            raise CharterError("invalid", "That problem is not in this charter.")
        t = _text(text, s.so_that_max) if isinstance(text, str) and text.strip() else ("" if isinstance(text, str) else None)
        if t is None:
            raise CharterError("invalid", f"The purpose is too long or has a character that cannot be saved. Please keep it under {s.so_that_max} characters.")
        t = with_so_that(t)  # a full "So that ..." sentence, whoever wrote it
        if len(t) > s.so_that_max:
            raise CharterError("invalid", f"The purpose is too long. Please keep it under {s.so_that_max} characters.")
        clean[pid] = t
    problems = [{**p, "so_that": clean[p["id"]] or None, "so_that_edited": bool(clean[p["id"]]), "so_that_draft": False,
                 "so_that_proposal": None}
                if p["id"] in clean else p for p in version["problems"]]
    return {**version, "problems": problems, "edited_at": now, "edited_by": by}


def confirm_purposes(version: dict, ids, by: str, now: str) -> dict:
    """The organiser accepts North's drafted line as it stands ("Use this line"): it stops being a draft and counts as
    the person's own, so a later redraft never replaces it (rule 7). Only a draft nobody has signed yet can change."""
    if version["status"] != "draft" or version["signatures"]:
        raise CharterError("read_only", "This charter can no longer be changed. A signed charter changes only through a new sign-off.")
    by_id = {p["id"]: p for p in version["problems"]}
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise CharterError("invalid", "Those details could not be read. Please try again.")
    for pid in ids:
        if pid not in by_id:
            raise CharterError("invalid", "That problem is not in this charter.")
        if not by_id[pid].get("so_that_draft"):
            raise CharterError("invalid", "That line is not a draft from North.")
    problems = [{**p, "so_that_draft": False, "so_that_edited": True, "so_that_proposal": None} if p["id"] in ids else p
                for p in version["problems"]]
    return {**version, "problems": problems, "edited_at": now, "edited_by": by}


def edit_priorities(version: dict, edits, s: CharterSettings, by: str, now: str) -> dict:
    """The organiser's choice for a problem whose vote tied (never any other: the vote is the priority, D-020), and only
    among the options that tied. Only a draft nobody has signed yet can change."""
    if version["status"] != "draft" or version["signatures"]:
        raise CharterError("read_only", "This charter can no longer be changed. A signed charter changes only through a new sign-off.")
    if not isinstance(edits, dict) or not edits:
        raise CharterError("invalid", "Those details could not be read. Please try again.")
    by_id = {p["id"]: p for p in version["problems"]}
    for pid, choice in edits.items():
        p = by_id.get(pid)
        if p is None:
            raise CharterError("invalid", "That problem is not in this charter.")
        if not p.get("tied_options"):
            raise CharterError("invalid", "Only a problem whose vote tied can be set by the organiser. The vote decides the others.")
        if choice not in p["tied_options"]:
            raise CharterError("invalid", "Please choose one of the options that tied.")
    problems = [{**p, "priority": edits[p["id"]], "priority_edited": True} if p["id"] in edits else p for p in version["problems"]]
    return {**version, "problems": problems, "edited_at": now, "edited_by": by}


# ---- signing
def signers_needed(seats: int, s: CharterSettings, wanted: int | None = None) -> int:
    """One signature by default (contracts/charter.yaml); the organiser may have asked for two in Prepare. Alone: always one."""
    return s.signers_required_solo if seats == 1 else (wanted or s.signers_required)


def sign_in_room(version: dict, signer: dict, needed: int, now: str) -> dict:
    """Adds one signature. The same person cannot sign twice (earlier product's gates.py); once enough have signed the
    charter is signed. Not allowed while an approver holds the draft."""
    if version["status"] == "awaiting_approver":
        raise CharterError("wrong_state", "This draft has been sent to an approver. Withdraw that link first if you want to sign it here.")
    if version["status"] != "draft":
        raise CharterError("read_only", "This charter is already signed, or was sent back. A signed charter changes only through a new sign-off.")
    if not version["problems"]:
        raise CharterError("empty", EMPTY)
    if any(p.get("so_that_draft") for p in version["problems"]):
        raise CharterError("unchecked_lines", UNCHECKED)
    if any(x["account_id"] == signer["account_id"] for x in version["signatures"]):
        raise CharterError("already_signed", "You have already signed. A different person needs to sign the rest.")
    sigs = [*version["signatures"], {**signer, "at": now, "how": "room"}]
    return {**version, "signatures": sigs, "status": "signed" if len(sigs) >= needed else "draft"}


def approve(version: dict, approver_name: str, now: str) -> dict:
    return {**version, "status": "signed", "signatures": [{"name": approver_name, "account_id": None, "at": now, "how": "approver"}]}


def decline(version: dict, comment: str, by: str, now: str) -> dict:
    return {**version, "status": "returned", "returned": {"comment": comment, "by": by, "at": now}}


def clean_comment(v, s: CharterSettings, required: bool) -> str:
    if v is None or v == "":
        v = ""
    if not isinstance(v, str):
        raise CharterError("invalid", "Your comment could not be read. Please try again.")
    text = v.strip()
    if required and not text:
        raise CharterError("comment_needed", "Please say why, so the room knows what to change.")
    if len(text) > s.comment_max or any(unicodedata.category(c) in _BAD and c not in "\n\t" for c in text):
        raise CharterError("invalid", f"Your comment is too long or has a character that cannot be saved. Please keep it under {s.comment_max} characters.")
    return text


# ---- the picture at sign-off (D-022): problems linked to the pack's measures, as a suggestion
def build_graph(problems: list[dict], pack_problems: list[dict], pack_kpis: list[dict], label: str) -> dict | None:
    """Only a problem that names a pack problem (library_problem_id) is linked, and only to measures that pack lists.
    None when there is nothing to draw: no pack, or no problem linked. Never another industry's content."""
    names = {k["id"]: str(k["name"]) for k in pack_kpis if isinstance(k.get("id"), str) and isinstance(k.get("name"), str)}
    by_id = {p.get("id"): p for p in pack_problems}
    links, used = [], []
    for p in problems:
        src = by_id.get(p["library_problem_id"]) if p["library_problem_id"] else None
        ids = [k for k in (src or {}).get("kpi_ids", []) if isinstance(k, str) and k in names]
        links += [{"problem": p["id"], "kpi": k} for k in ids]
        used += [k for k in ids if k not in used]
    if not links:
        return None
    return {"label": label, "problems": [{"id": p["id"], "title": p["title"]} for p in problems if any(l["problem"] == p["id"] for l in links)],
            "kpis": [{"id": k, "name": names[k]} for k in used], "links": links}
