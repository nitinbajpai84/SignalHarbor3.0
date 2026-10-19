"""Live run 7, invest group (docs/v3/LIVE-R7-ANALYSIS.md): uc-041, uc-043, uc-047, uc-048, uc-071, uc-074 and uc-076, each answered from its recipe's own lines.

The cases failed the way rounds 5 and 6 did: the answer was a plain read of one column (uc-041, uc-043, uc-074), the recipe's lines did not say the figures the
case asks for (uc-047), the question bound to a recipe that did not hold the figure (uc-048), the recipe's table was dropped by the plan check so the figure was
"Not available yet" (uc-071), or the data the figure rests on was not in the office (uc-076, see the last test). Every expected number is read from
tests/v1/fixtures/office6m/answer_keys.yaml; the office is the six-month Evergreen Office loaded by the real pack readers. Synthetic data only."""
from __future__ import annotations

import copy
from datetime import date
import importlib.util
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_plan_guard as PG
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
ENV_SCRIPT = REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_team_env.py"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
TODAY = "2026-10-13"


def key(card: str, n: int = 0) -> dict:
    return list(KEYS[card]["questions"].values())[n]["expected"]


def n(v) -> str:
    """A number as the answer says it: thousands separated, a decimal as the key writes it."""
    return f"{v:,}"


class Loaded:
    def __init__(self, plane):
        self.plane = plane
        self.con = wh.connect(plane)
        self.con.execute("set TimeZone = 'UTC'")

    def build(self, rid: str) -> list[dict]:
        r = R.recipe(rid)
        sql = R.render(r, f"t_{rid}", R.dims_for(r, {}))
        assert R.refusal(r, sql) is None, R.refusal(r, sql)
        self.con.execute(f"drop table if exists t_{rid}")
        self.con.execute(sql)
        t = R.tie_out(self.con, r, f"t_{rid}") if r.get("tie_out") else None
        assert t is None or t["ok"], (rid, t)
        cur = self.con.execute(f"select * from t_{rid}")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, x)) for x in cur.fetchall()]

    def says(self, rid: str, where=lambda x: True) -> str:
        return F.say(R.recipe(rid), [x for x in self.build(rid) if where(x)]) or ""


@pytest.fixture(scope="module")
def office(tmp_path_factory) -> Loaded:
    tmp = tmp_path_factory.mktemp("r7inv")
    spec = importlib.util.spec_from_file_location("v3_team_env", ENV_SCRIPT)
    env = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(env)
    info = env.load_office6m(tmp, TODAY)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    L.load_plane(plane, Path(info["dropbox"]))
    o = Loaded(plane)
    yield o
    o.con.close()


# ---- the answers say the figures the cases ask for -------------------------------------------------------------------------------------------

def test_uc041_the_commitment_check_says_the_ticket_the_uncalled_after_the_cash_and_its_cover(office):
    k = key("uc-041-commitappr")
    said = office.says("commit_check", lambda x: x["deal_name"] == "Harborlight Ventures IV")
    for v in (k["new_commitment"], k["uncalled_after"], k["cash_usd_equivalent"], k["cash_cover_of_uncalled_after_pct"]):
        assert n(v) in said, (v, said)


def test_uc043_the_liquid_book_says_the_value_today_the_net_trades_and_the_gain(office):
    k = key("uc-043-liquidpnl")
    said = office.says("liquid_pnl_mtd")
    for v in (k["value_13_oct"], k["net_trades_settled"], k["gain_loss_mtd"]):
        assert n(v) in said, (v, said)


def test_uc047_the_committee_pack_says_the_return_the_shortfall_and_the_deal_tickets(office):
    rows = office.build("pack_items")
    said = F.say(R.recipe("pack_items"), rows)
    ret = key("uc4-vs-benchmark")
    for v in (ret["portfolio_return_pct"], ret["benchmark_return_pct"], 270000, 2000000):
        assert n(v) in said, (v, said)
    assert {x["section"] for x in rows} == {"Report", "Performance", "Attribution", "Breaches", "Proposals"}  # five sections, as the key says


def test_uc074_the_board_pack_says_every_headline_figure(office):
    k = key("uc-074-boardpack")
    said = office.says("board_summary")
    for v in (k["net_worth_usd"], k["net_worth_sgd"], k["liquid_book_q3_return_pct"], k["benchmark_since_1_apr_pct"], k["cash_usd_eq"], k["call_7_shortfall_usd"],
              k["uncalled_commitments"]):
        assert n(v) in said, (v, said)


def test_uc074_a_shadow_commitment_row_is_not_uncalled_money_in_the_board_pack_either(office):
    """The live office held a placeholder row for each fund (no register source, no called figure) beside the real ones: 58.6M uncalled against the key's 14.6M.
    The board's embedded called_to_date leaves a shadow row out, as called_to_date and commit_check do."""
    k = key("uc-074-boardpack")
    con = office.con
    con.execute("begin")
    try:
        con.execute("insert into commitments select * replace (uuid() as id, null as source_record_id, null as called_to_date, null as called_as_at) "
                    "from commitments c where c.called_to_date is not null and not exists (select 1 from commitments y where y.supersedes_commitment_id = c.id) limit 3")
        rows = office.build("board_summary")
        assert float(rows[0]["uncalled_commitments_usd"]) == k["uncalled_commitments"]
    finally:
        con.execute("rollback")


