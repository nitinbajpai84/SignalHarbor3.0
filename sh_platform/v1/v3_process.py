"""Harbor 3.0 process-only builds (UC9): a use case that asks for a process, procedure or SOP, whose inputs are documents, not data tables.

No data load. Chains PA/PB/PC replace A/B/C for such a thread (th["mode"] == "process"): sign the brief, read the documents (i5_docs on text read by
context_docs.reader), draw the process map (lanes, steps, hand-overs, decision path), Decision 2 "Is this the process?", write the SOP (k8_sop),
Decision 3 the SOP preview, then live as a document deliverable with no schedule. Nothing is invented: a field the documents do not state is
written "Not stated yet" (k8_sop) and listed as an open point. The signed brief is never edited; the filled map lives on the thread (th["process"]).
Hooks in v3_harbor: CHAINS/SKILLS_OF are extended at its foot, decide() picks the chain, run_chain() picks the decision card, view() adds `process`.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)
NOT_STATED = "Not stated yet"
ASKS = re.compile(r"\b(sops?|standard operating|procedures?|process(?:es)?|swim ?lanes?|who does what|written down|runbook)\b", re.I)
DATA_EXT = {"csv", "tsv", "xlsx", "xls", "xlsm", "json", "parquet"}
STEPS_Q = re.compile(r"\b(steps?|process|procedure|sop|hand[- ]?overs?|who (?:does|do|is responsible|approves|checks|owns))\b", re.I)
CASH_Q = re.compile(r"\b(cash|liquidity|calls?|nav|net worth)\b", re.I)
SKILL_ASK = "consume.answer-question"
SKILLS_OF = {"p_read": ("intent.read-company-doc",), "p_map": ("intent.draw-process-lanes", "intent.draw-process-steps", "intent.map-decision-path"),
             "p_sop": ("intent.write-sop",), "p_live": ("build.go-live",)}


def _h():
    from sh_platform.v1 import v3_harbor as H
    return H


def _flat(s) -> str:
    return " ".join(str(s or "").split())


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


# ---- is this a process-only build? -------------------------------------------------------------------------------------------------

def is_process(plane, th: dict, sow: dict) -> bool:
    """The brief asks for a process, procedure or SOP, none of its figures is worked out by a formula over data (a figure a pack only
    suggested does not count), and every file that arrived is a document (text, Word, PDF, email), not a data table."""
    g = sow.get("goal") or {}
    if not ASKS.search(f"{g.get('line') or ''} {sow.get('title') or ''}"):
        return False
    filled = _filled(plane, sow.get("intent_id") or th.get("iid"))
    if any(isinstance(k, dict) and k.get("formula") and not k.get("pack_suggested") and _flat(k.get("name")).lower() not in filled for k in sow.get("kpis") or []):
        return False
    return not {_ext(f["name"]) for f in _h().read_files(plane) if f.get("thread") in (None, th["id"]) and f.get("status") != "loaded"} & DATA_EXT


def _filled(plane, iid) -> set[str]:
    """Names of the figures North drafted only in answer to Harbor's own "propose the usual practice" fill (v3_harbor.FILL): suggestions,
    whatever the model marked. Since the sign-off fix accepts North's drafts before Decision 1 they are in the brief when the mode is
    settled (test cycle 2, hr_admin: a process ask went down the data path). A figure the person's own words also gave still counts."""
    from sh_platform.v1 import l2_proposals as L2
    try:
        rows = L2._read(plane, iid) if iid else []
    except Exception:  # noqa: BLE001 - no proposals readable: every figure in the brief counts, as before
        return set()
    fill, said, head = set(), set(), _h().FILL[:60]
    for p in rows:
        pl = (p.get("payload") or {}) if p.get("document") == "sow" else {}
        names = {_flat(k.get("name")).lower() for k in (pl.get("sow_patch") or {}).get("kpis") or [] if isinstance(k, dict)}
        (fill if str(pl.get("text") or "").startswith(head) else said).update(names)
    return fill - said


