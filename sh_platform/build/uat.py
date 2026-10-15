"""R2: the UAT sign-off. The named tester (charter roles.tester) signs a measure or sends it back; with no tester named, the sponsor or a
company admin may. Writes the `uat` key of the measure in build/prove.json (shape 5) with the Prover's current figures; only a re-check resets it."""
import json
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
router = APIRouter()


class Sign(BaseModel):
    state: Literal["signed", "sent_back"]
    note: str = ""


def _role(plane, role: str) -> str | None:
    """roles.<role> saved for the session of the charter record with the latest signed_at (intents/m1_intent/roles/<session id>.json); None when absent."""
    best: tuple[str, dict] | None = None
    for f in sorted(plane.path("intents", "m1_intent", "outcomes").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("kind") == "charter" and d.get("signed_at") and (best is None or str(d["signed_at"]) > best[0]):
            best = (str(d["signed_at"]), d)
    roles = None
    if best:
        try:
            doc = json.loads(plane.path("intents", "m1_intent", "roles", f"{best[1].get('session_id')}.json").read_text(encoding="utf-8"))
            roles = {**(doc.get("roles") or {}), **{k: v for k, v in (doc.get("names") or {}).items() if v}}  # the IC charter keeps ids in roles, names in names
        except (OSError, ValueError, AttributeError):
            pass
    name = roles.get(role) if isinstance(roles, dict) else None
    return str(name).strip() or None if name else None


def _tester(plane) -> str | None:
    return _role(plane, "tester")


@router.post("/api/company/build/uat/{measure}/sign")
def post_api_company_build_uat_measure_sign(request: Request, measure: str, body: Sign):
    try:
        plane = _plane(request)
    except PermissionError:
        raise HTTPException(403, "There is no company space for you.") from None
    viewer, tester = _viewer(request), _tester(plane)
    fallback = tester is None
    if fallback:
        if not ({"sponsor", "company_admin"} & set(viewer.roles)):
            raise HTTPException(403, "No tester is named on the charter, so only the sponsor or a company admin may sign this.")
    elif norm(viewer.name) != norm(tester):
        raise HTTPException(403, f"Only {tester}, the tester named on the charter, may sign this.")
    note = body.note.strip()
    if body.state == "sent_back" and not note:
        raise HTTPException(400, "Say what needs fixing when you send a measure back.")
    path = plane.path("build", "prove.json")
    uat = {"state": body.state, "by": viewer.name, "at": datetime.now(timezone.utc).isoformat(), "note": note}
    with lock_for(path):
        try:
            doc = read_json_strict(path, dict)
        except (OSError, ValueError):
            raise HTTPException(409, "The prove file cannot be read, so nothing was changed.") from None
        from sh_platform.build.prove import settle  # the signature covers the figures the tester saw
        doc = settle(plane, doc or {})
        rows = doc.setdefault("measures", [])
        row = next((m for m in rows if isinstance(m, dict) and m.get("code") == measure), None)
        if row is None:
            rows.append({"code": measure, "uat": uat})
        elif (row.get("uat") or {}).get("state") == "signed":
            raise HTTPException(409, "This measure is already signed off; it opens again only when someone re-checks a changed result.")
        else:
            row["uat"] = uat
        write_json_atomic(path, doc)
    log.info("uat %s: %s", measure, body.state)
    out = {"measure": measure, **uat, "tester": tester}
    if fallback:
        out["message"] = "No tester is named on the charter, so the sponsor or company admin signed this."
    return out
