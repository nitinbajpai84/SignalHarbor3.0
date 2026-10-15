"""F1 The data engineer's conversation with Span. Span reads the catalogue, the mapping sheet (B3), the last runs (B4) and the review queue
(X5, guarded) and Span's data model (A1), lists every doubt as an **open point** and walks them one at a time with the engineer:
- a mapping row with status unclear (B3), or a gold row whose formula the runner could not express (B4 formula: the reason sits in `rule`);
- a check that failed in the latest run of a source (warehouse/runs.json);
- a document of this intent waiting in X5's review queue (`x5_extract.queue`, the same as `GET /api/v1/extract/queue`).

Span composes each question itself ("Row 14: concentration. I took ...; confirm or tell me the rule."): ids, row numbers and SQL never
come back from the model, which only reads the engineer's answer and says what to do with it (the reply guard rewrites digits, so tables go
out as letter aliases, as B4 formula does). An answer patches the mapping row through B3's `edit_row` (so a redraft keeps it) and, for SQL,
writes `sql` with `sql_by: engineer` (B4 formula never redrafts that). With the model off a rule-based reading stands, labelled
"Span (rules only)". A point may be flagged for a human data engineer: it stays open and exports as Markdown. When nothing is open, Span
hands over to the ops manager through the room.

Record: `build/engineer/<iid>.json` {intent_id, turns: [{id, by: "person"|"flow", name, text, at, point}], answers: {key: {text, by, at}},
flagged: {key: {note, by, at}}, handed_over}."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.build import contracts, runner
from sh_platform.build.agents.flow import _rows
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b3_mapping as M
from sh_platform.v1 import b4_formula as F
from sh_platform.v1 import b4_load as L
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1.egress_fit import fit
from sh_platform.v1 import doc_tools as DT
from sh_platform.v1.file_context import added_line, library_lines, preview_for_agent

log = logging.getLogger(__name__)
FLOW, FALLBACK_NAME = "Span", "Span (rules only)"
MAX_TEXT = 4000
YES = re.compile(r"^\s*(yes|yep|ok|okay|confirm(ed)?|correct|right|agreed?|fine|that'?s right)\b", re.I)
DONT_KNOW = re.compile(r"don'?t know|not sure|no idea|unsure|cannot say|can'?t say", re.I)
SQL = re.compile(r"^\s*(select|with)\b", re.I)
DECISIONS = ("confirm", "change", "sql", "open")
ROLE = """You are Span, the data engineer's assistant. You asked the engineer about one open point on the pipeline; read their answer \
and say what to do with it. Use the playbook below. Never guess a meaning, a figure or a rule: when the answer does not settle the point, \
the decision is "open". Answer with ONLY one JSON object:
{"reply": "one or two plain sentences: what you will do", "decision": "confirm" | "change" | "sql" | "open",
 "source_field": "" or the field to read, "transformation": "" or the new transformation in one sentence, "rule": "" or the rule,
 "sql": null or one DuckDB SELECT returning period and value, naming tables only by the alias given (silver."table a")}
"confirm": the engineer agrees with what you understood. "change": they gave a different field, transformation or rule. "sql": they \
described a calculation you can write as SQL over the tables given. Write no digit anywhere (the transport rewrites digits)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(plane, iid: str):
    return plane.path("build", "engineer", f"{M._check(iid)}.json")


def _record(plane, iid: str) -> dict:
    try:
        rec = read_json_strict(_path(plane, iid), dict) or {}
    except (OSError, ValueError):
        log.warning("the engineer conversation for %s could not be read", iid)
        rec = {}
    return {"intent_id": iid, "turns": [], "answers": {}, "flagged": {}, "handed_over": False, **rec}


def _pid(key: str) -> str:
    return "p" + hashlib.sha1(key.encode()).hexdigest()[:10]


def _sheet(plane, iid: str) -> dict:
    got = M.read(plane, iid)
    if got is None:
        raise M.NotFound("There is no mapping sheet for this intent yet. Span writes it once the scope is agreed.")
    return got["sheet"]


# ---- open points ------------------------------------------------------------------------------------------------------------------------

def _is_formula(r: dict) -> bool:
    return r.get("layer") == "gold" and r.get("target_field") == "value" and r.get("op") == "formula"


