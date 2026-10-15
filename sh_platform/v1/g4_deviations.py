"""G4 Deviations need approval before Span implements them.

Span may fix a benchmark miss itself while the signed design and the definitions stay as they are (a new run, a re-read): that is no deviation.
A change of the formulation, the source or the approach (another source field, another formula or SQL, dropping a row) is written as a
**deviation**: a P1 comment of kind `approval` on the build pack, addressed to the head of data (and to the raiser as well when a business
definition changes), with the before and after, why, and the benchmark rows it would fix. Nothing is implemented until every addressee has
answered "approved" (the answer is read by `decision`; anything else is refused with a sentence). A "not approved" closes the deviation and keeps
the approver's reason as the next fact for Span (f1 reads `declined`). An approved deviation is implemented (the mapping row or sheet row
changes), recorded as a **signed amendment to the system design** (`build/blueprint_conversation/<iid>.json` -> `amendments`, signed by the head
of data) and on the project trail (a note on the design). A miss Span cannot resolve at all is always raised: `raise_unresolved`.

Record: `build/deviations/<iid>.json` = [{id, kind, summary, about, before, after, why, effect: [refs], effect_labels, business_definition, change,
mapping_row, sheet_row, sheet_change, drop_sheet_row, status: pending|approved (not yet made)|implemented|declined, asks: [{key, name, cid}], decisions: {name: {decision,
reason, at}}, by, at, amendment, reason}].
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import p1_project as P1

log = logging.getLogger(__name__)
ARTEFACT = "build_pack"
SOURCE_KEYS = ("source_id", "source_table", "source_field")
FORMULA_KEYS = ("transformation", "sql", "formula")
YES = re.compile(r"^\W*approved\b", re.I)
NO = re.compile(r"^\W*(not approved|not this)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(plane, iid: str):
    return plane.path("build", "deviations", f"{iid}.json")


def read(plane, iid: str) -> list[dict]:
    try:
        return [d for d in read_json_strict(_path(plane, iid), list) or [] if isinstance(d, dict)]
    except (OSError, ValueError):
        return []


def decision(text: str) -> tuple[bool, str]:
    """(approved, reason) from an approver's answer, or P1.Refused when it says neither."""
    t = str(text or "").strip()
    if NO.match(t):
        return False, re.sub(NO, "", t, count=1).strip(" :.-,") or "no reason given"
    if YES.match(t):
        return True, re.sub(YES, "", t, count=1).strip(" :.-,")
    raise P1.Refused(400, 'Answer "approved", or "not approved" with your reason.')


def classify(change: dict | None, drop: bool = False) -> str:
    """"own_fix" when the change keeps the design's formulation, source and approach (Span just runs again), else the kind of deviation."""
    change = change or {}
    if drop:
        return "drop_row"
    if any(change.get(k) for k in SOURCE_KEYS):
        return "source"
    if any(change.get(k) for k in FORMULA_KEYS):
        return "formulation"
    return "own_fix"


def head_of_data(plane, iid: str) -> str | None:
    p = P1.project_of(plane, iid) or {}
    return (p.get("people") or {}).get("head_of_data") or None


def _ticket(plane, pid: str, dev: dict, c: dict, by: str) -> None:
    """T2: each approval is a ticket of stage design to the approver; the approval comment is its discussion and closes it when answered."""
    try:
        from sh_platform.v1 import t2_tickets
    except ImportError:
        return
    t2_tickets.raise_guarded(plane, by=by, to=c["to"], title=f"Approve or not: {dev['summary']}"[:120], body=c["text"], project=pid, stage="design", priority="high",
                             links=[{"kind": "line", "ref": f"{pid}:{ARTEFACT}:deviation:{dev['id']}"}, {"kind": "comment", "ref": f"{pid}:{c['id']}"}])


def _settle(plane, c: dict, who: str, note: str) -> None:
    try:
        from sh_platform.v1 import t2_tickets
        t2_tickets.settle_comment(plane, c["cid"] if "cid" in c else c["id"], who, "resolved", note)
    except Exception:  # noqa: BLE001 - the decision stands without its ticket
        log.warning("ticket for %s not settled", c.get("cid") or c.get("id"), exc_info=True)


