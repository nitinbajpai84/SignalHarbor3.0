"""M1-P04 routes: each person's private room with their own North (M1-08), the industry practice card (M1-10),
the problem library offer (M1-13) and notes only while the rooms are open (M1-16). Declared in manifest.yaml.

Who is "the person": the room belongs to a SEAT, and domain/seat_identity.seat_of is the one place that says which
seat the asking principal holds (a guest's token, a bound account, or the organiser). Anyone else, in this company or
another, gets the same "not found" answer as for a session that does not exist. A transcript is read by its author
here and by nobody else (D-034). Notes and their form live in api/notes.py (M1-11, M1-12).
"""
import logging
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from sh_platform.memory.summarise import background as memory_background

from modules.m1_intent.agent import north
from modules.m1_intent.agent.short_model import build_short_client
from modules.m1_intent.api import deps, session
from modules.m1_intent.domain import briefing as B
from modules.m1_intent.domain import interview_notes as IN
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import notes_quarters as Q
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.domain.seat_identity import person_name, profile_person, profile_viewer, register_names, seat_of
from modules.m1_intent.store.notes import NoteStore, SuggestionStore
from modules.m1_intent.store.sessions import SessionStore
from modules.m1_intent.store.transcripts import TranscriptStore
from modules.m1_intent.tools.pack_tools import kind_suggestions, load_guidance
from sh_platform.agents.runs import RunRegistry
from sh_platform.context_docs import context_passages
from sh_platform.context_docs.retrieval import MASK, mask_names, retrieve, whole_sentences
from sh_platform.context_docs.store import DocStore
from sh_platform.interview import engine as interview
from sh_platform.egress.providers import ProviderError, build_model_client, select_provider
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.profile import read as read_profile
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
_NO_MODEL = "North is not available right now, but your note is saved. Please carry on, or try again in a moment."
_LIBRARY_OFF = "The organiser has not switched on the problem library for this session."
_NO_LIBRARY = "There is no problem library for your industry yet."
_NO_NOTE = "We could not find that note."
WALL_PREFILL = {"q3": "Q7", "q4": "Q8"}   # wall question to the interview question whose profile prefill answers it (sources; definitions)
FINDING_LANE = {"pain": "pain_point", "signal": "future_signal"}   # what Lens found in the shared documents, by kind
_NO_SUGGESTIONS = "There are no industry suggestions for your industry yet. Please write in your own words."
LANE_NAME = {"intent": "Tracking now", "pain_point": "Missing", "future_signal": "Watch", "lever": "Levers"}  # the wall's lanes, by kind
_DRAFTED = "Thank you, that is enough for a card. I have drafted a card for the {lane} lane; confirm it when you are ready."
DRAFT_AFTER = 2   # North drafts a card once the person has answered this many times since their last card


EXTRA = (
    (R.RoomClosed, lambda e: deps.plain(409, "rooms_closed", e.message)),
    (N.NamesRule, lambda e: deps.plain(409, "names_rule", e.message)),
    (R.RoomError, lambda e: deps.plain(422, "invalid", e.message)),
    *session.EXTRA)
guarded = deps.guarded(*EXTRA)


# ---- one request's context

def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _rows(spec: N.NoteFields, t: dict) -> tuple[list[dict], list[dict]]:
    """A transcript as the screen shows it: (turns, notes). Never a seat, an account or a guest id."""
    turns = [{k: x[k] for k in ("id", "role", "text", "at", "answered", "readback") if k in x} for x in t["turns"]]
    keys = ("id", "text", "state", "source", "priority", "practice", "practice_added", "created_at", "updated_at",
            "fields", "labels_suggested", "anonymous", "restricted", "kind_suggested", "confirmed", "quarters", "quarter_drafts")
    return turns, [{**{k: x.get(k) for k in keys}, "kind": N.kind_of(x), "missing": N.missing(spec, x)} for x in t["notes"]]


