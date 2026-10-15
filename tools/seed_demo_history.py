"""Six months of illustrative operating history for one company (synthetic only). Follows packs/family_office/1/demo_journey/history.yaml.

Usage: python tools/seed_demo_history.py <company_id> [--from 2026-04-01] [--to 2026-09-30] [--reset] [--data-root PATH]
Writes through the stores: the run log (SHAPES 4) under its lock, build/alerts.json through sh_platform.build.alerts, map versions through
append_version, comments in the comment route's shape, Nira's messages through messages.draft, memory through remember() (so the filters run)
and model-call lines in the egress log (counts only). The stores stamp the time themselves, so each write runs under a pinned clock.
Dates are the only thing that varies by month; nothing is random. A manifest (build/demo_history.json) lists what was written; a second
run removes it first, so running twice gives the same files. --reset only removes. People are found in the profile by role, never named here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform import memory  # noqa: E402
from sh_platform.build import alerts, contracts  # noqa: E402
from sh_platform.build.runner import _deadline, _runs_path, read_runs  # noqa: E402
from sh_platform.graph import comments, versions  # noqa: E402
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile import store  # noqa: E402
from sh_platform.profile.view import _v  # noqa: E402
from sh_platform.pulse import messages  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402

log = logging.getLogger(__name__)
HISTORY = ROOT / "packs" / "family_office" / "1" / "demo_journey" / "history.yaml"
COMPANIES = ROOT / "local" / "companies.yaml"
PREFIX, CONV, UTC = "hist-", "history/", timezone.utc
EMPTY_RULE = re.compile(r"empty|null|missing|blank|complete")


@contextmanager
def clock(at: datetime):
    """The stores call now(); pin it to the history's date for the writes inside."""
    s = at.isoformat(timespec="seconds")
    pinned = type("Pinned", (datetime,), {"now": classmethod(lambda cls, tz=None: at)})
    with patch.object(alerts, "datetime", pinned), patch.object(versions, "_now", lambda: s), patch.object(comments, "_now", lambda: s), \
            patch.object(messages, "_now", lambda: s), patch.object(memory, "_now", lambda: at.isoformat(timespec="microseconds")):
        yield


def iso(t: datetime) -> str:
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).isoformat(timespec="seconds")


def on(month: date, day: int, hour: int = 9) -> datetime:
    return datetime(month.year, month.month, day, hour, tzinfo=UTC)


class People:
    """Names by role from the company's profile, kept to the people listed for the company in local/companies.yaml when it lists them."""

    def __init__(self, plane, company_id: str, companies_file: Path):
        self.plane, self.doc = plane, store.raw(plane)["people"]
        try:
            listed = yaml.safe_load(companies_file.read_text(encoding="utf-8")) or {}
        except OSError:
            listed = {}
        co = next((c for c in listed.get("companies") or [] if c.get("id") == company_id), None)
        self.listed = {p.get("name") for p in co.get("people") or []} if co else None

    def _ok(self, name) -> bool:
        return bool(name) and (self.listed is None or name in self.listed)

    def who(self, role: str) -> tuple[str | None, str]:
        """(profile id, name). Steward: versions.steward; an owner_of:<code> owns an item starting with the code. Else the organiser."""
        if role == "steward":
            name = versions.steward(self.plane, [])
            pid = next((k for k, p in self.doc.items() if _v(p, "name") == name), None)
            return (pid, name) if self._ok(name) else self.who("organiser")
        code = role.removeprefix("owner_of:") + " "
        tests = {"organiser": lambda p: _v(p, "is_organiser") is True, "sponsor": lambda p: _v(p, "is_sponsor") is True}
        if role.startswith("name:"):  # a person named in the history file (the people list holds the name once)
            tests[role] = lambda p: _v(p, "name") == role.removeprefix("name:")
        test = tests.get(role) or (lambda p: any(str(o).startswith(code) for o in _v(p, "owns") or []))
        pid = next((k for k, p in self.doc.items() if test(p) and self._ok(_v(p, "name"))), None)
        if pid:
            return pid, _v(self.doc[pid], "name")
        return self.who("organiser") if role != "organiser" else (None, contracts.NOT_YET)

    def name(self, role: str) -> str:
        return self.who(role)[1]


def months(start: date, end: date) -> list[date]:
    out, d = [], start.replace(day=1)
    while d <= end:
        out.append(d)
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def has(source: str, word: str) -> bool:
    """A whole word of the source slug: 'fee' is in fee_schedule, not in index_provider_feed."""
    return re.search(rf"(^|_){re.escape(word)}(_|$)", source) is not None


