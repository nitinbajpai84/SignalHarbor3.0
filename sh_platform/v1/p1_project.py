"""Card P1: projects and artefacts (docs/plan/V1-BUILD.md, Round 6).

A project `projects/<pid>.json` is created with the intent of work and carries its four artefacts (intent of work, system design,
build pack, consumption brief). Artefact state and the early stages are read from the artefact records on every read, so no other
card has to tell the project anything. Comments `projects/<pid>/comments.json` are anchored to an artefact line, written by an
agent or a person and addressed to one person (by name); P2 turns the open ones into cards. Agents call `comment(...)` with a
project id or an intent id (guarded import on their side)."""
from __future__ import annotations

import io
import logging
import re
import secrets
from contextlib import suppress
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)

KINDS = ("intent", "design", "build_pack", "brief", "run_book", "benchmarks")
KIND_NAMES = {"intent": "Intent of work", "design": "System design", "build_pack": "Build pack", "brief": "Consumption brief", "run_book": "Run book", "benchmarks": "Benchmark sheet"}
STAGES = ("talking", "signed", "designed", "built", "live")
PEOPLE = ("raiser", "sponsor", "builder", "head_of_data", "ops")
AGENTS = {"north": "North", "span": "Span", "flow": "Span", "lumen": "Lumen", "watcher": "Watcher", "nira": "Nira"}
STATES = ("open", "answered", "resolved")
QUIET = ("handover", "note", "suggestion")  # comments that tell, not ask: they never hold a signature
# who signs each artefact (people keys, first named wins); also who may resolve a comment on it besides its author
SIGNERS = {"intent": ("raiser", "sponsor"), "design": ("head_of_data", "builder"), "build_pack": ("head_of_data", "builder"),
           "brief": ("raiser", "sponsor"), "run_book": ("ops",), "benchmarks": ("raiser",)}
_PID = re.compile(r"^prj-[0-9a-f]{8}$")
_IID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
MAX_TEXT = 4000


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ppath(plane, pid: str):
    if not isinstance(pid, str) or not _PID.match(pid):
        raise Refused(404, "There is no such project.")
    return plane.path("projects", f"{pid}.json")


def _cpath(plane, pid: str):
    _ppath(plane, pid)
    return plane.path("projects", pid, "comments.json")


def _load(path, blank):
    try:
        got = read_json_strict(path)
    except (OSError, ValueError):
        raise Refused(500, "The project could not be read. Please ask your administrator.") from None
    return blank if got is None else got


def record_paths(iid: str) -> dict:
    return {"intent": f"intents/{iid}/sow.json", "design": f"build/blueprint_conversation/{iid}.json",
            "build_pack": f"build/mapping/{iid}.json", "brief": f"consume/brief/{iid}.json", "run_book": f"build/runbook/{iid}.json",
            "benchmarks": f"intents/{iid}/benchmarks.json"}


def _rec(plane, rel: str):
    try:
        return read_json_strict(plane.path(*rel.split("/")), dict)
    except (OSError, ValueError):
        return None


# ---- the project ---------------------------------------------------------------------------------------------------------------

def for_intent(plane, iid: str) -> dict | None:
    """The project created with this intent, or None (ponytail: a glob over projects/; an index once there are hundreds)."""
    for p in sorted(plane.path("projects").glob("prj-*.json")):
        try:
            rec = read_json_strict(p, dict) or {}
        except (OSError, ValueError):
            continue
        if rec.get("intent_id") == iid:
            return rec
    return None


