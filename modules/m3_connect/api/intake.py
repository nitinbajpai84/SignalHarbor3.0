"""M3-P02 routes: the data request to each source owner, the upload link (no account), uploads, profiles and benchmarks.

The customer's actions 1 and 2 (give source data, give benchmark data) are here; everything else is automatic. The two /intake/link routes are
guest `entry` routes copied from module 2's answer link (modules/m2_baseline/api/requests.py): the token is "di-<request id>-<secret>", read from
the X-Session-Token header only, never a URL, query or body. Defences in order: the failure lock, the token's shape, the control index, that the
company still owns the module, then the hash; every failure before the hash matches gives the same answer.
Company and person come from the server session, never from a body. There is no email service: the organiser gets the link once, with Nira's text.
Rows and figures stay in the plane; nothing here calls the model.
"""
import base64
import binascii
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from modules.m3_connect.api.assessment import NO_SPACE, NOT_FOUND, _plane, _viewer, plain
from modules.m3_connect.api.signed_guard import SIGNED, UNREADABLE, is_signed
from modules.m3_connect.domain import counters as K
from modules.m3_connect.domain import from_profile as FP
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import intake as N
from modules.m3_connect.domain import intake_store as S
from modules.m3_connect.domain import quality_rules as QR
from modules.m3_connect.domain import sources as P1
from modules.m3_connect.domain import tabular as T
from modules.m3_connect.domain.plan import PlanError
from modules.m3_connect.store import assessment as A
from sh_platform.auth.sessions import LoginThrottle
from sh_platform.context_docs.reader import Refusal
from sh_platform import profile
from sh_platform.jsonfile import lock_for, read_json_strict
from sh_platform.modulegate import may_use_module
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.public_link import full_url

log = logging.getLogger(__name__)
router = APIRouter()
MODULE = "m3_connect"
HEADER = "x-session-token"
BODY_MAX = 64 * 1024
UPLOAD_MAX = T.MAX_FILE_BYTES * 4 // 3 + 64 * 1024   # base64 grows a file by a third
BAD_BODY = "Those details could not be read. Please try again."
_INVALID = ("link_invalid", "This link is not working. Please ask for a new one.")
_LOCKED = ("too_many_tries", "Too many tries. Please wait a minute, then open your link again.")
GUEST = I.Viewer("", frozenset())  # a person on a link: only what no list limits
AUTO = "_auto"  # in place of a source id: Lens files the upload to the source it belongs to


class _Locked(Exception):
    pass


def _run(fn):
    """Runs fn and turns the module's failures into plain answers; nothing technical reaches the screen."""
    try:
        return fn()
    except _Locked:
        return plain(429, *_LOCKED)
    except S.LinkError as e:
        return plain(404 if e.code == "link_invalid" else 409, e.code, e.message)
    except S.WrongState as e:
        return plain(409, "wrong_state", str(e))
    except Refusal as e:
        return plain(e.status, "refused", str(e))
    except LookupError as e:
        return plain(404, "not_found", str(e) if str(e) == N.NO_MEASURE else NOT_FOUND)
    except (S.StoreError, A.StoreError, I.InputsUnreadable) as e:
        return plain(500, "unreadable", str(e))
    except (PermissionError, CrossCompanyError):
        return plain(403, "forbidden", NO_SPACE)


