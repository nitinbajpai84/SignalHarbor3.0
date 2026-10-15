"""M1 summary page: one read-only page for a session whose rooms have closed (the interview, the priorities, the pain
points, the board, the charter, who contributed what), for people who do not want to go back through the sessions.

Built from the same views as the other screens: `board_view` (the board), `together_view` (the vote) and `charter_view`
(the charter) are called, not copied, so the page cannot differ from them. It adds only what the notes carry apart from
the grouping (pain points, future signals, levers) and the contribution counts.

Privacy: public note records only (NoteStore.board), so an anonymous note has no author here; no private-room transcript
is read. The organiser's names rule (preparation["names"], missing means "choice") decides the contribution table:
  named      every note, comment and vote is counted by person, openly;
  choice     per person counts come from named notes and named comments only; anonymous ones are one separate total;
  anonymous  no per person counts at all, only the totals.
Who: the organiser and every seated person, a guest within the retention window (the guest resolver). Before the rooms close: 409.
"""
from collections import Counter

from fastapi import Request

from modules.m1_intent.api import charter as charter_api
from modules.m1_intent.api import deps
from modules.m1_intent.api.board import board_view, masked, router, route, settings
from modules.m1_intent.api.briefing import Open
from modules.m1_intent.api.together import together_view
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain.notes import load_fields
from modules.m1_intent.domain.seat_identity import seat_id_of
from modules.m1_intent.store.board import TogetherStore
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.room import RoomStore

SMALL_GROUP = 5   # chosen: at this many seated people or fewer, per person counts are not listed while anything is anonymous
NOT_YET = "The summary is ready once the private rooms have closed."
_SECTIONS = {"pain_point": "pain_points", "future_signal": "future_signals", "lever": "levers"}


def _kinds(spec: N.NoteFields, notes: list[dict]) -> dict:
    """Notes by kind, read the way the board and the charter read them: N.kind_of for the kind, N.details for what a
    note said in its kind's own fields ([{label, values}]). An intent note (or one with no kind) has no section here."""
    out: dict = {name: [] for name in _SECTIONS.values()}
    for n in notes:
        kind = N.kind_of(n)
        if kind in _SECTIONS:
            row = {"text": n["text"], "anonymous": n.get("anonymous") is True, "details": N.details(spec, kind, [n])}
            if not row["anonymous"] and n.get("author_name"):
                row["author_name"] = n["author_name"]
            out[_SECTIONS[kind]].append(row)
    return out


def _intent(options, clusters: list[dict]) -> list[dict]:
    """The room's clusters by the priority its vote gave, in the contract's order, then those the vote left open."""
    groups = [{"id": o["id"], "label": o["label"], "items": []} for o in options] + [{"id": "open", "label": "Not decided yet", "items": []}]
    by_id = {g["id"]: g for g in groups}
    for c in clusters:
        by_id[c["priority"] if c["priority"] in by_id else "open"]["items"].append(
            {"id": c["id"], "name": c["name"], "note_count": c["note_count"], "votes": c["votes"], "vote_total": c["vote_total"]})
    return groups


def _contributions(o: Open, notes: list[dict], data: dict, mode: str) -> dict:
    comments = [c for thread in data["comments"].values() for c in thread]
    votes = Counter(seat for per in data["votes"].values() for seat in per)
    totals = {"notes": len(notes), "comments": len(comments), "votes": sum(votes.values())}
    if mode == "anonymous":  # names are never shown: no row for any person
        return {"mode": mode, "totals": totals, "people": None, "anonymous": None}
    # notes and comments are matched to a seat by the name shown on them; a session never seats two people with one name (domain/room.py take_seat)
    named_notes = Counter(n["author_name"] for n in notes if n.get("author_name") and (mode == "named" or n.get("anonymous") is not True))
    named_comments = Counter(c["author_name"] for c in comments if c.get("author_name") and (mode == "named" or not c.get("anonymous")))
    seats = [x for x in (RoomStore(o.plane).get(o.session_id) or {"seats": []})["seats"] if x["state"] == "taken"]
    out = {"mode": mode, "totals": totals,
           "people": [{"name": x["name"], "role": x["role"], "notes": named_notes[x["name"]], "comments": named_comments[x["name"]],
                       "votes": votes[seat_id_of(o.plane, o.session_id, x)]} for x in seats],
           "anonymous": None}
    if mode == "choice":
        a_notes, a_comments = (sum(1 for n in notes if n.get("anonymous") is True), sum(1 for c in comments if c.get("anonymous")))
        out["anonymous"] = {"notes": a_notes, "comments": a_comments, "total": a_notes + a_comments}
        if len(seats) <= SMALL_GROUP and a_notes + a_comments > 0:  # in a small group the named counts would point at the anonymous author
            out["people"], out["small_group"] = None, True
    return out


@router.get("/sessions/{session_id}/summary")
@route
async def get_summary(request: Request, session_id: str):
    def work():
        o, s = Open(request, session_id, read_after_close=True), settings(request)
        if not B.readable(o.stage, o.s["paused_from"]):
            raise B.WrongStage(NOT_YET)
        notes = masked(o, NoteStore(o.plane).board(session_id, viewer=o.seat))
        voting = B.readable(o.stage, o.s["paused_from"], ("together", "signing", "closed"))
        together = together_view(o, s) if voting else {"clusters": []}
        cs = charter_api._settings(request)
        doc = charter_api._store(request, o.plane).read(session_id)
        charter = (charter_api.charter_view(request, o.plane, o.s, doc, cs, o.organiser, request.state.account_id)
                   if doc and charter_api._may_see(request, o.plane, o.s, cs) else None)
        seats = [x for x in (RoomStore(o.plane).get(session_id) or {"seats": []})["seats"] if x["state"] == "taken"]
        prep = o.s["preparation"]
        mode = prep.get("names") or "choice"
        return {"session": {"title": prep["purpose"], "date": o.s["created_at"][:10], "stage": o.stage, "names": mode,
                            "people": [{"name": x["name"], "role": x["role"]} for x in seats], "people_count": len(seats)},
                "intent": _intent(s.options, together["clusters"]), **_kinds(load_fields(getattr(request.app.state, "m1_contracts_dir", None)), notes),
                "board": board_view(o, s), "charter": charter,
                "can_download": bool(charter and charter["status"] == "signed"),
                "contributions": _contributions(o, notes, TogetherStore(o.plane).get(session_id), mode),
                "inputs": o.s["inputs"]}
    return await deps.blocking(work)
