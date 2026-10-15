"""BC-5: today's plan from the contracts (SHAPES 3) and the run log (SHAPES 4). Pure functions; the runner does the work."""
import re
from datetime import datetime

LATE_NOTE = "No file has landed for this source yet."


def due_at(expected: str, now: datetime) -> datetime | None:
    """'D+2 09:00' is read as 09:00 today: the contract does not say which data day a file is for, so the time of day is what is checked."""
    m = re.fullmatch(r"D\+\d+\s+(\d{1,2}):(\d{2})", (expected or "").strip())
    return now.replace(hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0) if m else None


def is_placeholder(run: dict) -> bool:
    """The 'late' entry written when nothing had landed: no rows, never loaded."""
    return run.get("status") == "late" and not run.get("rows") and LATE_NOTE in (run.get("notes") or [])


def today_runs(runs: list[dict], source: str, today) -> list[dict]:
    return [r for r in runs if r.get("source") == source and str(r.get("started", ""))[:10] == today.isoformat()]


def ok_today(runs: list[dict], source: str, today) -> bool:
    """ok, or loaded late (marts ready): a file that arrived after its time still gave the dependants their data."""
    return any(r.get("status") == "ok" or (r.get("status") == "late" and r.get("marts_ready")) for r in today_runs(runs, source, today))


def state_of(c: dict, runs: list[dict], now: datetime, has_file: bool) -> str:
    """ok, failed or late (a run today); due (past its time, file here, no run yet); late (past its time, no file); waiting."""
    real = [r for r in today_runs(runs, c["source"], now.date()) if not is_placeholder(r)]
    if real:
        return real[-1]["status"]
    due = due_at(c["expected"], now)
    if due is None or now < due:
        return "waiting"
    return "due" if has_file else "late"


def order(contracts: list[dict]) -> list[dict]:
    """Dependencies first. A cycle or an unknown dependency does not loop: what is left goes last, and the runner refuses it in words."""
    names, out, left = {c["source"] for c in contracts}, [], list(contracts)
    while left:
        done = {c["source"] for c in out}
        ready = [c for c in left if all(d in done or d not in names for d in c["depends_on"])] or left[:1]
        out.append(ready[0])
        left.remove(ready[0])
    return out
