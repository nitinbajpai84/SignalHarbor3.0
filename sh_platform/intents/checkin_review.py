"""IC v2 (spec 40): review of a Weekly check-in week. North's digest, one fate per item, the 30 minute session, closing, trends.

Week files are read and written directly at intents/<id>/weeks/<week_key>.json (checkin.py is B22's). All logic is in plain
functions on a week dict; the routes only load, check the viewer and save. Counts only: nothing here is a score.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, events
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
router = APIRouter()
FATES = ("problem", "backlog", "handled", "nothing")
KINDS = ("broke", "ran", "thought")
SEVERITIES = ("stopped", "slowed", "cost", "not_marked")
NOT_REVIEWED = "Not reviewed this week"
SESSION_MINUTES, EXTEND_MINUTES, MIN_TREND_WEEKS = 30, 10, 4
REASON_CHARS = 300
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(t: datetime | None = None) -> str:
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _words(text) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split())


def is_anonymous(item: dict) -> bool:
    return bool(item.get("anonymous")) or item.get("by") in (None, "", "anonymous")


# ---- the digest (North's draft; deterministic, every number carries the items it counts) ----

def _earlier(weeks: list[dict], week: dict) -> list[dict]:
    return sorted((w for w in weeks if w.get("week_key") and w["week_key"] < week["week_key"]), key=lambda w: w["week_key"])


def match_repeats(week: dict, weeks: list[dict]) -> list[dict]:
    """An item matches an earlier item of the same kind and the same words. Splits the reviewer made are kept."""
    kept = {r["item_id"]: r for r in (week.get("digest") or {}).get("repeats", []) if r.get("split")}
    out = []
    for item in week.get("items", []):
        if item["id"] in kept:
            out.append(kept[item["id"]])
            continue
        seen = [w["week_key"] for w in _earlier(weeks, week)
                if any(o.get("kind") == item["kind"] and _words(o.get("text")) == _words(item["text"]) for o in w.get("items", []))]
        if seen:
            out.append({"item_id": item["id"], "seen_in": seen, "matched_by": "north", "split": False})
    return out


def _seen(item_id: str, repeats: list[dict]) -> int:
    r = next((r for r in repeats if r["item_id"] == item_id), None)
    return 1 if r is None or r.get("split") else 1 + len(r["seen_in"])


def _same_text(items: list[dict], item: dict) -> list[dict]:
    return [o for o in items if o["kind"] == item["kind"] and _words(o["text"]) == _words(item["text"])]


def build_digest(week: dict, weeks: list[dict]) -> dict:
    """Groups: broke and ran by `ref` ("Not linked" has ref null), thought by `topic`. Broke ranked by people who reported the
    same thing, then by earlier weeks seen. Severity is displayed per item and never used to rank."""
    items = week.get("items", [])
    repeats = match_repeats(week, weeks)
    for it in items:
        it["people_count"] = len({o["id"] for o in _same_text(items, it)})
        it["seen_weeks"] = _seen(it["id"], repeats)
    groups = []
    for kind in KINDS:
        by_key: dict = {}
        for it in (i for i in items if i["kind"] == kind):
            by_key.setdefault(it.get("topic") if kind == "thought" else it.get("ref"), []).append(it)
        for key, members in by_key.items():
            members.sort(key=(lambda i: (-i["people_count"], -i["seen_weeks"])) if kind == "broke" else (lambda i: -i["people_count"]))
            ids = [m["id"] for m in members]
            top = members[0]
            line = f"{top['people_count']} {'person' if top['people_count'] == 1 else 'people'} said \"{top['text'][:90].rstrip(' .')}\"."
            if top["seen_weeks"] > 1:
                line += f" It has come up in {top['seen_weeks']} weeks."
            if len(members) > 1:
                line += f" {len(members) - 1} other item{'s' if len(members) > 2 else ''} in this group."
            groups.append({"kind": kind, "ref" if kind != "thought" else "topic": key, "item_ids": ids,
                           "line": line, "source_item_ids": [o["id"] for o in _same_text(items, top)]})
    return {"drafted_at": stamp(), "drafted_by": "north", "groups": groups, "repeats": repeats,
            "summary_line": summary_draft(week)}


SYSTEM = ("You are North. You word a weekly check-in digest for the reviewer; you never decide a fate, mark a severity or close the week. "
          "Use only the counted lines and item texts given. Never write a number that is not in them. Plain English, British spelling, "
          "no em dashes, no names of people.")
ASK = ("For each group write one plain sentence that says what people reported, keeping its counts. Then one summary sentence for the week, "
       'keeping its counts. Reply with ONLY one JSON object {"lines": [{"key": 0, "text": "..."}], "summary": "..."}')


def model_words(request, plane, week: dict, digest: dict) -> dict:
    """North's wording of the digest through the kernel runtime and the egress gateway (R14). Item texts and counts only: never an author,
    an account id or an anonymous token. A line whose number is not in its facts is dropped. When the model cannot answer, the counted
    lines stand and `fallback` is true so the screen says so."""
    from sh_platform.intents import north as N
    from sh_platform.intents.decision import drop_untraced, with_numbers
    digest["fallback"] = True
    gate = getattr(request.app.state, "entitlements", None) if request is not None else None
    if gate is None or not digest["groups"]:
        return digest
    text_of = {i["id"]: i.get("text") or "" for i in week.get("items", [])}
    groups = [{"key": k, "kind": g["kind"], "counted": g["line"], "texts": [text_of[x][:200] for x in g["item_ids"][:5]]} for k, g in enumerate(digest["groups"])]
    try:
        got = json.loads((lambda t: t[t.find("{"):t.rfind("}") + 1] or "null")(
            N._call(plane, N._model(request, plane), gate, SYSTEM, {"facts": [], "groups": {str(g["key"]): {k: g[k] for k in ("kind", "counted", "texts")} for g in groups}, "summary": digest["summary_line"]},
                    with_numbers(ASK, json.dumps(groups) + " " + digest["summary_line"])) or ""))
    except Exception:  # noqa: BLE001 - a provider failure leaves the counted lines, never breaks opening the week
        log.warning("North could not word the digest", exc_info=True)
        return digest
    if not isinstance(got, dict):
        return digest
    for x in got.get("lines") or []:
        k = x.get("key") if isinstance(x, dict) else None
        k = int(k) if isinstance(k, str) and k.isdigit() else k
        if isinstance(k, int) and 0 <= k < len(groups) and isinstance(x.get("text"), str):
            line = drop_untraced(" ".join(x["text"].split())[:300], groups[k]["counted"] + " " + " ".join(groups[k]["texts"]))[0]
            if line:
                digest["groups"][k]["line"], digest["fallback"] = line, False
    summ = got.get("summary")
    if isinstance(summ, str) and digest["summary_line"]:
        summ = drop_untraced(" ".join(summ.split())[:400], digest["summary_line"])[0]
        if summ:
            digest["summary_line"], digest["fallback"] = summ, False
    return digest


def severity_summary(items: list[dict]) -> dict:
    """Broke items by the severity their reporter marked: counts of items, plus the typed times and amounts, never estimated."""
    out = {k: 0 for k in SEVERITIES}
    amounts: dict[str, float] = {}
    times = 0
    for i in items:
        if i["kind"] != "broke":
            continue
        sv = "cost" if i.get("severity") == "cost_money" else i.get("severity")
        out[sv if sv in out else "not_marked"] += 1
        times += i["count"] if isinstance(i.get("count"), int) else 0
        a = i.get("amount")
        if isinstance(a, dict) and isinstance(a.get("value"), (int, float)):
            amounts[a.get("currency") or ""] = amounts.get(a.get("currency") or "", 0) + a["value"]
    return {"items": out, "times": times, "amounts": [{"currency": c, "value": v} for c, v in amounts.items()]}


def kind_count(items: list[dict], kind: str) -> int:
    return sum(1 for i in items if i["kind"] == kind)


def summary_draft(week: dict) -> str:
    items = week.get("items", [])
    if not items:
        return ""
    fates = {f: sum(1 for i in items if i.get("fate") == f) for f in FATES}
    lead = (f"{week.get('responded_count', 0)} of {week.get('participants_count', 0)} answered. {len(items)} items: "
            f"{kind_count(items, 'broke')} broke, {kind_count(items, 'ran')} ran well, {kind_count(items, 'thought')} on minds.")
    decided = sum(fates.values())
    return lead + (f" {fates['problem']} became a Problem, {fates['backlog']} went to the backlog, "
                   f"{fates['handled']} already handled, {fates['nothing']} nothing." if decided else "")


# ---- decisions, session, closing ----

def broke_open(week: dict) -> list[dict]:
    return [i for i in week.get("items", []) if i["kind"] == "broke" and not i.get("fate")]


def decide(week: dict, item_id: str, fate: str, reason: str, fate_ref: str | None, by: str, exists=None) -> dict:
    """One fate with a reason. problem and backlog need the created record; handled needs the link. Earlier decisions stay in history."""
    if week.get("read_only"):
        raise ValueError("This week is closed. A correction is a note on a later week.")
    item = next((i for i in week.get("items", []) if i["id"] == item_id), None)
    if item is None:
        raise LookupError("item")
    reason, fate_ref = str(reason or "").strip(), str(fate_ref or "").strip() or None
    if fate not in FATES:
        raise ValueError("Choose one of the four decisions.")
    if not reason:
        raise ValueError("Please say why.")
    if len(reason) > REASON_CHARS:
        raise ValueError(f"Keep the reason to {REASON_CHARS} characters.")
    if fate != "nothing" and not fate_ref:
        raise ValueError({"handled": "Add the link to what handled it.", "problem": "Create the Problem first, then add it here.",
                          "backlog": "Add it to the backlog first, then add it here."}[fate])
    if fate_ref and not (_ID.match(fate_ref) or fate_ref.startswith("/centre/")):
        raise ValueError("That link is not a record or a page in the centre.")
    if fate_ref and fate != "nothing" and exists is not None and not exists(fate, fate_ref):
        raise ValueError("We could not find that. Check the id, or use Create to make it from here.")
    if item.get("fate"):
        item.setdefault("history", []).append({k: item.get(k) for k in ("fate", "fate_reason", "fate_ref", "decided_by", "decided_at")})
    item.update(fate=fate, fate_reason=reason, fate_ref=fate_ref if fate != "nothing" else None, decided_by=by, decided_at=stamp())
    if week.get("state") == "ready":
        week["state"] = "reviewing"
    return item


def split_repeat(week: dict, item_id: str) -> None:
    """The reviewer says "Not the same": the item's count drops to 1; the match stays in the digest, marked split."""
    if week.get("read_only"):
        raise ValueError("This week is closed.")
    reps = week.setdefault("digest", {}).setdefault("repeats", [])
    r = next((r for r in reps if r["item_id"] == item_id), None)
    if r is None:
        raise LookupError("repeat")
    r["split"], r["matched_by"] = True, "reader"
    for it in week["items"]:
        if it["id"] == item_id:
            it["seen_weeks"] = 1


