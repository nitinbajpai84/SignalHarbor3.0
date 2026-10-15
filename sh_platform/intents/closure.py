"""Spec 09: closure and sign-off. The closure screen's data, North's draft, the per-type confirmer, the approver link, close, close with
what we have. The state moves themselves come from lifecycle.py (cancel, confirm, move, close); this file adds the draft, the checks, the
next list's links and the rating window around them.

Every action answers on its spec path and on `PUT /closure` with {"action": ...}; both run the same code and both need the record's
`version` (spec 01). `rating`, `outcome_used` and `closing_started_at` sit at the top of the record (specs 09, 10). An Initiative's
sponsor confirms through the charter signature (ruling 26): the signed charter counts as the sponsor's confirmation.
"""
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import events
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.intents.records import _run as _run_detail
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError

log = logging.getLogger(__name__)
router = APIRouter()
LINK_HOURS = 72           # contracts/charter.yaml approver_link.hours_valid; the guest route reads the contract for its own check
SMALL = 5                 # a per-person figure under five reads "Fewer than five" (ruling 8)
TOKEN = re.compile(r"ci\.([a-z0-9][a-z0-9_-]{0,63})\.((?:ini|bra|pul|prb|dec)-[0-9a-f]{32})\.([A-Za-z0-9_-]{20,64})")
KIND_TYPE = {"initiative": "initiative", "problem": "problem", "decision": "decision"}
MADE_OF = ("card", "reply", "vote", "comment", "note", "answer")
ACTIONS = ("start", "draft", "sign", "send", "withdraw", "close", "close_incomplete", "cancel")
NOT_YET = "Not available yet"
LIST_ROLE = {"participants": "participant", "advisers": "adviser", "affected": "affected", "observers": "observer"}
WHY = {"sponsor": "the sponsor", "decider": "the decider", "owner": "the owner", "reporter": "the reporter"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime | None = None) -> str:
    return (d or _now()).isoformat()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- who is who -------------------------------------------------------------------------------------------------------------

def slot(rec: dict, key: str) -> dict | None:
    p = (rec.get("people") or {}).get(key)
    return p if isinstance(p, dict) else None


def roles_of(rec: dict, viewer) -> set[str]:
    p, r = rec.get("people") or {}, set()
    for s in S.SLOTS:
        if S._named(p.get(s), viewer):
            r.add(s)
    for key, role in (("participants", "participant"), ("advisers", "participant"), ("affected", "affected"), ("observers", "observer")):
        if any(S._named(x, viewer) for x in p.get(key) or []):
            r.add(role)
    return r


def charter_confirm(rec: dict) -> dict | None:
    """An Initiative's sponsor confirms through the charter signature (ruling 26): the signed charter is that confirmation."""
    o = rec.get("outcome") or {}
    if rec["type"] != "initiative" or not o.get("signed_at"):
        return None
    sp = slot(rec, "sponsor") or {}
    return {"role": "sponsor", "by": sp.get("account_id"), "at": o["signed_at"], "name": o.get("signed_by") or sp.get("name", ""), "how": "charter"}


def confirmed(rec: dict) -> list[dict]:
    got = list((rec.get("closure") or {}).get("confirmed") or [])
    cc = charter_confirm(rec)
    return got + [cc] if cc and "sponsor" not in {c["role"] for c in got} else got


def waiting_role(rec: dict) -> str | None:
    done = {c["role"] for c in confirmed(rec)}
    return next((r for r in L.confirmers(rec["type"]) if r not in done), None)


# ---- the outcome block and the checks ---------------------------------------------------------------------------------------

def _text(v) -> str:
    if isinstance(v, list):
        return "; ".join(filter(None, (_text(x) for x in v)))
    if isinstance(v, dict):
        return str(v.get("text") or v.get("title") or v.get("name") or v.get("idea") or "").strip()
    return "" if v is None else str(v).strip()


def _charter_signed(plane, rec: dict) -> bool | None:
    cid = (rec.get("refs") or {}).get("charter_outcome_id")
    if not cid:
        return None
    try:
        d = read_json_strict(plane.path("intents", "m1_intent", "outcomes", f"{cid}.json"), dict)
    except (OSError, ValueError, CrossCompanyError):
        return None
    return bool(d and d.get("signed_at"))


def _weeks(plane, rec: dict) -> dict:
    out = {"problem": 0, "backlog": 0, "handled": 0, "nothing": 0}
    try:
        files = sorted(plane.path("intents", rec["id"], "weeks").glob("*.json"))
    except (OSError, CrossCompanyError):
        return out
    for f in files:
        try:
            for it in (read_json_strict(f, dict) or {}).get("items") or []:
                if it.get("fate") in out:
                    out[it["fate"]] += 1
        except (OSError, ValueError):
            continue
    return out


