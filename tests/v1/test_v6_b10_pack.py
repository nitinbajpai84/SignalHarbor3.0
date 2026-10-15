"""V6 b10: the Architecture step. Read before asking (systems shown from the intent), the minimal question set with defaults, samples (Excel profiled by
the existing scan, PDF fields marked and stored for the reader), the design pack as versioned data, correctable lines, approval by the head of data
(never the maker), locking and a new version with a diff, and the approved pack drawing the b6 plan."""
import io

import pytest

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import e0b_mappings as M
from sh_platform.v1 import p1_project as P
from sh_platform.v1.i2_north import Refused

ENG = Viewer("Leo Park", frozenset({"analyst"}), False, "acc-leo")
HEAD = Viewer("Anita Rao", frozenset({"analyst", "head_of_data"}), False, "acc-anita")
READER = Viewer("Mei Chen", frozenset({"sponsor"}), False, "acc-mei")
IID = "ini-" + "a1" * 16


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    sow = {"state": "signed", "title": "Monthly investment report", "goal": {"line": "One page a month", "readers": ["Family council"], "needed_by": "5th business day"},
           "process": {"steps": [{"name": "Check totals", "control": "Administrator total equals the file footer"},
                                 {"name": "Compare", "control": "Administrator and trading export agree within 5,000 USD per entity"}]},
           "sources": [{"id": "src-admin", "name": "Administrator export", "kind": "file", "structure": "structured", "holds": "valuations by month", "owner": "Mei Tan",
                        "channel": "sftp", "arrives": "daily"},
                       {"id": "src-trade", "name": "Trading export", "kind": "file", "structure": "structured", "holds": "trades and cash", "owner": "Arjun Mehta", "arrives": "daily"},
                       {"id": "src-stmt", "name": "Manager statements", "kind": "document", "structure": "unstructured", "holds": "manager statements",
                        "owner": "Mei Tan", "arrives": "monthly"}],
           "kpis": [{"code": "K1", "name": "Net worth by month", "definition": "Sum of valuations", "formula": "", "unit": "USD", "period": "monthly",
                     "owner": "Priya Nair", "sources": [], "benchmark_by": ["month"]},
                    {"code": "K2", "name": "Valuation by currency", "definition": "Valuations by currency", "formula": "", "unit": "USD", "period": "monthly",
                     "owner": "Priya Nair", "sources": [], "benchmark_by": ["month", "currency"]},
                    {"code": "K3", "name": "Customer happiness", "definition": "", "formula": "", "unit": "", "period": "", "owner": "x", "sources": [], "benchmark_by": []}],
           "governance": []}
    plane.path("intents", IID).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", IID, "sow.json"), sow)
    prj = P.create_project(plane, IID, "Monthly investment report", "Mei Chen")
    mid = M.save_proposal(plane, {"file_name": "administrator_export_2026_09.xlsx", "sheet": "Valuations", "purpose": "valuations", "owner": "Mei Tan", "columns": [
        {"source": "Valuation date", "target_table": "valuation_observations", "target_field": "valuation_date", "transform": None},
        {"source": "Value", "target_table": "valuation_observations", "target_field": "value_amount", "transform": None},
        {"source": "Currency", "target_table": "valuation_observations", "target_field": "currency", "transform": None}]})
    M.approve(plane, mid, ENG)
    return plane, prj["id"]


def packed(plane, pid):
    K.accept_all(plane, ENG, pid)
    return K.generate(plane, ENG, pid)


def test_read_before_asking_shows_systems_from_the_intent(world):
    plane, pid = world
    s = K.summary(plane, READER, pid)
    by = {x["name"]: x for x in s["systems"]}
    assert by["Administrator export"]["channel"] == "sftp" and by["Administrator export"]["from_intent"] and by["Administrator export"]["status"] == "never_seen"
    assert by["Trading export"]["channel"] == "" and by["Manager statements"]["format"] == "pdf"
    assert [k["name"] for k in s["kpis"] if not k["signed"]] == ["Customer happiness"]
    assert "I only need to ask you" in s["line"]