async def _body(request: Request, limit: int = BODY_MAX) -> dict | None:
    """The JSON object in the body, or None. Counted as it arrives: a missing or false Content-Length does not help."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return None
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks))
    except (ValueError, RecursionError):
        return None
    return body if isinstance(body, dict) else None


def _clock(request: Request):
    return getattr(request.app.state, "m3_clock", time.time)


SHUT_UPLOAD = "This source holds a restricted sample that you may not see, so you cannot replace it. Ask a person who may see it."


def _file(body: dict | None) -> tuple[str, bytes]:
    if body is None or not isinstance(body.get("filename"), str):
        raise Refusal("Please choose a file to send.", 400)
    try:
        return body["filename"], base64.b64decode(str(body.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        raise Refusal("That file could not be read. Please try again.", 400) from None


def _synonyms(request: Request, company_id: str) -> dict:
    """The industry pack's column spellings (a suggestion source only). A company with no pack gets none."""
    company = request.app.state.entitlements.company(company_id) or {}
    try:
        pack = request.app.state.packs.load(str(company.get("industry", "")))
        raw = pack.section("column_synonyms") if "column_synonyms" in pack.sections() else None
    except (ValueError, KeyError, OSError):
        return {}
    inner = raw.get("feeds") if isinstance(raw, dict) else None
    return inner if isinstance(inner, dict) else {}


class Ctx:
    """One assessment of one company, with its folder, requests and the catalogue as the full (organiser) view."""

    def __init__(self, plane, company_id: str, assessment_id: str, clock):
        self.plane, self.company_id, self.aid = plane, company_id, assessment_id
        a = A.read_assessment(plane, assessment_id)
        if a is None:
            raise LookupError("no assessment")
        self.a, self.folder = a, A.folder(plane, assessment_id)
        self.baseline = I.read_baseline_outcome(plane, a["baseline_outcome_id"])
        if self.baseline is None:
            raise LookupError("no baseline")
        self.requests, self.clock = S.Requests(self.folder, clock), clock
        self.pv, self._served = profile.Viewer("", frozenset()), None  # who is reading, for the profile's lists (closed until `_org` sets it)

    def served(self) -> dict[str, dict]:
        """The adopted samples as this reader may see them (`FP.served`); read once per request, again after anything changes."""
        if self._served is None:
            self._served = FP.served(self.folder, self.plane, self.pv)
        return self._served

    def inputs(self, viewer: I.Viewer) -> dict:
        return I.read_inputs(self.plane, self.baseline, self.a["charter_outcome_id"], viewer)

    def plans(self, viewer: I.Viewer) -> list[dict]:
        """What this reader may ask for: module 2's source and field rules are applied by `inputs` (domain/inputs.py), so a source or column
        the reader may not see is never in the plan."""
        try:
            sources = read_json_strict(self.folder / "sources.json")  # P01's file; not there yet is fine
        except (OSError, ValueError):
            raise S.StoreError(S.UNREADABLE) from None
        from sh_platform.intents.sources import intake_owners  # the kernel's one door to module 2's source owners (ruling R9)
        try:
            owners = intake_owners(self.plane, str(self.baseline.get("baseline_id")))
        except (S.StoreError, OSError, ValueError, KeyError):
            owners = {}  # no extras file or catalogue yet: the catalogue's Data owner column answers
        return N.source_plan(self.inputs(viewer), sources, owners)

    def period(self) -> dict:
        return N.latest_full_month(S.now_iso(self.clock).date())

    def adopt(self, request: Request, viewer: I.Viewer) -> list[dict]:
        """LI-M3: takes the profile's samples as intake and its reported figures as benchmarks. What is kept is only what a reader on no restricted
        list sees (`profile.read_unrestricted`, the guest's plans, the head of data's measures), so it is the same whoever opens the screen first and
        the shared files never hold a restricted item; those stay for the people who can see them to place by hand. Under the assessment's lock and
        a no-op when nothing is new. Returns the samples `viewer` may see that are still to place."""
        pv = self.pv = _pv(request, viewer)
        syn = _synonyms(request, self.company_id)
        try:
            signed = is_signed(self.plane, self.aid)  # a signed assessment is never written to, not even by opening a screen
        except (PlanError, A.StoreError, ValueError, OSError):
            signed = True
        if signed:
            return []
        with lock_for(self.folder):
            FP.adopt_samples(self.folder, self.plans(GUEST), FP.samples(self.plane, None), syn, self.period(), self.clock)
            for sid in FP.adopted(self.folder):
                r = self.requests.for_source(sid)
                if r is not None and r["state"] != "arrived":
                    self.requests.arrived(sid, {"account_id": None, "name": FP.PROFILE_BY})
            FP.adopt_figures(self.folder, FP.figures(self.plane, None), self.inputs(N.ADMIN)["measures"], self.period(), self.clock)
        self._served = None
        return FP.to_confirm(self.folder, self.plans(viewer), FP.samples(self.plane, pv), syn)

    def seen(self, viewer: I.Viewer) -> dict:
        i = self.inputs(viewer)
        return {"fields": {I._t(f.get("Field ID")) for f in i["fields"]}, "sources": {I._t(s.get("Source ID")) for s in i["sources"]},
                "measures": {m["id"] for m in i["measures"] if not m.get("restricted")}, "all": i["measures"]}

    def refuse_if_shut(self, source_id: str) -> None:
        """A source whose rows came from a restricted sample this reader may not see cannot be overwritten by them (the mark would then describe rows
        that are not the sample's). The people who may see the sample can replace it."""
        if source_id in FP.shut_sources(self.folder, self.plane, self.pv):
            raise Refusal(SHUT_UPLOAD, 409)

    def limits(self, source_id: str) -> dict:
        r = self.requests.for_source(source_id)
        return {c["field_id"]: c.get("limit") for t in (r or {"tables": []})["tables"] for c in t["columns"]}

    def profile_for(self, source_id: str, seen: dict, viewer: I.Viewer) -> dict | None:
        if (self.served().get(source_id) or {}).get("shut"):  # a restricted sample's rows are for the people who may see that sample
            return None
        p = S.read_profile(self.folder, source_id)
        return S.redact(p, seen["fields"], self.limits(source_id), viewer) if p else None

    def row_view(self, req: dict, seen: dict, viewer: I.Viewer) -> dict:
        v = N.view(req, self.requests.now(), seen["fields"], viewer, seen["measures"])
        return {**v, "profile": self.profile_for(req["source_id"], seen, viewer)}


