"""The six steps of an assessment and how each package reports where its step stands.

A package registers `state(assessment_dir) -> {"state": "not_started|in_progress|done", "waiting_on": "plain words"}`
for its step id, in its own module, at import time. A step nobody has registered reads "not started".
"""
from pathlib import Path
from typing import Callable

STATES = ("not_started", "in_progress", "done")
STEPS = (  # (id, label, who it waits on until a package says otherwise)
    ("map", "Source map", "Lens is scoring your sources. Nothing is needed from you yet."),
    ("request", "Data request", "Waiting for the people who own your sources to send their files."),
    ("scan", "Scan", "Waiting for the first source data to arrive."),
    ("trial", "Trial", "Waiting for the figures you already report, to check Lens against."),
    ("findings", "Findings", "Waiting for the trial to finish."),
    ("plan", "Plan", "Waiting for the findings, then the sponsor and the head of data sign."),
)
_registry: dict[str, Callable[[Path], dict]] = {}


def register(step_id: str, state: Callable[[Path], dict]) -> None:
    if step_id not in {s[0] for s in STEPS}:
        raise ValueError("unknown step")
    _registry[step_id] = state


def steps_for(assessment_dir: Path) -> list[dict]:
    out = []
    for sid, label, waiting in STEPS:
        got = _registry[sid](assessment_dir) if sid in _registry else {}
        state = got.get("state") if got.get("state") in STATES else "not_started"
        out.append({"id": sid, "label": label, "state": state,
                    "waiting_on": "" if state == "done" else str(got.get("waiting_on") or waiting)})
    return out


from modules.m3_connect.domain import sources as _p01  # noqa: E402  M3-P01

register("map", _p01.step_state)
from modules.m3_connect.domain import findings as _findings, trial as _trial  # noqa: E402  M3-P03
register("trial", _trial.state)
register("findings", _findings.state)
from modules.m3_connect.domain.accept import step_state as _plan_step  # noqa: E402  M3-P04
register("plan", _plan_step)
import modules.m3_connect.domain.intake  # noqa: E402,F401  M3-P02 registers the "request" and "scan" steps
