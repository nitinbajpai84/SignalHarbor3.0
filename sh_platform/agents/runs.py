"""Run registry: one JSON line per run in the company's own plane. No prompts, answers, names or figures."""
import json
import uuid
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for
from sh_platform.plane import CompanyPlane

STEPS_FILE = "run_steps.jsonl"
STATUSES = ("done", "refused", "could_not_finish", "error")


class RunRegistry:
    def __init__(self, plane: CompanyPlane):
        self._file = plane.area("context") / "run_registry.jsonl"
        self._steps = plane.area("context") / STEPS_FILE

    def record(self, *, agent: str, module_id: str, started: str, finished: str, status: str,
               steps: int, tools_called: list[str], numbers_replaced: int, refusals: list[dict] | None = None) -> str:
        if status not in STATUSES:
            raise ValueError("unknown run status")
        row = {"run_id": uuid.uuid4().hex, "agent": agent, "module_id": module_id,
               "started": started, "finished": finished, "status": status, "steps": steps,
               "tools_called": list(tools_called), "numbers_replaced": numbers_replaced}
        if refusals:  # SF14c: {tool, reason} codes only, never argument values
            row["refusals"] = [{"tool": str(r["tool"]), "reason": str(r["reason"])} for r in refusals]
        with lock_for(self._file), self._file.open("a", encoding="utf-8") as f:  # the same lock as the retention purge
            f.write(json.dumps(row) + "\n")
        return row["run_id"]

    def record_trace(self, *, trace_id: str, run_id: str | None, agent: str, status: str, steps: list[dict], elapsed_ms: int) -> None:
        """The steps of one run (tool names, argument keys, sizes, tiers, tokens, times, guard result): no prompt, answer, name or figure."""
        row = {"trace_id": trace_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": run_id, "agent": agent, "status": status, "elapsed_ms": elapsed_ms, "steps": steps}
        self._steps.parent.mkdir(parents=True, exist_ok=True)
        with lock_for(self._steps), self._steps.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