def session_act(week: dict, act: str, by: str, t: datetime | None = None) -> dict:
    t = t or now()
    s = week.get("session")
    if act == "start":
        if not week.get("items"):
            raise ValueError("Nothing to review.")
        if s and not s.get("ended_at"):
            raise ValueError("A session is already running.")
        week["session"] = s = {"started_at": stamp(t), "ended_at": None, "by": by, "minutes_used": None, "extended_by": []}
        week["state"] = "in_session"
    elif not s or s.get("ended_at"):
        raise ValueError("No session is running.")
    elif act == "extend":
        left = clock(week, t)
        if left and left["remaining_seconds"] > 0:
            raise ValueError("The time is not up yet. Extend once the clock reaches zero.")
        s["extended_by"].append({"by": by, "at": stamp(t), "minutes": EXTEND_MINUTES})
    elif act == "end":
        s["ended_at"] = stamp(t)
        s["minutes_used"] = round((t - _t(s["started_at"])).total_seconds() / 60)
        week["state"] = "reviewing"
    else:
        raise ValueError("Unknown session action.")
    return s


def _t(v) -> datetime:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def clock(week: dict, t: datetime | None = None) -> dict | None:
    """Server-held clock: the browser only draws `remaining_seconds` from `now`."""
    s, t = week.get("session"), t or now()
    if not s or s.get("ended_at"):
        return None
    end = _t(s["started_at"]) + timedelta(minutes=SESSION_MINUTES + sum(e["minutes"] for e in s["extended_by"]))
    return {"now": stamp(t), "ends_at": stamp(end), "remaining_seconds": int((end - t).total_seconds())}


