"""Spec 33: the build-ready check (seven lines read from records), the build-needed answer and the hand-off to Build.

The check never changes the intent's `state`. It is computed here from the records each line names; `build_ready` is stored on the
intent only by the check route, the answer and the hand-off. A line that cannot read its record fails and says why. Pure line
functions first, routes last. Reads are by file (the m1 and m2 stores keep their own files); nothing is copied.
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from modules.m2_baseline.api import data_sources as DS
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G
from modules.m2_baseline.domain import technical as T
from sh_platform.intents import _plane, _viewer, not_yet, north, source_map as SM, store as S
from sh_platform.intents.access import (EXISTENCE, ORGANISER, STAGE_BUILD_READY, IntentAccess, IntentRefused, IntentRoute, Me, intent_roles, load_intent,
                                        person_name, require_intent_role, roles_of)
from sh_platform.intents.events import try_append
from sh_platform.intents.lifecycle import company_zone
from sh_platform.jsonfile import lock_for, read_json_strict
from sh_platform.profile import store as P
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
router = APIRouter(route_class=IntentRoute)

OPEN_STATES = ("open", "in_session", "closing")
ANSWER = ORGANISER | frozenset({"closer"})  # the organiser or the sponsor (the Initiative's closer)
HANDOFF = ORGANISER  # ruling R15: only the organiser hands over to Build
TITLES = {1: "Charter signed", 2: "Every Must and Should measure has a confirmed business definition",
          3: "Every Must and Should measure has a confirmed technical definition, a catalogue entry and a governed state",
          4: "Every process has a confirmed business owner", 5: "Every data source has a confirmed source owner",
          6: "Who does what: architect, developer, tester named", 7: "Build needed is answered yes"}
GROUPS = {1: "Agreed on paper", 7: "Agreed on paper", 2: "Defined", 3: "Defined", 4: "Owned", 5: "Owned", 6: "Owned"}
KEYS = {1: "charter", 2: "business", 3: "technical", 4: "processes", 5: "sources", 6: "team", 7: "build_needed"}
_KERNEL = C.Viewer("", frozenset(), False, None)
NEED_LEFT = "Not available yet: {} could not be read."
ONLY_ORGANISER = "Only the organiser hands over."  # R15: the organiser hands over; the sponsor and the company admin see the button disabled


def _reader(request: Request, intent_id: str) -> IntentAccess:
    """EXISTENCE, and also the people the check asks things of who the people list does not name: a person the records name as an owner or
    confirmer (store.named_in_records) reads as a participant, a person who holds a North seat (the analyst) as an observer (R1)."""
    try:
        plane = _plane(request)
    except PermissionError:
        raise IntentRefused(404, "intent_not_found", S.NOT_FOUND) from None
    intent = load_intent(plane, intent_id)
    seen = intent
    if intent.get("state") != "draft" and not roles_of(intent, Me.of(request, plane)):
        v = _viewer(request)
        slot = "participants" if S.named_in_records(plane, intent, v) else None
        if slot is None:
            try:
                north.seat_or_refuse(plane, intent, v)
                slot = "observers"
            except north.NorthError:
                pass
        if slot and "super_admin" not in v.roles:
            p = intent.get("people") or {}
            seen = {**intent, "people": {**p, slot: [*(p.get(slot) or []), {"account_id": v.account_id, "name": v.name}]}}
    return IntentAccess(intent, require_intent_role(request, seen, EXISTENCE, plane=plane), plane)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- record reads ----------------------------------------------------------------------------------------------------------

def _read(path, kind=None):
    """The parsed file, or None when it is absent or cannot be read (the line then says so)."""
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        return None


def _by_person(cell) -> bool:
    """A confirmed cell: stated, written by a person (a Lens draft or any agent write never counts)."""
    return isinstance(cell, dict) and cell.get("mark") == "stated" and not cell.get("agent") and cell.get("by") != "Lens" \
        and cell.get("value") not in (None, "", [], {})


def _name(v) -> str | None:
    v = v.get("value") if isinstance(v, dict) and "value" in v else v
    v = v.get("name") if isinstance(v, dict) else v
    return str(v) if v else None


def _turn(name, role):
    return {"name": name, "role": role} if name else None


def _baseline_id(plane, intent: dict) -> str | None:
    ids = (intent.get("refs") or {}).get("baseline_ids") or []
    if ids:
        return str(ids[-1])
    cid = (intent.get("refs") or {}).get("charter_outcome_id")  # the baseline built on this charter
    root = plane.path("intents", "m2_baseline")
    for f in sorted(root.glob("*/baseline.json")) if root.is_dir() else []:
        b = _read(f, dict)
        if cid and b and b.get("charter_outcome_id") == cid:
            return f.parent.name
    return None


class Ctx:
    """Everything the lines read, loaded once per check."""

    def __init__(self, plane, intent: dict, viewer):
        self.plane, self.intent, self.viewer = plane, intent, viewer
        self.id = intent["id"]
        self.read_at = _now()
        refs = intent.get("refs") or {}
        self.outcome_id = refs.get("charter_outcome_id")
        self.outcome = _read(plane.path("intents", "m1_intent", "outcomes", f"{self.outcome_id}.json"), dict) if self.outcome_id else None
        self.bid = _baseline_id(plane, intent)
        base = plane.path("intents", "m2_baseline", self.bid) if self.bid else None
        self.kpis = (_read(base / "kpis.json", list) if base else None)
        self.glossary = {e.get("kpi_id"): e for e in (_read(base / "glossary.json", dict) or {}).get("entries", [])} if base else {}
        self.catalogue = (_read(base / "catalogue.json", dict) or {}) if base else {}
        self.governed = (_read(base / "governed_state.json", dict) or {}) if base else {}
        self.signoff = (_read(base / "signoff.json", dict) or {}) if base else {}
        self.sponsor = person_name(intent, "sponsor", plane)
        self.organiser = person_name(intent, "organiser", plane)

    @property
    def measures(self) -> list[dict]:
        """The Must and Should shelf of the signed charter; left-out measures leave the shelf first (open question 9)."""
        versions = self.signoff.get("versions") or [{}]
        left = {x for x in (versions[-1].get("left_out") or []) if isinstance(x, str)}
        return [k for k in self.kpis or [] if k.get("priority") in ("must", "should") and k.get("id") not in left]

    @property
    def version(self):
        v = (self.signoff.get("versions") or [{}])[-1]
        return v.get("version")

    def sealed(self, kpi: dict) -> bool:
        """A restricted measure, to a viewer who may not see it: counted, never named (rule: sealed material)."""
        gs = (self.governed.get(kpi.get("id")) or {}).get("classification") or {}
        if gs.get("value") != "restricted" or {"company_admin", "sponsor"} & set(self.viewer.roles):
            return False
        see = (self.governed.get(kpi.get("id")) or {}).get("may_see") or {}
        return norm(self.viewer.name) not in {norm(x) for x in see.get("value") or [] if isinstance(x, str)}

    def evidence(self, record: str, id_=None) -> dict:
        return {"record": record, "id": id_, "read_at": self.read_at}


def _line(n: int, ok: bool, count: int, of: int, missing: list, ev: dict, text: str, **more) -> dict:
    return {"n": n, "key": KEYS[n], "title": TITLES[n], "group": GROUPS[n], "ok": bool(ok), "count": count, "of": of, "missing": missing,
            "evidence": ev, "text": text, **more}


def _unavailable(n: int, record: str, ev: dict) -> dict:
    return _line(n, False, 0, 0, [], ev, NEED_LEFT.format(record), unavailable=True)


def _item(kind, ref, label, turn, href, fix, **more) -> dict:
    return {"kind": kind, "ref": ref, "label": label, "turn_of": turn, "href": href, "fix": fix, **more}


def _define(c: Ctx, tab: str, focus) -> str:
    return f"/centre/intent/{c.id}/define?tab={tab}" + (f"&focus={focus}" if focus else "")


def _sealed_item(count: int) -> dict:
    return _item("sealed", None, f"{count} sealed measure{'s' if count != 1 else ''}, counted", None, None, None, sealed=count)


def line1(c: Ctx) -> dict:
    ev = c.evidence("Charter outcome", c.outcome_id)
    if not c.outcome:
        return _unavailable(1, "The charter outcome", ev)
    sigs = [s for s in c.outcome.get("signatures") or [] if isinstance(s, dict) and s.get("name")]
    href = f"/centre/intent/{c.id}/charter"
    if not sigs:
        who = (c.sponsor or "The sponsor").split()[0]
        return _line(1, False, 0, 1, [_item("charter", c.outcome_id, "Sign the charter", _turn(c.sponsor, "sponsor"), href,
                                           "Fix it in the charter")], ev, f"The charter has no signature yet. {who} signs it.")
    return _line(1, True, 1, 1, [], ev, "", signer=sigs[0]["name"], signed_at=c.outcome.get("signed_at"), version=c.outcome.get("charter_version"))


def _measure_lines(c: Ctx) -> tuple[dict, dict]:
    ev2, ev3 = c.evidence("Glossary", c.bid), c.evidence("Technical definitions, catalogue and governed state", c.bid)
    if c.kpis is None:
        return _unavailable(2, "The baseline", ev2), _unavailable(3, "The baseline", ev3)
    shelf = c.measures
    cat_ids = {(r.get("KPI ID") or {}).get("value") for r in c.catalogue.get("kpis") or [] if isinstance(r, dict)}
    m2, m3, sealed2, sealed3 = [], [], 0, 0
    parts = {"technical": 0, "catalogue": 0, "governed": 0}
    ok2 = ok3 = 0
    for k in shelf:
        kid, sealed = k["id"], c.sealed(k)
        label = f"{kid} {k.get('name', '')}".strip()
        g = c.glossary.get(kid) or {}
        cell = g.get("business_definition")
        if _by_person(cell):
            ok2 += 1
        elif sealed:
            sealed2 += 1
        else:
            draft = isinstance(cell, dict) and cell.get("mark") == "guessed" and cell.get("value")
            m2.append(_item("measure", kid, label, _turn(_name(g.get("owner")) or _name((k.get("owners") or {}).get("business")), "business owner"),
                            _define(c, "glossary", kid), "Fix it in the glossary", part="business", state="Drafted, not yet confirmed" if draft else "Missing"))
        gov = c.governed.get(kid) or {}
        have = {"technical": T.confirmed(k) is not None, "catalogue": kid in cat_ids, "governed": G.is_complete(gov)}
        for p, v in have.items():
            parts[p] += v
        if all(have.values()):
            ok3 += 1
        elif sealed:
            sealed3 += 1
        else:
            owner = _name(((gov.get("owners") or {}).get("value") or {}).get("data")) or _name((k.get("owners") or {}).get("data"))
            lack = [p for p, v in have.items() if not v]
            tab = "catalogue" if lack[0] != "technical" else "glossary"
            m3.append(_item("measure", kid, label, _turn(owner, "data owner"), _define(c, tab, kid), "Fix it in the catalogue", part=lack,
                            state="Not confirmed: " + ", ".join(lack)))
    if sealed2:
        m2.append(_sealed_item(sealed2))
    if sealed3:
        m3.append(_sealed_item(sealed3))
    empty = "No measures are on the Must or Should shelf yet."
    return (_line(2, bool(shelf) and ok2 == len(shelf), ok2, len(shelf), m2, ev2, empty if not shelf else f"{len(shelf) - ok2} measures have no confirmed business definition."),
            _line(3, bool(shelf) and ok3 == len(shelf), ok3, len(shelf), m3, ev3, empty if not shelf else f"{len(shelf) - ok3} measures are not fully defined.", parts=parts))


def line4(c: Ctx) -> dict:
    ev = c.evidence("Process map", c.id)
    path = c.plane.path("intents", c.id, "processes.json")
    data = _read(path) if path.exists() else {"processes": []}  # file 27 is built: no file yet is an empty map
    if data is None:
        return _unavailable(4, "The process map", ev)
    rows = [p for p in (data.get("processes") if isinstance(data, dict) else data) or [] if isinstance(p, dict)
            and p.get("status") != "removed" and not p.get("removed")]
    people = P.raw(c.plane)["people"]
    who = lambda pid: _name(people.get(pid or "", {}).get("name")) or pid  # noqa: E731  file 27 stores the owner as a profile person id
    missing = [_item("process", str(p.get("id")), _name(p.get("name")) or str(p.get("id")), _turn(who(_name(p.get("owner"))), "business owner"),
                     f"/centre/intent/{c.id}/define?tab=process-map&process={p.get('id')}", "Fix it in the process map")
               for p in rows if not (_name(p.get("owner")) and p.get("confirmed"))]
    ok = len(rows) - len(missing)
    return _line(4, bool(rows) and not missing, ok, len(rows), missing, ev,
                 "The process map is empty. Draw it first." if not rows else f"{len(missing)} processes have no confirmed owner.")


def line5(c: Ctx) -> dict:
    """Read through the module's own source rows (kernel read: every row, whoever the viewer): confirmed means the named source owner confirmed it."""
    ev = c.evidence("Data sources", c.bid)
    try:
        got = DS.rows(c.plane, c.bid, _KERNEL, everything=True) if c.bid else None
    except Exception:  # noqa: BLE001  a store that cannot be read is "could not be read", never a crash of the check
        log.exception("build-ready: data sources unreadable")
        got = None
    if got is None:
        return _unavailable(5, "The data sources", ev)
    rows = got["rows"]
    missing = [_item("source", r["id"], r["name"] or r["id"], _turn(_name((r["owners"].get("source") or {}).get("value")), "source owner"),
                     f"/centre/intent/{c.id}/define?tab=data-sources&focus={r['id']}", "Fix it in the data sources")
               for r in rows if r["state"] != "confirmed"]
    more = {"restricted": got["restricted"]} if got.get("restricted") else {}
    return _line(5, bool(rows) and not missing, len(rows) - len(missing), len(rows), missing, ev,
                 "No data sources are mapped yet." if not rows else f"{len(missing)} sources have no confirmed source owner.", **more)


