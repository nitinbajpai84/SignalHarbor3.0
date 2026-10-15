"""Intake for one month (Leo uploads + Load this file; the data agent proposes a sheet mapping; Anita approves it as proposed; Leo loads again).
    sh py.sh load_month.py 2026-07 [--approve]
Prints each file's mapping (source column -> target) and the load result."""
import json
import sys
from uc6 import Person, dump, REPO
MONTH = sys.argv[1]
SRC = REPO / "docs/demo/uc6/sources" / MONTH
CODE = {"commitments": "commitments_schedule", "bank_cash": "bank_cash_files", "administrator": "administrator_cash_repor", "notice_receipt": "notice_receipt_log"}
files = sorted(p for p in SRC.iterdir() if p.suffix in (".csv", ".xlsx"))
res = {}
with Person("leo") as l:
    for f in files:
        code = next(v for k, v in CODE.items() if f.name.startswith(k))
        body = {"file": {"name": f.name, "mimeType": "application/octet-stream", "buffer": f.read_bytes()}, "source_code": code, "sensitivity": "internal"}
        st, rec = l.call("POST", "/api/v1/intake/upload", files=body)
        fid = rec.get("file_id") if isinstance(rec, dict) else None
        st2, prof = l.post(f"/api/v1/intake/files/{fid}/profile", {})
        st3, ld = l.post(f"/api/v1/intake/files/{fid}/load", {}, timeout=300000)
        res[f.name] = {"file_id": fid, "upload": st, "dup": rec.get("duplicate") if isinstance(rec, dict) else None, "load": st3, "result": ld}
        print(f.name, "upload", st, "load", st3, json.dumps(ld, default=str)[:260].encode("ascii", "replace").decode(), flush=True)
dump(f"load_{MONTH}_1", res)
if "--approve" in sys.argv:
    with Person("anita") as a:
        st, maps = a.get("/api/v1/model/mappings")
        for m in maps:
            if m.get("state") != "proposed":
                continue
            st, full = a.get(f"/api/v1/model/mappings/{m['id']}")
            cols = [(c.get("source"), (c.get("target_table") or "ignore") + "." + (c.get("target_field") or "")) for c in full.get("columns", [])]
            print("MAP", m["id"], full.get("example_file"), cols)
            st, r = a.post(f"/api/v1/model/mappings/{m['id']}/approve", {"note": "Approved as proposed by the data agent."})
            print("approve", m["id"], st, "" if st == 200 else json.dumps(r)[:300])
    with Person("leo") as l:
        for name, r in res.items():
            st, ld = l.post(f"/api/v1/intake/files/{r['file_id']}/load", {}, timeout=300000)
            r["load2"] = ld
            print(name, "load again", st, json.dumps(ld, default=str)[:300].encode("ascii", "replace").decode(), flush=True)
        l.shot("/centre/data/intake", f"{ {'2026-07':'jul','2026-08':'aug','2026-09':'sep','2026-10':'oct'}[MONTH] }-10-leo-files-loaded", 4000)
    dump(f"load_{MONTH}_2", res)
