"""D1 documents read like a coding agent: files are indexed locally (idempotent, re-indexed on change), search_documents and
read_document serve only files ticked for the conversation that the person may read (not ticked, restricted or another person's
private file is never returned), at most six calls a reply, read capped, tool figures become facts for the reply guard, and a
stub model that issues tool calls ends with an answer carrying the chips."""
import json
import time

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.build.agents.runtime import OpenGate
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import doc_index as DI
from sh_platform.v1 import doc_tools as DT

IID = "ini-" + "a" * 32
POLICY = ("# Investment policy\n\nThis policy defines net worth and time-weighted return.\n\n## Issuer limit\n\n"
          "No single issuer may exceed 10% of net worth at any month end.\n\n## Reporting\n\nThe committee reads the pack monthly.\n"
          + "\n".join(f"Filler line {i} about custody and settlement." for i in range(80)))
SECRET = "# Board salaries\n\nThe issuer limit exception is approved by the chair. Salary pool 4500.\n"
ME, OTHER = Viewer("Ann", frozenset({"analyst"}), False, "acc-ann"), Viewer("Bob", frozenset({"analyst"}), False, "acc-bob")


def item(i, name, path, **kw):
    return {"id": i, "name": name, "kind": "document", "note": "", "uploaded_by": "Seeded", "uploaded_by_id": "", "at": "", "sha256": "",
            "size": 1, "visibility": "company", "path": path, "tags": [], **kw}


@pytest.fixture()
def world(tmp_path):
    (tmp_path / "co" / "documents").mkdir(parents=True)
    (tmp_path / "co" / "documents" / "policy.md").write_text(POLICY, encoding="utf-8")
    (tmp_path / "co" / "documents" / "secret.md").write_text(SECRET, encoding="utf-8")
    (tmp_path / "co" / "documents" / "unticked.md").write_text("The issuer limit is in the unticked file.", encoding="utf-8")
    (tmp_path / "co" / "documents" / "bobs.md").write_text("Issuer limit notes private to Bob.", encoding="utf-8")
    plane = PlaneStore(tmp_path).plane_for("co")
    plane.path("intents", IID).mkdir(parents=True)
    write_json_atomic(plane.path("library", "index.json"), [
        item("lib_1", "policy.md", "documents/policy.md"),
        item("lib_2", "secret.md", "documents/secret.md", sensitivity="restricted"),
        item("lib_3", "unticked.md", "documents/unticked.md"),
        item("lib_4", "bobs.md", "documents/bobs.md", visibility="private", uploaded_by_id="acc-bob")])
    write_json_atomic(plane.path("intents", IID, "context.json"), {"library_ids": ["lib_1", "lib_2", "lib_4"]})
    return plane


def tools(plane, viewer=ME, facts=None):
    return DT.registry(OpenGate(), "m", plane, IID, viewer, [] if facts is None else facts)


def call(reg, name, **a):
    return reg.call("co", "m", name, a)


def test_index_is_idempotent_and_reindexes_on_change(world):
    first = DI.ensure(world, "documents/policy.md")
    assert first["lines"] > 50 and first["heads"][:2] == ["Investment policy", "Issuer limit"]
    con = DI._db(world)
    n = con.execute("select count(*) from passages").fetchone()[0]
    con.close()
    DI.ensure(world, "documents/policy.md")
    con = DI._db(world)
    assert con.execute("select count(*) from passages").fetchone()[0] == n
    con.close()
    (world.root / "documents" / "policy.md").write_text("# New\n\nCompletely different text about zebras.\n", encoding="utf-8")
    assert DI.search(world, ["documents/policy.md"], "zebras")[0]["from"] == 1
    assert DI.search(world, ["documents/policy.md"], "issuer") == []
    assert (world.root / "index" / "docs.sqlite").is_file()  # data/<company>/index/


def test_search_finds_the_passage_with_lines(world):
    reg, _ = tools(world)
    out = call(reg, "search_documents", query="issuer limit net worth", max=5)
    top = out["passages"][0]
    assert top.startswith("policy.md, lines ") and "10% of net worth" in top
    assert DT.NOTE == out["note"]


def test_unticked_restricted_and_private_files_never_come_back(world):
    reg, _ = tools(world)
    seen = json.dumps(call(reg, "search_documents", query="issuer limit exception salary private notes", max=8))
    assert "unticked" not in seen and "chair" not in seen and "Salary" not in seen and "Bob" not in seen
    for name in ("unticked.md", "secret.md", "bobs.md", "documents/policy.md", "nothing.md"):
        with pytest.raises(ToolRefused) as e:
            call(reg, "read_document", file=name, from_line=1, to_line=5)
        assert "not one of the files ticked" in str(e.value)
    reg, _ = tools(world, OTHER)  # Bob's own private file is readable by Bob, the restricted one still is not
    assert "Bob" in json.dumps(call(reg, "search_documents", query="issuer", max=8))
    assert "chair" not in json.dumps(call(reg, "search_documents", query="chair salary", max=8))


