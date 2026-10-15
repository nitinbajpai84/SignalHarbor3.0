"""Nira's drafted messages (shape in docs/plan/SHAPES.md section 1: P4 sends). Drafts live in the plane at pulse/messages.json; nothing leaves
until the organiser or a company admin posts to the send route. The send goes through `app.state.email_sender(plane, addresses, subject, body)`;
the repo has no email path yet, so without one the message stays a draft."""
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile.api import _plane, _viewer
from sh_platform.pulse.templates import KINDS, WRITERS

log = logging.getLogger(__name__)
router = APIRouter()


def _file(plane):
    return plane.path("pulse", "messages.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all(plane) -> list[dict]:
    return (read_json_strict(_file(plane), dict) or {}).get("messages", [])


def draft(plane, kind: str, record: dict) -> dict:
    """Append the draft for this record and kind, once: asking again returns the one already there (whatever its state)."""
    if kind not in KINDS:
        raise ValueError("unknown kind")
    from_record = str(record.get("from_record") or "")
    mid = "m-" + hashlib.sha256(f"{kind}|{from_record}".encode()).hexdigest()[:16]
    if kind == "ops_report" and "runs" not in record:
        record = {**record, "runs": (read_json_strict(plane.path("warehouse", "runs.json"), dict) or {}).get("runs", [])}
    text = WRITERS[kind](record)
    path = _file(plane)
    with lock_for(path):
        rows = _all(plane)
        if (old := next((m for m in rows if m["id"] == mid), None)) is not None:
            return old
        msg = {"id": mid, "kind": kind, "to": record.get("to") or [], **text, "drafted_at": _now(), "state": "draft", "sent_by": None,
               "sent_at": None, "from_record": from_record, "organiser_account_id": record.get("organiser_account_id")}  # last key: who may send
        write_json_atomic(path, {"messages": rows + [msg]})
        return msg


def _may(request: Request, m: dict) -> bool:
    return "company_admin" in (request.state.roles or []) or (
        m.get("organiser_account_id") is not None and m["organiser_account_id"] == request.state.account_id)


def _open(request: Request):
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, "No company space for you.") from None


@router.get("/api/pulse/messages")
def get_api_pulse_messages(request: Request):
    plane = _open(request)
    return {"messages": [m for m in _all(plane) if _may(request, m)]}


@router.post("/api/pulse/messages/{message_id}/send")
def post_api_pulse_messages_message_id_send(request: Request, message_id: str):
    plane = _open(request)
    sender = getattr(request.app.state, "email_sender", None)
    path = _file(plane)
    with lock_for(path):
        rows = _all(plane)
        m = next((x for x in rows if x["id"] == message_id), None)
        if m is None:
            raise HTTPException(404, "Not found.")
        if not _may(request, m):
            raise HTTPException(403, "Only the organiser or a company admin can send this.")
        if m["state"] != "draft":
            raise HTTPException(409, "This message has already been dealt with.")
        accounts = request.app.state.account_store
        addresses = [a["email"] for p in m["to"] if p.get("account_id") and (a := accounts.get(p["account_id"])) and a.get("email")]
        if not addresses:
            raise HTTPException(409, "None of the people named has an address yet.")
        if sender is None:
            raise HTTPException(503, "No email path is set up yet; the message stays a draft.")
        try:
            sender(plane, addresses, m["subject"], m["body"])
        except Exception:  # noqa: BLE001 the sender's text may echo the body; keep it out of the log
            log.warning("the message %s could not be sent", message_id)
            raise HTTPException(502, "The email could not be sent; it is still a draft.") from None
        m.update(state="sent", sent_by=_viewer(request).name, sent_at=_now())
        write_json_atomic(path, {"messages": rows})
        return {"id": m["id"], "state": "sent", "sent_by": m["sent_by"], "sent_at": m["sent_at"], "sent_to": len(addresses)}