def line6(c: Ctx) -> dict:
    sid = (c.outcome or {}).get("session_id")
    ev = c.evidence("Who does what", sid)
    roles = (_read(c.plane.path("intents", "m1_intent", "roles", f"{sid}.json"), dict) or {}).get("roles") or {} if sid else {}
    people = P.raw(c.plane)["people"]  # spec 34 stores a profile person id: shown by name, as line 4 does
    names = {s: (_name(people.get(_name(roles.get(s)) or "", {}).get("name")) or _name(roles.get(s))) for s in ("architect", "developer", "tester")}
    missing = [_item("role", s, f"{s.capitalize()} not named", _turn(c.organiser, "organiser"), f"/centre/intent/{c.id}/charter", "Name them")
               for s, v in names.items() if not v]
    ok = 3 - len(missing)
    return _line(6, not missing, ok, 3, missing, ev, "Nobody is named for the build yet." if ok == 0 else f"{len(missing)} of the three {'is' if len(missing) == 1 else 'are'} not named.", slots=names)


def line7(c: Ctx) -> dict:
    ev = c.evidence("Build needed answer", c.id)
    ans = c.intent.get("build_needed")
    by = (c.intent.get("build_needed_by") or {}).get("name")
    at = c.intent.get("build_needed_at")
    turn = _turn(c.sponsor or c.organiser, "sponsor" if c.sponsor else "organiser")
    miss = [] if ans is not None else [_item("answer", "build_needed", "Answer: do we need a build?", turn, None, "Answer it")]
    return _line(7, ans is not None, int(ans is not None), 1, miss, ev, f"Not answered. {(c.organiser or 'The organiser').split()[0]} or {(c.sponsor or 'the sponsor').split()[0]} answers this."
                 if ans is None else "", answer=ans, answered_by=by, answered_at=at, reason=c.intent.get("build_needed_reason"))


