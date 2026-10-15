"""Month 1, steps 2-3: Mei settles the open point and fixes units on the intent (the sign page's own edit route),
Daniel signs (sign page, the confirm box + Sign), Mei sends it to Build and hands the project over to Leo Park."""
import json
from uc6 import Person, dump

IID = "ini-8b228521c012e12c16c7d3c8939df05c"
with Person("mei") as m:
    st, props = m.get(f"/api/v1/intents/{IID}/proposals")  # the ChangeBar's Accept on each change North proposed
    for pr in props.get("pending", []):
        print("accept proposal", pr["id"], m.post(f"/api/v1/intents/{IID}/proposals/{pr['id']}/accept")[0])
    st, sow = m.get(f"/api/v1/intents/{IID}/sow")
    v = sow["version"]
    edits = [{"section": "unclear", "index": i, "field": "answer", "value": "Settled in the chat: confirmed calls, USD, by entity, our definition."}
             for i, u in enumerate(sow.get("unclear") or []) if not u.get("settled")] + [{"section": "unclear", "index": 0, "field": "answer", "value": "No. Use our definition: confirmed calls with due date within 30 days of the as-at date, in USD, by entity."},
             {"section": "kpis", "index": 0, "field": "unit", "value": "USD"},
             {"section": "kpis", "index": 1, "field": "unit", "value": "USD"},
             # North said it removed K03 but did not; the sign page has no delete, so Mei turns it into a figure she did ask for
             {"section": "kpis", "index": 2, "field": "name", "value": "Cash after calls by entity"},
             {"section": "kpis", "index": 2, "field": "definition", "value": "Administrator closing cash on the as-at date minus calls due within 30 days (confirmed only, and all noticed), by entity"},
             {"section": "kpis", "index": 2, "field": "unit", "value": "USD"},
             # North was told these in the chat but left the two template sections empty; Mei types them on the intent page
             {"section": "template_fields", "field": "result", "value": "One page per month: a card per entity (administrator cash, calls due in 30 days, calls due in 31 to 60 days, cash after confirmed calls, cash after all noticed calls), a table of commitment, called and uncalled by fund, and a list of calls not confirmed yet."},
             {"section": "template_fields", "field": "success", "value": "The figures match Mei's hand spreadsheet for July to September, and Raj approves October without opening the spreadsheet."}]
    for e in edits:
        st, sow = m.put(f"/api/v1/intents/{IID}/sow", {**e, "version": sow.get("version", v)})
        print("edit", e["section"], e["field"], st, (sow.get("message") if isinstance(sow, dict) else sow) if st != 200 else "ok")
    m.shot(f"/centre/intent/{IID}/sow", "jul-01-mei-intent-ready", 4000)
with Person("daniel") as d:
    d.shot("/centre/action", "jul-02-daniel-action-intent-to-sign")
    d.shot(f"/centre/intent/{IID}/sign", "jul-02-daniel-sign-page", 4000)
    st, sow = d.get(f"/api/v1/intents/{IID}/sow")
    st, out = d.post(f"/api/v1/intents/{IID}/sow/sign", {"confirm": True, "version": sow["version"]})
    print("sign", st, json.dumps({k: out.get(k) for k in ("state", "version", "signature")} if isinstance(out, dict) else out, default=str)[:600])
    d.shot(f"/centre/intent/{IID}/sow", "jul-02-daniel-intent-signed", 4000)
with Person("mei") as m:
    st, out = m.post(f"/api/v1/intents/{IID}/send-to-build")
    print("send-to-build", st, json.dumps(out)[:300])
    st, pr = m.get(f"/api/v1/intents/{IID}/project")
    pid = (pr.get("project") or pr).get("id") if isinstance(pr, dict) else None
    print("project", st, pid)
    st, out = m.post(f"/api/v1/projects/{pid}/handover", {"to": "Leo Park", "due": "2026-08-07",
                                                          "message": "Leo, July first. The Excel and CSVs come by upload; the notices are PDFs. Check against my July figures."})
    print("handover", st, json.dumps(out, default=str)[:400])
    dump("m1_project", {"pid": pid, "iid": IID})
with Person("daniel") as d:
    st, out = d.post(f"/api/v1/projects/{pid}/handover", {"to": "Leo Park", "due": "2026-08-07",
                                                          "message": "Leo, July first. The Excel and CSVs come by upload; the notices are PDFs. Check against Mei's July figures."})
    print("handover by Daniel", st, json.dumps(out, default=str)[:400])
with Person("leo") as l:
    l.shot("/centre/action", "jul-03-leo-action-handover")
