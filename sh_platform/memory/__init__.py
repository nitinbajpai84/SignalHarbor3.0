"""Agent long-term memory (MEM-1). Files `context/memory/<agent>/people/<pid>.json` and `.../company.json` (SHAPES 9).
`remember` is what MEM-2's summariser calls; `for_prompt` is what the agents read."""
import difflib
import hashlib
import re
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.memory import filters
from sh_platform.memory.compact import fold
from sh_platform.plane import CompanyPlane

AGENTS = ("north", "lens", "nira", "span", "flow")
KINDS = ("fact", "preference", "decision", "open")
BUDGET = 4000
SAME = 0.92  # near-same text: replaces the old entry with the new date
CLOSE = 0.6  # same subject, different words: a contradiction, kept as an open question
_PID = re.compile(r"[a-z0-9_@.-]{1,80}")
_SELF = re.compile(r"\b(i|i'm|i've|i'd|my|me|mine|myself)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _path(plane: CompanyPlane, agent: str, pid: str | None):
    if agent not in AGENTS or (pid is not None and not _PID.fullmatch(pid)):
        raise ValueError("unknown agent or person id")
    base = ("context", "memory", agent)
    return plane.path(*base, "company.json") if pid is None else plane.path(*base, "people", f"{pid}.json")


def load(plane: CompanyPlane, agent: str, pid: str | None = None) -> dict:
    doc = read_json_strict(_path(plane, agent, pid), dict)
    return doc if doc and isinstance(doc.get("entries"), list) else {"entries": [], "budget": BUDGET}


def save(plane: CompanyPlane, agent: str, pid: str | None, doc: dict) -> None:
    write_json_atomic(_path(plane, agent, pid), doc)


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, filters.view.norm(a), filters.view.norm(b)).ratio()


def _merge(entries: list[dict], new: dict, now: str) -> None:
    kind = new.get("kind") if new.get("kind") in KINDS else "fact"
    text = str(new["text"]).strip()
    prov = [{"conversation": new.get("conversation"), "at": new.get("at") or now}]
    best = max((e for e in entries if e["kind"] == kind), key=lambda e: _sim(e["text"], text), default=None)
    score = _sim(best["text"], text) if best else 0.0
    if best and score >= SAME:
        if best["by"] != "person":  # a person's edit is never overwritten
            best.update(text=text, updated_at=now, **{"from": [*best["from"], *prov]})
        return
    if best and score >= CLOSE and kind != "open":
        kind = "open"  # contradiction: kept beside the old entry as an open question
    entries.append({"id": hashlib.sha1(f"{kind}|{text}".encode()).hexdigest()[:12], "kind": kind, "text": text, "from": prov, "updated_at": now, "by": "agent"})


def remember(plane: CompanyPlane, agent: str, pid: str, summary_entries: list[dict]) -> dict:
    """Merge a conversation summary ({kind, text, conversation, at, anonymous?}) into this person's memory, after the filters."""
    path = _path(plane, agent, pid)
    with lock_for(path):
        doc = load(plane, agent, pid)
        now = _now()
        for e in filters.clean(plane, summary_entries):
            _merge(doc["entries"], e, now)
        doc["entries"] = fold(doc["entries"], doc.get("budget", BUDGET))
        save(plane, agent, pid, doc)
        return doc


def compact(plane: CompanyPlane, agent: str, pid: str | None = None) -> dict:
    path = _path(plane, agent, pid)
    with lock_for(path):
        doc = load(plane, agent, pid)
        doc["entries"] = fold(doc["entries"], doc.get("budget", BUDGET))
        save(plane, agent, pid, doc)
        return doc


def company_digest(plane: CompanyPlane, agent: str) -> dict:
    """Rebuild company.json from the person memories: names and quotes out, a self statement of one person left out. Admin edits stay."""
    folder = _path(plane, agent, "x").parent
    names = filters.person_names(plane)
    terms = filters.restricted_terms(plane)
    seen: list[tuple[dict, set[str]]] = []  # (entry, people who hold it)
    for f in sorted(folder.glob("*.json")):
        for e in load(plane, agent, f.stem)["entries"]:
            text = filters.depersonalise(e["text"], names)
            if text is None or not filters.allowed(text, terms):
                continue
            hit = next((s for s in seen if s[0]["kind"] == e["kind"] and _sim(s[0]["text"], text) >= SAME), None)
            if hit:
                hit[1].add(f.stem)
                continue
            ats = sorted(p["at"] for p in e["from"] if p.get("at"))[-1:]  # when, never who or which conversation
            seen.append(({"id": e["id"], "kind": e["kind"], "text": text, "from": [{"conversation": "company digest", "at": a} for a in ats],
                          "updated_at": e["updated_at"], "by": "agent"}, {f.stem}))
    kept = [e for e, who in seen if not (len(who) == 1 and _SELF.search(e["text"]))]
    doc = load(plane, agent)
    mine = [e for e in doc["entries"] if e["by"] == "person"]
    doc["entries"] = fold(mine + [e for e in kept if all(_sim(e["text"], m["text"]) < SAME for m in mine)], doc.get("budget", BUDGET))
    save(plane, agent, None, doc)
    return doc


def _fit(entries: list[dict], budget: int) -> tuple[list[dict], int]:
    out: list[dict] = []
    for e in sorted(entries, key=lambda e: (e["by"] == "person", e["updated_at"]), reverse=True):
        if len(e["text"]) > budget:
            continue
        budget -= len(e["text"])
        out.append({"id": e["id"], "kind": e["kind"], "text": e["text"]})
    return out, budget


def for_prompt(plane: CompanyPlane, agent: str, pid: str | None = None, budget: int = BUDGET) -> dict:
    """{"person": [...], "company": [...]} within `budget` characters in all; no person id, no person memory."""
    person, left = _fit(load(plane, agent, pid)["entries"], budget) if pid else ([], budget)
    company, _ = _fit(load(plane, agent)["entries"], left)
    return {"person": person, "company": company}
