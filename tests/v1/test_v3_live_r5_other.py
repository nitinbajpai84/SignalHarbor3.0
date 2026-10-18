"""Live run 5, the readers, intake and stuck fixer (docs/v3/LIVE-R5-ANALYSIS.md, "Other").

uc3 (r4 PASS, r5 STUCK): a ready table Span designed with the model calls to_char; the run on the copy failed and the card stopped. The table now comes
out of the pack and only its figure is held. uc-039: the manager statements share no word of their name with the source "Manager statements", so no
thread claimed them. uc-099: the pinnacle feed went the generic way. uc-060: IMG_2210.pdf and data_export.xlsx never reached the inbox reader. uc-098:
the mail proposing 'dry powder' was kept as context. Each case is the office6m files read the way a live dropbox is (test_w3_intake.py's flat_thread);
the r4-passing cases the new recognitions could touch are pinned on the whole office with their live question and North's figures. Synthetic data only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import v3_recipes as R

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W2 = _load("w2_loader_tests_r5_other", Path(__file__).with_name("test_w2_loader.py"))
W3 = _load("w3_intake_tests_r5_other", Path(__file__).with_name("test_w3_intake.py"))
VP = _load("v3_persona_r5_other", REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_persona.py")


def _waiting(plane, rels: list[str]) -> None:
    """Office files in the drop folder that no thread has claimed yet."""
    reg = json.loads(H._fp(plane).read_text(encoding="utf-8"))
    for rel in rels:
        H.drop(plane, Path(rel).name, (OFFICE / rel).read_bytes())
        reg.append({"name": Path(rel).name, "arrived_at": "2026-10-13T08:00:00Z", "status": "waiting", "source": "", "thread": None})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")


# ---- uc3: a failed model design holds one figure, the card goes on ---------------------------------------------------------------------------

class _Api:
    """The builder and the pack as the chain sees them: the first round failed on the model table, the round after the edit is ok."""
    def __init__(self, table: str, kpis: list[str]):
        self.gold = [{"name": table, "kpis": kpis}, {"name": "gold_x_missing_statements", "kpis": ["Missing statements count"]}]
        self.calls, self.failed = [], True

    def __call__(self, who, method, path, body=None, files=None, data=None, soft=False):
        self.calls.append((method, path, body))
        if path.endswith("/pack"):
            return {"pack": {"state": "approved", "target": {"gold": self.gold}}}
        if path.endswith("/pack/edit") and body["section"] == "gold_remove":
            self.gold = [g for g in self.gold if g["name"] != body["key"]]
            self.failed = False
            return {}
        if path.endswith("/builder"):
            err = f"{self.gold[0]['name']} could not be built: Catalog Error: Scalar Function with name to_char does not exist!" if self.failed else None
            return {"can": {}, "round": {"state": "ran", "run": {"run_id": "r1", "status": "failed" if self.failed else "ok", "error": err,
                                                                  "steps": [{"status": "failed", "label": "Chase drafts."}] if self.failed else []}}}
        return {}


def _x(api, model: bool = True):
    import types
    t = "gold_for_every_fund_i_want_statement_status"
    th = {"id": "t-uc3", "pid": "prj-1", "model_tables": {t: True} if model else {}, "figures": [{"kpi": "Chase‑email drafts prepared", "table": t}]}
    return types.SimpleNamespace(th=th, api=api, plane=None), t


def test_uc3_a_model_table_the_warehouse_cannot_build_is_held_and_the_run_goes_on(monkeypatch):
    from sh_platform.v1 import v3_rows
    sent = []
    monkeypatch.setattr(v3_rows, "send", lambda x: sent.append(1))
    api = _Api("gold_for_every_fund_i_want_statement_status", ["Chase‑email drafts prepared"])
    x, t = _x(api)
    assert H.b_run(x) == "ran on a copy"  # was: "The run on the copy stopped at the step that builds ...: it calls to_char ..." and the card STUCK
    assert ("PUT", "/api/v1/build/p/prj-1/architecture/pack/edit") in [(m, p) for m, p, _ in api.calls]
    assert [g["name"] for g in api.gold] == ["gold_x_missing_statements"] and sent == [1]
    assert x.th["held_tables"][t]["answered"] == "left out"  # cover() does not design it again; Decision 2 does not ask about it
    assert "to_char" in x.th["figure_notes"]["Chase‑email drafts prepared"]


def test_uc3_a_recipe_table_that_fails_is_still_a_question(monkeypatch):
    from sh_platform.v1 import v3_rows
    monkeypatch.setattr(v3_rows, "send", lambda x: None)
    api = _Api("gold_for_every_fund_i_want_statement_status", ["Chase‑email drafts prepared"])
    x, _ = _x(api, model=False)
    with pytest.raises(H.Q, match="to_char"):
        H.b_run(x)
    assert len(api.gold) == 2


# ---- uc-039: the manager statements are claimed by their kind --------------------------------------------------------------------------------

STATEMENTS = sorted(str(p.relative_to(OFFICE)).replace("\\", "/") for p in OFFICE.glob("*/manager_statements/*_final.pdf"))
REGISTER = "2026-10/commitments/commitments_register_2026-10-13.xlsx"
NOTICES = sorted(str(p.relative_to(OFFICE)).replace("\\", "/") for p in [*OFFICE.glob("*/notices/*_call*.pdf"), *OFFICE.glob("*/notices/*_distribution.pdf")])


def test_uc039_statements_no_thread_claimed_are_read_for_a_brief_whose_source_is_manager_statements(tmp_path):
    plane, x = W3.flat_thread(tmp_path, [*NOTICES, REGISTER])
    _waiting(plane, STATEMENTS)
    x.th["sources"] = ["Capital call notices", "Distribution notices", "Manager statements"]  # the r5 thread's sources
    PK.intake(x)
    kinds = {v["kind"] for n, v in x.th["pack"].items() if n in {Path(s).name for s in STATEMENTS}}
    assert kinds == {"manager_statements"} and sum(1 for v in x.th["pack"].values() if v["kind"] == "manager_statements") == len(STATEMENTS)
    n, aside = PK.load(x)
    assert aside == [] and n == len(STATEMENTS) + len(NOTICES) + 1
    o = W2.Loaded(plane, None)
    assert o.one("select count(*) from valuation_observations") > 0  # r5: "it reads valuation observations, which hold nothing yet"
    assert {r["fund"] for r in o.run("fund_irr_tvpi") if r["tvpi"] is not None} >= {"Evergreen Growth I", "Evergreen Income II"}  # r5: 0 rows
    o.con.close()


def test_uc039_a_kind_claims_only_for_a_source_that_names_all_its_words(tmp_path):
    plane, x = W3.flat_thread(tmp_path, [])
    _waiting(plane, STATEMENTS[:2])
    x.th["sources"] = ["Capital call notices", "Policy document"]  # "capital" is a word of the statement's plain name, not of its kind
    assert PK.claim(x) == 0
    assert all(f["thread"] is None for f in H.read_files(plane) if f["name"] in {Path(s).name for s in STATEMENTS})


# ---- uc-099, uc-060, uc-098: recognised by content -------------------------------------------------------------------------------------------

PINNACLE = ["2026-10/new_feed/pinnacle_custody_positions_2026-10-12.csv", "2026-10/new_feed/pinnacle_cover_note.pdf"]


def test_uc099_the_new_custodian_feed_is_profiled_not_mapped_the_generic_way(tmp_path):
    for rel in PINNACLE:
        assert PK.kind_of(Path(rel).name, (OFFICE / rel).read_bytes()) == ("new_feed", Path(rel).name)
    assert PK.kind_of("fund_flows.csv", W3.GENERIC) is None  # a table with a model field in its header is not a new feed
    plane, x = W3.flat_thread(tmp_path, PINNACLE)
    PK.intake(x)
    assert PK.load(x) == (2, [])
    o = W2.Loaded(plane, None)
    rows = [r for r in o.run("feed_mapping") if str(r["feed"]).startswith("pinnacle")]
    assert rows and {r["source_column"] for r in rows if r["in_doubt"]} == {"Value", "Dt"}
    assert o.one("select count(*) from position_snapshots") == 0  # no rows load until the mapping is approved
    said = F.say(R.recipe("feed_mapping"), rows)
    assert VP.missing(VP.said({"answer": said, "rows": rows}), ["Value"]) == []
    o.con.close()


INBOX = ["2026-10/inbox/IMG_2210.pdf", "2026-10/inbox/data_export.xlsx", "2026-10/inbox/scan_0412.pdf", "2026-10/inbox/account_extract.xlsx"]


def test_uc060_a_brief_about_the_inbox_reads_every_unknown_file_as_an_inbox_file(tmp_path):
    plane, x = W3.flat_thread(tmp_path, INBOX)
    x.th["bindings"] = [{"figure": "Inbox files and where they belong", "recipe": "unrecognised_files"}]  # the r5 binding
    PK.intake(x)
    assert {n: v["kind"] for n, v in x.th["pack"].items()} == {Path(r).name: "inbox" for r in INBOX}
    assert PK.load(x) == (4, [])
    o = W2.Loaded(plane, None)
    rows = o.run("unrecognised_files")
    assert {r["file"] for r in rows if r["unrecognised"]} == {"IMG_2210.pdf", "data_export.xlsx"}
    said = F.say(R.recipe("unrecognised_files"), rows)
    assert VP.missing(VP.said({"answer": said, "rows": rows}), ["IMG_2210.pdf", "data_export.xlsx", "scan_0412.pdf"]) == [], said
    o.con.close()


def test_uc060_other_briefs_keep_unknown_files_on_the_generic_path(tmp_path):
    plane, x = W3.flat_thread(tmp_path, INBOX[:2])
    PK.intake(x)
    assert x.th["pack"] == {} and {f["name"] for f in H.my_files(x, "source")} == {"IMG_2210.pdf", "data_export.xlsx"}  # the generic paths still see them


def test_uc098_the_mail_proposing_words_is_read_by_the_glossary_reader(tmp_path):
    rel = "2026-10/glossary/2026-10-06_word_proposal.eml"
    assert PK.kind_of("w.eml", (OFFICE / rel).read_bytes()) == ("glossary", "w.eml")
    for p in OFFICE.rglob("*.eml"):  # every other mail of the office stays a document (v3_docs)
        if p.name != Path(rel).name:
            assert PK.kind_of(p.name, p.read_bytes()) is None, p.name
    files = [rel, "2026-10/glossary/office_words_2026-10-01.csv", "2026-10/glossary/word_review_2026-10-08.md"]
    plane, x = W3.flat_thread(tmp_path, files)
    PK.intake(x)
    assert PK.load(x) == (3, [])
    o = W2.Loaded(plane, None)
    rows = o.run("terms_proposed")
    said = F.say(R.recipe("terms_proposed"), rows)
    assert VP.missing(VP.said({"answer": said, "rows": rows}), ["side letter", "stub period", "capital account", "dry powder"]) == [], said
    o.con.close()


# ---- the r4-passing cases the new recognitions touch: the whole office, their live question and North's figures ---------------------------------

PINNED = [  # card, the live ask, North's figures (name, definition, recipe or "")
    ("uc-016-schemadrift", "The administrator renamed a column. What breaks, and is the new mapping safe?",  # the pinnacle mapping now sits beside the renamed one
     [("Column‑mapping safety check", "Whether the renamed column matches the expected data type and values against the source statement", ""),
      ("Load‑pause duration", "Time elapsed between pausing the load and approving the new mapping", ""),
      ("Columns added, renamed or dropped", "For each sheet, the columns of the latest proposed mapping (the one Harbor drew up for the file that just arrived) set against the latest approved mapping. A target field with a different source column is renamed; one only in the proposal is added; one only in the approved mapping is dropped. batches_on_old_name counts the batches already loaded under the approved mapping of the same source system and sheet.", "columns_changed"),
      ("New feed columns mapped and in doubt", "For each mapping whose columns carry a confidence mark (a profiled new feed) and each of its columns: the target and the confidence (high, medium or doubt). Per mapping: columns, mapped_with_confidence (high), share_mapped_pct (high over columns, whole percent), rows_in_sample (from the batch that profiled the file) and safe_to_go_live = 1 only when the mapping is approved and no column is in doubt.", "feed_mapping"),
      ("Change since the issued report", "For each valuation that supersedes another (the link on the valuation), the original value is the valuation it replaces, the amended value is the replacing one, and the change is amended less original. Only the latest amendment of a chain counts.", "change_since_report")]),
    ("morning-networth-note", "What are we worth in the latest report?",  # the word-proposal mail now goes to the glossary reader in this thread too
     [("Net worth", "Total value of all assets plus cash, in the chosen currency", "net_worth"),
      ("Change since previous note", "Difference in net worth compared with the prior day's note", "change_since_report"),
      ("Attention items", "Any material break, missing price, or cash shortfall flagged for review", "")]),
]


@pytest.fixture(scope="module")
def office(tmp_path_factory):
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    import score50
    plane, con, _ = score50.load(tmp_path_factory.mktemp("r5_other"))
    tables = []
    for rid in sorted({rid for _, _, figs in PINNED for *_, rid in figs if rid}):
        r = R.recipe(rid)
        name = f"gold_r5o_{rid}"
        con.execute(R.render(r, name, R.dims_for(r, {})))
        cols = con.execute("select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position", [name]).fetchall()
        tables.append({"name": name, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f"select count(*) from {name}").fetchone()[0],
                       "purpose": f"{R.MARK}{rid}: {r['label']}", "kpis": []})
    con.close()
    return plane, tables


@pytest.mark.parametrize("card, ask, figs", PINNED, ids=[c[0] for c in PINNED])
def test_r4_passing_case_still_answers_its_live_question(office, monkeypatch, card, ask, figs):
    from sh_platform.v1 import b10_pack as P, cx_dash as CD, talk
    plane, tables = office
    kpis = [{"name": n, "definition": d, "built_from": rid} for n, d, rid in figs]
    monkeypatch.setattr(F, "kpis_of", lambda plane_, iid: [dict(k) for k in kpis])
    monkeypatch.setattr(P, "latest_approved", lambda *a, **k: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"], "kpis": t["kpis"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a, **k: tables)
    monkeypatch.setattr(talk, "reachable", lambda *a, **k: ([{"id": "prj-1"}], []))
    th = {"id": f"t-{card}", "pid": "prj-1", "iid": f"ini-{card}", "figures": [], "steps": []}
    got = F._answer(plane, None, ask, "prj-1", th)
    assert got and got["answer"] and not got["answer"].startswith("Not available yet"), (card, got)
    _, build = VP.load_uc(card)
    assert VP.missing(VP.said(got), build["check"]["expect"]) == [], got["answer"][:1500]
