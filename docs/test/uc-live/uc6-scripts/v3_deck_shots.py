import os
from pathlib import Path
from uc6 import BASE, SHOTS, Person
OUT = Path(SHOTS); OUT.mkdir(parents=True, exist_ok=True)
TID = os.environ["V3_TID"]
with Person("anita") as p:
    pg = p.page; pg.set_viewport_size({"width": 1600, "height": 1000})
    def shot(path, name, wait=4500, full=False):
        pg.goto(BASE + path); pg.wait_for_timeout(wait); pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full); print(name)
    shot("/v3/desk", "deck-desk")
    shot("/v3/action", "deck-action")
    shot(f"/v3/build/{TID}", "deck-build")
    shot("/v3/consume", "deck-consume")
    shot("/v3/knowledge", "deck-knowledge")
    pg.set_viewport_size({"width": 390, "height": 844}); shot("/v3/consume", "deck-phone")
