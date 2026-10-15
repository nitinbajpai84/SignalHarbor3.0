"""IC v2 (37): Brainstorm converge, the outcome card and late thoughts.

Back up to three ideas, counts never who. Seat keys live in `intents/<id>/converge_votes.json` while a round is open and the file is
deleted at round close. Everything else sits in the intent record's `outcome` object (keys chosen, ideas_kept, dropped, rounds, next,
converge, late_window, late_thoughts, frozen_at: the record's key set is strict, so they ride inside `outcome` until 01 lists them).

Reshaped from modules/m1_intent/domain/together.py (the kernel cannot import a module): `vote` becomes `back` (one value, take-back kept),
`tally` is copied for the single value "back". The ties-to-the-organiser rule replaces `auto_decision`.
Routes are declared in route_permissions.yaml; the stubs of the same paths in brainstorm.py must sit behind this router (see the report).
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, events
from sh_platform.intents import access as A
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view as pview

log = logging.getLogger(__name__)
router = APIRouter()

BOARD = Path(__file__).resolve().parents[2] / "modules" / "m1_intent" / "contracts" / "board.yaml"
# ponytail: used only when board.yaml has no `converge` block yet; the block (spec 37 "Records") is the place to change them.
DEFAULTS = {"max_backs": 3, "max_rounds": 2, "round_2_max_backs": 1, "top_n": 3, "runners_up": 2, "late_window_working_days": 1}
OPEN_STATES = ("round_1_open", "round_2_open")
CLOSED_STATES = ("round_1_closed", "round_2_closed")
WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five"}
USED_ALL = "You have used all three. Take one back first."
OUTCOME_KEYS = {"chosen": None, "ideas_kept": [], "dropped": [], "rounds": [], "next": None, "late_window": None, "late_thoughts": [],
                "frozen_at": None}


@lru_cache(maxsize=1)
def contract() -> dict:
    doc = yaml.safe_load(BOARD.read_text(encoding="utf-8")) or {}
    return {**DEFAULTS, **(doc.get("converge") or {}), "comment_chars": int((doc.get("limits") or {}).get("comment_chars", 300))}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- the record's outcome object -----------------------------------------------------------------------------------------------

def ensure(rec: dict) -> dict:
    oc = rec.setdefault("outcome", {})
    for k, v in OUTCOME_KEYS.items():
        if k not in oc or (isinstance(v, list) and not isinstance(oc[k], list)):
            oc[k] = [] if isinstance(v, list) else v
    for k in ("ideas_kept", "dropped"):  # a line typed by hand on the outcome card has text and no ref: it counts for nothing, but never breaks a read
        oc[k] = [i for i in oc[k] if isinstance(i, dict)]
        for i in oc[k]:
            i.setdefault("ref", "")
    cv = oc.get("converge")
    if not isinstance(cv, dict):
        c = contract()
        oc["converge"] = {"state": "not_open", "max_backs": c["max_backs"], "max_rounds": c["max_rounds"]}
    return oc


# ---- people ----------------------------------------------------------------------------------------------------------------------

def _seat_entry(p) -> bool:
    """A participant who has not declined or been removed holds a seat (35 and 36 write `status`)."""
    return not isinstance(p, dict) or p.get("status") in (None, "Accepted")


def _key(p) -> str:
    p = {"account_id": p, "name": p} if isinstance(p, str) else (p or {})
    return str(p.get("account_id") or p.get("person_id") or pview.norm(p.get("name") or ""))


def seats(rec: dict) -> int:
    """m in "n of m have backed": the seated participants plus the organiser, each once."""
    p = rec.get("people") or {}
    return len({k for k in [_key(p.get("organiser")), *(_key(x) for x in p.get("participants") or [] if _seat_entry(x))] if k})


def relation(rec: dict, me: A.Me) -> dict:
    """The viewer in this brainstorm. `seated`: organiser or an accepted participant (observers and the sponsor read, never back)."""
    roles = A.roles_of(rec, me)
    org = "organiser" in roles
    mine = [e for e in A._entries((rec.get("people") or {}).get("participants")) if A._is_me(e, me)]
    seated = org or (bool(mine) and all(_seat_entry(e) for e in mine))
    sponsor = A._named(rec, "sponsor", me)
    return {"organiser": org, "seated": seated, "reader": "content" in roles or sponsor, "sponsor": sponsor, "roles": roles}


def seat_key(intent_id: str, account_id: str) -> str:
    return hashlib.sha256(f"{intent_id}:{account_id}".encode()).hexdigest()[:16]


# ---- the open round: votes by seat key (together.py, reshaped) ----------------------------------------------------------------------

def _votes_file(plane, iid: str):
    return plane.path("intents", iid, "converge_votes.json")


def read_votes(plane, iid: str, n: int) -> dict:
    try:
        doc = read_json_strict(_votes_file(plane, iid), dict)
    except (OSError, ValueError):
        raise L.Refused(500, S.UNREADABLE) from None
    return doc if doc and doc.get("round") == n and isinstance(doc.get("votes"), dict) else {"round": n, "votes": {}}


def back(votes: dict, ref: str, seat: str, on: bool) -> dict:
    """The seat's back on the candidate; `on` False takes it back (together.vote with None)."""
    mine = {k: v for k, v in votes.get(ref, {}).items() if k != seat}
    if on:
        mine[seat] = "back"
    return {**votes, ref: mine}


def tally(votes: dict, ref: str) -> int:
    return sum(1 for o in votes.get(ref, {}).values() if o == "back")


def drop_votes(plane, iid: str) -> None:
    with lock_for(_votes_file(plane, iid)):
        _votes_file(plane, iid).unlink(missing_ok=True)


# ---- ranking: the top three and ties go to the organiser ---------------------------------------------------------------------------

