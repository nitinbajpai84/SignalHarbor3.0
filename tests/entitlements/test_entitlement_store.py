import json
import os

import pytest

from sh_platform.entitlements import EntitlementStore
from sh_platform.plane import InvalidCompanyId

IDS = ["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight", "m6_ops"]


@pytest.fixture
def store(tmp_path):
    return EntitlementStore(tmp_path / "data")


def control(tmp_path, name):
    return tmp_path / "data" / "_control" / name


@pytest.mark.parametrize("package,owned", [("discover", IDS[:3]), ("build", IDS[:5]), ("run", IDS),
                                           ("Discover", IDS[:3]), (None, [])])
def test_package_expands_to_its_modules(store, package, owned):
    store.create_company("co-a", "Company A", "industry_a", package=package)
    assert store.enabled_modules("co-a") == owned
    for m in IDS:
        assert store.is_enabled("co-a", m) is (m in owned)


def test_custom_set_and_catalogue_order(store):
    store.create_company("co-a", "A", "industry_a", modules=["m4_build", "m1_intent"])
    assert store.enabled_modules("co-a") == ["m1_intent", "m4_build"]
    assert store.company("co-a")["package"] is None


def test_company_record_and_plane(store, tmp_path):
    store.create_company("co-a", "Company A", "industry_a", package="build")
    rec = store.company("co-a")
    assert rec == {"company_id": "co-a", "name": "Company A", "industry": "industry_a", "package": "build"}
    for area in ("landing", "warehouse", "intents", "baseline", "context", "graph"):
        assert (tmp_path / "data" / "co-a" / area).is_dir()
    assert store.company("co-zz") is None


def test_industry_is_free_and_may_have_no_pack(store):
    for i, ind in enumerate(["none", "unknown-thing", "x", "Any Words Here"]):
        store.create_company(f"co-{i}", "N", ind, package="discover")
        assert store.company(f"co-{i}")["industry"] == ind


@pytest.mark.parametrize("kw", [
    {"company_id": "../x"}, {"company_id": "Co A"}, {"company_id": ""}, {"company_id": "_control"},
    {"company_id": "con"}, {"company_id": None},
    {"name": ""}, {"name": 5}, {"name": "x" * 500}, {"name": "a\x00b"},
    {"industry": ""}, {"industry": "a/b"}, {"industry": "a\\b"}, {"industry": ".."}, {"industry": None},
    {"package": "gold"}, {"modules": ["m9_nope"]}, {"modules": "m1_intent"}, {"modules": [1]},
    {"package": "build", "modules": ["m1_intent"]},
])
def test_create_company_refuses_bad_input_and_writes_nothing(store, tmp_path, kw):
    args = {"company_id": "co-a", "name": "A", "industry": "industry_a", **kw}
    with pytest.raises((ValueError, InvalidCompanyId)):
        store.create_company(**args)
    assert not (tmp_path / "data" / "co-a").exists()
    assert not control(tmp_path, "companies.json").exists()
    assert not control(tmp_path, "entitlements.json").exists()


def test_duplicate_company_is_refused_and_changes_nothing(store):
    store.create_company("co-a", "A", "industry_a", package="build")
    with pytest.raises(FileExistsError):
        store.create_company("co-a", "Other", "industry_b", package="run")
    assert store.company("co-a")["name"] == "A"
    assert store.enabled_modules("co-a") == IDS[:5]


def test_set_module_switches_at_once_and_keeps_data(store, tmp_path):
    store.create_company("co-a", "A", "industry_a", package="discover")
    (tmp_path / "data" / "co-a" / "intents" / "charter.txt").write_text("synthetic", encoding="utf-8")
    store.set_module("co-a", "m4_build", True)
    assert store.is_enabled("co-a", "m4_build")
    store.set_module("co-a", "m1_intent", False)
    assert not store.is_enabled("co-a", "m1_intent")
    assert store.enabled_modules("co-a") == ["m2_baseline", "m3_connect", "m4_build"]
    assert (tmp_path / "data" / "co-a" / "intents" / "charter.txt").read_text(encoding="utf-8") == "synthetic"


def test_set_module_only_touches_that_company_and_module(store):
    store.create_company("co-a", "A", "industry_a", package="discover")
    store.create_company("co-b", "B", "industry_b", package="discover")
    store.set_module("co-a", "m2_baseline", False)
    assert store.enabled_modules("co-b") == IDS[:3]
    assert store.enabled_modules("co-a") == ["m1_intent", "m3_connect"]


@pytest.mark.parametrize("company,module,enabled", [
    ("co-zz", "m1_intent", True), ("co-a", "m9_nope", True), ("co-a", "../x", True),
    ("../x", "m1_intent", True), (None, "m1_intent", True), ("co-a", None, True),
    ("co-a", "m1_intent", "yes"), ("co-a", "m1_intent", 1), ("co-a", "m1_intent", None)])
def test_set_module_refuses_unknown_or_malformed(store, company, module, enabled):
    store.create_company("co-a", "A", "industry_a", package="discover")
    before = store.enabled_modules("co-a")
    with pytest.raises((ValueError, LookupError, InvalidCompanyId)):
        store.set_module(company, module, enabled)
    assert store.enabled_modules("co-a") == before


