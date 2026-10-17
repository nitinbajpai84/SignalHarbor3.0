"""W1b invest: the recipe, signals and persona build of the Invest cards 51 to 100, proved on the six-month Evergreen Office loaded by the real pack readers.

All seven are built: 80 (vintage_split), 71 (expected_distributions), 53 (watch_flags), 76 (manager_score), 77 (deal_stage), 78 (redemption_dates) and
79 (rebalance_trades); the last five on the readers of manager news, the deal pipeline, redemption terms and the target allocation. Nothing here is stubbed: the office files go through the real loader
(sh_platform/v1/v3_pack_readers.py), the recipe is rendered and tied out by sh_platform/v1/v3_recipes.py, the signals are read by the engine's own check/resolve/calc,
and every expected number is read from tests/v1/fixtures/office6m/answer_keys.yaml. Synthetic data only. See docs/v3/w1/build51-invest.md.
"""
from __future__ import annotations

import glob
import importlib.util
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as S
from sh_platform.v1 import wh

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
PACK = REPO / "packs" / "family_office" / "1"
ENV_SCRIPT = REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_team_env.py"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
TODAY = "2026-10-13"
BUILT = {"uc-080-vintage": 80, "uc-071-expdist": 71, "uc-053-watchlist": 53, "uc-076-scorecard": 76, "uc-077-deals": 77, "uc-078-redemption": 78, "uc-079-rebalance": 79}
RECIPE = "vintage_split"
SIGNALS = {"uc-080-vintage-split": ("info", False), "uc-080-vintage-bunched": ("problem", True)}  # id -> (severity, is an exception)
SIGNALS71 = {"uc-071-expdist-fund": ("info", False), "uc-071-expdist-stale-value": ("needs", True)}


def key(card: str, n: int = 0) -> dict:
    return list(KEYS[card]["questions"].values())[n]["expected"]


# ---- an office loaded through the real loader ---------------------------------------------------------------------------------------------------

class Loaded:
    def __init__(self, plane, report):
        self.plane, self.report = plane, report
        self.con = wh.connect(plane)
        self.con.execute("set TimeZone = 'UTC'")

    def rows(self, sql: str, *args) -> list[dict]:
        cur = self.con.execute(sql, list(args))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    def one(self, sql: str, *args):
        return self.con.execute(sql, list(args)).fetchone()[0]

    def build(self, rid: str = RECIPE) -> list[dict]:
        """Render the recipe, check it reads only the tables it names, build its table, run its tie-out, return the rows."""
        r = R.recipe(rid)
        assert r is not None and r.get("status") != "stub", f"{rid} is not a built recipe"
        sql = R.render(r, f"t_{rid}", R.dims_for(r, {}))
        assert R.refusal(r, sql) is None, R.refusal(r, sql)
        self.con.execute(f"drop table if exists t_{rid}")
        self.con.execute(sql)
        if r.get("tie_out"):
            t = R.tie_out(self.con, r, f"t_{rid}")
            assert t and t["ok"], (rid, t)
        return self.rows(f"select * from t_{rid}")


@pytest.fixture(scope="module")
def office(tmp_path_factory) -> Loaded:
    tmp = tmp_path_factory.mktemp("w1b")
    spec = importlib.util.spec_from_file_location("v3_team_env", ENV_SCRIPT)
    env = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(env)
    info = env.load_office6m(tmp, TODAY)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    o = Loaded(plane, L.load_plane(plane, Path(info["dropbox"])))
    yield o
    o.con.close()


def f2(v) -> float:
    return round(float(v), 2)


def year_rows(rows: list[dict], ccy: str = "USD") -> dict:
    return {r["vintage_year"]: r for r in rows if r["currency"] == ccy and not r["is_total"]}


# ---- card 80: the recipe ------------------------------------------------------------------------------------------------------------------------

def test_the_recipe_is_built_reads_only_what_it_may_and_the_other_cards_stay_stubs():
    r = R.recipe(RECIPE)
    assert r and r.get("status") != "stub" and r["cards"] == [80]
    assert r.get("may_read") and r.get("never_read") and r.get("formula") and r.get("grain") and r["sql"] and r.get("measure") and r.get("columns") and r.get("tie_out") and r.get("needs")
    read = R.tables_read(R.render(r, "x"))
    assert read <= set(r["may_read"]) and not read & set(r["never_read"]), read
    assert not R.refusal(r, R.render(r, "x"))
    assert r["measure"] in r["columns"]
    stubs = {x["id"] for x in R.stubs()}
    assert not {"watch_flags", "manager_score", "expected_distributions"} & stubs  # every Invest card 51 to 100 is built


