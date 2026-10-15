import json,sys
sys.path.insert(0,".")
from uc6 import Person
tid=json.load(open("D:/Temp/sh3-e2e.json"))["tid"]
with Person("anita") as p:
    st,th=p.post(f"/api/v3/threads/{tid}/decide",{"n":2,"answer":"retry"}); print("retry",st,th.get("stage"))
