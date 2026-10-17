"""Team of ten: drive ONE build end to end as THAT person, through the same API the screens call.

    sh py.sh v3_persona.py <role_id> [--build N] [--dry-run]
    (UC6_BASE=http://127.0.0.1:8640 UC6_ENV=D:/Temp/sh3-team-env UC6_SHOTS=<dir> UC6_TMP=<dir>)

Plan comes from packs/family_office/1/role_builds.yaml. Resumable: state in $UC6_STATE (default D:/Temp/sh3-team-<role>.json), report in $UC6_REPORT (default D:/Temp/sh3-team/<role>.json);
give each parallel run its own pair so no run overwrites another's.
Steps: drop the build's files -> say the build's words -> wait out drafting -> "use the usual practice" once if Decision 1 shows gaps -> confirm
-> on a question try "retry" once, else STUCK -> Decision 2 (assumed answers; the administrator/custodian file as the check) -> Decision 3 go live
-> POST /api/v3/ask with check.ask and test every expect value appears. Long waits poll with time.sleep: run it as a background shell.
Needs the environment from v3_team_env.py (the three extra accounts and settings.jobs).
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
BUILDS = REPO / "packs" / "family_office" / "1" / "role_builds.yaml"
FIXTURES = REPO / "tests" / "v1" / "fixtures" / "10uc"
UC6_SOURCES = REPO / "docs" / "demo" / "uc6" / "sources"
NEW_PEOPLE = {"tom": "tom.hale", "priya": "priya.nair", "sam": "sam.lee", "helen": "helen.foo"}  # helen: the seed's owner account, absent from uc6.PEOPLE  # not in uc6.PEOPLE; uc6.py stays untouched
REPORTS = Path("D:/Temp/sh3-team")
LIMIT = 2 * 3600  # one persona run, all stages
BUSY = ("drafting", "working")


def paths(rid: str) -> tuple[Path, Path]:
    """(state file, report file) of one run: UC6_STATE / UC6_REPORT, else the shared defaults."""
    return Path(os.environ.get("UC6_STATE") or f"D:/Temp/sh3-team-{rid}.json"), Path(os.environ.get("UC6_REPORT") or REPORTS / f"{rid}.json")


def files_of(spec: list[str]) -> list[Path]:
    out: list[Path] = []
    for entry in spec:
        base, pat = ((UC6_SOURCES, entry[4:]) if entry.startswith("uc6:") else (OFFICE6M, entry[9:]) if entry.startswith("office6m:")
                     else (FIXTURES, entry))
        for m in sorted(glob.glob(str(base / pat))):
            p = Path(m)
            out += sorted(f for f in p.iterdir() if f.is_file() and f.name != "MANIFEST.md") if p.is_dir() else [p]
    return out


def norm(s: str) -> str:
    return s.replace(",", "").lower()


def said(out: dict) -> str:
    """What the answer shows: the sentence, then the figures behind "Show the figures" (each row's label and value)."""
    return " ".join([str(out.get("answer") or ""), *(f"{r.get('label', '')} {r.get('value', '')}" for r in out.get("rows") or [] if isinstance(r, dict))])


def missing(answer: str, expect: list[str]) -> list[str]:
    a = norm(answer)
    return [e for e in expect if norm(e) not in a and norm(e).removesuffix(".00") not in a]


OFFICE6M = REPO / "tests" / "v1" / "fixtures" / "office6m"
BUILDS_DIR = BUILDS.parent / "builds"  # one file per domain for the top-50 use cases; merged with role_builds.yaml


def all_roles() -> dict:
    roles = {r["id"]: dict(r, builds=list(r["builds"])) for r in yaml.safe_load(BUILDS.read_text(encoding="utf-8"))["roles"]}
    for f in sorted(BUILDS_DIR.glob("*.yaml")) if BUILDS_DIR.is_dir() else []:
        for r in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("roles") or []:
            roles.setdefault(r["id"], {**r, "builds": []})["builds"] += r.get("builds") or []
    return roles


def load_uc(uc: str) -> tuple[dict, dict]:
    """The role and build whose build id is `uc` (a top-50 card id). The builds folder wins over role_builds.yaml, so a card
    rebuilt for the six-month office (builds/legacy-office6m.yaml) runs on that world."""
    found = None
    for r in all_roles().values():
        for i, b in enumerate(r["builds"], 1):
            if b["id"] == uc:
                found = (r, b)  # later files (the builds folder) override role_builds.yaml
    if found:
        return found
    raise SystemExit(f"unknown use case {uc}")


def load_plan(role_id: str, n: int) -> tuple[dict, dict]:
    roles = all_roles()
    if role_id not in roles:
        raise SystemExit(f"unknown role {role_id}; one of: {', '.join(roles)}")
    r = roles[role_id]
    if not 1 <= n <= len(r["builds"]):
        raise SystemExit(f"{role_id} has {len(r['builds'])} build(s)")
    return r, r["builds"][n - 1]


def dry_run(role: dict, build: dict, n: int) -> None:
    fs = files_of(build["files"])
    env = os.environ.get("UC6_ENV", "<UC6_ENV>")
    print(f"role {role['id']} | {role['person']} | {role['title']} | build {n}: {build['id']}")
    print(f"1 drop {len(fs)} file(s) into {env}/evergreen/dropbox")
    for f in fs[:12]:
        print("    ", f.relative_to(REPO))
    print("    ..." if len(fs) > 12 else "", end="")
    print(f"2 say: {build['say']}")
    print("3 wait out drafting | 4 Decision 1: if gaps, say 'use the usual practice' once, then confirm")
    print("5 question: 'retry' once, then STUCK | 6 Decision 2: assumed answers; check file = administrator/custodian if offered | 7 Decision 3: go live")
    print(f"8 ask: {build['check']['ask']!r}  expect: {build['check']['expect']}")
    st, rp = paths(role["id"])
    print(f"state {st} | report {rp}")


def run(role: dict, build: dict, n: int) -> None:
    import uc6
    from uc6 import ENV, Person
    uc6.PEOPLE.update(NEW_PEOPLE)
    rid = role["id"]
    state_f, report_f = paths(rid)
    report_f.parent.mkdir(parents=True, exist_ok=True)
    s = json.loads(state_f.read_text()) if state_f.exists() and json.loads(state_f.read_text()).get("build") == build["id"] else {}
    s.setdefault("times", {})
    s.setdefault("shots", {})
    s.setdefault("retried", [])
    key = role["person"].split()[0].lower()

    def save() -> None:
        state_f.write_text(json.dumps(s, indent=1))

    def report(th: dict, stage: str, done: bool, check: dict | None = None, answer: str | None = None) -> None:
        qs = [e.get("text", "") for e in (th or {}).get("events", []) if e.get("kind") == "question"]
        report_f.write_text(json.dumps({
            "role": rid, "person": role["person"], "build": build["id"], "stage": stage, "done": done, "stuck_at": s.get("stuck_at"),
            "questions": {"count": len(qs), "texts": qs, "asked_counter": (th or {}).get("asked")},
            "timings_s": {k: round(v) for k, v in s["times"].items()}, "answer": answer if answer is not None else s.get("answer"),
            "check": check or s.get("check"), "screenshots": s["shots"], "thread": s.get("tid")}, indent=1, default=str), encoding="utf-8")

    with Person(key) as p:
        if not s.get("tid"):
            box = ENV / "evergreen" / "dropbox"
            box.mkdir(parents=True, exist_ok=True)
            fs = files_of(build["files"])
            for f in fs:
                shutil.copy2(f, box / f.name)
            print("dropped", len(fs), "file(s)")
            st, th = p.post("/api/v3/threads", {"text": build["say"]})
            if st >= 400:
                s["stuck_at"] = f"start: HTTP {st}"
                report({}, "start", False)
                raise SystemExit(f"could not start the thread: {st} {th}")
            s.update(build=build["id"], tid=th["id"], dropped=len(fs))
            save()
        tid, t0, last_stage, last_t = s["tid"], time.time(), None, time.time()
        while True:
            try:
                st, th = p.get(f"/api/v3/threads/{tid}", timeout=60000)
            except Exception as e:  # noqa: BLE001 - a busy server may drop one poll; the next poll tries again
                print("poll dropped, retrying:", str(e).splitlines()[0][:80], flush=True)
                time.sleep(5)
                continue
            stage = th.get("stage")
            now = time.time()
            s["times"][last_stage or stage] = s["times"].get(last_stage or stage, 0) + (now - last_t)
            last_stage, last_t = stage, now
            d = th.get("decision") or {}
            if stage != s.get("stage"):
                print(time.strftime("%H:%M:%S"), "stage", stage, "| asked", th.get("asked"))
                s["stage"] = stage
            save()
            report(th, stage, False)
            if stage in BUSY:
                time.sleep(5)
            elif stage == "decision1":
                gk = "gaps: " + " | ".join(g if isinstance(g, str) else str(g.get("label")) for g in d.get("gaps") or [])
                if d.get("gaps") and gk not in s["retried"]:  # the usual practice once per distinct gap set; an unchanged set falls through to confirm (capped)
                    s["retried"].append(gk)
                    save()
                    p.post(f"/api/v3/threads/{tid}/say", {"text": "use the usual practice"})
                elif (th.get("signoff") or {}).get("state") == "fill":
                    # the signer could not sign it as it stands: Harbor names what this person must still say; the usual practice once, then STUCK
                    q = th["signoff"].get("message") or ""
                    if q in s["retried"]:
                        s["stuck_at"] = f"decision1 gaps: {q[:300]}"
                        save()
                        print("STUCK", s["stuck_at"])
                        report(th, stage, False)
                        return None
                    s["retried"].append(q)
                    save()
                    print("gaps named for", role["person"], "->", q[:200], flush=True)
                    p.post(f"/api/v3/threads/{tid}/say", {"text": "use the usual practice"})
                elif (th.get("signoff") or {}).get("state") in ("send", "waiting"):
                    # this person may not sign: send the brief to the signer, who confirms it from Action
                    so = th["signoff"]
                    if so["state"] == "send":
                        p.post(f"/api/v3/threads/{tid}/decide", {"n": 1, "answer": "send_for_signature"})
                        p.shot(f"/v3/thread/{tid}", f"team-{rid}-sent-to-signer")
                    return so["signer"]["name"].split()[0].lower()  # Playwright can't nest: the caller confirms as the signer
                else:
                    # a brief that keeps coming back is a finding, not something to confirm forever
                    s["confirms"] = s.get("confirms", 0) + 1
                    if s["confirms"] > 4:
                        s["stuck_at"] = f"decision1 loop: confirmed {s['confirms'] - 1} times; gaps {[g if isinstance(g, str) else g.get('label') for g in d.get('gaps') or []]}"[:300]
                        save()
                        print("STUCK", s["stuck_at"])
                        report(th, stage, False)
                        return None
                    p.post(f"/api/v3/threads/{tid}/decide", {"n": 1, "answer": "confirm"})
                time.sleep(3)
            elif stage == "decision2":
                answers = {q["id"]: q.get("assumed") or q["options"][0] for q in d.get("questions") or [] if q.get("options")}
                for q in d.get("questions") or []:
                    if q["id"] == "check:file":  # the independent source: the administrator's or the custodian's file
                        answers[q["id"]] = next((o for o in q["options"] if "administrator" in o.lower() or "custodian" in o.lower()), "No check this time")
                p.post(f"/api/v3/threads/{tid}/decide", {"n": 2, "answer": "carry_on", "answers": answers})
                time.sleep(3)
            elif stage == "decision3":
                p.post(f"/api/v3/threads/{tid}/decide", {"n": 3, "answer": "go_live"})
                time.sleep(3)
            elif stage == "live":
                break
            elif stage == "question":
                q = next((e.get("text", "") for e in reversed(th.get("events", [])) if e.get("kind") == "question"), "")
                if q in s["retried"]:
                    s["stuck_at"] = f"question: {q[:300]}"
                    save()
                    print("STUCK", s["stuck_at"])
                    p.shot(f"/v3/thread/{tid}", f"team-{rid}-build-stuck")
                    report(th, stage, False)
                    return
                s["retried"].append(q)
                save()
                p.post(f"/api/v3/threads/{tid}/say", {"text": "retry"})
                time.sleep(3)
            else:
                s["stuck_at"] = f"unknown stage {stage}"
                report(th, stage, False)
                return
            if time.time() - t0 > LIMIT:
                s["stuck_at"] = f"timeout in {stage}"
                report(th, stage, False)
                return
        # live: the check, then the three screens as this person
        ask, expect = build["check"]["ask"], build["check"]["expect"]
        for attempt in (1, 2):
            st, out = p.post("/api/v3/ask", {"text": ask})
            if st < 400:
                break
            time.sleep(15)
        answer = out.get("answer", "") if isinstance(out, dict) and st < 400 else f"HTTP {st}: {out}"
        gone = missing(said(out), expect) if st < 400 else expect
        ok = st < 400 and bool(answer.strip()) and not gone
        s["answer"], s["check"] = answer, {"ask": ask, "expect": expect, "missing": gone, "pass": ok, "http": st}
        for name, url in (("desk", "/v3/desk"), ("build", f"/v3/thread/{tid}"), ("consume", "/v3/board")):
            s["shots"][name] = str(p.shot(url, f"team-{rid}-{name}"))
        save()
        report(th, "live", True)
        print(f"DONE {rid}: live; check {'PASS' if ok else 'FAIL'} missing={gone}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("role")
    ap.add_argument("--build", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uc", help="run a top-50 use case by its id (the role argument is then ignored)")
    a = ap.parse_args()
    role, build = load_uc(a.uc) if a.uc else load_plan(a.role, a.build)
    if a.dry_run:
        dry_run(role, build, a.build)
    else:
        tries = 0
        while (signer := run(role, build, a.build)) and tries < 2:
            tries += 1
            from uc6 import Person
            tid = json.loads(paths(role["id"])[0].read_text())["tid"]
            with Person(signer) as q:
                q.shot("/v3/action", f"team-{role['id']}-signer-action")
                st, out = q.post(f"/api/v3/threads/{tid}/decide", {"n": 1, "answer": "confirm"})
                print("signer", signer, "confirmed:", st)
                q.shot(f"/v3/thread/{tid}", f"team-{role['id']}-signed-record")
                if st >= 400:
                    raise SystemExit(f"signer could not confirm: {st} {str(out)[:300]}")
