import json
from uc6 import Person
with Person("anita") as p:
    st, c = p.get("/api/v3/consume"); print("consume", st, [(f["label"], f["value"]) for f in c.get("figures", [])][:4])
    st, d = p.get("/api/v3/desk"); print("desk", st, "needs", len(d.get("needs", [])), "threads", [(t["title"], t["stage"]) for t in d.get("threads", [])])
