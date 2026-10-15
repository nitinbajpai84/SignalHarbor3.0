"""M1-P05 routes: the note form (M1-11), anonymous or by name per note (M1-12), submitting, and retention (M1-29).
Declared in manifest.yaml and sh_platform/route_permissions.yaml. Built on the private room (api/private_room.py):
a note is the room's draft with its form fields. Who the person is comes only from domain/seat_identity.

Nothing here returns the author of a note to anyone but the author: the person's own view is their own
transcript, and the shared notes are read only through store/notes.NoteStore.board (public records only).
"""
import functools
import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from modules.m1_intent.agent import north
from modules.m1_intent.api import deps
from modules.m1_intent.api import private_room as P
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import notes_quarters as Q
from modules.m1_intent.domain.private_room import RoomError
from modules.m1_intent.domain.seat_identity import register_names
from modules.m1_intent.store.notes import NoteStore, NotApproved, load_retention, purge, retention_plan, submit_drafts
from sh_platform.agents.loop import run_agent
from sh_platform.agents.runs import RunRegistry

router = APIRouter()
guarded = deps.guarded((NotApproved, lambda e: deps.plain(
    409, "not_approved", "That list has changed or was not approved. Please look at the list again and approve it.")),
    *P.EXTRA)
_NEEDED = "Please fill in {} before you submit this note."


PREFILL_PROMPT = (
    "You are North, the industry expert. Read what this person said about their note and fill in the fields they "
    "have already answered. Reply with ONLY one JSON object whose keys are field ids from the list you are given, "
    "plus \"kind\" when you can tell which it is: intent (something they intend to do now), pain_point (something that "
    "hurts today), future_signal (something to keep an eye on in future) or lever (something they change to move a "
    "KPI). Leave \"kind\" out when it is not clear. "
    "Use the person's own words. Leave out any field they did not speak to. Never invent a problem, a figure, a name "
    "or a rule. Never give a number for what the person believes: that field is not yours. For labels give a short "
    "list of plain words that fit; the person decides which to keep. No text outside the JSON."
)


def prefill_fields(model, gate, company_id: str, spec: N.NoteFields, note: dict, recorder=None) -> dict:
    """North's proposal for the note's empty fields (M1-11): field id to value, only ids North may help with (never a
    person-only field), or {} when the model cannot answer. A suggestion: domain/notes.prefill keeps only what is
    still empty and checks every value."""
    ask = [{"id": f["id"], "label": f["label"], "kind": f["kind"]} for f in spec.extra() if not f["person_only"]]  # every kind's details: North may suggest a kind too
    lines = [f"{a['id']}: {a['label']} ({a['kind']})" for a in ask]  # plain text lines: a list of objects is refused as rows (raw_rows)
    # only this note and the field list go in: the rest of the conversation is about other notes (its people and facts are not this note's)
    res = run_agent(model, north.build_registry(gate, [], practice=False, library=False), company_id, north.MODULE_ID,
                    north.AGENT_NAME, f"{PREFILL_PROMPT} {north.load_rules()['prefill_rule']}", {"note": note["text"], "fields": lines},
                    note["text"], recorder=recorder)
    start, end = res.text.find("{"), res.text.rfind("}")
    try:
        proposal = json.loads(res.text[start:end + 1]) if res.status == "done" and 0 <= start < end else {}
    except ValueError:
        return {}
    return {k: v for k, v in proposal.items() if k in {"kind", *(f["id"] for f in ask)}} if isinstance(proposal, dict) else {}


def _note(ctx: P.Ctx, note_id: str) -> dict:
    note = P._find(ctx.transcripts.load(ctx.s["id"], ctx.seat), note_id)
    if note is None:
        raise P.NotFound
    return note


def _not_found(fn):
    """The one plain answer for a note that is not there (or not yours: the same answer)."""
    @functools.wraps(fn)
    async def inner(*a, **k):
        try:
            return await fn(*a, **k)
        except P.NotFound:
            return deps.plain(404, "not_found", P._NO_NOTE)
    return inner