def _pv(request: Request, viewer: I.Viewer) -> profile.Viewer:
    return profile.Viewer(viewer.name, viewer.roles, viewer.shared_name, str(request.state.account_id))


def _org(request: Request, assessment_id: str) -> tuple[Ctx, I.Viewer]:
    ctx, viewer = Ctx(_plane(request), request.state.company_id, assessment_id, _clock(request)), _viewer(request)
    ctx.pv = _pv(request, viewer)
    return ctx, viewer


def _link_path(request: Request, token: str) -> str:
    return full_url(request, f"/intake/{token}")


def _outgoing(request: Request, ctx: Ctx, req: dict, viewer: I.Viewer, token: str | None, remind: bool = False) -> dict:
    seen = ctx.seen(viewer)
    v = ctx.row_view(req, seen, viewer)
    organiser = viewer.name or "Your organiser"
    out = {"request": v}
    if remind:
        out["email"] = N.reminder_text(v, organiser)
    elif token:
        out.update(link_path=f"/intake/{token}", email=N.email_text(v, organiser, _link_path(request, token)))
    return out


# ---- the organiser: the request ----------------------------------------------------------------------------------------------------

@router.get("/assessments/{assessment_id}/intake/requests")
async def list_requests(request: Request, assessment_id: str):
    def work():
        ctx, viewer = _org(request, assessment_id)
        ask = ctx.adopt(request, viewer)
        seen = ctx.seen(viewer)
        used = ctx.served()
        names = {p["source_id"]: p["source_name"] for p in ctx.plans(viewer)}
        idle = P1.unneeded(ctx.inputs(viewer))  # feed no measure that is left in: not asked, listed apart
        rows = [ctx.row_view(r, seen, viewer) for r in ctx.requests.all() if r["source_id"] in seen["sources"] and r["source_id"] not in {u["id"] for u in idle}]
        asked = {r["source_id"] for r in rows}
        reused = [{"source_id": sid, "source_name": names.get(sid, sid), "from": FP.A_RESTRICTED_SAMPLE, "files": [], "profile": None} if v["shut"] else
                  {"source_id": sid, "source_name": names.get(sid, sid), "from": "; ".join(dict.fromkeys(f["label"] for f in v["files"] if f["label"])),
                   "files": [f["file"] for f in v["files"]], "profile": ctx.profile_for(sid, seen, viewer)}
                  for sid, v in used.items() if sid in seen["sources"] and sid in names]
        terms = I.hidden_terms(ctx.inputs(N.ADMIN), ctx.inputs(viewer))  # a file or label that names what this reader may not see is not listed
        reused = [r for r in reused if not any(I._mentions(x, terms) for x in [r["from"], *r["files"]])]
        return {"requests": rows, "from_profile": reused, "to_confirm": ask, "period": ctx.period(),
                "not_needed": [{"source_id": u["id"], "source_name": u["name"]} for u in idle if u["id"] in seen["sources"]],
                "not_yet_asked": [{"source_id": p["source_id"], "source_name": p["source_name"]} for p in ctx.plans(viewer)
                                  if p["source_id"] in seen["sources"] and p["source_id"] not in asked and p["source_id"] not in used],
                "summary": {"asked": len(rows), "arrived": sum(r["state"] == "arrived" for r in rows)}}
    return await run_in_threadpool(_run, work)


