from uc6 import BASE, Person
with Person("anita") as p:
    pg = p.page
    pg.goto(BASE + "/v3/thread/t-a6f00be2bb"); pg.wait_for_timeout(3000)
    w = lambda: round(pg.locator(".v3-talk").bounding_box()["width"])
    b = pg.locator(".v3-split").bounding_box(); before = w()
    pg.mouse.move(b["x"] + 7, b["y"] + 100); pg.mouse.down(); pg.mouse.move(b["x"] + 260, b["y"] + 100, steps=8); pg.mouse.up()
    after = w(); pg.reload(); pg.wait_for_timeout(3000)
    print("conversation width", before, "-> after drag", after, "-> after reload", w())
    pg.locator(".v3-split").focus(); pg.keyboard.press("ArrowLeft"); pg.keyboard.press("ArrowLeft"); print("after two left-arrow presses", w())
    pg.locator(".v3-split").dblclick(); pg.wait_for_timeout(300); print("after double-click reset", w())
    p.shot("/v3/thread/t-a6f00be2bb", "uat-split")