def chain_name(plane, th: dict, n: int) -> str:
    """The chain to run after decision n: A/B/C, or PA/PB/PC for a process-only thread. Decision 1 settles which it is, once."""
    if n == 1 and "mode" not in th and th.get("iid"):
        from sh_platform.v1 import i4_sow as S
        try:
            th["mode"] = "process" if is_process(plane, th, S.read(plane, th["iid"])) else "data"
        except Exception:  # noqa: BLE001 - unreadable brief: the usual path decides
            th["mode"] = "data"
        _h().save(plane, th)
    return ("P" if th.get("mode") == "process" else "") + "ABC"[n - 1]


# ---- reading the documents -------------------------------------------------------------------------------------------------------

_HEAD = re.compile(r"^#{1,6}\s*step\s+(\d+)\s*[.:)\-]?\s*(.+?)\s*$", re.I | re.M)
_FIELD = re.compile(r"^\s*[-*]\s*(who|owner|system|manual[^:]*|control|known exception|exception|inputs?|outputs?)\s*:\s*(.+?)\s*$", re.I | re.M)
_HAND = re.compile(r"hand-?over\s+(\d+)\s*[-–to]+\s*(\d+)\s*:\s*(.+)", re.I)
_NUM = re.compile(r"^\s*(\d+)[.)]\s+(\S.+)$", re.M)
_SECTION_END = re.compile(r"^#{1,2}\s", re.M)


def _structured(text: str) -> list[dict]:
    """'### Step 1. Name' blocks with '- Who:' ... bullets and a paragraph of what is done."""
    heads, out = list(_HEAD.finditer(text)), []
    for m in heads:
        rest = text[m.end():]
        end = _SECTION_END.search(rest)
        nxt = _HEAD.search(rest)
        stop = min(x.start() for x in (end, nxt) if x) if (end or nxt) else len(rest)
        block = rest[:stop]
        f = {k.lower().split()[0].rstrip("s"): v.strip() for k, v in _FIELD.findall(block)}
        prose = _flat(" ".join(ln for ln in block.splitlines() if ln.strip() and not re.match(r"\s*([-*]\s|\|)", ln)))
        s = {"n": int(m.group(1)), "name": _flat(m.group(2)), "who": f.get("who") or f.get("owner") or "", "system": f.get("system", ""), "does": prose,
             "control": f.get("control", ""), "exception": f.get("known") or f.get("exception", ""), "inputs": [f["input"]] if f.get("input") else [],
             "outputs": [f["output"]] if f.get("output") else []}
        flag = next((v for k, v in f.items() if k.startswith("manual")), "")
        if flag.lower().startswith(("yes", "no")):
            s["manual"] = flag.lower().startswith("yes")
        out.append(s)
    return out


def _numbered(text: str) -> list[dict]:
    """An informal list ('1. Collect the exports (File drop). I pull ...'): the name, the system in brackets, the rest as what is done.
    The sender of an email is who, for a sentence in the first person."""
    sender = (re.search(r"^From:\s*([^<\n]+)", text, re.M) or [None, ""])[1].strip()
    out = []
    for m in _NUM.finditer(text):
        body = _flat(m.group(2))
        head, _, rest = body.partition(". ")
        name = re.sub(r"\s*\([^)]*\)", "", head).strip()
        sysm = re.search(r"\(([^()]+)\)", head)
        out.append({"n": int(m.group(1)), "name": name, "who": sender if re.search(r"\bI\b", rest) else "", "system": sysm.group(1).strip() if sysm else "",
                    "does": rest, "control": "", "exception": "", "inputs": [], "outputs": []})
    return out if len(out) >= 2 else []


def _overlap(a: str, b: str) -> bool:
    return bool(_h()._toks(a) & _h()._toks(b))