def _row_point(r: dict, kpis: dict) -> dict:
    target = f"{r.get('target_table')}.{r.get('target_field')}"
    about = kpis.get(str(r.get("target_table") or "").removeprefix("gold.").lower()) or target
    understood = r.get("transformation") or "nothing yet"
    if _is_formula(r):
        why = r.get("rule") or "The runner cannot build it as a sum or a latest value."
        needs = "the rule in your words, or the SQL"
        question = f"Row {r.get('n')}: {about}. {why} I understood: {understood} Confirm, tell me the rule, or paste the SQL."
    else:
        why = "No source field is named." if not r.get("source_field") else "The row is marked unclear."
        needs = "the source field" if not r.get("source_field") else "the transformation or rule"
        question = f"Row {r.get('n')}: {about}. {why} I understood: {understood} Confirm or tell me the rule."
    return {"key": f"row:{target}", "kind": "formula" if _is_formula(r) else "mapping", "row": r.get("n"), "about": about,
            "understood": understood, "needs": needs, "why": why, "question": question, "sql": r.get("sql")}


def _check_points(plane, iid: str) -> list[dict]:
    out = []
    titles = {c["source"]: c["title"] for c in L.contracts_for(plane, iid)[0]}
    latest = {}
    for run in runner.read_runs(plane):
        if run.get("source") in titles:
            latest[run["source"]] = run
    for src, run in sorted(latest.items()):
        for x in run.get("rules") or []:
            if x.get("passed"):
                continue
            field, _, text = str(x.get("rule") or "").partition(":")
            what = f'The check "{text or field}" on {field}' if text else f'The check "{field}"'
            out.append({"key": f"check:{run.get('id')}:{x.get('rule')}", "kind": "check", "row": None, "about": titles[src],
                        "understood": f"{what} failed on {_rows(x.get('count'))} in the last load.",
                        "needs": "whether the file or the check is wrong", "why": None, "sql": None,
                        "question": f"{titles[src]}: {what} failed on {_rows(x.get('count'))} in the last load. Is the file wrong, or the check?"})
    return out


def _doc_points(plane, iid: str) -> list[dict]:
    """This intent's documents in X5's review queue. Guarded: a missing or broken X5 means no document points."""
    try:
        from sh_platform.v1 import x5_extract
        items = x5_extract.queue(plane).get("items") or []
    except Exception:  # noqa: BLE001 - another card's module
        return []
    out = []
    for d in items:
        if not isinstance(d, dict) or d.get("intent_id") not in (None, iid):
            continue
        name = str(d.get("file") or d.get("doc_id") or "A document").rsplit("/", 1)[-1]
        failed = [f for f in d.get("failed") or [] if isinstance(f, dict)]
        fields = ", ".join(str(f.get("field") or "a field") for f in failed) or "a field"
        why = "; ".join(str(f.get("why") or f.get("kind") or "") for f in failed if f.get("why") or f.get("kind")) or "a check failed"
        out.append({"key": f"doc:{d.get('doc_id') or name}:{d.get('at') or ''}", "kind": "document", "row": None, "about": name,
                    "understood": f"{fields} did not pass: {why}.", "needs": "the right value, or why it is missing", "why": why, "sql": None,
                    "question": f"{name}: {fields} did not pass ({why}). What is the right value? You can correct it on the review page too."})
    return out


def _deviation_points(plane, iid: str) -> list[dict]:
    """G4: deviations awaiting approval stay on Span's list until the approver answers; nothing changes before. Guarded."""
    try:
        from sh_platform.v1 import g4_deviations
        devs = g4_deviations.pending(plane, iid)
    except Exception:  # noqa: BLE001 - another card's record
        return []
    out = []
    for d in devs:
        who = ", ".join(a["name"] for a in d["asks"] if (d["decisions"].get(a["name"]) or {}).get("decision") != "approved")
        out.append({"key": f"deviation:{d['id']}", "kind": "deviation", "row": None, "about": d["about"] or "Deviation",
                    "understood": f"Span asked to {d['summary']}.", "needs": f"the answer of {who}", "why": d.get("why"), "sql": None,
                    "question": f"Waiting for {who}: Span asked to {d['summary']}. Nothing changes until they answer. You can add what you know here."})
    return out


