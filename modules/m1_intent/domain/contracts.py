"""Reads the module's contract lists (spec section 8). Strict: a broken file is a plain error, never a guess.

Every list and limit the screens offer comes from here, so a change to the YAML changes the behaviour.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

from sh_platform.plane import valid_module_id

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "contracts"
SPLIT_PARTS = ("briefing", "individual", "together")  # the three timed parts of a session (M1-02)


class ContractError(ValueError):
    """A contract file is not readable or not valid; the message names the file and what is wrong."""


@dataclass(frozen=True)
class SessionSettings:
    seats_min: int
    seats_max: int
    time_presets: tuple[int, ...]
    custom_min: int
    custom_max: int
    min_stage_minutes: int
    default_length_minutes: int
    default_split_percent: dict[str, int]
    warning_seconds: int
    text_limits: dict[str, int]
    briefing_video_options: tuple[str, ...]


@dataclass(frozen=True)
class CharterTemplate:
    id: str
    name: str
    description: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class CharterTemplates:
    default_id: str
    templates: tuple[CharterTemplate, ...]

    def get(self, template_id) -> CharterTemplate | None:
        return next((t for t in self.templates if t.id == template_id), None)


def _int(v, what: str, low: int = 1) -> int:
    if type(v) is not int or v < low:
        raise ValueError(f"{what} must be a whole number of at least {low}")
    return v


def _read(folder, name: str) -> dict:
    path = Path(folder or DEFAULT_DIR) / name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise ContractError(f"{name} cannot be read.") from None
    if not isinstance(data, dict):
        raise ContractError(f"{name} must be a mapping of settings.")
    return data


def load_session_settings(folder=None) -> SessionSettings:
    name = "intent_session.yaml"
    d = _read(folder, name)
    try:
        seats, custom = d["seats"], d["custom_length_minutes"]
        split = d["default_split_percent"]
        presets = d["time_presets_minutes"]
        limits = d["text_limits"]
        videos = d["briefing_video_options"]
        if not (isinstance(seats, dict) and isinstance(custom, dict) and isinstance(split, dict)
                and isinstance(presets, list) and isinstance(limits, dict) and isinstance(videos, list)):
            raise ValueError("a list or a group of settings has the wrong shape")
        s = SessionSettings(
            seats_min=_int(seats["min"], "seats min"), seats_max=_int(seats["max"], "seats max"),
            time_presets=tuple(_int(m, "a time preset") for m in presets),
            custom_min=_int(custom["min"], "custom length min"), custom_max=_int(custom["max"], "custom length max"),
            min_stage_minutes=_int(d["min_stage_minutes"], "min stage minutes"),
            default_length_minutes=_int(d["default_length_minutes"], "default length"),
            default_split_percent={p: _int(split[p], "a default split", 0) for p in SPLIT_PARTS},
            warning_seconds=_int(d["warning_seconds"], "warning seconds"),
            text_limits={k: _int(v, "a text limit") for k, v in limits.items()},
            briefing_video_options=tuple(str(v) for v in videos))
        if (s.seats_min > s.seats_max or s.custom_min > s.custom_max or sum(s.default_split_percent.values()) != 100
                or not s.time_presets or not s.briefing_video_options
                or set(limits) < {"purpose", "outcome", "approver_name", "template_name"}):
            raise ValueError("the numbers do not fit together")
    except (KeyError, ValueError, TypeError) as e:
        raise ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None
    return s


def load_charter_templates(folder=None) -> CharterTemplates:
    name = "charter_templates.yaml"
    d = _read(folder, name)
    try:
        rows = d["templates"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("there must be at least one template")
        out = []
        for r in rows:
            if not (isinstance(r, dict) and valid_module_id(r["id"])
                    and isinstance(r["name"], str) and r["name"].strip()
                    and isinstance(r["description"], str) and isinstance(r["columns"], list)):
                raise ValueError("a template needs an id, a name, a description and columns")
            out.append(CharterTemplate(r["id"], r["name"].strip(), r["description"].strip(),
                                       tuple(str(c) for c in r["columns"])))
        ids = [t.id for t in out]
        if len(set(ids)) != len(ids) or d["default_template"] not in ids:
            raise ValueError("template ids must be unique and the default must exist")
        return CharterTemplates(d["default_template"], tuple(out))
    except (KeyError, ValueError, TypeError) as e:
        raise ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None
