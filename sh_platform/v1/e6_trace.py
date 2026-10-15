"""E6a: every agent run leaves one `agent_runs` row, and one trace id follows a piece of work from arrival to pulse.

    with agent_run(plane, viewer, "tally", model_id, "p1", "t1", exception_id=eid) as run:
        run.tool_call()            # counted against the run limit
        run.output = "case://..."  # optional output reference

The row is written when the run starts (status running) and its state columns are updated when it ends
(succeeded or failed, finished_at, tool_calls, cost). An exception is recorded and re-raised, never swallowed.
Workflow table, so state columns may update; the row itself is never deleted.
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

log = logging.getLogger(__name__)
_TRACE: contextvars.ContextVar[str | None] = contextvars.ContextVar("sh_trace_id", default=None)
_LAST: contextvars.ContextVar[str | None] = contextvars.ContextVar("sh_last_trace_id", default=None)
# H1-02: the trace of the latest loop run in this request that did not answer; the rules answer that follows is written on it
_UNANSWERED: contextvars.ContextVar[str | None] = contextvars.ContextVar("sh_unanswered_trace_id", default=None)


def new_trace_id() -> str:
    return "tr-" + uuid.uuid4().hex[:16]


def person_tag(plane, viewer) -> str:
    """A short salted hash of the person (salt per company, kept in context/trace_salt): the only part of a trace id that stands for a person."""
    import hashlib
    import secrets
    from sh_platform.v1 import mem_agent
    path = plane.area("context") / "trace_salt"
    try:
        salt = path.read_text(encoding="utf-8").strip()
    except OSError:
        salt = ""
    if not salt:
        salt = secrets.token_hex(16)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(salt, encoding="utf-8")
        except OSError:
            pass
    return hashlib.sha256(f"{salt}|{mem_agent.who(viewer)}".encode("utf-8")).hexdigest()[:8]


def turn_trace_id(plane, viewer, agent: str) -> str:
    """tr-<agent>-<hashed person>-<random>: one chat turn's trace; never a name."""
    return f"tr-{agent}-{person_tag(plane, viewer)}-{uuid.uuid4().hex[:8]}"


def current_trace_id() -> str | None:
    return _TRACE.get()


def note_last(trace_id: str | None, answered: bool = True) -> None:
    """The loop calls this after every run: the trace id of the latest agent run in this request (ER-09). H1-02: a run that did not answer
    is remembered, so the rules answer given instead lands on the same trace (one turn, one trace) whatever id the caller made up."""
    _LAST.set(trace_id)
    _UNANSWERED.set(None if answered else trace_id)


def last_trace_id() -> str | None:
    return _LAST.get()


def response_trace_id() -> str | None:
    """ER-09: the trace id a chat route returns with its answer: the trace open now, else the latest agent run of this request."""
    return _TRACE.get() or _LAST.get()


def with_trace(body: dict, trace_id: str | None = None) -> dict:
    """`return with_trace({"reply": ...})`: the route's answer with its trace id (GET /api/v1/agent-runs/trace/{trace_id} shows the steps)."""
    out = dict(body)
    out["trace_id"] = trace_id or out.get("trace_id") or response_trace_id()
    return out


@contextmanager
def joined(label: str = ""):
    """NM-7/SS-9: a side call that belongs to the answer just given (the memory proposer, a conversation summary) joins the answer's
    trace instead of starting an unlinked one. Outside any answer it opens a trace of its own."""
    tid = _TRACE.get() or _LAST.get()
    token = _TRACE.set(tid or new_trace_id())
    try:
        yield _TRACE.get()
    finally:
        _TRACE.reset(token)
        if tid:
            _LAST.set(tid)  # the route still returns the answer's trace, not the side call's


