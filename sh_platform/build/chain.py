"""59: the Build chain. One change note per Initiative handed to Build, five steps, a named person closes each (agents draft, people sign).

build/changes/<C-0001>.json (C31: numbered per company, in order), shape in spec 59 "Records read and written". Steps:
  1 Architect (roles.architect)  2 Approval (roles.head_of_department, C25)  3 Data engineer (roles.developer)
  4 Tester (roles.tester; the sponsor or a company admin when none is named, as uat.py)  5 Ops manager (roles.ops)
The people come from the Initiative's charter roles block (34), else the newest signed charter's (uat._role). Lens drafts the head of
department from the Initiative's areas (a person whose team is the area and whose role reads "Head of") until the organiser names one.

Moves the server makes on read (the UAT and release routes are not ours): testing -> waiting_release when every measure of the change has a
UAT signature made after step 4 opened; a UAT sent back after that returns the change to step 3; waiting_release -> with_ops when the sponsor
signs the release after step 4 opened (the record and diagrams regenerate then). Opening: a change note is drafted the first time any chain
route is read after the Initiative's gap report is signed (m3_connect plan outcome)."""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from sh_platform.build import architecture as A
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store as pstore, view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
STEPS = ((1, "architect", "Span, the architect"), (2, "head_of_department", "Approval"), (3, "developer", "Flow, the data engineer"), (4, "tester", "Tester"),
         (5, "ops", "Ops manager"))
STEP_OF = {"drafting": 1, "with_architect": 1, "with_approver": 2, "building": 3, "testing": 4, "waiting_release": 4, "with_ops": 5, "live": 5,
           "stopped": 0}
