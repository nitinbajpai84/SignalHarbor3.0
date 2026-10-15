"""Start backend (127.0.0.1:8200) and UI dev server (8201); stop both on Ctrl+C."""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_PORT = 8200
UI_PORT = 8201


def main() -> int:
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sh_platform.app:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        cwd=ROOT,
    )
    ui = subprocess.Popen(
        "npm run dev -- --host 127.0.0.1 --port " + str(UI_PORT),
        cwd=ROOT / "ui",
        shell=True,  # npm is npm.cmd on Windows
    )
    procs = [backend, ui]
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None and sys.platform == "win32":
                # shell=True spawns a tree; kill it whole
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            elif p.poll() is None:
                p.terminate()
        for p in procs:
            p.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
