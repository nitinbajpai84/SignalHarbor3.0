"""M1-P09 routes for the organiser side of the charter: draft it from the room's ticked problems (M1-24), edit the purpose
lines, sign it in the room (M1-25), send it to the named approver (M1-26) and withdraw that link, with versions (M1-27),
the suggested picture (D-022) and the hand-off (M1-30, store/charter.py). Declared in manifest.yaml.

Who: the organiser drafts, edits and sends. The organiser, anyone of the company who holds a seat, and any company
administrator or sponsor of the company (the signing roles of contracts/charter.yaml, seated or not, a revoked seat
included) may read it and sign it; only a person with a signing role signs. A person with only a join token reaches none
of these.
"""
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.agent import charter_lines
from modules.m1_intent.api.board import _model, settings as board_settings
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import charter_export as X
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain.seat_identity import register_names
from modules.m1_intent.store.files import WrongState
from modules.m1_intent.store.charter import CharterStore, cluster_notes, new_token, notes_on_their_own, together_result
from modules.m1_intent.tools.pack_tools import load_guidance
from sh_platform.public_link import full_url
from sh_platform.agents.runs import RunRegistry
from modules.m1_intent.store.room import RoomStore
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter()

_STATUS = {"no_result": 409, "wrong_state": 409, "read_only": 409, "already_signed": 409, "forbidden": 403, "invalid": 422, "comment_needed": 422}
guarded = deps.guarded(
    (C.CharterError, lambda e: deps.plain(_STATUS.get(e.code, 409), e.code, e.message)),
    (LookupError, lambda e: deps.not_found()))


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _settings(request: Request) -> C.CharterSettings:
    return C.load_charter_settings(getattr(request.app.state, "m1_contracts_dir", None))


def _store(request: Request, plane) -> CharterStore:
    return CharterStore(plane, contracts_dir=getattr(request.app.state, "m1_contracts_dir", None))


def _may_see(request: Request, plane, s: dict, settings: C.CharterSettings) -> bool:
    """The organiser, a seated person, or a signer of this company: a signer needs no seat (the plane is the company's own)."""
    acct = request.state.account_id
    if acct is None:  # a seated guest (token) reads only, and only the session the token was made for. The room sees the
        # charter it is signing, and the result once the session closed; in earlier stages there is no charter to see.
        return s["state"] in ("signing", "closed") and request.state.m1_session_id == s["id"] and RoomStore(plane).seat_of_participant(s["id"], request.state.guest_id) is not None
    return (s["organiser_account_id"] == acct or bool(set(request.state.roles) & settings.sign_roles)
            or RoomStore(plane).seat_of_account(s["id"], acct) is not None or _intent_participant(request, plane, s["id"]))


def _intent_participant(request: Request, plane, session_id: str) -> bool:
    """A person named on the intent this session belongs to (participant, approver, observer or organiser), with no seat in the room (the kernel's own matching, ruling R2)."""
    from sh_platform.intents import charter as IC
    from sh_platform.intents.access import Me, roles_of
    intent = IC.intent_for_session(plane, session_id)
    return intent is not None and bool(roles_of(intent, Me.of(request, plane)) & {"organiser", "closer", "participant", "observer"})


def _name(request: Request) -> str:
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return str(acct.get("display_name") or "A signer")


def _pack_rows(request: Request) -> tuple[list, list, str]:
    """The company's own industry pack: its problems, its measures and the suggestion label. Empty, never an error."""
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    try:
        pack = request.app.state.packs.load(str(company.get("industry", "")))
    except ValueError:
        return [], [], ""
    rows = []
    for section, key in (("problems", "problems"), ("kpi_tree", "kpis")):
        try:
            raw = pack.section(section) if section in pack.sections() else None
        except (KeyError, OSError, ValueError):
            raw = None
        got = raw.get(key) if isinstance(raw, dict) else None
        rows.append([r for r in got if isinstance(r, dict)] if isinstance(got, list) else [])
    return rows[0], rows[1], pack.suggestion_label


