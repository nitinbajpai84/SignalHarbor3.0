"""Card L2: proposed changes. An agent's change to a document is a *proposal* until a person accepts it.

`projects/<pid>/proposals.json` (or `intents/<iid>/proposals.json` before the intent has a project) holds a list of
`{id, document, summary, changes: [{op: add|change|remove, path, before, after}], by, at, status, payload}`. The document itself is
untouched until `accept`, so a signed check or a downstream agent (which read the document records, never this file) cannot take a
pending proposal for content. `payload` is what the owning engine needs to apply the change (its own patch, kept as it was).

Engines call `propose(...)` instead of merging, and register an applier: the module named in DOCS exports
`apply_proposal(plane, iid, proposal, who)`, which is its existing merge logic run on the live record. `accept` claims the proposal
under the file lock (pending -> applying), applies it with no lock held (engines take their own locks), then marks it accepted: two
concurrent accepts apply it once, the second is refused. A person's own edit is never a proposal.
"""
from __future__ import annotations

import importlib
import logging
import re
import secrets
from contextlib import suppress
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)

# document key -> (engine module, project artefact, name in a sentence, agent key)
DOCS = {
    "sow": ("i6_chat", "intent", "intent of work", "north"),
    "process_map": ("i6_chat", "intent", "process map", "north"),
    "design": ("a1_chat", "design", "system design", "span"),
    "mapping": ("f1_chat", "build_pack", "ETL mapping", "flow"),
    "brief": ("c3_chat", "brief", "consumption brief", "lumen"),
}
NAMES = {"north": "North", "span": "Span", "flow": "Span", "lumen": "Lumen"}
# who may accept or reject a document's proposals (the people who may talk to its agent); None = every company role
_NOT_PARTICIPANT = {"company_admin", "sponsor", "analyst", "owner", "approver"}  # NI-14 (A11): a participant may ask and draft, never accept
WRITERS = {"design": {"company_admin", "analyst"}, "mapping": {"company_admin", "analyst"}, "brief": {"company_admin", "sponsor", "analyst"},
           "sow": _NOT_PARTICIPANT, "process_map": _NOT_PARTICIPANT}


def may_write(viewer, document: str) -> bool:
    """Whether this person may accept or turn down the document's proposals (the route and the agent's "yes" ask the same)."""
    need = WRITERS.get(document)
    return not need or bool(need & set(getattr(viewer, "roles", ()) or ()))
MAX_KEEP = 200
_IID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_SKIP = {"id", "n", "code", "stated_by", "source_id", "source_ids", "feeds_kpis", "settled", "status", "pack_suggested", "sql_by"}
_LABEL = ("name", "table", "rule", "question", "title", "term", "target_field")


SIGNED_WHY = "The document was signed, so this change can no longer be made."


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


STALE_APPLYING = 60  # seconds


def _age(stamp) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()
    except (TypeError, ValueError):
        return STALE_APPLYING + 1  # no stamp: from before this fix


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- storage ---------------------------------------------------------------------------------------------------------------------

def _path(plane, iid: str):
    if not isinstance(iid, str) or not _IID.match(iid):
        raise Refused(404, "There is no such intent.")
    from sh_platform.v1 import p1_project as P1
    prj = P1.for_intent(plane, iid)
    early = plane.path("intents", iid, "proposals.json")
    if prj is None or early.exists():  # kept where it started if the project came later
        return early
    return plane.path("projects", prj["id"], "proposals.json")


def _read(plane, iid: str) -> list[dict]:
    try:
        got = read_json_strict(_path(plane, iid), list)
    except (OSError, ValueError):
        raise Refused(500, "The proposed changes could not be read. Please ask your administrator.") from None
    rows = [p for p in got or [] if isinstance(p, dict)]
    for p in rows:  # an "applying" that never finished (a crash) is offered again after a minute; apply is idempotent
        if p.get("status") == "applying" and _age(p.get("applying_at")) > STALE_APPLYING:
            p["status"] = "pending"
    return rows


def _write(plane, iid: str, rows: list[dict]) -> None:
    done = [p for p in rows if p.get("status") not in ("pending", "applying")]
    drop = {id(p) for p in done[:-MAX_KEEP]} if MAX_KEEP else {id(p) for p in done}
    # keep the order they were made in (a same-second sort put pending ones first, so "recent[-1]" was not always the latest)
    write_json_atomic(_path(plane, iid), [p for p in rows if id(p) not in drop])


# ---- what changed ----------------------------------------------------------------------------------------------------------------