def record_rules_answer(plane, agent: str, reason: str, trace_id: str | None = None) -> str:
    """lumen-memory-09 / ER-05: an answer worded by fixed rules (no model) still leaves a trace saying so, under the current trace when there
    is one. `reason`: a short code ("model_off", "egress_blocked", "tile_rule", ...). Returns the trace id for the response."""
    from sh_platform.agents.runs import RunRegistry
    tid = _UNANSWERED.get() or trace_id or response_trace_id() or new_trace_id()
    _UNANSWERED.set(None)  # used once: a later rules answer in the same request is its own
    code = "".join(c for c in str(reason or "rules") if c.isalnum() or c == "_")[:40] or "rules"
    try:
        RunRegistry(plane).record_trace(trace_id=tid, run_id=None, agent=agent, status="done",
                                        steps=[{"kind": "rules", "reason": code}], elapsed_ms=0)
    except Exception:  # noqa: BLE001 - the answer is never lost for a trace
        log.warning("the rules trace could not be kept", exc_info=True)
    _LAST.set(tid)
    return tid


# ---- billing and provider trouble (the Settings banner and the administrator's line in a reply) ---------------------------------------

PROVIDER_OF_HOST = {"openrouter.ai": "OpenRouter", "generativelanguage.googleapis.com": "Google"}
# the provider failures an administrator can fix; a passing outage or rate limit is not worth a line in every reply
TROUBLE_WORDS = {"no_credit": "out of credit", "provider_key_refused": "refusing the access key", "model_unknown": "not offering the model set for a tier"}
_TROUBLE_TAIL = 400  # ponytail: the last 400 egress lines; a provider not called in that window is not reported


def model_trouble(plane) -> dict | None:
    """{code, providers, words, at} when the latest model call to some provider ended in a failure the administrator can fix (out of credit,
    key refused, unknown model), read from the egress log (codes and hosts only); None when every provider's latest call went through."""
    import json
    try:
        lines = (plane.area("context") / "egress_log.jsonl").read_text(encoding="utf-8").splitlines()[-_TROUBLE_TAIL:]
    except OSError:
        return None
    latest: dict[str, dict] = {}
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("kind") == "model" and r.get("host"):
            latest[str(r["host"])] = r  # file order: a failed line follows its sent line, so the last line is the call's outcome
    bad = [(h, r) for h, r in latest.items() if r.get("decision") == "failed" and r.get("reason_code") in TROUBLE_WORDS]
    if not bad:
        return None
    code = bad[-1][1]["reason_code"]
    providers = sorted({PROVIDER_OF_HOST.get(h, h) for h, r in bad if r.get("reason_code") == code})
    return {"code": code, "providers": providers, "at": bad[-1][1].get("time"),
            "words": f"The model account is {TROUBLE_WORDS[code]} ({' / '.join(providers)}); ask the administrator to "
                     + ("top it up." if code == "no_credit" else "check the model settings.")}


OFFLINE_LINE = "The assistant is offline for now; keep typing, your words are kept."


def model_offline_line(plane, viewer) -> str:
    """NM1: the one line a person reads when no model answers (North's reply, the voice button). A company administrator is told why and what
    to do; everyone else is not told about billing."""
    t = None
    if "company_admin" in (getattr(viewer, "roles", None) or ()):
        try:
            t = model_trouble(plane)
        except Exception:  # noqa: BLE001 - a note never costs the answer
            log.warning("the model trouble could not be read", exc_info=True)
    if not t:
        return OFFLINE_LINE
    fix = "Top it up" if t["code"] == "no_credit" else "Check the model settings in Settings"
    return (f"The model account is {TROUBLE_WORDS[t['code']]} ({' / '.join(t['providers'])}). {fix} to get model answers and voice; "
            "until then answers come from rules.")


def model_trouble_note(plane, viewer) -> str | None:
    """The line an agent appends to its model-failure reply for a company administrator ("the OpenRouter account is out of credit"); None
    for anyone else (a participant is not told about billing) and when no provider is in trouble."""
    if "company_admin" not in (getattr(viewer, "roles", None) or ()):
        return None
    try:
        t = model_trouble(plane)
    except Exception:  # noqa: BLE001 - a note never costs the answer
        log.warning("the model trouble could not be read", exc_info=True)
        return None
    if not t:
        return None
    fix = "top it up" if t["code"] == "no_credit" else "check the model settings in Settings"
    return (f"Note for the administrator: the {' and '.join(t['providers'])} model account is {TROUBLE_WORDS[t['code']]}, so the agents "
            f"cannot reach the model; {fix} and they answer again.")