@pytest.mark.parametrize("company,module", [
    ("co-zz", "m1_intent"), ("co-a", "m9_nope"), ("co-a", "ghost"), ("co-a", ""), ("co-a", None),
    (None, "m1_intent"), ("", "m1_intent"), (123, "m1_intent"), ("../co-a", "m1_intent"),
    ("co-a\n", "m1_intent"), ("CO-A", "m1_intent"), ("co-a", "M1_INTENT"), ("co-a", ["m1_intent"]),
    ({"a": 1}, "m1_intent"), ("co-a", b"m1_intent")])
def test_is_enabled_never_raises_and_is_false(store, company, module):
    store.create_company("co-a", "A", "industry_a", package="run")
    assert store.is_enabled(company, module) is False


def test_enabled_modules_for_unknown_company_is_empty(store):
    assert store.enabled_modules("co-zz") == []
    assert store.enabled_modules("../x") == []
    assert store.enabled_modules(None) == []


@pytest.mark.parametrize("content", [
    "{not json", "", "[]", "null", '"text"', '{"co-a": []}', '{"co-a": "m1_intent"}',
    '{"co-a": {"m1_intent": "true"}}', '{"co-a": {"m1_intent": 1}}', '{"co-a": {"m1_intent": "yes"}}',
    '{"co-a": {"m1_intent": null}}'])
def test_damaged_or_odd_entitlement_file_is_never_enabled(store, tmp_path, content):
    store.create_company("co-a", "A", "industry_a", package="run")
    control(tmp_path, "entitlements.json").write_text(content, encoding="utf-8")
    assert store.is_enabled("co-a", "m1_intent") is False  # only a real JSON true counts
    assert store.enabled_modules("co-a") == []


def test_missing_entitlement_file_means_nothing_owned(tmp_path):
    s = EntitlementStore(tmp_path / "data")
    assert s.is_enabled("co-a", "m1_intent") is False


def test_each_call_rereads_the_file(store, tmp_path):
    store.create_company("co-a", "A", "industry_a", package="discover")
    other = EntitlementStore(tmp_path / "data")  # a second object, as another worker would be
    other.set_module("co-a", "m1_intent", False)
    assert store.is_enabled("co-a", "m1_intent") is False  # no caching


def test_a_crashed_write_leaves_valid_json_and_no_litter(store, tmp_path, monkeypatch):
    store.create_company("co-a", "A", "industry_a", package="discover")
    ent = control(tmp_path, "entitlements.json")
    before = ent.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk went away")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.set_module("co-a", "m1_intent", False)
    monkeypatch.undo()
    assert ent.read_text(encoding="utf-8") == before
    json.loads(ent.read_text(encoding="utf-8"))
    assert sorted(p.name for p in ent.parent.iterdir()) == ["companies.json", "entitlements.json"]
    assert store.is_enabled("co-a", "m1_intent")


def test_a_crash_mid_create_owns_nothing(store, tmp_path, monkeypatch):
    real = os.replace
    calls = {"n": 0}

    def second_write_fails(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:  # companies.json written, entitlements.json not
            raise OSError("crash")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", second_write_fails)
    with pytest.raises(OSError):
        store.create_company("co-a", "A", "industry_a", package="run")
    monkeypatch.undo()
    assert store.enabled_modules("co-a") == []  # fail closed: a company with no row owns nothing
    for name in ("companies.json", "entitlements.json"):
        p = control(tmp_path, name)
        if p.exists():
            json.loads(p.read_text(encoding="utf-8"))


def test_writes_keep_other_companies_rows(store, tmp_path):
    for i in range(5):
        store.create_company(f"co-{i}", f"C{i}", "industry_a", package="discover")
    data = json.loads(control(tmp_path, "entitlements.json").read_text(encoding="utf-8"))
    assert sorted(data) == [f"co-{i}" for i in range(5)]
    assert all(set(v) == set(IDS) for v in data.values())  # one row per module, owned or not


def test_a_row_for_a_module_not_in_the_catalogue_is_never_enabled(store, tmp_path):
    store.create_company("co-a", "A", "industry_a", package="run")
    control(tmp_path, "entitlements.json").write_text(
        json.dumps({"co-a": {"ghost": True, "m1_intent": True}}), encoding="utf-8")
    assert store.is_enabled("co-a", "ghost") is False
    assert store.enabled_modules("co-a") == ["m1_intent"]


def test_company_missing_from_directory_owns_nothing(world):
    """A removed or damaged company directory fails closed: no modules, whatever entitlements.json says."""
    s = world.store
    assert s.is_enabled("co-a", "m1_intent")
    s._companies_path.write_text("[]", encoding="utf-8")
    assert not s.is_enabled("co-a", "m1_intent") and s.enabled_modules("co-a") == []
    s._companies_path.write_text("garbage", encoding="utf-8")
    assert not s.is_enabled("co-a", "m1_intent")
    s._companies_path.unlink()
    assert not s.is_enabled("co-a", "m1_intent")


def test_deeply_nested_files_never_raise(world):
    s = world.store
    s._ent_path.write_text("[" * 5000, encoding="utf-8")
    assert s.is_enabled("co-a", "m1_intent") is False
    s._companies_path.write_text("[" * 5000, encoding="utf-8")
    assert s.company("co-a") is None
