"""Data-backed opportunities (spec 56, ruling 32): the Watcher notices a pattern in the records, Lens adds evidence, North judges, a person acts.

Records: `intents/opportunities/<id>.json` (SHAPES section 15). No function here creates, opens or changes an intent: "Pick it up" only marks the
opportunity and hands back the start-flow address (`/centre/intent/new?type=initiative&from=<id>`); the start flow writes the intent.
Visibility (rule in 56): the company admin sees every opportunity (existence, state, counters); anyone else only when tagged to one of its
areas (or it names none) and only when they may see every measure it touches. Otherwise it is absent, not a silhouette.
"""
import json
import logging
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.build import opportunity_watch as watch
from sh_platform.context_docs.api import _json_body, _plain
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.intents import _plane, _viewer
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.perf import cached
from sh_platform.profile import areas as areas_store, store, view
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
NOT_FOUND = "We could not find that."
OPEN = ("noticed", "under_review", "proposed")
LIVE = OPEN + ("parked",)
LABEL = {"watcher": "The operations monitor", "lens": "Lens", "north": "North"}
CONFIDENCE = {"fairly_sure", "not_sure", "unlikely"}
ANSWERS = ("goal", "people", "build", "definitions", "areas", "deadline")
SOURCE_KINDS = {"alert", "run", "week_item", "map_node", "document", "pack", "feed", "measure", "process", "source"}
ACTIONS = ("pick_up", "think_through", "park", "dismiss", "bring_back")
PICKERS = {"owner", "company_admin", "sponsor", "analyst"}  # C3: who may pick up or think it through
MODULE_ID = "m1_intent"


# ---- the store --------------------------------------------------------------------------------------------------------------------------
def _dir(plane):
    return plane.path("intents", "opportunities")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path) -> dict | None:
    try:
        rec = read_json_strict(path, dict)
    except (OSError, ValueError) as e:
        log.warning("an opportunity record is unreadable: %s", type(e).__name__)
        return None
    return rec if isinstance(rec, dict) and rec.get("id") == path.stem else None


def all_records(plane) -> list[dict]:
    return [r for f in sorted(_dir(plane).glob("opp-*.json")) if (r := _read(f))]


def get(plane, opp_id: str) -> dict | None:
    return _read(_dir(plane) / f"{opp_id}.json") if re.fullmatch(r"opp-[0-9a-f]{4,40}", str(opp_id)) else None


def _hist(rec: dict, by: str, action: str, note: str | None = None) -> None:
    rec["history"].append({"at": _now(), "by": by, "action": action, "note": note})


def _create(plane, draft: dict, by: str, evidence: dict | None = None) -> dict:
    with lock_for(_dir(plane) / ".lock"):
        n = 1 + max((int(r["id"][4:]) for r in all_records(plane) if r["id"][4:].isdigit()), default=0)  # seeded records may carry hex ids
        at = _now()
        rec = {"id": f"opp-{n:04d}", "title": draft["title"], "state": "noticed", "noticed_by": by, "noticed_at": at, "areas": draft["areas"],
               "touches": draft["touches"], "pattern": draft["pattern"], "evidence": [], "judgement": None, "picked_up_by": None, "picked_up_at": None,
               "became": None, "parked": None, "dismissed": None, "history": [{"at": at, "by": by, "action": "noticed", "note": None}]}
        if evidence:
            _add_evidence(rec, evidence, by)
        write_json_atomic(_dir(plane) / f"{rec['id']}.json", rec)
        return rec


def _save(plane, rec: dict) -> None:
    write_json_atomic(_dir(plane) / f"{rec['id']}.json", rec)


def _add_evidence(rec: dict, ev: dict, by: str) -> None:
    rec["evidence"].append({"id": f"e{len(rec['evidence']) + 1}", "text": ev["text"], "kind": ev["kind"], "source": ev.get("source"), "by": by, "at": _now()})
    _hist(rec, by, "evidence_" + ev["kind"], None)
    if rec["state"] == "noticed":
        rec["state"] = "under_review"
        _hist(rec, by, "under_review")
    elif rec["state"] == "proposed" and ev["kind"] == "disputes":
        rec["state"] = "under_review"
        _hist(rec, by, "under_review", "Disputed")


