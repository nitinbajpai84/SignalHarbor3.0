"""E4a routes: the Action Desk's cases.

- `GET /api/v1/cases?status=&owner=&exception_type=&materiality_status=&portfolio_id=` → {cases} (each also has the screen names: materiality high|medium|low, due, state, amount, currency)
- `GET /api/v1/cases/{id}` (id or CASE-0001) → the case with history, impacts, approvals and `may` (the buttons this person may press; the same map is `can`), plus the screen view: maker_name, checker_name, proposal {text, sources}, affects[], history[] {at, by, text}
- `POST /api/v1/cases` {exception_type, title, ...} → the case
- `POST /api/v1/cases/{id}/explain` → the case, with Tally's proposal added to its history, and `tally` (the analysis)
- `GET /api/v1/cases/{id}/tally` → Tally's analysis (read-only); `POST /api/v1/cases/{id}/ask {question}` → the same with `answer`. Anyone who can see the case may use both; neither changes it (N1)
- `POST /api/v1/cases/{id}/take | assign {to,note?} | submit {explanation, checker?} | approve {rationale?} | send_back {reason} | resolve {code,note?} |
   dismiss {reason} | ask_finance {to} | note {text}` → the case
Logic and rules: e4_cases."""
import logging

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e4_cases as C
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
log = logging.getLogger(__name__)
BASE = "/api/v1/cases"


def _run(request: Request, fn):
    viewer = viewer_of(request)
    try:
        return fn(_plane(request), viewer)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    except C.Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message} if e.status == 403 else e.message) from None


@router.get(BASE)
def list_cases(request: Request, status: str = "", owner: str = "", exception_type: str = "", materiality_status: str = "", portfolio_id: str = ""):
    f = {"status": status, "owner": owner, "exception_type": exception_type, "materiality_status": materiality_status, "portfolio_id": portfolio_id}
    return _run(request, lambda p, v: {"cases": C.listing(p, v, {k: x for k, x in f.items() if x})})


@router.post(BASE)
def post_case(request: Request, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: C.get(p, C.open(p, {**body, "actor": v}), v))


@router.get(BASE + "/{cid}")
def get_case(request: Request, cid: str):
    return _run(request, lambda p, v: C.get(p, cid, v))


def _act(request: Request, cid: str, fn):
    return _run(request, lambda p, v: (C.get(p, cid, v), fn(p, v), C.get(p, cid, v))[2])  # the access check comes before the action


@router.post(BASE + "/{cid}/take")
def post_take(request: Request, cid: str):
    return _act(request, cid, lambda p, v: C.take(p, cid, v))


@router.post(BASE + "/{cid}/assign")
def post_assign(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.assign(p, cid, v, body.get("to"), body.get("note") or ""))


@router.post(BASE + "/{cid}/submit")
def post_submit(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.submit(p, cid, v, body.get("explanation") or "", body.get("checker"), body.get("code") or ""))


@router.post(BASE + "/{cid}/approve")
def post_approve(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.approve(p, cid, v, body.get("rationale") or ""))


@router.post(BASE + "/{cid}/send_back")
def post_send_back(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.send_back(p, cid, v, body.get("reason") or ""))


@router.post(BASE + "/{cid}/resolve")
def post_resolve(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.resolve(p, cid, v, body.get("code") or "", body.get("note") or ""))


@router.post(BASE + "/{cid}/dismiss")
def post_dismiss(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.dismiss(p, cid, v, body.get("reason") or ""))


@router.post(BASE + "/{cid}/ask_finance")
def post_ask_finance(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.ask_finance(p, cid, v, body.get("to")))


def _tally(request: Request, cid: str, question: str | None = None, record: bool = False, with_case: bool = False, quick: bool = False):
    """Tally's analysis of a case. A failure inside Tally is a plain sentence for the screen, never a server error."""
    from sh_platform.v1 import n1_tally as T

    def go(p, v):
        try:
            got = T.explain(p, v, C.get(p, cid, v)["id"], question, record=record, **({"quick": True} if quick else {}))
        except (C.Refused, PermissionError):
            raise
        except Exception:  # noqa: BLE001 - e.g. the warehouse file is busy; the person is told and can try again
            log.warning("tally could not look at case %s", cid, exc_info=True)
            raise C.Refused(409, "Tally could not look at this case just now. Please try again in a moment.") from None
        return {**C.get(p, cid, v), "tally": got} if with_case else got
    return _run(request, go)


@router.post(BASE + "/{cid}/explain")
def post_explain(request: Request, cid: str):
    def gate(p, v):  # filing a proposal changes the case: owner or company_admin only (viewing and asking stay open)
        if not (C.get(p, cid, v)["is_owner"] or C._admin(v)):
            raise C.Refused(403, "Only the person who owns this case, or a company administrator, can file Tally's proposal.")
    _run(request, gate)
    return _tally(request, cid, record=True, with_case=True)


@router.get(BASE + "/{cid}/tally")
def get_tally(request: Request, cid: str, quick: bool = False):
    return _tally(request, cid, quick=quick)  # quick=1: the rules analysis now; a plain call after it brings the model's wording


@router.post(BASE + "/{cid}/ask")
def post_ask(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    q = str(body.get("question") or "").strip()
    if not q:
        raise HTTPException(400, "Type a question for Tally.")
    return _tally(request, cid, question=q[:500])


@router.post(BASE + "/{cid}/note")
def post_note(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    return _act(request, cid, lambda p, v: C.add_event(p, cid, v, "comment", body.get("text") or ""))
