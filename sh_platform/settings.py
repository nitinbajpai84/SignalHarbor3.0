import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

_NAMES = ("SH_MODE", "SH_DATA_ROOT", "SH_SESSION_SECRET", "SH_EGRESS_DEFAULT")


@dataclass(frozen=True)
class Settings:
    mode: str = "dev"
    data_root: str = "./data"
    session_secret: str = field(default="", repr=False)
    egress_default: str = "off"


def _is_model_name(name: str) -> bool:
    return name in ("GOOGLE_API_KEY", "OPENROUTER_API_KEY") or name.startswith("SH_MODEL_")


def _read_env_file(path: Path, wanted=lambda n: n in _NAMES) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        name = name.strip()
        if sep and wanted(name) and value.strip().strip("\"'"):
            out[name] = value.strip().strip("\"'")
    return out


def load_settings(
    env: Mapping[str, str] | None = None, env_file: Path | None = None
) -> Settings:
    """Environment wins over .env; only the names listed in .env.example are read."""
    if env is None:
        env = os.environ
    merged = {
        **_read_env_file(env_file or Path(".env")),
        **{k: env[k] for k in _NAMES if k in env},
    }
    return Settings(
        mode=merged.get("SH_MODE") or "dev",
        data_root=merged.get("SH_DATA_ROOT") or "./data",
        session_secret=merged.get("SH_SESSION_SECRET", ""),
        egress_default=merged.get("SH_EGRESS_DEFAULT") or "off",
    )


def load_model_env(env: Mapping[str, str] | None = None, env_file: Path | None = None) -> dict[str, str]:
    """Only the model settings (GOOGLE_API_KEY, OPENROUTER_API_KEY, SH_MODEL_*) from .env and the process
    environment, which wins even when a value there is empty. SH_MODEL_PROVIDER=off switches model calls off. This is what picks the model provider; no value is ever printed or logged."""
    env = os.environ if env is None else env
    return {**_read_env_file(env_file or Path(".env"), _is_model_name),
            **{k: v for k, v in env.items() if _is_model_name(k)}}  # set but empty still wins: that provider is off


def model_is_off() -> bool:
    """True when no model provider is set, or it is switched off: read the same way the model client reads it (.env plus the process
    environment), so a server that loads its model settings from .env is never mistaken for one with the model off."""
    return (load_model_env().get("SH_MODEL_PROVIDER") or "").strip().lower() in ("", "off", "none")
