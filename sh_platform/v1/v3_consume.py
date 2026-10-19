"""Consume reading room for Harbor 3.0 (spec: docs/v3/HARBOR-SPEC.md, 15 Oct, Consume).

The ask cache: an answer is kept for one viewer, one normalised question and one data version (the latest live run id across the threads).
A new live run changes the version, so every older answer stops being served. `precompute` answers the most-asked and the golden questions for
the current version ahead of time. The 2.0 read_cache cannot hold these: it is dropped after every non-GET request, and an ask is a POST.
ponytail: in memory, one process; a restart answers the first ask live again.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_process

log = logging.getLogger(__name__)
LOCK = threading.Lock()
KEPT: dict[tuple, dict] = {}
PRE: dict[str, str] = {}  # company -> data version already pre-computed (or being)
MAX = 500
STALE_DAYS = 2
NUMBER = re.compile(r"[$]?\d[\d,]*(?:\.\d+)?(?:\s?(?:bn|m|k|%))?", re.I)


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9%.$ ]+", " ", str(text).lower()).split())


def version(plane) -> tuple[str, str] | None:
    """(run id, when) of the latest step with a run among the live threads."""
    runs = [(s.get("at") or "", s["run_id"]) for t in H.all_threads(plane) if t.get("stage") == "live" for s in t.get("steps") or [] if s.get("run_id")]
    at, rid = max(runs, default=(None, None))
    return (rid, at) if rid else None


def _who(viewer) -> str:
    return str(getattr(viewer, "account_id", None) or getattr(viewer, "name", viewer))


def _log_path(plane):
    return plane.path("v3", "ask_log.json")


def _count(plane, text: str) -> None:
    p, k = _log_path(plane), norm(text)
    with LOCK:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d[k] = {"q": d.get(k, {}).get("q") or text, "n": d.get(k, {}).get("n", 0) + 1}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d), encoding="utf-8")


def top(plane, n: int = 8) -> list[str]:
    try:
        d = json.loads(_log_path(plane).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [v["q"] for v in sorted(d.values(), key=lambda v: -v["n"])[:n]]


GOLDEN = ["What is our cash by entity today?", "Which entity has the least cash?", "What calls are due in the next 30 days?", "Can each entity meet its calls?"]


def golden(plane) -> list[str]:
    from sh_platform.v1 import v3_model
    return list(dict.fromkeys(GOLDEN + [g["q"] for g in v3_model.language(plane)["golden"] if g.get("q")] + v3_process.golden(plane)))


def figure_of(answer: str, question: str) -> dict | None:
    m = next((m.group(0).strip() for m in NUMBER.finditer(answer) if len(m.group(0).strip()) >= 3), None)
    return {"label": " ".join(question.split())[:60], "value": m, "change": ""} if m else None


BARE = re.compile(r"^([a-z][a-z _]*?)\s+(-?[$]?\d[\d,]*(?:\.\d+)?%?)$")  # "commitment 10,000,000": a column word, then its number
CCY_CODE = re.compile(r"^[A-Z]{3}$")


def named(fig: dict | None) -> dict | None:
    """A headline that is a column word and a number ("commitment 10,000,000") is said plainly: "Commitment for Cedarpoint Ventures III: 10,000,000",
    the subject being the most specific thing the label names (its last part that is not the figure itself or a currency). Every answer passes here."""
    if not fig or not (hit := BARE.match(str(fig.get("value") or "").strip())):
        return fig
    word, number = hit.group(1).replace("_", " ").strip(), hit.group(2)
    parts = [p.strip() for p in str(fig.get("label") or "").split("·")][1:]
    subject = next((p for p in reversed(parts) if p and not CCY_CODE.match(p) and not p.lower().startswith("total")), "")
    return fig | {"value": f"{word[:1].upper()}{word[1:]}{f' for {subject}' if subject else ''}: {number}"}


def _key(plane, viewer, text: str, ver) -> tuple:
    return (str(plane.path("v3")), _who(viewer), norm(text), ver[0] if ver else "")


def answer(plane, viewer, text: str, compute, count: bool = True) -> dict:
    """The kept answer, instantly, or `compute()` (today's path) stored with its trace. Adds cached, ms, as_of."""
    t0, ver = time.perf_counter(), version(plane)
    k = _key(plane, viewer, text, ver)
    if count:
        _count(plane, text)
    with LOCK:
        hit = KEPT.get(k)
    as_of = ver[1] if ver else None
    if hit:
        return hit | {"cached": True, "ms": int((time.perf_counter() - t0) * 1000), "as_of": as_of}
    got = compute()
    got = got | ({"figure": f} if "figure" not in got and (f := figure_of(got["answer"], text)) else {})
    got = got | ({"figure": named(got["figure"])} if got.get("figure") else {})
    with LOCK:
        if len(KEPT) >= MAX:
            KEPT.clear()
        KEPT[k] = got
    return got | {"cached": False, "ms": int((time.perf_counter() - t0) * 1000), "as_of": as_of}


def precompute(plane, viewer, compute_for, n: int = 8) -> int:
    """Answer the top-N asked and the golden questions for this data version. `compute_for(text)` returns the compute() for one question.
    The skills agent calls this after a live run; GET /consume calls it lazily. Returns how many were worked out."""
    ver, done = version(plane), 0
    if not ver:
        return 0
    PRE[str(plane.path("v3"))] = ver[0]
    for q in dict.fromkeys(top(plane, n) + golden(plane)):
        with LOCK:
            if _key(plane, viewer, q, ver) in KEPT:
                continue
        try:
            answer(plane, viewer, q, compute_for(q), count=False)
            done += 1
        except Exception:  # noqa: BLE001 - one question failing never stops the rest; it is asked live when someone asks
            log.info("pre-compute of %r failed", q, exc_info=True)
    return done


def due(plane) -> bool:
    ver = version(plane)
    return bool(ver) and PRE.get(str(plane.path("v3"))) != ver[0]


# ---- the liquidity answer skill (a tool, ahead of Lumen) ----------------------------------------------------------------------------

SKILL = "consume.answer-question"
CASH = re.compile(r"\b(cash|liquidity)\b", re.I)  # not "liquid": the Evergreen Liquid portfolio is not a cash question
CALLS = re.compile(r"\bcalls?\b|capital call|drawdown", re.I)
OTHER = re.compile(r"\b(nav|net worth|uncalled|exposure|price|breaks?|differences?|mismatch|reconcil\w*|worth|portfolio)\b", re.I)  # mentions cash but is about something else


def latest_day(plane) -> date:
    """Latest bank or administrator value date in the warehouse (cash positions); today when there is none."""
    from sh_platform.v1 import wh
    try:
        with wh.connect(plane, read_only=True) as con:
            d = con.execute("select max(position_date) from position_snapshots where instrument_id in (select id from instruments where instrument_type = 'cash')").fetchone()[0]
        if d:
            return d if isinstance(d, date) and not isinstance(d, datetime) else date.fromisoformat(str(d)[:10])
    except Exception:  # noqa: BLE001 - no warehouse yet
        log.info("latest value date unavailable", exc_info=True)
    return date.today()


def liquidity(plane, viewer, day: date) -> list[dict]:
    """Per entity {code, name, cash, c30, c60 (due within 60 days), n_unconfirmed, dated} from the 2.0 liquidity forecast, read in-process as the viewer."""
    from sh_platform.v1 import k6_liquidity
    out = []
    for e in k6_liquidity.forecast(plane, day, viewer=viewer, currency="USD")["entities"]:
        b = {x["key"]: x for x in e["buckets"]}
        c30, c31 = Decimal(b.get("30", {}).get("calls") or 0), Decimal(b.get("60", {}).get("calls") or 0)
        dates = [str(s["position_date"]) for s in e.get("cash_sources") or []]
        out.append({"code": e["entity_code"], "name": e["entity_name"], "cash": Decimal(e["available_cash"]), "c30": c30, "c60": c30 + c31,
                    "n_unconfirmed": len(e.get("unconfirmed") or []), "dated": max(dates, default=None)})
    return out


def m(x) -> str:
    return f"{Decimal(x):,.2f}"


def _fast(plane, viewer, text: str) -> dict | None:
    q = text.lower()
    cash, calls = bool(CASH.search(q)), bool(CALLS.search(q))
    if not (cash or calls) or OTHER.search(q):
        return None
    day = latest_day(plane)
    ents = liquidity(plane, viewer, day)
    if not ents or not any(e["cash"] for e in ents):  # no cash loaded yet: say nothing here; a missing figure is never shown as zero
        return None
    ver = version(plane)
    asat = f"{day:%d %b %Y}".lstrip("0")
    named = [e for e in ents if e["name"].lower() in q or e["code"].lower() in q]
    scope = named or ents
    total = sum((e["cash"] for e in scope), Decimal(0))
    horizon = "60" if re.search(r"\b60\b|sixty|two months", q) else "30"
    key = "c60" if horizon == "60" else "c30"
    base = {"source": f"Bank statements and administrator, as at {asat}" + (f" · run {ver[0]}" if ver else ""), "used": [],
            "trace": [{"kind": "tool", "label": "Read the liquidity forecast"}, {"kind": "guard", "label": "Every figure comes from the signed numbers"}]}

    def fig(label, value):
        return {"label": label, "value": value, "change": ""}

    if calls and re.search(r"\b(meet|cover|afford|enough)\b", q):
        rows = [{"label": e["name"], "value": f"Cash {m(e['cash'])}, calls in 60 days {m(e['c60'])}: " + ("covered" if e["cash"] >= e["c60"] else f"short by {m(e['c60'] - e['cash'])}")} for e in scope]
        short = [e["name"] for e in scope if e["cash"] < e["c60"]]
        ans = (f"Yes: each entity's cash covers the calls due in the next 60 days (as at {asat})." if not short
               else f"Not every entity: {', '.join(short)} would be short if the calls due in 60 days are paid (as at {asat}).")
        return base | {"answer": ans, "figure": fig("Cash after calls due in 60 days · USD", m(sum((e["cash"] - e["c60"] for e in scope), Decimal(0)))), "rows": rows}
    if calls:
        tot, unc = sum((e[key] for e in scope), Decimal(0)), sum(e["n_unconfirmed"] for e in scope)
        ans = f"Capital calls due in the next {horizon} days total {m(tot)} USD (as at {asat})." if tot else f"No capital calls are due in the next {horizon} days (as at {asat})."
        return base | {"answer": ans + (f" {unc} call{'s are' if unc != 1 else ' is'} not confirmed yet." if unc else ""),
                       "figure": fig(f"Calls due in {horizon} days · USD", m(tot) if tot else "None"),
                       "rows": [{"label": e["name"], "value": m(e[key]) if e[key] else "None"} for e in scope]}
    for word, pick, sign in ((r"\b(least|lowest|smallest)\b", min, 1), (r"\b(most|highest|largest|biggest)\b", max, -1)):
        if re.search(word, q) and len(ents) > 1:
            e = pick(ents, key=lambda x: x["cash"])
            return base | {"answer": f"{e['name']} has the {'least' if sign > 0 else 'most'} cash: {m(e['cash'])} USD (as at {asat}).",
                           "figure": fig(f"{'Least' if sign > 0 else 'Most'} cash · {e['name']} · USD", m(e["cash"])),
                           "rows": [{"label": x["name"], "value": m(x["cash"])} for x in sorted(ents, key=lambda x: sign * x["cash"])]}
    ans = (f"{scope[0]['name']} holds {m(total)} USD in cash (as at {asat})." if len(scope) == 1
           else "Cash by entity: " + "; ".join(f"{e['name']} {m(e['cash'])}" for e in scope) + f". Total {m(total)} USD (as at {asat}).")
    return base | {"answer": ans, "figure": fig(f"Cash · {scope[0]['name'] if len(scope) == 1 else 'all entities'} · USD", m(total)),
                   "rows": [{"label": e["name"], "value": m(e["cash"])} for e in scope]}


def liquidity_answer(plane, viewer, text: str, pid=None) -> dict | None:
    """The deterministic answer to a cash, calls-due or can-we-meet-our-calls question, or None (Lumen answers). Logged as a skill run."""
    from sh_platform.v1 import v3_skills
    hit: dict | None = None
    try:
        with v3_skills.record(plane, pid, SKILL) as rec:
            hit = _fast(plane, viewer, text)
            rec["detail"] = (hit or {}).get("figure", {}).get("label", "not a liquidity question")
    except Exception:  # noqa: BLE001 - any failure falls back to Lumen
        log.info("liquidity answer failed", exc_info=True)
        return None
    return hit


def verified_answer(plane, viewer, text: str, pid=None, th: dict | None = None) -> dict | None:
    """The office's verified figures first (the ready tables of the live thread's figures, through their figure records), then the liquidity tool.
    A "no calls due" from the tool never stands over a calls figure the thread holds (w6: the tool counted a pack notice as no call)."""
    from sh_platform.v1 import v3_figures as F
    got = F.figure_answer(plane, viewer, text, (th or {}).get("pid") or pid, th)
    if got and not str(got.get("answer") or "").startswith("Not available yet"):
        return got
    liq = liquidity_answer(plane, viewer, text, (th or {}).get("id"))
    if liq and not (got and CALLS.search(text) and (liq.get("figure") or {}).get("value") == "None"):
        return liq
    return got


# ---- the answer as a person reads it (r7 review: docs/v3/LIVE-R7-ANSWERS.md) ----------------------------------------------------------
# The last pass over every answer's text, whoever worded it: plain words, the polarity the question asks for, and a verdict first on a yes/no question.
# It only rewords and adds a currency or a verdict the text itself supports; it never drops or changes a figure.

CCY = r"(?:USD|SGD|EUR|GBP|HKD|CHF|JPY|AUD|CNY)"
SNAKE = re.compile(r"(?<![\w\\/-])[a-z]+(?:_[a-z]+)+(?!\w|[\\/-]|\.[a-z]{2,4}\b)")  # listed_equity, a table.column; never a file name
AMOUNT = re.compile(r"(?<![\w.,/-])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d%x]|\.\d|,\d)")
NOT_MONEY = re.compile(r"^\s*(?:units?|shares|days?|business days|months?|minutes|lots?|payments?|rows|times|people|guests)\b", re.I)
QUANTITY = re.compile(r"\b(?:units?|shares|quantity|(?:buy|sell|bought|sold) of|holds? \d)", re.I)
UNKNOWN_CCY = re.compile(rf"(?<=· ){CCY} [01](?=\s*(?:[;.]|$))")  # a flag read as an amount ("· USD 0;"): the value is not stated


def _money_units(text: str, hint: str | None) -> str:
    """Every amount carries its currency: the nearest currency named before it in its clause, else after it; else, for the whole answer, the one
    currency it names (or the rows' one currency, `hint`). A clause about units or shares is left alone, so is a score or a count."""
    named = {c for p in re.findall(rf"\b({CCY})\s?-?\d|\d\s({CCY})\b", text) for c in p if c}  # a unit of an amount, not "SGD exposure"
    whole = next(iter(named)) if len(named) == 1 else (hint if not named else None)
    if QUANTITY.search(text):
        whole = None
    out = []
    for clause in re.split(r"(;\s|\.\s)", text):
        if QUANTITY.search(clause):
            out.append(clause)
            continue
        cur = [(m.start(), m.group(0)) for m in re.finditer(rf"\b{CCY}\b", clause)]
        pieces, last = [], 0
        for m in AMOUNT.finditer(clause):
            before, after = clause[:m.start()], clause[m.end():]
            if re.search(rf"\b{CCY}(?:\s+[a-z]+)?\s*:?\s*$", before) or re.match(rf"\s*{CCY}\b", after) or NOT_MONEY.match(after) or re.search(r"\b(?:score|rank)\s*(?:of\s*)?$", before, re.I):
                continue
            unit = next((c for p, c in reversed(cur) if p < m.start()), None) or next((c for p, c in cur if p > m.end()), None) or whole
            if unit:
                pieces += [clause[last:m.start()], f"{unit} "]
                last = m.start()
        out.append("".join(pieces) + clause[last:])
    return "".join(out)


def _plain(text: str, hint: str | None = None) -> str:
    t = re.sub(r"\bgold_\w+", "a ready table", text)
    t = re.sub(r"\s*\((?:synthetic|SYNTHETIC|Synthetic)\b[^)]*\)", "", t)  # a test tag on a fixture name
    t = re.sub(r";?\s*[^;:()]*\banswer key\b[^;:()]*", "", t)  # test wording ("the assumption of the answer key")
    t = re.sub(r"(?<![\w\\/-])[a-z]+(?:_[a-z]+)+\.([a-z]+(?:_[a-z]+)+)\b", r"\1", t)  # a table.column: the column
    t = SNAKE.sub(lambda m: m.group(0).replace("_", " "), t)
    t = re.sub(r"\b(\d[\d,]*) ((?:[a-z]+ ){0,2}[a-z]+)\((e?s)\)", lambda m: f"{m[1]} {m[2]}{'' if m[1] == '1' else m[3]}", t)  # "1 fund(s)"
    t = re.sub(r"\b1 ([a-z]{2,})ies\b", r"1 \1y", t)
    t = re.sub(r"\b1 ([a-z]{2,}[^ius\W])s\b", r"1 \1", t)  # "1 portfolios"
    t = re.sub(r"\bdue 0\b(?![.,]\d)", "due date not stated", t)
    t = UNKNOWN_CCY.sub("value not stated", t)
    return _money_units(t, hint)


YES_NO = re.compile(r"^\s*(?:is|are|can|could|does|do|did|will|has|have)\b|^\s*whether\b(?!\s+to\b)", re.I)  # "whether to pay" is a decision, not a fact
OPENS_WITH_VERDICT = re.compile(r"^\W*(?:yes|no|not(?!\s+available)|none|hold|release|pay|do not|don't|approve|reject|refuse|accept|ask|keep|add|exit|sell|buy|fix|order|"
                                r"escalate|waive|cure|raise|lower|renew|all|only)\b", re.I)
PROBLEM_Q = re.compile(r"\b(?:outside|over|above|exceed\w*|breach\w*|short\w*|late|missing|overdue|too|more than|differ\w*|fail\w*)\b", re.I)
PROBLEM_A = re.compile(r"\b(?:short|shortfall|not (?:yet|confirmed|ready|explained|traced|complete|covered|approved|matched)|outside|over (?:the |its )?(?:limit|budget|band|room|tolerance|threshold)|"
                       r"above the|breach\w*|missing|overdue|differs?|apart|on hold|pending|open:)", re.I)
SIGN_OFF_Q = re.compile(r"^\s*whether to (?:sign|issue|send|publish|approve)\b", re.I)
NOT_READY_A = re.compile(r"\bnot (?:yet )?(?:ready|complete|signed|approved)\b|\b(?:missing|pending|outstanding)\b", re.I)
FINE_A = re.compile(r"\b(?:fits?|covers?|covered|agrees?|within|complete|in full|can (?:meet|pay|cover)|approved|on time)\b", re.I)


def _verdict(question: str, text: str) -> str:
    """A yes/no question gets its verdict first, read from what the answer itself says (a shortfall, a gap, "not confirmed"); none is guessed."""
    if OPENS_WITH_VERDICT.match(text) or " or " in question.lower() or text.startswith("Not available"):  # no figure: no verdict either
        return text
    if (m := re.match(r"\s*whether to (\w+)", question, re.I)) and text.lower().startswith(f"to {m[1].lower()} "):  # "To add to the list: ..." says it: "Add ..."
        return text[3].upper() + text[4:]
    if SIGN_OFF_Q.search(question):  # "whether to sign off and issue the report": something not ready is a "not yet", nothing else is guessed
        return f"Not yet. {text}" if NOT_READY_A.search(text) or any(int(a) < int(b) for a, b in re.findall(r"\b(\d+) of (\d+)\b(?![,.]\d)", text)) else text
    if not YES_NO.search(question):
        return text
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text):  # the first sentence that says either way decides; a problem outweighs a fit in it
        bad = bool(PROBLEM_A.search(s)) or any(int(a) < int(b) for a, b in re.findall(r"\b(\d+) of (\d+)\b(?![,.]\d)", s))  # "3 of 5 items complete"
        fine = bool(FINE_A.search(s))
        if bad or fine:
            if PROBLEM_Q.search(question):  # "is anything outside its band?": a problem found is a yes
                return f"Yes. {text}" if bad else f"No. {text}"
            return f"No. {text}" if bad else f"Yes. {text}"
    return text