def propose(plane, iid: str, *, summary: str, about: str, before: str, after: str, why: str, effect: list[str],
            effect_labels: list[str] | None = None, change: dict | None = None, mapping_row: int | None = None, drop_sheet_row: str | None = None,
            sheet_row: str | None = None, sheet_change: dict | None = None, business_definition: bool = False, by: str = "flow") -> dict:
    """Write a deviation and ask the approver(s). Refused (P1.Refused) when the change needs none, or the same change was already declined."""
    kind = classify(change, bool(drop_sheet_row)) if (change or drop_sheet_row) else "approach"
    if kind == "own_fix":
        raise P1.Refused(409, "This change keeps the signed design and its definitions, so Span runs the load again without asking.")
    p = P1.project_of(plane, iid)
    if p is None:
        raise P1.Refused(404, "This intent has no project yet.")
    if not head_of_data(plane, iid):  # P1 would send an unnamed part to the raiser, who must not approve a technical change
        raise P1.Refused(409, "Name the head of data on the project first; a technical change is approved by them.")
    text_of = lambda v, n=400: " ".join(str(v or "").split())[:n]  # noqa: E731
    dev = {"id": "dv_" + secrets.token_hex(4), "kind": kind, "summary": text_of(summary, 200), "about": text_of(about, 120), "before": text_of(before),
           "after": text_of(after), "why": text_of(why, 600), "effect": [str(e) for e in effect][:40], "effect_labels": [text_of(x, 100) for x in effect_labels or []][:40],
           "business_definition": bool(business_definition), "change": change or {}, "mapping_row": mapping_row, "sheet_row": sheet_row,
           "sheet_change": sheet_change or {}, "drop_sheet_row": drop_sheet_row, "status": "pending", "asks": [], "decisions": {}, "by": by, "at": _now(),
           "amendment": None, "reason": None}
    with lock_for(_path(plane, iid)):
        devs = read(plane, iid)
        if any(d["status"] in ("pending", "declined") and d["summary"] == dev["summary"] and d["after"] == dev["after"] for d in devs):
            raise P1.Refused(409, "Span has already asked about this change. Answer that request, or change what is asked.")
        keys = ["head_of_data"] + (["raiser"] if business_definition else [])
        text = (f"{'Span' if by == 'flow' else by} asks to {dev['summary']}.\nBefore: {dev['before']}\nAfter: {dev['after']}\nWhy: {dev['why']}\n"
                f"If approved it would fix {len(dev['effect'])} benchmark row{'s' if len(dev['effect']) != 1 else ''}"
                + (f": {', '.join(dev['effect_labels'])}" if dev["effect_labels"] else "") + ".\n"
                'Answer "approved", or "not approved" with your reason. Nothing changes until then.')
        for key in keys:
            c = P1.comment(plane, iid, ARTEFACT, f"deviation:{dev['id']}", by, key, text, kind="approval")
            if c and not any(a["name"] == c["to"] for a in dev["asks"]):
                dev["asks"].append({"key": key, "name": c["to"], "cid": c["id"]})
                _ticket(plane, p["id"], dev, c, by)
        devs.append(dev)
        write_json_atomic(_path(plane, iid), devs)
    return dev


# ---- the answer ------------------------------------------------------------------------------------------------------------------------

def _implement(plane, iid: str, dev: dict) -> None:
    """The approved change, made: a mapping row edited, a sheet row changed or dropped. Business definitions are recorded only (the SOW is signed)."""
    if dev.get("mapping_row") is not None and dev.get("change"):
        from sh_platform.v1 import b3_mapping as M
        M.edit_row(plane, iid, int(dev["mapping_row"]), {**{k: str(v) for k, v in dev["change"].items()}, "status": "mapped"})
    if dev.get("drop_sheet_row") or dev.get("sheet_row"):
        from sh_platform.v1 import g3_sheet as G3
        with lock_for(G3._path(plane, iid)):
            sheet = G3.read(plane, iid)
            row = next((r for r in sheet["rows"] if r.get("id") == (dev.get("drop_sheet_row") or dev.get("sheet_row"))), None)
            if row is None:
                raise ValueError("The benchmark row it changes no longer exists.")
            if dev.get("drop_sheet_row"):
                row["dropped"] = True
            for f in G3.EDITABLE:
                if f in (dev.get("sheet_change") or {}):
                    row[f] = float(dev["sheet_change"][f])
            row["amended_by"] = dev["id"]
            G3._write(plane, iid, sheet)


