"""Harbor 3.0 case (spec: docs/v3/HARBOR-SPEC.md, 14 Oct addendum). The 2.0 case (e4_cases) and Tally (n1_tally), reshaped; no new store.

- `GET /api/v3/cases/{cid}` -> {id,title,status,owner,due,thread,what,evidence:[{source,row,side}],steps:[{label,answer}],history:[{at,text}],
   number,kind,amount,currency,closed,draft:{to,subject,body,sent:false}}
- `POST /api/v3/cases/{cid}/act {answer, reason?}` -> the case. answer: ask (keep the drafted email on the case), note (needs reason),
   timing (close as timing), resolved (close, needs reason), dismiss (not an exception, needs reason).
A drafted email is only drafted: nothing here sends mail."""
import logging

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e4_cases as C
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
log = logging.getLogger(__name__)
TIMING = "A timing difference that clears by itself."
STEPS = [{"label": "Ask the administrator", "answer": "ask"}, {"label": "Mark as timing, expect next month", "answer": "timing"},
         {"label": "Correct our record", "answer": "note"}]


def _run(request: Request, fn):
    viewer = viewer_of(request)
    try:
        return fn(_plane(request), viewer)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    except C.Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message} if e.status == 403 else e.message) from None


def _tally(plane, viewer, cid: str) -> dict:
    """Tally's rules analysis (no model call). A failure inside Tally leaves the case readable with no evidence."""
    from sh_platform.v1 import n1_tally as T
    try:
        return T.explain(plane, viewer, cid, quick=True)
    except Exception:  # noqa: BLE001 - one odd case must not break the page
        log.warning("tally could not look at case %s", cid, exc_info=True)
        return {}


def _project(plane, cid: str) -> str:
    try:
        from sh_platform.v1 import n1_tally as T
        return T._project_of(plane, cid)
    except Exception:  # noqa: BLE001
        return ""


def _evidence(t: dict) -> list[dict]:
    out = []
    for f in t.get("findings") or []:
        chips = f.get("chips") or []
        out += [{"source": c["label"], "row": f["text"], "side": "have"} for c in chips] or [{"source": "Harbor", "row": f["text"], "side": "have"}]
    return out + [{"source": "Not there", "row": m, "side": "missing"} for m in t.get("missing") or []]


def _draft(c: dict) -> dict:
    amt = f"{c['currency']} {c['amount']:,.0f}" if c.get("amount") is not None and c.get("currency") else "the amount"
    ref = c.get("number") or c["id"]
    return {"to": "[administrator contact]", "subject": f"{c['title']} ({ref})", "sent": False,
            "body": f"Hello, our records show: {c['title']}, {amt}. It does not appear on your side. Could you check whether it was received and booked, "
                    f"and tell us the expected date if it is timing? Our reference is {ref}."}


def _shape(plane, viewer, cid: str) -> dict:
    c = C.get(plane, cid, viewer)
    t = _tally(plane, viewer, c["id"])
    closed = c["status"] in ("resolved", "rejected")
    amount = float(c["amount"]) if c.get("amount") is not None else None
    what = c.get("description") or t.get("summary") or c["title"]
    out = {"id": c["id"], "number": c.get("number"), "title": c["title"], "status": "closed" if closed else "open", "owner": c.get("owner") or "",
           "due": str(c["due"])[:10] if c.get("due") else "", "thread": _project(plane, c["id"]), "what": t.get("summary") or what,
           "kind": c.get("exception_type"), "amount": amount, "currency": c.get("currency"), "closed": closed,
           "evidence": _evidence(t), "steps": [] if closed else STEPS,
           "history": [{"at": str(h["at"]), "text": h["text"]} for h in c["history"]]}
    out["draft"] = None if closed else _draft(out)
    return out


@router.get("/api/v3/cases/{cid}")
def get_case(request: Request, cid: str):
    return _run(request, lambda p, v: _shape(p, v, cid))


@router.post("/api/v3/cases/{cid}/act")
def post_act(request: Request, cid: str, body: dict = Body(default_factory=dict)):
    answer, reason = str(body.get("answer") or ""), str(body.get("reason") or "").strip()

    def go(p, v):
        c = C.get(p, cid, v)  # the access check comes before the action
        if answer == "ask":
            C.add_event(p, c["id"], v, "comment", "Drafted an email to the administrator. Nothing was sent." + (f" Draft: {reason}" if reason else ""))
        elif answer == "note":
            if not reason:
                raise C.Refused(400, "Write the note first.")
            C.add_event(p, c["id"], v, "comment", reason)
        elif answer == "timing":
            C.dismiss(p, c["id"], v, reason or TIMING)
        elif answer in ("resolved", "dismiss"):
            if not reason:
                raise C.Refused(400, "Say why this case is closing.")
            if answer == "resolved":
                if c["status"] == "new":  # single-signer office: closing a new case takes it first
                    C.take(p, c["id"], v)
                C.resolve(p, c["id"], v, "resolved", reason)
            else:
                C.dismiss(p, c["id"], v, reason)
        else:
            raise C.Refused(400, "Choose one of the steps on the page.")
        return _shape(p, v, c["id"])
    return _run(request, go)
