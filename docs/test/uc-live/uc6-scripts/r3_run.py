import json, sys
from uc6 import Person
PID = "prj-a4d01dff"
with Person("leo") as l:
    for mode in sys.argv[1:]:
        st, r = l.post(f"/api/v1/build/p/{PID}/run?mode={mode}", {}, timeout=600000); print(mode, st, json.dumps(r, default=str)[:700])
