"""M2-E4: the ready-to-build gate read from the baseline's files. `compute` is over EVERY measure and row (the same for everyone: what stops a
signature); `for_viewer` is the same gate as one person may see it. Reads only."""
from typing import Callable

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import gate as D
from modules.m2_baseline.domain import glossary as DG
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import glossary as SG
from modules.m2_baseline.store import governance as SGOV
from modules.m2_baseline.store import kpis as K


def _used_rows(kpis: list[dict], left_out: dict) -> set[str]:
    """The catalogue rows (sources, tables, fields) the technical definitions of the measures that count point at."""
    return {i for k in kpis if isinstance(k, dict) and k.get("id") and k["id"] not in left_out
            for part in T.LINKS for i in (T.parts_of(k)[part].get("value") or []) if T.present(T.parts_of(k)[part])}


def _open(items: list[dict], left_out: dict, kpis: list[dict]) -> list[dict]:
    """The open questions that count. One about a measure left out is dropped, unless it names a row a measure that counts still uses."""
    used = _used_rows(kpis, left_out)
    return [a for a in items if a["status"] == "open" and (a["kpi_id"] not in left_out or any(r.get("id") in used for r in a.get("refs") or []))]


def compute(plane, baseline_id: str, left_out: dict | None = None) -> dict:
    left = left_out or {}
    kpis = K.read_kpis(plane, baseline_id)
    items = SA.listing(plane, baseline_id, SA.ALL_SEEING, lambda k: True)
    return D.check(kpis, SA.derived_open_all(plane, baseline_id), left, SG.glossary_ready(plane, baseline_id),
                   SGOV.governance_ready(plane, baseline_id), len(_open(items, left, kpis)))


def for_viewer(plane, baseline_id: str, left_out: dict | None, viewer: C.Viewer, sees: Callable[[dict], bool], full: dict | None = None) -> dict:
    """The gate for one person: their measures, their reasons, and "Something restricted is still open" when something they may not see is."""
    left = left_out or {}
    full = full or compute(plane, baseline_id, left)
    kpis = K.read_kpis(plane, baseline_id)
    seen = {k["id"] for k in kpis if sees(k)}
    mine = _open(SA.listing(plane, baseline_id, viewer, sees), left, kpis)
    by_kpi: dict[str, int] = {}
    for a in mine:
        if a["kpi_id"]:
            by_kpi[a["kpi_id"]] = by_kpi.get(a["kpi_id"], 0) + 1
    entries = SG.seen(plane, baseline_id, sees)
    have = {e["kpi_id"] for e in entries}
    glossary = DG.glossary_ready(entries, sum(1 for k in kpis if sees(k) and k["id"] not in have))
    return D.for_viewer(full, seen, by_kpi, len(mine), glossary, SGOV.governance_ready(plane, baseline_id, viewer))
