import json
from uc6 import Person, dump
DOC = "a0c4111a-1a19-4c3f-99bf-ee01599b23fe"
with Person("leo") as l:
    st, r = l.post(f"/api/v1/evidence/documents/{DOC}/extract", {}, timeout=300000); print("extract", st, json.dumps(r, default=str)[:1800].encode("ascii","replace").decode())
    dump("aug_extract", r)
    st, d = l.get(f"/api/v1/evidence/documents/{DOC}"); dump("aug_doc", d); print(json.dumps(d, default=str)[:1500].encode("ascii","replace").decode())
