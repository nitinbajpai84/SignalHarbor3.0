"""Harbor 3.0 engine: one thread, three decisions. A thin layer over the 2.0 routes, called in-process (TestClient on the same app) as the people
the UC6 scripts used (docs/test/uc-live/uc6-scripts). Anita confirms; the engine acts for the other seats. Anything that fails becomes a question.

Chains (CHAINS): A after decision 1 (sign .. approved pack .. files read) -> decision 2; B after decision 2 (mappings, load, run on a copy,
compare) -> decision 3; C after "go live" (live, Lumen starter, morning note). Threads are JSON under <company>/v3/threads/."""
import logging
import base64
import json
import os
import re
import sys
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from sh_platform.v1 import v3_pdf as V  # PDFs go down the document path

LOCK = threading.RLock()
SYNC = False  # tests run chains inline
log = logging.getLogger(__name__)
PEOPLE = {"mei": "mei.chen", "daniel": "daniel.foo", "anita": "anita.rao", "leo": "leo.park", "grace": "grace.ong"}
ALL = ["company_admin", "sponsor", "analyst", "owner", "approver", "participant"]
NO_BENCH = "No report to compare with yet. Drop last month's report in the drop folder, or go live without a comparison."


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Q(Exception):
    """A step that needs a person: becomes a question event."""
    def __init__(self, text: str, options: list | None = None):
        super().__init__(text)
        self.text, self.options = text, options or []


# ---- store ------------------------------------------------------------------------------------------------------------------------

def _dir(plane):
    d = plane.path("v3", "threads")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load(plane, tid: str) -> dict:
    p = _dir(plane) / f"{re.sub(r'[^a-z0-9-]', '', tid)}.json"
    if not p.is_file():
        raise KeyError(tid)
    return json.loads(p.read_text(encoding="utf-8"))


def save(plane, th: dict) -> None:
    with LOCK:
        (_dir(plane) / f"{th['id']}.json").write_text(json.dumps(th, default=str), encoding="utf-8")


def all_threads(plane, discarded: bool = False) -> list[dict]:
    """Newest first. A discarded thread is kept on disk for the record but leaves the Desk, the lists and file recognition."""
    ths = (json.loads(p.read_text(encoding="utf-8")) for p in _dir(plane).glob("*.json"))
    return sorted((t for t in ths if discarded or t.get("stage") != "discarded"), key=lambda t: t["created"], reverse=True)


def _gone(plane, tid) -> bool:
    return load(plane, tid).get("stage") == "discarded"


def discard(app, plane, tid, reason, account_id) -> dict:
    """The person drops a thread they no longer want. Never deleted: who, when and why stay in the record."""
    th = load(plane, tid)
    if th["stage"] == "live":
        raise ValueError("This thread is live and runs every month. Ask your data engineer to switch it off first.")
    acct = app.state.account_store.get(account_id) or {}
    who = acct.get("display_name") if isinstance(acct, dict) else getattr(acct, "display_name", None)
    th["discarded"] = {"by": who, "at": now(), "reason": (reason or "").strip()[:300], "stage_was": th["stage"]}
    th["stage"], th["decision"], th["resume"] = "discarded", None, None
    ev(th, "decision_done", "Discarded" + (f": {th['discarded']['reason']}" if th["discarded"]["reason"] else "."), by=who or "You")
    save(plane, th)
    return th


def ev(th, kind, text=None, chips=None, by="Harbor") -> None:
    th["events"].append({k: v for k, v in {"at": now(), "kind": kind, "text": text, "chips": chips, "by": by}.items() if v is not None})


def _left(x) -> str:
    lo = x.th.get("left_out") or []
    return (" Left out because no file has arrived yet: " + ", ".join(lo) + ".") if lo else ""


def summary(th) -> dict:
    needs = int(th["stage"] in ("decision1", "decision2", "decision3", "question")) + len(th.get("exceptions") or [])
    return {"id": th["id"], "title": th["title"], "stage": th["stage"], "needs": needs, **({"next_run": th["next_run"]} if th.get("next_run") else {})}


def view(th) -> dict:
    return {**summary(th), "events": th["events"], "decision": th.get("decision"), "asked": th.get("asked", 0), "harbor_steps": len(th["steps"]), "now": th.get("now"), "record": th.get("record"), "started_by": th.get("started_by"), "brief": th.get("brief"), "process": _P.view_of(th)}


# ---- acting as the 2.0 seats ------------------------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, app, plane, th, account_id):
        self.app, self.plane, self.th, self.account_id, self.clients = app, plane, th, account_id, {}

    def client(self, who: str) -> TestClient:
        if who not in self.clients:
            st = self.app.state
            acct = (st.account_store.get(self.account_id) if who == "me"  # the person at the screen: their name goes on what they raise and sign
                    else st.account_store.get_by_email(f"{PEOPLE[who]}.{self.plane.company_id}@example.test") or st.account_store.get(self.account_id))
            cookie, csrf = st.sessions.create(acct)  # single-signer office: with no such seat the signed-in person acts
            c = TestClient(self.app, raise_server_exceptions=False, headers={"X-CSRF-Token": csrf})
            c.cookies.set("sh_session", cookie)
            c.cookies.set("sh_csrf", csrf)
            self.clients[who] = c
        return self.clients[who]

    def api(self, who, method, path, body=None, files=None, data=None, soft=False):
        r = self.client(who).request(method, path, json=body if files is None else None, files=files, data=data, timeout=600)
        try:
            out = r.json()
        except ValueError:
            out = {}
        if r.status_code >= 400:
            if soft:
                return {}
            d = out.get("detail") if isinstance(out, dict) else None
            msg = (out.get("message") if isinstance(out, dict) else None) or (d.get("message") if isinstance(d, dict) else d if isinstance(d, str) else None)
            raise Q(msg or f"{method} {path} answered {r.status_code}.")
        return out


def step(x, agent, action, ok=True, detail="", run_id=None) -> None:
    x.th["steps"].append({k: v for k, v in {"n": len(x.th["steps"]) + 1, "at": now(), "agent": agent, "action": action, "ok": ok, "run_id": run_id, "detail": detail}.items() if v is not None})


def _b(path_or_bytes) -> str:
    return base64.b64encode(path_or_bytes).decode()


def my_files(x, kind=None) -> list[dict]:
    if getattr(x, "app", None):  # files dropped before the brief existed are matched now, at the moment Harbor looks for them
        scan(x.app, x.plane)
    fs = [f for f in read_files(x.plane) if f.get("thread") == x.th["id"] and f["status"] in ("recognised", "loaded", "question")]
    return [f for f in fs if kind is None or (f["source"] == "benchmark") == (kind == "benchmark")]


def blob(plane, name: str) -> bytes:
    return plane.path("dropbox", name).read_bytes()


# ---- skills: each step is a catalogue skill; Harbor logs the call and says what it is doing (docs/v3/SKILLS-CATALOGUE.md) -----------------------

SKILLS_OF = {"a_sign": ("intent.sign",), "a_arch": ("model.find-reusable",), "a_samples": ("data.profile-file",), "a_pack": ("model.design-ready-table",),
             "a_intake": ("data.recognise-file", "map.map-file"), "b_load": ("run.load-file",), "b_run": ("run.on-copy",), "b_compare": ("check.against-source",),
             "c_live": ("build.go-live",), "c_lumen": ("consume.build-board",), "c_note": ("consume.write-morning-note",),
             "m_load": ("run.load-file",), "m_exceptions": ("action.detect-exception",)}


@contextmanager
def _skill(x, sid: str, text: str):
    """Run one skill: th["now"] says what is happening while it works, and the call is timed and logged (v3_skills.record)."""
    from sh_platform.v1 import v3_skills as S
    th = x.th
    th["now"] = {"skill": sid, "name": S.name_of(x.plane, sid), "text": text}
    try:
        save(x.plane, th)
    except Exception:  # noqa: BLE001 - saying what is happening never stops the work
        log.warning("could not save the working note", exc_info=True)
    try:
        with S.record(x.plane, th["id"], sid) as rec:
            yield rec
    finally:
        th["now"] = None