def _process_rows(plane, intent_id: str) -> list[dict]:
    """The live processes (not removed), owner shown by name: what Build room 0 receives."""
    data = _read(plane.path("intents", intent_id, "processes.json"))
    people = P.raw(plane)["people"]
    rows = [p for p in (data.get("processes") if isinstance(data, dict) else data) or [] if isinstance(p, dict) and p.get("status") != "removed" and not p.get("removed")]
    return [{"id": str(p.get("id")), "name": _name(p.get("name")) or str(p.get("id")), "confirmed": bool(p.get("confirmed")),
             "owner": _name(people.get(_name(p.get("owner")) or "", {}).get("name")) or _name(p.get("owner"))} for p in rows]


def _map_rows(plane, intent: dict, now: str) -> list[dict]:
    """The source map as written (or Lens's draft when nobody wrote it yet): one row per source with its zone and strategic flag (R16)."""
    m = SM.read_map(plane, intent["id"]) or SM.build_file(plane, intent, None, now)
    return [{"id": sid, "name": v.get("name"), "zone": v.get("zone"), "restricted": bool(v.get("restricted")),
             "strategic": bool((v.get("classification") or {}).get("value", {}).get("strategic")), "mark": (v.get("classification") or {}).get("mark")}
            for sid, v in (m.get("sources") or {}).items()]


