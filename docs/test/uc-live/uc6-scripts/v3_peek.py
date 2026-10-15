import json,sys
from uc6 import Person
with Person("leo") as p:
    for path in sys.argv[1:]:
        st,o=p.get(path); print(path, st); print(json.dumps(o,default=str)[:1500])
