"""Data sources and technical areas (spec 28): a view and an editor over the catalogue `sources` tab plus a thin extras file.

intents/m2_baseline/<baseline_id>/data_sources.json  {version, state, sources: {<Source ID>: entry}, areas: [overlay], notices: []}
An entry holds what the catalogue has no column for: `source_owner` and `business_owner` (provenance cells, kept apart from the catalogue's
"Data owner", column F), `system_ref`, `used_in`, `known_problems`, `left_out`, `confirmed_by`, `proposals`, `history`. Rows are written through
the catalogue store (add_row, edit_row, propose_rows); nothing in the catalogue is copied here. Chips for systems and teams are worked out
from the profile each time; `areas` only holds what a person added or changed on a chip.

The same operations answer on two spellings: here under /baselines/{baseline_id}/data-sources, and in the kernel (sh_platform/intents/sources.py)
under /api/intents/{id}/data-sources, which resolves the baseline from the intent. `register()` builds both from one table.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from modules.m2_baseline.api.signed_guard import SignedGuard, refuse_if_signed
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import catalogue as S
from modules.m2_baseline.store.answers import read_answers
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.profile import view as PV

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)

FILE = "data_sources.json"
LENS = "Lens"
COMMITTEE = frozenset({"company_admin", "sponsor", "analyst", "participant"})
READERS = COMMITTEE | {"approver"}  # an owner reads only the rows they are named on
NOT_NAMED = "Not named yet"
NEEDS_NAME = "A source needs a name."
ONLY_OWNER = "Only the source owner can confirm this."
NOTHING_TO_READ = "Nothing to read yet. Add files in Bring what you have or the systems list."
RESTRICTED = "A restricted source"
RESTRICTED_AREA = "A restricted area"
MAX_NOTE = 500
HEADERS = {"name": "Source name", "format": "Source type", "structure": "Structured or unstructured", "lands": "Where it lands or lives",
           "connection": "Connection method", "frequency": "How often it arrives", "sla": "Expected arrival time or SLA",
           "personal": "Contains personal data?", "who_may_see": "Who may see it", "data_owner": "Data owner"}
LEAD_ONLY = ("personal", "who_may_see")  # the governance lead or the data owner sets these; others propose
_SLUG = re.compile(r"[^a-z0-9]+")


class Refusal(C.CatalogueError):
    """A refusal in plain words with the status it maps to (the catalogue's error, plus forbidden)."""


STATUS = {"not_found": 404, "invalid": 422, "conflict": 409, "read_only": 409, "forbidden": 403, "contract_unreadable": 500, "signed": 409}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(x: Any) -> str:
    return C.norm(x or "")


def _slug(text: str) -> str:
    return _SLUG.sub("-", str(text).lower()).strip("-")[:60] or "area"


# ---- the extras file ---------------------------------------------------------------------------------------------------------------

def _path(plane, bid: str):
    return S._folder(plane, bid) / FILE


def _empty() -> dict:
    return {"version": 1, "state": {"state": "not_started", "drafted_at": None, "drafted_by": None, "done_by": None, "done_at": None, "opened_at": None},
            "sources": {}, "areas": [], "notices": []}


def load(plane, bid: str) -> dict:
    try:
        doc = read_json_strict(_path(plane, bid), dict)
    except (OSError, ValueError):
        raise S.StoreError(S.UNREADABLE) from None
    return {**_empty(), **(doc or {})}


def _update(plane, bid: str, fn: Callable[[dict], Any]) -> Any:
    with lock_for(_path(plane, bid)):
        doc = load(plane, bid)
        out = fn(doc)
        st = doc["state"]
        if st["state"] == "not_started":
            st["state"] = "in_review"  # any first change (confirm, hand over, problem, edit) opens the substage
        if not st.get("opened_at"):
            st["opened_at"] = st.get("drafted_at") or now()  # the substage opens at the first touch; days to done count from here
        try:
            write_json_atomic(_path(plane, bid), doc)
        except OSError:
            raise S.StoreError(S.NOT_SAVED) from None
    return out


def _entry(doc: dict, sid: str) -> dict:
    return doc["sources"].setdefault(sid, {"source_owner": None, "business_owner": None, "system_ref": None, "used_in": {"clusters": [], "steps": []},
                                           "known_problems": [], "left_out": None, "confirmed_by": None, "confirmed_at": None,
                                           "proposals": {}, "history": []})


def _log(e: dict, by: str, what: str) -> None:
    e["history"].append({"by": by, "at": now(), "what": what})


# ---- who the viewer is ---------------------------------------------------------------------------------------------------------------

def is_named(viewer: C.Viewer, name: Any) -> bool:
    return bool(norm(name)) and norm(name) == norm(viewer.name) and not viewer.shared_name


def committee(viewer: C.Viewer) -> bool:
    return bool(COMMITTEE & viewer.roles)


def _pviewer(viewer: C.Viewer) -> PV.Viewer:
    return PV.Viewer(viewer.name, viewer.roles, viewer.shared_name, viewer.account_id)


def _cell(c: Any) -> dict:
    text = C.text_of(c)
    if not text or not isinstance(c, dict):
        return {"value": None, "mark": "unknown", "by": c.get("by") if isinstance(c, dict) else None, "at": None, "from": None}
    return {"value": text, "mark": c.get("mark"), "by": c.get("by"), "at": c.get("at"), "from": c.get("from")}


def _human(c: Any) -> bool:
    return isinstance(c, dict) and c.get("mark") == "stated" and not C.is_blank(c) and norm(c.get("by")) not in C.NOT_A_PERSON


def owner_cells(row: dict, e: dict) -> dict:
    """The three owner kinds, apart. A v1 row with only a Data owner seeds the source owner as a guess, from "old catalogue owner"; it is never promoted."""
    src = e.get("source_owner")
    if C.is_blank(src) and not C.is_blank(row.get("Data owner")):
        src = prov(C.text_of(row["Data owner"]), "guessed", "the old catalogue", "old catalogue owner")
    return {"business": _cell(e.get("business_owner")), "data": _cell(e.get("data_owner") or row.get("Data owner")), "source": _cell(src)}


def intake_owners(plane, bid: str) -> dict[str, dict]:
    """For the intake plan (module 3): who to ask for each file. {Source ID: {name, label}}: the source owner first; failing that the data owner,
    labelled "data owner, no source owner named". A source with neither is absent."""
    cat, _ = S._raw(plane, bid)
    doc, out = load(plane, bid), {}
    for r in cat["sources"]:
        sid = C.row_id("sources", r)
        e = doc["sources"].get(sid) or {}
        if C.text_of(e.get("source_owner")):
            out[sid] = {"name": C.text_of(e["source_owner"]), "label": "source owner"}
        elif C.text_of(e.get("data_owner") or r.get("Data owner")):
            out[sid] = {"name": C.text_of(e.get("data_owner") or r["Data owner"]), "label": "data owner, no source owner named"}
    return out


# ---- reading --------------------------------------------------------------------------------------------------------------------

def _state(row: dict, e: dict, owners: dict) -> str:
    if e.get("left_out"):
        return "left_out"
    src = owners["source"]["value"]
    if not src:
        return "needs_owner"
    if e.get("confirmed_by") and norm(e["confirmed_by"]) == norm(src):
        return "confirmed"
    people = [c for h, c in row.items() if h not in (C.id_header("sources"), C.HIDDEN) and isinstance(c, dict)]
    return "edited" if any(_human(c) for c in people) or _human(e.get("source_owner")) or _human(e.get("business_owner")) else "drafted"


def _kpi_names(shown: dict) -> dict[str, str]:
    return {C.row_id("kpis", k): C.text_of(k.get("KPI name")) or C.row_id("kpis", k) for k in shown["kpis"] if not k.get(C.HIDDEN)}


def _fields_of(shown: dict, sid: str, kpis: dict[str, str]) -> tuple[list[dict], list[dict]]:
    tids = {C.row_id("tables", t) for t in shown["tables"] if not t.get(C.HIDDEN) and C.text_of(t.get("Source ID")) == sid}
    fields = [{"id": C.row_id("fields", f), "name": C.text_of(f.get("Field name as in the source")), "meaning": C.text_of(f.get("Business meaning")) or None,
               "class": C.text_of(f.get("Personal data class")) or None}
              for f in shown["fields"] if not f.get(C.HIDDEN) and C.text_of(f.get("Item ID")) in tids]
    feeds = {k for t in shown["tables"] if C.row_id("tables", t) in tids for k in C.split_ids(C.text_of(t.get("Related KPIs")))}
    feeds |= {k for f in shown["fields"] if not f.get(C.HIDDEN) and C.text_of(f.get("Item ID")) in tids for k in C.split_ids(C.text_of(f.get("Feeds KPI")))}
    return fields, [{"id": k, "name": kpis[k]} for k in sorted(feeds) if k in kpis]


def _row(r: dict, e: dict, shown: dict, kpis: dict, profile: dict, viewer: C.Viewer, org: bool) -> dict:
    sid, owners = C.row_id("sources", r), owner_cells(r, e)
    state = _state(r, e, owners)
    fields, measures = _fields_of(shown, sid, kpis)
    ref = e.get("system_ref")
    system = next((s for k, s in profile["systems"].items() if ref == f"systems.{k}"), None)
    system_name = PV._v(system, "name") if system and not system.get("restricted") else None
    lead = "approver" in viewer.roles or is_named(viewer, owners["data"]["value"])
    proposals = e.get("proposals") or {}
    mine = is_named(viewer, owners["source"]["value"])
    problems = [{"id": p["id"], "text": p["text"], "by": "Anonymous" if p.get("anonymous") else p["by"], "at": p["at"]} for p in e.get("known_problems") or []]
    return {
        "id": sid, "name": C.text_of(r.get("Source name")), "system": {"ref": ref, "name": system_name or (ref if str(ref).startswith("area:") else None)},
        "format": _cell(r.get("Source type")), "structure": _cell(r.get("Structured or unstructured")), "lands": _cell(r.get("Where it lands or lives")),
        "connection": _cell(r.get("Connection method")), "frequency": _cell(r.get("How often it arrives")), "sla": _cell(r.get("Expected arrival time or SLA")),
        "personal": _cell(r.get("Contains personal data?")), "undecided": norm(C.text_of(r.get("Contains personal data?"))) in ("", "not sure"),
        "who_may_see": _cell(r.get("Who may see it")), "owners": owners, "state": state,
        "confirmed_by": e.get("confirmed_by"), "confirmed_at": e.get("confirmed_at"), "waiting_for": None if state == "confirmed" else owners["source"]["value"],
        "proposals": {k: {**v, "waiting_for": owners["data"]["value"] or "the governance lead"} for k, v in proposals.items()},
        "fields": fields, "used_in": {"measures": measures, "steps": e.get("used_in", {}).get("steps", []), "clusters": e.get("used_in", {}).get("clusters", [])},
        "problems": problems, "left_out": e.get("left_out"), "history": e.get("history", []),
        "can": {"edit": committee(viewer) and state != "left_out", "set_class": lead, "confirm": mine and state != "left_out",
                "reassign": mine, "remove": org and state != "left_out", "restore": org and state == "left_out", "problem": committee(viewer) or mine},
    }


def _visible(plane, bid: str, viewer: C.Viewer, everything: bool) -> tuple[dict, dict, int]:
    """The catalogue tabs this viewer may see (the catalogue's own governance, with the organiser and the sponsor passing a source's own
    personal-data list), and how many source rows are closed to them."""
    cat, _ = S._raw(plane, bid)
    if everything:
        return cat, {}, 0
    guards = C.guards(cat, S._governance(plane, bid))
    for key, lists in guards.items():
        if key[0] == "sources" and lists and lists[0]:
            lists[0] = lists[0] | C.ROLE_PASS  # personal "Yes" or restricted: the people named, the organiser, the sponsor, the company admin
    shown, _f = C.view_of(cat, guards, viewer)
    return shown, guards, sum(1 for r in shown["sources"] if r.get(C.HIDDEN))


def rows(plane, bid: str, viewer: C.Viewer, org: bool = False, everything: bool = False) -> dict:
    """{rows, left_out, restricted, counters} at the viewer's tier. `everything` is the kernel's own read (no viewer)."""
    base = B.read_baseline(plane, bid)
    if base is None:
        raise Refusal("not_found", "We could not find that baseline.")
    shown, _g, closed = _visible(plane, bid, viewer, everything)
    doc, kpis = load(plane, bid), _kpi_names(shown)
    profile = PV.read(plane, _pviewer(viewer))
    out, gone = [], []
    for r in shown["sources"]:
        if r.get(C.HIDDEN):
            continue
        row = _row(r, doc["sources"].get(C.row_id("sources", r)) or {}, shown, kpis, profile, viewer, org)
        if not everything and not (READERS & viewer.roles) and not any(is_named(viewer, o["value"]) for o in row["owners"].values()):
            continue  # a source owner sees their own rows only
        (gone if row["state"] == "left_out" else out).append(row)
    restricted = closed if (READERS & viewer.roles) or everything else 0
    return {"rows": out, "left_out": gone if (org or everything or committee(viewer)) else [], "restricted": restricted,
            "restricted_label": RESTRICTED, "counters": counters(out, restricted, doc), "state": doc["state"], "profile": profile}


def counters(rs: list[dict], restricted: int, doc: dict) -> dict:
    """Exact counts from the rows shown. Nothing is averaged."""
    n = lambda f: sum(1 for r in rs if f(r))  # noqa: E731
    areas = doc.get("areas") or []
    return {"named": len(rs), "confirmed": n(lambda r: r["state"] == "confirmed"), "drafted": n(lambda r: r["state"] == "drafted"),
            "edited": n(lambda r: r["state"] == "edited"),
            "all_three_owners": n(lambda r: all(o["value"] for o in r["owners"].values())),
            "no_source_owner": n(lambda r: not r["owners"]["source"]["value"]),
            "class_decided": n(lambda r: norm(r["personal"]["value"]) in ("yes", "no")),
            "arrival_known": n(lambda r: r["frequency"]["value"] and r["lands"]["value"]),
            "with_problems": n(lambda r: r["problems"]), "used_by_no_measure": n(lambda r: not r["used_in"]["measures"]),
            "restricted": restricted, "areas_added": len(areas)}


# ---- technical areas ------------------------------------------------------------------------------------------------------------

def areas(plane, bid: str, viewer: C.Viewer, rs: list[dict], doc: dict, profile: dict, org: bool) -> dict:
    """Chips: a system per profile system, a team per distinct `people.<id>.team`, plus what a person added. A shut system is a count-free
    chip reading "A restricted area". Linked areas are those the same sources touch (a source's system and its owners' teams)."""
    by_name = {norm(PV._v(p, "name")): p for p in profile["people"].values()}
    team_of = lambda name: norm(PV._v(by_name.get(norm(name)) or {}, "team"))  # noqa: E731
    overlay = {a["id"]: a for a in doc.get("areas") or []}
    chips: dict[str, dict] = {}
    for key, s in profile["systems"].items():
        if s.get("restricted"):
            chips[key] = {"id": key, "kind": "system", "name": RESTRICTED_AREA, "restricted": True, "who_can_say": [], "profile_ref": None}
            continue
        owner = PV._v(s, "owner")
        say = [{"name": owner, "mark": (s.get("owner") or {}).get("mark", "stated"), "from": "the systems list"}] if owner else []
        chips[f"system:{key}"] = {"id": f"system:{key}", "kind": "system", "name": PV._v(s, "name") or key, "profile_ref": f"systems.{key}", "who_can_say": say}
    teams: dict[str, dict] = {}
    for p in profile["people"].values():
        t = PV._v(p, "team")
        if t and PV._v(p, "name"):
            c = teams.setdefault(norm(t), {"id": f"team:{_slug(t)}", "kind": "team", "name": str(t), "profile_ref": None, "who_can_say": []})
            c["who_can_say"].append({"name": PV._v(p, "name"), "mark": (p.get("team") or {}).get("mark", "stated"), "from": "the people list"})
    chips.update({c["id"]: c for c in teams.values()})
    for a in overlay.values():
        c = chips.setdefault(a["id"], {"id": a["id"], "kind": a["kind"], "name": a["name"], "profile_ref": None, "who_can_say": []})
        c["who_can_say"] = c["who_can_say"] + [w for w in a.get("who_can_say", []) if norm(w["name"]) not in {norm(x["name"]) for x in c["who_can_say"]}]
        c["hidden"] = a.get("hidden")
        c["added"] = a["id"].startswith("added:")
    touch: dict[str, set[str]] = {}
    for r in rs:
        ref = r["system"]["ref"] or ""
        mine = {f"system:{ref[8:]}"} if ref.startswith("systems.") else {ref} if ref.startswith("area:") else set()
        mine = {("added:" + m[5:]) if m.startswith("area:") else m for m in mine}
        mine |= {c["id"] for n in (o["value"] for o in r["owners"].values()) if n for c in teams.values() if team_of(n) == norm(c["name"])}
        touch[r["id"]] = {m for m in mine if m in chips}
    for c in chips.values():
        ids = [sid for sid, t in touch.items() if c["id"] in t and (c["kind"] == "system" or not c.get("restricted"))]
        c["source_ids"] = ids
        c["count"] = len(ids) if c["kind"] == "system" else len(c["who_can_say"])
        c["confirmed"] = bool(ids) and all(next(r for r in rs if r["id"] == i)["state"] == "confirmed" for i in ids)
        c["linked"] = sorted({o for i in ids for o in touch[i]} - {c["id"]})
        c.setdefault("hidden", None)
        c.setdefault("added", False)
    shown = [c for c in chips.values() if not c["hidden"]]
    return {"chips": shown, "hidden": [c for c in chips.values() if c["hidden"]] if org else [],
            "nobody_named": sum(1 for c in shown if not c["who_can_say"] and not c.get("restricted"))}


def read(plane, bid: str, viewer: C.Viewer, body: dict | None = None, org: bool = False, **_: Any) -> dict:
    got = rows(plane, bid, viewer, org)
    doc = load(plane, bid)
    ar = areas(plane, bid, viewer, got["rows"], doc, got["profile"], org)
    got["counters"]["areas"] = len(ar["chips"])
    got["counters"]["areas_nobody_named"] = ar["nobody_named"]
    systems = [{"ref": f"systems.{k}", "name": PV._v(s, "name")} for k, s in got["profile"]["systems"].items() if not s.get("restricted") and PV._v(s, "name")]
    schema = {"formats": C.options("sources", "Source type"), "frequencies": C.options("sources", "How often it arrives"),
              "connections": C.options("sources", "Connection method"), "structures": C.options("sources", "Structured or unstructured"),
              "classes": ["Yes", "No", "Not sure"]}
    people = sorted({str(PV._v(p, "name")) for p in got["profile"]["people"].values() if PV._v(p, "name")})
    return {"baseline_id": bid, "sources": got["rows"], "left_out": got["left_out"], "restricted": got["restricted"], "restricted_label": RESTRICTED,
            "counters": got["counters"], "areas": ar, "data_sources": doc["state"], "systems": systems, "people": people, "schema": schema,
            "can": {"draft": bool({"company_admin", "sponsor"} & viewer.roles), "add": committee(viewer), "done": org, "area": committee(viewer)}}


# ---- writing --------------------------------------------------------------------------------------------------------------------

def _writable(plane, bid: str, extras_only: bool = False) -> None:
    """The catalogue row is read only once the baseline is signed; the owner cells, the confirmation and known problems live in the extras file and stay writable."""
    if extras_only:
        S._baseline(plane, bid)  # still a 404 for a baseline that is not there
        return
    try:
        S._changeable(plane, bid)  # a signed baseline answers read_only here: the same "signed" refusal, so edit() can still save the owner cells
        refuse_if_signed(plane, bid)
    except B.Locked as e:
        raise Refusal("signed", str(e)) from None
    except C.CatalogueError as e:
        if e.code != "read_only":
            raise
        raise Refusal("signed", e.message) from None


def _seen(plane, bid: str, viewer: C.Viewer, sid: str) -> dict:
    """The visible row, or the same 404 as a row that does not exist."""
    got = rows(plane, bid, viewer)
    row = next((r for r in got["rows"] + got["left_out"] if r["id"] == sid), None)
    if row is None:
        raise Refusal("not_found", "We could not find that source.")
    return row


def _need_committee(viewer: C.Viewer) -> None:
    if not committee(viewer):
        raise Refusal("forbidden", "Only the committee can change a source.")


def _owner_cell(value: Any, by: str, how: str) -> dict:
    text = str(value or "").strip()
    return prov(text, "stated", by, how) if text else unknown(by, how)


def _touch(doc: dict, e: dict, sid: str, by: str, what: str, owner: str | None) -> None:
    """A change to a confirmed source clears the confirmation (history keeps who gave it) and tells its source owner."""
    if e.get("confirmed_by"):
        _log(e, by, f"was confirmed by {e['confirmed_by']}; changed ({what})")
        e["confirmed_by"] = e["confirmed_at"] = None
        if owner:
            doc["notices"].append({"to": owner, "kind": "info", "source_id": sid, "at": now(), "by": by, "text": "Your source changed"})


def _guess(plane, bid: str, cells: dict[str, dict[str, Any]], source: str, by: str = LENS) -> None:
    """Fill blank catalogue cells with a guess. A cell a person wrote or answered is left alone."""
    with lock_for(S._folder(plane, bid) / "catalogue.json"):
        cat, conflicts = S._raw(plane, bid)
        for rid, want in cells.items():
            r = C.find(cat, "sources", rid)
            for header, value in want.items():
                if r is not None and value and C.is_blank(r.get(header)) and not C.is_manual(r.get(header)):
                    r[header] = prov(value, "guessed", by, source)
        S._save(plane, bid, cat, conflicts)


def add(plane, bid: str, viewer: C.Viewer, body: dict, org: bool = False, **_: Any) -> dict:
    _need_committee(viewer)
    _writable(plane, bid)
    name = str((body.get("cells") or body).get("name") or "").strip()
    if not name:
        raise Refusal("invalid", NEEDS_NAME)
    cells = {HEADERS[k]: str(v) for k, v in (body.get("cells") or body).items() if k in HEADERS and k not in LEAD_ONLY and str(v or "").strip()}
    sid = S.add_row(plane, bid, "sources", cells, viewer.name, "stated")
    _guess(plane, bid, {sid: {"Contains personal data?": "Not sure"}}, "undecided until the governance lead decides", "Signal Harbor")  # a blank answer would close the row to everyone but the admin
    extras = {k: body.get("cells", body).get(k) for k in ("source_owner", "business_owner", "system_ref")}

    def put(doc):
        e = _entry(doc, sid)
        for k in ("source_owner", "business_owner"):
            if str(extras[k] or "").strip():
                e[k] = _owner_cell(extras[k], viewer.name, "named in the data sources tab")
        e["system_ref"] = extras["system_ref"] or None
        _log(e, viewer.name, "added")
        if doc["state"]["state"] in ("not_started", "drafted"):
            doc["state"]["state"] = "in_review"
    _update(plane, bid, put)
    return {"id": sid}


def edit(plane, bid: str, viewer: C.Viewer, body: dict, source_id: str, org: bool = False, **_: Any) -> dict:
    row = _seen(plane, bid, viewer, source_id)
    mine = is_named(viewer, row["owners"]["source"]["value"])
    cells = body.get("cells") if isinstance(body.get("cells"), dict) else body
    if body.get("left_out") is not None or body.get("restore"):
        return _leave(plane, bid, viewer, source_id, body, org)
    lead = row["can"]["set_class"]
    if not committee(viewer) and not (mine and set(cells) <= {"frequency", "connection", "lands", "sla"}) and not (lead and set(cells) <= set(LEAD_ONLY)):
        raise Refusal("forbidden", "Only the committee can change a source.")
    if "name" in cells and not str(cells["name"] or "").strip():
        raise Refusal("invalid", NEEDS_NAME)
    cat_changes = {HEADERS[k]: str(v or "") for k, v in cells.items() if k in HEADERS and not (k in LEAD_ONLY and not lead)}
    try:
        _writable(plane, bid)
        data_extra = False
    except Refusal:
        # signed baseline: the catalogue row stays read only; the three owner cells (data owner too) and the proposals still save to the extras file
        if set(cat_changes) - {"Data owner"} or not (cells.keys() & {"data_owner", "source_owner", "business_owner", "system_ref"}):
            raise
        data_extra, cat_changes = "Data owner" in cat_changes, {}
    proposed = [k for k in LEAD_ONLY if k in cells and not lead]
    if cat_changes:
        S.edit_row(plane, bid, "sources", source_id, cat_changes, viewer.name, "stated", viewer)

    def put(doc):
        e = _entry(doc, source_id)
        for k in ("source_owner", "business_owner"):
            if k in cells:
                e[k] = _owner_cell(cells[k], viewer.name, "named in the data sources tab")
        if "system_ref" in cells:
            e["system_ref"] = cells["system_ref"] or None
        if data_extra:
            e["data_owner"] = _owner_cell(cells["data_owner"], viewer.name, "named in the data sources tab")
        for k in proposed:
            e["proposals"][k] = {"value": str(cells[k] or ""), "by": viewer.name, "at": now()}
        for k in LEAD_ONLY:
            if k in cells and lead:
                e["proposals"].pop(k, None)
        _touch(doc, e, source_id, viewer.name, ", ".join(cells), row["owners"]["source"]["value"])
        if e.get("history") is not None and (cat_changes or any(k in cells for k in ("source_owner", "business_owner", "system_ref", "data_owner"))):
            _log(e, viewer.name, "edited " + ", ".join(sorted(cells)))
        if doc["state"]["state"] in ("not_started", "drafted"):
            doc["state"]["state"] = "in_review"
    _update(plane, bid, put)
    return {"status": "saved", "proposed": proposed}


def _leave(plane, bid: str, viewer: C.Viewer, sid: str, body: dict, org: bool) -> dict:
    if not org:
        raise Refusal("forbidden", "Only the organiser can take a source off the map.")
    _writable(plane, bid)
    reason = str((body.get("left_out") or {}).get("reason") if isinstance(body.get("left_out"), dict) else body.get("reason") or "").strip()
    if not body.get("restore") and not reason:
        raise Refusal("invalid", "Say why this is not a source.")

    def put(doc):
        e = _entry(doc, sid)
        e["left_out"] = None if body.get("restore") else {"by": viewer.name, "reason": reason[:MAX_NOTE], "at": now()}
        _log(e, viewer.name, "restored" if body.get("restore") else f"left out: {reason[:80]}")
    _update(plane, bid, put)
    return {"status": "saved"}


def confirm(plane, bid: str, viewer: C.Viewer, body: dict, source_id: str, **_: Any) -> dict:
    row = _seen(plane, bid, viewer, source_id)
    if not row["can"]["confirm"]:
        raise Refusal("forbidden", ONLY_OWNER)  # the organiser cannot confirm for them
    _writable(plane, bid, extras_only=True)

    def put(doc):
        e = _entry(doc, source_id)
        e["source_owner"] = prov(viewer.name, "stated", viewer.name, "confirmed by the source owner")
        e["confirmed_by"], e["confirmed_at"] = viewer.name, now()
        _log(e, viewer.name, "confirmed")
    _update(plane, bid, put)
    return {"status": "confirmed", "confirmed_by": viewer.name}


def reassign(plane, bid: str, viewer: C.Viewer, body: dict, source_id: str, **_: Any) -> dict:
    row = _seen(plane, bid, viewer, source_id)
    to = str(body.get("to") or "").strip()
    if not row["can"]["reassign"]:
        raise Refusal("forbidden", ONLY_OWNER)
    if not to:
        raise Refusal("invalid", "Say who runs this source.")
    _writable(plane, bid, extras_only=True)

    def put(doc):
        e = _entry(doc, source_id)
        e["source_owner"] = prov(to, "stated", viewer.name, f"handed over by {viewer.name}")
        e["confirmed_by"] = e["confirmed_at"] = None
        _log(e, viewer.name, f"handed the source owner cell to {to}")
        doc["notices"].append({"to": to, "kind": "request", "source_id": source_id, "at": now(), "by": viewer.name,
                               "text": f"Confirm your source: {row['name']}"})
    _update(plane, bid, put)
    return {"status": "handed_over", "to": to}


def problem(plane, bid: str, viewer: C.Viewer, body: dict, source_id: str, **_: Any) -> dict:
    row = _seen(plane, bid, viewer, source_id)
    text = str(body.get("text") or "").strip()
    if not row["can"]["problem"]:
        raise Refusal("forbidden", "Only the committee or the source owner can add a problem.")
    if not text:
        raise Refusal("invalid", "Say what the problem is.")
    _writable(plane, bid, extras_only=True)
    note = {"id": f"p{int(datetime.now(timezone.utc).timestamp() * 1000)}", "text": text[:MAX_NOTE], "by": viewer.name, "at": now(),
            "anonymous": bool(body.get("anonymous"))}
    _update(plane, bid, lambda doc: _entry(doc, source_id)["known_problems"].append(note))
    return {"id": note["id"]}


def area_add(plane, bid: str, viewer: C.Viewer, body: dict, **_: Any) -> dict:
    _need_committee(viewer)
    _writable(plane, bid)
    name, kind = str(body.get("name") or "").strip(), body.get("kind")
    if not name or kind not in ("system", "team"):
        raise Refusal("invalid", "Name the area and say whether it is a system or a team.")
    aid = f"added:{_slug(name)}"

    def put(doc):
        if any(a["id"] == aid for a in doc["areas"]):
            raise Refusal("conflict", "That area is already on the strip.")
        doc["areas"].append({"id": aid, "kind": kind, "name": name[:120], "profile_ref": None, "source_ids": [], "linked": [], "hidden": None,
                             "who_can_say": [], "added_by": viewer.name, "mark": "stated"})
    _update(plane, bid, put)
    return {"id": aid}


def area_edit(plane, bid: str, viewer: C.Viewer, body: dict, area_id: str, org: bool = False, **_: Any) -> dict:
    _need_committee(viewer)
    _writable(plane, bid)
    if not re.fullmatch(r"[a-z0-9:_-]{1,90}", area_id):
        raise Refusal("not_found", "We could not find that area.")
    if "hidden_reason" in body or body.get("restore"):
        if not org:
            raise Refusal("forbidden", "Only the organiser can hide an area.")
        if "hidden_reason" in body and not str(body["hidden_reason"] or "").strip():
            raise Refusal("invalid", "Say why this is not an area.")

    def put(doc):
        a = next((x for x in doc["areas"] if x["id"] == area_id), None)
        if a is None:  # a chip worked out from the profile gets its overlay on the first change
            kind = "team" if area_id.startswith("team:") else "system"
            a = {"id": area_id, "kind": kind, "name": str(body.get("name") or area_id.split(":", 1)[-1]), "profile_ref": None, "source_ids": [],
                 "linked": [], "hidden": None, "who_can_say": []}
            doc["areas"].append(a)
        if "hidden_reason" in body:
            a["hidden"] = {"by": viewer.name, "reason": str(body["hidden_reason"]).strip()[:MAX_NOTE]}
        if body.get("restore"):
            a["hidden"] = None
        who = str(body.get("add_person") or "").strip()
        if who and not any(norm(w["name"]) == norm(who) for w in a["who_can_say"]):
            a["who_can_say"].append({"name": who, "mark": "stated", "from": f"named by {viewer.name}"})
            doc["notices"].append({"to": who, "kind": "invite", "at": now(), "by": viewer.name,
                                   "text": f"You were named as someone who could say how {a['name']} works"})
        a["who_can_say"] = [w for w in a["who_can_say"] if norm(w["name"]) != norm(body.get("remove_person"))]
    _update(plane, bid, put)
    return {"status": "saved"}


def draft(plane, bid: str, viewer: C.Viewer, body: dict, **_: Any) -> dict:
    """Lens drafts: one source per system on the profile systems list, and per system or file the owners named in their answers, every cell
    guessed, from the document or interview. A person's cell is never replaced; a source already on the map is not made twice."""
    if not ({"company_admin", "sponsor"} & viewer.roles):
        raise Refusal("forbidden", "Only the organiser or the sponsor can ask Lens to draft.")
    _writable(plane, bid)
    profile = PV.read(plane, _pviewer(viewer))
    systems = [(k, s) for k, s in profile["systems"].items() if not s.get("restricted") and PV._v(s, "name")]
    named = C._systems(read_answers(plane, bid))
    docs = {(s[c].get("ref") or {}).get("id") for _k, s in systems for c in s if isinstance(s.get(c), dict) and (s[c].get("ref") or {}).get("kind") == "document"} - {None}
    if not systems and not named:
        raise Refusal("invalid", NOTHING_TO_READ)
    cat, _c = S._raw(plane, bid)
    have = [C.match_name(C.text_of(r.get("Source name"))) for r in cat["sources"]]
    want: dict[str, dict] = {}
    for k, s in systems:
        want[PV._v(s, "name")] = {"ref": f"systems.{k}", "kind": PV._v(s, "kind") or "", "owner": PV._v(s, "owner"), "lands": PV._v(s, "lands"),
                                  "freq": PV._v(s, "frequency"), "from": "the systems list"}
    for key, items in named.items():
        nm = C.text_of(items[0]["row"]["name"]).strip()
        if not any(C._same_system(C.match_name(w), key) for w in want):
            owner = next((C.text_of(i["row"].get("owner")) for i in items if C.text_of(i["row"].get("owner"))), None)
            want[nm] = {"ref": None, "kind": C.text_of(items[0]["row"].get("kind")), "owner": owner, "lands": C.text_of(items[0]["row"].get("lands")) or None,
                        "freq": None, "from": "the owners' answers"}
    new = {n: w for n, w in want.items() if not any(C._same_system(C.match_name(n), h) or C._same_system(h, C.match_name(n)) for h in have if h)}
    ids = S.propose_rows(plane, bid, {"sources": [(n, w["kind"]) for n, w in new.items()]}, "", "the systems list", False)["sources"]
    by_name = {C.match_name(n): w for n, w in new.items()}
    freq = C.options("sources", "How often it arrives")
    stamp = now()
    cat, _c = S._raw(plane, bid)
    for rid in ids:
        r = C.find(cat, "sources", rid)
        w = by_name.get(C.match_name(C.text_of(r.get("Source name")))) if r else None
        if w:
            _guess(plane, bid, {rid: {"Where it lands or lives": w["lands"], "How often it arrives": next((o for o in freq if norm(o) == norm(w["freq"])), None)}}, w["from"])

    def put(doc):
        for rid in ids:
            r = C.find(cat, "sources", rid)
            w = by_name.get(C.match_name(C.text_of(r.get("Source name")))) if r else None
            e = _entry(doc, rid)
            if w and C.is_blank(e.get("source_owner")) and w["owner"]:
                e["source_owner"] = prov(str(w["owner"]), "guessed", LENS, w["from"])
            if w and w["ref"] and not e.get("system_ref"):
                e["system_ref"] = w["ref"]
            if not e["history"]:
                _log(e, LENS, "drafted")
        doc["state"].update(state="drafted" if doc["state"]["state"] in ("not_started", "drafted") else doc["state"]["state"], drafted_at=stamp, drafted_by=LENS)
    _update(plane, bid, put)
    chips = len(systems) + len({norm(PV._v(p, "team")) for p in profile["people"].values() if PV._v(p, "team")})
    return {"drafted": len(ids), "documents": len(docs), "areas": chips,
            "message": f"Lens drafted {len(ids)} source{'s' if len(ids) != 1 else ''} from {len(docs)} document{'s' if len(docs) != 1 else ''} and the systems list."}


def _close_once(by: str) -> Callable[[dict], dict]:
    def close(doc: dict) -> dict:
        if doc["state"]["state"] != "done":  # a second Done keeps the first done_at
            doc["state"].update(state="done", done_by=by, done_at=now())
        return dict(doc["state"])
    return close


def done(plane, bid: str, viewer: C.Viewer, body: dict, org: bool = False, **_: Any) -> dict:
    if not org:
        raise Refusal("forbidden", "Only the organiser can close the data sources.")
    _writable(plane, bid, extras_only=True)  # the substage's own state lives in the extras file, so Done works on a signed baseline too
    state = _update(plane, bid, _close_once(viewer.name))
    return {"status": "done", "data_sources": state, "counters": read(plane, bid, viewer, org=org)["counters"]}


# ---- the two spellings ----------------------------------------------------------------------------------------------------------

OPS: list[tuple[str, str, str, Callable]] = [
    ("GET", "", "read", read), ("POST", "", "add", add), ("POST", "/draft", "draft", draft), ("POST", "/done", "done", done),
    ("POST", "/areas", "area_add", area_add), ("PUT", "/areas/{area_id}", "area_edit", area_edit),
    ("PUT", "/{source_id}", "edit", edit), ("POST", "/{source_id}/confirm", "confirm", confirm),
    ("POST", "/{source_id}/reassign", "reassign", reassign), ("POST", "/{source_id}/problems", "problem", problem)]


def plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message, "detail": message}, status_code=status)