def test_card80_commitments_by_vintage_year_match_the_key(office):
    k, rows = key("uc-080-vintage"), office.build()
    years = year_rows(rows)
    assert {str(y) for y in years} == set(k["by_year"])
    for y, want in k["by_year"].items():
        got = years[int(y)]
        assert f2(got["commitment"]) == f2(want["commitment"]), y
        assert f2(got["share_pct"]) == f2(want["share_pct"]), y
        assert set(got["funds"].split("; ")) == set(want["funds"]) and got["funds_count"] == len(want["funds"]), y
    total = [r for r in rows if r["currency"] == "USD" and r["is_total"]]
    assert len(total) == 1 and f2(total[0]["commitment"]) == f2(k["total"]) and f2(total[0]["share_pct"]) == 100.0
    assert [str(y) for y, r in years.items() if r["is_largest"]] == [k["largest_year"]]
    assert f2(years[int(k["largest_year"])]["share_pct"]) == f2(k["largest_share_pct"])
    assert sum(f2(r["commitment"]) for r in years.values()) == f2(k["total"])  # the monthly registers supersede one another: counted once
    assert {r["currency"] for r in rows} == {"USD"}


def test_card80_a_corrected_register_row_counts_once_and_a_second_currency_is_never_added(office):
    """A later row that supersedes a commitment replaces it; a commitment in another currency has its own rows and its own shares."""
    con = office.con
    base = office.rows("select * from commitments where committed_on = date '2021-03-15' and supersedes_commitment_id is null order by recorded_at desc")
    live = office.rows("select x.* from commitments as x where x.committed_on = date '2021-03-15' and not exists (select 1 from commitments as y where y.supersedes_commitment_id = x.id)")
    assert len(live) == 1 and base
    con.execute("begin")
    try:
        con.execute("insert into commitments (id, organization_id, legal_entity_id, instrument_id, commitment_amount, currency, committed_on, called_to_date, called_as_at, recorded_at, supersedes_commitment_id) "
                    "select uuid(), organization_id, legal_entity_id, instrument_id, 14000000, currency, committed_on, called_to_date, called_as_at, now(), id from commitments where id = ?", [live[0]["id"]])
        con.execute("insert into commitments (id, organization_id, legal_entity_id, instrument_id, commitment_amount, currency, committed_on, recorded_at) "
                    "select uuid(), organization_id, legal_entity_id, instrument_id, 1000000, 'SGD', date '2025-05-05', now() from commitments where id = ?", [live[0]["id"]])
        rows = office.build()
        usd, sgd = year_rows(rows), year_rows(rows, "SGD")
        assert f2(usd[2021]["commitment"]) == 14_000_000 and usd[2021]["funds_count"] == 1
        assert f2(sum(r["commitment"] for r in usd.values())) == 53_850_000
        assert set(sgd) == {2025} and f2(sgd[2025]["commitment"]) == 1_000_000 and f2(sgd[2025]["share_pct"]) == 100.0
        assert {r["currency"]: f2(r["commitment"]) for r in rows if r["is_total"]} == {"USD": 53_850_000, "SGD": 1_000_000}
    finally:
        con.execute("rollback")
    assert f2(year_rows(office.build())[2021]["commitment"]) == 15_000_000


def test_card80_with_no_commitment_on_the_register_the_recipe_is_held(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("create temp table keep as select * from commitments")
        con.execute("delete from commitments")
        r = R.recipe(RECIPE)
        n = R.needs(con, r)
        assert n and "commitment" in str(n).lower()
    finally:
        con.execute("rollback")
    assert R.needs(con, R.recipe(RECIPE)) is None


# ---- card 80: the signals -----------------------------------------------------------------------------------------------------------------------

def signals(card: str = "uc-080") -> dict:
    out = {}
    for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(s.get("trigger"), dict) and True in s["trigger"]:
            s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}
        s["_file"] = p.name
        out[s["id"]] = s
    return out