def _mask_map(plane, intent: dict, rows: list[dict], viewer) -> list[dict]:
    """A restricted source the viewer may not see is counted, never named."""
    seen = {s["id"] for s in SM.positions(plane, intent, viewer)["sources"] if not s.get("silhouette")}
    return [r if r["id"] in seen else {"id": None, "name": SM.RESTRICTED, "restricted": True, "strategic": r["strategic"], "zone": None, "mark": None} for r in rows]


def compute(plane, intent: dict, viewer) -> dict:
    """The seven lines in full (the server's copy). Lines 4 and 5 are not required when the answer is No (open question 5: they count as passed)."""
    c = Ctx(plane, intent, viewer)
    l2, l3 = _measure_lines(c)
    lines = [line1(c), l2, l3, line4(c), line5(c), line6(c), line7(c)]
    if intent.get("build_needed") is False:
        for ln in lines[3:5]:
            ln.update(ok=True, missing=[], text="Not required: no build", required=False)
    cat_ids = {(r.get("KPI ID") or {}).get("value") for r in c.catalogue.get("kpis") or [] if isinstance(r, dict)}
    catalogue = [{"id": k["id"], "name": k.get("name") or k["id"], "priority": k.get("priority")} for k in c.measures if k["id"] in cat_ids and not c.sealed(k)]
    return {"lines": lines, "baseline_id": c.bid, "catalogue_version": c.version, "catalogue": catalogue,
            "source_count": next((ln["of"] for ln in lines[4:5] if not ln.get("unavailable")), len((c.catalogue.get("sources") or []))),
            "measure_count": lines[1]["of"]}


