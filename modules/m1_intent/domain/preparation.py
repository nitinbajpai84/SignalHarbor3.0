"""The preparation values of a session (M1-01) and its seats and time (M1-02): defaults, checks, plain messages.

Pure Python. Limits, presets, templates and video options come from the contract files (domain/contracts.py).
The company and the organiser are never part of these values: the server takes them from the signed-in session.
"""
import re
import unicodedata
from dataclasses import dataclass

from modules.m1_intent.domain.contracts import SPLIT_PARTS, CharterTemplates, SessionSettings

KEYS = ("purpose", "outcome", "charter_template", "seats", "length_minutes", "split",
        "north_industry_practice", "north_problem_library", "briefing_video",
        "approver_name", "approver_account_id", "names", "signers", "wall_window_days", "topic")
NAMES = ("named", "choice", "anonymous")  # how names show on notes: the organiser decides ("choice": each person, per note)
_HEX = re.compile(r"[0-9a-f]{32}")
_OK_CONTROL = "\n\t"


# What an older saved record gets for a field added later (the briefing video follows the contract's first option, "standard").
OLDER_DEFAULTS = {"north_industry_practice": False, "north_problem_library": False, "briefing_video": "standard",
                  "approver_name": "", "approver_account_id": None, "names": "choice", "signers": None, "wall_window_days": None, "topic": None}


def with_defaults(prep):
    """`prep` with any newer field it lacks filled in; anything that is not a dict is returned as it is."""
    return {**OLDER_DEFAULTS, **prep} if isinstance(prep, dict) else prep


TOPIC_MAX = 60  # a wall's topic or department: 1 to 60 characters, or none (a company's only wall needs none)
WALL_DAYS_DEFAULT, WALL_DAYS_MAX = 5, 20  # the screen shows 5 as the default; chosen: 1 to 20 working days (Monday to Friday, no holidays); 1 is the least