def test_only_what_is_missing_is_asked_each_with_a_default(world):
    plane, pid = world
    qs = K.questions(plane, ENG, pid)
    ids = {q["id"] for q in qs["open"]}
    assert "source:src-trade" in ids and "source:src-admin" not in ids  # the intent already says how the administrator export arrives
    assert {"history", "checks", "freshness", "definitions"} <= ids and "grain" not in ids
    by = {q["id"]: q for q in qs["open"]}
    assert by["source:src-trade"]["proposal"] == "sftp" and by["freshness"]["proposal"]["freq"] == "monthly"
    assert [c["kind"] for c in by["checks"]["proposal"]] == ["control_total", "agree"]
    assert by["checks"]["proposal"][1]["tolerance"].startswith("5,000")
    assert "Access: inherited from the intent" in qs["known"] and any(k.startswith("Grain: monthly by currency") for k in qs["known"])
    assert list(by["definitions"]["proposal"]) == ["K3"]  # only the unsigned figure is asked
    assert any("Definitions signed" in k for k in qs["known"])


def test_an_answer_goes_into_the_intent_system_map_so_nobody_asks_twice(world):
    plane, pid = world
    K.answer(plane, ENG, pid, "source:src-trade", "mailbox")
    assert "source:src-trade" not in {q["id"] for q in K.questions(plane, ENG, pid)["open"]}
    s = {x["name"]: x for x in K.systems_of(plane, IID)}["Trading export"]
    assert s["channel"] == "mailbox" and s["intent"]["channel"] == "" and s["corrected"] == ["channel"]
    with pytest.raises(Refused):
        K.answer(plane, ENG, pid, "source:src-trade", "carrier pigeon")
    with pytest.raises(Refused):
        K.answer(plane, READER, pid, "history", [])  # only the data team answers
    from sh_platform.v1 import i2_north as N
    assert "channel" not in N.read_sow(plane, IID)["sources"][1]  # the signed intent itself is untouched


def test_excel_sample_is_profiled_by_the_existing_scan(world):
    plane, pid = world
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["trade_date", "account", "mkt_val"])
    for i in range(3):
        ws.append(["2026-09-3%d" % 0, f"A{i}", 100 + i])
    buf = io.BytesIO()
    wb.save(buf)
    smp = K.sample_table(plane, ENG, pid, "src-trade", "trading_export.xlsx", buf.getvalue())
    assert smp["kind"] == "table" and [c["name"] for c in smp["columns"]] == ["trade_date", "account", "mkt_val"]
    assert K.summary(plane, ENG, pid)["systems"][1]["status"] == "landed"
    with pytest.raises(Refused):
        K.sample_table(plane, ENG, pid, "src-trade", "notes.pdf", b"%PDF-1.4 x")


def test_pdf_fields_are_marked_and_stored_for_the_reader(world):
    fitz = pytest.importorskip("fitz")
    plane, pid = world
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Valuation date: 30 September 2026")
    page.insert_text((72, 100), "Net asset value 10,180,000")
    pdf = doc.tobytes()
    smp = K.sample_pdf(plane, ENG, pid, "src-stmt", "statement.pdf", pdf)
    lines = K.sample_lines(plane, ENG, pid, "src-stmt")
    nav = next(x["n"] for x in lines if "Net asset" in x["text"])
    K.mark_field(plane, ENG, pid, "src-stmt", nav, "NAV", "number")
    got = K.mark_field(plane, ENG, pid, "src-stmt", next(x["n"] for x in lines if "Valuation" in x["text"]), "Date", "date")
    assert smp["kind"] == "pdf" and {f["name"] for f in got["fields"]} == {"NAV", "Date"}
    assert next(f for f in got["fields"] if f["name"] == "NAV")["example"] == "10180000"
    from sh_platform.v1 import x5_extract as X
    t = X.read_spec(plane, IID)["types"][0]
    assert t["state"] == "confirmed" and {f["name"] for f in t["fields"]} == {"NAV", "Date"}
    assert "sample:src-stmt" not in {q["id"] for q in K.questions(plane, ENG, pid)["open"]}


