"""W7 shared data: a file belongs to the office, not to one build. In one office, thread A reads the bank statement and the call notice into the
warehouse; thread B, whose brief needs the same sources, reaches Decision 2 with "Already in the office" and is not asked for files again.
A source no file ever came for still asks. A file arriving for two open builds goes to one reader, not to a question.

Real: the office6m files, a company plane and its warehouse, the drop folder and file registry, the pack readers, Harbor's a_samples, a_intake
and Decision 2. Stubbed: the 2.0 API calls (recorded). Synthetic data only."""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import wh

OFFICE = Path(__file__).resolve().parent / "fixtures" / "office6m"
A_FILES = ["2026-10/bank_statements/HB_HOLD_USD_2026-09.xlsx", "2026-10/notices/2026-10-13_C_call7.pdf"]
STANDING = ["reference/master_data.json", "reference/accounts.csv", "reference/standing_instructions.csv", "reference/vendor_master.csv", "reference/fund_terms.csv",
            "reference/office_rules.csv", "reference/EG_security_master_20261008.xlsx", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf"]


def thread(plane, tid, title, sources, who="Mei Tan"):
    th = {"id": tid, "title": title, "sources": sources, "started_by": who, "created": f"2026-10-17T08:00:0{tid[-1]}Z", "stage": "working", "events": [], "steps": [],
          "pid": f"prj-{tid}", "systems": [{"id": "s1", "name": "Bank"}, {"id": "s2", "name": "Notices"}], "intake": {}}
    H.save(plane, th)
    calls: list = []

    def api(who, method, path, body=None, **kw):
        calls.append((method, path))
        return []
    return types.SimpleNamespace(app=None, plane=plane, th=th, api=api, calls=calls)


@pytest.fixture()
def office(tmp_path):
    """Thread A has read the bank statement and the call notice into the warehouse."""
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("w7")
    H._fp(plane).parent.mkdir(parents=True, exist_ok=True)
    reg = []
    for rel in [*A_FILES, *STANDING]:
        H.drop(plane, Path(rel).name, (OFFICE / rel).read_bytes())
        mine = rel in A_FILES
        reg.append({"name": Path(rel).name, "arrived_at": "2026-10-13T08:00:00Z", "status": "recognised" if mine else "waiting", "source": "", "thread": "t-a" if mine else None})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")
    a = thread(plane, "t-a", "Cash by bank", ["Bank balances", "Capital call notices"], who="Sam Lee")
    PK.intake(a)
    assert PK.load(a) == (2, [])
    return plane


def test_a_second_build_uses_what_the_first_loaded_and_is_not_asked_for_files(office):
    b = thread(office, "t-b", "Can we fund the next call?", ["Bank balance feed", "Call notice"])
    assert H.a_samples(b) == "2 files given to Span as samples"  # the office's files, as samples for the design; nothing is asked
    out = H.a_intake(b)
    assert out.endswith("2 sources already in the office") and b.th["pack"] == {} and b.th["intake"] == {}  # not read again
    d = H.d2(b)
    lines = [f["read_as"] for f in d["files"]]
    assert any(t.startswith("Already in the office: Bank balance feed (loaded 20") and t.endswith("by Sam Lee's Cash by bank)") for t in lines), lines
    assert any(t.startswith("Already in the office: Call notice (loaded ") for t in lines), lines
    assert not any("no files" in q["text"] for q in d["questions"])
    assert {f["name"]: f["thread"] for f in H.read_files(office)}["HB_HOLD_USD_2026-09.xlsx"] == "t-a"  # still the reader's file; shared, not moved


def test_a_source_that_never_arrived_still_asks(office):
    c = thread(office, "t-c", "Payroll run", ["Payroll register"])
    with pytest.raises(H.Q, match="I have no files to read yet"):
        H.a_samples(c)


def test_a_file_for_two_open_builds_goes_to_one_reader_not_a_question(office):
    ths = [{"id": t, "stage": "decision1", "sources": ["Bank balances"]} for t in ("t-x", "t-y")]
    status, source, tid = H.recognise(office, "bank_balances_2026-10.csv", ths)
    assert status == "recognised" and source == "Bank balances" and tid in ("t-x", "t-y")


def test_a_brief_that_names_no_source_finds_the_office_files_by_its_question(office):
    d = thread(office, "t-d", "Every morning I check cash at the bank for each entity", [])
    assert "bank statement" in H.office_files(d) and H.a_samples(d).endswith("given to Span as samples")
