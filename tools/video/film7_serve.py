"""Film v4's recording server: port 8697, data .sh-tmp/testenv/vid7/data, the UI built from the current source into D:/Temp/vid7/dist
(build it with: cd ui && npx vite build --outDir D:/Temp/vid7/dist --emptyOutDir). Scheduler off; log next to the data."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DATA = Path(os.environ.get("SH_SERVE_DATA") or ROOT / ".sh-tmp/testenv/vid7/data")    # the explainer passes its own (vid6, port 8696)
os.environ["SH_DATA_ROOT"] = str(DATA)
os.environ["SH_SCHEDULER"] = "off"
sys.stdout = sys.stderr = open(DATA.parent / "server.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the server

import uvicorn  # noqa: E402

from sh_platform.app import create_app  # noqa: E402

uvicorn.run(create_app(dist_dir=Path("D:/Temp/vid7/dist")), host="127.0.0.1", port=int(os.environ.get("SH_SERVE_PORT", 8697)), log_level="warning")