@router.post("/sessions/{session_id}/room/notes/{note_id}")
@guarded
@_not_found
async def save_note(request: Request, session_id: str, note_id: str):
    """The person's changes to one of their drafts: the problem text, priority, the kind of note, the form fields, and By name or
    Anonymous. A draft only; a submitted note is read-only."""
    ctx, no = await P._open_room(request, session_id, rooms_open=True)
    if no:
        return no
    body = P._check(await deps.body_object(request), {"text", "priority", "fields", "anonymous", "restricted", "kind", "keep", "quarters"})
    if not body:
        raise RoomError(deps.BAD_READ)
    if "restricted" in body and not isinstance(body["restricted"], bool):
        raise RoomError(deps.BAD_READ)
    deps.typed(request, ("text" in body) + sum(isinstance(v, str) and bool(v.strip()) for v in (body.get("fields") or {}).values()
                                              if isinstance(body.get("fields"), dict)))
    confirmed_count = [0]

    def change(t: dict) -> None:
        note = P._find(t, note_id)
        if note is None:
            raise P.NotFound
        new = N.edit(ctx.spec, note, {k: v for k, v in body.items() if k not in ("keep", "quarters", "restricted")}, ctx.author(), P._now(), ctx.names)
        if "restricted" in body:
            new = {**new, "restricted": body["restricted"]}
        if "quarters" in body:  # the four wall questions (A-055): typed answers are stated, Keep takes North's draft
            wall = ctx.wall()
            new = Q.answer(wall, ctx.wall_start(new), body["quarters"])
        if new.get("confirmed") is False:  # Keep, Change or Anonymous: the person has looked at North's draft and decided
            new = {**new, "confirmed": True}
            confirmed_count[0] = 1
        if "text" in body:
            new = P._retag(ctx, new)
        new = ctx.wall_anonymous(new)  # a card made anonymous keeps no name in its quarters
        if new["anonymous"]:
            NoteStore(ctx.plane).mark_anonymous(session_id, ctx.seat)  # before the note says so: a one-way flag
        P._replace(t, new)

    def work():
        ctx.transcripts.update(session_id, ctx.seat, change)
        from modules.m1_intent.store.sessions import SessionStore
        if confirmed_count[0] > 0:
            SessionStore(ctx.plane).count(session_id, cards_confirmed=confirmed_count[0])
        return ctx.view()

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/room/notes/{note_id}/prefill")
@guarded
@_not_found
async def prefill_note(request: Request, session_id: str, note_id: str):
    """North fills what is still empty from the conversation (never the belief number); labels are only suggested.
    The answer lists what is still missing, which is all North then asks about."""
    ctx, no = await P._open_room(request, session_id, rooms_open=True)
    if no:
        return no

    def work():
        t = ctx.transcripts.load(session_id, ctx.seat)
        note = P._find(t, note_id)
        if note is None:
            raise P.NotFound
        if note["state"] != "draft":
            raise RoomError(N.SUBMITTED)
        model = P._model(ctx, short=True)  # one JSON object: a small thinking budget
        if model is not None:
            register_names(request, ctx.plane, session_id)
            proposal = prefill_fields(model,request.app.state.entitlements, request.state.company_id, ctx.spec,
                                            note, recorder=RunRegistry(ctx.plane))

            def change(tr: dict) -> None:
                cur = P._find(tr, note_id)
                if cur is not None and cur["state"] == "draft":
                    P._replace(tr, N.prefill(ctx.spec, cur, proposal, P._now()))

            ctx.transcripts.update(session_id, ctx.seat, change)
        return ctx.view()

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/room/notes/{note_id}/submit")
@guarded
@_not_found
async def submit_note(request: Request, session_id: str, note_id: str):
    """Submitting is the person's act. Notes are accepted only while the rooms are open (M1-16)."""
    ctx, no = await P._open_room(request, session_id, rooms_open=True)
    if no:
        return no

    def work():
        note = _note(ctx, note_id)
        if note["state"] == "draft":
            if note.get("confirmed") is False:  # sending it is the person's decision too
                ctx.transcripts.update(session_id, ctx.seat, lambda t: P._replace(t, {**P._find(t, note_id), "confirmed": True}))
            Q.check_placeable(ctx.wall(), note)  # two of four answered (A-055)
            gaps = [f["label"] for f in ctx.spec.fields if f["required"] and f["id"] in N.missing(ctx.spec, note)]
            if gaps:
                raise RoomError(_NEEDED.format(", ".join(gaps)))
            submit_drafts(ctx.plane, session_id, ctx.seat, only=note_id)
        return ctx.view()

    return await deps.blocking(work)


# ---- retention (M1-29, D-017): see the list, then approve exactly that list
@router.post("/retention/purge")
@guarded
async def retention(request: Request):
    """No body: a dry run that lists what is past its retention period and removes nothing. `{"approve": <plan id>}`:
    removes exactly that list (and refuses if it has changed). Only a company admin; nothing runs on a schedule."""
    body = P._check(await deps.body_object(request), {"approve"})

    def work():
        plane = P._plane(request)
        rules = load_retention(request.state.company_id, getattr(request.app.state, "m1_contracts_dir", None))
        now = datetime.fromtimestamp(float(getattr(request.app.state, "m1_clock", time.time)()), timezone.utc)
        if "approve" not in body:
            return {"dry_run": True, "rules": rules, **retention_plan(plane, rules, now)}
        if not isinstance(body["approve"], str):
            raise RoomError(deps.BAD_READ)
        return {"dry_run": False, "rules": rules, **purge(plane, rules, now, body["approve"])}

    return await deps.blocking(work)
