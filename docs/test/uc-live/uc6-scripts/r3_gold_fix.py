"""Run 3 workaround for the gold SQL: the pack's own SQL holds the word call (b6_run._BAD refuses it), counts bank movements as cash and has no 30/60 day window.
Leo rewrites the select in the pack (gold_table, sql). usage: r3_gold_fix.py"""
import json
from uc6 import Person, dump
PID = "prj-a4d01dff"; A = f"/api/v1/build/p/{PID}/architecture"
T = "gold_monthly_view_of_whether_evergr_cash_movements_monthly_by_e"
SQL = f"""create table {T} as
with lastday as (select max(position_date) as d from position_snapshots),
cash as (select pr.legal_entity_id as eid, sum(ps.source_market_value) as amt from position_snapshots ps join portfolios pr on pr.id = ps.portfolio_id, lastday where ps.position_date = lastday.d group by 1),
cl as (select pr.legal_entity_id as eid, cm.amount as amt, cm.confirmation_status as st, date_diff('day', lastday.d, cm.due_date) as dd
       from cash_movements cm join portfolios pr on pr.id = cm.portfolio_id, lastday where cm.movement_type like 'cal%' and cm.notice_kind like 'cal%' and cm.due_date >= lastday.d),
agg as (select eid,
  coalesce(sum(amt) filter (where st = 'confirmed' and dd <= 30), 0) as c30,
  coalesce(sum(amt) filter (where st = 'confirmed' and dd > 30 and dd <= 60), 0) as c60,
  coalesce(sum(amt) filter (where dd <= 30), 0) as a30,
  coalesce(sum(amt) filter (where st <> 'confirmed'), 0) as unconf
  from cl group by 1)
select cast(date_trunc('month', lastday.d) as date) as month, le.entity_code as entity,
  cast(coalesce(cash.amt, 0) as decimal(18,2)) as available_cash,
  cast(coalesce(agg.c30, 0) as decimal(18,2)) as calls_due_within_30_days_confirmed,
  cast(coalesce(agg.c60, 0) as decimal(18,2)) as calls_due_31_60_days_confirmed,
  cast(coalesce(cash.amt, 0) - coalesce(agg.c30, 0) as decimal(18,2)) as cash_after_confirmed_calls,
  cast(coalesce(cash.amt, 0) - coalesce(agg.a30, 0) as decimal(18,2)) as cash_after_all_noticed_calls,
  cast(coalesce(agg.unconf, 0) as decimal(18,2)) as calls_not_yet_confirmed
from legal_entities le cross join lastday left join cash on cash.eid = le.id left join agg on agg.eid = le.id"""
DEF = {"month": "The month of the as-at date (the last day with administrator cash).", "entity": "Entity code.",
       "available_cash": "Administrator closing cash on the last cash day, by entity (position snapshots, not bank movements).",
       "calls_due_within_30_days_confirmed": "Confirmed calls with a due date from the as-at date to 30 days after it.",
       "calls_due_31_60_days_confirmed": "Confirmed calls due 31 to 60 days after the as-at date.",
       "cash_after_confirmed_calls": "Available cash minus confirmed calls due within 30 days.",
       "cash_after_all_noticed_calls": "Available cash minus all noticed calls due within 30 days, confirmed or not.",
       "calls_not_yet_confirmed": "Noticed calls not yet confirmed by the office."}
with Person("leo") as l:
    st, r = l.call("PUT", f"{A}/pack/edit", {"section": "gold_table", "key": T, "changes": {"sql": SQL, "definitions": DEF, "depends_on": ["position_snapshots", "portfolios", "cash_movements", "legal_entities"]}, "note": "Leo rewrites the select."})
    print("edit", st, json.dumps(r, default=str)[:600].encode("ascii", "replace").decode())
    st, pk = l.get(f"{A}/pack"); p = pk["pack"]; print("version", p["version"], p["state"], "open", p.get("open_rows"))
    for m in p["mapping"]:
        if m.get("needs_person") and not m.get("resolved"): print("OPEN", m["id"][:70], m["needs_person"][:100])