def create_project(plane, iid: str, title: str, started_by: str, account_id: str | None = None) -> dict:
    """The project for this intent; made once (a second call returns the first)."""
    if not isinstance(iid, str) or not _IID.match(iid):
        raise Refused(404, "There is no such intent.")
    with lock_for(plane.path("projects")):
        got = for_intent(plane, iid)
        if got:
            return got
        pid = "prj-" + secrets.token_hex(4)
        rec = {"id": pid, "intent_id": iid, "title": str(title or "")[:300], "started_by": started_by, "started_at": _now(),
               "stage": "talking",
               "artefacts": [{"kind": k, "record_path": p, "version": None, "state": "draft", "signed_by": None, "signed_at": None}
                             for k, p in record_paths(iid).items()],
               "people": {"raiser": started_by, "sponsor": None, "builder": None, "head_of_data": None, "ops": None}, "raiser_id": account_id}
        with suppress(Exception):  # G1: Internal, the company's sponsor on the team
            from sh_platform.v1 import g1_access
            rec.update(g1_access.defaults(plane))
        write_json_atomic(_ppath(plane, pid), rec)
    with suppress(Exception): from sh_platform.v1.m1_map import touch; touch(plane)  # K2: a new project lands on the company map
    return rec


def project_of(plane, iid: str) -> dict | None:
    """The intent's project; made on first ask for an intent started before projects existed (None when there is no intent)."""
    got = for_intent(plane, iid)
    if got:
        return _sync(plane, got)
    if not isinstance(iid, str) or not _IID.match(iid):
        return None
    sow = _rec(plane, f"intents/{iid}/sow.json")
    if sow is None:
        return None
    turns = (_rec(plane, f"intents/{iid}/thread.json") or {}).get("turns") or []
    first = next((t.get("name") for t in turns if isinstance(t, dict) and t.get("by") == "person"), None)
    return _sync(plane, create_project(plane, iid, sow.get("title") or iid, first))


def _sync(plane, rec: dict) -> dict:
    """Artefact state, version and signature from the records themselves; the early stages follow them."""
    have = {a["kind"] for a in rec.setdefault("artefacts", [])}  # a project made before a kind existed gets it on read
    rec["artefacts"] += [{"kind": k, "record_path": p, "version": None, "state": "draft", "signed_by": None, "signed_at": None}
                         for k, p in record_paths(rec["intent_id"]).items() if k not in have]
    for a in rec["artefacts"]:
        r = _rec(plane, a["record_path"]) or {}
        if a["kind"] in ("intent", "run_book"):
            sig = r.get("signature") or {}
            a.update(version=r.get("version"), state="signed" if r.get("state") == "signed" else "draft",
                     signed_by=sig.get("name"), signed_at=sig.get("at"))
        elif a["kind"] == "benchmarks":  # G3: signed by the raiser (and the owners of KPIs that are not theirs)
            a.update(version=r.get("version"), state="signed" if r.get("state") == "signed" else "draft",
                     signed_by=", ".join(dict.fromkeys(x.get("name") for x in r.get("signatures") or [] if x.get("version") == r.get("version"))) or None,
                     signed_at=(r.get("signature") or {}).get("at"))
        elif a["kind"] == "design":
            done = r.get("state") == "approved"
            a.update(state="signed" if done else "draft", signed_by=r.get("approved_by") if done else None,
                     signed_at=r.get("approved_at") if done else None)
        elif a["kind"] == "build_pack":
            a["version"] = r.get("version")  # signed by P4 (`signed`) when the benchmarks are met
        if a["kind"] == "intent" and a["state"] == "signed" and not rec["people"].get("sponsor") and a["signed_by"] != rec["people"].get("raiser"):
            rec["people"]["sponsor"] = a["signed_by"]  # V6: the person who signed the intent of work is the project's sponsor (a raiser's own signature is not)
        if a["kind"] == "design" and a["state"] == "signed" and not rec["people"].get("head_of_data"):
            rec["people"]["head_of_data"] = a["signed_by"]
    state = {a["kind"]: a["state"] for a in rec.get("artefacts") or []}
    if rec.get("stage") not in ("built", "live"):
        rec["stage"] = "designed" if state.get("design") == "signed" else "signed" if state.get("intent") == "signed" else "talking"
    return rec


def read(plane, pid: str) -> dict:
    rec = _load(_ppath(plane, pid), None)
    if not isinstance(rec, dict):
        raise Refused(404, "There is no such project.")
    return _sync(plane, rec)


