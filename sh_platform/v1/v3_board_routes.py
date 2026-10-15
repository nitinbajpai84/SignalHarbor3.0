"""Harbor 3.0 board, ask and note (spec: docs/v3/HARBOR-SPEC.md, 14 Oct addendum). No new chart or answer logic: the board is the live thread's
published 2.0 dashboard (cx_dash), the ask is Lumen's company talk with its number guard (talk.ask), the note is k10_note's morning note.
GET /api/v3/board -> {title, as_at, figures:[{label,value,change,source?}], tiles:[2.0 tile + project_id, dashboard_id], empty}
POST /api/v3/ask {text} -> {answer, figure?, understood?, trace:[{kind,label}], used:[str], cached, ms, as_of} (kept per question and data version: v3_consume)
GET /api/v3/consume -> {office, answer, as_of, figures, watchlist, boards, note, reports, golden} (v3_consume)
GET /api/v3/note -> {text, figures, history:[{at, headline}]}. Every failure answers a plain message, never a trace."""
import json
import logging
import re
import threading
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import e6_trace, k10_note as N, talk as T, teach
from sh_platform.v1 import v3_consume as C
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_process as P
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
EMPTY = {"title": "", "as_at": "", "figures": [], "tiles": [], "empty": True}
STEP = {"model": "Wrote the answer", "rules": "Answered by fixed rules from the data", "context": "Looked at what the project holds"}


def _live(plane) -> dict | None:
    return next((t for t in H.all_threads(plane) if t["stage"] == "live" and t.get("pid") and t.get("mode") != "process"), None)  # a procedure has no board


def _source(th: dict) -> str | None:
    run = next((s["run_id"] for s in reversed(th.get("steps") or []) if s.get("run_id")), None)
    return f"Run {run} of {th['title']}" if run else None


def _figures(th: dict) -> list[dict]:
    src = _source(th)
    return [f | ({"source": src} if src else {}) for f in (th.get("note") or {}).get("figures") or []]


def _has_data(plane, pid: str, dash: dict, tid: str) -> bool:
    """A tile is shown only when its series has a figure in it; an error or an all-null answer counts as no data."""
    try:
        rows = D.tile_rows(plane, pid, dash, tid)["rows"]
    except Exception:  # noqa: BLE001 - a tile that does not run is a tile with no data yet, never a crash
        log.info("board tile %s has no data", tid, exc_info=True)
        return False
    return any(v is not None and v == v for r in rows for v in r.values())  # NaN is not a figure


def _board(plane, viewer, th: dict) -> dict:
    pid = th["pid"]
    S.adopt(plane, pid)
    mine = [d for d in D.list_for(plane, viewer, pid) if d.get("accepted")]
    if not mine:
        return EMPTY | {"title": th["title"]}
    dash = D.get_published(plane, viewer, pid, mine[0]["id"])
    accepted = [t for t in dash["tiles"] if t["state"] == "accepted"]
    shown = [t for t in accepted if _has_data(plane, pid, dash, t["id"])]
    tiles = [{k: t.get(k) for k in ("id", "title", "state", "spec", "kpi", "note")} | {"project_id": pid, "dashboard_id": dash["id"]} for t in shown]
    shown_ids = {t["id"] for t in shown}
    lines = [f"{t['title']}: no data yet" for t in accepted if t["id"] not in shown_ids]
    return {"title": dash["title"], "as_at": D._last_refresh(plane, pid) or dash.get("published_at") or "", "figures": _figures(th), "tiles": tiles, "lines": lines, "empty": False}


@router.get("/api/v3/board")
def get_board(request: Request):
    plane, viewer = _plane(request), viewer_of(request)
    th = _live(plane)
    if th is None:
        return EMPTY
    try:
        return _board(plane, viewer, th)
    except Refused as e:
        raise HTTPException(e.status, e.message) from None


def _label(s: dict) -> str:
    k = s.get("kind")
    if k == "tool":
        return "Read " + str(s.get("tool") or "the data").replace("_", " ")
    if k == "guard":
        n = int(s.get("numbers_replaced") or 0)
        return "Checked every number against the data" + (f"; {n} could not be checked and was left out" if n else "")
    return STEP.get(k, "Worked on it")


