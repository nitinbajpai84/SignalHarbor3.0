"""The seed's optional local company file: a company that is never committed is seeded like a built-in one."""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from sh_platform.auth.accounts import AccountStore
from sh_platform.context_docs.store import DocStore
from sh_platform.entitlements import EntitlementStore
from sh_platform.plane import PlaneStore

_spec = importlib.util.spec_from_file_location("tool_seed_local", Path(__file__).resolve().parents[1] / "tools" / "seed.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = seed
_spec.loader.exec_module(seed)

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8"/></svg>'
ROLES = ["company_admin", "sponsor", "analyst", "participant", "approver", "owner"]


@pytest.fixture
def local(tmp_path):
    base = tmp_path / "local"
    (base / "docs").mkdir(parents=True)
    (base / "brand").mkdir()
    (base / "brand" / "logo.svg").write_bytes(SVG)
    (base / "docs" / "investment_policy.md").write_text("Illustrative policy: keep a reserve.", encoding="utf-8")
    (base / "docs" / "bonus_policy_extract.md").write_text("Illustrative bonus pool.", encoding="utf-8")
    people = [{"name": n, "role": r, "team": "T"} for n, r in zip(
        ["Ada Quill", "Ben Marsh", "Cleo Dunn", "Dev Okoro", "Elif Vane", "Finn Hale"], ROLES)]
    people.append({"name": "Gus Lark", "role": "hr_lead", "team": "HR"})
    path = base / "companies.yaml"
    path.write_text(yaml.safe_dump({"companies": [{
        "id": "harbour-office", "name": "Illustrative Harbour Office", "industry": "family_office",
        "brand": {"logo": "brand/logo.svg", "primary_colour": "#224466"}, "people": people, "documents": ["docs"]}]}),
        encoding="utf-8")
    return path


def test_no_local_file_is_exactly_todays_seed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    seed.seed(a)
    r = seed.seed(b, local_file=tmp_path / "missing.yaml")
    ids = lambda root: [c["company_id"] for c in EntitlementStore(root)._load(EntitlementStore(root)._companies_path, list)]
    assert ids(a) == ids(b) and "harbour-office" not in ids(b) and r["off_system_owners"] == seed.OFF_SYSTEM_OWNERS


def test_local_company_gets_accounts_modules_logo_and_documents(tmp_path, local):
    root = tmp_path / "data"
    r = seed.seed(root, local_file=local)
    es = EntitlementStore(root)
    assert es.company("harbour-office")["name"] == "Illustrative Harbour Office"
    assert es.enabled_modules("harbour-office") == ["m1_intent", "m2_baseline", "m3_connect"]
    accts = {a["email"]: a for a in AccountStore(root)._read() if a["company_id"] == "harbour-office"}
    assert sorted(accts) == sorted(f"{r_}.harbour-office@example.test" for r_ in ROLES)
    assert accts["owner.harbour-office@example.test"]["display_name"] == "Finn Hale"
    assert r["off_system_owners"]["harbour-office"] == ["Gus Lark"]
    plane = PlaneStore(root).plane_for("harbour-office")
    assert plane.path("brand", "logo.svg").read_bytes() == SVG
    assert es.company("harbour-office")["brand"] == {"logo": "logo.svg", "primary_colour": "#224466"}
    docs = {d["filename"]: d for d in DocStore(plane).documents("north")}
    assert set(docs) == {"investment_policy.md", "bonus_policy_extract.md"}
    assert docs["bonus_policy_extract.md"]["restricted"] and not docs["investment_policy.md"]["restricted"]


def test_lens_shelf_copies_are_shared_full_and_pay_stays_restricted(tmp_path, local):
    root = tmp_path / "data"
    seed.seed(root, local_file=local)
    docs = {d["filename"]: d for d in DocStore(PlaneStore(root).plane_for("harbour-office")).documents("lens")}
    assert {d["visibility"] for d in docs.values()} == {"shared_full"} and docs["bonus_policy_extract.md"]["restricted"]


def test_local_seed_is_idempotent_and_the_logo_reaches_its_company_only(tmp_path, local):
    root = tmp_path / "data"
    seed.seed(root, local_file=local)
    again = seed.seed(root, local_file=local)
    assert again["companies"] == 0 and again["accounts"] == 0 and again["documents"] == 0
    other = PlaneStore(root).plane_for("lakeside-family-office")
    assert not (other.root / "brand").exists()


def test_a_bad_local_file_is_skipped_not_fatal(tmp_path):
    bad = tmp_path / "companies.yaml"
    bad.write_text("companies: [{id: x}]\n", encoding="utf-8")
    assert seed.load_local_companies(bad) == []
    bad.write_text("companies: [unclosed\n", encoding="utf-8")
    assert seed.load_local_companies(bad) == []


def _edit(path, change):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data["companies"][0])
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.mark.parametrize("field", ["logo", "documents"])
def test_paths_outside_the_local_folder_are_refused(tmp_path, local, field):
    (tmp_path / "secret.md").write_text("outside", encoding="utf-8")
    (tmp_path / "outside_dir").mkdir()
    for bad in ("../secret.md", "../outside_dir", str(tmp_path / "secret.md")):
        _edit(local, lambda c: c.update(brand={"logo": bad}) if field == "logo" else c.update(documents=[bad]))
        with pytest.raises(ValueError, match="outside"):
            seed.load_local_companies(local)


def test_documents_with_unreadable_extensions_are_left_out(local):
    (local.parent / "docs" / "picture.png").write_bytes(b"\x89PNG")
    (local.parent / "docs" / "tool.exe").write_bytes(b"MZ")
    names = {p.name for p in seed.load_local_companies(local)[0]["documents"]}
    assert names == {"investment_policy.md", "bonus_policy_extract.md"}


def test_a_local_company_cannot_take_a_built_in_id(tmp_path, local):
    _edit(local, lambda c: c.update(id="lakeside-family-office"))
    with pytest.raises(ValueError, match="built-in"):
        seed.load_local_companies(local)
    with pytest.raises(ValueError, match="built-in"):
        seed.seed(tmp_path / "data", local_file=local)


def test_a_registered_company_with_no_plane_folder_gets_one_and_the_seed_carries_on(tmp_path, local):
    root = tmp_path / "data"
    seed.seed(root, local_file=local)
    shutil.rmtree(PlaneStore(root).plane_for("harbour-office").root)
    seed.seed(root, local_file=local)  # used to raise LookupError("unknown company")
    plane = PlaneStore(root).plane_for("harbour-office")
    assert [d["filename"] for d in DocStore(plane).documents("north")]
