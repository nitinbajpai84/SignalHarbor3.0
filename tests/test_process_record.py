import json
import os
import pathlib
import subprocess
import threading

import pytest

from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.process_record import Landing, ProcessRecordError, ProcessRecords


@pytest.fixture
def store(tmp_path):
    return PlaneStore(tmp_path / "data")


@pytest.fixture
def plane(store):
    return store.create("acme")


@pytest.fixture
def recs(plane):
    return ProcessRecords(plane)


def _file(plane):
    return plane.area("context") / "process_records.json"


def test_start_links_both_ways(recs, plane):
    r = recs.start("intent_room", "charter", "Q3 review")
    assert r.session_state == r.outcome_state == "in_progress"
    assert len(r.session_id) >= 16 and r.session_id != r.outcome_id
    assert recs.get_by_session(r.session_id) == r == recs.get_by_outcome(r.outcome_id)
    assert "Q3 review" in _file(plane).read_text()


def test_stored_fields_only(recs, plane):
    recs.start("m1", "charter")
    row = json.loads(_file(plane).read_text())["records"][0]
    assert set(row) == {"session_id", "outcome_id", "module_id", "kind", "label",
                        "session_state", "outcome_state", "started_at", "updated_at"}


def test_ids_unique(recs, plane):
    other = ProcessRecords(plane)
    rs = [(recs if i % 2 else other).start("m1", "charter") for i in range(200)]
    assert len({r.session_id for r in rs} | {r.outcome_id for r in rs}) == 400


def test_landing(recs):
    r = recs.start("m1", "charter")
    assert recs.landing_for(r.session_id) == Landing("session", session_id=r.session_id, state="in_progress")
    recs.set_session_state(r.session_id, "paused")
    assert recs.landing_for(r.session_id).state == "paused"
    recs.complete_outcome(r.outcome_id)
    assert recs.landing_for(r.session_id) == Landing("outcome", outcome_id=r.outcome_id, ready=True)
    assert recs.landing_for("nope") is None
    assert recs.landing_for(5) is None


def test_state_machine(recs):
    r = recs.start("m1", "charter")
    s = r.session_id
    recs.set_session_state(s, "paused")
    recs.set_session_state(s, "in_progress")
    recs.set_session_state(s, "paused")
    recs.set_session_state(s, "completed")
    for bad in ("in_progress", "paused", "completed", "weird"):
        with pytest.raises(ProcessRecordError):
            recs.set_session_state(s, bad)
    # session completed on its own, outcome still in progress: outcome completes once
    recs.complete_outcome(r.outcome_id)
    with pytest.raises(ProcessRecordError):
        recs.complete_outcome(r.outcome_id)
    assert recs.get_by_session(s).outcome_state == "completed"


def test_complete_outcome_completes_session_and_is_readonly(recs):
    r = recs.start("m1", "charter")
    done = recs.complete_outcome(r.outcome_id)
    assert done.session_state == done.outcome_state == "completed"
    before = recs.get_by_outcome(r.outcome_id)
    for call in (lambda: recs.set_session_state(r.session_id, "paused"),
                 lambda: recs.set_session_state(r.session_id, "completed"),
                 lambda: recs.complete_outcome(r.outcome_id)):
        with pytest.raises(ProcessRecordError):
            call()
    assert recs.get_by_outcome(r.outcome_id) == before


def test_unknown_ids_on_writes(recs):
    with pytest.raises(ProcessRecordError, match="That session was not found."):
        recs.set_session_state("abc", "paused")
    with pytest.raises(ProcessRecordError, match="That outcome was not found."):
        recs.complete_outcome("abc")
    with pytest.raises(ProcessRecordError):
        recs.set_session_state(None, "paused")


def test_timestamps_and_clock(plane):
    t = iter([1000.0, 2000.0])
    recs = ProcessRecords(plane, clock=lambda: next(t))
    r = recs.start("m1", "charter")
    assert r.started_at == r.updated_at == "1970-01-01T00:16:40+00:00"
    r2 = recs.set_session_state(r.session_id, "paused")
    assert r2.started_at == r.started_at and r2.updated_at == "1970-01-01T00:33:20+00:00"


def test_list_filters_newest_first(plane):
    t = iter(range(1, 100))
    recs = ProcessRecords(plane, clock=lambda: float(next(t)))
    a = recs.start("m1", "charter")
    b = recs.start("m2", "process_map")
    c = recs.start("m1", "charter")
    recs.complete_outcome(a.outcome_id)
    assert [r.session_id for r in recs.list()] == [c.session_id, b.session_id, a.session_id]
    assert [r.session_id for r in recs.list(module_id="m1")] == [c.session_id, a.session_id]
    assert [r.session_id for r in recs.list(outcome_state="completed")] == [a.session_id]
    assert [r.session_id for r in recs.list(session_state="in_progress", module_id="m2")] == [b.session_id]