def _flat(v) -> str:
    if isinstance(v, list):
        return ", ".join(_flat(x) for x in v if x not in (None, "", []))
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_flat(x)}" for k, x in v.items() if k not in _SKIP and x not in (None, "", []))
    if isinstance(v, bool):
        return "yes" if v else "no"
    return "" if v is None else " ".join(str(v).split())


def _label(row: dict, i: int) -> str:
    for k in _LABEL:
        if row.get(k):
            return " ".join(str(row[k]).split())[:80]
    return f"item {i + 1}"


PREVIEW = 600  # N1-A15-02: a drafted row's preview holds every field, short ones first, a long text cut in its own place


def _row_text(row: dict) -> str:
    parts = [f"{k}: {_flat(x)}" for k, x in row.items() if k not in _SKIP and x not in (None, "", [])]
    parts.sort(key=lambda t: len(t) > 120)  # control, exception, who and system are not pushed out by a long "does"
    return "; ".join(t if len(t) <= 160 else t[:157].rstrip() + "..." for t in parts)[:PREVIEW]


def diff(before, after, path: str = "") -> list[dict]:
    """Field-level changes between two versions of a record: rows of a list are matched by their name, table, rule or question."""
    out: list[dict] = []
    if isinstance(before, dict) or isinstance(after, dict):
        a, b = before if isinstance(before, dict) else {}, after if isinstance(after, dict) else {}
        for k in [*a, *(k for k in b if k not in a)]:
            if k not in _SKIP:
                out += diff(a.get(k), b.get(k), f"{path}/{k}" if path else str(k))
    elif any(isinstance(x, dict) for v in (before, after) if isinstance(v, list) for x in v):
        la = {_label(x, i): x for i, x in enumerate(before or []) if isinstance(x, dict)}
        lb = {_label(x, i): x for i, x in enumerate(after or []) if isinstance(x, dict)}
        for lab, row in la.items():
            if lab not in lb:
                out.append({"op": "remove", "path": f"{path}/{lab}", "before": _row_text(row), "after": ""})
        for lab, row in lb.items():
            if lab not in la:
                out.append({"op": "add", "path": f"{path}/{lab}", "before": "", "after": _row_text(row)})
            else:
                out += diff(la[lab], row, f"{path}/{lab}")
    else:
        x, y = _flat(before), _flat(after)
        if x != y:
            out.append({"op": "add" if not x else "remove" if not y else "change", "path": path, "before": x[:PREVIEW], "after": y[:PREVIEW]})
    return out


def _what(c: dict) -> str:
    parts = str(c.get("path") or "").split("/")
    return "the " + (" ".join(parts[1:3]) if len(parts) >= 3 else parts[-1]).replace("_", " ")


def _plural(n: int) -> str:
    return "1 thing" if n == 1 else f"{n} things"


# ---- propose, accept, reject -----------------------------------------------------------------------------------------------------

def propose(plane, iid: str, document: str, summary: str | None, changes: list[dict], *, payload: dict | None = None, by: str | None = None) -> dict | None:
    """Store a proposal and return it (None when nothing would change). Pending proposals stack: an agent's next patch is
    incremental, so an earlier one still waiting for a yes must not be dropped."""
    if document not in DOCS:
        raise Refused(400, "Unknown document.")
    if not changes:
        return None
    agent = by if by in NAMES else DOCS[document][3]
    n = len(changes)
    rec = {"id": "pr_" + secrets.token_hex(6), "document": document,
           "summary": summary or f"{NAMES[agent]} changed {_plural(n)} in the {DOCS[document][2]}",
           "changes": [{k: str(c.get(k) or "")[:PREVIEW] for k in ("op", "path", "before", "after")} for c in changes][:100],
           "by": agent, "at": _now(), "status": "pending", "payload": payload or {}}
    with lock_for(_path(plane, iid)):
        rows = _read(plane, iid)
        rows.append(rec)
        _write(plane, iid, rows)
    return rec


def _signed(plane, iid: str, document: str) -> bool:
    from sh_platform.v1 import p1_project as P1
    prj = P1.for_intent(plane, iid)
    return any(a["kind"] == DOCS[document][1] and a.get("state") == "signed" for a in (prj or {}).get("artefacts") or [])


def _sweep(plane, iid: str) -> None:
    """Pending proposals for a document that has since been signed can never apply: they become `superseded`, with the reason."""
    try:
        gone = {d for d in DOCS if any(p["document"] == d and p["status"] == "pending" for p in _read(plane, iid)) and _signed(plane, iid, d)}
        if not gone:
            return
        with lock_for(_path(plane, iid)):
            rows = _read(plane, iid)
            for p in rows:
                if p["status"] == "pending" and p["document"] in gone:
                    p.update(status="superseded", resolved_at=_now(), reason=SIGNED_WHY)
            _write(plane, iid, rows)
    except Refused:
        pass


