"""Step 2 of the plan ("Roles and prior intersection"): Harbor's small judgement calls go to a cheap worker model, and a second model from a
DIFFERENT family checks the same question. Two that agree are trusted and recorded as an assumption; two that disagree become one Decision 2
question for a person, quoting both. Rules still go first: callers ask the judge only where they used to guess or ask one model.

    ask(plane, kind, question, options, evidence, standard) -> {answer, agreed, opinions: [{model, answer, why}], cost, ...}

- Worker = the fast tier, checker = the specialist tier (then the manager) of the office's current Testing / Real use mode, whichever is the
  first of a different family (qwen vs openai in Testing). No new vendor is configured here.
- Both run at temperature 0; the pair of replies is cached by the input, so the same question is never asked twice.
- Budget: SH_JUDGE_BUDGET_USD per build (the thread; one pool for the office outside a thread), default 0.25. Spent, the judge asks the person.
- No model, or no second family: `unavailable` and `agreed: False` and no question, so the caller does what it did before.
- A person's answer to a judge question is kept by the same key and wins from then on."""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone

log = logging.getLogger(__name__)
LOCK = threading.RLock()
THREAD: contextvars.ContextVar = contextvars.ContextVar("judge_thread", default=None)  # set by the chain runner: which build is asking
SOURCE = "Harbor (two models agreed)"
CLIENTS = None  # tests set a function (plane) -> (worker, checker)
ELSE = "Something else, I will say"
DEFAULT_BUDGET = 0.25
SKILLS = {"file": "data.recognise-file", "amount_line": "data.read-pdf-fields", "fund_match": "data.match-identity", "trade_side": "run.load-file",
          "recipe": "intent.define-figure"}
