"""r9: mapping rows that still need a person, settled before the design pack is sent for approval (b10_pack.submit refuses while any is open).

Round 8 stuck Sofia (investment analyst) at "12 mapping rows still need a person: settle them first." Not a permission or a signer problem: Span
designed a ready table for her figures after Harbor had settled the pack's rows (v3_figures.cover runs after that), and the 12 columns of the new
table had no definition, so the submit refused on every retry.

Now each open row of a ready table's column goes to the judge (v3_judge, kind "mapping_row"): is the proposed definition clear and true to the
table's select? Two models that agree "yes" settle it; the definition is written on the column and the judgement is recorded as an assumption.
The tables with any unclear column are taken out of the pack (gold_remove), so the rest is sent and approved, and become ONE Decision 2 question
to the person who raised the brief, listing every unclear column with the definition Span proposes. "Use these definitions" puts the tables back
(a new pack version, approved by the head of data); "Leave these tables out" leaves them out and the figures say why. A row that waits on a sample
or a file (no ready-table column) is settled at intake, as before."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)
KIND = "mapping_row"
USE, LEAVE = "Use these definitions", "Leave these tables out"
QID = "rows:held"
INTAKE_NOTE = "Mapped at intake from the uploaded file and approved by the head of data."


def _A(x) -> str:
    return f"/api/v1/build/p/{x.th['pid']}/architecture"


def proposal(g: dict, col: str, model_cols: dict[str, set]) -> str:
    """Span's definition of one column: a column the select passes through from a table it reads says where it comes from; else plain words."""
    from sh_platform.v1 import v3_figures as F
    src = next((t for t in g.get("depends_on") or [] if col in model_cols.get(t, set())), None)
    if src:
        return f"The {col.replace('_', ' ')} of the {src.replace('_', ' ')} row it comes from ({src}.{col}), unchanged."
    return F.defined({"sql": g.get("sql") or "", "columns": [col]}).get(col) or f"The {col.replace('_', ' ')} the figure is for."


def _model_cols(x) -> dict[str, set]:
    from sh_platform.v1 import e0a_catalogue as E
    try:
        return {t["name"]: {c["name"] for c in t.get("columns") or []} for t in E.current(x.plane)["tables"]}
    except Exception:  # noqa: BLE001 - without the model every column gets plain words; the judge still decides
        log.info("the company model could not be read", exc_info=True)
        return {}


def settle(x) -> str:
    """Settle the open rows of the draft pack: by the judge for a ready table's column, at intake for the rest. Unclear tables are held out."""
    from sh_platform.v1 import v3_figures as F, v3_judge as J
    A = _A(x)
    pk = x.api("leo", "GET", A + "/pack").get("pack") or {}
    gold = {g["name"]: g for g in (pk.get("target") or {}).get("gold") or []}
    rows = [m for m in pk.get("mapping") or [] if m.get("needs_person") and not m.get("resolved")]
    cols, held, agreed, ask = _model_cols(x), {}, 0, []
    keep = x.th.setdefault("held_tables", {})
    for m in rows:
        t, _, c = str(m.get("gold") or "").partition(".")
        if m.get("kind") != "derived" or t not in gold:  # waits on a sample or a file: settled at intake
            x.api("leo", "PUT", A + "/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": INTAKE_NOTE}, "note": "Harbor settles this row."})
            continue
        if (keep.get(t) or {}).get("answered") == "used":  # the person confirmed this table's definitions at Decision 2
            x.api("leo", "PUT", A + "/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": True},
                                                   "note": f"{x.th.get('started_by') or 'The person'} confirmed the definition at Decision 2."})
            continue
        g = gold[t]
        col = next((k for k in g.get("columns") or [] if k.get("name") == c), {})
        ask.append((m, t, c, proposal(g, c, cols), {"table": t, "what the table is for": g.get("purpose") or "", "select": (g.get("sql") or "")[:1500], "column": c,
                                                     "type": col.get("type") or "", "tables it reads": g.get("depends_on") or []}))

    def judge(item):
        m, t, c, words, ev = item
        return J.judged(x.plane, KIND, J.question(KIND, column=c, table=F.plain(t, list(gold.values()))), ["yes", "no"], {**ev, "proposed definition": words},
                        J.standard(KIND), x.th["id"], person=False, describe=DESCRIBE)
    with ThreadPoolExecutor(4) as pool:  # ponytail: 4 at a time keeps a 12-column table under a minute; the judge's budget still caps the spend
        said = list(pool.map(judge, ask))
    for (m, t, c, words, _), ok in zip(ask, said):
        if ok == "yes":
            x.api("leo", "PUT", A + "/pack/edit", {"section": "gold_column", "key": f"{t}.{c}", "changes": {"definition": words}, "note": "Two models agreed the definition is clear."})
            x.api("leo", "PUT", A + "/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": True},
                                                   "note": f"Settled by two models that agreed: {words}"[:300]})
            agreed += 1
        else:
            held.setdefault(t, []).append({"column": c, "proposed": words})
    notes = x.th.setdefault("figure_notes", {})
    for t, unclear in held.items():
        g = gold[t]
        kpis = list(dict.fromkeys([*(g.get("kpis") or []), *(f["kpi"] for f in x.th.get("figures") or [] if f.get("table") == t)]))
        for k in kpis:  # said at Decision 3 too, for a table held after Decision 2 has passed
            notes[k] = f"Its table waits for {x.th.get('started_by') or 'the person'}: two models could not agree the meaning of {', '.join(u['column'] for u in unclear)[:150]}."
        keep[t] = {"purpose": g.get("purpose") or "", "sql": g.get("sql") or "", "depends_on": list(g.get("depends_on") or []), "grain": g.get("grain") or "",
                   "keys": list(g.get("keys") or []), "kpis": kpis, "unclear": unclear,
                   "definitions": {**{k["name"]: k.get("definition") for k in g.get("columns") or [] if k.get("definition") and k.get("definition") != "Needs a definition"},
                                   **{u["column"]: u["proposed"] for u in unclear}}}
        x.api("leo", "PUT", A + "/pack/edit", {"section": "gold_remove", "key": t, "changes": {"remove": True}, "note": "Held for the person: the meaning of some columns is not clear."})
    return f"{len(rows)} open rows: {agreed} settled by two models, {sum(len(v) for v in held.values())} held in {len(held)} tables for the person"


