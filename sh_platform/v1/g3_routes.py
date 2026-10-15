"""G3 The benchmark sheet: GET /api/v1/build/{iid}/benchmarks/sheet reads it (rows, columns, why it cannot be signed, who signs);
POST …/sheet/rows/{rid} types a figure into a row; POST …/sheet/read {file} reads last month's report from a document of the company's files
(X5; the program copies the values and keeps the line; the person must be able to read the file, K1) with {file} or {item_id}; GET …/sheet/doc?file=&line= opens it; POST …/sheet/sign signs it. The sheet as a spreadsheet: the project's artefact export
(`/api/v1/projects/{pid}/artefacts/benchmarks/export?format=xlsx`). Logic: g3_sheet."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.build import runner
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import g3_sheet as G3
from sh_platform.v1.b4_load import IID

router = APIRouter()
BASE = "/api/v1/build/{iid}/benchmarks/sheet"


def _iid(iid: str) -> str:
    if not IID.fullmatch(iid):
        raise HTTPException(404, "There is no such intent.")
    return iid


LOCKED = "That file is locked for you. Ask its owner for access in the library, then try again."


def _item(plane, request: Request, body: dict) -> dict:
    """The library item to read, by id or by file name: it must exist, be visible and readable for this person (K1), else 403/404."""
    from sh_platform.v1 import c4_library as L
    from sh_platform.v1 import x5_extract as X
    from sh_platform.v1.seats import viewer_of
    viewer = viewer_of(request)
    items = L._index(plane)
    if body.get("item_id"):
        item = next((i for i in items if i.get("id") == body["item_id"]), None)
    else:
        try:
            rel = X._doc_path(plane, body.get("file") or body.get("path"))
        except X.Refused:  # a path the library knows (an upload) is not under documents/
            rel = str(body.get("file") or body.get("path") or "").replace("\\", "/")
        from sh_platform.v1 import l3_library as F
        now = F.alias(plane.root, rel)  # a chip made before a move still names the old path
        item = next((i for i in items if i.get("path") in (rel, now)), None)
    if item is None or not L.visible(item, viewer):
        raise HTTPException(404, "That document is not in the company's files.")
    if not L.readable(item, viewer):
        raise HTTPException(403, {"error": "not_allowed", "message": LOCKED})  # the screen shows this sentence
    return item


def _run(fn, *a):
    try:
        return fn(*a)
    except G3.SheetError as e:
        raise HTTPException(e.status, e.message) from None


@router.get(BASE)
def get_sheet(request: Request, iid: str):
    plane, viewer = runner._company(request)
    G1.http_gate(plane, viewer, iid)  # G1
    return _run(G3.view, plane, _iid(iid), viewer.name)


@router.post(BASE + "/rows/{rid}")
def post_row(request: Request, iid: str, rid: str, body: dict = Body(default_factory=dict)):
    plane, viewer = runner._company(request)
    G1.http_gate(plane, viewer, iid, "full")  # G1
    _run(G3.set_figure, plane, _iid(iid), rid, body, viewer.name)
    G3._sync_sow(plane, iid, G3.read(plane, iid))
    return G3.view(plane, iid, viewer.name)


@router.post(BASE + "/read")
def post_read(request: Request, iid: str, body: dict = Body(default_factory=dict)):
    plane, viewer = runner._company(request)
    G1.http_gate(plane, viewer, iid, "full")  # G1
    rows = _run(G3.from_document, plane, _iid(iid), _item(plane, request, body)["path"], viewer.name)
    return {**G3.view(plane, iid, viewer.name), "read": len(rows)}


@router.get(BASE + "/doc")
def get_doc(request: Request, iid: str, file: str, line: int = 0):
    """The document a sheet row was read from, as numbered lines (the row's `line` is the 1-based number): only for whoever may read it."""
    from sh_platform.v1 import x5_extract as X
    plane, viewer = runner._company(request)
    G1.http_gate(plane, viewer, iid)  # G1
    _iid(iid)  # the intent must be a real id; the file is one of the library items this person may read (K1), which includes every sheet source
    item = _item(plane, request, {"path": file})
    try:
        lines = X._lines(plane, item["path"])
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "That file could not be read.") from None
    return {"name": item["name"], "line": line, "lines": [{"n": i, "text": t} for i, t in enumerate(lines[:3000], 1)]}


@router.post(BASE + "/sign")
def post_sign(request: Request, iid: str):
    plane, viewer = runner._company(request)
    G1.http_gate(plane, viewer, iid, "full")  # G1
    _run(G3.sign, plane, _iid(iid), viewer.name)
    return G3.view(plane, iid, viewer.name)
