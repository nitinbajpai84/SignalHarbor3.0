import time
from uc6 import Person
with Person("anita") as p:
    t = time.time(); st, th = p.post("/api/v3/threads", {"text": "How much uncalled commitment do we have by fund?"})
    print("start returned", st, "in", round(time.time() - t, 1), "s; stage", th.get("stage"), "|", th["events"][-1]["text"][:80])