def run_watcher(plane, today: date | None = None, names: dict[str, str] | None = None) -> list[dict]:
    """The daily read: draft a record for each pattern the set thresholds find that is not already on record. Returns the ones written.
    `names` (measure id to pack name) puts the measure's name in the title and sentence in place of its code."""
    today, t = today or datetime.now(timezone.utc).date(), watch.thresholds(plane)
    drafts = cached(plane, "opp_watch", [plane.root], lambda: watch.detect(plane, today, t), viewer=(today, tuple(t.items())))
    named = (lambda s: re.sub(r"\bK\d+\b", lambda m: (names or {}).get(m.group(0), m.group(0)), s))
    made = []
    for d in drafts:
        with lock_for(_dir(plane) / ".lock"):
            if not any(watch.same(d, r) for r in all_records(plane)):
                d = {**d, "title": named(d["title"]), "pattern": {**d["pattern"], "text": named(d["pattern"]["text"])}}
                made.append(_create(plane, d, "watcher"))
    return made


# ---- North's judgement ------------------------------------------------------------------------------------------------------------------
SYSTEM = ("You are North, the industry expert. A pattern has been noticed in a family office's own records. Decide whether it merits an Initiative: "
          "yes when it crosses a source contract, a process step and a reported measure, so more than one fix is needed, or when it enhances something already built; "
          "no when it is something wrong in operations today that one owner can fix, which reads as a Problem. Write in words, never in numbers. "
          'Reply with one JSON object only: {"fits": true or false, "why": "two or three sentences", "confidence": "fairly_sure" or "not_sure" or "unlikely", '
          '"start_answers": {"goal": "", "people": "", "build": "", "definitions": "", "areas": "", "deadline": ""}}. '
          "Each start answer is a short draft of one sentence at most; write \"not sure\" where the record does not say.")


def _parse(text: str, rec: dict) -> dict | None:
    t = re.sub(r"```(?:json)?", "", text or "")
    i = t.find("{")
    try:
        obj, _ = json.JSONDecoder().raw_decode(t, i) if i >= 0 else (None, 0)
    except ValueError:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("fits"), bool) or not isinstance(obj.get("why"), str) or not obj["why"].strip():
        return None
    answers = obj.get("start_answers") if isinstance(obj.get("start_answers"), dict) else {}
    guessed = {k: {"value": str(answers[k]).strip()[:300], "mark": "guessed", "by": "North", "from": rec["id"]} for k in ANSWERS if str(answers.get(k) or "").strip()} if obj["fits"] else {}
    conf = obj.get("confidence") if obj.get("confidence") in CONFIDENCE else "not_sure"
    return {"fits": obj["fits"], "why": obj["why"].strip()[:600], "confidence": conf, "start_answers": guessed, "at": _now()}


def _model(request: Request, plane):
    factory = getattr(request.app.state, "opportunity_model_factory", None)
    override = getattr(request.app.state, "model_env", None)
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def judge(request: Request, plane, rec: dict) -> dict | None:
    """North's judgement of the record, in words; None when North cannot be reached (the screen says it has not judged yet)."""
    model = _model(request, plane)
    if model is None:
        return None
    pat = rec["pattern"]
    ctx = {"stage": "opportunity", "facts": []}
    q = json.dumps({"title": rec["title"], "pattern": pat["text"], "touches": rec["touches"], "areas": rec["areas"],
                    "evidence": [{"kind": e["kind"], "text": e["text"]} for e in rec["evidence"]]})
    try:
        res = run_agent(model, ToolRegistry(request.app.state.entitlements), request.state.company_id, MODULE_ID, "North", SYSTEM, ctx, q, recorder=RunRegistry(plane))
    except Exception:  # noqa: BLE001 - a provider failure must never break the person's own action
        log.warning("North could not judge an opportunity", exc_info=True)
        return None
    return _parse(res.text, rec) if res.status == "done" else None


