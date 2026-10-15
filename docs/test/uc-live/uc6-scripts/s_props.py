import json, sys
from uc6 import Person
with Person("mei") as m:
    st, o = m.get("/api/v1/intents/ini-8b228521c012e12c16c7d3c8939df05c/proposals")
    print(st, json.dumps(o, default=str)[:1500].encode("ascii", "replace").decode())
