"""Serve the built UI (ui/dist) from the backend, as the last route, with a fallback for deep links."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

log = logging.getLogger(__name__)
DEFAULT_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"


# Paths the backend owns: they stay a plain 404 when nothing serves them (never index.html).
BACKEND_PREFIXES = {"api", "docs", "redoc", "openapi.json"}


class SpaFiles(StaticFiles):
    """Any other unknown address returns index.html so the UI can show its own "page not found"."""

    async def get_response(self, path: str, scope):
        path = path.replace("\\", "/")  # Starlette normalises with os.path: backslashes on Windows
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            parts = path.split("/")
            if exc.status_code != 404 or parts[0].lower() in BACKEND_PREFIXES or "." in parts[-1]:
                raise  # a missing file (has an extension) is a real 404
            return await super().get_response("index.html", scope)


def install_webui(app: FastAPI, dist_dir: Path | str | None = None) -> None:
    dist = Path(dist_dir or DEFAULT_DIST)
    if not (dist / "index.html").is_file():
        log.info("UI not built (%s has no index.html); serving the API only.", dist)
        return
    app.mount("/", SpaFiles(directory=dist, html=True))  # declared as MOUNT /{path}