def plan_top(counts: dict, order: list[str], n: int, picks: list[str] | None = None) -> tuple[list[str], dict | None]:
    """The refs that go forward, and the tie on the cut line when there is one. Only backed ideas go forward. Equal counts only."""
    ranked = sorted((r for r in order if counts.get(r, 0) > 0), key=lambda r: -counts[r])
    if len(ranked) <= n:
        return ranked, None
    cut = counts[ranked[n - 1]]
    sure = [r for r in ranked if counts[r] > cut]
    tied = [r for r in ranked if counts[r] == cut]
    free = n - len(sure)
    if len(tied) <= free:
        return sure + tied, None
    tie = {"among": tied, "free": free, "count": cut}
    if picks and len(picks) == free and set(picks) <= set(tied):
        return sure + list(picks), {**tie, "resolved": True, "picks": list(picks)}
    return sure, {**tie, "resolved": False, "picks": []}


def leaders(counts: dict, order: list[str]) -> list[str]:
    top = max((counts.get(r, 0) for r in order), default=0)
    return [r for r in order if top > 0 and counts.get(r, 0) == top]


# ---- candidates: groups and cards of the live session --------------------------------------------------------------------------------

def candidates(plane, rec: dict) -> list[dict]:
    """Groups first, then cards: read from `intents/<id>/ideas.json` (36). A withdrawn idea is never a candidate; an anonymous one carries no name."""
    try:
        doc = read_json_strict(plane.path("intents", rec["id"], "ideas.json"), dict) or {}
    except (OSError, ValueError):
        raise L.Refused(500, S.UNREADABLE) from None
    live = {i["id"]: i for i in doc.get("ideas") or [] if not i.get("withdrawn") and " ".join(str(i.get("text") or "").split())}
    where = {x: g["id"] for g in doc.get("groups") or [] for x in g.get("idea_ids") or [] if x in live}
    from sh_platform.intents.brainstorm import mask_names, read_names  # late import: brainstorm imports this module
    names = read_names(plane, rec, doc)
    cards = [{"ref": f"c:{iid}", "kind": "card", "text": " ".join((mask_names(i["text"], names) if i.get("anonymous") is True else i["text"]).split())[:600], "group": where.get(iid), "anonymous": i.get("anonymous") is True,
              "from": None if i.get("anonymous") is True else i.get("author") or None, "replies": len(i.get("replies") or [])} for iid, i in live.items()]
    groups = []
    for g in doc.get("groups") or []:
        inside = [c for c in cards if c["group"] == g["id"]]
        if inside:
            groups.append({"ref": f"g:{g['id']}", "kind": "group", "text": str(g.get("name") or "A group"), "group": None, "anonymous": False, "from": None,
                           "replies": sum(c["replies"] for c in inside), "note_count": len(inside), "samples": [c["text"][:80] for c in inside[:3]]})
    return groups + cards


def members(cands: list[dict], ref: str) -> list[dict]:
    return [c for c in cands if c["ref"] == ref or (ref.startswith("g:") and c["kind"] == "card" and f"g:{c['group']}" == ref)]


# ---- the record view -----------------------------------------------------------------------------------------------------------------

def _count(entry: dict, n: int) -> int:
    return int((entry.get("backed") or {}).get(f"round{n}") or 0)


def _round_refs(oc: dict, cands: list[dict]) -> list[str]:
    rounds = oc["rounds"]
    return list(rounds[-1]["candidates"]) if rounds else [c["ref"] for c in cands]


def counts_now(plane, rec: dict, cands: list[dict]) -> dict:
    oc = ensure(rec)
    n = len(oc["rounds"])
    if oc["converge"]["state"] in OPEN_STATES:
        votes = read_votes(plane, rec["id"], n)["votes"]
        return {r: tally(votes, r) for r in _round_refs(oc, cands)}
    kept = {i["ref"]: i for i in oc["ideas_kept"]}
    return {r: _count(kept.get(r, {}), n) for r in _round_refs(oc, cands)}


def ranking(oc: dict, counts: dict) -> dict:
    """Closed round: the top three with the tie dialog's data, and a tie at first place."""
    order = list(counts)
    last = oc["rounds"][-1] if oc["rounds"] else {}
    top, tie = plan_top(counts, order, contract()["top_n"], last.get("tie_picks"))
    lead = leaders(counts, order)
    return {"top": top, "tie": tie, "lead": lead, "lead_tie": len(lead) > 1}


def round2_block(state: str, n: int, first_round: int, rank: dict | None) -> str | None:
    """Why "Run round 2" is not offered, or None when it is."""
    c = contract()
    if state != "round_1_closed":
        return "Round 2 has already run." if n >= c["max_rounds"] and state != "not_open" and state not in OPEN_STATES else "Close the count first."
    if first_round < c["top_n"]:
        return "Only two ideas, so no second round."
    if rank["tie"] and not rank["tie"]["resolved"]:
        return "Pick which ideas go forward first."
    return None if len(rank["top"]) >= 2 and n < c["max_rounds"] else "Fewer than two ideas were backed, so no second round."


def north_line(state: str, have: int, m: int, counts: dict, texts: dict, rank: dict | None) -> str:
    if state in OPEN_STATES:
        return f"{have} of {m} have backed." if have else "Waiting for the first back."
    if rank and rank["lead_tie"]:
        return f"{WORDS.get(len(rank['lead']), str(len(rank['lead'])))} ideas are tied at the top. You decide."
    if rank and rank["lead"]:
        r = rank["lead"][0]
        return f"\"{texts[r][:60]}\" leads with {counts[r]} backed."
    return "Waiting for the first back."


def _row(c: dict, counts: dict, mine: set, rank: dict | None, closed: bool) -> dict:
    r = c["ref"]
    row = {k: c[k] for k in ("ref", "kind", "text", "group", "anonymous", "from") if k in c}
    row |= {"backed": counts.get(r, 0), "i_backed": r in mine, "replies": c["replies"]}
    if c["kind"] == "group":
        row |= {"note_count": c["note_count"], "samples": c["samples"]}
    if closed and rank:
        row["top"] = r in rank["top"]
        for grp in ([rank["lead"]] if rank["lead_tie"] else []) + ([rank["tie"]["among"]] if rank["tie"] else []):
            if r in grp:
                row["tie"] = len(grp) - 1
    return row