def verdict(intent: dict, lines: list[dict]) -> str:
    if intent.get("build_handoff"):
        return "handed_over"
    n = sum(ln["ok"] for ln in lines)
    if intent.get("build_needed") is False:
        return "not_needed"
    return "ready" if n == 7 and intent.get("build_needed") is True else "incomplete"


def _stored(intent: dict, lines: list[dict]) -> list[dict]:
    """The `build_ready.lines[]` shape of the spec, plus `since`: the date a line first failed (kept while it keeps failing)."""
    prev = {ln.get("key"): ln for ln in (intent.get("build_ready") or {}).get("lines") or []}
    now = _now()
    return [{"key": ln["key"], "ok": ln["ok"], "count": ln["count"], "of": ln["of"], "missing": ln["missing"], "evidence": ln["evidence"],
             "since": None if ln["ok"] else (prev.get(ln["key"]) or {}).get("since") or now,
             **({"unavailable": True, "text": ln["text"]} if ln.get("unavailable") else {})} for ln in lines]


def todo(lines: list[dict], since: dict) -> list[dict]:
    """North's to-do: one sentence per missing item, the item that blocks most first (the line with most missing)."""
    out = []
    for ln in sorted((x for x in lines if not x["ok"]), key=lambda x: -len(x["missing"])):
        for m in ln["missing"] or [None]:
            who = (m or {}).get("turn_of")
            out.append({"line": ln["n"], "text": (f"{who['name'].split()[0]}, {who['role']}: " if who else "") + ((m or {}).get("label") or ln["text"]),
                        "turn_of": who, "ref": (m or {}).get("ref"), "href": (m or {}).get("href"), "fix": (m or {}).get("fix"), "since": since.get(ln["key"]),
                        "item": (m or {}).get("kind")})
    return out