@router.post("/assessments/{assessment_id}/intake/requests")
async def create_requests(request: Request, assessment_id: str):
    """What to ask each source in zones p1 and p2 for, from the signed catalogue. A new request's link is returned here, once."""
    def work():
        ctx, viewer = _org(request, assessment_id)
        ctx.adopt(request, viewer)
        used = FP.adopted(ctx.folder)  # a source whose sample the profile holds is not asked for it again (whoever may see that sample)
        made = ctx.requests.sync([p for p in ctx.plans(viewer) if p["source_id"] not in used], ctx.period(), S.Index(request.app.state.settings.data_root), request.state.company_id, assessment_id)
        seen = ctx.seen(viewer)
        sent = [{**_outgoing(request, ctx, r, viewer, tok), "source_id": r["source_id"]} for r, tok in made if r["source_id"] in seen["sources"]]
        return {"sent": sent, "new": sum(1 for s in sent if s.get("link_path"))}
    return await run_in_threadpool(_run, work)


def _one(request: Request, assessment_id: str, request_id: str, fn):
    ctx, viewer = _org(request, assessment_id)
    seen = ctx.seen(viewer)
    row = ctx.requests.get(request_id)
    if row["source_id"] not in seen["sources"]:
        raise LookupError("no request")
    return fn(ctx, viewer, row)


@router.post("/assessments/{assessment_id}/intake/requests/{request_id}/remind")
async def remind(request: Request, assessment_id: str, request_id: str):
    return await run_in_threadpool(_run, lambda: _one(request, assessment_id, request_id,
                                   lambda c, v, r: _outgoing(request, c, c.requests.remind(r["id"]), v, None, remind=True)))


@router.post("/assessments/{assessment_id}/intake/requests/{request_id}/revoke")
async def revoke(request: Request, assessment_id: str, request_id: str):
    """Withdraws the link. A body {"will_not_send": true} also marks the request "will not send"; neither blocks the Data request step."""
    body = await _body(request)
    wont = bool((body or {}).get("will_not_send"))

    def go(c: Ctx, v: I.Viewer, r: dict):
        organiser = "company_admin" in v.roles or (v.name and I._norm(v.name) == I._norm(c.a.get("created_by")) and not v.shared_name)
        if wont and not organiser:
            return plain(403, "forbidden", "Only the organiser of this assessment can say a source owner will not send.")
        who = {"account_id": str(request.state.account_id), "name": v.name}
        return {"request": c.row_view(c.requests.revoke(r["id"], wont, who), c.seen(v), v)}
    return await run_in_threadpool(_run, lambda: _one(request, assessment_id, request_id, go))


