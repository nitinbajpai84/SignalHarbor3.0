"""Workaround W2: Span drafted 0 gold and 0 silver tables and 12 open mapping rows ('no table could be chosen'). The pack cannot be sent
until every row is settled, and the pack edit has no way to add a table (ALLOWED in b10_pack.py). Leo settles each open row with a note
(PUT .../pack/edit {section: mapping, key, changes: {resolve: true}, note}), the 'Correct a line' control, then sends it to Anita.
Anita approves (POST .../pack/approve) and asks Span for the build plan (POST .../pack/plan)."""
from lib import *
pid = st("pid"); A = f"/api/v1/build/p/{pid}/architecture"
NOTE = {"check": "Settled: the file lands through intake into silver transactions (external_trade_id, trade_date, quantity, price, amount); the trade check reads it.",
        "derived": "Settled: worked out by the product's trade check trade_vs_admin (Action > Reconciliations) from silver transactions, per month-end.",
        "read": "Settled: kept as a document; the figures are compared on the administrator file's SGD amount."}
w = W("leo"); s, r = w.api("GET", A + "/pack"); pack = r["pack"]
for m in pack["mapping"]:
    if not m.get("resolved", True) or m.get("needs_person"):
        s2, r2 = w.api("PUT", A + "/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": True}, "note": NOTE.get(m["kind"], NOTE["check"])})
        print("settle", m["id"], s2, "" if s2 < 300 else r2)
s, r = w.api("PUT", A + "/pack/edit", {"section": "definition", "key": "K07", "changes": {"definition": "Count of breaks whose absolute USD difference is above 5,000 USD; same figure as K05."}, "note": "Span's question answered"}); print("def K07", s, "" if s < 300 else r)
s, r = w.api("POST", A + "/pack/submit", {}); keep("pack-submit", r); print("submit", s, json.dumps(r)[:300] if s >= 300 else r["pack"]["state"], r.get("pack", {}).get("counts") if isinstance(r, dict) else "")
w.close()
a = W("anita"); a.go(f"/centre/build/p/{pid}/architecture/pack", 6000); a.shot("jul-05-anita-pack-to-approve")
s, r = a.api("POST", A + "/pack/approve", {"note": "Approved for July: matching runs on silver transactions through the trade check."}); keep("pack-approve", r)
print("approve", s, json.dumps(r)[:400] if s >= 300 else (r["pack"]["state"], r["pack"].get("approved_by")))
t = time.time(); s, r = a.api("POST", A + "/pack/plan", {}); keep("pack-plan", r); print("plan", s, round(time.time() - t), "s", json.dumps(r)[:300] if s >= 300 else r.get("plan_version"))
a.go(f"/centre/build/p/{pid}/architecture/pack", 6000); a.shot("jul-06-anita-pack-approved"); print(a.text()[-1500:]); a.close()
