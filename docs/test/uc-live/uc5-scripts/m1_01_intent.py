"""M1-05: Mei (business owner) tells North what she needs, typed into Build > New project, then Start."""
from uc5lib import W
TEXT = ("Monthly limit monitoring for Evergreen Office. Each month, when the administrator's month-end positions arrive, check the portfolios "
        "EG-LIQUID, EG-B-OPS and EG-FUNDS against the signed investment limits. For each limit show the exposure as a percentage of its portfolio, "
        "the maximum, the headroom in percentage points, and whether it is inside, in breach, or in breach with stale inputs. Show each breach as "
        "real or stale. List instruments with no asset class as questions. Readers: Sofia Reyes (risk owner), Mei Chen, and Daniel Foo (CIO, who "
        "signs). The work is ready by the 5th business day. Sources: the administrator month-end positions workbook (sheets Positions and Latest "
        "statements) and the signed limits workbook (sheet Signed limits), both uploaded by hand each month.")
w = W("mei"); w.go("/centre/build/new")
w.pg.fill("textarea[aria-label='What you would like to build']", TEXT)
w.pg.get_by_role("button", name="Start").click()
for i in range(40):
    w.pg.wait_for_timeout(5000)
    if "/build/new" not in w.pg.url and "North" in w.text() and "Thinking" not in w.text():
        break
w.pg.wait_for_timeout(5000)
print(w.pg.url); print(w.text()[:4000])
print("BUTTONS:", [b.inner_text()[:40] for b in w.pg.query_selector_all("button") if b.is_visible()])
print("INPUTS:", [(e.evaluate("e=>e.tagName"), e.get_attribute("aria-label")) for e in w.pg.query_selector_all("input,textarea") if e.is_visible()])
w.shot("jul-01-mei-intent-first-reply")