def close_week(week: dict, summary: str, by: str, closed_for: str | None = None, edited: bool = False) -> dict:
    """Closes only when every broke item has a fate. Undecided ran and thought items close as Nothing, Not reviewed this week."""
    if week.get("read_only"):
        raise ValueError("This week is already closed.")
    left = broke_open(week)
    if left:
        raise ValueError(f"{len(left)} broke item{'s' if len(left) != 1 else ''} still need{'' if len(left) != 1 else 's'} a decision.")
    for it in week.get("items", []):
        if not it.get("fate"):
            it.update(fate="nothing", fate_reason=NOT_REVIEWED, fate_ref=None, decided_by=by, decided_at=stamp())
    if week.get("session") and not week["session"].get("ended_at"):
        session_act(week, "end", by)
    week["closure"] = {"closed_by": by, "closed_at": stamp(), "closed_for": closed_for, "summary": str(summary or "").strip(), "edited_by_person": edited}
    week["state"], week["read_only"], week["closed_at"] = "closed", True, week["closure"]["closed_at"]
    return week["closure"]


def outcome_row(week: dict) -> dict:
    items = week.get("items", [])
    return {"week_key": week["week_key"], "closed_at": week.get("closed_at"), "items_count": len(items), "broke_count": kind_count(items, "broke"),
            "fates": {f: sum(1 for i in items if i.get("fate") == f) for f in FATES}}