def _call(x, fn, action: str):
    """fn(x), as the catalogue skills it stands for (a step with no skill, such as a test's stub, just runs)."""
    ids = SKILLS_OF.get(getattr(fn, "__name__", ""), ())
    with ExitStack() as st:
        recs = [st.enter_context(_skill(x, i, action)) for i in ids]
        out = fn(x)
        for r in recs:
            r["detail"] = str(out or "")[:300]
        return out


def _learn(plane, th: dict, kind: str, text: str) -> None:
    """A person stepped in. The second time for the same kind, Harbor drafts a skill for a person to admit (best effort, off the request)."""
    entry = {"kind": kind, "at": now(), "text": text[:300]}
    th.setdefault("learn", []).append(entry)
    save(plane, th)  # on disk before the draft counts the repeats across threads

    def go():
        from sh_platform.v1 import v3_skills as S
        S.write_skill(plane, th, kind, [entry])
    if SYNC:
        go()
    else:
        threading.Thread(target=go, daemon=True).start()


# ---- chain A: intent signed .. pack approved .. files read ------------------------------------------------------------------------

def _team_up(x, pid: str) -> None:
    """Single-signer office: the people Harbor acts for join the project team, so an Internal project does not lock them out."""
    from sh_platform.v1 import g1_access as G
    st = x.app.state
    for who, role in (("mei", "raiser"), ("daniel", "sponsor"), ("grace", "admin"), ("leo", "engineer"), ("anita", "head of data")):
        acct = st.account_store.get_by_email(f"{PEOPLE[who]}.{x.plane.company_id}@example.test")
        if acct:
            G.join(x.plane, pid, acct.get("display_name"), role, acct.get("id"))


def a_sign(x):
    from sh_platform.v1 import v3_signoff as SO
    SO.check_signer(x)  # signs as the person at the screen; one who may not sign is told who may
    iid = x.th["iid"]
    pid = x.api("me", "GET", f"/api/v1/intents/{iid}/chat", soft=True).get("project_id")
    if pid:
        _team_up(x, pid)
    sow = x.api("me", "GET", f"/api/v1/intents/{iid}/sow")
    if sow.get("state") != "signed":  # a retry after a later step failed must not sign twice
        SO.before_sign(x)  # the self-signer's gap fill, for every signer; a gap only a person can say goes to the raiser, named
        sow = x.api("me", "GET", f"/api/v1/intents/{iid}/sow")
        x.api("me", "POST", f"/api/v1/intents/{iid}/sow/sign", {"confirm": True, "version": sow["version"], "note": "Confirmed in Harbor, Decision 1."})
    x.api("me", "POST", f"/api/v1/intents/{iid}/send-to-build", soft=True)
    x.th["pid"] = x.api("me", "GET", f"/api/v1/intents/{iid}/chat").get("project_id")
    if not x.th["pid"]:
        raise Q("The intent is signed but I could not find its project. Say what to do next.")
    _team_up(x, x.th["pid"])
    sig = (x.api("me", "GET", f"/api/v1/intents/{iid}/sow", soft=True) or {}).get("signature") or {}
    x.th["record"] = {"started_by": x.th.get("started_by"), "started_at": x.th.get("created"), "signed_by": sig.get("name"), "role": sig.get("role"),
                      "signed_at": sig.get("at"), "version": (x.api("me", "GET", f"/api/v1/intents/{iid}/sow", soft=True) or {}).get("version"),
                      "document": f"/api/v1/projects/{x.th['pid']}/artefacts/intent/export?format=docx",
                      "sent_at": (x.th.get("signoff") or {}).get("at"), "line": SO.record_line(x.th, sig.get("name"))}
    signed = x.api("me", "GET", f"/api/v1/intents/{iid}/chat", soft=True).get("sow") or {}
    x.th["sources"] = [s.get("name", "") for s in signed.get("sources") or []] or x.th.get("sources") or []  # the signed brief's sources
    SO.claim_files(x)  # files dropped before the sign-off are this thread's
    return "signed and sent to Build"


def a_handover(x):
    x.api("grace", "POST", f"/api/v1/projects/{x.th['pid']}/handover",
          {"to": "Leo Park", "due": (date.today() + timedelta(days=14)).isoformat(), "message": "Harbor hands this over to build."})
    return "handed to the data engineer"


def a_arch(x):
    A = f"/api/v1/build/p/{x.th['pid']}/architecture"
    s = x.api("leo", "GET", A + "/summary")
    x.th["systems"] = [{"id": i.get("id"), "name": i.get("name") or ""} for i in s.get("systems") or [] if i.get("id")]
    for i in x.th["systems"]:  # every file reaches Harbor through the drop folder or intake: an upload, never a connection to set up first
        x.api("leo", "PUT", f"{A}/systems/{i['id']}", {"channel": "upload", "note": "Files arrive through Harbor's drop folder."}, soft=True)
    x.api("leo", "POST", A + "/systems/confirm", {"ids": [i["id"] for i in x.th["systems"]]})
    qs = x.api("leo", "GET", A + "/questions").get("questions") or []
    x.th["span_q"] = [{"id": f"span:{q['id']}", "text": q.get("question") or q.get("text") or "", "assumed": _s(q.get("proposal") if q.get("proposal") is not None else q.get("default"))} for q in qs if q.get("id")]
    x.api("leo", "POST", A + "/questions/accept-all")
    return f"{len(x.th['systems'])} systems, {len(qs)} questions assumed"


GENERIC = {"cash", "file", "files", "feed", "data", "the", "and", "for", "csv", "xlsx", "pdf", "log", "report", "statement"}


def _toks(s) -> set:
    """Words of a name, singular, without the ones every source shares (cash, file, feed ...)."""
    return {t[:-1] if t.endswith("s") and len(t) > 4 else t for t in re.split(r"[^a-z]+", str(s).lower()) if len(t) > 2} - GENERIC


def a_samples(x):
    A = f"/api/v1/build/p/{x.th['pid']}/architecture"
    fs = my_files(x, "source")
    if not fs:
        raise Q("I have no files to read yet. Drop this month's files in the drop folder and say so.")
    for f in fs:
        sys_ = max(x.th["systems"], key=lambda s: len(_toks(s["name"]) & _toks(f["name"])), default=None)
        if not sys_ or not _toks(sys_["name"]) & _toks(f["name"]):
            continue
        if f["name"].lower().endswith(".pdf"):
            x.api("leo", "POST", f"{A}/samples/{sys_['id']}/pdf", {"name": f["name"], "data": _b(blob(x.plane, f["name"]))})
            continue  # the lines of a PDF are marked once per layout in Decision 2 (v3_pdf), not asked here
        if not f["name"].lower().endswith((".csv", ".xlsx", ".xls")):
            continue  # an email or a note is not a table sample (the table sample refuses it)
        x.api("leo", "POST", f"{A}/samples/{sys_['id']}/table", {"name": f["name"], "data": _b(blob(x.plane, f["name"]))})
    return f"{len(fs)} files given to Span as samples"


def a_pack(x):
    A = f"/api/v1/build/p/{x.th['pid']}/architecture"
    x.api("leo", "POST", A + "/pack/generate")
    pk = x.api("leo", "GET", A + "/pack")
    x.th["tables"] = [{"layer": t.get("layer", ""), "name": t.get("name", ""), "rows": t.get("rows") or 0, "state": "reused" if t.get("existing") else "new"} for t in pk["pack"].get("tables") or []]
    for m in pk["pack"].get("mapping") or []:
        if m.get("needs_person") and not m.get("resolved"):
            x.api("leo", "PUT", A + "/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": "Mapped at intake from the uploaded file and approved by the head of data."}, "note": "Harbor settles this row."})
    from sh_platform.v1 import v3_figures as F
    F.cover(x, "draft")  # a figure of the brief with no ready table gets one designed before the pack is submitted
    x.api("leo", "POST", A + "/pack/submit", {})
    vs = x.api("leo", "GET", A + "/pack").get("versions") or [{"version": 1}]
    x.api("anita", "POST", A + "/pack/approve", {"version": vs[-1]["version"], "note": "Approved by the head of data."})
    return "design pack approved"


