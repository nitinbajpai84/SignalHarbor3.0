from uc6 import Person
with Person("anita") as p:
    st, th = p.post("/api/v3/threads/t-a6f00be2bb/say", {"text": "retry"})
    print(st, th.get("stage"), "|", th["events"][-1]["text"][:100])