def role_ids() -> set:
    ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    for p in (PACK / "builds").glob("*.yaml"):
        ids |= {r["id"] for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles") or []}
    return ids


FUNCS = {"abs": abs, "min": min, "max": max, "round": round, "last4": S.last4, "num": S.num}


def run_signal(sig: dict, row: dict, rules: dict | None = None):
    """The engine's own resolve and condition on one row of the figure. -> True/False, or the Missing reason when an input is not there (skipped, never guessed)."""
    fields = [f for i in sig["inputs"] if i["kind"] == "doc" for f in i["fields"]]
    ev = {"doc": {f: row.get(f) for f in fields}, "today": TODAY, "facts": {"rules": rules or {}}}
    try:
        ns, _ = S.resolve(None, sig, ev, FUNCS, [])
        for name, e in (sig.get("let") or {}).items():
            ns[name] = S.calc(e, ns, FUNCS)
        return bool(S.calc(sig["condition"], ns, FUNCS))
    except S.Missing as m:
        return f"missing {m}"


def test_the_signals_are_read_by_the_engine_name_a_known_role_and_the_exception_is_there():
    sigs = signals()
    assert set(sigs) == set(SIGNALS)
    roles = role_ids()
    for sid, (sev, exception) in SIGNALS.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True
        assert S.check(s, {r: r for r in roles}) is None, S.check(s, {r: r for r in roles})
        assert s["trigger"] == {"on": "figure_changed", "figure": RECIPE} and s["severity"] == sev and s["route_to"] == "risk_officer", sid
        assert not s.get("hold"), sid  # the story is read only (signs: none): nothing to block
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia|Tom)\b", yaml.safe_dump(s)), sid  # a role, never a person
    assert any(SIGNALS[s][1] for s in sigs)


def test_signal_fields_are_columns_of_the_figure_they_watch(office):
    have = set(office.build()[0])
    for sid, s in signals().items():
        for i in s["inputs"]:
            if i["kind"] == "doc":
                assert set(i["fields"]) <= have, (sid, set(i["fields"]) - have)
        used = set(re.findall(r"doc\.(\w+)", " ".join([s["condition"], *(s.get("let") or {}).values(), s["message"], s["subject"]])))
        assert used <= {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}, sid


def test_the_normal_signal_fires_for_each_of_the_five_years_and_not_on_the_total_row(office):
    s = signals()["uc-080-vintage-split"]
    rows = office.build()
    fired = [r["vintage_year"] for r in rows if run_signal(s, r) is True]
    assert sorted(fired) == [2021, 2022, 2023, 2024, 2025]
    total = next(r for r in rows if r["is_total"])
    assert run_signal(s, total) != True  # noqa: E712 - the total row has no year: skipped, not fired


def test_the_exception_is_skipped_while_no_limit_is_signed_and_fires_on_the_bunched_year_when_one_is(office):
    s = signals()["uc-080-vintage-bunched"]
    rows = [r for r in office.build() if not r["is_total"]]
    assert all(str(run_signal(s, r)).startswith("missing rule limit_vintage_year") for r in rows)  # the policy signs no vintage limit: never guessed
    rule = {"limit_vintage_year": {"value": {"max_pct": 25, "text": "test-only limit"}}}  # a limit signed for this test only
    assert [r["vintage_year"] for r in rows if run_signal(s, r, rule) is True] == [2021]  # 27.35 percent against 25
    rule = {"limit_vintage_year": {"value": {"max_pct": 30, "text": "test-only limit"}}}
    assert not [r for r in rows if run_signal(s, r, rule) is True]
    msg = S.render(s["message"], {"doc": {"vintage_year": 2021, "share_pct": Decimal("27.35"), "currency": "USD", "commitment": Decimal("15000000"), "funds": "Evergreen Growth I"},
                                  "limit": {"max_pct": Decimal(25)}, "over": Decimal("2.35")})
    assert "27.35" in msg and "2.35" in msg and "25.00" in msg


# ---- card 80: the persona build ------------------------------------------------------------------------------------------------------------------

