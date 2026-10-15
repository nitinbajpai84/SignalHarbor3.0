"""Run 3: Leo presses Approve on each fund waiting for approval on a file page, then loads that file again. usage: r3_funds.py <load json month> <file name>"""
import json, sys
from uc6 import Person, dump
mon, name = sys.argv[1], sys.argv[2]
import os
f2 = f"D:/Temp/uc6r3/load_{mon}_2.json"
d = json.load(open(f2))[name] if os.path.exists(f2) else json.load(open(f"D:/Temp/uc6r3/load_{ {'aug': '2026-08'}[mon] }_1.json"))[name]["result"]
na = d["last_load"]["needs_approval"]; print(json.dumps(na)[:1500])
fid = d["last_load"]["file_id"]
with Person("leo") as l:
    for f in na["funds"]:
        st, r = l.post(f"/api/v1/evidence/aliases/{f['identifier_id']}/approve", {}); print("approve fund", f["name"], st, "" if st == 200 else json.dumps(r)[:300])
    st, ld = l.post(f"/api/v1/intake/files/{fid}/load", {}, timeout=300000)
    print(st, json.dumps(ld.get("last_load"), default=str)[:1500])
    dump("funds_" + mon, ld)
