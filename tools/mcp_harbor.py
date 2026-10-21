"""A minimal MCP server (stdio, JSON-RPC 2.0, one message per line) that lets a client's own AI tool query Signal Harbor through the public API.

Tools: ask, figures (the list, or one figure with its receipts when `id` is given), signals. Read only: it can do what the API key can do and nothing more.
Set HARBOR_API_KEY (the shpub... key an office admin made under Build, API keys) and, if Harbor is not on this machine, HARBOR_API_BASE (default http://localhost:8200).
Run it from the AI tool's MCP settings:  python tools/mcp_harbor.py   (docs/v3/API.md). Standard library only.
What these tools return goes to whichever AI tool you connected: connect only one you are happy to see this key's data.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = "Signal Harbor, read only. Answers and figures come with their receipts; quote them, do not recompute them."
TOOLS = [
    {"name": "ask", "description": "Ask Signal Harbor a question about the office's figures in plain words. Returns the answer, the figure it came from and how it was worked out.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "description": "The question, in plain words."}}, "required": ["question"]}},
    {"name": "figures", "description": "List the office's figures. With an id, return that figure with its receipts (what it reads, how it was checked, its runs).",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string", "description": "A figure id from the list, for its receipts."}}}},
    {"name": "signals", "description": "List the signals that have fired, newest first. Optionally only those open, acted or dismissed.",
     "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "acted", "dismissed"]}}}},
]


def http_api(method: str, path: str, body: dict | None = None, *, base: str | None = None, key: str | None = None):
    """(status, parsed JSON) from the public API. A key that is missing is a plain message, never a request."""
    key = key if key is not None else os.environ.get("HARBOR_API_KEY", "").strip()
    if not key:
        return 0, {"message": "HARBOR_API_KEY is not set. Make a key under Build, API keys, and put it in that variable."}
    url = (base or os.environ.get("HARBOR_API_BASE", "http://localhost:8200")).rstrip("/") + "/api/public/v1" + path
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - the base is the operator's own setting
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {"message": "Signal Harbor could not be reached. Check HARBOR_API_BASE."}


def _say(status: int, body) -> str:
    if status == 200:
        return json.dumps(body, indent=1, ensure_ascii=False)
    d = body.get("detail", body) if isinstance(body, dict) else {}
    return str((d.get("message") if isinstance(d, dict) else d) or {401: "The API key is wrong or revoked.", 403: "The key does not allow that.", 429: "Too many calls; try again in a minute."}.get(status, "That did not work."))


def call_tool(name: str, args: dict, api=http_api) -> dict:
    """The tool result; `api(method, path, body)` replaces the HTTP call (tests)."""
    if name == "ask":
        q = str(args.get("question") or "").strip()
        out = api("POST", "/ask", {"text": q}) if q else (0, {"message": "Give a question."})
    elif name == "figures":
        fid = str(args.get("id") or "").strip()
        out = api("GET", "/figures/" + urllib.parse.quote(fid, safe="")) if fid else api("GET", "/figures")
    elif name == "signals":
        status = str(args.get("status") or "")
        out = api("GET", "/signals" + (f"?status={urllib.parse.quote(status, safe='')}" if status else ""))
    else:
        return {"content": [{"type": "text", "text": "That tool is not available."}], "isError": True}
    return {"content": [{"type": "text", "text": _say(*out)}], "isError": out[0] != 200}


def handle(msg, api=http_api) -> dict | None:
    """The reply to one JSON-RPC message, or None for a notification."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request."}}
    if "id" not in msg:
        return None
    mid, method, params = msg["id"], msg["method"], msg.get("params") if isinstance(msg.get("params"), dict) else {}
    if method == "initialize":
        want = params.get("protocolVersion")
        result = {"protocolVersion": want if want in VERSIONS else VERSIONS[0], "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "signal-harbor-public-api", "version": "1.0"}, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") if isinstance(params.get("arguments"), dict) else {}, api)
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found."}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            msg = None
        out = handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
