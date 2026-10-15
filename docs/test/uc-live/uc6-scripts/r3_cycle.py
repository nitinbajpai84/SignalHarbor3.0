import json, sys
from uc6 import Person
with Person("anita") as a:
    st, r = a.put("/api/v1/cycle-date", {"cycle_date": sys.argv[1]}); print("cycle", st, json.dumps(r)[:200])
    st, r = a.get("/api/v1/cycle-date"); print(r)
    a.shot("/centre/settings", f"{sys.argv[2]}-00-anita-cycle-date", 3000)
