import sys
from uc6 import Person
with Person("leo") as l:
    l.shot("/centre/data/intake", "jul-06-leo-intake-files", 4000)
    l.shot("/centre/data/intake/372ddad6-a84e-43fb-bfeb-09a0ec623d46", "jul-06-leo-intake-commitments-file-page", 4500)
    print(l.text()[:1200].encode("ascii","replace").decode().replace("\n"," | "))
    l.shot("/centre/operations", "aug-07-leo-operations-runs", 4000)
    l.shot("/centre/map/data-model", "aug-07-leo-map-data-model", 4000)
with Person("raj") as r:
    r.shot("/centre/consume/office", "aug-11-raj-consume-office", 5000)
    print(r.text()[:1800].encode("ascii","replace").decode().replace("\n"," | "))
with Person("daniel") as d:
    d.shot("/centre/consume/office", "aug-11-daniel-consume-office", 4000)
