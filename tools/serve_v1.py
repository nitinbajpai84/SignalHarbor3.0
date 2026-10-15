"""Serve Signal Harbor 1.0: the API and the built UI (ui/dist) on one port, 8400. No reload; see .sh-tmp/backend-watch-v1.sh."""
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sh_platform.app import create_app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(create_app(dist_dir=ROOT / "ui" / "dist"), host="127.0.0.1", port=8400, log_level="warning")
