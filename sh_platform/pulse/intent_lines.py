"""Pulse lines for intents (spec 13, 45): derived on every read from intents/<id>/intent.json, the week files and events.jsonl.
Nothing is stored and no line is marked done: a line goes the moment its record stops saying so. One line per person per intent
(the order in PRIORITY); the organiser's "not answered" count (row 16) is separate. Row 7 (charter signature) and the wall rows for an
Initiative are the existing lines in lines.py, so an Initiative makes no row 1, 7 or 16 here."""
import contextvars
import json
import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sh_platform.intents.clock import clock as time_box_clock, overdue_words, parse, working_days
from sh_platform.intents.types import load_catalogue
from sh_platform.profile import view

log = logging.getLogger(__name__)
MINUTES = {"invite": 5, "decision": 3, "request": 5, "signature": 5, "rating": 1, "clock": 2, "outcome": 2}
RATING_DAYS, OUTCOME_CHARS, QUESTION_CAP = 7, 140, 3  # placeholders in one place (spec 13 open questions 4, 11; ruling 9)
NOT_INTENTS = frozenset({"m1_intent", "m2_baseline", "m3_connect", "opportunities"})
LIVE = ("open", "in_session")
PRIORITY = ["closesign", "closeit", "invitation", "decide", "overdue", "turn", "owner", "vote", "card", "definition", "signature", "process", "start",
            "clock", "week", "invite", "wallcards", "rating", "outcome"]
SIGN_FIRST = {"closesign", "signature"}  # group 0 on the Intent home strip (spec 45): signatures, then decisions, then questions, then ratings
GROUP = {**dict.fromkeys(SIGN_FIRST, 0), **dict.fromkeys(["closeit", "decide", "overdue", "turn", "owner", "vote", "clock"], 1),
         **dict.fromkeys(["card", "definition", "process", "start", "week", "invite", "invitation", "wallcards", "people"], 2), "rating": 3, "outcome": 3}
# type: (action for row 1, what the quiet people have not done)
OWES = {"brainstorm": ("Add your ideas", "added ideas"), "initiative": ("Open the wall", "added ideas"), "decision": ("Give your view", "given a view"),
        "problem": ("Add what you know", "added what they know"), "pulse": ("Answer three questions", "answered")}
TURN = {("brainstorm", "choose"): "Choose the idea", ("pulse", "review"): "Read the week", ("pulse", "sort"): "Give each item a fate",
        ("problem", "find_cause"): "Add the cause", ("problem", "fix"): "Name the fix", ("problem", "confirm"): "Confirm it is gone",
        ("decision", "options"): "Give your view", ("initiative", "build_ready"): "Check the build-ready list"}
TURN_VIEW = {("pulse", "review"): "/review", ("pulse", "sort"): "/review", ("initiative", "build_ready"): "/build-ready"}
CONFIRMERS = {"initiative": ("sponsor",), "decision": ("decider",), "problem": ("owner", "reporter")}