def test_never_orphaned_on_failed_replace(recs, plane, monkeypatch):
    first = recs.start("m1", "charter")
    good = _file(plane).read_bytes()

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(ProcessRecordError):
        recs.start("m1", "charter")
    monkeypatch.undo()
    assert _file(plane).read_bytes() == good
    json.loads(good)
    assert len(recs.list()) == 1
    assert not list(plane.area("context").glob("*.tmp"))
    assert recs.start("m1", "charter") and len(recs.list()) == 2
    assert recs.get_by_session(first.session_id)


@pytest.mark.parametrize("module_id,kind,label", [
    ("Bad", "charter", None), ("m 1", "charter", None), ("", "charter", None),
    ("a" * 41, "charter", None), ("m1", "Charter", None), ("m1", "", None),
    ("m1", "a-b", None), ("m1", "charter", "x" * 121), ("m1", "charter", "a\nb"),
    ("m1", "charter", "a\x00b"), (5, "charter", None), ("m1", None, None),
    ("m1", "charter", 7), ("m1\n", "charter", None),
])
def test_start_bad_input(recs, plane, module_id, kind, label):
    with pytest.raises(ProcessRecordError):
        recs.start(module_id, kind, label)
    assert not _file(plane).exists()


def test_label_limits_ok(recs):
    assert recs.start("m1", "charter", "x" * 120).label == "x" * 120
    assert recs.start("m1", "charter").label is None


@pytest.mark.parametrize("bad", [None, 5, b"x", "", "zz", "a" * 5000, "../x", {"a": 1}, ["a"]])
def test_get_never_raises(recs, bad):
    r = recs.start("m1", "charter")
    assert recs.get_by_session(bad) is None
    assert recs.get_by_outcome(bad) is None
    assert recs.get_by_session(r.outcome_id) is None  # ids are not interchangeable


def test_missing_file_is_empty(recs, plane):
    assert recs.list() == [] and recs.get_by_session("a" * 32) is None
    assert not _file(plane).exists()


@pytest.mark.parametrize("content", [b"not json{", b"", b"[]", b"null", b'{"records": 5}',
                                     b'{"records": [{"session_id": 1}]}', b"\xff\xfe"])
def test_corrupt_file_never_overwritten(recs, plane, content):
    _file(plane).write_bytes(content)
    for call in (lambda: recs.start("m1", "charter"), recs.list,
                 lambda: recs.get_by_session("a" * 32),
                 lambda: recs.set_session_state("a" * 32, "paused"),
                 lambda: recs.complete_outcome("a" * 32)):
        with pytest.raises(ProcessRecordError, match="could not be read"):
            call()
    assert _file(plane).read_bytes() == content


def test_two_companies_isolated(store):
    pa, pb = store.create("acme"), store.create("beta")
    a, b = ProcessRecords(pa), ProcessRecords(pb)
    ra = a.start("m1", "charter")
    assert b.get_by_session(ra.session_id) is None and b.get_by_outcome(ra.outcome_id) is None
    assert b.list() == [] and b.landing_for(ra.session_id) is None
    assert not _file(pb).exists()
    with pytest.raises(ProcessRecordError) as e:
        b.complete_outcome(ra.outcome_id)
    assert not _file(pb).exists()
    _file(pb).write_text("garbage")
    with pytest.raises(ProcessRecordError) as e2:
        b.list()
    root = str(store.root)
    for msg in (str(e.value), str(e2.value)):
        for form in (root, root.replace("\\", "\\\\"), root.replace("\\", "/"), "acme", "beta"):
            assert form not in msg
    assert json.loads(_file(pa).read_text())["records"]


def test_no_company_id_in_api():
    import inspect
    for name in ("start", "get_by_session", "get_by_outcome", "list", "landing_for",
                 "set_session_state", "complete_outcome"):
        assert "company" not in str(inspect.signature(getattr(ProcessRecords, name)))