def outcome_block(plane, rec: dict) -> dict:
    """{lines: [{label, value}], missing: [label]}: what the type's own record says, read only (spec 09, outcome table)."""
    o, t, lines, missing = rec.get("outcome") or {}, rec["type"], [], []

    def line(label: str, value, required: bool = False):
        if _text(value):
            items = [_text(x) for x in value if _text(x)] if isinstance(value, list) and len(value) > 1 else None  # a list reads as a list
            lines.append({"label": label, "value": _text(value)} | ({"items": items} if items else {}))
        elif required:
            missing.append(label)
    if t == "initiative":
        line("Goal", o.get("goal"))
        line("Why", o.get("why"))
        signed = _charter_signed(plane, rec)
        lines.append({"label": "Charter", "value": "Signed" if signed else "Not signed yet"})
        if not signed:
            missing.append("Signed charter")
        br = _build_flag(rec)
        lines.append({"label": "Build-ready", "value": br}) if br else missing.append("Build-ready flag")
        lines.append({"label": "Definitions and maps", "value": f"{NOT_YET}: no confirmed definitions are recorded for this intent"})
    elif t == "brainstorm":
        line("Chosen idea", o.get("chosen"), True)
        line("Runners-up", o.get("runners_up"))
        line("Thinking kept", o.get("ideas_kept"))
    elif t == "pulse":
        w = _weeks(plane, rec)
        lines.append({"label": "Items by fate", "value": ", ".join(f"{k} {v}" for k, v in w.items())})
    elif t == "problem":
        line("Root cause", o.get("root_cause"), True)
        line("Fix", o.get("fix"), True)
        lines.append({"label": "Owner", "value": (slot(rec, "owner") or {}).get("name") or ""}) if slot(rec, "owner") else missing.append("Owner")
    elif t == "decision":
        line("Decision", _option_name(o) or (f"No decision. {o['no_decision_reason']}" if o.get("no_decision_reason") else None), True)
        line("Options considered", o.get("options"))
        line("Why", o.get("why"), True)
        lines.append({"label": "Decided by", "value": (slot(rec, "decider") or {}).get("name") or ""}) if slot(rec, "decider") else missing.append("Decider")
    return {"lines": lines, "missing": missing}


def _option_name(o: dict) -> str:
    """The chosen option's name (spec 43 keeps its id in `chosen`); the snapshot holds it if the live list changed."""
    cid = o.get("chosen")
    if not cid or not isinstance(cid, str):
        return ""
    name = next((x.get("name") or x.get("title") or "" for x in [*(o.get("options") or []), *(o.get("considered_snapshot") or [])]
                 if isinstance(x, dict) and x.get("id") == cid), "")
    return name or ("" if cid.startswith("opt-") else cid)  # an older record kept the choice as text; an id never shows


def _build_flag(rec: dict) -> str | None:
    """Yes once handed to Build, No with the reason once "build needed: no" was answered (spec 33); None while neither."""
    if rec.get("build_handoff") or (rec.get("build_ready") or {}).get("state") == "handed_over":
        return "Yes, handed to Build"
    if rec.get("build_needed") is False:
        return "No" + (f": {rec['build_needed_reason']}" if rec.get("build_needed_reason") else "")
    br = (rec.get("outcome") or {}).get("build_ready")
    return {True: "Yes", False: "No"}.get(br) if isinstance(br, bool) else None


def unmet(plane, rec: dict, incomplete: bool = False) -> str | None:
    """The first unmet check, in the spec's order (journey step 8), in plain words; None when the intent may close."""
    c = rec.get("closure") or {}
    if not str(rec.get("purpose") or "").strip():
        return "Add why this was opened."
    if not incomplete and (m := outcome_block(plane, rec)["missing"]):
        return f"The outcome is missing: {', '.join(m).lower()}."
    nxt = c.get("next") or []
    if not nxt:
        return "Add what happens next. Nothing is a choice, and it needs a reason."
    if any(n.get("kind") not in L.NEXT_KINDS or not str(n.get("reason") or "").strip() for n in nxt):
        return "Add the reason for each next item."
    if (r := waiting_role(rec)):
        who = (slot(rec, r) or {}).get("name")
        return f"Waiting for {WHY[r]}" + (f", {who}." if who else ". Name them first.")
    return None


# ---- contributions (counts only; anonymous and sealed never named) ----------------------------------------------------------

