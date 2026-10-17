"""Figure recipes (sh_platform/v1/v3_recipes.py, assumptions A7 and A8): a common figure is built from its recipe, the same on every build; a design that reads a
table its figure must never read is refused; the tie-out runs on the copy; a model design that worked is kept and reused. Real: the recipes file, the plan
check, the warehouse of the seeded Evergreen office. Stubbed: the model."""
from types import SimpleNamespace

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b10_design as D
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_skills as SK
from sh_platform.v1 import wh
from tools import seed_evergreen as EG

NW = {"name": "Net worth", "definition": "Sum of positions value for each portfolio", "unit": "USD", "period": "monthly", "benchmark_by": ["portfolio"]}


@pytest.fixture()
def plane(tmp_path):
    EG.company(tmp_path)
    p = PlaneStore(str(tmp_path)).plane_for("evergreen").ensure()
    wh.use(p)
    _load(p)
    return p


def _load(p):
    """One entity, two portfolios, one fund: Liquid holds 41.2m at 30 September (its carried-forward duplicate is not added again), Growth holds 6.4m."""
    with wh.connect(p) as con:
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values ('00000000-0000-0000-0000-00000000000e', '00000000-0000-0000-0000-000000000001', 'E', 'Entity A', 'USD')")
        for pid, name in (("00000000-0000-0000-0000-0000000000a1", "Evergreen Liquid portfolio"), ("00000000-0000-0000-0000-0000000000a2", "Evergreen Growth portfolio")):
            con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?, '00000000-0000-0000-0000-000000000001', "
                        "'00000000-0000-0000-0000-00000000000e', ?, ?, 'USD')", [pid, name[:12], name])
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, currency, created_at) values ('00000000-0000-0000-0000-0000000000f1', "
                    "'00000000-0000-0000-0000-000000000001', 'Fund One', 'liquid_fund', 'USD', now())")
        rows = [("a1", 41200000, "Final", 1), ("a1", 41200000, "Carried forward", 2), ("a2", 6400000, "Final", 3), ("a2", 5000000, "Final", 4)]
        for portfolio, v, status, n in rows:
            con.execute("insert into position_snapshots (id, organization_id, source_record_id, portfolio_id, instrument_id, position_date, as_of_at, received_at, recorded_at, "
                        "source_market_value, currency, view_type, data_status, supersedes_position_id) values (?, '00000000-0000-0000-0000-000000000001', "
                        "'00000000-0000-0000-0000-0000000000b1', ?, '00000000-0000-0000-0000-0000000000f1', '2026-09-30', now(), now(), now() + to_seconds(?), ?, 'USD', 'operational', ?, ?)",
                        [f"00000000-0000-0000-0000-00000000010{n}", f"00000000-0000-0000-0000-0000000000{portfolio}", n, v, status,
                         "00000000-0000-0000-0000-000000000104" if n == 3 else None])  # the 6.4m snapshot is superseded by the 5.0m one


def _plan():
    return {"tables": [], "project_slug": "t", "notes": []}


def _build(plane, kpi=NW):
    plan, notes = _plan(), []
    left = R.place(plane, None, "prj-1", [kpi], "t", {"dims": []}, plan, notes)
    return left, plan, notes


def _run(plane, plan):
    with wh.connect(plane) as con:
        for t in plan["tables"]:
            con.execute(f"drop table if exists {t['name']}")
            con.execute(t["sql"])
        t = plan["tables"][0]
        return con.execute(f"select sum({R.recipe('net_worth')['measure']}) from {t['name']}").fetchone()[0]


