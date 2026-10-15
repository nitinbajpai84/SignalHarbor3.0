"""One guard for "a signed baseline is read-only" (N-E). Every router of this module is built with `route_class=SignedGuard`:
a write (anything but GET) on /baselines/{baseline_id}/... answers 409 once that baseline is signed, before the route runs.
Signing sets baseline.json to "signed" (store/baseline.set_state); a new version sets it back. A baseline signed before that
was kept is read as signed too when its sign-off record says so for the current version. Two writes stay open on a signed
baseline: the new version itself and the retry of the closing step of a signature (matched on the route's own template).
When the state cannot be read the write is refused (fail closed); only a baseline that does not exist is left to the route's 404.
The answer-link routes carry no baseline id; they call `refuse_if_signed` themselves (api/requests.py)."""
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from modules.m2_baseline.store import baseline as B
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CrossCompanyError, PlaneStore

OPEN_WRITES = ("/baselines/{baseline_id}/versions", "/baselines/{baseline_id}/countersign",
               "/baselines/{baseline_id}/lens/ask", "/baselines/{baseline_id}/nira")
OPEN_WRITES += ("/send-back",)  # a note is a proposal beside a signed record (store/technical.py NOTES_FILE); it writes nothing the signature covers  # the two conversations change nothing; the redraft inside lens/ask refuses a signed baseline itself
SIGNING_STARTED = "Signing has started; nothing can change until it is finished or a new version is started."
UNREADABLE = "This baseline could not be checked, so nothing was changed. Please try again."


def refuse_if_signed(plane, baseline_id) -> None:
    """Raises Locked when signed, StoreError (or OSError/ValueError) when the state cannot be read; returns for no such baseline."""
    base = B.read_baseline(plane, baseline_id)
    if base is None:
        return
    doc = read_json_strict(B.root(plane) / baseline_id / "signoff.json", dict)
    versions = (doc or {}).get("versions")
    last = versions[-1] if isinstance(versions, list) and versions and isinstance(versions[-1], dict) else {}
    if base.get("state") == "signed" or last.get("status") == "signed":
        raise B.Locked(B.LOCKED)
    if last.get("countersign"):  # M2-E4: the first signature covers the documents as they were; nothing changes until the second is given or a new version starts
        raise B.Locked(SIGNING_STARTED)


def _answer(error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=409)


class SignedGuard(APIRoute):
    def get_route_handler(self) -> Callable:
        inner = super().get_route_handler()
        stays_open = self.path_format.endswith(OPEN_WRITES)

        async def handler(request: Request):
            baseline_id = request.scope.get("path_params", {}).get("baseline_id")
            if baseline_id and request.method not in ("GET", "HEAD", "OPTIONS") and not stays_open:
                try:
                    plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
                    refuse_if_signed(plane, baseline_id)
                except B.Locked as e:
                    return _answer("signed", str(e) or B.LOCKED)
                except (B.StoreError, ValueError, OSError):
                    return _answer("unreadable", UNREADABLE)
                except (LookupError, CrossCompanyError, AttributeError):
                    pass  # no company space: the route gives its own answer
            return await inner(request)
        return handler