def points(plane, iid: str, rec: dict | None = None) -> list[dict]:
    """Every open point, in walking order: mapping rows, formulas, failed checks, documents. Answered points drop out; flagged stay."""
    rec = rec or _record(plane, iid)
    sow = contracts._read(plane, "intents", iid, "sow.json")
    names = {k.get("code"): k.get("name") for k in sow.get("kpis") or [] if isinstance(k, dict)}
    kpis = {str(c.get("table") or "").removeprefix("gold.").lower(): names.get(next(iter(c.get("feeds_kpis") or []), None))
            for c in sow.get("catalogue") or [] if isinstance(c, dict)}
    rows = [r for r in _sheet(plane, iid).get("rows") or [] if isinstance(r, dict) and r.get("status") == "unclear"]
    found = [_row_point(r, {k: v for k, v in kpis.items() if v}) for r in rows]
    found.sort(key=lambda p: p["kind"] == "formula")  # plain rows first, then the formulas
    found += _check_points(plane, iid) + _doc_points(plane, iid) + _deviation_points(plane, iid)
    out = []
    for p in found:
        if p["key"] in rec["answers"]:
            continue
        flag = rec["flagged"].get(p["key"])
        out.append({**p, "id": _pid(p["key"]), "flagged": flag})
    return out


def _current(open_points: list[dict]) -> dict | None:
    return next((p for p in open_points if not p["flagged"]), None) or (open_points[0] if open_points else None)


# ---- the view ---------------------------------------------------------------------------------------------------------------------------

def _context(plane, iid: str, sheet: dict) -> dict:
    sow = contracts._read(plane, "intents", iid, "sow.json")
    model = (contracts._read(plane, "build", "blueprint.json").get("model") or {})
    span = contracts._read(plane, "build", "blueprint_conversation", f"{iid}.json").get("data_model") or []  # A1's data model, when drafted
    srcs = {c["source"] for c in L.contracts_for(plane, iid)[0]}
    rows = [r for r in sheet.get("rows") or [] if isinstance(r, dict)]
    try:
        from sh_platform.v1.skill_loader import skill_label
        skill = skill_label("flow", plane)
    except ImportError:
        skill = "Data engineer"
    try:
        from sh_platform.v1 import g4_deviations
        declined = g4_deviations.declined(plane, iid)  # G4: the approver's reason is the next fact for Span
    except Exception:  # noqa: BLE001
        declined = []
    return {"declined_deviations": declined, "catalogue_tables": len(sow.get("catalogue") or []), "mapping_rows": len(rows), "mapping_version": sheet.get("version"),
            "transformations": sum(bool(r.get("transformation")) for r in rows), "sql_rows": sum(bool(r.get("sql")) for r in rows),
            "data_model_tables": len(span) or len(model.get("facts") or []) + len(model.get("dimensions") or []),
            "runs": sum(r.get("source") in srcs for r in runner.read_runs(plane)), "skill": skill}


def opening(ctx: dict, open_points: list[dict]) -> str:
    head = (f"I have read the catalogue ({ctx['catalogue_tables']} tables), the mapping sheet ({ctx['mapping_rows']} rows) "
            f"and the last runs ({ctx['runs']}).")
    cur = _current(open_points)
    if cur is None:
        return head + " Nothing is open: every row is mapped and the last load passed its checks. Run the load from the Pipeline tab."
    return head + f" I have {len(open_points)} open point{'s' if len(open_points) != 1 else ''}; here is the first. {cur['question']}"


def view(plane, iid: str) -> dict:
    sheet = _sheet(plane, iid)
    rec = _record(plane, iid)
    open_points = points(plane, iid, rec)
    ctx = _context(plane, iid, sheet)
    cur = _current(open_points)
    return {"intent_id": iid, "turns": rec["turns"], "opening": opening(ctx, open_points), "points": open_points,
            "current": cur["id"] if cur else None, "context": ctx, "handed_over": bool(rec.get("handed_over")), "proposals": _proposals(plane, iid)}


def _proposals(plane, iid: str) -> dict:
    try:
        return L2.view(plane, iid)
    except L2.Refused:
        return {"pending": [], "recent": []}


