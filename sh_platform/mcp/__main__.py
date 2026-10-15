"""Stdio transport: newline-delimited JSON-RPC. `SH_MCP_TOKEN=shmcp... python -m sh_platform.mcp --data-root DIR`."""
import argparse
import json
import os
import sys

from sh_platform.mcp.server import handle


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", required=True)
    root, token = p.parse_args().data_root, os.environ.get("SH_MCP_TOKEN", "")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            status, out = handle(root, token, json.loads(line))
        except ValueError:
            status, out = 400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error."}}
        if status == 401:
            sys.exit("The token is not valid.")
        if out is not None:
            print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
