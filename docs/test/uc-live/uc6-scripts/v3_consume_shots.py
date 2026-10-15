import json, time
from pathlib import Path
from uc6 import BASE, SHOTS, Person
OUT = Path(SHOTS) / "gallery"; OUT.mkdir(parents=True, exist_ok=True)
with Person("anita") as p:
    t = time.time(); st, a = p.post("/api/v3/ask", {"text": "What is our cash by entity today?"}); print("ask", st, round(time.time() - t, 2), "s |", a.get("answer", "")[:160], "| cached", a.get("cached"))
    st, c = p.get("/api/v3/consume"); print("figures", [(f["label"], f["value"]) for f in c.get("figures", [])][:6])
    pg = p.page
    pg.goto(BASE + "/v3/consume"); pg.wait_for_timeout(4500); pg.screenshot(path=str(OUT / "c1-consume-desktop.png"), full_page=True)
    pg.get_by_role("button", name="Which entity has the least cash?").first.click(timeout=5000); pg.wait_for_timeout(3000)
    pg.screenshot(path=str(OUT / "c2-consume-followup.png"), full_page=True)
    pg.set_viewport_size({"width": 390, "height": 844}); pg.goto(BASE + "/v3/consume"); pg.wait_for_timeout(4500)
    pg.screenshot(path=str(OUT / "c3-consume-phone.png"), full_page=True); print("shots done")