# ---- trends (closed weeks only) ----

def trends(weeks: list[dict], range_weeks: int | None = None, process: str | None = None) -> dict:
    closed = sorted((w for w in weeks if w.get("state") == "closed"), key=lambda w: w["week_key"])
    n = len(closed)
    if n < MIN_TREND_WEEKS:
        return {"available": False, "closed_weeks": n, "reason": f"Not available yet: trends need four closed weeks. This series has {n}."}
    shown = closed[-range_weeks:] if range_weeks else closed
    keys = [w["week_key"] for w in shown]
    cells: dict = {}
    for w in shown:
        for it in w["items"]:
            if it["kind"] == "broke" and (process is None or it.get("ref") == process):
                row = cells.setdefault(it.get("ref"), {})
                row[w["week_key"]] = row.get(w["week_key"], 0) + 1
    processes = sorted({i.get("ref") for w in closed for i in w["items"] if i["kind"] == "broke"}, key=lambda r: (r is None, str(r)))
    rows = [{"process": p, "counts": [cells[p].get(k, 0) for k in keys], "total": sum(cells[p].values())} for p in cells]
    seen: dict = {}
    for w in shown:
        for it in w["items"]:
            seen.setdefault((it["kind"], _words(it["text"])), []).append((w["week_key"], it))
    repeated = [{"text": its[-1][1]["text"], "kind": its[-1][1]["kind"], "process": its[-1][1].get("ref"), "weeks": [k for k, _ in its],
                 "seen_weeks": len({k for k, _ in its}), "latest_fate": its[-1][1].get("fate"), "latest_week": its[-1][0],
                 "item_id": its[-1][1]["id"]} for its in seen.values() if len({k for k, _ in its}) > 1]
    repeated.sort(key=lambda r: -r["seen_weeks"])
    top = repeated[0] if repeated else None
    reading = (f"{top['text'][:80]} has been reported in {top['seen_weeks']} of the last {len(shown)} weeks." if top else "")
    return {"available": True, "closed_weeks": n, "weeks": keys, "rows": rows, "processes": processes, "repeated": repeated,
            "reading": reading, "reading_item_ids": [top["item_id"]] if top else []}


