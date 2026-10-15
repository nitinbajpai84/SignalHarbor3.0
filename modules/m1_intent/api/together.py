"""M1-P07 routes, back in the room (stage 7): start it, the view everyone sees, vote (D-020), agree, comment, tick a
cluster into the charter (M1-21) and pause or resume (M1-23).

Everyone seated may vote, agree and comment, and only in their own session (briefing.Open finds the seat from the
server session or token, never from the request). Ticking, starting, pausing and resuming are the organiser's. A vote is
one per person per cluster, changeable until the room moves on; the screens only get counts and the viewer's own choice,
never who voted what. A comment is by name or anonymous, per comment, and an anonymous one holds nothing about its author.
"""
from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.api.board import group_for_close, masked, route, settings
from modules.m1_intent.api.briefing import Open, Refuse, _advance
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import timer
from modules.m1_intent.domain import together as T
from modules.m1_intent.domain.seat_identity import person_name, seat_id_of
from modules.m1_intent.store.board import BoardStore, TogetherStore
from modules.m1_intent.store.files import WrongState
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.together_shelves import ShelfStore
from modules.m1_intent.store.notes import NoteStore

router = APIRouter()


def together_view(o: Open, s: B.BoardSettings, request: Request | None = None) -> dict:  # no request (summary): no pack, so no measure codes
    T.check_readable(o.stage, o.s["paused_from"])
    notes = masked(o, NoteStore(o.plane).board(o.session_id, viewer=o.seat))
    board, data = BoardStore(o.plane).get(o.session_id), TogetherStore(o.plane).get(o.session_id)
    shown = B.view(board["clusters"], notes)
    shelves = ShelfStore(o.plane).get(o.session_id)["shelves"]
    from modules.m1_intent.api.charter import _pack_rows  # the charter's own read of the company's pack
    pack_problems, pack_kpis, _ = _pack_rows(request) if request else ([], [], "")
    links = {c["id"]: c.get("pack_problem_id") for c in board["clusters"]}
    baseline = T.latest_signed_baseline_id(o.plane)
    codes = {c["id"]: T.measure_codes(links.get(c["id"]), pack_problems, pack_kpis) for c in shown["clusters"]}
    clusters = [{**T.cluster_view(s, data, {"id": c["id"], "name": c["name"], "note_ids": c["note_ids"]}, o.seat, shelves.get(c["id"])),
                 "notes": c["notes"], "colour": c.get("colour"), "topic": o.s["preparation"]["topic"],  # a cluster's topic is its session's (IC-2g)
                  "measure_codes": codes[c["id"]], "baseline_id": baseline,
                 **T.governed_of(o.plane, baseline, codes[c["id"]])} for c in shown["clusters"]]
    ticked = sum(1 for c in clusters if c["ticked"])
    rooms = RoomStore(o.plane)
    chair = rooms.seat_of_account(o.session_id, o.s["organiser_account_id"])  # the organiser decides, so is not counted
    people = sum(1 for x in (rooms.get(o.session_id) or {"seats": []})["seats"] if x["state"] == "taken" and x != chair)
    return {"topic": o.s["preparation"]["topic"], "stage": o.stage, "paused_from": o.s["paused_from"], "held": o.stage == "paused", "organiser": o.organiser, "can_vote": o.stage == T.VOTING,
            "options": [dict(x) for x in s.options], "clusters": clusters, "on_its_own_count": len(shown["on_its_own"]),
            "ticked_count": ticked, "open_count": len(clusters) - ticked, "i_done": o.seat in data["done"],
            "done_count": len(data["done"]), "people_count": people, "names": N.names_rule(o.s["preparation"])}


def everyone_done(o: Open, data: dict) -> bool:
    """Every seated person but the organiser (who decides, and is not counted) has said "I'm done"."""
    rooms = RoomStore(o.plane)
    chair = rooms.seat_of_account(o.session_id, o.s["organiser_account_id"])
    seats = [x for x in (rooms.get(o.session_id) or {"seats": []})["seats"] if x["state"] == "taken" and x != chair]
    return bool(seats) and all(seat_id_of(o.plane, o.session_id, x) in data["done"] for x in seats)