def pending(plane, iid: str, documents=None) -> list[dict]:
    _sweep(plane, iid)
    return [p for p in _read(plane, iid) if p.get("status") == "pending" and (documents is None or p["document"] in documents)]


def _set(plane, iid: str, pid: str, **kw) -> dict:
    with lock_for(_path(plane, iid)):
        rows = _read(plane, iid)
        p = next(x for x in rows if x["id"] == pid)
        p.update(kw)
        _write(plane, iid, rows)
    return p


def _claim(plane, iid: str, pid: str) -> dict:
    with lock_for(_path(plane, iid)):
        rows = _read(plane, iid)
        p = next((x for x in rows if x.get("id") == pid), None)
        if p is None:
            raise Refused(404, "There is no such proposed change.")
        if p["status"] != "pending":
            raise Refused(409, "That change has already been dealt with.")
        p.update(status="applying", applying_at=_now())
        _write(plane, iid, rows)
    return p


def accept(plane, iid: str, proposal_id: str, who: str) -> dict:
    """Apply the proposal through its engine, exactly once, and record it as a resolved `change` comment on the document line."""
    p = _claim(plane, iid, proposal_id)
    if _signed(plane, iid, p["document"]):
        _set(plane, iid, proposal_id, status="superseded", resolved_at=_now(), reason=SIGNED_WHY)
        raise Refused(409, SIGNED_WHY)
    try:
        engine = importlib.import_module(f"sh_platform.v1.{DOCS[p['document']][0]}")
        note = engine.apply_proposal(plane, iid, p, who)
    except Exception as e:
        _set(plane, iid, proposal_id, status="pending")  # it can be tried again; an engine may have written part of it, so apply must be idempotent
        if isinstance(e, Refused) or not str(getattr(e, "message", "") or e):
            raise
        raise Refused(int(getattr(e, "status", 409)), str(getattr(e, "message", "") or e)) from None  # an engine's own refusal, in one shape
    done = _set(plane, iid, proposal_id, status="accepted", resolved_by=who, resolved_at=_now(), **({"note": note} if note else {}))
    with suppress(Exception):
        _record(plane, iid, done, who)
    return _public(done)


def withdraw(plane, iid: str, proposal_id: str, changes: list[dict], payload: dict, who: str, reason: str = "") -> dict | None:
    """NU-02: the person turned down part of a pending proposal in words. What is left stays pending with its new changes and payload;
    a proposal with nothing left is rejected with the reason. Returns the proposal as it now stands (None when it was not pending)."""
    with lock_for(_path(plane, iid)):
        rows = _read(plane, iid)
        p = next((x for x in rows if x.get("id") == proposal_id and x.get("status") == "pending"), None)
        if p is None:
            return None
        if changes:
            n = len(changes)
            p.update(changes=[{k: str(c.get(k) or "")[:PREVIEW] for k in ("op", "path", "before", "after")} for c in changes][:100],
                     payload=payload, summary=f"{NAMES.get(p.get('by'), 'The agent')} changed {_plural(n)} in the {DOCS[p['document']][2]}")
        else:
            p.update(status="rejected", resolved_by=who, resolved_at=_now(), reason=" ".join(str(reason or "").split())[:500])
        _write(plane, iid, rows)
    return _public(p)


def reject(plane, iid: str, proposal_id: str, who: str, reason: str = "") -> dict:
    _claim(plane, iid, proposal_id)
    return _public(_set(plane, iid, proposal_id, status="rejected", resolved_by=who, resolved_at=_now(),
                        reason=" ".join(str(reason or "").split())[:500]))


