"""Capture every 3.0 screen as Anita (full page) into UC6_SHOTS/gallery."""
from pathlib import Path
from uc6 import BASE, SHOTS, Person
OUT = Path(SHOTS) / "gallery"; OUT.mkdir(parents=True, exist_ok=True)
import os
TID = os.environ.get('V3_TID', 't-4dda9fccda')
with Person("anita") as p:
    pg = p.page
    def shot(path, name, then=None, wait=3500):
        pg.goto(BASE + path); pg.wait_for_timeout(wait)
        if then:
            try:
                then(); pg.wait_for_timeout(1200)
            except Exception as e:  # a click that finds nothing still leaves the page captured
                print("  (no click on", name, ":", str(e).splitlines()[0][:80], ")")
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True); print(name)
    def click(text):
        return lambda: pg.get_by_role("button", name=text).first.click(timeout=4000)
    shot("/v3/desk", "01-desk")
    shot("/v3/action", "02-action")
    shot("/v3/action", "03-action-selected", then=lambda: pg.locator(".v3-card, article, li").filter(has_text="files").first.click(timeout=4000))
    shot("/v3/build", "04-build-board")
    shot(f"/v3/build/{TID}", "05-build-usecase")
    shot(f"/v3/build/{TID}", "06-build-node-open", then=lambda: pg.locator("svg g, svg rect").filter(has_text="Who reads").first.click(timeout=4000))
    shot("/v3/consume", "07-consume")
    shot("/v3/knowledge", "08-knowledge-map")
    shot("/v3/knowledge", "09-knowledge-node", then=lambda: pg.locator("svg g").filter(has_text="Entity B").first.click(timeout=4000))
    shot("/v3/knowledge", "10-knowledge-processes", then=click("Processes"))
    shot("/v3/knowledge", "11-knowledge-things", then=click("Things we track"))
    shot("/v3/knowledge/skills", "12-skills-library")
    shot("/v3/knowledge/skills", "13-skill-open", then=lambda: pg.locator("tbody tr, li, button").filter(has_text="answer").first.click(timeout=4000))
    shot("/v3/welcome", "14-welcome")
    shot("/v3/start", "15-start")
    pg.set_viewport_size({"width": 390, "height": 844})
    shot("/v3/consume", "16-consume-phone")
    shot("/v3/desk", "17-desk-phone")
