"""M1-P07 routes, the board (stage 6): live counts for the organiser while the rooms are open (deck slide 14), closing
the rooms, North's grouping (M1-18), the board itself (M1-17) and the organiser's edits (M1-19).

Who is asking comes only from briefing.Open (the server session or token; a seat, or the organiser). Reading the board is
for every seated person but only once the rooms have closed; before that it is refused with a plain message. The
board is built from the public note records alone (NoteStore.board), so an anonymous note has no author anywhere here.
Edits and grouping are the organiser's. Declared in manifest.yaml AND route_permissions.yaml (default deny).
"""
import logging

from fastapi import APIRouter, Request

from modules.m1_intent.agent import gather
from modules.m1_intent.agent.short_model import build_short_client
from modules.m1_intent.api import briefing, deps
from modules.m1_intent.api.briefing import Open
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import timer
from modules.m1_intent.domain.notes import NOTE_KINDS, kind_of, load_fields
from modules.m1_intent.domain.seat_identity import person_name, profile_viewer, register_names, seat_id_of
from modules.m1_intent.store.board import BoardStore, counts
from modules.m1_intent.store.files import WrongState, lock_for
from modules.m1_intent.store.notes import NoteStore, submit_all
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.transcripts import TranscriptStore
from modules.m1_intent.tools.pack_tools import MODULE_ID, load_guidance
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.providers import ProviderError
from sh_platform.memory.summarise import remember_for_account
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
_guard = deps.guarded((N.NamesRule, lambda e: deps.plain(409, "names_rule", e.message)),
                      (B.WrongStage, lambda e: deps.plain(409, "wrong_state", e.message)),
                      (B.BoardError, lambda e: deps.plain(422, "invalid", e.message)))


def route(fn):
    """Plain answers for every refusal (Open's, the board's, the module's)."""
    return _guard(briefing.refusing(fn))


def settings(request: Request) -> B.BoardSettings:
    return B.load_settings(getattr(request.app.state, "m1_contracts_dir", None))


def masked(o: Open, notes: list[dict]) -> list[dict]:
    """`B.mask_sealed` for the person asking. A seat holder with no account is on no list."""
    return B.mask_sealed(o.plane, notes, profile_viewer(o.request) if o.request.state.account_id is not None else None)


def board_view(o: Open, s: B.BoardSettings) -> dict:
    """The board as this viewer may see it (only after the rooms close). Public note records only."""
    B.check_board_readable(o.stage, o.s["paused_from"])
    notes = masked(o, NoteStore(o.plane).board(o.session_id, viewer=o.seat))
    board = BoardStore(o.plane).get(o.session_id)

    # Assign colours: preserve colours from snapshot (North's grouping) if available, otherwise assign new ones
    clusters = board["clusters"]
    if board["snapshot"] is not None:
        # Preserve colours from snapshot
        snapshot_colours = {c["id"]: c.get("colour") for c in board["snapshot"] if "colour" in c}
        snapshot_ids = {c["id"] for c in board["snapshot"]}
        clusters = B.assign_colours(clusters, preserve_ids=snapshot_ids, previous_colours=snapshot_colours)
    else:
        clusters = B.assign_colours(clusters)

    out = B.view(clusters, notes)
    spec = load_fields(getattr(o.request.app.state, "m1_contracts_dir", None))
    return {"kinds": [{"id": k["id"], "heading": k["heading"]} for k in spec.kinds],
            "stage": o.stage, "paused_from": o.s["paused_from"], "organiser": o.organiser, "status": board["status"], "grouped_without_north": board.get("fallback") is True, "can_edit": o.organiser and o.stage in B.EDIT_STAGES,
            "can_restore": board["snapshot"] is not None, "edited": B.edited(clusters, board["snapshot"]), "by_kind": {k: sum(kind_of(n) == k for n in notes) for k in NOTE_KINDS}, "counts": {"notes": len(notes), "clusters": len(out["clusters"]),
                                                                    "on_its_own": len(out["on_its_own"])}, **out}


def _organiser_in(request: Request, session_id: str) -> Open:
    o = Open(request, session_id)
    o.only_organiser()
    return o


def _editing(request: Request, session_id: str, change) -> dict:
    """Runs one edit: `change(board, note_ids, settings)` returns the new clusters, a short kind and its detail; the
    edit is saved with the editor's name and kind (never a note's words)."""
    o, s = _organiser_in(request, session_id), settings(request)
    B.check_editable(o.stage)
    with lock_for(o.plane.root / ".m1_board_edit"):
        store = BoardStore(o.plane)
        board = store.get(session_id)
        if board["status"] == "none":
            raise B.WrongStage("North has not grouped the notes yet. Group them first.")
        note_ids = [n["id"] for n in NoteStore(o.plane).board(session_id)]
        clusters, kind, detail = change(board, note_ids, s)

        # Preserve colours from existing clusters, assign new colours to new clusters
        existing_colours = {c["id"]: c.get("colour") for c in board["clusters"] if "colour" in c}
        clusters = B.assign_colours(clusters, preserve_ids=set(existing_colours.keys()), previous_colours=existing_colours)

        store.edit(session_id, clusters, person_name(request, o.s, o.plane) or "Organiser", kind, **detail)
    return board_view(o, s)


