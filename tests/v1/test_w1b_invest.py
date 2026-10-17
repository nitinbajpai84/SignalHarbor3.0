"""W1b invest: the recipe, signals and persona build of the Invest cards 51 to 100, proved on the six-month Evergreen Office loaded by the real pack readers.

Cards 80 (vintage_split) and 71 (expected_distributions) are built. Cards 53, 76, 77, 78 and 79 are not: each test below states what they wait for (a reader that does not exist, or a rule nobody has signed),
so the day the reader or the rule arrives the test fails and says the card can be built. Nothing here is stubbed: the office files go through the real loader
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
BUILT = {"uc-080-vintage": 80, "uc-071-expdist": 71}
NOT_BUILT = {"uc-053-watchlist": 53, "uc-076-scorecard": 76, "uc-077-deals": 77, "uc-078-redemption": 78, "uc-079-rebalance": 79}
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
    assert {"watch_flags", "manager_score"} <= stubs and "expected_distributions" not in stubs  # cards 53, 76 wait (see the tests of the unbuilt cards below)


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


# ---- the cards that are not built: what they wait for ---------------------------------------------------------------------------------------------
# Each test passes while the thing is missing and fails the day it exists, so the card is then built instead of forgotten.

def not_read(office, kind: str) -> bool:
    return "no reader for this kind" in office.report.get(kind, {}).get("not_loaded", [])


def test_the_not_built_cards_have_a_key_and_still_no_recipe_or_build():
    stubs = {x["id"] for x in R.stubs()}
    assert {"watch_flags", "manager_score"} <= stubs
    d = yaml.safe_load((PACK / "builds" / "invest-51.yaml").read_text(encoding="utf-8"))
    ids = {b["id"] for r in d["roles"] for b in r["builds"]}
    for cid in NOT_BUILT:
        assert cid in KEYS and cid not in ids
        assert not list((PACK / "signals").glob(f"{cid}-*.yaml")), cid  # a signal on a figure nobody builds would watch nothing


def test_cards_77_78_79_wait_for_readers_of_files_the_loader_does_not_know(office):
    for kind in ("deal_pipeline", "fund_documents", "target_allocation", "manager_news"):
        assert not_read(office, kind) and office.report[kind]["rows"] == 0, kind
    assert office.one("select count(*) from documents where document_type in ('redemption_terms', 'interim_targets')") == 0
    assert office.one("select count(*) from deal_pipeline") == 1  # the Harborlight teaser only; the five-deal csv and two other teasers are unread (key: 5 deals)
    assert len(key("uc-077-deals")["deals"]) == 5


def test_cards_76_and_79_also_wait_for_a_signed_rule(office):
    codes = {r["rule_code"] for r in office.rows("select r.rule_code from business_rules as r join rule_versions as v on v.business_rule_id = r.id where v.approval_status = 'approved'")}
    assert not [c for c in codes if re.search(r"score|weight|target|rebalanc|stuck|stage", c)], codes  # scorecard weights and bands, allocation targets, the 60-day stuck limit: none is signed
    proposed = key("uc-079-rebalance")["targets_status"]
    assert "not signed" in proposed


STATEMENT_FLAGS = """
with asat as (select max(cast(received_at as date)) as d from documents), lo as (select d - 90 as d from asat),
due as (select e.* from expected_statements as e where not exists (select 1 from expected_statements as x where x.supersedes_expected_statement_id = e.id)),
st as (select i.manager_name as m, o.evidence_document_id as doc, o.valuation_type as t, cast(o.received_at as date) as r, d.due_date from valuation_observations as o
  join instruments as i on i.id = o.instrument_id left join due as d on d.instrument_id = o.instrument_id and d.period_end = o.valuation_date where cast(o.received_at as date) >= (select d from lo)),
mi as (select i.manager_name as m from due as e join instruments as i on i.id = e.instrument_id where i.manager_name is not null and e.due_date < (select d from asat)
  and not exists (select 1 from valuation_observations as o where o.instrument_id = e.instrument_id and o.valuation_date = e.period_end)),
pc as (select c.value_text as m, count(distinct d.id) as n from documents as d join extracted_fields as c on c.document_id = d.id and c.field_name = 'counterparty'
  join extracted_fields as t on t.document_id = d.id and t.field_name = 'team_change' where coalesce(d.document_date, cast(d.received_at as date)) >= (select d from lo) group by 1)
select g.m as manager, (select count(distinct doc) from st where st.m = g.m and st.t <> 'manager_amended' and st.r > st.due_date) as late,
  (select count(distinct doc) from st where st.m = g.m and st.t = 'manager_amended') as amended, (select count(*) from mi where mi.m = g.m) as missing,
  coalesce((select n from pc where pc.m = g.m), 0) as personnel_changes from (select distinct manager_name as m from instruments where manager_name is not null) as g order by 1
"""


def test_card53_late_amended_and_missing_statements_reproduce_the_key_but_personnel_changes_do_not(office):
    """The draft of watch_flags: three of its four counts equal the key for all six managers. The fourth needs the manager_news mails, which no reader loads
    (the key counts Northgate and Saltmarsh personnel mails and leaves the Kestrel newsletter out), so the card stays unbuilt and the recipe a stub."""
    k = key("uc-053-watchlist")
    assert k["window_start"] == "2026-07-15"
    got = {r["manager"]: r for r in office.rows(STATEMENT_FLAGS)}
    assert set(got) == set(k["by_manager"])
    for m, want in k["by_manager"].items():
        assert (got[m]["late"], got[m]["amended"], got[m]["missing"]) == (want["late"], want["amended"], want["missing"]), m
    mails = {m: got[m]["personnel_changes"] for m in got}
    assert mails["Northgate Partners"] == 0 and mails["Saltmarsh Real Assets"] == 0  # the key has 1 and 1: their mails are in manager_news, unread
    assert mails["Kestrel Ridge Advisors"] == 1 and k["by_manager"]["Kestrel Ridge Advisors"]["personnel_changes"] == 0  # the newsletter's team change: in the files, not in the key
    assert not_read(office, "manager_news")