def test_a_figure_is_matched_to_its_recipe_by_name_and_words_and_a_count_is_not_the_figure():
    names = ["Net worth", "Net worth by portfolio", "NAV", "Cash break", "Cash balance per entity", "Statements missing by fund", "Single-issuer concentration",
             "Change since the issued report", "FX forward confirmation variance", "Allocation drift", "Breaks over 5,000"]
    ids = {n: (R.match({"name": n}) or {}).get("id") for n in names}
    assert ids == {"Net worth": "net_worth", "Net worth by portfolio": "net_worth", "NAV": "net_worth", "Cash break": "cash_break", "Cash balance per entity": "cash_by_entity",
                   "Statements missing by fund": "missing_statements", "Single-issuer concentration": "concentration", "Change since the issued report": "change_since_report",
                   "FX forward confirmation variance": "fx_confirmation_variance", "Allocation drift": "drift_vs_target", "Breaks over 5,000": None}
    bad = [r["id"] for r in R.recipes() if not (r.get("may_read") and r.get("never_read") is not None and r.get("formula") and r.get("grain") and r["sql"])]
    assert not bad, f"malformed pack recipes (for the domain fixers): {bad}"


def test_a_figure_with_a_recipe_is_placed_from_it_and_loses_its_could_not_place_note(plane):
    plan, notes = _plan(), ["Span could not place the KPI 'Net worth' on a table that holds data."]
    left = R.place(plane, None, "prj-1", [NW, {"name": "Cash drag"}], "t", {"dims": []}, plan, notes)
    assert [k["name"] for k in left] == ["Cash drag"]  # the model is asked only for the figure with no recipe
    t = plan["tables"][0]
    assert t["name"] == "gold_t_net_worth_by_portfolio" and t["kpis"] == ["Net worth"] and t["purpose"].startswith("Recipe net_worth:")
    assert set(t["depends_on"]) == {"position_snapshots", "portfolios", "legal_entities", "instruments", "bank_accounts"} and not notes  # cash counted once (holdings)


def test_a_design_that_reads_a_table_the_figure_must_never_read_is_refused_with_the_tables_it_may_read():
    r = R.recipe("net_worth")
    why = R.refusal(r, "create table g as select sum(commitment_amount) as net_worth from commitments")
    assert why and "commitments" in why and "position_snapshots" in why and "must never read" in why
    assert R.refusal(r, "create table g as with p as (select * from position_snapshots) select sum(source_market_value) from p join portfolios using (id)") is None
    notes = []
    kept = R.allowed([{"name": "gold_t_a", "kpis": ["Net worth"], "sql": "create table gold_t_a as select sum(commitment_amount) from commitments"},
                      {"name": "gold_t_b", "kpis": ["Cash drag"], "sql": "create table gold_t_b as select 1 from commitments"}], notes)
    assert [g["name"] for g in kept] == ["gold_t_b"] and notes[0].startswith("Span dropped gold_t_a: Net worth reads only")


def test_the_tie_out_passes_on_the_rows_and_fails_when_the_ready_table_is_wrong(plane):
    left, plan, _ = _build(plane)
    assert left == []
    name = plan["tables"][0]["name"]
    _run(plane, plan)
    with wh.connect(plane) as con:
        ok = R.tie_out(con, R.recipe("net_worth"), name)
        assert ok["ok"] and ok["a"] == ok["b"] and ok["a"] > 0 and "sum of the position snapshots" in ok["label"]
        con.execute(f"update {name} set net_worth = net_worth + 1000 where rowid = 0")
        bad = R.tie_out(con, R.recipe("net_worth"), name)
        assert not bad["ok"] and bad["a"] - bad["b"] == 1000
        assert R.tie_out(con, R.recipe("net_worth"), "no_such_table") is None  # not built on the copy: no line, the figure's own check says so