def _remember_north(request: Request, o: Open, session_id: str) -> None:
    """MEM-2: each seated, profile-linked person's North conversation is summarised into North's memory of them. Guests have no
    account, so no link, so nothing. Never raises."""
    try:
        model = _model(request, o.plane)
        if model is None:
            return
        register_names(request, o.plane, session_id)
        seats = {seat_id_of(o.plane, session_id, s): s["account_id"] for s in (RoomStore(o.plane).get(session_id) or {}).get("seats", [])
                 if s.get("account_id")}
        organiser = o.s["organiser_account_id"]  # the organiser always has a room, seated or not
        seats[seat_id_of(o.plane, session_id, {"account_id": organiser, "participant_id": None})] = organiser
        transcripts = TranscriptStore(o.plane)
        for seat in transcripts.seats(session_id):
            if seat not in seats:
                continue
            turns = [f"{'Person' if t['role'] == 'person' else 'North'}: {t['text']}" for t in transcripts.load(session_id, seat)["turns"]]
            remember_for_account(o.plane, "north", seats[seat], turns, model=model, gate=request.app.state.entitlements,
                                 recorder=RunRegistry(o.plane), company_id=request.state.company_id, module_id=MODULE_ID,
                                 conversation=f"North, session {session_id}")
    except Exception:  # noqa: BLE001 - memory must never fail closing the rooms
        log.warning("North's memory of the rooms could not be written", exc_info=True)


# ---- the rooms close, and the live counts until then
@router.post("/sessions/{session_id}/rooms/close")
@route
async def close_rooms(request: Request, session_id: str):
    def work():
        o = _organiser_in(request, session_id)
        with lock_for(o.plane.path("intents", "m1_intent")):  # the store's own lock: the move and its hook happen once
            o.reload()
            if o.stage != "private_rooms":
                raise WrongState("The private rooms can only be closed while they are open.")
            submit_all(o.plane, session_id)  # M1-14: the notes written so far are submitted, each keeping its anonymity
            timer.on_rooms_end(o.s)
            o.s = o.sessions.transition(session_id, "board")
        from sh_platform.intents.wall import mark_wall
        mark_wall(o.plane, session_id, "rooms_closed_at")  # an intent's wall records when its rooms closed
        _remember_north(request, o, session_id)  # MEM-2: after the rooms close; a failure only logs
        return {"state": "board"}
    return await deps.blocking(work)


@router.get("/sessions/{session_id}/board/counts")
@route
async def board_counts(request: Request, session_id: str):
    """Counts only, for the organiser, while the rooms are open and after. Never a note's words (deck slide 14)."""
    def work():
        o = _organiser_in(request, session_id)
        if o.stage in ("draft", "lobby", "briefing"):
            raise B.WrongStage("The private rooms have not opened yet.")
        submitted = len(NoteStore(o.plane).board(session_id))
        return {"stage": o.stage, **counts(o.plane, session_id, submitted)}
    return await deps.blocking(work)


# ---- the board
@router.get("/sessions/{session_id}/board")
@route
async def get_board(request: Request, session_id: str):
    def work():
        o = Open(request, session_id, read_after_close=True)  # a seated guest may read the board after the close
        return board_view(o, settings(request))
    return await deps.blocking(work)


def _model(request: Request, plane):
    """North's model client for the board's short structured tasks (grouping, the charter's lines): a small thinking
    budget, same gateway as the private room. None when none is set up."""
    factory = getattr(request.app.state, "north_model_factory", None)  # tests plug a stub in here
    override = getattr(request.app.state, "model_env", None)
    try:
        return factory(plane) if factory else build_short_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


@router.post("/sessions/{session_id}/board/group")
@route
async def group(request: Request, session_id: str):
    """North groups the notes. If North cannot answer, notes are grouped by shared keywords and marked for checking;
    the organiser can regroup until North has done it."""
    def work():
        o, s = _organiser_in(request, session_id), settings(request)
        if o.stage != "board":
            raise B.WrongStage(B.NOT_YET if o.stage != "paused" else "The room is held.")
        with lock_for(o.plane.root / ".m1_board_group"):
            board = BoardStore(o.plane).get(session_id)
            if board["status"] == "done" and not board.get("fallback"):  # a grouping made without North can always be redone
                raise B.WrongStage("North has already grouped these notes. Use Restore North's grouping to undo your changes.")
            run_grouping(request, o, s)
        return board_view(o, s)
    return await deps.blocking(work)