def a_intake(x):
    th, mp = x.th, {}
    th["intake"] = {}
    from sh_platform.v1 import v3_docs as D
    D.intake(x)  # emails and notes: document intake, never table intake (v3_docs)
    V.intake(x)  # PDFs: document intake and reading by layout; the loop below is for spreadsheets
    from sh_platform.v1 import v3_loads as L
    L.intake(x)  # labelled-figures workbooks (a report's summary) are kept as a document's figures, not mapped as rows
    for f in my_files(x, "source"):
        if V.is_pdf(f["name"]) or D.is_doc(f["name"]) or L.skip(x, f["name"]):
            continue
        r = x.api("leo", "POST", "/api/v1/intake/upload", files={"file": (f["name"], blob(x.plane, f["name"]))}, data={"source_code": re.sub(r"\W+", "_", f["source"] or "upload").lower()[:24]})
        th["intake"][f["name"]] = r.get("file_id")
        if r.get("file_id"):  # 2.0 proposes a mapping when a load finds none; nothing loads without an approved one
            x.api("leo", "POST", f"/api/v1/intake/files/{r['file_id']}/load", {}, soft=True)
    for m in x.api("leo", "GET", "/api/v1/model/mappings?state=proposed") or []:
        d = x.api("leo", "GET", f"/api/v1/model/mappings/{m['id']}")
        cols = d.get("columns") or []
        conf = round(sum(1 for c in cols if c.get("target_field")) / len(cols), 2) if cols else 0
        mp[m["id"]] = {"name": d.get("example_file") or m["id"], "tables": sorted({c["target_table"] for c in cols if c.get("target_table")}), "confidence": conf, "unmapped": [c["source"] for c in cols if not c.get("target_field") and c.get("source")]}
    th["maps"] = mp
    return f"{len(th['intake'])} files read, {len(mp)} mappings proposed"


def d2(x) -> dict:
    th = x.th
    words = {"legal_entities": "entities", "cash_movements": "cash movements"}  # ponytail: a few known names, the rest get underscores swapped for spaces
    key_only = {"legal_entities", "portfolios", "instruments", "instrument_identifiers"}
    reused = {t["name"] for t in th.get("tables") or [] if t.get("state") == "reused"}
    files = []
    for m in th["maps"].values():
        ts = ([t for t in m["tables"] if t not in key_only] or m["tables"])[:2]
        names = ", ".join(words.get(t, t.replace("_", " ")) for t in ts)
        files.append({"name": m["name"], "read_as": names or "not recognised", "goes_to": names or "nowhere yet",
                      "state": "reused" if ts and all(t in reused for t in ts) else "new",
                      "confidence": "high" if m["confidence"] >= .8 else "medium" if m["confidence"] >= .5 else "low"})
    qs = [{"id": q["id"], "text": q["text"], "options": [q["assumed"], "Something else, I will say"] if q["assumed"] else ["Yes", "No"], "assumed": q["assumed"]} for q in th.get("span_q") or []]
    for i, m in th["maps"].items():
        if m["confidence"] < .5:
            left = m.get("unmapped") or []
            reason = f" No place yet for: {', '.join(left[:4])}." if left else ""
            qs.append({"id": f"map:{i}", "text": f"I am not sure how to read {m['name']}.{reason} Use my reading?", "options": ["Use my reading", "Leave this file out"], "assumed": "Use my reading"})
    from sh_platform.v1 import v3_loads as L
    from sh_platform.v1 import v3_docs as D
    files += V.d2_files(x) + L.d2_files(x) + D.d2_files(x)
    qs += V.questions(x) + D.questions(x)  # one question per new PDF layout; one per document that states a value
    from sh_platform.v1 import v3_figures as F
    qs += F.account_questions(x)  # "Which entity owns account X?": an account number no portfolio has holds back the whole bank statement
    csvs = [f["name"] for f in my_files(x, "source") if f["name"].lower().endswith(".csv")]
    if csvs and not my_files(x, "benchmark"):
        qs.append({"id": "check:file", "text": "Which file should I check the numbers against before going live? Pick the statement that comes from someone else, not one I load.",
                   "options": [*csvs, "No check this time"], "assumed": None})
    return {"n": 2, "title": "Here is what I understood", "files": files, "questions": qs}


# ---- chain B: mappings .. load .. run on a copy .. compare ------------------------------------------------------------------------

def b_answers(x):
    A = f"/api/v1/build/p/{x.th['pid']}/architecture"
    for qid, val in (x.th.get("answers") or {}).items():
        kind, _, key = qid.partition(":")
        if kind == "check":
            x.th["check_file"] = None if val == "No check this time" else val
        elif kind == "span" and val and not str(val).startswith("Something else"):
            x.api("leo", "POST", f"{A}/questions/{key}", {"value": val}, soft=True)
        elif kind == "doc":
            from sh_platform.v1 import v3_docs as D
            D.answer(x, key, val)
        elif kind == "pdf":
            V.answer(x, key, val)
        elif kind == "acct" and val:
            from sh_platform.v1 import v3_figures as F
            F.tie_account(x, key, val)
        elif kind == "map" and val == "Leave this file out":
            x.api("leo", "POST", f"/api/v1/model/mappings/{key}/reject", {"reason": "Left out by the person."}, soft=True)
            x.th["maps"].pop(key, None)
    return f"{len(x.th.get('answers') or {})} answers applied"


def b_load(x):
    for i in x.th["maps"]:
        x.api("anita", "POST", f"/api/v1/model/mappings/{i}/approve", {"note": "Approved by the head of data."}, soft=True)
    loaded, aside = 0, []
    for name, fid in (x.th.get("intake") or {}).items():
        if V.is_pdf(name) or str(fid).startswith("doc:"):
            continue  # loaded below under its layout; an email or a note below as a document (v3_docs)
        try:  # one file that will not load is set aside and named to the person; the others still load
            from sh_platform.v1 import v3_figures as F
            ok, why = F.load_file(x, name, fid)  # what the load really said: a file that was held back or rejected is not "loaded"
            if not ok:
                raise Q(why)
        except Exception as e:  # noqa: BLE001
            set_status(x.plane, name, "question")
            aside.append({"title": f"{name} did not load", "text": str(getattr(e, "text", e))[:200]})
            continue
        set_status(x.plane, name, "loaded")
        loaded += 1
    n_pdf, a_pdf = V.load(x)
    from sh_platform.v1 import v3_loads as L
    n_fig, a_fig = L.load(x)  # labelled figures (report workbooks and report PDFs) go to the document's extracted fields
    from sh_platform.v1 import v3_docs as D
    n_doc, a_doc = D.load(x)  # a value an email or a note states loads only once the person confirmed its line; the rest is context
    loaded, aside = loaded + n_pdf + n_fig + n_doc, aside + a_pdf + a_fig + a_doc
    titles = {a["title"] for a in aside}  # a retry replaces the lines of the last try, it does not repeat them
    x.th["exceptions"] = [*(e for e in x.th.get("exceptions") or [] if e.get("title") not in titles), *aside]
    if not loaded and aside:  # nothing at all loaded: each file with its reason, in one line each
        raise Q("None of the files would load. " + " ".join(f"{a['title']}: {a['text']}" for a in aside)[:900])
    return f"{loaded} files loaded" + (f", {len(aside)} set aside" if aside else "")