def _trace(plane, trace_id: str | None) -> list[dict]:
    if not trace_id:
        return []
    return [{"kind": str(s.get("kind") or "step"), "label": _label(s)} for r in e6_trace.steps_for(plane, trace_id) for s in r.get("steps") or [] if isinstance(s, dict)]


def _ask(plane, viewer, text: str, pid: str | None) -> dict:
    fast = P.answer(plane, text) or C.liquidity_answer(plane, viewer, text, pid)  # the steps of a live procedure (the SOP); cash, calls due: tool calls, ahead of Lumen
    if fast:
        return fast
    from sh_platform.v1 import v3_figures as F  # the ready table of the figure the question names, ahead of Lumen's free answer
    fig = F.figure_answer(plane, viewer, text, pid, _live(plane))
    if fig:
        return fig
    s, token = teach.open_scope("lumen", text, plane=plane)
    try:
        got = T.ask(plane, viewer, "lumen", text, pid)
    finally:
        teach.close_scope(token)
    used = [] if got.get("rules_only") else [u["line"] for u in s.used]  # a reply worded by the fixed rules used no taught passage
    out = {"answer": got["reply"], "trace": _trace(plane, got.get("trace_id")), "used": used}
    return honest(plane, text, _live(plane), out)


# ---- the last guard on Lumen's reply (c2: "could you share the previous status", "the variance is minimal", "the data may still be loading") ------------
# talk.ask's number guard already blanks a figure no tool returned, and a blanked reply becomes the rules reply; a reply with no figure at all, one that asks
# the person for records, or one that guesses why, passed it. For a question about the project's figures that reply becomes the thread's own record.
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_DATES = re.compile(rf"\b\d{{4}}-\d{{2}}(?:-\d{{2}})?\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\b(?:,?\s+\d{{4}})?|\b{_MONTH}\s+\d{{1,2}}?(?:,?\s*\d{{4}})?\b"
                    r"|\b(?:19|20)\d{2}\b|\b[QH][1-4]\b", re.I)
_NUMBER = re.compile(r"(?<![\w./-])-?\d[\d,]*(?:\.\d+)?(?![\w/-])")
FIGURE_Q = re.compile(r"\b(?:how (?:much|many)|worth|differ\w*|variance|break|total|balance|amount|value|figure|percent\w*|nav|p&l|cash|limit|"
                      r"return|exposure|concentration|uncalled|overdue)\b", re.I)
HOW_TO = re.compile(r"^\s*(?:how (?:do|can|should|would) (?:i|we|you)|what (?:does|do) .{1,60} mean|explain|define|what is meant)\b", re.I)
ASKS_BACK = re.compile(r"\b(?:could|can|would) you (?:please )?(?:share|send|provide|upload|tell me)|\bplease (?:share|send|provide|upload)\b"
                       r"|\bmay (?:still )?be loading\b|\bstill loading\b", re.I)


LEFT_OUT = "could not check a figure in my answer"  # talk.ask's rules reply after the number guard blanked a figure: "1 set of figures" in it is a count, not the answer


def has_figure(reply: str) -> bool:
    """A number in the reply that is not a date, a year or part of a name (a file name, a trade id)."""
    from sh_platform.v1.talk import untraced
    return not untraced(reply) and LEFT_OUT not in (reply or "") and bool(_NUMBER.search(_DATES.sub(" ", reply or "")))


def asks_figure(text: str, kpis: list[dict]) -> bool:
    from sh_platform.v1 import v3_figures as F
    return not HOW_TO.search(text) and bool(F.kpi_for(text, kpis) or FIGURE_Q.search(text) or F.CHANGE_Q.search(text))


def honest_line(text: str, th: dict, kpis: list[dict]) -> str:
    """"Not available yet: <figure> ... <what is missing>", from the thread's own record: the figure's reason and the files that did not load."""
    from sh_platform.v1 import v3_figures as F
    k = F.kpi_for(text, kpis)
    if k:
        f = next((f for f in th.get("figures") or [] if f.get("kpi") == k["name"]), {})
        why = str(f.get("reason") or (th.get("figure_notes") or {}).get(k["name"]) or "")
        say = f"Not available yet: {k['name']} has no figure in the ready tables." + (f" {why}" if why else "")
    else:
        names = ", ".join(k["name"] for k in kpis)
        say = "Not available yet: no ready table of this project holds that figure" + (f" (its figures are {names})." if names else ".")
    return say if " Not loaded:" in say else say + F._not_loaded(th)