def send(x) -> None:
    """Settle the rows, then send the pack and approve it as the head of data (the pack's two steps)."""
    settle(x)
    A = _A(x)
    x.api("leo", "POST", A + "/pack/submit", {})
    vs = x.api("leo", "GET", A + "/pack").get("versions") or [{"version": 1}]
    x.api("anita", "POST", A + "/pack/approve", {"version": vs[-1]["version"], "note": "Approved by the head of data."})


def questions(x) -> list[dict]:
    """Decision 2: ONE question listing every unclear column of the held tables, addressed to the person who raised the brief."""
    from sh_platform.v1 import v3_figures as F
    held = {t: h for t, h in (x.th.get("held_tables") or {}).items() if not h.get("answered")}
    if not held:
        return []
    who = x.th.get("started_by") or "you"
    lines = "; ".join(f"{F.plain(t)} ({', '.join(h['kpis']) or 'no figure named'}): " + ", ".join(f"{u['column']} = {u['proposed']}" for u in h["unclear"])
                      for t, h in held.items())
    return [{"id": QID, "for": who, "text": f"For {who}, who raised the brief: Span designed ready tables for your figures, but two models could not agree "
             f"that these columns are clear. {lines[:1500]} Use Span's definitions, or leave these tables out?", "options": [USE, LEAVE], "assumed": None}]


def answer(x, val: str) -> str:
    """The person's answer: the held tables go back into the pack with the definitions (a new version the head of data approves), or stay out."""
    held = {t: h for t, h in (x.th.get("held_tables") or {}).items() if not h.get("answered")}
    if not held:
        return ""
    if val != USE:
        notes = x.th.setdefault("figure_notes", {})
        for h in held.values():
            h["answered"] = "left out"
            for k in h["kpis"]:
                notes[k] = "Left out at Decision 2: the meaning of some columns of its table was not clear."
        return f"{len(held)} tables left out"
    A, back = _A(x), 0
    for t, h in held.items():
        try:
            x.api("leo", "PUT", A + "/pack/edit", {"section": "gold_add", "key": t, "note": f"{x.th.get('started_by') or 'The person'} confirmed the definitions at Decision 2.",
                                                   "changes": {k: h[k] for k in ("purpose", "sql", "depends_on", "grain", "keys", "definitions")}})
            h["answered"] = "used"
            back += 1
            for k in h["kpis"]:
                x.th.setdefault("figure_notes", {}).pop(k, None)
        except Exception as e:  # noqa: BLE001 - the plan check refused it now: the figure says why
            h["answered"] = "refused"
            for k in h["kpis"]:
                x.th.setdefault("figure_notes", {})[k] = f"The table could not be put back: {str(getattr(e, 'text', e))[:200]}"
    if back:
        send(x)
    return f"{back} tables put back with the confirmed definitions"


DESCRIBE = {"yes": "Yes: a reader knows what the column holds and where it comes from, and the select produces it that way.",
            "no": "No: the definition is vague, or the select produces the column differently (computed, fixed or empty)."}
