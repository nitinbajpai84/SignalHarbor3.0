"""Start-up check: fails loudly when something Signal Harbor needs is missing. Never prints a secret.

Usage: python tools/doctor.py
"""
from __future__ import annotations

import logging
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so sh_platform imports when run as a script
MODEL_KEYS = ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")
SPEECH_NAMES = ("SH_SPEECH_PROVIDER", "SPEECH_PROVIDER")
REQUIRED = ("SH_MODE", "SH_DATA_ROOT", "SH_SESSION_SECRET")

log = logging.getLogger("doctor")


def read_env(path: Path) -> dict[str, str]:
    """Names and values from a .env file; values are only checked for being non-empty."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def port_is_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _data_root_writable(raw: str) -> bool:
    """Create the folder if needed, then create and delete one temp file inside it."""
    try:
        root = Path(raw or "./data")
        root = root if root.is_absolute() else ROOT / root
        root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=root, prefix=".doctor-")
        os.close(fd)
        os.unlink(name)
        return True
    except OSError:
        return False


def _packs_load(packs_root: Path) -> bool:
    from sh_platform.packs import PackLoader

    try:
        return not any(PackLoader(packs_root).load(i).empty for i in ("insurance", "asset_management"))
    except (OSError, ValueError):
        return False


def _model_row(env: dict[str, str]) -> tuple[str, bool, str]:
    """Which provider North would use: names only (provider, model, key variable), never a value."""
    from sh_platform.egress.providers import key_status
    from sh_platform.settings import _is_model_name

    st = key_status({k: v for k, v in env.items() if _is_model_name(k) and v})
    fix = st["problem"] or "Set GOOGLE_API_KEY or OPENROUTER_API_KEY in .env"
    if st["off"]:
        return "Model calls: off", True, fix
    if st["provider"] is None:
        return "Model provider in use: none", False, fix
    return f"Model provider in use: {st['provider']}, model {st['model']}, key {st['key_env']}", True, fix


def _speech_row(env: dict[str, str]) -> tuple[str, bool, str]:
    """Which speech provider the screens use (M1-09, D-028): names only. Typing works with none."""
    from sh_platform.speech import status

    st = status(env, env.get("SH_MODE", ""))
    if st["provider"]:
        return f"Speech provider in use: {st['provider']}, key GOOGLE_API_KEY. {st['note']}", True, ""
    return f"Speech provider in use: none (typing only). {st['problem'] or ''}".strip(), st["ok"], st["problem"] or ""


def checks(env: dict[str, str] | None = None, port_free: Callable[[int], bool] = port_is_free,
           ui_dir: Path | None = None, packs_root: Path | None = None) -> list[tuple[str, bool, str]]:
    """Each check: (name, passed, the one action that fixes it). `env` is injectable for tests."""
    env_file = ROOT / ".env"
    if env is None:
        env = read_env(env_file) if env_file.exists() else {}
        env.update({k: os.environ[k] for k in os.environ if k in REQUIRED + MODEL_KEYS + SPEECH_NAMES or k.startswith("SH_MODEL_")
                    if os.environ.get(k)})
    mode = env.get("SH_MODE", "")
    results = [
        ("Python 3.11 or later", sys.version_info >= (3, 11), "Install Python 3.11+"),
        ("Node.js on the path", shutil.which("node") is not None, "Install Node.js 20+"),
        ("graft on the path", shutil.which("graft") is not None, "npm install -g @nanonets/graft"),
        (".env present", env_file.exists(), "Copy .env.example to .env and fill it in"),
        ("A model key set", any(env.get(k) for k in MODEL_KEYS), f"Set one of {', '.join(MODEL_KEYS)} in .env"),
    ]
    results.append(_model_row(env))
    results.append(_speech_row(env))
    results += [(f"{k} set", bool(env.get(k)), f"Set {k} in .env") for k in REQUIRED]
    results += [
        (f"Port {p} is free", port_free(p), f"Stop the program using port {p}") for p in (8400, 8401)
    ]
    results += [
        ("Data folder can be written", _data_root_writable(env.get("SH_DATA_ROOT", "")),
         "Set SH_DATA_ROOT in .env to a folder you can write to"),
        ("SH_MODE is dev or prod", mode in ("dev", "prod"), "Set SH_MODE to dev or prod in .env"),
        ("Session secret long enough", mode == "dev" or len(env.get("SH_SESSION_SECRET", "")) >= 32,
         "Set SH_SESSION_SECRET to at least 32 characters in .env"),
        ("Industry packs load", _packs_load(packs_root or ROOT / "packs"),
         "Restore the insurance and asset_management folders under packs"),
        ("ui/node_modules installed", (ui_dir or ROOT / "ui").joinpath("node_modules").is_dir(),
         "Run npm install in the ui folder"),
    ]
    return results


def main(rows: Callable[[], list[tuple[str, bool, str]]] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    failed = 0
    for name, ok, fix in (rows or checks)():
        log.info("%s  %s%s", "PASS" if ok else "FAIL", name, "" if ok else f"  ->  {fix}")
        failed += not ok
    log.info("%s", "Ready." if not failed else f"{failed} check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
