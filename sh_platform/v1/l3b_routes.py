"""L3b: a read-only viewer for a library file with no project. `GET /api/v1/library/view?file=<plane path>` → {name, lines: [{n, text}]}.
The person must see the library file (same check as the library list: C4 `visible`) and be allowed to read it (K1 `readable`);
anyone else gets the same "not found" sentence, so a private file's existence does not leak."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import doc_index
from sh_platform.v1 import l3_library as F
from sh_platform.v1.seats import viewer_of

router = APIRouter()
MAX_LINES = 3000


@router.get("/api/v1/library/view")
def view(request: Request, file: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    rel = file.replace("\\", "/")
    moved = F.alias(plane.root, rel)
    item = next((i for i in L._index(plane) if i.get("path") in (rel, moved)), None)
    if item is None or not L.visible(item, viewer):
        raise HTTPException(404, L.NOT_FOUND)
    if not L.readable(item, viewer):
        raise HTTPException(403, "You need access to read this file. Ask for access from the library.")
    p = plane.path(*str(item["path"]).split("/"))
    if not p.is_file():  # a sample folder is a folder, not one file
        raise HTTPException(400, "That library item is a folder of files, not one file.")
    try:
        lines, _ = doc_index.read_lines(p.name, p.read_bytes())
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "That file could not be read.") from None
    return {"name": item["name"], "lines": [{"n": i, "text": t} for i, t in enumerate(lines[:MAX_LINES], 1)]}