def b_run(x):
    B = f"/api/v1/build/p/{x.th['pid']}/builder"
    v = x.api("leo", "GET", B)
    if (v.get("can") or {}).get("start"):
        v = x.api("leo", "POST", B + "/start", {})
    elif not v.get("round"):
        x.api("leo", "POST", f"/api/v1/build/p/{x.th['pid']}/run?mode=sandbox", {})
    cur = v.get("round") or {}
    waiting = [c for c in cur.get("connections") or [] if c.get("status") == "needs_sample"]
    if cur.get("state") == "blocked" and waiting:  # a source no file came for is left out, by name, and the run tries again
        for c in waiting:
            x.api("leo", "POST", B + "/not-needed", {"source": c["code"], "reason": "No file has arrived for it yet; Harbor left it out. Say if it is needed."}, soft=True)
        x.th["left_out"] = sorted({*(x.th.get("left_out") or []), *(c.get("name") or c["code"] for c in waiting)})
        v = x.api("leo", "POST", B + "/start", {}, soft=True) or x.api("leo", "GET", B)
        cur = v.get("round") or {}
    x.th["run_id"] = (cur.get("run") or {}).get("run_id")
    from sh_platform.v1.b11_builder import run_trouble
    if why := run_trouble(cur):  # the failing step in plain words, here, not a generic refusal at go-live
        raise Q(why)
    if cur.get("state") == "blocked" or not cur:
        raise Q("The run on a copy is stuck: " + "; ".join(str(n.get("text") or n) for n in v.get("needs") or [])[:300])
    return "ran on a copy"


def b_compare(x):
    B = f"/api/v1/build/p/{x.th['pid']}/builder"
    fs = my_files(x, "benchmark")
    if fs:
        x.api("leo", "POST", B + "/benchmark", {"name": fs[0]["name"], "b64": _b(blob(x.plane, fs[0]["name"]))})
        return "compared with " + fs[0]["name"]
    import csv
    import io

    def cash_lines(data: bytes) -> list[str]:
        """Latest closing cash per entity, as 'Available cash <entity> <amount>' lines copied from the file."""
        rows = csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
        cols = rows.fieldnames or []

        def col(pat, skip=r"^$"):
            return next((c for c in cols if re.search(pat, c, re.I) and not re.search(skip, c, re.I)), None)
        dcol, ecol = col(r"date|as.?of"), col(r"entity")
        acol = col(r"closing|balance|cash|amount", skip=r"date|entity|currency|code")
        if not (dcol and ecol and acol):
            return []
        latest: dict = {}
        for r in rows:
            e, d = (r.get(ecol) or "").strip(), (r.get(dcol) or "").strip()
            v = (r.get(acol) or "").strip().replace("$", "").strip()
            if not e or not d or not re.fullmatch(r"[+-]?\d[\d,]*(\.\d+)?", v):
                continue
            n = float(v.replace(",", ""))
            if e not in latest or d > latest[e][0]:
                latest[e] = (d, n)
            elif d == latest[e][0]:
                latest[e] = (d, latest[e][1] + n)  # several rows of one entity on one day (portfolios) add up
        return [f"Available cash {e} {t:,.2f}" for e, (_, t) in latest.items()]

    # no benchmark dropped: the brief's check source is the file of this thread that shares a word with the thread's wording,
    # else any statement from another party
    words = _toks(" ".join([str(x.th.get("title") or ""), *map(str, x.th.get("rules") or []), *(str(e.get("text") or "") for e in x.th["events"])]))
    cands = [f for f in my_files(x, "source") if f["name"].lower().endswith(".csv")]
    ordered = [f for n, f in sorted(((len(_toks(f["source"]) & words), f) for f in cands), key=lambda p: -p[0]) if n]
    ordered += [f for f in cands if re.search(r"\bstatements?\b", str(f["source"]).lower())]
    if x.th.get("check_file"):
        ordered = [f for f in cands if f["name"] == x.th["check_file"]] + ordered
    elif "check_file" in x.th:
        return "no check, by the person's choice"
    for f in ordered:
        lines = cash_lines(blob(x.plane, f["name"]))
        if lines:
            name = f["name"].rsplit(".", 1)[0] + ".txt"  # plain text, so the reader takes the lines as they are
            x.api("leo", "POST", B + "/benchmark", {"name": name, "text": "\n".join(lines)})
            return f"compared with {f['name']}, {len(lines)} figures"
    return "no report to compare with"


def d3(x) -> dict:
    cur = x.api("leo", "GET", f"/api/v1/build/p/{x.th['pid']}/builder").get("round") or {}
    var = cur.get("variance")
    if not var:
        return {"n": 3, "title": "Numbers match. Go live?", "checks": [], "summary": NO_BENCH + _left(x)}
    checks = [{"label": r["figure"], "value": str(r["run"]), "ok": r["status"] != "unexplained",
               "note": (r["evidence"][0].get("text") if r.get("evidence") else f"Report says {r['report']}, difference {r['diff']}")} for r in var["lines"] + var["legs"]]
    checks += [{"label": r["label"], "value": "", "ok": False, "note": "The run has no figure for this line."} for r in var.get("unmatched") or []]
    return {"n": 3, "title": "Numbers match. Go live?" if var["summary"]["unexplained"] == 0 else "Some numbers do not match. Go live?", "checks": checks, "summary": var["headline"] + _left(x)}


# ---- chain C: live, Lumen starter, morning note ------------------------------------------------------------------------------------

def c_live(x):
    pid, B = x.th["pid"], f"/api/v1/build/p/{x.th['pid']}/builder"
    x.api("leo", "POST", B + "/go-live", {"accept_variance": True, "no_benchmark": True})
    pk = (x.api("leo", "GET", B).get("pack") or {}).get("schedule") or {}
    x.th["next_run"] = f"{pk.get('freq', 'daily')} at {pk.get('at', '06:00')}"
    return "live on " + x.th["next_run"]


def c_lumen(x):
    S = f"/api/v1/build/p/{x.th['pid']}/studio"
    d = x.api("leo", "POST", S + "/starter", {})
    did = d.get("id") or (d.get("dashboard") or {}).get("id")
    DASH = f"{S}/{did}"
    NUM, DATE = ("tinyint", "smallint", "integer", "bigint", "hugeint", "decimal", "double", "float", "real", "numeric"), ("date", "timestamp")
    STOP = {"the", "and", "per", "by", "due", "in", "of", "for", "days", "day", "month", "period"}

    def words(s) -> set[str]:
        return {w for w in re.split(r"[^a-z]+", str(s or "").lower()) if len(w) > 2 and w not in STOP}

    v = x.api("leo", "GET", DASH)
    starter = {t["id"] for t in v.get("tiles") or [] if t.get("starter")}
    # a starter tile with no figure in it (all null or NaN) comes off the grid; accept leaves it out
    kept = [i for i in v["layout"]["items"] if i.get("tile") not in starter
            or any(c is not None and c == c for r in x.api("leo", "GET", f"{DASH}/tiles/{i['tile']}/data", soft=True).get("rows") or [] for c in r.values())]
    # the thread's own KPIs: each takes the numeric column whose words its name shares, one tile per column, in a new row
    kpis = (x.api("anita", "GET", f"/api/v1/intents/{x.th['iid']}/chat", soft=True).get("sow") or {}).get("kpis") or []
    tables, picks, seen = v["library"]["tables"], [], set()
    for k in kpis:
        want = words(k.get("name"))
        hits = [(len(want & words(c["name"])), t, c) for t in tables for c in t["columns"] if c["type"].lower().startswith(NUM) and not c["name"].endswith("_id")]
        score, t, c = max(hits, key=lambda h: h[0], default=(0, None, None))
        if not score or (t["name"], c["name"]) in seen:
            continue
        seen.add((t["name"], c["name"]))
        when = next((n["name"] for n in t["columns"] if n["type"].lower().startswith(DATE)), None)
        split = next((n["name"] for n in t["columns"] if "entity" in n["name"] and not n["type"].lower().startswith(NUM)), None) if "entity" in want else None
        picks.append({"kind": "bar" if split else "figure", "table": t["name"], "measure": c["name"], "when": when, "split": split})
    picks = picks[:4]
    if len(kept) < len(v["layout"]["items"]) or picks:
        items = [{"id": i["id"], "row": i["row"], "col": i["col"], "size": i["size"]} for i in kept]
        x.api("leo", "PUT", f"{DASH}/layout", {"rev": v["rev"], "rows": v["layout"]["rows"] + len(picks), "items": items})
    for n, p in enumerate(picks):  # one new row each, from the left
        x.api("leo", "POST", f"{DASH}/widgets", p | {"row": v["layout"]["rows"] + n, "col": 0, "size": "wide" if p["kind"] == "bar" else "small"}, soft=True)
    x.api("leo", "POST", f"{DASH}/starter/accept", {})
    for a, who in (("submit", "leo"), ("approve", "anita")):
        x.api(who, "POST", f"{DASH}/{a}", {}, soft=True)
    return "Lumen starter board accepted and published"


