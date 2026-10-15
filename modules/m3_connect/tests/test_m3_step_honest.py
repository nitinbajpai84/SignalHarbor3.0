"""A trial or findings file on an assessment with no source data must not show the step as done (Nitin's screen, 4 Oct)."""
import json

from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import trial as T


def test_trial_and_findings_are_not_done_before_any_source_file(tmp_path):
    (tmp_path / "trial.json").write_text(json.dumps({"K04": {"result": "cannot"}}), encoding="utf-8")
    (tmp_path / "findings.json").write_text(json.dumps({"measures": [{"measure_id": "K04"}], "risks": []}), encoding="utf-8")
    assert T.state(tmp_path)["state"] == "not_started"
    assert F.state(tmp_path)["state"] == "not_started"
