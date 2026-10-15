"""The process map files of one baseline, in the company's own plane (M2-P03).

  intents/m2_baseline/<baseline id>/process_map.json            {kpi_id: {lanes, steps}}          (SHARED.md)
  intents/m2_baseline/<baseline id>/process_map_tracking.json   {kpi_id: {status, tentative_date, next_step, steps: {step id: status}}}

Strict reads (a damaged file is refused, never overwritten), atomic writes, one lock per plane.
The three readers at the bottom stand in for the read functions of M2-P01 (kpis.json, baseline.json) and M2-P02
(answers.json) until those stores land: they read the file exactly as SHARED.md shapes it. Swap them then.
"""
import re

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
UNREADABLE = "The process map could not be read. Please ask your administrator."


class MapUnreadable(Exception):
    pass


class BadId(ValueError):
    pass


class ProcessMapStore:
    def __init__(self, plane, baseline_id: str):
        if not _ID.fullmatch(baseline_id or ""):
            raise BadId(baseline_id)
        self._plane, self._bid = plane, baseline_id

    def _path(self, name: str):
        return self._plane.path("intents", "m2_baseline", self._bid, name)

    def lock(self):
        return lock_for(self._plane.root / ".m2_process_map")

    def _read(self, name: str, kind: type = dict):
        try:
            data = read_json_strict(self._path(name), kind)
        except (OSError, ValueError):
            raise MapUnreadable(UNREADABLE) from None
        return kind() if data is None else data

    def maps(self) -> dict:
        return self._read("process_map.json")

    def save_map(self, kpi_id: str, kpi_map: dict) -> None:
        with self.lock():
            write_json_atomic(self._path("process_map.json"), {**self.maps(), kpi_id: kpi_map})

    def tracking(self) -> dict:
        return self._read("process_map_tracking.json")

    def save_tracking(self, kpi_id: str, record: dict) -> None:
        with self.lock():
            write_json_atomic(self._path("process_map_tracking.json"), {**self.tracking(), kpi_id: record})

    # -- the other packages' read functions (integration, A-043)
    def kpis(self) -> list:
        from modules.m2_baseline.store.kpis import read_kpis
        return read_kpis(self._plane, self._bid)

    def answers(self) -> list:
        from modules.m2_baseline.store.answers import read_answers
        return read_answers(self._plane, self._bid)

    def baseline(self) -> dict:
        from modules.m2_baseline.store.baseline import read_baseline
        return read_baseline(self._plane, self._bid) or {}