def pick(cs: list[dict], words: list[str]) -> str | None:
    return next((c["source"] for w in words for c in cs if has(c["source"], w)), None)


def month_runs(cs: list[dict], m: date, cal: dict, late_src: str | None, fail_src: str | None) -> list[dict]:
    """One run per source for month m, on the data of the month before, timed from the contract's expected and SLA."""
    key, data_day, late, failed = m.strftime("%Y-%m"), m - timedelta(days=1), cal["late"], cal["failed"]
    out = []
    for c in cs:
        is_late = key == late["month"] and c["source"] == late_src
        is_failed = key == failed["month"] and c["source"] == fail_src
        due = _deadline(c["expected"], data_day) or datetime(m.year, m.month, 1, 9)
        arrived = due + timedelta(days=late["days"]) if is_late else due - timedelta(minutes=30)
        ready, sla = arrived + timedelta(minutes=14), _deadline(c["sla"], data_day)
        rules = [{"rule": r, "passed": True, "count": 0} for r in c["rules"]]
        if is_failed:
            rid = next((r for r in c["rules"] if EMPTY_RULE.search(r.lower())), failed["rule"])
            rules = [r for r in rules if r["rule"] != rid] + [{"rule": rid, "passed": False, "count": failed["count"]}]
        rows = next((n for k, n in cal["rows"].items() if k != "default" and has(c["source"], k)), cal["rows"]["default"])
        out.append({"id": f"{PREFIX}{key}-{c['source']}", "source": c["source"], "started": iso(arrived + timedelta(minutes=5)), "ended": iso(ready),
                    "on_time": not is_late, "rows": rows, "schema_ok": True, "rules": rules, "not_run": [], "notes": [],
                    "marts_ready": None if is_failed else iso(ready), "sla_met": None if is_failed or not sla else ready <= sla,
                    "owner": c["owner"], "status": "failed" if is_failed else "late" if is_late else "ok"})
    return sorted(out, key=lambda r: r["started"])


def write_alerts(plane, m: date, runs: list[dict], cs: list[dict], cal: dict, engineer: str) -> list[str]:
    key, made = m.strftime("%Y-%m"), []
    for r in (r for r in runs if r["status"] in ("late", "failed")):
        made.append(({"id": f"{r['source']}:{r['status']}", "kind": r["status"], "source": r["source"], "measure": None, "owner": r["owner"]},
                     datetime.fromisoformat(r["ended"]), cal[r["status"]]["note"]))
    rb = cal["range_break"]
    if key == rb["month"]:
        code = rb["measure"].lower()
        c = next((c for c in cs if f"gold.{code}" in c["marts"]), None)
        made.append(({"id": f"gold.{code}:range", "kind": "outside_range", "source": c and c["source"], "measure": code,
                      "owner": c["owner"] if c else None}, on(m, rb["day"]), None))
    for a, at, note in made:
        with clock(at):
            alerts.sync(plane, alerts._read(plane) + [a], at.date().isoformat())
        if note:
            with clock(at + timedelta(hours=2)):
                alerts.act(plane, a["id"], "ack", engineer, note)
    return [a["id"] for a, _, _ in made]


def write_versions(plane, m: date, cal: dict, people: People) -> int:
    key, n = m.strftime("%Y-%m"), 0
    for step, spec in cal["versions"].items():
        if spec["month"] != key:
            continue
        for code in cal["measures"]:
            by = spec.get("by") or people.name(f"owner_of:{code}")
            with clock(on(m, spec["day"])):
                versions.append_version(plane, f"measure:{code}", spec["what"], by, f"history:{key}:{step}")
            n += 1
    return n


def write_comments(plane, m: date, cal: dict, people: People) -> int:
    key, path, n = m.strftime("%Y-%m"), plane.path("graph", "comments.json"), 0
    for i, c in enumerate(cal["comments"]):
        if c["month"] != key:
            continue
        node, at = f"measure:{c['measure']}", on(m, c["day"])
        item = {"id": f"{PREFIX}c{i + 1}", "kind": c["kind"], "text": c["text"], "by": "Anonymous" if c.get("anonymous") else people.name(c["by"]),
                "at": iso(at), "state": "open", "decided_by": None, "decided_at": None, "answer": None}
        if c.get("state"):
            decider = people.name("steward" if c["decided_by"] == "steward" else f"owner_of:{c['measure']}")
            item.update(state=c["state"], decided_by=decider, decided_at=iso(at + timedelta(days=1)), answer=c.get("answer"))
        with lock_for(path):
            doc = comments._read(plane)
            doc.setdefault(node, []).append(item)
            write_json_atomic(path, doc)
        if c.get("state") == "accepted":
            with clock(at + timedelta(days=1)):
                for code in [c["measure"], *c.get("also", [])]:
                    comments._add_version(plane, f"measure:{code}", f"Accepted: {c['text'][:120]}", item["decided_by"], f"comment:{item['id']}")
        n += 1
    return n