@router.post("/assessments/{assessment_id}/intake/requests/{request_id}/relink")
async def relink(request: Request, assessment_id: str, request_id: str):
    def go(c: Ctx, v: I.Viewer, r: dict):
        row, token = c.requests.relink(r["id"], S.Index(request.app.state.settings.data_root), request.state.company_id, assessment_id)
        return _outgoing(request, c, row, v, token)
    return await run_in_threadpool(_run, lambda: _one(request, assessment_id, request_id, go))


# ---- the organiser: upload and profile --------------------------------------------------------------------------------------------

def _record_rules(ctx: Ctx, source_id: str, scanned: dict) -> None:
    """IC-0d: the scan's quality facts become proposed rules on the measures this source feeds (never for a signed assessment; the upload itself
    already passed the reader's source and field rules). A failure here never loses the upload."""
    try:
        if is_signed(ctx.plane, ctx.aid):
            return
        with lock_for(ctx.folder):
            QR.record_scan(ctx.plane, ctx.baseline, source_id, scanned, S.now_iso(ctx.clock).isoformat())
    except (PlanError, A.StoreError, ValueError, OSError, KeyError):
        log.warning("quality rules were not recorded for an upload")


def _take(ctx: Ctx, request: Request, source_id: str, filename: str, data: bytes, by: str, viewer: I.Viewer | None = None) -> dict:
    """An organiser (`viewer`) uploads against what they may see; an owner's link uploads against the request that was made for their source."""
    req = ctx.requests.for_source(source_id)
    plan = next((p for p in ctx.plans(viewer) if p["source_id"] == source_id), None) if viewer else (N.plan_of(req) if req else None)
    if plan is None:
        raise LookupError("no source")
    ctx.refuse_if_shut(source_id)
    profile = S.ingest(ctx.folder, plan, filename, data, by, (req or {}).get("period") or ctx.period(), _synonyms(request, ctx.company_id), ctx.clock)
    _record_rules(ctx, source_id, profile)
    FP.forget_closed(ctx.folder, ctx.plane, source_id)  # an upload by someone who may see the restricted sample replaces it: its mark goes
    ctx._served = None
    ctx.requests.arrived(source_id, {"account_id": str(request.state.account_id), "name": viewer.name} if viewer else {"account_id": None, "name": by})
    return profile


@router.post("/assessments/{assessment_id}/intake/sources/{source_id}/upload")
async def upload(request: Request, assessment_id: str, source_id: str):
    """A file for a source. With `_auto` in place of the source, Lens files it by its columns and name and asks only when it is not certain
    (`needs_confirm`: nothing is kept until the organiser chooses). `profile_sample` (a key from `to_confirm`) places a profile sample the same way."""
    body = await _body(request, UPLOAD_MAX)

    def work():
        ctx, viewer = _org(request, assessment_id)
        seen = ctx.seen(viewer)
        key = (body or {}).get("profile_sample")
        if source_id == AUTO and not key:
            name, data = _file(body)
            plans = [p for p in ctx.plans(viewer) if p["source_id"] in seen["sources"]]
            m = FP.file_source(plans, name, T.read_table(name, data)[0], _synonyms(request, ctx.company_id))
            if not m["certain"]:
                return {"filed": None, "needs_confirm": {"file": name, "candidates": m["candidates"]}}
            sid, filed = m["source_id"], {"source_id": m["source_id"], "source_name": m["source_name"]}
        else:
            sid, filed = (str((body or {}).get("source_id") or "") if source_id == AUTO else source_id), None
            if sid not in seen["sources"]:
                raise LookupError("no source")
        if key:  # a profile sample the organiser placed by hand
            sample = next((x for x in FP.samples(ctx.plane, ctx.pv) if x["key"] == key), None)
            plan = next((p for p in ctx.plans(viewer) if p["source_id"] == sid), None)
            if sample is None or plan is None:
                raise LookupError("no source")
            ctx.refuse_if_shut(sid)
            shared = key in FP.sample_names(ctx.plane, None)  # not open to everyone: the mark keeps the key only
            FP.take_sample(ctx.folder, plan, sample, ctx.period(), _synonyms(request, ctx.company_id), ctx.clock, shared)
            ctx._served = None
            ctx.requests.arrived(sid, {"account_id": str(request.state.account_id), "name": viewer.name})
        else:
            name, data = _file(body)
            _take(ctx, request, sid, name, data, viewer.name, viewer)
        K.bump(ctx.folder, "confirm_source" if key else "upload_source")
        return {"profile": ctx.profile_for(sid, ctx.seen(viewer), viewer), **({"filed": filed} if filed else {})}
    return await run_in_threadpool(_run, work)