def build_view(plane, rec: dict, viewer, rel: dict, namer) -> dict:
    """Everything the converge screen, the outcome card and the late-thought panel read, cut for this viewer."""
    oc, c = ensure(rec), contract()
    cv = oc["converge"]
    cands = candidates(plane, rec)
    refs = set(_round_refs(oc, cands))
    live = [x for x in cands if x["ref"] in refs]
    texts = {x["ref"]: x["text"] for x in cands}
    n = len(oc["rounds"])
    state = cv["state"]
    opened, closed = state in OPEN_STATES, state in CLOSED_STATES or state == "done"
    counts = counts_now(plane, rec, cands)
    votes = read_votes(plane, rec["id"], n)["votes"] if opened else {}
    mine = {r for r, v in votes.items() if viewer.account_id and seat_key(rec["id"], viewer.account_id) in v} if opened else set()
    have = len({s for v in votes.values() for s in v}) if opened else (oc["rounds"][-1].get("people_backed") if closed and n else 0)
    rank = ranking(oc, counts) if closed and n else None
    m = seats(rec)
    max_backs = c["round_2_max_backs"] if n == 2 else cv["max_backs"]
    rows = []
    for x in live:
        if x["kind"] == "group":
            inside = [y for y in live if y["kind"] == "card" and y["group"] == x["ref"][2:]]
            rows.append({**_row(x, counts, mine, rank, closed), "cards": [_row(y, counts, mine, rank, closed) for y in inside]})
    grouped = {y["ref"] for r in rows for y in r["cards"]}
    rows += [_row(x, counts, mine, rank, closed) for x in live if x["kind"] == "card" and x["ref"] not in grouped]
    org = rel["organiser"]
    cap = {"open": None if state == "not_open" else "The count has already opened.",
           "close": None if opened and have else "The count is closed." if not opened else "Nobody has backed yet.",
           "round2": round2_block(state, n, len(oc["rounds"][0]["candidates"]) if n else len(cands), rank)}
    out = {
        "id": rec["id"], "title": rec["title"], "intent_state": rec["state"], "tier": "content", "tz": str(getattr(L.company_zone(plane), "key", "UTC")),
        "viewer": {"organiser": org, "seated": rel["seated"], "can_back": rel["seated"] and opened},
        "converge": {"state": state, "round": n or None, "max_rounds": cv["max_rounds"], "max_backs": max_backs, "used": len(mine)},
        "have_backed": have, "seated_count": m, "rows": rows,
        "mine": [{"ref": r, "text": texts.get(r, "")} for r in mine], "tie": rank["tie"] if rank else None,
        "north": north_line(state, have or 0, m, counts, texts, rank), "ends": (rec.get("time_box") or {}).get("ends"),
        "can": cap if org else {}, "next_kinds": list(L.NEXT_KINDS), "outcome": outcome_view(rec, org, rel),
        "late": late_view(plane, rec, rel, viewer, namer, cands),
    }
    if org or rel["sponsor"]:
        out["numbers"] = numbers(rec, cands)
    if oc["chosen"] and org:  # the Initiative and backlog previews are the organiser's (spec 37, screen C)
        out["prefill"] = prefill(rec)
        out["backlog_preview"] = backlog_preview(rec)
    if closed and rank:
        out["candidates"] = [{"ref": r, "text": texts.get(r, ""), "backed": counts[r], "top": r in rank["top"]} for r in counts]
    return out


# ---- the outcome ---------------------------------------------------------------------------------------------------------------------

def _plural(k: int, one: str, many: str) -> str:
    return f"{k} {one if k == 1 else many}"


def draft_chosen(rec: dict, cands: list[dict], counts: dict, ref: str, now: str) -> dict:
    """North's draft for one candidate. Every `why` sentence carries its source; a sentence it cannot source is not written."""
    oc = ensure(rec)
    n, cand = len(oc["rounds"]), next(x for x in cands if x["ref"] == ref)
    cards = members(cands, ref) if cand["kind"] == "group" else [cand]
    cards = [x for x in cards if x["kind"] == "card"]
    if cand["kind"] == "group":
        said = "; ".join(f"\"{x['text'][:80]}\"" for x in cards[:3])
        idea = f"{cand['text']}. {_plural(len(cards), 'idea sits', 'ideas sit')} in this group, among them {said}."
    else:
        idea = cand["text"]
    b, m = counts.get(ref, 0), seats(rec)
    others = sorted((v for r, v in counts.items() if r != ref), reverse=True)
    why = [{"text": f"{b} of {m} backed it.", "source": f"{b} of {m} backed"}]
    r1 = _count(next((i for i in oc["ideas_kept"] if i["ref"] == ref), {}), 1)
    if n == 2:
        why.append({"text": f"It had {r1} backs in round 1 and {b} in round 2.", "source": "Round 2"})
    elif others:
        why.append({"text": f"It had {b} backs against {others[0]} for the next idea.", "source": f"Round {n}"})
    k = sum(x["replies"] for x in cards)
    if k:
        why.append({"text": f"{_plural(k, 'comment was', 'comments were')} added to it in the session.", "source": _plural(k, "comment", "comments")})
    names = list(dict.fromkeys(x["from"] for x in cards if x["from"]))
    takes = [{"text": f"Talk with {nm}, who raised it, about taking it forward.", "source": f"Card by {nm}"} for nm in names]
    takes.append({"text": "Name who will take this forward, and by when.", "source": "north_suggestion"})
    return {"idea": idea, "why": " ".join(w["text"] for w in why), "why_sources": why, "kind": cand["kind"], "ref": ref, "what_it_takes": takes,
            "proposed_by": [{"name": nm, "account_id": None} for nm in names], "proposed_unnamed": sum(1 for x in cards if x["anonymous"]),
            "backed": b, "backed_of": m, "overridden_reason": None, "drafted_by": "north", "drafted_at": now, "edited_by": None,
            "edited_at": None, "confirmed_by": None, "confirmed_at": None}


def mark_runners_up(oc: dict, counts: dict, chosen_ref: str) -> None:
    rest = sorted((r for r in counts if r != chosen_ref), key=lambda r: -counts[r])[:contract()["runners_up"]]
    for i in oc["ideas_kept"]:
        i["runner_up"] = i["ref"] in rest


