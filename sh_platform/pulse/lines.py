"""Pulse lines (SHAPES 1, A-071): one small reader per record kind. Each takes (plane, viewer, now) and returns [LINE]; a missing or unreadable
file gives [] so the pulse never fails because one module has no data. Records are read by path, never imported from the modules."""
import functools
import json
import re
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sh_platform.graph.read import graph_for
from sh_platform.interview import engine
from sh_platform.profile import view

log = logging.getLogger(__name__)
OPEN_WALL = ("lobby", "briefing", "private_rooms", "board", "together", "signing", "paused")
OPEN_M2_REQUEST = ("sent", "opened", "no_reply")  # modules/m2_baseline/domain/requests.py OPEN_STATES
SLOTS = ("sponsor", "company_admin")  # countersign order in modules/m2_baseline/contracts/signoff.yaml and modules/m3_connect/contracts/plan.yaml
DATA_TEAM = frozenset({"analyst", "company_admin"})
WEEK = timedelta(days=7)
QUIET = ("Person", "Field", "Pipeline")  # people are not "new on the map"; fields and pipelines carry raw column and file names
SILENT = timedelta(days=3)  # an owner asked longer ago than this is "waiting on others" (the organiser artboard)
MINUTES = {"invite": 5, "decision": 3, "request": 5, "measure": 1, "brief": 2, "ops": 10, "signature": 5,
    "review": 30,
}  # the time a line is expected to take


