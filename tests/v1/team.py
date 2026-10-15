"""A test helper: put a person on a project's team, as picking the work up does (G1: Internal is the team's alone)."""
from pathlib import Path

from sh_platform.plane import PlaneStore
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P


def on_team(app, iid: str, name: str, role: str = "builder") -> str:
    plane = PlaneStore(Path(app.state.settings.data_root)).plane_for("neera")
    pid = P.project_of(plane, iid)["id"]
    G1.join(plane, pid, name, role)
    return pid