def all_projects(plane) -> list[dict]:
    out = []
    for p in sorted(plane.path("projects").glob("prj-*.json")):
        try:
            out.append(read(plane, p.stem))
        except Refused:
            continue
    return out


def _update(plane, pid: str, fn) -> dict:
    path = _ppath(plane, pid)
    with lock_for(path):
        rec = read(plane, pid)
        fn(rec)
        write_json_atomic(path, rec)
    return rec


def set_person(plane, pid: str, key: str, name: str | None) -> dict:
    """Record who holds a part on the project (P3: the builder picks it up; P5: ops)."""
    if key not in PEOPLE:
        raise Refused(400, "Unknown part on the project.")
    return _update(plane, pid, lambda r: r["people"].__setitem__(key, name))


def set_stage(plane, pid: str, stage: str) -> dict:
    """Move the project forward to built or live (P4, P5); never backwards."""
    if stage not in STAGES:
        raise Refused(400, "Unknown stage.")
    return _update(plane, pid, lambda r: r.__setitem__("stage", max(r["stage"], stage, key=STAGES.index)))


def signed(plane, pid: str, kind: str, by: str) -> dict:
    """Mark an artefact signed that has no record state of its own (the build pack, the brief)."""
    def go(r):
        for a in r["artefacts"]:
            if a["kind"] == kind:
                a.update(state="signed", signed_by=by, signed_at=_now())
    out = _update(plane, _pid_of(plane, pid), go)
    with suppress(Exception): from sh_platform.v1.m1_map import touch; touch(plane)  # K2: a signed build pack or brief lands on the map
    return out


# ---- comments ------------------------------------------------------------------------------------------------------------------

def _pid_of(plane, pid_or_iid: str) -> str | None:
    if isinstance(pid_or_iid, str) and _PID.match(pid_or_iid):
        return pid_or_iid
    got = project_of(plane, pid_or_iid)
    return got["id"] if got else None


def comments(plane, pid: str, artefact: str | None = None) -> list[dict]:
    got = _load(_cpath(plane, pid), [])
    return [c for c in got if isinstance(c, dict) and (artefact is None or c.get("artefact") == artefact)]


def _person(rec: dict, to: str | None) -> str | None:
    """A name, or a part on the project ("sponsor") turned into its name; the raiser when nobody holds that part yet."""
    if to in PEOPLE:
        return rec["people"].get(to) or rec["people"].get("raiser")
    return to


def comment(plane, pid: str, artefact: str, line_ref: str | None, by: str, to: str | None, text: str, *, kind: str = "comment") -> dict | None:
    """Add one comment and return it. `pid` may be the intent id (agents know only that); None when the intent has no project.
    `by` is an agent key or a person's name; `to` a person's name or a part on the project (raiser, sponsor, builder, ...)."""
    pid = _pid_of(plane, pid)
    if pid is None:
        return None
    if artefact not in KINDS:
        raise Refused(400, "Unknown artefact.")
    text = str(text or "").strip()
    if not text:
        raise Refused(400, "A comment needs some text.")
    rec = read(plane, pid)
    entry = {"id": "c_" + secrets.token_hex(6), "artefact": artefact, "line_ref": str(line_ref or "") or None,
             "by": str(by)[:120], "name": AGENTS.get(by, str(by)[:120]), "to": _person(rec, to), "text": text[:MAX_TEXT],
             "kind": kind, "state": "open", "at": _now(), "answer": None, "answered_at": None}
    path = _cpath(plane, pid)
    with lock_for(path):
        got = comments(plane, pid)
        got.append(entry)
        write_json_atomic(path, got)
    if artefact == "run_book" and kind == "comment":  # T2: ops asking the data engineer is a ticket (guarded; the comment is its thread)
        with suppress(Exception): from sh_platform.v1 import t2_tickets; t2_tickets.from_runbook_comment(plane, pid, entry)
    return entry