def test_pack_is_drafted_with_target_catalogue_mapping_rules_sources(world):
    plane, pid = world
    pack = packed(plane, pid)
    assert pack["version"] == 1 and pack["state"] == "draft" and pack["created_by"] == "Leo Park"
    golds = {g["name"]: g for g in pack["target"]["gold"]}
    assert set(golds) == {"gold_monthly_investment_report_valuation_monthly", "gold_monthly_investment_report_valuation_monthly_by_currency"}
    g = golds["gold_monthly_investment_report_valuation_monthly_by_currency"]
    assert [c["name"] for c in g["columns"]][:2] == ["month", "currency"] and g["keys"] == ["month", "currency"] and g["owner"] == "Priya Nair"
    assert all(c["expr"] and c["definition"] for c in g["columns"])
    assert {s["name"] for s in pack["target"]["silver"]} == {"valuation_observations"}
    row = next(m for m in pack["mapping"] if m["gold"].endswith("by_currency.currency"))
    assert row["bronze"].startswith("bronze_administrator_export") and row["source_field"] == "Currency" and row["system"] == "Administrator export"
    assert any(c["layer"] == "gold" and c["column"] == "currency" for c in pack["catalogue"]) and any(c["layer"] == "bronze" for c in pack["catalogue"])
    assert [c["kind"] for c in pack["rules"]["checks"]] == ["control_total", "agree"] and pack["rules"]["refresh"]["freq"] == "monthly"
    assert {s["code"] for s in pack["sources"]} == {"administrator_export", "trading_export", "manager_statements"}
    amber = {m["system"] for m in K.open_rows(pack)}
    assert {"Trading export", "Manager statements", ""} <= amber  # what a person must settle is named, never guessed
    assert any("Customer happiness" in m["needs_person"] for m in K.open_rows(pack))


def test_history_answer_extends_silver_or_says_where_it_is_missing(world):
    plane, pid = world
    K.answer(plane, ENG, pid, "history", ["currency", "manager"])
    pack = K.generate(plane, ENG, pid)
    silver = pack["target"]["silver"][0]
    assert silver["status"] == "extended" and silver["history"] == ["currency"] and "type 2" in silver["note"]
    assert any("Manager" in n and "model change" in n for n in pack["notes"])
    g = pack["target"]["gold"][1]
    assert g["history"] == ["currency"] and next(c for c in g["columns"] if c["name"] == "currency")["history"]


def test_correct_a_line_is_recorded_and_open_rows_stop_the_send(world):
    plane, pid = world
    pack = packed(plane, pid)
    gname = pack["target"]["gold"][0]["name"]
    out = K.edit(plane, ENG, pid, "gold_table", gname, {"owner": "Daniel Foo", "grain": "Month, currency"}, "per the sponsor")
    assert out["version"] == 1 and [e["field"] for e in out["edits"]] == ["owner", "grain"] and out["edits"][0]["before"] == "Priya Nair"
    with pytest.raises(Refused):
        K.edit(plane, ENG, pid, "gold_table", gname, {"keys": ["nope"]})
    with pytest.raises(Refused):
        K.edit(plane, ENG, pid, "gold_column", f"{gname}.month", {"expr": "drop table x"})
    with pytest.raises(Refused):
        K.edit(plane, ENG, pid, "gold_table", gname, {"sql": "x"})  # a field that is not correctable
    with pytest.raises(Refused) as e:
        K.submit(plane, ENG, pid)
    assert "still need a person" in e.value.message
    with pytest.raises(Refused):
        K.edit(plane, READER, pid, "gold_table", gname, {"owner": "x"})


def settle(plane, pid):
    for m in K.open_rows(K.get(plane, pid)):
        K.edit(plane, ENG, pid, "mapping", m["id"], {"resolve": True}, "settled by Leo")


def test_head_of_data_approves_never_the_maker_and_approval_locks(world):
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    with pytest.raises(Refused):
        K.approve(plane, HEAD, pid)  # still a draft
    K.submit(plane, ENG, pid)
    with pytest.raises(Refused) as e:
        K.approve(plane, ENG, pid)
    assert e.value.status == 403
    with pytest.raises(Refused) as e:
        K.approve(plane, READER, pid)
    assert e.value.status == 403
    p = K.approve(plane, HEAD, pid, note="Keep the tolerance per entity")
    assert p["state"] == "approved" and p["approved_by"] == "Anita Rao"
    v = K.view(plane, HEAD, pid)
    assert v["pack"]["locked"] and not v["can"]["approve"]