# ---- Pulse lines (counts only) ----

def pulse_lines(intent: dict, week: dict, account_id: str, reviewer_id: str | None) -> list[dict]:
    """The reviewer's "Read the week" and the reporter's "Your items have a decision". Built in the shape of pulse.lines.line()."""
    base = f"/centre/intent/{intent['id']}"
    label = _day(week["week_key"])
    out = []
    if account_id == reviewer_id and week.get("state") in ("ready", "reviewing", "in_session", "closing"):
        n = len(broke_open(week))
        undecided = sum(1 for i in week["items"] if not i.get("fate"))
        title = "Read the week" if week["state"] == "ready" else f"Give each item a decision: {undecided} item{'s' if undecided != 1 else ''} need{'' if undecided != 1 else 's'} one"
        out.append(_line(f"{intent['id']}:{week['week_key']}:review", title, f"Weekly check-in, week of {label}. {n} broke item{'s' if n != 1 else ''} without a decision.",
                         f"{base}/review?week={week['week_key']}", "Read the week", week))
    if week.get("state") == "closed" and any(i.get("by") == account_id and not is_anonymous(i) for i in week["items"]):
        out.append(_line(f"{intent['id']}:{week['week_key']}:mine", f"Your items from the week of {label} have a decision", "Read what happened to each item, and why.",
                         f"{base}/review?week={week['week_key']}&view=mine", "Open", week))
    return out


def _day(week_key: str) -> str:
    d = datetime.fromisoformat(week_key)
    return f"{d.day} {d.strftime('%b')}"


def _line(id: str, title: str, detail: str, href: str, action: str, week: dict) -> dict:
    return {"id": id, "kind": "review", "title": title, "detail": detail, "href": href, "action": action, "minutes": 30, "due": None,
            "source": {"record": "intents/weeks", "at": week.get("closed_at") or (week.get("digest") or {}).get("drafted_at")}}


# ---- files, viewer, routes ----

def _bad(msg: str, status: int = 422) -> JSONResponse:
    return JSONResponse({"detail": msg}, status_code=status)


def _paths(plane, intent_id: str, week_key: str | None = None):
    if not _ID.match(intent_id) or (week_key is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", week_key)):
        raise LookupError("not found")
    base = plane.path("intents", intent_id)
    return base, (base / "weeks" / f"{week_key}.json" if week_key else base / "weeks")


def _all_weeks(folder) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            w = read_json_strict(p, dict)
        except (OSError, ValueError):
            continue
        if w and w.get("week_key"):
            out.append(w)
    return out


def _ids(people: dict) -> set[str]:
    found: set[str] = set()
    for v in (people or {}).values():
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str):
                found.add(x)
            elif isinstance(x, dict):
                found.update(str(x[k]) for k in ("account", "account_id", "id", "person_id") if x.get(k))
    return found


def reviewer_of(intent: dict) -> str | None:
    r = (intent.get("series") or {}).get("reviewer") or (intent.get("people") or {}).get("reviewer") or (intent.get("people") or {}).get("organiser")
    return r.get("account_id") or r.get("id") if isinstance(r, dict) else r


def _viewer_rights(intent: dict, v, week: dict | None) -> dict:
    """role: reviewer | admin | reader (participant, observer) | affected | None. Anyone else gets a 404, never a hint."""
    people, aid = intent.get("people") or {}, v.account_id
    reviewer = aid is not None and aid == reviewer_of(intent)
    admin = "company_admin" in v.roles
    member = aid in _ids({k: people.get(k) for k in ("organiser", "sponsor", "participants", "advisers", "observers", "reporter", "owner", "decider")})
    affected = aid in _ids({"a": people.get("affected")})
    closed_or_not = week or {}
    may_read = reviewer or admin or member or (affected and bool(intent.get("affected_may_read")))
    stuck = closed_or_not.get("state") == "closing"
    return {"may_read": may_read, "is_reviewer": reviewer, "can_decide": (reviewer or (admin and stuck)) and not closed_or_not.get("read_only", False),
            "can_close": (reviewer or (admin and stuck)) and not closed_or_not.get("read_only", False)}