def _polarity(question: str, text: str) -> str:
    """Asked what is outside, told what is inside (r7 uc-032): say plainly that nothing is outside."""
    if re.search(r"\boutside\b", question, re.I) and not re.search(r"\boutside\b", text, re.I):
        return re.sub(r"\bInside (?:the|their|its) (band|limits?|range|tolerance)\b:?", r"None is outside its \1; all are within it:", text, count=1)
    return text


def polish(question: str, out: dict) -> dict:
    """The answer as the person reads it: plain words, what the question asks for (outside, not inside), a verdict first on a yes/no question."""
    text = str(out.get("answer") or "")
    if not text:
        return out
    ccy = {c for r in out.get("rows") or [] if isinstance(r, dict) for c in re.findall(rf"\b{CCY}\b", f"{r.get('label', '')} {r.get('value', '')}")}
    text = _verdict(question, _polarity(question, _plain(text, next(iter(ccy)) if len(ccy) == 1 else None)))
    return out | {"answer": text}


STEPS_Q = re.compile(r"\bsteps?\b|\bwho does (?:each|what)\b|\bstandard operating procedure\b|\bSOP\b", re.I)


def no_steps(question: str) -> dict | None:
    """A "steps / who does each" question is answered from the process map; with no map live, say so, never another figure (r7 uc9-sop)."""
    if not STEPS_Q.search(question):
        return None
    return {"answer": "Not available yet: no process map is live, so the steps and who does each one are not on record. Start one in Build: "
                      "say which process and drop its notes.", "figure": None, "rows": [], "source": "The office's process maps", "used": [],
            "trace": [{"kind": "guard", "label": "A steps question is answered from a live process map only"}]}


