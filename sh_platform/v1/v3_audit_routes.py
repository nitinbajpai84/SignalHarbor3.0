"""W7 routes: the audit log (read, filter, verify, CSV) and the office security setting. Company admin only."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from sh_platform.auth import mfa as MFA
from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_audit as A

router = APIRouter()


def _rows(request: Request, q: dict) -> list[dict]:
    rows = A.query(A.read(_plane(request).path("ops", "audit.jsonl")), q.get("actor", ""), q.get("action", ""), q.get("q", ""),
                   q.get("since", ""), q.get("until", ""))
    return rows


@router.get("/api/v3/audit")
def get_audit(request: Request, limit: int = 200):
    f = _plane(request).path("ops", "audit.jsonl")
    rows = _rows(request, dict(request.query_params))
    return {"entries": rows[-max(1, min(limit, 2000)):][::-1], "total": len(rows), "chain": A.verify(f)}


@router.get("/api/v3/audit/export.csv")
def export_audit(request: Request):
    f = _plane(request).path("ops", "audit.jsonl")
    body = A.to_csv(_rows(request, dict(request.query_params)), A.verify(f)["head"])
    return Response(body, media_type="text/csv", headers={"content-disposition": 'attachment; filename="audit-log.csv"'})


@router.get("/api/v3/security/settings")
def get_security(request: Request):
    st = request.app.state
    mine = [a for a in st.account_store._read() if a.get("company_id") == request.state.company_id]
    return {"mfa_required": MFA.office_requires(request.app, request.state.company_id),
            "people": len(mine), "mfa_enrolled": sum(1 for a in mine if (a.get("mfa") or {}).get("enabled"))}


@router.put("/api/v3/security/settings")
async def put_security(request: Request):
    try:
        b = await request.json()
    except ValueError:
        b = None
    if not isinstance(b, dict) or not isinstance(b.get("mfa_required"), bool):
        raise HTTPException(400, "Send mfa_required as true or false.")
    MFA.set_office_requires(_plane(request), b["mfa_required"])
    return get_security(request)