def test_read_is_capped_and_returns_numbered_lines(world):
    reg, t = tools(world)
    out = call(reg, "read_document", file="policy.md", from_line=1, to_line=500)
    rows = out["text"].splitlines()
    assert len(rows) <= 60 and rows[0].startswith("1: # Investment policy") and len(out["text"]) <= 3100
    assert t.chips("see policy.md") == [{"file": "policy.md", "path": "documents/policy.md", "from": 1, "to": len(rows)}]
    with pytest.raises(ToolRefused):
        call(reg, "read_document", file="policy.md", from_line=9, to_line=2)


def test_six_calls_a_reply(world):
    reg, _ = tools(world)
    for _ in range(6):
        call(reg, "search_documents", query="policy", max=2)
    with pytest.raises(ToolRefused) as e:
        call(reg, "search_documents", query="policy", max=2)
    assert "6 document looks" in str(e.value)


def test_figures_in_passages_become_facts(world):
    facts = []
    reg, _ = tools(world, facts=facts)
    call(reg, "search_documents", query="issuer", max=3)
    assert "10" in {f["value"] for f in facts}


class Scripted:
    def __init__(self, steps):
        self.steps, self.seen = list(steps), []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return self.steps.pop(0)


def test_stub_model_searches_reads_and_answers_with_a_figure_from_the_passage(world):
    facts = []
    reg, t = tools(world, facts=facts)
    model = Scripted([
        ModelReply(tool_calls=[ToolCall("search_documents", {"query": "issuer limit", "max": 5}, "c1")]),
        ModelReply(tool_calls=[ToolCall("read_document", {"file": "policy.md", "from_line": 5, "to_line": 8}, "c2")]),
        ModelReply(text="policy.md, lines 5-8: no issuer may exceed 10% of net worth, and 77% is invented.")])
    res = run_agent(model, reg, "co", "m", "North", "system", {"facts": facts}, "what is the issuer limit?")
    assert res.status == "done" and res.tools_called == ["search_documents", "read_document"]
    assert "10%" in res.text and "77%" not in res.text  # the passage's figure passes the guard, the invented one is rewritten
    assert t.chips(res.text)[0]["file"] == "policy.md"
    tool_msgs = [m["content"] for m in model.seen[-1] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and all(len(m) < 20_000 for m in tool_msgs)


def test_north_acknowledges_a_dropped_document_from_the_local_digest(world):
    from sh_platform.v1 import i2_north as N
    from sh_platform.v1 import i6_chat
    sow = N.empty_sow(IID, "Monthly pack")
    sow["sources"] = [{"id": "s1", "name": "policy", "kind": "document", "sample_path": "documents/policy.md",
                       "read": {"definitions": [{"term": "net worth"}, {"term": "TWR"}], "owners": [{"what": "benchmark", "who": "Priya"}]}}]
    write_json_atomic(world.path("intents", IID, "sow.json"), sow)
    line = i6_chat._ack(world, IID, [{"name": "policy.md", "path": "documents/policy.md", "kind": "document"},
                                     {"name": "x.csv", "path": "documents/policy.md", "kind": "sample"}])
    assert line == "I have read your policy."  # NI2-08 (cycle 1 re-measure): no read-out of headings; North's reply says what it took
    # digest must not block on slow files not yet indexed
    (world.root / "documents" / "scan.pdf").write_bytes(b"%PDF-1.4")
    assert DI.digest(world, "documents/scan.pdf") == ""


def test_a_scan_is_read_in_the_background_and_search_says_still_reading(world, monkeypatch):
    import threading
    gate = threading.Event()
    real = DI.read_lines
    monkeypatch.setattr(DI, "read_lines", lambda name, data: (gate.wait(10), real("scan.md", b"# Scan\n\nThe issuer limit is ten percent.\n"))[1])
    (world.root / "documents" / "scan.pdf").write_bytes(b"%PDF-1.4 not read: read_lines is stubbed")
    write_json_atomic(world.path("library", "index.json"), [item("lib_5", "scan.pdf", "documents/scan.pdf")])
    write_json_atomic(world.path("intents", IID, "context.json"), {"library_ids": ["lib_5"]})
    reg = tools(world)[0]
    out = call(reg, "search_documents", query="issuer limit", max=5)
    assert out["found"].startswith("none") and "still reading scan.pdf" in out["still_reading"]  # the reply did not wait for the read
    gate.set()
    for _ in range(100):  # the background read finishes
        if not DI.reading(world, "documents/scan.pdf"):
            break
        time.sleep(0.1)
    out = call(reg, "search_documents", query="issuer limit", max=5)
    assert out["passages"] and "still_reading" not in out