def _change(plane, pid: str, cid: str, fn) -> dict:
    path = _cpath(plane, pid)
    with lock_for(path):
        got = comments(plane, pid)
        c = next((x for x in got if x.get("id") == cid), None)
        if c is None:
            raise Refused(404, "There is no such comment.")
        fn(c)
        write_json_atomic(path, got)
    return c


def answer(plane, pid: str, cid: str, who: str, text: str) -> dict:
    """The addressee answers."""
    text = str(text or "").strip()[:MAX_TEXT]
    if not text:
        raise Refused(400, "Write your answer.")

    c0 = next((c for c in comments(plane, pid) if c.get("id") == cid), None)
    if c0 and c0.get("kind") == "approval" and str(c0.get("line_ref") or "").startswith("deviation:"):  # the raiser never answers
        from sh_platform.v1 import g4_deviations as G4
        G4.check_answerer(plane, read(plane, pid)["intent_id"], c0["line_ref"].removeprefix("deviation:"), who)

    def go(c):
        if c["to"] != who:
            raise Refused(403, f"Only {c['to'] or 'the person it is addressed to'} can answer this comment.")
        if c["state"] == "resolved":
            raise Refused(409, "This comment is resolved.")
        if c.get("kind") == "approval":  # G4: only "approved" or "not approved" answers a deviation request
            from sh_platform.v1 import g4_deviations as G4
            G4.decision(text)
        c.update(state="answered", answer=text, answered_at=_now())
    got = _change(plane, pid, cid, go)
    if got.get("kind") == "approval":  # G4: the decision acts (implement and amend, or decline) once the answer is kept
        from sh_platform.v1 import g4_deviations as G4
        G4.after_answer(plane, read(plane, pid)["intent_id"], got, who)
    return got


def signers(rec: dict, kind: str) -> set[str]:
    a = next((x for x in rec.get("artefacts") or [] if x["kind"] == kind), {})
    return {n for n in [*(rec["people"].get(k) for k in SIGNERS.get(kind, ())), a.get("signed_by")] if n}


def resolve(plane, pid: str, cid: str, who: str) -> dict:
    """The author or the signer resolves."""
    rec = read(plane, pid)

    def go(c):
        if c["state"] == "open" and who != c.get("by"):
            raise Refused(409, "Answer it before it is resolved.")
        if who != c.get("by") and who not in signers(rec, c["artefact"]):
            raise Refused(403, "Only the person who wrote the comment or the person who signs this document can resolve it.")
        c.update(state="resolved", resolved_by=who, resolved_at=_now())
    return _change(plane, pid, cid, go)


def sign_block(plane, iid: str, kind: str, signer: str) -> str | None:
    """A plain sentence when `signer` still has an open comment on this artefact, else None. never raises (the sign hooks)."""
    if not signer:
        return None
    try:
        pid = _pid_of(plane, iid)
        if pid is None:
            return None
        n = sum(1 for c in comments(plane, pid, kind)
                if c.get("state") == "open" and c.get("to") == signer and c.get("kind") not in QUIET)
    except Exception:  # noqa: BLE001 - a broken project file never stops a signature on its own
        log.warning("the comment check before signing failed for %s", iid)
        return None
    if not n:
        return None
    return (f"{signer}, {n} comment{'s' if n > 1 else ''} on the {KIND_NAMES[kind].lower()} "
            f"{'are' if n > 1 else 'is'} waiting for your answer. Answer {'them' if n > 1 else 'it'} before you sign.")


def check_sign(plane, iid: str, kind: str, signer: str, error) -> None:
    """For the sign hooks: raise `error(sentence)` when `sign_block` has one."""
    block = sign_block(plane, iid, kind, signer)
    if block:
        raise error(block)


# ---- the artefact as a document of numbered lines ------------------------------------------------------------------------------

def _j(xs) -> str:
    return ", ".join(str(x) for x in xs or [] if x) or "none"


