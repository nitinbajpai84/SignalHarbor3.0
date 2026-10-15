"""Company plane tests. Tmp folders only; no industry appears here."""
import os
import subprocess
from pathlib import Path

import pytest

from sh_platform.plane import (
    AREAS, CompanyPlane, CrossCompanyError, InvalidCompanyId, PlaneStore,
    require_same_company, valid_company_id,
)


@pytest.fixture
def store(tmp_path):
    return PlaneStore(tmp_path / "data")


def test_create_then_plane_for(store):
    p = store.create("acme")
    assert store.exists("acme") and store.plane_for("acme").root == p.root
    for a in AREAS:
        assert p.area(a).is_dir()
    assert store.list_company_ids() == ["acme"]


def test_unknown_company_creates_nothing(store, tmp_path):
    with pytest.raises(LookupError, match="unknown company"):
        store.plane_for("ghost")
    assert not (tmp_path / "data" / "ghost").exists()


def test_create_twice_raises(store):
    store.create("acme")
    with pytest.raises(FileExistsError):
        store.create("acme")


@pytest.mark.parametrize("ok", ["a", "acme", "a-b_c", "9lives", "a" * 64])
def test_valid_ids(ok):
    assert valid_company_id(ok) == ok


@pytest.mark.parametrize("bad", [
    "../x", "a/b", "a\\b", "C:", ".", "..", "_control", "_x", "", "a" * 65,
    "Acme", "con", "CON", "nul", "com1", "lpt9", "prn", "aux", "a b", "a.b", "-a", "a\x00b", "\u0430cme", "\uff41cme", None, 5,
])
def test_invalid_ids(bad):
    with pytest.raises(InvalidCompanyId):
        valid_company_id(bad)


def test_path_refuses_escapes(store):
    store.create("acme")
    store.create("beta")
    p = store.plane_for("acme")
    assert p.path("landing", "f.csv") == p.root / "landing" / "f.csv"
    for parts in [("..",), ("..", "beta"), ("landing", "..", "..", "beta"),
                  (str(store.plane_for("beta").root),), ("/etc/passwd",),
                  ("C:\\Windows",)]:
        with pytest.raises(CrossCompanyError):
            p.path(*parts)


def test_path_refuses_symlink_escape(store):
    store.create("acme")
    store.create("beta")
    p = store.plane_for("acme")
    link = p.root / "landing" / "link"
    try:
        os.symlink(store.plane_for("beta").root, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("OS refused to create a symlink (Windows without privilege)")
    with pytest.raises(CrossCompanyError):
        p.path("landing", "link", "x")


def test_two_companies_isolated(store):
    a, b = store.create("a1"), store.create("b1")
    (a.area("warehouse") / "secret.db").write_text("x")
    # same relative name resolves inside B and does not see A's file
    assert not b.path("warehouse", "secret.db").exists()
    # reaching A by relative or absolute path is refused
    with pytest.raises(CrossCompanyError):
        b.path("..", "a1", "warehouse", "secret.db")
    with pytest.raises(CrossCompanyError):
        b.path(str(a.area("warehouse") / "secret.db"))
    with pytest.raises(CrossCompanyError):
        require_same_company("a1", "b1")
    require_same_company("a1", "a1")
    with pytest.raises(CrossCompanyError):
        require_same_company("a1", "../a1")


def test_area_names(store):
    p = store.create("acme")
    with pytest.raises(ValueError):
        p.area("secrets")


def test_ensure_idempotent_never_deletes(store):
    p = store.create("acme")
    f = p.area("graph") / "keep"
    f.write_text("x")
    p.ensure()
    assert f.read_text() == "x"


def test_list_skips_control_and_files(store):
    store.create("acme")
    (store.root / "_control").mkdir()
    (store.root / "stray.txt").write_text("x")
    assert store.list_company_ids() == ["acme"]


def test_errors_leak_no_path_or_other_id(store):
    store.create("acme")
    store.create("beta")
    p = store.plane_for("acme")
    errs = []
    for fn in (lambda: p.path("..", "beta"), lambda: store.plane_for("ghost"),
               lambda: store.create("acme"), lambda: require_same_company("acme", "beta"),
               lambda: p.area("zzz"), lambda: valid_company_id("../beta")):
        with pytest.raises(Exception) as e:
            fn()
        errs.append(str(e.value))
    for m in errs:
        assert str(store.root) not in m and "beta" not in m


def _junction(link, target):
    """A Windows junction; elsewhere the same thing as a directory symlink."""
    if os.name != "nt":
        os.symlink(target, link, target_is_directory=True)
        return
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       capture_output=True)
    if r.returncode != 0:
        pytest.skip("OS cannot create a junction")


def test_junction_to_other_company_fails_closed(store):
    store.create("beta")
    _junction(store.root / "evil", store.root / "beta")
    for fn in (store.plane_for, store.exists, store.create):
        with pytest.raises(CrossCompanyError):
            fn("evil")
    assert store.list_company_ids() == ["beta"]


def test_junction_outside_root_fails_closed(store, tmp_path):
    store.create("beta")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.txt").write_text("x")
    _junction(store.root / "evil", outside)
    for fn in (store.plane_for, store.exists, store.create):
        with pytest.raises(CrossCompanyError):
            fn("evil")
    assert store.list_company_ids() == ["beta"]


def test_path_refuses_reserved_device_names(store):
    p = store.create("acme")
    for part in ("con", "NUL.txt", "landing/com1", "lpt3.log", "aux."):
        with pytest.raises(CrossCompanyError):
            p.path(part)
    assert p.path("console.txt").name == "console.txt"


