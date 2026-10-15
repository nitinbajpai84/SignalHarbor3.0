from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.auth.accounts import normalise_email

router = APIRouter()
_BAD_LOGIN = {"error": "login_failed", "message": "That email and password do not match. Please try again."}


@router.post("/api/auth/login")
async def login(request: Request):
    st = request.app.state
    # Only a JSON content type: a cross-site form or text/plain POST cannot set it without a preflight.
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse(_BAD_LOGIN, status_code=415)
    try:
        body = await request.json()
        email, password = body["email"], body["password"]
        if not isinstance(email, str) or not isinstance(password, str):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        return JSONResponse(_BAD_LOGIN, status_code=401)
    key = normalise_email(email)
    if st.login_throttle.locked(key):
        return JSONResponse(_BAD_LOGIN, status_code=401)
    acct = await run_in_threadpool(st.account_store.verify, email, password)  # scrypt: off the event loop
    if acct is None:
        st.login_throttle.failed(key)
        return JSONResponse(_BAD_LOGIN, status_code=401)
    st.login_throttle.ok(key)
    previous = st.sessions.resolve(request.cookies.get("sh_session"))
    if previous:
        st.sessions.destroy(previous["sid"])  # a new sign-in ends the session the browser still held
    cookie, csrf = st.sessions.create(acct)
    resp = JSONResponse({"display_name": acct["display_name"], "company_id": acct["company_id"],
                         "roles": acct["roles"]})
    secure = st.settings.mode != "dev"
    resp.set_cookie("sh_session", cookie, httponly=True, samesite="lax", secure=secure, path="/",
                    max_age=st.sessions.absolute)
    resp.set_cookie("sh_csrf", csrf, httponly=False, samesite="lax", secure=secure, path="/",
                    max_age=st.sessions.absolute)
    return resp


@router.post("/api/auth/logout")
def logout(request: Request):
    request.app.state.sessions.destroy(request.state.sid)
    resp = JSONResponse({"status": "signed_out"})
    resp.delete_cookie("sh_session", path="/")
    resp.delete_cookie("sh_csrf", path="/")
    return resp


@router.get("/api/auth/me")
def me(request: Request):
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return {"display_name": acct.get("display_name"), "company_id": request.state.company_id,
            "roles": request.state.roles, "account_id": request.state.account_id, "time_zone": _time_zone(request)}


def _time_zone(request: Request) -> str:
    """PF2: the company's one time zone for every displayed date (profile company.time_zone), else Asia/Singapore."""
    from sh_platform.intents.lifecycle import company_zone
    from sh_platform.profile.api import _plane
    try:
        return getattr(company_zone(_plane(request)), "key", None) or "Asia/Singapore"
    except Exception:  # noqa: BLE001  no company space (super admin) or an unreadable profile: the default
        return "Asia/Singapore"
