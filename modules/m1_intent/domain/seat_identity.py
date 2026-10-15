"""Who holds which seat (M1-P05): the ONE place that turns the signed-in principal into a seat id.

The seat comes only from the server: a guest's token (its session must be the session in the path), or a signed-in
account that holds a seat, or the account that prepared the session (the organiser always has a room, also when
running the session alone). Never from a body, header or query. A seat id is a keyed hash (per-plane key) of the session and the
person, so it carries nothing about them and is the same wherever it is used (briefing, room, notes).
"""
import hmac
import logging
import secrets

from fastapi import Request

from modules.m1_intent.store.files import StoreError, lock_for
from modules.m1_intent.store.room import RoomStore
from sh_platform.egress.names import protected_names  # noqa: F401  (re-exported)
from sh_platform.egress.vault import NameVault, VaultUnavailable
from sh_platform.plane import CompanyPlane
from sh_platform.profile import Viewer, read as read_profile, read_unrestricted
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)


def plane_key(plane: CompanyPlane) -> bytes:
    """A key that lives only in this company's plane (made on first use): seals the join link and keys the seat ids."""
    f = plane.area("context") / "join_link.key"
    with lock_for(f):
        if not f.exists():
            f.write_text(secrets.token_hex(32), encoding="utf-8")
        return bytes.fromhex(f.read_text(encoding="utf-8").strip())


def _seat_id(plane: CompanyPlane, session_id: str, who: str) -> str:
    """Keyed hash: someone holding a guest id and the session id cannot work out the seat id without the plane's key."""
    return hmac.new(plane_key(plane), f"{session_id}:{who}".encode(), "sha256").hexdigest()[:32]


def seat_id_of(plane: CompanyPlane, session_id: str, seat: dict) -> str:
    """The seat id of a taken seat of the room (an account-bound seat counts as that account)."""
    return _seat_id(plane, session_id, seat["account_id"] or seat["participant_id"])


def seat_of(request: Request, session: dict, plane: CompanyPlane, read_after_close: bool = False) -> str | None:
    """The seat id of whoever is asking, or None (the caller then answers "not found" or "no seat"). After the close a
    guest's token is a seat only where the caller says so (`read_after_close`: the board and the charter)."""
    st, sid = request.state, session["id"]
    if st.account_id is None and session["state"] == "closed" and not read_after_close:
        return None
    rooms = RoomStore(plane)
    if st.account_id is not None:
        if session["organiser_account_id"] == st.account_id or rooms.seat_of_account(sid, st.account_id):
            return _seat_id(plane, sid, st.account_id)
        return None
    if st.guest_id is not None and st.m1_session_id == sid and rooms.seat_of_participant(sid, st.guest_id):
        return _seat_id(plane, sid, st.guest_id)
    return None


def person_name(request: Request, session: dict, plane: CompanyPlane) -> str:
    """The asking person's display name: their seat's name, else their account's."""
    st, sid, rooms = request.state, session["id"], RoomStore(plane)
    seat = (rooms.seat_of_account(sid, st.account_id) if st.account_id is not None
            else rooms.seat_of_participant(sid, st.guest_id))
    if seat:
        return str(seat["name"])
    acct = request.app.state.account_store.get(st.account_id) if st.account_id is not None else None
    return str((acct or {}).get("display_name") or "")


_ORGANISER_VIEW = Viewer("", frozenset({"company_admin"}))  # the only view that carries a person's account tie


def profile_viewer(request: Request) -> Viewer:
    """The signed-in person as the profile's viewer, built as the kernel does (sh_platform/profile/api.py `_viewer`): the account id and the
    shared-name flag (another account of the company with the same display name), so a restricted area that lists a name two accounts
    carry stays shut to both."""
    st = request.state
    name = str((request.app.state.account_store.get(st.account_id) or {}).get("display_name") or "")
    twins = [a for a in request.app.state.account_store.in_company(st.company_id) if norm(a.get("display_name")) == norm(name)]
    return Viewer(name, frozenset(st.roles or []), len(twins) > 1, st.account_id)


def profile_person(plane: CompanyPlane, account_id: str | None) -> str | None:
    """Which profile person this signed-in account is, or None: only the person whose `people.<pid>.account_id` is this account (A-043).
    Never matched by a display name, a slug or a name typed at a seat."""
    if account_id is None:
        return None
    people = read_profile(plane, _ORGANISER_VIEW)["people"]
    return next((pid for pid, p in sorted(people.items()) if (p.get("account_id") or {}).get("value") == account_id), None)


def name_is_tied_elsewhere(plane: CompanyPlane, name: str, account_id: str | None, is_enabled) -> bool:
    """True when `name` is (once case and spaces are set aside) the name of a profile person linked to an enabled account other than the
    caller's (a guest has none), and that person is visible in the unrestricted view: the answer tells a link holder nothing about
    people in restricted areas. `is_enabled(account_id)` says whether an account of this company exists and is switched on."""
    wanted = norm(name)
    if not wanted:
        return False
    org = read_profile(plane, _ORGANISER_VIEW)["people"]
    for pid, person in read_unrestricted(plane)["people"].items():
        if norm((person.get("name") or {}).get("value") or "") != wanted:
            continue
        tied = ((org.get(pid) or {}).get("account_id") or {}).get("value")
        if tied and tied != account_id and is_enabled(tied):
            return True
    return False


def register_names(request: Request, plane: CompanyPlane, session_id: str) -> None:
    """The company name, the signed-in person's name and every seated person's name (each part too) go into the
    egress vault before anything leaves (D-007). Guests have no account: their names come from their seats."""
    st = request.app.state
    acct = (st.account_store.get(request.state.account_id) if request.state.account_id is not None else None) or {}
    company = st.entitlements.company(request.state.company_id) or {}
    try:
        room = RoomStore(plane).get(session_id)
    except StoreError:
        room = None
        log.warning("the seats of this session could not be read")
    people = [str(acct.get("display_name") or ""),
              *(str(s["name"] or "") for s in (room or {}).get("seats", []) if s["state"] == "taken")]
    vault = NameVault(plane)
    for kind, name in protected_names(str(company.get("name") or ""), people):
        try:
            if name:
                vault.register(kind, name)
        except (ValueError, VaultUnavailable):
            log.warning("a name could not be registered with the egress vault")  # the gateway then refuses to send
