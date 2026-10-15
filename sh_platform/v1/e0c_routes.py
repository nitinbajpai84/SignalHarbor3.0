"""E0c1 routes: the data intake census.

- `GET /api/v1/intake/files` → {files, by_source, states, inbox_note}  (scans the inbox first)
- `POST /api/v1/intake/scan` → {registered: [file]}
- `POST /api/v1/intake/upload` multipart (field `file`, optional `source_code`, `sensitivity`) → the record + `duplicate`
- `GET /api/v1/intake/files/{file_id}` → record with profile and last load result
- `POST /api/v1/intake/files/{file_id}/profile` {sheet?} → record  ·  `POST /api/v1/intake/files/{file_id}/load` → record
The multipart body is read with the standard library (no multipart package is installed)."""
from email import policy
from email.parser import BytesParser

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1.i2_routes import _json_body, _model, _plain
from sh_platform.v1.seats import DATA_ENGINEER, require_seat, viewer_of

router = APIRouter()
BASE = "/api/v1/intake"
TOO_BIG = L.MAX_BYTES + 64 * 1024
MONTH_BYTES = 8 * L.MAX_BYTES


def _answer(fn):
    try:
        return fn()
    except L.Refused as e:
        return _plain(e.status, {403: "not_allowed", 404: "not_found", 413: "too_big", 503: "not_ready"}.get(e.status, "invalid"), e.message)
    except PermissionError:
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


def _worker(request: Request):
    return require_seat(request, DATA_ENGINEER)  # the ops manager seat has the same roles


def _plane_started(request: Request):
    plane = _plane(request)
    L.ensure_poll(plane)
    return plane


async def _multipart(request: Request, cap: int = TOO_BIG) -> dict | JSONResponse:
    ctype = request.headers.get("content-type", "")
    if not ctype.lower().startswith("multipart/form-data"):
        return _plain(400, "bad_request", "Please send the file as a form upload.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cap:
        return _plain(413, "too_big", f"That file is too large. The limit is {L.MAX_BYTES // 1_000_000} MB.")
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > cap:
            return _plain(413, "too_big", f"That file is too large. The limit is {L.MAX_BYTES // 1_000_000} MB.")
    boundary = BytesParser(policy=policy.default).parsebytes(b"Content-Type: " + ctype.encode("latin-1") + b"\r\n\r\n", headersonly=True).get_boundary()
    out: dict = {}
    # Each part's bytes are cut at the boundary, never decoded by the email parser: a part sent as message/rfc822 (an .eml file) has no
    # decodable payload there and arrived as an empty file (cycle 2, cio and fund_accountant).
    for seg in bytes(raw).split(b"--" + boundary.encode("latin-1"))[1:] if boundary else []:
        head, sep, body = seg.removeprefix(b"\r\n").partition(b"\r\n\r\n")
        if not sep:
            continue  # the closing "--"
        part = BytesParser(policy=policy.default).parsebytes(head + b"\r\n\r\n", headersonly=True)
        name, body = part.get_param("name", header="content-disposition"), body.removesuffix(b"\r\n")
        if not name:
            continue
        if part.get_filename():
            out["filename"], out["data"] = part.get_filename(), body
            out.setdefault("files", []).append((out["filename"], out["data"]))
        else:
            out[name] = body.decode("utf-8", errors="replace")
    return out


@router.get(f"{BASE}/files")
def files(request: Request):
    viewer_of(request)
    plane = _plane_started(request)
    return _answer(lambda: (L.scan_inbox(plane), L.listing(plane))[1])


@router.post(f"{BASE}/scan")
def scan(request: Request):
    _worker(request)
    plane = _plane_started(request)
    return _answer(lambda: {"registered": [{k: v for k, v in r.items() if k != "profile"} for r in L.scan_inbox(plane)]})


@router.post(f"{BASE}/upload")
async def upload(request: Request):
    viewer = _worker(request)
    plane = _plane_started(request)
    form = await _multipart(request)
    if isinstance(form, JSONResponse):
        return form
    if "data" not in form:
        return _plain(400, "bad_request", "Please choose a file to upload.")
    return _answer(lambda: L.receive(plane, form["data"], form["filename"], viewer.name,
                                     source_code=form.get("source_code") or "upload", sensitivity=form.get("sensitivity") or "internal",
                                     received_on=form.get("received_on")))


@router.post(f"{BASE}/month")
async def month(request: Request):
    """Several files at once (a month of daily CSVs, the administrator workbook, bank files): trade files go through trade_intake.load_folder,
    every other file through the normal per-file path. Returns {files: {name: {file_id, state, message}}}."""
    viewer = _worker(request)
    plane = _plane_started(request)
    form = await _multipart(request, MONTH_BYTES)
    if isinstance(form, JSONResponse):
        return form
    if not form.get("files"):
        return _plain(400, "bad_request", "Please choose the files for the month.")
    return _answer(lambda: L.load_month(plane, form["files"], viewer, _model(request, plane), form.get("mode") or "replace"))


@router.get(BASE + "/files/{file_id}")
def one_file(file_id: str, request: Request):
    viewer = viewer_of(request)
    plane = _plane(request)
    return _answer(lambda: L.detail(plane, file_id, viewer))


@router.post(BASE + "/files/{file_id}/profile")
async def profile(file_id: str, request: Request):
    _worker(request)
    plane = _plane(request)
    body = await _json_body(request, 4096) if request.headers.get("content-length", "0") != "0" else {}
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: L.profile(plane, file_id, body.get("sheet")))


@router.post(BASE + "/files/{file_id}/load")
async def load(file_id: str, request: Request):
    """{sheet?}: load that sheet of the workbook (default: the first)."""
    viewer = _worker(request)
    plane = _plane(request)
    body = await _json_body(request, 4096) if request.headers.get("content-length", "0") != "0" else {}
    if isinstance(body, JSONResponse):
        return body
    sheet = body.get("sheet") if isinstance(body.get("sheet"), str) and body.get("sheet").strip() else None
    return await run_in_threadpool(_answer, lambda: L.load(plane, file_id, viewer, _model(request, plane), sheet))
