import json, sys
from uc6 import Person, dump
tag = sys.argv[1]
for who in ("mei", "raj", "leo", "anita"):
    with Person(who) as p:
        st, c = p.get("/api/v1/cases"); dump(f"{tag}_cases_{who}", c)
        cs = c.get("cases", [])
        print("==", who, st, len(cs), [(x.get("id"), x.get("title"), x.get("state") or x.get("status")) for x in cs][:12])
        p.shot("/centre/action", f"{tag}-09-{who}-action", 4500)
        print(p.text()[:1500].encode("ascii","replace").decode().replace("\n", " | ")[:1100])