def _link_state(doc: dict, version: dict) -> str:
    mine = [l for l in doc["links"] if l["version"] == version["version"]]
    if not mine:
        return "none"
    last = mine[-1]
    if last["state"] == "open" and datetime.fromisoformat(last["expires_at"]) <= datetime.now(timezone.utc):
        return "expired"
    return last["state"]


def charter_view(request: Request, plane, s: dict, doc: dict, settings: C.CharterSettings, is_organiser: bool, account_id) -> dict:
    v = doc["versions"][-1]
    needed = C.signers_needed(s["preparation"]["seats"], settings, s["preparation"].get("signers"))
    mine = any(x["account_id"] == account_id for x in v["signatures"])
    can_sign = (v["status"] == "draft" and bool(set(request.state.roles) & settings.sign_roles) and not mine
                and s["state"] == "signing")
    problems, kpis, label = _pack_rows(request)
    rules = charter_lines.load_rules()
    spec = N.load_fields(getattr(request.app.state, "m1_contracts_dir", None))
    return {
        "version": v["version"], "status": v["status"], "template": v["template"],
        "lists": C.lists([(k["id"], k["heading"]) for k in spec.kinds], v["problems"]),
        "problems": [{"id": p["id"], "title": p["title"], "kind": p.get("kind", "intent"), "details": p.get("details", []),
                      "priority": p["priority"], "priority_label": settings.label(p["priority"]),
                      "tie": C.tie_text(p["votes"], settings) if p.get("tied_options") and p["priority"] is None else None,
                      "tied_options": [{"id": o, "label": settings.label(o)} for o in p.get("tied_options", [])],
                      "so_that": p["so_that"], "so_that_edited": p["so_that_edited"], "so_that_proposal": p["so_that_proposal"],
                      "so_that_draft": p.get("so_that_draft", False),
                      "so_that_note": (rules["messages"]["draft_label"] if p.get("so_that_draft") else None if p["so_that"]
                                       else rules["messages"]["ask_organiser"]),
                      "note_count": p["note_count"]} for p in v["problems"]],
        "later": v["later"], "parked": v.get("parked", []), "wall": v.get("wall"), "alone": v.get("alone", []), "footer": v["footer"],
        "signing": {"needed": len(v["signatures"]) if v["status"] == "signed" else needed, "signed": len(v["signatures"]), "can_sign": can_sign, "i_signed": mine,
                    "signers": [{"name": x["name"], "at": x["at"], "how": x["how"]} for x in v["signatures"]]},
        "approver": {"name": s["preparation"]["approver_name"], "link": _link_state(doc, v),
                     "expires_at": next((l["expires_at"] for l in reversed(doc["links"]) if l["version"] == v["version"]), None)},
        "returned": v["returned"] and {"comment": v["returned"]["comment"], "by": v["returned"]["by"], "at": v["returned"]["at"]},
        "versions": [{"version": x["version"], "status": x["status"], "created_at": x["created_at"], "created_by": x["created_by"],
                      "edited_at": x["edited_at"], "edited_by": x["edited_by"],
                      "comment": x["returned"]["comment"] if x["returned"] else None} for x in doc["versions"]],
        "editable": is_organiser and v["status"] == "draft" and not v["signatures"] and s["state"] == "signing",
        "graph": C.build_graph(v["problems"], problems, kpis, label) if kpis else None,
        "handed_on": v["status"] == "signed",
    }


def _wrap(request: Request, plane, s: dict, store: CharterStore, settings: C.CharterSettings) -> dict:
    """The page's whole answer: where the session is, and the charter if there is one."""
    doc, st = store.read(s["id"]), request.state
    organiser = s["organiser_account_id"] == st.account_id
    ready = organiser and s["state"] == "together" and (doc is None or doc["versions"][-1]["status"] == "returned")
    has_result = together_result(plane, s["id"]) is not None
    return {"state": s["state"], "organiser": organiser,
            "can_draft": ready and has_result, "no_result": ready and not has_result,
            "charter": charter_view(request, plane, s, doc, settings, organiser, st.account_id) if doc else None}