def _names(request: Request) -> dict:
    st = request.app.state
    return {a.get("id") or a.get("account_id"): a.get("display_name") for a in st.account_store.in_company(request.state.company_id)}


def _load(request: Request, intent_id: str, week_key: str | None):
    plane, v = _plane(request), _viewer(request)
    base, wpath = _paths(plane, intent_id, week_key)
    intent = read_json_strict(base / "intent.json", dict)
    if intent is None or intent.get("type") != "pulse":
        raise LookupError("not found")
    week = read_json_strict(wpath, dict) if week_key else None
    if week_key and week is None:
        raise LookupError("not found")
    rights = _viewer_rights(intent, v, week)
    if not rights["may_read"]:
        raise LookupError("not found")
    return plane, v, base, intent, week, rights


def _event(plane, intent_id: str, kind: str, v, week_key: str, detail: dict) -> None:
    """One line in events.jsonl through the one writer."""
    events.try_append(plane, intent_id, kind, {"account": v.account_id, "name": v.name, "role": "reviewer"}, {"store": "weeks", "id": week_key}, detail, "act", stage="review")


def _shape(week: dict, request: Request, rights: dict) -> dict:
    """The week for the viewer: anonymous items lose author and name; the others get a display name."""
    names, out = _names(request), dict(week)
    items = []
    for it in week.get("items", []):
        it = dict(it)
        if is_anonymous(it):
            it.pop("by", None)
            it["anonymous"], it["by_name"] = True, None
        else:
            it["by_name"] = names.get(it.get("by"))
            it.pop("by", None)
        items.append(it)
    out["items"], out["viewer"] = items, rights
    out["clock"] = clock(week)
    out["severity_summary"] = severity_summary(week.get("items", []))
    out["broke_open"] = [i["id"] for i in broke_open(week)]
    return out


def _exists(plane, v):
    """The checker decide() calls: a Problem id must be a Problem the reviewer may open, a backlog id a backlog item, a handled link any
    of those or a page in the centre."""
    from sh_platform.intents import backlog as B
    from sh_platform.intents import store as S
    areas = S.areas_of(plane, v)

    def known(fate: str, ref: str) -> bool:
        if fate == "handled" and ref.startswith("/centre/"):
            return True
        if ref.startswith("/") or not _ID.match(ref):
            return False
        if fate in ("backlog", "handled") and any(i.get("id") == ref for i in B.read_items(plane)):
            return True
        if fate == "backlog":
            return False
        try:
            rec = S.read_intent(plane, ref)
        except S.Unreadable:
            return False
        return rec is not None and (fate != "problem" or rec.get("type") == "problem") and S.tier_of(rec, v, areas) is not None
    return known