# ---- GET /consume ------------------------------------------------------------------------------------------------------------------

def _fig(label: str, value: str) -> dict:
    return {"label": label, "value": value, "change": "", "stale": False}


def _read(plane, viewer) -> tuple[date | None, list[dict], list[dict]]:
    """(as-of day, figures, watchlist) from the liquidity tool at the latest value date; empty when the office has no cash data."""
    try:
        day = latest_day(plane)
        ents = liquidity(plane, viewer, day)
    except Exception:  # noqa: BLE001 - no warehouse yet: the page still opens
        log.info("consume figures unavailable", exc_info=True)
        return None, [], []
    if not ents or not any(e["cash"] for e in ents):  # entities with no cash loaded would show a row of 0.00s: show nothing instead
        return None, [], []
    try:
        prev = {e["code"]: e["cash"] for e in liquidity(plane, viewer, day.replace(day=1) - timedelta(days=1))}
    except Exception:  # noqa: BLE001 - no change shown
        prev = {}
    newest = max((e["dated"] for e in ents if e["dated"]), default=None)
    watch = []
    for e in ents:
        was = prev.get(e["code"])
        old = bool(e["dated"] and newest and (date.fromisoformat(newest) - date.fromisoformat(e["dated"])).days >= STALE_DAYS)
        watch.append({"label": e["name"], "code": e["code"], "value": m(e["cash"]), "stale": old, "dated": e["dated"] if old else None,
                      "change": f"{(e['cash'] - was) / was * 100:+.1f}% vs last month".replace("-", "−") if was else ""})
    tot, c30, c60 = (sum((e[k] for e in ents), Decimal(0)) for k in ("cash", "c30", "c60"))
    figs = [_fig(f"Cash · {e['name']}", m(e["cash"])) for e in ents] + [_fig("Total cash", m(tot)), _fig("Calls due in 30 days", m(c30) if c30 else "None"),
                                                                       _fig("Calls due in 60 days", m(c60) if c60 else "None")]
    return day, figs, watch


