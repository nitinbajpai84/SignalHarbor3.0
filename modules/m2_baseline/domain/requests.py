"""Requests to owners (M2-06, M2-07, M2-29): who is asked what, the answer link's token, and who still owes an answer.

A request carries KPI names and questions only, never client data or figures. There is no email service (decision), so
Nira writes a short plain email for the organiser to copy. The link token follows module 1's approver link: "ow-<request
id>-<secret>", only its SHA-256 hash is stored, it expires, can be withdrawn, and travels only in a header."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta

STATES = ("sent", "opened", "answered", "no_reply", "in_meeting")
TOKEN = re.compile(r"ow-([0-9a-f]{32})-([A-Za-z0-9_-]{43})")
OPEN_STATES = ("sent", "opened", "no_reply")  # still owes an answer
ANSWER_HERE = "You can answer here without signing in"  # the link needs no sign-in for anyone, an account holder included
LINK_GONE = {"revoked": "This link was withdrawn. Please ask for a new one.",
             "expired": "This link has expired. Please ask for a new one."}


def new_request_id() -> str:
    return secrets.token_hex(16)


def new_token(request_id: str) -> str:
    return f"ow-{request_id}-{secrets.token_urlsafe(32)}"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def owners_to_ask(kpis: list[dict]) -> list[dict]:
    """One entry per named person across the KPIs' business, data and process owners: {name, role, kpi_ids}.
    An owner nobody named (unknown or blank) is not asked; that is a finding for the sponsor, not a request."""
    people: dict[str, dict] = {}
    for k in kpis:
        for role in ("business", "data", "process"):
            name = ((k.get("owners") or {}).get(role) or {}).get("value")
            if not isinstance(name, str) or not name.strip():
                continue
            p = people.setdefault(name.strip(), {"name": name.strip(), "roles": [], "kpi_ids": []})
            if role not in p["roles"]:
                p["roles"].append(role)
            if k["id"] not in p["kpi_ids"]:
                p["kpi_ids"].append(k["id"])
    return [{"name": p["name"], "role": ", ".join(f"{r} owner" for r in p["roles"]), "kpi_ids": p["kpi_ids"]}
            for p in people.values()]


def plain_name(name: str) -> str:
    """A name as a person would write it in an email: the demo tag "(illustrative)" is not part of it."""
    return re.sub(r"\s*\(illustrative\)", "", name, flags=re.I).strip()


def question_lines(questions: list[str] | None) -> str:
    """M2-E1: the open questions an organiser added for this person, as a short list for the email ("" when there are none)."""
    return ("\n\nI would also like your answer to:\n" + "\n".join(f"- {' '.join(q.split())}" for q in questions) + "\n") if questions else ""


def email_text(owner: str, organiser: str, kpi_names: list[str], link: str | None = None, has_account: bool = False, questions: list[str] | None = None) -> dict:
    """The words for the organiser to copy, with `link` filled in at the moment the link is shown (once). Without a
    link the placeholder stays. Names and questions only: no figures, no client data. Everyone is told they can answer
    without signing in (`has_account` no longer changes the words). No time estimate: we cannot know it."""
    owner, organiser = plain_name(owner), plain_name(organiser)
    n = len(kpi_names)
    measures = "\n".join(f"- {plain_name(k)}" for k in kpi_names)
    return {"subject": f"A few questions about {n} measure{'s' if n != 1 else ''} from {organiser}",
            "body": (f"Hello {owner},\n\n{organiser} named you as an owner of {'this measure' if n == 1 else 'these measures'}:\n{measures}\n\n"
                     f"{question_lines(questions).lstrip(chr(10)) + chr(10) if questions else ''}"
                     f"Answer here: {link or '{link}'}\n\n"
                     f"{ANSWER_HERE}. No data is sent. \"I don't know\" is a fine answer.\n\nThank you,\nNira")}


def reminder_text(owner: str, organiser: str, kpi_names: list[str], questions: list[str] | None = None) -> dict:
    """The link already sent still works, so the reminder points to it instead of carrying it again."""
    owner, organiser = plain_name(owner), plain_name(organiser)
    quoted = ", ".join(f"\"{plain_name(n)}\"" for n in kpi_names)
    n = len(kpi_names)
    return {"subject": f"Reminder: a few questions about {n} measure{'s' if n != 1 else ''}",
            "body": (f"Hello {owner},\n\nA gentle reminder: {organiser} is still waiting for your answers about {quoted}. "
                     f"{question_lines(questions).lstrip(chr(10)) + chr(10) if questions else ''}"
                     "Please use the link in my earlier message. "
                     "\"I don't know\" is a fine answer.\n\nThank you,\nNira")}


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def link_state(req: dict, now: datetime) -> str:
    if req.get("revoked_at"):
        return "revoked"
    return "expired" if _t(req["expires_at"]) <= now else "open"


def days_waiting(req: dict, now: datetime) -> int:
    return max(0, (now - _t(req["sent_at"])).days)


def effective_state(req: dict, now: datetime, no_reply_days: int) -> str:
    """"no_reply" is a request nobody has opened for `no_reply_days` (slide 6: "No reply, 3 days")."""
    if req["state"] == "sent" and days_waiting(req, now) >= no_reply_days:
        return "no_reply"
    return req["state"]


def chase(req: dict, now: datetime, reminder_days: list[int]) -> dict:
    """Where this request stands in the 3 and 7 day rhythm. `remind_due` is true when a reminder day has passed that no
    marked reminder covers; `organiser_told` is true once the last reminder day has passed with no answer."""
    waited = days_waiting(req, now)
    passed = sum(1 for d in reminder_days if d <= waited)
    owes = req["state"] in OPEN_STATES
    nxt = next((d for d in reminder_days if d > waited), None)
    return {"days_waiting": waited, "remind_due": owes and passed > len(req["reminders"]),
            "organiser_told": owes and waited >= reminder_days[-1],
            "next_reminder_on": (_t(req["sent_at"]) + timedelta(days=nxt)).isoformat() if owes and nxt else None}


def nira_note(name: str, state: str, c: dict) -> str | None:
    """Nira's line for one person who still owes answers, in plain words."""
    if state not in OPEN_STATES or c["days_waiting"] == 0:
        return None
    d = c["days_waiting"]
    days = f"{d} day{'s' if d != 1 else ''}"
    if c["organiser_told"]:
        return f"{name} has not answered in {days}. You may want to answer in a meeting instead."
    if c["remind_due"]:
        return f"{name} has not replied in {days}. A reminder is due: press Remind and I will note it."
    return f"{name} has not replied in {days}. I will remind them at the next reminder day and keep you told."


def request_view(req: dict, now: datetime, q, kpi_names: dict[str, str], answered_kpis: int) -> dict:
    """One row of the outstanding view. Never carries the token or its hash."""
    state = effective_state(req, now, q.no_reply_days)
    c = chase(req, now, q.reminder_days)
    return {"id": req["id"], "owner_name": req["owner_name"], "role": req["role"], "state": state,
            "kpis": [{"id": k, "name": kpi_names.get(k, "A measure")} for k in req["kpi_ids"]],
            "sent_at": req["sent_at"], "opened_at": req.get("opened_at"), "answered_at": req.get("answered_at"),
            "reminders": list(req["reminders"]), "link": link_state(req, now), "expires_at": req["expires_at"],
            "answered_kpis": answered_kpis, "meeting": req.get("meeting"), **c, "nira": nira_note(req["owner_name"], state, c)}