@router.get("/assessments/{assessment_id}/intake/sources/{source_id}/profile")
async def get_profile(request: Request, assessment_id: str, source_id: str):
    def work():
        ctx, viewer = _org(request, assessment_id)
        seen = ctx.seen(viewer)
        if source_id not in seen["sources"]:
            raise LookupError("no source")
        try:
            rules = QR.visible(QR.read(ctx.plane, ctx.baseline["baseline_id"]), ctx.inputs(viewer))
        except (ValueError, OSError):
            rules = {}
        mine = {m: here for m, rs in rules.items() if (here := [r for r in rs if r["source_id"] in (None, source_id)])}
        return {"profile": ctx.profile_for(source_id, seen, viewer), **({"quality_rules": mine} if mine else {})}
    return await run_in_threadpool(_run, work)


# ---- benchmarks -----------------------------------------------------------------------------------------------------------------------

def _bench_view(ctx: Ctx, viewer: I.Viewer, request: Request | None = None) -> dict:
    if request is not None:  # the profile's reported figures are the benchmarks; nothing needs uploading
        ctx.adopt(request, viewer)
    seen = ctx.seen(viewer)
    names = {m["id"]: m["name"] for m in seen["all"]}
    doc = S.read_benchmarks(ctx.folder)
    rows = [{"measure_id": mid, "measure_name": names.get(mid, I.RESTRICTED_NAME), "restricted": mid not in seen["measures"],
             **({} if mid not in seen["measures"] else {k: v for k, v in rec.items()})} for mid, rec in doc["measures"].items()]
    return {"file": doc["file"], "measures": rows, "unmatched": doc["unmatched"],
            "choices": [{"id": m["id"], "name": m["name"]} for m in seen["all"] if m["id"] in seen["measures"]],
            "waiting_for": [{"id": m["id"], "name": m["name"]} for m in seen["all"] if m["id"] in seen["measures"] and m["id"] not in doc["measures"]]}


@router.get("/assessments/{assessment_id}/intake/benchmarks")
async def get_benchmarks(request: Request, assessment_id: str):
    def work():
        ctx, viewer = _org(request, assessment_id)
        return _bench_view(ctx, viewer, request)
    return await run_in_threadpool(_run, work)


@router.post("/assessments/{assessment_id}/intake/benchmarks/upload")
async def upload_benchmarks(request: Request, assessment_id: str):
    body = await _body(request, UPLOAD_MAX)

    def work():
        ctx, viewer = _org(request, assessment_id)
        name, data = _file(body)
        S.save_benchmarks(ctx.folder, name, data, ctx.inputs(N.ADMIN)["measures"], viewer.name, ctx.clock)
        K.bump(ctx.folder, "upload_benchmarks")
        return _bench_view(ctx, viewer)
    return await run_in_threadpool(_run, work)


@router.post("/assessments/{assessment_id}/intake/benchmarks/map")
async def map_benchmark(request: Request, assessment_id: str):
    """A person says which measure an unmatched line is. Lens never does this for them."""
    body = await _body(request)

    def work():
        ctx, viewer = _org(request, assessment_id)
        if body is None or not isinstance(body.get("index"), int) or not isinstance(body.get("measure_id"), str):
            return plain(400, "bad_request", BAD_BODY)
        seen = ctx.seen(viewer)
        S.map_benchmark(ctx.folder, body["index"], body["measure_id"], [m for m in seen["all"] if m["id"] in seen["measures"]], viewer.name, ctx.clock)
        K.bump(ctx.folder, "map_benchmark")
        return _bench_view(ctx, viewer)
    return await run_in_threadpool(_run, work)