class PrepError(ValueError):
    """A value is not acceptable. `message` is plain words for the screen; `field` says which value."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message, self.field = message, field


@dataclass(frozen=True)
class Offers:
    """What North can offer this company: only what its industry pack holds (never another industry's)."""
    practice: bool
    problem_library: bool


def default_split(length: int, s: SessionSettings) -> dict[str, int]:
    """The default shares of the length, in whole minutes; whatever is left over goes to the last part."""
    a = length * s.default_split_percent["briefing"] // 100
    b = length * s.default_split_percent["individual"] // 100
    return {"briefing": a, "individual": b, "together": length - a - b}


def default_preparation(s: SessionSettings, t: CharterTemplates) -> dict:
    return {"purpose": "", "outcome": "", "charter_template": t.default_id, "seats": s.seats_min,
            "length_minutes": s.default_length_minutes, "split": default_split(s.default_length_minutes, s),
            "north_industry_practice": False, "north_problem_library": False,
            "briefing_video": s.briefing_video_options[0], "approver_name": "", "approver_account_id": None, "names": "choice",
            "signers": None, "wall_window_days": None, "topic": None}  # None: the charter contract's default (one signature); 2 asks for two signers


def _text(v, field: str, limit: int, label: str, required: bool = False) -> str:
    if not isinstance(v, str):
        raise PrepError(f"Please write the {label} as text.", field)
    v = v.strip()
    if required and not v:
        raise PrepError(f"Please say what the {label} is.", field)
    if len(v) > limit:
        raise PrepError(f"The {label} is too long. Please keep it under {limit} characters.", field)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Zl", "Zp") and c not in _OK_CONTROL for c in v):
        raise PrepError(f"The {label} has a character that cannot be saved.", field)
    return v


def _int(v) -> bool:
    return type(v) is int


def clean(raw: dict, base: dict, s: SessionSettings, t: CharterTemplates, offers: Offers) -> dict:
    """`base` with `raw` laid over it, fully checked. Raises PrepError with a plain message."""
    if not isinstance(raw, dict):
        raise PrepError("Those details could not be read.")
    if set(raw) - set(KEYS):
        raise PrepError("Some of the details sent are not recognised.")
    p = {**base, **raw}
    if (_int(p["length_minutes"]) and p["length_minutes"] != base.get("length_minutes")
            and raw.get("split", base.get("split")) == base.get("split")):
        p["split"] = default_split(p["length_minutes"], s)  # a new length brings a new default split, unless a new split came with it
    lim = s.text_limits
    out = {
        "purpose": _text(p["purpose"], "purpose", lim["purpose"], "purpose of the session", required=True),
        "outcome": _text(p["outcome"], "outcome", lim["outcome"], "outcome you want"),
        "approver_name": _text(p["approver_name"], "approver_name", lim["approver_name"], "approver's name"),
    }
    if t.get(p["charter_template"]) is None:
        raise PrepError("Please choose one of the charter templates on offer.", "charter_template")
    out["charter_template"] = p["charter_template"]
    if not _int(p["seats"]) or not s.seats_min <= p["seats"] <= s.seats_max:
        raise PrepError(f"Please choose between {s.seats_min} and {s.seats_max} people. "
                        f"One person means a solo session.", "seats")
    out["seats"] = p["seats"]
    n = p["length_minutes"]
    if not _int(n) or not s.custom_min <= n <= s.custom_max:
        raise PrepError(f"Please choose a length between {s.custom_min} and {s.custom_max} minutes.", "length_minutes")
    out["length_minutes"] = n
    out["split"] = _split(p["split"], n, s)
    for key, have, what in (("north_industry_practice", offers.practice, "industry practice"),
                            ("north_problem_library", offers.problem_library, "problem library")):
        if type(p[key]) is not bool:
            raise PrepError("Please answer yes or no.", key)
        if p[key] and not have:
            raise PrepError(f"North has no {what} to offer for your industry yet, so this option stays off.", key)
        out[key] = p[key]
    if p["briefing_video"] not in s.briefing_video_options:
        raise PrepError("Please choose one of the briefing video options on offer.", "briefing_video")
    out["briefing_video"] = p["briefing_video"]
    acct = p["approver_account_id"]
    if acct is not None and not (isinstance(acct, str) and _HEX.fullmatch(acct)):
        raise PrepError("That person could not be chosen as the approver.", "approver_account_id")
    out["approver_account_id"] = acct
    names = p.get("names", "choice")  # an older session has none: each person chooses
    if names not in NAMES:
        raise PrepError("Please choose how names are shown on notes: open, each person chooses, or anonymous.", "names")
    out["names"] = names
    signers = p.get("signers")  # None: the charter contract decides (one signature); an older session has none
    if signers not in (None, 1, 2) or isinstance(signers, bool):
        raise PrepError("Please choose one signer or two.", "signers")
    out["signers"] = signers
    days = p.get("wall_window_days")  # None: not chosen, the rooms keep their own length (an older session has none)
    if days is not None and (not _int(days) or not 1 <= days <= WALL_DAYS_MAX):
        raise PrepError(f"Please choose between 1 and {WALL_DAYS_MAX} working days for the wall to stay open.", "wall_window_days")
    out["wall_window_days"] = days
    topic = p.get("topic")  # None or blank: no topic (an older session has none)
    out["topic"] = _text(topic, "topic", TOPIC_MAX, "topic or department") or None if topic is not None else None
    return {k: out[k] for k in KEYS}


def template_name(v, s: SessionSettings) -> str:
    if not isinstance(v, str) or not v.strip():
        raise PrepError("Please give the template a name.", "name")
    return _text(v, "name", s.text_limits["template_name"], "template name")


def _split(v, length: int, s: SessionSettings) -> dict[str, int]:
    if not isinstance(v, dict) or set(v) != set(SPLIT_PARTS) or not all(_int(x) for x in v.values()):
        raise PrepError("Please give the minutes for the briefing, the individual rooms and together.", "split")
    if any(x < s.min_stage_minutes for x in v.values()):
        raise PrepError(f"Each part needs at least {s.min_stage_minutes} minute"
                        f"{'' if s.min_stage_minutes == 1 else 's'}.", "split")
    total = sum(v.values())
    if total != length:
        raise PrepError(f"The three parts add up to {total} minutes, but the session is {length} minutes. "
                        f"Change the parts so they add up to {length}.", "split")
    return {k: v[k] for k in SPLIT_PARTS}
