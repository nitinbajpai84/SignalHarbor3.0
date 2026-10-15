import sys
from uc6 import Person
with Person("anita") as p:
    for u in sys.argv[1:]:
        print(p.shot(f"/v3/{u}", "uat-" + u.replace("/", "-")))