def write_messages(plane, m: date, runs: list[dict], cal: dict, people: People, late_src: str | None, owners: dict) -> int:
    key, spec = m.strftime("%Y-%m"), cal["messages"]
    words = spec["months"].get(key)
    if not words:
        return 0
    org = people.name("organiser")
    invitees = [{"name": people.name(r)} for r in spec["invite_roles"]]
    to = {"invite": invitees, "reminder": invitees, "sponsor_ask": [{"name": org}], "ops_report": [{"name": org}],
          "owner_ask": [{"name": owners.get(late_src) or org}]}
    at = on(m, spec["day"])
    for kind in to:  # the kinds this seed writes; messages.KINDS grows when intents.nira is imported (intent_nudge)
        record = {**words, "from_record": f"{CONV}{key}/{kind}", "to": to[kind], "organiser": org, "sponsor": people.name("sponsor"),
                  "runs": runs, "owner": owners.get(late_src) or org, "source": late_src}
        with clock(at):
            msg = messages.draft(plane, kind, record)
        if key < spec["drafts_from"]:
            path = messages._file(plane)
            with lock_for(path):
                rows = messages._all(plane)
                next(x for x in rows if x["id"] == msg["id"]).update(state="sent", sent_by=org, sent_at=iso(at + timedelta(hours=2)))
                write_json_atomic(path, {"messages": rows})
    return len(to)


def write_memory(plane, m: date, cal: dict, people: People) -> list[str]:
    key, files = m.strftime("%Y-%m"), []
    people_ids = [(people.who(p["role"])[0], p["entries"]) for p in cal["memory"]["people"]]
    targets = [("north", pid, entries) for pid, entries in people_ids if pid]  # a role nobody holds has no person memory
    targets += [(agent, None, entries) for agent, entries in cal["memory"]["company"].items()]
    for agent, pid, entries in targets:
        mine = [e for e in entries if e["month"] == key]
        if not mine:
            continue
        at = on(m, 18)
        with clock(at):
            memory.remember(plane, agent, pid, [{"kind": e["kind"], "text": e["text"], "conversation": f"{CONV}{key}/{agent}", "at": iso(at)}
                                                for e in mine])
        files.append(f"{agent}/people/{pid}.json" if pid else f"{agent}/company.json")
    return files


def write_egress(plane, m: date, cal: dict) -> int:
    spec, key = cal["egress"], m.strftime("%Y-%m")
    path = plane.area("context") / "egress_log.jsonl"
    lines = []
    for i, call in enumerate(spec["calls"]):
        attempt = f"{PREFIX}{key}-{i + 1}"
        lines.append({"attempt": attempt, "time": iso(on(m, spec["day"] + i, 10)), "module": call["module"], "kind": "model", "host": spec["host"],
                      "decision": "sent", "reason_code": "", "bytes": call["bytes"], "sha256": hashlib.sha256(attempt.encode()).hexdigest()})
    with lock_for(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(json.dumps(x) + "\n" for x in lines)
    return len(lines)


def _strip(path: Path, keep) -> None:
    """Rewrite a JSON file under its lock with keep(doc) applied; absent files stay absent."""
    with lock_for(path):
        doc = read_json_strict(path, dict)
        if doc is not None:
            write_json_atomic(path, keep(doc))


def _mine(e: dict) -> bool:
    return all(str(p.get("conversation") or "").startswith(CONV) for p in e.get("from") or [])


def remove_history(plane) -> None:
    """Remove everything the history wrote: ids and refs carry its prefix; alerts and memory files are named in the manifest."""
    man_path = plane.path("build", "demo_history.json")
    man = read_json_strict(man_path, dict) or {}
    _strip(_runs_path(plane), lambda d: {"runs": [r for r in d.get("runs", []) if not str(r.get("id")).startswith(PREFIX)]})
    _strip(alerts._path(plane), lambda d: {"alerts": [a for a in d.get("alerts", []) if a.get("id") not in man.get("alerts", [])]})
    ours = ("history:", f"comment:{PREFIX}")
    _strip(plane.path("graph", "versions.json"),
           lambda d: {k: rows for k, v in d.items() if (rows := [r for r in v if not str(r.get("ref")).startswith(ours)])})
    _strip(plane.path("graph", "comments.json"),
           lambda d: {k: rows for k, v in d.items() if (rows := [c for c in v if not str(c.get("id")).startswith(PREFIX)])})
    _strip(messages._file(plane), lambda d: {"messages": [x for x in d.get("messages", []) if not str(x.get("from_record")).startswith(CONV)]})
    for rel in man.get("memory", []):
        _strip(plane.path("context", "memory", *rel.split("/")), lambda d: {**d, "entries": [e for e in d.get("entries", []) if not _mine(e)]})
    log_path = plane.area("context") / "egress_log.jsonl"
    with lock_for(log_path):
        if log_path.exists():
            kept = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if f'"attempt": "{PREFIX}' not in ln]
            log_path.write_text("".join(ln + "\n" for ln in kept), encoding="utf-8")
    man_path.unlink(missing_ok=True)


