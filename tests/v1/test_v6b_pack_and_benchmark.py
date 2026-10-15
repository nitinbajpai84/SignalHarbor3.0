"""V6B: the design pack carries the full target model and a benchmark block; the builder compares the run with the uploaded report line by line; the walk story
(version 1 reads the sleeve weight wrongly, the architect corrects the line, version 2 clears) is played on a freshly seeded company by tools/seed_walk_benchmark.py
with no model and no figure typed into product code; Lumen's starter reads the pack's portfolio and shows rates as percentages by month; North's largest system
prompt leaves 2,000 characters under the gateway's limit."""
from decimal import Decimal

import pytest

from sh_platform.egress.rows import MAX_STRING_CHARS
from sh_platform.plane import PlaneStore
from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import b9_verify as V
from sh_platform.v1 import b11_builder as BU
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import wh
from tools import seed_10uc as S
from tools import seed_walk_benchmark as W


def test_north_largest_system_prompt_leaves_two_thousand_characters_under_the_gateway_limit(tmp_path):
    """The string the model client is given is the system prompt plus the loop's rules. The gateway refuses any one string over MAX_STRING_CHARS (the V6 walk's
    first North turn failed at 20,033). Measured over the default goals and every template's goals, on the repo's skill files."""
    from sh_platform.agents import loop
    from sh_platform.v1 import g1_access as G1
    from sh_platform.v1 import i6_chat as C
    from sh_platform.v1 import t1_templates as T1
    plane = PlaneStore(tmp_path / "data").create("acme")
    T1.ensure(plane)
    sizes = {"default goals": len(C.system_prompt(plane, C.GOALS) + "\n\n" + loop._RULES)}
    for t in T1._all(plane):
        goals = G1.place(T1.goals_from(t)) or C.GOALS
        sizes[t["id"]] = len(C.system_prompt(plane, goals) + "\n\n" + loop._RULES)
    worst = max(sizes, key=sizes.get)
    assert sizes[worst] <= MAX_STRING_CHARS - 2000, f"{worst} is {sizes[worst]} characters; the limit is {MAX_STRING_CHARS}"


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("v6b")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    V_ = S.viewers(ids)
    got = W.play(plane, V_["Leo Park"], V_["Anita Rao"])
    got.update(plane=plane, eng=V_["Leo Park"], head=V_["Anita Rao"])
    yield got
    mp.undo()


def test_the_pack_has_the_three_gold_tables_typed_with_grain_keys_owners_and_type_two(walk):
    pack = walk["pack_drawn"]
    by = {g["name"]: g for g in pack["target"]["gold"]}
    names = list(by)
    for suffix in ("_benchmark_monthly", "_holdings_monthly", "_net_worth_entity_monthly"):
        assert any(n.endswith(suffix) for n in names), suffix
    bm = next(g for n, g in by.items() if n.endswith("_benchmark_monthly"))
    types = {c["name"]: c["type"] for c in bm["columns"]}
    assert types == {"portfolio_code": "VARCHAR", "benchmark_code": "VARCHAR", "month": "DATE", "portfolio_return": "DECIMAL(9,6)", "benchmark_return": "DECIMAL(9,6)",
                     "difference": "DECIMAL(9,6)"}
    assert bm["keys"] == ["portfolio_code", "benchmark_code", "month"] and bm["grain"] == "Portfolio, Benchmark, Month" and bm["owner"]
    hold = next(g for n, g in by.items() if n.endswith("_holdings_monthly"))
    ht = {c["name"]: c["type"] for c in hold["columns"]}
    assert ht["value"] == "DECIMAL(18,2)" and ht["month"] == "DATE" and ht["fund"].startswith("VARCHAR")
    assert hold["history"] == ["manager_name", "asset_class"] and hold["keys"] == ["portfolio_code", "fund", "month"]  # type 2: a manager or class change keeps the past
    nw = next(g for n, g in by.items() if n.endswith("_net_worth_entity_monthly"))
    assert {c["name"]: c["type"] for c in nw["columns"]}["net_worth"] == "DECIMAL(18,2)" and nw["keys"] == ["entity", "month"]
    inst = next(s for s in pack["target"]["silver"] if s["name"] == "instruments")
    assert inst["status"] == "extended" and "type 2" in inst["note"]
    assert not K.open_rows(pack) and not any("could not place" in n for n in pack["notes"])  # the benchmark KPIs are not left as rows a person settles in words


def test_one_definition_per_figure_and_each_column_carries_its_own(walk):
    pack = walk["pack_drawn"]
    defs = {d["name"]: d for d in pack["definitions"]}
    assert set(defs) == {"Portfolio return", "Benchmark return", "Net worth"}
    assert defs["Portfolio return"]["source"] == "Signed in the intent" and "net flows" in defs["Portfolio return"]["definition"]
    assert defs["Benchmark return"]["source"] == "Signed: benchmark version 1" and "EG-OFFICE-BLEND" in defs["Benchmark return"]["definition"]
    assert "private-markets sleeve" in defs["Benchmark return"]["definition"]
    cols = {f"{g['name']}.{c['name']}": c["definition"] for g in pack["target"]["gold"] for c in g["columns"]}
    pr = next(v for k, v in cols.items() if k.endswith("_benchmark_monthly.portfolio_return"))
    br = next(v for k, v in cols.items() if k.endswith("_benchmark_monthly.benchmark_return"))
    assert pr == defs["Portfolio return"]["definition"] and br == defs["Benchmark return"]["definition"] and pr != br  # not one copied text
    assert defs["Net worth"]["columns"]