def merge(docs: list[tuple[str, list[dict]]]) -> tuple[list[dict], dict]:
    """The document with most steps is the base; another document fills only what the base leaves empty, for the step with the same number and
    a shared word in its name. Each step keeps the files it came from. Returns (steps, {n: [files]})."""
    docs = [d for d in docs if d[1]]
    if not docs:
        return [], {}
    docs.sort(key=lambda d: -len(d[1]))
    (bf, base), rest = docs[0], docs[1:]
    seen = {s["n"]: [bf] for s in base}
    for f, steps in rest:
        for s in steps:
            tgt = next((b for b in base if b["n"] == s["n"] and (_overlap(b["name"], s["name"]) or _overlap(b["system"], s["system"]))), None)
            if not tgt:
                continue
            for k in ("who", "system", "does", "control", "exception"):
                if not tgt[k] and s[k]:
                    tgt[k] = s[k]
            seen[tgt["n"]].append(f)
    return base, seen


def handovers_of(text: str) -> list[dict]:
    return [{"from_step": int(a), "to_step": int(b), "what": _flat(w)} for a, b, w in _HAND.findall(text)]


def _section(text: str, word: str) -> str:
    m = re.search(rf"^#{{1,3}}\s*(?:\d+\.\s*)?{word}\s*$", text, re.I | re.M)
    if not m:
        return ""
    rest = text[m.end():]
    end = re.search(r"^#{1,3}\s", rest, re.M)
    return _flat(rest[:end.start() if end else len(rest)])


def read_docs(plane, names: list[str]) -> tuple[list[dict], list[dict]]:
    """[{file, text, facts}] for every document that reads, [{title, text}] for each that does not. Facts are i5_docs's rule-based reading."""
    from sh_platform.context_docs import reader
    from sh_platform.v1 import i5_docs
    got, aside = [], []
    for name in names:
        try:
            data = plane.path("dropbox", name).read_bytes()
            text = "\n".join(t for _, t in reader.read_segments(name, data))
            if not text.strip():
                raise reader.Refusal("It holds no text I can read.")
            got.append({"file": name, "text": text, "facts": i5_docs.read_document(None, name, text)})
        except Exception as e:  # noqa: BLE001 - one document that will not read is set aside and named; the others still count
            aside.append({"title": f"{name} did not read", "text": str(e)[:200]})
    return got, aside


def figures(docs: list[dict]) -> dict:
    """The figures a document-read process gives the signals and the key: the step count, the owner of each step by its name, the steps with no
    owner or no control, the steps done by hand, the hand-overs. From read_docs' output; {} when no document gives steps."""
    steps, seen = merge([(d["file"], _structured(d["text"]) or _numbered(d["text"])) for d in docs])
    if not steps:
        return {}
    text = "\n".join(d["text"] for d in docs)
    return {"process_name": _flat((re.search(r"^Project:\s*(.+)$", text, re.M) or [None, ""])[1]), "steps": len(steps),
            "steps_without_owner": sum(1 for s in steps if not s["who"]), "steps_without_check": sum(1 for s in steps if not s["control"]),
            "manual_steps": sum(1 for s in steps if s.get("manual")), "manual_step_numbers": [s["n"] for s in steps if s.get("manual")],
            "owners": {s["name"]: s["who"] for s in steps}, "handovers": next((h for d in docs if (h := handovers_of(d["text"]))), []),
            "files": [d["file"] for d in docs]}


def _claim(x) -> list[str]:
    """The documents of this thread: its recognised files and any document still waiting for a home. They are marked read."""
    H = _h()
    names = []
    with H.LOCK:
        fs = H.read_files(x.plane)
        for f in fs:
            doc = _ext(f["name"]) not in DATA_EXT and f["source"] != "benchmark"
            if doc and (f.get("thread") == x.th["id"] or (f.get("thread") is None and f["status"] in ("waiting", "question"))):
                f.update(thread=x.th["id"], status="loaded", source=f.get("source") or "process description")
                names.append(f["name"])
        if names:
            import json
            H._fp(x.plane).write_text(json.dumps(fs), encoding="utf-8")
    return names


# ---- the chains ---------------------------------------------------------------------------------------------------------------------