def test_new_version_keeps_history_and_diff_and_old_stays_locked(world):
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    K.submit(plane, ENG, pid)
    K.approve(plane, HEAD, pid)
    gname = K.get(plane, pid)["target"]["gold"][0]["name"]
    v2 = K.edit(plane, ENG, pid, "gold_column", f"{gname}.month", {"definition": "Month end"}, "clearer")
    assert v2["version"] == 2 and v2["state"] == "draft" and v2["base_version"] == 1
    assert K.get(plane, pid, 1)["state"] == "approved" and next(c for c in K.get(plane, pid, 1)["target"]["gold"][0]["columns"] if c["name"] == "month")["definition"] != "Month end"
    d = K.diff(plane, pid, 1, 2)
    assert [(c["line"], c["change"]) for c in d["changes"]] == [(f"gold {gname}.month", "changed")]
    assert "Month end" in d["changes"][0]["after"]
    K.submit(plane, ENG, pid)
    K.approve(plane, HEAD, pid)
    assert [(h["version"], h["state"]) for h in K.history(plane, pid)] == [(1, "superseded"), (2, "approved")]
    assert K.latest_approved(plane, pid)["version"] == 2


def test_system_correction_updates_intent_map_and_pack_together(world):
    plane, pid = world
    packed(plane, pid)
    K.edit(plane, ENG, pid, "system", "src-admin", {"frequency": "weekly", "channel": "upload"}, "builder found a weekly file")
    s = {x["name"]: x for x in K.systems_of(plane, IID)}["Administrator export"]
    assert s["frequency"] == "weekly" and s["intent"]["frequency"] == "daily" and sorted(s["corrected"]) == ["channel", "frequency"]
    assert next(x for x in K.get(plane, pid)["sources"] if x["id"] == "src-admin")["channel"] == "upload"


def test_approved_pack_draws_the_plan_and_a_formula_correction_reaches_the_sql(world):
    plane, pid = world
    with pytest.raises(Refused):
        K.apply_to_plan(plane, ENG, pid)  # nothing approved yet
    packed(plane, pid)
    settle(plane, pid)
    gname = "gold_monthly_investment_report_valuation_monthly"
    meas = next(c for c in K.get(plane, pid)["target"]["gold"][0]["columns"] if c["expr"].lower().startswith("sum("))
    K.edit(plane, ENG, pid, "gold_column", f"{gname}.{meas['name']}", {"expr": meas["expr"].replace("SUM(", "AVG(")}, "average, not sum")
    K.submit(plane, ENG, pid)
    K.approve(plane, HEAD, pid)
    plan = K.apply_to_plan(plane, ENG, pid)
    assert plan["state"] == "proposed" and plan["pack_version"] == 1 and plan["proposed_by"] == "Leo Park"
    t = next(x for x in plan["tables"] if x["name"] == gname)
    assert "avg(" in t["sql"].lower() and "sum(" not in t["sql"].lower()
    assert plan["schedule"]["freq"] == "monthly" and K.get(plane, pid, 1)["plan_version"] == plan["version"]
    B.approve(plane, HEAD, pid)  # the existing plan approval still applies, unchanged
    with pytest.raises(Refused):
        K.apply_to_plan(plane, READER, pid)


def test_a_formula_the_plan_check_refuses_stops_the_plan(world):
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    gname = "gold_monthly_investment_report_valuation_monthly"
    K.edit(plane, ENG, pid, "gold_column", f"{gname}.month", {"expr": "f.no_such_column"})
    K.submit(plane, ENG, pid)
    K.approve(plane, HEAD, pid)
    with pytest.raises(Refused) as e:
        K.apply_to_plan(plane, ENG, pid)
    assert "refused" in e.value.message and gname in e.value.message


def test_unsigned_intent_is_refused(world):
    plane, pid = world
    sow = K.S.signed_sow(plane, P.read(plane, pid))
    write_json_atomic(plane.path("intents", IID, "sow.json"), {**sow, "state": "draft"})
    with pytest.raises(Refused):
        K.summary(plane, ENG, pid)


# ---- North (walk gaps 1-3, 7) and the intent system map ----------------------------------------------------------------------------

def test_north_records_how_a_system_arrives_and_how_often():
    from sh_platform.v1 import i6_chat as C
    sow = {"sources": [], "kpis": [], "catalogue": [], "governance": [], "unclear": [], "goal": {}, "process": {"steps": [], "handovers": []}}
    C.merge(sow, {"sources": [{"name": "Index levels", "kind": "file", "owner": "Mei", "channel": "An SFTP folder from the provider", "arrives": "daily", "format": "CSV"}]}, None, {}, "Mei")
    s = sow["sources"][0]
    assert (s["channel"], s["arrives"], s["format"]) == ("sftp", "daily", "csv")
    C.merge(sow, {"sources": [{"name": "Index levels", "channel": "carrier pigeon"}]}, None, {}, "Mei")
    assert sow["sources"][0]["channel"] == "sftp"  # a way it does not arrive by is not recorded, and never replaces what was said