def numbers(v) -> set:
    out = set()
    if isinstance(v, dict):
        for x in v.values():
            out |= numbers(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            out |= numbers(x)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out.add(round(float(v), 4))
    elif isinstance(v, str):
        out.add(v.strip())
    return out


def test_the_build_is_runnable_and_its_expect_is_copied_from_the_key():
    d = yaml.safe_load((PACK / "builds" / "invest-51.yaml").read_text(encoding="utf-8"))
    assert d["template"] == "family_office@1"
    built = {b["id"]: (r["id"], b) for r in d["roles"] for b in r["builds"]}
    assert {built["uc-080-vintage"][0], built["uc-071-expdist"][0]} == {"risk_officer", "investment_analyst"}
    assert set(built) == set(BUILT)
    existing = {x["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"] for x in r["builds"]}
    assert not set(built) & existing
    for cid, (role, b) in built.items():
        assert role in role_ids() and b.get("say") and b.get("title") and b.get("dashboard") and b["skills"] and len(b["say"]) > 80
        assert b["check"]["ask"].endswith("?") and b["check"]["expect"], cid
        k = numbers(list(KEYS[cid]["questions"].values()))
        for e in b["check"]["expect"]:
            n = re.sub(r"[,%]", "", e)
            assert e in k or (re.fullmatch(r"-?[\d.]+", n) and round(float(n), 4) in k), (cid, e)
        assert b["files"]
        for f in b["files"]:
            assert f.startswith("office6m:") and glob.glob(str(OFFICE / f[len("office6m:"):])), (cid, f)
        want = {re.sub(r"^\*/", "", g) for g in KEYS[cid]["input_files"]}
        assert any(f.removeprefix("office6m:").removeprefix("*/") in want for f in b["files"]), cid


def test_the_build_expect_numbers_come_out_of_the_recipe(office):
    d = yaml.safe_load((PACK / "builds" / "invest-51.yaml").read_text(encoding="utf-8"))
    expect = next(b for r in d["roles"] for b in r["builds"] if b["id"] == "uc-080-vintage")["check"]["expect"]
    rows = office.build()
    shown = {f"{f2(r['commitment']):,.0f}" for r in rows} | {str(f2(r["share_pct"])).rstrip("0").rstrip(".") for r in rows} | {str(r["vintage_year"]) for r in rows}
    assert set(expect) <= shown, set(expect) - shown


# ---- card 71: expected distributions ---------------------------------------------------------------------------------------------------------

R71 = "expected_distributions"


def test_card71_the_recipe_is_built_and_reads_only_what_it_may():
    r = R.recipe(R71)
    assert r and r.get("status") != "stub" and r["cards"] == [71]
    assert r.get("may_read") and r.get("never_read") and r.get("formula") and r.get("grain") and r["sql"] and r.get("measure") and r.get("columns") and r.get("tie_out") and r.get("needs")
    read = R.tables_read(R.render(r, "x"))
    assert read <= set(r["may_read"]) and not read & set(r["never_read"]), read
    assert r["measure"] in r["columns"]


def test_card71_expected_distributions_match_the_key(office):
    k, rows = key("uc-071-expdist"), office.build(R71)
    assert {r["currency"] for r in rows} == {"USD"}
    qt = {str(r["quarter_end"]): f2(r["amount"]) for r in rows if r["row_kind"] == "quarter_total"}
    assert qt == {q: f2(v) for q, v in k["by_quarter"].items()}
    assert [f2(r["amount"]) for r in rows if r["row_kind"] == "total"] == [f2(k["total_next_4_quarters"])]
    funds = {r["fund"]: r for r in rows if r["row_kind"] == "fund_total"}
    assert set(funds) == set(k["by_fund"])
    for fund, want in k["by_fund"].items():
        got = funds[fund]
        assert f2(got["latest_value"]) == f2(want["latest_value"]) and str(got["valuation_date"]) == want["valuation_date"], fund
        assert f2(got["amount"]) == f2(want["total"]), fund
        qs = sorted((r for r in rows if r["row_kind"] == "fund_quarter" and r["fund"] == fund), key=lambda r: r["quarter_end"])
        assert [f2(r["payout_pct"]) for r in qs] == [f2(x) for x in want["payout_pct"]], fund
        assert [f2(r["amount"]) for r in qs] == [f2(x) for x in want["amounts"]], fund
    assert sorted(f for f, r in funds.items() if r["is_stale"]) == ["Cedarpoint Opportunities II", "Cedarpoint Ventures III", "Saltmarsh Renewables I"]  # 31 Mar and 30 Jun values
    assert f2(funds["Evergreen Growth I"]["latest_value"]) == 10_180_000  # the amended 30 Sep statement replaces the 10,000,000 estimate


def test_card71_a_newer_outlook_replaces_the_old_and_a_second_currency_is_never_added(office):
    con = office.con
    old = office.rows("select d.id from documents as d join instruments as i on i.id = d.instrument_id where d.document_type = 'manager_distribution_outlook' and i.canonical_name = 'Evergreen Income II'")
    assert len(old) == 1
    con.execute("begin")
    try:
        con.execute("create temp table nd as select * from documents where id = ?", [old[0]["id"]])
        con.execute("update nd set id = uuid(), received_at = received_at + interval 5 day, content_hash = content_hash || '-v2'")
        con.execute("insert into documents select * from nd")
        con.execute("create temp table nf as select * from extracted_fields where document_id = ?", [old[0]["id"]])
        con.execute("update nf set id = uuid(), document_id = (select id from nd), value_numeric = 0.02")
        con.execute("insert into extracted_fields select * from nf")
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, valuation_date, received_at, recorded_at, value_amount, currency, valuation_type, approval_status) "
                    "select uuid(), organization_id, instrument_id, date '2026-10-31', now(), now(), 1000000, 'SGD', 'manager_final', 'final' from valuation_observations "
                    "where instrument_id = (select instrument_id from documents where document_type = 'manager_distribution_outlook' and title like 'Saltmarsh Renewables I%') limit 1")
        rows = office.build(R71)
        inc = [r for r in rows if r["fund"] == "Evergreen Income II" and r["row_kind"] == "fund_total"]
        assert len(inc) == 1 and f2(inc[0]["amount"]) == 512_000  # 6,400,000 x 2 percent x 4 quarters, the old 1.5 percent outlook is replaced
        assert {r["currency"]: f2(r["amount"]) for r in rows if r["row_kind"] == "total"} == {"USD": 2_660_810 + 128_000 - 21_100, "SGD": 20_000}
    finally:
        con.execute("rollback")
    assert [f2(r["amount"]) for r in office.build(R71) if r["row_kind"] == "total"] == [2_660_810]


