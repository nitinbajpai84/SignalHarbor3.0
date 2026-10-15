"""C5 operations: test (read only), dry run, fetch (lands through e0c_landing), health (feeds Map health)."""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime

from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.jsonfile import write_json_atomic
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import wh
from sh_platform.v1.c5_connect import spec as S
from sh_platform.v1.c5_connect.kinds import DEFAULTS, SESSIONS, ConnectorError

log = logging.getLogger(__name__)
MODULE = "c5_connect"
LATE_GRACE = 1.5
_LOCK = threading.RLock()


def _company_wide(pol) -> bool:
    """The Settings switch sets every enabled module; c5_connect is not one of them, so a company with internet on for all of its modules counts as on."""
    d = pol._read().get("internet")
    return isinstance(d, dict) and bool(d) and all(v is True for v in d.values())


class Gate:
    """Default deny: the connector switch must be on for this company and the host on its internet list. Each connection is
    logged before it is made (host, kind, byte count; never a credential or a file name)."""

    def __init__(self, plane):
        self.gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[], transport=None)

    def call(self, kind, host, fn):
        gw, aid = self.gw, uuid.uuid4().hex[:8]
        f = gw._open_log()
        with f:
            on = gw.policy.is_internet_allowed(MODULE) or (gw.policy.flag("connectors") and _company_wide(gw.policy))  # internet alone is for agents; connectors need their own Settings switch too
            if not on or host.lower() not in gw.policy.internet_hosts():
                reason = "internet_off" if not on else "destination_not_allowed"
                gw._write(f, MODULE, kind, host, "blocked", reason, b"", aid)
                raise EgressBlocked(reason)
            gw._write(f, MODULE, kind, host, "sent", "", b"", aid)
            try:
                return fn()
            except Exception as e:
                gw._write(f, MODULE, kind, host, "failed", getattr(e, "reason_code", "transport_failed"), b"", aid)
                raise


def _env(spec):
    def get(key):
        name = spec["credentials"][key]
        v = os.environ.get(name)  # read at the moment of use; never stored, logged or returned
        if not v:
            raise ConnectorError("missing_credential", f"The environment variable {name} is not set on the server.")
        return v
    return get


def _open(plane, spec, F):
    return SESSIONS[spec["kind"]](spec, _env(spec), Gate(plane), {**DEFAULTS, **(F or {})})


def _explain(e: Exception) -> dict:
    if isinstance(e, ConnectorError):
        return {"code": e.code, "message": e.message}
    if isinstance(e, EgressBlocked):
        return {"code": e.reason_code, "message": e.message + " An administrator can allow the host in Settings, Egress."}
    log.warning("connector call failed: %s", type(e).__name__)  # the type only: the text could echo a credential
    return {"code": "failed", "message": "The connector could not complete. Check the host, folder and credentials, then try again."}


def _runs_path(plane, cid):
    return plane.path("connectors", "runs", f"{cid}.json")