def _context(request: Request, session_id: str, organiser_only: bool):
    plane, settings = _plane(request), _settings(request)
    store = _store(request, plane)
    s = store.sessions.get(session_id)
    ok = s is not None and (s["organiser_account_id"] == request.state.account_id if organiser_only
                            else _may_see(request, plane, s, settings))
    if not ok:
        raise LookupError("no session")
    return plane, settings, store, s


def _with_drafts(request: Request, plane, store: CharterStore, session_id: str, clusters: list[dict], settings: C.CharterSettings) -> list[dict]:
    """North's "So that ..." draft for each ticked problem the room wrote no purpose for and no person has edited. A draft
    is marked as one; without a model it is skipped and the line stays blank (the screen asks the organiser)."""
    doc = store.read(session_id)
    edited = {p["id"] for p in doc["versions"][-1]["problems"] if p["so_that_edited"]} if doc else set()
    notes = cluster_notes(plane, session_id)
    todo = [{"id": c["id"], "title": c["title"], "notes": notes[c["id"]]} for c in clusters
            if c["ticked"] and not c["so_that"] and c["id"] not in edited and notes.get(c["id"])]
    model = _model(request, plane) if todo else None
    if model is None:
        return clusters
    register_names(request, plane, session_id)  # protected before anything leaves (D-007)
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    guidance = load_guidance(request.app.state.packs, company.get("industry"))
    lines = charter_lines.draft_lines(model, request.app.state.entitlements, RunRegistry(plane), request.state.company_id, todo,
                                      settings.so_that_max, guidance.north or None)
    return [{**c, "so_that": lines[c["id"]], "so_that_draft": True} if c["id"] in lines else c for c in clusters]


def make_draft(request: Request, plane, settings: C.CharterSettings, store: CharterStore, session_id: str, together: list[dict],
               organiser_id: str, who: str, day=None) -> None:
    """Drafts the charter from the room's cleaned result and ends the together stage (the organiser's POST and the timer share it)."""
    s = store.sessions.get(session_id)
    clusters = _with_drafts(request, plane, store, session_id, together, settings)
    _, templates = deps.contracts(request)
    template = templates.get(s["preparation"]["charter_template"]) or templates.get(templates.default_id)
    room = RoomStore(plane).get(session_id)
    people = sum(1 for x in (room or {"seats": []})["seats"] if x["state"] == "taken")
    now = datetime.now(timezone.utc)
    from modules.m1_intent.store.board import BoardStore
    from modules.m1_intent.store.files import StoreError
    from modules.m1_intent.store.together_shelves import ShelfStore
    try:  # no shelf file is nothing parked; an unreadable one stops the draft (the route answers "cannot be read") so nothing is lost
        away = {c: r for c, r in ShelfStore(plane).get(session_id)["shelves"].items() if r["shelf"] == "future"}
    except StoreError:
        log.warning("The shelf file of session %s could not be read; the charter was not drafted.", session_id)
        raise
    parked = [{"title": c["name"], "reason": away[c["id"]]["reason"], "review_date": away[c["id"]]["review_date"]}
              for c in BoardStore(plane).get(session_id)["clusters"] if c["id"] in away]  # Future shelf (A-058): listed, never a problem or in the hand-off
    from modules.m1_intent.store import wall_snapshot
    wall_snapshot.freeze(plane, session_id)  # the close hook freezes it; this only covers a session closed before that existed (no-op when frozen)
    wall = wall_snapshot.served(plane, session_id)  # sealed cards are silhouettes for everyone: a version is read by more people than drafted it
    store.draft(session_id, organiser_id, lambda earlier, n: {**C.build_version(
        clusters, template, settings, number=n, by=who, now=now.isoformat(), date=(day or now.date()).isoformat(),
        participants=people, earlier=earlier, alone=notes_on_their_own(plane, session_id)),
        "parked": parked, "wall": wall})


