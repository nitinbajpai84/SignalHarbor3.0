"""P1-09: doctor checks and the synthetic seed. Everything runs in tmp_path."""
import importlib.util
import logging
import socket
import sys
from pathlib import Path

import pytest

from sh_platform.auth.accounts import AccountStore
from sh_platform.entitlements import EntitlementStore
from sh_platform.packs import PackLoader
from sh_platform.plane import CrossCompanyError, PlaneStore, require_same_company

TOOLS = Path(__file__).resolve().parents[1] / "tools"
FAKE_SECRET = "FAKE-secret-value-for-tests-0123456789abcdef-xyz"  # fake, clearly marked


def _load(name):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


doctor, seed = _load("doctor"), _load("seed")


# ---------------------------------------------------------------- doctor
@pytest.fixture
def good(tmp_path):
    ui = tmp_path / "ui"
    (ui / "node_modules").mkdir(parents=True)
    env = {"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": FAKE_SECRET,
           "GOOGLE_API_KEY": "FAKE-model-key"}
    return dict(env=env, port_free=lambda p: True, ui_dir=ui)


def result(rows, fragment):
    return next(r for r in rows if fragment in r[0])


def test_doctor_new_checks_pass(good):
    rows = doctor.checks(**good)
    for frag in ("Port 8400", "Port 8401", "Data folder", "Session secret", "SH_MODE is", "Industry packs", "node_modules"):
        assert result(rows, frag)[1], frag


def test_doctor_names_the_provider_model_and_key_variable_never_a_value(good):
    name, ok, fix = result(doctor.checks(**good), "Model provider")
    assert ok and "gemini" in name and "GOOGLE_API_KEY" in name and "gemini-2.5-flash" in name
    assert "FAKE-model-key" not in name + fix
    good["env"].update({"OPENROUTER_API_KEY": "FAKE-other-key", "SH_MODEL_PROVIDER": "openrouter", "SH_MODEL_NAME": "a/b"})
    name, ok, fix = result(doctor.checks(**good), "Model provider")
    assert ok and "openrouter" in name and "OPENROUTER_API_KEY" in name and "a/b" in name and "FAKE-other-key" not in name + fix
    good["env"].pop("GOOGLE_API_KEY"), good["env"].pop("OPENROUTER_API_KEY")
    name, ok, fix = result(doctor.checks(**good), "Model provider")
    assert not ok and "GOOGLE_API_KEY" in fix
    good["env"].update({"GOOGLE_API_KEY": "FAKE-model-key", "SH_MODEL_NAME": "../../x", "SH_MODEL_PROVIDER": ""})
    assert not result(doctor.checks(**good), "Model provider")[1]


def test_doctor_names_the_speech_provider_and_the_free_tier_note_never_a_value(good):
    name, ok, fix = result(doctor.checks(**good), "Speech provider")
    assert ok and "gemini" in name and "Speech is on the Gemini free tier: development and demos only" in name
    assert "GOOGLE_API_KEY" in name and "FAKE-model-key" not in name + fix
    good["env"]["SH_SPEECH_PROVIDER"] = "stub"
    name, ok, fix = result(doctor.checks(**good), "Speech provider")
    assert ok and "none" in name and "typing only" in name and "free tier" not in name
    good["env"].pop("SH_SPEECH_PROVIDER"), good["env"].pop("GOOGLE_API_KEY")
    assert result(doctor.checks(**good), "Speech provider")[1] and "typing only" in result(doctor.checks(**good), "Speech provider")[0]


def test_doctor_says_the_free_tier_is_off_in_production_and_fails_on_an_unknown_provider(good):
    good["env"]["SH_MODE"] = "prod"
    name, ok, fix = result(doctor.checks(**good), "Speech provider")
    assert ok and "none" in name and "development and demos only" in name
    good["env"].update(SH_MODE="dev", SPEECH_PROVIDER="nonsense")
    name, ok, fix = result(doctor.checks(**good), "Speech provider")
    assert not ok and "must be one of" in fix


