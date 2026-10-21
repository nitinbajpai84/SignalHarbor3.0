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
          "recipe": "intent.define-figure", "mapping_row": "model.design-ready-table"}
VERSION = 2  # the wording of the questions; a new wording is a new question (no stale cached reply)
CANNOT = "cannot tell"
SYSTEM = ("You make one small judgement for a family office's operations tool. Read the question, the options and the evidence. Apply the evidence "
          "standard below: it says what is enough to pick an option. Pick exactly one option by its letter. Answer \"cannot tell\" only when, under "
          "the standard, the evidence fits two options equally; evidence that is short or imperfect but points one way is enough.\n"
          "Evidence standard: {standard}\n{examples}"
          'Reply with JSON only: {{"answer": "<the letter of one option>" or "cannot tell", "why": "<one plain sentence naming the evidence you used>"}}.')

# Each judgement kind: the question as Harbor asks it, what counts as enough evidence, and worked examples (none taken from the held-out cases in
# tests/v1/fixtures/judge_heldout.json, which measure this wording). Callers take the question and the standard from here (question(), standard()).
GUIDES = {
    "file": {
        "question": "Which of the build's sources did the file {name} come from?",
        "standard": ("Compare the file's column headings and first rows, then its name, with what each source holds. Enough to pick a source: the headings "
                     "or the name point to that source's kind of records (trades, bank balances, positions, notices, rates) and not to another option's. "
                     "A source named after a system that the file's name or columns mention counts. Cannot tell: two options would hold exactly these columns."),
        "examples": [("file custody_holdings_0930.csv with columns account, isin, quantity, market_value; options: A Bank balances, B Custodian positions",
                      "B", "the columns are holdings with quantities and market values, not account balances"),
                     ("file calls_2026.xlsx whose lines cannot be read; options: A Fund call notices, B Price feed", "A", "the name says capital calls"),
                     ("file export.csv with columns date, amount; options: A Bank cash file, B Administrator cash file", "cannot tell",
                      "both hold dated amounts and nothing names either")]},
    "amount_line": {
        "question": "In {name}, which line holds the one amount this document exists to report, the amount to load?",
        "standard": ("On a statement, the amount to load is the closing balance or value of the holding at the period end (closing capital account balance, "
                     "net asset value of the holding, partner capital balance), also when the statement shows what was previously reported and the "
                     "change. On an FX forward confirmation it is the first leg, the amount the client sells: the trade's notional as the desk records it "
                     "(the bought amount is that notional times the rate). Never a previously reported value, a change, a movement, a fee, an opening "
                     "balance or a rate. Enough: the line's label says it is that amount."),
        "examples": [("statement lines: A Opening balance: EUR 4,000,000.00, B Closing balance: EUR 4,120,000.00", "B", "the closing balance is the period-end value"),
                     ("amended statement lines: A Partner capital: USD 5,050,000.00, B Previously reported: USD 5,000,000.00, C Change: USD +50,000.00", "A",
                      "the amended closing value, not the earlier value or the change"),
                     ("FX confirmation lines: A Client sells (EUR): EUR 1,000,000.00, B Client buys (USD): USD 1,085,000.00", "A",
                      "the sold leg is the notional the desk records")]},
    "fund_match": {
        "question": "Is the fund named '{page}' on the page the same fund as '{on_file}' on file?",
        "standard": ("Same fund: after ignoring case, punctuation and legal or generic words (L.P., LP, Ltd, Inc, SICAV, Fund, Partners), every remaining "
                     "word of the two names agrees, allowing a plain abbreviation. Different fund: any remaining word differs or is missing on one side: a "
                     "series or vintage number (II and III), a strategy (Macro and Long/Short), a currency, a share class or a different sponsor."),
        "examples": [("'Bluewater Income Fund II, L.P.' against 'Bluewater Income II'", "same fund", "only 'Fund' and 'L.P.' differ"),
                     ("'Northgate Growth II' against 'Northgate Growth III'", "different fund", "the series number differs"),
                     ("'Harbor Credit Opportunities' against 'Harbor Credit Income'", "different fund", "the strategy word differs")]},
    "trade_side": {
        "question": "Does the trade side word {side!r} mean a buy or a sell of the instrument?",
        "standard": ("Buy when the word means acquiring or paying for the holding (bot, bought, purchase, long, subscribe, receive); sell when it means "
                     "disposing of it (sld, sold, sale, short, redeem, deliver). Cannot tell when the word names both directions (a currency pair "
                     "such as 'buy EUR / sell USD') or neither (a dividend, a fee, a transfer)."),
        "examples": [("'BOT'", "buy", "BOT is the usual short form of bought"), ("'Redemption'", "sell", "a redemption disposes of fund units"),
                     ("'buy EUR / sell USD'", "cannot tell", "a currency exchange buys one currency and sells the other")]},
    "recipe": {
        "question": "Which recipe computes the figure '{figure}', defined as: {definition} (formula: {formula})?",
        "standard": ("Judge this one figure by its definition and formula, not by the brief's wider question, which is background only. Pick a recipe "
                     "when the figure is the very quantity the recipe computes, from the records the recipe reads: the quantity itself, its total over all "
                     "items, the same quantity split by entity, fund or date, or kept to a subset all count. Pick the option that no recipe computes it "
                     "when the figure is another quantity: a count of items, a percentage, a ratio or share of a recipe's result, a date or a duration, or "
                     "something measured from records no recipe reads. A shared word in the names is not enough."),
        "examples": [("'Total cash difference', the sum of the per-entity cash breaks; options include A Cash break", "A", "a total of the break the recipe computes"),
                     ("'Late statements', the number of statements that arrived after their due date", "the no-recipe option", "a count of items is another quantity"),
                     ("'Cash share', cash divided by net worth", "the no-recipe option", "a ratio of two results is another quantity"),
                     ("'Restated value change', amended value less original value per fund; options include C Change since the issued report", "C",
                      "the same supersession difference, split by fund")]},
    "mapping_row": {
        "question": "Does the proposed definition say clearly what the column {column} of the ready table {table} holds?",
        "standard": ("Yes when the definition names what the column holds and agrees with how the select produces it: a column the select passes through "
                     "unchanged from a table it reads is clear when the definition names that table and column; a computed column is clear when the "
                     "definition says the calculation the select does. No when the definition only repeats the column's name for a computed column, "
                     "contradicts the select, or the select fills the column with a fixed number or NULL that no record supports."),
        "examples": [("column amount of a cash table whose select passes m.amount from cash_movements; definition: the amount of the cash_movements row it "
                      "comes from (cash_movements.amount), unchanged", "yes", "the select passes the column through and the definition names its source"),
                     ("column drift whose select says 100 as drift; definition: the drift the figure is for", "no", "a fixed number is not read from any record"),
                     ("column net_worth whose select sums p.market_value by portfolio and date; definition: the net worth the figure is for", "no",
                      "a computed column needs its calculation, not its name again")]},
}