def evidence_of(plane, rec: dict) -> list[dict]:
    """The one evidence list (57, C7): the hypothesis's lines when the record carries one, else the record's own."""
    if rec.get("hypothesis_ref"):
        from sh_platform.intents import hypotheses as H
        hyp = H.get(plane, rec["hypothesis_ref"].get("id", ""))
        if hyp:
            return H.as_56_evidence(hyp)
    return rec["evidence"]


def _rejudge(request: Request, plane, rec: dict) -> None:
    """North judges once per change: yes moves an under-review record to proposed; no leaves it under review."""
    ev = evidence_of(plane, rec)
    if rec["state"] != "under_review" or not any(e["by"] not in ("watcher", "lens", "north") for e in ev):
        return
    j = judge(request, plane, {**rec, "evidence": ev})
    if j is None:
        return
    rec["judgement"] = j
    _hist(rec, "north", "judged_yes" if j["fits"] else "judged_no")
    if j["fits"]:
        rec["state"] = "proposed"
        _hist(rec, "north", "proposed")


# ---- who sees what ---------------------------------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, request: Request, plane):
        self.request, self.plane, self.viewer = request, plane, _viewer(request)
        self.admin = view.ADMIN in self.viewer.roles
        doc = store.load(plane)  # read only here, so the copy raw() makes is not needed
        self.areas = areas_store.areas_of_account(doc, self.viewer.account_id)
        self.rules = doc["governance"]["field_rules"]
        self.names = _measure_names(request)

    def shut(self, measure: str) -> bool:
        key = view._key(measure)
        return any(not view.sees_rule(r, self.viewer) for k, r in self.rules.items() if key in {view._key(k), view._key(view._v(r, "field") or "")}
                   or (self.names.get(measure) and view._key(self.names[measure]) in {view._key(k), view._key(view._v(r, "field") or "")}))

    def sees(self, rec: dict) -> bool:
        if self.admin:
            return True
        if rec["areas"] and not set(rec["areas"]) & self.areas:
            return False
        return not any(self.shut(m) for m in rec["touches"]["measures"])


def _measure_names(request: Request) -> dict[str, str]:
    try:
        co = request.app.state.entitlements.company(request.state.company_id) or {}
        return {str(k["id"]): str(k["name"]) for k in request.app.state.packs.load(str(co.get("industry") or "-")).section("kpi_tree")["kpis"]}
    except (KeyError, AttributeError, TypeError, ValueError):
        return {}


def _who(request: Request, v) -> str | None:
    if v is None:
        return None
    return LABEL.get(v) or str((request.app.state.account_store.get(v) or {}).get("display_name") or "Someone")


def _can(ctx: Ctx, rec: dict) -> dict:
    r, st = ctx.viewer.roles, rec["state"]
    owner, analyst = "owner" in r, "analyst" in r
    live = st not in ("picked_up", "dismissed")
    picker = bool(r & PICKERS) or (bool(set(rec["areas"]) & ctx.areas) and "participant" not in r)  # C3
    ready = _ready(ctx.plane, rec)
    return {"raise": owner or analyst, "add_evidence": (owner or analyst) and live, "dispute": analyst and live,
            "pick_up": picker and st == "proposed" and ready, "think_through": picker and st == "proposed" and ready and bool(rec.get("hypothesis_ref")),
            "park": owner and st in OPEN, "dismiss": owner and st in OPEN, "bring_back": owner and st in ("parked", "dismissed", "rejected"),
            "edit_hypothesis": (owner or analyst) and live and bool(rec.get("hypothesis_ref"))}


def _ready(plane, rec: dict) -> bool:
    """57: a record that carries a hypothesis needs a review date and a "Holds" check before anyone picks it up or thinks it through."""
    if not rec.get("hypothesis_ref"):
        return True
    from sh_platform.intents import hypotheses as H
    v = H.latest(H.get(plane, rec["hypothesis_ref"].get("id", ""))) or {}
    return bool(v.get("review_date")) and (v.get("counter_check") or {}).get("verdict") == "holds"


