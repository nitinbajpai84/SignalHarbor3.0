from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.auth import mfa as MFA
from sh_platform.auth.accounts import normalise_email
from sh_platform.v1 import v3_audit as AUD

router = APIRouter()
_BAD_LOGIN = {"error": "login_failed", "message": "That email and password do not match. Please try again."}
_MFA_NEEDED = {"error": "mfa_required", "message": "Enter the 6-digit code from your authenticator app (or a recovery code)."}
_MFA_BAD = {"error": "mfa_failed", "message": "That code did not work. Please try again."}
_MFA_SETUP = {"error": "mfa_setup_required", "message": "Your company requires a second step at sign-in. Set up your authenticator app first."}


def _fail(st, request, key: str, why: str, status: int = 401, body: dict = _BAD_LOGIN):
    """A refused sign-in: counted against the login name, written to the audit log (the company's if the account is known)."""
    st.login_throttle.failed(key)
    known = st.account_store.get_by_email(key)
    AUD.log_event(request.app, known["company_id"] if known else None, key, "login_failed", why, ok=False)
    return JSONResponse(body, status_code=status)


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
        return _fail(st, request, key, "wrong email or password")
    m = acct.get("mfa") or {}
    if m.get("enabled") or MFA.office_requires(request.app, acct["company_id"]):
        if not m.get("enabled"):
            return JSONResponse(_MFA_SETUP, status_code=403)
        code = body.get("otp")
        if not isinstance(code, str) or not code.strip():
            return JSONResponse(_MFA_NEEDED, status_code=401)
        if not _second_step(st, acct, m, code):
            return _fail(st, request, key, "wrong second-step code", body=_MFA_BAD)
    st.login_throttle.ok(key)
    AUD.log_event(request.app, acct["company_id"], f"{acct['display_name']} <{acct['account_id'][:8]}>", "login", "signed in")
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


def _second_step(st, acct: dict, m: dict, code: str) -> bool:
    """A valid TOTP (each code once) or an unspent recovery code; the account record is updated to match."""
    n = MFA.check_totp(m["secret"], code, m.get("last_counter", -1))
    if n is not None:
        st.account_store.set_mfa(acct["email"], {**m, "last_counter": n})
        return True
    left = MFA.use_recovery(m, code)
    if left is None:
        return False
    st.account_store.set_mfa(acct["email"], {**m, "recovery": left})
    return True


async def _password_proof(request: Request):
    """(body, account, refusal): the password proves who is setting up MFA, signed in or not."""
    st = request.app.state
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return None, None, JSONResponse(_BAD_LOGIN, status_code=415)
    try:
        body = await request.json()
        email, password = body["email"], body["password"]
        if not isinstance(email, str) or not isinstance(password, str):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        return None, None, JSONResponse(_BAD_LOGIN, status_code=401)
    key = normalise_email(email)
    if st.login_throttle.locked(key):
        return None, None, JSONResponse(_BAD_LOGIN, status_code=401)
    acct = await run_in_threadpool(st.account_store.verify, email, password)
    if acct is None:
        return None, None, _fail(st, request, key, "wrong email or password (MFA setup)")
    return body, acct, None


@router.post("/api/auth/mfa/start")
async def mfa_start(request: Request):
    """Begin authenticator setup: the secret and otpauth link are shown once here. It is not active until confirmed."""
    body, acct, refusal = await _password_proof(request)
    if refusal:
        return refusal
    if (acct.get("mfa") or {}).get("enabled"):
        return JSONResponse({"error": "mfa_on", "message": "A second step is already set up for this account."}, status_code=409)
    secret = MFA.new_secret()
    request.app.state.account_store.set_mfa(acct["email"], {"secret": secret, "enabled": False, "recovery": [], "last_counter": -1})
    return {"secret": secret, "otpauth": MFA.otpauth_uri(secret, acct["email"])}


@router.post("/api/auth/mfa/confirm")
async def mfa_confirm(request: Request):
    """Switch MFA on with the first valid code; the recovery codes are shown once and kept only as hashes."""
    body, acct, refusal = await _password_proof(request)
    if refusal:
        return refusal
    st = request.app.state
    m = acct.get("mfa") or {}
    n = MFA.check_totp(m["secret"], str(body.get("otp") or "")) if m.get("secret") and not m.get("enabled") else None
    if n is None:
        return JSONResponse(_MFA_BAD, status_code=401)
    codes, hashes = MFA.new_recovery_codes()
    st.account_store.set_mfa(acct["email"], {"secret": m["secret"], "enabled": True, "recovery": hashes, "last_counter": n})
    AUD.log_event(request.app, acct["company_id"], f"{acct['display_name']} <{acct['account_id'][:8]}>", "settings_change", "MFA switched on")
    return {"enabled": True, "recovery_codes": codes}


@router.post("/api/auth/logout")
def logout(request: Request):
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    AUD.log_event(request.app, request.state.company_id, f"{acct.get('display_name')} <{str(request.state.account_id)[:8]}>", "logout", "signed out")
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
