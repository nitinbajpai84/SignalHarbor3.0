"""G2 Run book: the fifth artefact of a project (`run_book` in P1). Span drafts it from the build pack and the pipeline contracts (rules,
no model: the record says so); the ops manager edits it and signs it. Record `build/runbook/<iid>.json`:
{intent_id, version, sections: [{heading, lines}], drafted_by, rules_only, state: draft|signed, signature: {name, at}}.
Anything ops does not understand is an ordinary P1 comment on the run book addressed to the data engineer (the builder)."""
from __future__ import annotations

from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

HEADINGS = ("1. Sources and arrival", "2. Schedule", "3. Checks and what to do when each fails", "4. Who to call")
KIND = "run_book"
MAX_LINES, MAX_LINE = 60, 1000
NOTE = "Drafted by Span from the signed build pack and the pipeline contracts, using rules and no model. Ops edits it and signs it."


class Refusal(ValueError):
    """A plain sentence for the person; the route turns it into 409 (400 for a bad body)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(plane, iid: str):
    return plane.path("build", "runbook", f"{iid}.json")


def read(plane, iid: str) -> dict:
    try:
        return read_json_strict(_path(plane, iid), dict) or {}
    except (OSError, ValueError):
        return {}


def blocks(plane, iid: str) -> list[tuple[str, list[str]]]:
    """(heading, lines) per section for P1's document view; empty sections before the first draft."""
    got = {s.get("heading"): s.get("lines") or [] for s in read(plane, iid).get("sections") or [] if isinstance(s, dict)}
    return [(h, [str(x) for x in got.get(h, [])]) for h in HEADINGS]


def _lines(plane, rec: dict) -> list[list[str]]:
    from sh_platform.v1 import b4_load as L
    cs, _ = L.contracts_for(plane, rec["intent_id"])
    if not cs:
        raise Refusal("The build pack has no mapped source yet, so there is nothing to draft the run book from.")
    people = rec.get("people") or {}
    eng = people.get("builder") or "the data engineer"
    src, sched, checks = [NOTE], [], []
    for c in cs:
        src.append(f"{c['title']}: from {c['owner'] if c['owner'] != 'Not available yet' else 'an owner not named yet'}, "
                   f"a file each month into the landing area.")
        sched.append(f"{c['title']}: expected by working day {c['expected'].removeprefix('WD')}, late after working day {c['sla'].removeprefix('WD')} "
                     "(to be confirmed by ops).")
        checks.append(f"{c['title']}: if the file has not arrived, call its owner and raise a ticket to {eng} on the ops page.")
        for rule in c["rules"]:
            field, _, text = rule.partition(":")
            checks.append(f"{c['title']}, {field}: {text.strip()} If this fails, do not mark the period Loaded; raise a ticket to {eng} with the source and what you saw.")
    sched += ["The Watcher checks every source each day and raises a ticket to the builder for a late, missing or failed file.",
              "Once a period's files are in and the checks pass, ops marks the period Loaded on the ops page."]
    call = [f"{n}: {role}." for role, n in (("the data engineer, first call for a failed check or a late run", people.get("builder")),
                                          ("the head of data, for anything that changes a definition", people.get("head_of_data")),
                                          ("the project's owner", people.get("raiser")), ("the sponsor", people.get("sponsor"))) if n]
    call += [f"{c['owner']}: owner of {c['title']}, for a file that has not arrived." for c in cs if c["owner"] != "Not available yet"]
    return [src, sched, checks, call or ["Nobody is named on this project yet."]]


def draft(plane, rec: dict, by: str = "flow") -> dict:
    """Span's draft (a new one replaces an unsigned run book; a signed one is kept)."""
    iid = rec["intent_id"]
    with lock_for(_path(plane, iid)):
        old = read(plane, iid)
        if old.get("state") == "signed":
            raise Refusal("The run book is signed. Edit it to start a new version.")
        out = {"intent_id": iid, "version": int(old.get("version") or 0) + 1, "drafted_by": "Span", "rules_only": True, "drafted_at": _now(),
               "state": "draft", "sections": [{"heading": h, "lines": ls} for h, ls in zip(HEADINGS, _lines(plane, rec))]}
        _path(plane, iid).parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(_path(plane, iid), out)
    return out


def edit(plane, iid: str, sections, by: str) -> dict:
    """Ops replaces the lines of each section (a signed run book goes back to draft as the next version)."""
    if not isinstance(sections, list) or len(sections) != len(HEADINGS):
        raise ValueError("Send the four sections of the run book.")
    clean = []
    for h, s in zip(HEADINGS, sections):
        ls = (s or {}).get("lines") if isinstance(s, dict) else None
        if not isinstance(ls, list) or len(ls) > MAX_LINES or not all(isinstance(x, str) for x in ls):
            raise ValueError("Each section needs a list of lines.")
        clean.append({"heading": h, "lines": [x.strip()[:MAX_LINE] for x in ls if x.strip()]})
    with lock_for(_path(plane, iid)):
        old = read(plane, iid)
        if not old:
            raise Refusal("There is no run book yet. Ask Span for a draft first.")
        out = {**old, "sections": clean, "version": int(old.get("version") or 1) + (old.get("state") == "signed"), "state": "draft",
               "edited_by": by, "edited_at": _now()}
        out.pop("signature", None)
        write_json_atomic(_path(plane, iid), out)
    return out


def sign(plane, rec: dict, by: str) -> dict:
    """The ops manager signs. Refused while a comment on the run book is not resolved."""
    from sh_platform.v1 import p1_project as P
    iid = rec["intent_id"]
    left = [c for c in P.comments(plane, rec["id"], KIND) if c.get("state") != "resolved" and c.get("kind") not in P.QUIET]
    if left:
        raise Refusal(f"{len(left)} comment{'s' if len(left) > 1 else ''} on the run book {'are' if len(left) > 1 else 'is'} not resolved yet. "
                      "Resolve them before you sign.")
    with lock_for(_path(plane, iid)):
        got = read(plane, iid)
        if not got:
            raise Refusal("There is no run book yet. Ask Span for a draft first.")
        got.update(state="signed", signature={"name": by, "at": _now()})
        write_json_atomic(_path(plane, iid), got)
    if not (rec.get("people") or {}).get("ops"):
        P.set_person(plane, rec["id"], "ops", by)
    return got
