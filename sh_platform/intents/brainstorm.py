"""IC v2 (35, 36): the Brainstorm start (five questions, related work, people, launch) and the live session (diverge, group, converge hand-over).

The intent record is `intents/<id>/intent.json` (store.py, lifecycle.py, access.py); this module adds the `session` block to it. Ideas, replies and groups
live in `intents/<id>/ideas.json` beside it (one writer, one lock). An anonymous idea carries `anon-<key>` and never a name (D-013); the key is derived,
the file never leaves the server. Every act after the start is one POST `/api/intents/{id}/session/{act}`; the session read is GET `/session`.
Converge and the outcome (37) are another card: their routes stay stubs here until it lands.
"""
import hashlib
import json
import logging
import re
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, not_yet
from sh_platform.intents import access as A
from sh_platform.intents import converge as C
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import links
from sh_platform.profile import store as pstore
from sh_platform.profile import view as pview

log = logging.getLogger(__name__)
router = APIRouter()

# ponytail: the limits, session lengths and phase minutes are proposals (35 and 36 open questions); move them to the type contract when confirmed.
STATEMENT_MAX, CONTEXT_MAX, OUTCOME_MAX, IDEA_MAX, REPLY_MAX, NAME_MAX = 200, 1000, 300, 600, 400, 80
SEATS = (4, 8)
LENGTHS = (45, 60)
PHASE_MINUTES = {"diverge": 15, "group": 10, "converge": 15}
MIN_NOTES = 2  # modules/m1_intent/contracts/board.yaml min_cluster_notes: a group of fewer stays "not grouped yet"
REGROUP_SECONDS = 30
PHASES = ("diverge", "group", "converge")
LIVE_WRITE = ("diverge", "group")
MEMBERS = frozenset({"organiser", "participant", "observer"})
DRAFT_KEYS = ("statement", "context", "good_outcome", "people", "suggested", "observers", "areas", "session_date", "session_time", "session_minutes",
              "anonymous_ideas", "affected_may_read", "related", "related_checked", "title", "purpose", "message", "step")
FIRST = {"diverge": "Add as many ideas as you can for: {s}. One idea per card. Short is fine. Do not judge or reject any idea, yours or anyone's. "
                    "You may build on an idea; you may not argue with it.",
         "group": "These are the groups I can see. Read them. Move any card that sits in the wrong group. Rename any group that is badly named. "
                  "Do not add new ideas now; add a build-on note if one occurs to you."}
_WORD = re.compile(r"[a-z]{4,}")
_STOP = frozenset("""about above after again also another because been before being between both could does doing done each from have into just
like make more most much only other over same should some such take takes than that their them then there these they this those through very want were what when
where which while will with would your""".split())
_SEEN: dict[str, dict[str, float]] = {}  # who has the session open, per intent, in this process only
_SEEN_LOCK = threading.Lock()
HERE_SECONDS = 12