# ---- reading the engineer's answer --------------------------------------------------------------------------------------------------------

def _tables(plane, iid: str, row: dict | None) -> dict:
    """The silver tables of the row's KPI sources, with columns (B4 formula's reading)."""
    if not row:
        return {}
    sow = contracts._read(plane, "intents", iid, "sow.json")
    table = str(row.get("target_table") or "").removeprefix("gold.").lower()
    cat = next((c for c in sow.get("catalogue") or [] if isinstance(c, dict) and str(c.get("table") or "").removeprefix("gold.").lower() == table), {})
    codes = set(cat.get("feeds_kpis") or [])
    sids = [s for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code") in codes for s in k.get("source_ids") or []]
    sids = [s for s in dict.fromkeys(sids + [row.get("source_id")]) if s]
    try:
        from sh_platform.warehouse import open_company
        con = open_company(plane)
    except Exception:  # noqa: BLE001 - no warehouse yet: no tables to name
        return {}
    try:
        return F.tables_of(con, sids)
    finally:
        con.close()


def _unalias(sql: str, alias: dict[str, str]) -> str:
    """B4 formula's alias back to the real table, quoted or not."""
    for k, t in alias.items():
        sql = re.sub(r'silver\s*\.\s*"?' + re.escape(k) + '"?', f'silver."{t}"', sql, flags=re.I)
        sql = re.sub(r'(?<![\w."])"?' + re.escape(k) + r'"?(?![\w"])', f'silver."{t}"', sql, flags=re.I)
    return sql


def read_answer(text: str, kind: str) -> dict:
    """The rule-based reading (no model): SQL pasted, a yes, a don't-know, or new words for the row."""
    if SQL.match(text) and kind in ("formula", "mapping"):
        return {"decision": "sql", "sql": text.strip().rstrip(";").strip(), "reply": "I will keep your SQL on the row."}
    if YES.match(text):
        return {"decision": "confirm", "reply": "Confirmed as I understood it."}
    if DONT_KNOW.search(text):
        return {"decision": "open", "reply": "I will leave it open. Flag it for a data engineer in the Real engineer tab if nobody here knows."}
    if kind in ("formula", "mapping"):
        return {"decision": "change", "transformation": text.strip()[:M.MAX_CELL], "reply": "I have written your rule on the row."}
    return {"decision": "change", "reply": "Noted. I have kept your answer with the point." + (
        " Correct the value on the review page so the document leaves the queue." if kind == "document" else "")}


def ask(rt, plane, iid: str, point: dict, row: dict | None, text: str, skill: str, files: list | None = None, viewer=None) -> dict | None:
    """The model's reading of the answer, or None (no model, no JSON, or the reply guard had to rewrite a figure)."""
    if rt is None or rt.model is None:
        return None
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.build.agents.runtime import MODULE_ID
    tables = _tables(plane, iid, row) if point["kind"] == "formula" else {}
    alias = {f"table {chr(ord('a') + i)}": t for i, t in enumerate(sorted(tables)[:26])}  # digit-free names
    back = {v: k for k, v in alias.items()}
    ctx = fit({"point": {k: point.get(k) for k in ("kind", "about", "understood", "needs", "why")},
               "row": {k: (row or {}).get(k) for k in ("layer", "target_field", "source_field", "transformation", "rule", "test")} if row else None,
               "declined_deviations": _context(plane, iid, _sheet(plane, iid))["declined_deviations"],  # G4: what the approver said no to, and why
               **L2.facts(plane, iid, ("mapping",)),  # L2: what waits for a yes, and what the engineer turned down and why
               "files_now": preview_for_agent(plane, iid, files or []),  # V1: what was dropped in this turn
               "library": library_lines(plane, iid, viewer),  # C4: the context-library items ticked for this conversation
               "tables": [{"table": back[t], "columns": [f"{c} ({ty})" for c, ty in cols]} for t, cols in sorted(tables.items())]}, (("files_now", None), ("library", None)))
    rt = rt.routed("flow", "formula_sql" if point["kind"] == "formula" else "reply", iid, plane, want_json=True, text=text, files=bool(files))  # R1
    try:
        reg, _ = DT.registry(rt.gate, MODULE_ID, plane, iid, viewer, ctx.setdefault("facts", []))  # D1: search_documents and read_document
        res = run_agent(rt.model, reg, rt.company_id or plane.company_id, MODULE_ID, FLOW, ROLE + "\n\n" + skill + "\n\n" + DT.PROMPT_LINE, ctx,
                        f"THE ENGINEER ANSWERED: {text}", recorder=rt.recorder)
    except Exception:  # noqa: BLE001 - a model failure leaves the rule-based reading
        log.warning("Span's reading of the engineer's answer failed")
        return None
    if res.status != "done" or res.numbers_replaced:
        return None
    a, b = (res.text or "").find("{"), (res.text or "").rfind("}")
    try:
        got = json.loads(res.text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        return None
    if not isinstance(got, dict) or got.get("decision") not in DECISIONS or not str(got.get("reply") or "").strip():
        return None
    out = {k: " ".join(str(got.get(k) or "").split())[:M.MAX_CELL] for k in ("reply", "source_field", "transformation", "rule")}
    out["decision"] = got["decision"]
    if got["decision"] == "sql":
        if not isinstance(got.get("sql"), str) or not got["sql"].strip():
            return None
        out["sql"] = _unalias(got["sql"].strip().rstrip(";").strip(), alias)
    return out


# ---- applying it ------------------------------------------------------------------------------------------------------------------------

def _write_sql(plane, iid: str, n: int, sql: str) -> None:
    p = M.path(plane, iid)
    with lock_for(p):
        sheet = _sheet(plane, iid)
        for r in sheet.get("rows") or []:
            if r.get("n") == n:
                r["sql"], r["sql_by"] = sql, "engineer"
        write_json_atomic(p, sheet)


def apply(plane, iid: str, point: dict, row: dict | None, got: dict) -> tuple[bool, str]:
    """(settled, what Span says). A row point patches the mapping row; others keep the answer with the point."""
    d = got["decision"]
    if d == "open":
        return False, ""
    if point.get("kind") == "deviation":  # G4: only the approver settles it
        return False, "I have kept that with the request. Nothing changes until the approver answers."
    if row is None:
        return True, ""
    n = int(row["n"])
    if d == "sql":
        tables = _tables(plane, iid, row)
        why = F.check_sql(got["sql"], set(tables)) if tables else None
        if why:
            return False, f"I cannot keep that SQL: {why} Please correct it."
        _write_sql(plane, iid, n, got["sql"])
        M.edit_row(plane, iid, n, {"status": "mapped", "rule": "SQL by the data engineer; it runs at the next load."
                                   + ("" if tables else " It is checked then, as no cleaned table is loaded yet.")})
        return True, ""
    change = {"status": "mapped"}
    if d == "change":
        change.update({k: got[k] for k in ("source_field", "transformation", "rule") if got.get(k)})
        if len(change) == 1:
            return False, "I could not tell what to change. Tell me the field, the transformation or the rule."
    if not (row.get("source_field") or change.get("source_field")):
        return False, "The row still names no source field. Which field should it read?"
    M.edit_row(plane, iid, n, change)
    return True, ""


def propose_answer(plane, iid: str, point: dict, row: dict, got: dict, text: str, who: str) -> int:
    """L2: the model's reading of the engineer's answer (a changed row or SQL) waits for a yes. Returns how many changes."""
    label = f"{row.get('target_table')}.{row.get('target_field')}"
    fields = ("sql",) if got["decision"] == "sql" else ("source_field", "transformation", "rule")
    changes = [{"op": "add" if not row.get(f) else "change", "path": f"rows/{label}/{f}", "before": str(row.get(f) or ""), "after": got.get(f) or ""}
               for f in fields if got.get(f) and got.get(f) != row.get(f)]
    payload = {"point": {k: point.get(k) for k in ("id", "key", "kind", "row", "about")}, "row": row.get("n"), "got": got, "text": text, "who": who}
    return len(changes) if L2.propose(plane, iid, "mapping", None, changes, payload=payload) else 0


def apply_proposal(plane, iid: str, p: dict, who: str) -> str:
    """Accept: the same `apply` as before, on the live mapping row; the point is answered when it settles. A cell the engineer
    changed by hand since Span proposed is skipped (returned as a note), as North does for the SOW."""
    pl = p["payload"]
    with lock_for(_path(plane, iid)):
        rec = _record(plane, iid)
        row = next((r for r in _sheet(plane, iid).get("rows") or [] if r.get("n") == pl["row"]), None)
        point = next((x for x in points(plane, iid, rec) if x["key"] == pl["point"]["key"]), None) or pl["point"]
        got, skipped = dict(pl["got"]), []
        for c in p.get("changes") or []:
            f = str(c.get("path") or "").rsplit("/", 1)[-1]
            if row and f in got and str(row.get(f) or "") != c.get("before"):
                got.pop(f)
                skipped.append(f.replace("_", " "))
        if skipped and not any(got.get(f) for f in ("source_field", "transformation", "rule", "sql")):
            raise M.Refusal(f"The {', '.join(skipped)} of that row changed since Span proposed this, so nothing was changed.")
        settled, said = apply(plane, iid, point, row, got)
        if not settled:
            raise M.Refusal(said or "That change could not be applied. Please tell me how the row should read.")
        rec["answers"][point["key"]] = {"text": pl["text"], "by": pl.get("who") or who, "at": _now(), "decision": pl["got"]["decision"]}
        rec["flagged"].pop(point["key"], None)
        write_json_atomic(_path(plane, iid), rec)
    return f"Left your own change to the {', '.join(skipped)} as it is." if skipped else ""


def _turn(by: str, name: str, text: str, point: str | None) -> dict:
    return {"id": "t_" + secrets.token_hex(6), "by": by, "name": name, "text": text, "at": _now(), "point": point}


def _room(plane, iid: str, kind: str, text: str) -> None:
    with __import__("contextlib").suppress(Exception): from sh_platform.v1 import p1_project as P1; P1.comment(plane, iid, "build_pack", None, "flow", {"question": "builder", "handover": "ops"}.get(kind, "raiser"), text, kind="comment" if kind == "question" else kind)  # P1
    try:
        from sh_platform.v1 import room
        room.post(plane, iid, "flow", kind, text, to=["people"], refs=[{"kind": "mapping", "id": iid}])
    except Exception:  # noqa: BLE001 - a missing or broken room never breaks the conversation
        log.warning("the room post from the engineer conversation failed")


def chat(plane, iid: str, viewer, text: str, point_id: str | None = None, *, rt=None, files: list | None = None) -> dict:
    """The engineer's answer to the current open point (or the one named), Span's reading and its next question."""
    from sh_platform.v1 import g1_access as G1; G1.check_agent(plane, iid, viewer, lambda m: M.Refusal(m))  # G1: the agent reads a project's artefacts only for a person who may see it
    text = str(text or "").strip()[:MAX_TEXT] or added_line(files or [])
    if not text:
        raise M.Refusal("Write your answer first.")
    with lock_for(_path(plane, iid)):
        moved = L2.resolve_words(plane, iid, text, getattr(viewer, "name", ""), ("mapping",))  # L2: "yes" accepts what Span proposed, "no ..." turns it down
        rec = _record(plane, iid)
        before = points(plane, iid, rec)
        if not rec["turns"]:
            rec["turns"].append(_turn("flow", FLOW, opening(_context(plane, iid, _sheet(plane, iid)), before), None))
        point = next((p for p in before if p["id"] == point_id), None) if point_id else _current(before)
        if point_id and point is None:
            raise M.NotFound("That point is no longer open.")
        rec["turns"].append(_turn("person", viewer.name, text, point["id"] if point else None))
        if moved and (moved[0]["status"] == "accepted" or len(text.split()) <= 3):  # the yes or the bare no was the answer to the proposal, not to the next point
            nxt = _current(points(plane, iid, rec))
            reply, name = ("Done, the row is changed." if moved[0]["status"] == "accepted" else "Understood, I have left the row as it was. How should it read?")                 + (f" Next: {nxt['question']}" if moved[0]["status"] == "accepted" and nxt else ""), FLOW
        elif point is None:
            reply, name = "Nothing is open. Run the load from the Pipeline tab, and I will come back with anything it finds.", FLOW
        else:
            row = next((r for r in _sheet(plane, iid).get("rows") or [] if point["row"] is not None and r.get("n") == point["row"]), None)
            skill = ""
            try:
                from sh_platform.v1.skill_loader import load_skill
                skill = load_skill("flow", plane)
            except ImportError:
                pass
            got = None if SQL.match(text) else ask(rt, plane, iid, point, row, text, skill, files, viewer)  # pasted SQL is kept as written
            name = FLOW if got or SQL.match(text) else FALLBACK_NAME
            got = got or read_answer(text, point["kind"])
            if name == FLOW and not SQL.match(text) and got["decision"] in ("change", "sql") and row is not None and point["kind"] != "deviation"                     and (n := propose_answer(plane, iid, point, row, got, text, viewer.name)):
                settled, said = False, got["reply"] + L2.tail(n)  # L2: the model's reading waits for a yes; pasted SQL and rule-based readings apply as before
            else:
                settled, said = apply(plane, iid, point, row, got)
            if settled:
                rec["answers"][point["key"]] = {"text": text, "by": viewer.name, "at": _now(), "decision": got["decision"]}
                rec["flagged"].pop(point["key"], None)
                if point["kind"] == "check":
                    _room(plane, iid, "note", f"{viewer.name} on {point['about']}: {text[:300]}")
            after = points(plane, iid, rec)
            nxt = _current(after)
            reply = (said or got["reply"]) + (f" Next: {nxt['question']}" if settled and nxt else "")
            if not after:
                reply += " That was the last open point. I have told the ops manager; run the load from the Pipeline tab."
                if not rec.get("handed_over"):
                    _room(plane, iid, "handover", "Span has no open points left on the pipeline. Ops manager: after the next load, "
                                                  "confirm Loaded per period on the ops page.")
                    rec["handed_over"] = True
        rec["turns"].append(_turn("flow", name, reply, point["id"] if point else None))
        write_json_atomic(_path(plane, iid), rec)
    return view(plane, iid)


def flag(plane, iid: str, viewer, point_id: str, note: str) -> dict:
    """Flag an open point for a human data engineer. It stays open until answered."""
    note = str(note or "").strip()[:1000]
    with lock_for(_path(plane, iid)):
        rec = _record(plane, iid)
        point = next((p for p in points(plane, iid, rec) if p["id"] == point_id), None)
        if point is None:
            raise M.NotFound("That point is no longer open.")
        rec["flagged"][point["key"]] = {"note": note, "by": viewer.name, "at": _now()}
        write_json_atomic(_path(plane, iid), rec)
    _room(plane, iid, "question", f"{viewer.name} flagged a point for a data engineer: {point['about']}. {note}".strip())
    with __import__("contextlib").suppress(Exception):  # T2: a ticket to the builder; the comment above is its discussion
        from sh_platform.v1 import p1_project as P1, t2_tickets
        pid = P1._pid_of(plane, iid)
        t2_tickets.raise_guarded(plane, by="flow", to="builder", title=f"Flagged for a data engineer: {point['about']}"[:120], body=f"{point['about']}. {note}".strip(),
                                 project=pid, stage="build", links=[{"kind": "artefact", "ref": f"{pid}:build_pack"}])
    return view(plane, iid)


def flagged_markdown(plane, iid: str) -> str:
    """The flagged points with their context, for a human data engineer."""
    v = view(plane, iid)
    out = [f"# Open points for a data engineer: intent {iid}", "",
           f"Mapping sheet version {v['context']['mapping_version']}, {v['context']['mapping_rows']} rows. Exported {_now()}.", ""]
    flagged = [p for p in v["points"] if p["flagged"]]
    if not flagged:
        out.append("Nothing is flagged.")
    for p in flagged:
        out += [f"## {p['about']}" + (f" (row {p['row']})" if p["row"] is not None else ""), "",
                f"- Kind: {p['kind']}", f"- What Span understood: {p['understood']}", f"- What Span needs: {p['needs']}",
                *([f"- Why: {p['why']}"] if p["why"] else []),
                f"- Flagged by {p['flagged']['by']} on {p['flagged']['at']}: {p['flagged']['note'] or 'no note'}",
                *(["", "```sql", p["sql"], "```"] if p["sql"] else []), ""]
    return "\n".join(out)
