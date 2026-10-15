"""build/alerts.json: the Ops alerts, kept so the same alert keeps its id and state across days.
Shape: {"alerts": [{"id", "kind", "source", "measure", "owner", "opened", "state": "open|acknowledged|closed", "by", "at", "note"}]}."""
import logging
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
STATES = {"ack": "acknowledged", "close": "closed"}


def _path(plane):
    return plane.path("build", "alerts.json")


def _read(plane) -> list[dict]:
    try:
        data = read_json_strict(_path(plane), dict)
    except (OSError, ValueError) as e:
        log.warning("alerts.json unreadable: %s", type(e).__name__)
        return []
    return [a for a in (data or {}).get("alerts") or [] if isinstance(a, dict)]


def sync(plane, derived: list[dict], today: str) -> list[dict]:
    """Today's derived alerts (each with id, kind, source, measure, owner) joined to the stored ones by id. A stored alert keeps its
    state and note; one whose cause has cleared is dropped, so a new occurrence opens fresh. Returns the stored records, closed included."""
    derived = list({d["id"]: d for d in derived}.values())  # one alert per id, or the stored copy never matches and the file is rewritten every read
    with lock_for(_path(plane)):
        old = {a.get("id"): a for a in _read(plane)}
        out = []
        for d in derived:
            rec = old.get(d["id"]) or {"opened": today, "state": "open", "by": None, "at": None, "note": None}
            out.append({**rec, **{k: d.get(k) for k in ("id", "kind", "source", "measure", "owner", "change_id", "tell")}})  # 59
        if out != list(old.values()):
            write_json_atomic(_path(plane), {"alerts": out})
        return out


def act(plane, alert_id: str, action: str, by: str, note: str | None) -> dict | None:
    """Acknowledge ('ack') or close ('close') one alert; None when there is no such alert."""
    with lock_for(_path(plane)):
        items = _read(plane)
        hit = next((a for a in items if a.get("id") == alert_id), None)
        if hit is None:
            return None
        hit.update(state=STATES[action], by=by, at=datetime.now(timezone.utc).isoformat(), note=note)
        write_json_atomic(_path(plane), {"alerts": items})
        return hit
