"""Smoke: no hardcoded industry in the real tree (the P1-08 walker), and the smoke run leaves the repo untouched."""
import importlib.util
import sys

import pytest

from smoke_helpers import ROOT, snapshot


def _walker():
    spec = importlib.util.spec_from_file_location("smoke_p108_walker", ROOT / "tests" / "test_no_hardcoded_industry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_p108_walker_still_catches_a_planted_word(tmp_path):
    (tmp_path / "a.py").write_text("# Policyholder list\n")
    (tmp_path / "b.ts").write_text("const label = 'asset-management';\n")
    assert len(_walker().find_hardcoded(tmp_path)) == 2


def test_kernel_and_modules_have_no_industry_word():
    roots = [ROOT / d for d in ("sh_platform", "modules") if (ROOT / d).is_dir()]
    assert roots and _walker().find_hardcoded(*roots) == []


def test_ui_copy_has_no_industry_word():
    ui = ROOT / "ui" / "src"
    if not ui.is_dir():
        pytest.skip("ui/src is not in this checkout; it runs in the main repo")
    assert _walker().find_hardcoded(ui) == []


def test_repo_guard_notices_a_new_file(tmp_path):
    for d in ("sh_platform", "tools", "packs", "ui/src"):
        (tmp_path / d).mkdir(parents=True)
    before = snapshot(tmp_path)
    assert snapshot(tmp_path) == before
    (tmp_path / "tools" / "stray.txt").write_text("x")
    assert snapshot(tmp_path) != before