def honest(plane, text: str, th: dict | None, out: dict) -> dict:
    """Lumen's reply, or for a question about the live project's figures that holds no figure (or asks the person for records) the honest line."""
    if not th or not th.get("pid"):
        return out
    from sh_platform.v1 import v3_figures as F, v3_skills as SK
    kpis = F.kpis_of(plane, th.get("iid"))
    reply = str(out.get("answer") or "")
    if not asks_figure(text, kpis) or (has_figure(reply) and not ASKS_BACK.search(reply)):
        return out
    with SK.record(plane, th.get("id"), C.SKILL) as rec:
        line = honest_line(text, th, kpis)
        rec["detail"] = "the reply held no figure from the rows: " + line[:200]
    return {"answer": line, "figure": None, "rows": [], "source": "The project's own record", "used": [],
            "trace": out.get("trace", []) + [{"kind": "guard", "label": "The reply held no figure from the data, so it says what is missing"}]}


@router.post("/api/v3/ask")
async def post_ask(request: Request):
    plane, viewer = _plane(request), viewer_of(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    text = str(body.get("text") or "").strip()[:2000] if isinstance(body, dict) else ""
    if not text:
        raise HTTPException(400, "Write your question first.")
    th = _live(plane)
    pid = th["pid"] if th else None
    try:
        return await run_in_threadpool(C.answer, plane, viewer, text, lambda: _ask(plane, viewer, text, pid))
    except Refused as e:
        raise HTTPException(e.status, e.message) from None
    except Exception:  # noqa: BLE001 - a plain message, never a trace
        log.warning("v3 ask failed", exc_info=True)
        raise HTTPException(502, "I could not answer that just now. Please try again.") from None


def _from_k10(plane, viewer) -> dict | None:
    try:
        n = N.morning_note(plane, viewer)
    except Exception:  # noqa: BLE001 - no 2.0 data for this office yet: the thread's own note stands in
        return None
    if n["headline"] == N.NOT_YET:
        return None
    return {"text": " ".join(x for x in (n["headline"], n.get("summary")) if x),
            "figures": [{"label": t["label"], "value": N._tile_text(t), "change": t.get("note") or "", **({"source": t["where"]["text"]} if (t.get("where") or {}).get("text") else {})}
                        for t in n["tiles"] if t["available"]]}


def _history(plane, headline: str) -> list[dict]:
    """One line per day, kept beside the threads; today's line is replaced when the note changes, the past is the list."""
    p = plane.path("v3", "note_log.json")
    try:
        log_ = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log_ = {}
    today = date.today().isoformat()
    if headline and log_.get(today) != headline:
        log_[today] = headline
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(log_), encoding="utf-8")
    return [{"at": d, "headline": h} for d, h in sorted(log_.items(), reverse=True) if d != today][:30]


@router.get("/api/v3/note")
def get_note(request: Request):
    plane, viewer = _plane(request), viewer_of(request)
    th = _live(plane)
    note = _from_k10(plane, viewer) or ({"text": th["note"]["text"], "figures": _figures(th)} if th and th.get("note") else {"text": "", "figures": []})
    return note | {"history": _history(plane, note["text"].split(". ")[0])}


def _boards(plane, viewer, th: dict | None) -> list[dict]:
    if th is None:
        return []
    try:
        S.adopt(plane, th["pid"])
        return [{"id": d["id"], "title": d.get("title") or th["title"]} for d in D.list_for(plane, viewer, th["pid"]) if d.get("accepted")]
    except Exception:  # noqa: BLE001 - boards that cannot be listed leave the list empty, never the page
        log.info("consume boards unavailable", exc_info=True)
        return []


def precompute(plane, viewer) -> int:
    """Warm the answers of the most-asked and golden questions for the current data version (the skills agent calls this after a live run)."""
    pid = (_live(plane) or {}).get("pid")
    return C.precompute(plane, viewer, lambda q: lambda: _ask(plane, viewer, q, pid))


@router.get("/api/v3/consume")
def get_consume(request: Request):
    plane, viewer = _plane(request), viewer_of(request)
    th = _live(plane)
    out = C.consume(plane, viewer, _boards(plane, viewer, th))
    if C.due(plane):  # the data version changed: warm the answers in the background, the page does not wait
        threading.Thread(target=precompute, args=(plane, viewer), daemon=True).start()
    return out