def _record(plane, iid: str, p: dict, who: str) -> None:
    """P1: 'North changed the Net worth definition; accepted by Meredith', resolved, on the line it touched."""
    from sh_platform.v1 import p1_project as P1
    prj = P1.for_intent(plane, iid)  # never makes a project: an intent without one has no trail to write to
    if prj is None:
        return
    pid = prj["id"]
    _, kind, _, agent = DOCS[p["document"]]
    first = p["changes"][0] if p["changes"] else {}
    more = len(p["changes"]) - 1
    text = f"{NAMES[agent]} changed {_what(first) if first else 'the document'}" + (f" and {more} more" if more > 0 else "") + f"; accepted by {who}"
    ref = None
    with suppress(Exception):  # the line of the first change that names one (a goal field such as needed_by has no line of its own)
        lines = [ln for s in P1.document(plane, pid, kind)["sections"] for ln in s["lines"]]
        for c in p["changes"]:
            needle = (str(c.get("path") or "").split("/") + [""])[1].lower()
            ref = ref or next((ln["ref"] for ln in lines if needle and needle in ln["text"].lower()), None)
    c = P1.comment(plane, pid, kind, ref, agent, None, text, kind="change")
    if c:
        P1._change(plane, pid, c["id"], lambda x: x.update(state="resolved", resolved_by=who, resolved_at=_now()))


# ---- the words in chat -----------------------------------------------------------------------------------------------------------

_YES = re.compile(r"^\W*(yes|yep|yeah|accept|accepted|ok|okay|go ahead|looks good|sounds good|that is right|that's right|approved?|please do)\b", re.I)
_FILLER = {"please", "thanks", "thank", "you", "go", "ahead", "do", "it", "that", "them", "all", "is", "right", "looks", "good", "sounds", "north", "span", "flow", "lumen", "to", "me", "so", "great"}
_NO = re.compile(r"^\W*(no|nope|not this|not that|reject|rejected|don't|do not|that's wrong|that is wrong|not quite|wrong)\b", re.I)
_NO_LONG = re.compile(r"^\W*(not this|not that|reject|rejected|that's wrong|that is wrong|don't change|do not change|turn it down)\b", re.I)


def words(text: str) -> str | None:
    """'accept' for a message that is essentially a yes, 'reject' for a bare no (up to four words, "No, liabilities count too") or one that says so outright (the rest is the
    reason). Anything longer ("No, we have never measured it") is an answer to the agent, not a verdict on its proposal."""
    t = str(text or "")
    if _NO_LONG.match(t) or (_NO.match(t) and len(t.split()) <= 4):
        return "reject"
    if (m := _YES.match(t)) and len(t.split()) <= 8 and all(w in _FILLER for w in re.findall(r"[a-z']+", t[m.end():].lower())):
        return "accept"
    return None


def resolve_words(plane, iid: str, text: str, who: str, documents) -> list[dict]:
    """The person's yes or no settles the pending proposals of these documents. Returns what was settled (never raises)."""
    kind = words(text)
    if kind is None:
        return []
    out = []
    try:
        todo = pending(plane, iid, documents)
    except Refused:
        return []
    for p in todo:
        try:
            out.append(accept(plane, iid, p["id"], who) if kind == "accept" else reject(plane, iid, p["id"], who, text))
        except Refused as e:  # e.g. the document was signed meanwhile: it stays pending and the buttons say why
            log.warning("proposal %s not settled by words: %s", p["id"], e.message)
        except Exception:  # noqa: BLE001 - a failing apply never breaks the talk
            log.warning("proposal %s not applied", p["id"])
    return out


def line(p: dict) -> str:
    """A digit-free handle for a proposal, for the agent's next turn."""
    labels = list(dict.fromkeys(_what(c) for c in p.get("changes") or []))[:3]
    return re.sub(r"\d+", "", f"{NAMES.get(p.get('by'), 'The agent')} proposed changes to " + (", ".join(labels) or "the document")).strip()


def facts(plane, iid: str, documents) -> dict:
    """What the agent needs next turn: what is still waiting for a yes, and what the person turned down, with their reason. Strings, not objects: two or more objects in a list are rows to the egress gateway."""
    try:
        rows = [p for p in _read(plane, iid) if p["document"] in documents]
    except Refused:
        return {}
    out = {}
    if w := [line(p) for p in rows if p["status"] == "pending"]:
        out["proposed_waiting_for_the_person"] = w
    if r := [f"{line(p)} (reason: {p.get('reason') or 'no reason given'})" for p in rows if p["status"] == "rejected"][-5:]:
        out["turned_down_by_the_person"] = r
    return out


def tail(n: int) -> str:
    return f" I have proposed {_plural(n)} to change; say yes to accept, or tell me what is wrong."


def _public(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "payload"}


def view(plane, iid: str) -> dict:
    """For the screens: pending proposals (the ChangeBar and the highlights) and the last few that were settled."""
    _sweep(plane, iid)
    rows = _read(plane, iid)
    return {"pending": [_public(p) for p in rows if p["status"] == "pending"],
            "recent": [_public(p) for p in rows if p["status"] in ("accepted", "rejected", "superseded")][-10:]}