def _words(ctx: Ctx, text):
    """A measure code in stored text reads as the measure's name, or as a restricted measure when the viewer may not see it."""
    return re.sub(r"\bK\d+\b", lambda m: "a restricted measure" if ctx.shut(m.group(0)) else ctx.names.get(m.group(0), "a measure"), text) if isinstance(text, str) else text


def _shape(ctx: Ctx, rec: dict) -> dict:
    rq = ctx.request
    w = lambda s: _words(ctx, s)  # noqa: E731
    shut = {m for m in rec["touches"]["measures"] if ctx.shut(m)}
    pat = rec["pattern"]
    numbers = [{**n, "label": w(n["label"]), **({"value": None, "restricted": True} if shut and n["trace"]["kind"] in ("feed", "range_break") else {})} for n in pat["numbers"]]
    j = rec["judgement"] and {**rec["judgement"], "why": w(rec["judgement"]["why"])}
    return {"id": rec["id"], "title": w(rec["title"]), "state": rec["state"], "noticed_by": _who(rq, rec["noticed_by"]), "noticed_at": rec["noticed_at"], "areas": rec["areas"],
            "touches": {"measures": [{"id": m, "name": None if m in shut else ctx.names.get(m, m)} for m in rec["touches"]["measures"]],
                        "processes": rec["touches"]["processes"], "sources": rec["touches"]["sources"]},
            "pattern": {**pat, "text": w(pat["text"]), "numbers": numbers}, "evidence": [{**e, "text": w(e["text"]), "by": "Someone, anonymously" if e["by"] == "anonymous" else _who(rq, e["by"])} for e in evidence_of(ctx.plane, rec)],
            "judgement": j, "picked_up_by": _who(rq, rec["picked_up_by"]), "picked_up_at": rec["picked_up_at"], "became": rec["became"],
            "parked": rec["parked"] and {**rec["parked"], "by": _who(rq, rec["parked"]["by"])}, "dismissed": rec["dismissed"] and {**rec["dismissed"], "by": _who(rq, rec["dismissed"]["by"])},
            "history": [{**h, "note": w(h["note"]), "by": _who(rq, h["by"])} for h in rec["history"]], "can": _can(ctx, rec), "href": f"/centre/intent/backlog?opportunity={rec['id']}",
            "start_href": f"/centre/intent/new?type=initiative&from={rec['id']}", "think_href": f"/centre/intent/new?type=brainstorm&from={rec['id']}",
            "hypothesis_ref": rec.get("hypothesis_ref"), "rejected": rec.get("rejected") and {**rec["rejected"], "why": w(rec["rejected"]["why"])},
            "linked": rec.get("linked"), "links_proposed": [{k: v for k, v in p.items() if k != "decider"} for p in rec.get("links_proposed") or []],
            "picked_up_as": rec.get("picked_up_as")}


def _counters(plane, recs: list[dict]) -> dict:
    """Numbers only, each from the records; None where the screen says Not available yet."""
    if not recs:
        return {k: None for k in ("noticed_by_watcher", "noticed_by_person", "picked_up", "parked", "dismissed", "became_initiatives", "judged_yes_then_picked_up")}
    def became(r):
        i = read_json_strict(plane.path("intents", str(r["became"]), "intent.json"), dict) if r.get("became") and re.fullmatch(r"[\w-]+", str(r["became"])) else None
        return bool(i and i.get("type") == "initiative" and (i.get("refs") or {}).get("opportunity_id") == r["id"])
    yes = sum(1 for r in recs if r["state"] == "picked_up" and (r["judgement"] or {}).get("fits"))
    return {"noticed_by_watcher": sum(r["noticed_by"] == "watcher" for r in recs), "noticed_by_person": sum(r["noticed_by"] != "watcher" for r in recs),
            "picked_up": sum(r["state"] == "picked_up" for r in recs), "parked": sum(r["state"] == "parked" for r in recs),
            "dismissed": sum(r["state"] == "dismissed" for r in recs), "became_initiatives": sum(1 for r in recs if became(r)),
            "judged_yes_then_picked_up": yes if yes >= 5 else None}  # ruling 8: below five is "Fewer than five"


