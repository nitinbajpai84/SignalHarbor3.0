"""Mei Chen talks to North. First call: python north.py start "<brief>"; later: python north.py say "<answer>" (LOOK = only read)."""
from lib import *
mode, msg = sys.argv[1], sys.argv[2]
w = W("mei")
def wait():
    w.pg.wait_for_timeout(4000)
    for _ in range(100):
        if "North is thinking" not in w.text(): break
        w.pg.wait_for_timeout(3000)
    w.pg.wait_for_timeout(1500)
t0 = time.time()
if mode == "start":
    w.go("/centre/build/new", 3000)
    w.pg.locator("textarea").first.fill(msg); w.pg.get_by_role("button", name="Start").click()
    for _ in range(100):
        if "/new" not in w.pg.url: break
        w.pg.wait_for_timeout(3000)
    wait()
    st("intent_url", w.pg.url); print("URL", w.pg.url)
else:
    w.pg.goto(st("intent_url")); w.pg.wait_for_timeout(5000)
    acc = 0
    for _ in range(10):
        b = w.pg.get_by_role("button", name="Accept", exact=True)
        if not b.count(): break
        try: b.first.click(timeout=3000); w.pg.wait_for_timeout(1500); acc += 1
        except Exception: break
    print("accepted", acc)
    if msg != "LOOK":
        w.pg.locator("textarea").first.fill(msg); w.pg.get_by_role("button", name="Send", exact=True).click(); wait()
t = w.text(); j = t.rfind("North\n"); reply = t[j:j + 2500]
print(f"TURN {round(time.time()-t0)}s |", reply)
with open(ENV / "north_log.txt", "a", encoding="utf-8") as f: f.write(f"MEI: {msg}\nNORTH: {reply}\n---\n")
if len(sys.argv) > 3: w.shot(sys.argv[3])
print("BUTTONS", w.buttons()[-20:])
w.close()
