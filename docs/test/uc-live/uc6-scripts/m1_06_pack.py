"""Month 1, step 6: Leo marks the notice fields, asks Span for a silver capital-call schedule, proposes the model change if Span cannot,
Anita approves it, Leo drafts the design pack."""
import json
from uc6 import Person, dump
PID = "prj-a4d01dff"
A = f"/api/v1/build/p/{PID}/architecture"
NOTICES = "src_2e265c52d311"
MARKS = [(0, "notice_kind", "text"), (2, "fund", "text"), (3, "manager_reference", "text"), (4, "investor", "text"), (5, "notice_date", "date"),
         (6, "amount", "money"), (7, "due_date", "date"), (9, "paid_in_after_call", "money")]
ASK = ("Please propose a silver table for the capital call schedule: fund, legal entity, amount, due date, status (noticed or confirmed), "
       "notice reference, superseded flag, notice kind (call or distribution), cycle. Put it in the pack as a model change.")
TABLE = {"name": "capital_call_schedule", "group": "liquidity", "note": "One row per capital call or distribution notice; a later notice with the same reference supersedes the earlier one; manager estimates never enter.",
         "columns": [{"name": n, "type": t, "note": d} for n, t, d in (
             ("fund_name", "varchar", "Fund as named on the notice"), ("legal_entity_code", "varchar", "Investing entity"),
             ("notice_kind", "varchar", "call or distribution"), ("manager_reference", "varchar", "Manager's call reference; the de-duplication key"),
             ("notice_date", "date", "Date on the notice"), ("due_date", "date", "Due or payment date"), ("amount", "decimal", "USD amount"),
             ("status", "varchar", "noticed or confirmed"), ("superseded", "boolean", "True when a later notice with the same reference replaced it"),
             ("received_on", "date", "When the office received the notice"), ("cycle", "varchar", "Run month YYYY-MM"))]}
with Person("leo") as l:
    for n, name, fmt in MARKS:
        st, r = l.post(f"{A}/samples/{NOTICES}/mark", {"line": n, "name": name, "format": fmt})
        print("mark", n, name, st, "" if st == 200 else json.dumps(r)[:200])
    st, r = l.post(f"/api/v1/build/p/{PID}/chat", {"text": ASK}, timeout=300000)
    dump("m1_span_silver_reply", r)
    print("SPAN", st, json.dumps(r, default=str)[:900].encode("ascii", "replace").decode())
    st, mp = l.post("/api/v1/model/proposals", {"add_table": TABLE, "note": "UC6: the capital-call schedule has no silver table (UC6-12). Span drafts gold only."})
    dump("m1_model_proposal", mp)
    n = mp.get("n") or mp.get("id") or mp.get("number") if isinstance(mp, dict) else None
    print("model proposal", st, n, json.dumps(mp, default=str)[:300])
with Person("anita") as a:
    st, r = a.post(f"/api/v1/model/proposals/{n}/approve", {"note": "Approved for UC6: one row per notice, keyed on the manager reference."})
    print("anita approves model change", st, json.dumps(r, default=str)[:300])
    a.shot("/centre/map/data-model", "jul-05-anita-model-change-approved", 5000)
with Person("leo") as l:
    st, pk = l.post(f"{A}/pack/generate", timeout=300000)
    dump("m1_pack_v1", pk)
    print("pack", st, json.dumps({k: pk.get(k) for k in ("version", "state", "open", "needs", "blocking")} if isinstance(pk, dict) else pk, default=str)[:1500].encode("ascii", "replace").decode())
    l.shot(f"/centre/build/p/{PID}/architecture/pack", "jul-06-leo-design-pack-drafted", 5000)
