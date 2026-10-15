"""IC v2 (41, 42): the Problem. Start questions, triage and acceptance, then cause, fix and confirmation. Closing is spec 09 (closure.py).

The record is the intent store's (`store.py`: version check, key check, index row). Every change is a named person's press; North only
drafts. The triage summary and the cause draft come from the kernel agent runtime through the egress gateway (R14, north._call); when the
model cannot answer, the plain matches and a plain reading of the notes are stored instead, marked so the screen says so.
`notes`, `what_we_know` and `short_ref` are fields of spec 42 that `store.KEYS` does not list yet; they sit in `outcome` until it does (see `_h`).
"""
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from sh_platform.build import alerts as store_alerts
from sh_platform.graph import versions as graph_versions
from sh_platform.intents import _plane, _viewer, clock
from sh_platform.intents import events as ev
from sh_platform.intents import north as N
from sh_platform.intents.decision import drop_untraced, with_numbers
from sh_platform.intents import lifecycle as L
from sh_platform.intents import problem_lookup as lk
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import store as profile_store

log = logging.getLogger(__name__)
router = APIRouter()

STAGE_DAYS = {"describe": 1, "find_cause": 2, "fix": 1, "confirm": 1}
STAGE_NAMES = {"describe": "Describe", "find_cause": "Find the cause", "fix": "Fix", "confirm": "Confirm"}
BITES = ("slowed", "stopped", "cost_money")
REASON_MIN, WHAT_MAX, SAW_MAX, NOTE_MAX, TEXT_MAX = 10, 140, 600, 2000, 2000
REOPEN_DAYS, EXTEND_CHOICES = 2, (1, 2, 3, 5)  # REOPEN_DAYS is the drafted figure of spec 42, open question 4
QUESTIONS = ["When did it start?", "What changed just before it started?", "Who else has seen it?"]  # at most three (A-045)
OPEN = ("open", "in_session")
NOT_YET = "not available yet"  # what the runtime figure guard writes over a number it cannot trace
NO = lambda status, message: L.Refused(status, message)  # noqa: E731
FORBIDDEN = "That is not yours to do."
SYSTEM = ("You are North. You help a named person own an operations problem; you never accept, confirm, sign, fix or close. Use only the "
          "records in the context. Never write a number that is not in them. Plain English, British spelling, no em dashes, no names of people.")
ASK_TRIAGE = 'Restate the problem as reported in at most two sentences, for the person asked to own it. Reply with ONLY one JSON object {"text": "..."}'
ASK_CAUSE = ("Draft the most likely root cause in one or two sentences from the notes, and at most three short questions that would settle it. "
             'Reply with ONLY one JSON object {"text": "...", "based_on": ["note id"], "questions": ["..."]}')


def _ask(request: Request, plane, task: str, context: dict) -> dict | None:
    """One North turn through the kernel runtime, read as a JSON object; None when the model cannot answer (the caller then falls back)."""
    gate = getattr(request.app.state, "entitlements", None)
    if gate is None:
        return None
    try:
        text = N._call(plane, N._model(request, plane), gate, SYSTEM, {"facts": [], **context}, with_numbers(task, json.dumps(context))) or ""
        a, b = text.find("{"), text.rfind("}")
        got = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except Exception:  # noqa: BLE001 - a provider failure falls back to the plain draft, never breaks the person's own act
        log.warning("North could not draft for a problem", exc_info=True)
        return None
    return got if isinstance(got, dict) else None


def _triage_summary(request: Request, plane, what: str, saw: str, about: dict | None) -> str | None:
    """North's two-sentence statement for the triage note; numbers it cannot trace to the report are dropped."""
    allowed = f"{what} {saw} {(about or {}).get('name') or ''}"
    got = _ask(request, plane, ASK_TRIAGE, {"problem": {"what": what, "saw": saw, "about": (about or {}).get("name") or "Not sure"}})
    text = drop_untraced(_text((got or {}).get("text"), 400), allowed)[0] if got else ""
    return None if NOT_YET in text.lower() else text or None  # the figure guard ate a digit run inside a word ("T24b"): use the plain restatement


def _with_summary(note: dict, summary: str | None) -> dict:
    return {**note, "summary": summary, "drafted_plainly": not summary}


def _cause_draft(request: Request, plane, rec: dict) -> dict | None:
    """North's cause from the named notes and the linked alert (anonymous notes are never sent). None when the model cannot answer."""
    notes = [n for n in _h(rec).get("notes") or [] if not n.get("system") and not n.get("anonymous")]
    out, al = rec["outcome"], (rec.get("links") or {}).get("alert")
    got = _ask(request, plane, ASK_CAUSE, {"problem": {"what": out.get("what"), "saw": out.get("saw"), "ops_alert": al},
                                          "notes": {n["id"]: n["text"] for n in notes[-12:]}})
    allowed = " ".join([out.get("what") or "", out.get("saw") or "", al or ""] + [n["text"] for n in notes])
    text = drop_untraced(_text((got or {}).get("text"), 600), allowed)[0] if got else ""
    if not text or NOT_YET in text.lower():
        return None
    ids = {n["id"] for n in notes}
    qs = [_text(q, 200) for q in (got.get("questions") or []) if isinstance(q, str) and q.strip()][:3]
    return {"text": text, "based_on": [str(i) for i in got.get("based_on") or [] if str(i) in ids] + ([al] if al else []), "questions": qs or QUESTIONS}


def _text(v, limit: int) -> str:
    return " ".join(str(v or "").split())[:limit] if limit <= WHAT_MAX else str(v or "").strip()[:limit]


def _date(text) -> str | None:
    return text[:10] if isinstance(text, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text) else None


def _part(x):
    """A cause or fix as a dict: an older record keeps it as plain text, or leaves it out."""
    return {"text": x, "what": x} if isinstance(x, str) and x else x if isinstance(x, dict) else None


def _h(rec: dict) -> dict:
    """Where the spec 42 top-level fields live: on the record once `store.KEYS` lists them, else inside `outcome`."""
    return rec if {"notes", "what_we_know", "short_ref"} <= S.KEYS else rec["outcome"]


# ---- people and the record -----------------------------------------------------------------------------------------------------------------

def _key(p: dict | None) -> str | None:
    return (p.get("account_id") or p.get("name")) if isinstance(p, dict) else None


def _same(a: dict | None, b: dict | None) -> bool:
    return bool(a and b and (a.get("account_id") == b.get("account_id") if a.get("account_id") and b.get("account_id") else a.get("name") == b.get("name")))


def _person(request: Request, plane, key, need_account: bool = False) -> dict | None:
    """A profile person (by id or name) as a store person `{account_id, name}`; with `need_account` only someone who can sign in."""
    hit = next((p for p in lk.people(plane, _viewer(request)) if key in (p["id"], p["name"])), None)
    if hit is None:
        return None
    acct = lk.accounts(request).get(hit["name"].lower())
    return None if need_account and not acct else L.person(acct, hit["name"])


def _admin(request: Request) -> dict | None:
    a = next((a for a in request.app.state.account_store.in_company(request.state.company_id) if "company_admin" in a["roles"] and not a["disabled"]), None)
    return L.person(a["account_id"], a["display_name"]) if a else None


def _grant(rec: dict, p: dict | None) -> None:
    """The proposed owner reads the problem: named as a participant until the owner slot holds them."""
    if p and not any(_same(p, x) for x in rec["people"]["participants"]) and not _same(p, rec["people"].get("owner")):
        rec["people"]["participants"].append(L.person(p.get("account_id"), p["name"]))