def lanes_of(steps: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for s in steps:
        by.setdefault(s["who"] or NOT_STATED, []).append(s)
    return [{"name": w, "systems": list(dict.fromkeys(s["system"] for s in ss if s["system"])), "steps": [s["n"] for s in ss]} for w, ss in by.items()]


def decisions_of(steps: list[dict]) -> list[dict]:
    """The decision path: a step with a control and a way out when it fails. Owner is the step's person, the trigger is its control; who is told
    is only filled when the step's own words say so ('X is told')."""
    out = []
    for s in steps:
        if s["control"] and s["exception"]:
            told = re.search(r"\b([A-Z][a-z]+) is told\b", s["does"])
            out.append({"step": s["n"], "owner": s["who"] or NOT_STATED, "trigger": s["control"], "then": s["exception"], "told": told.group(1) if told else ""})
    return out


def p_read(x):
    from sh_platform.v1.v3_harbor import Q
    th, names = x.th, _claim(x)
    docs, aside = read_docs(x.plane, names)
    th["exceptions"] = [*(e for e in th.get("exceptions") or [] if "did not read" not in e.get("title", "")), *aside]
    sow_steps = (x.api("me", "GET", f"/api/v1/intents/{th['iid']}/sow", soft=True) or {}).get("process", {}).get("steps") or []
    if not docs and not sow_steps:
        raise Q("I have no description of the process yet. Drop the document that describes it (Word, PDF, text or an email) in the drop folder and say so.")
    th["process_docs"] = [{"file": d["file"], "text": d["text"][:60000], "facts": {k: len(v) for k, v in d["facts"].items() if isinstance(v, list)}} for d in docs]
    return f"{len(docs)} documents read" + (f", {len(aside)} set aside" if aside else "") + f"; {sum(len(v) for d in docs for k, v in d['facts'].items() if isinstance(v, list))} facts with quotes"


def p_map(x):
    from sh_platform.v1.v3_harbor import Q
    th = x.th
    sow = x.api("me", "GET", f"/api/v1/intents/{th['iid']}/sow", soft=True) or {}
    docs = th.get("process_docs") or []
    steps, seen = merge([(d["file"], _structured(d["text"]) or _numbered(d["text"])) for d in docs])
    hand = next((h for d in docs if (h := handovers_of(d["text"]))), [])
    drafted = False
    if not steps:  # no document gives steps: the signed brief's own map (North's draft) stands, and says so
        drafted = True
        steps = [{"n": s.get("n") or i, "name": s.get("name") or "", "who": s.get("who") or "", "system": s.get("system") or "", "does": s.get("does") or "",
                  "control": s.get("control") or "", "exception": s.get("exception") or "", "inputs": s.get("inputs") or [], "outputs": s.get("outputs") or [],
                  **({"manual": s["manual"]} if isinstance(s.get("manual"), bool) else {})} for i, s in enumerate((sow.get("process") or {}).get("steps") or [], 1)]
        hand = (sow.get("process") or {}).get("handovers") or []
        seen = {s["n"]: ["the signed brief (North's draft)"] for s in steps}
    if not steps:
        raise Q("I could not find the steps of the process in the documents. Tell me the steps in your own words, or drop a document that lists them.")
    for s in steps:
        s["sources"] = seen.get(s["n"], [])
    text = "\n".join(d["text"] for d in docs)
    title = _flat((re.search(r"^Project:\s*(.+)$", text, re.M) or [None, ""])[1]) or sow.get("title") or th["title"]
    th["process"] = {"title": title, "purpose": _section(text, "Purpose")[:500], "steps": steps, "handovers": hand, "lanes": lanes_of(steps),
                     "decisions": decisions_of(steps), "from_documents": not drafted, "files": [d["file"] for d in docs]}
    return f"{len(steps)} steps in {len(th['process']['lanes'])} lanes, {len(hand)} hand-overs, {len(th['process']['decisions'])} decisions" + (" (from North's draft)" if drafted else "")


def d2(x) -> dict:
    """Decision 2: is this the process? One row per step (who, system, where it hands over), the lanes in the summary."""
    p, rows = x.th["process"], []
    hand = {h["from_step"]: h for h in p["handovers"]}
    for s in p["steps"]:
        h = hand.get(s["n"])
        goes = f"hands over to step {h['to_step']}: {h['what']}" if h else "end of the process"
        rows.append({"name": f"{s['n']}. {s['name']}", "read_as": f"{s['who'] or NOT_STATED}, {s['system'] or NOT_STATED}" + (", by hand" if s.get("manual") else ""),
                     "goes_to": goes, "state": "manual" if s.get("manual") else "not manual",
                     "confidence": "high" if p["from_documents"] and s["control"] and s["exception"] else "medium"})
    lanes = "; ".join(f"{la['name']}: steps {', '.join(map(str, la['steps']))}" + (f" in {', '.join(la['systems'])}" if la["systems"] else "") for la in p["lanes"])
    src = "Read from " + ", ".join(p["files"]) + "." if p["from_documents"] else "No document gave the steps, so this is North's draft from the brief."
    return {"n": 2, "title": "Is this the process?", "files": rows, "questions": [], "process": p,
            "summary": f"{src} {len(p['steps'])} steps, {len(p['lanes'])} lanes ({lanes}), {len(p['handovers'])} hand-overs. Nothing is loaded; this use case is a process and a procedure."}


def p_sop(x):
    from sh_platform.v1 import i4_sow as S
    from sh_platform.v1 import k8_sop as K
    th, p = x.th, x.th["process"]
    sow = S.read(x.plane, th["iid"])
    g = sow.get("goal") or {}
    sop = K.build({**sow, "title": p["title"], "goal": {**g, "why": g.get("why") or p["purpose"]}, "kpis": [], "unclear": [],
                   "process": {"steps": [{k: v for k, v in s.items() if k != "sources"} for s in p["steps"]], "handovers": p["handovers"]}})
    sop["controls"] += [f"Decision at step {d['step']} ({d['owner']}): when {d['trigger'].rstrip('.')}, then {d['then'].rstrip('.')}." + (f" {d['told']} is told." if d["told"] else "")
                        for d in p["decisions"]]
    sop["open_points"] += [f"Step {s['n']} ({s['name']}): input and output are not stated in the documents." for s in p["steps"] if not s["inputs"] and not s["outputs"]]
    th["sop"] = sop
    return f"SOP written: {len(sop['steps'])} steps, {len(sop['manual_steps'])} flagged for automation, {len(sop['open_points'])} open points"


def downloads(th: dict) -> dict:
    base = f"/api/v3/threads/{th['id']}/sop"
    return {"docx": f"{base}?format=docx", "md": f"{base}?format=md"}


def d3(x) -> dict:
    """Decision 3: the SOP as a preview, one row per step; a step is 'ok' when its control and what to do when it goes wrong are stated."""
    sop = x.th["sop"]
    checks = [{"label": f"{s['n']}. {s['name']}", "value": f"{s['who']}, {s['system']}" + (" (manual)" if s["manual"] else ""),
               "ok": s["control"] != "Not stated yet" and s["exception"] != "Not stated yet",
               "note": f"Control: {s['control']}. If it goes wrong: {s['exception']}."} for s in sop["steps"]]
    return {"n": 3, "title": "Here is the procedure. Go live?", "checks": checks, "sop": {"title": sop["title"], "purpose": sop["purpose"], "roles": sop["roles"],
            "manual_steps": sop["manual_steps"], "controls": sop["controls"], "open_points": sop["open_points"], "download": downloads(x.th)},
            "summary": f"{sop['title']}. {len(sop['manual_steps'])} of {len(sop['steps'])} steps are manual and flagged for automation. "
                       f"{len(sop['open_points'])} open points are listed in the document. Going live keeps the procedure here, to read and download; nothing runs on a schedule."}


def p_live(x):
    th, n = x.th, len(x.th["sop"]["steps"])
    th.pop("next_run", None)  # a document deliverable: no schedule
    short = _flat(th["process"]["title"])[:60]
    th["note"] = {"text": f"{short} is live as a procedure: {n} steps, {len(th['sop']['manual_steps'])} flagged for automation.", "figures": []}
    return "live as a document deliverable, no schedule"


def register(H) -> None:
    """Called once at the foot of v3_harbor: the process chains (they use its a_sign) and the skills each step stands for."""
    H.CHAINS.update({"PA": ([("North", "Signed the intent", H.a_sign), ("North", "Read the documents", p_read), ("North", "Drew the process map", p_map)], "decision2"),
                     "PB": ([("North", "Wrote the procedure", p_sop)], "decision3"),
                     "PC": ([("Harbor", "Went live with the procedure", p_live)], "live")})
    H.SKILLS_OF.update(SKILLS_OF)


DECISIONS = {"decision2": d2, "decision3": d3}
SAY = {"PA": "Here is the process as I read it. Check the lanes, the steps and the hand-overs.", "PB": "I have written the procedure. Take a look."}


def view_of(th: dict) -> dict | None:
    if th.get("mode") != "process" or th.get("stage") != "live" or not th.get("sop"):
        return None
    return {"title": th["sop"]["title"], "steps": len(th["sop"]["steps"]), "download": downloads(th)}


# ---- Consume, Ask, Knowledge --------------------------------------------------------------------------------------------------------

def live_threads(plane) -> list[dict]:
    return [t for t in _h().all_threads(plane) if t.get("stage") == "live" and t.get("mode") == "process" and t.get("sop")]


def golden(plane) -> list[str]:
    return [f"What are the steps of {t['process']['title']}?" for t in live_threads(plane)[:3]]


def reports(plane) -> list[dict]:
    return [{"name": "Standard operating procedure (Word)", "href": downloads(t)["docx"]} for t in live_threads(plane)[:3]]


def _pick(plane, text: str) -> dict | None:
    ths = live_threads(plane)
    return max(ths, key=lambda t: len(_h()._toks(text) & _h()._toks(" ".join([t["process"]["title"], *(s["name"] for s in t["sop"]["steps"])]))), default=None)


def answer(plane, text: str, pid=None) -> dict | None:
    """'What are the steps of ...': from the live SOP, as a tool call. None for any other question, so Lumen answers it."""
    if not STEPS_Q.search(text) or (CASH_Q.search(text) and not re.search(r"\b(steps?|process|procedure|sop)\b", text, re.I)):
        return None
    th = _pick(plane, text)
    if not th:
        return None
    from sh_platform.v1 import v3_skills
    sop, q = th["sop"], text.lower()
    with v3_skills.record(plane, th["id"], SKILL_ASK) as rec:
        steps = sop["steps"]
        one = re.search(r"\bstep (\d+)\b", q)
        if one and (s := next((s for s in steps if str(s["n"]) == one.group(1)), None)):
            ans = (f"Step {s['n']}, {s['name']}, is done by {s['who']} in {s['system']}. Input: {s['input']}. Output: {s['output']}. "
                   f"Control: {s['control']}. If it goes wrong: {s['exception']}." + "".join(f" It hands over to step {h['to_step']}: {h['what']}." for h in s["handovers"]))
            rows = [{"label": f"Step {s['n']}", "value": f"{s['who']}, {s['system']}"}]
        else:
            pick = [s for s in steps if s["manual"]] if re.search(r"manual|automat", q) else steps
            lead = "These steps are done by hand and are candidates for automation: " if pick is not steps else f"{sop['title'].split(': ', 1)[-1]} has {len(steps)} steps: "
            ans = lead + "; ".join(f"{s['n']}. {s['name']} ({s['who']}, {s['system']})" for s in pick) + "."
            rows = [{"label": f"{s['n']}. {s['name']}", "value": f"{s['who']}, {s['system']}"} for s in pick]
        rec["detail"] = ans[:200]
    return {"answer": ans, "figure": None, "rows": rows, "source": f"{sop['title']}, version {sop['version']}", "used": [],
            "trace": [{"kind": "tool", "label": "Read the standard operating procedure"}, {"kind": "guard", "label": "Every step comes from the documents you dropped"}]}
