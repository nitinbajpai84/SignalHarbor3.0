"""Harbor 3.0 operations: people, runs, connections, setup (spec: docs/v3/HARBOR-SPEC.md, 14 Oct addendum).
Reads the 2.0 stores (accounts, run log, c5 connector specs, thread store) and keeps only autonomy and ask rules of its own in
`<company>/v3/settings.json`. Never returns a secret: connector specs hold variable NAMES, and none of them leave here."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.entitlements import EntitlementStore
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import router, run_log, v3_harbor as H
from sh_platform.v1.c5_connect import ops as C5ops, spec as C5spec

log = logging.getLogger(__name__)
LEVELS = ("assist", "auto", "silent")
# platform role -> what the person does in the office; the highest one a person holds wins
ROLE_KIND = {"sponsor": "decides", "owner": "decides", "approver": "decides", "head_of_data": "decides",
             "company_admin": "does", "analyst": "does", "participant": "reads"}
_RANK = {"decides": 0, "does": 1, "reads": 2}
DEFAULT_RULES = [
    {"id": "new_file_or_column", "text": "A file type it has never seen, or a column that appears or disappears", "on": True},
    {"id": "shared_table", "text": "A change to a shared table that another thread reads", "on": True},
    {"id": "tolerance", "text": "A match against the administrator or custodian outside tolerance (USD)", "on": True, "value": 5000},
    {"id": "untraceable", "text": "A figure it cannot trace to a row, so it will not say it", "on": True},
    {"id": "money", "text": "A money decision: paying, transferring, approving", "on": True},
]


# ---- settings -----------------------------------------------------------------------------------------------------------------

def _sfile(plane) -> Path:
    return plane.path("v3", "settings.json")


def settings(plane) -> dict:
    try:
        d = read_json_strict(_sfile(plane), dict)
    except (OSError, ValueError):
        log.warning("v3 settings unreadable; using defaults")
        d = None
    return d or {}


def _save(plane, d: dict) -> None:
    f = _sfile(plane)
    f.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(f, d)


# ---- people -------------------------------------------------------------------------------------------------------------------

def _kind(roles: list[str]) -> str:
    return min((ROLE_KIND.get(r, "reads") for r in roles), key=_RANK.get, default="reads")


def people(plane, accounts: list[dict]) -> dict:
    s = settings(plane)
    levels = s.get("autonomy") if isinstance(s.get("autonomy"), dict) else {}
    saved = {r.get("id"): r for r in s.get("ask_rules") or [] if isinstance(r, dict)}
    rules = [{**r, **{k: saved.get(r["id"], {})[k] for k in ("on", "value") if k in saved.get(r["id"], {})}} for r in DEFAULT_RULES]
    return {"people": sorted(({"name": a["display_name"], "role": _kind(a["roles"])} for a in accounts if not a.get("disabled")),
                             key=lambda p: (_RANK[p["role"]], p["name"])),
            "second_signer": bool(s.get("second_signer", False)),
            "autonomy": [{"thread": t["id"], "level": levels.get(t["id"]) if levels.get(t["id"]) in LEVELS else "assist"} for t in H.all_threads(plane)],
            "ask_rules": rules,
            "usage": {"questions": int(router.costs(plane).get("calls") or 0), "builds": len(run_log.list_runs(plane, limit=100000)),
                      "mode": router.mode_of(plane)["mode"]}}


def set_autonomy(plane, tid: str, level: str) -> None:
    """ValueError for a bad level, KeyError for an unknown thread."""
    if level not in LEVELS:
        raise ValueError("Choose assist, auto or silent.")
    H.load(plane, tid)
    with lock_for(_sfile(plane)):
        s = settings(plane)
        s["autonomy"] = {**(s.get("autonomy") or {}), tid: level}
        _save(plane, s)
    log.info("autonomy of %s set to %s", tid, level)


# ---- runs ---------------------------------------------------------------------------------------------------------------------

def runs(plane) -> dict:
    owner: dict[str, str] = {}
    for t in H.all_threads(plane):
        for rid in [t.get("run_id"), *(s.get("run_id") for s in t.get("steps") or [])]:
            if rid:
                owner.setdefault(rid, t["id"])
    steps = run_log._read(plane, "run_steps.jsonl")
    out = []
    for r in run_log.list_runs(plane, limit=100000):
        mine = [s for s in steps if s.get("run_id") == r["run_id"]]
        passed, failed = sum(s.get("checks_passed") or 0 for s in mine), sum(s.get("checks_failed") or 0 for s in mine)
        live = r.get("mode") == "production"
        out.append({"run_id": r["run_id"], "thread": owner.get(r["run_id"]), "kind": "live" if live else "copy", "started": r.get("started"),
                    "files": len({s.get(k) for s in mine for k in ("file_id", "batch_id") if s.get(k)}),
                    "checks_passed": passed, "checks_total": passed + failed,
                    "result": r.get("status") or "running", "signed_by": r.get("who") if live else None})
    return {"runs": out}


# ---- connections --------------------------------------------------------------------------------------------------------------

KIND_OUT = {"imap": "mailbox", "sftp": "sftp", "graph": "http", "api": "api"}  # graph (a shared drive over HTTPS) has no kind of its own in the spec


def _target(s: dict) -> str:
    p = s.get("params") or {}
    return "/".join(x for x in (s.get("host"), p.get("remote_path") or p.get("mailbox") or p.get("folder")) if x)


def connections(plane) -> dict:
    health = {h["id"]: h for h in C5ops.health(plane)}
    drop = plane.path("dropbox")
    newest = max((p.stat().st_mtime for p in drop.iterdir() if p.is_file()), default=None) if drop.is_dir() else None
    out = [{"id": "dropbox", "kind": "folder", "name": "Drop folder", "target": "dropbox/", "schedule": "every 30 seconds",
            "last_pull": datetime.fromtimestamp(newest, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if newest else None, "state": "ok"}]
    for cid, s in sorted(C5spec.all_specs(plane).items()):
        h = health.get(cid) or {}
        out.append({"id": cid, "kind": KIND_OUT.get(s.get("kind"), "http"), "name": cid, "target": _target(s), "schedule": s.get("schedule", "manual"),
                    "last_pull": h.get("last_ok") or h.get("last_run"), "state": "failing" if h.get("failed") or h.get("late") else "ok"})
    out += [{"id": f"{k}-coming", "kind": k, "name": n, "target": "", "schedule": "", "last_pull": None, "state": "coming"}
            for k, n in (("database", "Database"), ("api", "API"))]
    return {"connections": out}


# ---- setup --------------------------------------------------------------------------------------------------------------------

def _industry(app, company: str) -> str | None:
    c = EntitlementStore(app.state.settings.data_root).company(company) or {}
    return c.get("industry") if c.get("industry") in app.state.packs.industries() else None


def _pack(app, pid: str | None) -> dict | None:
    if not pid:
        return None
    pk = app.state.packs.load(pid)
    try:
        examples = (pk.section("intent_examples") or {}).get("examples") or []
    except KeyError:
        examples = []
    return {"id": pid, "label": pk.label, "intent_examples": list(examples)}


def setup(app, plane, company: str) -> dict:
    pid = _industry(app, company)
    ths = H.all_threads(plane)
    drop = plane.path("dropbox")
    files = [p for p in drop.iterdir() if p.is_file()] if drop.is_dir() else []
    n_acc = len([a for a in app.state.account_store.in_company(company) if not a.get("disabled")])
    n_conn = len(C5spec.all_specs(plane))
    live = [t for t in ths if t.get("stage") == "live"]
    steps = [("pack", "Pick your industry", bool(pid), pid and f"Industry pack: {_pack(app, pid)['label']}"),
             ("connection", "Connect a source", bool(n_conn or files), f"{n_conn} connection(s) and the drop folder" if n_conn or files else "Nothing connected yet"),
             ("files", "Files arrive", bool(files), f"{len(files)} file(s) in the drop folder" if files else "No files yet"),
             ("people", "Add your people", bool(n_acc), f"{n_acc} people" if n_acc else "No one yet"),
             ("thread", "Start a first thread", bool(ths), f"{len(ths)} thread(s)" if ths else "No thread yet"),
             ("live", "Take a thread live", bool(live), f"{len(live)} live" if live else "None live yet")]
    return {"steps": [{"id": i, "label": l, "done": d, "detail": det or ""} for i, l, d, det in steps], "pack": _pack(app, pid)}


def choose_pack(app, company: str, pack: str) -> None:
    """ValueError for an unknown pack, FileExistsError when the company already has one."""
    if pack not in app.state.packs.industries():
        raise ValueError("I do not know that industry pack.")
    if _industry(app, company):
        raise FileExistsError("Your office already has an industry pack. Ask your administrator if it must change.")
    es = EntitlementStore(app.state.settings.data_root)
    with es._lock:  # ponytail: EntitlementStore has no industry setter; this writes its own file under its own lock
        rows = es._load(es._companies_path, list)
        es._write(es._companies_path, [{**r, "industry": pack} if r.get("company_id") == company else r for r in rows])
    log.info("company %s chose pack %s", company, pack)
