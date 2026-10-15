"""Signal Harbor 1.0: every slim feature lives in its own pair of files here, so builders never touch a shared file.

- `sh_platform/v1/<card>_routes.py` exports `router` (a FastAPI APIRouter); `install(app)` includes every one it finds.
- `sh_platform/v1/<card>.permissions.yaml` holds that card's `routes:` block in the shape of route_permissions.yaml;
  `extra_permission_files()` lists them and the permissions loader merges them in (a key already declared wins, so a
  card cannot widen a kernel route)."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path

from fastapi import Depends, FastAPI

log = logging.getLogger(__name__)
HERE = Path(__file__).resolve().parent


def extra_permission_files() -> list[Path]:
    return sorted(HERE.glob("*.permissions.yaml"))


def install(app: FastAPI) -> None:
    from sh_platform.v1 import g1_access as G1
    for p in sorted(HERE.glob("*_routes.py")):
        mod = importlib.import_module(f"sh_platform.v1.{p.stem}")
        router = getattr(mod, "router", None)
        if router is None:
            log.warning("v1 card %s has no `router`; skipped", p.name)
            continue
        app.include_router(router, dependencies=[Depends(G1.intent_gate)])
