"""Harbor 3.0 board, ask and note (spec: docs/v3/HARBOR-SPEC.md, 14 Oct addendum). No new chart or answer logic: the board is the live thread's
published 2.0 dashboard (cx_dash), the ask is Lumen's company talk with its number guard (talk.ask), the note is k10_note's morning note.
GET /api/v3/board[?pid=] -> {title, as_at, figures:[{label,value,change,source?}], tiles:[2.0 tile + project_id, dashboard_id], empty, pid, dashboard_id, can_edit}
GET /api/v3/boards -> {can_edit, boards:[{pid, dashboard_id, title, use_case, owner, refreshed, draft, status}]} (one per live use case; draft = a change waiting in the studio)
POST /api/v3/board/add {pid, dashboard_id?, figure_id?, label, value?, text?} -> {added, kind, status}: the figure as a widget of the studio's draft (a maker only; approval as the studio requires)
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
from sh_platform.v1 import b7h_history as H7
from sh_platform.v1 import e6_trace, k10_note as N, talk as T, teach
from sh_platform.v1 import v3_consume as C
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_process as P
from sh_platform.v1 import v3_signal_draft as SD
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
EMPTY = {"title": "", "as_at": "", "figures": [], "tiles": [], "empty": True}
STEP = {"model": "Wrote the answer", "rules": "Answered by fixed rules from the data", "context": "Looked at what the project holds"}


def _live(plane, text: str = "") -> dict | None:
    """The live build a question is about: of the live builds (a procedure has no board), the one whose request in the person's own words shares the
    most words with the question, the newest on a tie. r6: with uc-001 and uc-002 both live, uc-001's question got uc-002's answer (the newest build)."""
    live = [t for t in H.all_threads(plane) if t["stage"] == "live" and t.get("pid") and t.get("mode") != "process"]
    if len(live) < 2 or not text:
        return live[0] if live else None
    from sh_platform.v1 import v3_recipes as R
    q = R._stems(text)
    asked = lambda t: next((str(e.get("text") or "") for e in t.get("events") or [] if e.get("kind") == "person"), t.get("title") or "")  # noqa: E731
    return max(live, key=lambda t: len(q & R._stems(asked(t))))  # max keeps the first (newest) of equals


def _live_all(plane) -> list[dict]:
    return [t for t in H.all_threads(plane) if t["stage"] == "live" and t.get("pid") and t.get("mode") != "process"]


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
    return {"title": dash["title"], "as_at": D._last_refresh(plane, pid) or dash.get("published_at") or "", "figures": _figures(th), "tiles": tiles, "lines": lines, "empty": False,
            "pid": pid, "dashboard_id": dash["id"], "can_edit": S.is_maker(viewer)}


@router.get("/api/v3/board")
def get_board(request: Request, pid: str | None = None):
    plane, viewer = _plane(request), viewer_of(request)
    th = next((t for t in _live_all(plane) if t["pid"] == pid), None) if pid else _live(plane)
    if th is None:
        return EMPTY
    try:
        return _board(plane, viewer, th)
    except Refused as e:
        raise HTTPException(e.status, e.message) from None


def _board_rows(plane, viewer) -> list[dict]:
    """One row per live use case that has a published dashboard: where it is, who made it, when its data last ran, and whether the studio holds a change."""
    out = []
    for th in _live_all(plane):
        try:
            S.adopt(plane, th["pid"])
            pub = next((d for d in D.list_for(plane, viewer, th["pid"]) if d.get("accepted")), None)
            if pub is None:
                continue
            mine = {r["id"]: r for r in S.listing(plane, viewer, th["pid"])}.get(pub["id"], {})
            status = mine.get("status") or "published"
            out.append({"pid": th["pid"], "dashboard_id": pub["id"], "title": pub.get("title") or th["title"], "use_case": th["title"],
                        "owner": mine.get("made_by") or str(mine.get("created_by") or "") or None, "refreshed": D._last_refresh(plane, th["pid"]),
                        "draft": status != "published", "status": status})
        except Exception:  # noqa: BLE001 - a use case whose board cannot be read is left off the list, never the page
            log.info("board row unavailable for %s", th.get("pid"), exc_info=True)
    return out


@router.get("/api/v3/boards")
def get_boards(request: Request):
    plane, viewer = _plane(request), viewer_of(request)
    return {"can_edit": S.is_maker(viewer), "boards": _board_rows(plane, viewer)}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _figure_widget(plane, pid: str, figure_id: str, label: str) -> dict | None:
    """The studio widget body for a stored figure: its first ready table of this project that has a number column, the column named like the figure when there is one."""
    from sh_platform.v1 import v3_figstore as FS
    rec = FS.read(plane, figure_id) if figure_id else None
    reads = (FS.version(rec) or {}).get("reads") or [] if rec else []
    gold = {t["name"]: t for t in D.gold_tables(plane, pid)} if reads else {}
    for name in reads:
        cols = {c["name"] for c in gold.get(name, {}).get("columns", [])}
        want = next((c for c in (_slug(label), _slug((rec or {}).get("name") or "")) if c in cols), None)
        try:
            S.build_tile(plane, pid, "figure", name, want)
        except Refused:
            continue
        return {"kind": "figure", "table": name, "measure": want}
    return None


@router.post("/api/v3/board/add")
async def post_board_add(request: Request):
    """Add a figure to a board as a widget of the studio's draft. Only a maker (the studio's own rule); the draft then goes for approval in the studio."""
    plane, viewer = _plane(request), viewer_of(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    body = body if isinstance(body, dict) else {}
    pid, label = str(body.get("pid") or ""), str(body.get("label") or "").strip()[:200]
    if not S.is_maker(viewer):
        raise HTTPException(403, "Only the data team can build dashboards.")
    row = next((b for b in _board_rows(plane, viewer) if b["pid"] == pid and (not body.get("dashboard_id") or b["dashboard_id"] == body["dashboard_id"])), None)
    if row is None or not label:
        raise HTTPException(400, "Choose a board and a figure to add.")

    def go():
        did = row["dashboard_id"]
        rec = S._editor(plane, viewer, pid, did)
        D.begin_edit(rec, viewer)
        lay = S._layout(rec)
        rows0 = lay["rows"]
        r, c = S._first_free(lay)
        if lay["rows"] != rows0:  # the grid was full: the new row is saved first so the slot exists
            D._save(plane, rec)
        w = _figure_widget(plane, pid, str(body.get("figure_id") or ""), label)
        if w is None:  # no ready table to follow: the number as it stands, as a note, so it is never lost
            text = str(body.get("text") or "").strip() or f"{label}: {body.get('value') or ''}".strip(": ")
            w = {"kind": "note", "text": text}
        placed = S.add_widget(plane, viewer, pid, did, w | {"row": r, "col": c})
        H7.record_step(plane, viewer, pid, did, "", f"Added {placed['title']}")
        return {"added": placed["title"], "kind": placed["kind"], "status": D.status_of(D._load(plane, pid, did)), "dashboard_id": did}
    try:
        return await run_in_threadpool(go)
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


def fast(plane, viewer, text: str, pid: str | None) -> dict | None:
    """The answer without the model, as the person reads it (C.polish), or None: the live procedure (the SOP), else for a steps question the plain
    "no process map" line, else the verified figures, then the cash tool."""
    got = P.answer(plane, text) or C.no_steps(text) or C.verified_answer(plane, viewer, text, pid, _live(plane, text))
    return C.polish(text, got) if got else None


def _ask(plane, viewer, text: str, pid: str | None) -> dict:
    if got := fast(plane, viewer, text, pid):
        return got
    return C.polish(text, _model(plane, viewer, text, pid))


def _model(plane, viewer, text: str, pid: str | None) -> dict:
    if not _live(plane) and asks_figure(text, []):
        # nothing is live, so no figure can be on record: say so at once instead of a 40-second model call that ends in the same place
        return {"answer": "Not available yet: no build is live, so there is no figure on record for that. Start one in Build: say what you need and drop your files.",
                "figure": None, "rows": [], "source": "The office's own record", "used": [],
                "trace": [{"kind": "guard", "label": "No live build holds a figure, so the answer says so without asking the model"}]}
    s, token = teach.open_scope("lumen", text, plane=plane)
    try:
        got = T.ask(plane, viewer, "lumen", text, pid)
    finally:
        teach.close_scope(token)
    used = [] if got.get("rules_only") else [u["line"] for u in s.used]  # a reply worded by the fixed rules used no taught passage
    out = {"answer": got["reply"], "trace": _trace(plane, got.get("trace_id")), "used": used}
    return honest(plane, text, _live(plane, text), out)


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
    from sh_platform.v1 import v3_figures as F, v3_rule_checks as RC
    k = RC.kpi_by_recipe(text, kpis) or F.kpi_for(text, kpis)  # the figure bound to the recipe the question names
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


def _email(request: Request) -> str:
    me = request.app.state.account_store.get(request.state.account_id) or {}
    return str((me if isinstance(me, dict) else vars(me)).get("email") or "")


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
    th = _live(plane, text)
    pid = th["pid"] if th else None
    try:
        got = await run_in_threadpool(C.answer, plane, viewer, text, lambda: _ask(plane, viewer, text, pid))
        fig = got.get("figure") or {}
        SD.observe(plane, "question", _email(request), fig.get("id") or fig.get("label") or "", text, figure=fig.get("id"), text=text)  # who asked what, answered by which figure
        return got
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
    """The published boards of every live use case this person may see (not only the newest one: when another use case went live, the
    others' boards vanished from Consume although they were still published). `th` first, so the newest stays on top."""
    out: list[dict] = []
    for t in ([th] if th else []) + [t for t in _live_all(plane) if not th or t["id"] != th["id"]]:
        try:
            S.adopt(plane, t["pid"])
            out += [{"id": d["id"], "title": t["title"] if (d.get("title") or "").startswith("Lumen's starter") else d.get("title") or t["title"]}
                    for d in D.list_for(plane, viewer, t["pid"]) if d.get("accepted")]  # nine "starter dashboard"s read as nothing: name it by its use case
        except Exception:  # noqa: BLE001 - one use case whose boards cannot be listed is skipped, never the page
            log.info("consume boards unavailable for %s", t.get("id"), exc_info=True)
    return out


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


# ---- "Check what I read": fields Harbor held for a person (v3_review, A60) ----------------------------------------------------------------

@router.get("/api/v3/review")
def get_review(request: Request):
    """GET -> {min, items:[{id, field, reading, currency, page, line, confidence, document, quote}]}: the held fields."""
    from sh_platform.v1 import v3_review as R
    plane = _plane(request)
    return {"min": R.minimum(plane), "items": R.queue(plane)}


@router.post("/api/v3/review/{field_id}")
async def post_review(field_id: str, request: Request):
    """POST {value?} -> confirm the reading (no value) or correct it; the field is released with the person's name and time."""
    from sh_platform.v1 import v3_review as R
    plane, viewer = _plane(request), viewer_of(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - no body is a confirm
        body = {}
    value = body.get("value") if isinstance(body, dict) else None
    if value is not None and not str(value).strip():
        raise HTTPException(422, "Type the right value, or choose Confirm.")
    try:
        return await run_in_threadpool(R.resolve, plane, field_id, viewer.name, None if value is None else str(value).strip())
    except KeyError:
        raise HTTPException(404, "That field is not waiting for a check.") from None
