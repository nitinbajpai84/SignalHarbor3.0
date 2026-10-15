"""Harbor skills (docs/v3/SKILLS-CATALOGUE.md; contract in docs/v3/HARBOR-SPEC.md, "Added 15 Oct").

A skill is a folder `skills/<id>/` (SKILL.md + optional tests.jsonl). An office's own folder `<company>/skills/<id>/` overrides the core one of the
same id. Usage is one line per call in `<company>/v3/skill_runs.jsonl`. `write_skill` drafts an office skill (status waiting) once a person has had
to step in twice for the same kind of work; a person admits it (signed, version + 1) or rejects it."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml

from sh_platform.v1.skill_loader import SKILLS_DIR

log = logging.getLogger(__name__)
LOCK = threading.RLock()
LISTS = {"steps": "Steps", "tools": "Tools", "checks": "Checks", "never": "Never"}
TEXTS = {"inputs": "Inputs", "output": "Output"}
EDITABLE = {"name", "goal", "when", "why", *LISTS, *TEXTS}
NO_TEST = "no automatic test"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ok_id(sid: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+\.[a-z0-9-]+", sid or ""))


# ---- files --------------------------------------------------------------------------------------------------------------------------

def _folder(plane, sid: str) -> Path | None:
    """The folder that holds this skill: the office's first, else the core one."""
    if not _ok_id(sid):
        return None
    for d in ((plane.path("skills", sid) if plane is not None else None), SKILLS_DIR / sid):
        if d is not None and (d / "SKILL.md").is_file():
            return d
    return None


def parse(text: str) -> dict:
    """SKILL.md -> front matter keys plus inputs, output (text) and steps, tools, checks, never (lists)."""
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.S)
    meta = yaml.safe_load(m.group(1)) if m else {}
    meta = meta if isinstance(meta, dict) else {}
    sections: dict[str, list[str]] = {}
    cur = None
    for line in (m.group(2) if m else text).splitlines():
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            sections[cur] = []
        elif cur is not None and line.strip():
            sections[cur].append(line.strip())
    for key, title in LISTS.items():
        meta[key] = [re.sub(r"^(?:[-*]|\d+\.)\s+", "", s) for s in sections.get(title.lower(), [])]
    for key, title in TEXTS.items():
        meta[key] = " ".join(sections.get(title.lower(), []))
    return meta


def dump(meta: dict) -> str:
    """The SKILL.md text for a skill dict (front matter values as JSON, which is valid YAML)."""
    skip = {*LISTS, *TEXTS}
    head = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items() if k not in skip and v is not None]
    body = [f"# {meta.get('name') or meta.get('id')}", ""]
    for key, title in TEXTS.items():
        body += [f"## {title}", str(meta.get(key) or ""), ""]
    for key, title in LISTS.items():
        items = meta.get(key) or []
        body += [f"## {title}", *([f"{i}. {s}" for i, s in enumerate(items, 1)] if key == "steps" else [f"- {s}" for s in items]), ""]
    return "\n".join(["---", *head, "---", "", *body])


def read_tests(plane, sid: str) -> list[dict]:
    d = _folder(plane, sid)
    p = d / "tests.jsonl" if d else None
    if not p or not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---- the checks a skill can be tried against (plain code, no model) -------------------------------------------------------------------

def _same_bytes(i: dict) -> str:
    return "yes" if hashlib.sha256(str(i["a"]).encode()).digest() == hashlib.sha256(str(i["b"]).encode()).digest() else "no"


CHECKS: dict[str, Callable[[dict], str]] = {
    "data.detect-duplicate": _same_bytes,
    "run.load-file": lambda i: "ok" if i["rows_in"] == i["rows_out"] else "fail",
    "intent.sign": lambda i: "ok" if i["clicked"] == i["signed"] else "fail",
    "consume.answer-from-cache": lambda i: "hit" if i["cached_version"] == i["current_version"] else "miss",
}


