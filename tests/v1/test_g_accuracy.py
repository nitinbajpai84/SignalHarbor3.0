import json

from sh_platform.v1 import v3_accuracy as A


def _round(d, name, answers):
    (d / name).mkdir()
    for i, (ans, ok) in enumerate(answers):
        (d / name / f"b{i}.json").write_text(json.dumps({"build": f"zz-{i}", "answer": ans, "check": {"expect": ["42"], "pass": ok}}), encoding="utf-8")


def test_rounds_count_right_and_slipped(tmp_path, monkeypatch):
    _round(tmp_path, "r2", [("It is 42.", True), ("It is 7.", False), ("I cannot tell from the files.", False)])
    _round(tmp_path, "r1", [("It is 7.", False)])
    monkeypatch.delenv("SH3_LIVE_DIR", raising=False)
    r = A.rounds(None, tmp_path)
    assert [x["round"] for x in r] == ["r1", "r2"]
    assert (r[1]["total"], r[1]["right"], r[1]["slipped"], r[1]["corrected"]) == (3, 1, 1, 0)
    assert r[0]["right_pct"] == 0


def test_no_folder_is_empty_and_corrections_are_counted(tmp_path):
    assert A.rounds(None, tmp_path / "none") == []
    _round(tmp_path, "r1", [("It is 7.", False)])

    class P:
        def path(self, *a):
            return tmp_path / "c.jsonl"
    (tmp_path / "c.jsonl").write_text('{"round": "r1"}\nnot json\n{"round": "r1"}\n', encoding="utf-8")
    assert A.rounds(P(), tmp_path)[0]["corrected"] == 2
