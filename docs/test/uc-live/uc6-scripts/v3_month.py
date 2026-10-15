"""After live: drop a month's files, wait for Harbor's monthly run, show what reached the person. sh py.sh v3_month.py 2026-08"""
import json, sys, time
from uc6 import Person, dump
from v3_e2e import drop
import os
tid = json.load(open(os.environ.get("V3_STATE", "D:/Temp/sh3-e2e.json")))["tid"]
with Person("anita") as p:
    drop(sys.argv[1])
    t0 = time.time()
    while time.time() - t0 < 900:
        st, d = p.get("/api/v3/desk")
        st, th = p.get(f"/api/v3/threads/{tid}")
        if th.get("stage") not in ("working",) and time.time() - t0 > 60:
            break
        time.sleep(10)
    dump("v3_desk_" + sys.argv[1], d)
    print("stage", th.get("stage"), "| files", d.get("files"))
    for c in d.get("needs") or []:
        print(" NEEDS", c["kind"], "|", c["title"], "|", c["text"][:250])
    for e in th.get("events", [])[-4:]:
        print(" ", e.get("kind"), "|", (e.get("text") or ", ".join(e.get("chips") or []))[:300])
    for u in ("desk", f"thread/{tid}", "files", "board", "note"):
        p.shot(f"/v3/{u}", f"v3-{sys.argv[1]}-" + u.split("/")[0])