def c_note(x):
    cur = x.api("leo", "GET", f"/api/v1/build/p/{x.th['pid']}/builder").get("round") or {}
    figs = [{"label": r["figure"], "value": str(r["run"]), "change": str(r["diff"])} for r in ((cur.get("variance") or {}).get("lines")) or []]
    if not figs:  # no variance lines: the run's ready tables, as the Office view reads them
        as_of = (cur.get("run") or {}).get("as_of") or date.today().isoformat()
        liq = x.api("leo", "GET", f"/api/v1/office/liquidity?currency=USD&as_of={as_of}", soft=True) or {}
        for e in liq.get("entities") or []:
            code, buckets = e.get("entity_code") or "", {b.get("key"): b for b in e.get("buckets") or []}
            if e.get("available_cash") is not None:
                figs.append({"label": f"Available cash {code}", "value": str(e["available_cash"]), "change": ""})
            if (buckets.get("30") or {}).get("calls") is not None:
                figs.append({"label": f"Calls due in 30 days {code}", "value": str(buckets["30"]["calls"]), "change": ""})
    from sh_platform.v1 import v3_figures as F
    figs += F.note_figures(x)  # the brief's own figures, read from their ready tables
    title = " ".join(str(x.th["title"]).split())
    short = " ".join(title[:60].rsplit(" ", 1)[0].split()) if len(title) > 60 else title
    short = re.sub(r"\s+(from|to|of|the|and|with|whether|that|a|an|in|on|for)$", "", short).rstrip(" ,:;") or "The check"
    n = len(figs)
    x.th["note"] = {"text": f"{short} is live. {n} figure{'s' if n != 1 else ''} in the first note.", "figures": figs}
    return "morning note written"


# ---- chains and the runner --------------------------------------------------------------------------------------------------------

CHAINS = {
    "A": ([("North", "Signed the intent", a_sign), ("North", "Handed over to build", a_handover), ("Span", "Read the systems", a_arch),
           ("Span", "Read the sample files", a_samples), ("Span", "Drafted and approved the design pack", a_pack), ("Flow", "Read the dropped files", a_intake)], "decision2"),
    "B": ([("Span", "Applied your answers", b_answers), ("Flow", "Accepted the mappings and loaded", b_load), ("Flow", "Ran on a copy", b_run),
           ("Flow", "Compared with the report", b_compare)], "decision3"),
    "C": ([("Flow", "Went live", c_live), ("Lumen", "Built the starter board", c_lumen), ("Lumen", "Wrote the morning note", c_note)], "live"),
}
DECISIONS = {"decision2": d2, "decision3": d3}
INTRO = {"A": "Working on it. I will come back when I have understood your files.", "B": "Thank you. Loading and checking the numbers now.", "C": "Going live."}


def start_chain(app, plane, tid, name, account_id, at=0) -> None:
    def go():
        run_chain(app, plane, tid, name, account_id, at)
    if SYNC:
        go()
    else:
        threading.Thread(target=go, daemon=True).start()


def run_chain(app, plane, tid, name, account_id, at=0) -> None:
    th = load(plane, tid)
    x, (steps, final) = Ctx(app, plane, th, account_id), CHAINS[name]
    th["stage"], th["resume"] = "working", None
    chips = []
    for i in range(at, len(steps)):
        agent, action, fn = steps[i]
        if _gone(plane, tid):  # the person discarded it while Harbor was working: stop, never write over the record
            return None
        th["at"] = {"chain": name, "i": i}  # where to carry on if the server stops mid-step
        try:
            detail = _call(x, fn, action) or ""
            step(x, agent, action, True, detail)
            chips.append(action)
        except Exception as e:  # noqa: BLE001 - every failure is a question, never a crashed thread
            q = e if isinstance(e, Q) else Q(f"I hit a snag at \"{action}\": {str(e)[:300]}")
            step(x, agent, action, False, q.text)
            th["asked"] = th.get("asked", 0) + 1
            if chips:
                ev(th, "chips", chips=chips)
            ev(th, "question", q.text, by=agent)
            th["events"][-1]["about"] = action  # the kind of step a person is asked about: two of a kind become a skill
            th["stage"], th["resume"] = "question", {"chain": name, "i": i, "q": q.options}
            return save(plane, th)
        save(plane, th)
    ev(th, "chips", chips=chips)
    try:
        th["decision"] = (_P.DECISIONS if name[0] == "P" else DECISIONS)[final](x) if final in DECISIONS else None
    except Exception as e:  # noqa: BLE001
        step(x, "Harbor", "Prepared the next decision", False, str(e)[:300])
        ev(th, "question", f"I could not prepare the next decision: {str(e)[:200]}. Say retry to try again.")
        th["stage"], th["resume"] = "question", {"chain": name, "i": len(steps), "q": []}
        return save(plane, th)
    if final == "live":
        th["decision"] = None
        ev(th, "harbor", "It is live. " + (th.get("note") or {}).get("text", ""))
    else:
        th["asked"] = th.get("asked", 0) + len((th["decision"] or {}).get("questions") or [])
        ev(th, "harbor", _P.SAY.get(name) or {"decision2": "Here is what I understood. Check the files and answer anything I was unsure of.", "decision3": "I have checked the numbers. Take a look."}[final])
    th["stage"] = final
    save(plane, th)


# ---- the public calls the routes use ----------------------------------------------------------------------------------------------

def _turns(view_) -> str:
    return next((t.get("text") for t in reversed(view_.get("turns") or []) if t.get("by") != "person" and t.get("text")), "") or ""


def _v(x) -> str:
    return ", ".join(map(str, x)) if isinstance(x, list) else str(x or "")


