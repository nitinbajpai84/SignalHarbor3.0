"""Harbor drafts a signal from a repeated human action (docs/v3/SIGNAL-ENGINE.md, "Harbor drafts a signal").

Harbor watches three things people do: the questions they ask in Consume (with the figure that answered), the exceptions they raise or close in
Action, and the checks or holds they apply by hand (a note "checked bank details for X", a dismissal, a manual hold). `observe()` keeps one line
per action in `<company>/v3/signals/watch.jsonl`. When the same kind of action has happened twice (different subjects count), `scan()` drafts a signal
in the engine's yaml format and keeps it as a suggestion with status waiting (`drafts.json`), exactly like an office skill (v3_skills.write_skill).

- The condition comes from a small catalogue of known checks; where two wordings fit, the two-model judge (v3_judge) picks.
- A threshold is never invented. If the pattern implies one and no signed rule exists, the draft says so and asks for the rule; it cannot be admitted until
  that rule is signed.
- `backtest()` runs the drafted condition over the documents the office loaded in the last six months (`arrivals.jsonl`) and counts the hits.
- The decision maker admits (the draft becomes an office signal, which overrides the pack's), edits or rejects. A rejection is remembered: the same pattern is
  never drafted again."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

import yaml

from sh_platform.jsonfile import write_json_atomic

log = logging.getLogger(__name__)
LOCK = threading.RLock()
REPEATS = 2
MONTHS = 6
DECIDER = "principal"  # the role that decides what Harbor watches for
SOURCES = {"question", "exception", "check", "dismissal", "hold"}
VERB = {"question": "see", "exception": "record", "check": "record", "dismissal": "record", "hold": "record"}
# Known checks: the kind of action, the document it happens after, and the condition that says it is needed. No threshold lives here.
KNOWN = {
    "bank_details": {
        "title": "Bank details differ from the standing instructions", "after": "capital_call_notice", "verb": "call_back",
        "inputs": [{"kind": "doc", "fields": ["fund", "bank_account", "call_no"]}, {"kind": "figure", "id": "standing_instructions", "as": "si", "by": {"fund": "doc.fund"}}],
        "conditions": ["last4(doc.bank_account) != last4(si.account)"], "subject": "{doc.fund} call {doc.call_no}",
        "message": "The bank account on the notice for {doc.fund} ends {doc.bank_account}; the standing instructions say {si.account}. Check the details before any payment.",
        "hold": {"blocks": "prepare_payment", "scope": "{doc.fund}", "until": "the check is recorded"}},
}
WATCH = {  # anything else: a figure someone keeps looking at. It needs a limit, and the limit is the office's to sign.
    "conditions": ["num(fig.value) > num(limit.amount)", "num(fig.value) < num(limit.amount)"],
    "direction": ("Pick the wording that matches what the person was checking: the figure going above the limit (A) or below it (B). Enough: the notes or "
                  "questions say over, above, more, too high, or under, below, less, too low. Cannot tell when they say neither.")}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dir(plane):
    d = plane.path("v3", "signals")
    d.mkdir(parents=True, exist_ok=True)
    return d


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:60]


def _read(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except (OSError, ValueError):
        return default


def _lines(p) -> list[dict]:
    try:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.is_file() else []
    except (OSError, ValueError):
        return []


def _append(p, row: dict) -> None:
    with LOCK, p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


# ---- watching ---------------------------------------------------------------------------------------------------------------------------

def kind_of_note(note: str) -> tuple[str, str] | None:
    """'checked bank details for Cedarpoint' -> ('bank_details', 'Cedarpoint'); None when the note is not a check."""
    m = re.match(r"\s*(?:i\s+)?(?:checked|verified|confirmed|held|called back)\s+(.+?)(?:\s+(?:for|on|with)\s+(.+?))?[.\s]*$", note or "", re.I)
    return (slug(m[1]), (m[2] or "").strip()) if m else None


def observe(plane, source: str, who: str, kind: str, subject: str, *, figure: str | None = None, file_kind: str | None = None, text: str = "", at: str | None = None) -> list[dict]:
    """Keep one thing a person did, then look for a pattern. Never raises (watching must not break the work). Returns the drafts it started."""
    try:
        if source not in SOURCES or not slug(kind):
            return []
        _append(_dir(plane) / "watch.jsonl", {"at": at or _now(), "source": source, "who": str(who or "").casefold(), "kind": slug(kind), "subject": str(subject or "").strip(),
                                              "figure": figure, "file_kind": file_kind, "text": str(text)[:300]})
        return scan(plane)
    except Exception:  # noqa: BLE001
        log.warning("watching failed", exc_info=True)
        return []


def arrival(plane, kind: str, file: str, doc: dict) -> None:
    """A document loaded: kept so a drafted condition can be run over what the office has already received."""
    try:
        _append(_dir(plane) / "arrivals.jsonl", {"at": _now(), "kind": kind, "file": file, "doc": json.loads(json.dumps(doc, default=str))})
    except Exception:  # noqa: BLE001
        log.warning("arrival not kept", exc_info=True)


# ---- drafting ---------------------------------------------------------------------------------------------------------------------------

def _drafts(plane) -> dict:
    return _read(_dir(plane) / "drafts.json", {})


def _save(plane, d: dict) -> None:
    write_json_atomic(_dir(plane) / "drafts.json", d)


def _role(plane, who: str) -> str | None:
    from sh_platform.v1 import v3_roles as R
    return R._jobs(plane).get(who)


def _rule_signed(plane, rule: str) -> bool:
    from sh_platform.v1 import v3_signals as SG
    try:
        return SG._fact(plane, {}, "rule", rule) is not None
    except Exception:  # noqa: BLE001
        return False


def _phrase(plane, options: list[str], obs: list[dict]) -> tuple[str, bool]:
    """(condition, sure). One fitting wording is the wording; two go to the two-model judge, and without agreement the first stands, flagged."""
    if len(options) == 1:
        return options[0], True
    from sh_platform.v1 import v3_judge as J
    said = [o["text"] or f"{o['source']}: {o['kind']} {o['subject']}" for o in obs][-5:]
    got = J.judged(plane, "condition", "Which wording of the check matches what these people did?", options, said, WATCH["direction"],
                   describe={options[0]: "the figure is above the limit", options[1]: "the figure is below the limit"}, person=False)
    return (got or options[0]), got is not None


def _build(plane, key: str, kind: str, role: str | None, obs: list[dict]) -> dict:
    known = KNOWN.get(kind)
    who = obs[-1]["who"]
    src = obs[-1]["source"]
    needs: list[str] = []
    if known:
        cond, sure = _phrase(plane, known["conditions"], obs)
        file_kind = next((o["file_kind"] for o in reversed(obs) if o.get("file_kind")), None) or known["after"]
        sig = {"id": f"draft-{kind}".replace("_", "-"), "title": known["title"], "trigger": {"on": "file_arrived", "kind": file_kind}, "inputs": known["inputs"],
               "condition": cond, "subject": known["subject"], "severity": "needs", "action": {"verb": known["verb"], **({"options": ["Record the check"]} if known["verb"] != "see" else {})},
               "message": known["message"]}
        if any(o["source"] == "hold" for o in obs):
            sig["hold"] = known["hold"]
    else:
        fig = next((o["figure"] for o in reversed(obs) if o.get("figure")), None)
        rule = f"{kind}_limit"
        cond, sure = _phrase(plane, WATCH["conditions"], obs)
        sig = {"id": f"draft-{kind}".replace("_", "-"), "title": f"{kind.replace('_', ' ').capitalize()} needs a look",
               "trigger": {"on": "figure_changed", "figure": fig} if fig else {"on": "schedule"},
               "inputs": [{"kind": "figure", "id": fig or kind, "as": "fig"}, {"kind": "rule", "id": rule, "as": "limit"}], "condition": cond,
               "subject": f"{kind.replace('_', ' ')}", "severity": "needs", "action": {"verb": VERB.get(src, "see")},
               "message": f"{kind.replace('_', ' ').capitalize()} is {{fig.value}}, past the limit of {{limit.amount}} the office signed."}
        if not _rule_signed(plane, rule):
            needs.append(f"I cannot tell what limit you use. {len(obs)} people checked {kind.replace('_', ' ')}, but no limit is signed. Sign one as the office rule {rule} (an amount) and I will use it.")
        if not sure:
            needs.append("I could not tell whether you watch for the figure going above or below the limit. Please check the wording.")
    sig["route_to"] = role or ""
    if not role:
        needs.append("I do not know which role should act on this. Please choose one.")
    names = sorted({o["who"] for o in obs if o["who"]})
    return {"id": key, "kind": kind, "signal": sig, "status": "waiting", "created": _now(), "needs": needs, "who": names, "repeats": len(obs),
            "sources": sorted({o["source"] for o in obs}), "subjects": [o["subject"] for o in obs if o["subject"]][-5:],
            "noticed": _noticed(kind, sig, names, obs), "evidence": [{"at": o["at"], "text": o["text"] or f"{o['source']}: {o['subject']}"} for o in obs[-5:]]}


def _noticed(kind: str, sig: dict, names: list[str], obs: list[dict]) -> str:
    first = (names[0].split("@")[0].replace(".", " ").title() if names else "Someone")
    what = kind.replace("_", " ")
    verb = {"question": "keeps asking about", "exception": "keeps dealing with", "hold": "keeps holding for", "dismissal": "keeps dismissing"}.get(obs[-1]["source"], "checks")
    when = " before every payment" if known_after(kind) else ""
    return f"Harbor noticed {first} {verb} {what}{when}. Watch for it automatically?"


def known_after(kind: str) -> bool:
    return kind == "bank_details"


def scan(plane) -> list[dict]:
    """Draft a signal for every kind of action seen twice that has no draft yet (waiting, admitted or rejected) and no signal of that id."""
    from sh_platform.v1 import v3_signals as SG
    groups: dict[tuple, list[dict]] = {}
    for o in _lines(_dir(plane) / "watch.jsonl"):
        groups.setdefault((o["kind"], _role(plane, o["who"])), []).append(o)
    made = []
    with LOCK:
        d = _drafts(plane)
        have = {s["id"] for s in SG.library(plane)}
        for (kind, role), obs in groups.items():
            key = "sd-" + hashlib.sha1(f"{kind}|{role}".encode()).hexdigest()[:10]
            if len(obs) < REPEATS or key in d or f"draft-{kind}".replace("_", "-") in have or any(s["id"] == kind for s in SG.library(plane)):
                continue
            d[key] = _build(plane, key, kind, role, obs)
            d[key]["backtest"] = backtest(plane, d[key])
            made.append(d[key])
        if made:
            _save(plane, d)
    return made


# ---- backtest ---------------------------------------------------------------------------------------------------------------------------

def backtest(plane, draft: dict) -> dict:
    """Run the drafted condition over the documents loaded in the last six months. {count, checked, examples, line}; count is None when it cannot be counted."""
    from sh_platform.v1 import v3_signals as SG
    sig = draft["signal"]
    if sig["trigger"]["on"] != "file_arrived":
        return {"count": None, "checked": 0, "examples": [], "line": "I cannot look back at this kind of event yet, so I cannot say how often it would have fired."}
    if draft.get("needs"):
        return {"count": None, "checked": 0, "examples": [], "line": "I cannot count this until " + ("the missing rule is signed." if any("limit" in n for n in draft["needs"]) else "the open questions are answered.")}
    since = datetime.now(timezone.utc) - timedelta(days=30 * MONTHS)
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": SG.last4, "num": SG.num, "same_fund": lambda a, b: SG.same_fund(plane, a, b, [])}
    checked, hits = 0, []
    for a in _lines(_dir(plane) / "arrivals.jsonl"):
        if a["kind"] != sig["trigger"].get("kind") or datetime.strptime(a["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < since:
            continue
        ev = {"trigger": "file_arrived", "kind": a["kind"], "file": a["file"], "doc": a["doc"], "facts": a.get("facts")}
        try:
            ns, _ = SG.resolve(plane, sig, ev, funcs, [])
            if SG.calc(sig["condition"], ns, funcs):
                hits.append(SG.render(sig.get("subject") or a["file"], ns))
            checked += 1
        except SG.Missing:
            continue
    n = len(hits)
    line = (f"Would have fired {n} time{'s' if n != 1 else ''} in {MONTHS} months" + (f": {', '.join(hits[:5])}" if hits else "")
            + f" ({checked} {sig['trigger'].get('kind', 'file').replace('_', ' ')}{'s' if checked != 1 else ''} checked).") if checked else \
        f"No {sig['trigger'].get('kind', 'file').replace('_', ' ')} in the last {MONTHS} months has the details to test it on."
    return {"count": n if checked else None, "checked": checked, "examples": hits[:5], "line": line}


# ---- the decision -----------------------------------------------------------------------------------------------------------------------

def listing(plane, status: str | None = None) -> list[dict]:
    scan(plane)
    with LOCK:
        d = _drafts(plane)
        for r in d.values():  # a limit signed since the draft was made no longer holds it back
            if r["status"] == "waiting" and any(n.startswith("I cannot tell what limit") for n in r["needs"]) and all(i.get("kind") != "rule" or _rule_signed(plane, i["id"]) for i in r["signal"]["inputs"]):
                r["needs"] = [n for n in r["needs"] if not n.startswith("I cannot tell what limit")]
                r["backtest"] = backtest(plane, r)
                _save(plane, d)
    rows = [r for r in _drafts(plane).values() if not status or r["status"] == status]
    return sorted(rows, key=lambda r: r["created"], reverse=True)


def _get(plane, did: str) -> dict:
    d = _drafts(plane)
    if did not in d:
        raise KeyError(did)
    return d


def edit(plane, did: str, fields: dict) -> dict:
    """The decision maker changes the title, the message, the role or the condition of a waiting draft. ValueError in plain words."""
    from sh_platform.v1 import v3_signals as SG
    with LOCK:
        d = _get(plane, did)
        row = d[did]
        if row["status"] != "waiting":
            raise ValueError("This one is already decided.")
        sig = {**row["signal"], **{k: v for k, v in fields.items() if k in ("title", "message", "route_to", "condition") and str(v).strip()}}
        if why := SG.check(sig, SG._roles(plane) or None):
            raise ValueError(f"That does not work yet: {why}.")
        row["signal"] = sig
        row["needs"] = [n for n in row["needs"] if not (n.startswith("I do not know which role") and sig["route_to"])]
        row["backtest"] = backtest(plane, row)
        _save(plane, d)
        return row


def admit(plane, did: str, by: str) -> dict:
    """The draft becomes an office signal (an office file overrides the pack's of the same id). ValueError while the draft still asks for something."""
    from sh_platform.v1 import v3_signals as SG
    with LOCK:
        d = _get(plane, did)
        row = d[did]
        if row["status"] != "waiting":
            raise ValueError("This one is already decided.")
        sig = row["signal"]
        if sig["inputs"] and any(i.get("kind") == "rule" and not _rule_signed(plane, i["id"]) for i in sig["inputs"]):
            raise ValueError("I still need the limit signed as an office rule before I can watch for this.")
        if not sig.get("route_to"):
            raise ValueError("Choose the role that acts on this first.")
        if why := SG.check(sig, SG._roles(plane) or None):
            raise ValueError(f"That does not work yet: {why}.")
        out = SG._dir(plane) / "office"
        out.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump({**sig, "suggestion": False, "from_draft": did}, sort_keys=False, allow_unicode=True)
        (out / f"{sig['id']}.yaml").write_text(text, encoding="utf-8")
        row.update(status="admitted", by=by, decided=_now(), needs=[])
        _save(plane, d)
        return row


def reject(plane, did: str, by: str, reason: str = "") -> dict:
    with LOCK:
        d = _get(plane, did)
        if d[did]["status"] != "waiting":
            raise ValueError("This one is already decided.")
        d[did].update(status="rejected", by=by, decided=_now(), reason=reason.strip())
        _save(plane, d)
        return d[did]


def cards(plane) -> list[dict]:
    """The waiting drafts, as the Desk's needs for the decision maker."""
    from sh_platform.v1 import v3_signals as SG
    who = SG._person(plane, DECIDER)
    return [{"kind": "signal_draft", "id": r["id"], "title": "Harbor noticed a pattern", "text": r["noticed"], "role": DECIDER, "person": who["email"],
             "draft": {"title": r["signal"]["title"], "message": r["signal"]["message"], "route_to": r["signal"]["route_to"], "condition": r["signal"]["condition"]},
             "needs": r["needs"], "backtest": r["backtest"]["line"], "actions": [{"label": "Admit", "answer": "admit"}, {"label": "Edit", "answer": "edit"}, {"label": "Reject", "answer": "reject"}]}
            for r in _drafts(plane).values() if r["status"] == "waiting"]
