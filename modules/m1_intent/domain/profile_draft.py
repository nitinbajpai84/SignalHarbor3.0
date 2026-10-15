"""Prepare, drafted from the company profile (LI-M1). Pure Python: the profile comes in as the dict `sh_platform.profile.read` gives
for the organiser, so restricted people and fields are already out of it. Every value carries `source`, the profile's own plain
label for where it came from ("Investment policy statement, page 2", "Interview with Sue Sponsor"). A value the profile does
not hold is left out, never made up; with nothing at all the screen opens today's wizard.

Where each value comes from:
  purpose        the strategy summary (input group 2), else the sponsor's Q1
  outcome        the sponsor's Q13 (what should be true in three months), else Q6 (what matters now)
  seats, people  the profile's people
  approver_name  a person the sponsor named as a signer in Q13, else the sponsor
  names, length  the standing defaults of the session settings
"""
from types import SimpleNamespace

from modules.m1_intent.domain.contracts import SessionSettings
from modules.m1_intent.domain.preparation import default_preparation

NAMES_SOURCE = "Standing default: each person chooses"
LENGTH_SOURCE = "Standing default length"


def _cell(item: dict, key: str):
    c = item.get(key)
    return (c.get("value"), str(c.get("from") or "")) if isinstance(c, dict) and c.get("mark") != "unknown" and c.get("value") not in (None, "") else (None, "")


def _norm(text) -> str:
    return " ".join(str(text).lower().split())


def _answers(prof: dict, qid: str, sponsors: list[str]) -> list[tuple[str, str]]:
    """(answer, source) for a question from the SPONSORS' interviews only (nobody else's answer speaks for the session's purpose). An
    answer marked restricted is skipped."""
    out = []
    for pid in sorted(p for p in prof["interviews"] if p in sponsors):
        v, frm = _cell(prof["interviews"][pid], qid.lower())
        text = " ".join(str(v.get("answer") or "").split()) if isinstance(v, dict) and not v.get("restricted") else ""
        if text and not pid.startswith("anon-"):
            out.append((text, frm))
    return out


def build(prof: dict, s: SessionSettings, text_limit: dict[str, int] | None = None) -> dict:
    """{available, fields: {name: {value, source}}, people: [{name, role, source}]} for the Prepare screen."""
    limit = text_limit or s.text_limits
    people = []
    for pid, p in prof["people"].items():
        name, frm = _cell(p, "name")
        if name:
            people.append({"id": pid, "name": str(name), "role": str(_cell(p, "role")[0] or ""), "source": frm, "sponsor": _cell(p, "is_sponsor")[0] is True})
    sponsors = [p["id"] for p in people if p["sponsor"]]
    fields: dict[str, dict] = {}

    def put(key: str, value, source: str) -> None:
        if value not in (None, "") and source:
            fields[key] = {"value": value, "source": source}

    summary, frm = _cell(prof["inputs"].get("g2", {}), "summary")
    first = (_answers(prof, "Q1", sponsors) or [(None, "")])[0]
    put("purpose", *((summary, frm) if summary else first))
    said = (_answers(prof, "Q13", sponsors) or _answers(prof, "Q6", sponsors) or [(None, "")])[0]
    put("outcome", *said)
    if fields.get("purpose"):
        fields["purpose"]["value"] = str(fields["purpose"]["value"])[:limit["purpose"]]
    if fields.get("outcome"):
        fields["outcome"]["value"] = str(fields["outcome"]["value"])[:limit["outcome"]]
    if people:
        labels = list(dict.fromkeys(p["source"] for p in people if p["source"]))
        put("seats", min(max(len(people), s.seats_min), s.seats_max), "; ".join(labels) or "the people list")
    signer = _signer(prof, people, sponsors)
    if signer:
        put("approver_name", *signer)
    if fields:  # the standing defaults are shown only beside something drafted from the company's own papers
        base = default_preparation(s, SimpleNamespace(default_id=""))  # only the standing defaults are read: the template is chosen elsewhere
        put("names", base["names"], NAMES_SOURCE)
        put("length_minutes", base["length_minutes"], LENGTH_SOURCE)
    return {"available": bool(fields), "fields": fields,
            "people": [{"name": p["name"], "role": p["role"], "source": p["source"]} for p in people]}


def _signer(prof: dict, people: list[dict], sponsors: list[str]):
    """(name, source) of the approver: the first person in the profile whose name the sponsor's Q13 answer mentions, else the sponsor."""
    for text, frm in _answers(prof, "Q13", sponsors):
        hits = sorted(((_norm(text).find(_norm(p["name"])), p) for p in people if _norm(p["name"]) in _norm(text)), key=lambda h: h[0])
        if hits:
            return hits[0][1]["name"], frm
    chair = next((p for p in people if p["sponsor"]), None)
    return (chair["name"], chair["source"]) if chair and chair["source"] else None