class _Shelf(DocStore):
    """North's shelf as one signed-in person may draft from: documents shared with the company (`shared_full`, with their text) and the
    person's own uploads. Never another person's private file, an accepted memory or a summary of another agent's file."""

    def __init__(self, plane, account_id: str):
        super().__init__(plane)
        self._account = account_id

    def own_chunks(self, agent: str) -> list[dict]:
        """Passages from `shared_full` documents and the person's own uploads; a `shared` document gives its summary only, or nothing."""
        out = []
        for d in self.documents_for(agent):
            if d["agent"] != agent:
                continue
            if d.get("visibility") == "shared_full" or d.get("uploader") == self._account:
                out += [{"title": d["title"], "text": c["text"], "location": c.get("location"), "source": "own_document"} for c in d.get("chunks", [])]
            elif d.get("visibility") == "shared" and d.get("shared_summary"):
                out.append({"title": d["title"], "text": d["shared_summary"], "location": None, "source": "shared_summary"})
        return out

    def accepted_memories(self, agent: str) -> list[dict]:
        return []

    def shared_summaries(self, agent: str) -> list[dict]:
        return []


class Ctx:
    def __init__(self, request: Request, session_id: str):
        self.plane = _plane(request)
        self.request, self.sessions, self.transcripts = request, SessionStore(self.plane), TranscriptStore(self.plane)
        self.s = self.sessions.get(session_id)
        self.seat = seat_of(request, self.s, self.plane) if self.s else None
        self.spec = N.load_fields(getattr(request.app.state, "m1_contracts_dir", None))
        self.ok = self.seat is not None
        company = request.app.state.entitlements.company(request.state.company_id) or {}
        self.company_name = str(company.get("name") or "")
        self.guidance = load_guidance(request.app.state.packs, company.get("industry"))
        self.pack, self.problems = self.guidance.pack, self.guidance.problems
        prep = self.s["preparation"] if self.s else {}
        self.names = N.names_rule(prep)  # the organiser's rule for names on notes
        self.practice_switch = bool(prep.get("north_industry_practice"))  # the organiser's switch
        self.practice_on = self.practice_switch and bool(self.problems)   # the card on a note needs a pack problem
        self.library_on = bool(prep.get("north_problem_library")) and bool(self.problems)

    def author(self) -> str:
        """The name a by-name note carries (kept private in the draft until it is submitted)."""
        return person_name(self.request, self.s, self.plane)

    def new_note(self, *args) -> dict:
        return N.start(_retag(self, R.new_note(*args)), self.author(), self.names)

    def interview_answers(self) -> list[tuple[str, str]]:
        """The signed-in person's own interview answers (Q1-Q6), read through the shared profile. Only a person signed in with an
        account has any, and only the interview of the profile person explicitly linked to THIS account (people.<pid>.account_id,
        A-043). No match by any name: not the display name, not a name typed at a seat. An unlinked person gets none."""
        got = self.interview_profile()
        return IN.answers(got[1]["interviews"].get(got[0], {})) if got else []

    def interview_profile(self) -> tuple[str, dict] | None:
        """(profile person id, the profile as this person may see it) for the signed-in account linked to a profile person, else None."""
        if self.request.state.account_id is None or not self.s:
            return None
        pid = profile_person(self.plane, self.request.state.account_id)
        return None if pid is None else (pid, read_profile(self.plane, profile_viewer(self.request)))

    # ---- the four wall questions (A-055) and North's suggestion cards (A-056)
    def wall(self) -> Q.WallQuestions:
        return Q.load(getattr(self.request.app.state, "m1_contracts_dir", None))

    def wall_drafts(self, note: dict) -> dict:
        """Drafts for the quarters from what is already known: the person's own interview (the note's words when it came from it, and the
        interview prefill for where the data comes from and its definition), then their documents on North's shelf. Each is shown with its
        source and only kept when the person says so; one from a document is guessed."""
        drafts, src = {}, note.get("source") or {}
        if src.get("kind") == "interview":
            drafts["q1"] = {"text": note["text"], "from": src.get("from") or "your interview", "source": "interview"}
        got = self.interview_profile()
        for q, iq in WALL_PREFILL.items():  # the interview's own prefill (sh_platform/interview/engine.prefill)
            d = interview.prefill(got[1], iq, self.author()) if got else None
            if d and d["text"]:
                drafts[q] = {"text": d["text"], "from": d["from"], "source": "document"}
        try:
            for q in ("q2", "q3", "q4"):
                if q not in drafts and (hit := self._passage(note["text"], self.wall().get(q)["lead"])):
                    drafts[q] = hit
        except (OSError, ValueError, PermissionError):
            log.warning("company documents could not be read for the wall questions")
        return drafts

    def _passage(self, text: str, lead: str) -> dict | None:
        """The best passage of the person's North shelf for this card and question, as a draft, only when it shares two or more words
        with the card. ponytail: word overlap, not meaning; a model read would need North's existing call path."""
        words = set(re.findall(r"[a-z]{4,}", text.lower()))
        account = self.request.state.account_id
        if account is None:  # a link guest has no uploads of their own and reads nobody else's private files
            return None
        for h in retrieve(_Shelf(self.plane, account), "north", f"{text} {lead}", 1):
            said = whole_sentences(h["text"], text)
            if said and len(words & set(re.findall(r"[a-z]{4,}", said.lower()))) >= 2:
                return {"text": mask_names(said)[:self.spec.field_chars], "from": str(h["title"]), "source": "document"}
        return None

    def wall_start(self, note: dict) -> dict:
        note = note if "quarters" in note else Q.start(note, self.wall_drafts(note))
        return self.wall_anonymous(note)

    def wall_anonymous(self, note: dict) -> dict:
        """An anonymous card (or a session whose rule is anonymous) carries no person's name in its quarters: every name of the profile's
        people and the author's own are replaced by the mask the documents use. The wall shows these words."""
        if "quarters" not in note or not (note.get("anonymous") or self.names == "anonymous"):
            return note
        names = {self.author()}
        if self.request.state.account_id is not None:
            names |= {str(interview._v(p, "name") or "") for p in read_profile(self.plane, profile_viewer(self.request))["people"].values()}
        parts = sorted({w for n in names for w in [n, *n.split()] if len(w) >= 3}, key=len, reverse=True)
        pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in parts) + r")(?!\w)", re.I) if parts else None
        return Q.mask(note, (lambda t: pattern.sub(MASK, t)) if pattern else (lambda t: t))

    def seed_suggestions(self) -> None:
        """Once per person per room: at most three suggestion cards per lane from the pack and from the person's shared documents' findings."""
        if self.s["state"] != R.ROOM_STAGE or self.wall().max_suggestions == 0:
            return
        sid, store = self.s["id"], SuggestionStore(self.plane)
        if store.get(sid, self.seat) is not None:
            return
        found = []
        if self.request.state.account_id is not None:
            for g in read_profile(self.plane, profile_viewer(self.request))["inputs"].values():
                cell = g.get("findings") if isinstance(g, dict) else None
                for f in (cell or {}).get("value") or []:
                    kind = FINDING_LANE.get(f.get("kind"))
                    name = str(f.get("from") or "").split(":")[0].strip() or str((cell or {}).get("from") or "")
                    if kind and f.get("text") and name:
                        found.append({"kind": kind, "text": f["text"], "from": name})
        label = f"{self.guidance.label} pack" if self.guidance.label else "the industry pack"
        notes = self.transcripts.load(sid, self.seat)["notes"]
        store.put(sid, self.seat, Q.suggest(self.wall(), found + Q.from_pack(kind_suggestions(self.guidance), label), notes))

    def seed_from_interview(self) -> None:
        """Makes the person's interview answers into note drafts in their own private room, once each, and has North say what is
        still open. The drafts are unconfirmed until the person taps Keep, Change or Anonymous."""
        if self.s["state"] != R.ROOM_STAGE:
            return
        found = self.interview_answers()
        if not found:
            return
        folder = getattr(self.request.app.state, "m1_contracts_dir", None)
        words = IN.load(folder)
        have = {(n.get("source") or {}).get("q") for n in self.transcripts.load(self.s["id"], self.seat)["notes"]
                if (n.get("source") or {}).get("kind") == "interview"}
        todo = [(q, text) for q, text in found if q in words.kinds and q not in have]
        if not todo:
            return
        label, now = words.words["from_label"].format(name=self.author()), _now()

        def change(t: dict) -> None:
            for q, text in todo:
                t["notes"].append(self.wall_start(IN.draft_note(self.new_note(text, now, secrets.token_hex(8)), words.kinds[q], q, label)))
            said = IN.intro(words.words, len(todo), IN.gaps(self.spec, t["notes"]))
            t["turns"].append({"id": secrets.token_hex(8), "role": "north", "text": said, "at": now, "answered": True})

        self.transcripts.update(self.s["id"], self.seat, change)

    def view(self) -> dict:
        t = self.transcripts.load(self.s["id"], self.seat)
        turns, notes = _rows(self.spec, t)
        from_interview = any((n.get("source") or {}).get("kind") == "interview" for n in t["notes"])
        msg = R.stage_message(self.s["state"])
        return {"open": msg is None, "message": msg, "title": B.title_of(self.s["preparation"]), "turns": turns, "notes": notes,
                "names": self.names,
                "unsent": N.unsent(t["notes"], self.names),  # what the rooms' end would send for them
                "form": N.form_view(self.spec), "kinds": N.kinds_view(self.spec),
                "interview": {"drafted": from_interview, "gaps": IN.gaps(self.spec, t["notes"]) if from_interview else []},
                "wall": self.wall_so_far(),
                "suggestions": (SuggestionStore(self.plane).get(self.s["id"], self.seat) or []) if msg is None else [],
                "wall_questions": [{"id": q["id"], "lead": q["lead"], "unknown_ok": q["unknown_ok"]} for q in self.wall().questions],
                "north": {"practice_on": self.practice_on, "library_on": self.library_on,
                          "available": _model_available(self.request), **self.suggestions()}}

    def wall_so_far(self) -> dict:
        """The wall while the rooms are open, as every seat may see it: how many cards OTHER people have put in each lane (a count, never
        their words) and the names of people who have put a named card up (never the author of an anonymous or sealed card)."""
        rows = NoteStore(self.plane).board(self.s["id"], self.seat)
        return {"others": {k: sum(1 for r in rows if not r["mine"] and r["kind"] == k) for k in N.NOTE_KINDS},
                "writers": sorted({r["author_name"] for r in rows if r.get("author_name") and not r.get("anonymous") and not r.get("restricted")})}

    def suggestions(self) -> dict:
        """What others in the industry usually raise for each kind of note, labelled as a suggestion; an honest empty state."""
        got = kind_suggestions(self.guidance)
        some = any(got.values())
        return {"suggestions": got, "suggestions_label": R.PRACTICE_LABEL if some else None,
                "suggestions_empty": None if some else _NO_SUGGESTIONS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _model_env(request: Request) -> dict:
    """The model settings (keys and SH_MODEL_*) from .env and the process environment, the one mapping both the
    provider choice and the transport use. `app.state.model_env` overrides it (tests set it to {}: the real .env
    holds keys and a test must never reach a live model)."""
    override = getattr(request.app.state, "model_env", None)
    return dict(override) if override is not None else load_model_env()


def _model_available(request: Request) -> bool:
    if getattr(request.app.state, "north_model_factory", None):
        return True
    try:
        return select_provider(_model_env(request)) is not None
    except ProviderError:
        return False


def _model(ctx: Ctx, short: bool = False):
    """The model client for this company, or None (no key set up, or a setting is wrong). `short`: a one-shot
    structured task (prefill), which gets a small thinking budget; North's conversation keeps the default."""
    factory = getattr(ctx.request.app.state, "north_model_factory", None)  # tests plug a stub in here
    try:
        return factory(ctx.plane) if factory else (build_short_client if short else build_model_client)(ctx.plane, _model_env(ctx.request))
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _retag(ctx: Ctx, note: dict) -> dict:
    return R.set_practice(note, R.match_practice(ctx.problems, note["text"])) if ctx.practice_on else note


def _converse(ctx: Ctx, change, kind: str) -> dict:
    """Save the person's turn (and the note change), let North answer with one question, save that, return the
    room. `change(transcript, now)` edits the transcript and returns (turn text, readback or None)."""
    sid, seat, box = ctx.s["id"], ctx.seat, {}

    def person(t: dict) -> None:
        now = _now()
        text, box["readback"], extra = change(t, now)
        t["turns"].append({"id": secrets.token_hex(8), "role": "person", "text": text, "at": now, "kind": kind, **extra})

    t = ctx.transcripts.update(sid, seat, person)
    register_names(ctx.request, ctx.plane, ctx.s["id"])
    model, drafted = _model(ctx), None
    if model is None:
        reply, answered = _NO_MODEL, False
    else:
        documents = context_passages(ctx.plane, "north", t["turns"][-1]["text"])  # D-032

        def turn_once(documents: str = documents) -> tuple[str, bool]:
            return north.next_question(model, ctx.request.app.state.entitlements, ctx.request.state.company_id,
                                       ctx.guidance, t["turns"], practice=ctx.practice_switch, library=ctx.library_on,
                                       recorder=RunRegistry(ctx.plane), company_name=ctx.company_name,
                                       ask_how_others=getattr(ctx, "ask_how_others", False), documents=documents,
                                       background=memory_background(ctx.plane, "north", ctx.request.state.account_id))  # MEM-2
        with ThreadPoolExecutor(1) as pool:  # North's drafting runs beside its reply, so the person waits for one model call, not two
            drafting = pool.submit(_draft_from_talk, ctx, model, t) if kind == "answer" else None
            reply, answered = turn_once()
            if not answered:  # "could not finish" or a failed model call: the whole turn runs once more before the person sees it
                reply, answered = turn_once("")  # without the document passages: one the egress check refuses never costs the reply
            drafted = drafting.result() if drafting else None
    # a card with the words of one the person already has is not drafted again, and North does not say it was
    drafted = drafted if answered and drafted and N.norm_text(drafted["text"]) not in {N.norm_text(n["text"]) for n in t["notes"]} else None
    if drafted:
        reply = _DRAFTED.format(  # acknowledge, say so, and ask nothing more this turn
            lane=LANE_NAME.get(drafted["kind"], LANE_NAME["intent"]))
    turn = {"id": secrets.token_hex(8), "role": "north", "text": reply, "at": _now(), "answered": answered}
    if box["readback"]:
        turn["readback"] = box["readback"]

    def save(tr: dict) -> None:
        if drafted:
            tr["notes"].append(drafted)
        tr["turns"].append(turn)
    ctx.transcripts.update(sid, seat, save)
    return ctx.view()


def _draft_from_talk(ctx: Ctx, model, t: dict) -> dict | None:
    """North's drafted wall card from what the person has answered since their last card (at least DRAFT_AFTER answers), with the
    questions it already answers filled; unconfirmed until the person keeps, changes, marks it anonymous or puts it on the wall.
    None when North has not heard enough yet, or anything fails (the reply still reaches the person)."""
    since = max((str(n.get("created_at") or "") for n in t["notes"]), default="")
    said = [x["text"] for x in t["turns"] if x["role"] == "person" and x.get("kind") == "answer" and str(x.get("at") or "") > since]
    if len(said) < DRAFT_AFTER:
        return None
    try:
        wall = ctx.wall()
        got = north.draft_card(model, ctx.request.app.state.entitlements, ctx.request.state.company_id, said,
                               {q["id"]: q["lead"] for q in wall.questions}, recorder=RunRegistry(ctx.plane))
        if got is None:
            return None
        now = _now()
        note = ctx.new_note(R.check_text(" ".join(got["q1"].split())[:R.MAX_MESSAGE_CHARS]), now, secrets.token_hex(8))
        note = {**note, "kind": got["kind"] if got["kind"] in ctx.spec.kind_ids() else N.DEFAULT_KIND, "kind_chosen": True,
                "confirmed": False, "source": {"kind": "north", "from": "North, from your conversation"}}
        given = {q: {"text": " ".join(v.split())[:R.MAX_MESSAGE_CHARS]} for q in Q.IDS if isinstance(v := got.get(q), str) and v.strip()}
        return ctx.wall_anonymous(Q.answer(wall, Q.start(note), given))
    except Exception:  # noqa: BLE001 - a draft that cannot be made never costs the person North's reply
        log.warning("North could not draft a card from the conversation", exc_info=True)
        return None


def _find(t: dict, note_id) -> dict | None:
    return next((n for n in t["notes"] if n["id"] == note_id), None)


def _replace(t: dict, note: dict) -> None:
    t["notes"] = [note if n["id"] == note["id"] else n for n in t["notes"]]


class NotFound(Exception):
    pass


def _check(body, allowed: set, required: set = frozenset()) -> dict:
    if not isinstance(body, dict) or not set(body) <= allowed or not required <= set(body):
        raise R.RoomError(deps.BAD_READ)
    return body


async def _open_room(request: Request, session_id: str, *, rooms_open: bool):
    """(Ctx, None) or (None, the 404 answer). With rooms_open the stage must be the private rooms stage."""
    ctx = await deps.blocking(Ctx, request, session_id)
    if not ctx.ok:
        return None, deps.not_found()
    if rooms_open:
        R.check_stage(ctx.s["state"])
    return ctx, None


# ---- routes

@router.get("/sessions/{session_id}/room")
@guarded
async def my_room(request: Request, session_id: str):
    ctx, no = await _open_room(request, session_id, rooms_open=False)
    if no:
        return no

    def work():
        ctx.seed_from_interview()  # LI-M1: the person's one interview feeds their room
        ctx.seed_suggestions()     # A-056: at most three per lane, dropped when the rooms close
        return ctx.view()
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/room/messages")
@guarded
async def post_message(request: Request, session_id: str):
    ctx, no = await _open_room(request, session_id, rooms_open=True)
    if no:
        return no
    body = _check(await deps.body_object(request), {"text", "kind", "note_id", "ask_how_others", "note_kind"}, {"text"})
    text, kind = R.check_text(body["text"]), body.get("kind", "answer")
    deps.typed(request)  # chat is an answer; only "Save as a note" (kind "note") makes a note
    if not isinstance(body.get("ask_how_others", False), bool):
        raise R.RoomError("Please say yes or no to asking how others do it.")
    ctx.ask_how_others = body.get("ask_how_others", False)  # the person's explicit ask; default is listen and check
    if kind not in R.KINDS:
        raise R.RoomError("Please say whether this is a new note, an answer or a correction.")
    if body.get("note_kind", N.DEFAULT_KIND) not in ctx.spec.kind_ids():
        raise R.RoomError(N.BAD_KIND)
    note_id = body.get("note_id")
    if kind == "correction" and not isinstance(note_id, str):
        raise R.RoomError("Please say which note you are correcting.")

    def change(t: dict, now: str):
        if kind == "answer":
            return text, None, {}
        if kind == "note":
            note = ctx.new_note(text, now, secrets.token_hex(8))
            if "note_kind" in body:  # the person chose the kind when saving; otherwise it is an intent until North suggests
                note = {**note, "kind": body["note_kind"], "kind_chosen": True}
            t["notes"].append(note)
        else:
            old = _find(t, note_id)
            if old is None:
                raise NotFound
            if old["state"] != "draft":
                raise R.RoomError(N.SUBMITTED)
            note = _retag(ctx, R.correct_note(old, text, now))
            if old.get("confirmed") is False:  # Change on North's draft: the person has decided
                note = {**note, "confirmed": True}
            _replace(t, note)
        return text, {"note_id": note["id"], "text": note["text"]}, {"note_id": note["id"]}

    try:
        return await deps.blocking(_converse, ctx, change, kind)
    except NotFound:
        return deps.plain(404, "not_found", _NO_NOTE)


@router.post("/sessions/{session_id}/room/notes")
@guarded
async def start_from_library(request: Request, session_id: str):
    ctx, no = await _open_room(request, session_id, rooms_open=True)
    if no:
        return no
    body = _check(await deps.body_object(request), {"from_library", "text", "priority", "from_conversation", "from_suggestion"})
    if "from_suggestion" in body:  # A-056: picking a suggestion up makes it a card; an untouched one never counts
        return await deps.blocking(_pick_up, ctx, body["from_suggestion"])
    if body.get("from_conversation") is True:  # LI-M1: North writes the note cards from the conversation
        return await deps.blocking(_cards, ctx)
    if "from_library" not in body:
        raise R.RoomError(deps.BAD_READ)
    if not ctx.s["preparation"]["north_problem_library"]:
        return deps.plain(409, "library_off", _LIBRARY_OFF)
    problem = next((p for p in R.library_list(ctx.problems) if p["id"] == body["from_library"]), None)
    if problem is None:
        return deps.plain(404, "not_found", "We could not find that problem in the library.")
    text = R.check_text(body["text"]) if "text" in body else problem["text"]
    priority = R.clean_priority(body.get("priority"))

    def change(t: dict, now: str):
        note = ctx.new_note(text, now, secrets.token_hex(8), {"kind": "library", "problem_id": problem["id"]}, priority)
        t["notes"].append(note)
        return text, {"note_id": note["id"], "text": text}, {"note_id": note["id"]}

    return await deps.blocking(_converse, ctx, change, "library")


def _pick_up(ctx: Ctx, suggestion_id) -> dict:
    got = SuggestionStore(ctx.plane).take(ctx.s["id"], ctx.seat, suggestion_id) if isinstance(suggestion_id, str) else None
    if got is None:
        raise R.RoomError("That suggestion is no longer there.")
    card = Q.pick_up(got, ctx.new_note(got["text"], _now(), secrets.token_hex(8)))
    card["quarter_drafts"].update({q: d for q, d in ctx.wall_drafts(card).items() if q != "q1"})
    ctx.transcripts.update(ctx.s["id"], ctx.seat, lambda t: t["notes"].append(card))
    return ctx.view()


def _cards(ctx: Ctx) -> dict:
    """North's note cards from the person's conversation, as unconfirmed drafts in their own room (never a repeat of a note they have)."""
    words = IN.load(getattr(ctx.request.app.state, "m1_contracts_dir", None))
    model = _model(ctx, short=True)  # one JSON object: a small thinking budget
    if model is None:
        return {**ctx.view(), "cards_message": words.words["no_cards_model"]}
    sid, seat = ctx.s["id"], ctx.seat
    register_names(ctx.request, ctx.plane, sid)
    help_ = [f"{k['id']}: " + (", ".join(f["id"] for f in ctx.spec.extra(k["id"]) if f["kind"] == "text" and not f["person_only"]) or "none")
             for k in ctx.spec.kinds]
    rows = north.propose_cards(model, ctx.request.app.state.entitlements, ctx.request.state.company_id,
                               ctx.transcripts.load(sid, seat)["turns"], help_, words.max_cards, recorder=RunRegistry(ctx.plane))
    made, now = [], _now()

    def change(t: dict) -> None:
        seen = {N.norm_text(n["text"]) for n in t["notes"]}
        for r in rows:
            try:  # North's text is capped and checked exactly like a typed note
                text = R.check_text(" ".join(str(r.get("text") or "").split())[:R.MAX_MESSAGE_CHARS])
            except R.RoomError:
                continue
            if N.norm_text(text) in seen:
                continue
            note = IN.card_note(ctx.new_note(text, now, secrets.token_hex(8)), ctx.spec, {**r, "text": text}, now, words.words["cards_label"])
            if note:
                note = ctx.wall_start(note)
                seen.add(N.norm_text(text))
                made.append(note)
                t["notes"].append(note)

    ctx.transcripts.update(sid, seat, change)
    return {**ctx.view(), **({} if made else {"cards_message": words.words["no_cards_found"]})}


@router.post("/sessions/{session_id}/room/notes/{note_id}/practice")
@guarded
async def decide_practice(request: Request, session_id: str, note_id: str):
    ctx, no = await _open_room(request, session_id, rooms_open=True)
    if no:
        return no
    body = _check(await deps.body_object(request), {"action"}, {"action"})

    def change(t: dict) -> None:
        note = _find(t, note_id)
        if note is None:
            raise NotFound
        if note["state"] != "draft":
            raise R.RoomError(N.SUBMITTED)
        _replace(t, R.decide_practice(note, body["action"], _now()))

    def work():
        ctx.transcripts.update(ctx.s["id"], ctx.seat, change)
        return ctx.view()

    try:
        return await deps.blocking(work)
    except NotFound:
        return deps.plain(404, "not_found", _NO_NOTE)


@router.get("/sessions/{session_id}/room/library")
@guarded
async def library(request: Request, session_id: str):
    ctx, no = await _open_room(request, session_id, rooms_open=False)
    if no:
        return no
    on = bool(ctx.s["preparation"]["north_problem_library"])
    available = bool(R.library_list(ctx.problems))  # the pack has a library at all
    problems = R.library_list(ctx.problems) if on else []
    message = _NO_LIBRARY if not available else _LIBRARY_OFF if not on else None  # no library says so before "switched off"
    return {"on": on, "available": available, "label": R.PRACTICE_LABEL, "problems": problems, "message": message}
