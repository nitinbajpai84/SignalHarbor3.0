import json
from uc6 import Person
with Person("leo") as m:
    st, r = m.post("/api/v1/evidence/fields/d59bc77b-5bf0-451f-aaaf-7b7fb9e7d87d/confirm", {}); print("confirm", st, json.dumps(r, default=str)[:300])
    m.shot("/centre/data/evidence", "aug-05-leo-notice-confirmed", 4000)