def doc(sow: dict) -> list[dict]:
    """The whole brief as a document: groups of lines, each line naming the 2.0 field it edits (section, index, field)."""
    g = sow.get("goal") or {}
    line = lambda sec, i, f, label, v, sug=False: {"section": sec, "index": i, "field": f, "label": label, "value": _v(v), "suggested": sug}  # noqa: E731
    out = [{"title": "What you want", "lines": [
        line("goal", None, "line", "The question", g.get("line")), line("goal", None, "why", "Why it matters", g.get("why")),
        line("goal", None, "readers", "Read by", g.get("readers")), line("goal", None, "decisions", "What they decide", g.get("decisions")),
        line("goal", None, "needed_by", "When it is needed", g.get("needed_by"))]}]
    for i, k in enumerate(sow.get("kpis") or []):
        if isinstance(k, dict):
            sug = bool(k.get("pack_suggested"))
            out.append({"title": f"Figure: {k.get('name') or 'unnamed'}", "lines": [
                line("kpis", i, "name", "Name", k.get("name"), sug), line("kpis", i, "definition", "What it means", k.get("definition"), sug),
                line("kpis", i, "formula", "How it is worked out", k.get("formula"), sug), line("kpis", i, "period", "How often", k.get("period"), sug),
                line("kpis", i, "owner", "Owner", k.get("owner"), sug)]})
    srcs = [line("sources", i, "holds", s.get("name") or "Source", s.get("holds") or s.get("owner"))
            for i, s in enumerate(sow.get("sources") or []) if isinstance(s, dict)]
    if srcs:
        out.append({"title": "Where the data comes from", "lines": srcs})
    steps = [line("process", i, "does", f"{i + 1}. {st.get('name') or 'Step'}" + (f" ({st['who']})" if st.get("who") else ""), st.get("does") or st.get("name"))
             for i, st in enumerate((sow.get("process") or {}).get("steps") or []) if isinstance(st, dict)]
    if steps:
        out.append({"title": "How it is done today (process map)", "lines": steps})
    rules = [line("governance", i, "rule", "Rule", r.get("rule")) for i, r in enumerate(sow.get("governance") or []) if isinstance(r, dict)]
    if rules:
        out.append({"title": "Rules", "lines": rules})
    return out


def brief(sow: dict) -> dict:
    g = sow.get("goal") or {}
    return {"question": g.get("line") or "", "files": [s.get("name", "") for s in sow.get("sources") or []],
            "read_by": ", ".join(g.get("readers") or []), "refresh": g.get("needed_by") or "", "cases_when": "; ".join(g.get("decisions") or []),
            "doc": doc(sow), "title": sow.get("title") or ""}


def edit_brief(app, plane, tid, body: dict, account_id) -> dict:
    """One line of the brief changed by the person, straight into the 2.0 intent of work (no model call), then the card is refreshed."""
    th = load(plane, tid)
    if th["stage"] != "decision1" or not th.get("iid"):
        raise ValueError("The brief can be changed while Decision 1 is open.")
    x = Ctx(app, plane, th, account_id)
    sow = x.api("me", "GET", f"/api/v1/intents/{th['iid']}/sow")
    x.api("me", "PUT", f"/api/v1/intents/{th['iid']}/sow", {**{k: body.get(k) for k in ("section", "index", "field", "value")}, "version": sow.get("version")})
    sow = x.api("me", "GET", f"/api/v1/intents/{th['iid']}/chat").get("sow") or sow
    th["sources"] = [s.get("name", "") for s in sow.get("sources") or []]
    th["decision"] = {**(th.get("decision") or {}), "brief": brief(sow), "gaps": _gaps(x, th["iid"])}
    ev(th, "person", f"Changed {str(body.get('field') or '').replace('_', ' ')}: {str(body.get('value') or '')[:160]}", by="You")
    save(plane, th)
    return th


def _north(x, text, first=False):
    th = x.th
    with _skill(x, "intent.restate-ask", "Reading what you asked"):
        out = x.api("me", "POST", "/api/v1/intents/chat" if first else f"/api/v1/intents/{th['iid']}/chat", {"text": text})
    th["iid"] = out.get("id") or th.get("iid")
    sow = out.get("sow") or x.api("me", "GET", f"/api/v1/intents/{th['iid']}/chat").get("sow") or {}
    with _skill(x, "intent.find-gaps", "Checking what is still open"):
        gaps = _gaps(x, th["iid"])
    fill = first or "usual practice" in text.lower()  # later replies are one model call; filling the gaps again is only on asking
    if fill and gaps:  # show the first draft now; the suggested lines arrive as an update
        th["decision"] = {"n": 1, "title": "Is this what you want?", "brief": brief(sow), "gaps": gaps}
        ev(th, "harbor", (_turns(out) or "Here is my first draft.") + " I am filling the open parts with the usual practice now, marked as suggestions.", by="North")
        save(x.plane, th)
    with _skill(x, "intent.fill-with-practice", "Filling the open parts with the usual practice") if fill and gaps else nullcontext():
        for _ in range(2 if fill else 0):  # Harbor fills what the person left open with the industry's usual practice, marked as suggested
            if not gaps:
                break
            out = x.api("me", "POST", f"/api/v1/intents/{th['iid']}/chat", {"text": FILL + "; ".join(gaps)})
            sow = out.get("sow") or x.api("me", "GET", f"/api/v1/intents/{th['iid']}/chat").get("sow") or sow
            gaps = _gaps(x, th["iid"])
    if fill and gaps and all("last period" in g for g in gaps):  # a first report has no earlier figures: say so plainly, once North has asked
        x.api("me", "POST", f"/api/v1/intents/{th['iid']}/chat", {"text": NO_EARLIER})
        gaps = _gaps(x, th["iid"])
    sow = x.api("me", "GET", f"/api/v1/intents/{th['iid']}/chat").get("sow") or sow  # after the drafted lines were accepted
    th["sources"] = [s.get("name", "") for s in sow.get("sources") or []]
    th["rules"] = [str(g.get("rule") or g.get("text") or g.get("name") or g) if isinstance(g, dict) else str(g) for g in sow.get("governance") or []]
    th["title"] = str(sow.get("title") or th["title"])[:80]  # the drafted title, not the first sentence typed
    before = {(l["section"], l["index"], l["field"]): l["value"] for g in (((th.get("decision") or {}).get("brief") or {}).get("doc") or []) for l in g["lines"]}
    b = brief(sow)
    if before:  # mark what this reply changed, so the person sees it at a glance
        for g in b["doc"]:
            for l in g["lines"]:
                l["changed"] = before.get((l["section"], l["index"], l["field"]), "") != l["value"]
    th["decision"] = {"n": 1, "title": "Is this what you want?", "brief": b, "gaps": gaps}
    th["stage"] = "decision1"
    ev(th, "harbor", _turns(out) or "Here is what I understood you want. Is this right?", by="North")
    if gaps:
        ev(th, "harbor", "Before you confirm, I still need: " + "; ".join(gaps) + ". Tell me in your own words, or say \"use the usual practice\".")


FILL = ("Where I have not said it, propose the usual practice for an office like ours and mark each as a suggestion "
        "I can change. We don't have a benchmark for figures we have not reported before; they are checked against the source "
        "statements instead. Fill these now: ")


NO_EARLIER = "We don't have a benchmark for any of these figures; none were reported before."


def _no_earlier_figures(app, plane, iid: str) -> None:
    """Confirming the brief accepts what it shows: suggested figures become the person's own, and a first report has no earlier
    figures, so each figure without a benchmark is recorded as "none". Signing then never dead-ends on either. Benchmarks given are kept."""
    from sh_platform.jsonfile import lock_for, write_json_atomic
    from sh_platform.v1 import i4_sow as S
    path = S.path_of(plane, iid)
    try:
        with lock_for(path):
            sow = S.read(plane, iid)
            if sow.get("state") == "signed":
                return
            changed = False
            for k in sow.get("kpis") or []:
                if not isinstance(k, dict):
                    continue
                if "benchmark" not in k:
                    k["benchmark"], changed = None, True
                if k.get("pack_suggested") and k.get("status") == "unclear":  # the person confirmed the brief with this figure on it
                    k["status"], k["confirmed_in"], changed = "defined", "Decision 1", True
            if changed:
                write_json_atomic(path, sow)
    except Exception:  # noqa: BLE001 - never blocks the confirm; signing still says what is missing
        log.warning("could not record no earlier figures for %s", iid, exc_info=True)


def _gaps(x, iid: str) -> list[str]:
    from sh_platform.v1 import v3_signoff as SO
    SO.accept_drafts(x, iid)  # drafted lines count as filled; the person still reviews them in Decision 1
    from sh_platform.v1 import i6_chat as I6
    return [g.strip() for g in I6._sign_gaps(x.plane, iid).split(";") if g.strip()]