def test_the_benchmark_block_names_the_portfolio_the_signed_benchmark_and_the_month(walk):
    b = walk["pack_drawn"]["benchmark"]
    assert (b["portfolio"], b["code"], b["version"], b["month"]) == ("EG-LIQUID", "EG-OFFICE-BLEND", 1, "2026-09")
    assert [f["key"] for f in b["figures"]] == ["portfolio_return", "benchmark_return", "difference"]
    assert b["names"]["IDX:GLEQ:SYN plus spread"] == "Private-markets sleeve"
    figs = walk["pack_drawn"]["key_figures"]
    assert {"Total holdings", "Net worth"} <= {f["label"] for f in figs} and any(f.get("by") == "fund" for f in figs)
    assert walk["pack_drawn"]["rules"]["benchmark"].startswith("checked against EG-OFFICE-BLEND version 1 for EG-LIQUID in 2026-09")


def test_the_plan_carries_the_block_and_the_key_figures_for_the_builder(walk):
    plan = BU.pack_of(walk["plane"], walk["project_id"])
    assert plan["benchmark"]["portfolio"] == "EG-LIQUID" and plan["benchmark"]["month"] == "2026-09" and plan["key_figures"] and plan["own_batches"]
    assert plan["pack_version"] == 2


def line(var, name):
    return next(x for x in var["lines"] + var["legs"] if x["figure"] == name)


def test_version_1_reads_the_sleeve_weight_wrongly_and_the_variance_is_unexplained(walk):
    v = walk["variance1"]
    sleeve, bench, port = line(v, "Private-markets sleeve"), line(v, "Office blend"), line(v, "Portfolio")
    assert sleeve["status"] == "unexplained" and Decimal(sleeve["run"]).quantize(Decimal("1")) == 28 and sleeve["report"] == "30"
    assert bench["status"] == "unexplained" and Decimal(bench["run"]).quantize(Decimal("0.01")) != Decimal("2.71")
    assert port["status"] == "matches" and line(v, "Global equity index")["status"] == "matches" and line(v, "Global bond index")["status"] == "matches"
    held = line(v, W.HELD)
    assert held["status"] == "explained" and held["evidence"][0]["text"].startswith(f"{W.HELD} amended")  # a revision with its evidence, from the records
    diff = line(v, "Difference")
    assert Decimal(diff["run"]).quantize(Decimal("0.01")) == Decimal("1.53") and diff["status"] == "explained" and diff["evidence"][0]["text"].startswith("Follows the benchmark")  # H8
    assert v["summary"]["unexplained"] == 2 and walk["round1"]["state"] in ("ran", "checked")


def test_version_2_reads_the_signed_weights_and_the_rerun_clears_at_2_71_against_4_17(walk):
    v = walk["variance2"]
    assert v["summary"]["unexplained"] == 0 and v["headline"].startswith("Matches")
    bench, sleeve, diff = line(v, "Office blend"), line(v, "Private-markets sleeve"), line(v, "Difference")
    assert Decimal(bench["run"]).quantize(Decimal("0.01")) == Decimal("2.71") and bench["status"] == "matches"
    assert Decimal(line(v, "Portfolio")["run"]).quantize(Decimal("0.01")) == Decimal("4.17")
    assert Decimal(diff["run"]).quantize(Decimal("0.01")) == Decimal("1.46") and diff["status"] == "matches"  # +1.46 points
    assert Decimal(sleeve["run"]).quantize(Decimal("1")) == 30 and sleeve["status"] == "matches"
    rec = BU.load(walk["plane"], walk["project_id"])
    assert len(rec["rounds"]) == 2 and rec["rounds"][0]["pack_version"] < rec["rounds"][1]["pack_version"] and rec["rounds"][1]["state"] == "checked"  # FIXC: approving a pack also approves its plan, so plan versions skip
    pf = walk["project_id"]
    ch = K.diff(walk["plane"], pf, 1, 2)["changes"]
    assert any(c["line"].endswith("benchmark_weights.component_weight") for c in ch)  # Compare versions shows the line that was corrected


def test_go_live_then_lumen_proposes_a_starter_that_reads_the_pack_portfolio_by_month(walk):
    plane, pid = walk["plane"], walk["project_id"]
    said = BU.go_live(plane, walk["eng"], pid, {})["thread"][-1]["text"]
    fresh = K.get(plane, pid)["rules"]["refresh"]           # FIX1: the live schedule is the pack's refresh rule, its day too
    assert f"({fresh['freq']} at {fresh['at']}, by the {fresh['day']})" in said, said
    got = L.propose_starter(plane, pid)
    titles = {t["title"]: t for t in got["tiles"]}
    ret = next(t for n, t in titles.items() if n.lower().startswith("portfolio return"))
    assert "latest month" in ret["title"] and "EG-LIQUID" in ret["title"]
    cols, rows, _ = D.run_sql(plane, ret["sql"])
    assert len(rows) == 1 and Decimal(str(rows[0]["portfolio_return"])).quantize(Decimal("0.0001")) == Decimal("0.0417")  # the liquid portfolio, not every portfolio added up
    trend = next(t for n, t in titles.items() if "against" in n.lower())
    x = trend["spec"]["encoding"]["x"]
    assert x["timeUnit"] == "yearmonth" and x["axis"]["format"] == "%b %Y"
    _, series, _ = D.run_sql(plane, trend["sql"])
    assert {r["series"] for r in series} and all(abs(Decimal(str(r["value"]))) < Decimal("0.2") for r in series if r["value"] is not None)
    mine = [f for f in V.figures(plane, pid) if "batch" in f["traced_to"]]
    assert mine == []  # this plan loads no file of its own, so none of the company's other control totals are shown on its page