def test_a_model_design_that_worked_is_saved_and_the_next_build_reuses_it_word_for_word(plane):
    sql = ("create table gold_old_slug_nw as select p.portfolio_name as portfolio, sum(s.source_market_value) as net_worth "
           "from position_snapshots as s join portfolios as p on p.id = s.portfolio_id group by all")
    g = {"name": "gold_old_slug_nw", "sql": sql, "depends_on": ["position_snapshots", "portfolios"], "grain": "Portfolio", "keys": ["portfolio"], "purpose": "Net worth"}
    figure = {"name": "Cash drag", "definition": "x"}
    assert R.saved(plane, "Cash drag") is None
    assert R.remember(plane, "Cash drag", g, "gold_old_slug_") and not R.remember(plane, "Cash drag", g, "gold_old_slug_")  # saved once
    assert SK.read(plane, "office.design-cash-drag")["status"] == "in_use"
    plan, notes = {**_plan(), "project_slug": "new_slug"}, ["Span could not place the KPI 'Cash drag' on a table that holds data."]
    left = R.place(plane, None, "prj-1", [figure], "new_slug", {"dims": []}, plan, notes)
    assert left == [] and plan["tables"][0]["name"] == "gold_new_slug_nw"
    assert plan["tables"][0]["sql"] == " ".join(sql.split()).replace("gold_old_slug_nw", "gold_new_slug_nw")  # the same words, the new name
    assert plan["tables"][0]["purpose"].startswith("Saved design Cash drag")


def test_the_same_figure_built_twice_on_the_same_data_gives_the_same_sql_and_the_same_number(plane):
    _, p1, _ = _build(plane)
    _, p2, _ = _build(plane)
    assert p1["tables"][0]["sql"] == p2["tables"][0]["sql"]
    assert _run(plane, p1) == _run(plane, p2) and _run(plane, p1) > 0