def create(app, plane, text, account_id) -> dict:
    th = {"id": "t-" + uuid.uuid4().hex[:10], "title": text.strip()[:80] or "New thread", "created": now(), "stage": "drafting", "events": [], "steps": [], "asked": 0}
    acct = app.state.account_store.get(account_id) or {}
    th["started_by"] = acct.get("display_name") if isinstance(acct, dict) else getattr(acct, "display_name", None)
    ev(th, "person", text, by="You")
    ev(th, "harbor", "Reading your question. I am drafting the brief now; it appears here in a few minutes. You can leave this page.")
    save(plane, th)
    _later(app, plane, th, account_id, text, first=True)  # the click returns at once; the brief arrives on the thread
    scan(app, plane)
    return th


def _later(app, plane, th, account_id, text, first=False) -> None:
    """Draft or redraft the brief off the request, so no click waits on the model. Failures become a question on the thread."""
    def go():
        x = Ctx(app, plane, th, account_id)
        try:
            _north(x, text, first)
        except Exception as e:  # noqa: BLE001
            q = e if isinstance(e, Q) else Q(str(e)[:300])
            ev(th, "question", f"I could not draft the brief yet: {q.text} Say it another way and I will try again.")
            th["stage"] = "question"
        if not _gone(plane, th["id"]):
            save(plane, th)
            scan(app, plane)  # the brief now names its sources: files already dropped can be matched
    if SYNC:
        go()
    else:  # ponytail: an in-process thread; a queue and worker (2.0 production mode) when more than one server runs
        threading.Thread(target=go, daemon=True).start()


def say(app, plane, tid, text, account_id) -> dict:
    th = load(plane, tid)
    asked = next((e for e in reversed(th["events"]) if e["kind"] == "question"), None) if th.get("stage") == "question" else None
    ev(th, "person", text, by="You")
    if asked and asked.get("about") and text.strip().lower() != "retry":  # a real answer to a question about a kind of step
        _learn(plane, th, asked["about"], f"{asked.get('text', '')[:140]} -> {text.strip()[:140]}")
    x = Ctx(app, plane, th, account_id)
    r = th.get("resume")
    if r and r.get("chain"):
        if r["chain"] == "A" and r.get("i", 0) == 0 and th.get("iid") and text.strip().lower() != "retry":
            try:  # the brief could not be signed: the reply goes to the brief first, then the chain retries
                _north(x, text)
            except Exception as e:  # noqa: BLE001
                log.warning("brief reply failed: %s", e)
            if (th.get("decision") or {}).get("gaps"):  # still not signable: the brief stays open with what is missing
                th["resume"] = None
                save(plane, th)
                return th
            th["decision"], th["stage"] = None, "working"  # already confirmed once: carry on from the sign step
        save(plane, th)
        start_chain(app, plane, tid, r["chain"], account_id, r["i"])  # any reply to a question retries from the step that stopped
        return load(plane, tid)
    try:
        if th.get("pid") or not th.get("iid") and th["stage"] not in ("drafting", "decision1", "question"):
            ev(th, "harbor", "Noted. I will use that in the next run.")
        else:
            if text.strip().lower() == "retry":  # carry on drafting with the person's last real message, never the word "retry"
                said = [e.get("text") for e in th["events"] if e.get("kind") == "person" and (e.get("text") or "").strip().lower() != "retry"]
                text = said[-1] if said else text
            th["stage"] = "drafting"
            said = text.strip() if len(text.strip()) <= 120 else text.strip()[:text.strip().rfind(" ", 0, 120)] + "…"  # a whole word, never cut mid-word
            ev(th, "harbor", f"Got it: \"{said}\". I am updating the brief now; the lines that change will be marked. About half a minute.")
            save(plane, th)
            _later(app, plane, th, account_id, text, first=not th.get("iid"))
            return th
    except Exception as e:  # noqa: BLE001
        ev(th, "question", str(e)[:300])
        th["stage"] = "question"
    save(plane, th)
    return th


def decide(app, plane, tid, n, answer, answers, account_id) -> dict:
    th = load(plane, tid)
    cur = (th.get("decision") or {}).get("n")
    if answer == "retry" and th.get("resume"):
        return say(app, plane, tid, "retry", account_id)
    if th["stage"] != f"decision{n}" or cur != n:
        raise ValueError(f"Decision {n} is not waiting for you.")
    from sh_platform.v1 import v3_signoff as SO
    if answer == "send_for_signature":
        SO.send(app, plane, th, (answers or {}).get("to"), account_id)
        return save(plane, th) or th
    SO.guard(app, plane, th, n, answer, account_id)
    if answer == "not_yet":
        ev(th, "decision_done", f"Not yet. Decision {n} stays open.")
        th["stage"] = "drafting" if n == 1 else th["stage"]
        ev(th, "harbor", "Tell me what to change.")
        return save(plane, th) or th
    ev(th, "decision_done", {1: "Confirmed. This is what you want.", 2: "This is right, carry on.", 3: "Go live."}[n])
    th["answers"] = {**(th.get("answers") or {}), **{k: v for k, v in (answers or {}).items() if k}}
    srcs = {f["name"]: f.get("source") for f in read_files(plane)}
    for k, v in (answers or {}).items():  # an answer about how a file is read: the second one for the same source becomes a skill
        m = (th.get("maps") or {}).get(k.partition("map:")[2]) if k.startswith("map:") else None
        if m and srcs.get(m["name"]):
            _learn(plane, th, f"file:{srcs[m['name']]}", f"{m['name']}: {v}")
    if n == 1 and answer == "confirm" and th.get("iid"):
        _no_earlier_figures(app, plane, th["iid"])
    if n == 1 and (th.get("decision") or {}).get("brief"):
        th["brief"] = th["decision"]["brief"]  # the confirmed brief stays on screen (the Build graph) after Decision 1 closes
    th["decision"], th["stage"] = None, "working"
    ev(th, "harbor", INTRO["ABC"[n - 1]])
    save(plane, th)
    start_chain(app, plane, tid, _P.chain_name(plane, th, n), account_id)  # A/B/C, or PA/PB/PC for a process-only thread
    return load(plane, tid)


def workbench(th) -> dict:
    return {"steps": th["steps"], "tables": th.get("tables") or [], "rules": th.get("rules") or []}


# ---- files: drop folder + POST /files ----------------------------------------------------------------------------------------------

def _fp(plane):
    return plane.path("v3", "files.json")


def read_files(plane) -> list[dict]:
    p = _fp(plane)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []


def set_status(plane, name, status) -> None:
    with LOCK:
        fs = read_files(plane)
        for f in fs:
            if f["name"] == name:
                f["status"] = status
        _fp(plane).write_text(json.dumps(fs), encoding="utf-8")


def drop(plane, name: str, data: bytes) -> None:
    d = plane.path("dropbox")
    d.mkdir(parents=True, exist_ok=True)
    (d / re.sub(r"[\\/]", "_", name)).write_bytes(data)