def test_running_md_explains_speech_and_the_model_switch_by_names_only():
    text = (Path(__file__).resolve().parents[1] / "docs" / "RUNNING.md").read_text(encoding="utf-8")
    for needed in ("Speech is on the Gemini free tier: development and demos only", "SH_SPEECH_PROVIDER", "SPEECH_PROVIDER",
                   "SH_MODE=dev", "synthetic", "SH_MODEL_PROVIDER=off", "GOOGLE_API_KEY=", "typing", "not stored"):
        assert needed in text, needed
    assert "AIza" not in text and "sk-" not in text  # no key value of any kind


def test_port_in_use_fails_with_fix(good):
    good["port_free"] = lambda p: p != 8400  # the app moved to 8400/8401 (doctor.py)
    rows = doctor.checks(**good)
    name, ok, fix = result(rows, "Port 8400")
    assert not ok and "Stop the program using port 8400" in fix
    assert result(rows, "Port 8401")[1]


def test_real_port_prober_sees_bound_socket():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    try:
        assert doctor.port_is_free(s.getsockname()[1]) is False
    finally:
        s.close()


def test_data_root_unwritable(good, tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    good["env"]["SH_DATA_ROOT"] = str(blocker / "data")
    assert not result(doctor.checks(**good), "Data folder")[1]


def test_data_root_probe_leaves_nothing(good):
    root = Path(good["env"]["SH_DATA_ROOT"])
    assert result(doctor.checks(**good), "Data folder")[1]
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("mode,secret,ok", [("dev", "", True), ("prod", "short", False),
                                            ("prod", "x" * 32, True), ("prod", "", False)])
def test_session_secret_length(good, mode, secret, ok):
    good["env"].update(SH_MODE=mode, SH_SESSION_SECRET=secret)
    assert result(doctor.checks(**good), "Session secret")[1] is ok


@pytest.mark.parametrize("mode,ok", [("dev", True), ("prod", True), ("staging", False), ("", False)])
def test_mode_values(good, mode, ok):
    good["env"]["SH_MODE"] = mode
    assert result(doctor.checks(**good), "SH_MODE is")[1] is ok


def test_missing_node_modules(good, tmp_path):
    good["ui_dir"] = tmp_path / "nowhere"
    name, ok, fix = result(doctor.checks(**good), "node_modules")
    assert not ok and "npm install" in fix


def test_missing_packs(good, tmp_path):
    good["packs_root"] = tmp_path / "nopacks"
    assert not result(doctor.checks(**good), "Industry packs")[1]


def test_no_secret_in_output_and_ready(good, caplog, capsys):
    caplog.set_level(logging.INFO)
    rows = doctor.checks(**good)
    doctor.main(lambda: rows)
    seen = caplog.text + "".join(capsys.readouterr())
    assert FAKE_SECRET not in seen and "FAKE-model-key" not in seen
    assert not any(FAKE_SECRET in fix for _, _, fix in rows)
    failed = [r for r in rows if not r[1]]
    # only machine-level checks (node, graft, .env) may fail in a bare test environment
    assert all(r[0] in ("Node.js on the path", "graft on the path", ".env present") for r in failed)
    if not failed:
        assert "Ready." in caplog.text


# ---------------------------------------------------------------- seed
@pytest.fixture
def root(tmp_path):
    return tmp_path / "data"


def run(root, *flags):
    # a missing local file: these tests are about the built-in companies, whatever local/companies.yaml holds on this machine
    return seed.main(["--data-root", str(root), "--local-file", str(root.parent / "no-local-companies.yaml"), *flags])


def accounts(root):
    return AccountStore(root)._read()


def creds_lines(root):
    f = root / "_control" / "seed_credentials.txt"
    return [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def test_seed_creates_four_companies_and_super_admin(root):
    assert run(root) == 0
    es = EntitlementStore(root)
    ids = PlaneStore(root).list_company_ids()
    assert len(ids) == 4
    assert {es.company(i)["industry"] for i in ids} == {"insurance", "asset_management", "family_office", "unlisted"}
    accts = accounts(root)
    assert sum("super_admin" in a["roles"] for a in accts) == 1
    assert len(accts) == 6 + 6 + 6 + 1 + 1
    for cid in ids:
        assert {"company_admin", "sponsor"} <= {r for a in accts if a["company_id"] == cid for r in a["roles"]}


def test_modules_per_package_and_empty_company(root):
    run(root)
    es, loader = EntitlementStore(root), PackLoader(Path(__file__).resolve().parents[1] / "packs")
    by_ind = {es.company(i)["industry"]: i for i in PlaneStore(root).list_company_ids()}
    assert es.enabled_modules(by_ind["insurance"]) == es.catalogue.packages["discover"]
    assert es.enabled_modules(by_ind["asset_management"]) == es.catalogue.packages["build"]
    assert es.enabled_modules(by_ind["family_office"]) == es.catalogue.packages["discover"]
    assert not loader.load("family_office").empty and loader.load("family_office").status == "proposed"
    assert es.enabled_modules(by_ind["unlisted"]) == []
    assert es.company(by_ind["unlisted"])["package"] is None
    assert loader.load("unlisted").empty and loader.load("unlisted").sections() == []
    solo = [a for a in accounts(root) if a["company_id"] == by_ind["unlisted"]]
    assert len(solo) == 1 and set(solo[0]["roles"]) == {"company_admin", "sponsor"}


def test_six_roles_in_each_full_company(root):
    run(root)
    es = EntitlementStore(root)
    for cid in PlaneStore(root).list_company_ids():
        if es.company(cid)["industry"] == "unlisted":
            continue
        roles = sorted(r for a in accounts(root) if a["company_id"] == cid for r in a["roles"])
        assert roles == sorted(["company_admin", "sponsor", "analyst", "participant", "approver", "owner"])


def test_companies_cannot_read_each_other(root):
    run(root)
    ids = PlaneStore(root).list_company_ids()
    with pytest.raises(CrossCompanyError):
        require_same_company(ids[0], ids[1])


def test_second_run_changes_nothing(root, capsys):
    run(root)
    before, creds = accounts(root), (root / "_control" / "seed_credentials.txt").read_text()
    capsys.readouterr()
    run(root)
    assert accounts(root) == before
    assert (root / "_control" / "seed_credentials.txt").read_text() == creds
    assert "unchanged" in capsys.readouterr().out.lower()


def test_credentials_valid_and_never_printed(root, capsys):
    run(root)
    printed = capsys.readouterr()
    store, lines = AccountStore(root), creds_lines(root)
    assert len(lines) == len(accounts(root))
    for ln in lines:
        email, password, *_ = ln.split()
        assert store.verify(email, password), email
        assert password not in printed.out + printed.err
    assert "seed_credentials.txt" in printed.out and str(len(lines)) in printed.out


def test_reset_credentials(root, capsys):
    run(root)
    old_hash = {a["email"]: a["password_hash"] for a in accounts(root)}
    old_ids = {a["email"]: a["account_id"] for a in accounts(root)}
    old_lines = creds_lines(root)
    capsys.readouterr()
    run(root, "--reset-credentials")
    out = capsys.readouterr()
    assert all(a["password_hash"] != old_hash[a["email"]] and a["account_id"] == old_ids[a["email"]]
               for a in accounts(root))
    store = AccountStore(root)
    for ln in creds_lines(root):
        email, password, *_ = ln.split()
        assert store.verify(email, password) and password not in out.out
    assert creds_lines(root) != old_lines
    assert len(accounts(root)) == 20


def test_names_illustrative_and_example_emails(root):
    run(root)
    es = EntitlementStore(root)
    for cid in PlaneStore(root).list_company_ids():
        assert "Illustrative" in es.company(cid)["name"]
    for a in accounts(root):  # the company name carries the marker; a person's display name is a plain name
        assert a["email"].endswith("@example.test")
        if a["company_id"]:
            assert "illustrative" not in a["display_name"].casefold() and "(" not in a["display_name"]


def test_people_have_person_names_not_role_or_company_words(root):
    # every part of a display name is a protected name in the egress vault; "Family" or "Admin" would block
    # ordinary industry text (3 Oct 2026)
    run(root)
    banned = {"admin", "company", "family", "office", "sponsor", "analyst", "harbor", "capital", "lakeside"}
    for a in accounts(root):
        if a["company_id"]:
            assert not banned & set(a["display_name"].casefold().replace("(", " ").replace(")", " ").split())


def test_the_analyst_is_nobodys_owner_and_the_story_owners_are_people_or_clearly_off_system(root):
    """CRITIC-M2 P7: Sara Lim, the story's process owner, holds the owner role; the analyst is a separate person; no extra Lena Kerr;
    Lina Ho (HR) has no account and is named as an off-system owner who answers by link."""
    run(root)
    lakeside = {a["display_name"]: a["roles"] for a in accounts(root) if a["company_id"] == "lakeside-family-office"}
    assert lakeside["Sara Lim"] == ["owner"] and lakeside["Priya Nair"] == ["analyst"]
    assert "Lena Kerr" not in lakeside and "Lina Ho" not in lakeside
    assert seed.OFF_SYSTEM_OWNERS == {"lakeside-family-office": ["Lina Ho"]}
    assert seed.seed(root)["off_system_owners"] == seed.OFF_SYSTEM_OWNERS  # the seed's own summary names her
    names = [a["display_name"] for a in accounts(root) if a["company_id"]]
    assert "Lena Kerr" not in names and names.count("Sara Lim") == 3  # one owner account in each of the three full companies, never an analyst


def test_a_rerun_renames_people_seeded_with_old_names(root):
    run(root)
    store = AccountStore(root)
    email = accounts(root)[1]["email"]
    store.set_display_name(email, "Illustrative Company Admin (Old)")
    run(root)
    assert "Company Admin" not in store.get_by_email(email)["display_name"]


def test_nothing_written_outside_data_root(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    root = work / "data"
    snapshot = set(tmp_path.rglob("*"))
    run(root)
    new = set(tmp_path.rglob("*")) - snapshot
    assert all(p == root or root in p.parents for p in new)


def test_existing_company_data_untouched(root):
    run(root)
    cid = PlaneStore(root).list_company_ids()[0]
    marker = PlaneStore(root).plane_for(cid).area("context") / "marker.txt"
    marker.write_text("keep me")
    run(root)
    assert marker.read_text() == "keep me"


def test_doctor_says_model_calls_are_off_when_switched_off(good):
    good["env"]["SH_MODEL_PROVIDER"] = "off"
    name, ok, fix = result(doctor.checks(**good), "Model calls")
    assert ok and name == "Model calls: off" and "FAKE-model-key" not in name + fix


def test_the_seed_gives_each_company_only_its_own_industrys_demo_documents(root, capsys):
    from sh_platform.context_docs.store import DocStore
    assert run(root) == 0 and "Demo documents added: 42" in capsys.readouterr().out  # (5 test-pack documents + 16 story) on each of North's and Lens's shelves
    counts = {i: len(DocStore(PlaneStore(root).plane_for(i)).documents("north")) for i in PlaneStore(root).list_company_ids()}
    assert sorted(counts.values()) == [0, 0, 0, 21]
    fam = DocStore(PlaneStore(root).plane_for(next(i for i, n in counts.items() if n)))
    lens, north = fam.documents("lens"), fam.documents("north")
    assert len(lens) == 21 and {d["visibility"] for d in lens} == {"shared_full"} and {d["visibility"] for d in north} == {"private"}
    assert sorted(d["filename"] for d in lens if d["restricted"]) == sorted(d["filename"] for d in north if d["restricted"])
    assert run(root) == 0 and "Demo documents added: 0" in capsys.readouterr().out  # never a duplicate