def test_card71_with_no_outlook_the_recipe_is_held(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("delete from extracted_fields where field_name = 'projected_payout_rate'")
        n = R.needs(con, R.recipe(R71))
        assert n and "outlook" in n
    finally:
        con.execute("rollback")
    assert R.needs(con, R.recipe(R71)) is None


def test_card71_signals_are_read_by_the_engine_and_fire_on_the_right_funds(office):
    sigs, roles, rows = signals("uc-071"), role_ids(), office.build(R71)
    assert set(sigs) == set(SIGNALS71)
    have = set(rows[0])
    for sid, (sev, exception) in SIGNALS71.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True and S.check(s, {r: r for r in roles}) is None, sid
        assert s["trigger"] == {"on": "figure_changed", "figure": R71} and s["severity"] == sev and s["route_to"] == "investment_analyst", sid
        assert not s.get("hold"), sid  # the story is read only (signs: none): nothing to block
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia|Tom)\b", yaml.safe_dump(s)), sid
        fields = {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}
        assert fields <= have and set(re.findall(r"doc\.(\w+)", " ".join([s["condition"], s["message"], s["subject"]]))) <= fields, sid
    fired = {sid: sorted(r["fund"] for r in rows if run_signal(sigs[sid], r) is True) for sid in sigs}
    assert len(fired["uc-071-expdist-fund"]) == 8 and "All funds" not in fired["uc-071-expdist-fund"]
    assert fired["uc-071-expdist-stale-value"] == ["Cedarpoint Opportunities II", "Cedarpoint Ventures III", "Saltmarsh Renewables I"]


def test_card71_the_build_expect_numbers_come_out_of_the_recipe(office):
    d = yaml.safe_load((PACK / "builds" / "invest-51.yaml").read_text(encoding="utf-8"))
    expect = next(b for r in d["roles"] for b in r["builds"] if b["id"] == "uc-071-expdist")["check"]["expect"]
    rows = office.build(R71)
    shown = {f"{f2(r['amount']):,.0f}" for r in rows} | {f"{f2(r['latest_value']):,.0f}" for r in rows if r["latest_value"] is not None}
    assert set(expect) <= shown, set(expect) - shown


# ---- cards 53, 76, 77, 78, 79: built on the last readers (manager news, deal pipeline, redemption terms, target allocation) -------------------------