def _next_ref(plane) -> str:
    path = plane.path("intents", "counters.json")
    with lock_for(path):
        c = read_json_strict(path, dict) or {}
        c["problem"] = int(c.get("problem") or 0) + 1
        write_json_atomic(path, c)
    return f"P-{c['problem']}"


def _stage_key(rec: dict) -> str | None:
    return next((s["key"] for s in rec.get("stages") or [] if s.get("state") == "open"), None)


def _stage_shut(rec: dict, now: str) -> None:
    for s in rec["stages"]:
        if s["state"] == "open":
            s.update(state="closed", closed_at=now)


def _stage_open(rec: dict, key: str, now: str) -> None:
    for s in rec["stages"]:
        if s["key"] == key:
            due = L.add_working_days(datetime.fromisoformat(now), STAGE_DAYS[key])
            s.update(state="open", opened_at=now, closed_at=None, due=min(due, clock.parse(rec["time_box"]["ends"])).isoformat())


def _move(rec: dict, key: str, now: str) -> None:
    _stage_shut(rec, now)
    _stage_open(rec, key, now)


# ---- who may see and do what ---------------------------------------------------------------------------------------------------------------

def _rel(rec: dict, viewer, plane) -> dict:
    p, out = rec["people"], rec["outcome"]
    n = lambda x: S._named(x, viewer)  # noqa: E731
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer))
    admin = "company_admin" in viewer.roles
    passer = any(n({"account_id": x.get("from_id"), "name": x.get("from")}) or n({"account_id": x.get("to_id"), "name": x.get("to")}) for x in rec.get("passes") or [])
    prop = out.get("triage") == "waiting" and n(out.get("proposed_owner"))
    r = {"tier": tier, "content": tier == "content", "organiser": n(p.get("organiser")), "reporter": n(p.get("reporter")), "owner": n(p.get("owner")),
         "adviser": any(n(x) for x in p.get("advisers") or []), "proposed": bool(prop), "admin": admin, "affected": any(n(x) for x in p["affected"]), "participant": any(n(x) for x in p["participants"]),
         "passer": passer}
    r["outcome_only"] = admin and not r["content"]
    r["reads"] = r["content"] or r["reporter"] or r["owner"] or r["adviser"] or (r["affected"] and bool(rec.get("affected_may_read")))  # who sees the thread, cause and fix as they are written
    r["triage"] = r["reporter"] or r["owner"] or r["proposed"] or passer
    return r


def _heal(rec: dict) -> dict:
    """The people list (file 06) keeps one role per person, so its rebuild of `people` drops the reporter slot when the reporter is also the
    organiser (always, spec 41). The reporter is the person who opened the problem: put the slot back."""
    p = rec.get("people") or {}
    if rec.get("type") == "problem" and rec.get("opened_by") and not p.get("reporter") and (p.get("organiser") or {}).get("account_id") == rec["opened_by"]:
        p["reporter"] = dict(p["organiser"])
    return rec


def _get(request: Request, intent_id: str):
    """(plane, viewer, record) of a problem the viewer may see at all; LookupError otherwise (404, not even a stub)."""
    plane, viewer = _plane(request), _viewer(request)
    rec = S.read_intent(plane, intent_id)
    if rec is None or rec.get("type") != "problem" or S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None:
        raise LookupError(intent_id)
    return plane, viewer, _heal(rec)