def close_together(request: Request, plane, session_id: str) -> bool:
    """The together stage ends (its timer is up, or everyone is done): the vote rule's ticks are made, then the charter is
    drafted for the organiser to sign. Nothing is drafted when no group was backed: that waits for the organiser. True when
    the stage moved on."""
    from modules.m1_intent.domain import together as T
    from modules.m1_intent.store.board import BoardStore, TogetherStore
    settings, rule = _settings(request), board_settings(request)
    store = _store(request, plane)
    s = store.sessions.get(session_id)
    if s is None or s["state"] != "together":
        return False
    clusters = BoardStore(plane).get(session_id)["clusters"]
    TogetherStore(plane).update(session_id, lambda d: T.apply_auto_ticks(rule, d, clusters))
    together = C.clean_together(together_result(plane, session_id), settings)
    if not any(c["ticked"] for c in together):
        return False
    try:
        make_draft(request, plane, settings, store, session_id, together, s["organiser_account_id"], "North, from the room's vote")
    except WrongState:
        return False  # another look at the timer got there first
    return True


@router.get("/sessions/{session_id}/charter")
@guarded
async def read_charter(request: Request, session_id: str):
    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=False)
        return _wrap(request, plane, s, store, settings)

    return await deps.blocking(work)


def _local_day(value):
    """The organiser's own date from the screen, or None when it is not a date within a day of today (UTC)."""
    try:
        day = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return day if day and abs((day - datetime.now(timezone.utc).date()).days) <= 1 else None


@router.post("/sessions/{session_id}/charter", status_code=201)
@guarded
async def draft_charter(request: Request, session_id: str):
    """Drafts the charter and so ends the room stage. With groups still open it needs {"confirm": true}, as the screen asks.
    {"date": "YYYY-MM-DD"} is the organiser's own day for the footer (the server's clock is UTC); one day either side of UTC is believed."""
    raw = await deps.body_object(request)
    day = _local_day(raw.get("date")) if raw is not None else None
    if raw is not None and (not set(raw) <= {"confirm", "date"} or not isinstance(raw.get("confirm", False), bool)
                            or ("date" in raw and day is None)):
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=True)
        together = C.clean_together(together_result(plane, session_id), settings)
        names = [c["title"] for c in together if not c["ticked"]]
        still_open = len(names)
        if s["state"] == "together" and still_open and not (raw or {}).get("confirm"):  # the Define close dialog says the same, names and all
            raise C.CharterError("needs_confirm", f"{still_open} {'group is' if still_open == 1 else 'groups are'} still open: {', '.join(names)}. "
                                                  "Please confirm that you want to finish anyway.")
        make_draft(request, plane, settings, store, session_id, together, request.state.account_id, _name(request), day)
        return _wrap(request, plane, store.sessions.get(session_id), store, settings)

    return await deps.blocking(work)


@router.put("/sessions/{session_id}/charter")
@guarded
async def edit_charter(request: Request, session_id: str):
    raw = await deps.body_object(request)
    if raw is None or not raw or not set(raw) <= {"so_that", "priority", "confirm_so_that"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=True)
        now = datetime.now(timezone.utc).isoformat()
        if "so_that" in raw:
            deps.typed(request, len(raw["so_that"]) if isinstance(raw["so_that"], dict) else 1)

        def change(v: dict) -> dict:
            if "so_that" in raw:
                v = C.edit_purposes(v, raw["so_that"], settings, _name(request), now)
            if "confirm_so_that" in raw:  # "Use this line": accept North's drafts as they stand (list of problem ids)
                v = C.confirm_purposes(v, raw["confirm_so_that"], _name(request), now)
            return C.edit_priorities(v, raw["priority"], settings, _name(request), now) if "priority" in raw else v
        store.edit(session_id, request.state.account_id, change)
        return _wrap(request, plane, s, store, settings)

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/charter/sign")
@guarded
async def sign_charter(request: Request, session_id: str):
    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=False)
        from sh_platform.intents import charter as IC
        if IC.intent_for_session(plane, session_id) is not None:
            raise C.CharterError("forbidden", "Sign this charter on the intent's charter page. Only the sponsor signs it.")
        if not set(request.state.roles) & settings.sign_roles:
            raise C.CharterError("forbidden", "Only a sponsor or a company administrator can sign the charter.")
        signer = {"name": _name(request), "account_id": request.state.account_id}
        store.sign(session_id, signer, C.signers_needed(s["preparation"]["seats"], settings, s["preparation"].get("signers")))
        return _wrap(request, plane, store.sessions.get(session_id), store, settings)

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/charter/send")
@guarded
async def send_to_approver(request: Request, session_id: str):
    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=True)
        token = new_token(session_id)
        _, expires = store.send(session_id, request.state.account_id, token, settings.link_hours)
        # the link is shown once: only its hash is kept, so this answer is the only place it exists
        return {**_wrap(request, plane, s, store, settings), "link_path": f"/approve/{token}", "link_expires_at": expires}

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/charter/withdraw")
@guarded
async def withdraw_link(request: Request, session_id: str):
    def work():
        plane, settings, store, s = _context(request, session_id, organiser_only=True)
        store.revoke(session_id, request.state.account_id)
        return _wrap(request, plane, s, store, settings)

    return await deps.blocking(work)