NEW = {"watch_flags": 53, "manager_score": 76, "deal_stage": 77, "redemption_dates": 78, "rebalance_trades": 79}
NEW_SIGNALS = {  # id -> (recipe, severity, route, has a hold)
    "uc-053-watchlist-flagged": ("watch_flags", "needs", "investment_analyst", False), "uc-053-watchlist-missing": ("watch_flags", "problem", "investment_analyst", True),
    "uc-076-scorecard-score": ("manager_score", "info", "cio", False), "uc-076-scorecard-review": ("manager_score", "problem", "cio", False),
    "uc-077-deals-stage": ("deal_stage", "info", "investment_analyst", False), "uc-077-deals-stuck": ("deal_stage", "problem", "cio", True),
    "uc-078-redemption-notice": ("redemption_dates", "needs", "ops_lead", False), "uc-078-redemption-locked": ("redemption_dates", "problem", "cio", False),
    "uc-079-rebalance-proposal": ("rebalance_trades", "needs", "cio", False), "uc-079-rebalance-unsigned": ("rebalance_trades", "needs", "cio", True),
}


def by(rows: list[dict], col: str) -> dict:
    return {r[col]: r for r in rows}


def test_the_five_recipes_are_built_and_read_only_what_they_may():
    for rid, card in NEW.items():
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["cards"] == [card], rid
        assert r.get("may_read") and r.get("never_read") and r.get("formula") and r.get("grain") and r["sql"] and r.get("measure") and r.get("columns") and r.get("tie_out") and r.get("needs"), rid
        read = R.tables_read(R.render(r, "x"))
        assert read <= set(r["may_read"]) and not read & set(r["never_read"]), (rid, read)
        assert r["measure"] in r["columns"], rid


def test_the_manager_news_mails_are_read_with_their_manager_and_team_change(office):
    assert office.report["manager_news"]["files"] == 2 and "no reader for this kind" not in office.report["manager_news"]["not_loaded"]
    got = office.rows("select c.value_text as manager, t.value_text as change, d.document_date from documents as d join extracted_fields as c on c.document_id = d.id and c.field_name = 'counterparty' "
                      "join extracted_fields as t on t.document_id = d.id and t.field_name = 'team_change' where d.document_type = 'manager_news' order by d.document_date")
    assert [(g["manager"], str(g["document_date"])) for g in got] == [("Saltmarsh Real Assets", "2026-08-18"), ("Northgate Partners", "2026-09-09")]
    assert "resigns" in got[0]["change"] and "key person" in got[1]["change"]


def test_card53_watch_flags_match_the_key_and_the_newsletter_is_not_a_mail(office):
    k, rows = key("uc-053-watchlist"), office.build("watch_flags")
    got = by(rows, "manager")
    assert set(got) == set(k["by_manager"]) and {str(r["window_start"]) for r in rows} == {k["window_start"]}
    for m, want in k["by_manager"].items():
        assert {c: got[m][c] for c in want} == want, m
    assert sorted(m for m, r in got.items() if r["on_watchlist"]) == sorted(k["on_watchlist"])
    assert got["Kestrel Ridge Advisors"]["personnel_changes"] == 0  # the Q3 newsletter's team change is a newsletter, not a mail: the key's method counts mails
    assert office.one("select count(*) from documents d join extracted_fields f on f.document_id = d.id and f.field_name = 'team_change' where d.document_type = 'newsletter'") == 1
    assert got["Cedarpoint Ventures"]["missing_detail"] == "Cedarpoint Opportunities II 2026-06-30"