def _amend(plane, iid: str, dev: dict, signer: str | None) -> dict:
    from sh_platform.v1 import a1_chat as A1
    with lock_for(A1._path(plane, iid)):
        rec = A1.read(plane, iid)
        n = len(rec.get("amendments") or []) + 1
        am = {"id": "am_" + secrets.token_hex(4), "version": f"A{n}", "at": _now(), "deviation": dev["id"], "kind": dev["kind"], "summary": dev["summary"],
              "before": dev["before"], "after": dev["after"], "why": dev["why"], "effect": dev["effect_labels"], "signed_by": signer, "signed_at": _now(),
              "also_approved_by": [a["name"] for a in dev["asks"] if a["name"] != signer]}
        rec.setdefault("amendments", []).append(am)
        write_json_atomic(A1._path(plane, iid), rec)
    return am


def _make(plane, iid: str, dev: dict, who: str) -> str:
    """Make an approved change. Only when it is made is the design amendment signed; else it stays "approved, not yet made" and can be retried."""
    try:
        _implement(plane, iid, dev)
    except Exception as e:  # noqa: BLE001 - the approval stands; the failure is said, not hidden, and the miss stays open
        log.warning("deviation %s approved but not implemented (%s)", dev["id"], type(e).__name__)
        dev.update(status="approved", implement_error=str(e)[:200])
        return f"Approved by {', '.join(a['name'] for a in dev['asks'])}: Span {dev['summary']}, but the change is not made yet ({dev['implement_error']}). The engineer can make it now."
    dev.update(status="implemented", implement_error=None)
    signer = next((a["name"] for a in dev["asks"] if a["key"] == "head_of_data"), who)
    am = _amend(plane, iid, dev, signer)
    dev["amendment"] = am["id"]
    return f"Approved by {', '.join(a['name'] for a in dev['asks'])}: Span {dev['summary']}. Recorded as amendment {am['version']} of the system design, signed by {signer}. Span runs the load again to check it."


def make_now(plane, iid: str, did: str, who: str) -> dict:
    """The engineer re-runs the implementation of an "approved, not yet made" deviation (P1.Refused when there is nothing to make)."""
    with lock_for(_path(plane, iid)):
        devs = read(plane, iid)
        dev = next((d for d in devs if d["id"] == did), None)
        if dev is None:
            raise P1.Refused(404, "There is no such request.")
        if dev["status"] != "approved":
            raise P1.Refused(409, "Only an approved change that is not yet made can be made now.")
        note = _make(plane, iid, dev, who)
        write_json_atomic(_path(plane, iid), devs)
    with __import__("contextlib").suppress(Exception):
        P1.comment(plane, iid, "design", f"deviation:{did}", "flow", "raiser", note, kind="note")
    return dev


def after_answer(plane, iid: str, c: dict, who: str) -> None:
    """Called by P1 once an approval comment is answered: record the decision; decline at once, or implement when everyone approved."""
    did = str(c.get("line_ref") or "").removeprefix("deviation:")
    with lock_for(_path(plane, iid)):
        devs = read(plane, iid)
        dev = next((d for d in devs if d["id"] == did), None)
        if dev is None or dev["status"] != "pending":
            return
        ok, reason = decision(c.get("answer"))
        dev["decisions"][who] = {"decision": "approved" if ok else "not approved", "reason": reason, "at": _now()}
        note = None
        if not ok:
            dev.update(status="declined", reason=reason)
            for a in dev["asks"]:  # the other ask is closed: the question no longer stands
                if a["name"] != who:
                    with __import__("contextlib").suppress(Exception):
                        P1._change(plane, P1._pid_of(plane, iid), a["cid"], lambda x: x.update(state="resolved", resolved_by="flow", resolved_at=_now())
                                   if x["state"] == "open" else None)
            note = f"{who} did not approve: Span {dev['summary']}. Reason: {reason}. The miss stays open."
        elif all(dev["decisions"].get(a["name"], {}).get("decision") == "approved" for a in dev["asks"]):
            note = _make(plane, iid, dev, who)
        write_json_atomic(_path(plane, iid), devs)
    for a in dev["asks"]:  # T2: an answer settles that approver's ticket; a decline settles the other approver's too (their question no longer stands)
        if a["name"] == who or not ok:
            _settle(plane, a, who, f"{who}: {dev['decisions'][who]['decision']}" if a["name"] == who else f"{who} did not approve.")
    if note:
        with __import__("contextlib").suppress(Exception):
            P1.comment(plane, iid, "design", f"deviation:{did}", "flow", "raiser", note, kind="note")