def contributions(plane, iid: str) -> tuple[dict, int, bool]:
    """(count per account id, anonymous count, whether the history exists). Sealed lines are not counted at all."""
    counts, anon, seen = {}, 0, False
    try:
        lines = plane.path("intents", iid, "events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, CrossCompanyError):
        return counts, 0, False
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        seen = True
        if e.get("sealed") or not any(k in str(e.get("kind")) for k in MADE_OF):
            continue
        if e.get("anonymous"):
            anon += 1
        elif (e.get("by") or {}).get("account"):
            counts[e["by"]["account"]] = counts.get(e["by"]["account"], 0) + 1
    return counts, anon, seen


def people_rows(plane, rec: dict) -> dict:
    counts, anon, seen = contributions(plane, rec["id"])
    rows, p = [], rec.get("people") or {}
    singles = [(s, p.get(s)) for s in S.SLOTS]
    lists = [(LIST_ROLE[k], x) for k in S.LISTS for x in p.get(k) or []]
    for role, who in singles + lists:
        if not isinstance(who, dict):
            continue
        n = counts.get(who.get("account_id"))
        label = NOT_YET + ": this type records no contributions" if not seen else "Fewer than five" if (n or 0) < SMALL else str(n)
        rows.append({"name": who.get("name", ""), "role": role, "count": n if (n or 0) >= SMALL else None, "label": label, "unit": "contributions"})
    return {"rows": rows, "anonymous": anon}


# ---- North's draft ----------------------------------------------------------------------------------------------------------

def _src(label: str, ref: str) -> dict:
    return {"label": label, "ref": ref}


def draft_sentences(plane, rec: dict) -> list[dict]:
    """Three to six sentences, each with a source chip. A sentence with no source is dropped. North's own turn (card 08) is used when
    it offers one; otherwise this plain reading of the records, marked as a draft."""
    out = []
    if (rec.get("purpose") or "").strip():
        out.append(("purpose", f"The reason given was: {rec['purpose'].strip().rstrip('.')}.", [_src("Intent record", "intent")]))
    ob = outcome_block(plane, rec)
    if ob["lines"]:
        out.append(("outcome", " ".join(f"{x['label']}: {x['value'].rstrip('.')}." for x in ob["lines"][:3] if NOT_YET not in x["value"]),
                    [_src(f"Outcome, {len(ob['lines'])} line{'s' if len(ob['lines']) != 1 else ''}", "outcome")]))
    ppl = people_rows(plane, rec)
    if ppl["rows"]:
        out.append(("people", (f"{len(ppl['rows'])} people were named in it." if len(ppl["rows"]) != 1 else "1 person was named in it."), [_src(f"People, {len(ppl['rows'])}", "people")]))
    n = int(rec.get("event_count") or 0)
    if n:
        out.append(("events", f"Its history holds {n} recorded event{'s' if n != 1 else ''}.", [_src(f"Events, {n}", "events")]))
    return [{"slot": k, "text": t, "sources": s, "by": "north", "edited_at": None} for k, t, s in out if t.strip()]


def sentences(rec: dict) -> list[dict]:
    """The summary as kept, or, before North's draft, the summary the confirmer's act wrote (a Decision's "Decided: ..."), so a
    closure that has a summary never reads as undrafted."""
    c = rec.get("closure") or {}
    kept = [s for s in c.get("summary_sentences") or [] if s.get("sources") and str(s.get("text") or "").strip()]
    if kept or not str(c.get("summary") or "").strip():
        return kept
    return [{"slot": "summary", "text": str(c["summary"]).strip(), "sources": [_src("Outcome", "outcome")], "by": "north", "edited_at": None}]


def redraft(old: list[dict], fresh: list[dict]) -> list[dict]:
    """Draft again keeps every sentence the organiser edited (spec 09, journey step 4)."""
    edited = {s.get("slot"): s for s in old if s.get("edited_at")}
    return [edited.pop(s["slot"], s) for s in fresh] + list(edited.values())


# ---- edits and actions (each runs inside S.update_intent: lock, version check, index row) -------------------------------------

def _organiser(rec: dict, by: str) -> None:
    L._organiser(rec, by)


def _closing(rec: dict) -> dict:
    if rec["state"] != "closing":
        raise L.Refused(409, "This intent is not being closed now.")
    return rec["closure"]


def _event(plane, rec: dict, kind: str, viewer, now: str, detail: dict | None = None) -> None:
    """One line to events.jsonl through the one writer (spec 16: keys, enums and numbers only); the counter is copied into `rec`, which the caller writes."""
    detail = dict(detail or {})
    if kind == "closure_signed":
        kind, detail = "signed", {"what": "closure", **detail}
    elif kind == "closed_incomplete":
        kind, detail = "closed", {"incomplete": True, **detail}
    who = {"account": viewer.account_id, "name": viewer.name, "role": detail.get("role") or "organiser"}
    events.point_rec(rec, events.try_append(plane, rec["id"], kind, who, None, detail, "act"))


def clear_signatures(c: dict) -> None:
    """Once signed, the text is read-only: an edit clears the signature and asks again (spec 09, rules)."""
    c["confirmed"], c["signature"], c["signed"] = [], None, False
    for l in c.get("links") or []:
        if l["state"] == "open":
            l["state"] = "revoked"


def _answers(a: dict) -> dict:
    """The What next panel's edited start answers: question id to {key: text}, short strings only."""
    return {str(q)[:8]: {str(k)[:40]: (str(v) if not isinstance(v, list) else ", ".join(map(str, v)))[:600] for k, v in list(cell.items())[:8]}
            for q, cell in list(a.items())[:6] if isinstance(cell, dict)}


def edit(rec: dict, viewer, b: dict, now: str, plane) -> None:
    _organiser(rec, viewer.account_id)
    c = _closing(rec)
    before = json.dumps([c.get("why_it_happened"), c.get("summary_sentences"), c.get("next")], sort_keys=True)
    if "why_it_happened" in b:
        c["why_it_happened"] = str(b["why_it_happened"]).strip()[:500]
    if "summary_sentences" in b:
        old = {s.get("slot"): s for s in sentences(rec)}
        new = []
        for i, s in enumerate(b["summary_sentences"] if isinstance(b["summary_sentences"], list) else []):
            text, base = str(s.get("text") or "").strip(), old.get(s.get("slot"))
            sources = s.get("sources") or (base or {}).get("sources")
            if not text or not sources:
                continue  # a sentence with no source chip is not allowed (spec 09)
            new.append(base if base and base["text"] == text else
                       {"slot": s.get("slot") or f"e{i}", "text": text, "sources": sources, "by": viewer.name, "edited_at": now})
        c["summary_sentences"] = new
    if "next" in b:
        rows = b["next"] if isinstance(b["next"], list) else []
        c["next"] = [{"kind": str(n.get("kind") or ""), "title": str(n.get("title") or "").strip()[:200], "ref": n.get("ref"),
                      "reason": str(n.get("reason") or "").strip()[:300],
                      **({"answers": _answers(n["answers"])} if isinstance(n.get("answers"), dict) else {})} for n in rows if isinstance(n, dict)]
    if json.dumps([c.get("why_it_happened"), c.get("summary_sentences"), c.get("next")], sort_keys=True) != before:
        if c.get("confirmed"):
            c["asked_again"] = {"by": viewer.name, "at": now, "roles": [x["role"] for x in c["confirmed"]]}
            clear_signatures(c)
        c["draft_by"] = c.get("draft_by") or viewer.account_id
        _event(plane, rec, "closure_edited", viewer, now)


def _started(rec: dict, now: str) -> None:
    """closing_started_at: the moment the intent last moved to closing (the history says when), set once per closing."""
    if not rec.get("closing_started_at"):
        rec["closing_started_at"] = next((h["at"] for h in reversed(rec.get("history") or []) if h.get("to") == "closing"), now)


def start(rec: dict, viewer, b: dict, now: str, plane) -> None:
    L.move(rec, "closing", viewer.account_id, now, tz=L.company_zone(plane))
    rec["closing_started_at"] = now
    _event(plane, rec, "closing_started", viewer, now)


def cancel(rec: dict, viewer, b: dict, now: str, plane) -> None:
    L.cancel(rec, viewer.account_id, b.get("cancel_reason") if "cancel_reason" in b else b.get("reason"), now)
    _event(plane, rec, "cancelled", viewer, now)


def _next_reason(rec: dict) -> str:
    o = rec.get("outcome") or {}
    if rec["type"] == "decision" and _option_name(o):
        return f"The decision itself is the outcome: {_option_name(o).rstrip('.')}."
    return "North found nothing in the records that needs a follow-on."


def do_draft(rec: dict, viewer, b: dict, now: str, plane) -> None:
    _organiser(rec, viewer.account_id)
    c = _closing(rec)
    _started(rec, now)
    c["summary_sentences"] = redraft(c.get("summary_sentences") or [], draft_sentences(plane, rec))
    c["drafted_at"] = now
    if not c.get("why_it_happened"):
        c["why_it_happened"] = (rec.get("purpose") or "").strip()
    if not c.get("next"):
        c["next"] = [{"kind": "nothing", "title": "", "ref": None, "reason": _next_reason(rec)}]  # North proposes; the organiser may change it
    c["draft_by"] = "north"
    _event(plane, rec, "closure_drafted", viewer, now)


def sign(rec: dict, viewer, b: dict, now: str, plane) -> None:
    c = _closing(rec)
    role = waiting_role(rec)
    if role is None:
        raise L.Refused(409, "Nothing is waiting for a signature.")
    if not S._named(slot(rec, role), viewer):
        raise L.Refused(403, f"Waiting for {WHY[role]}.")
    L.confirm(rec, viewer.account_id, now)
    c["confirmed"][-1].update(name=viewer.name, how="room")
    c["signature"] = {"required": True, "by_role": role, "name": viewer.name, "account_id": viewer.account_id, "at": now, "how": "room"}
    c["send_back"], c["asked_again"] = None, None
    for l in c.get("links") or []:
        if l["state"] == "open" and l["role"] == role:
            l["state"] = "revoked"
    _event(plane, rec, "closure_signed", viewer, now, {"role": role, "how": "room"})


def send(rec: dict, viewer, b: dict, now: str, plane) -> dict:
    _organiser(rec, viewer.account_id)
    c = _closing(rec)
    role = waiting_role(rec)
    if role is None:
        raise L.Refused(409, "Nothing is waiting for a signature.")
    if not slot(rec, role):
        raise L.Refused(409, f"Name {WHY[role]} in the intent first.")
    token = f"ci.{rec['company']}.{rec['id']}.{secrets.token_urlsafe(32)}"
    ends = _iso(datetime.fromisoformat(now) + timedelta(hours=LINK_HOURS))
    links = [{**l, "state": "revoked"} if l["state"] == "open" else l for l in c.get("links") or []]
    c["links"] = [*links, {"hash": _digest(token), "role": role, "issued_at": now, "expires_at": ends, "state": "open"}]
    _event(plane, rec, "closure_link_sent", viewer, now, {"role": role})
    return {"link": f"/approve/{token}", "expires_at": ends, "role": role, "name": slot(rec, role)["name"]}  # shown once; only the hash is kept


def withdraw(rec: dict, viewer, b: dict, now: str, plane) -> None:
    _organiser(rec, viewer.account_id)
    c = _closing(rec)
    if not any(l["state"] == "open" for l in c.get("links") or []):
        raise L.Refused(409, "There is no link out.")
    for l in c["links"]:
        if l["state"] == "open":
            l["state"] = "revoked"
    _event(plane, rec, "closure_link_withdrawn", viewer, now)


def _backlog_links(plane, rec: dict, viewer, now: str) -> None:
    """Backlog rows get their item inside the close (spec 09 journey step 9); intent rows get their child after it (_children)."""
    for n in rec["closure"]["next"]:
        if not n.get("ref") and n["kind"] == "backlog":
            n["ref"] = _backlog_item(plane, rec, n, viewer, now)


def _start_answers(plane, rec: dict, n: dict, kind: str) -> dict:
    """The child's start answers, pre-filled and marked guessed with prefilled_from (spec 20). From a Brainstorm the goal comes from
    the converge pre-fill (spec 37 step 12) with the organiser's edits in the What next panel laid over it."""
    from sh_platform.intents import converge, links
    out = links.prefill(rec, kind, None, area_ids=links.area_ids(plane))
    if rec["type"] == "brainstorm" and kind == "initiative" and "goal" in out:
        i1 = next((q["answers"] for q in converge.prefill(rec)["questions"] if q["id"] == "i1"), {})
        mine = ((n.get("answers") or {}).get("i1") or {})
        line, why = str(mine.get("goal_line") or i1.get("goal_line") or "").strip(), str(mine.get("why") or i1.get("why") or "").strip()
        out["goal"]["value"] = {"line": line[:140] or out["goal"]["value"]["line"], "why": why[:600]}
    return out


def _children(plane, rec: dict, viewer) -> None:
    """After the close is written: one draft child per initiative, problem or decision row, pre-filled, linked on both records
    through links.link_intents (which also writes the row's ref). Runs outside the source's lock: the link writes both records."""
    from sh_platform.intents import links
    for n in [x for x in rec["closure"]["next"] if not x.get("ref") and x["kind"] in KIND_TYPE]:
        kind = KIND_TYPE[n["kind"]]
        title = n.get("title") or links.title_from(links.source_text(rec, None)) or ""
        child = L.new_record(kind, rec["company"], L.person(viewer.account_id, viewer.name), S.now_iso(),
                             title=title, purpose=n["reason"], areas=rec.get("areas"), link_from=rec["id"])
        child["start_answers"] = _start_answers(plane, rec, n, kind)
        S.create_intent(plane, child)
        links.link_intents(plane, rec["id"], child["id"], kind, by=viewer, proposed_by="north", reason=n["reason"])


def _backlog_item(plane, rec: dict, n: dict, viewer, now: str) -> str:
    path, iid = plane.path("intents", "backlog.json"), f"bk-{secrets.token_hex(8)}"
    with lock_for(path):
        doc = read_json_strict(path, dict) or {"items": []}
        doc.setdefault("items", []).append({
            "id": iid, "title": n.get("title") or n["reason"][:80], "kind": "idea", "area": (rec.get("areas") or [None])[0],
            "source": {"intent_id": rec["id"], "type": rec["type"], "stage_ref": "close", "week_key": None, "week_item_id": None},
            "raised_by": viewer.account_id, "raised_at": now, "why_it_matters": {"text": n["reason"], "drafted_by": "north", "edited_by": None, "edited_at": None},
            "source_quote": "", "taps": [], "review_date": "", "status": "open", "parked": None, "dropped": None, "merged_into": None,
            "merged_from": [], "opened_intent": None, "reminded_at": [], "history": [{"at": now, "by": viewer.account_id, "action": "raised", "note": "from closure"}]})
        write_json_atomic(path, doc)
    return iid


def close(rec: dict, viewer, b: dict, now: str, plane, incomplete: bool = False) -> None:
    from sh_platform.intents import ratings
    _organiser(rec, viewer.account_id)
    c = _closing(rec)
    missing = outcome_block(plane, rec)["missing"]
    if incomplete:
        if not missing:
            raise L.Refused(409, "Nothing is missing. Close it the usual way.")
        if not str(b.get("reason") or "").strip():
            raise L.Refused(400, "Please say why it is closing with what we have.")
    no_hand = bool(b.get("no_handoff"))
    if no_hand and (rec["type"] != "initiative" or rec.get("build_handoff")):
        raise L.Refused(409, "There is nothing to close without a hand-off here.")
    if no_hand and not str(b.get("reason") or "").strip():
        raise L.Refused(400, "Please say why this closes without a hand-off to Build.")
    if (why := unmet(plane, rec, incomplete)):
        raise L.Refused(409, why)
    ob = outcome_block(plane, rec)
    sents = sentences(rec)
    if not sents:
        raise L.Refused(400, "Please write a summary before closing. Press Draft it, then check each sentence.")
    first = (ob["lines"] or [{"value": ""}])[0]["value"].strip()
    nxt = [dict(n) for n in c["next"]]
    cc = charter_confirm(rec)
    if cc and "sponsor" not in {x["role"] for x in c.get("confirmed") or []}:
        c.setdefault("confirmed", []).append(cc)  # the charter signature is the sponsor's confirmation (ruling 26)
    _started(rec, now)
    L.close(rec, viewer.account_id, {"summary": " ".join(s["text"] for s in sents),
                                     "why_it_happened": c.get("why_it_happened") or rec.get("purpose", ""), "what_came_out": first, "next": nxt}, now)
    c = rec["closure"]
    c["next"] = nxt
    c.update(summary_sentences=sents, incomplete=incomplete, missing=missing if incomplete else [],
             incomplete_reason=str(b.get("reason")).strip()[:500] if incomplete else None,
             no_handoff_reason=str(b.get("reason")).strip()[:500] if no_hand else None, people_counts=people_rows(plane, rec)["rows"])
    _backlog_links(plane, rec, viewer, now)
    if rec["type"] == "brainstorm" and nxt:
        rec["outcome"]["next"] = {k: nxt[0].get(k) for k in ("kind", "title", "reason")}  # the What next choice (spec 37 screen C)
    ratings.on_close(rec, datetime.fromisoformat(now), L.company_zone(plane))
    _event(plane, rec, "closed_incomplete" if incomplete else "closed", viewer, now, {"next": len(nxt)})


def _act(action: str, request: Request, intent_id: str, b: dict):
    """One closure action by the signed-in person: the answer is the closure view as that person sees it."""
    out: dict = {}

    def go(plane, viewer, now):
        if action not in ACTIONS and action != "edit":
            raise L.Refused(400, "That is not something this screen can do.")
        rec0 = S.read_intent(plane, intent_id)
        if rec0 is None or _tier(plane, rec0, viewer) is None:
            raise LookupError(intent_id)

        def change(rec):
            fn = {"edit": edit, "draft": do_draft, "sign": sign, "withdraw": withdraw, "start": start, "cancel": cancel}.get(action)
            if fn:
                fn(rec, viewer, b, now, plane)
            elif action == "send":
                out.update(send(rec, viewer, b, now, plane))
            else:
                close(rec, viewer, b, now, plane, incomplete=action == "close_incomplete")
        v = b.get("version")
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("Please reload and try again: the version is missing.")  # spec 01: every write names the version it read
        rec = S.update_intent(plane, intent_id, v, change)
        if rec["state"] in ("closed", "cancelled") and action in ("close", "close_incomplete", "cancel"):
            rec = _after_close(plane, rec, viewer, request)
        return {**view(plane, rec, viewer, _names(request)), **({"sent": out} if out else {})}
    return _run(request, go)


def _run(request: Request, fn):
    """records._run, plus the `message` key the screen's client reads: a refusal here shows the server's own sentence."""
    r = _run_detail(request, fn)
    if r.status_code >= 400:
        body = json.loads(r.body)
        if isinstance(body, dict) and "detail" in body and "message" not in body:
            return JSONResponse({**body, "message": body["detail"]}, status_code=r.status_code)
    return r


def _after_close(plane, rec: dict, viewer, request=None) -> dict:
    """After the close is written (ruling R11): open join requests are withdrawn (spec 47), a Problem's write-back runs (spec 42),
    children are written, North's memory pass runs once (spec 46) and the knowledge map hears of it (spec 55). None may undo a
    close: each import and call is guarded, a failure is logged and the record stands."""
    def guard(what, fn):
        try:
            fn()
        except Exception:  # noqa: BLE001 the close is written; a follow-on failure must not turn it into an error
            log.exception("after close: %s failed", what)

    def sweep():
        from sh_platform.intents import affected
        affected.close_sweep(plane, rec["id"])

    def write_back():
        from sh_platform.intents import problem
        problem._close_out(plane, viewer, S.read_intent(plane, rec["id"]) or rec, request)

    def memory():
        from sh_platform.intents import memory_close
        memory_close.write_closure_memory(plane, S.read_intent(plane, rec["id"]) or rec)

    def knowledge_map():  # spec 55 line 155: a close is not an update moment unless the map names one; otherwise the lazy rebuild
        from sh_platform.graph import knowledge_map as km
        if "intent_closed" in km.MOMENTS:
            km.record_moment(plane, "intent_closed", rec["id"], getattr(viewer, "name", "") or viewer.account_id)
        else:
            from sh_platform.graph.hooks import mark_dirty
            mark_dirty(plane)

    guard("close sweep", sweep)
    if rec["state"] == "closed":
        if rec["type"] == "problem":
            guard("problem write-back", write_back)
        guard("closure children", lambda: _children(plane, rec, viewer))
        guard("closure memory", memory)
        guard("knowledge map", knowledge_map)
    return S.read_intent(plane, rec["id"]) or rec


# ---- the view ---------------------------------------------------------------------------------------------------------------

def _tier(plane, rec: dict, viewer) -> str | None:
    return S.tier_of(rec, viewer, S.areas_of(plane, viewer))


def _names(request: Request):
    def name(account_id):
        a = request.app.state.account_store.get(account_id) if account_id else None
        return (a or {}).get("display_name") or ""
    return name


def _day(iso: str | None, tz) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(tz)
    return f"{d.day} {d.strftime('%b')}"


def view(plane, rec: dict, viewer, names) -> dict:
    """The closure screen's record for this person. `card` tier people get the header, why, outcome and strip; no sentences, people or
    sources. Anonymous and sealed material is only ever a count."""
    from sh_platform.intents import ratings
    tier, roles, c = _tier(plane, rec, viewer), roles_of(rec, viewer), rec.get("closure") or {}
    org = S._named(slot(rec, "organiser"), viewer)
    tz, state, full = L.company_zone(plane), rec["state"], _tier(plane, rec, viewer) == "content"
    ob, waiting = outcome_block(plane, rec), waiting_role(rec) if rec["type"] in ("initiative", "problem", "decision") else None
    why = unmet(plane, rec) if state == "closing" else None
    now = _now()
    ends = (rec.get("time_box") or {}).get("ends") or ""
    live_link = next((l for l in c.get("links") or [] if l["state"] == "open"), None)
    who = lambda a: names(a) or "someone"  # noqa: E731
    strip = None
    if state == "closed":
        strip = f"Closed by {who(c.get('closed_by'))} on {_day(c.get('closed_at'), tz)}." + "".join(
            f" Signed by {x.get('name') or 'a named person'} on {_day(x.get('at'), tz)}." for x in confirmed(rec))
        if c.get("incomplete"):
            strip = f"Closed with what we have: {', '.join(c.get('missing') or []).lower()} was missing. Reason: {c.get('incomplete_reason')}"
    out = {
        "id": rec["id"], "type": rec["type"], "title": rec["title"], "state": state, "version": rec["version"], "tier": tier,
        "purpose": rec.get("purpose", ""), "areas": rec.get("areas") or [], "time_zone": getattr(tz, "key", "UTC"),
        "ends": _day(ends, tz), "late": bool(ends) and state in ("open", "in_session", "closing") and now > datetime.fromisoformat(ends),
        "opened_by": who((rec.get("created_by"))), "opened_on": _day(rec.get("created_at"), tz),
        "outcome": ob, "strip": strip, "cancelled": state == "cancelled",
        "cancel": {"reason": c.get("cancel_reason"), "by": who(c.get("closed_by")), "on": _day(c.get("closed_at"), tz)} if state == "cancelled" else None,
        "closed_on": _day(c.get("closed_at"), tz) if state in ("closed", "cancelled") else None,
        "why_it_happened": c.get("why_it_happened") or "", "send_back": c.get("send_back"), "next": c.get("next") or [],
        "asked_again": c.get("asked_again") if state == "closing" else None,
        "links": {"from": (rec.get("links") or {}).get("from"), "to": (rec.get("links") or {}).get("to") or []},
        "rated": rec["type"] != "pulse",
        "you": {"roles": sorted(roles), "organiser": org, "can_start": org and state in ("open", "in_session"), "can_back": org and state == "closing",
                "can_edit": org and state == "closing", "can_draft": org and state == "closing",
                "can_sign": state == "closing" and bool(waiting) and S._named(slot(rec, waiting), viewer),
                "sign_label": {"sponsor": "Sign closure", "decider": "Decide", "owner": "Confirm the fix", "reporter": "Confirm closure"}.get(waiting or "", ""),
                "can_send": org and state == "closing" and bool(waiting) and bool(slot(rec, waiting)), "has_link": bool(live_link),
                "can_close": org and state == "closing" and why is None, "blocked_by": why if org and state == "closing" else None,
                "can_close_incomplete": org and state == "closing" and bool(ob["missing"]),
                "can_cancel": state in ("open", "in_session", "closing") and org or state == "draft" and rec.get("created_by") == viewer.account_id}}
    done = confirmed(rec)
    out["signature"] = [{"role": r, "name": (slot(rec, r) or {}).get("name") or "", "state": "signed" if r in {x["role"] for x in done} else "waiting",
                         "at": _day(next((x["at"] for x in done if x["role"] == r), None), tz),
                         "how": next((x.get("how") for x in done if x["role"] == r), None)} for r in L.confirmers(rec["type"])]
    out["build_link"] = f"/centre/build/gap-analysis?from={rec['id']}" if state == "closed" and (_build_flag(rec) or "").startswith("Yes") else None
    out["build_ready"] = _build_strip(rec, org, state)
    out["link_out"] = {"role": live_link["role"], "expires_at": live_link["expires_at"]} if live_link and org else None
    if full:
        sents = sentences(rec)
        ppl = people_rows(plane, rec)
        out.update(sentences=sents, drafted=bool(sents), people=ppl["rows"], anonymous_count=ppl["anonymous"],
                   panels=_panels(rec, ob, ppl), rating=ratings.view(plane, rec, viewer, roles, names, now), editable_outcome=org and state == "closing")
    return out


def requirements(rec: dict) -> list[dict]:
    """What closing needs, each with whether it is done and where to do it (spec 09): the build answer, summary, next step, sponsor signature."""
    c, iid = rec.get("closure") or {}, rec["id"]
    nxt = c.get("next") or []
    sponsor = (slot(rec, "sponsor") or {}).get("name")
    return [
        {"key": "build", "label": "Say whether Build is needed", "done": _build_flag(rec) is not None, "href": f"/centre/intent/{iid}/build-ready"},
        {"key": "summary", "label": "Write the summary", "done": bool(sentences(rec)), "href": "#close-summary"},
        {"key": "next", "label": "Say what happens next", "done": bool(nxt) and all(n.get("kind") in L.NEXT_KINDS and str(n.get("reason") or "").strip() for n in nxt), "href": "#close-next"},
        {"key": "sponsor", "label": "Sponsor signature" + (f" ({sponsor})" if sponsor else ""), "done": waiting_role(rec) is None, "href": "#close-signature"},
    ]


def _build_strip(rec: dict, org: bool, state: str) -> dict | None:
    """Spec 33 panel C: the stored check for an Initiative (counts only, no names), and whether the organiser may close without a hand-off."""
    if rec["type"] != "initiative" or state == "draft":
        return None
    br, lines = rec.get("build_ready") or {}, (rec.get("build_ready") or {}).get("lines") or []
    n_ok, handed = sum(1 for x in lines if x.get("ok")), bool(rec.get("build_handoff"))
    if handed:
        text = "Handed to Build."
    elif not lines:
        text = "Not checked yet."
    elif rec.get("build_needed") is False:
        text = "No build needed. This Initiative closes with its charter and glossary."
    elif br.get("state") == "ready":
        text = "Build-ready. Ready to hand to Build."
    else:
        text = f"Not build-ready: {len(lines) - n_ok} items missing"
    return {"text": text, "n_ok": n_ok, "of": len(lines) or 7, "handed": handed, "href": f"/centre/intent/{rec['id']}/build-ready",
            "can_skip": org and state == "closing" and not handed and (br.get("state") != "ready" or rec.get("build_needed") is False),
            "skipped_reason": (rec.get("closure") or {}).get("no_handoff_reason"), "requirements": requirements(rec)}


def _panels(rec: dict, ob: dict, ppl: dict) -> dict:
    """What a source chip opens: read-only lines from the records the sentence came from, never an anonymous or sealed item."""
    return {"intent": [{"label": "Purpose", "value": rec.get("purpose", "")}, {"label": "Opened on", "value": rec.get("created_at", "")[:10]}],
            "outcome": ob["lines"], "people": [{"label": r["role"], "value": r["name"]} for r in ppl["rows"]],
            "events": [{"label": "Recorded events", "value": str(rec.get("event_count") or 0)}]}


# ---- routes -----------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/{intent_id}/closure")
def get_intents_by_intent_id_closure(request: Request, intent_id: str):
    def go(plane, viewer, now):
        rec = S.read_intent(plane, intent_id)
        if rec is None or _tier(plane, rec, viewer) is None:
            raise LookupError(intent_id)
        return view(plane, rec, viewer, _names(request))
    return _run(request, go)


@router.put("/api/intents/{intent_id}/closure")
def put_intents_by_intent_id_closure(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(str(body.get("action") or "edit"), request, intent_id, body)


def _spec_route(path: str, action: str):
    def handler(request: Request, intent_id: str, body: dict = Body(default={})):
        return _act(action, request, intent_id, body)
    router.add_api_route(path, handler, methods=["POST"], name=f"closure_{action}")


# ponytail: the same code answers the spec's own paths; they work once route_permissions.yaml declares them
for _p, _a in (("/closure/draft", "draft"), ("/closure/confirm", "sign"), ("/closure/sign", "sign"), ("/closure/send", "send"),
               ("/closure/withdraw", "withdraw"), ("/close", "close"), ("/close-incomplete", "close_incomplete")):
    _spec_route("/api/intents/{intent_id}" + _p, _a)


# ---- the approver by link (called by modules/m1_intent/api/closure_approver.py) ----------------------------------------------

class LinkGone(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _link_ground(plane, rec: dict | None, token: str) -> tuple[dict, dict]:
    """(record, link) for a token that is good now. A wrong token gives one answer; a used, withdrawn or old one says which."""
    found = None
    for l in ((rec or {}).get("closure") or {}).get("links") or []:
        if hmac.compare_digest(l["hash"], _digest(token)):  # every link is compared: the time does not show which matched
            found = l
    if rec is None or found is None:
        raise LinkGone("This link is not working. Please ask for a new one.", 404)
    if found["state"] != "open" or rec["state"] != "closing":
        raise LinkGone("This link has been used or withdrawn. Please ask for a new one.")
    if datetime.fromisoformat(found["expires_at"]) <= _now():
        raise LinkGone("This link has expired. Please ask for a new one.")
    return rec, found


def approver_read(plane, token: str) -> dict:
    m = TOKEN.fullmatch(token)
    rec = S.read_intent(plane, m.group(2)) if m else None
    rec, link = _link_ground(plane, rec, token)
    c, ob = rec["closure"], outcome_block(plane, rec)
    p = slot(rec, link["role"])
    return {"title": rec["title"], "purpose": rec.get("purpose", ""), "role": link["role"], "approver_name": (p or {}).get("name", ""),
            "expires_at": link["expires_at"], "sentences": [s["text"] for s in sentences(rec)],
            "outcome": ob["lines"], "missing": ob["missing"], "next": [{"kind": n["kind"], "title": n.get("title", ""), "reason": n["reason"]} for n in c.get("next") or []]}


def approver_decide(plane, token: str, decision: str, comment: str) -> dict:
    """Approve (signs for the named person, how: approver) or send back (a comment is needed, the signature is cleared). One use."""
    m = TOKEN.fullmatch(token)
    if m is None:
        raise LinkGone("This link is not working. Please ask for a new one.", 404)
    now = _iso()

    def change(rec):
        rec, link = _link_ground(plane, rec, token)
        c, p = rec["closure"], slot(rec, link["role"]) or {}
        link["state"] = "used"
        if decision == "approve":
            c["confirmed"] = [*(c.get("confirmed") or []), {"role": link["role"], "by": p.get("account_id"), "at": now, "name": p.get("name", ""), "how": "approver"}]
            c["signature"] = {"required": True, "by_role": link["role"], "name": p.get("name", ""), "account_id": p.get("account_id"), "at": now, "how": "approver"}
            c["send_back"] = None
        else:
            if not comment.strip():
                raise L.Refused(422, "Please say why, so the organiser knows what to change.")
            c["send_back"] = {"by": p.get("name", ""), "at": now, "comment": comment.strip()[:1000]}
            clear_signatures(c)
            link["state"] = "used"  # clear_signatures revokes open links; this one is used, not revoked
        rec["history"].append({"at": now, "by": p.get("account_id") or "approver", "from": "closing", "to": "closing", "note": f"closure {decision} by link"})
    rec0 = S.read_intent(plane, m.group(2))
    if rec0 is None:
        raise LinkGone("This link is not working. Please ask for a new one.", 404)
    try:
        S.update_intent(plane, rec0["id"], rec0["version"], change)
    except L.Refused as e:
        raise LinkGone(e.message, e.status) from None
    return {"decision": decision}


from sh_platform.intents import ratings  # noqa: E402  the rating routes ride on this router (no card owns app.py)
router.include_router(ratings.router)
from modules.m1_intent.api import closure_approver  # noqa: E402  guest route under /api/modules/m1_intent/ (declared in the manifest)
router.include_router(closure_approver.router, prefix="/api/modules/m1_intent")
