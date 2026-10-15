import json
from uc6 import Person
pid = "prj-bfa534be"
with Person("leo") as p:
    st, o = p.post(f"/api/v1/build/p/{pid}/builder/benchmark", {"name": "administrator_cash_2026-07.txt", "text": "Available cash EG-HOLD 2,305,906.48\nAvailable cash EG-B 905,000.00"})
    print(st, json.dumps(o)[:600])
