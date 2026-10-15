"""Run 3: Leo corrects the proposed mappings (what the file page lets him do), Anita approves, Leo loads. usage: r3_intake_fix.py <month-code jul|aug> [--shots]"""
import json, sys
from uc6 import Person, dump
MON = sys.argv[1]
PORT = {"EG-B": "EG-B-OPS", "EG-HOLD": "EG-GROWTH", "EG-TRUST": "EG-LIQUID"}
def fixes(ex):
    if ex.startswith("commitments"):
        return [{"source": "Estimate amount", "target": "ignore"}, {"source": "Fund key", "target": "ignore"}], {}
    if ex.startswith("bank_cash_"):
        e = ex.split("_")[2]
        return [{"source": "account_number", "target": "ignore"}, {"source": "account_name", "target": "ignore"}], {"portfolios.portfolio_code": PORT[e]}
    return [], {}
res = {}
with Person("leo") as l:
    st, maps = l.get("/api/v1/model/mappings")
    for m in maps:
        if m.get("state") == "proposed":
            st, full = l.get(f"/api/v1/model/mappings/{m['id']}")
            lines, fixed = fixes(full["example_file"])
            if lines or fixed:
                st, r = l.put(f"/api/v1/model/mappings/{m['id']}", {"columns": lines, "fixed": fixed})
                print("edit", full["example_file"], st, "" if st == 200 else json.dumps(r)[:300])
with Person("anita") as a:
    st, maps = a.get("/api/v1/model/mappings")
    for m in maps:
        if m.get("state") == "proposed":
            st, r = a.post(f"/api/v1/model/mappings/{m['id']}/approve", {"note": "Approved after Leo's corrections."})
            print("approve", m["id"], st, "" if st == 200 else json.dumps(r)[:300])
files = json.load(open(f"D:/Temp/uc6r3/load_{ {'jul':'2026-07','aug':'2026-08'}[MON] }_1.json"))
with Person("leo") as l:
    for name, r in files.items():
        st, ld = l.post(f"/api/v1/intake/files/{r['file_id']}/load", {}, timeout=300000)
        res[name] = ld
        print(name, st, json.dumps({k: ld.get(k) for k in ("state", "note", "needs_approval", "last_load")} if isinstance(ld, dict) else ld, default=str)[:700].encode("ascii", "replace").decode(), flush=True)
    dump(f"load_{MON}_2", res)
