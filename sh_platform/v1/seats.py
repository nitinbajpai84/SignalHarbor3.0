"""Seats for Signal Harbor 1.0: who acts where, from the roles an account already has (no new roles).

`seat_of(viewer)` maps roles to seats per the seat table in docs/plan/V1-BUILD.md. `require_seat(request, seat)`
resolves the viewer the way the kernel routes do (sh_platform.profile.api) and refuses with a 403 the screen words:
`{"error": "not_allowed", "message": ...}` inside `detail`, which ui/src/api/client.ts lifts and shows."""
from __future__ import annotations

from fastapi import HTTPException, Request

from sh_platform.profile.view import Viewer

DECISION_MAKER, ARCHITECT, DATA_ENGINEER, OPS_MANAGER, CONSUMER, HEAD_OF_DATA = (
    "decision_maker", "architect", "data_engineer", "ops_manager", "consumer", "head_of_data")

SEAT_ROLES: dict[str, frozenset[str]] = {
    DECISION_MAKER: frozenset({"company_admin", "sponsor"}),
    ARCHITECT: frozenset({"analyst", "company_admin"}),
    DATA_ENGINEER: frozenset({"analyst", "company_admin"}),
    OPS_MANAGER: frozenset({"analyst", "company_admin"}),
    # V6: the head of data approves the design pack, the build plan and the verified map. `head_of_data` is held in addition to `analyst`
    # (Anita Rao in the seed); the company administrator keeps the seat it always had.
    HEAD_OF_DATA: frozenset({"head_of_data", "company_admin"}),
    CONSUMER: frozenset({"owner", "approver", "participant", "company_admin", "sponsor", "analyst"}),
}

REFUSAL = {
    DECISION_MAKER: "Only the decision maker can do this.",
    ARCHITECT: "Only the architect can do this.",
    DATA_ENGINEER: "Only the data engineer can do this.",
    OPS_MANAGER: "Only the ops manager can do this.",
    HEAD_OF_DATA: "Only the head of data can do this.",
    CONSUMER: "You do not have access to this.",
}
NO_SPACE = "Your company space could not be opened. Please ask your administrator."


def seat_of(viewer) -> set[str]:
    """Seats a viewer holds. Takes a profile Viewer, anything with `.roles`, or a plain iterable of roles."""
    roles = set(getattr(viewer, "roles", viewer) or ())
    return {seat for seat, allowed in SEAT_ROLES.items() if roles & allowed}


def viewer_of(request: Request) -> Viewer:
    """The signed-in viewer, resolved as sh_platform.profile.api._viewer does. 403 when there is no company."""
    if getattr(request.state, "company_id", None) is None:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE})
    from sh_platform.profile.api import _viewer  # deferred: profile.api pulls in the whole profile router
    return _viewer(request)


def require_seat(request: Request, seat: str) -> Viewer:
    """The viewer if they hold `seat`, else a 403 naming who may act."""
    if seat not in SEAT_ROLES:
        raise ValueError(f"unknown seat {seat!r}")  # a typo in a card must fail loudly, never open the door
    viewer = viewer_of(request)
    if seat not in seat_of(viewer):
        raise HTTPException(403, {"error": "not_allowed", "message": REFUSAL[seat]})
    return viewer
