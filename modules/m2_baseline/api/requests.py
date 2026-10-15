"""M2-P02 routes: requests to owners, the answer link with no account, the owner questionnaire, answering in a meeting, and
the outstanding view. The four /answer routes are a SECURITY PATH copied from module 1's approver link (m1_intent/api/approver.py).

What the link is: "ow-<request id>-<secret>", made when Nira sends the requests. Only its SHA-256 hash is stored
(store/requests.py). It belongs to one person's request, expires, can be withdrawn, and shows only that person's KPI names and
questions: no client data, no figures, no other person's answers.
How it travels: in the X-Session-Token header only; the page address /answer/<token> carries it to the screen, never to the API,
and no API route takes it in a URL, a query or a body.
Defences, in order (the answer routes are `entry` routes, so they check everything themselves): the failure lock (5 failures,
then a wait), the token's shape, the control index, that the company still owns the module, then the hash. Every failure before
the hash matches gives the same answer.
There is no email service: the organiser's routes return the link once, with a plain email text to copy. Nothing is sent.
"""
import base64
import binascii
import json
import logging
import time
from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from modules.m2_baseline.api.signed_guard import SignedGuard, refuse_if_signed
from modules.m2_baseline.domain import requests as R
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.questionnaire import AnswerError, Questionnaire, clean_answers, load_questionnaire
from modules.m2_baseline.domain.signoff import SignoffError
from modules.m2_baseline.store.answers import AnswerStore, read_answers
from modules.m2_baseline.store.baseline import Locked, read_baseline
from modules.m2_baseline.store.signoff import SignoffStore
from modules.m2_baseline.store.requests import LinkError, OwnerIndex, RequestStore, StoreError, WrongState
from sh_platform.auth.sessions import LoginThrottle
from sh_platform.context_docs import reader
from sh_platform.context_docs.store import DocStore
from sh_platform.modulegate import may_use_module
from sh_platform.public_link import full_url
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)
MODULE = "m2_baseline"
HEADER = "x-session-token"
BODY_MAX = 64 * 1024
SAMPLE_BODY_MAX = reader.MAX_UPLOAD_BYTES * 4 // 3 + 64 * 1024   # base64 grows a file by a third
SAMPLE_AGENT = "lens"         # a sample is filed on Lens's shelf, the one she reads
SOURCE_LINK, SOURCE_MEETING = "answer link", "a meeting"
_INVALID = ("link_invalid", "This link is not working. Please ask for a new one.")
_LOCKED = ("too_many_tries", "Too many tries. Please wait a minute, then open your link again.")
_NOT_FOUND = ("not_found", "We could not find that.")
BAD_BODY = "Those details could not be read. Please try again."