def pulse_lines(plane, request: Request) -> list[dict]:
    """The two Pulse lines (Nira, kind decision) for the viewer: analysts hear of a noticed pattern, the ops manager of a proposed Initiative."""
    from sh_platform.pulse.lines import line
    if not {"analyst", "owner"} & set(_viewer(request).roles):  # nobody else gets either line
        return []
    ctx, out = Ctx(request, plane), []
    for r in all_records(plane):
        if not ctx.sees(r):
            continue
        r = {**r, "title": _words(ctx, r["title"])}
        href = f"/centre/intent/backlog?opportunity={r['id']}"
        if "analyst" in ctx.viewer.roles and r["state"] in ("noticed", "under_review") and r["noticed_by"] == "watcher":
            out.append(line(f"opportunity:{r['id']}:evidence", "decision", f"The operations monitor noticed a pattern: {r['title']}", "Add or dispute evidence.", href, "Open it", f"intents/opportunities/{r['id']}.json", r["noticed_at"]))
        if "owner" in ctx.viewer.roles and r["state"] == "proposed":
            out.append(line(f"opportunity:{r['id']}:proposed", "decision", f"North suggests an Initiative from the records: {r['title']}.", (r["judgement"] or {}).get("why") or "", href, "Open it", f"intents/opportunities/{r['id']}.json", (r["judgement"] or {}).get("at")))
    return out


# ---- routes -----------------------------------------------------------------------------------------------------------------------------
def _text(v, limit: int) -> str | None:
    return " ".join(v.split())[:limit] if isinstance(v, str) and v.strip() else None


def _ids(v, limit: int = 10) -> list[str] | None:
    if v is None:
        return []
    ok = isinstance(v, list) and all(isinstance(x, str) and re.fullmatch(r"[\w:.\- ]{1,80}", x) for x in v) and len(v) <= limit
    return list(dict.fromkeys(v)) if ok else None


def _evidence_in(body: dict, need_text: str) -> dict | JSONResponse:
    text, kind, src = _text(body.get("text"), 500), body.get("kind", "supports"), body.get("source")
    if text is None:
        return _plain(422, "text", need_text)
    if kind not in ("supports", "disputes"):
        return _plain(422, "kind", "Say whether the evidence supports the opportunity or disputes it.")
    if src is not None and not (isinstance(src, dict) and src.get("kind") in SOURCE_KINDS and _text(src.get("ref"), 200)):
        return _plain(422, "source", "Pick a source record from the list, or leave it out.")
    return {"text": text, "kind": kind, "source": {"kind": src["kind"], "ref": _text(src["ref"], 200)} if src else None}


def _guard(request: Request, work):
    try:
        return work(_plane(request))
    except PermissionError:
        return _plain(403, "company_space_closed", "Your company space could not be opened. Please ask your administrator.")


def _find(ctx: Ctx, opp_id: str) -> dict | None:
    rec = get(ctx.plane, opp_id)
    return rec if rec and ctx.sees(rec) else None


@router.get("/api/intents/opportunities")
def get_opportunities(request: Request):
    def work(plane):
        try:
            run_watcher(plane, names=_measure_names(request))
        except (OSError, ValueError, KeyError, TypeError) as e:  # the Watcher failing must never hide the records
            log.warning("the Watcher could not read the records: %s", type(e).__name__)
        ctx, recs = Ctx(request, plane), all_records(plane)
        t = watch.thresholds(plane)
        mine = [_shape(ctx, r) for r in recs if ctx.sees(r)]
        mine.sort(key=lambda o: o["noticed_at"], reverse=True)
        return {"opportunities": mine, "counters": _counters(plane, recs) if ctx.admin else None,  # the counters strip is the company admin's
                "thresholds": {"set": not watch.missing(t), "missing": watch.missing(t), "message": None if not watch.missing(t) else watch.NOT_SET},
                "can_raise": bool(ctx.viewer.roles & {"owner", "analyst"})}
    return _guard(request, work)