def _json(path: Path, empty=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def _dirs(folder: Path) -> list[Path]:
    try:
        return sorted(p for p in folder.iterdir() if p.is_dir())
    except OSError:
        return []


def _files(folder: Path) -> list[Path]:
    try:
        return sorted(folder.glob("*.json"))
    except OSError:
        return []


def _time(v) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _name(v: view.Viewer, *names) -> bool:
    """The viewer is one of these named people (a shared display name never matches: view.allows)."""
    guard = frozenset(view.norm(n) for n in names if isinstance(n, str) and n.strip())
    return bool(guard) and view.allows(guard, v)


def safe(fn):
    @functools.wraps(fn)
    def run(*a, **k) -> list[dict]:
        try:
            return fn(*a, **k)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
            log.warning("pulse: %s skipped (%s)", fn.__name__, type(e).__name__)
            return []
    return run


def line(id: str, kind: str, title: str, detail: str, href: str, action: str, record: str, at, due=None) -> dict:
    return {"id": id, "kind": kind, "title": title, "detail": detail, "href": href, "action": action, "minutes": MINUTES[kind],
            "due": str(due)[:10] if due else None, "source": {"record": record, "at": str(at) if at else None}}


def _plain(source) -> str:
    """A source id such as capital_calls_mailbox, read as words."""
    t = str(source).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def _topic(s: dict) -> str:
    prep = s.get("preparation") or {}
    return prep.get("topic") or (prep.get("purpose") or "A wall")[:120]


def _closes(plane, s: dict):
    """The wall's close: the start of the private rooms plus the window the rooms were given; None when either is missing."""
    prep = s.get("preparation") or {}
    started = ((_json(plane.path("intents", "m1_intent", "stages", f"{s['id']}.json")) or {}).get("started") or {}).get("private_rooms")
    if prep.get("wall_window_days") is None or not started:
        return None
    return datetime.fromtimestamp(started + float((prep.get("split") or {}).get("individual", 0)) * 60, timezone.utc).date()


def sessions(plane) -> list[dict]:
    return [s for s in (_json(p) for p in _files(plane.path("intents", "m1_intent", "sessions"))) if isinstance(s, dict) and s.get("id")]


def _mine(s: dict, v: view.Viewer, key: str = "organiser_account_id") -> bool:
    """The viewer organises this wall, or (key approver_account_id) is its approver, the sponsor who signs the charter."""
    who = s.get(key) if key == "organiser_account_id" else (s.get("preparation") or {}).get(key)
    return bool(v.account_id) and who == v.account_id


def _charter(plane, sid: str) -> dict:
    """The charter's latest version, {} when there is none."""
    return ((_json(plane.path("intents", "m1_intent", "charters", f"{sid}.json")) or {}).get("versions") or [{}])[-1]


# ---- Invited
@safe
def invited(plane, v: view.Viewer, now: datetime) -> list[dict]:
    out = []
    for p in _files(plane.path("intents", "m1_intent", "sessions")):
        s = _json(p) or {}
        if s.get("state") not in OPEN_WALL:
            continue
        sid = s["id"]
        seats = (_json(plane.path("intents", "m1_intent", "rooms", f"{sid}.json")) or {}).get("seats") or []
        if not any(x.get("state") == "taken" and v.account_id and x.get("account_id") == v.account_id for x in seats):
            continue
        out.append(line(f"invite:{sid}", "invite", _topic(s), "You have a seat on this wall.", f"/centre/intent/wall/{sid}", "Open the wall",
                        f"sessions/{sid}", s.get("updated_at"), _closes(plane, s)))
    return out


@safe
def interview(plane, v: view.Viewer, now: datetime) -> list[dict]:
    me = next((q for q in engine.people(plane, [v.name]) if view.norm(q["name"]) == view.norm(v.name)), None)
    rows = [r for r in (_json(plane.path("context", "interview", "links.json"), []) or [])
            if me and r.get("person") == me["id"] and not r.get("revoked_at") and (_time(r.get("expires_at")) or now) > now]
    if not rows or v.shared_name:
        return []
    if (_json(plane.path("context", "interview", f"{me['id']}.json"), {}) or {}).get("status") == "done":
        return []  # finished interviews are not an act any more
    r = rows[-1]
    return [line(f"interview:{r['id']}", "invite", "Your interview", "A short interview is open for you.", "/company/interview",
                 "Start the interview", f"interview/{r['id']}", r.get("at"), r.get("expires_at"))]


# ---- Decide
@safe
def measures(plane, v: view.Viewer, now: datetime) -> list[dict]:
    out = []
    for b in _dirs(plane.path("intents", "m2_baseline")):
        if b.name == "outcomes" or (_json(b / "baseline.json") or {}).get("state") == "signed":
            continue
        gov = _json(b / "governed_state.json", {}) or {}
        names = {k.get("id"): k.get("name") for k in (_json(b / "kpis.json", []) or []) if isinstance(k, dict)}
        for kid, entry in gov.items():
            owners = ((entry.get("owners") or {}).get("value")) or {}
            people = [(o.get("value") if isinstance(o, dict) else o) for o in (owners.values() if isinstance(owners, dict) else [])]
            open_fields = [f for f, c in entry.items() if not (isinstance(c, dict) and c.get("mark") == "stated")]
            if _name(v, *people) and open_fields:
                out.append(line(f"confirm:{b.name}:{kid}", "decision", names.get(kid) or "A measure",
                                f"{len(open_fields)} part(s) wait for your confirmation.", f"/centre/intent/baseline/{b.name}", "Confirm",
                                f"m2_baseline/{b.name}/governed_state", (entry.get("owners") or {}).get("at")))
    return out


def _all_confirmed(plane, baseline_id: str) -> bool:
    """The part of the ready-to-build gate that is readable by path: there are measures and every part of each is stated by its owner."""
    gov = _json(plane.path("intents", "m2_baseline", baseline_id, "governed_state.json"), {}) or {}
    return bool(gov) and all(isinstance(c, dict) and c.get("mark") == "stated"
                             for entry in gov.values() if isinstance(entry, dict) for c in entry.values())


def _next_slot_mine(signed, open_: bool, v: view.Viewer) -> bool:
    signed = signed or []
    return bool(open_ and len(signed) < len(SLOTS) and SLOTS[len(signed)] in v.roles)


@safe
def signatures(plane, v: view.Viewer, now: datetime) -> list[dict]:
    out = []
    for p in _files(plane.path("intents", "m1_intent", "charters")):
        doc, sid = _json(p) or {}, p.stem
        last = (doc.get("versions") or [{}])[-1]
        prep = (_json(plane.path("intents", "m1_intent", "sessions", f"{sid}.json")) or {}).get("preparation") or {}
        if last.get("status") == "awaiting_approver" and v.account_id and prep.get("approver_account_id") == v.account_id:
            out.append(line(f"sign:charter:{sid}", "signature", "A charter waits for your signature", prep.get("approver_name") or "",
                            f"/centre/intent/charter/{sid}", "Review and sign", f"charters/{sid}", last.get("created_at")))
    for b in _dirs(plane.path("intents", "m2_baseline")):  # a version the first signer has signed waits for the next slot
        last = ((_json(b / "signoff.json") or {}).get("versions") or [{}])[-1]
        if _all_confirmed(plane, b.name) and _next_slot_mine(last.get("countersign"), last.get("status") == "open", v):
            out.append(line(f"sign:baseline:{b.name}", "signature", "The baseline waits for your signature", "", f"/centre/intent/baseline/{b.name}",
                            "Review and sign", f"m2_baseline/{b.name}/signoff", (last.get("countersign") or [{}])[-1].get("at") or last.get("created_at")))
    for a in _dirs(plane.path("intents", "m3_connect", "assessments")):
        plan = _json(a / "plan.json") or {}
        if plan and _next_slot_mine(plan.get("signatures"), not plan.get("signed_at"), v):
            out.append(line(f"sign:plan:{a.name}", "signature", "The build plan waits for your signature", "", f"/centre/intent/truth/{a.name}",
                            "Review and sign", f"m3_connect/{a.name}/plan", (plan.get("signatures") or [{}])[-1].get("at")))
    return out


def owned_nodes(plane, v: view.Viewer) -> dict[str, dict]:
    """Graph nodes the viewer owns (an owned_by edge to a Person node carrying their name): id -> node."""
    g = _json(plane.path("graph", "company.json"), {}) or {}
    nodes = {n["id"]: n for n in g.get("nodes", [])}
    return {e["from"]: nodes[e["from"]] for e in g.get("edges", [])
            if e.get("type") == "owned_by" and e["from"] in nodes and e["to"] in nodes and _name(v, nodes[e["to"]].get("label"))}


@safe
def gaps(plane, v: view.Viewer, now: datetime) -> list[dict]:
    mine = owned_nodes(plane, v)
    keys = {k.split(":", 1)[-1].lower() for k in mine} | {str(n.get("label")).lower() for n in mine.values()}
    out = []
    for m in (_json(plane.path("build", "prove.json"), {}) or {}).get("measures", []):
        open_ = [x for x in m.get("periods", []) if x.get("result") == "gap" and not x.get("accepted_by")]
        if open_ and str(m.get("code")).lower() in keys:
            out.append(line(f"gap:{m['code']}", "decision", f"{m['code']} does not match the reported figure",
                            f"{len(open_)} period(s) differ.", "/centre/build/prove", "Explain or accept", f"build/prove/{m['code']}", None))
    return out


@safe
def release(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The sponsor signs the release (POST /api/company/build/release/sign); the line lasts while build/prove.json says it is a draft."""
    p = _json(plane.path("build", "prove.json"), {}) or {}
    ms = [m for m in p.get("measures") or [] if isinstance(m, dict)]
    if "sponsor" not in v.roles or not ms or (p.get("release") or {}).get("state") != "draft":
        return []
    ready = sum(1 for m in ms if m.get("release_ready"))
    return [line("sign:release", "signature", "The release waits for your signature", f"{ready} of {len(ms)} measures are ready to release.",
                 "/centre/build/prove", "Review and release", "build/prove", None)]


@safe
def blueprint(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """A draft blueprint from a signed baseline waits for the company admin, the one signer of POST /api/company/build/blueprint/sign."""
    b = _json(plane.path("build", "blueprint.json"), {}) or {}
    if b.get("state") != "draft" or b.get("basis") == "draft baseline" or "company_admin" not in v.roles:
        return []
    m = b.get("model") or {}
    detail = (f"{len(m.get('facts') or [])} facts, {len(m.get('dimensions') or [])} dimensions, {len(b.get('lineage') or [])} measures traced to source, "
              f"{len(b.get('rules') or [])} rules. Sign, or change a field first.")
    return [line("sign:blueprint", "signature", "The blueprint waits for your signature", detail, "/centre/build/blueprint", "Review blueprint",
                 "build/blueprint", None)]


@safe
def purpose_asks(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """A drafted wall whose sponsor (its approver) has not given the purpose line yet."""
    return [line(f"purpose:{s['id']}", "decision", f"{_topic(s)}: one sentence on what the wall is for",
                 "The organiser has the session drafted and waits only for your purpose line.", "/centre/intent", "Write it",
                 f"sessions/{s['id']}", s.get("updated_at"))
            for s in sessions(plane) if s.get("state") == "draft" and _mine(s, v, "approver_account_id")
            and not str((s.get("preparation") or {}).get("purpose") or "").strip()]


@safe
def suggestions(plane, v: view.Viewer, now: datetime) -> list[dict]:
    mine, out = owned_nodes(plane, v), []
    for nid, items in (_json(plane.path("graph", "comments.json"), {}) or {}).items():
        for c in items if nid in mine else []:
            if c.get("state") == "open" and c.get("kind") in ("suggestion", "ambiguity"):
                out.append(line(f"suggest:{c['id']}", "decision", f"{'An' if c['kind'] == 'ambiguity' else 'A'} {c['kind']} on {mine[nid].get('label')}", str(c.get("text", ""))[:140],
                                f"/centre/intent/map/{nid}", "Decide", f"graph/comments/{nid}", c.get("at")))
    return out


# ---- Give
@safe
def requests(plane, v: view.Viewer, now: datetime) -> list[dict]:
    out = []
    for a in _dirs(plane.path("intents", "m3_connect", "assessments")):
        for r in _json(a / "requests.json", []) or []:
            if _name(v, r.get("owner")) and r.get("state") not in ("arrived", "will_not_send") and not r.get("revoked_at"):
                out.append(line(f"data:{r['id']}", "request", f"Data for {r.get('source_name') or 'a source'}", "A file is requested from you.",
                                f"/centre/intent/truth/{a.name}", "Send the file", f"m3_connect/{a.name}/requests/{r['id']}", r.get("sent_at"), r.get("expires_at")))
    for b in _dirs(plane.path("intents", "m2_baseline")):
        for r in _json(b / "requests.json", []) or []:
            if _name(v, r.get("owner_name")) and r.get("state") in OPEN_M2_REQUEST:
                out.append(line(f"ask:{r['id']}", "request", "Questions about your measures", f"{len(r.get('kpi_ids') or [])} measure(s).",
                                f"/centre/intent/baseline/{b.name}", "Answer", f"m2_baseline/{b.name}/requests/{r['id']}", r.get("sent_at"), r.get("expires_at")))
    return out


def _latest_runs(plane) -> list[dict]:
    """The latest run per source, for the sources that have a pipeline card (the same set Pipelines and Ops show)."""
    folder = plane.path("build", "pipelines")
    cards = {f.stem for f in folder.glob("*.json") if not f.name.endswith(".commits.json")} if folder.is_dir() else set()
    latest: dict = {}
    for r in (_json(plane.path("warehouse", "runs.json"), {}) or {}).get("runs", []):  # newest last
        if cards and r.get("source") not in cards:
            continue
        latest[r.get("source")] = r
    return list(latest.values())


@safe
def late_files(plane, v: view.Viewer, now: datetime) -> list[dict]:
    return [line(f"late:{r['id']}", "request", f"{_plain(r['source'])} is {r['status']}", "The latest file did not arrive on time.", "/centre/build/ops",
                 "See the run", f"warehouse/runs/{r['id']}", r.get("started")) for r in _latest_runs(plane)
            if r.get("status") in ("late", "failed") and _name(v, r.get("owner"))]


# ---- Watch
@safe
def range_breaks(plane, v: view.Viewer, now: datetime) -> list[dict]:
    n = sum(1 for x in owned_nodes(plane, v).values() if x.get("type") == "Measure" and x.get("range_break") is True)  # counts only, never the figure
    return [line("watch:range", "measure", f"{n} of your measures are outside their usual range", "", "/centre/consume/feeds", "Look",
                 "graph/company", None)] if n else []


@safe
def brief(plane, v: view.Viewer, briefs: Path | None, now: datetime) -> list[dict]:
    files = sorted(briefs.glob("*.md")) if briefs else []
    if not files or not v.roles - {"participant"}:  # a participant has no Consume centre: the link would be a dead end
        return []
    title = next((t[2:].strip() for t in files[0].read_text(encoding="utf-8").splitlines() if t.startswith("# ")), files[0].stem)
    title = title.replace(" -- ", ": ").replace(" — ", ": ")  # no dashes in copy
    return [line(f"brief:{files[0].stem}", "brief", title, "Outside material from your industry pack.", "/centre/consume/market", "Read",
                 f"market_briefs/{files[0].name}", None)]


@safe
def ops(plane, v: view.Viewer, now: datetime) -> list[dict]:
    bad = [r for r in _latest_runs(plane) if r.get("status") in ("late", "failed")]
    return [line("watch:ops", "ops", f"{len(bad)} {'source' if len(bad) == 1 else 'sources'} late or failed", "", "/centre/build/ops", "Open Ops", "warehouse/runs", None)] \
        if bad and DATA_TEAM & v.roles else []


# ---- the organiser
def _drafts(plane, v: view.Viewer) -> list[dict]:
    """Nira's drafted messages this person may send (the rule of messages.py _may)."""
    return [m for m in (_json(plane.path("pulse", "messages.json"), {}) or {}).get("messages", [])
            if isinstance(m, dict) and m.get("state") == "draft"
            and ("company_admin" in v.roles or (v.account_id and m.get("organiser_account_id") == v.account_id))]


def _ask_detail(m: dict) -> str:
    """The sponsor's own words from the draft (what the note quotes), so two notes never read the same."""
    said = re.search(r'"([^"]{3,})"', str(m.get("body") or ""))
    return (f"“{said.group(1)[:140]}” Nira drafted the note. Read it, then start the session or reply." if said
            else "Nira drafted the note from the sponsor's ask. Read it, then start the session or reply.")


@safe
def starts(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """A sponsor's ask for a wall (a sponsor_ask draft) waits for the organiser."""
    return [line(f"start:{m['id']}", "decision", str(m.get("subject") or "A request for a wall"),
                 _ask_detail(m), "/centre/intent", "Review draft",
                 f"pulse/messages/{m['id']}", m.get("drafted_at")) for m in _drafts(plane, v) if m.get("kind") == "sponsor_ask"]


@safe
def running(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The organiser's open walls with how many seated people have not written a card (a count, never who), and closed walls with no charter."""
    out = []
    for s in sessions(plane):
        sid = s["id"]
        if not _mine(s, v):
            continue
        if s.get("state") in OPEN_WALL:
            seats = [x for x in (_json(plane.path("intents", "m1_intent", "rooms", f"{sid}.json")) or {}).get("seats") or [] if x.get("state") == "taken"]
            authors = (_json(plane.path("intents", "m1_intent", "note_authors", f"{sid}.json")) or {}).get("authors") or {}
            missing = max(0, len(seats) - len(set(authors.values())))  # a count of distinct seats only; no seat or name leaves this function
            topic = _topic(s).replace(":", ",")  # one colon only, before the count
            title = (f"{topic}: {missing} of {len(seats)} have not written a card" if missing
                     else f"{topic}: everyone seated has written" if seats else f"{topic}: no one has taken a seat yet")
            out.append(line(f"running:{sid}", "invite", title, "Send a reminder, extend the wall, or move it to the next stage.",
                            f"/centre/intent/wall/{sid}", "Open the wall", f"sessions/{sid}", s.get("updated_at"), _closes(plane, s)))
        elif s.get("state") == "closed" and not _charter(plane, sid):
            to = (s.get("preparation") or {}).get("approver_name") or "the sponsor"
            out.append(line(f"define:{sid}", "decision", f"{_topic(s)} closed with no charter yet",
                            f"Open Define, put the clusters on shelves, hand the charter to {to}.", f"/centre/intent/define/{sid}", "Open Define",
                            f"sessions/{sid}", s.get("updated_at")))
    return out


def _silent(plane, now: datetime) -> list[tuple[str, list[str]]]:
    """Per baseline, the owners asked more than three days ago who have not answered."""
    out = []
    for b in _dirs(plane.path("intents", "m2_baseline")):
        names = sorted({str(r.get("owner_name")) for r in _json(b / "requests.json", []) or []
                        if r.get("state") in OPEN_M2_REQUEST and (_time(r.get("sent_at")) or now) < now - SILENT})
        if names:
            out.append((b.name, names))
    return out


@safe
def waiting(plane, v: view.Viewer, now: datetime) -> list[dict]:
    if "company_admin" not in v.roles:
        return []
    return [line(f"silent:{bid}", "request", f"{len(names)} baseline measure owner(s) have not answered for more than three days",
                 f"Asked: {', '.join(names)}.", f"/centre/intent/baseline/{bid}", "See them", f"m2_baseline/{bid}/requests", None)
            for bid, names in _silent(plane, now)]


def stat(label: str, value, note: str | None = None) -> dict:
    """A counter for a strip. No record behind it: value None and the note says so."""
    return {"label": label, "value": None if value is None else str(value), "note": "Not available yet" if value is None and note is None else note}


def _in_quarter(t: datetime | None, now: datetime) -> bool:
    return t is not None and t.year == now.year and (t.month - 1) // 3 == (now.month - 1) // 3


def _governed(plane) -> tuple[int, int]:
    """Measures whose every governed field is stated, of all the measures in the baselines."""
    done = total = 0
    for b in _dirs(plane.path("intents", "m2_baseline")):
        for entry in (_json(b / "governed_state.json", {}) or {}).values():
            total += 1
            done += isinstance(entry, dict) and all(isinstance(c, dict) and c.get("mark") == "stated" for c in entry.values())
    return done, total


def quarter(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The organiser's counters. No record keeps the time spent, so that one says Not available yet."""
    try:
        mine = [s for s in sessions(plane) if _mine(s, v) and s.get("state") != "draft"]  # all of the organiser's walls: a charter signed in spring still counts
        signed = sum(1 for s in mine if _charter(plane, s["id"]).get("status") == "signed")
        done, total = _governed(plane)
        return [stat("Walls run", len(mine)), stat("Charters signed", signed), stat("Measures governed", f"{done} of {total}" if total else None),
                stat("Your time so far", None)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        log.warning("pulse: quarter skipped (%s)", type(e).__name__)
        return []


def drafts(plane, v: view.Viewer) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in _drafts(plane, v):
        out[str(m.get("kind"))] = out.get(str(m.get("kind")), 0) + 1
    return out


# ---- the data team
def _prove(plane) -> dict:
    return _json(plane.path("build", "prove.json"), {}) or {}


@safe
def critical(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """Every measure whose own figure differs from the reported one and is not accepted, for the data team."""
    if not DATA_TEAM & v.roles:
        return []
    out = []
    for m in _prove(plane).get("measures", []):
        open_ = [x for x in m.get("periods", []) if x.get("result") == "gap" and not x.get("accepted_by")]
        if open_:
            out.append(line(f"gap:{m['code']}", "ops", f"Critical: {m['code']} does not match the reported figure",
                            f"{len(open_)} period(s) differ. Accept the gap with a reason, or ask the owner.", "/centre/build/prove", "Open in Prove",
                            f"build/prove/{m['code']}", None))
    return out


@safe
def late_runs(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """Every source whose latest run is late or failed, for the data team (late_files is the owner's own)."""
    if not DATA_TEAM & v.roles:
        return []
    out = []
    for r in _latest_runs(plane):
        if r.get("status") not in ("late", "failed"):
            continue
        expected = (_json(plane.path("build", "pipelines", f"{r['source']}.json")) or {}).get("expected")
        detail = (f"Expected {expected[:1].lower() + expected[1:] if expected.startswith('As ') else expected}; not arrived." if expected else "The file has not arrived.") if r["status"] == "late" else "The latest run failed."
        out.append(line(f"late:{r['id']}", "ops", f"{_plain(r['source'])} file {r['status']}", detail, "/centre/build/ops", "Open in Ops",
                        f"warehouse/runs/{r['id']}", r.get("started")))
    return out


def _released(plane) -> tuple[int, int, int] | None:
    """(measures released, measures on the trial, measures ready to release) from build/prove.json; None when there is no trial."""
    p = _prove(plane)
    ms = [m for m in p.get("measures") or [] if isinstance(m, dict)]
    if not ms:
        return None
    rel = p.get("release") or {}
    ready = sum(1 for m in ms if m.get("release_ready"))
    released = len(rel.get("released") or []) if rel.get("state") == "signed" and isinstance(rel.get("released"), list) else (ready if rel.get("state") == "signed" else 0)
    return released, len(ms), ready


def ops_report(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The four counts of the ops report, from the latest run of each source and the release."""
    try:
        runs = _latest_runs(plane)
        failed = sum(1 for r in runs for x in r.get("rules") or [] if isinstance(x, dict) and x.get("passed") is False)
        rel = _released(plane)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        log.warning("pulse: ops_report skipped (%s)", type(e).__name__)
        return []
    return [stat("Loads on time", f"{sum(1 for r in runs if r.get('status') == 'ok')} of {len(runs)}" if runs else None),
            stat("Late", sum(1 for r in runs if r.get("status") == "late") if runs else None),
            stat("Checks failed", failed if runs else None), stat("Measures released", rel[0] if rel else None)]


# ---- the sponsor
def watch_stats(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """No record keeps people's time, so that one says Not available yet."""
    try:
        rel = _released(plane)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        rel = None
    note = None if not rel else (f"{rel[1] - rel[0]} held back" if rel[0] else f"{rel[2]} ready to release" if rel[2] else "all wait on the trial")
    return [stat("Measures released", f"{rel[0]} of {rel[1]}" if rel else None, note),
            stat("People's time this quarter", None)]


def _by_outcome(folder: Path, key: str, name: str) -> dict[str, str]:
    """outcome id -> the folder name of the record (a baseline or an assessment) made from that charter."""
    out = {}
    for d in _dirs(folder):
        doc = _json(d / name) or {}
        if isinstance(doc, dict) and doc.get(key):
            out[doc[key]] = d.name
    return out


def _initiative(plane, s: dict, base: dict, tests: dict, silent: dict, now: datetime) -> dict:
    sid, state, ch = s["id"], s.get("state"), _charter(plane, s["id"]).get("status")
    row = {"name": _topic(s), "where": "", "hurdle": None, "who": "The organiser", "href": f"/centre/intent/wall/{sid}"}
    if state == "draft":
        gap = not str((s.get("preparation") or {}).get("purpose") or "").strip()
        row.update(where="Waiting to start", hurdle="Your purpose line" if gap else None, who="You" if gap else "The organiser", href="/centre/intent")
    elif state in OPEN_WALL:
        row.update(where="The wall is open")
    elif ch == "awaiting_approver":
        row.update(where="Define: charter ready to sign", who="You", href=f"/centre/intent/charter/{sid}")
    elif ch != "signed":
        row.update(where="Define: charter being drafted", href=f"/centre/intent/define/{sid}")
    elif s.get("outcome_id") in tests:
        aid = tests[s["outcome_id"]]
        late = [r for r in _json(plane.path("intents", "m3_connect", "assessments", aid, "requests.json"), []) or []
                if r.get("state") not in ("arrived", "will_not_send") and not r.get("revoked_at") and (_time(r.get("expires_at")) or now) < now]
        row.update(where="Moment of truth", href=f"/centre/intent/truth/{aid}", hurdle=f"{late[0].get('source_name') or 'A source'} file not sent in time" if late else None,
                   who=str(late[0].get("owner") or "The owner") if late else "The data team")
    elif s.get("outcome_id") in base:
        bid = base[s["outcome_id"]]
        names = silent.get(bid) or []
        signed = (_json(plane.path("intents", "m2_baseline", bid, "baseline.json")) or {}).get("state") == "signed"
        row.update(where="Baseline signed" if signed else "Baseline: owners confirm the measures", href=f"/centre/intent/baseline/{bid}",
                   hurdle="Owners have not answered" if names else None, who=", ".join(names) if names else "The organiser")
    else:
        row.update(where="Charter signed", href=f"/centre/intent/charter/{sid}")
    return row


def initiatives(plane, v: view.Viewer, now: datetime) -> list[dict]:
    """The sponsor's walls (they are the approver): where each is, the hurdle the records show, and who clears it."""
    try:
        base = _by_outcome(plane.path("intents", "m2_baseline"), "charter_outcome_id", "baseline.json")
        tests = _by_outcome(plane.path("intents", "m3_connect", "assessments"), "charter_outcome_id", "assessment.json")
        silent = dict(_silent(plane, now))
        return [_initiative(plane, s, base, tests, silent, now) for s in sessions(plane) if _mine(s, v, "approver_account_id")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        log.warning("pulse: initiatives skipped (%s)", type(e).__name__)
        return []


# ---- map
def new_nodes(plane, v: view.Viewer, now: datetime) -> dict:
    try:
        versions = _json(plane.path("graph", "versions.json"), {}) or {}
        labels = {n["id"]: n.get("label") for n in graph_for(plane, v)["nodes"] if n.get("type") not in QUIET and not n.get("restricted") and n.get("label") not in ("A card", "Sealed card") and len(n.get("label") or "") < 80}  # the viewer's own graph: a restricted name never shows  # people are not "new on the map"
        since, mine = now - WEEK, owned_nodes(plane, v)
        new, changed, owned_new = [], 0, 0
        for nid, vs in versions.items():
            vs = [x for x in vs if isinstance(x, dict)]
            if nid in labels and any(x.get("v") == 1 and (_time(x.get("at")) or since) > since for x in vs):
                new.append(str(labels[nid]))
                owned_new += nid in mine
            if nid in mine:
                changed += sum(1 for x in vs if (_time(x.get("at")) or since) > since)
        return {"new_this_week": sorted(new), "owned_changes": changed, "owned_new": owned_new}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"new_this_week": [], "owned_changes": 0, "owned_new": 0}