# ---- the upload link (no account) -----------------------------------------------------------------------------------------------------

def _throttle(app) -> LoginThrottle:
    if getattr(app.state, "intake_throttle", None) is None:
        app.state.intake_throttle = LoginThrottle()
    return app.state.intake_throttle


def _ground(request: Request) -> tuple[Ctx, dict]:
    """(context, request row) for a header token that is good right now. Every failure counts against the caller and gives one answer."""
    throttle, key = _throttle(request.app), request.client.host if request.client else "unknown"
    if throttle.locked(key):
        raise _Locked()
    try:
        token = request.headers.get(HEADER, "")
        m = N.TOKEN.fullmatch(token)
        if not m:
            raise S.LinkError(*_INVALID)
        root = request.app.state.settings.data_root
        entry = S.Index(root).lookup(m.group(1))
        if entry is None or not may_use_module(request.app.state.entitlements, entry["company_id"], MODULE):
            raise S.LinkError(*_INVALID)
        ctx = Ctx(PlaneStore(root).plane_for(entry["company_id"]).ensure(), entry["company_id"], entry["assessment_id"], _clock(request))
        return ctx, ctx.requests.ground(m.group(1), token)
    except S.LinkError:
        throttle.failed(key)
        raise
    except (S.StoreError, A.StoreError, I.InputsUnreadable, LookupError, CrossCompanyError, ValueError, OSError):
        throttle.failed(key)
        raise S.LinkError(*_INVALID) from None


@router.post("/intake/link/form")
async def link_form(request: Request):
    """What this source owner is asked for, and what has come so far. Shows only what no list limits."""
    def work():
        ctx, row = _ground(request)
        row = ctx.requests.opened(row["id"])
        seen = ctx.seen(GUEST)
        if row["source_id"] not in seen["sources"]:
            raise S.LinkError(*_INVALID)
        return ctx.row_view(row, seen, GUEST)
    return await run_in_threadpool(_run, work)


def _refuse_signed(c: Ctx) -> JSONResponse | None:
    """409 in plain words when the link's assessment is signed (or its state cannot be read: fail closed), else None."""
    try:
        return plain(409, "signed", SIGNED) if is_signed(c.plane, c.aid) else None
    except (PlanError, A.StoreError, ValueError, OSError):
        return plain(409, "unreadable", UNREADABLE)


@router.post("/intake/link/upload")
async def link_upload(request: Request):
    """The owner sends a file for their source, or a benchmark file (`kind`: "source" or "benchmark"). Checked before any body is read."""
    ctx = await run_in_threadpool(_run, lambda: _ground(request))
    if isinstance(ctx, JSONResponse):
        return ctx
    if (gone := _refuse_signed(ctx[0])) is not None:  # the link has no assessment id in its path, so the router-level guard cannot see it
        return gone
    body = await _body(request, UPLOAD_MAX)

    def work():
        c, row = ctx
        if row["source_id"] not in c.seen(GUEST)["sources"]:  # a source limited to named people is not for a link holder
            raise S.LinkError(*_INVALID)
        name, data = _file(body)
        by = row["owner"] or f"the owner of {row['source_name']}"
        if (body or {}).get("kind") == "benchmark":
            S.save_benchmarks(c.folder, name, data, c.inputs(N.ADMIN)["measures"], by, c.clock, only={b["measure_id"] for b in row["benchmarks"]})
        else:
            _take(c, request, row["source_id"], name, data, by)
        K.bump(c.folder, "upload_benchmarks" if (body or {}).get("kind") == "benchmark" else "upload_source")
        return c.row_view(c.requests.get(row["id"]), c.seen(GUEST), GUEST)
    return await run_in_threadpool(_run, work)