SYSTEM = ("You make one small judgement for a finance operations tool. Answer with exactly one of the options, copied word for word, or with "
          '"none" when the evidence does not settle it. Evidence standard (what counts as enough): {standard} Do not say "none" because the '
          "evidence is imperfect; say it only when two options remain equally likely. Reply with JSON only: "
          '{{"answer": <one option or "none">, "why": <one plain sentence>}}.')


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dir(plane):
    d = plane.path("v3", "judge")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, data) -> None:
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def key_of(kind, question, options, evidence, standard) -> str:
    return hashlib.sha256(json.dumps([kind, question, list(options), evidence, standard], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


# ---- the two models --------------------------------------------------------------------------------------------------------------------

def family(model: str) -> str:
    m = (model or "").lower()
    if "/" in m:
        return m.split("/")[0]
    return "google" if m.startswith("gemini") else "openai" if m.startswith(("gpt", "o1", "o3")) else "anthropic" if m.startswith("claude") else m


def _clients(plane):
    """(worker, checker): model clients of two different families, or None when the model is off or only one family is set up."""
    from sh_platform.egress.providers import build_model_client
    from sh_platform.settings import load_model_env
    from sh_platform.v1 import router
    env, mode = load_model_env(), router.mode_of(plane)["mode"]
    if (env.get("SH_MODEL_PROVIDER") or "").strip().lower() == "off" or "PYTEST_CURRENT_TEST" in os.environ:  # a test never reaches a live model
        return None
    got = []
    for tier, alt in (("fast", False), ("specialist", False), ("manager", False), ("fast", True), ("specialist", True)):  # Real use: the _ALT models are the other family
        e = router.mode_env(env, mode, tier, alt)
        c = build_model_client(plane, e, tier) if e is not None else None
        if c is not None and (not got or family(c.model_id) != family(got[0].model_id)):
            got.append(c)
        if len(got) == 2:
            return tuple(got)
    return None


def _price(model, usage) -> float:
    from sh_platform.v1.router import price_usd
    return price_usd(model, (usage or {}).get("tokens_in"), (usage or {}).get("tokens_out"), "fast") or 0.0


def _opinion(client, system, user, options) -> dict:
    """One model's reply at temperature 0: {model, answer (an option or None), why, cost}. A reply that is not one of the options is no answer."""
    from sh_platform.egress.providers import TEMPERATURE
    token = TEMPERATURE.set(0)
    try:
        r = client.complete("m3_connect", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        a, b = r.text.find("{"), r.text.rfind("}")
        d = json.loads(r.text[a:b + 1]) if 0 <= a < b else {}
        said = " ".join(str(d.get("answer") or "").split()).lower()
        pick = next((o for o in options if " ".join(str(o).split()).lower() == said), None)
        return {"model": client.model_id, "answer": pick, "why": str(d.get("why") or "")[:300], "cost": _price(client.model_id, r.usage)}
    except Exception:  # noqa: BLE001 - a failed call is no opinion; the two cannot agree
        log.warning("a judge model call failed", exc_info=True)
        return {"model": getattr(client, "model_id", "?"), "answer": None, "why": "The model could not be reached.", "cost": 0.0}
    finally:
        TEMPERATURE.reset(token)


# ---- budget, log, questions ----------------------------------------------------------------------------------------------------------------

def budget() -> float:
    try:
        return float(os.environ.get("SH_JUDGE_BUDGET_USD") or DEFAULT_BUDGET)
    except ValueError:
        return DEFAULT_BUDGET


def spent(plane, build) -> float:
    return round(sum(r.get("cost") or 0 for r in _read(_dir(plane) / "log.json", []) if r.get("thread") == build), 6)


def _log(plane, row: dict) -> None:
    with LOCK:
        p = _dir(plane) / "log.json"
        _write(p, _read(p, []) + [row])


def _pending_add(plane, key, row) -> None:
    with LOCK:
        p = _dir(plane) / "pending.json"
        d = _read(p, {})
        d[key] = row
        _write(p, d)


def _text(o: dict) -> str:
    return f"{o['answer'] or 'no answer'}: {o['why']}".strip(": ")


def pending(plane, thread=None) -> list[dict]:
    """Decision 2's questions from the judge: those of this build (and those asked outside any build)."""
    return [{"id": f"judge:{k}", "text": r["text"], "options": r["options"], "assumed": None}
            for k, r in _read(_dir(plane) / "pending.json", {}).items() if r.get("thread") in (None, thread)]


def answer(plane, key: str, value: str) -> None:
    """The person's pick (an option's text, or their own words after "Something else"). Kept by the question's key; ask() returns it from now on."""
    with LOCK:
        pend = _read(_dir(plane) / "pending.json", {})
        row = pend.pop(key, None)
        if row is None or not str(value or "").strip() or str(value).startswith(ELSE):
            return
        mapped = (row.get("picks") or {}).get(value, str(value).strip())
        a = _read(_dir(plane) / "answers.json", {})
        a[key] = mapped
        _write(_dir(plane) / "answers.json", a)
        _write(_dir(plane) / "pending.json", pend)


def assumptions(plane, thread) -> list[dict]:
    """The agreed judgements of one build, as figure assumptions ("What I assumed")."""
    return [{"text": r["text"], "source": SOURCE, "at": r["at"]} for r in _read(_dir(plane) / "log.json", []) if r.get("agreed") and r.get("thread") == thread]


# ---- the judge -----------------------------------------------------------------------------------------------------------------------

def ask(plane, kind: str, question: str, options: list, evidence, standard: str, thread=None, person: bool = True) -> dict:
    """See the module note. `answer` is one of `options` when `agreed`, else None. `agreed` is also True for a person's earlier answer (`by: person`)."""
    options, thread = [str(o) for o in options], thread if thread is not None else THREAD.get()
    key = key_of(kind, question, options, evidence, standard)
    out = {"answer": None, "agreed": False, "opinions": [], "cost": 0.0, "key": key, "kind": kind}
    if (a := _read(_dir(plane) / "answers.json", {}).get(key)) is not None:
        return {**out, "answer": a, "agreed": True, "by": "person"}
    if cached := _read(_dir(plane) / "cache" / f"{key}.json", None):
        return {**out, **cached, "cost": 0.0, "cached": True}
    try:
        pair = CLIENTS(plane) if CLIENTS else _clients(plane)
    except Exception:  # noqa: BLE001 - a wrong model setting is no model
        log.warning("the judge's models could not be set up", exc_info=True)
        pair = None
    if pair is None:
        return {**out, "unavailable": "no second model of a different family"}
    ask_row = {"thread": thread, "kind": kind, "key": key, "at": _now()}

    def to_person(why, ops, picks):
        if person:  # a caller that already asks the person itself (the PDF layout question) passes person=False
            _pending_add(plane, key, {"thread": thread, "picks": picks, "options": [*picks, ELSE], "text": f"{question} {why}"})
        return {**out, "opinions": ops, "why": why}

    with LOCK:
        if spent(plane, thread) >= budget():  # the hard stop: the person is asked, Harbor never guesses
            _log(plane, {**ask_row, "agreed": False, "stopped": "budget", "cost": 0})
            return {**to_person("Harbor's budget for judgement calls on this build is used up, so I am asking you.", [], {o: o for o in options}), "stopped": "budget"}
    system, user = SYSTEM.format(standard=standard), json.dumps({"kind": kind, "question": question, "options": options, "evidence": evidence}, default=str)
    ops = [_opinion(c, system, user, options) for c in pair]
    cost = round(sum(o.pop("cost") for o in ops), 6)
    a, b = ops
    (_dir(plane) / "cache").mkdir(exist_ok=True)
    if a["answer"] and a["answer"] == b["answer"]:
        text = f"{question} Harbor took: {a['answer']}. {a['model']}: {a['why']} {b['model']}: {b['why']}".strip()
        res = {"answer": a["answer"], "agreed": True, "opinions": ops, "cost": cost}
        _log(plane, {**ask_row, "agreed": True, "answer": a["answer"], "text": text, "cost": cost})
        _write(_dir(plane) / "cache" / f"{key}.json", res)
        return {**out, **res}
    _log(plane, {**ask_row, "agreed": False, "cost": cost})
    picks = {f"{_text(o)} ({o['model']})": o["answer"] for o in ops if o["answer"]} or {o: o for o in options}
    _write(_dir(plane) / "cache" / f"{key}.json", {"agreed": False, "opinions": ops, "cost": cost})  # a disagreement is kept too: no second call
    return {**to_person("Two models I asked did not agree.", ops, picks), "cost": cost}


def judged(plane, kind: str, question: str, options: list, evidence, standard: str, thread=None, person: bool = True) -> str | None:
    """The agreed answer (one of the options) or None, recorded under the judgement's skill. What the hooks call."""
    from sh_platform.v1 import v3_skills as S
    th = thread if thread is not None else THREAD.get()
    with S.record(plane, th, SKILLS.get(kind, "harbor.route")) as rec:
        r = ask(plane, kind, question, options, evidence, standard, th, person)
        rec["detail"] = (f"{kind}: {r['answer']} ({'person' if r.get('by') else 'two models agreed'})" if r["agreed"]
                         else f"{kind}: {r.get('stopped') or r.get('unavailable') or 'the models disagreed; a person is asked'}")
    return r["answer"] if r["agreed"] and r["answer"] in [str(o) for o in options] else None  # a person's own words are not one of the options