def office_name(plane) -> str:
    cid = plane.root.name
    try:
        rows = json.loads((plane.root.parent / "_control" / "companies.json").read_text(encoding="utf-8"))
        return next(r["name"] for r in rows if r.get("company_id") == cid and r.get("name"))
    except (OSError, ValueError, StopIteration, TypeError, KeyError):
        return cid.replace("-", " ").replace("_", " ").title()


def consume(plane, viewer, boards: list[dict], note: dict | None = None) -> dict:
    """{office, as_of, figures, watchlist, boards, note, reports, golden, answer}. The note headline is built from the figures (None when there are none);
    `answer` is the first golden question already answered, by the fast liquidity path only (never a slow model call from a page load)."""
    live = next((t for t in H.all_threads(plane) if t["stage"] == "live" and t.get("pid") and t.get("mode") != "process"), None)
    day, figs, watch = _read(plane, viewer)
    g = golden(plane)
    note, first = None, None
    if figs:
        by = {f["label"]: f["value"] for f in figs}
        n = sum(f["label"].startswith("Cash ·") for f in figs)
        c30 = by["Calls due in 30 days"]
        note = {"headline": f"Cash is {by['Total cash']} USD across {n} entit{'ies' if n != 1 else 'y'}; "
                            + ("no capital calls are due in the next 30 days." if c30 == "None" else f"calls due in 30 days are {c30} USD.")}
        try:
            first = answer(plane, viewer, g[0], lambda: polish(g[0], verified_answer(plane, viewer, g[0], None, live) or (_ for _ in ()).throw(LookupError())),
                           count=False) | {"q": g[0]}  # polished as /api/v3/ask is: both share the kept answer
        except LookupError:
            first = None
    return {"office": office_name(plane), "as_of": day.isoformat() if day else None, "figures": figs, "watchlist": watch, "boards": boards, "note": note,
            "reports": [{"name": "Run book (Word)", "href": f"/api/v1/projects/{live['pid']}/artefacts/run_book/export?format=docx"}] if live else v3_process.reports(plane),
            "golden": [{"q": q} for q in g], "answer": first}