def _run(plane, cid) -> dict:
    try:
        return json.loads(_runs_path(plane, cid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "never", "landed_total": 0, "duplicates_total": 0, "checkpoint": {}, "last_run": None, "last_ok": None, "error": None}


def _api():
    from sh_platform.v1.c5_connect import api
    return api


def test(plane, spec, F=None) -> dict:
    if spec["kind"] == "api":
        return _api().test(plane, spec, F)
    s = None
    try:
        s = _open(plane, spec, F)
        return {"ok": True, **s.probe()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, **_explain(e)}
    finally:
        s and s.close()


def dry_run(plane, spec, F=None) -> dict:
    if spec["kind"] == "api":
        return {"ok": True, "would_arrive": [], **{k: v for k, v in _api().test(plane, spec, F).items() if k in ("message", "rows")}}
    s = None
    try:
        s = _open(plane, spec, F)
        items, _ = s.items(_run(plane, spec["id"]).get("checkpoint"))
        return {"ok": True, "would_arrive": [{"name": i["name"], "size": i["size"]} for i in items]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "would_arrive": [], **_explain(e)}
    finally:
        s and s.close()


def fetch(plane, spec, F=None) -> dict:
    out = _fetch(plane, spec, F)
    from sh_platform.v1 import run_log
    ok = out["status"] == "ok"
    run_log.record(plane, "connector_pull", "production", "connector", None, [dict(name=spec["id"], layer="bronze", target=spec.get("source_code") or spec.get("provider"),
                   rows_in=out.get("seen", 0), inserted=out.get("landed", 0), rejected=out.get("skipped", 0), checks_passed=int(ok), checks_failed=int(not ok), error=out.get("error"))], "ok" if ok else "failed")
    return out


def _fetch(plane, spec, F=None) -> dict:
    """Land new files. The same bytes are never landed twice (e0c_landing hashes), and the checkpoint only moves on a clean run."""
    if spec["kind"] == "api":
        return _api().pull(plane, spec, F)
    with _LOCK:
        run, now = _run(plane, spec["id"]), wh.now().isoformat()
        landed = dups = skipped = 0
        s = None
        try:
            s = _open(plane, spec, F)
            items, ck = s.items(run.get("checkpoint"))
            for it in items:
                try:
                    r = L.receive(plane, s.read(it), it["name"], f"connector:{spec['id']}", spec["source_code"])
                except L.Refused:
                    skipped += 1  # empty or too large: it would never succeed, so it is not retried
                    continue
                dups, landed = dups + r["duplicate"], landed + (not r["duplicate"])
            run.update(status="ok", error=None, checkpoint=ck, last_ok=now, last_files=landed, last_seen=len(items), last_skipped=skipped,
                       landed_total=run["landed_total"] + landed, duplicates_total=run["duplicates_total"] + dups)
        except Exception as e:  # noqa: BLE001
            run.update(status="failed", error=_explain(e), last_files=0)
        finally:
            s and s.close()
        run["last_run"] = now
        write_json_atomic(_runs_path(plane, spec["id"]), run)
        return {"status": run["status"], "error": run["error"], "landed": run["last_files"], "seen": run.get("last_seen", 0),
                "duplicates": dups, "skipped": skipped}


def health(plane, now: datetime | None = None) -> list[dict]:
    """One row per connector: last run, files, late or failed. `late` = no clean run within 1.5 schedule intervals (manual is never late)."""
    now = now or wh.now()
    out = []
    for cid, spec in sorted(S.all_specs(plane).items()):
        r = _run(plane, cid)
        every = S.SCHEDULES.get(spec["schedule"], 0)
        ref = r.get("last_ok") or spec.get("created_at")
        late = bool(every and ref and (now - datetime.fromisoformat(ref)).total_seconds() > every * LATE_GRACE)
        out.append({"id": cid, "kind": spec["kind"], "source_code": spec["source_code"], "schedule": spec["schedule"],
                    "status": r["status"], "failed": r["status"] == "failed", "late": late, "error": r.get("error"),
                    "last_run": r.get("last_run"), "last_ok": r.get("last_ok"), "last_files": r.get("last_files", 0),
                    "files_landed": r["landed_total"], "duplicates_skipped": r["duplicates_total"]})
    return out


def map_feed(plane) -> dict[str, dict]:
    """For Map health: source_code -> {connector, is_late, failed, last_ok}. A source with several connectors is late if any is."""
    out: dict[str, dict] = {}
    for h in health(plane):
        o = out.setdefault(h["source_code"], {"connector": h["id"], "is_late": False, "failed": False, "last_ok": h["last_ok"]})
        o["is_late"] |= h["late"] or h["failed"]
        o["failed"] |= h["failed"]
    return out


def run_due(plane, F=None) -> list[str]:
    """For a poll: fetch every scheduled connector whose last run is older than its interval. Returns the ids run."""
    now, ran = wh.now(), []
    for cid, spec in S.all_specs(plane).items():
        every = S.SCHEDULES.get(spec["schedule"], 0)
        last = _run(plane, cid).get("last_run")
        if spec["kind"] == "api":  # daily at its own time (05:30), like the pipeline scheduler
            if _api().is_due(spec, last):
                fetch(plane, spec, F)
                ran.append(cid)
            continue
        if every and (not last or (now - datetime.fromisoformat(last)).total_seconds() >= every):
            fetch(plane, spec, F)
            ran.append(cid)
    return ran
