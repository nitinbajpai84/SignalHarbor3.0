import json,sys
from uc6 import Person
tid=json.load(open("D:/Temp/sh3-e2e.json"))["tid"]
with Person("anita") as p:
    st,th=p.post(f"/api/v3/threads/{tid}/say",{"text":sys.argv[1]}, timeout=600000)
    print(st, th.get("stage"))
    for e in th.get("events",[])[-3:]: print(" ",e.get("kind"),"|",(e.get("text") or ",".join(e.get("chips") or []))[:700])
    d=th.get("decision") or {}; print(json.dumps(d.get("brief"),default=str)[:800])