def test_concurrent_starts(plane):
    stores = [ProcessRecords(plane) for _ in range(4)]
    out, errs = [], []

    def work(i):
        try:
            out.append(stores[i % 4].start("m1", "charter"))
        except Exception as e:  # collected, asserted empty
            errs.append(e)
    ts = [threading.Thread(target=work, args=(i,)) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs
    assert len(stores[0].list()) == 20
    assert len({r.session_id for r in out} | {r.outcome_id for r in out}) == 40
    json.loads(_file(plane).read_text())


class StrSub(str):
    pass


def _forms(store):
    root = str(store.root)
    return (root, root.replace("\\", "\\\\"), root.replace("\\", "/"), "acme")


@pytest.mark.parametrize("exc", [NotADirectoryError, PermissionError])
def test_cleanup_failure_keeps_plain_error(recs, store, monkeypatch, exc):
    def bad_replace(*a, **k):
        raise OSError("disk")

    def bad_unlink(self, *a, **k):
        raise exc(f"{self} acme")
    monkeypatch.setattr(os, "replace", bad_replace)
    monkeypatch.setattr(pathlib.Path, "unlink", bad_unlink)
    with pytest.raises(ProcessRecordError) as e:
        recs.start("m1", "charter")
    assert str(e.value) == "The process records could not be saved."
    for f in _forms(store):
        assert f not in str(e.value)


def test_context_replaced_by_file_gives_plain_errors(recs, plane, store):
    ctx = plane.area("context")
    ctx.rmdir()
    ctx.write_text("x")
    with pytest.raises(ProcessRecordError) as e:
        recs.start("m1", "charter")
    for f in _forms(store):
        assert f not in str(e.value)
    try:  # Windows reads a file-as-folder as "missing" (empty); Linux as unreadable
        assert recs.list() == []
    except ProcessRecordError as e2:
        for f in _forms(store):
            assert f not in str(e2)


def test_deep_json_is_unreadable_and_untouched(recs, plane):
    content = b'{"records": ' + b"[" * 100000 + b"]" * 100000 + b"}"
    _file(plane).write_bytes(content)
    for call in (recs.list, lambda: recs.start("m1", "charter")):
        with pytest.raises(ProcessRecordError, match="could not be read"):
            call()
    assert _file(plane).read_bytes() == content


@pytest.mark.parametrize("state", [[], {}, {"a": 1}, None, 5, "weird", StrSub("paused")])
def test_bad_state_types_give_plain_error(recs, state):
    r = recs.start("m1", "charter")
    with pytest.raises(ProcessRecordError):
        recs.set_session_state(r.session_id, state)
    assert recs.get_by_session(r.session_id).session_state == "in_progress"


def _good_row(recs):
    r = recs.start("m1", "charter", "lbl")
    return dict(session_id=r.session_id, outcome_id=r.outcome_id, module_id="m1", kind="charter",
                label="lbl", session_state="in_progress", outcome_state="in_progress",
                started_at=r.started_at, updated_at=r.updated_at)


def _mut_extra(r): r["notes"] = "x"
def _mut_missing(r): del r["label"]
def _mut_state(r): r["session_state"] = "archived"
def _mut_ostate(r): r["outcome_state"] = "paused"
def _mut_inconsistent(r): r.update(outcome_state="completed", session_state="paused")
def _mut_module(r): r["module_id"] = "Bad Module"
def _mut_label(r): r["label"] = "a‮b"
def _mut_id(r): r["session_id"] = "xyz"
def _mut_type(r): r["started_at"] = 5


@pytest.mark.parametrize("mut", [_mut_extra, _mut_missing, _mut_state, _mut_ostate,
                                 _mut_inconsistent, _mut_module, _mut_label, _mut_id, _mut_type])
def test_stored_row_revalidated_strictly(recs, plane, mut):
    row = _good_row(recs)
    mut(row)
    _file(plane).write_text(json.dumps({"records": [row]}))
    raw = _file(plane).read_bytes()
    with pytest.raises(ProcessRecordError, match="could not be read"):
        recs.list()
    assert _file(plane).read_bytes() == raw


@pytest.mark.parametrize("label", ["a‮b", "a​b", "a﻿b", "a\ud800b", "a b"])
def test_label_hidden_characters_refused(recs, label):
    with pytest.raises(ProcessRecordError):
        recs.start("m1", "charter", label)


def test_str_subclasses_cannot_bypass(recs):
    with pytest.raises(ProcessRecordError):
        recs.start(StrSub("m1"), "charter")
    with pytest.raises(ProcessRecordError):
        recs.start("m1", StrSub("charter"))
    with pytest.raises(ProcessRecordError):
        recs.start("m1", "charter", StrSub("x"))
    r = recs.start("m1", "charter")
    assert recs.get_by_session(StrSub(r.session_id)) is None
    assert recs.get_by_outcome(StrSub(r.outcome_id)) is None


def test_records_file_symlink_to_other_company_is_refused(store):
    pa, pb = store.create("acme"), store.create("beta")
    ProcessRecords(pb).start("m1", "charter")
    a = ProcessRecords(pa)
    try:
        os.symlink(_file(pb), _file(pa))
    except (OSError, NotImplementedError):
        pytest.skip("OS refused to create the file link")
    before = _file(pb).read_bytes()
    for call in (a.list, lambda: a.start("m1", "charter"), lambda: a.get_by_session("a" * 32)):
        with pytest.raises(CrossCompanyError):
            call()
    assert _file(pb).read_bytes() == before


def test_records_file_symlink_inside_same_plane_is_refused(plane):
    recs = ProcessRecords(plane)
    recs.start("m1", "charter")
    other = plane.area("graph") / "x.json"
    other.write_bytes(_file(plane).read_bytes())
    _file(plane).unlink()
    try:
        os.symlink(other, _file(plane))
    except (OSError, NotImplementedError):
        pytest.skip("OS refused to create the file link")
    with pytest.raises(CrossCompanyError):
        recs.list()


def test_wrong_shape_error_has_no_path(recs, plane, store):
    _file(plane).write_text('{"records": [1, 2]}')
    with pytest.raises(ProcessRecordError) as e:
        recs.list()
    assert str(e.value) == "The process records could not be read."
    for f in _forms(store):
        assert f not in str(e.value)


def test_duplicate_ids_in_file_are_unreadable(recs, plane):
    row = _good_row(recs)
    for second in ({**row}, {**row, "session_id": row["outcome_id"]}):
        _file(plane).write_text(json.dumps({"records": [row, second]}))
        raw = _file(plane).read_bytes()
        with pytest.raises(ProcessRecordError, match="could not be read"):
            recs.list()
        assert _file(plane).read_bytes() == raw


@pytest.mark.parametrize("bad", ["g" * 32, "A" * 32, "a" * 15, "a" * 65, " " + "a" * 31, "a" * 31 + "\n"])
def test_id_pattern_enforced(recs, plane, bad):
    row = _good_row(recs)
    assert recs.get_by_session(bad) is None and recs.get_by_outcome(bad) is None
    # a stored row with a bad id is unreadable, so the pattern is enforced on both sides
    _file(plane).write_text(json.dumps({"records": [{**row, "session_id": bad}]}))
    with pytest.raises(ProcessRecordError, match="could not be read"):
        recs.list()
    _file(plane).write_text(json.dumps({"records": [row]}))
    with pytest.raises(ProcessRecordError):
        recs.set_session_state(bad, "paused")
    with pytest.raises(ProcessRecordError):
        recs.complete_outcome(bad)


def test_context_swapped_for_link_after_build_is_refused(store):
    pa, pb = store.create("acme"), store.create("beta")
    a = ProcessRecords(pa)
    ProcessRecords(pb).start("m1", "charter")
    ctx = pa.area("context")
    ctx.rmdir()
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(ctx), str(pb.area("context"))],
                           check=True, capture_output=True)
        else:
            os.symlink(pb.area("context"), ctx, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("OS refused to create the link")
    for call in (a.list, lambda: a.start("m1", "charter"), lambda: a.get_by_session("a" * 32)):
        with pytest.raises(CrossCompanyError):
            call()
    assert len(ProcessRecords(pb).list()) == 1


def test_unreadable_file_is_never_treated_as_empty_and_overwritten(recs, plane, monkeypatch):
    """A read that fails (for example a permission error) must stop the write: no data loss."""
    first = recs.start("intent_room", "charter")
    before = _file(plane).read_bytes()
    real = pathlib.Path.read_bytes

    def refuse(self, *a, **k):
        if self.name == "process_records.json":
            raise PermissionError("denied")
        return real(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_bytes", refuse)
    with pytest.raises(ProcessRecordError):
        recs.start("intent_room", "charter")
    monkeypatch.undo()
    assert _file(plane).read_bytes() == before
    assert recs.get_by_session(first.session_id) == first


def test_a_replace_that_always_fails_gives_the_plain_error_and_saves_nothing(recs, plane, monkeypatch):
    recs.start("intent_room", "charter")
    before = _file(plane).read_bytes()

    def deny(*a, **k):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", deny)
    with pytest.raises(ProcessRecordError) as e:
        recs.start("intent_room", "charter")
    assert "could not be saved" in str(e.value)
    monkeypatch.undo()
    assert _file(plane).read_bytes() == before
    assert [p.name for p in _file(plane).parent.iterdir() if ".tmp" in p.name] == []