def seed(data_root: Path, company_id: str, start: str = "2026-04-01", end: str = "2026-09-30", reset: bool = False,
         calendar_file: Path = HISTORY, companies_file: Path = COMPANIES) -> list[dict]:
    """Month-by-month summary rows. Only this company's plane is opened."""
    plane = PlaneStore(data_root).plane_for(company_id)
    remove_history(plane)
    if reset:
        return []
    cal = yaml.safe_load(calendar_file.read_text(encoding="utf-8"))
    files = sorted(plane.path("build", "pipelines").glob("*.json"))
    cs = [c for f in files if not f.name.endswith(".commits.json") and isinstance(c := read_json_strict(f, dict), dict) and c.get("source")] if files else contracts.ensure(plane)
    cs.sort(key=lambda c: c["source"])
    people = People(plane, company_id, companies_file)
    engineer = people.name("steward")
    late_src, fail_src = pick(cs, cal["late"]["source_match"]), pick(cs, cal["failed"]["source_match"])
    owners = {c["source"]: c["owner"] for c in cs}
    summary, alert_ids, mem_files = [], [], set()
    for m in months(date.fromisoformat(start), date.fromisoformat(end)):
        runs = month_runs(cs, m, cal, late_src, fail_src)
        with lock_for(_runs_path(plane)):
            write_json_atomic(_runs_path(plane), {"runs": read_runs(plane) + runs})
        ids = write_alerts(plane, m, runs, cs, cal, engineer)
        alert_ids += ids
        mem = write_memory(plane, m, cal, people)
        mem_files |= set(mem)
        summary.append({"month": m.strftime("%Y-%m"), "runs": len(runs), **{s: sum(r["status"] == s for r in runs) for s in ("ok", "late", "failed")},
                        "alerts": len(ids), "versions": write_versions(plane, m, cal, people), "comments": write_comments(plane, m, cal, people),
                        "messages": write_messages(plane, m, runs, cal, people, late_src, owners), "memory": len(mem), "egress": write_egress(plane, m, cal)})
    write_json_atomic(plane.path("build", "demo_history.json"), {"illustrative": True, "company": company_id, "from": start, "to": end,
                                                                 "alerts": alert_ids, "memory": sorted(mem_files), "months": summary})
    log.info("demo history for %s: %s", company_id, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed six months of illustrative operating history (synthetic).")
    ap.add_argument("company_id")
    ap.add_argument("--from", dest="start", default="2026-04-01")
    ap.add_argument("--to", dest="end", default="2026-09-30")
    ap.add_argument("--reset", action="store_true", help="only remove what an earlier run wrote")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    try:
        rows = seed(root, args.company_id, args.start, args.end, reset=args.reset)
    except (LookupError, ValueError, OSError) as e:
        print(f"Demo history not seeded: {e}")
        return 1
    if args.reset:
        print(f"Removed the demo history from {args.company_id}.")
    for r in rows:
        print(f"{r['month']}: {r['runs']} runs ({r['ok']} ok, {r['late']} late, {r['failed']} failed), {r['alerts']} alerts, {r['versions']} versions, "
              f"{r['comments']} comments, {r['messages']} messages, {r['memory']} memory writes, {r['egress']} model calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
