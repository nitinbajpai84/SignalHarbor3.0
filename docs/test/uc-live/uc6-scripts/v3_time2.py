import time
from uc6 import Person
def wait(p, tid):
    t = time.time()
    while True:
        st, th = p.get(f"/api/v3/threads/{tid}")
        if th["stage"] != "drafting":
            return th, round(time.time() - t)
        time.sleep(2)
with Person("anita") as p:
    t = time.time(); st, th = p.post("/api/v3/threads", {"text": "How much uncalled commitment do we have by fund? Mei reads it monthly."}); print("start returned in", round(time.time() - t, 2), "s")
    th, s = wait(p, th["id"]); print("first brief ready after", s, "s; stage", th["stage"])
    t = time.time(); st, th = p.post(f"/api/v3/threads/{th['id']}/say", {"text": "Daniel also reads it, by the 5th of each month."}); print("reply acknowledged in", round(time.time() - t, 2), "s:", th["events"][-1]["text"][:70])
    th, s = wait(p, th["id"]); print("brief updated after", s, "s; changed lines:", [l["label"] for g in th["decision"]["brief"]["doc"] for l in g["lines"] if l.get("changed")])