def test_card53_a_mail_before_the_window_is_not_counted(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update documents set document_date = date '2026-07-01' where document_type = 'manager_news' and title like 'Saltmarsh%'")
        assert by(office.build("watch_flags"), "manager")["Saltmarsh Real Assets"]["personnel_changes"] == 0
    finally:
        con.execute("rollback")
    assert by(office.build("watch_flags"), "manager")["Saltmarsh Real Assets"]["personnel_changes"] == 1


def test_card76_scores_match_the_key_with_the_signed_weights(office):
    k, got = key("uc-076-scorecard"), by(office.build("manager_score"), "manager")
    for m, want in k["by_manager"].items():
        g = got[m]
        assert (f2(g["return_pct"]), g["fee_drag_pct"] and f2(g["fee_drag_pct"]), round(float(g["on_time_share"]), 3)) == \
               (want["return_pct_since_1_apr"], want["fee_drag_pct"], want["on_time_share"]), m
        assert (g["watch_flags"], f2(g["score"]), g["verdict"]) == (want["watch_flags"], want["score"], want["verdict"]), m
    w = got["Bluewater Capital"]
    assert {"returns": w["weight_returns"], "fees": w["weight_fees"], "timeliness": w["weight_timeliness"], "watch": w["weight_watch"]} == k["weights"]
    assert got["Meridian Index Managers"]["verdict"] == "keep"  # scored like the others; the key leaves the index manager out


def test_card76_with_no_signed_weights_there_is_no_score(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where rule_code = 'manager_score_weights')")
        rows = office.build("manager_score")
        assert all(r["score"] is None and r["verdict"] is None for r in rows)
        assert "weights are not signed" in R.needs(con, R.recipe("manager_score"))
    finally:
        con.execute("rollback")
    assert R.needs(con, R.recipe("manager_score")) is None


def test_card77_deals_match_the_key(office):
    k, rows = key("uc-077-deals"), office.build("deal_stage")
    got = by(rows, "deal_name")
    assert set(got) == {d["deal"] for d in k["deals"]}  # the teaser's 'Harborlight Ventures Iv' row is superseded by the pipeline's
    for d in k["deals"]:
        g = got[d["deal"]]
        assert (g["stage"], g["days_in_stage"], f2(g["ticket"]), bool(g["stuck"])) == (d["stage"], d["days_in_stage"], d["ticket"], d["stuck"]), d["deal"]
    assert {r["stage"]: r["deals_in_stage"] for r in rows} == k["by_stage"]
    assert sorted(n for n, g in got.items() if g["stuck"]) == sorted(k["stuck_over_60_days"])
    assert {f2(r["total_ticket"]) for r in rows} == {k["total_ticket"]} and {r["stage_limit_days"] for r in rows} == {60}


def test_card77_with_no_signed_stage_limit_nothing_is_called_stuck(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("delete from rule_versions where business_rule_id in (select id from business_rules where rule_code = 'deal_stage_limit_days')")
        rows = office.build("deal_stage")
        assert all(r["stuck"] is None and r["stage_limit_days"] is None for r in rows) and len(rows) == 5
    finally:
        con.execute("rollback")


def test_card78_redemption_dates_match_the_key(office):
    k, got = key("uc-078-redemption")["by_fund"], by(office.build("redemption_dates"), "fund")
    assert set(got) == set(k)
    for fund, want in k.items():
        g = got[fund]
        assert {c: (str(g[c]) if "date" in c or c == "send_notice_by" else f2(g[c]) if c != "days_to_send" else g[c]) for c in want} == want, fund
    assert got["Kestrel Ridge Equity Long/Short Fund"]["locked_up"] == 1 and got["Kestrel Ridge Macro Fund"]["locked_up"] == 0


def test_card78_a_later_lockup_moves_the_dealing_date(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update extracted_fields set value_text = '2027-01-15' where field_name = 'lockup_end_date' and document_id in (select id from documents where title = 'kestrel_H1_redemption_terms')")
        g = by(office.build("redemption_dates"), "fund")["Kestrel Ridge Macro Fund"]
        assert (str(g["dealing_date"]), str(g["send_notice_by"])) == ("2027-01-29", "2026-12-15")  # first month-end business day after the lock-up; 45 days back
    finally:
        con.execute("rollback")


def test_card79_rebalance_matches_the_key_and_says_the_targets_are_proposed(office):
    k, rows = key("uc-079-rebalance"), office.build("rebalance_trades")
    got = by(rows, "asset_class")
    assert set(got) == set(k["by_class"]) and {f2(r["book"]) for r in rows} == {k["book"]}
    for c, want in k["by_class"].items():
        assert {x: f2(got[c][x]) for x in want} == want, c
    assert f2(sum(r["trade"] for r in rows)) == k["net_trade"]
    assert {r["targets_status"] for r in rows} == {"proposed, not signed: a suggestion only"} and "not signed" in k["targets_status"]
    assert got["convertible"]["class_from_type"] == 1  # the convertible note has no asset class on record: counted under its instrument type


def test_card79_a_signed_target_is_shown_as_signed(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update rule_versions set approval_status = 'approved' where business_rule_id in (select id from business_rules where rule_code = 'allocation_bond')")
        got = by(office.build("rebalance_trades"), "asset_class")
        assert got["bond"]["targets_status"] == "signed" and got["listed_equity"]["targets_status"].startswith("proposed")
    finally:
        con.execute("rollback")


def test_cards_34_and_41_screen_harborlight_among_the_five_deals(office):
    """The pipeline holds five deals: the mandate fit and the commitment tests give one row per deal; the Harborlight row equals the keys of 34 and 41."""
    k34, k41 = key("uc-034-prospect"), key("uc-041-commitappr")
    fit, chk = office.build("mandate_fit"), office.build("commit_check")
    assert len(fit) == len(chk) == 5
    h = by(fit, "deal_name")["Harborlight Ventures IV"]
    assert (f2(h["ticket"]), f2(h["uncalled_before"]), f2(h["uncalled_after"]), round(float(h["ticket_pct_of_uncalled"]), 1)) == \
           (k34["minimum_ticket"], k34["uncalled_before"], k34["uncalled_after"], k34["ticket_pct_of_current_uncalled"])
    c = by(chk, "deal_name")["Harborlight Ventures IV"]
    assert (f2(c["new_commitment"]), f2(c["uncalled_after"]), f2(c["cash_usd"]), f2(c["cash_cover_pct"])) == \
           (k41["new_commitment"], k41["uncalled_after"], k41["cash_usd_equivalent"], k41["cash_cover_of_uncalled_after_pct"])


def test_the_new_signals_are_read_by_the_engine_and_fire_on_the_right_rows(office):
    roles = role_ids()
    sigs = {**signals("uc-053"), **signals("uc-076"), **signals("uc-077"), **signals("uc-078"), **signals("uc-079")}
    assert set(sigs) == set(NEW_SIGNALS)
    rows = {rid: office.build(rid) for rid in NEW}
    for sid, (rid, sev, route, hold) in NEW_SIGNALS.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True and S.check(s, {r: r for r in roles}) is None, sid
        assert s["trigger"] == {"on": "figure_changed", "figure": rid} and s["severity"] == sev and s["route_to"] == route and bool(s.get("hold")) == hold, sid
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia|Tom)\b", yaml.safe_dump(s)), sid
        fields = {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}
        assert fields <= set(rows[rid][0]) and set(re.findall(r"doc\.(\w+)", " ".join([s["condition"], s["message"], s["subject"]]))) <= fields, sid
    def fired(sid, col):
        return sorted(str(r[col]) for r in rows[NEW_SIGNALS[sid][0]] if run_signal(sigs[sid], r) is True)
    assert fired("uc-053-watchlist-flagged", "manager") == ["Cedarpoint Ventures", "Kestrel Ridge Advisors", "Northgate Partners", "Saltmarsh Real Assets"]
    assert fired("uc-053-watchlist-missing", "manager") == ["Cedarpoint Ventures"]
    assert fired("uc-076-scorecard-review", "manager") == ["Cedarpoint Ventures", "Kestrel Ridge Advisors", "Saltmarsh Real Assets"]
    assert len(fired("uc-076-scorecard-score", "manager")) == 6
    assert fired("uc-077-deals-stuck", "deal_name") == ["Ashgrove Growth Equity V", "Marlow Infrastructure Partners III"] and len(fired("uc-077-deals-stage", "deal_name")) == 5
    assert fired("uc-078-redemption-locked", "fund") == ["Kestrel Ridge Equity Long/Short Fund"] and len(fired("uc-078-redemption-notice", "fund")) == 2
    assert fired("uc-079-rebalance-unsigned", "asset_class") == ["bond", "convertible", "listed_equity"] == fired("uc-079-rebalance-proposal", "asset_class")


def shown(rows: list[dict]) -> set:
    out = set()
    for r in rows:
        for v in r.values():
            if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                out |= {f"{float(v):,.0f}", str(round(float(v), 3)).rstrip("0").rstrip("."), f"{float(v):g}"}
            elif v is not None:
                out.add(str(v))
    return out


def test_the_new_builds_expect_numbers_come_out_of_the_recipes(office):
    d = yaml.safe_load((PACK / "builds" / "invest-51.yaml").read_text(encoding="utf-8"))
    builds = {b["id"]: b for r in d["roles"] for b in r["builds"]}
    for cid, rid in {"uc-053-watchlist": "watch_flags", "uc-076-scorecard": "manager_score", "uc-077-deals": "deal_stage", "uc-078-redemption": "redemption_dates",
                     "uc-079-rebalance": "rebalance_trades"}.items():
        expect = builds[cid]["check"]["expect"]
        assert set(expect) <= shown(office.build(rid)), (cid, set(expect) - shown(office.build(rid)))