def run(op: Callable, resolve: Callable) -> Callable:
    """An endpoint: `resolve(request, params)` gives (plane, baseline_id, viewer, organiser) or raises Refusal; the op does the rest."""
    async def endpoint(request: Request):
        try:
            body: dict = {}
            if request.method != "GET":
                try:
                    body = await request.json()
                except ValueError:
                    body = {}
                if not isinstance(body, dict):
                    raise Refusal("invalid", "Those details could not be read. Please try again.")
            params = {k: v for k, v in request.path_params.items() if k in ("source_id", "area_id")}
            plane, bid, viewer, org = await run_in_threadpool(resolve, request)
            return await run_in_threadpool(lambda: op(plane, bid, viewer, body=body, org=org, **params))
        except C.CatalogueError as e:
            return plain(STATUS.get(e.code, 409), "not_allowed" if e.code == "forbidden" else e.code, e.message)
        except S.StoreError as e:
            return plain(500, "unreadable", str(e))
        except (PermissionError, CrossCompanyError):
            return plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")
    return endpoint


def register(rt: APIRouter, prefix: str, resolve: Callable, only: tuple[str, ...] = ()) -> None:
    for method, suffix, name, op in OPS:
        if not only or name in only:
            rt.add_api_route(prefix + suffix, run(op, resolve), methods=[method], name=f"data_sources_{name}")


def _baseline_side(request: Request):
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except LookupError:
        raise PermissionError("no company space") from None
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    name = str(acct.get("display_name") or "")
    twins = [a for a in request.app.state.account_store.in_company(request.state.company_id) if norm(a.get("display_name")) == norm(name)]
    viewer = C.Viewer(name, frozenset(request.state.roles), len(twins) > 1, request.state.account_id)
    return plane, request.path_params["baseline_id"], viewer, "company_admin" in viewer.roles


register(router, "/baselines/{baseline_id}/data-sources", _baseline_side)