def check_answerer(plane, iid: str, did: str, who: str) -> None:
    """The person who raised a deviation never answers it, whatever the `by` label says (P1.Refused 403)."""
    dev = next((d for d in read(plane, iid) if d["id"] == did), None)
    if dev and dev.get("by") == who:
        raise P1.Refused(403, "You raised this request; another approver answers it.")


def declined(plane, iid: str) -> list[dict]:
    """Not-approved deviations with the approver's reason: the next fact for Span."""
    return [{"about": d["about"], "summary": d["summary"], "reason": d.get("reason"), "effect": d.get("effect_labels")} for d in read(plane, iid)
            if d.get("status") == "declined"]


def pending(plane, iid: str) -> list[dict]:
    return [d for d in read(plane, iid) if d.get("status") == "pending"]


def unmade(plane, iid: str) -> list[dict]:
    """Approved but the change could not be made, and its rows are not met by the last load (a hand fix that meets them clears it)."""
    from sh_platform.v1 import p4_benchmarks as P4
    met = {P4._ref(r) for r in P4._read(plane.path("build", "verify", f"{iid}.json"), list) if isinstance(r, dict) and r.get("met") is True}
    return [d for d in read(plane, iid) if d.get("status") == "approved" and not (d.get("effect") and set(d["effect"]) <= met)]


def pending_block(plane, iid: str) -> str | None:
    p, u = pending(plane, iid), unmade(plane, iid)
    if u and not p:
        return f"{len(u)} approved deviation{'s are' if len(u) > 1 else ' is'} approved, not yet made ({u[0].get('implement_error') or 'Span could not apply it'})."
    if not p:
        return None
    who = ", ".join(dict.fromkeys(a["name"] for d in p for a in d["asks"] if (d["decisions"].get(a["name"]) or {}).get("decision") != "approved"))
    return f"{len(p)} deviation request{'s are' if len(p) > 1 else ' is'} still waiting for approval from {who or 'the approver'}."


def raise_unresolved(plane, iid: str, sow: dict, rows: list[dict]) -> None:
    """A miss Span cannot resolve (no loaded figure to compare, or no column to compare it on) is never left silent: a plain comment to the
    head of data on the build pack, once."""
    if not rows:
        return
    from sh_platform.v1 import p4_benchmarks as P4
    names = {k.get("code"): k.get("name") or k.get("code") for k in sow.get("kpis") or [] if isinstance(k, dict)}
    have = {(c.get("line_ref"), c.get("text")) for c in P1.comments(plane, P1.project_of(plane, iid)["id"], ARTEFACT)}
    for r in rows:
        name = f"{names.get(r['code'], r['code'])}" + (f" ({r['label']})" if r.get("label") else "")
        text = (f"Span cannot resolve the miss on {name} for {r['period']}: {r.get('why') or 'there is no loaded figure to compare'}. "
                "Span could not fix this by running again. Please decide how the figure should be sourced; Span will ask for approval before it changes anything.")
        if (P4._ref(r), text) not in have:
            P1.comment(plane, iid, ARTEFACT, P4._ref(r), "flow", "head_of_data", text)


def view(plane, iid: str) -> dict:
    return {"intent_id": iid, "deviations": read(plane, iid), "pending": pending_block(plane, iid)}