def run_grouping(request: Request, o: Open, s: B.BoardSettings) -> list[dict]:
    """North's grouping, saved as the board and as the one to restore. The caller holds the group lock. Returns the clusters."""
    session_id = o.session_id
    store = BoardStore(o.plane)
    notes = NoteStore(o.plane).board(session_id)
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    guidance = load_guidance(request.app.state.packs, company.get("industry"))
    model = _model(request, o.plane)
    if model is not None and notes:
        register_names(request, o.plane, session_id)  # protected before anything leaves (D-007)
    # a lever is never grouped with a pain point: North groups the notes of one kind at a time
    clusters, fallback = [], False
    sealed = [n["id"] for n in notes if n.get("restricted")]  # sealed words never reach North or the keyword fallback
    notes = [n for n in notes if not n.get("restricted")]
    if sealed:
        clusters.append(B.new_cluster(B.SEALED_GROUP, sealed, "north"))  # a cluster like any other: the organiser can move its notes
    for kind_notes in B.by_kind(notes).values():
        if len(kind_notes) < s.min_notes:
            continue  # too few notes of this kind to make a group: they stay on their own
        made = gather.group_notes(model, request.app.state.entitlements, RunRegistry(o.plane), request.state.company_id,
                                  s, kind_notes, guidance)
        if made.ok:
            clusters += B.apply_grouping(s, [n["id"] for n in kind_notes], made.groups, made.problem_ids)
        else:  # North could not answer (after the transport's retries): group by shared keywords, marked for checking
            clusters += B.keyword_groups(s, kind_notes)
            fallback = True
    # Assign colours to clusters
    clusters = B.assign_colours(clusters)
    store.set_grouping(session_id, "done", clusters, fallback=fallback)
    return clusters


def group_for_close(request: Request, o: Open, s: B.BoardSettings) -> None:
    """"Close the wall" never stops at "Group the notes first" (file 24): when nobody has grouped, North groups now; when no group
    holds a note (too few notes of each kind), the notes left on their own form one group per kind, named by its lane."""
    with lock_for(o.plane.root / ".m1_board_group"):
        notes = NoteStore(o.plane).board(o.session_id)
        if not notes:
            return
        board = BoardStore(o.plane).get(o.session_id)
        if board["status"] == "none":
            run_grouping(request, o, s)
            board = BoardStore(o.plane).get(o.session_id)
        if any(c["note_ids"] for c in board["clusters"]):
            return
        spec = load_fields(getattr(request.app.state, "m1_contracts_dir", None))
        made = [B.new_cluster(spec.heading(k), [n["id"] for n in ns], "north") for k, ns in B.by_kind(notes).items() if ns]
        BoardStore(o.plane).set_grouping(o.session_id, "done", B.assign_colours(made), fallback=True)


# ---- the organiser's edits (M1-19)
@router.post("/sessions/{session_id}/board/restore")
@route
async def restore(request: Request, session_id: str):
    def work():
        def change(board, note_ids, s):
            if board["snapshot"] is None:
                raise B.WrongStage("There is no grouping from North to restore.")
            return [dict(c, note_ids=list(c["note_ids"])) for c in board["snapshot"]], "restore", {}
        return _editing(request, session_id, change)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/board/clusters")
@route
async def add_cluster(request: Request, session_id: str):
    """The organiser makes a cluster by hand: {"name": "...", "note_ids": [optional]}."""
    raw = await deps.body_object(request)
    if raw is None or "name" not in raw or not set(raw) <= {"name", "note_ids"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        def change(board, note_ids, s):
            return B.add_cluster(s, board["clusters"], note_ids, raw["name"], raw.get("note_ids") or []), "add", {}
        return _editing(request, session_id, change)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/board/notes/{note_id}/move")
@route
async def move_note(request: Request, session_id: str, note_id: str):
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"cluster_id"} or not (raw["cluster_id"] is None or isinstance(raw["cluster_id"], str)):
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        def change(board, note_ids, s):
            return B.move_note(board["clusters"], note_ids, note_id, raw["cluster_id"]), "move", {"to": raw["cluster_id"]}
        return _editing(request, session_id, change)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/board/clusters/{cluster_id}/rename")
@route
async def rename_cluster(request: Request, session_id: str, cluster_id: str):
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"name"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        def change(board, note_ids, s):
            clusters = board["clusters"]
            old = next((c["name"] for c in clusters if c["id"] == cluster_id), "")
            return B.rename(s, clusters, cluster_id, raw["name"]), "rename", {"cluster": cluster_id, "from": old, "to": " ".join(str(raw["name"]).split())}
        return _editing(request, session_id, change)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/board/clusters/{cluster_id}/split")
@route
async def split_cluster(request: Request, session_id: str, cluster_id: str):
    raw = await deps.body_object(request)
    if raw is None or not set(raw) <= {"note_ids", "name"} or "note_ids" not in raw:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        def change(board, note_ids, s):
            return B.split(s, board["clusters"], cluster_id, raw["note_ids"], raw.get("name")), "split", {"cluster": cluster_id}
        return _editing(request, session_id, change)
    return await deps.blocking(work)
