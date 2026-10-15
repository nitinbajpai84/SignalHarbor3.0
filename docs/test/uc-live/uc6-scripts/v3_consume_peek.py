import json
from uc6 import Person
with Person("anita") as p:
    st, c = p.get("/api/v3/consume"); print("consume", st, json.dumps(c, default=str)[:1500])
    st, a = p.post("/api/v3/ask", {"text": "What is our cash by entity today?"}, timeout=300000); print("ask", st, json.dumps(a, default=str)[:1500])