def _split(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def outcome_view(rec: dict, org: bool, rel: dict) -> dict:
    oc = ensure(rec)
    ch = oc["chosen"]
    pub = rec["state"] == "closed" or rel["reader"]
    if not ch or not pub:
        return {"chosen": None, "ideas_kept": [], "next": oc.get("next"), "rounds": len(oc["rounds"])}
    keep = ("idea", "why", "why_sources", "kind", "ref", "what_it_takes", "proposed_by", "proposed_unnamed", "backed", "backed_of", "overridden_reason",
            "drafted_by", "fallback", "edited_by", "confirmed_by", "confirmed_at")
    chosen = {k: ch.get(k) for k in keep}
    chosen["proposed_by"] = [{"name": p["name"]} for p in ch.get("proposed_by") or []]
    chosen["by_rounds"] = {f"round{i + 1}": (next((_count(e, i + 1) for e in oc["ideas_kept"] if e["ref"] == ch["ref"]), 0)) for i in range(len(oc["rounds"]))}
    kept = [{k: i.get(k) for k in ("ref", "kind", "text", "from", "anonymous", "backed", "runner_up") if k != "from" or not i.get("anonymous")}
            for i in oc["ideas_kept"] if i["ref"] != ch["ref"]] if rel["reader"] else []  # people only affected read the outcome, not the runners-up
    return {"chosen": chosen, "ideas_kept": kept, "dropped": [{"ref": d["ref"], "text": d["text"]} for d in oc["dropped"]] if org else [],
            "next": oc.get("next"), "rounds": len(oc["rounds"]), "confirmed": bool(ch.get("confirmed_at"))}


def numbers(rec: dict, cands: list[dict]) -> dict:
    oc = ensure(rec)
    miss = lambda what: {"missing": what}  # noqa: E731
    r0, ch = (oc["rounds"] or [{}])[0], oc["chosen"] or {}
    spent = sum(_count(i, k) for i in oc["ideas_kept"] for k in (1, 2))
    mins = None
    if r0.get("opened_at") and ch.get("confirmed_at"):
        mins = round((datetime.fromisoformat(ch["confirmed_at"]) - datetime.fromisoformat(r0["opened_at"])).total_seconds() / 60)
    return {
        "ideas_added": sum(1 for c in cands if c["kind"] == "card"), "groups": sum(1 for c in cands if c["kind"] == "group"),
        "backs_cast": spent if oc["rounds"] and oc["rounds"][-1].get("closed_at") else miss("no count has closed yet"),
        "people_backed": [r.get("people_backed") for r in oc["rounds"] if r.get("closed_at")] or miss("no count has closed yet"),
        "rounds_run": len([r for r in oc["rounds"] if r.get("closed_at")]),
        "minutes_to_confirm": mins if mins is not None else miss("the outcome is not confirmed yet"),
    }


def prefill(rec: dict) -> dict:
    """The six Initiative start questions with what this outcome can fill (spec 37 step 12). Marked "From the brainstorm"; Q3, Q4, Q6 stay empty."""
    ch, p = ensure(rec)["chosen"] or {}, rec.get("people") or {}
    why = " ".join([ch.get("why") or "", *(f"{t['text']}" for t in ch.get("what_it_takes") or [])]).strip()
    why = why if len(why) <= 600 else (ch.get("why") or "")[:600]
    who = list(dict.fromkeys([*(x["name"] for x in ch.get("proposed_by") or []),
                              *(x.get("name") for x in p.get("participants") or [] if isinstance(x, dict) and x.get("name"))]))
    leads = {q["id"]: q["lead"] for q in L.type_def("initiative")["start_questions"]}
    rows = [("i1", {"goal_line": (ch.get("idea") or "")[:140], "why": why}), ("i2", {"involve": who}), ("i3", {}), ("i4", {}),
            ("i5", {"areas": list(rec.get("areas") or [])}), ("i6", {})]
    # 57: a Brainstorm opened from an opportunity hands its hypothesis to the Initiative its What next makes (initiative.inherited_ref)
    return {"questions": [{"id": i, "lead": leads.get(i, ""), "answers": a, "from_brainstorm": any(a.values())} for i, a in rows],
            "hypothesis_ref": rec.get("hypothesis_ref") or ch.get("hypothesis_ref")}


def backlog_preview(rec: dict) -> dict:
    oc = ensure(rec)
    ch = oc["chosen"] or {}
    named = [x["name"] for x in ch.get("proposed_by") or []]
    return {"title": ch.get("idea"), "why": ch.get("why"), "raised_by": ", ".join(named) if named else "unnamed",
            "also_considered": [i["text"] for i in oc["ideas_kept"] if i.get("runner_up")], "review_date": None}


# ---- late thoughts -------------------------------------------------------------------------------------------------------------------

def _names_choice(rec: dict) -> bool:
    """Late thoughts follow the intent's names rule: a choice when the organiser allowed hidden names at the start (35), else by name."""
    return ensure(rec).get("anonymous_ideas") is not False


def _late_open(oc: dict, now: datetime) -> bool:
    w = oc.get("late_window")
    return bool(w) and not oc.get("frozen_at") and now < datetime.fromisoformat(w["closes_at"])


def late_view(plane, rec: dict, rel: dict, viewer, namer, cands: list[dict]) -> dict | None:
    oc = ensure(rec)
    w = oc["late_window"]
    if not w:
        return None
    opened = _late_open(oc, _now())
    rows = [{"text": t["text"], "about": next((x["text"] for x in cands if x["ref"] == t["about"]), ""), "at": t["at"],
             "anonymous": t["anonymous"], "name": None if t["anonymous"] else namer(t["by"])} for t in oc["late_thoughts"]]
    if not rel["reader"]:  # the company admin reads by-name thoughts only
        rows = [r for r in rows if not r["anonymous"]]
    abouts = [{"ref": oc["chosen"]["ref"], "text": oc["chosen"]["idea"][:80]}] if oc["chosen"] else []
    abouts += [{"ref": i["ref"], "text": i["text"][:80]} for i in oc["ideas_kept"] if i.get("runner_up")]
    return {"opens_at": w["opens_at"], "closes_at": w["closes_at"], "open": opened, "frozen_at": oc.get("frozen_at"),
            "can_add": opened and rel["seated"], "names": "choice" if _names_choice(rec) else "named", "limit": contract()["comment_chars"],
            "about": abouts, "thoughts": rows}


# ---- writes ---------------------------------------------------------------------------------------------------------------------------

def _mutate(plane, intent_id: str, change) -> tuple[dict, list]:
    """Read fresh, change under the store's version check (retried twice), then append the events the change asked for."""
    for attempt in range(3):
        rec = S.read_intent(plane, intent_id)
        if rec is None:
            raise L.Refused(404, S.NOT_FOUND)
        ev: list = []
        try:
            out = S.update_intent(plane, intent_id, rec["version"], lambda r: change(r, ev))
        except S.VersionConflict:
            if attempt == 2:
                raise
            continue
        for e in ev:
            _append_event(plane, intent_id, e)
        return out, ev
    raise S.VersionConflict()


def _event(rec: dict, ev: list, kind: str, by: dict | None, detail: dict | None = None, *, agent: str | None = None, anonymous: bool = False) -> None:
    ev.append({"kind": kind, "by": by, "agent": agent, "anonymous": anonymous, "detail": detail or {}})
    rec["event_count"] = int(rec.get("event_count") or 0) + 1


def _append_event(plane, intent_id: str, e: dict) -> None:
    """One line per count close, tie pick, confirm and late thought, through the one writer; never a seat, never who backed, no free text."""
    if e["agent"]:
        events.try_append(plane, intent_id, e["kind"], e["agent"], None, e["detail"], "draft", stage="choose")
    else:
        events.try_append(plane, intent_id, e["kind"], e["by"], None, e["detail"], "act", stage="choose", anonymous=e["anonymous"])


def _who(viewer) -> dict:
    return {"account": viewer.account_id, "name": viewer.name, "role": "organiser"}


def do_open(plane, rec: dict, actor: dict, now: str) -> None:
    oc = ensure(rec)
    if oc["converge"]["state"] != "not_open":
        raise L.Refused(409, "The count has already opened.")
    if rec["state"] not in ("open", "in_session"):
        raise L.Refused(409, L.ILLEGAL)
    cands = candidates(plane, rec)
    oc["rounds"] = [{"n": 1, "candidates": [c["ref"] for c in cands], "opened_at": now, "closed_at": None, "closed_by": None,
                     "people_backed": None, "tie_picks": None, "tie_broken_by": None, "top": []}]
    oc["converge"]["state"] = "round_1_open"


def do_back(plane, rec: dict, viewer, ref, on) -> None:
    oc = ensure(rec)
    state, n = oc["converge"]["state"], len(oc["rounds"])
    if state not in OPEN_STATES:
        raise L.Refused(409, "The count is closed." if state != "not_open" else "The count has not opened.")
    if not isinstance(on, bool) or not isinstance(ref, str) or ref not in oc["rounds"][-1]["candidates"]:
        raise L.Refused(422, "We could not find that idea.")
    seat = seat_key(rec["id"], viewer.account_id)
    cap = contract()["round_2_max_backs"] if n == 2 else oc["converge"]["max_backs"]
    with lock_for(_votes_file(plane, rec["id"])):
        doc = read_votes(plane, rec["id"], n)
        have = [r for r, v in doc["votes"].items() if seat in v]
        if on and ref not in have and len(have) >= cap:
            raise L.Refused(409, USED_ALL if cap == 3 else "You have used your one back. Take it back first." if cap == 1 else USED_ALL.replace("three", str(cap)))
        write_json_atomic(_votes_file(plane, rec["id"]), {"round": n, "votes": back(doc["votes"], ref, seat, on)})


def do_close(plane, rec: dict, actor: dict, now: str, picks: list | None, ev: list) -> None:
    """Close the open round: counts onto ideas_kept, seat keys no longer needed; or, on a closed round with a tie, write the organiser's pick."""
    oc = ensure(rec)
    state, n = oc["converge"]["state"], len(oc["rounds"])
    cands = candidates(plane, rec)
    if state in CLOSED_STATES:
        rank = ranking(oc, counts_now(plane, rec, cands))
        tie = rank["tie"]
        if not (picks and tie and not tie["resolved"]):
            raise L.Refused(409, "The count is closed.")
        if len(picks) != tie["free"] or not set(picks) <= set(tie["among"]) or len(set(picks)) != len(picks):
            raise L.Refused(422, f"Pick exactly {tie['free']} of the tied ideas.")
        oc["rounds"][-1].update(tie_picks=list(picks), tie_broken_by=actor["account"])
        oc["rounds"][-1]["top"] = ranking(oc, counts_now(plane, rec, cands))["top"]
        _event(rec, ev, "tie_picked", actor, {"round": n, "free": tie["free"]})
        return
    if state not in OPEN_STATES:
        raise L.Refused(409, "The count has not opened.")
    votes = read_votes(plane, rec["id"], n)["votes"]
    r = oc["rounds"][-1]
    if not any(votes.get(x) for x in r["candidates"]):
        raise L.Refused(409, "Nobody has backed yet.")
    by_ref = {i["ref"]: i for i in oc["ideas_kept"]}
    byc = {c["ref"]: c for c in cands}
    for ref in r["candidates"]:
        c = byc.get(ref)
        if c is None:
            continue
        e = by_ref.get(ref) or {"ref": ref, "kind": c["kind"], "text": c["text"], "group": c["group"] and f"g:{c['group']}",
                                 "backed": {"round1": 0, "round2": None}, "runner_up": False,
                                 **({"anonymous": True} if c["anonymous"] else {"from": c["from"]} if c["from"] else {})}
        e["backed"][f"round{n}"] = tally(votes, ref)
        if ref not in by_ref:
            oc["ideas_kept"].append(e)
    r.update(closed_at=now, closed_by=actor["account"], people_backed=len({s for v in votes.values() for s in v}))
    oc["converge"]["state"] = f"round_{n}_closed"
    r["top"] = ranking(oc, counts_now(plane, rec, cands))["top"]
    _event(rec, ev, "count_closed", actor, {"round": n, "people_backed": r["people_backed"]})


def do_round2(plane, rec: dict, actor: dict, now: str) -> None:
    oc, c = ensure(rec), contract()
    if oc["converge"]["state"] != "round_1_closed" or len(oc["rounds"]) >= c["max_rounds"]:
        raise L.Refused(409, "Round 2 has already run." if len(oc["rounds"]) >= c["max_rounds"] else "Close the count first.")
    cands = candidates(plane, rec)
    if len(oc["rounds"][0]["candidates"]) < c["top_n"]:
        raise L.Refused(409, "Only two ideas, so no second round.")
    rank = ranking(oc, counts_now(plane, rec, cands))
    if rank["tie"] and not rank["tie"]["resolved"]:
        raise L.Refused(409, "Pick which ideas go forward first.")
    if len(rank["top"]) < 2:
        raise L.Refused(409, "Fewer than two ideas were backed, so no second round.")
    oc["rounds"].append({"n": 2, "candidates": rank["top"], "opened_at": now, "closed_at": None, "closed_by": None, "people_backed": None,
                         "tie_picks": None, "tie_broken_by": None, "top": []})
    oc["converge"]["state"] = "round_2_open"


SYSTEM = ("You are North. You draft one outcome card for a brainstorm and never decide. Use only the facts and idea texts given. "
          "Never write a number that is not in them. Plain English, British spelling, no names of people.")
ASK = ('Write the idea as one short paragraph (at most 300 characters) and the reason as two to four sentences. Each reason sentence rests on one '
       'fact: give its source exactly as written in the facts. Reply with ONLY one JSON object {"idea": "...", "why": [{"text": "...", "source": "..."}]}')


def _model_text(request, plane, ch: dict, cands: list[dict]) -> dict | None:
    """North's wording through the kernel runtime and the egress gateway (R14); None when the model cannot answer or nothing it wrote is sourced.
    Counts and idea texts only: no names, no anonymous author. A sentence whose source is not a given fact, or whose number is not in the facts, is dropped."""
    from sh_platform.intents import decision as D  # drop_untraced
    from sh_platform.intents import north as N
    gate = getattr(request.app.state, "entitlements", None) if request is not None else None
    if gate is None:
        return None
    cards = [x["text"] for x in (members(cands, ch["ref"]) if ch["kind"] == "group" else [next(x for x in cands if x["ref"] == ch["ref"])])]
    facts = [{"source": w["source"], "text": w["text"]} for w in ch["why_sources"]]
    try:
        text = N._call(plane, N._model(request, plane), gate, SYSTEM, {"facts": [], "counted": {f["source"]: f["text"] for f in facts}, "ideas": cards[:6]},
                       D.with_numbers(ASK, " ".join(f["text"] for f in facts) + " " + " ".join(cards))) or ""
        a, b = text.find("{"), text.rfind("}")
        got = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except Exception:  # noqa: BLE001 - a provider failure falls back to the counted sentences, never breaks the organiser's act
        log.warning("North could not draft the outcome", exc_info=True)
        return None
    if not isinstance(got, dict) or not isinstance(got.get("why"), list):
        return None
    allowed = " ".join(f["text"] for f in facts) + " " + " ".join(cards)
    known = {f["source"] for f in facts}
    why = []
    for w in got["why"][:4]:
        t, src = (w.get("text"), w.get("source")) if isinstance(w, dict) else (None, None)
        t = D.drop_untraced(t, allowed)[0] if isinstance(t, str) else ""
        if t and src in known:
            why.append({"text": t[:300], "source": src})
    idea = D.drop_untraced(got["idea"], allowed)[0][:300] if isinstance(got.get("idea"), str) else ""
    return {"idea": idea, "why": why} if why and idea else None


def _drafted(plane, rec: dict, cands: list[dict], counts: dict, ref: str, now: str, request) -> dict:
    """North's card for `ref`: the model's wording (R14) over the counted sentences, which stand in, marked `fallback`, when it cannot answer."""
    ch = draft_chosen(rec, cands, counts, ref, now)
    made = _model_text(request, plane, ch, cands)
    if made:
        ch.update(idea=made["idea"], why=" ".join(w["text"] for w in made["why"]), why_sources=made["why"])
    ch["fallback"] = made is None  # the screen says so when the counted sentences stand in for the model
    return ch


def do_draft(plane, rec: dict, actor: dict, now: str, ref, ev: list, request=None) -> None:
    oc = ensure(rec)
    if oc["converge"]["state"] not in CLOSED_STATES:
        raise L.Refused(409, "Close the count first.")
    if oc["chosen"]:
        raise L.Refused(409, "A draft already exists.")
    cands = candidates(plane, rec)
    counts = counts_now(plane, rec, cands)
    lead = leaders(counts, list(counts))
    if ref is None and len(lead) == 1:
        ref = lead[0]
    if ref is None:
        raise L.Refused(409, "Two ideas are tied at the top. You decide." if lead else "Nothing was backed, so there is nothing to draft.")
    if ref not in counts:
        raise L.Refused(422, "We could not find that idea.")
    oc["chosen"] = _drafted(plane, rec, cands, counts, ref, now, request)
    mark_runners_up(oc, counts, ref)
    _event(rec, ev, "outcome_drafted", None, {"kind": oc["chosen"]["kind"]}, agent="north")


def do_edit(plane, rec: dict, actor: dict, now: str, body: dict, ev: list, request=None) -> None:
    oc = ensure(rec)
    ch = oc["chosen"]
    if oc["converge"]["state"] == "done":
        raise L.Refused(409, "This outcome is confirmed and cannot be changed.")
    if not ch:
        raise L.Refused(409, "North has not drafted the outcome yet.")
    cands = candidates(plane, rec)
    counts = counts_now(plane, rec, cands)
    if "ref" in body and body["ref"] != ch["ref"]:
        ref = body["ref"]
        if ref not in counts:
            raise L.Refused(422, "We could not find that idea.")
        reason = " ".join(str(body.get("overridden_reason") or "").split())
        if ref not in leaders(counts, list(counts)) and not reason:
            raise L.Refused(422, "Why this one when another had more backs?")
        mine = [t for t in ch.get("what_it_takes") or [] if t.get("source") == "Added by the organiser"]  # rule 7: the organiser's own lines stay
        oc["chosen"] = ch = {**_drafted(plane, rec, cands, counts, ref, now, request), "overridden_reason": reason or None}
        ch["what_it_takes"] = ch["what_it_takes"] + mine
        mark_runners_up(oc, counts, ref)
    elif "overridden_reason" in body:
        ch["overridden_reason"] = " ".join(str(body["overridden_reason"] or "").split()) or None
    if isinstance(body.get("idea"), str):
        ch["idea"] = body["idea"].strip()[:2000]
    if isinstance(body.get("why"), str):
        old = {s["text"]: s["source"] for s in ch.get("why_sources") or []}
        ch["why"] = " ".join(body["why"].split())
        ch["why_sources"] = [{"text": s, "source": old.get(s, "Written by the organiser")} for s in _split(ch["why"])]
    if isinstance(body.get("what_it_takes"), list):
        ch["what_it_takes"] = [{"text": str(t.get("text") or "").strip()[:300], "source": t.get("source") or "Added by the organiser"}
                               for t in body["what_it_takes"] if isinstance(t, dict) and str(t.get("text") or "").strip()]
    gone = body.get("remove_runner_up")
    if isinstance(gone, dict):
        why = " ".join(str(gone.get("reason") or "").split())
        hit = next((i for i in oc["ideas_kept"] if i["ref"] == gone.get("ref") and i.get("runner_up")), None)
        if hit is None:
            raise L.Refused(422, "We could not find that runner-up.")
        if not why:
            raise L.Refused(422, "Say why this idea is removed.")
        oc["ideas_kept"].remove(hit)
        oc["dropped"].append({"ref": hit["ref"], "text": hit["text"], "reason": why})
    if any(k in body for k in ("idea", "why", "what_it_takes", "ref")):
        ch.update(drafted_by=None, edited_by=actor["name"], edited_at=now)


def unmet(ch: dict | None, needs_override: bool = False) -> str:
    """The first thing missing before the outcome can be confirmed, in plain words."""
    if not ch or not (ch.get("idea") or "").strip():
        return "No idea is chosen yet. Pick one from the count."
    if needs_override and not ch.get("overridden_reason"):
        return "Say why this one when another had more backs."
    if not (ch.get("why") or "").strip():
        return "Add the reason."
    if not any((t.get("text") or "").strip() for t in ch.get("what_it_takes") or []):
        return "Add at least one line under what it would take, or write 'To be found out'."
    return ""


def do_confirm(plane, rec: dict, actor: dict, now: str, ev: list) -> None:
    oc = ensure(rec)
    ch = oc["chosen"]
    if oc["converge"]["state"] not in CLOSED_STATES:
        raise L.Refused(409, "Close the count first.")
    counts = counts_now(plane, rec, candidates(plane, rec))
    miss = unmet(ch, bool(ch) and ch.get("ref") not in leaders(counts, list(counts)))
    if miss:
        raise L.Refused(422, miss)
    zone = L.company_zone(plane)
    closes = L.add_working_days(datetime.fromisoformat(now), int(contract()["late_window_working_days"]), zone)
    ch.update(confirmed_by={"account_id": actor["account"], "name": actor["name"]}, confirmed_at=now)
    oc["converge"]["state"] = "done"
    oc["late_window"] = {"opens_at": now, "closes_at": closes.isoformat()}
    for s in rec.get("stages") or []:
        if s.get("key") == "choose" and s.get("state") == "open":
            s.update(state="closed", closed_at=now)
    if rec["state"] != "closing":
        L.move(rec, "closing", actor["account"], now, tz=zone)
    _event(rec, ev, "outcome_confirmed", actor, {"rounds": len(oc["rounds"])})


def do_late(plane, rec: dict, viewer, now: datetime, body: dict, ev: list) -> None:
    oc = ensure(rec)
    if not (oc["late_window"] and rec["state"] in ("closing", "closed")):
        raise L.Refused(409, "Late thoughts open once the outcome is confirmed.")
    if oc.get("frozen_at") or not _late_open(oc, now):
        raise L.Refused(409, "This record is frozen.")
    text = " ".join(str(body.get("text") or "").split())
    limit = contract()["comment_chars"]
    if not text:
        raise L.Refused(422, "Please write something first.")
    if len(text) > limit:
        raise L.Refused(422, f"That is too long. Please keep it under {limit} characters.")
    about = body.get("about") or (oc["chosen"] or {}).get("ref")
    ok = {(oc["chosen"] or {}).get("ref"), *(i["ref"] for i in oc["ideas_kept"] if i.get("runner_up"))}
    if about not in ok:
        raise L.Refused(422, "Pick which idea this is about.")
    anon = body.get("anonymous") is True if _names_choice(rec) else False
    oc["late_thoughts"].append({"by": None if anon else viewer.account_id, "anonymous": anon, "text": text, "about": about, "at": now.isoformat()})
    _event(rec, ev, "late_thought", None if anon else {"account": viewer.account_id, "name": viewer.name, "role": "participant"}, {"about_kind": about[:1]},
           anonymous=anon)


def freeze_if_due(plane, rec: dict) -> dict:
    """North freezes the record at `closes_at`: written once, a second call changes nothing."""
    oc = ensure(rec)
    w = oc["late_window"]
    if not w or oc.get("frozen_at") or _now() < datetime.fromisoformat(w["closes_at"]):
        return rec

    def change(r, ev):
        o = ensure(r)
        if not o.get("frozen_at"):
            o["frozen_at"] = o["late_window"]["closes_at"]
            _event(r, ev, "record_frozen", None, {}, agent="north")
    try:
        return _mutate(plane, rec["id"], change)[0]
    except (S.VersionConflict, L.Refused):
        return rec


# ---- routes ----------------------------------------------------------------------------------------------------------------------------

def _namer(request: Request):
    store = request.app.state.account_store
    return lambda acct: str((store.get(acct) or {}).get("display_name") or "") if acct else ""


def _ctx(request: Request, intent_id: str, *, organiser: bool = False, seated: bool = False, content: bool = False):
    """The plane, the viewer, the record and the viewer's relation to it. 404 for a person who may not know it exists (file 14)."""
    try:
        plane = _plane(request)
        rec = A.load_intent(plane, intent_id)
    except PermissionError:
        raise L.Refused(404, S.NOT_FOUND) from None
    except A.IntentRefused as e:
        raise L.Refused(e.status_code, e.detail["message"]) from None
    me = A.Me.of(request, plane)
    rel = relation(rec, me)
    if rec.get("type") != "brainstorm" or not rel["roles"]:
        raise L.Refused(404, S.NOT_FOUND)
    tier = "content" if rel["reader"] else "outcome"
    if (organiser and not rel["organiser"]) or (seated and not rel["seated"]) or (content and tier != "content"):
        raise L.Refused(403, "Only the organiser can do that." if organiser else "Only people seated in this brainstorm can do that.")
    return plane, me, rec, rel, tier


def _safe(fn):
    try:
        return fn()
    except L.Refused as e:
        return JSONResponse({"message": e.message}, status_code=e.status)
    except S.VersionConflict:
        return JSONResponse({"message": S.CONFLICT}, status_code=409)
    except S.Unreadable:
        return JSONResponse({"message": S.UNREADABLE}, status_code=500)
    except (KeyError, TypeError, IndexError):  # a record of an odd shape: a calm sentence, never a server error
        log.exception("converge could not read a record")
        return JSONResponse({"message": "This page cannot be shown for this record yet. Tell the organiser."}, status_code=422)


def _body(body) -> dict:
    return body if isinstance(body, dict) else {}


def _act(request: Request, intent_id: str, change):
    """An organiser's write: `change(plane, rec, actor, events)` edits the record under the version check; the answer is the new view."""
    plane, viewer, rec, rel, _ = _ctx(request, intent_id, organiser=True, content=True)
    actor = _who(viewer)
    rec2, _ = _mutate(plane, intent_id, lambda r, ev: change(plane, r, actor, ev))
    return _answer(request, plane, rec2, viewer)


def _answer(request: Request, plane, rec: dict, viewer):
    return build_view(plane, rec, viewer, relation(rec, viewer), _namer(request))


@router.get("/api/intents/{intent_id}/converge")
def get_converge(intent_id: str, request: Request):
    def work():
        plane, viewer, rec, rel, tier = _ctx(request, intent_id)
        rec = freeze_if_due(plane, rec)
        if tier == "content":
            return _answer(request, plane, rec, viewer)
        oc = ensure(rec)
        if rec["state"] != "closed" or "super_admin" in rel["roles"]:  # the outcome only, once closed (rulings 4 and 5)
            raise L.Refused(404, S.NOT_FOUND)
        full = build_view(plane, rec, viewer, rel, _namer(request))
        late = full["late"]
        admin = pview.ADMIN in viewer.roles  # the company admin reads by-name thoughts only
        return {"id": rec["id"], "title": rec["title"], "intent_state": rec["state"], "tier": tier, "viewer": {"organiser": False, "seated": False, "can_back": False},
                "converge": {"state": oc["converge"]["state"]}, "outcome": full["outcome"], "rows": [], "mine": [], "can": {}, "next_kinds": [],
                "late": {**late, "thoughts": late["thoughts"] if admin else [], "can_add": False} if late else None, "tz": full["tz"], "ends": None,
                "north": "", "have_backed": 0, "seated_count": 0, "tie": None}
    return _safe(work)


@router.post("/api/intents/{intent_id}/converge/open")
def post_converge_open(intent_id: str, request: Request):
    return _safe(lambda: _act(request, intent_id, lambda plane, r, a, ev: do_open(plane, r, a, S.now_iso())))


@router.post("/api/intents/{intent_id}/converge/back")
async def post_converge_back(intent_id: str, request: Request):
    body = await _json(request)

    def work():
        plane, viewer, rec, rel, _ = _ctx(request, intent_id, seated=True, content=True)
        do_back(plane, rec, viewer, body.get("candidate"), body.get("on"))
        return _answer(request, plane, S.read_intent(plane, intent_id), viewer)
    return _safe(work)


async def _json(request: Request) -> dict:
    try:
        return _body(await request.json())
    except ValueError:
        return {}


@router.post("/api/intents/{intent_id}/converge/close")
async def post_converge_close(intent_id: str, request: Request):
    body = await _json(request)
    picks = body.get("tie_picks") if isinstance(body.get("tie_picks"), list) else None

    def work():
        out = _act(request, intent_id, lambda p, r, a, ev: do_close(p, r, a, S.now_iso(), picks, ev))
        drop_votes(_plane(request), intent_id)  # the seat keys go with the round
        return out
    return _safe(work)


@router.post("/api/intents/{intent_id}/converge/round2")
def post_converge_round2(intent_id: str, request: Request):
    return _safe(lambda: _act(request, intent_id, lambda plane, r, a, ev: do_round2(plane, r, a, S.now_iso())))


@router.post("/api/intents/{intent_id}/outcome/draft")
async def post_outcome_draft(intent_id: str, request: Request):
    ref = (await _json(request)).get("ref")
    return _safe(lambda: _act(request, intent_id, lambda plane, r, a, ev: do_draft(plane, r, a, S.now_iso(), ref, ev, request)))


@router.put("/api/intents/{intent_id}/outcome")
async def put_outcome(intent_id: str, request: Request):
    body = await _json(request)
    return _safe(lambda: _act(request, intent_id, lambda plane, r, a, ev: do_edit(plane, r, a, S.now_iso(), body, ev, request)))


@router.post("/api/intents/{intent_id}/outcome/confirm")
def post_outcome_confirm(intent_id: str, request: Request):
    return _safe(lambda: _act(request, intent_id, lambda plane, r, a, ev: do_confirm(plane, r, a, S.now_iso(), ev)))


@router.post("/api/intents/{intent_id}/late-thoughts")
async def post_late_thoughts(intent_id: str, request: Request):
    body = await _json(request)

    def work():
        plane, viewer, rec, rel, _ = _ctx(request, intent_id, seated=True, content=True)
        rec2, _ = _mutate(plane, intent_id, lambda r, ev: do_late(plane, r, viewer, _now(), body, ev))
        return _answer(request, plane, rec2, viewer)
    return _safe(work)