@contextmanager
def trace(trace_id: str | None = None):
    """Make `trace_id` (or a new one) the current correlation id; runs, cases and pulse items opened inside carry it.
    H1-02: inside a trace already open (a chat route that hands the turn to the company talk) the open one is kept, so one turn has one
    trace: the failed loop and the rules answer after it are never split over two ids."""
    token = _TRACE.set(_TRACE.get() or trace_id or new_trace_id())
    try:
        yield _TRACE.get()
    finally:
        _TRACE.reset(token)


class Run:
    def __init__(self, run_id: str, trace_id: str):
        self.id, self.trace_id, self.tool_calls, self.output = run_id, trace_id, 0, None

    def tool_call(self, n: int = 1) -> None:
        self.tool_calls += n


def _user_uuid(plane, account_id) -> str | None:
    """acting_for_user_id is a UUID; an account id that is not one maps to a fixed uuid5 under this company."""
    if not account_id:
        return None
    try:
        return str(uuid.UUID(str(account_id)))
    except ValueError:
        return str(uuid.uuid5(uuid.UUID(org_id(plane)), str(account_id)))


def _when(text) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def router_cost(plane, agent_type: str, start: datetime, end: datetime) -> float | None:
    """Sum `cost_usd` of the router cost-log rows for this agent during the run. None when the log has no price (it holds tokens today)."""
    from sh_platform.v1 import router
    total, seen = 0.0, False
    for r in router.costs(plane)["rows"]:  # the last 50 rows are plenty for one run
        at = _when(r.get("at"))
        if r.get("agent") == agent_type and at and start <= at <= end and r.get("cost_usd") is not None:
            total, seen = total + float(r["cost_usd"]), True
    return round(total, 6) if seen else None


@contextmanager
def agent_run(plane, viewer, agent_type: str, model_id: str, prompt_version: str, tool_policy_version: str,
              exception_id: str | None = None, decision_intent_id: str | None = None):
    run = Run(wh.new_id(), current_trace_id() or new_trace_id())
    started = wh.now()
    with wh.connect(plane) as con:
        con.execute(
            "insert into agent_runs (id, organization_id, decision_intent_id, exception_id, acting_for_user_id, agent_type, model_id,"
            " prompt_version, tool_policy_version, started_at, run_status, tool_calls, trace_id) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [run.id, org_id(plane), decision_intent_id, exception_id, _user_uuid(plane, getattr(viewer, "account_id", None)), agent_type, model_id,
             prompt_version, tool_policy_version, started, "running", 0, run.trace_id])
    token = _TRACE.set(run.trace_id)  # work done inside the run shares its trace
    status = "failed"
    try:
        yield run
        status = "succeeded"
    except Exception:
        log.warning("agent run %s (%s) failed", run.id, agent_type)
        raise
    finally:
        _TRACE.reset(token)
        end = wh.now()
        try:
            cost = router_cost(plane, agent_type, started, end)
        except Exception:  # the cost log is optional; the run row still closes
            log.warning("no cost for agent run %s", run.id, exc_info=True)
            cost = None
        with wh.connect(plane) as con:
            con.execute("update agent_runs set finished_at=?, run_status=?, tool_calls=?, cost_usd=?, output_artifact_uri=? where id=?",
                        [end, status, run.tool_calls, cost, run.output, run.id])


# Runs keep the name they were recorded under; older names are shown as the agent that does that work now (North, Span, Lumen, Tally).
AGENT_OF = {"investigation": "tally", "intake": "span", "identity_match": "span", "data": "span", "flow": "span",
            "briefing": "lumen", "consumer": "lumen"}


def agent_of(agent_type: str | None) -> str | None:
    return AGENT_OF.get(agent_type or "", agent_type)


_KEYS = ("id", "agent_type", "model_id", "status", "started_at", "finished_at", "tool_calls", "cost_usd", "trace_id", "exception_id",
         "acting_for_user_id")