def _cut(lines: list[dict], level: str) -> list[dict]:
    """affected people and the company admin without content: counts only, never names or evidence."""
    if level == "full":
        return lines
    return [{k: ln[k] for k in ("n", "key", "title", "group", "ok", "count", "of")} for ln in lines]


def _view(a: IntentAccess, full: dict, viewer, stored: list[dict] | None = None) -> dict:
    intent, lines, level = a.intent, full["lines"], "full" if "content" in a.roles else "counts"
    n_ok, st = sum(ln["ok"] for ln in lines), verdict(intent, lines)
    since = {s["key"]: s.get("since") for s in stored or (intent.get("build_ready") or {}).get("lines") or []}
    first_fail = next((ln for ln in lines if not ln["ok"]), None)
    hand, tz = intent.get("build_handoff"), company_zone(a.plane)
    assessment = ((intent.get("refs") or {}).get("assessment_ids") or [None])[-1]
    can_answer = bool(a.roles & ANSWER) and intent.get("state") in OPEN_STATES
    return {"id": intent["id"], "title": intent.get("title"), "type": intent["type"], "state": intent["state"], "level": level,
            "time_zone": getattr(tz, "key", "UTC"), "n_ok": n_ok, "of": 7, "verdict": st, "checked_at": (intent.get("build_ready") or {}).get("checked_at"),
            "lines": _cut(lines, level), "todo": todo(lines, since) if level == "full" else [],
            "build_needed": intent.get("build_needed"), "build_needed_reason": intent.get("build_needed_reason") if level == "full" else None,
            "is_organiser": "organiser" in a.roles, "can_answer": can_answer, "may_recheck": bool(a.roles & STAGE_BUILD_READY),
            "may_hand_over": bool(a.roles & HANDOFF),  # R15: the organiser only
            "can_hand_over": bool(a.roles & HANDOFF) and st == "ready" and intent["state"] in OPEN_STATES,
            "stops": f"Line {first_fail['n']} stops this: {first_fail['text'] or first_fail['title']}" if first_fail else None,
            "measure_count": full["measure_count"], "source_count": full["source_count"], "catalogue_version": full["catalogue_version"],
            "handoff": _handoff_view(a, hand, full, viewer) if hand and level == "full" else None,
            "assessment_id": assessment,
            "gap_analysis_href": f"/centre/build/gap-analysis?from={intent['id']}"}  # room 0 (ruling 10); it shows the assessment below its banner


def _handoff_view(a: IntentAccess, hand: dict, full: dict, viewer) -> dict:
    intent = a.intent
    changed = hand.get("catalogue_version") != full["catalogue_version"]
    return {**{k: v for k, v in hand.items() if k != "lines_frozen"}, "definition_changed": changed or bool(hand.get("definition_changed")),
            "current_catalogue_version": full["catalogue_version"], "sponsor": (intent.get("people") or {}).get("sponsor"),
            "processes": hand.get("processes") or [], "source_map": _mask_map(a.plane, intent, hand.get("source_map") or [], viewer)}


def _event(plane, intent_id: str, viewer, frm: str, to: str, role: str = "organiser") -> None:
    """The check verdict moved: `build_ready_changed`; the hand-over itself writes `handed_to_build`. Never raises: the act must not fail on the log."""
    who = {"account": viewer.account_id, "name": viewer.name, "role": role}
    ref = {"store": "build_ready", "id": intent_id, "version": None}
    if to == "handed_over":
        try_append(plane, intent_id, "handed_to_build", who, ref, {}, "act")
    else:
        try_append(plane, intent_id, "build_ready_changed", who, ref, {"from": frm, "to": to}, "act")


def _initiative(a: IntentAccess) -> None:
    if a.intent.get("type") != "initiative":
        raise IntentRefused(404, "intent_not_found", S.NOT_FOUND)


