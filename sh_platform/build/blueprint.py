"""BC-3: the blueprint. `GET /api/company/build/blueprint` returns the current blueprint of the signed-in company, drafting it (deterministically, see
blueprint_draft.py) from the signed baseline when none exists. `PUT` edits one field as stated by the signed-in person; `POST .../sign` records
the signer (company admin) and makes it read-only; an edit after that makes version 2 beside it. Shape: docs/plan/SHAPES.md section 2.

Files in the company plane: build/blueprint.json (the current one) and build/blueprint.v<n>.json (a signed one that a later edit replaced). Module
records are read by path, never imported (as sh_platform/outcomes.py). Who may see a restricted measure is applied on every read: a row for a
measure the person may not see comes back as {"hidden": true}, so the row numbers stay the same for everyone."""
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform import build_env
from sh_platform.build import blueprint_draft as D
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store, view
from sh_platform.profile.api import _name, _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
HEX32 = re.compile(r"[0-9a-f]{32}")
SEVERITY, BAND = ("block", "warn", "inform"), ("now", "next", "later")
MAX_TEXT = 2000
DRAFT_BASIS = "draft baseline"


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _read(path) -> Any:
    try:
        return read_json_strict(path)
    except (OSError, ValueError):
        log.warning("a record needed for the blueprint could not be read")
        return None


def _file(plane):
    return plane.path("build", "blueprint.json")


def _baseline(plane) -> tuple[str, bool] | None:
    """(id, signed) of the newest signed baseline, else of the newest draft baseline that has measures, else None."""
    root, signed, drafts = plane.path("intents", "m2_baseline"), [], []
    for d in root.iterdir() if root.is_dir() else []:
        b = _read(d / "baseline.json")
        if not (HEX32.fullmatch(d.name) and isinstance(b, dict)):
            continue
        if b.get("state") == "signed":
            signed.append((str(b.get("created_at")), d.name))
        elif any(isinstance(k, dict) and "id" in k for k in _read(d / "kpis.json") or []):
            drafts.append((str(b.get("created_at")), d.name))
    return (max(signed)[1], True) if signed else (max(drafts)[1], False) if drafts else None


def _trials(plane) -> dict:
    root = plane.path("intents", "m3_connect", "assessments")
    runs = sorted((a.stat().st_mtime, a) for a in root.iterdir() if (a / "trial.json").is_file()) if root.is_dir() else []
    t = _read(runs[-1][1] / "trial.json") if runs else None  # ponytail: newest assessment with a trial; match on baseline id when there are several
    return t if isinstance(t, dict) else {}


def _drafted(plane) -> dict | None:
    found = _baseline(plane)
    if found is None:
        return None
    bid, signed = found
    folder = plane.path("intents", "m2_baseline", bid)
    kpis, cat = _read(folder / "kpis.json"), _read(folder / "catalogue.json")
    quality = (_read(folder / "quality_rules.json") or {}).get("rules")
    profile = store.raw(plane)
    answers = {q["key"]: q["answer"] for q in build_env.read(plane, profile)["questions"]}
    deadlines = [D.text(c.get("text")) for c in (profile.get("constraints") or {}).values() if D.text(c.get("kind")).lower() == "deadline"]
    doc = D.draft([k for k in kpis if isinstance(k, dict) and "id" in k] if isinstance(kpis, list) else [], cat if isinstance(cat, dict) else {},
                  quality if isinstance(quality, dict) else {}, _trials(plane), answers, deadlines)
    return doc if signed else {**doc, "basis": DRAFT_BASIS}


def _current(plane) -> dict | None:
    """The saved blueprint, drafting and saving one when none exists and a baseline is signed."""
    path = _file(plane)
    with lock_for(path):
        try:
            doc = read_json_strict(path, dict)
        except (OSError, ValueError):
            return None
        # a blueprint drafted from a draft baseline is redrafted once a baseline is signed (ponytail: edits made meanwhile are lost)
        if doc is None or (doc.get("basis") == DRAFT_BASIS and doc["state"] == "draft"):
            new = _drafted(plane)
            if new is not None and (doc is None or "basis" not in new):
                doc = new
                write_json_atomic(path, doc)
        return doc


def _hidden(doc: dict, viewer: view.Viewer) -> set[str]:
    """Measure codes whose mart this person may not see: the mart's list does not name them (the company admin sees all)."""
    if "company_admin" in viewer.roles:
        return set()
    me = view.norm(viewer.name)
    return {a["mart"].split(".", 1)[-1] for a in doc["access"] if a["may_see"] is not None and me not in {view.norm(n) for n in a["may_see"]}}


def _shown(doc: dict, viewer: view.Viewer) -> dict:
    gone = {c for c in _hidden(doc, viewer)}
    low = lambda code: str(code).lower()  # noqa: E731  (marts are named from the lowercase code)
    hide = lambda rows, f: [{"hidden": True} if f(r) else r for r in rows]  # noqa: E731
    out = {**doc, "lineage": hide(doc["lineage"], lambda r: low(r["measure"]) in gone), "rules": hide(doc["rules"], lambda r: low(r["measure"]) in gone),
           "access": hide(doc["access"], lambda r: r["mart"].split(".", 1)[-1] in gone),
           "model": {**doc["model"], "facts": [{**f, "measures": [m for m in f["measures"] if low(m) not in gone]} for f in doc["model"]["facts"]]}}
    return out