def summary(plane, day: str | None = None, agent_type: str | None = None) -> dict:
    """Runs by agent and day with cost and failures, plus the runs themselves (newest first, up to 200)."""
    where, args = ["organization_id = ?"], [org_id(plane)]
    if day:
        where.append("cast(started_at as date) = cast(? as date)")
        args.append(day)
    if agent_type:
        names = [agent_type] + [k for k, v in AGENT_OF.items() if v == agent_type]
        where.append(f"agent_type in ({', '.join('?' * len(names))})")
        args.extend(names)
    w = " and ".join(where)
    with wh.connect(plane, read_only=True) as con:
        groups = con.execute(
            f"select agent_type, strftime(cast(started_at as date), '%Y-%m-%d'), count(*), sum(case when run_status='failed' then 1 else 0 end),"
            f" sum(coalesce(tool_calls,0)), sum(cost_usd) from agent_runs where {w} group by 1,2 order by 2 desc, 1", args).fetchall()
        runs = con.execute(
            f"select id, agent_type, model_id, run_status, started_at, finished_at, tool_calls, cost_usd, trace_id, exception_id,"
            f" acting_for_user_id from agent_runs where {w} order by started_at desc limit 200", args).fetchall()

    def cell(k, v):
        return v.isoformat() if isinstance(v, datetime) else float(v) if k == "cost_usd" and v is not None else v

    days: dict[tuple, dict] = {}
    for a, d, n, f, t, c in groups:
        row = days.setdefault((agent_of(a), d), {"agent_type": agent_of(a), "day": d, "runs": 0, "failures": 0, "tool_calls": 0, "cost_usd": None})
        row["runs"], row["failures"], row["tool_calls"] = row["runs"] + n, row["failures"] + f, row["tool_calls"] + t
        if c is not None:
            row["cost_usd"] = (row["cost_usd"] or 0.0) + float(c)
    out = [{k: cell(k, v) for k, v in zip(_KEYS, r)} for r in runs]
    for r in out:
        r["agent_type"] = agent_of(r["agent_type"])
    # RC2-4: the agents' chat turns (loop traces in run_steps.jsonl) count in the day table too, with their tool calls and cost; before this
    # the table held only the warehouse's pipeline runs and read "Span, 6 runs, cost not available" after 39 priced chat turns
    for t in loop_traces(plane, limit=100_000):
        a, d = agent_key(t.get("agent")), str(t.get("at") or "")[:10]
        if not d or (day and d != str(day)[:10]) or (agent_type and a != agent_of(agent_type)):
            continue
        row = days.setdefault((a, d), {"agent_type": a, "day": d, "runs": 0, "failures": 0, "tool_calls": 0, "cost_usd": None})
        row["runs"] += 1
        row["failures"] += 0 if t.get("outcome") == "done" else 1
        row["tool_calls"] += int(t.get("tool_calls") or 0)
        if t.get("cost_usd") is not None:
            row["cost_usd"] = round((row["cost_usd"] or 0.0) + float(t["cost_usd"]), 6)
    return {"by_agent_day": sorted(days.values(), key=lambda r: (r["day"], r["agent_type"]), reverse=True), "runs": out}


_SIDE = (" summary", " memory")  # NM2-7, RC2-5: the memory side calls that join an answer's trace ("North summary", "Tally memory")


def agent_key(label) -> str:
    """'North', 'North summary', 'Tally memory' -> 'north' / 'tally'; an old run name maps to the agent doing that work now."""
    first = (str(label or "").strip().lower().split() or [""])[0]
    return agent_of(first) or first


def _side(label) -> bool:
    return str(label or "").lower().endswith(_SIDE)


