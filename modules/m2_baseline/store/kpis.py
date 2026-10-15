"""The baseline's KPIs: intents/m2_baseline/<baseline id>/kpis.json, a list in the shape of contracts/SHARED.md.
No KPI exists until a person confirms it: only `add` writes one. `read_kpis(plane, baseline_id)` is what the other
module 2 packages call. A signed baseline is read-only (Locked)."""
from typing import Callable

from modules.m2_baseline.store import baseline as B
from sh_platform.jsonfile import lock_for


def _file(plane, baseline_id):
    return B.root(plane) / baseline_id / "kpis.json"


def read_kpis(plane, baseline_id) -> list[dict]:
    """The KPIs of one baseline, [] when it has none (or there is no such baseline)."""
    if not B.is_id(baseline_id):
        return []
    return B.read_file(_file(plane, baseline_id), list) or []


def _editable(plane, baseline_id) -> dict:
    base = B.read_baseline(plane, baseline_id)
    if base is None:
        raise LookupError("no baseline")
    if base["state"] == "signed":
        raise B.Locked(B.LOCKED)
    return base


def add(plane, baseline_id: str, kpi: dict) -> dict:
    with lock_for(_file(plane, baseline_id)):
        _editable(plane, baseline_id)
        kpis = read_kpis(plane, baseline_id)
        if any(k["id"] == kpi["id"] for k in kpis):
            raise FileExistsError("already confirmed")
        B.write_file(_file(plane, baseline_id), [*kpis, kpi])
        return kpi


def change(plane, baseline_id: str, kpi_id: str, edit: Callable[[dict], dict]) -> dict:
    """Replace one KPI with `edit(kpi)`. LookupError when there is no such KPI."""
    with lock_for(_file(plane, baseline_id)):
        _editable(plane, baseline_id)
        kpis = read_kpis(plane, baseline_id)
        i = next((n for n, k in enumerate(kpis) if k["id"] == kpi_id), None)
        if i is None:
            raise LookupError("no KPI")
        kpis[i] = edit(kpis[i])
        B.write_file(_file(plane, baseline_id), kpis)
        return kpis[i]


def remove(plane, baseline_id: str, kpi_id: str) -> None:
    with lock_for(_file(plane, baseline_id)):
        _editable(plane, baseline_id)
        kpis = read_kpis(plane, baseline_id)
        if not any(k["id"] == kpi_id for k in kpis):
            raise LookupError("no KPI")
        B.write_file(_file(plane, baseline_id), [k for k in kpis if k["id"] != kpi_id])