def _create_target(plane, v, intent: dict, week_key: str, item: dict, fate: str, spec: dict, reason: str) -> str:
    """The pre-filled panel's Create: a Problem draft only the reviewer sees, or a backlog item, linked back to this series. Returns its id."""
    from sh_platform.intents import backlog as B
    from sh_platform.intents import lifecycle as L
    from sh_platform.intents import links as K
    from sh_platform.intents import store as S
    title = " ".join(str(spec.get("title") or "").split()) or K.title_from(" ".join(str(item.get("text") or "").split()))
    if not title:
        raise ValueError("Give it a title.")
    anon = is_anonymous(item)
    areas = [a for a in (spec.get("areas") if isinstance(spec.get("areas"), list) else intent.get("areas") or []) if isinstance(a, str) and a.strip()]
    ref = {"kind": "checkin_item", "id": item["id"], "week_key": week_key, "hidden": anon}
    if fate == "backlog":
        made = B.create_item(plane, title=title, kind="ops_problem", area=(areas or [None])[0],
                             source={"intent_id": intent["id"], "type": "pulse", "stage_ref": None, "week_key": week_key, "week_item_id": item["id"]},
                             raised_by="anonymous" if anon else item.get("by") or v.account_id, why=reason, quote=item.get("text") or "")
        K.link_intents(plane, intent["id"], made["id"], "backlog", by=v, item={**ref, "title": title}, reason=reason)
        return made["id"]
    if not areas:
        raise ValueError("Pick an area for the Problem.")
    rec = L.new_record("problem", intent.get("company") or "", L.person(v.account_id, v.name), S.now_iso(), title=title, areas=areas, link_from=intent["id"])
    rec["start_answers"] = K.prefill(intent, "problem", item.get("text"), item["id"], None)
    rec["start_answers"]["what"] = " ".join(str(item.get("text") or "").split())[:300]
    S.create_intent(plane, rec)
    K.link_intents(plane, intent["id"], rec["id"], "problem", by=v, item=ref)
    return rec["id"]


def _save(plane, wpath, week: dict) -> None:
    write_json_atomic(wpath, week)


def _go(fn):
    try:
        return fn()
    except LookupError:
        return _bad("We could not find that.", 404)
    except PermissionError:
        return _bad("You cannot do that here.", 403)
    except ValueError as e:
        return _bad(str(e))


@router.get("/api/intents/{intent_id}/weeks/{week_key}")
def get_week(intent_id: str, week_key: str, request: Request):
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if week.get("state") == "collecting":
            return JSONResponse(_shape({**week, "items": [], "digest": None}, request, {**rights, "can_decide": False, "can_close": False}) | {"collecting": True})
        if not week.get("digest"):  # answers have closed: North drafts once, then never overwrites an edit
            wpath = base / "weeks" / f"{week_key}.json"
            with lock_for(wpath):
                week = read_json_strict(wpath, dict)
                if not week.get("digest"):
                    # ponytail: the model call runs under the week lock, once per week; move it outside if readers queue behind it
                    week["digest"] = model_words(request, plane, week, build_digest(week, _all_weeks(base / "weeks")))
                    week["state"] = "ready" if week.get("state") == "collecting" else week.get("state")
                    _save(plane, wpath, week)
        return JSONResponse(_shape(week, request, rights) | {"reviewer_id_known": reviewer_of(intent) is not None, "title": intent.get("title"),
                                                              "areas": intent.get("areas") or [], "series_id": intent["id"]})
    return _go(run)


@router.get("/api/intents/{intent_id}/weeks/{week_key}/mine")
def get_mine(intent_id: str, week_key: str, request: Request):
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if not week.get("read_only"):
            return {"week_key": week_key, "items": [], "closed": False, "note": "Your items show here once the week is closed."}
        from sh_platform.intents import checkin as C
        own = {r.get("item_id") for r in C._pointers(plane, v.account_id) if r.get("intent") == intent_id and r.get("week_key") == week_key}
        mine = [{**{k: i.get(k) for k in ("id", "kind", "text", "fate", "fate_reason", "fate_ref")}, "anonymous": is_anonymous(i)} for i in week["items"]
                if (not is_anonymous(i) and i.get("by") == v.account_id) or (is_anonymous(i) and i["id"] in own)]  # anonymous: only the author's own pointer file
        return {"week_key": week_key, "items": mine, "closed": True, "reviewer": _names(request).get(reviewer_of(intent))}
    return _go(run)


@router.post("/api/intents/{intent_id}/weeks/{week_key}/digest")
async def post_digest(intent_id: str, week_key: str, request: Request):
    """North drafts the digest itself, so a person cannot post one. The one thing a person posts here is "Not the same": {split: item_id}."""
    body = await request.json() if request.headers.get("content-length") not in (None, "0") else {}
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if not isinstance(body, dict) or not body.get("split"):
            raise PermissionError
        if not rights["can_decide"]:
            raise PermissionError
        wpath = base / "weeks" / f"{week_key}.json"
        with lock_for(wpath):
            week = read_json_strict(wpath, dict)
            split_repeat(week, str(body["split"]))
            _save(plane, wpath, week)
        _event(plane, intent_id, "repeat_split", v, week_key, {"item": str(body["split"])})
        return {"ok": True}
    return _go(run)