def _fail(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


def _run(request: Request, fn):
    try:
        return fn()
    except L.Refused as e:
        return _fail(e.status, e.message)
    except LookupError:
        return _fail(404, S.NOT_FOUND)
    except S.VersionConflict:
        return _fail(409, S.CONFLICT)
    except S.Unreadable:
        return _fail(500, S.UNREADABLE)
    except (PermissionError, CrossCompanyError):
        return _fail(403, FORBIDDEN)


def _mutate(request: Request, intent_id: str, check, change, event=None):
    """Read, `check` (raises Refused), `change`, write through the store, then log the event lines `change` queued. Answers with the view."""
    queue: list = []

    def go():
        plane, viewer, rec0 = _get(request, intent_id)
        now = S.now_iso()

        def edit(rec):
            _heal(rec)
            check(rec, _rel(rec, viewer, plane), viewer)
            change(rec, viewer, now, queue)
        rec = S.update_intent(plane, intent_id, rec0["version"], edit)
        _log(plane, intent_id, viewer, queue)
        return view_of(request, plane, viewer, rec)
    return _run(request, go)


def _log(plane, intent_id: str, viewer, queue: list) -> None:
    """The event lines a change queued (spec 16 kinds only). A draft by North is a draft line; an anonymous note has no author."""
    who = {"account": viewer.account_id, "name": viewer.name, "role": "member"}
    for kind, detail, kw in queue:
        if kind == "north_drafted":
            ev.try_append(plane, intent_id, kind, "north", None, detail, "draft", **kw)
        else:
            anon = bool(kw.get("anonymous"))
            ev.try_append(plane, intent_id, kind, None if anon else who, None, detail, "act", **kw)


def _open_only(rec: dict) -> None:
    if rec["state"] not in OPEN:
        raise NO(409, "This problem is no longer open.")


def _need(rel: dict, *roles: str) -> None:
    if not all(rel[r] for r in roles):
        raise NO(403, FORBIDDEN)


# ---- the view ----------------------------------------------------------------------------------------------------------------------------------

HIDDEN_ROW = "One related intent you cannot open"


def _row(plane, viewer, o: dict, why: str, n: int = 0) -> dict:
    """One row of a triage panel, only for an intent the viewer may open; any other is one line with no id, title, state or names."""
    rel, out, p = _rel(o, viewer, plane), o.get("outcome") or {}, o.get("people") or {}
    if not rel["content"]:
        return {"id": f"hidden-{n}", "title": HIDDEN_ROW, "type": None, "state": None, "why": "", "owner": None, "organiser": None,
                "can_open": False, "closed_at": None}
    row = {"id": o["id"], "title": o.get("title"), "type": o.get("type"), "state": o.get("state"), "why": why, "owner": (p.get("owner") or {}).get("name"),
           "organiser": (p.get("organiser") or {}).get("name"), "can_open": rel["content"], "closed_at": (o.get("closure") or {}).get("closed_at")}
    if row["can_open"]:
        rc, fx = _part(out.get("root_cause")) or {}, _part(out.get("fix")) or {}
        row["root_cause"] = rc.get("text") if isinstance(rc, dict) else rc
        row["fix"] = fx.get("text") or fx.get("what") if isinstance(fx, dict) else fx
    return row


def _others(plane) -> list[dict]:
    out = []
    for i in S._ids_on_disk(plane):
        try:
            rec = S.read_intent(plane, i)
        except S.Unreadable:
            continue
        if rec:
            out.append(rec)
    return out


def _triage_panels(plane, viewer, rec: dict) -> dict:
    note = rec.get("triage_note") or {}
    by_id = {o["id"]: o for o in _others(plane)}
    today = lk.ops_today(plane, viewer)
    al = {a["id"]: a for a in today.get("alerts") or []}
    rb = {b["mart"]: b for b in today.get("range_breaks") or []}
    return {
        "drafted_at": note.get("drafted_at"), "drafted_plainly": note.get("drafted_plainly", True), "summary": note.get("summary"),
        "similar": [_row(plane, viewer, by_id[x["intent"]], x["why"], i) for i, x in enumerate(note.get("similar") or []) if x["intent"] in by_id],
        "related": [_row(plane, viewer, by_id[x["intent"]], x["why"], i) for i, x in enumerate(note.get("related") or []) if x["intent"] in by_id],
        "alerts": [{"id": a["alert_id"], "kind": a["kind"], "state": (al.get(a["alert_id"]) or a).get("state"), "opened": (al.get(a["alert_id"]) or {}).get("opened"),
                    "by": (al.get(a["alert_id"]) or {}).get("by"), "note": (al.get(a["alert_id"]) or {}).get("note"), "source": (al.get(a["alert_id"]) or {}).get("source")}
                   for a in note.get("alerts") or []],
        "range_breaks": [{"mart": b["mart"], "basis": (rb.get(b["mart"]) or b).get("basis"), "latest": (rb.get(b["mart"]) or {}).get("latest"),
                          "hidden": b["mart"] in rb and rb[b["mart"]].get("latest") is None} for b in note.get("range_breaks") or []],
        "terms": note.get("terms") or [], "ops_unreadable": bool(today.get("unreadable")),
        "can_redraw": (note.get("drafted_at") or "") < (rec.get("updated_at") or ""),
    }


def _clock(plane, rec: dict) -> dict | None:
    tb = rec.get("time_box") or {}
    if not (tb.get("starts") and tb.get("ends")):
        return None
    return clock.clock(clock.parse(tb["starts"]), clock.parse(tb["ends"]), datetime.now(timezone.utc), len([e for e in tb.get("extended_by") or [] if e.get("status", "approved") == "approved"]))


def _name(request: Request, ref) -> str | None:
    if not ref:
        return None
    a = request.app.state.account_store.get(ref)
    return str(a["display_name"]) if a else str(ref)


def _affected_rows(rec: dict, rel: dict, viewer) -> list[dict]:
    rows, confirms = [], rec["outcome"].get("affected_confirms") or []
    for p in rec["people"]["affected"]:
        mine = S._named(p, viewer)
        if not (rel["content"] or mine):
            continue
        c = next((x for x in confirms if x["by"] == _key(p)), None)
        rows.append({"name": p["name"], "mine": mine, "state": c["state"] if c else "waiting", "at": c["at"] if c else None, "comment": c.get("comment") if c else None})
    return rows


def view_of(request: Request, plane, viewer, rec: dict) -> dict:
    rel, out = _rel(rec, viewer, plane), rec["outcome"]
    people_, state, triage, h = rec["people"], rec["state"], out.get("triage"), _h(rec)
    if not triage and out.get("owner_accepted_at") and people_.get("owner"):
        triage = "accepted"  # older records kept only the acceptance date
    stage = STAGE_NAMES.get(_stage_key(rec) or "")
    open_, accepted = state in OPEN, triage == "accepted"
    ext = rec["time_box"].get("extended_by") or []
    prop = out.get("proposed_owner")
    v = {"id": rec["id"], "version": rec["version"], "short_ref": h.get("short_ref"), "title": rec.get("title"), "purpose": rec.get("purpose"), "state": state, "stage": stage, "stage_key": _stage_key(rec),
         "triage": triage, "tz": getattr(L.company_zone(plane), "key", "UTC"), "clock": _clock(plane, rec), "created_at": rec.get("created_at"), "closed_at": (rec.get("closure") or {}).get("closed_at") if state == "closed" else None,
         "reporter": (people_.get("reporter") or {}).get("name"), "owner": (people_.get("owner") or {}).get("name"), "organiser": (people_.get("organiser") or {}).get("name"),
         "tier": "content" if rel["content"] else "outcome" if rel["outcome_only"] else "card", "reads": bool(rel["reads"]),
         "people_count": len({_key(x) for x in [people_.get("reporter"), people_.get("owner"), people_.get("organiser"), *people_["affected"]] if x}),
         "waiting_for": prop["name"] if prop and triage == "waiting" else None, "affected_may_read": bool(rec.get("affected_may_read")), "areas": rec.get("areas"),
         "me": {k: rel[k] for k in ("reporter", "owner", "proposed", "organiser", "admin", "affected")},
         "extended": ({"on": ext[-1]["at"], "reason": ext[-1]["reason"]} if ext and rel["content"] else None), "links": {}}
    if rel["reads"] or rel["outcome_only"]:
        v["as_reported"] = {"what": out.get("what"), "saw": out.get("saw"), "bites": out.get("bites"), "about": out.get("about"), "areas": rec.get("areas"),
                            "affected": [p["name"] for p in people_["affected"]], "reported_at": rec.get("created_at")}
        v["passes"] = [{"from": x["from"], "to": x["to"], "reason": x["reason"], "at": x["at"]} for x in rec.get("passes") or []]
        v["escalated"] = triage == "escalated"
    if rel["triage"]:
        v["triage_note"] = _triage_panels(plane, viewer, rec)
        v["proposed_owner"] = {**{k: prop[k] for k in ("name", "source", "label")}, "picked_by_reporter": rec.get("owner_picked_by") == "reporter"} if prop else None
    v["can"] = {"accept": rel["proposed"] and open_, "pass": rel["proposed"] and open_ and len(rec.get("passes") or []) < 2,
                "assign": rel["admin"] and triage == "escalated" and open_, "redraw": (rel["reporter"] or rel["proposed"]) and triage in ("waiting", "escalated") and open_,
                "extend": rel["owner"] and open_ and accepted and not ext, "change_owner": rel["organiser"] and open_ and accepted}
    al = (rec.get("links") or {}).get("alert")
    if al and rel["reporter"] and lk.alert_state(plane, al) == "open":
        v["alert_line"] = {"id": al}
    if (rec.get("links") or {}).get("from") and rel["content"]:
        v["links"]["from"] = rec["links"]["from"]
    if accepted or state in ("closing", "closed"):
        v.update(_resolution(request, plane, viewer, rec, rel))
    if state == "closed" and (rel["content"] or rel["outcome_only"]):
        v["closed_summary"] = (rec.get("closure") or {}).get("summary") or None
        ref = next((n.get("ref") for n in (rec.get("closure") or {}).get("next") or [] if n.get("kind") == "initiative" and n.get("ref")), None)
        child = S.read_intent(plane, ref) if ref else None
        if child:  # "Became Initiative <title>": the link only for whoever may open it (a draft is its creator's alone)
            v["became"] = {"id": ref, "title": child.get("title") or "", "state": child["state"],
                           "may_open": child["state"] != "draft" or child.get("created_by") == viewer.account_id}
    return v


def _resolution(request: Request, plane, viewer, rec: dict, rel: dict) -> dict:
    out, state, p, h = rec["outcome"], rec["state"], rec["people"], _h(rec)
    r = {"affected": _affected_rows(rec, rel, viewer)}
    rc, fx = _part(out.get("root_cause")), _part(out.get("fix"))  # older records hold plain text
    confirms, n_aff = out.get("affected_confirms") or [], len(p["affected"])
    if rel["reads"] or rel["outcome_only"]:
        r["root_cause"] = rc and {**rc, "confirmed_by": _name(request, rc.get("confirmed_by"))}
        r["fix"] = fx and {**fx, "by": _name(request, fx.get("by")), "accepted_by": _name(request, fx.get("accepted_by"))}
        r["tally"] = {"fixed": sum(c["state"] == "fixed" for c in confirms), "still": sum(c["state"] == "still" for c in confirms), "affected": n_aff, "no_answer": n_aff - len(confirms)}
    elif rel["affected"] and fx:
        r["fix_line"] = f"{(p.get('owner') or {}).get('name') or 'The owner'} did: {str(fx.get('what') or fx.get('reason')).rstrip('.')}, on {datetime.fromisoformat(_date(fx.get('done_at'))).strftime('%d %b').lstrip('0') if _date(fx.get('done_at')) else 'a date to be given'}"
    if rel["reads"]:
        r["what_we_know"] = h.get("what_we_know")
        r["notes"] = [{"id": n["id"], "by": _name(request, n["by"]) if n.get("by") else None, "role": n.get("role"), "at": n["at"], "text": n["text"],
                       "anonymous": n.get("anonymous", False)} for n in h.get("notes") or []]
        r["node"] = _node_of(plane, rec)
        r["north_banner"] = _banner(rec)
    open_, stage = state in OPEN, _stage_key(rec)
    r["can_resolve"] = {
        "draft_cause": rel["owner"] and open_ and stage == "find_cause" and bool(h.get("notes") or (rec["links"] or {}).get("alert")),
        "confirm_cause": rel["owner"] and open_ and stage == "find_cause", "cause_unknown": rel["owner"] and open_ and stage == "find_cause",
        "save_fix": rel["owner"] and open_ and stage in ("fix", "confirm") and bool(rc),
        "note": open_ and (rel["owner"] or rel["reporter"] or rel["participant"] or (rel["affected"] and bool(rec.get("affected_may_read")))),
        "tap": rel["affected"] and open_ and bool(fx) and stage == "confirm", "close": rel["owner"] and open_ and stage == "confirm"}
    r["close_checks"] = _close_checks(rec) if (rel["owner"] or rel["organiser"]) and open_ else None
    if state == "closing":
        waiting = next((x for x in L.confirmers("problem") if x not in {c["role"] for c in (rec["closure"].get("confirmed") or [])}), None)
        r["closing"] = {"waiting": waiting, "summary": rec["closure"].get("summary"), "why": rec["closure"].get("why_it_happened"), "came_out": rec["closure"].get("what_came_out"),
                        "reopened_once": bool(out.get("reopened")), "can_reopen": rel["reporter"] and not out.get("reopened"),
                        "can_confirm_owner": waiting == "owner" and rel["owner"], "can_confirm_reporter": waiting == "reporter" and rel["reporter"],
                        "can_finish": rel["organiser"]}
    return r


def _node_of(plane, rec: dict) -> dict | None:
    nid = (rec.get("links") or {}).get("node")
    if not nid:
        return None
    try:
        nodes = (read_json_strict(plane.path("graph", "company.json"), dict) or {}).get("nodes") or []
    except (OSError, ValueError):
        return None
    n = next((n for n in nodes if n.get("id") == nid), None)
    return {"id": nid, "name": n.get("label") if n else None, "found": bool(n)}


def _banner(rec: dict) -> str | None:
    b, out = _clock(None, rec), rec["outcome"]
    if rec["state"] not in OPEN or not b or b["state"] not in ("at_risk", "overdue"):
        return None
    gaps = [x for x, missing in (("no cause yet", not out.get("root_cause")), ("no fix yet", not out.get("fix"))) if missing]
    lead = "Past the time box" if b["state"] == "overdue" else f"{b['working_days_left']} working days left"
    return lead + (f" and {' and '.join(gaps)}" if gaps else "") + ". Options: extend, close as accepted, cancel."


def _close_checks(rec: dict) -> list[dict]:
    out = rec["outcome"]
    rc, fx = _part(out.get("root_cause")) or {}, _part(out.get("fix")) or {}
    return [{"key": "cause", "ok": bool(rc.get("confirmed_at")), "line": "Confirm the cause, or say it is not known."},
            {"key": "fix", "ok": bool(fx), "line": "Save the fix, or close without a fix."},
            {"key": "affected", "ok": bool(rec["people"]["affected"]), "line": "Name at least one affected person."},
            {"key": "workaround", "ok": fx.get("kind") != "workaround" or bool(fx.get("real_fix_by")), "line": "A workaround needs a real fix date."}]


# ---- start (41) ------------------------------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/problem/start")
def get_start(request: Request, about: str | None = None, alert: str | None = None, item: str | None = None, frm: str | None = Query(None, alias="from")):
    """What the five questions need: the pick lists, the owner chips for `about`, and the prefill from an alert or a check-in item."""
    plane, viewer = _plane(request), _viewer(request)
    cat = lk.catalogue(plane, viewer)
    acc = lk.accounts(request)
    ppl = [{**p, "can_own": p["name"].lower() in acc} for p in lk.people(plane, viewer)]
    base = {"people": ppl, "areas": lk.areas(plane, viewer), "catalogue": cat, "currency": _currency(plane)}
    pre: dict = {"what": None, "about": None, "owner_source": None, "origin": None}
    if alert:
        hit = next((a for a in lk.ops_today(plane, viewer).get("alerts") or [] if a["id"] == alert), None)
        if hit is None:
            return {**base, "chips": [], "prefill": {**pre, "alert_missing": True}}
        title = next((c.get("title") for c in lk._contracts(plane) if c["source"] == hit["source"]), None) or hit["source"]
        words = lk.KIND_WORDS.get(hit["kind"], hit["kind"])
        mid = next((c["id"] for c in cat if hit.get("measure") and lk._norm(lk._code(c["id"])) == lk._norm(hit["measure"])), None)
        pre = {"what": f"{title}: {words}", "about": mid, "owner_source": "source_owner", "alert": alert, "origin": f"Started from: {title}, {words}"}
        about = about or mid
    elif item and frm:
        text = _item_text(plane, frm, item)
        pre = {"what": text, "about": None, "owner_source": None, "origin": "Started from a Weekly check-in item" if text else None, "from": frm, "item": item}
    return {**base, "chips": lk.owner_chips(plane, viewer, about), "prefill": pre}


def _item_text(plane, from_id: str, item_id: str) -> str | None:
    if not S.ID_RE.fullmatch(from_id):
        return None
    for f in sorted(plane.path("intents", from_id, "weeks").glob("*.json")):
        try:
            d = read_json_strict(f, dict)
        except (OSError, ValueError):
            continue
        for it in (d or {}).get("items") or []:
            if it.get("id") == item_id:
                return str(it.get("text") or "")[:WHAT_MAX]
    return None


def _currency(plane) -> str | None:
    try:
        c = ((profile_store.load(plane).get("company") or {}).get("currency") or {}).get("value")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return str(c) if c else None


def _answers(body: dict) -> dict:
    """The five answers, checked. Refuses with the first missing item in plain words."""
    what, saw = _text(body.get("what"), WHAT_MAX), _text(body.get("saw"), SAW_MAX)
    bites = body.get("bites") or {}
    aff = [str(x) for x in body.get("affected") or [] if str(x).strip()]
    areas = [str(x) for x in body.get("areas") or [] if str(x).strip()]
    if not what or not saw:
        raise NO(422, "Say what is wrong, and what you saw.")
    if bites.get("kind") not in BITES:
        raise NO(422, "Say how hard it bites.")
    if not areas or not aff:
        raise NO(422, "Pick an area and name at least one person who feels it.")
    return {"what": what, "saw": saw, "bites": {"kind": bites["kind"], "count": bites.get("count"), "amount": bites.get("amount"), "unit": bites.get("unit")},
            "about": body.get("about") or {"kind": "unknown"}, "owner": body.get("owner") or {}, "areas": areas, "affected": aff,
            "affected_may_read": bool(body.get("affected_may_read")), "alert": body.get("alert") or None, "from": body.get("from") or None, "item": body.get("item") or None}


@router.get("/api/intents/{intent_id}/problem")
def get_problem(intent_id: str, request: Request):
    def go():
        plane, viewer, rec = _get(request, intent_id)
        if rec["state"] == "draft":
            return {"id": rec["id"], "state": "draft", "start_answers": rec.get("start_answers") or {}}
        if rec["state"] == "closed" and "writeback" not in rec["outcome"]:  # until the closure screen calls write_back itself (file 09), the first read does
            rec = _close_out(plane, viewer, rec, request)
        return view_of(request, plane, viewer, rec)
    return _run(request, go)


def _close_out(plane, viewer, rec: dict, request: Request) -> dict:
    def edit(r):
        r["outcome"]["writeback"] = write_back(plane, r, request)
        rep = next((c for c in r["closure"].get("confirmed") or [] if c.get("role") == "reporter"), None)
        r["outcome"].update(confirmed_by=rep and rep["by"], confirmed_at=rep and rep["at"])
    try:
        return S.update_intent(plane, rec["id"], rec["version"], edit)
    except (OSError, ValueError, S.VersionConflict):
        log.exception("write-back for problem %s did not finish; the next read tries again", rec["id"])
        return rec


@router.post("/api/intents/{intent_id}/problem/start")
def post_start(intent_id: str, request: Request, body: dict = Body(default={})):
    """Save the answers on the draft (open false) or open the problem (open true): the reporter's one press."""
    def go():
        plane, viewer = _plane(request), _viewer(request)
        rec0 = S.read_intent(plane, intent_id)
        if rec0 is None or rec0.get("type") != "problem" or rec0["state"] != "draft" or rec0.get("created_by") != viewer.account_id:
            raise LookupError(intent_id)
        now = S.now_iso()
        queue: list = []
        if not body.get("open"):
            def keep(rec):
                rec["start_answers"] = {k: body.get(k) for k in ("what", "saw", "bites", "about", "owner", "areas", "affected", "affected_may_read", "alert", "from", "item", "step")}
                rec["title"] = _text(body.get("what"), WHAT_MAX)
            S.update_intent(plane, intent_id, rec0["version"], keep)
            return {"saved": True, "id": intent_id}
        a = _answers(body)
        summary = _triage_summary(request, plane, a["what"], a["saw"], a.get("about"))

        def edit(rec):
            about_id = (a["about"] or {}).get("id")
            node = next((c for c in lk.catalogue(plane, viewer) if c["id"] == about_id), None) if about_id else None
            a["about"] = {"kind": "measure" if (node or {}).get("group") == "Measures" else "process" if node else "unknown", "id": node["id"] if node else None, "name": node["name"] if node else None}
            picked = _pick_owner(request, plane, a)
            rec.update(title=a["what"], purpose=a["what"], areas=a["areas"], affected_may_read=a["affected_may_read"], opened_by=viewer.account_id,
                       start_answers={"r1": a["what"], "r3": a["bites"]["kind"], "r5": a["areas"]})  # the required start questions are answered: North asks none (spec 08)
            me = L.person(viewer.account_id, viewer.name)
            rec["people"].update(organiser=me, reporter=me, affected=[p for p in (_person(request, plane, x) or L.person(None, x) for x in a["affected"])])
            L.move(rec, "open", viewer.account_id, now, tz=L.company_zone(plane))
            rec["links"].update(alert=a["alert"], node=a["about"]["id"], **({"from": a["from"]} if a["from"] else {}))
            if a["item"]:
                rec["from_item"] = a["item"]
            rec["outcome"] = {"kind": "problem", "what": a["what"], "saw": a["saw"], "about": a["about"], "bites": a["bites"], "accepted_at": None, "accepted_by": None,
                              "assigned_by_admin": False, "triage": "waiting", "proposed_owner": picked}
            if (a["owner"] or {}).get("source") == "reporter":
                rec["owner_picked_by"] = "reporter"
            rec["passes"] = []
            h = _h(rec)
            h.update(short_ref=_next_ref(plane), notes=[])
            _stage_open(rec, "describe", now)
            _grant(rec, picked)
            rec["triage_note"] = _with_summary(lk.triage_refs(plane, viewer, rec, [o for o in _others(plane) if o["id"] != rec["id"]]), summary)
            if _same(picked, me):  # the reporter holds it: no acceptance is asked for (spec 41, open question 12)
                _accept(rec, me, now, assigned=False)
            _redraw_knowledge(rec, now)
            queue.append(("opened", {"type": "problem"}, {}))
        rec = S.update_intent(plane, intent_id, rec0["version"], edit)
        _log(plane, intent_id, viewer, queue)
        return {"id": intent_id, "state": "open", "short_ref": _h(rec)["short_ref"]}
    return _run(request, go)


def _pick_owner(request: Request, plane, a: dict) -> dict:
    """The proposed owner as `{account_id, name, source, label}`: the reporter's pick, else the best chip, else the company admin."""
    own, viewer = a["owner"] or {}, _viewer(request)
    if own.get("name") and own.get("source") in ("business_owner", "source_owner", "data_owner", "reporter"):
        hit = _person(request, plane, own["name"], need_account=True)
        if hit:
            return {**hit, "source": own["source"], "label": lk.SOURCE_LABELS[own["source"]]}
    for c in lk.owner_chips(plane, viewer, a["about"].get("id")):
        hit = _person(request, plane, c["name"], need_account=True)
        if hit:
            return {**hit, "source": c["source"], "label": c["label"]}
    adm = _admin(request) or L.person(None, "the company admin")
    return {**adm, "source": "admin", "label": lk.SOURCE_LABELS["admin"]}


# ---- triage (41) ---------------------------------------------------------------------------------------------------------------------------------------

def _accept(rec: dict, who: dict, now: str, assigned: bool, owner: dict | None = None) -> None:
    out = rec["outcome"]
    owner = owner or who
    rec["people"]["owner"] = L.person(owner.get("account_id"), owner["name"])
    rec["people"]["participants"] = [x for x in rec["people"]["participants"] if not _same(x, owner)]
    for e in rec.get("people_detail") or []:  # the people list (file 06) rebuilds `people` from its roles: the proposed owner's row becomes the owner's
        if owner.get("account_id") and e.get("person_id") == owner["account_id"] and e.get("role") == "participant":
            e.update(role="owner", status="joined", joined_at=e.get("joined_at") or now)
    out.update(triage="accepted", accepted_at=now, accepted_by=who.get("account_id") or who.get("name"), assigned_by_admin=assigned)
    _move(rec, "find_cause", now)
    _redraw_knowledge(rec, now)


@router.post("/api/intents/{intent_id}/triage/accept")
def post_accept(intent_id: str, request: Request):
    def check(rec, rel, viewer):
        _open_only(rec)
        _need(rel, "proposed")

    def change(rec, viewer, now, q):
        _accept(rec, L.person(viewer.account_id, viewer.name), now, False)
        q += [("joined", {"role": "owner", "how": "accepted"}, {"stage": "describe"}), ("stage_opened", {"stage": "find_cause"}, {})]
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/triage/pass")
def post_pass(intent_id: str, request: Request, body: dict = Body(default={})):
    to, reason = None, _text(body.get("reason"), 300)

    def check(rec, rel, viewer):
        nonlocal to
        _open_only(rec)
        _need(rel, "proposed")
        if len(rec.get("passes") or []) >= 2 or rec["outcome"].get("triage") != "waiting":
            raise NO(409, "This problem has been passed twice. The company admin picks the owner.")
        if len(reason) < REASON_MIN:
            raise NO(422, "Name who should own this and say why, in at least 10 characters.")
        to = _person(request, _plane(request), body.get("to"), need_account=True)
        if to is None:
            raise NO(422, "Name who should own this and say why.")
        if _same(to, L.person(viewer.account_id, viewer.name)) or _same(to, rec["people"]["reporter"]):
            raise NO(422, "Pick someone other than yourself and the reporter.")

    def change(rec, viewer, now, q):
        n = len(rec["passes"]) + 1
        rec["passes"].append({"from": viewer.name, "from_id": viewer.account_id, "to": to["name"], "to_id": to.get("account_id"), "reason": reason, "at": now})
        if n >= 2:
            rec["outcome"].update(triage="escalated", proposed_owner=None)
            _grant(rec, _admin(request))
        else:
            rec["outcome"]["proposed_owner"] = {**to, "source": "passed", "label": f"Passed on by {viewer.name}"}
            _grant(rec, to)
        q.append(("person_invited", {"role": "owner"}, {}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/triage/assign")
def post_assign(intent_id: str, request: Request, body: dict = Body(default={})):
    to = None

    def check(rec, rel, viewer):
        nonlocal to
        _open_only(rec)
        _need(rel, "admin")
        if rec["outcome"].get("triage") != "escalated":
            raise NO(409, "Only a problem that was passed twice is assigned.")
        to = _person(request, _plane(request), body.get("to"), need_account=True)
        if to is None:
            raise NO(422, "Pick the owner.")

    def change(rec, viewer, now, q):
        _accept(rec, L.person(viewer.account_id, viewer.name), now, True, owner=to)
        q.append(("joined", {"role": "owner", "how": "assigned"}, {"stage": "describe"}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/triage/refresh")
def post_refresh(intent_id: str, request: Request):
    def check(rec, rel, viewer):
        _open_only(rec)
        if not (rel["reporter"] or rel["proposed"]):
            raise NO(403, FORBIDDEN)
        if rec["outcome"].get("triage") not in ("waiting", "escalated"):
            raise NO(409, "The note is only redrawn while the problem waits for an owner.")
        if (rec.get("triage_note") or {}).get("drafted_at", "") >= rec["updated_at"]:
            raise NO(409, "The note is up to date.")

    summary = None
    try:  # North drafts before the lock, only for a person who may redraw
        plane, viewer, rec0 = _get(request, intent_id)
        check(rec0, _rel(rec0, viewer, plane), viewer)
        o = rec0["outcome"]
        summary = _triage_summary(request, plane, o.get("what") or "", o.get("saw") or "", o.get("about"))
    except Exception:  # noqa: BLE001 - _mutate below refuses with the right answer
        pass

    def change(rec, viewer, now, q):
        plane = _plane(request)
        rec["triage_note"] = _with_summary(lk.triage_refs(plane, viewer, rec, [o for o in _others(plane) if o["id"] != rec["id"]]), summary)
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/extend")
def post_extend(intent_id: str, request: Request, body: dict = Body(default={})):
    """The owner extends the time box once, with a reason (spec 41, open question 5)."""
    days, reason = body.get("days"), _text(body.get("reason"), 300)

    def check(rec, rel, viewer):
        _open_only(rec)
        _need(rel, "owner")
        if rec["time_box"].get("extended_by"):
            raise NO(409, "This problem has been extended once. Close it, or ask the company admin.")
        if days not in EXTEND_CHOICES or isinstance(days, bool):
            raise NO(422, "Choose 1, 2, 3 or 5 working days.")
        if len(reason) < REASON_MIN:
            raise NO(422, "Say why, in at least 10 characters.")

    def change(rec, viewer, now, q):
        was = rec["time_box"]["ends"]
        rec["time_box"]["ends"] = L.add_working_days(clock.parse(was), days).isoformat()
        rec["time_box"]["extended_by"].append({"by": viewer.account_id, "at": now, "reason": reason, "days": days, "status": "approved"})
        for s in rec["stages"]:
            if s.get("due") and s["state"] == "open":
                s["due"] = min(L.add_working_days(clock.parse(s["due"]), days), clock.parse(rec["time_box"]["ends"])).isoformat()
        q.append(("extended", {"old_end": was[:10], "new_end": rec["time_box"]["ends"][:10]}, {}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/owner")
def post_owner(intent_id: str, request: Request, body: dict = Body(default={})):
    to = None

    def check(rec, rel, viewer):
        nonlocal to
        _open_only(rec)
        _need(rel, "organiser")
        to = _person(request, _plane(request), body.get("to"), need_account=True)
        if to is None:
            raise NO(422, "Pick the new owner.")

    def change(rec, viewer, now, q):
        was = (rec["people"].get("owner") or {}).get("name") or "nobody"
        rec["people"]["owner"] = to
        _note(rec, None, "organiser", f"Owner changed from {was} to {to['name']}", now, system=True)
        q.append(("person_invited", {"role": "owner"}, {}))
    return _mutate(request, intent_id, check, change)


# ---- notes and what we know (42) --------------------------------------------------------------------------------------------------------------------

def _note(rec: dict, who_id, role: str, text: str, now: str, system=False, anonymous=False) -> dict:
    h = _h(rec)
    n = {"id": f"n{len(h.setdefault('notes', [])) + 1}", "by": None if anonymous else who_id, "role": "anonymous" if anonymous else role, "at": now, "text": text,
         "ref": None, "anonymous": anonymous, "system": system}
    h["notes"].append(n)
    _redraw_knowledge(rec, now)
    return n


def _redraw_knowledge(rec: dict, now: str) -> None:
    """What we know, redrawn from the statement and the notes. Plain: one sentence per source, each with its source label; a pinned one is kept."""
    h, out = _h(rec), rec["outcome"]
    old = {s["source_ref"]["id"]: s for s in (h.get("what_we_know") or {}).get("sentences") or [] if s.get("pinned")}
    sents = [{"text": f"{out['what']}.".replace("..", "."), "source_ref": {"kind": "statement", "id": "statement", "label": "The report"}, "pinned": False}]
    if (rec.get("links") or {}).get("alert"):
        sents.append({"text": f"This came from the Ops alert {rec['links']['alert']}.", "source_ref": {"kind": "alert", "id": rec["links"]["alert"], "label": "Ops alert"}, "pinned": False})
    for n in [x for x in h.get("notes") or [] if not x.get("system")][-4:]:
        first = re.split(r"(?<=[.!?])\s", n["text"].strip(), maxsplit=1)[0][:200]
        sents.append({"text": first, "source_ref": {"kind": "note", "id": n["id"], "label": f"{'Note without a name' if n.get('anonymous') else 'Note by the ' + n['role']}, {datetime.fromisoformat(n['at']).strftime('%d %b').lstrip('0')}"}, "pinned": False})
    h["what_we_know"] = {"text": " ".join(s["text"] for s in sents), "sentences": [old.get(s["source_ref"]["id"], s) for s in sents], "drafted_at": now}


@router.post("/api/intents/{intent_id}/problem/note")
def post_note(intent_id: str, request: Request, body: dict = Body(default={})):
    text, anon = _text(body.get("text"), NOTE_MAX), bool(body.get("anonymous"))

    def check(rec, rel, viewer):
        _open_only(rec)
        if not (rel["owner"] or rel["reporter"] or rel["participant"] or (rel["affected"] and rec.get("affected_may_read"))):
            raise NO(403, FORBIDDEN)
        if not text:
            raise NO(422, "Write the note first.")

    def change(rec, viewer, now, q):
        rel = _rel(rec, viewer, _plane(request))
        role = "owner" if rel["owner"] else "reporter" if rel["reporter"] else "affected" if rel["affected"] else "participant"
        _note(rec, viewer.account_id, role, text, now, anonymous=anon)
        q.append(("card_added", {"lane": "note"}, {"anonymous": anon} if anon else {}))
    return _mutate(request, intent_id, check, change)


# ---- cause, fix, taps (42) -----------------------------------------------------------------------------------------------------------------------------

@router.post("/api/intents/{intent_id}/problem/cause")
def post_cause(intent_id: str, request: Request, body: dict = Body(default={})):
    action, text, reason = body.get("action"), _text(body.get("text"), TEXT_MAX), _text(body.get("reason"), 300)

    def check(rec, rel, viewer):
        _open_only(rec)
        _need(rel, "owner")
        if _stage_key(rec) != "find_cause":
            raise NO(409, "The cause is settled at the Find the cause stage.")
        if action not in ("draft", "confirm", "unknown"):
            raise NO(422, "Choose draft, confirm or unknown.")
        if action == "draft" and not (_h(rec).get("notes") or rec["links"].get("alert")):
            raise NO(422, "Add a note first.")
        if action == "confirm" and not text:
            raise NO(422, "Draft or write a cause first.")
        if action == "unknown" and len(reason) < REASON_MIN:
            raise NO(422, "Say why the cause is not known, in at least 10 characters.")

    drafted = None
    if action == "draft":
        try:  # North drafts before the lock, only for the owner at the right stage
            plane, viewer, rec0 = _get(request, intent_id)
            check(rec0, _rel(rec0, viewer, plane), viewer)
            drafted = _cause_draft(request, plane, rec0)
        except Exception:  # noqa: BLE001 - _mutate below refuses with the right answer
            pass

    def change(rec, viewer, now, q):
        out, h = rec["outcome"], _h(rec)
        if action == "draft" and drafted:
            out["root_cause"] = {**drafted, "drafted_by_north": True, "fallback": False, "confirmed_by": None, "confirmed_at": None, "unknown": False, "reason": None}
            q.append(("north_drafted", {"draft_of": "stage_summary"}, {}))
            return
        if action == "draft":
            notes = [n for n in h.get("notes") or [] if not n.get("system")][-4:]
            al = rec["links"].get("alert")
            lead = f"The Ops alert {al} is open. " if al else ""
            body_ = " ".join(re.split(r"(?<=[.!?])\s", n["text"], maxsplit=1)[0] for n in notes)
            out["root_cause"] = {"text": f"{lead}{body_}".strip(), "drafted_by_north": True, "confirmed_by": None, "confirmed_at": None,
                                 "based_on": [n["id"] for n in notes] + ([al] if al else []), "unknown": False, "reason": None, "questions": QUESTIONS, "fallback": True}
            q.append(("north_drafted", {"draft_of": "stage_summary"}, {}))
            return
        prev = out.get("root_cause") or {}
        if action == "confirm":
            out["root_cause"] = {**prev, "text": text, "drafted_by_north": bool(prev.get("drafted_by_north")) and text == prev.get("text"), "confirmed_by": viewer.account_id,
                                 "confirmed_at": now, "unknown": False, "reason": None, "based_on": prev.get("based_on") or []}
        else:
            out["root_cause"] = {"text": f"Not known: {reason}", "drafted_by_north": False, "confirmed_by": viewer.account_id, "confirmed_at": now, "based_on": [], "unknown": True, "reason": reason}
        _move(rec, "fix", now)
        q += [("signed", {"what": "root_cause"}, {"stage": "find_cause"}), ("stage_opened", {"stage": "fix"}, {})]
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/fix")
def post_fix(intent_id: str, request: Request, body: dict = Body(default={})):
    kind, by = body.get("kind"), None
    what, reason = _text(body.get("what"), TEXT_MAX), _text(body.get("reason"), 300)
    done, real = _date(body.get("done_at")), _date(body.get("real_fix_by"))
    today = datetime.now(timezone.utc).date().isoformat()

    def check(rec, rel, viewer):
        nonlocal by
        _open_only(rec)
        _need(rel, "owner")
        plane = _plane(request)
        if not (rec["outcome"].get("root_cause") or {}).get("confirmed_at"):
            raise NO(409, "Confirm the cause first.")
        if _stage_key(rec) not in ("fix", "confirm"):
            raise NO(409, "The fix is saved after the cause.")
        if kind == "accepted_no_fix":
            by = _person(request, plane, body.get("accepted_by")) or L.person(viewer.account_id, viewer.name)
            if len(reason) < REASON_MIN:
                raise NO(422, "Say why, in at least 10 characters.")
            return
        if kind not in ("fixed", "workaround"):
            raise NO(422, "Choose fixed or workaround.")
        by = _person(request, plane, body.get("by"))
        if not what or not by or not done:
            raise NO(422, "Say what was done, by whom, and when.")
        if kind == "fixed" and done > today:
            raise NO(422, "A fix cannot be dated in the future.")
        if kind == "workaround" and not (real and real > today):
            raise NO(422, "A workaround needs a real fix date after today.")

    def change(rec, viewer, now, q):
        out = rec["outcome"]
        who = by.get("account_id") or by["name"]
        if kind == "accepted_no_fix":
            fx = {"kind": kind, "what": None, "by": None, "done_at": None, "real_fix_by": None, "accepted_by": who, "reason": reason, "text": f"Closed without a fix: {reason}"}
        else:
            fx = {"kind": kind, "what": what, "by": who, "done_at": done, "real_fix_by": real if kind == "workaround" else None, "accepted_by": None, "reason": None,
                  "text": what if kind == "fixed" else f"Workaround: {what.rstrip('.')}. Real fix by {real}"}
        out["fix"], out["affected_confirms"] = fx, []
        if _stage_key(rec) == "fix":
            _move(rec, "confirm", now)
            q.append(("stage_opened", {"stage": "confirm"}, {}))
        q.append(("signed", {"what": "fix"}, {"stage": "fix"}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/confirm-tap")
def post_tap(intent_id: str, request: Request, body: dict = Body(default={})):
    state, comment = body.get("state"), _text(body.get("comment"), 300)

    def check(rec, rel, viewer):
        _open_only(rec)
        _need(rel, "affected")
        if not rec["outcome"].get("fix"):
            raise NO(409, "Waiting for the fix.")
        if state not in ("fixed", "still"):
            raise NO(422, "Choose fixed for me, or still happening for me.")
        if state == "still" and not comment:
            raise NO(422, "Say in one sentence what is still happening.")

    def change(rec, viewer, now, q):
        mine = next(_key(x) for x in rec["people"]["affected"] if S._named(x, viewer))
        rows = [c for c in rec["outcome"].setdefault("affected_confirms", []) if c["by"] != mine]
        rows.append({"by": mine, "state": state, "at": now, "comment": comment or None})
        rec["outcome"]["affected_confirms"] = rows
        if state == "still":
            _note(rec, None, "affected", f"{viewer.name} says it is still happening: {comment}", now, system=True)
        q.append(("question_answered", {"question_key": "confirm_tap"}, {}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/close")
def post_close(intent_id: str, request: Request, body: dict = Body(default={})):
    """The owner's "Close and send for confirmation" (spec 42 screen B): the closure drafted from the cause and the fix, the owner's
    confirmation recorded, the problem moved to `closing` for the reporter. The organiser's final close is file 09's (ruling 25)."""
    def check(rec, rel, viewer):
        _open_only(rec)
        _need(rel, "owner")
        if _stage_key(rec) != "confirm":
            raise NO(409, "Save the fix first.")
        miss = next((c["line"] for c in _close_checks(rec) if not c["ok"]), None)
        if miss:
            raise NO(409, miss)

    def change(rec, viewer, now, q):
        out = rec["outcome"]
        why, came = (out.get("root_cause") or {}).get("text") or "", (out.get("fix") or {}).get("text") or ""
        rec["closure"] = {**L.blank_closure(viewer.account_id), "summary": _text(body.get("summary"), 300) or f"{out['what']}. {came}".strip(),
                          "why_it_happened": why, "what_came_out": came, "confirmed": [{"role": "owner", "by": viewer.account_id, "at": now}]}
        rec["state"] = "closing"
        rec["history"].append({"at": now, "by": viewer.account_id, "from": "open", "to": "closing", "note": "owner closed, waiting for the reporter"})
        q.append(("state_changed", {"from": "open", "to": "closing"}, {}))
    return _mutate(request, intent_id, check, change)


@router.post("/api/intents/{intent_id}/problem/to-initiative")
def post_to_initiative(intent_id: str, request: Request, body: dict = Body(default={})):
    """"This is bigger than a fix" (spec 42, journey 53 branch B): the owner or organiser says what is bigger, the problem closes as a named
    closure kind with `next: [{kind: initiative, reason}]` (no fix and no reporter confirmation needed), and the closure's own child step
    writes the Initiative draft, pre-filled and linked on both records. The answer carries the draft's start route."""
    reason = _text(body.get("reason"), 300)

    def check(rec, rel, viewer):
        _open_only(rec)
        if not (rel["owner"] or rel["organiser"]):
            raise NO(403, FORBIDDEN)
        if len(reason) < REASON_MIN:
            raise NO(422, "Say what is bigger about it, in at least 10 characters.")

    def change(rec, viewer, now, q):
        rec["closure"] = {**L.blank_closure(viewer.account_id), "kind": "bigger_than_fix", "closed_by": viewer.account_id, "closed_at": now,
                          "summary": f"Closed as bigger than a fix: {reason}", "why_it_happened": (rec["outcome"].get("root_cause") or {}).get("text") or "",
                          "what_came_out": "Handed to an Initiative", "next": [{"kind": "initiative", "reason": reason, "ref": None}]}
        _note(rec, viewer.account_id, "owner" if _rel(rec, viewer, _plane(request))["owner"] else "organiser",
              f"{viewer.name} closed this as bigger than a fix and turned it into an Initiative: {reason}", now, system=True)
        _stage_shut(rec, now)
        rec["state"] = "closed"
        rec["history"].append({"at": now, "by": viewer.account_id, "from": "open", "to": "closed", "note": "closed as bigger than a fix"})
        q.append(("state_changed", {"from": "open", "to": "closed"}, {}))

    answer = _mutate(request, intent_id, check, change)
    if isinstance(answer, JSONResponse):
        return answer
    from sh_platform.intents import closure  # the close follow-ons of ruling R11, the Initiative draft among them
    plane, viewer = _plane(request), _viewer(request)
    rec = closure._after_close(plane, S.read_intent(plane, intent_id), viewer, request)
    ref = next((n.get("ref") for n in rec["closure"]["next"] if n["kind"] == "initiative"), None)
    return {**view_of(request, plane, viewer, rec), "url": f"/centre/intent/new?type=initiative&draft={ref}&from={intent_id}" if ref else f"/centre/intent/{intent_id}"}


# ---- reopen and write-back (42) --------------------------------------------------------------------------------------------------------------------------

@router.post("/api/intents/{intent_id}/problem/reopen")
def post_reopen(intent_id: str, request: Request, body: dict = Body(default={})):
    """The reporter reopens a problem that is waiting for confirmation, once. The second time is a new Problem."""
    reason, stage = _text(body.get("reason"), 600), body.get("stage")

    def check(rec, rel, viewer):
        if rec["state"] != "closing":
            raise NO(409, "Only a problem waiting for your answer can be reopened.")
        _need(rel, "reporter")
        if rec["outcome"].get("reopened"):
            raise NO(409, "Reopened once already. Start a new Problem.")
        if stage not in ("find_cause", "fix"):
            raise NO(422, "Choose Find the cause or Fix.")
        if not reason:
            raise NO(422, "Say what is still wrong.")

    def change(rec, viewer, now, q):
        out = rec["outcome"]
        out["reopened"] = [{"by": viewer.account_id, "at": now, "reason": reason}]
        if stage == "find_cause":
            out["root_cause"] = None
        out["fix"], out["affected_confirms"] = None, []
        rec["state"] = "open"
        rec["closure"] = {**rec["closure"], "confirmed": [], "signed": False, "closed_by": None, "closed_at": None}
        rec["time_box"]["ends"] = L.add_working_days(clock.parse(now), REOPEN_DAYS).isoformat()  # drafted figure, spec 42 open question 4
        rec["history"].append({"at": now, "by": viewer.account_id, "from": "closing", "to": "open", "note": f"reopened: {reason}"[:200]})
        _note(rec, viewer.account_id, "reporter", f"Reopened: {reason}", now, system=True)
        _move(rec, stage, now)
        q.append(("state_changed", {"from": "closing", "to": "open"}, {}))
    return _mutate(request, intent_id, check, change)


def write_back(plane, rec: dict, request: Request | None = None) -> dict:
    """On `closed`: the version note on the measure or process node, and the Ops alert acknowledged with the link. Idempotent. The author is the
    owner, never North. The closure screen (file 09) can call this when it closes a problem; until then the first read of a closed problem does."""
    out, ref, h = rec["outcome"], f"problem:{rec['id']}", _h(rec)
    owner = (rec["people"].get("owner") or {}).get("name") or "the owner"
    done: dict = {}
    node = (rec.get("links") or {}).get("node")
    if node and out.get("fix"):  # closed as bigger than a fix: nothing was fixed, no version note
        rows = (read_json_strict(plane.path("graph", "versions.json"), dict) or {}).get(node)
        if not _node_of(plane, rec)["found"]:
            done["node"] = "not_found"
        elif any(r.get("ref") == ref for r in rows or []):
            done["node"] = "written"
        else:
            day = datetime.now(timezone.utc).strftime("%d %b").lstrip("0")
            fx = out.get("fix") or {}
            what = (f"Problem {h['short_ref']} closed without a fix on {day}" if fx.get("kind") == "accepted_no_fix"
                    else f"Problem {h['short_ref']} {'fixed' if fx.get('kind') == 'fixed' else 'worked around'} on {day}")
            graph_versions.append_version(plane, node, what, owner, ref)
            done["node"] = "written"
    alert = (rec.get("links") or {}).get("alert")
    if alert:
        if lk.alert_state(plane, alert) == "open":
            store_alerts.act(plane, alert, "ack", owner, f"Problem {h['short_ref']}: /centre/intent/{rec['id']}")
        done["alert"] = "acknowledged"
    return done