def people(plane) -> dict[str, str]:
    """lumen-memory-c1-06: person tag (the hashed part of a chat turn's trace id) -> display name, for this company's accounts. Read only by
    the administrator's runs list; the trace itself never holds a name."""
    import json
    from types import SimpleNamespace
    try:
        accounts = json.loads((plane.root.parent / "_control" / "accounts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for a in accounts if isinstance(accounts, list) else []:
        if isinstance(a, dict) and a.get("company_id") == plane.company_id and a.get("account_id"):
            out[person_tag(plane, SimpleNamespace(account_id=a["account_id"]))] = str(a.get("display_name") or "")
    return out


def by_trace(plane, trace_id: str) -> list[dict]:
    """The runs of one trace: warehouse run rows, and (RC-9) one row per loop run kept in run_steps.jsonl (chat turns, memory calls)."""
    try:
        rows = [r for r in summary(plane)["runs"] if r["trace_id"] == trace_id]
    except Exception:  # noqa: BLE001 - a busy warehouse still shows the loop runs
        log.warning("agent runs could not be read for a trace", exc_info=True)
        rows = []
    for r in steps_for(plane, trace_id):
        st = [s for s in r.get("steps") or [] if isinstance(s, dict)]
        prices = [float(s["cost_usd"]) for s in st if s.get("cost_usd") is not None]
        rows.append({"id": r.get("run_id"), "agent_type": r.get("agent"), "status": r.get("status"), "started_at": r.get("at"),
                     "elapsed_ms": r.get("elapsed_ms"), "steps": len(st), "tool_calls": sum(1 for s in st if s.get("kind") == "tool"),
                     "cost_usd": round(sum(prices), 6) if prices else None, "trace_id": trace_id, "kind": "loop",
                     "worded_by": "rules" if any(s.get("kind") == "rules" for s in st) else "model"})
    return rows


def steps_for(plane, trace_id: str) -> list[dict]:
    """The per-step records of every loop run on this trace (model calls with tier and tokens, tool calls, the number guard)."""
    import json
    from sh_platform.agents.runs import STEPS_FILE
    out = []
    try:
        for line in (plane.area("context") / STEPS_FILE).read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("trace_id") == trace_id:
                out.append(r)
    except OSError:
        pass
    return out


def loop_traces(plane, limit: int = 100, agent: str | None = None, offset: int = 0) -> list[dict]:
    """One row per trace kept in run_steps.jsonl (chat turns of North, Span, Lumen, Tally; a memory call that joined an answer is part of
    its row), newest first: agent, when, steps, tokens, cost, ms, outcome, worded by model or rules. RC-10: filter by agent, page by offset."""
    import json
    from sh_platform.agents.runs import STEPS_FILE
    rows = []
    try:
        lines = (plane.area("context") / STEPS_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or not r.get("trace_id"):
            continue
        st = [s for s in r.get("steps") or [] if isinstance(s, dict)]
        prices = [float(s["cost_usd"]) for s in st if s.get("cost_usd") is not None]
        tokens = sum(int(s.get("tokens_in") or 0) + int(s.get("tokens_out") or 0) for s in st)
        cost = sum(prices) if prices else None
        rows.append({"trace_id": r["trace_id"], "agent": r.get("agent"), "at": r.get("at"), "steps": len(st), "tokens": tokens,
                     "cost_usd": round(cost, 6) if cost is not None else None, "ms": r.get("elapsed_ms"), "outcome": r.get("status"),
                     "worded_by": "rules" if any(s.get("kind") == "rules" for s in st) else "model",
                     "estimated": any(s.get("estimated") for s in st), "tool_calls": sum(1 for s in st if s.get("kind") == "tool")})
    merged: dict[str, dict] = {}
    for r in rows[::-1]:  # newest first (file order); one line per trace: a memory call under the same trace adds to its answer's line
        m = merged.get(r["trace_id"])
        if m is None:
            merged[r["trace_id"]] = dict(r, runs=1)
            continue
        if _side(m["agent"]) and not _side(r["agent"]):
            # NM2-7, RC2-5: the line is the agent's answer, not the summary written after it (the newest run of the trace)
            m.update(agent=r["agent"], outcome=r["outcome"])
        m.update(steps=m["steps"] + r["steps"], tokens=m["tokens"] + r["tokens"], ms=(m["ms"] or 0) + (r["ms"] or 0), runs=m["runs"] + 1,
                 cost_usd=None if m["cost_usd"] is None and r["cost_usd"] is None else round((m["cost_usd"] or 0) + (r["cost_usd"] or 0), 6),
                 estimated=m["estimated"] or r["estimated"], worded_by="rules" if "rules" in (m["worded_by"], r["worded_by"]) else "model",
                 tool_calls=m["tool_calls"] + r["tool_calls"])
    out = list(merged.values())
    names = people(plane) if out else {}
    for r in out:  # c1-06: who asked (tr-<agent>-<person tag>-<random>), so an administrator can find the trace of a given answer
        parts = str(r["trace_id"]).split("-")
        r["person"] = names.get(parts[2]) if len(parts) == 4 else None
    if agent:
        want = agent.strip().lower()
        out = [r for r in out if agent_key(r.get("agent")) == want or agent_of(str(r.get("agent") or "").lower()) == want]
    return out[max(0, offset):max(0, offset) + limit]
