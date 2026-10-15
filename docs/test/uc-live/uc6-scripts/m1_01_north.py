"""Month 1, step 1: Mei Chen tells North what she needs, typed into the Intent screen (real UI: textarea + Start, then the chat box)."""
import json
import sys
import time
from uc6 import Person, dump

MSGS = [
    "I need a monthly view of whether Evergreen Office can meet the capital calls on its private funds. Readers: me, Raj Patel and Sofia Reyes. Decision: whether to fund a call from Entity B, and when.",
    "The figures: available cash by entity (Evergreen Holdings EG-HOLD, Evergreen Family Trust EG-TRUST, Entity B EG-B), calls due in the next 30 days, calls due in 31 to 60 days, cash after those calls, uncalled commitment by fund, and any call not yet confirmed.",
    "Cash is the administrator's closing cash on the last cash day of the month. The bank statements are a timing check, not the figure.",
    "A call is due when its due date falls within 30 days of the as-at date. A notice is noticed until the office confirms it; only confirmed calls count as called. A manager's call plan in the commitments file is an estimate and is never due.",
    "A distribution is money coming in, never a call. An amended notice replaces the earlier amount with the same reference; count it once.",
    "Sources: (1) the commitments schedule, an Excel workbook sent at month end; (2) the bank cash files, one CSV per entity, daily, sent each month; (3) the administrator's cash report, a CSV, the official figure; (4) the capital call and distribution notices, PDFs from the managers; (5) the notice receipt log, a CSV that says when each notice reached us. All arrive by upload each month.",
    "Readers see the view each month on the fifth business day. Raj approves the 30-day view. Today we do it by hand in a spreadsheet from the administrator report and the notices; last month Entity B showed no call due.",
    "That is everything. Please draft the intent and the process map.",
]
start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
with Person("mei") as p:
    pg = p.page
    st, o = p.get("/api/v1/intents/open")
    iid = o.get("id")
    log = []
    for i, m in enumerate(MSGS[start:], start):
        if not iid:
            pg.goto("http://127.0.0.1:8811/centre/intent")
            pg.wait_for_timeout(2500)
            pg.locator("textarea").first.fill(m)
            pg.get_by_role("button", name="Start").click()
        else:
            if f"/centre/intent/{iid}" not in pg.url:
                pg.goto(f"http://127.0.0.1:8811/centre/intent/{iid}")
                pg.wait_for_timeout(3000)
            box = pg.locator("textarea").last
            box.fill(m)
            box.press("Enter")
        t0 = time.time()
        # wait until North answered (the thread grows by a North turn)
        for _ in range(120):
            pg.wait_for_timeout(2000)
            if not iid:
                st, o = p.get("/api/v1/intents/open")
                iid = o.get("id")
                if not iid:
                    continue
            st, c = p.get(f"/api/v1/intents/{iid}/chat")
            turns = c.get("turns", []) if isinstance(c, dict) else []
            mine = sum(1 for t in turns if t.get("by") == "person")
            if turns and turns[-1].get("by") != "person" and mine >= i + 1:
                break
        reply = turns[-1] if turns else {}
        log.append({"n": i + 1, "typed": m, "north": json.dumps(reply, default=str)[:700], "secs": round(time.time() - t0)})
        print(i + 1, round(time.time() - t0), json.dumps(reply, default=str)[:500].encode("ascii", "replace").decode())
    dump("m1_north_turns", log)
    st, c = p.get(f"/api/v1/intents/{iid}/chat")
    dump("m1_north_chat", c)
    print("IID", iid)
    p.shot(f"/centre/intent/{iid}", "jul-01-mei-intent-drafted", 5000)