def test_closing_summary_names_what_blocks_the_signature_and_the_benchmark_given(monkeypatch):
    from sh_platform.v1 import i6_chat as C
    monkeypatch.setattr(C, "_sign_gaps", lambda plane, iid: "What the result looks like; What is still unclear")
    monkeypatch.setattr(C, "_benchmark_sheet", lambda plane, iid: {"rows": [{"code": "K01", "reported": 4.17}]})
    sow = {"title": "Monthly performance", "goal": {"line": "One page a month"}, "sources": [], "unclear": [], "process": {"steps": []},
           "kpis": [{"code": "K01", "name": "Portfolio return", "source_ids": [], "benchmark": None}]}
    text = C.closing_summary("ini-" + "a1" * 16, sow, object(), None)
    assert "1 row on the benchmark sheet" in text and "no benchmark given" not in text
    assert "cannot be signed yet: What the result looks like; What is still unclear" in text
    assert "Nothing is left unclear" not in text and "press Sign" not in text and "/api/v1" not in text and "Download a copy" in text


def test_a_long_first_sentence_gives_a_short_project_name():
    from sh_platform.v1 import i6_chat as C
    from sh_platform.v1 import e0a_catalogue as E
    said = "Every month I need a one page report of how our private funds did against the benchmark blend, in USD and SGD, for the family council."
    title, line = C.opening(said)
    assert title == "Report of how our private funds" and line.startswith("Every month")
    assert E.slug_of(said) == "report_of_how_our_private_fund"  # at most 30 characters
    assert C.short_title("Monthly investment report") == "Monthly investment report"  # a short title is left alone


def test_head_of_data_who_corrected_a_line_cannot_approve_it(world):
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    gname = K.get(plane, pid)["target"]["gold"][0]["name"]
    K.edit(plane, HEAD, pid, "gold_table", gname, {"owner": "Anita Rao"}, "mine now")  # Anita also holds the data team seat
    K.submit(plane, ENG, pid)
    with pytest.raises(Refused) as e:
        K.approve(plane, HEAD, pid)
    assert e.value.status == 403 and not K.view(plane, HEAD, pid)["can"]["approve"]


def test_an_answer_must_fit_its_question(world):
    plane, pid = world
    for qid, bad in (("freshness", "tomorrow"), ("history", "manager"), ("checks", ["x"])):
        with pytest.raises(Refused) as e:
            K.answer(plane, ENG, pid, qid, bad)
        assert e.value.status == 400
    assert K.answer(plane, ENG, pid, "history", ["currency"])


def test_a_pack_sent_for_approval_waits_in_the_head_of_datas_action_not_the_makers(world):
    from sh_platform.v1 import p2_assign
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    K.submit(plane, ENG, pid)
    kinds = lambda v: [w["kind"] for w in p2_assign._waiting(plane, v)]  # noqa: E731
    assert "pack" in kinds(HEAD) and "pack" not in kinds(ENG)
    K.approve(plane, HEAD, pid)
    assert "pack" not in kinds(HEAD)


def test_the_plan_carries_how_each_source_arrives_and_the_marked_fields_for_the_builder(world):
    plane, pid = world
    packed(plane, pid)
    settle(plane, pid)
    K.submit(plane, ENG, pid)
    K.approve(plane, HEAD, pid)
    plan = K.apply_to_plan(plane, ENG, pid)
    by = {s["code"]: s for s in plan["sources"]}
    assert by["administrator_export"]["arrives"]["how"] == "sftp" and by["manager_statements"]["arrives"]["how"] == "mailbox"
    assert all("fields" in s for s in plan["sources"])


def test_a_pack_schedule_worded_as_a_working_day_does_not_break_the_next_run():
    from datetime import datetime, timezone
    from sh_platform.v1 import b6_schedule as SCH
    s = {"freq": "monthly", "at": "06:00", "day": "8th working day of each month"}
    assert SCH._dom(s) == 8 and SCH.last_slot(s, datetime(2026, 10, 11, 12, tzinfo=timezone.utc)).day == 8
