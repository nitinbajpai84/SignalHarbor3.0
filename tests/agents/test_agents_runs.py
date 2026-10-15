import json

import pytest

from conftest import StubModel
from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.plane import PlaneStore

ROW = dict(agent="North", module_id="m1", started="s", finished="f", status="done",
           steps=1, tools_called=[], numbers_replaced=0)


def test_one_line_per_run_no_content(tmp_path):
    p = PlaneStore(tmp_path).create("acme")
    reg = RunRegistry(p)
    reg.record(**ROW)
    reg.record(**{**ROW, "tools_called": ["count"], "numbers_replaced": 1})
    rows = [json.loads(x) for x in (p.area("context") / "run_registry.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and rows[0]["run_id"] != rows[1]["run_id"]
    assert set(rows[0]) == {"run_id", "agent", "module_id", "started", "finished", "status",
                            "steps", "tools_called", "numbers_replaced"}


def test_content_fields_and_bad_status_rejected(tmp_path):
    reg = RunRegistry(PlaneStore(tmp_path).create("acme"))
    with pytest.raises(TypeError):
        reg.record(**ROW, answer="secret words")
    with pytest.raises(ValueError):
        reg.record(**{**ROW, "status": "weird"})


def test_end_to_end_stores_no_words(tmp_path, gate):
    p = PlaneStore(tmp_path).create("acme")
    run_agent(StubModel(ModelReply("Zebra answer 77", [])), ToolRegistry(gate), "acme", "m1", "North",
              "sys", {"facts": []}, "Giraffe question", recorder=RunRegistry(p))
    text = (p.area("context") / "run_registry.jsonl").read_text()
    assert '"done"' in text
    for word in ("Zebra", "Giraffe", "answer 77"):  # not a bare "77": run ids and times are random digits
        assert word not in text


def test_each_company_own_plane(tmp_path):
    store = PlaneStore(tmp_path)
    a, b = store.create("acme"), store.create("beta")
    RunRegistry(a).record(**ROW)
    assert (a.area("context") / "run_registry.jsonl").exists()
    assert not (b.area("context") / "run_registry.jsonl").exists()