def try_(plane, sid: str) -> dict:
    """Run tests.jsonl through the skill's check function. No check function or no tests: "no automatic test"."""
    fn, tests = CHECKS.get(sid), read_tests(plane, sid)
    if fn is None or not tests:
        return {"ok": None, "message": NO_TEST, "tests": [], "passed": 0, "total": 0}
    out = []
    for t in tests:
        try:
            got = fn(t["input"])
        except Exception as e:  # noqa: BLE001 - a bad test row fails that row only
            got = f"error: {e}"[:80]
        out.append({"input": t["input"], "expected": t["expected"], "got": got, "ok": got == t["expected"]})
    passed = sum(o["ok"] for o in out)
    return {"ok": passed == len(out), "message": f"{passed} of {len(out)} passed", "tests": out, "passed": passed, "total": len(out)}


# ---- usage log ---------------------------------------------------------------------------------------------------------------------

def _runs_path(plane) -> Path:
    p = plane.path("v3", "skill_runs.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def runs(plane, thread: str | None = None) -> list[dict]:
    p = _runs_path(plane)
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if thread is None or r.get("thread") == thread:
            rows.append(r)
    return rows


def _log_run(plane, thread_id: str | None, sid: str, ms: int, ok: bool, detail: str) -> None:
    try:
        with LOCK, _runs_path(plane).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": _now(), "skill": sid, "thread": thread_id, "ms": ms, "ok": ok, "detail": str(detail or "")[:300]}) + "\n")
    except Exception:  # noqa: BLE001 - the log never breaks the work it records
        log.warning("skill run not logged: %s", sid, exc_info=True)


@contextmanager
def _timed(plane, thread_id: str | None, sid: str) -> Iterator[dict]:
    rec: dict[str, Any] = {"detail": ""}
    t0, ok = time.perf_counter(), True
    try:
        yield rec
    except BaseException as e:
        ok = False
        rec["detail"] = rec.get("detail") or str(getattr(e, "text", e))[:300]
        raise
    finally:
        _log_run(plane, thread_id, sid, int((time.perf_counter() - t0) * 1000), ok, rec.get("detail") or "")


def record(plane, thread_id: str | None, skill_id: str, fn: Callable[[], Any] | None = None):
    """Time one piece of work and log it. `with record(...) as rec:` (set rec["detail"]) or `record(..., fn)` which calls fn() and returns its
    result (a text result becomes the detail). A raised error is logged as not ok and raised again."""
    if fn is None:
        return _timed(plane, thread_id, skill_id)
    with _timed(plane, thread_id, skill_id) as rec:
        out = fn()
        if isinstance(out, str):
            rec["detail"] = out
        return out


# ---- reading -----------------------------------------------------------------------------------------------------------------------

def ids(plane=None) -> list[str]:
    core = [p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and _ok_id(p.name) and (p / "SKILL.md").is_file()]
    mine = []
    if plane is not None and plane.path("skills").is_dir():
        mine = [p.name for p in plane.path("skills").iterdir() if p.is_dir() and _ok_id(p.name) and (p / "SKILL.md").is_file()]
    return sorted({*core, *mine})


def _row(plane, sid: str, meta: dict, used: dict[str, int]) -> dict:
    hist = meta.get("history") or []
    t = try_(plane, sid) if sid in CHECKS else None
    last = hist[-1] if hist else None
    return {"id": sid, "name": meta.get("name") or sid, "goal": meta.get("goal") or "", "when": meta.get("when") or "", "centre": meta.get("centre") or "",
            "source": meta.get("source") or "core", "tier": meta.get("tier") or "fast", "version": int(meta.get("version") or 0),
            "status": meta.get("status") or "in_use", "tested": {"passed": t["passed"], "total": t["total"]} if t and t["total"] else None,
            "used": used.get(sid, 0), "last_changed": {"by": last.get("by"), "at": last.get("at")} if last else None}


def _used(plane) -> dict[str, int]:
    month, out = _now()[:7], {}
    for r in runs(plane):
        if str(r.get("at", ""))[:7] == month:
            out[r["skill"]] = out.get(r["skill"], 0) + 1
    return out


def _meta(plane, sid: str) -> dict | None:
    d = _folder(plane, sid)
    return parse((d / "SKILL.md").read_text(encoding="utf-8")) if d else None


def name_of(plane, sid: str) -> str:
    try:
        return (_meta(plane, sid) or {}).get("name") or sid
    except Exception:  # noqa: BLE001
        return sid


def listing(plane, status: str | None = None) -> list[dict]:
    used, out = _used(plane), []
    for sid in ids(plane):
        meta = _meta(plane, sid)
        if meta and (status is None or meta.get("status", "in_use") == status):
            out.append(_row(plane, sid, meta, used))
    return out


def waiting(plane) -> list[dict]:
    return listing(plane, "waiting")


def read(plane, sid: str) -> dict:
    """The row plus the sections, history and (for a drafted skill) why and evidence; tests with their results where there is a check."""
    meta = _meta(plane, sid)
    if meta is None:
        raise KeyError(sid)
    out = {**_row(plane, sid, meta, _used(plane)), **{k: meta[k] for k in (*TEXTS, *LISTS)},
           "history": meta.get("history") or [{"v": int(meta.get("version") or 1), "at": "", "by": "Signal Harbor", "change": "Core skill"}]}
    for k in ("why", "evidence"):
        if meta.get(k):
            out[k] = meta[k]
    t = try_(plane, sid)
    if t["tests"]:
        out["tests"] = t["tests"]
    return out


# ---- writing: office skills only ------------------------------------------------------------------------------------------------------

def _save(plane, meta: dict) -> None:
    d = plane.path("skills", meta["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(dump(meta), encoding="utf-8", newline="\n")


def _mine(plane, sid: str) -> dict:
    """The office copy of a waiting skill (the only kind a person edits, admits or rejects)."""
    meta = parse(plane.path("skills", sid, "SKILL.md").read_text(encoding="utf-8")) if _ok_id(sid) and plane.path("skills", sid, "SKILL.md").is_file() else None
    if meta is None:
        raise KeyError(sid)
    if meta.get("status") != "waiting":
        raise ValueError("Only a skill that is waiting for a person can be changed.")
    return meta


def _hist(meta: dict, by: str, change: str, version: int | None = None) -> None:
    meta["history"] = [*(meta.get("history") or []), {"v": version if version is not None else int(meta.get("version") or 0), "at": _now(), "by": by, "change": change}]
    meta["changed_by"], meta["changed_at"] = by, meta["history"][-1]["at"]


def edit(plane, sid: str, field: str, value: Any, by: str) -> dict:
    if field not in EDITABLE:
        raise ValueError("That part of a skill cannot be edited here.")
    with LOCK:
        meta = _mine(plane, sid)
        if field in LISTS:
            meta[field] = [str(s).strip() for s in (value if isinstance(value, list) else str(value or "").splitlines()) if str(s).strip()]
        else:
            meta[field] = str(value or "").strip()
        _hist(meta, by, f"Edited {field}")
        _save(plane, meta)
    return read(plane, sid)


def admit(plane, sid: str, by: str) -> dict:
    """Signed in the person's display name: version + 1, status in_use, one history line."""
    with LOCK:
        meta = _mine(plane, sid)
        meta["version"], meta["status"], meta["signed_by"] = int(meta.get("version") or 0) + 1, "in_use", by
        _hist(meta, by, "Admitted", meta["version"])
        _save(plane, meta)
    return read(plane, sid)


def reject(plane, sid: str, reason: str, by: str) -> dict:
    with LOCK:
        meta = _mine(plane, sid)
        meta["status"] = "retired"
        _hist(meta, by, "Rejected" + (f": {reason.strip()[:200]}" if reason and reason.strip() else ""))
        _save(plane, meta)
    return read(plane, sid)


# ---- harbor.write-skill ------------------------------------------------------------------------------------------------------------

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48].strip("-")


def skill_id_for(kind: str) -> str:
    return "office." + (_slug(re.sub(r"^file:", "read-", kind)) or "step")


def _template(kind: str) -> dict:
    label = re.sub(r"^file:", "files from ", kind)
    return {"name": label[:1].upper() + label[1:], "goal": f"Do what a person did each time this came up: {label}",
            "when": f"Use when the same situation as {label} comes up again",
            "steps": ["Recognise the same situation as in the evidence.", "Apply the answer people gave before, shown in the evidence.",
                      "If anything differs from the evidence, ask a person."],
            "checks": ["The result matches the answer given in every piece of evidence."]}


def _clean(d: dict | None) -> dict | None:
    """A model draft is used only if it is complete and holds no digit (a skill holds method, never figures)."""
    if not isinstance(d, dict):
        return None
    try:
        out: dict[str, Any] = {k: str(d[k]).strip()[:200] for k in ("name", "goal", "when")}
        out.update({k: [str(s).strip()[:200] for s in d[k]][:5] for k in ("steps", "checks")})
    except (KeyError, TypeError):
        return None
    flat = " ".join([*(out[k] for k in ("name", "goal", "when")), *out["steps"], *out["checks"]])
    return out if out["name"] and out["steps"] and out["checks"] and not re.search(r"\d", flat) else None


ASK = 'Reply with JSON only: {"name": "...", "goal": "one line", "when": "one line", "steps": ["2 to 4 short lines"], "checks": ["1 to 2 lines"]}'
SYSTEM = ("You are Harbor writing a small skill from steps people had to do by hand more than once. "
          "Describe the method only. Never write a digit or a figure.")


def _model_draft(plane, kind: str, evidence: list[dict]) -> dict | None:
    """The strong tier drafts the skill through the router. None when no model is available or the reply is unusable."""
    try:
        from sh_platform.agents.loop import run_agent
        from sh_platform.agents.registry import ToolRegistry
        from sh_platform.agents.runs import RunRegistry
        from sh_platform.build.agents.runtime import OpenGate, runtime_for_plane
        from sh_platform.v1.egress_fit import fit
        from sh_platform.v1.router import route
        model = runtime_for_plane(plane).model
        if model is None:
            return None
        model = route(model, "north", "design_approval", "", plane, want_json=True)  # design_approval is a strong-tier (manager) task
        ctx = fit({"kind_of_step": kind, "what_people_did": " | ".join(re.sub(r"\d", "#", str(e.get("text") or "")) for e in evidence)[:1500]})
        res = run_agent(model, ToolRegistry(OpenGate()), plane.company_id, "m1_intent", "Harbor", SYSTEM, ctx, ASK, recorder=RunRegistry(plane))
        a, b = res.text.find("{"), res.text.rfind("}")
        return _clean(json.loads(res.text[a:b + 1])) if res.status == "done" and 0 <= a < b else None
    except Exception:  # noqa: BLE001 - no model, or it failed: the plain template is used
        log.warning("the skill draft model call failed; the template is used", exc_info=True)
        return None


def write_skill(plane, thread: dict, kind: str, evidence: list[dict]) -> dict | None:
    """harbor.write-skill. When a person has stepped in twice for the same kind of work (entries in `thread["learn"]`, across this office's
    threads), draft an office skill with status waiting. Returns the row, or None when it is not yet the second time. Never raises."""
    try:
        from sh_platform.v1 import v3_harbor as H
        seen: dict[tuple, dict] = {}
        for t in [thread, *(t for t in H.all_threads(plane) if t["id"] != thread["id"])]:
            for e in t.get("learn") or []:
                if e.get("kind") == kind:
                    seen[(t["id"], e.get("at"), e.get("text"))] = {"at": e.get("at"), "text": e.get("text")}
        for e in evidence or []:
            seen.setdefault((thread["id"], e.get("at"), e.get("text")), {"at": e.get("at"), "text": e.get("text")})
        found = sorted(seen.values(), key=lambda e: str(e["at"]))
        sid = skill_id_for(kind)
        if len(found) < 2 or _folder(plane, sid) is not None:
            return None
        draft = _model_draft(plane, kind, found) or _template(kind)
        meta = {"id": sid, "name": draft["name"], "goal": draft["goal"], "when": draft["when"], "centre": "build", "source": "office", "tier": "fast",
                "version": 0, "status": "waiting", "from": "harbor.write-skill",
                "why": f"A person had to step in {len(found)} times for the same kind of work: {kind}.",
                "evidence": [{"at": e["at"], "text": str(e["text"])[:300]} for e in found[-5:]],
                "inputs": "The step Harbor could not settle on its own.", "output": "The answer a person gave before, applied again.",
                "steps": draft["steps"], "tools": [], "checks": draft["checks"],
                "never": ["Never invent a figure, name or rule that is not in the inputs.", "Never act before a person has admitted this skill."]}
        _hist(meta, "Harbor", "Drafted from repeated steps", 0)
        with LOCK:
            _save(plane, meta)
        return read(plane, sid)
    except Exception:  # noqa: BLE001 - learning is best effort and never breaks the chain
        log.warning("write-skill failed for %s", kind, exc_info=True)
        return None