def _blocks(plane, iid: str, kind: str) -> list[tuple[str, list[str]]]:
    """(heading, lines) per section, read from the artefact's records. The intent of work reuses I4's own sections."""
    from sh_platform.v1 import i4_sow as S
    sow = _rec(plane, f"intents/{iid}/sow.json") or {}
    if kind == "intent":
        return S._blocks(sow)
    if kind == "design":
        conv = _rec(plane, f"build/blueprint_conversation/{iid}.json") or {}
        design = _rec(plane, f"build/design/{iid}.json") or {}
        return [
            ("1. The three layers", [str(x) for x in design.get("lines") or []]),
            ("2. Data model", [f"**{m.get('table')}** ({m.get('kind')}): {m.get('grain') or ''}. Keys: {_j(m.get('keys'))}."
                               + (f" {_j(m.get('relationships'))}." if m.get("relationships") else "")
                               + (f" History: {m['history']}." if m.get("history") else "")
                               for m in conv.get("data_model") or [] if isinstance(m, dict)]),
            ("3. Questions for the business", [f"{q.get('question') or q.get('text') or ''} "
                                               f"({'answered: ' + str(q.get('answer')) if q.get('settled') else 'open'})"
                                               for q in conv.get("questions") or [] if isinstance(q, dict)]),
            ("4. Agreed scope", [_j(conv.get("scope"))] if conv.get("scope") else []),
            ("5. Amendments", [f"{a.get('version')}: {a.get('summary')}. Before: {a.get('before')} After: {a.get('after')} Why: {a.get('why')} "
                               f"Signed by {a.get('signed_by')}." for a in conv.get("amendments") or [] if isinstance(a, dict)]),
        ]
    if kind == "build_pack":
        rows = [r for r in (_rec(plane, f"build/mapping/{iid}.json") or {}).get("rows") or [] if isinstance(r, dict)]
        return [
            ("1. Data catalogue", S._blocks(sow)[4][1]),
            ("2. ETL mapping", [f"{r.get('n')}. {r.get('layer')} {r.get('target_table')}.{r.get('target_field')} from "
                                f"{r.get('source_table') or '-'}.{r.get('source_field') or '-'}: {r.get('transformation') or 'as is'}"
                                + (f". Rule: {r['rule']}" if r.get("rule") else "") + f" ({r.get('status')})" for r in rows]),
            ("3. Testing approach", [f"{r.get('target_table')}.{r.get('target_field')}: {r['test']}" for r in rows if r.get("test")]),
        ]
    if kind == "brief":
        b = _rec(plane, f"consume/brief/{iid}.json") or {}
        return [
            ("1. Views", [f"**{v.get('name')}**" + (f" for {v['audience']}" if v.get("audience") else "") + f": {_j(v.get('kpis'))}"
                          + (f"; refreshed {v['refresh']}" if v.get("refresh") else "") for v in b.get("views") or [] if isinstance(v, dict)]),
            ("2. Outside feeds", [str(f) for f in b.get("feeds_wanted") or []]),
            ("3. What-if levers", [f"{lv.get('name')} (affects {_j(lv.get('affects'))})" for lv in b.get("levers") or [] if isinstance(lv, dict)]),
            ("4. Dashboards in use today", [str(d.get("name") if isinstance(d, dict) else d) for d in b.get("existing_dashboards") or []]),
            ("5. Notes", [str(n.get("text") if isinstance(n, dict) else n) for n in b.get("notes") or []]),
        ]
    if kind == "benchmarks":
        from sh_platform.v1 import g3_sheet as G3
        return [("1. Reported figures", G3.lines(G3.read(plane, iid)))]
    if kind == "run_book":
        from sh_platform.v1 import g2_runbook as R
        return R.blocks(plane, iid)
    raise Refused(404, "Unknown artefact.")


