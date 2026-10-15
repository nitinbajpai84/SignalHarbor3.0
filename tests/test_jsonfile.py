"""The shared JSON file helper: strict read, atomic write, one lock per file."""
import json
import os

import pytest

from sh_platform.auth.accounts import AccountStore, check_password
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic


def test_missing_file_reads_as_none(tmp_path):
    assert read_json_strict(tmp_path / "none.json") is None


@pytest.mark.parametrize("raw", [b"{half", b"\xff\xfe", b"[" * 100000], ids=["half", "bad-utf8", "too-deep"])
def test_corrupt_file_is_refused_and_left_untouched(tmp_path, raw):
    p = tmp_path / "x.json"
    p.write_bytes(raw)
    with pytest.raises(ValueError):
        read_json_strict(p)
    assert p.read_bytes() == raw


def test_wrong_shape_is_refused(tmp_path):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"a": 1})
    assert read_json_strict(p, dict) == {"a": 1}
    with pytest.raises(ValueError):
        read_json_strict(p, list)


def test_write_creates_folders_and_leaves_no_temp_file(tmp_path):
    p = tmp_path / "deep" / "x.json"
    write_json_atomic(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    assert [f.name for f in p.parent.iterdir()] == ["x.json"]


def test_failed_replace_leaves_the_file_intact_and_no_temp_file(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"a": 1})
    before = p.read_bytes()

    def boom(src, dst):
        raise OSError("disk full (test)")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_json_atomic(p, {"a": 2})
    monkeypatch.undo()
    assert p.read_bytes() == before
    assert [f.name for f in tmp_path.iterdir()] == ["x.json"]


def test_a_briefly_locked_target_is_retried(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    real, calls = os.replace, {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("held by a scanner (test)")
        return real(src, dst)
    monkeypatch.setattr(os, "replace", flaky)
    write_json_atomic(p, [1])
    assert calls["n"] == 3 and json.loads(p.read_text(encoding="utf-8")) == [1]


def test_lock_is_shared_across_spellings_of_one_path(tmp_path):
    a = lock_for(tmp_path / "x.json")
    assert lock_for(tmp_path / "sub" / ".." / "x.json") is a
    assert lock_for(tmp_path / "y.json") is not a


def test_lock_is_shared_across_store_objects(tmp_path):
    assert AccountStore(tmp_path)._lock is AccountStore(tmp_path)._lock


def test_set_password_replaces_only_that_accounts_hash(tmp_path):
    s = AccountStore(tmp_path)
    s.create("a@test.invalid", "old-a", "A", "co-a", ["participant"])
    s.create("b@test.invalid", "old-b", "B", "co-a", ["participant"])
    s.set_password("A@test.invalid", "new-a")
    assert s.verify("a@test.invalid", "new-a") and not s.verify("a@test.invalid", "old-a")
    assert check_password("old-b", s.get_by_email("b@test.invalid")["password_hash"])
    with pytest.raises(ValueError):
        s.set_password("nobody@test.invalid", "x")
