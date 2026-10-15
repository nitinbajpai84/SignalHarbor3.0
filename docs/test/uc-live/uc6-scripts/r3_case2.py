import json, sys
from uc6 import Person
CID = "672a4238-4102-47fc-8aea-c31d5cd80502"; tag = sys.argv[1]
with Person("mei") as p:
    st, r = p.post(f"/api/v1/cases/{CID}/dismiss", {"reason": "Already paid on 23 Jul from Entity B (PAY-20260723-B01). The notice reached us late, on 12 Aug. Not an open call."}); print("dismiss", st, json.dumps(r, default=str)[:300])
    p.shot("/centre/action", f"{tag}-10-mei-action-after", 4000)
    print(p.text()[:900].encode("ascii","replace").decode().replace("\n"," | "))