def _save(request: Request, a: IntentAccess, change, event: tuple[str, str] | None = None) -> dict:
    """Write through the intent store (version-checked), then the event line. Returns the new record."""
    try:
        rec = S.update_intent(a.plane, a.intent["id"], a.intent["version"], change)
    except S.VersionConflict:
        raise IntentRefused(409, "intent_conflict", S.CONFLICT) from None
    if event:
        role = next((r for r in ("organiser", "closer", "company_admin") if r in a.roles), "organiser")
        _event(a.plane, rec["id"], _viewer(request), *event, role="sponsor" if role == "closer" else role)
    return rec


def _record(request: Request, a: IntentAccess, intent: dict) -> dict:
    """Recompute against `intent` and store build_ready on it (not handed over: that record stays frozen). Returns the full result."""
    full = compute(a.plane, intent, _viewer(request))
    if intent.get("build_handoff"):
        return full
    st, before = verdict(intent, full["lines"]), (intent.get("build_ready") or {})

    def change(rec: dict) -> None:
        rec["build_ready"] = {"state": st, "checked_at": _now(), "lines": _stored(rec, full["lines"])}

    rec = _save(request, a, change, (before.get("state") or "not_checked", st) if before.get("state") != st else None)
    intent.update(rec)
    return full


# ---- routes ----------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/{intent_id}/build-ready")
def get_intents_by_intent_id_build_ready(request: Request, a: IntentAccess = Depends(_reader)):
    """The check as it stands now, computed from the records each line names. Read only. Named source owners and the analyst may open it (R1)."""
    _initiative(a)
    if a.intent["state"] == "draft":
        return {"id": a.intent["id"], "verdict": "not_checked", "lines": [], "todo": [], "n_ok": 0, "of": 7, "level": "full",
                "message": "Not checked yet. North checks when Define has a charter draft."}
    return _view(a, compute(a.plane, a.intent, _viewer(request)), _viewer(request))


@router.post("/api/intents/{intent_id}/build-ready/check")
def post_intents_by_intent_id_build_ready_check(request: Request, a: IntentAccess = Depends(intent_roles(STAGE_BUILD_READY))):
    """"Recheck now": recompute and store `build_ready`; an event line only when the verdict or the count changes."""
    _initiative(a)
    if a.intent["state"] == "draft":
        raise IntentRefused(409, "intent_not_open", "Open the intent first.")
    return _view(a, _record(request, a, a.intent), _viewer(request))


class Answer(BaseModel):
    build_needed: bool | None
    reason: str | None = None


@router.put("/api/intents/{intent_id}/build-needed")
def put_intents_by_intent_id_build_needed(body: Answer, request: Request, a: IntentAccess = Depends(intent_roles(ANSWER))):
    """Yes or No (a reason is required for No), or null to change the answer. The organiser or the sponsor, while the intent is open."""
    _initiative(a)
    if a.intent["state"] not in OPEN_STATES or a.intent.get("build_handoff"):
        raise IntentRefused(409, "intent_not_open", "This answer cannot change now.")
    reason = (body.reason or "").strip()
    if body.build_needed is False and not reason:
        raise IntentRefused(422, "reason_required", "Say why no build is needed.")
    v = _viewer(request)

    def change(rec: dict) -> None:
        on = body.build_needed is not None
        rec.update(build_needed=body.build_needed, build_needed_reason=reason[:500] if body.build_needed is False else None,
                   build_needed_by={"account_id": v.account_id, "name": v.name} if on else None, build_needed_at=_now() if on else None)

    rec = _save(request, a, change)
    na = IntentAccess(rec, a.roles, a.plane)
    return _view(na, _record(request, na, rec), _viewer(request))