def _signed_view(request: Request, session_id: str, organiser_only: bool):
    """The charter as this person sees it, only once it is signed (else a plain 409), plus the file's headings."""
    plane, settings, store, s = _context(request, session_id, organiser_only)
    doc = store.read(session_id)
    from sh_platform.intents import charter as IC
    intent = IC.intent_for_session(plane, session_id)
    if intent is not None:
        IC.sync_approved(request, plane, intent)  # an approver-link signature is frozen here if no read has done it yet
        doc = store.read(session_id)
    live = [i for i, v in enumerate(doc["versions"] if doc else []) if v["status"] == "signed" and not v.get("superseded_by") and not v.get("discarded")]
    if not live:
        raise C.CharterError("wrong_state", "The charter can be downloaded once it is signed.")
    signed = doc["versions"][live[-1]]  # a newer draft, or a discarded one, does not hide the signed charter
    view = charter_view(request, plane, s, {**doc, "versions": doc["versions"][: live[-1] + 1]}, settings,
                        s["organiser_account_id"] == request.state.account_id, request.state.account_id)
    view["frozen"] = {"pages": (signed.get("pages_frozen") or {}).get("pages") or [], "risks": signed.get("risks") or []}
    name = str((request.app.state.entitlements.company(request.state.company_id) or {}).get("name") or "")
    return plane, s, view, name, name.casefold().startswith("illustrative"), (s["preparation"]["purpose"] or "Intent session")[:120]


@router.get("/sessions/{session_id}/charter/download")
@guarded
async def download_charter(request: Request, session_id: str):
    """The signed charter as a printable HTML file and as Markdown, built from the same view as the screen."""
    def work():
        _, _, view, name, illus, title = _signed_view(request, session_id, organiser_only=False)
        base = X.safe_filename(name, view["footer"]["date"])
        return {"files": [{"format": "html", "filename": f"{base}.html", "mime": "text/html", "content": X.to_html(view, name, title, illus)},
                          {"format": "markdown", "filename": f"{base}.md", "mime": "text/markdown", "content": X.to_markdown(view, name, title, illus)}]}

    return await deps.blocking(work)


@router.get("/sessions/{session_id}/charter/email")
@guarded
async def email_participants(request: Request, session_id: str):
    """A ready email for the organiser to copy: nothing is sent. Addresses are known only for people who joined with an
    account; a guest is listed by name with no address. The body carries the charter summary and the charter's own link."""
    def work():
        plane, s, view, name, _, title = _signed_view(request, session_id, organiser_only=True)
        accounts, people = request.app.state.account_store, []
        for seat in (RoomStore(plane).get(session_id) or {"seats": []})["seats"]:
            if seat["state"] == "taken":
                email = (accounts.get(seat["account_id"]) or {}).get("email") if seat["account_id"] else None
                people.append({"name": seat["name"], "email": email or None})
        path = f"/modules/m1_intent/sessions/{session_id}/charter"
        link = full_url(request, path)  # the same configured base as module 2's request emails
        return {**X.email_text(view, name, title, link), "link_path": path, "link": link, "people": people,
                "no_address": [p["name"] for p in people if not p["email"]]}

    return await deps.blocking(work)