def _json(path: Path, empty=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def intents(plane) -> list[dict]:
    """Every intent record in the plane, read by path (the m1, m2, m3 folders and the opportunities are not intents)."""
    try:
        folders = sorted(p for p in plane.path("intents").iterdir() if p.is_dir() and p.name not in NOT_INTENTS and not p.name.startswith("_"))
    except OSError:
        return []
    return [r for r in (_json(p / "intent.json") for p in folders) if isinstance(r, dict) and r.get("id")]


_MEMO: contextvars.ContextVar = contextvars.ContextVar("pulse_memo", default=None)


def records(plane) -> list[dict]:
    """`intents(plane)`, read once per Pulse request and shared by every reader in it (read-only); outside a request, read now."""
    memo = _MEMO.get()
    if memo is None:
        return intents(plane)
    if "intents" not in memo:
        memo["intents"] = intents(plane)
    return memo["intents"]


def _ids(ref) -> set[str]:
    """The ways a people slot can name someone: an account id or a display name, a string or {account_id, name}."""
    items = [ref.get("account_id"), ref.get("name")] if isinstance(ref, dict) else [ref]
    return {view.norm(i) for i in items if isinstance(i, str) and i.strip()}


def _me(ref, v: view.Viewer) -> bool:
    keys = _ids(ref)
    return bool(keys) and ((bool(v.account_id) and view.norm(v.account_id) in keys) or (not v.shared_name and view.norm(v.name) in keys))


def _in(refs, v: view.Viewer) -> bool:
    return any(_me(r, v) for r in refs or [])


def _slot(rec: dict, key: str):
    return (rec.get("people") or {}).get(key)


def _stage(rec: dict) -> dict | None:
    return next((s for s in rec.get("stages") or [] if s.get("state") == "open"), None) or next(
        (s for s in rec.get("stages") or [] if s.get("opened_at") and not s.get("closed_at")), None)


def _cat(rec: dict) -> dict:
    return load_catalogue()["types"].get(rec.get("type"), {})


def _stage_due(rec: dict, s: dict | None):
    """The end of the open stage: its own `due`, else its opening plus the catalogue's days; None when neither is on record."""
    if not s:
        return None
    if s.get("due"):
        return str(s["due"])[:10]
    days = next((x.get("default_days") for x in _cat(rec).get("stages", []) if x.get("key") == s.get("key")), None)
    return working_days(parse(s["opened_at"]), int(days)).date().isoformat() if days and s.get("opened_at") else None


def _title(rec: dict) -> str:
    return str(rec.get("title") or "").strip() or f"your {_cat(rec).get('title', 'intent').lower()}"


def _type(rec: dict) -> str:
    return _cat(rec).get("title", "intent")


def _date(d) -> str:
    t = datetime.fromisoformat(str(d)[:10])
    return f"{t:%a} {t.day} {t:%b}"


def _row(rec: dict, trig: str, kind: str, strip: str, title: str, detail: str, action: str, at, due=None, view_path: str = "", href: str | None = None):
    base = f"/centre/intent/{rec['id']}"
    return trig, strip, {"id": f"intent:{rec['id']}:{trig}", "kind": kind, "title": title, "detail": detail, "href": href or base + view_path,
                         "action": action, "minutes": MINUTES[kind], "due": str(due)[:10] if due else None,
                         "source": {"record": f"intents/{rec['id']}", "at": str(at) if at else None}}


# ---- who has acted in the open stage
def _events(plane, rec: dict) -> list[dict]:
    try:
        text = plane.path("intents", rec["id"], "events.jsonl").read_text(encoding="utf-8")
    except OSError:
        return []
    return [e for e in (_json_line(x) for x in text.splitlines()) if isinstance(e, dict)]


def _json_line(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


def not_acted(plane, rec: dict) -> dict:
    """The people in the open stage who have no act of their own in it (events since it opened, and an adviser's notes).
    Anonymous acts are counted, never named: `anonymous` says some exist. Returns {people: [ref], total, stage, since, anonymous}."""
    s = _stage(rec)
    p = rec.get("people") or {}
    pool = [*(p.get("participants") or []), *(p.get("advisers") or [])] if rec.get("type") == "decision" else list(p.get("participants") or [])
    if not s or rec.get("state") not in LIVE:
        return {"people": [], "total": len(pool), "stage": s, "since": None, "anonymous": False}
    since = s.get("opened_at") or ""
    acted, anon = set(), False
    for e in _events(plane, rec):
        if e.get("agent") or e.get("status") == "draft" or str(e.get("at") or "") < since:
            continue
        by = e.get("by") or {}
        if e.get("anonymous"):
            anon = True
        elif by:
            acted |= {view.norm(x) for x in (by.get("account"), by.get("name")) if x}
    for o in (rec.get("outcome") or {}).get("options") or []:
        acted |= {view.norm(n.get("by")) for n in o.get("notes") or [] if isinstance(n, dict) and n.get("by") and n.get("by") != "anonymous"}
    quiet = [r for r in pool if not (_ids(r) & acted)]
    return {"people": quiet, "total": len(pool), "stage": s, "since": since or None, "anonymous": anon}


# ---- the rows, each (record, viewer, now, ctx) -> iterable of (trigger, strip, line)
def _week(plane, rec: dict) -> dict | None:
    try:
        files = sorted(plane.path("intents", rec["id"], "weeks").glob("*.json"))
    except OSError:
        return None
    return next((w for w in (_json(f) for f in reversed(files)) if isinstance(w, dict) and w.get("state") in ("collect", "open") and not w.get("closed_at")), None)


def _answerable(plane, w: dict, now: datetime) -> bool:
    """Answers are still open: the same test the check-in route applies (collect, today inside opens..answers_close in the company's zone)."""
    from sh_platform.intents.lifecycle import company_zone
    today = now.astimezone(company_zone(plane)).date().isoformat()
    return w.get("state") in ("collect", "open") and (not w.get("opens") or w["opens"] <= today) and (not w.get("answers_close") or today <= w["answers_close"])


def _week_acted(w: dict, v: view.Viewer) -> bool:
    return _in([i.get("by") for i in w.get("items") or []] + [a.get("account_id") for a in w.get("answers") or []], v)


def _confirmed(rec: dict, who: str) -> bool:
    """The confirmer in this slot has acted: closure.confirmed holds {role, ...} (spec 09), a signature is also read from signed or signed_by."""
    c = rec.get("closure") or {}
    return who in {x.get("role") for x in c.get("confirmed") or [] if isinstance(x, dict)} or (who in ("sponsor", "decider") and bool(c.get("signed") or c.get("signed_by")))


def _rows(plane, rec: dict, v: view.Viewer, now: datetime):
    t, state, kind = _type(rec), rec.get("state"), rec.get("type")
    stage, at = _stage(rec), rec.get("updated_at")
    due, T, init = _stage_due(rec, _stage(rec)), _title(rec), rec.get("type") == "initiative"
    org, p = _me(_slot(rec, "organiser"), v), rec.get("people") or {}
    part = _in(p.get("participants"), v) or (kind == "decision" and _in(p.get("advisers"), v))
    box, c = rec.get("time_box") or {}, rec.get("closure") or {}
    if state == "draft":
        if v.account_id and rec.get("created_by") == v.account_id:
            left = sum(1 for q in _cat(rec).get("start_questions", []) if q.get("required") and not any(
                (rec.get("start_answers") or {}).get(k) for k in [q["id"], *(q.get("fields") or [])]))
            if left:
                yield _row(rec, "start", "decision", "decide", f"Finish starting {T}", f"{left} question{' is' if left == 1 else 's are'} left. "
                           "North cannot plan the work until they are answered.", "Answer them", at,
                           href=f"/centre/intent/new?type={kind}&draft={rec['id']}")
        return
    if state == "closing":
        if kind == "pulse":
            w = next((w for w in (_json(f) for f in sorted(plane.path("intents", rec["id"], "weeks").glob("*.json"))) if isinstance(w, dict) and w.get("state") == "closing"), None)
            if w and _me((rec.get("series") or {}).get("reviewer"), v):
                yield _row(rec, "closesign", "signature", "decide", f"{T} is ready to close", "North drafted why it happened and what came out. Read it, then close it.",
                           "Review and close", w.get("closes") or at, view_path="/review")
        else:
            todo = next((s for s in CONFIRMERS.get(kind, ()) if not _confirmed(rec, s)), None)
            if todo and _me(_slot(rec, todo), v):
                yield _row(rec, "closesign", "signature", "decide", f"{T} is ready to close", "North drafted why it happened and what came out. Read it, then close it.",
                           "Review and close", at, view_path="/close")
            if not todo and org:
                yield _row(rec, "closeit", "decision", "decide", f"Close {T}", "All confirmers have acted. Close the intent.", "Close it", at, view_path="/close")
        return
    if state == "closed" and kind != "pulse":
        closed = c.get("closed_at")
        if part and closed and parse(closed) + timedelta(days=RATING_DAYS) > now and not any(
                _ids(r.get("by")) & _ids(v.account_id) for r in rec.get("ratings") or [] if isinstance(r, dict)):
            yield _row(rec, "rating", "rating", "give", f"How did {T} go?", "Give a rating from 1 to 5 and a line if you wish. You may rate without your name.",
                       "Rate it", closed, (parse(closed) + timedelta(days=RATING_DAYS)).date(), view_path="/close#rate")
        named = any(_me(x.get("person_id"), v) and not x.get("revoked_at") for x in (rec.get("share") or {}).get("who_may_open") or [] if isinstance(x, dict))
        if not part and c.get("summary") and (named or (rec.get("affected_may_read") and _in(p.get("affected"), v))):
            yield _row(rec, "outcome", "outcome", "watch", f"Shared with you: {T}", str(c["summary"])[:OUTCOME_CHARS], "Read what came out", closed or at, view_path="/share")
        return
    if state not in LIVE:
        return
    sk = stage and stage.get("key")
    wo = rec.get("waiting_on") or {}
    asked = next((e for e in rec.get("people_detail") or [] if _me(e.get("person_id"), v) and e.get("status") == "invited" and e.get("role") != "affected"), None)
    if asked:  # W2F1: an invitation not yet answered is the person's first line; the pointer rows below say the same thing less plainly
        yield _row(rec, "invitation", "invite", "invited", T, f"{_who(plane, rec)} invited you as {asked.get('role')}: {rec.get('purpose') or ''}. Accept or decline.",
                   "Accept or decline", asked.get("invited_at") or at, due)
    if kind == "decision" and sk == "decide" and _me(_slot(rec, "decider"), v):
        voices = {view.norm(n.get("by")) for o in (rec.get("outcome") or {}).get("options") or [] for n in o.get("notes") or [] if isinstance(n, dict) and n.get("by")}
        n_opt = len((rec.get("outcome") or {}).get("options") or [])
        views = "1 adviser has given a view" if len(voices) == 1 else f"{len(voices)} advisers have given views"
        sets = "1 option is set out" if n_opt == 1 else f"{n_opt} options are set out"
        yield _row(rec, "decide", "decision", "decide", f"A decision waits for you: {T}", f"{views} and {sets}. "
                   "Choose one and give the reason.", "Decide", at, box.get("ends"))
    over = bool(box.get("starts") and box.get("ends") and box.get("ends") and parse(box["ends"]) < now)
    closer = org or any(_me(_slot(rec, s), v) for s in CONFIRMERS.get(kind, ())[:1])
    if closer and kind != "pulse" and box.get("starts") and box.get("ends"):
        ck = time_box_clock(parse(box["starts"]), parse(box["ends"]), now, len(box.get("extended_by") or []))
        if over:
            yield _row(rec, "overdue", "decision", "decide", f"{T} is overdue", f"It ended on {_date(box['ends'])}. {overdue_words(-ck['hours_left'])}. Pick one: extend, close with what we have, or cancel.",
                       "Choose", at, box["ends"], "/close")
        elif ck["state"] == "at_risk":
            todo = sum(x.get("default_days") or 0 for x in _cat(rec).get("stages", []) if not any(
                s.get("key") == x["key"] and s.get("closed_at") for s in rec.get("stages") or []))
            late = todo > ck["working_days_left"]
            yield _row(rec, "clock", "clock", "decide" if late else "watch", f"{T}: {ck['working_days_left']} working days left of {ck['working_days_total']}",
                       "North does not expect to finish in time. Pick one: extend, close with what we have, or cancel." if late else "North expects to finish in time.",
                       "Choose" if late else "Open it", at, box["ends"], "/close")
    if wo.get("person") and _me(wo["person"], v) and stage and (kind, sk) != ("initiative", "define_strategically"):
        yield _row(rec, "turn", "decision", "decide", f"Your turn on {T}", str(wo.get("what") or ""), TURN.get((kind, sk), "Open it"), wo.get("since") or at, due,
                   TURN_VIEW.get((kind, sk), ""))
    if kind == "problem" and sk == "describe" and _me(_slot(rec, "owner"), v) and not (rec.get("owner_accepted_at") or (rec.get("outcome") or {}).get("owner_accepted_at")):
        yield _row(rec, "owner", "decision", "decide", f"A problem needs an owner: {T}", f"{_who(plane, rec)} reported it: {rec.get('purpose') or ''}. Take it, or hand it back with a reason.",
                   "Take it", at, box.get("ends"))
    vote = next((x for x in rec.get("votes") or [] if x.get("state") == "open" and _in(x.get("voters"), v) and not _in(x.get("cast_by"), v)), None)
    if vote:
        bs = kind == "brainstorm"
        yield _row(rec, "vote", "decision", "decide", f"Back up to three ideas in {T}" if bs else f"Vote: {vote.get('question')}",
                   f"{len(vote.get('cast_by') or [])} of {len(vote.get('voters') or [])} have voted." + (f" The vote closes {_date(vote['closes'])}." if vote.get("closes") else ""),
                   "Back your ideas" if bs else "Vote", at, vote.get("closes"), "" if bs else "/define")
    if any(d.get("author") and _me(d["author"], v) and not d.get("confirmed_by") for d in rec.get("drafts_to_confirm") or []):
        yield _row(rec, "card", "decision", "decide", "Check what North wrote for you", "North turned your answer into a short card. Keep it, change it, or delete it.",
                   "Check the card", at, due)
    d = next((d for d in rec.get("definitions_waiting") or [] if d.get("state") == "open" and _me(d.get("owner"), v)), None)
    if d:
        yield _row(rec, "definition", "decision", "decide", f"A term needs your confirmation: {d.get('term')}", "Lens drafted the meaning from the intent. Confirm it, or write your own.",
                   "Confirm", at, due, "/define")
    s2 = next((s for s in rec.get("process_waiting") or [] if s.get("state") == "open" and not s.get("confirmed_by") and _me(s.get("owner"), v)), None)
    if s2:
        yield _row(rec, "process", "decision", "decide", f"A process step needs your check: {s2.get('step')}", "Lens drafted the step from the intent. Confirm it, or write your own.",
                   "Check the step", at, due, "/define")
    w = _week(plane, rec) if kind == "pulse" else None
    if w and not _answerable(plane, w, now):  # the stored state can lag the calendar: past the answers day nothing is asked (W2F1)
        w = None
    if w and part and not _week_acted(w, v):
        yield _row(rec, "week", "request", "give", f"Your week for {', '.join(rec.get('areas') or []) or T}",
                   "Three questions: what ran well, what broke or nearly broke, what is on your mind. About 5 minutes.", "Answer three questions", w.get("opens") or at,
                   w.get("closes"), "/week")
    if part and kind not in ("pulse", "initiative"):
        quiet = not_acted(plane, rec)
        if any(_me(r, v) for r in quiet["people"]):
            yield _row(rec, "invite", "invite", "invited", T, f"{_who(plane, rec)} invited you to a {t}: {rec.get('purpose') or ''}.", OWES[kind][0],
                       (stage or {}).get("opened_at") or at, due)
    if part and init and sk == "think_unfiltered":  # F51: an invited person is asked for cards until they have written one
        mine = next((e for e in rec.get("people_detail") or [] if _me(e.get("person_id"), v)), None)
        if mine and mine.get("status") in ("invited", "joined"):
            yield _row(rec, "wallcards", "invite", "invited", T, f"{_who(plane, rec)} invited you to add your cards to the wall: {rec.get('purpose') or ''}.",
                       "Add your cards", (stage or {}).get("opened_at") or at, due, "/wall")
    if org and kind not in ("pulse", "initiative"):
        q = not_acted(plane, rec)
        if q["people"] and q["total"]:
            verb = OWES[kind][1]
            yield _row(rec, "people", "request", "waiting", f"{T}: {len(q['people'])} of {q['total']} have not {verb}", "Draft a reminder, extend the stage, or move on.",
                       "See who to remind", (stage or {}).get("opened_at") or at, due, "/people")


def _who(plane, rec: dict) -> str:
    """The organiser's first name for the detail line; 'Your organiser' when the slot holds no display name."""
    o = _slot(rec, "organiser")
    name = str((o.get("name") if isinstance(o, dict) else o) or "").strip()
    return name.split()[0] if name and "@" not in name else "Your organiser"


# ---- the readers
def candidates(plane, v: view.Viewer, now: datetime) -> list[tuple[dict, str, str, dict]]:
    """Every true row for the viewer as (record, trigger, strip, line), before the one-line-per-intent rule."""
    out = []
    for rec in records(plane):
        if rec.get("state") == "cancelled":  # a cancelled intent makes no row
            continue
        try:
            out += [(rec, trig, strip, ln) for trig, strip, ln in _rows(plane, rec, v, now)]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            log.warning("pulse: intent %s skipped (%s)", rec.get("id"), type(e).__name__)
    return out


def waiting(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The viewer's whole list for the Intent home strip (spec 45): every true line, no cap, signatures and decisions first, then due soonest
    (none last), then newest. At most three Define questions (rows 6 and 17) at once. Each carries its `group` for the filter chips."""
    rows, qs = [], 0
    cands = candidates(plane, v, now)
    asked = {rec["id"] for rec, trig, _, _ in cands if trig == "invitation"}
    for rec, trig, strip, ln in cands:
        if rec["id"] in asked and trig in ("invite", "wallcards"):  # W2F1: the invitation says it once
            continue
        if trig in ("definition", "process"):
            qs += 1
            if qs > QUESTION_CAP:
                continue
        rows.append(({**ln, "group": ["Signature", "Decision", "Question", "Rating"][GROUP[trig]]}, GROUP[trig]))
    rows.sort(key=lambda r: r[0]["source"]["at"] or "", reverse=True)
    rows.sort(key=lambda r: (r[1], r[0]["due"] is None, r[0]["due"] or ""))
    return [r[0] for r in rows]


def strips(plane, v: view.Viewer, now: datetime) -> dict[str, list[dict]]:
    """Lines by strip key for Pulse: for each intent the viewer's single highest line (PRIORITY), plus row 16 which is separate."""
    best: dict[str, tuple[int, str, dict]] = {}
    out: dict[str, list[dict]] = {}
    for rec, trig, strip, ln in candidates(plane, v, now):
        if trig == "people":
            out.setdefault(strip if "company_admin" in v.roles else "watch", []).append(ln)
        elif rec["id"] not in best or PRIORITY.index(trig) < best[rec["id"]][0]:
            best[rec["id"]] = (PRIORITY.index(trig), strip, ln)
    for _, strip, ln in best.values():
        out.setdefault(strip, []).append(ln)
    return out


def others(plane, v: view.Viewer) -> dict[str, list[dict]]:
    """The lines other cards asked Pulse to carry: B30's affected-people lines (Watch) and B36's opportunity lines (Decide).
    The opportunity reader needs the request (field rules by measure name), so it runs only inside GET /api/pulse."""
    out: dict[str, list[dict]] = {}
    try:
        from sh_platform.intents import affected
        from sh_platform.intents.access import Me, name_twin, person_of
        pid, areas = person_of(plane, v.account_id)
        me = Me(v.account_id, v.name, v.roles, v.shared_name or name_twin(plane, v.name, pid), pid, areas)
        out["watch"] = affected.watch_lines(plane, me)
    except Exception as e:  # noqa: BLE001  a failing neighbour reader never takes the whole Pulse page down
        log.warning("pulse: affected lines skipped (%s)", type(e).__name__)
    request = _REQUEST.get()
    if request is not None:
        try:
            from sh_platform.intents import opportunities
            out["decide"] = opportunities.pulse_lines(plane, request)
        except Exception as e:  # noqa: BLE001
            log.warning("pulse: opportunity lines skipped (%s)", type(e).__name__)
        try:  # B57a: radar lines (Nira, kind decision)
            from sh_platform.intents import radar
            out.setdefault("decide", []).extend(radar.pulse_lines(plane, request))
        except Exception as e:  # noqa: BLE001
            log.warning("pulse: radar lines skipped (%s)", type(e).__name__)
    now = datetime.now(timezone.utc).isoformat()
    try:  # B35: what changed in the map, a field found in another system
        from sh_platform.intents import knowledge_map
        out.setdefault("watch", []).extend(knowledge_map.pulse_lines(plane, v, datetime.now(timezone.utc)))
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: knowledge map lines skipped (%s)", type(e).__name__)
    try:  # B29: North's backlog review reminder (today's due items, then weekly); the company admin carries it until areas have a lead
        from sh_platform.intents import backlog
        from sh_platform.pulse.lines import line
        admin = "company_admin" in v.roles  # the raiser hears of their own item on its review date, the admin of every one
        out.setdefault("decide", []).extend(line(f"backlog-review:{r['href'].rsplit('=', 1)[-1]}", "decision", r["text"], r["note"], r["href"],
                                                 "Review it", "intents/backlog.json", None, r["due"]) for r in backlog.remind_due(plane, peek=True) if admin or r.get("raiser") == v.account_id)  # stamped in build(), only if shown
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: backlog lines skipped (%s)", type(e).__name__)
    try:  # B18: role asks and declines; the sponsor's signature is already carried by the sign strip
        from sh_platform.intents import charter
        out.setdefault("decide", []).extend(r for r in charter.role_pulse_lines(plane, v, now) if not r["id"].startswith("charter-sign:"))
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: charter lines skipped (%s)", type(e).__name__)
    try:  # B58a: weekly reports to confirm, the sponsor's verdict line, receipts
        from sh_platform.intents import proving
        for k, rows in proving.pulse_lines(plane, v).items():
            out.setdefault(k, []).extend(rows)
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: proving lines skipped (%s)", type(e).__name__)
    try:  # 59: the build chain, one line per gate and the architecture brief
        from sh_platform.build import chain
        for k, rows in chain.pulse_lines(plane, v).items():
            out.setdefault(k, []).extend(rows)
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: build chain lines skipped (%s)", type(e).__name__)
    try:  # SF13: Span's suggestions to decide, drafts to check, Flow's run notes (plan 3.7)
        from sh_platform.build import proposals as build_proposals
        from sh_platform.build.agents import routes as span_flow
        for part in (build_proposals.pulse_lines(plane, v), span_flow.agent_lines(plane, v)):
            for k, rows in part.items():
                out.setdefault(k, []).extend(rows)
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: Span and Flow lines skipped (%s)", type(e).__name__)
    try:  # F27: North's nudges for this person (spec 08, screen C): one line per intent with a nudge today
        from sh_platform.intents import north
        from sh_platform.pulse.lines import line
        out.setdefault("decide", []).extend(
            line(f"north-nudge:{n['intent_id']}", "request", n["title"], n["detail"], f"/centre/intent/{n['intent_id']}", "Open it", n["record"], n["at"], n["due"])
            for n in north.nudges_for(plane, v))
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: North nudge lines skipped (%s)", type(e).__name__)
    try:  # F29: confirm a process, questions about a process
        from sh_platform.intents import processes
        out.setdefault("decide", []).extend(processes.pulse_lines(plane, v))
    except Exception as e:  # noqa: BLE001
        log.warning("pulse: process lines skipped (%s)", type(e).__name__)
    return out


# ---- joining Pulse without editing the shared file: wrap its strip list and its builder. See "Shared files needed" in the card report.
_SEEN = threading.local()
_REQUEST: contextvars.ContextVar = contextvars.ContextVar("pulse_request", default=None)


PROTECT = ("decide", "sign")  # signature and decision strips: never cut (spec 45 rule 5, ruling R10)
YIELD = ("start", "running", "waiting")  # the organiser's informational strips go first


def _protect(result: list, cap: int, order) -> list:
    """Trim the other strips so `build()`'s cut in strip order cannot reach a signature or decision line. Only the room is cut here;
    order, one line per intent and the `more` count (taken before this) are untouched."""
    def rank(r):  # signatures first, decisions next, the intent's own questions (start, card) last; other readers' lines count as decisions
        if r["id"].startswith("backlog-review:"):  # the weekly review reminder ranks with signatures so a long decision list cannot bury it
            return 0
        return GROUP.get(r["id"].rsplit(":", 1)[-1], 1) if r["id"].startswith("intent:") else 1
    result = [(k, sorted(order(rows), key=rank)[:cap] if k in PROTECT and len(rows) > cap else rows) for k, rows in result]
    keep = {r["id"] for k, rows in result if k in PROTECT for r in rows}
    room, seen, out = max(0, cap - len(keep)), set(keep), {}
    for k, rows in sorted(result, key=lambda kr: kr[0] in YIELD):  # stable: the yielding strips fill last
        if k in PROTECT:
            continue
        out[k] = []
        for r in order(rows):
            if r["id"] not in seen and room > 0:
                seen.add(r["id"]); room -= 1; out[k].append(r)
    return [(k, rows if k in PROTECT else out[k]) for k, rows in result]


def install(pulse) -> None:
    """Add the intent lines to `pulse._strips` and the `more` count to `pulse.build`. Idempotent."""
    if getattr(pulse, "_intent_lines", False):
        return
    pulse._intent_lines = True
    plain_strips, plain_build, plain_briefs = pulse._strips, pulse.build, pulse._briefs

    def _briefs(request):  # the route calls this with the request; kept for the opportunity reader
        _REQUEST.set(request)
        return plain_briefs(request)

    def _strips(plane, v, briefs, now, kind):
        got = strips(plane, v, now)
        for key, rows in others(plane, v).items():
            got[key] = got.get(key, []) + rows
        if kind != "organiser":  # row 16 has no waiting strip on this layout
            got["watch"] = got.get("watch", []) + got.pop("waiting", [])
        result = [(key, rows + got.pop(key, [])) for key, rows in plain_strips(plane, v, briefs, now, kind)]
        for key in ("invited", "decide", "give", "watch"):  # a strip the person's layout has no list for still gets its lines
            if got.get(key) and not any(k == key for k, _ in result):
                result.append((key, got.pop(key)))
        if got.get("waiting") and kind == "organiser" and not any(k == "waiting" for k, _ in result):
            result.append(("waiting", got.pop("waiting")))
        mine = {r["id"].split(":")[1] for _, rows in result for r in rows if r["id"].startswith("intent:")}  # one line per intent: B06's twin yields
        result = [(k, [r for r in rows if r["id"].split(":")[0] not in ("intent-invite", "intent-wait") or r["id"].split(":")[1] not in mine]) for k, rows in result]
        _SEEN.total = len({r["id"] for _, rows in result for r in rows})
        return _protect(result, getattr(pulse, "CAP", 7), pulse._order)

    def build(plane, v, briefs=None, now=None):
        _SEEN.total = 0
        token = _MEMO.set({})  # every reader in this request shares one read of the intent records
        try:
            data = plain_build(plane, v, briefs, now)
        finally:
            _MEMO.reset(token)
        shown = {r["id"].split(":", 1)[1] for s in data["strips"] for r in s["lines"] if r["id"].startswith("backlog-review:")}
        if shown:  # F35: only a reminder the page showed counts as sent; one pushed into "more" is offered again
            try:
                from sh_platform.intents import backlog
                backlog.remind_due(plane, only=shown)
            except Exception as e:  # noqa: BLE001
                log.warning("pulse: backlog reminder not stamped (%s)", type(e).__name__)
        data["more"] = max(0, _SEEN.total - sum(len(s["lines"]) for s in data["strips"]))
        return data

    pulse._strips, pulse.build, pulse._briefs = _strips, build, _briefs
