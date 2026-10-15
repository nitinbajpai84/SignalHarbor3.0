"""X2 Home: what waits for the signed-in person, per seat, read from the 1.0 records (docs/plan/V1-BUILD.md, "Records").

Reads per intent: intents/<iid>/thread.json, sow.json, room_state.json; build/scan/<iid>.json, build/mapping/<iid>.json; and the
company-wide build/ops/loaded.json. Every file may be absent or damaged: it then counts as not there yet. Nothing is written."""
from __future__ import annotations

import logging

from sh_platform.build.home import _day
from sh_platform.jsonfile import read_json_strict
from sh_platform.v1.seats import ARCHITECT, CONSUMER, DATA_ENGINEER, DECISION_MAKER, OPS_MANAGER, seat_of

log = logging.getLogger(__name__)
NEEDS = ("goal", "process", "inputs", "kpis", "rules", "unclear")
SEAT_NAMES = {DECISION_MAKER: "Decision maker", ARCHITECT: "Architect", DATA_ENGINEER: "Data engineer",
              OPS_MANAGER: "Ops manager", CONSUMER: "Consumer"}


def _read(path) -> dict:
    try:
        data = read_json_strict(path, dict)
    except (OSError, ValueError) as e:
        log.warning("%s unreadable: %s", path, type(e).__name__)
        return {}
    return data or {}


def _list(rec: dict, key: str) -> list[dict]:
    v = rec.get(key)
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _title(iid: str, thread: dict, sow: dict) -> str:
    if sow.get("title"):
        return str(sow["title"])
    first = next((t.get("text") for t in _list(thread, "turns") if t.get("by") == "person" and t.get("text")), None)
    return str(first)[:80] if first else iid


def _intent(plane, iid: str, seats: set[str], loaded: list[dict]) -> tuple[dict, list[dict]]:
    """The intent's line and what in it waits for these seats."""
    thread = _read(plane.path("intents", iid, "thread.json"))
    sow = _read(plane.path("intents", iid, "sow.json"))
    scan = _read(plane.path("build", "scan", f"{iid}.json"))
    mapping = _read(plane.path("build", "mapping", f"{iid}.json"))
    nira = _read(plane.path("intents", iid, "room_state.json"))
    title = _title(iid, thread, sow)
    signed = sow.get("state") == "signed"
    rows = _list(mapping, "rows")
    sources = [s for s in _list(sow, "sources") if s.get("id")]
    src_ids = {s["id"] for s in sources}
    mine = [p for p in loaded if p.get("source_id") in src_ids]
    out: list[dict] = []

    def wait(seat: str, kind: str, text: str, action: str, href: str, since=None) -> None:
        if seat in seats:
            out.append({"id": f"{iid}:{kind}", "intent_id": iid, "intent": title, "seat": seat, "seat_name": SEAT_NAMES[seat],
                        "kind": kind, "text": text, "action": action, "href": href, "since": _day(since) if since else None})

    turns = _list(thread, "turns")
    last_at = turns[-1].get("at") if turns else None
    if thread and not signed:
        if thread.get("state") == "sow_ready":
            open_points = sum(1 for u in _list(sow, "unclear") if not u.get("settled"))
            extra = f"; {_plural(open_points, 'unclear point')} to settle first" if open_points else ""
            wait(DECISION_MAKER, "sign", f"The intent of work is ready: read and sign{extra}.", "Read and sign",
                 f"/centre/intent/{iid}/sow", last_at)
        else:
            done = set(thread.get("needs_done") or []) & set(NEEDS)
            wait(DECISION_MAKER, "thread", f"North is waiting on you: {len(done)} of {len(NEEDS)} needs met.", "Answer North",
                 f"/centre/intent/{iid}", last_at)
    if signed and not scan:
        wait(ARCHITECT, "design", "The intent of work is signed: review Span's design and scan the sources.", "Review the design",
             f"/centre/build/{iid}", (sow.get("signature") or {}).get("at") if isinstance(sow.get("signature"), dict) else None)
    if scan and not scan.get("agreed"):
        k = _list(scan, "kpis")
        ready = sum(1 for x in k if x.get("status") == "available")
        wait(DECISION_MAKER, "scope", f"Agree the scope: {ready} of {len(k)} KPIs can be built now.", "Agree the scope",
             f"/centre/build/{iid}", scan.get("at"))
    if scan.get("agreed") and not mapping:
        wait(ARCHITECT, "mapping", "The scope is agreed: write the mapping sheet.", "Open the mapping sheet",
             f"/centre/build/{iid}", (scan.get("agreed") or {}).get("at") if isinstance(scan.get("agreed"), dict) else None)
    unclear_rows = sum(1 for r in rows if r.get("status") == "unclear")
    if unclear_rows:
        wait(ARCHITECT, "mapping", f"{_plural(unclear_rows, 'mapping line')} still unclear.", "Correct the lines",
             f"/centre/build/{iid}")
    if rows and not mine:
        wait(DATA_ENGINEER, "load", "The mapping sheet is written: run the loads.", "Run the loads", f"/centre/build/{iid}/engineer")
    if rows:
        done = {p.get("source_id") for p in mine if p.get("state") == "loaded"}
        todo = [s.get("name") or s["id"] for s in sources if s["id"] not in done]
        if todo:
            wait(OPS_MANAGER, "loaded", f"Confirm Loaded or Not loaded for {', '.join(todo[:3])}{' and more' if len(todo) > 3 else ''}.",
                 "Confirm the period", "/centre/build/ops")
    if any(p.get("state") == "loaded" for p in mine):
        wait(CONSUMER, "consume", "KPIs are loaded: read them, and the offers that would add more.", "Open Consume", "/centre/consume")

    stage = ("Loaded" if any(p.get("state") == "loaded" for p in mine) else "Mapping sheet" if rows else "Scope agreed" if scan.get("agreed")
             else "Scan" if scan else "Signed" if signed else "Intent of work" if sow else "Talking to North")
    waiting = f"Nira: waiting on {nira['waiting_on']}" + (f" since {_day(nira['since'])}" if nira.get("since") else "") \
        if nira.get("waiting_on") else None
    return {"id": iid, "title": title, "stage": stage, "nira": waiting,
            "open": f"/centre/intent/{iid}" if not signed else f"/centre/intent/{iid}/sow"}, out


def build(plane, viewer) -> dict:
    seats = seat_of(viewer)
    loaded = [p for p in _list(_read(plane.path("build", "ops", "loaded.json")), "periods")]
    root = plane.path("intents")
    iids = sorted({f.parent.name for pat in ("*/thread.json", "*/sow.json") for f in root.glob(pat)}) if root.is_dir() else []
    intents, waits = [], []
    for iid in iids:
        line, mine = _intent(plane, iid, seats, loaded)
        intents.append(line)
        waits += mine
    order = list(SEAT_NAMES)
    return {"name": viewer.name, "seats": [{"id": s, "name": SEAT_NAMES[s]} for s in order if s in seats],
            "may_start": True,  # anyone may start; the sign-off carries the weight
            "waiting": sorted(waits, key=lambda w: order.index(w["seat"])), "intents": intents}