@router.post("/api/intents/{intent_id}/handoff")
def post_intents_by_intent_id_handoff(request: Request, a: IntentAccess = Depends(intent_roles(HANDOFF))):
    """Hand to Build (R15): the organiser only; only at 7 of 7 with the answer Yes. Writes links.build and build_handoff; `state` does not change."""
    _initiative(a)
    intent = a.intent
    if intent.get("build_handoff"):
        raise IntentRefused(409, "already_handed_over", "This was already handed to Build.")
    if intent["state"] not in OPEN_STATES:
        raise IntentRefused(409, "intent_not_open", "This intent is not open.")
    full = compute(a.plane, intent, _viewer(request))
    if verdict(intent, full["lines"]) != "ready":
        raise IntentRefused(409, "not_build_ready", "The check is not at 7 of 7 with the answer Yes.")
    v, now = _viewer(request), _now()
    refs = intent.get("refs") or {}
    ref = (refs.get("assessment_ids") or [f"intake-{intent['id']}"])[-1]

    def change(rec: dict) -> None:
        frozen = _stored(rec, full["lines"])
        rec["links"] = {**(rec.get("links") or {}), "build": f"build:{ref}"}
        rec["build_handoff"] = {"by": {"account_id": v.account_id, "name": v.name}, "at": now, "charter_outcome_id": refs.get("charter_outcome_id"),
                                "catalogue_version": full["catalogue_version"], "source_count": full["source_count"],
                                "baseline_id": full["baseline_id"], "catalogue": full["catalogue"],  # R16: room 0 receives the catalogue itself
                                "measure_count": full["measure_count"], "lines_frozen": frozen,
                                "processes": _process_rows(a.plane, intent["id"]), "source_map": _map_rows(a.plane, intent, now)}
        rec["build_ready"] = {"state": "handed_over", "checked_at": now, "lines": frozen}

    rec = _save(request, a, change, ("ready", "handed_over"))
    return _view(IntentAccess(rec, a.roles, a.plane), full, v)


class Nudge(BaseModel):
    line: int
    ref: str | None = None


def _nudge_target(plane, name: str) -> str | None:
    """The sign-in id of the person a to-do row names, or None when the profile has no sign-in for that name."""
    people = P.raw(plane)["people"]
    pid = next((k for k, q in people.items() if norm(_name(q.get("name")) or "") == norm(name)), None)
    acct = north._account(plane, pid) if pid else None
    return acct if acct and acct != pid else None


@router.post("/api/intents/{intent_id}/build-ready/nudge")
def post_intents_by_intent_id_build_ready_nudge(body: Nudge, request: Request, a: IntentAccess = Depends(intent_roles(ORGANISER))):
    """North's drafted reminder for one to-do row. It goes to the person's North thread when they have a sign-in; otherwise the draft comes back
    unsent and says so. Organiser only; a repeat on the same day for the same person is not sent twice."""
    _initiative(a)
    full = compute(a.plane, a.intent, _viewer(request))
    row = next((t for t in todo(full["lines"], {}) if t["line"] == body.line and (body.ref is None or body.ref == t.get("ref"))), None)
    who = (row or {}).get("turn_of")
    if not row or not who:
        raise IntentRefused(409, "no_one_named", "No one is named for that row yet.")
    text = f"{who['name'].split()[0]}, the build-ready check is waiting for you: {row['text'].split(': ', 1)[-1]}. Open it from your list when you can."
    acct, now = _nudge_target(a.plane, who["name"]), datetime.now(timezone.utc)
    if not acct:
        return {"sent": False, "text": text, "to": who["name"], "note": "North wrote this reminder. It was not sent because no sign-in is linked to that name."}
    today = now.date().isoformat()

    def work(st: dict) -> bool:
        if any(n["to"] == acct and n["stage"] == "build_ready" and n["at"][:10] == today for n in st["nudges"]):
            return False
        st["nudges"].append({"to": acct, "at": north._iso(now), "kind": "pulse", "stage": "build_ready", "text": text})
        north._turn(st, "north", text, "nudge", now, to=acct)
        return True

    fresh = north._update(a.plane, a.intent["id"], work)
    return {"sent": fresh, "text": text, "to": who["name"], "note": "Sent." if fresh else "Already nudged today. Nothing was sent again."}


@router.put("/api/intents/{intent_id}/build-team")
def put_intents_by_intent_id_build_team(request: Request):
    return not_yet("34")  # naming the team is spec 34's form; line 6 only reads it