@router.get("/api/intents/opportunities/{opp_id}")
def get_opportunity(request: Request, opp_id: str):
    def work(plane):
        ctx = Ctx(request, plane)
        rec = _find(ctx, opp_id)
        return _shape(ctx, rec) if rec else _plain(404, "not_found", NOT_FOUND)
    return _guard(request, work)


@router.post("/api/intents/opportunities")
async def post_opportunity(request: Request):
    body = await _json_body(request, 16384)
    if isinstance(body, JSONResponse):
        return body

    def work(plane):
        ctx = Ctx(request, plane)
        if not ctx.viewer.roles & {"owner", "analyst"}:
            return _plain(403, "opportunity_not_your_role", "Only the ops manager or the business analyst can raise an opportunity.")
        title, noticed, t = _text(body.get("title"), 160), _text(body.get("noticed"), 600), body.get("touches") or {}
        if title is None:
            return _plain(422, "title", "A title is needed.")
        if noticed is None:
            return _plain(422, "noticed", "Say what you noticed.")
        touches = {k: _ids((t if isinstance(t, dict) else {}).get(k)) for k in ("measures", "processes", "sources")}
        if None in touches.values() or not any(touches.values()):
            return _plain(422, "touches", "Name at least one measure, process or source.")
        doc = store.load(plane)
        known = {a["id"] for a in areas_store.listing(doc) if a["status"] == "active"}
        areas = _ids(body.get("areas")) if body.get("areas") is not None else sorted(ctx.areas)
        if areas is None or not set(areas) <= known:
            return _plain(422, "areas", "Pick areas from the list.")
        ev = _evidence_in(body["evidence"], "Say what the evidence is.") if isinstance(body.get("evidence"), dict) else None
        if isinstance(ev, JSONResponse):
            return ev
        if ctx.names and not set(touches["measures"]) <= set(ctx.names):
            return _plain(422, "touches", "Pick measures from the list.")
        draft = {"title": title, "areas": areas, "touches": touches, "pattern": {"text": noticed, "periods": [], "numbers": []}}
        rec = _create(plane, draft, ctx.viewer.account_id or "unknown", ev)
        _rejudge(request, plane, rec)
        _save(plane, rec)
        return JSONResponse(_shape(ctx, rec), status_code=201)
    return await run_in_threadpool(_guard, request, work)


@router.post("/api/intents/opportunities/{opp_id}/evidence")
async def post_opportunity_evidence(request: Request, opp_id: str):
    body = await _json_body(request, 8192)
    if isinstance(body, JSONResponse):
        return body

    def work(plane):
        ctx = Ctx(request, plane)
        rec = _find(ctx, opp_id)
        if rec is None:
            return _plain(404, "not_found", NOT_FOUND)
        if not ctx.viewer.roles & {"owner", "analyst"}:
            return _plain(403, "opportunity_not_your_role", "Only the ops manager or the business analyst can add evidence.")
        if rec["state"] in ("picked_up", "dismissed"):
            return _plain(409, "closed", "This opportunity is closed, so evidence can no longer be added.")
        ev = _evidence_in(body, "Say what the evidence is." if body.get("kind") != "disputes" else "Give a reason for the dispute.")
        if isinstance(ev, JSONResponse):
            return ev
        with lock_for(_dir(plane) / f"{rec['id']}.json"):
            rec = get(plane, opp_id)
            _add_evidence(rec, ev, ctx.viewer.account_id or "unknown")
            if rec.get("hypothesis_ref"):  # C7: the line lives on the hypothesis, one list
                from sh_platform.intents import hypotheses as H
                line = rec["evidence"].pop()
                if H.add_evidence(plane, rec["hypothesis_ref"]["id"], ev, ctx.viewer.account_id or "unknown"):
                    rec["hypothesis_ref"] = H.ref(H.get(plane, rec["hypothesis_ref"]["id"]))
                else:
                    rec["evidence"].append(line)
            _save(plane, rec)
        return rec
    out = _guard(request, work)
    if isinstance(out, JSONResponse):
        return out

    def judge_it(plane):
        with lock_for(_dir(plane) / f"{opp_id}.json"):
            rec = get(plane, opp_id)
            _rejudge(request, plane, rec)
            _save(plane, rec)
        return _shape(Ctx(request, plane), rec)
    return await run_in_threadpool(_guard, request, judge_it)