def _walk(node: Any, path: str) -> Any:
    for part in path.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _set(node: Any, path: str, value: Any) -> None:
    *head, last = path.split(".")
    parent = _walk(node, ".".join(head)) if head else node
    parent[int(last) if isinstance(parent, list) else last] = value


def _checked(path: str, old: Any, new: Any) -> str | None:
    """A plain-words reason the new value is refused, or None."""
    if isinstance(old, list):
        if not isinstance(new, list) or not all(isinstance(x, str) and 0 < len(x) <= MAX_TEXT for x in new):
            return "This field is a list of lines of text."
    elif isinstance(old, int) and not isinstance(old, bool) or path.endswith(".scd"):
        if new not in (1, 2):
            return "Slowly changing type is 1 or 2."
    elif old is None or isinstance(old, str):
        if new is not None and (not isinstance(new, str) or not new.strip() or len(new) > MAX_TEXT):
            return f"This field is a line of text, up to {MAX_TEXT} characters."
    if path.endswith(".severity") and new not in SEVERITY:
        return "Severity is block, warn or inform."
    if path == "band" and new not in BAND:
        return "The band is now, next or later."
    return None


@router.get("/api/company/build/blueprint")
def get_api_company_build_blueprint(request: Request):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    doc = _current(plane)
    if doc is None:
        return {"state": "none", "message": "There is nothing to draft from yet: no baseline has measures. Add measures to the baseline first."}
    return _shown(doc, viewer)


@router.put("/api/company/build/blueprint")
async def put_api_company_build_blueprint(request: Request):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    try:
        body = await request.json()
    except ValueError:
        return _err(422, "invalid", "Send the edit as JSON: a path and a value.")
    path = body.get("path") if isinstance(body, dict) else None
    if not isinstance(path, str) or "value" not in body:
        return _err(422, "invalid", "Send a path and a value.")
    who = _name(request) or "A team member"
    file = _file(plane)
    with lock_for(file):
        doc = _current(plane)
        if doc is None:
            return _err(404, "no_blueprint", "There is no blueprint yet: the baseline is not signed.")
        if path not in doc["provenance"]:
            return _err(422, "invalid", "That is not a field of the blueprint.")
        try:
            old, seen = _walk(doc, path), _walk(_shown(doc, viewer), path)
        except (KeyError, IndexError, ValueError, TypeError):
            return _err(403, "forbidden", "You may not change that field.")
        if seen != old:
            return _err(403, "forbidden", "You may not change that field.")
        if (why := _checked(path, old, body["value"])) is not None:
            return _err(422, "invalid", why)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if doc["state"] == "signed":  # the signed one stays beside the new version
            write_json_atomic(plane.path("build", f"blueprint.v{doc['version']}.json"), doc)
            doc = {**doc, "version": doc["version"] + 1, "state": "draft", "signed_by": []}
        _set(doc, path, body["value"])
        doc["provenance"][path] = {"mark": "stated", "from": "Edited in the blueprint", "by": who, "at": now}
        write_json_atomic(file, doc)
    return _shown(doc, viewer)


@router.post("/api/company/build/blueprint/sign")
def post_api_company_build_blueprint_sign(request: Request):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    who = _name(request) or "A team member"
    from sh_platform.build import architecture, chain  # 59, C33: with a change note open, the head of department signs through /approve
    if any(n.get("state") == "with_approver" for n in chain.all_notes(plane)):
        return _err(409, "approve_on_change_note", "Approve the design on the change note: the head of department signs the blueprint with it.")
    role = "Head of department" if chain.holds(plane, viewer, ("head_of_department",)) else "Company admin"
    with lock_for(_file(plane)):
        doc = _current(plane)
        if doc is None:
            return _err(404, "no_blueprint", "There is no blueprint yet: the baseline is not signed.")
        if doc.get("basis") == DRAFT_BASIS:
            return _err(409, "baseline_not_signed", "Sign the baseline first. This blueprint is drafted from a draft baseline and cannot be signed yet.")
        if doc["state"] == "signed":
            return _err(409, "already_signed", "This blueprint is already signed. Change a field to start the next version.")
        doc = {**doc, "state": "signed", "signed_by": [{"name": who, "role": role, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}]}
        write_json_atomic(_file(plane), doc)
    from sh_platform.graph.knowledge_map import try_moment
    try_moment(plane, "blueprint_signed", f"v{doc.get('version', '')}", who)
    try:
        architecture.regenerate(plane, "blueprint_signed", f"v{doc['version']}", who, [])
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the architecture record was not regenerated for the blueprint signature", exc_info=True)
    try:  # SF13: Span reviews the model once after each blueprint signature (plan 3.5), beside the request
        from sh_platform.build.agents import routes as span_flow
        span_flow.after_blueprint_signed(request, plane)
    except Exception:  # noqa: BLE001  a review that cannot start never undoes the signature
        log.warning("Span's review after the blueprint signature did not start", exc_info=True)
    return _shown(doc, viewer)
