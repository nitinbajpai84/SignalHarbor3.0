"""W2 pain-point demo: a YAML list of pain points, each with how Signal Harbor covers it and a Show me link.

Source: local/painpoints/<name>.yaml (gitignored, may name a real prospect's pain) else packs/family_office/1/painpoints_sample.yaml (synthetic).
`GET /api/v1/demo/painpoints[?name=x]` -> {source, clusters: [{cluster, items}], counts}. Read only; no model, no egress."""
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.v1.seats import viewer_of

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "packs" / "family_office" / "1" / "painpoints_sample.yaml"
COVERAGE = ("strong", "partial", "not_in_scope")
SEVERITY = ("high", "medium", "low")
_NAME = re.compile(r"[a-z0-9_-]{1,40}")
router = APIRouter()


def _item(raw, n: int) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"item {n} is not a mapping")
    out = {k: str(raw.get(k) or "").strip() for k in ("id", "cluster", "title", "does", "use_case", "link", "reason")}
    out["severity"], out["coverage"] = str(raw.get("severity") or "").strip(), str(raw.get("coverage") or "").strip()
    for k in ("id", "cluster", "title", "does"):
        if not out[k]:
            raise ValueError(f"item {n} has no {k}")
    if out["severity"] not in SEVERITY or out["coverage"] not in COVERAGE:
        raise ValueError(f"item {out['id']}: severity is high, medium or low; coverage is strong, partial or not_in_scope")
    if out["coverage"] == "not_in_scope" and not out["reason"]:
        raise ValueError(f"item {out['id']}: not_in_scope needs an honest reason")
    if out["link"] and not (out["link"].startswith("/") and not out["link"].startswith("//") and "\\" not in out["link"]):
        raise ValueError(f"item {out['id']}: link must be an app path starting with a single /")  # no off-site links
    if out["coverage"] == "not_in_scope":
        out["link"] = ""
    return out


def load(name: str = "", root: Path = ROOT) -> dict:
    """The grouped list. An unknown or missing `name` falls back to the sample; a malformed file raises ValueError."""
    src, path = "sample", root / "packs" / "family_office" / "1" / "painpoints_sample.yaml"
    if name:
        if not _NAME.fullmatch(name):
            raise ValueError("name may use lowercase letters, digits, - and _")
        mine = root / "local" / "painpoints" / f"{name}.yaml"
        if mine.is_file():
            src, path = "local", mine
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("painpoints") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise ValueError("the file needs a non-empty painpoints list")
    items = [_item(r, i + 1) for i, r in enumerate(raw)]
    if len({i["id"] for i in items}) != len(items):
        raise ValueError("pain point ids must be unique")
    groups: dict[str, list] = {}
    for i in items:
        groups.setdefault(i["cluster"], []).append(i)  # dicts keep file order
    counts = {c: sum(1 for i in items if i["coverage"] == c) for c in COVERAGE}
    return {"source": src, "total": len(items), "counts": counts, "clusters": [{"cluster": c, "items": v} for c, v in groups.items()]}


@router.get("/api/v1/demo/painpoints")
def painpoints(request: Request, name: str = ""):
    viewer_of(request)
    try:
        return load(name)
    except (ValueError, yaml.YAMLError) as e:
        return JSONResponse({"error": "bad_request", "message": f"The pain-point list could not be read: {e}"}, status_code=400)