def test_uc071_the_payout_forecast_says_the_quarters_the_total_and_the_funds(office):
    k = key("uc-071-expdist")
    said = office.says("expected_distributions")
    for v in (*k["by_quarter"].values(), k["total_next_4_quarters"], k["by_fund"]["Evergreen Growth I"]["total"], k["by_fund"]["Evergreen Growth I"]["latest_value"]):
        assert n(v) in said, (v, said)


def test_uc076_the_scorecard_says_each_score_when_the_manager_news_is_loaded(office):
    """With the two manager mails read (the office6m tree), Northgate Partners has two flags and scores 86.8, the key's. The live office is a flat dropbox: kind_of
    (v3_pack_readers) does not recognise an .eml as manager news, so the mails never became documents, Northgate had one flag and scored 91.8 (r7)."""
    k = key("uc-076-scorecard")
    said = office.says("manager_score")
    for m, want in k["by_manager"].items():
        assert f"{m} {n(want['score'])}" in said, (m, said)


# ---- the questions and the figures bind to the recipes that hold them -----------------------------------------------------------------------

def test_uc048_the_limits_question_and_the_month_end_figure_are_the_limit_changes_recipe():
    assert R.match({"name": "Which limits to change and by how much?"}, strict=False)["id"] == "limit_changes"
    figs = [{"name": "Largest single‑name exposure", "definition": "Highest direct issuer exposure as a percentage of total included assets at each month‑end"},
            {"name": "Breach count at 5 % limit", "definition": "Number of holdings where the single‑name exposure exceeds 5 % at month‑end"},
            {"name": "Breach count at 6 % limit", "definition": "Number of holdings where the single‑name exposure exceeds 6 % at month‑end"}]
    goal = ("Our single-name limit is 5 percent and one holding keeps breaching it. Before the annual review show me the largest single name at each month end, and how many "
            "breaches a 5 percent limit and a 6 percent limit would have caused, so the committee can decide.")
    ks = copy.deepcopy(figs)
    R.bind(None, None, ks, "Which limits to change and by how much?", goal)
    assert ks[0]["built_from"] == "limit_changes"


def test_uc048_the_limit_changes_answer_says_every_month_end_and_the_breaches_each_limit_would_have_caused():
    k = key("uc-048-policyupd")
    months = k["max_single_name_pct_by_month_end"]
    names = {"2026-04-30": "Kingfisher Telecom 4.6% 2030 bond"}
    rows = [{"version_number": 1, "limit_pct": 5, "is_opening": True, "month_end": date(2026, 3, 31), "largest_holding": "Opening Holding", "largest_name_pct": 5.55,
             "months_tested": 6, "breaches_in_period": 6}]
    for v, lim, br in ((1, 5, 6), (2, 6, 1)):
        for d, pct in months.items():
            rows.append({"version_number": v, "limit_pct": lim, "is_opening": False, "month_end": date.fromisoformat(d),
                         "largest_holding": names.get(d, "Harborview Semiconductor"), "largest_name_pct": pct, "months_tested": 6, "breaches_in_period": br})
    said = F.say(R.recipe("limit_changes"), rows)
    for pct in months.values():
        assert f"{pct}%" in said, (pct, said)
    assert "Opening Holding" not in said and "6 of 6 month ends would have been breaches" in said and "1 of 6 would have been" in said


# ---- no recipe table is dropped by the plan check ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rid", [r["id"] for r in R.recipes()])
def test_every_recipe_table_passes_the_rate_guard(rid):
    """uc-071 (r7): payout_pct was a percent that the SQL multiplied but never divided, so the plan check dropped the whole table and the answer was 'Not available yet'."""
    assert PG.rate_without_division(R._table("r7", R.recipe(rid), {"name": "x"})) is None


def test_uc071_the_payout_percent_is_worked_out_by_a_division():
    assert "/" in R.recipe("expected_distributions")["sql"]


def test_r7_uc076_a_managers_team_change_mail_dropped_flat_is_manager_news():
    """uc-076: in a flat dropbox the personnel mails were never read, so Northgate scored 91.8 instead of 86.8. Only the two team-change mails are."""
    from pathlib import Path

    from sh_platform.v1.v3_pack_readers import kind_of
    root = Path(__file__).parent / "fixtures" / "office6m"
    news = sorted(p.name for p in root.rglob("*.eml") if (k := kind_of(p.name, p.read_bytes())) and k[0] == "manager_news")
    assert news == ["2026-08-18_saltmarsh_personnel.eml", "2026-09-09_northgate_personnel.eml"]