class Bad(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _err(status: int, message: str, code: str | None = None) -> JSONResponse:
    # the client turns a 403 into words only when the code is not_allowed
    return JSONResponse({"error": "not_allowed" if status == 403 else (code or "refused"), "message": message}, status_code=status)


def _safe(fn):
    try:
        out = fn()
        return out if isinstance(out, JSONResponse) else JSONResponse(out)
    except Bad as e:
        return _err(e.status, e.message)
    except A.IntentRefused as e:
        return _err(e.status_code, e.detail["message"], e.detail["error"])
    except L.Refused as e:
        return _err(e.status, e.message)
    except S.VersionConflict:
        return _err(409, S.CONFLICT)
    except (PermissionError, CrossCompanyError):
        return _err(404, S.NOT_FOUND)
    except S.Unreadable:
        return _err(500, S.UNREADABLE)


# ---- pure rules (unit tested) ------------------------------------------------------------------------------------------------

def _aware(iso: str) -> datetime:
    """A recorded start: seed records hold a bare date or a naive time, read as UTC."""
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def next_workday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def prev_workday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d


def window(session_day: date) -> dict:
    """The three working days (35): the day before for ideas, the session day, the day after for late thoughts and closing."""
    return {"before": prev_workday(session_day).isoformat(), "session": session_day.isoformat(), "after": next_workday(session_day).isoformat()}


def time_box(session_day: date, tz) -> dict:
    """Working hours in the company zone: 09:00 on the day before to 17:00 on the day after (not midnight to midnight)."""
    w = window(session_day)
    starts = datetime.combine(date.fromisoformat(w["before"]), datetime.min.time().replace(hour=9), tzinfo=tz)
    ends = datetime.combine(date.fromisoformat(w["after"]), datetime.min.time().replace(hour=17), tzinfo=tz)
    return {"starts": starts.isoformat(), "ends": ends.isoformat()}


def check_answers(a: dict, today: date, organiser_pid: str | None = None) -> str | None:
    """The first missing or wrong answer in plain words, or None when all five are valid."""
    if not str(a.get("statement") or "").strip():
        return "Say what the idea or the problem is."
    if not str(a.get("good_outcome") or "").strip():
        return "Say what a good outcome would look like."
    n = len(a.get("people") or [])
    if not SEATS[0] <= n <= SEATS[1]:
        return f"{n} people picked. A Brainstorm needs four to eight." if n < SEATS[0] else f"{n} people picked. Take {n - SEATS[1]} off."
    if organiser_pid and organiser_pid in a["people"]:
        return "You are the organiser. Pick the other people."
    if not a.get("areas"):
        return "Pick at least one area."
    try:
        day = date.fromisoformat(str(a.get("session_date")))
        datetime.strptime(str(a.get("session_time")), "%H:%M")
    except ValueError:
        return "Pick a working day, tomorrow or later."
    if day.weekday() > 4 or day < next_workday(today):
        return "Pick a working day, tomorrow or later."
    if a.get("session_minutes") not in LENGTHS:
        return "Pick 45 or 60 minutes."
    return None


def keyword_groups(ideas: list[dict]) -> list[dict]:
    """North's fallback: ideas that share a word of four letters or more go together, most shared word first. No model, nothing invented.
    ponytail: crude plural-stripping, one word per group; the model grouping through the gateway can replace it."""
    words = {i["id"]: {w.rstrip("s") for w in _WORD.findall(i["text"].lower()) if w not in _STOP} for i in ideas}
    df: dict[str, int] = {}
    for ws in words.values():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    too_common = len(ideas) * 0.6 if len(ideas) >= 5 else len(ideas) + 1
    out, taken = [], set()
    for w in sorted((w for w, c in df.items() if MIN_NOTES <= c <= too_common), key=lambda w: (-df[w], w)):
        ids = [i["id"] for i in ideas if w in words[i["id"]] and i["id"] not in taken]
        if len(ids) >= MIN_NOTES:
            taken.update(ids)
            out.append({"id": secrets.token_hex(6), "name": w.capitalize(), "idea_ids": ids, "by": "north", "fallback": True})
    return out


def anon_key(salt: str, account_id: str) -> str:
    return "anon-" + hashlib.sha256(f"{salt}:{account_id}".encode()).hexdigest()[:12]


def remaining(session: dict, now: float) -> int | None:
    """Seconds left in the phase: its minutes plus any added, less the time since it started and less the time paused. None outside a timed phase."""
    ph = session.get("phase")
    if ph not in PHASES or not session.get("phase_started_at"):
        return None
    started = datetime.fromisoformat(session["phase_started_at"]).timestamp()
    stopped = float(session.get("phase_paused_s") or 0)
    if session.get("paused") and session.get("paused_at"):
        stopped += now - datetime.fromisoformat(session["paused_at"]).timestamp()
    added = sum(int(x["minutes"]) for x in session.get("extended_by") or [] if x.get("phase") == ph)
    return round((int(session.get("minutes", PHASE_MINUTES)[ph]) + added) * 60 - (now - started - stopped))


def draft_prompt(statement: str, phase: str) -> dict:
    return {"text": FIRST[phase].format(s=statement), "drafted_by": "north", "edited_by": None, "edited_at": None}


def mask_names(text: str, names: list[str]) -> str:
    """The text of an anonymous idea with the invited people's names taken out (as wall_anonymous does today)."""
    parts = {p for n in names for p in [n, *n.split()] if len(p) >= 3}
    return re.sub("|".join(re.escape(p) for p in sorted(parts, key=len, reverse=True)), "[name]", text, flags=re.I) if parts else text


def read_names(plane, rec: dict, doc: dict | None = None) -> list[str]:
    """Every name an anonymous idea must not show on read: the invited, the organiser, named authors and the company's people (cards written before the write-time mask)."""
    pp = (rec.get("people") or {})
    names = [str(p.get("name") or "") for p in pp.get("participants") or []] + [str((pp.get("organiser") or {}).get("name") or "")]
    names += [str(i.get("author") or "") for i in (doc or {}).get("ideas") or []]
    try:
        names += [str(pview._v(p, "name") or "") for p in pstore.raw(plane)["people"].values()]
    except (OSError, KeyError, ValueError, TypeError):
        logging.getLogger(__name__).warning("people names unreadable for masking", exc_info=True)
    return [n for n in dict.fromkeys(names) if n]


# ---- the ideas file ----------------------------------------------------------------------------------------------------------

def _blank() -> dict:
    return {"salt": secrets.token_hex(8), "ideas": [], "groups": [], "group_edits": [], "grouped_at": None, "grouped_count": 0, "group_note": None}


def _ideas_path(plane, iid: str):
    return plane.path("intents", iid, "ideas.json")


def _edit_ideas(plane, iid: str, change):
    """Read, change and write ideas.json under its lock. `change(doc)` returns what the caller wants back."""
    path = _ideas_path(plane, iid)
    with lock_for(path):
        doc = read_json_strict(path, dict) or _blank()
        out = change(doc)
        write_json_atomic(path, doc)
        return out


def _read_ideas(plane, iid: str) -> dict:
    return read_json_strict(_ideas_path(plane, iid), dict) or {**_blank(), "salt": ""}


def _live_ideas(doc: dict) -> list[dict]:
    return [i for i in doc["ideas"] if not i.get("withdrawn")]


def _group_of(doc: dict, idea_id: str) -> dict | None:
    return next((g for g in doc["groups"] if idea_id in g["idea_ids"]), None)


GROUP_SYSTEM = ("You are North. You group a brainstorm's ideas for the people in the room; you never judge, rank or reject an idea. "
                "Use only the ideas given. Plain English, British spelling, no em dashes, no names of people.")
ASK_GROUP = ("Group these ideas by what they are about. Use each idea id at most once and leave out an idea that fits nowhere. "
             'Name each group in at most four words. Reply with ONLY one JSON object {"groups": [{"name": "...", "ids": ["idea id"]}]}')


def model_groups(request, plane, ideas: list[dict]) -> list[dict] | None:
    """North's groups through the kernel runtime and the egress gateway (R14): idea ids and texts only, never an author or an anonymous key.
    None when the model cannot answer or gives nothing usable; the caller then groups by shared words and the screen says so."""
    from sh_platform.intents import north as N
    from sh_platform.intents.decision import with_numbers
    gate = getattr(request.app.state, "entitlements", None) if request is not None else None
    if gate is None or len(ideas) < MIN_NOTES:
        return None
    try:
        text = N._call(plane, N._model(request, plane), gate, GROUP_SYSTEM, {"facts": [], "ideas": {i["id"]: i["text"] for i in ideas}},
                       with_numbers(ASK_GROUP, " ".join(f"{i['id']} {i['text']}" for i in ideas))) or ""  # idea ids hold digits the guard would replace
        a, b = text.find("{"), text.rfind("}")
        got = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except Exception:  # noqa: BLE001 - a provider failure falls back to grouping by shared words, never breaks the person's act
        log.warning("North could not group the ideas", exc_info=True)
        return None
    known, taken, out = {i["id"] for i in ideas}, set(), []
    for g in (got or {}).get("groups") or [] if isinstance(got, dict) else []:
        name = str(g.get("name") or "").strip()[:NAME_MAX] if isinstance(g, dict) else ""
        ids = [x for x in dict.fromkeys(g.get("ids") or []) if x in known and x not in taken] if name else []
        if len(ids) >= MIN_NOTES:
            taken.update(ids)
            out.append({"id": secrets.token_hex(6), "name": name, "idea_ids": ids, "by": "north", "fallback": False})
    return out or None


def _rest(doc: dict) -> list[dict]:
    """The live ideas North may group: not those in a group people made or renamed (rule 7)."""
    held = {x for g in doc["groups"] if g.get("by") == "person" for x in g["idea_ids"]}
    return [i for i in _live_ideas(doc) if i["id"] not in held]


def _north_group(doc: dict, made: list[dict] | None = None) -> str:
    """North groups every current idea again: the model's groups when `made` holds them (ideas gone since are dropped), else by shared words
    (labelled fallback). A group people made or renamed stays as it is with its ideas (rule 7); only the rest are grouped again.
    People's moves stay in `moves`; the note says how many ideas moved and how many had been moved by people."""
    before = {i["id"]: (_group_of(doc, i["id"]) or {}).get("name") for i in _live_ideas(doc)}
    kept = [g for g in doc["groups"] if g.get("by") == "person"]
    rest = _rest(doc)
    ids = {i["id"] for i in rest}
    fit = [g for g in ({**g, "idea_ids": [x for x in g["idea_ids"] if x in ids]} for g in made or []) if len(g["idea_ids"]) >= MIN_NOTES]
    doc["groups"] = kept + ((fit or keyword_groups(rest)) if len(rest) >= MIN_NOTES else [])
    moved = [i for i in _live_ideas(doc) if before.get(i["id"]) is not None and before[i["id"]] != (_group_of(doc, i["id"]) or {}).get("name")]
    doc["grouped_at"] = datetime.now(timezone.utc).isoformat()
    doc["grouped_count"] = len(_live_ideas(doc))
    doc["group_note"] = f"I moved {len(moved)} ideas. {sum(1 for i in moved if i.get('moves'))} were moved by people before." if moved else None
    return doc["group_note"] or ""


def _group_due(doc: dict, phase: str) -> bool:
    """While ideas land (diverge only: in the group phase people's moves stand) group once enough are in, at most every 30 seconds."""
    n, last = len(_live_ideas(doc)), doc.get("grouped_at")
    stale = not last or time.time() - datetime.fromisoformat(last).timestamp() >= REGROUP_SECONDS
    return phase == "diverge" and n >= MIN_NOTES and n != doc.get("grouped_count") and stale


def _ask_then_group(ctx: "Ctx") -> str:
    """The model call runs outside the ideas lock (it can take many seconds); the result is applied under it."""
    made = ctx.ask_groups(_rest(_read_ideas(ctx.plane, ctx.iid)))
    return _edit_ideas(ctx.plane, ctx.iid, lambda d: _north_group(d, made))


_BUSY: set[str] = set()  # intents with a grouping under way, in this process only
_BUSY_LOCK = threading.Lock()


def _spawn(fn) -> None:  # tests swap this for an inline call
    threading.Thread(target=fn, daemon=True).start()


def _auto_group(ctx: "Ctx", phase: str) -> None:
    """Group while ideas land without making anyone wait: by shared words at once when no model is set up, else through the model in the
    background, one grouping per intent at a time."""
    if not _group_due(_read_ideas(ctx.plane, ctx.iid), phase):
        return
    if getattr(ctx.request.app.state, "entitlements", None) is None:
        _edit_ideas(ctx.plane, ctx.iid, lambda d: _north_group(d) if _group_due(d, phase) else None)
        return
    _group_in_background(ctx)


def _group_in_background(ctx: "Ctx") -> None:
    with _BUSY_LOCK:
        if ctx.iid in _BUSY:
            return
        _BUSY.add(ctx.iid)

    def work():
        try:
            _ask_then_group(ctx)
        except Exception:  # noqa: BLE001 - a failed background grouping leaves the ideas as they were; the next one tries again
            log.warning("grouping the ideas failed", exc_info=True)
        finally:
            with _BUSY_LOCK:
                _BUSY.discard(ctx.iid)
    _spawn(work)


# ---- who is asking -----------------------------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, request: Request, iid: str, allow=MEMBERS):
        self.request, self.iid = request, iid
        self.plane = _plane(request)
        self.rec = A.load_intent(self.plane, iid)
        if self.rec.get("type") != "brainstorm":
            raise A.IntentRefused(404, "intent_not_found", S.NOT_FOUND)
        self.me = A.Me.of(request, self.plane)
        self.roles = A.require_intent_role(request, self.rec, allow, plane=self.plane, me=self.me)
        self.organiser = "organiser" in self.roles

    def entry(self) -> dict | None:
        return next((e for e in (self.rec.get("people") or {}).get("participants") or [] if A._is_me(e, self.me)), None)

    @property
    def role(self) -> str:
        return "organiser" if self.organiser else "participant" if "participant" in self.roles else "observer"

    def ask_groups(self, ideas: list[dict]) -> list[dict] | None:
        return model_groups(self.request, self.plane, ideas)

    def owner_key(self, doc: dict, anonymous: bool) -> str:
        return anon_key(doc["salt"], self.me.account_id or self.me.name) if anonymous else (self.me.account_id or f"name:{pview.norm(self.me.name)}")

    def unnamed(self, text: str, anonymous: bool) -> str:
        """A hidden-name idea or reply is stored with the writer's own names taken out of its words (D-013: no name in the file)."""
        return mask_names(text, [n for n in (self.me.name, (self.entry() or {}).get("name"),
                                             (self.rec["people"].get("organiser") or {}).get("name") if self.organiser else None) if n]) if anonymous else text

    def need_organiser(self) -> None:
        if not self.organiser:
            raise Bad(403, "Only the organiser can do that.")

    def need_writer(self) -> None:
        if self.role == "observer":
            raise Bad(403, "You can read along. Observers do not add ideas.")
        if not self.organiser and (self.entry() or {}).get("status") != "Accepted":
            raise Bad(403, "Accept the invitation first.")


def _write(ctx: Ctx, change, kind: str | None = None, detail: dict | None = None) -> dict:
    """The one write path to the record: read fresh, version checked, indexed, all under the store's lock. An organiser act also
    appends its line to events.jsonl (spec 16, ruling 12) through the shared writer in clock.py."""
    from sh_platform.intents import clock

    def logged(rec):
        change(rec)
        if kind:
            clock._log(ctx.plane, ctx.iid, rec, {"id": ctx.me.account_id, "name": ctx.me.name}, kind, detail or {})
    with S.locked(ctx.plane):
        rec = S.read_intent(ctx.plane, ctx.iid)
        S.update_intent(ctx.plane, ctx.iid, rec["version"], logged)
        return S.read_intent(ctx.plane, ctx.iid)


def _ph(rec: dict) -> str:
    return (rec.get("session") or {}).get("phase", "not_opened")


# ---- the read ----------------------------------------------------------------------------------------------------------------

def _idea_out(i: dict, doc: dict, ctx: Ctx, names: list[str]) -> dict:
    mine_keys = (ctx.owner_key(doc, False), ctx.owner_key(doc, True))
    g = _group_of(doc, i["id"])
    text = mask_names(i["text"], names) if i["anonymous"] else i["text"]
    replies = [{"id": r["id"], "text": mask_names(r["text"], names) if r["anonymous"] else r["text"], "author": None if r["anonymous"] else r.get("author"),
                "anonymous": r["anonymous"], "at": r["at"], "mine": r["owner"] in mine_keys} for r in i.get("replies") or []]
    return {"id": i["id"], "text": text, "why": i.get("why") or "", "anonymous": i["anonymous"], "author": None if i["anonymous"] else i.get("author"),
            "mine": i["owner"] in mine_keys, "at": i["at"], "edited": any(e["kind"] == "text" for e in i.get("edits") or []), "replies": replies,
            "group_id": g["id"] if g else None, "group_name": g["name"] if g else None}


def _people_counts(rec: dict) -> dict:
    ps = (rec.get("people") or {}).get("participants") or []
    return {"total": len(ps), **{s.lower(): sum(1 for p in ps if p.get("status") == s) for s in ("Invited", "Accepted", "Declined")}}


def _here(iid: str, who: str) -> int:
    now = time.time()
    with _SEEN_LOCK:
        seen = _SEEN.setdefault(iid, {})
        seen[who] = now
        return sum(1 for t in seen.values() if now - t <= HERE_SECONDS)


def _lines(rec: dict, doc: dict, ctx: Ctx, left: int | None) -> list[str]:
    s, out = rec.get("session") or {}, []
    if s.get("phase") in PHASES and left is not None and left <= 0:
        out.append("The clock is at zero. Move on, add time or close.")
    if doc.get("group_note") and s.get("phase") in LIVE_WRITE:
        out.append(doc["group_note"])
    if ctx.organiser and s.get("phase") == "diverge" and doc["ideas"]:
        owners = {i["owner"] for i in _live_ideas(doc)}
        accepted = [p for p in rec["people"].get("participants") or [] if p.get("status") == "Accepted"]
        quiet = sum(1 for p in accepted if (p.get("account_id") or "name:" + pview.norm(p["name"])) not in owners
                    and anon_key(doc["salt"], p.get("account_id") or p["name"]) not in owners)
        if quiet:
            out.append(f"{quiet} {'person has' if quiet == 1 else 'people have'} not added an idea yet.")  # a count, never names
    return out


def _decided_in(ctx: Ctx) -> list[dict]:
    """The Decisions made from this brainstorm that the viewer may open, as id and title; any other is left out."""
    from sh_platform.intents import visibility as V
    out, viewer = [], _viewer(ctx.request)
    for to in (ctx.rec.get("links") or {}).get("to") or []:
        try:
            d = S.read_intent(ctx.plane, to) if str(to).startswith("dec-") else None
            seen = V.read_intent(ctx.plane, d, viewer) if d else None
        except Exception:  # a broken link never breaks the page
            log.warning("decided_in skipped %s", to, exc_info=True)
            continue
        if seen and seen.get("title"):
            out.append({"id": d["id"], "title": seen["title"]})
    return out


def build_view(ctx: Ctx, display: str | None = None) -> dict:
    rec = ctx.rec
    s, o, ph = rec.get("session") or {}, rec.get("outcome") or {}, _ph(rec)
    if rec["state"] == "draft":
        raise Bad(409, "This brainstorm is not open yet.")
    mine, ps = ctx.entry(), (rec["people"].get("participants") or [])
    base = {"id": rec["id"], "title": rec["title"], "purpose": rec["purpose"], "state": rec["state"], "role": ctx.role,
            "organiser": (rec["people"].get("organiser") or {}).get("name"), "statement": o.get("statement"), "context": o.get("context"), "good_outcome": o.get("good_outcome"),
            "session_at": o.get("session_at"), "session_minutes": o.get("session_minutes"), "anonymous_allowed": bool(o.get("anonymous_ideas")),
            "window": window(datetime.fromisoformat(o["session_at"]).date()) if o.get("session_at") else None,
            "starts": (rec.get("time_box") or {}).get("starts"), "ends": (rec.get("time_box") or {}).get("ends"),
            "my_status": (mine or {}).get("status"), "counts": _people_counts(rec) if ctx.organiser else None,
            "invited": [{"name": p["name"], "status": p.get("status"), "reason": p.get("reason")} for p in ps] if ctx.organiser else None,
            "message": (rec.get("start_answers") or {}).get("message") if ctx.organiser else None}
    if ctx.role == "participant" and (mine or {}).get("status") != "Accepted":
        return {**base, "mode": "invitation" if (mine or {}).get("status") == "Invited" else "declined", "ideas": [], "groups": []}
    if ph in LIVE_WRITE and not s.get("paused"):
        _auto_group(ctx, ph)
    doc = _read_ideas(ctx.plane, rec["id"])
    live = _live_ideas(doc)
    names = read_names(ctx.plane, rec, doc)
    left = remaining(s, time.time()) if ph in PHASES and ph != "converge" else None  # the count runs to the end of the time box, not a phase timer
    mode = "before" if ph == "not_opened" else "closed" if ph == "closed" else "live"
    mine_keys = (ctx.owner_key(doc, False), ctx.owner_key(doc, True))
    shown = [i for i in live if mode != "before" or i["owner"] in mine_keys]  # pre-thinking is private to its author
    groups = [{"id": g["id"], "name": g["name"], "by": g["by"], "fallback": g.get("fallback", False),
               "count": sum(1 for x in g["idea_ids"] if any(i["id"] == x for i in live))} for g in doc["groups"]]
    groups = [g for g in groups if g["count"]] if mode != "before" else []
    starts = (rec.get("time_box") or {}).get("starts")
    out = {**base, "mode": mode, "paused": bool(s.get("paused")), "phase": ph, "remaining_seconds": left, "prompts": s.get("prompts") or {},
           "north_lines": _lines(rec, doc, ctx, left), "ideas_count": len(live) if mode != "before" else None, "groups": groups,
           "here": {"n": C.seats(rec), "total": len(ps) + 1} if mode == "live" else None,  # seated people, not who polled in the last seconds
           "ideas_open": bool(starts) and datetime.now(timezone.utc) >= _aware(starts),
           "grouped_by_words": any(g.get("fallback") for g in doc["groups"]), "can_add": _can_add(ctx, rec),
           "decided_in": _decided_in(ctx)}
    if display == "projector":  # counts and group names only: no idea text, replies, authors or the North panel
        return {k: v for k, v in out.items() if k not in ("north_lines", "counts", "invited", "message", "organiser")} | {"ideas": [], "ideas_count": len(live)}
    out["ideas"] = [_idea_out(i, doc, ctx, names) for i in sorted(shown, key=lambda x: x["at"], reverse=True)]
    if ctx.organiser and mode == "before":  # counts only: the organiser never reads pre-thinking
        out["prethink"] = {"authors": len({i["owner"] for i in live}), "ideas": len(live), "invited": len(ps)}
    return out


def _can_add(ctx: Ctx, rec: dict) -> bool:
    s = rec.get("session") or {}
    if ctx.role == "observer" or rec["state"] not in ("open", "in_session"):
        return False
    return (s.get("phase") in LIVE_WRITE and not s.get("paused")) or s.get("phase", "not_opened") == "not_opened"


# ---- start: draft, related work, people --------------------------------------------------------------------------------------

def _profile_people(ctx: Ctx) -> list[dict]:
    """The people the organiser may see. The account link stays on the server."""
    raw, seen = pstore.raw(ctx.plane)["people"], pview.read(ctx.plane, _viewer(ctx.request))["people"]
    def tags(p):  # the areas an admin tagged this person to (05): a stated list only
        c = p.get("areas")
        return [str(x) for x in c["value"]] if isinstance(c, dict) and c.get("mark") == "stated" and isinstance(c.get("value"), list) else []
    out = [{"id": pid, "name": pview._v(p, "name") or pid, "role": pview._v(p, "role") or "", "team": pview._v(p, "team") or "",
            "areas": tags(p), "account_id": links._account_of(p)} for pid, p in raw.items() if pid in seen]
    return sorted(out, key=lambda x: x["name"].lower())


def _words(text: str) -> set[str]:
    return {w.rstrip("s") for w in _WORD.findall(str(text).lower()) if w not in _STOP}


def related(ctx: Ctx, statement: str) -> list[dict]:
    """Intents and backlog items the viewer may see that share words with the statement, each with one reason. Titles and purposes only."""
    want, out = _words(statement), []
    for r in S.list_for_viewer(ctx.plane, _viewer(ctx.request)) if want else []:
        hit = sorted(want & _words(f"{r['title']} {r['purpose']}"))
        if hit and r["id"] != ctx.iid and r["state"] != "draft":
            out.append({"kind": "intent", "ref": r["id"], "type": r["type"], "title": r["title"], "state": r["state"],
                        "ends": r["time_box"].get("ends") or "", "why": "Both mention: " + ", ".join(hit[:3]) + ".", "n": len(hit)})
    try:
        items = (read_json_strict(ctx.plane.path("intents", "backlog.json"), dict) or {}).get("items") or []
    except (OSError, ValueError):
        items = []
    for b in items if want else []:
        hit = sorted(want & _words(b.get("title", "")))
        if hit and not b.get("dropped") and (b.get("raised_by") == ctx.me.account_id or "company_admin" in ctx.me.roles
                                             or pview.norm(b.get("area") or "") in ctx.me.areas):
            out.append({"kind": "backlog", "ref": b.get("id"), "type": "backlog", "title": b.get("title"), "state": b.get("status") or "", "ends": "",
                        "why": "Both mention: " + ", ".join(hit[:3]) + ".", "n": len(hit)})
    seen, rows = set(), []  # each piece of work once: by id, and by type and title (the same question asked four times is one line)
    for x in sorted(out, key=lambda x: (-x["n"], x["ends"] or "")):
        key = (x["type"], " ".join(str(x["title"]).lower().split()))
        if x["ref"] in seen or key in seen:
            continue
        seen.update((x["ref"], key))
        rows.append({k: v for k, v in x.items() if k != "n"})
    return rows[:5]


def suggest_people(ctx: Ctx, statement: str, areas: list[str], picked: list[str]) -> dict:
    """Everyone the organiser may see, and North's suggestions each with one reason. Interview answers are never quoted; restricted ones are never read."""
    people = [p for p in _profile_people(ctx) if p["id"] != ctx.me.person_id]
    flat = lambda x: pview.norm(str(x).replace("-", " ").replace("_", " "))  # noqa: E731
    want, tagged, line = _words(statement), {flat(a) for a in areas}, f" {pview.norm(statement)} "
    interviews, past = pstore.raw(ctx.plane)["interviews"], {}
    for r in S.list_for_viewer(ctx.plane, _viewer(ctx.request)):
        if r["type"] == "brainstorm" and r["state"] != "draft" and r["id"] != ctx.iid:
            for e in ((S.read_intent(ctx.plane, r["id"]) or {}).get("people") or {}).get("participants") or []:
                past.setdefault(e.get("person_id"), r["title"])
    rows = []
    for p in people:
        team, hit, why = flat(p["team"]), next((a for a in p["areas"] if flat(a) in tagged), None), None
        if team and team in tagged:
            why = f"In {p['team']}, which you tagged"
        elif hit:
            why = f"In {hit.replace('-', ' ').replace('_', ' ').title() if hit == hit.lower() else hit}, which you tagged"
        elif team and f" {team} " in line:
            why = f"{p['team']} is named in your line"
        elif p["id"] in past:
            why = f"Took part in {past[p['id']]}"
        else:
            said = " ".join(str((c.get("value") or {}).get("answer") or "") for c in (interviews.get(p["id"]) or {}).values()
                            if isinstance(c, dict) and c.get("mark") == "stated" and not (c.get("value") or {}).get("restricted"))
            why = "Raised something like this in an interview" if len(want & _words(said)) >= 2 else None
        rows.append({"id": p["id"], "name": p["name"], "role": p["role"], "team": p["team"], "areas": p["areas"], "suggested": why is not None, "reason": why})
    return {"people": sorted(rows, key=lambda r: (not r["suggested"], r["name"].lower())),
            "suggested_areas": sorted({a for p in people if p["id"] in picked for a in p["areas"]})}


def _clean_draft(b) -> dict:
    if not isinstance(b, dict):
        raise Bad(422, "That is not valid.")
    out, text_limit = {}, {"statement": STATEMENT_MAX, "context": CONTEXT_MAX, "good_outcome": OUTCOME_MAX, "title": 200, "purpose": 500, "session_time": 5,
                           "session_date": 10, "step": 20}
    for k in DRAFT_KEYS:
        if k not in b:
            continue
        v = b[k]
        if k in text_limit and (not isinstance(v, str) or len(v) > text_limit[k]):
            raise Bad(422, "That answer is too long or not text.")
        if k in ("people", "suggested", "observers", "areas") and (not isinstance(v, list) or len(v) > 50 or any(not isinstance(x, str) or len(x) > 80 for x in v)):
            raise Bad(422, "That should be a list.")
        if k in ("anonymous_ideas", "affected_may_read") and not isinstance(v, bool):
            raise Bad(422, "That should be on or off.")
        if k == "session_minutes" and v is not None and v not in LENGTHS:
            raise Bad(422, "Pick 45 or 60 minutes.")
        if k in ("related", "related_checked", "message") and not isinstance(v, (list, dict)):
            raise Bad(422, "That is not valid.")
        out[k] = v
    return out


def invitation_message(rec: dict, a: dict, who: str, origin: str) -> dict:
    link = f"{origin}/centre/intent/{rec['id']}"
    try:
        d = date.fromisoformat(str(a["session_date"]))
        when = f"{d:%a} {d.day} {d:%b}"
    except ValueError:
        when = str(a["session_date"])
    body = (f"Hello,\n\n{who} would like your thinking on: {a['statement']}\n\nA good outcome: {a['good_outcome']}\n\n"
            f"Session: {when} at {a['session_time']} ({a['session_minutes']} minutes). You can add ideas on your own from the day before; "
            f"nobody else sees them until the session starts.\n\nOpen it here: {link}\n\nThank you,\n{who}")
    return {"subject": f"Think with me: {a['statement'][:80]}", "body": body}


def _draft(ctx: Ctx, b: dict) -> dict:
    if ctx.rec["state"] != "draft":
        raise Bad(409, "This brainstorm is already open.")
    ctx.need_organiser()
    clean = _clean_draft(b.get("answers") or {})

    def change(rec):
        a = rec["start_answers"] = {**(rec.get("start_answers") or {}), **clean}
        rec["draft_updated_at"] = S.now_iso()
        if a.get("title") or a.get("statement"):
            rec["title"] = str(a.get("title") or a["statement"])[:80 if not a.get("title") else 200].rstrip(" .,;:")
        if isinstance(a.get("areas"), list):
            rec["areas"] = [x for x in a["areas"] if x][:20]
    rec = _write(ctx, change)
    a, origin = rec["start_answers"], str(b.get("origin") or "")
    ready = all(a.get(k) for k in ("statement", "good_outcome", "session_date", "session_time", "session_minutes"))
    draft_msg = invitation_message(rec, a, ctx.me.name, origin.rstrip("/") if re.fullmatch(r"https?://[A-Za-z0-9.:\[\]-]+/?", origin) else "") if ready else None
    return {"ok": True, "answers": a, "title": rec["title"], "message_draft": draft_msg}


def _launch(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    if ctx.rec["state"] != "draft":
        raise Bad(409, "This brainstorm is already open.")
    a = {**(ctx.rec.get("start_answers") or {}), **_clean_draft(b.get("answers") or {})}
    tz, now = L.company_zone(ctx.plane), datetime.now(timezone.utc)
    people = {p["id"]: p for p in _profile_people(ctx)}
    bad = check_answers(a, now.astimezone(tz).date(), ctx.me.person_id)
    if not bad and any(x not in people for x in a["people"]):
        bad = "One of the people picked is not in the company profile. Pick again."
    if bad:
        raise Bad(422, bad)
    day = date.fromisoformat(a["session_date"])
    at = datetime.combine(day, datetime.strptime(a["session_time"], "%H:%M").time(), tzinfo=tz)
    stamp, sugg = now.isoformat(), set(a.get("suggested") or [])
    origin = str(b.get("origin") or "")
    msg = a.get("message") if isinstance(a.get("message"), dict) else invitation_message(
        ctx.rec, a, ctx.me.name, origin.rstrip("/") if re.fullmatch(r"https?://[A-Za-z0-9.:\[\]-]+/?", origin) else "")

    def person(x, **more):
        return {"account_id": people[x]["account_id"], "person_id": x, "name": people[x]["name"], **more}

    def change(rec):
        L.move(rec, "open", ctx.me.account_id, stamp, tz=tz)
        rec["title"] = (a.get("title") or a["statement"][:80]).strip()
        rec["purpose"] = (a.get("purpose") or f"To find: {a['good_outcome']}").strip()[:500]
        rec["areas"] = [x.strip() for x in a["areas"] if x.strip()][:20]
        rec["affected_may_read"] = bool(a.get("affected_may_read"))
        rec["people"]["participants"] = [person(x, status="Invited", reason=None, suggested_by="north" if x in sugg else None) for x in a["people"]]
        rec["people"]["observers"] = [person(x) for x in a.get("observers") or [] if x in people]
        rec["time_box"].update(time_box(day, tz))
        rec["outcome"].update(statement=a["statement"].strip(), context=str(a.get("context") or "").strip(), good_outcome=a["good_outcome"].strip(),
                              session_at=at.isoformat(), session_minutes=a["session_minutes"], anonymous_ideas=bool(a.get("anonymous_ideas")),
                              related=[x for x in a.get("related") or [] if isinstance(x, dict)],
                              related_checked=a.get("related_checked") or {"at": stamp, "shown": 0, "dismissed": False}, session_history=[], ideas_open_at=None)
        rec["opened_by"] = ctx.me.account_id
        rec["start_answers"] = {**a, "message": msg}
        rec["session"] = {"phase": "not_opened", "paused": False, "opened_at": None, "phase_started_at": None, "phases": [], "pauses": [], "extended_by": [],
                          "prompts": {}, "minutes": dict(PHASE_MINUTES), "closed_at": None, "closed_by": None, "closed_early": False}
    rec = _write(ctx, change, "brainstorm_opened", {"participants": len(a["people"])})
    return {"id": rec["id"], "message": msg, "window": window(day), "session_at": at.isoformat()}


# ---- session acts ------------------------------------------------------------------------------------------------------------

def _need_phase(ctx: Ctx, *phases: str) -> None:
    if ctx.rec["state"] not in ("open", "in_session"):
        raise Bad(409, "This brainstorm is not open for that.")
    if _ph(ctx.rec) not in phases:
        raise Bad(409, "The session is not at a stage where that can be done.")


def _text(v, limit: int, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise Bad(422, f"Add some words for the {what}.")
    if len(v.strip()) > limit:
        raise Bad(422, f"Keep the {what} under {limit} characters.")
    return v.strip()


def _open_session(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    if ctx.rec["state"] != "open" or _ph(ctx.rec) != "not_opened":
        raise Bad(409, "The session has already opened.")
    stamp, statement = S.now_iso(), ctx.rec["outcome"].get("statement") or ctx.rec["title"]

    def change(rec):
        by = ctx.me.account_id
        L.set_stage(rec, "think_alone", "closed", by, stamp)
        L.set_stage(rec, "live_session", "open", by, stamp)
        L.move(rec, "in_session", by, stamp)
        rec["session"].update(phase="diverge", opened_at=stamp, phase_started_at=stamp, phase_paused_s=0, paused=False, paused_at=None,
                              prompts={p: draft_prompt(statement, p) for p in LIVE_WRITE})
        rec["outcome"]["ideas_open_at"] = rec["outcome"].get("ideas_open_at") or rec["time_box"]["starts"]
    _write(ctx, change, "session_opened", {"phase": "diverge"})
    _edit_ideas(ctx.plane, ctx.iid, lambda d: None)  # the file exists from the first moment of the session
    return {"ok": True}


def _end_pause(s: dict, stamp: str) -> None:
    if s.get("paused"):
        s["phase_paused_s"] = float(s.get("phase_paused_s") or 0) + (datetime.fromisoformat(stamp) - datetime.fromisoformat(s["paused_at"])).total_seconds()
        s["pauses"][-1]["ended"] = stamp
        s.update(paused=False, paused_at=None)


def _move_phase(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    to, now = b.get("to"), S.now_iso()
    if to not in ("group", "converge") or _ph(ctx.rec) != PHASES[PHASES.index(to) - 1]:
        raise Bad(409, "The session moves one phase at a time, forward.")

    def change(rec):
        s = rec["session"]
        _end_pause(s, now)
        s["phases"].append({"phase": s["phase"], "started": s["phase_started_at"], "ended": now})
        s.update(phase=to, phase_started_at=now, phase_paused_s=0)
    _write(ctx, change, "session_phase", {"to": to})
    return {"ok": True}


def _pause(ctx: Ctx, b: dict, on: bool) -> dict:
    ctx.need_organiser()
    if _ph(ctx.rec) not in LIVE_WRITE or bool((ctx.rec.get("session") or {}).get("paused")) == on:
        raise Bad(409, "The session cannot be " + ("paused" if on else "resumed") + " now.")
    now = S.now_iso()

    def change(rec):
        s = rec["session"]
        if on:
            s.update(paused=True, paused_at=now)
            s["pauses"].append({"by": ctx.me.name, "at": now, "ended": None})
        else:
            _end_pause(s, now)
    _write(ctx, change, "session_paused" if on else "session_resumed")
    return {"ok": True}


def _close(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    if _ph(ctx.rec) not in PHASES:
        raise Bad(409, "The session is not running.")
    now = S.now_iso()

    def change(rec):
        by, s = ctx.me.account_id, rec["session"]
        _end_pause(s, now)
        s["phases"].append({"phase": s["phase"], "started": s["phase_started_at"], "ended": now})
        s.update(closed_early=s["phase"] != "converge", phase="closed", closed_at=now, closed_by=by)
        L.set_stage(rec, "live_session", "closed", by, now)
        if any(st["key"] == "choose" and st["state"] == "waiting" for st in rec["stages"]):
            L.set_stage(rec, "choose", "open", by, now)
        L.move(rec, "open", by, now)
    _write(ctx, change, "session_closed")
    return {"ok": True}


def _add_time(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    m = b.get("minutes")
    if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= 60:
        raise Bad(422, "Add between 1 and 60 minutes.")
    _need_phase(ctx, *PHASES)
    _write(ctx, lambda rec: rec["session"]["extended_by"].append({"by": ctx.me.name, "at": S.now_iso(), "minutes": m, "phase": rec["session"]["phase"],
                                                                  "reason": str(b.get("reason") or "")[:200]}), "session_time_added", {"minutes": m})
    return {"ok": True}


def _prompt(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    ph = b.get("phase")
    if ph not in LIVE_WRITE:
        raise Bad(422, "Pick a phase that has a prompt.")
    _need_phase(ctx, *PHASES)
    statement = ctx.rec["outcome"].get("statement") or ctx.rec["title"]
    new = draft_prompt(statement, ph) if b.get("reset") else {**draft_prompt(statement, ph), "text": _text(b.get("text"), 600, "prompt"),
                                                              "edited_by": ctx.me.name, "edited_at": S.now_iso()}
    _write(ctx, lambda rec: rec["session"]["prompts"].__setitem__(ph, new), "prompt_edited", {"phase": ph})
    return {"ok": True}


def _regroup(ctx: Ctx, b: dict) -> dict:
    ctx.need_organiser()
    _need_phase(ctx, *LIVE_WRITE)
    if len(_live_ideas(_read_ideas(ctx.plane, ctx.iid))) < MIN_NOTES:
        raise Bad(409, "Add ideas first.")
    if getattr(ctx.request.app.state, "entitlements", None) is None:
        return {"ok": True, "note": _edit_ideas(ctx.plane, ctx.iid, _north_group)}
    _group_in_background(ctx)  # the model can take a minute: the groups change on screen when it is done
    return {"ok": True, "note": "I am grouping the ideas again. The groups change when I am done."}


def _add_idea(ctx: Ctx, b: dict) -> dict:
    ctx.need_writer()
    rec, ph = ctx.rec, _ph(ctx.rec)
    if rec["state"] not in ("open", "in_session") or ph in ("closed", "converge"):
        raise Bad(409, "Ideas are closed.")
    if ph == "not_opened" and datetime.now(timezone.utc) < _aware(rec["time_box"]["starts"]):
        raise Bad(409, "Ideas are not open yet.")
    if (rec.get("session") or {}).get("paused"):
        raise Bad(409, "The session is paused.")
    anonymous = b.get("anonymous") is True
    if anonymous and not rec["outcome"].get("anonymous_ideas"):
        raise Bad(422, "The organiser did not allow hidden names.")
    text, why = (ctx.unnamed(x, anonymous) for x in (_text(b.get("text"), IDEA_MAX, "idea"), str(b.get("why") or "").strip()[:IDEA_MAX]))

    def change(doc):
        i = {"id": secrets.token_hex(6), "text": text, "why": why, "anonymous": anonymous, "owner": ctx.owner_key(doc, anonymous),
             "author": None if anonymous else ctx.me.name, "at": S.now_iso(), "withdrawn": False, "edits": [], "moves": [], "replies": []}
        doc["ideas"].append(i)
        return i["id"]
    out = _edit_ideas(ctx.plane, ctx.iid, change)
    _auto_group(ctx, ph)
    return {"ok": True, "id": out}


def _idea(doc: dict, idea_id) -> dict:
    i = next((x for x in doc["ideas"] if x["id"] == idea_id and not x.get("withdrawn")), None)
    if not i:
        raise Bad(404, "We could not find that idea.")
    return i


def _mine(doc: dict, ctx: Ctx, i: dict) -> bool:
    return i["owner"] in (ctx.owner_key(doc, False), ctx.owner_key(doc, True))


def _idea_change(ctx: Ctx, b: dict, kind: str) -> dict:
    ctx.need_writer()
    live = ctx.rec["state"] in ("open", "in_session")
    counting = _ph(ctx.rec) == "converge" or (ctx.rec.get("outcome") or {}).get("converge", {}).get("state", "not_open") != "not_open"
    if not live or _ph(ctx.rec) == "closed":
        raise Bad(409, "Ideas are closed.")
    if counting:
        raise Bad(409, "The count has opened, so ideas can no longer be changed or withdrawn.")  # converge.ensure keeps state in outcome.converge

    def change(doc):
        i = _idea(doc, b.get("id"))
        if not _mine(doc, ctx, i):
            raise Bad(403, "Only the person who wrote an idea can change it.")
        if kind == "edit":
            i.update(text=ctx.unnamed(_text(b.get("text"), IDEA_MAX, "idea"), i["anonymous"]), why=ctx.unnamed(str(b.get("why") or "").strip()[:IDEA_MAX], i["anonymous"]))
            i["edits"].append({"at": S.now_iso(), "kind": "text"})
        else:
            i["withdrawn"] = True
            i["edits"].append({"at": S.now_iso(), "kind": "withdrawn"})
    _edit_ideas(ctx.plane, ctx.iid, change)
    return {"ok": True}


def _move_idea(ctx: Ctx, b: dict) -> dict:
    ctx.need_writer()
    _need_phase(ctx, "group")
    if ctx.rec["session"].get("paused"):
        raise Bad(409, "The session is paused.")

    def change(doc):
        i = _idea(doc, b.get("id"))
        src, to = _group_of(doc, i["id"]), b.get("to")
        if to == "new":
            dest = {"id": secrets.token_hex(6), "name": _text(b.get("name") or "A new group", NAME_MAX, "group name"), "idea_ids": [], "by": "person", "fallback": False}
            doc["groups"].append(dest)
        else:
            dest = next((g for g in doc["groups"] if g["id"] == to), None)
            if not dest:
                raise Bad(404, "We could not find that group.")
        if src is dest:
            return
        if src:
            src["idea_ids"].remove(i["id"])
        dest["idea_ids"].append(i["id"])
        doc["groups"] = [g for g in doc["groups"] if g["idea_ids"]]
        by = ctx.owner_key(doc, True) if i["anonymous"] and _mine(doc, ctx, i) else ctx.me.name  # a move of one's own hidden idea names no one
        i["moves"].append({"at": S.now_iso(), "by": by, "from": src and src["name"], "to": dest["name"], "kind": "group"})
        doc["group_edits"].append({"by": by, "kind": "move", "at": S.now_iso()})
    _edit_ideas(ctx.plane, ctx.iid, change)
    return {"ok": True}


def _rename(ctx: Ctx, b: dict) -> dict:
    ctx.need_writer()
    _need_phase(ctx, "group")

    def change(doc):
        g = next((x for x in doc["groups"] if x["id"] == b.get("group_id")), None)
        if not g:
            raise Bad(404, "We could not find that group.")
        g.update(name=_text(b.get("name"), NAME_MAX, "group name"), by="person", fallback=False)
        doc["group_edits"].append({"by": ctx.me.name, "kind": "rename", "at": S.now_iso()})
    _edit_ideas(ctx.plane, ctx.iid, change)
    return {"ok": True}


def _answer(ctx: Ctx, b: dict) -> dict:
    if not ctx.entry() or ctx.role != "participant":
        raise Bad(403, "You are not invited to this brainstorm.")
    if ctx.rec["state"] not in ("open", "in_session"):
        raise Bad(409, "This brainstorm is not open.")
    ans = b.get("answer")
    if ans not in ("accept", "decline"):
        raise Bad(422, "Choose to accept or decline.")
    if ans == "decline" and not str(b.get("reason") or "").strip():
        raise Bad(422, "Say in one line why you cannot take part.")

    def change(rec):
        e = next(x for x in rec["people"]["participants"] if A._is_me(x, ctx.me))
        e.update(status="Accepted" if ans == "accept" else "Declined", reason=None if ans == "accept" else str(b["reason"]).strip()[:200], answered_at=S.now_iso())
    _write(ctx, change)
    return {"ok": True}


def _reply(ctx: Ctx, card_id: str, b: dict) -> dict:
    ctx.need_writer()
    _need_phase(ctx, *LIVE_WRITE)
    if ctx.rec["session"].get("paused"):
        raise Bad(409, "The session is paused.")
    anonymous = b.get("anonymous") is True
    if anonymous and not ctx.rec["outcome"].get("anonymous_ideas"):
        raise Bad(422, "The organiser did not allow hidden names.")
    text = ctx.unnamed(_text(b.get("text"), REPLY_MAX, "reply"), anonymous)

    def change(doc):
        r = {"id": secrets.token_hex(6), "text": text, "anonymous": anonymous, "owner": ctx.owner_key(doc, anonymous),
             "author": None if anonymous else ctx.me.name, "at": S.now_iso()}
        _idea(doc, card_id)["replies"].append(r)
        return r["id"]
    return {"ok": True, "id": _edit_ideas(ctx.plane, ctx.iid, change)}


ACTS = {"draft": _draft, "launch": _launch, "open": _open_session, "phase": _move_phase, "close": _close, "add-time": _add_time, "prompt": _prompt,
        "group": _regroup, "idea": _add_idea, "idea-edit": lambda c, b: _idea_change(c, b, "edit"), "idea-withdraw": lambda c, b: _idea_change(c, b, "withdraw"),
        "move": _move_idea, "rename": _rename, "answer": _answer, "pause": lambda c, b: _pause(c, b, True), "resume": lambda c, b: _pause(c, b, False)}
START_ACTS = ("draft", "launch", "related", "suggest-people")  # the organiser of a draft


def _do(request: Request, iid: str, act: str, body) -> JSONResponse:
    def go():
        if not isinstance(body, dict):
            raise Bad(422, "Please send the details as a JSON object.")
        if act in START_ACTS:
            ctx = Ctx(request, iid, frozenset({"organiser"}))
            if act == "related":
                return {"related": related(ctx, str(body.get("statement") or ""))}
            if act == "suggest-people":
                return suggest_people(ctx, str(body.get("statement") or ""), [str(x) for x in body.get("areas") or []], [str(x) for x in body.get("picked") or []])
            return ACTS[act](ctx, body)
        if act not in ACTS:
            raise Bad(404, S.NOT_FOUND)
        return ACTS[act](Ctx(request, iid), body)
    return _safe(go)


# ---- routes ------------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/{intent_id}/session")
def get_intents_by_intent_id_session(request: Request, intent_id: str):
    return _safe(lambda: build_view(Ctx(request, intent_id), request.query_params.get("display")))


@router.post("/api/intents/{intent_id}/session/open")
def post_intents_by_intent_id_session_open(request: Request, intent_id: str, body: dict = Body(default={})):
    return _do(request, intent_id, "open", body)


@router.post("/api/intents/{intent_id}/session/group")
def post_intents_by_intent_id_session_group(request: Request, intent_id: str, body: dict = Body(default={})):
    return _do(request, intent_id, "group", body)


@router.post("/api/intents/{intent_id}/session/{act}")
def post_intents_by_intent_id_session_by_act(request: Request, intent_id: str, act: str, body: dict = Body(default={})):
    return _do(request, intent_id, act, body)


@router.post("/api/intents/{intent_id}/cards/{card_id}/replies")
def post_intents_by_intent_id_cards_by_card_id_replies(request: Request, intent_id: str, card_id: str, body: dict = Body(default={})):
    return _safe(lambda: _reply(Ctx(request, intent_id), card_id, body))


# ---- 37 (converge and the outcome) stays a stub until its card lands ----------------------------------------------------------

@router.get("/api/intents/{intent_id}/converge")
def get_intents_by_intent_id_converge(request: Request):
    return not_yet("37")


@router.put("/api/intents/{intent_id}/outcome")
def put_intents_by_intent_id_outcome(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/late-thoughts")
def post_intents_by_intent_id_late_thoughts(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/converge/open")
def post_intents_by_intent_id_converge_open(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/converge/back")
def post_intents_by_intent_id_converge_back(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/converge/close")
def post_intents_by_intent_id_converge_close(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/converge/round2")
def post_intents_by_intent_id_converge_round2(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/outcome/draft")
def post_intents_by_intent_id_outcome_draft(request: Request):
    return not_yet("37")


@router.post("/api/intents/{intent_id}/outcome/confirm")
def post_intents_by_intent_id_outcome_confirm(request: Request):
    return not_yet("37")