def question(kind: str, **subject) -> str:
    """The question of a judgement kind, filled with its subject (the file's name, the two fund names ...)."""
    return GUIDES[kind]["question"].format(**subject)


def standard(kind: str) -> str:
    return GUIDES[kind]["standard"]


def _examples(kind: str) -> str:
    ex = (GUIDES.get(kind) or {}).get("examples") or []
    return "".join(["Worked examples:\n", *(f"- {c} -> {a}: {w}\n" for c, a, w in ex)]) if ex else ""


def _letters(options: list[str], describe: dict | None) -> dict[str, str]:
    """The options as the models see them: a letter each, in plain words (the caller's description, else the option itself)."""
    return {chr(65 + i): str((describe or {}).get(o) or o) for i, o in enumerate(options)}


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
    return hashlib.sha256(json.dumps([VERSION, kind, question, list(options), evidence, standard], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


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


def _opinion(client, system, user, options, letters: dict | None = None) -> dict:
    """One model's reply at temperature 0: {model, answer (an option or None), why, cost}. The reply names an option by its letter, its own text or
    its plain words; anything else ("cannot tell" too) is no answer."""
    from sh_platform.egress.providers import TEMPERATURE
    token = TEMPERATURE.set(0)
    try:
        r = client.complete("m3_connect", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        a, b = r.text.find("{"), r.text.rfind("}")
        d = json.loads(r.text[a:b + 1]) if 0 <= a < b else {}
        said = " ".join(str(d.get("answer") or "").split()).lower().strip(" .)")
        by = {k.lower(): o for k, o in zip(letters or {}, options)}
        by.update({" ".join(str(w).split()).lower(): o for w, o in zip((letters or {}).values(), options)})
        pick = by.get(said) or next((o for o in options if " ".join(str(o).split()).lower() == said), None)
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

def ask(plane, kind: str, question: str, options: list, evidence, standard: str, thread=None, person: bool = True, describe: dict | None = None) -> dict:
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
    letters = _letters(options, describe)  # both models get the very same system text and user text: the same evidence, the same options
    system = SYSTEM.format(standard=standard, examples=_examples(kind))
    user = json.dumps({"question": question, "options": letters, "evidence": evidence}, default=str, ensure_ascii=False)
    ops = [_opinion(c, system, user, options, letters) for c in pair]
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


def judged(plane, kind: str, question: str, options: list, evidence, standard: str, thread=None, person: bool = True, describe: dict | None = None) -> str | None:
    """The agreed answer (one of the options) or None, recorded under the judgement's skill. What the hooks call."""
    from sh_platform.v1 import v3_skills as S
    th = thread if thread is not None else THREAD.get()
    with S.record(plane, th, SKILLS.get(kind, "harbor.route")) as rec:
        r = ask(plane, kind, question, options, evidence, standard, th, person, describe)
        rec["detail"] = (f"{kind}: {r['answer']} ({'person' if r.get('by') else 'two models agreed'})" if r["agreed"]
                         else f"{kind}: {r.get('stopped') or r.get('unavailable') or 'the models disagreed; a person is asked'}")
    return r["answer"] if r["agreed"] and r["answer"] in [str(o) for o in options] else None  # a person's own words are not one of the options


def ask_kind(plane, kind: str, subject: dict, options: list, evidence, thread=None, person: bool = True, describe: dict | None = None) -> dict:
    """ask() with the kind's own question and standard (GUIDES): what tools/judge_eval.py measures, the same text the call sites send."""
    return ask(plane, kind, question(kind, **subject), options, evidence, standard(kind), thread, person, describe)


def field_agreement(plane, items: list[dict], thread=None) -> dict:
    """Agreement per field, not per document: {label: True when both models take the reading as right, False when they say wrong or disagree,
    None when no second model is available}. items: [{label, value, quote}]. What v3_loads.pdf_figures(agree=) and v3_review.score take."""
    out = {}
    for it in items:
        r = ask(plane, "field_read", f"The page says: {it['quote']!r}. Is {it['value']!r} the value of {it['label']!r}?", ["right", "wrong"],
                {"label": it["label"], "value": it["value"], "quote": it["quote"]}, "Answer right only when the quoted lines show this value for this label.",
                thread, person=False)
        out[it["label"]] = None if r.get("unavailable") else bool(r["agreed"] and r["answer"] == "right")
    return out