def recognise(plane, name: str, threads: list[dict]):
    """(status, source, thread id): a file is recognised when its name shares a word with a source of exactly one open thread."""
    scored = sorted(((len(_toks(s) & _toks(name)), t["id"], s) for t in threads if t["stage"] not in ("drafting",)
                     for s in t.get("sources") or []), reverse=True)
    best = scored[0][0] if scored else 0
    hits = [(tid, s) for n, tid, s in scored if n and n == best]  # the source sharing the most words wins
    if "benchmark" in _toks(name):
        live = [t for t in threads if t.get("pid")]
        return ("recognised", "benchmark", live[0]["id"]) if len(live) == 1 or live else ("waiting", "", None)
    if not hits:
        open_ = [t for t in threads if t["stage"] in ("decision1", "working", "decision2", "question")]
        if len(open_) == 1 and name.lower().rsplit(".", 1)[-1] in ("csv", "xlsx", "xls", "pdf", "txt"):  # one thread is being built: an unnamed file goes to it, and Decision 2 shows it to the person
            return "recognised", re.sub(r"[_\-]?\d[\d\-]*", "", name.rsplit(".", 1)[0]).replace("_", " ").strip() or name, open_[0]["id"]
        return "waiting", "", None
    if len({h[0] for h in hits}) == 1 and len({h[1] for h in hits}) > 1:  # one thread, two sources equally likely: the file's own words decide, when they clearly do
        from sh_platform.v1 import v3_figures as F
        pick = F.pick_source(plane, name, [h[1] for h in hits], next(t for t in threads if t["id"] == hits[0][0]))
        if pick:
            return "recognised", pick, hits[0][0]
    if len({h[0] for h in hits}) > 1 or len({h[1] for h in hits}) > 1:  # two threads, or two sources equally likely: ask, never guess
        return "question", hits[0][1], None
    return "recognised", hits[0][1], hits[0][0]


def scan(app, plane) -> list[dict]:
    """Register what sits in the drop folder and re-judge what is waiting. Called on every read and every 30 s."""
    with LOCK:
        d = plane.path("dropbox")
        d.mkdir(parents=True, exist_ok=True)
        fs, ths = read_files(plane), all_threads(plane)
        by = {f["name"]: f for f in fs}
        for p in sorted(d.iterdir()):
            if p.is_file() and p.name not in by:
                by[p.name] = {"name": p.name, "arrived_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "waiting", "source": "", "thread": None}
        new = []
        for f in by.values():
            if f["status"] in ("waiting", "question"):
                f["status"], f["source"], f["thread"] = recognise(plane, f["name"], ths)
                if f["status"] == "recognised":
                    new.append(f)
        fs = sorted(by.values(), key=lambda f: f["arrived_at"], reverse=True)
        _fp(plane).write_text(json.dumps(fs), encoding="utf-8")
    for f in new:  # monthly: a file for a live thread runs it and only exceptions come back
        t = next((t for t in ths if t["id"] == f["thread"] and t["stage"] == "live"), None)
        if t and f["source"] != "benchmark" and t.get("mode") != "process":  # a process-only thread has no monthly load
            start_chain(app, plane, t["id"], "M", None)
    return fs


def m_load(x):
    B, pid = None, x.th["pid"]
    x.th["file_problems"], done, pdfs, docs = [], 0, [], []
    for f in my_files(x, "source"):
        if f["status"] != "recognised":
            continue
        if V.is_pdf(f["name"]) or f["name"].lower().endswith((".eml", ".md", ".txt", ".docx")):
            (pdfs if V.is_pdf(f["name"]) else docs).append(f["name"])
            continue
        try:  # one file that will not load is named to the person; the others still load and the run still happens
            r = x.api("leo", "POST", "/api/v1/intake/upload", files={"file": (f["name"], blob(x.plane, f["name"]))}, data={"source_code": re.sub(r"\W+", "_", f["source"]).lower()[:24]})
            x.api("leo", "POST", f"/api/v1/intake/files/{r['file_id']}/load", {})
            set_status(x.plane, f["name"], "loaded")
            done += 1
        except Exception as e:  # noqa: BLE001
            set_status(x.plane, f["name"], "question")
            x.th["file_problems"].append({"title": f"{f['name']} did not load", "text": str(getattr(e, "text", e))[:200]})
    n_pdf, a_pdf = V.load_files(x, pdfs, monthly=True)  # a PDF of a remembered layout loads without a question
    from sh_platform.v1 import v3_docs as D
    a_pdf += D.monthly(x, docs)  # an email or a note is a document: context, or a stated value waiting in Evidence
    done, x.th["file_problems"] = done + n_pdf, x.th["file_problems"] + a_pdf
    x.api("anita", "POST", f"/api/v1/build/p/{pid}/run?mode=live", {})
    return f"{done} files loaded, {len(x.th['file_problems'])} set aside, monthly run done"


def m_exceptions(x):
    runs = x.api("leo", "GET", f"/api/v1/build/p/{x.th['pid']}/runs", soft=True)
    last = ((runs.get("runs") if isinstance(runs, dict) else runs) or [{}])[0] or {}
    x.th["exceptions"] = [{"title": str(q.get("rule") or "Check"), "text": f"{q.get('count', 'Some')} rows set aside"} for q in last.get("quarantined") or []]
    x.th["exceptions"] += x.th.get("file_problems") or []
    return f"{len(x.th['exceptions'])} exceptions"


CHAINS["M"] = ([("Flow", "Loaded the new files", m_load), ("Flow", "Looked for exceptions", m_exceptions)], "live")

from sh_platform.v1 import v3_process as _P  # noqa: E402 - process-only builds (UC9): chains PA/PB/PC, the cards and the SOP
_P.register(sys.modules[__name__])
from sh_platform.v1 import v3_figures as _F  # noqa: E402 - every figure of the brief ends in a filled ready table (chain B steps, Decision 3 lines)
_F.install(sys.modules[__name__])


def _recover(app) -> None:
    """After a restart, no work is running: a thread left drafting or working becomes a question the person can carry on from."""
    from sh_platform.plane import PlaneStore
    store = PlaneStore(app.state.settings.data_root)
    for cid in store.list_company_ids():
        plane = store.plane_for(cid)
        for th in all_threads(plane):
            if th.get("stage") not in ("drafting", "working"):
                continue
            th = load(plane, th["id"])
            th["resume"] = th.get("at") if th["stage"] == "working" else None
            ev(th, "question", "I was interrupted while working (the app restarted). Say retry and I will carry on from where I stopped.")
            th["stage"] = "question"
            save(plane, th)


def start_scanner(app) -> None:
    if os.environ.get("SH_V3_SCAN") == "off" or getattr(app.state, "v3_scanner", False):
        return
    app.state.v3_scanner = True
    _recover(app)

    def loop():
        from sh_platform.plane import PlaneStore
        while True:
            time.sleep(30)
            try:
                store = PlaneStore(app.state.settings.data_root)
                for cid in store.list_company_ids():
                    if store.plane_for(cid).path("dropbox").is_dir():
                        scan(app, store.plane_for(cid))
            except Exception:  # noqa: BLE001 - the scanner never dies
                pass
    threading.Thread(target=loop, daemon=True).start()


# ---- the desk ---------------------------------------------------------------------------------------------------------------------

def desk(plane) -> dict:
    ths, fs = all_threads(plane), read_files(plane)
    needs = []
    for t in ths:
        d = t.get("decision")
        if t["stage"] in ("decision1", "decision2", "decision3") and d:
            acts = {1: [("Confirm", "confirm"), ("Not yet", "not_yet")], 2: [("This is right, carry on", "carry_on"), ("Not yet", "not_yet")], 3: [("Go live", "go_live"), ("Not yet", "not_yet")]}[d["n"]]
            needs.append({"kind": "decision", "thread": t["id"], "title": d["title"], "text": t["title"], "actions": [{"label": a, "answer": b} for a, b in acts]})
        elif t["stage"] == "question":
            q = next((e for e in reversed(t["events"]) if e["kind"] == "question"), {})
            needs.append({"kind": "question", "thread": t["id"], "title": t["title"], "text": q.get("text", ""), "actions": [{"label": "Try again", "answer": "retry"}]})
        needs += [{"kind": "exception", "thread": t["id"], "title": e["title"], "text": e["text"], "actions": [{"label": "Open the thread", "answer": "open"}]} for e in t.get("exceptions") or []]
    note = next((t["note"] for t in ths if t.get("note")), None)
    return {"needs": needs, "note": note, "threads": [summary(t) for t in ths],
            "files": {"arrived": len(fs), "recognised": sum(f["status"] in ("recognised", "loaded") for f in fs), "waiting": sum(f["status"] in ("waiting", "question") for f in fs)}}
