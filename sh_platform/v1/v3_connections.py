"""W1 + W8 (docs/v3/PROGRAM-GAPS.md): the Connections page (what each connector is doing) and the Onboarding checklist (ten steps, a health score).
Connectors register themselves in connectors.base.REGISTRY; this module only lists them, runs them and remembers the last run. Onboarding steps are
computed from what exists in the office; the steps only a person can do are ticked by a person, with name and time kept."""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

from sh_platform.v1 import v3_harbor as H
from sh_platform.v1.connectors import base

log = logging.getLogger(__name__)
# The other builders' connector modules; each registers itself on import. A module that is not merged yet is skipped.
MODULES = ("files", "plaid", "saxo", "gocardless", "banksg")  # each registers its connectors in base.REGISTRY on import


def load_connectors() -> None:
    for m in MODULES:
        try:
            importlib.import_module(f"sh_platform.v1.connectors.{m}")
        except ImportError:
            pass
        except Exception:  # noqa: BLE001 - one broken connector never hides the rest
            log.warning("connector %s failed to load", m, exc_info=True)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(plane, name: str) -> dict:
    p = plane.path("v3", name)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def _write(plane, name: str, data: dict) -> None:
    p = plane.path("v3", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


# ---- connections ----------------------------------------------------------------------------------------------------------------------

def _missing(c) -> list[str]:
    return [n for n in c.env if not os.environ.get(n)]


def listing(plane) -> list[dict]:
    load_connectors()
    runs = _read(plane, "connections.json")
    out = []
    for cid, c in sorted(base.REGISTRY.items()):
        last, miss = runs.get(cid) or {}, _missing(c)
        state = "needs_settings" if miss else "error" if last.get("error") else "connected"
        out.append({"id": cid, "label": c.label, "kind": c.kind, "missing": miss, "state": state, "last_run": last.get("at"),
                    "files": last.get("files", 0), "errors": [last["error"]] if last.get("error") else [], "message": last.get("message", "")})
    return out


def run(plane, cid: str, since: date | None = None) -> dict:
    load_connectors()
    c = base.REGISTRY.get(cid)
    if c is None:
        raise KeyError(cid)
    rec = {"at": _now()}
    try:
        st = base.run(plane, c, since or date.today() - timedelta(days=30))
        rec.update(files=st.files, message=st.message, error=None if st.ok or st.missing else st.message)
    except Exception as e:  # noqa: BLE001 - a provider failing is a message on the card, never a crash
        log.warning("connector %s failed", cid, exc_info=True)
        rec.update(files=0, message="", error=f"The run failed: {type(e).__name__}: {e}"[:300])
    runs = _read(plane, "connections.json")
    runs[cid] = rec
    _write(plane, "connections.json", runs)
    return next(x for x in listing(plane) if x["id"] == cid)


# ---- onboarding -----------------------------------------------------------------------------------------------------------------------

HISTORY_MONTHS = 6  # W8: the readers back-fill six months

# id, step, owner, what Harbor does ("" when only a person can), manual (a person ticks it)
STEPS = [
    ("discovery", "Discovery: entities, accounts, funds, ownership chart, reports wanted", "Office admin with Harbor", "North drafts the brief from a conversation", False),
    ("letters", "Authorisation letters to each bank and custodian", "Office admin", "Harbor lists the feeds that need a letter; the office signs and sends them", True),
    ("history", "Historical load: past statements and transactions", "Harbor", "The readers load every file dropped, months back", False),
    ("opening", "Opening balance reconciliation", "Harbor, checked by the data team", "The cash recon runs against the administrator's figures", False),
    ("ownership", "Ownership structure built", "Harbor with the data team", "Span builds the ownership table from the documents", False),
    ("reports", "Report and dashboard set-up", "Harbor", "Lumen builds the boards once a use case is live", False),
    ("testing", "User testing with the office", "Office team", "", True),
    ("training", "Training", "Office admin", "", True),
    ("golive", "Go-live", "Office admin", "", True),
    ("hypercare", "Hypercare: daily check-ins for a few weeks", "Data team", "Harbor posts the daily exceptions; the team checks in", True),
]


def _months(plane) -> list[str]:
    d = plane.path("dropbox")
    out = set()
    for p in d.iterdir() if d.is_dir() else []:
        if p.is_file():
            m = re.search(r"(20\d{2})[-_]?(0[1-9]|1[0-2])", p.name)
            out.add(f"{m[1]}-{m[2]}" if m else datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m"))
    return sorted(out)


def _ownership_rows(plane) -> int | None:
    """Rows in entity_ownership; None when the table is not there yet."""
    try:
        from sh_platform.v1 import wh
        with wh.connect(plane, read_only=True) as con:
            return int(con.execute("select count(*) from entity_ownership").fetchone()[0])
    except Exception:  # noqa: BLE001 - no table, no warehouse, or busy: not built yet
        return None


def _recon(plane) -> dict | None:
    try:
        from sh_platform.v1 import e3_recon
        return next((r for r in e3_recon.last_runs(plane, 50) if r.get("recon_code") == "cash_by_entity"), None)
    except Exception:  # noqa: BLE001
        return None


def onboarding(plane) -> dict:
    ticks = _read(plane, "onboarding.json")
    conns = listing(plane)
    live_feeds = [c for c in conns if c["state"] == "connected" and c["last_run"]]
    months = _months(plane)
    own = _ownership_rows(plane)
    rec = _recon(plane)
    queue = sum(1 for f in H.read_files(plane) if f.get("status") == "question")
    threads = [t for t in H.all_threads(plane) if t.get("stage") != "discarded"]
    live = [t for t in threads if t.get("stage") == "live"]
    auto = {
        "discovery": ("done" if threads else "waiting", f"{len(threads)} use case(s) started" if threads else "No use case started yet"),
        "history": (("done" if len(months) >= HISTORY_MONTHS else "doing") if months else "waiting",
                    f"{len(months)} month(s) of files loaded ({months[0]} to {months[-1]})" if months else "No files dropped yet"),
        "opening": (("waiting", "The cash recon has not run yet") if not rec else
                    ("done", f"Cash recon of {rec.get('as_of_date')}: all {rec.get('checked')} matched") if not rec.get("breaks") else
                    ("attention", f"Cash recon of {rec.get('as_of_date')}: {len(rec['breaks'])} difference(s) to look at")),
        "ownership": ("waiting", "The ownership table is not built yet") if own is None else
                     (("done", f"{own} ownership row(s)") if own else ("waiting", "The ownership table is empty")),
        "reports": ("done" if live else "waiting", f"{len(live)} use case(s) live" if live else "No use case is live yet"),
    }
    steps = []
    for sid, text, owner, harbor, manual in STEPS:
        s = {"id": sid, "step": text, "owner": owner, "harbor": harbor, "manual": manual, "status": "waiting", "detail": "", "ticked_by": None, "ticked_at": None}
        if sid in auto:
            s["status"], s["detail"] = auto[sid]
        if sid == "letters":
            s["detail"] = f"{len(live_feeds)} of {len(conns)} feed(s) connected" if conns else "No feed registered yet"
        t = ticks.get(sid)
        if t:
            s.update(status="done", ticked_by=t["by"], ticked_at=t["at"], detail=t.get("note") or s["detail"] or "Ticked by a person")
        steps.append(s)
    by = {s["id"]: s for s in steps}
    parts = [("Feeds connected", 25, len(live_feeds) / len(conns) if conns else 0, f"{len(live_feeds)} of {len(conns)}"),
             ("History loaded", 25, min(len(months) / HISTORY_MONTHS, 1), f"{len(months)} of {HISTORY_MONTHS} months"),
             ("Opening balances reconciled", 25, 1.0 if by["opening"]["status"] == "done" else 0, by["opening"]["detail"]),
             ("Review queue empty", 15, max(0, 1 - queue / 10), f"{queue} waiting"),
             ("Ownership set", 10, 1.0 if by["ownership"]["status"] == "done" else 0, by["ownership"]["detail"])]
    return {"score": round(sum(w * f for _, w, f, _ in parts)),
            "parts": [{"label": n, "weight": w, "points": round(w * f), "detail": d} for n, w, f, d in parts], "steps": steps}


def tick(plane, sid: str, by: str, done: bool = True, note: str = "") -> dict:
    s = next((x for x in STEPS if x[0] == sid), None)
    if s is None:
        raise KeyError(sid)
    if not s[4]:
        raise ValueError("Harbor works this step out itself; there is nothing to tick.")
    ticks = _read(plane, "onboarding.json")
    if done:
        ticks[sid] = {"by": by, "at": _now(), "note": note[:300]}
    else:
        ticks.pop(sid, None)
    _write(plane, "onboarding.json", ticks)
    return onboarding(plane)