def test_the_design_call_runs_at_temperature_zero_is_kept_by_its_input_and_asks_the_model_again_before_the_rules(plane, monkeypatch):
    from sh_platform.agents import loop
    from sh_platform.egress.providers import TEMPERATURE
    seen = []
    replies = iter([RuntimeError("timeout"), SimpleNamespace(status="done", text='{"gold": [], "silver": []}')])

    def fake(*a, **kw):
        seen.append(TEMPERATURE.get())
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(loop, "run_agent", fake)
    ctx = {"kpis": [], "model": {}, "goal": "g"}
    assert D._ask_design(plane, object(), None, "prj-1", ctx) == {"gold": [], "silver": []}
    assert seen == [0, 0] and TEMPERATURE.get() is None  # asked again, not the rules; both calls at temperature 0
    assert D._ask_design(plane, object(), None, "prj-1", ctx) == {"gold": [], "silver": []} and len(seen) == 2  # the same input: the kept reply, no call
    monkeypatch.setattr(loop, "run_agent", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    assert D._ask_design(plane, object(), None, "prj-1", {**ctx, "goal": "other"}) is None  # two failed calls: the rules take over


def test_a_figure_with_a_recipe_is_built_from_it_also_when_the_rules_table_already_covers_it():
    rules = [{"name": "gold_p_net_worth_entity_monthly", "purpose": "Net worth by entity", "kpis": []}]
    mine = [{"name": "gold_p_net_worth_by_portfolio", "purpose": "Recipe net_worth: Net worth from the pack's recipe", "kpis": ["Net worth"]}]
    assert R.stale(NW, rules) and not R.stale(NW, mine + rules) and not R.stale({"name": "Cash drag"}, rules)


# ---- Decision 1: a figure is bound to its recipe by meaning, once, and every later step reads the binding (round 7) ------------------------------

BREAKS = [{"name": "Cash break amount", "definition": "Amount over 5,000 flagged as a break with likely cause", "formula": "Cash balance - 5,000"},
          {"name": "Variance over 5,000", "definition": "Administrator cash change against the bank and desk movements"},
          {"name": "Admin vs desk gap", "definition": "The administrator's change in cash less the movements our desk recorded"}]


def _reply(monkeypatch, bindings, seen):
    from sh_platform.agents import loop
    from sh_platform.egress.providers import TEMPERATURE

    def fake(*a, **kw):
        from sh_platform.egress.rows import json_findings
        assert json_findings(__import__("json").dumps(a[6]))[0] is None  # the egress row guard lets the question out (c7: lists of records were refused)
        seen.append(TEMPERATURE.get())
        return SimpleNamespace(status="done", text=__import__("json").dumps({"bindings": bindings}))
    monkeypatch.setattr(loop, "run_agent", fake)


def test_three_north_names_for_one_figure_bind_to_the_same_recipe_by_meaning_and_a_count_does_not(plane, monkeypatch):
    seen = []
    kpis = [dict(k) for k in BREAKS] + [{"name": "Number of breaks", "definition": "How many entities are over 5,000"}]
    _reply(monkeypatch, [{"figure": 0, "recipe": "cash_break", "why": "The administrator's change in cash against the movements."},
                         {"figure": 1, "recipe": "none", "why": "A count of breaks is not the break."}], seen)  # only what the rules left goes to the model
    assert R.bind(plane, object(), kpis, "Every morning I check cash for each entity", [{"name": "Administrator cash", "holds": "cash per entity"}])
    assert [k["built_from"] for k in kpis] == ["cash_break", "cash_break", "cash_break", ""] and seen == [0]  # one typed question, temperature 0
    assert [k["built_from_by"] for k in kpis] == [R.RULES, R.RULES, R.SPAN, R.RULES] and kpis[2]["built_from_why"]
    assert not R.bind(plane, object(), kpis) and len(seen) == 1  # bound once: no second question
    again = [dict(k) for k in BREAKS] + [{"name": "Number of breaks", "definition": "How many entities are over 5,000"}]
    R.bind(plane, object(), again, "Every morning I check cash for each entity", [{"name": "Administrator cash", "holds": "cash per entity"}])
    assert [k["built_from"] for k in again] == [k["built_from"] for k in kpis] and len(seen) == 1  # the same brief: the kept reply, no call
    rules = [dict(k) for k in BREAKS]
    R.bind(plane, None, rules)  # no model: the rules' first pass (the name, then the words of the definition) miss the third, which only the meaning binds
    assert [k["built_from"] for k in rules] == ["cash_break", "cash_break", ""] and {k["built_from_by"] for k in rules} == {R.RULES}
    from sh_platform.v1 import v3_harbor as H
    line = next(l for g in H.doc({"kpis": kpis}) for l in g["lines"] if l["field"] == "built_from")
    assert line["label"] == "Built from" and line["value"] == "Cash break recipe (suggested)" and line["suggested"]


def test_the_binding_survives_a_rebuild_and_is_never_matched_again_by_name(plane):
    k = {"name": "Admin vs desk gap", "definition": "x", "built_from": "cash_break", "built_from_by": "Grace Ong", "built_from_confirmed": "Grace Ong"}
    k = __import__("json").loads(__import__("json").dumps(k))  # as stored on the brief and read back
    _, p1, _ = _build(plane, k)
    _, p2, _ = _build(plane, k)  # the rebuild
    assert p1["tables"][0]["sql"] == p2["tables"][0]["sql"] and p1["tables"][0]["purpose"].startswith("Recipe cash_break:")
    assert not R.bind(plane, None, [k]) and k["built_from"] == "cash_break"  # a confirmed binding is never re-matched
    unbound = {**NW, "built_from": ""}  # the person said none: the name "Net worth" is not matched again
    left, plan, _ = _build(plane, unbound)
    assert left == [unbound] and plan["tables"] == [] and R.bound(unbound) is None
    assert R.stale(k, [{"name": "gold_t_rules", "purpose": "rules", "kpis": []}])  # a table the recipe did not build is rebuilt from the binding
    assert R.shown(k) == "Cash break recipe (confirmed by Grace Ong)"


def test_a_failed_tie_out_holds_the_figure_and_the_answer_says_not_available(plane, monkeypatch):
    from sh_platform.v1 import v3_figures as F, talk
    _, plan, _ = _build(plane)
    _run(plane, plan)
    g = plan["tables"][0]
    with wh.connect(plane) as con:
        con.execute(f"update {g['name']} set net_worth = net_worth + 1000 where rowid = 0")
        assert R.needs(con, R.recipe("cash_break"))  # no cash movements: a cash break would be held too
    th = {"id": "t-1", "pid": "prj-1", "iid": None, "figures": [{"kpi": "Net worth", "table": g["name"], "rows": 1, "ok": True, "reason": ""}],
          "exceptions": [{"title": "How often does Fund A send statements?", "text": "a question"}]}
    x = SimpleNamespace(th=th, plane=plane, api=lambda *a, **kw: {"pack": {"target": {"gold": [g]}}})
    d = R.finish(x, {"checks": [{"label": "Net worth", "ok": True, "value": "1 rows"}]})
    assert R.held(th, "Net worth") and not th["figures"][0]["ok"] and "Does not tie out" in [c["value"] for c in d["checks"]]
    assert d["checks"][0]["value"].startswith("Held") and "a question" not in th["figures"][0]["reason"]  # not loaded lists files only
    monkeypatch.setattr(F, "kpis_of", lambda *a: [NW])
    monkeypatch.setattr(talk, "reachable", lambda *a: ([{"id": "prj-1"}], None))
    monkeypatch.setattr(F, "report_total", lambda *a: None)
    monkeypatch.setattr(F, "missing_statements", lambda *a: None)
    got = F._answer(plane, None, "What is our net worth?", "prj-1", th)
    assert got["answer"].startswith("Not available yet: Net worth:") and got["figure"] is None and "41" not in got["answer"]


def test_a_recipe_the_question_names_that_no_figure_is_bound_to_is_added_as_a_suggested_figure(plane, monkeypatch):
    seen = []
    kpis = [{"name": "Matches count", "definition": "Trades where desk equals administrator", "period": "daily", "owner": "Sam Lee"},
            {"name": "Mismatches total amount", "definition": "Sum of absolute differences for mismatched trades", "period": "daily", "owner": "Sam Lee"}]
    _reply(monkeypatch, [{"figure": 0, "recipe": "none", "why": "A count."}, {"figure": 1, "recipe": "none", "why": "Trades against the administrator."}], seen)
    R.bind(plane, object(), kpis, "Match the FX forward confirmations against our own record: by how much do they differ?")
    assert [k["built_from"] for k in kpis] == ["", "", "fx_confirmation_variance"] and kpis[2]["name"] == "FX forward confirmation variance"  # net worth: not named
    assert kpis[2]["pack_suggested"] and kpis[2]["owner"] == "Sam Lee" and kpis[2]["code"] == "K03" and len(seen) == 1


def test_recipes_load_from_the_domain_folder_stubs_are_skipped_and_the_old_file_is_still_read(tmp_path, monkeypatch):
    from sh_platform.v1 import e0a_catalogue as C
    built = {r["id"] for r in R.recipes()}
    assert built >= {"net_worth", "cash_by_entity", "cash_break", "missing_statements", "concentration", "change_since_report", "fx_confirmation_variance"}
    assert {p.stem for p in R.DIR.glob("*.yaml")} >= {"_shared", "invest", "hold", "cash", "report", "operate", "family", "office"} and R.PACK.joinpath("signals").is_dir()
    stubs = R.stubs()
    assert stubs and not built & {s["id"] for s in stubs} and all(s["sql"] is None and s["formula"] and s["names"] and s["may_read"] for s in stubs)
    assert R.match({"name": "Cash forecast"}) is None and R.recipe("cash_forecast") is None  # a stub is never matched, bound or run
    core = {t["name"] for t in C._core()["tables"]}
    assert all(set(s["may_read"]) <= core for s in stubs), [(s["id"], set(s["may_read"]) - core) for s in stubs if not set(s["may_read"]) <= core]
    assert "positions" in R._file()["snippets"]  # the snippets of _shared.yaml reach every domain
    old = tmp_path / "recipes.yaml"  # the old single file keeps working; a recipe id that is also in the folder keeps the folder's
    old.write_text(yaml.safe_dump({"recipes": [{"id": "legacy_one", "label": "Legacy", "names": ["legacy"]}, {"id": "net_worth", "label": "Replaced"}]}), encoding="utf-8")
    monkeypatch.setattr(R, "FILE", old)
    R._file.cache_clear()
    try:
        assert R.recipe("legacy_one")["label"] == "Legacy" and R.recipe("net_worth")["label"] == "Net worth"
    finally:
        monkeypatch.undo()
        R._file.cache_clear()


def test_the_top_50_figures_bind_to_the_recipe_that_answers_their_key():
    """w4: figures of the family-office cards bind by their meaning (a tie on the name is read by the formula), never by the figure's id."""
    want = {"unfunded_after_call": "called_to_date", "fee_part_check": "call_fee_check", "sgd_to_convert": "fx_required", "call_vs_commitment_check": "called_to_date",
            "payments_on_hold": "bank_details_changed", "unclassified_holdings": "identifier_gaps", "networth_usd_sgd": "report_total_fx",
            "missing_statements": "statement_timeliness", "cash_break": "cash_difference_by_source", "uncalled_total": "called_to_date",
            "net_worth_after_debt": "net_worth_after_debt"}
    cards = yaml.safe_load(open("packs/family_office/1/use_cases_100.yaml", encoding="utf-8"))

    def figs(o):
        if isinstance(o, dict):
            if o.get("id") in want and "name" in o:
                yield o
            for v in o.values():
                yield from figs(v)
        elif isinstance(o, list):
            for v in o:
                yield from figs(v)
    got = {f["id"]: (R.match(f) or {}).get("id") for f in figs(cards)}
    assert got == want


# ---- live r1 (uc-001, uc-015, uc-023, uc-024, uc-028, uc-032): the figures North wrote in those threads, names and definitions as on the brief ----

R1_FIGURES = {
    "uc-015": [("Known obligations due", "Sum of current, unpaid approved obligations within each monthly bucket after notice supersession; converted with approved FX basis"),
               ("Cash availability", "Opening cash plus approved inflows minus known obligations, scenario\u2011only calls and reserve"),
               ("Funding headroom (six\u2011month)", "Minimum across six closing\u2011month headrooms of opening cash + approved inflows \u2013 known obligations \u2013 scenario\u2011only calls \u2013 proposed funding \u2013 reserve")],
    "uc-023": [("Allocation drift", "Difference between actual asset allocation and policy ranges."), ("Cash drag", "Cash holding as a percentage of total assets."),
               ("Fee ratio", "Total fees as a proportion of assets under management."), ("Liquidity runway", "Months of cash available to meet known calls and costs.")],
    "uc-024": [("Total items traced", "Count of auditor numbers successfully linked to a source file and page."),
               ("Missing trace count", "Count of auditor numbers for which no source file or page could be found.")],
    "uc-028": [("Allocation drift", "Current asset allocation versus policy target ranges"), ("Cash drag", "Cash held relative to total assets, indicating opportunity cost"),
               ("Liquidity runway", "Months of known cash outflows that can be covered by cash balances")],
    "uc-032": [("Policy\u2011band breach", "Asset\u2011class or manager value outside the limits set in the signed policy."), ("Old\u2011value alert", "Value that has not been refreshed for more than the allowed data\u2011age window.")],
    "uc-001": [("Allocation drift", "Difference between actual asset allocation and policy ranges."), ("Single\u2011issuer concentration", "Direct exposure to any single issuer as % of total assets.")],
}


def _r1(case):
    return [{"name": n, "definition": d, "period": "monthly"} for n, d in R1_FIGURES[case]]


def test_the_figures_north_wrote_in_the_r1_threads_bind_by_name_to_the_recipe_that_computes_them():
    """Live r1 class a: a figure with a recipe in the library was left unbound because the name North used was not one the recipe answered to. The names and
    definitions are the brief's own. A count is still not a recipe's amount (the rule of test_a_figure_is_matched...), so "Missing trace count" stays unbound."""
    got = {case: {k["name"]: (R.match(k) or {}).get("id") for k in _r1(case)} for case in R1_FIGURES}
    assert got == {
        "uc-015": {"Known obligations due": "allowance_due", "Cash availability": None, "Funding headroom (six\u2011month)": None},
        "uc-023": {"Allocation drift": "drift_vs_target", "Cash drag": None, "Fee ratio": None, "Liquidity runway": None},
        "uc-024": {"Total items traced": "trace_coverage", "Missing trace count": None},
        "uc-028": {"Allocation drift": "drift_vs_target", "Cash drag": None, "Liquidity runway": None},
        "uc-032": {"Policy\u2011band breach": "drift_vs_target", "Old\u2011value alert": "value_age_days"},
        "uc-001": {"Allocation drift": "drift_vs_target", "Single\u2011issuer concentration": "concentration"},
    }


def test_the_question_North_was_asked_adds_the_tie_out_and_the_intercompany_figure_when_the_brief_has_none():
    """uc-023 and uc-028: the brief's figures do not name the tie-out or the loans; the person's own words do, so the recipe is added as a suggested figure."""
    ask23 = ("Before the monthly report goes out I check it line by line. Compare each number on our issued report with the administrator's pack for the same month end, "
             "show me every line that does not agree and by how much, so I can explain it or correct it before Raj signs.")
    k23 = _r1("uc-023")
    R.bind(None, None, k23, ask23, [], ask23)
    added = [k for k in k23 if k.get("pack_suggested")]
    assert [(k["name"], k["built_from"]) for k in added] == [("Issued report against the administrator", "report_tie_out")]
    said28 = "We moved money between entities in August. Show me which entity lent to which, the amount, the date, the reference and whether the approval is on record."
    k28 = _r1("uc-028")
    R.bind(None, None, k28, "We moved money between entities in August.", [], said28)
    assert [(k["name"], k["built_from"]) for k in k28 if k.get("pack_suggested")] == [("Intercompany balance", "intercompany_balance")]


# Live run 2 (docs/v3/LIVE-R2-ANALYSIS.md, class a): the brief figures of the failing offices, by the exact names and definitions North wrote. Each must be
# bound to the recipe that computes it, by the rules alone (no model), so the same brief binds the same way on every build.
R2_FIGURES = [
    ("uc-015", "Cash availability", "Cash balance at month start minus total scheduled payments; must be non-negative.", "cash_by_entity"),
    ("uc-017", "Loan debt", "Total outstanding principal from the monthly loan statement.", "facility_headroom"),
    ("uc-026", "Statement variance", "Administrator value minus manager statement value", "statement_vs_admin"),
    ("uc-031", "Private\u2011market allocation", "Value of funded private-equity and venture-capital holdings divided by total assets", "allocation"),
    ("uc-034", "Minimum ticket vs policy limit", "Compare the manager's minimum ticket size with the maximum ticket allowed in policy.", "mandate_fit"),
    ("uc-034", "Ticket vs uncalled commitments", "Ticket amount expressed as a proportion of total uncalled commitments still available.", "called_to_date"),
    ("uc-038", "Quarterly private\u2011fund valuation reconciliation", "Previous quarter-end value plus calls less distributions gives the net change", "nav_rollforward"),
    ("uc-040", "Called amount (including latest call)", "Sum of all capital calls received to date, with the most recent call added", "called_to_date"),
    ("uc-040", "Latest value", "Latest reported NAV or market value of each private fund", "nav_rollforward"),
    ("uc-040", "Amendment status", "Whether the manager has amended the latest valuation", "change_since_report"),
    ("uc-040", "Unfunded amount", "Commitment less total called amount to date", "commitments_by_fund"),
    ("uc-043", "Daily liquid\u2011book profit\u2011and\u2011loss", "Change in the value of the liquid book since the start of the month, after accounting for cash flows from trading.", "liquid_pnl_mtd"),
    ("uc-044", "Quarter return", "Time\u2011weighted return for the quarter, net of fees, chained from month\u2011end values", "time_weighted_return"),
    ("uc-044", "Year\u2011to\u2011date return", "Time\u2011weighted return from start of year to current quarter\u2011end, net of fees", "time_weighted_return"),
    ("uc-044", "Benchmark return", "Return of the agreed benchmark over the same period (quarter or YTD)", "time_weighted_return"),
    ("uc-047", "Private\u2011market allocation", "Funded private equity and VC carrying value divided by total asset value; unfunded commitments shown separately.", "allocation"),
    ("uc-049", "Fee share of gain", "Manager fee paid divided by the manager's reported gain for the period", "fee_drag"),
    ("uc3", "Statement receipt status", "For each fund: expected month\u2011end statement date, actual receipt date, days late (actual \u2013 expected), and a boolean flag if never received.", "statement_timeliness"),
    ("uc-032", "Allocation drift", "Difference between actual asset allocation and policy target ranges.", "drift_vs_target"),
]


@pytest.mark.parametrize("uc,name,definition,want", R2_FIGURES, ids=[f"{u}-{n}"[:60] for u, n, _, _ in R2_FIGURES])
def test_a_live_r2_figure_binds_to_the_recipe_that_computes_it(uc, name, definition, want):
    r = R.match({"name": name, "definition": definition, "formula": definition})
    assert (r or {}).get("id") == want, uc


def test_a_question_adds_the_recipe_its_words_name_when_no_figure_does():
    # uc-031 / uc-045 / uc-047: the asked question names the recipe, not a figure of the brief
    assert [r["id"] for r in R.recipes() if R.asks("What share of the family is in each asset class, and in each entity?", r)] == ["allocation"]
    assert [r["id"] for r in R.recipes() if R.asks("Whether to sign off and issue the report: which sections are ready?", r)] == ["report_ready"]
    assert [r["id"] for r in R.recipes() if R.asks("Which matters to put to the committee and what to recommend?", r)] == ["pack_items"]


def test_bind_by_rules_gives_each_live_r2_figure_its_recipe_and_adds_the_asked_one():
    kpis = [{"name": n, "definition": d, "formula": d, "period": "monthly", "owner": "x", "status": "defined"} for _, n, d, _ in R2_FIGURES[:4]]
    R.bind(None, None, kpis, "What do we owe each family member this month, and do we have the cash?", [], "")
    assert [k["built_from"] for k in kpis] == ["cash_by_entity", "facility_headroom", "statement_vs_admin", "allocation"]
    assert all(k["built_from_by"] == R.RULES for k in kpis)
    qk: list[dict] = [{"name": "Net worth", "definition": "Total value of all family assets", "formula": "x", "period": "monthly", "owner": "x", "status": "defined"}]
    R.bind(None, None, qk, "What share of the family is in each asset class, and in each entity?", [], "")
    added = [k for k in qk if k.get("pack_suggested")]
    assert [(k["name"], k["built_from"]) for k in added] == [("Allocation by asset class and entity", "allocation")]


def test_a_definition_that_only_mentions_a_recipe_term_or_states_a_ratio_is_not_bound_by_it():
    # a forecast that mentions "known obligations" is not the allowances recipe; a percentage of cash is not the cash balance; a figure whose definition
    # leads with another term is not the recipe that term names
    assert R.match({"name": "Available cash after buffer", "definition": "Opening cash + approved inflows \u2013 known obligations \u2013 pending calls \u2013 $250,000 buffer"}) is None
    assert R.match({"name": "Cash drag", "definition": "Cash balance expressed as a percentage of total assets, indicating idle capital."}) is None
    assert R.match({"name": "Fee ratio", "definition": "Total fees paid (management, performance, custody) divided by total asset value."}) is None
    assert R.match({"name": "Assets", "definition": "Total assets under management reported in the questionnaire"}) is None


def test_the_age_of_the_latest_value_is_not_nav_rollforward():
    # uc-021 (score50 card 21): "latest value" is a name of nav_rollforward's latest reported NAV, but "the age of the latest value" is another figure
    k = {"name": "Figure Age of the latest value per fund", "definition": "As-of date less the latest valuation date, flagged above 90 days."}
    assert (R.match(k) or {}).get("id") != "nav_rollforward"


def test_a_fee_in_the_latest_call_is_not_the_called_to_date_recipe():
    # uc-040: "Fee in latest call" is read from the call notice's fee part, not the call amounts
    assert (R.match({"name": "Fee in latest call", "definition": "Management fee amount included in the most recent capital call"}) or {}).get("id") != "called_to_date"