def _plain(status: int, error: str, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": error, "message": message, **extra}, status_code=status)


class _Locked(Exception):
    pass


def _clock(request: Request) -> Callable[[], float]:
    return getattr(request.app.state, "m2_clock", time.time)  # tests move time forward


def _throttle(app) -> LoginThrottle:
    """One failure counter per app, keyed by the caller's address. ponytail: behind a proxy every caller shares one
    address; key on the proxy's forwarded address when one is deployed."""
    if getattr(app.state, "owner_throttle", None) is None:
        app.state.owner_throttle = LoginThrottle()
    return app.state.owner_throttle


def _run(fn: Callable):
    """Runs fn and turns the module's failures into plain answers; nothing technical reaches the screen."""
    try:
        return fn()
    except _Locked:
        return _plain(429, *_LOCKED)
    except LinkError as e:
        return _plain(404 if e.code == "link_invalid" else 409, e.code, e.message)
    except AnswerError as e:
        return _plain(422, "invalid", str(e), field=e.field)
    except WrongState as e:
        return _plain(409, "wrong_state", str(e))
    except reader.Refusal as e:
        return _plain(e.status, "refused", str(e))
    except LookupError:
        return _plain(404, *_NOT_FOUND)
    except StoreError as e:
        return _plain(500, "unreadable", str(e))
    except (PermissionError, CrossCompanyError):
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


async def _body(request: Request, limit: int = BODY_MAX) -> dict | None:
    """The JSON object in the body, or None. Counted as it arrives: a missing or false Content-Length does not help."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return None
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks))
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


# ---- the answer link (no account) ------------------------------------------------------------------------------

def _ground(request: Request) -> tuple:
    """(plane, store, request row, token, questionnaire) for a header token that is good right now. Every failure counts
    against the caller and gives one answer."""
    throttle, key = _throttle(request.app), request.client.host if request.client else "unknown"
    if throttle.locked(key):
        raise _Locked()
    try:
        token = request.headers.get(HEADER, "")
        m = R.TOKEN.fullmatch(token)
        if not m:
            raise LinkError(*_INVALID)
        root = request.app.state.settings.data_root
        entry = OwnerIndex(root).lookup(m.group(1))
        if entry is None or not may_use_module(request.app.state.entitlements, entry["company_id"], MODULE):
            raise LinkError(*_INVALID)
        plane = PlaneStore(root).plane_for(entry["company_id"]).ensure()
        store = RequestStore(plane, entry["baseline_id"], _clock(request))
        row = store.ground(m.group(1), token)
        return plane, store, row, token, load_questionnaire()
    except LinkError:
        throttle.failed(key)
        raise
    except (StoreError, LookupError, CrossCompanyError, ValueError, OSError):
        throttle.failed(key)
        raise LinkError(*_INVALID) from None


def _own_kpi(row: dict, body: dict) -> str:
    kpi_id = body.get("kpi_id")
    if not isinstance(kpi_id, str) or kpi_id not in row["kpi_ids"]:
        raise AnswerError("That measure is not part of your questions.", "kpi_id")
    return kpi_id


def _record_view(rec: dict | None, plane) -> dict | None:
    """A saved record for the screen, with the title of an attached sample (never its text)."""
    if rec is None:
        return None
    sample = (rec.get("sample_doc_id") or {}).get("value")
    title = None
    if sample:
        try:
            title = DocStore(plane).get(SAMPLE_AGENT, sample)["title"]
        except (LookupError, OSError, ValueError, KeyError, PermissionError):
            title = None
    return {**rec, "sample_title": title}


async def _grounded(request: Request):
    """The link's context, or the plain refusal. Runs BEFORE any body is read, so a caller with a bad token or a lock
    costs the server nothing."""
    return await run_in_threadpool(_run, lambda: _ground(request))


def _unsigned(plane, store: RequestStore) -> None:
    try:
        refuse_if_signed(plane, store.baseline_id)  # the link routes carry no baseline id for the route guard (N-E)
    except Locked as e:
        raise WrongState(str(e)) from None


def _open_for_edit(plane, store: RequestStore, row: dict) -> None:
    _unsigned(plane, store)
    if row["state"] == "answered":
        raise WrongState("Your answers are in. Ask the organiser to reopen them if something changed.")


@router.post("/answer/form")
async def answer_form(request: Request):
    def work():
        plane, store, row, _, q = _ground(request)
        row = store.opened(row["id"])  # sent -> opened, once
        names, mine = store.kpi_names(), AnswerStore(plane, store.baseline_id)
        by_kpi = {r["kpi_id"]: r for r in mine.for_owner(row["owner_name"])}
        return {"owner_name": row["owner_name"], "role": row["role"], "state": row["state"], "expires_at": row["expires_at"],
                "signed": (read_baseline(plane, store.baseline_id) or {}).get("state") == "signed",
                "confirmable": _my_parts(plane, store, row, request),
                "sign_in_parts": _my_parts(plane, store, row, request, with_account=True),
                "technical": _link_technical(plane, store, row, False),
                "technical_sign_in": [{"kpi_id": t["kpi_id"], "name": t["name"]} for t in _link_technical(plane, store, row, True)],
                "sign_in_path": f"/modules/m2_baseline/signoff/{store.baseline_id}",
                "kpis": [{"id": k, "name": names.get(k, "A measure"), "answers": _record_view(by_kpi.get(k), plane)}
                         for k in row["kpi_ids"]],
                "questions": _owner_questions(plane, store, row, getattr(request.state, "account_id", None)),
                "questionnaire": q.public()}
    return await run_in_threadpool(_run, work)


SIGN_IN = "Please sign in to answer this question."
SIGN_IN_TECH = "Please sign in to confirm this technical definition."


def _link_technical(plane, store: RequestStore, row: dict, with_account: bool) -> list[dict]:
    """The technical definitions of this link's measures that the person is the named data owner of, as THEY may see them (a part naming a row or
    measure hidden from them is withheld). An owner with no account confirms here; one with an account is sent to sign in (decision N4), so
    `with_account=True` lists those only for the page to say so."""
    from modules.m2_baseline.domain import catalogue as C
    from modules.m2_baseline.domain import technical as T
    from modules.m2_baseline.store import ambiguities as SA
    from modules.m2_baseline.store import catalogue as SC
    from modules.m2_baseline.store import technical as ST
    out = []
    for k in store.kpis():
        o = (k.get("owners") or {}).get("data") or {}
        mine = o.get("mark") != "unknown" and str(o.get("value") or "").strip().casefold() == row["owner_name"].strip().casefold()
        if k["id"] not in row["kpi_ids"] or not mine or bool(o.get("account_id")) != with_account:
            continue
        viewer, sees = SA.owner_view(plane, store.baseline_id, row["owner_name"], o.get("account_id"))
        if not sees(k):
            continue
        try:
            shown, _ = ST.catalogue_for(plane, store.baseline_id, viewer)
            out.append(ST.definition_view(k, T.row_names(shown), ST.hidden_terms(plane, store.baseline_id, viewer, sees)))
        except (C.CatalogueError, SC.StoreError):
            continue  # no catalogue to read yet: nothing to show, and nothing hidden is guessed at
    return out


@router.post("/answer/technical/confirm")
async def answer_technical_confirm(request: Request):
    """An owner with no account confirms the technical definition of a measure they are the data owner of, through their link; the confirmation is
    written under their name. An owner with an account is told to sign in."""
    ctx = await _grounded(request)
    if isinstance(ctx, JSONResponse):
        return ctx
    body = await _body(request)

    def work():
        from modules.m2_baseline.domain import technical as T
        from modules.m2_baseline.store import ambiguities as SA
        from modules.m2_baseline.store import technical as ST
        plane, store, row, _, _q = ctx
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        _unsigned(plane, store)
        kpi_id = _own_kpi(row, body)
        if any(t["kpi_id"] == kpi_id for t in _link_technical(plane, store, row, True)):
            return _plain(403, "not_allowed", SIGN_IN_TECH)
        if not any(t["kpi_id"] == kpi_id for t in _link_technical(plane, store, row, False)):
            raise AnswerError("That technical definition is not yours to confirm.", "kpi_id")
        _, sees = SA.owner_view(plane, store.baseline_id, row["owner_name"])
        try:
            ST.confirm(plane, store.baseline_id, kpi_id, row["owner_name"], sees)
        except T.Refused as e:
            raise AnswerError(str(e), "kpi_id") from None
        return {"technical": _link_technical(plane, store, row, False)}
    return await run_in_threadpool(_run, work)


def _owner_questions(plane, store: RequestStore, row: dict, session_account: str | None = None) -> list[dict]:
    """M2-E1: the open questions an organiser added for this owner, worded for THEM: [{ambiguity_id, kpi_id, kpi_name, text}]. A question that would
    name something hidden from the owner reads generically; one about a measure they may not see is left out."""
    from modules.m2_baseline.store import ambiguities as SA
    kpis, out = {k["id"]: k for k in store.kpis()}, []
    for x in row.get("questions") or []:
        k = kpis.get(x.get("kpi_id"))
        item = next((a for a in (k or {}).get("ambiguities") or [] if a["id"] == x.get("ambiguity_id")), None)
        if k is None or item is None or item.get("status") != "open" or k["id"] not in row["kpi_ids"]:
            continue
        o = next((o for o in k["owners"].values() if o.get("value") == row["owner_name"]), {})
        text = SA.for_owner(plane, store.baseline_id, k, item, row["owner_name"], o.get("account_id"))
        if text:
            out.append({"ambiguity_id": item["id"], "kpi_id": k["id"], "kpi_name": k["name"], "text": text,
                        "needs_sign_in": bool(o.get("account_id")) and o.get("account_id") != session_account})  # an owner with an account answers signed in (decision N4)
    return out


@router.post("/answer/question")
async def answer_question(request: Request):
    """The owner replies to a question put to them: the existing settle path, stated by them (it updates the part of the definition it is about
    and settles the item). Only a question that was asked of this owner, on one of their own measures."""
    ctx = await _grounded(request)
    if isinstance(ctx, JSONResponse):
        return ctx
    body = await _body(request)

    def work():
        from modules.m2_baseline.domain import ambiguities as A
        from modules.m2_baseline.store import ambiguities as SA
        plane, store, row, _, _q = ctx
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        _unsigned(plane, store)
        kpi_id, amb_id = _own_kpi(row, body), body.get("ambiguity_id")
        if not any(x.get("ambiguity_id") == amb_id and x.get("kpi_id") == kpi_id for x in row.get("questions") or []):
            raise AnswerError("That question was not put to you.", "ambiguity_id")
        session = getattr(request.state, "account_id", None)
        if any(q["ambiguity_id"] == amb_id and q["needs_sign_in"] for q in _owner_questions(plane, store, row, session)):
            return _plain(403, "not_allowed", SIGN_IN)  # a forwarded link cannot answer as an account holder
        try:
            SA.answer_as_owner(plane, store.baseline_id, kpi_id, str(amb_id), str(body.get("resolution") or ""), row["owner_name"])
        except A.Refused as e:
            raise AnswerError(str(e), "resolution") from None
        return {"questions": _owner_questions(plane, store, row, session)}
    return await run_in_threadpool(_run, work)


def _signoff(plane, request: Request) -> SignoffStore:
    return SignoffStore(plane, contracts_dir=getattr(request.app.state, "m2_contracts_dir", None))


def _my_parts(plane, store: RequestStore, row: dict, request: Request | None = None, with_account: bool = False) -> list[dict]:
    """The parts of this person's own KPIs that they may confirm through their link: only those where they are the
    nominated owner and have no account (a person with an account confirms after signing in)."""
    contracts = getattr(request.app.state, "m2_contracts_dir", None) if request else None
    return SignoffStore(plane, contracts_dir=contracts).my_parts(store.baseline_id, row["owner_name"], set(row["kpi_ids"]), with_account)


@router.post("/answer/confirm")
async def answer_confirm(request: Request):
    """"Confirm my part": a nominee with no account confirms their own part of one of their own measures. The link is
    the proof; the confirmation is written to the sign-off audit trail under their name."""
    ctx = await _grounded(request)
    if isinstance(ctx, JSONResponse):
        return ctx
    body = await _body(request)

    def work():
        plane, store, row, _, _q = ctx
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        _unsigned(plane, store)
        kpi_id = _own_kpi(row, body)
        part = body.get("part")
        if not isinstance(part, str) or not any(m["kpi_id"] == kpi_id and m["part"] == part for m in _my_parts(plane, store, row, request)):
            raise AnswerError("That part is not yours to confirm.", "part")
        try:
            _signoff(plane, request).confirm_by_link(store.baseline_id, row["owner_name"], kpi_id, part)
        except SignoffError as e:
            return _plain(409, e.code, e.message)
        return {"confirmable": _my_parts(plane, store, row, request)}
    return await run_in_threadpool(_run, work)


@router.post("/answer/save")
async def answer_save(request: Request):
    ctx = await _grounded(request)
    if isinstance(ctx, JSONResponse):
        return ctx
    body = await _body(request)

    def work():
        plane, store, row, _, q = ctx
        _open_for_edit(plane, store, row)
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        kpi_id = _own_kpi(row, body)
        fields = clean_answers(q, body.get("answers"), row["owner_name"], SOURCE_LINK)
        if not fields:
            raise AnswerError("Please answer at least one question, or mark it \"I don't know\".")
        rec = AnswerStore(plane, store.baseline_id, _clock(request)).save(row["owner_name"], kpi_id, fields, request_id=row["id"])
        return {"saved": _record_view(rec, plane)}
    return await run_in_threadpool(_run, work)


@router.post("/answer/submit")
async def answer_submit(request: Request):
    def work():
        plane, store, row, _, _q = _ground(request)
        _unsigned(plane, store)
        done = AnswerStore(plane, store.baseline_id).answered_kpis(row["owner_name"])
        if not set(row["kpi_ids"]) <= done:
            raise AnswerError("Please answer at least one question for each measure, or mark it \"I don't know\".")
        return {"state": store.answered(row["id"])["state"]}
    return await run_in_threadpool(_run, work)


def _attach_sample(plane, store: RequestStore, owner: str, kpi_id: str, body: dict, now) -> dict:
    """Reads the upload into the company context store (it stays on this machine) and records it on the answer."""
    try:
        data = base64.b64decode(str(body.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        raise AnswerError("That file could not be read. Please try again.", "data") from None
    doc = DocStore(plane).upload(SAMPLE_AGENT, owner, str(body.get("filename") or ""), data,
                                 title=str(body.get("title") or ""), description=f"Sample for a measure, from {owner}")
    rec = AnswerStore(plane, store.baseline_id, now).save(owner, kpi_id, {"sample_doc_id": prov(doc["doc_id"], "stated", owner, doc["title"])})
    return {"saved": _record_view(rec, plane)}


@router.post("/answer/sample")
async def answer_sample(request: Request):
    ctx = await _grounded(request)
    if isinstance(ctx, JSONResponse):
        return ctx
    body = await _body(request, SAMPLE_BODY_MAX)

    def work():
        plane, store, row, _, q = ctx
        _open_for_edit(plane, store, row)
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        kpi_id = _own_kpi(row, body)
        store.count_sample(row["id"], q.limits["samples_per_link"])
        return _attach_sample(plane, store, row["owner_name"], kpi_id, body, _clock(request))
    return await run_in_threadpool(_run, work)


# ---- the organiser: requests, outstanding view, chasing (M2-06, M2-29) ----------------------------------------------

def _org(request: Request, baseline_id: str) -> tuple:
    """(plane, store, questionnaire, organiser name) of the signed-in company's own baseline. Company and person come from
    the server session, never from the request."""
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None
    if not baseline_id or len(baseline_id) > 64 or not all(c.isalnum() or c in "_-" for c in baseline_id):
        raise LookupError("no baseline")
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return plane, RequestStore(plane, baseline_id, _clock(request)), load_questionnaire(), str(acct.get("display_name") or "Your organiser")


def _seen(request: Request, store: RequestStore) -> set[str]:
    """The measures the signed-in person may see (the work list's rule, domain/worklist.py). Anything about a measure
    outside this set is left out of every answer: its answers, its requests, its owners' names, its counts."""
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    organiser = "company_admin" in (request.state.roles or [])
    return W.visible_ids(store.kpis(), str(acct.get("display_name") or ""), request.state.account_id, organiser)


def _mine(store: RequestStore, request_id: str, seen: set[str]) -> dict:
    """The request, or "not found" when none of its measures is one the asker may see."""
    row = store.get(request_id)
    if not set(row["kpi_ids"]) & seen:
        raise LookupError("no request")
    return row


def _outstanding(plane, store: RequestStore, q: Questionnaire, seen: set[str]) -> dict:
    now = store.now()
    names = {k: n for k, n in store.kpi_names().items() if k in seen}
    done = AnswerStore.kpis_by_owner(AnswerStore(plane, store.baseline_id).all())  # one read of the answers file
    everyone = store.all()
    rows = [R.request_view(r, now, q, names, len(done.get(r["owner_name"], set()) & set(r["kpi_ids"])))
            for r in ({**r, "kpi_ids": [k for k in r["kpi_ids"] if k in seen]} for r in everyone) if r["kpi_ids"]]
    owes = [r for r in rows if r["state"] in R.OPEN_STATES]
    waiting = {}
    for r in owes:
        for k in r["kpis"]:
            waiting.setdefault(k["id"], {"kpi_id": k["id"], "kpi_name": k["name"], "waiting_on": []})["waiting_on"].append(r["owner_name"])
    asked = {r["owner_name"] for r in everyone}
    return {"requests": rows, "signed": (read_baseline(plane, store.baseline_id) or {}).get("state") == "signed",
            "summary": {"asked": len(rows), "answered": sum(r["state"] == "answered" for r in rows),
                        "outstanding": len(owes), "in_meeting": sum(r["state"] == "in_meeting" for r in rows)},
            "waiting_on": list(waiting.values()),
            "alerts": [r["nira"] for r in owes if r["organiser_told"] and r["nira"]],
            "not_yet_asked": [o["name"] for o in R.owners_to_ask([k for k in store.kpis() if k["id"] in seen]) if o["name"] not in asked]}


def _view_of(plane, store, q, request_id: str, seen: set[str]) -> dict:
    found = next((r for r in _outstanding(plane, store, q, seen)["requests"] if r["id"] == request_id), None)
    if found is None:
        raise LookupError("no request")
    return found


@router.get("/baselines/{baseline_id}/requests")
async def outstanding(request: Request, baseline_id: str):
    def work():
        plane, store, q, _ = _org(request, baseline_id)
        return _outstanding(plane, store, q, _seen(request, store))
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/requests")
async def send_requests(request: Request, baseline_id: str):
    """One request per nominated owner. The link of a new one is returned here, once, with the email text to copy."""
    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        seen = _seen(request, store)
        made = store.send(OwnerIndex(request.app.state.settings.data_root), q, seen, organiser)
        skipped = any(set(o["kpi_ids"]) - seen for o in R.owners_to_ask(store.kpis()))
        view = _outstanding(plane, store, q, seen)["requests"]
        out = []
        for row, token in made:
            v = next((x for x in view if x["id"] == row["id"]), None)
            if v is None:  # every measure of this request is one the asker may not see
                continue
            out.append({**v, "link_path": f"/answer/{token}" if token else None, "address": _full_link(request, token) if token else None,
                        "email": _email(store, row, organiser, link=_full_link(request, token), only=seen) if token else None})
        return {"sent": out, "new": sum(o["link_path"] is not None for o in out),
                "note": SKIPPED if skipped else None}
    return await run_in_threadpool(_run, work)


SKIPPED = "Some requests can only be sent by someone who can see those measures."


def _full_link(request: Request, token: str) -> str:
    """The address to put in the email (sh_platform/public_link.py: shared with module 1's emails)."""
    return full_url(request, f"/answer/{token}")


def _email(store: RequestStore, row: dict, organiser: str, make=R.email_text, link: str | None = None, only: set[str] | None = None) -> dict:
    names = store.kpi_names()
    shown = [names.get(k, "A measure") for k in row["kpi_ids"] if only is None or k in only]
    me = row["owner_name"].strip()
    mine = {k for k in row["kpi_ids"] if only is None or k in only}  # only this request's measures that the caller may see
    has_account = any(o.get("account_id") for k in store.kpis() if k["id"] in mine for o in k["owners"].values() if (o.get("value") or "").strip() == me)
    asked = [x["text"] for x in row.get("questions") or [] if x.get("kpi_id") in mine] or None  # M2-E1: open questions added for this owner
    return make(row["owner_name"], organiser, shown, link, has_account, questions=asked) if link else make(row["owner_name"], organiser, shown, questions=asked)


@router.post("/baselines/{baseline_id}/requests/{request_id}/remind")
async def remind(request: Request, baseline_id: str, request_id: str):
    """Marks a reminder as sent and records its date. Nira has no email service, so she gives the words to copy."""
    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        seen = _seen(request, store)
        _mine(store, request_id, seen)
        row = store.remind(request_id)
        return {"request": _view_of(plane, store, q, request_id, seen), "email": _email(store, row, organiser, R.reminder_text, only=seen)}
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/requests/{request_id}/revoke")
async def revoke(request: Request, baseline_id: str, request_id: str):
    def work():
        plane, store, q, _ = _org(request, baseline_id)
        seen = _seen(request, store)
        _mine(store, request_id, seen)
        store.revoke(request_id)
        return {"request": _view_of(plane, store, q, request_id, seen)}
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/requests/{request_id}/relink")
async def relink(request: Request, baseline_id: str, request_id: str):
    """A new link; the old one stops working. Returned once, with the email text."""
    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        seen = _seen(request, store)
        _mine(store, request_id, seen)
        row, token = store.relink(request_id, OwnerIndex(request.app.state.settings.data_root), q)
        return {"request": _view_of(plane, store, q, request_id, seen), "link_path": f"/answer/{token}", "address": _full_link(request, token),
                "email": _email(store, row, organiser, link=_full_link(request, token), only=seen)}
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/requests/{request_id}/reopen")
async def reopen(request: Request, baseline_id: str, request_id: str):
    """Lets an answered person change their answers: a new link (shown once), the old answers kept, recorded in the audit trail.
    Contract: the organiser roles only, the same as relink (company_admin, sponsor, analyst; see manifest.yaml); a participant or
    guest is refused by the route permissions."""
    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        seen = _seen(request, store)
        _mine(store, request_id, seen)
        row, token = store.reopen(request_id, OwnerIndex(request.app.state.settings.data_root), q)
        _signoff(plane, request).record(baseline_id, organiser, "reopen", detail=f"reopened the answers of {row['owner_name']}")
        return {"request": _view_of(plane, store, q, request_id, seen), "link_path": f"/answer/{token}", "address": _full_link(request, token),
                "email": _email(store, row, organiser, link=_full_link(request, token), only=seen)}
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/requests/{request_id}/meeting")
async def to_meeting(request: Request, baseline_id: str, request_id: str):
    """"Answer in a meeting instead": the link is withdrawn and the organiser fills the form for the person."""
    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        seen = _seen(request, store)
        _mine(store, request_id, seen)
        store.to_meeting(request_id, organiser)
        return {"request": _view_of(plane, store, q, request_id, seen)}
    return await run_in_threadpool(_run, work)


# ---- the organiser: answers, and answering in a meeting (M2-10, M2-11) ----------------------------------------------

@router.get("/baselines/{baseline_id}/answers")
async def answers(request: Request, baseline_id: str):
    def work():
        plane, store, q, _ = _org(request, baseline_id)
        seen = _seen(request, store)
        names = {k: n for k, n in store.kpi_names().items() if k in seen}
        return {"questionnaire": q.public(), "kpis": [{"id": k, "name": n} for k, n in names.items()],
                "answers": [_record_view(a, plane) for a in read_answers(plane, baseline_id, q) if a["kpi_id"] in seen]}
    return await run_in_threadpool(_run, work)


def _meeting_target(store: RequestStore, body: dict, q: Questionnaire, seen: set[str]) -> tuple[str, str]:
    owner = str(body.get("owner_name") or "").strip()
    if not owner or len(owner) > q.limits["name_chars"]:
        raise AnswerError("Please give the name of the person who is answering.", "owner_name")
    kpi_id = body.get("kpi_id")
    if not isinstance(kpi_id, str) or kpi_id not in seen:
        raise AnswerError("Please choose one of the measures.", "kpi_id")
    return owner, kpi_id


@router.put("/baselines/{baseline_id}/meeting-answers")
async def meeting_answers(request: Request, baseline_id: str):
    """The organiser fills the same form for someone, marked "in a meeting" with that person's name."""
    body = await _body(request)

    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        owner, kpi_id = _meeting_target(store, body, q, _seen(request, store))
        fields = clean_answers(q, body.get("answers"), owner, f"{SOURCE_MEETING}, written down by {organiser}")
        if not fields:
            raise AnswerError("Please answer at least one question, or mark it \"I don't know\".")
        meeting = {"by": organiser, "at": store.now().isoformat()}
        rec = AnswerStore(plane, baseline_id, _clock(request)).save(owner, kpi_id, fields, meeting=meeting)
        store.meeting_started(owner, organiser)
        return {"saved": _record_view(rec, plane)}
    return await run_in_threadpool(_run, work)


@router.post("/baselines/{baseline_id}/sample")
async def meeting_sample(request: Request, baseline_id: str):
    body = await _body(request, SAMPLE_BODY_MAX)

    def work():
        plane, store, q, organiser = _org(request, baseline_id)
        if body is None:
            return _plain(400, "bad_request", BAD_BODY)
        owner, kpi_id = _meeting_target(store, body, q, _seen(request, store))
        return _attach_sample(plane, store, owner, kpi_id, body, _clock(request))
    return await run_in_threadpool(_run, work)
