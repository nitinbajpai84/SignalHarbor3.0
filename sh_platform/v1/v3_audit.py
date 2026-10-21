"""W7 audit log: an append-only, hash-chained JSONL per company (`ops/audit.jsonl`); sign-ins with no company go to `_control/audit.jsonl`.

Each line carries the hash of the line before it, so an edited or removed middle line breaks the chain and `verify` names where.
Limit (ponytail): cutting lines off the END leaves a valid chain; an auditor keeps the `head` hash from an export to catch that.
Logging never breaks a request: a failure to write is a warning, not an error.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.jsonfile import lock_for

log = logging.getLogger(__name__)
GENESIS = "0" * 64
_SEEN: dict[tuple, float] = {}  # (actor, path) -> last logged read; polling pages would otherwise flood the log
READ_COLLAPSE_SECONDS = 60
_DECISION = re.compile(r"/(sign|countersign|decide|decision|approve|charter|closure)(/|$)")
_EXPORT = re.compile(r"(export|download|\.csv$|\.xlsx$|\.docx$|\.pdf$)")
_QUIET = ("/api/auth/", "/api/health", "/api/v3/audit")


def _hash(prev: str, rec: dict) -> str:
    return hashlib.sha256((prev + json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str)).encode()).hexdigest()


def _last(f: Path) -> dict | None:
    if not f.exists() or f.stat().st_size == 0:
        return None
    with open(f, "rb") as h:
        h.seek(max(0, f.stat().st_size - 8192))
        lines = [x for x in h.read().splitlines() if x.strip()]
    try:
        return json.loads(lines[-1])
    except (ValueError, IndexError):
        return None


def append(f: Path, actor: str, action: str, detail: str = "", ok: bool = True, company: str | None = None) -> dict:
    with lock_for(f):
        f.parent.mkdir(parents=True, exist_ok=True)
        last = _last(f)
        body = {"seq": (last["seq"] + 1) if last else 1, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "actor": actor or "anonymous", "company": company, "action": action, "detail": detail[:300], "ok": ok}
        prev = last["hash"] if last else GENESIS
        rec = {**body, "prev": prev, "hash": _hash(prev, body)}
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(rec, default=str) + "\n")
    return rec


def read(f: Path) -> list[dict]:
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"seq": None, "hash": None, "torn": True})  # a damaged line is shown to verify, never skipped
    return out


def verify(f: Path) -> dict:
    """{ok, count, head, broken_at}: broken_at is the seq (or line number) of the first line that does not fit the chain."""
    prev, rows = GENESIS, read(f)
    for i, r in enumerate(rows, 1):
        body = {k: v for k, v in r.items() if k not in ("prev", "hash")}
        if r.get("torn") or r.get("prev") != prev or r.get("seq") != i or r.get("hash") != _hash(prev, body):
            return {"ok": False, "count": len(rows), "head": prev, "broken_at": i}
        prev = r["hash"]
    return {"ok": True, "count": len(rows), "head": prev, "broken_at": None}


def _file(app, company_id: str | None) -> Path:
    from sh_platform.plane import PlaneStore
    root = Path(app.state.settings.data_root)
    if company_id:
        return PlaneStore(root).plane_for(company_id).path("ops", "audit.jsonl")
    return root / "_control" / "audit.jsonl"


def log_event(app, company_id: str | None, actor: str, action: str, detail: str = "", ok: bool = True) -> None:
    try:
        append(_file(app, company_id), actor, action, detail, ok, company_id)
    except Exception:  # noqa: BLE001 - see module docstring
        log.warning("audit: could not record %s", action, exc_info=True)


def classify(method: str, path: str) -> str | None:
    """The audit action for an API call, or None for calls not logged (auth is logged by the sign-in routes themselves)."""
    if not path.startswith("/api/") or path.startswith(_QUIET[:2]):
        return None
    m = method.upper()
    if m in ("GET", "HEAD"):
        return "export" if _EXPORT.search(path) else "read"
    if _DECISION.search(path):
        return "signed_decision"
    if "/settings" in path or "/security" in path:
        return "settings_change"
    return "export" if _EXPORT.search(path) else "change"


def record_request(app, state: dict, method: str, path: str) -> None:
    """Called by the access middleware for an allowed, signed-in call."""
    action = classify(method, path)
    if action is None or not state.get("account_id"):
        return
    if path.startswith("/api/v3/audit"):  # reading the log is itself recorded, once, as an audit view
        action = "export" if _EXPORT.search(path) else "audit_view"
    actor = state["account_id"]
    if action in ("read", "audit_view"):
        now, key = time.monotonic(), (actor, path)
        if now - _SEEN.get(key, -1e9) < READ_COLLAPSE_SECONDS:
            return
        if len(_SEEN) > 5000:
            _SEEN.clear()
        _SEEN[key] = now
    acct = app.state.account_store.get(actor) or {}
    log_event(app, state.get("company_id"), f"{acct.get('display_name') or actor} <{actor[:8]}>", action, f"{method.upper()} {path}")


def query(rows: list[dict], actor: str = "", action: str = "", text: str = "", since: str = "", until: str = "") -> list[dict]:
    a, t = actor.casefold(), text.casefold()
    return [r for r in rows if (not a or a in str(r.get("actor", "")).casefold()) and (not action or r.get("action") == action)
            and (not t or t in str(r.get("detail", "")).casefold()) and (not since or str(r.get("ts", "")) >= since)
            and (not until or str(r.get("ts", "")) <= until + "~")]


def to_csv(rows: list[dict], head: str) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["seq", "time_utc", "actor", "action", "ok", "detail", "prev_hash", "hash"])
    for r in rows:
        w.writerow([_safe(r.get(k)) for k in ("seq", "ts", "actor", "action", "ok", "detail", "prev", "hash")])
    w.writerow(["# chain head", head])
    return out.getvalue()


def _safe(v):
    """A cell that starts with = + - @ would run as a formula in a spreadsheet."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s