def test_dangling_junction_create_makes_nothing(store, tmp_path):
    gone = tmp_path / "gone"
    gone.mkdir()
    store.root.mkdir(parents=True, exist_ok=True)
    _junction(store.root / "evil", gone)
    gone.rmdir()
    with pytest.raises(CrossCompanyError):
        store.create("evil")
    assert not gone.exists()


@pytest.mark.parametrize("bad", ["../beta", "_control", "Beta", "a\\b", "C:", "con", "com0", "LPT0", "nul"])
@pytest.mark.parametrize("op", ["plane_for", "create", "exists"])
def test_store_entry_points_validate_ids(store, bad, op):
    before = sorted(p.name for p in store.root.parent.iterdir()) if store.root.exists() else None
    with pytest.raises(InvalidCompanyId):
        getattr(store, op)(bad)
    assert not store.root.exists() or sorted(p.name for p in store.root.iterdir()) == []
    assert before is None or before == ["data"]


def _msgs(fn):
    with pytest.raises(Exception) as e:
        fn()
    return str(e.value)


def _no_root(store, msg):
    r = str(store.root)
    for form in (r, r.replace("\\", "\\\\"), r.replace("\\", "/")):
        assert form not in msg


def test_ensure_failure_is_fixed_message(store):
    p = store.create("acme")
    (p.root / "landing").rmdir()
    (p.root / "landing").write_text("file in the way")
    m = _msgs(p.ensure)
    assert m == "plane could not be prepared"
    _no_root(store, m)


def test_data_root_is_a_file(tmp_path):
    f = tmp_path / "afile"
    f.write_text("x")
    m = _msgs(lambda: PlaneStore(f).create("acme"))
    assert m == "plane could not be prepared"
    _no_root(PlaneStore(f), m)


def test_create_race_has_fixed_message(store, monkeypatch):
    store.create("acme")
    # simulate another process creating the folder just before our mkdir
    def raced(self, *a, **k):
        raise FileExistsError(str(self))
    monkeypatch.setattr(Path, "mkdir", raced)
    m = _msgs(lambda: store.create("acme"))
    assert m == "company already exists"
    _no_root(store, m)


def test_error_texts_hide_root_forms(store):
    store.create("acme")
    p = store.plane_for("acme")
    for fn in (lambda: p.path("..", "x"), lambda: store.plane_for("ghost"),
               lambda: store.create("acme")):
        _no_root(store, _msgs(fn))
    _no_root(store, repr(p))
    _no_root(store, str(p))


def _loop(link):
    """Junction whose target is itself, else two junctions pointing at each other."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":  # a symlink to itself: the same loop
        os.symlink(link, link, target_is_directory=True)
        return
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(link)], capture_output=True)
    if r.returncode != 0 or not link.exists() and not link.is_symlink() and not os.path.lexists(link):
        pytest.skip("OS cannot create a looping junction")


def test_loop_in_data_root_fails_closed(store):
    store.create("beta")
    _loop(store.root / "jl")
    for fn in (store.plane_for, store.exists, store.create):
        with pytest.raises(CrossCompanyError) as e:
            fn("jl")
        _no_root(store, str(e.value))
    assert store.list_company_ids() == ["beta"]


def test_loop_inside_plane_fails_closed(store):
    p = store.create("acme")
    _loop(p.root / "landing" / "jlp")
    with pytest.raises(CrossCompanyError) as e:
        p.path("landing", "jlp", "x")
    _no_root(store, str(e.value))


def test_listing_edge_cases(store, tmp_path):
    store.create("acme")
    (store.root / "zeta").write_text("a file with a valid id")
    assert store.list_company_ids() == ["acme"]
    f = tmp_path / "afile"
    f.write_text("x")
    assert PlaneStore(f).list_company_ids() == []
    assert PlaneStore(tmp_path / "missing").list_company_ids() == []


def test_huge_part_refused(store):
    p = store.create("acme")
    with pytest.raises(CrossCompanyError):
        p.path("x" * 40000)


def test_more_device_names_refused(store):
    p = store.create("acme")
    for part in ("CONIN$", "conout$", "CLOCK$", "com¹", "COM².txt", "lpt³"):
        with pytest.raises(CrossCompanyError):
            p.path(part)


def test_ensure_passes_cross_company_error_through(store, monkeypatch):
    p = store.create("acme")

    def boom(self, name):
        raise CrossCompanyError("x")
    monkeypatch.setattr(CompanyPlane, "area", boom)
    with pytest.raises(CrossCompanyError):
        p.ensure()


def test_path_refuses_non_strings_and_nul(store):
    p = store.create("acme")
    for bad in (None, "a\x00b", 5):
        with pytest.raises(CrossCompanyError):
            p.path(bad)


def test_list_filters_invalid_names(store):
    store.create("acme")
    (store.root / "Bad Name").mkdir()
    assert store.list_company_ids() == ["acme"]


def test_plane_validates_on_construction(store):
    with pytest.raises(InvalidCompanyId):
        CompanyPlane("../x", store.root)
    with pytest.raises(ValueError):
        CompanyPlane("acme", Path("relative"))


def test_symlink_with_invalid_target_name_fails_closed(store):
    store.root.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink("bad<name", store.root / "bl", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this OS refuses to create a symlink")
    for call in (store.plane_for, store.exists, store.create):
        with pytest.raises(CrossCompanyError):
            call("bl")
