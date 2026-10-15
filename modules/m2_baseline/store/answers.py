"""The owners' answers (M2-10, M2-11): intents/m2_baseline/<baseline id>/answers.json, the shape in contracts/SHARED.md.

One record per person per KPI. A save merges the fields it carries and leaves the rest, so a person can save and return. Every
field is a provenance value. Other packages call `read_answers`; nothing else reads this file."""
import secrets
import time
from datetime import datetime, timezone

from modules.m2_baseline.domain.questionnaire import Questionnaire, load_questionnaire, with_blanks
from modules.m2_baseline.store.requests import baseline_folder, read_list
from sh_platform.jsonfile import lock_for, write_json_atomic


def read_answers(plane, baseline_id: str, q: Questionnaire | None = None) -> list[dict]:
    """What other packages call: every answer record of the baseline with all fields present. A question nobody answered
    reads as unknown from "not answered yet" (never as a known value) and is listed in the record's `unanswered`.
    A baseline with no answers gives []. Raises StoreError when the file cannot be read."""
    q = q or load_questionnaire()
    return [with_blanks(r, q) for r in read_list(baseline_folder(plane, baseline_id) / "answers.json")]


class AnswerStore:
    def __init__(self, plane, baseline_id: str, clock=time.time):
        self._clock = clock
        self._dir = baseline_folder(plane, baseline_id)
        self._file = self._dir / "answers.json"

    def all(self) -> list[dict]:
        return read_list(self._file)

    def for_owner(self, owner_name: str) -> list[dict]:
        return [r for r in self.all() if r["owner_name"] == owner_name]

    def save(self, owner_name: str, kpi_id: str, fields: dict[str, dict], *, request_id: str | None = None,
             meeting: dict | None = None) -> dict:
        """Merges `fields` (provenance values) into this person's record for this KPI, creating it on the first save."""
        with lock_for(self._dir):
            rows = self.all()
            at = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()
            i = next((n for n, r in enumerate(rows) if r["owner_name"] == owner_name and r["kpi_id"] == kpi_id), None)
            base = rows[i] if i is not None else {"id": secrets.token_hex(8), "request_id": None, "meeting": None,
                                                  "owner_name": owner_name, "kpi_id": kpi_id}
            rec = {**base, **fields, "saved_at": at}
            if request_id:
                rec["request_id"] = request_id
            if meeting:
                rec["meeting"] = meeting
            rows = [*rows[:i], rec, *rows[i + 1:]] if i is not None else [*rows, rec]
            write_json_atomic(self._file, rows)
            return rec

    @staticmethod
    def kpis_by_owner(rows: list[dict]) -> dict[str, set[str]]:
        """{owner: the KPIs they have at least one answer for}, from rows already read."""
        skip = {"id", "request_id", "meeting", "owner_name", "kpi_id", "saved_at"}
        out: dict[str, set[str]] = {}
        for r in rows:
            if set(r) - skip:
                out.setdefault(r["owner_name"], set()).add(r["kpi_id"])
        return out

    def answered_kpis(self, owner_name: str) -> set[str]:
        """The KPIs this person has at least one answer for."""
        return self.kpis_by_owner(self.all()).get(owner_name, set())