def document(plane, pid: str, kind: str) -> dict:
    """{kind, name, state, sections: [{n, heading, lines: [{ref "<section>.<line>", text}]}], comments}. Who may read it is G1's
    `may_see_project`, asked by the route (p1_routes) before this is called."""
    rec = read(plane, pid)
    if kind not in KINDS:
        raise Refused(404, "Unknown artefact.")
    art = next(a for a in rec["artefacts"] if a["kind"] == kind)
    sections = [{"n": i, "heading": h, "lines": [{"ref": f"{i}.{j}", "text": t} for j, t in enumerate(lines, 1)]}
                for i, (h, lines) in enumerate(_blocks(plane, rec["intent_id"], kind), 1)]
    return {"project": rec["id"], "kind": kind, "name": KIND_NAMES[kind], "title": rec["title"], **{k: art[k] for k in ("state", "version", "signed_by", "signed_at")},
            "signers": sorted(signers(rec, kind)), "sections": sections, "comments": comments(plane, pid, kind)}


def export(plane, pid: str, kind: str, fmt: str) -> tuple[bytes, str, str]:
    """(data, media type, file name). The build pack's mapping goes out as a spreadsheet; the rest as Word or Markdown."""
    doc = document(plane, pid, kind)
    stem = f"{re.sub(r'[^A-Za-z0-9]+', '-', doc['title']).strip('-')[:50] or 'project'}-{kind.replace('_', '-')}"
    if kind == "intent" and fmt in ("md", "docx"):  # T1b: the intent of work keeps its template's layout and headings
        from sh_platform.v1 import i4_sow as S
        iid = read(plane, pid)["intent_id"]
        lay, sow = S.layout_of(plane, iid), _rec(plane, f"intents/{iid}/sow.json") or {}
        if lay:
            from sh_platform.v1 import t1_layout as L
            head, note = f"{doc['name']}: {doc['title']}", f"Project {pid}, {doc['state']}."
            if fmt == "md":
                return L.to_markdown(lay, head, note).encode("utf-8"), "text/markdown; charset=utf-8", f"{stem}.md"
            if S.docx_available():
                return L.to_docx(lay, head, note), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{stem}.docx"
    if fmt == "md":
        out = [f"# {doc['name']}: {doc['title']}", f"Project {pid}, {doc['state']}.", ""]
        for s in doc["sections"]:
            out += [f"## {s['n']}. {s['heading'].split('. ', 1)[-1]}", ""] + ([f"{ln['ref']} {ln['text']}" for ln in s["lines"]] or ["Nothing yet."]) + [""]
        return "\n".join(out).encode("utf-8"), "text/markdown; charset=utf-8", f"{stem}.md"
    if fmt == "xlsx":
        if kind == "benchmarks":
            from sh_platform.v1 import g3_sheet as G3
            return G3.xlsx(G3.read(plane, read(plane, pid)["intent_id"])), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{stem}.xlsx"
        if kind != "build_pack":
            raise Refused(400, "Only the build pack and the benchmark sheet go out as a spreadsheet. Choose Word or Markdown.")
        from sh_platform.v1 import b3_mapping as M
        sheet = _rec(plane, f"build/mapping/{read(plane, pid)['intent_id']}.json")
        if not sheet:
            raise Refused(404, "There is no mapping sheet yet.")
        return M.xlsx(sheet), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{stem}.xlsx"
    if fmt == "docx":
        from sh_platform.v1 import i4_sow as S
        if not S.docx_available():
            raise Refused(404, "A Word file cannot be made on this server. Download the Markdown file instead.")
        import docx
        d = docx.Document()
        d.add_heading(f"{doc['name']}: {doc['title']}", 0)
        d.add_paragraph(f"Project {pid}, {doc['state']}.")
        for s in doc["sections"]:
            d.add_heading(s["heading"], 1)
            for ln in s["lines"] or [{"ref": "", "text": "Nothing yet."}]:
                d.add_paragraph(f"{ln['ref']} {ln['text']}".replace("**", "").strip())
        buf = io.BytesIO()
        d.save(buf)
        return buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{stem}.docx"
    raise Refused(400, "Choose Word, a spreadsheet or Markdown.")
