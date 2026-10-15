"""Nira's drafted messages in plain words, written from records. No model call, no figure, no row: names, dates and words only."""
from typing import Callable

KINDS = ("invite", "reminder", "sponsor_ask", "ops_report", "owner_ask")
SIGN = "\n\nThank you,\nNira"


def _who(record: dict, key: str, fallback: str) -> str:
    return str(record.get(key) or fallback)


def _link(record: dict) -> str:
    return str(record.get("link") or "the sign-in page")


def invite(r: dict) -> dict:
    org = _who(r, "organiser", "your organiser")
    return {"subject": f"You are invited: {_who(r, 'purpose', 'a Signal Harbor session')}",
            "body": (f"Hello,\n\n{org} is running a session on {_who(r, 'purpose', 'a topic for your company')} and would like you to take part. "
                     f"The wall closes {_who(r, 'closes', 'on the date the organiser sets')}.\n\nJoin or sign in here: {_link(r)}" + SIGN)}


def reminder(r: dict) -> dict:
    org = _who(r, "organiser", "your organiser")
    return {"subject": f"A reminder: {_who(r, 'purpose', 'the session')} is waiting for your card",
            "body": (f"Hello,\n\nYou have not written a card yet for {_who(r, 'purpose', 'the session')}. {org} would value your view. "
                     f"The wall closes {_who(r, 'closes', 'soon')}.\n\nWrite it here: {_link(r)}" + SIGN)}


def sponsor_ask(r: dict) -> dict:
    sponsor, org = _who(r, "sponsor", "The sponsor"), _who(r, "organiser", "there")
    return {"subject": f"A note from {sponsor}",
            "body": f"Hello {org},\n\n{sponsor} asked me to pass this on to you:\n\n\"{_who(r, 'ask', '')}\"\n\nPlease take it from here." + SIGN}


def ops_report(r: dict) -> dict:
    runs = r.get("runs") or []

    def names(status: str) -> str:
        return ", ".join(sorted({str(x.get("source")) for x in runs if x.get("status") == status})) or "none"
    return {"subject": "The daily data report",
            "body": (f"Hello,\n\nHere is how the data runs went.\n\nOn time: {names('ok')}.\nLate: {names('late')}.\nFailed: {names('failed')}.\n\n"
                     "The run log has the detail." + SIGN)}


def owner_ask(r: dict) -> dict:
    owner, source = _who(r, "owner", "there"), _who(r, "source", "the daily file")
    expected = f" and was expected {r['expected']}" if r.get("expected") else ""
    return {"subject": f"Your file is late: {source}",
            "body": f"Hello {owner},\n\nThe file {source} has not arrived{expected}. Could you send it, or tell us when it will come?" + SIGN}


WRITERS: dict[str, Callable[[dict], dict]] = {"invite": invite, "reminder": reminder, "sponsor_ask": sponsor_ask,
                                              "ops_report": ops_report, "owner_ask": owner_ask}