@router.post("/api/intents/opportunities/{opp_id}/state")
async def post_opportunity_state(request: Request, opp_id: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body

    def work(plane):
        ctx = Ctx(request, plane)
        rec = _find(ctx, opp_id)
        if rec is None:
            return _plain(404, "not_found", NOT_FOUND)
        act = body.get("action")
        if act not in ACTIONS:
            return _plain(422, "action", "Choose pick up, think it through first, park, dismiss or bring back.")
        picking = act in ("pick_up", "think_through")
        if picking and not (ctx.viewer.roles & PICKERS or (set(rec["areas"]) & ctx.areas and "participant" not in ctx.viewer.roles)):
            return _plain(403, "opportunity_not_your_role", "Only the people of this area can pick it up or think it through.")
        if not picking and "owner" not in ctx.viewer.roles:
            return _plain(403, "opportunity_not_your_role", "Only the ops manager can park, dismiss or bring back an opportunity.")
        if picking and rec["state"] == "proposed" and not _ready(plane, rec):
            return _plain(409, "not_ready", "Set a review date first. North's check must also hold.")
        if not _can(ctx, rec)[act]:
            return _plain(409, "state", "That is not possible while the opportunity is " + rec["state"].replace("_", " ") + ".")
        reason, by = _text(body.get("reason"), 500), ctx.viewer.account_id or "unknown"
        if (act in ("park", "dismiss") or (act == "bring_back" and rec["state"] == "rejected")) and reason is None:
            return _plain(422, "reason", "A reason is needed.")
        review = body.get("review_date")
        if act == "park" and not (isinstance(review, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", review) and _valid_date(review)):
            return _plain(422, "review_date", "A review date is needed.")
        with lock_for(_dir(plane) / f"{rec['id']}.json"):
            rec = get(plane, opp_id)
            at = _now()
            if picking:
                rec.update(state="picked_up", picked_up_by=by, picked_up_at=at, picked_up_as="brainstorm" if act == "think_through" else "initiative")
            elif act == "park":
                rec.update(state="parked", parked={"by": by, "at": at, "reason": reason, "review_date": review})
            elif act == "dismiss":
                rec.update(state="dismissed", dismissed={"by": by, "at": at, "reason": reason})
            else:
                rec.update(state="under_review")
            if act == "bring_back" and rec.get("rejected") and rec.get("hypothesis_ref"):  # North re-checks: a new version, back to draft
                from sh_platform.intents import hypotheses as H
                if H.add_version(plane, rec["hypothesis_ref"]["id"], {"counter_check": None}, by, state="draft"):
                    rec["hypothesis_ref"] = H.ref(H.get(plane, rec["hypothesis_ref"]["id"]))
            _hist(rec, by, {"pick_up": "picked_up", "think_through": "picked_up", "park": "parked", "dismiss": "dismissed", "bring_back": "brought_back"}[act], reason)
            _save(plane, rec)
        return rec

    out = _guard(request, work)
    if isinstance(out, JSONResponse):
        return out
    if body.get("action") == "bring_back":
        def judge_it(plane):
            with lock_for(_dir(plane) / f"{opp_id}.json"):
                rec = get(plane, opp_id)
                _rejudge(request, plane, rec)
                _save(plane, rec)
            return rec
        out = await run_in_threadpool(_guard, request, judge_it)
    return _guard(request, lambda plane: _shape(Ctx(request, plane), out))


def _valid_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True