STATE_AT = {1: "with_architect", 2: "with_approver", 3: "building", 4: "testing", 5: "with_ops"}
BACK = {(2, 1), (3, 1), (3, 2), (4, 3), (5, 5)}  # send back: one step back, step 3 straight to step 1; step 5 "Not ready" stays
SECTIONS = ("why", "what_changes", "decisions", "build_steps", "tests", "run_book", "risks")
ROLE_WORD = {"architect": "Architect", "head_of_department": "Head of department", "developer": "Data engineer", "tester": "Tester", "ops": "Ops manager"}
BUILD_USERS = frozenset({"company_admin", "analyst"})
MAX_TEXT = 2000
CID = re.compile(r"C-\d{4,6}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rd(path, empty=None) -> Any:
    try:
        d = read_json_strict(path)
    except (OSError, ValueError):
        log.warning("a chain input could not be read")
        return empty
    return empty if d is None else d


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _folder(plane):
    return plane.path("build", "changes")


def _path(plane, cid: str):
    return plane.path("build", "changes", f"{cid}.json")


def all_notes(plane) -> list[dict]:
    f = _folder(plane)
    out = [_rd(p, None) for p in sorted(f.glob("C-*.json"))] if f.is_dir() else []
    return [n for n in out if isinstance(n, dict) and n.get("id")]


def _intent(plane, iid: str | None) -> dict:
    from sh_platform.intents import store as istore
    try:
        return (istore.read_intent(plane, iid) or {}) if iid else {}
    except istore.Unreadable:
        return {}


# ---- people at each step --------------------------------------------------------------------------------------------------------------

def _pname(people: dict, v: Any) -> str | None:
    if not v:
        return None
    p = people.get(v) if isinstance(v, str) else None
    n = A._cell(p.get("name")) if isinstance(p, dict) else v
    return str(n).strip() or None


def _hod_guess(plane, intent: dict, people: dict) -> str | None:
    """Lens's draft of the head of department (C25): the person whose team is one of the Initiative's areas and whose role reads Head of."""
    areas = pstore.raw(plane).get("areas") or {}
    names = {view.norm(A._cell((areas.get(a) or {}).get("name")) or a) for a in intent.get("areas") or []}
    for p in people.values():
        if isinstance(p, dict) and view.norm(A._cell(p.get("team")) or "") in names and str(A._cell(p.get("role")) or "").lower().startswith("head of"):
            return _pname(people, A._cell(p.get("name")))
    return None


def people_of(plane, intent: dict, note: dict | None = None) -> dict[str, dict]:
    """{role: {"name": str | None, "mark": stated | guessed | None}} for the five step roles."""
    from sh_platform.build import uat
    people = pstore.raw(plane).get("people") or {}
    sid = next(iter((intent.get("refs") or {}).get("wall_session_ids") or []), None)
    rec = _rd(plane.path("intents", "m1_intent", "roles", f"{sid}.json"), {}) if isinstance(sid, str) else {}
    rec = rec if isinstance(rec, dict) else {}
    out = {}
    for _, role, _ in STEPS:
        name = _pname(people, (rec.get("names") or {}).get(role)) or _pname(people, (rec.get("roles") or {}).get(role))
        if name is None and role != "head_of_department":
            name = uat._role(plane, role)
        out[role] = {"name": name, "mark": "stated" if name else None}
    for role, name in ((note or {}).get("people") or {}).items():  # a note opened by open_note names its own five people
        if role in out and name:
            out[role] = {"name": name, "mark": "stated"}
    if out["head_of_department"]["name"] is None and (g := _hod_guess(plane, intent, people)):
        out["head_of_department"] = {"name": g, "mark": "guessed", "by": "Lens", "from": "The profile names the head of the Initiative's area"}
    return out


def _is(viewer: view.Viewer, name: str | None) -> bool:
    return bool(name) and view.allows(frozenset({view.norm(name)}), viewer)


def may_act(viewer: view.Viewer, role: str, who: dict) -> bool:
    if role == "tester" and not who["name"]:
        return bool({"sponsor", "company_admin"} & set(viewer.roles))
    return _is(viewer, who["name"])


def holds(plane, viewer: view.Viewer, roles: tuple[str, ...]) -> bool:
    """The viewer holds one of these roles on an open change, or on the newest charter when no change is open."""
    notes = [n for n in all_notes(plane) if n.get("state") not in ("live", "stopped")]
    for n in notes or [{}]:
        ppl = people_of(plane, _intent(plane, n.get("intent_id")), n)
        if any(_is(viewer, ppl[r]["name"]) for r in roles):
            return True
    return False


# ---- opening and drafting -------------------------------------------------------------------------------------------------------------

def _gap_outcome(plane, intent: dict) -> dict | None:
    """The signed gap report (m3_connect plan outcome) for the assessment the Initiative was handed over with."""
    h = intent.get("build_handoff") or {}
    ref = str((intent.get("links") or {}).get("build") or "").removeprefix("build:")
    folder = plane.path("intents", "m3_connect", "outcomes")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        o = _rd(f, {})
        if isinstance(o, dict) and o.get("kind") == "plan" and o.get("signed_at") and (
                o.get("assessment_id") == ref or (h.get("charter_outcome_id") and o.get("charter_outcome_id") == h.get("charter_outcome_id"))):
            return o
    return None


def hypothesis(plane, intent: dict) -> dict | None:
    """The newest version of the Initiative's hypothesis (57): hypothesis_ref, else a file that names the Initiative."""
    if not intent.get("id"):  # no id: None == None would match any hypothesis with no origin
        return None
    ref = intent.get("hypothesis_ref") or {}
    folder = plane.path("intents", "hypotheses")
    cands = [folder / f"{ref['id']}.json"] if isinstance(ref, dict) and isinstance(ref.get("id"), str) and re.fullmatch(r"[\w-]+", ref["id"]) else []
    cands += sorted(folder.glob("*.json")) if folder.is_dir() else []
    for f in cands:
        h = _rd(f, None) if f.is_file() else None
        if not isinstance(h, dict):
            continue
        mine = (h.get("origin") or {}).get("ref") == intent.get("id") or any(c.get("intent") == intent.get("id") for c in h.get("carried_into") or [] if isinstance(c, dict))
        if mine and h.get("versions"):
            return {**h["versions"][-1], "id": h.get("id")}
    return None


def ensure(plane) -> None:
    """Open a change note for every Initiative handed to Build whose gap report is signed and that has none yet."""
    from sh_platform.intents import store as istore
    have = {n.get("intent_id") for n in all_notes(plane)}
    for r in istore.read_index(plane):
        if r.get("type") != "initiative" or r["id"] in have:
            continue
        rec = _intent(plane, r["id"])
        if not rec.get("build_handoff"):
            continue
        gap = _gap_outcome(plane, rec)
        if gap is not None:
            _open(plane, rec, gap)


def _blank(n: int, intent_id: str | None, title: Any, now: str, bp: dict, gap_ref: Any = None) -> dict:
    return {"id": f"C-{n:04d}", "intent_id": intent_id, "title": title, "state": "drafting", "opened_at": now,
            "blueprint_version": bp.get("version"), "gap_report_ref": gap_ref, "sections": {k: [] for k in SECTIONS},
            "components": {"added": [], "changed": [], "retired": []}, "measures": [],
            "steps": [{"n": i, "role": role, "opened_at": None, "signed": None} for i, role, _ in STEPS],
            "returns": [], "release_ref": None, "stopped": None, "redrafts": []}


def open_note(plane, title: str, sections: dict, people: dict, source: dict, by: str) -> dict:
    """Open a change note from outside the Initiative path (for example a Span proposal). `sections` maps a section name to line texts
    (str) or line dicts; each becomes a guessed line by `by`. `people` maps the five step roles (architect, head_of_department,
    developer, tester, ops) to names. `source` ({"kind": ..., "id": ...}) is kept on the note; its optional intent_id links the note."""
    with lock_for(_folder(plane) / "_seq"):
        n = max([int(x["id"][2:]) for x in all_notes(plane) if CID.fullmatch(x["id"])] + [0]) + 1
        now = _now()
        note = _blank(n, (source or {}).get("intent_id"), title, now, _rd(plane.path("build", "blueprint.json"), {}) or {})
        for k, lines in (sections or {}).items():
            if k in SECTIONS:
                note["sections"][k] = [{**_ln(x, f"{(source or {}).get('kind', 'proposal')}:{(source or {}).get('id', '')}"), "by": by}
                                       if isinstance(x, str) else {**_ln(x.get("text", ""), x.get("from") or "proposal"), **x, "mark": "guessed", "by": by} for x in lines]
        note["people"] = {r: v for r, v in (people or {}).items() if r in ROLE_WORD and v}
        note["source"] = dict(source or {})
        note["state"], note["steps"][0]["opened_at"] = "with_architect", now
        _folder(plane).mkdir(parents=True, exist_ok=True)
        write_json_atomic(_path(plane, note["id"]), note)
    return note


def _span_draft(plane, note: dict, by: str) -> dict:
    """Span's decisions and risks on a saved note (gate 1). Rule lines stay when the model is unavailable; `drafting_note` then says so.
    Missing module or any failure: today's rule-based draft stands."""
    try:
        from sh_platform.build.agents import runtime as R, span_arch
        got = span_arch.draft_change_note(plane, note["id"], R.runtime_for_plane(plane), by)
    except Exception:  # ponytail: any failure keeps the rule draft; log only
        log.warning("Span could not draft change note %s", note.get("id"), exc_info=True)
        return note
    if not got:
        return note
    out = {**got["note"], "drafting_note": got.get("message") if got.get("fallback") else None}
    with lock_for(_path(plane, note["id"])):
        _save(plane, out)
    return out


def _open(plane, intent: dict, gap: dict) -> dict:
    with lock_for(_folder(plane) / "_seq"):
        if any(n.get("intent_id") == intent["id"] for n in all_notes(plane)):
            return {}
        n = max([int(x["id"][2:]) for x in all_notes(plane) if CID.fullmatch(x["id"])] + [0]) + 1
        now = _now()
        bp = _rd(plane.path("build", "blueprint.json"), {}) or {}
        note = _blank(n, intent["id"], intent.get("title"), now, bp, gap.get("outcome_id"))
        note = _draft(plane, note, intent, gap)
        note["state"], note["steps"][0]["opened_at"] = "with_architect", now
        _folder(plane).mkdir(parents=True, exist_ok=True)
        write_json_atomic(_path(plane, note["id"]), note)
    note = _span_draft(plane, note, "")
    A.propose(plane, note["id"], note["components"]["added"] + note["components"]["changed"])
    return note


def _ln(text: str, src: str, **kw) -> dict:
    return {"text": str(text)[:MAX_TEXT], "mark": "guessed", "from": src, "by": "Span", "at": _now(), **kw}


def _measures(plane, intent: dict, hyp: dict | None) -> list[str]:
    """The measures the change is about: the hypothesis measure, else the lineage measures fed by the sources handed over (R16)."""
    if hyp and isinstance(hyp.get("measure"), dict) and hyp["measure"].get("id"):
        return [str(hyp["measure"]["id"]).upper()]
    names = {view.norm(s.get("name")) for s in (intent.get("build_handoff") or {}).get("source_map") or [] if isinstance(s, dict) and s.get("name")}
    bp = _rd(plane.path("build", "blueprint.json"), {}) or {}
    return sorted({str(ln["measure"]).upper() for ln in bp.get("lineage") or [] if isinstance(ln, dict) and view.norm(ln.get("source")) in names})


def _draft(plane, note: dict, intent: dict, gap: dict | None) -> dict:
    """The Architect's seven sections, every line guessed with its source. Lines a person stated are kept (rule 7)."""
    hyp = hypothesis(plane, intent)
    codes = _measures(plane, intent, hyp)
    proj, rec = A.project(plane), A.read(plane)
    have = {c["id"]: c for c in rec["components"]}
    marts = {f"gold:{c.lower()}" for c in codes}
    pipes = [(p, d) for p, d in A.contracts(plane) if {f"gold:{A._mart(m).split('.', 1)[-1]}" for m in d.get("marts") or []} & marts]
    related = [m for m in sorted(marts) if m in proj]
    for _, d in pipes:
        s = A._slug(d["source"]).replace("-", "_")
        related += [f"{k}:{s}" for k in ("source", "bronze", "silver")]
    added = [i for i in related if i not in have or (have[i].get("state") == "proposed" and have[i].get("made_by") == note["id"])]
    changed = [i for i in related if i in have and i not in added and not A._same(have[i], proj[i])]
    sec: dict[str, list[dict]] = {k: [] for k in SECTIONS}
    if hyp:
        src = f"intents/hypotheses/{hyp.get('id')}.json"
        b, t = hyp.get("baseline") or {}, hyp.get("target") or {}
        sec["why"] += [_ln(f"Belief: {hyp.get('belief')}", src), _ln(f"Measure: {(hyp.get('measure') or {}).get('name')} ({codes[0]})", src, measure=codes[0]),
                       _ln(f"Baseline: {b.get('value')} for {', '.join(b.get('periods') or []) or 'Not available yet'}", src),
                       _ln(f"Target: {t.get('value')} by {t.get('by') or 'Not available yet'}", src), _ln(f"Review date: {hyp.get('review_date') or 'Not available yet'}", src)]
    h = intent.get("build_handoff") or {}
    if h:
        sec["why"].append(_ln(f"Handed to Build by {(h.get('by') or {}).get('name') or 'the organiser'} on {str(h.get('at'))[:10]}", f"intents/{intent['id']}/intent.json build_handoff"))
    for word, ids in (("Add", added), ("Change", changed)):
        for i in ids:
            c = proj[i]
            sec["what_changes"].append(_ln(f"{word} {c['label']} ({c['kind']})", c["from"], group=c["view"], component=i,
                                           href=f"/centre/build/architecture?view={c['view']}&focus={i}"))
    for i in added:
        c = proj[i]
        if c["kind"] == "gold":
            opts = ["Keep it in the main warehouse file", "Put it in the restricted marts file, readable only by its list"]
            pick, why = (opts[1], "the blueprint limits who may see it") if c["restricted"] else (opts[0], "the blueprint gives it no access list")
            follows = "Query tools read it from the read-only copy" if pick == opts[0] else "Only the people on its list can read it"
        elif c["kind"] == "source":
            opts = ["Load it with the built-in runner from the landing folder", "Adopt an existing warehouse table and build nothing"]
            pick, why, follows = opts[0], "the pipeline contract names a landing folder and a file pattern", "The Watcher checks its arrival against the contract"
        else:
            continue
        sec["decisions"].append(_ln(f"{c['label']}: {pick}, because {why}. Other option: {[o for o in opts if o != pick][0]}. Then: {follows}.", c["from"],
                                    component=i, placement=c["label"], options=opts, chosen=pick, why=why, follows=follows))
    for path, d in pipes:
        title = d.get("title") or d["source"]
        sec["build_steps"].append(_ln(f"Pipeline contract for {title}, loading {', '.join(d.get('marts') or []) or 'no mart yet'}", path,
                                      contract=path, source=d["source"], component=f"source:{d['source']}", href="/centre/build/pipelines"))
        sec["run_book"].append(_ln(f"{title}: expected {d.get('expected') or 'Not stated'}, service level {d.get('sla') or 'Not stated'}, "
                                   f"source owner {d.get('owner') or 'not named'}; {d.get('owner') or 'the source owner'} is told when it is late", path,
                                   component=f"source:{d['source']}", href="/centre/build/ops"))
    for code in codes:
        sec["tests"].append(_ln(f"{code}: our figure matches the reported figure for every reported period", "build/prove.json", measure=code, check="catalogue",
                                href="/centre/build/prove"))
        if hyp:
            b = hyp.get("baseline") or {}
            sec["tests"].append(_ln(f"{code}: the hypothesis baseline {b.get('value')} for {(b.get('periods') or ['Not available yet'])[-1]} reproduces from gold.{code.lower()}",
                                    "intents/hypotheses", measure=code, check="hypothesis", href="/centre/build/prove"))
    srcs = {view.norm(d.get("title") or d["source"]) for _, d in pipes}
    for r in (gap or {}).get("accepted_risks") or []:
        if not isinstance(r, dict):
            continue
        hit = [c for c in codes if c in set(map(str.upper, r.get("measures") or []))]
        if hit or any(s in view.norm(r.get("text")) for s in srcs if s):  # SF14: the key lets the design document mask the line
            sec["risks"].append(_ln(r.get("text") or "An accepted risk", f"intents/m3_connect/outcomes/{(gap or {}).get('outcome_id')}.json",
                                    **({"measure": hit[0]} if hit else {})))
    keep = note.get("sections") or {}
    for k in SECTIONS:
        # a proposal note's quoted why and test lines have no records to regenerate from, so they stay
        stated = [x for x in keep.get(k) or [] if x.get("mark") == "stated" or ((note.get("source") or {}).get("kind") == "proposal" and k in ("why", "tests"))]
        sec[k] = stated + [x for x in sec[k] if x["text"] not in {s["text"] for s in stated}]
    return {**note, "sections": sec, "measures": codes, "components": {"added": added, "changed": changed, "retired": []},
            "blueprint_version": (_rd(plane.path("build", "blueprint.json"), {}) or {}).get("version")}


# ---- read-time facts: build steps done, tests, North's check -------------------------------------------------------------------------

def _last_runs(plane) -> dict[str, str]:
    last = {}
    for r in (_rd(plane.path("warehouse", "runs.json"), {}) or {}).get("runs") or []:
        if isinstance(r, dict):
            last[r.get("source")] = r.get("status")
    return last


def _steps_done(plane, note: dict) -> list[dict]:
    last = _last_runs(plane)
    out = []
    for s in note["sections"]["build_steps"]:
        ok = bool(s.get("contract")) and plane.path(*s["contract"].split("/")).is_file() and last.get(s.get("source")) == "ok"
        out.append({**s, "done": ok})
    return out


def _gold(plane, code: str, period: str) -> float | None:
    from sh_platform import warehouse
    try:
        con = warehouse.open_readonly(plane)
    except Exception:  # noqa: BLE001  no read-only copy yet: the line says so
        return None
    try:
        row = con.execute(f'select value from gold."{code.lower()}" where period = ?', [period]).fetchone()
    except Exception:  # noqa: BLE001
        row = None
    finally:
        con.close()
    return None if row is None or row[0] is None else float(row[0])


def _tests(plane, note: dict, hyp: dict | None) -> list[dict]:
    prove = {m.get("code"): m for m in (_rd(plane.path("build", "prove.json"), {}) or {}).get("measures") or [] if isinstance(m, dict)}
    out = []
    for t in note["sections"]["tests"]:
        code, extra = t.get("measure"), ""
        if t.get("check") == "catalogue":
            res = [p.get("result") for p in (prove.get(code) or {}).get("periods") or []]
            done = bool(res) and all(r == "match" for r in res)
            extra = " Result: matches for every period." if done else (" Result: a gap." if "gap" in res else " Result: not proven yet.")
        elif t.get("check") == "hypothesis" and hyp:
            b = hyp.get("baseline") or {}
            per = (b.get("periods") or [None])[-1]
            got = _gold(plane, code, per) if per and b.get("value") is not None else None
            done = got is not None and math.isclose(got, float(b["value"]), rel_tol=0.01, abs_tol=0.005)
            extra = (" Result: Not available yet: gold has no value for that period." if got is None else
                     " Result: reproduces." if done else f" Result: gold reads {round(got, 4)}, not the baseline.")
        else:
            done = None
        out.append({**t, "text": t["text"] + extra, "done": done})
    return out


def completeness(plane, note: dict) -> dict:
    """North's step 2 line: every component has an owner, every measure has a test line, every build step names a contract."""
    rec = {c["id"]: c for c in A.read(plane)["components"]}
    ids = note["components"]["added"] + note["components"]["changed"]
    lost = [rec[i]["label"] for i in ids if i in rec and not rec[i].get("owner")]
    untested = [m for m in note.get("measures") or [] if not any(t.get("measure") == m for t in note["sections"]["tests"])]
    nocontract = [s["text"] for s in note["sections"]["build_steps"] if not s.get("contract")]
    gap = (f"{len(lost)} component{'s have' if len(lost) != 1 else ' has'} no owner: {', '.join(lost)}" if lost else
           f"{untested[0]} has no test line" if untested else f"A build step names no contract: {nocontract[0]}" if nocontract else None)
    return {"line": gap or "Every component has an owner; every measure has a test; every build step names a contract", "gap": gap}


def _it_signer(plane) -> str | None:
    from sh_platform.intents import admin
    v = admin._read(admin._files(plane)[1]).get("it_signer")
    return v.strip() if isinstance(v, str) and v.strip() else None


def _infra_changed(note: dict) -> bool:
    return any(i.startswith("infra:") for i in note["components"]["added"] + note["components"]["changed"])


# ---- moves the server makes when it reads (UAT and release are other routes) ----------------------------------------------------------

def _sync(plane, note: dict) -> dict:
    step4 = note["steps"][3].get("opened_at") or ""
    if note["state"] not in ("testing", "waiting_release") or not step4:
        return note
    prove = _rd(plane.path("build", "prove.json"), {}) or {}
    rows = {m.get("code"): m.get("uat") or {} for m in prove.get("measures") or [] if isinstance(m, dict)}
    moved = False
    with lock_for(_path(plane, note["id"])):
        note = _rd(_path(plane, note["id"]), note)
        if note["state"] == "testing":
            us = [rows.get(c) or {} for c in note.get("measures") or []]
            back = [u for u in us if u.get("state") == "sent_back" and str(u.get("at") or "") >= step4]
            if back:
                b = max(back, key=lambda u: str(u.get("at")))
                note["returns"].append({"from": 4, "to": 3, "by": b.get("by"), "reason": b.get("note") or "Sent back", "at": b.get("at")})
                _reopen(note, 3)
                moved = True
            elif us and all(u.get("state") == "signed" and str(u.get("at") or "") >= step4 for u in us):
                last = max(us, key=lambda u: str(u.get("at")))
                note["steps"][3]["signed"] = {"by": last.get("by"), "role": "Tester", "at": last.get("at")}
                note["state"], moved = "waiting_release", True
                A.set_state(plane, note["id"], "tested")
        rel = prove.get("release") or {}
        if note["state"] == "waiting_release" and rel.get("state") == "signed" and str(rel.get("at") or "") >= step4:
            note["release_ref"] = {"by": rel.get("by"), "at": rel.get("at")}
            note["state"], note["steps"][4]["opened_at"], moved = "with_ops", _now(), True
        if moved:
            write_json_atomic(_path(plane, note["id"]), note)
    if note["state"] == "with_ops" and moved:
        _regen(plane, "release_signed", str(note["release_ref"]["at"]), note["release_ref"]["by"] or "the sponsor", [note["id"]], "release")
    return note


def _regen(plane, moment: str, ref: str, by: str, ids: list[str], map_moment: str) -> None:
    from sh_platform.graph.knowledge_map import try_moment
    try:
        A.regenerate(plane, moment, ref, by, ids)
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the architecture record was not regenerated for %s", moment, exc_info=True)
    try_moment(plane, map_moment, ref, by)


def on_release(plane, by: str) -> None:
    """For prove.py's release route: move every change waiting for the release now instead of on the next read."""
    for n in all_notes(plane):
        if n.get("state") == "waiting_release":
            _sync(plane, n)


def _reopen(note: dict, n: int) -> None:
    note["state"] = STATE_AT[n]
    for s in note["steps"]:
        if s["n"] >= n:
            s["signed"] = None
            s["opened_at"] = _now() if s["n"] == n else None


# ---- what a viewer gets ---------------------------------------------------------------------------------------------------------------

def _days(plane, at: str | None) -> int | None:
    if not at:
        return None
    from sh_platform.intents import clock
    try:
        return int(clock.working_days_between(datetime.fromisoformat(at), datetime.now(timezone.utc)))
    except (ValueError, TypeError):
        return None


def _visible(plane, viewer: view.Viewer, note: dict, intent: dict, ppl: dict) -> bool:
    if BUILD_USERS & set(viewer.roles) or any(_is(viewer, p["name"]) for p in ppl.values()):
        return True
    people = intent.get("people") or {}
    rows = [people.get(k) for k in ("organiser", "sponsor", "decider", "owner", "reporter")]
    rows += [p for k in ("participants", "advisers") for p in people.get(k) or []]
    return any(isinstance(p, dict) and ((viewer.account_id and p.get("account_id") == viewer.account_id) or _is(viewer, p.get("name"))) for p in rows)


def summary(plane, note: dict, ppl: dict) -> dict:
    cur = STEP_OF.get(note["state"], 0)
    last = note["returns"][-1] if note.get("returns") else None
    steps = []
    for (n, role, word), s in zip(STEPS, note["steps"]):
        st = ("signed" if s.get("signed") else
              ("drafting" if note["state"] == "drafting" else
               "sent_back" if last and last.get("to") == n and str(last.get("at") or "") >= str(s.get("opened_at") or "") else "with")
              if n == cur and note["state"] not in ("live", "stopped", "waiting_release") else "waiting")
        steps.append({"n": n, "name": word, "role": role, "person": ppl[role]["name"], "person_mark": ppl[role]["mark"], "state": st,
                      "days": _days(plane, s.get("opened_at")) if st in ("with", "sent_back", "drafting") else None, "signed": s.get("signed")})
    return {"id": note["id"], "intent_id": note["intent_id"], "title": note.get("title"), "state": note["state"], "step": cur, "steps": steps,
            "last_return": last, "opened_at": note.get("opened_at")}


def _run_notes(plane, viewer: view.Viewer, note: dict) -> list[dict] | None:
    """Flow's note on the latest run of each source the change touches; None when Flow is not there (the payload then has no run_notes)."""
    try:
        from sh_platform.build.agents import flow as flow_notes, runtime as R
        rt = R.runtime_for_plane(plane, viewer)
    except Exception:  # ponytail: a missing Flow keeps the screen as it was
        return None
    last = {}
    for r in (_rd(plane.path("warehouse", "runs.json"), {}) or {}).get("runs") or []:
        if isinstance(r, dict) and r.get("id"):
            last[r.get("source")] = r["id"]
    out = []
    for src in dict.fromkeys(s.get("source") for s in note["sections"]["build_steps"] if s.get("source")):
        try:
            n = flow_notes.explain_run(plane, last[src], rt) if src in last else None
        except Exception:
            log.warning("Flow could not explain a run for %s", src, exc_info=True)
            n = None
        out.append({"source": src, "run_id": last.get(src) if n else None, "note": n})
    return out


def detail(plane, viewer: view.Viewer, note: dict, intent: dict, ppl: dict) -> dict:
    out = summary(plane, note, ppl)
    hyp = hypothesis(plane, intent)
    build = _steps_done(plane, note)
    secs = {**note["sections"], "build_steps": build, "tests": _tests(plane, note, hyp) if note["state"] not in ("with_architect", "with_approver", "building") else []}
    cur, role = out["step"], dict((n, r) for n, r, _ in STEPS).get(out["step"])
    comp = completeness(plane, note)
    can = bool(role) and note["state"] not in ("live", "stopped", "waiting_release") and may_act(viewer, role, ppl[role])
    gate = None
    if role and not ppl[role]["name"] and role != "tester":
        gate = "Not named yet. Name them in the charter: Who does what"
    elif cur == 2:
        signer = (note["steps"][0].get("signed") or {}).get("by")
        it = _it_signer(plane)
        gate = (comp["gap"] or ("You signed the design as the architect, so another person approves it." if _is(viewer, signer) else None) or
                (f"{it} signs the infrastructure part first." if it and _infra_changed(note) and not note.get("it_signed") else None))
    elif cur == 3:
        gate = next((f"The {s.get('source', '').replace('_', ' ')} pipeline has not run yet" for s in build if not s["done"]), None)
    elif cur == 4:
        gate = "Sign UAT or send back on the Prove page." if note["state"] == "testing" else "Waiting for the sponsor to sign the release."
    elif cur == 5 and not note.get("release_ref"):
        gate = "Waiting for the release."
    organiser = (intent.get("people") or {}).get("organiser") or {}
    out.update({
        "sections": {k: secs[k] for k in SECTIONS},
        "returns": note["returns"],
        "signatures": [{"step": s["n"], "name": s["signed"]["by"], "role": s["signed"].get("role") or ROLE_WORD[s["role"]], "at": s["signed"]["at"]}
                       for s in note["steps"] if s.get("signed")] + ([{"step": 4, "name": note["release_ref"]["by"], "role": "Sponsor, release", "at": note["release_ref"]["at"]}]
                                                                     if note.get("release_ref") else []),
        "handed": {"by": ((intent.get("build_handoff") or {}).get("by") or {}).get("name"), "at": (intent.get("build_handoff") or {}).get("at")} if intent.get("build_handoff") else None,
        "release": note.get("release_ref"),
        "build_progress": {"done": sum(1 for s in build if s["done"]), "of": len(build)} if build else None,
        "completeness": comp if cur == 2 else None,
        "gate": gate,
        "can_act": can,
        "can_edit": note["state"] == "with_architect" and may_act(viewer, "architect", ppl["architect"]),
        "can_stop": note["state"] not in ("live", "stopped") and ((viewer.account_id and organiser.get("account_id") == viewer.account_id) or _is(viewer, organiser.get("name"))),
        "drafted_from": f"Span, the architect, drafted this change from blueprint v{note.get('blueprint_version')} and the signed gap report.",
        "it_signer": _it_signer(plane) if _infra_changed(note) else None, "it_signed": note.get("it_signed"),
        "stopped": note.get("stopped"), "drafting_note": note.get("drafting_note"),
        "intent_readable": True,
    })
    if cur >= 4 and (rn := _run_notes(plane, viewer, note)) is not None:  # gate 3 pressed: testers and ops read what Flow saw
        out["run_notes"] = rn
    return out


def home_rows(plane, viewer: view.Viewer) -> dict:
    """For GET /api/company/build/home: `chain` rows (open changes) and the live count."""
    ensure(plane)
    rows, live = [], 0
    for n in all_notes(plane):
        live += n["state"] == "live"
        if n["state"] not in ("live", "stopped"):
            rows.append(summary(plane, _sync(plane, n), people_of(plane, _intent(plane, n.get("intent_id")), n)))
    return {"chain": rows, "live": live}


# ---- routes ---------------------------------------------------------------------------------------------------------------------------

def _ctx(request: Request, cid: str | None = None):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return None, _err(403, "forbidden", "This company space cannot be opened.")
    ensure(plane)
    if cid is None:
        return (plane, viewer, None, None, None), None
    if not CID.fullmatch(cid) or not _path(plane, cid).is_file():
        return None, _err(404, "not_found", "There is no such change.")
    note = _sync(plane, _rd(_path(plane, cid), {}))
    intent = _intent(plane, note.get("intent_id"))
    ppl = people_of(plane, intent, note)
    if not _visible(plane, viewer, note, intent, ppl):
        return None, _err(404, "not_found", "There is no such change.")
    return (plane, viewer, note, intent, ppl), None


@router.get("/api/company/build/changes")
def get_changes(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer = c[0], c[1]
    out = []
    for n in all_notes(plane):
        intent = _intent(plane, n.get("intent_id"))
        ppl = people_of(plane, intent, n)
        if _visible(plane, viewer, n, intent, ppl):
            out.append(summary(plane, _sync(plane, n), ppl))
    return {"changes": out, "live": sum(1 for n in out if n["state"] == "live")}


@router.get("/api/company/build/changes/{cid}")
def get_change(request: Request, cid: str):
    c, e = _ctx(request, cid)
    return e or detail(*c[:2], *c[2:])


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


def _reason(b: dict, key: str = "reason") -> str | None:
    r = b.get(key)
    return r.strip()[:MAX_TEXT] if isinstance(r, str) and r.strip() else None


def _sign(note: dict, n: int, viewer: view.Viewer) -> None:
    note["steps"][n - 1]["signed"] = {"by": viewer.name, "role": ROLE_WORD[STEPS[n - 1][1]], "at": _now()}
    if n < 5:
        note["steps"][n]["opened_at"] = _now()


def _act(request: Request, cid: str, step: int, b: dict):
    """Common checks for a step button: the change is at that step and the viewer is the named person. Returns (ctx, error)."""
    c, e = _ctx(request, cid)
    if e:
        return None, e
    plane, viewer, note, intent, ppl = c
    if STEP_OF.get(note["state"]) != step or note["state"] in ("live", "stopped", "waiting_release"):
        return None, _err(409, "wrong_step", "This change is not at that step.")
    role = STEPS[step - 1][1]
    if not ppl[role]["name"] and role != "tester":
        return None, _err(409, "not_named", "Nobody is named for this step. Name them in the charter: Who does what.")
    if not may_act(viewer, role, ppl[role]):
        return None, _err(403, "forbidden", f"Only {ppl[role]['name'] or 'the named person'}, the {ROLE_WORD[role].lower()}, may do this.")
    return c, None


def _save(plane, note: dict) -> None:
    write_json_atomic(_path(plane, note["id"]), note)


@router.post("/api/company/build/changes/{cid}/send")
async def post_send(request: Request, cid: str):
    c, e = _act(request, cid, 1, {})
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        _sign(note, 1, viewer)
        note["state"] = "with_approver"
        _save(plane, note)
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/redraft")
async def post_redraft(request: Request, cid: str):
    b = await _body(request)
    c, e = _act(request, cid, 1, b)
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    if not (why := _reason(b, "note")):
        return _err(422, "invalid", "Say what should change.")
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        if not note.get("source"):  # ponytail: a note opened by open_note has no records to redraft from; its lines are edited by hand
            note = _draft(plane, note, intent, _gap_outcome(plane, intent))
        note["redrafts"] = [*(note.get("redrafts") or []), {"by": viewer.name, "note": why, "at": _now()}]
        _save(plane, note)
        if not note.get("source"):
            note = _span_draft(plane, note, viewer.name)
    A.propose(plane, cid, note["components"]["added"] + note["components"]["changed"])
    return detail(plane, viewer, note, intent, ppl)


@router.put("/api/company/build/changes/{cid}/lines")
async def put_line(request: Request, cid: str):
    """The architect edits a guessed line at step 1: it becomes stated, by them."""
    b = await _body(request)
    c, e = _act(request, cid, 1, b)
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    sec, i, text = b.get("section"), b.get("index"), _reason(b, "text")
    if sec not in SECTIONS or not isinstance(i, int) or text is None:
        return _err(422, "invalid", "Send the section, the line number and the new text.")
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        if not 0 <= i < len(note["sections"][sec]):
            return _err(404, "not_found", "There is no such line.")
        note["sections"][sec][i] = {**note["sections"][sec][i], "text": text, "mark": "stated", "by": viewer.name, "at": _now()}
        _save(plane, note)
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/approve")
async def post_approve(request: Request, cid: str):
    """Step 2. The head of department approves the design: the change note and the blueprint are signed in one act (C33). With body
    {"part": "infrastructure"} the IT signer (company setting it_signer, C26) signs the infrastructure part instead."""
    b = await _body(request)
    if b.get("part") == "infrastructure":
        c, e = _ctx(request, cid)
        if e:
            return e
        plane, viewer, note, intent, ppl = c
        it = _it_signer(plane)
        if note["state"] != "with_approver" or not it or not _infra_changed(note):
            return _err(409, "wrong_step", "No infrastructure part waits for a signature.")
        if not _is(viewer, it):
            return _err(403, "forbidden", f"Only {it} signs the infrastructure part.")
        with lock_for(_path(plane, cid)):
            note = _rd(_path(plane, cid), note)
            note["it_signed"] = {"by": viewer.name, "at": _now()}
            _save(plane, note)
        return detail(plane, viewer, note, intent, ppl)
    c, e = _act(request, cid, 2, b)
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    if _is(viewer, (note["steps"][0].get("signed") or {}).get("by")):
        return _err(403, "own_design", "You signed the design as the architect, so another person approves it.")
    if gap := completeness(plane, note)["gap"]:
        return _err(409, "incomplete", gap)
    it = _it_signer(plane)
    if it and _infra_changed(note) and not note.get("it_signed"):
        return _err(409, "it_first", f"{it} signs the infrastructure part first.")
    bp_path = plane.path("build", "blueprint.json")
    with lock_for(bp_path):
        bp = _rd(bp_path, None)
        if not isinstance(bp, dict) or bp.get("basis") == "draft baseline":
            return _err(409, "no_blueprint", "There is no blueprint drafted from a signed baseline to sign yet.")
        if bp.get("state") != "signed":
            bp = {**bp, "state": "signed", "signed_by": [{"name": viewer.name, "role": "Head of department", "at": _now()}]}
            write_json_atomic(bp_path, bp)
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        _sign(note, 2, viewer)
        note["state"], note["blueprint_version"] = "building", bp.get("version")
        _save(plane, note)
    try:  # the design document is signed in the same act as the blueprint (plan S2); None when there is no draft
        from sh_platform.build import design_doc
        design_doc.sign(plane, viewer.name, "Head of department")
    except ImportError:
        pass
    try:  # Span reviews the model once after the signature, beside the request (same hook as blueprint/sign)
        from sh_platform.build.agents.routes import after_blueprint_signed
        after_blueprint_signed(request, plane)
    except Exception:  # noqa: BLE001  a failed review never undoes a signature
        log.warning("Span's review after the chain signature did not start", exc_info=True)
    A.set_state(plane, cid, "approved")
    _regen(plane, "blueprint_signed", f"v{bp.get('version')}", viewer.name, [cid], "blueprint_signed")
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/built")
async def post_built(request: Request, cid: str):
    """Step 3. Enabled only when every build step is done; reopens the UAT of the change's measures (a new build is a new result)."""
    c, e = _act(request, cid, 3, {})
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    steps = _steps_done(plane, note)
    if miss := next((s for s in steps if not s["done"]), None):
        return _err(409, "not_built", f"The {str(miss.get('source', '')).replace('_', ' ')} pipeline has not run yet.")
    prove = plane.path("build", "prove.json")
    with lock_for(prove):
        doc = _rd(prove, {}) or {}
        for m in doc.get("measures") or []:
            if isinstance(m, dict) and m.get("code") in (note.get("measures") or []):
                m["uat"] = {"state": "pending", "by": None, "at": None, "note": f"Opened again for change {cid}"}
                m["release_ready"] = False
        if doc:
            write_json_atomic(prove, doc)
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        _sign(note, 3, viewer)
        note["state"], note["build_snapshot"] = "testing", [{k: s.get(k) for k in ("text", "contract", "done")} for s in steps]
        _save(plane, note)
    A.set_state(plane, cid, "built")
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/take-over")
async def post_take_over(request: Request, cid: str):
    c, e = _act(request, cid, 5, {})
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    if not note.get("release_ref"):
        return _err(409, "no_release", "Waiting for the release.")
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        _sign(note, 5, viewer)
        note["state"] = "live"
        _save(plane, note)
    A.set_state(plane, cid, "live")
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/send-back")
async def post_send_back(request: Request, cid: str):
    """{to, reason}: 2->1, 3->1, 3->2, 4->3 (the tester; the Prove page's send-back does the same), 5->5 ("Not ready to take over")."""
    b = await _body(request)
    c, e = _ctx(request, cid)
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    frm, to = STEP_OF.get(note["state"]), b.get("to")
    if note["state"] in ("live", "stopped", "waiting_release", "drafting") or (frm, to) not in BACK:
        return _err(409, "wrong_step", "This change cannot be sent there from its current step.")
    c, e = _act(request, cid, frm, b)
    if e:
        return e
    if not (why := _reason(b)):
        return _err(422, "invalid", "Say why it goes back.")
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        note["returns"].append({"from": frm, "to": to, "by": viewer.name, "reason": why, "at": _now()})
        if to != frm:
            _reopen(note, to)
        _save(plane, note)
    if to == 1:
        A.set_state(plane, cid, "proposed")
    return detail(plane, viewer, note, intent, ppl)


@router.post("/api/company/build/changes/{cid}/stop")
async def post_stop(request: Request, cid: str):
    b = await _body(request)
    c, e = _ctx(request, cid)
    if e:
        return e
    plane, viewer, note, intent, ppl = c
    org = (intent.get("people") or {}).get("organiser") or {}
    if not ((viewer.account_id and org.get("account_id") == viewer.account_id) or _is(viewer, org.get("name"))):
        return _err(403, "forbidden", "Only the Initiative's organiser stops a change.")
    if note["state"] in ("live", "stopped"):
        return _err(409, "wrong_step", "This change is already live or stopped.")
    if not (why := _reason(b)):
        return _err(422, "invalid", "Say why the change stops.")
    with lock_for(_path(plane, cid)):
        note = _rd(_path(plane, cid), note)
        note["state"], note["stopped"] = "stopped", {"by": viewer.name, "at": _now(), "reason": why}
        _save(plane, note)
    A.drop(plane, cid)
    return detail(plane, viewer, note, intent, ppl)


# ---- for neighbours: Pulse, alerts --------------------------------------------------------------------------------------------------------

def pulse_lines(plane, v: view.Viewer) -> dict[str, list[dict]]:
    """{decide: [...], watch: [...]}: one line for the person whose step it is, one to the person a change was sent back to, and the
    'architecture changed' brief for 7 days after a regeneration (everyone who may open the map)."""
    from sh_platform.pulse.lines import line
    decide, watch = [], []
    words = {1: "Span drafted the change for {t}. Check it.", 2: "Approve the design for {t}", 3: "Build {t} from change note {c}",
             4: "Test {t}", 5: "Take over {t} from today"}
    for n in all_notes(plane):
        n = _sync(plane, n)
        if n["state"] in ("live", "stopped", "waiting_release", "drafting"):
            continue
        step = STEP_OF[n["state"]]
        role = STEPS[step - 1][1]
        ppl = people_of(plane, _intent(plane, n.get("intent_id")), n)
        if not may_act(v, role, ppl[role]):
            continue
        t, last = n.get("title") or n["id"], (n.get("returns") or [None])[-1]
        href = f"/centre/build/change/{n['id']}?step={step}"
        if last and last.get("to") == step and str(last.get("at")) >= str(n["steps"][step - 1].get("opened_at") or ""):
            decide.append(line(f"chain-back:{n['id']}", "request", f"{t} was sent back at {STEPS[last['from'] - 1][2]}: {last['reason']}", n["id"], href,
                               "Open the change note", f"build/changes/{n['id']}.json", last.get("at")))
        else:
            decide.append(line(f"chain:{n['id']}:{step}", "signature" if step in (2, 5) else "request", words[step].format(t=t, c=n["id"]), n["id"], href,
                               "Open the change note", f"build/changes/{n['id']}.json", n["steps"][step - 1].get("opened_at")))
    rec = A.read(plane)
    h = (rec.get("history") or [None])[-1]
    if h and h.get("changes") and (datetime.now(timezone.utc) - datetime.fromisoformat(h["at"])).days < 7:
        titles = {n["id"]: n.get("title") for n in all_notes(plane)}
        t = ", ".join(titles.get(x) or x for x in h["changes"])
        watch.append(line(f"arch:v{h['version']}", "brief", f"The architecture changed: {len(h['added'])} components added by {t}", f"Version {h['version']}",
                          f"/centre/build/architecture?v={h['version']}&focus=change", "See what changed", "build/architecture/record.json", h["at"]))
    return {"decide": decide, "watch": watch}


def alert_fields(plane, source: str) -> dict:
    """For ops/alerts: {change_id, tell} for an alert on this pipeline source. Before `live` the developer is told, after it the ops person."""
    notes = [n for n in sorted(all_notes(plane), key=lambda x: x["id"], reverse=True) if n["state"] != "stopped"]

    def names(n: dict) -> bool:  # a build step for the source, or (note opened before the pipeline existed) a what-changes line for it
        return any(s.get("source") == source for s in n["sections"]["build_steps"])             or any(s.get("component") == f"source:{source}" for s in n["sections"].get("what_changes") or [])
    # SF15: a pipeline made after its note opened has no build step in it; the newest open note still has someone to tell
    for n in [n for n in notes if names(n)] or notes[:1]:
        ppl = people_of(plane, _intent(plane, n.get("intent_id")), n)
        return {"change_id": n["id"], "tell": ppl["ops" if n["state"] == "live" else "developer"]["name"]}
    return {"change_id": None, "tell": None}


def install(app: FastAPI) -> None:
    """Called from app.py: the chain and the architecture routes."""
    app.include_router(router)
    app.include_router(A.router)
