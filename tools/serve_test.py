"""Serve Signal Harbor for one tester: its own port and its own copy of the data, so testers never share state.

    python tools/serve_test.py --port 8501 --data-root .sh-tmp/testenv/t01/data

The data root is a copy of the golden demo data (`tools/make_test_env.py`). The scheduler is off unless --scheduler.
The server writes its log to <data-root>/../server.log, never to the console that started it: in cycle 1 a test server died with exit
code 2 right after logging "model call failed" (j-uc5a.0), because the console it wrote to had gone. A failed model call is a warning.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--scheduler", action="store_true")
    ap.add_argument("--dist", help="a built UI folder (default ui/dist); lets one tester try a UI build without changing the others' screens")
    a = ap.parse_args()
    os.environ["SH_DATA_ROOT"] = str(Path(a.data_root).resolve())
    if not a.scheduler:
        os.environ["SH_SCHEDULER"] = "off"
    log = Path(a.data_root).resolve().parent / "server.log"
    print(f"serving {a.data_root} on port {a.port}; log in {log}", flush=True)
    sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the server
    import uvicorn
    from sh_platform.app import create_app
    uvicorn.run(create_app(dist_dir=Path(a.dist).resolve() if a.dist else ROOT / "ui" / "dist"), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
