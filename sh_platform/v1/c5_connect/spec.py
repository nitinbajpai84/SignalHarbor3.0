"""Connector specs: kept in the company plane (connectors/specs.json). Credentials are environment variable NAMES only."""
from __future__ import annotations

import json
import re
import threading

from sh_platform.jsonfile import write_json_atomic
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import wh

SCHEDULES = {"manual": 0, "hourly": 3600, "daily": 86400, "weekly": 7 * 86400}
# kind -> (credential keys required, one of optional, param keys)
KINDS = {
    "imap": {"creds": ("user", "password"), "params": ("mailbox",), "host": True},
    "sftp": {"creds": ("user",), "any": ("password", "key_file"), "params": ("remote_path", "port"), "host": True},
    "graph": {"creds": ("tenant", "client_id", "client_secret"), "params": ("drive_id", "folder"), "host": False},
}
GRAPH_HOST = "graph.microsoft.com"
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
# connector variables must start CONN_, so a connector can never be pointed at a platform secret (SH_JEV_API_KEY, SH_MCP_TOKEN)
_VAR = re.compile(r"CONN_[A-Z0-9_]{1,59}")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+")
_LOCK = threading.RLock()


def _path(plane):
    return plane.path("connectors", "specs.json")


def all_specs(plane) -> dict[str, dict]:
    try:
        d = json.loads(_path(plane).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def get(plane, cid: str) -> dict:
    s = all_specs(plane).get(cid)
    if not s:
        raise L.Refused("We could not find that connector.", 404)
    return s


def clean(raw: dict, cid: str) -> dict:
    """Validate a spec; raises Refused. Unknown keys are dropped; a credential value that is not a variable name is refused."""
    if not isinstance(raw, dict) or not _ID.fullmatch(cid):
        raise L.Refused("The connector name must be lower-case letters, digits, - or _.")
    kind = raw.get("kind")
    if kind == "api":  # a fixed public provider (api.py): no credentials in the spec, the host is never the caller's
        from sh_platform.v1.c5_connect import api
        return api.clean_spec(raw, cid)
    k = KINDS.get(kind)
    if not k:
        raise L.Refused("The connector kind must be imap, sftp or graph.")
    creds = raw.get("credentials") if isinstance(raw.get("credentials"), dict) else {}
    allowed = set(k["creds"]) | set(k.get("any", ()))
    if set(creds) - allowed or any(not isinstance(v, str) or not _VAR.fullmatch(v) for v in creds.values()):
        raise L.Refused("Credentials are given as the NAMES of environment variables starting CONN_ (capital letters and _), never the values.")
    if set(k["creds"]) - set(creds) or (k.get("any") and not set(k["any"]) & set(creds)):
        raise L.Refused("Name the environment variable for each credential: " + ", ".join(k["creds"] + k.get("any", ())) + ".")
    host = GRAPH_HOST if not k["host"] else str(raw.get("host") or "").strip().lower()
    if not _HOST.fullmatch(host):
        raise L.Refused("The host must be a plain host name such as mail.example.com.")
    sched = raw.get("schedule", "manual")
    if sched not in SCHEDULES:
        raise L.Refused("The schedule must be manual, hourly, daily or weekly.")
    code = re.sub(r"[^a-z0-9_]", "", str(raw.get("source_code") or "").lower())
    if not code:
        raise L.Refused("Say which source these files belong to (the source code).")
    params = {p: str(raw.get("params", {}).get(p) or "")[:300] for p in k["params"]} if isinstance(raw.get("params"), dict) else {}
    if kind == "imap":
        params["mailbox"] = params.get("mailbox") or "INBOX"
    if kind == "sftp":
        if not params.get("remote_path"):
            raise L.Refused("Give the remote folder to read.")
        params["port"] = params.get("port") or "22"
        if not params["port"].isdigit():
            raise L.Refused("The port must be a number.")
    if kind == "graph" and not params.get("drive_id"):
        raise L.Refused("Give the drive id to read.")
    pattern = str(raw.get("file_pattern") or "*.xlsx;*.xlsm;*.csv")[:200]
    if any(_CTRL.search(v) for v in (*params.values(), pattern)):  # no CR/LF smuggled into IMAP or path commands
        raise L.Refused("The folder, path and file names cannot contain line breaks or control characters.")
    return {"id": cid, "kind": kind, "host": host, "schedule": sched, "source_code": code, "credentials": dict(creds),
            "params": params, "file_pattern": pattern}


def save(plane, cid: str, raw: dict) -> dict:
    spec = clean(raw, cid)
    with _LOCK:
        d = all_specs(plane)
        spec["created_at"] = d.get(cid, {}).get("created_at") or wh.now().isoformat()
        d[cid] = spec
        write_json_atomic(_path(plane), d)
    if spec["kind"] == "api":
        from sh_platform.v1.c5_connect import api
        api.allow_host(plane, spec["host"])  # the internet switch stays as the administrator set it
    return spec


def remove(plane, cid: str) -> None:
    with _LOCK:
        d = all_specs(plane)
        if d.pop(cid, None) is None:
            raise L.Refused("We could not find that connector.", 404)
        write_json_atomic(_path(plane), d)