def _in_cluster(o: Open, cluster_id: str) -> None:
    if not any(c["id"] == cluster_id for c in BoardStore(o.plane).get(o.session_id)["clusters"]):
        raise B.BoardError("We could not find that group.")


async def _body(request: Request, keys: set[str], required: set[str]):
    raw = await deps.body_object(request)
    return raw if raw is not None and required <= set(raw) <= keys else None


@router.post("/sessions/{session_id}/together")
@route
async def start_together(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        o.only_organiser()
        if o.stage != "board":
            raise WrongState("The room can come back together only from the board.")
        group_for_close(request, o, settings(request))  # North groups first when nobody has (never "Group the notes first")
        if NoteStore(o.plane).board(session_id) and not any(c["note_ids"] for c in BoardStore(o.plane).get(session_id)["clusters"]):
            raise B.WrongStage(B.NO_CLUSTERS)
        o.s = o.sessions.transition(session_id, "together")
        o.stages.start(session_id, "together", o.now)  # the together clock starts now
        from sh_platform.intents.wall import define_opened, mark_wall
        mark_wall(o.plane, session_id, "frozen_at")  # the wall was frozen when the board closed; an intent's record says when
        define_opened(request, o.plane, session_id)  # an intent's Think unfiltered closes, Define opens with its baseline, Lens starts
        return {"state": "together"}
    return await deps.blocking(work)


class _IntentReader(Open):
    """A person the intent that owns this wall names (the sponsor, an observer, a participant who never took a seat) reads the shelves
    in Define without a seat (spec 50 step 6): no seat, so no vote of their own, and nothing is changed."""

    def __init__(self, request: Request, session_id: str):
        try:
            super().__init__(request, session_id)
            return
        except Refuse:
            if not hasattr(self, "s"):  # no such session: the same answer
                raise
            refused = True
        from sh_platform.intents.charter import intent_for_session
        from sh_platform.intents.clock import _who
        from sh_platform.intents.define import relation
        rec = intent_for_session(self.plane, session_id) if refused and request.state.account_id else None
        if rec is None or self.s["state"] == "draft" or not relation(rec, _who(request), self.plane)["reader"]:
            raise Refuse(deps.not_found())
        self.organiser, self.seat = False, None


@router.get("/sessions/{session_id}/together")
@route
async def get_together(request: Request, session_id: str):
    def work():
        o = _IntentReader(request, session_id)
        if o.seat is not None or o.organiser:
            _advance(o)  # the stage's time may be up; a reader's look never moves it
        return together_view(o, settings(request), request)
    return await deps.blocking(work)


def _change(request: Request, session_id: str, cluster_id: str, change, organiser: bool = False) -> dict:
    o, s = Open(request, session_id), settings(request)
    if organiser:
        o.only_organiser()
    T.check_voting(o.stage)
    _in_cluster(o, cluster_id)
    TogetherStore(o.plane).update(session_id, lambda d: change(d, o, s))
    return together_view(o, s, request)


@router.post("/sessions/{session_id}/together/clusters/{cluster_id}/vote")
@route
async def vote(request: Request, session_id: str, cluster_id: str):
    raw = await _body(request, {"option"}, {"option"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    return await deps.blocking(_change, request, session_id, cluster_id, lambda d, o, s: T.apply_auto_ticks(
        s, T.vote(s, d, cluster_id, o.seat, raw["option"]), BoardStore(o.plane).get(session_id)["clusters"]))  # the vote rule ticks


@router.post("/sessions/{session_id}/together/clusters/{cluster_id}/agree")
@route
async def agree(request: Request, session_id: str, cluster_id: str):
    raw = await _body(request, {"agree"}, {"agree"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    return await deps.blocking(_change, request, session_id, cluster_id, lambda d, o, s: T.agree(d, cluster_id, o.seat, raw["agree"]))


@router.post("/sessions/{session_id}/together/clusters/{cluster_id}/comments")
@route
async def add_comment(request: Request, session_id: str, cluster_id: str):
    raw = await _body(request, {"text", "anonymous"}, {"text"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    deps.typed(request)

    def change(d, o, s):
        anonymous = N.apply_names(N.names_rule(o.s["preparation"]), raw.get("anonymous"))
        name = "" if anonymous is True else person_name(request, o.s, o.plane)  # an anonymous one never looks the name up
        return T.comment(s, d, cluster_id, raw["text"], anonymous, name)
    return await deps.blocking(_change, request, session_id, cluster_id, change)


@router.post("/sessions/{session_id}/together/done")
@route
async def say_done(request: Request, session_id: str):
    """A participant's "I'm done": a readiness signal the organiser sees as "4 of 6 are done". It ends nothing; ending
    the stage is the organiser's alone (drafting the charter, POST /charter, the one way the room moves on)."""
    raw = await _body(request, {"done"}, {"done"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        o, s = Open(request, session_id), settings(request)
        T.check_voting(o.stage)
        data = TogetherStore(o.plane).update(session_id, lambda d: T.done(d, o.seat, raw["done"]))
        if everyone_done(o, data):  # "I'm done" from everyone ends the stage early
            from modules.m1_intent.api.charter import close_together
            close_together(request, o.plane, session_id)
            o.reload()
        return together_view(o, s, request)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/together/clusters/{cluster_id}/tick")
@route
async def tick(request: Request, session_id: str, cluster_id: str):
    raw = await _body(request, {"ticked"}, {"ticked"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def change(d, o, s):
        return T.tick(d, BoardStore(o.plane).get(session_id)["clusters"], cluster_id, raw["ticked"])
    return await deps.blocking(_change, request, session_id, cluster_id, change, True)


@router.post("/sessions/{session_id}/together/clusters/{cluster_id}/shelf")
@route
async def shelve(request: Request, session_id: str, cluster_id: str):
    """The organiser puts a cluster on a shelf (A-058): must, should, good_to_have, future (which needs a reason).
    Every move is kept with the person and time."""
    raw = await _body(request, {"shelf", "reason"}, {"shelf"})
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        o, s = Open(request, session_id), settings(request)
        o.only_organiser()
        T.check_voting(o.stage)  # refused once the room has moved on to signing
        cluster = next((c for c in BoardStore(o.plane).get(session_id)["clusters"] if c["id"] == cluster_id), None)
        if cluster is None:
            raise B.BoardError("We could not find that group.")
        from modules.m1_intent.api.charter import _pack_rows
        pack_problems, pack_kpis, _ = _pack_rows(request)
        cluster = {**cluster, **T.governed_of(o.plane, T.latest_signed_baseline_id(o.plane), T.measure_codes(cluster.get("pack_problem_id"), pack_problems, pack_kpis))}
        by = person_name(request, o.s, o.plane) or "Organiser"
        ShelfStore(o.plane, clock=lambda: o.now).update(session_id, lambda d: T.move_to_shelf(
            d, cluster, raw["shelf"], raw.get("reason"), by, o.now, s.comment_chars, request.state.account_id))
        return together_view(o, s, request)
    return await deps.blocking(work)


# ---- pause and resume (M1-23): the stage and everything in it are kept; the stage's clock stops
@router.post("/sessions/{session_id}/pause")
@route
async def pause(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        o.only_organiser()
        stage = o.stage
        if timer.is_timed(stage):
            o.stages.started(session_id, stage, timer.parse(o.s["updated_at"]))  # the clock's start is fixed before the stop
        o.s = o.sessions.transition(session_id, "paused")  # a plain refusal where a pause is not possible (draft, closed)
        TogetherStore(o.plane).update(session_id, lambda d: {**d, "paused_at": timer.iso(o.now)})
        return {"state": "paused", "paused_from": stage}
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/resume")
@route
async def resume(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        o.only_organiser()
        if o.stage != "paused":
            raise WrongState("The session is not paused.")
        stage = o.s["paused_from"]
        data = TogetherStore(o.plane).get(session_id)
        o.s = o.sessions.transition(session_id, stage)
        if timer.is_timed(stage) and data["paused_at"]:
            held = timer.parse(data["paused_at"])
            started = o.stages.started(session_id, stage, held)
            end = timer.ends_at(stage, o.s["preparation"]["split"], started, o.stages.extensions(session_id, stage))
            if end > held and o.now > held:  # the stage was still running when it was held: it gets the held time back
                o.stages.extend(session_id, stage, (o.now - held) / 60, held)  # "at" is the moment it stopped, so it adds to the old end
        TogetherStore(o.plane).update(session_id, lambda d: {**d, "paused_at": None})
        return {"state": stage}
    return await deps.blocking(work)