@router.post("/api/intents/{intent_id}/weeks/{week_key}/items/{item_id}/fate")
async def post_fate(intent_id: str, week_key: str, item_id: str, request: Request):
    body = await request.json()
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if not rights["can_decide"] or not isinstance(body, dict):
            raise PermissionError
        wpath = base / "weeks" / f"{week_key}.json"
        with lock_for(wpath):
            week = read_json_strict(wpath, dict)
            fate, ref, spec = str(body.get("fate", "")), body.get("fate_ref"), body.get("create")
            item = next((i for i in week.get("items", []) if i["id"] == item_id), None)
            if isinstance(spec, dict) and item is not None and fate in ("problem", "backlog") and not week.get("read_only") and str(body.get("reason") or "").strip():
                ref = _create_target(plane, v, intent, week_key, item, fate, spec, str(body["reason"]).strip())
            it = decide(week, item_id, fate, body.get("reason"), ref, v.account_id, _exists(plane, v))
            _save(plane, wpath, week)
        _event(plane, intent_id, "decision_saved", v, week_key, {"item": item_id, "fate": it["fate"]})
        return {"ok": True, "broke_open": [i["id"] for i in broke_open(week)]}
    return _go(run)


@router.post("/api/intents/{intent_id}/weeks/{week_key}/session")
async def post_session(intent_id: str, week_key: str, request: Request):
    body = await request.json()
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if not rights["is_reviewer"] or week.get("read_only") or not isinstance(body, dict):
            raise PermissionError
        wpath = base / "weeks" / f"{week_key}.json"
        act = str(body.get("act", ""))
        with lock_for(wpath):
            week = read_json_strict(wpath, dict)
            session_act(week, act, v.account_id)
            _save(plane, wpath, week)
        _event(plane, intent_id, {"start": "session_started", "extend": "session_extended", "end": "session_ended"}[act], v, week_key, {})
        return {"session": week["session"], "clock": clock(week), "state": week["state"]}
    return _go(run)


@router.post("/api/intents/{intent_id}/weeks/{week_key}/close")
async def post_close(intent_id: str, week_key: str, request: Request):
    body = await request.json()
    def run():
        plane, v, base, intent, week, rights = _load(request, intent_id, week_key)
        if not rights["can_close"] or not isinstance(body, dict):
            raise PermissionError
        wpath = base / "weeks" / f"{week_key}.json"
        with lock_for(wpath):
            week = read_json_strict(wpath, dict)
            drafted = (week.get("digest") or {}).get("summary_line", "")
            summary = str(body.get("summary") or drafted)
            admin_for = None if rights["is_reviewer"] else reviewer_of(intent)
            close_week(week, summary, v.account_id, admin_for, edited=summary != drafted)
            _save(plane, wpath, week)
        _event(plane, intent_id, "week_closed", v, week_key, {"items": len(week["items"])})
        ipath = base / "intent.json"
        with lock_for(ipath):  # counts only; the content stays in the week file
            rec = read_json_strict(ipath, dict)
            weeks = [r for r in (rec.get("outcome") or {}).get("weeks", []) if r.get("week_key") != week_key] + [outcome_row(week)]
            rec["outcome"] = {**(rec.get("outcome") or {}), "weeks": weeks}
            write_json_atomic(ipath, rec)
        return {"closure": week["closure"], "state": "closed"}
    return _go(run)


@router.get("/api/intents/{intent_id}/trends")
def get_trends(intent_id: str, request: Request, range: int | None = None, process: str | None = None):
    def run():
        plane, v, base, intent, _, rights = _load(request, intent_id, None)
        return {**trends(_all_weeks(base / "weeks"), range if range in (4, 8) else None, process or None), "title": intent.get("title")}
    return _go(run)
