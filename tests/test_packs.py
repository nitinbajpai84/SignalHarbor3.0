import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from modules.m1_intent.agent import north
from modules.m1_intent.tools.pack_tools import ground, load_guidance
from sh_platform.agents.protocols import ModelReply
from sh_platform.packs import EmptyPack, Pack, PackLoader

REAL = PackLoader(Path(__file__).resolve().parents[1] / "packs")


def _tmp_pack(root, industry, version, label, data):
    d = root / industry / str(version)
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(f"industry: {industry}\nversion: {version}\nlabel: {label}\n")
    for name, text in data.items():
        (d / name).write_text(text)


def test_industries_lists_both_packs():
    assert {"insurance", "asset_management"} <= set(REAL.industries())


@pytest.mark.parametrize("industry", ["insurance", "asset_management"])
def test_loads_each_real_pack(industry):
    p = REAL.load(industry)
    assert isinstance(p, Pack) and p.industry == industry and p.version == 1 and not p.empty
    for name in ("problems", "glossary", "kpi_tree", "feeds"):
        assert name in p.sections()
        assert p.section(name)
    assert "pack" not in p.sections()
    assert "suggestion" in p.suggestion_label


def test_unknown_section_raises():
    with pytest.raises(KeyError):
        REAL.load("insurance").section("nope")


def test_unknown_industry_is_empty_never_fallback():
    p = REAL.load("retail")
    assert isinstance(p, EmptyPack) and p.empty and p.industry == "retail"
    assert p.sections() == []
    with pytest.raises(KeyError):
        p.section("glossary")


def test_empty_message_has_no_industry_wording():
    m = REAL.load("retail").message.lower()
    assert "no industry knowledge" in m
    for w in ("insurance", "asset", "insurer"):
        assert w not in m


def test_two_industries_differ():
    a, b = REAL.load("insurance"), REAL.load("asset_management")
    assert a.section("kpi_tree") != b.section("kpi_tree")
    assert a.section("glossary") != b.section("glossary")


@pytest.mark.parametrize("bad", ["..", "../insurance", "a/b", "a\\b", "Insurance", "", "x y", "a.b"])
def test_bad_industry_rejected(bad):
    with pytest.raises(ValueError):
        REAL.load(bad)


@pytest.mark.parametrize("bad", ["..", "1/../1", "x", "-1", "1.0"])
def test_bad_version_rejected(bad):
    with pytest.raises(ValueError):
        REAL.load("insurance", bad)


def test_latest_version_and_explicit(tmp_path):
    _tmp_pack(tmp_path, "toy", 2, "Toy", {"a.yaml": "k: two\n"})
    _tmp_pack(tmp_path, "toy", 10, "Toy", {"a.yaml": "k: ten\n"})
    _tmp_pack(tmp_path, "toy", 9, "Toy", {"a.yaml": "k: nine\n"})
    ld = PackLoader(tmp_path)
    assert ld.load("toy").section("a") == {"k": "ten"}
    assert ld.load("toy", 2).section("a") == {"k": "two"}
    assert ld.load("toy", "9").version == 9
    assert ld.load("toy", 3).empty  # missing version: honest empty, no substitute


def test_json_sections_and_non_sections_ignored(tmp_path):
    _tmp_pack(tmp_path, "toy", 1, "Toy", {"x.json": '{"a": 1}', "notes.md": "hi"})
    p = PackLoader(tmp_path).load("toy")
    assert p.sections() == ["x"] and p.section("x") == {"a": 1} and p.label == "Toy"


def test_missing_root_gives_no_industries(tmp_path):
    ld = PackLoader(tmp_path / "none")
    assert ld.industries() == [] and ld.load("insurance").empty


def test_status_and_metadata_files(tmp_path):
    p = REAL.load("asset_management")
    assert p.status == "proposed" and REAL.load("insurance").status == "approved"
    assert not {"pack", "template", "generator"} & set(REAL.load("insurance").sections())


def test_leading_zero_version_folder_is_ignored(tmp_path):
    _tmp_pack(tmp_path, "x", 1, "X", {"a.yaml": "k: 1\n"})
    (tmp_path / "x" / "01").mkdir()
    assert PackLoader(tmp_path).load("x").version == 1


# ---- M1-P04c: North's use of the real packs (kpi_tree, industry_defaults, glossary, problems, north)

INDUSTRIES = ["insurance", "asset_management", "family_office"]
NOTES = {  # a note in the person's words, and a word the KPI name offered for it must contain
    "insurance": ("Policies are lapsing early after the first year", "early termination"),
    "asset_management": ("We are losing clients and redemptions are rising", "redemption"),
    "family_office": ("Can we fund the capital calls over six months?", "funding"),
}


def test_the_family_office_pack_is_a_labelled_snapshot_with_provenance():
    p = REAL.load("family_office")
    meta = yaml.safe_load((REAL.root / "family_office" / "1" / "pack.yaml").read_text(encoding="utf-8"))
    assert p.version == 1 and p.label == "Family office" and meta["illustrative"] is True and p.status == "proposed"
    assert "practical-hawking" in meta["provenance"] and "2026-10-03" in meta["provenance"]
    assert {"problems", "kpi_tree", "glossary", "industry_defaults", "intent_examples", "north"} <= set(p.sections())


def test_the_family_office_pack_holds_no_client_data():
    """Data check: no email (except the reserved example.test and example.invalid domains, which can never be real), web
    address, phone or account-like number, and no real client name."""
    # an address on a reserved top-level domain (.test, .invalid, .example: RFC 2606) can never be real
    risky = re.compile(r"[\w.+-]+@(?![\w-]+(?:\.[\w-]+)*\.(?:test|invalid|example)(?![\w-]|\.\w))[\w-]+\.\w+|https?://|www\.|\+\d[\d ()-]{7,}"
                       r"|\b\d{9,}\b(?!\.\d)", re.IGNORECASE)  # a 9+ digit run is account-like; with a decimal part it is an amount (custody SGD)
    import zipfile
    for f in (REAL.root / "family_office" / "1").rglob("*"):
        if not f.is_file() or "__pycache__" in f.parts or f.name == "make_demo_module3.py":  # the generator holds schema URLs, not data
            continue
        if f.suffix == ".xlsx":  # a workbook is a zip of XML parts: scan each
            with zipfile.ZipFile(f) as z:
                text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist())
            text = re.sub(r'(?:xmlns(?::\w+)?|Type)="http://schemas\.openxmlformats\.org/[^"]*"', "", text)  # fixed schema identifiers, not data
        else:
            text = f.read_text(encoding="utf-8")
        assert not risky.search(text), f.name
        assert not banned_name_hits(text), f.name


# A real prospect's name must never appear in a tracked file, not even as a hash, so the guard reads SHA-256 hashes
# (of a lowercased word bigram "first second" and of the two words run together) from the gitignored local/ folder.
_BANNED_FILE = Path(__file__).resolve().parents[1] / "local" / "banned-names.sha256"
BANNED_NAME_HASHES = set(_BANNED_FILE.read_text(encoding="utf-8").split()) if _BANNED_FILE.is_file() else set()


def banned_name_hits(text: str, hashes=BANNED_NAME_HASHES) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    grams = {" ".join(p) for p in zip(words, words[1:])} | set(words)
    return {g for g in grams if hashlib.sha256(g.encode()).hexdigest() in hashes}


def test_the_name_guard_catches_a_bigram_however_it_is_written():
    probe = {hashlib.sha256(b"illustrative harbour").hexdigest()}
    for text in ("Illustrative Harbour", "x illustrative\n\tHARBOUR y", "illustrative-harbour"):
        assert banned_name_hits(text, probe), text
    assert not banned_name_hits("Illustrative Lakeside Family Office", probe)


def test_the_real_guard_hashes_match_the_local_company_name_when_the_local_file_exists():
    """Built at run time from the gitignored local file (never written here): the guard catches that company's display name."""
    local = Path(__file__).resolve().parents[1] / "local" / "companies.yaml"
    if not local.is_file() or not BANNED_NAME_HASHES:
        pytest.skip("no local company file on this machine")
    names = [c["name"] for c in yaml.safe_load(local.read_text(encoding="utf-8"))["companies"]]
    caught = [n for n in names if banned_name_hits(f"our client {n} said") and banned_name_hits(n.upper().replace(" ", "\n"))]
    assert caught, "the guard's hashes match none of the local companies' names"


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_each_pack_has_a_north_file_with_its_industry_wording(industry):
    n = REAL.load(industry).section("north")
    for key in ("advisor_role", "peers", "typical_breakdowns", "example_data_line"):
        assert isinstance(n[key], str) and n[key].strip()
    assert isinstance(n["rules"], list)


def test_the_family_office_north_rules_are_the_forks_seven():
    assert len(REAL.load("family_office").section("north")["rules"]) == 7


def _g(industry):
    return load_guidance(REAL, industry)


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_kpis_from_the_kpi_tree_are_offered_labelled_with_no_id(industry):
    note, word = NOTES[industry]
    g = _g(industry)
    got = ground(g, [note])
    assert got["label"] == "Industry practice (suggestion)" and got["note"] == "Your company decides."
    assert got["kpis"] and any(word in name.lower() for name in got["kpis"])
    names = {k["name"] for k in g.kpis}
    assert all(name in names for name in got["kpis"])  # only KPIs of this pack's own tree
    blob = json.dumps(got)
    assert not re.search(r"\bK\d", blob)  # ui-copy: no id (a pack figure stays: the guard lets North repeat it)


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_an_unrelated_note_offers_no_kpi(industry):
    assert ground(_g(industry), ["The coffee machine is broken again"]) == {"nothing_matched": True}


def test_an_industry_without_a_pack_offers_nothing():
    g = _g("unlisted")
    assert g.pack.empty and not g.has_content and ground(g, [NOTES["family_office"][0]]) == {"nothing_matched": True}


def test_the_family_office_company_sees_its_own_content_and_never_the_others():
    fo = _g("family_office")
    own = {k["name"] for k in fo.kpis}
    other = {k["name"] for i in ("insurance", "asset_management") for k in _g(i).kpis}
    assert not own & other
    for note, _ in NOTES.values():  # an insurance or asset management note in a family office room pulls none of their KPIs
        assert not {n for n in ground(fo, [note]).get("kpis", {})} & other


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_north_leads_with_a_labelled_draft_from_the_pack_and_asks_one_question(industry):
    note, word = NOTES[industry]
    seen = {}

    class Model:
        def complete(self, module_id, messages, tools=None):
            ctx = json.loads(messages[1]["content"])["context"]
            seen["ctx"], seen["system"] = ctx, messages[0]["content"]
            name = " and ".join(x.split(" - KPI: ")[1].split(":")[0] for x in ctx["industry_guidance"].splitlines() if " - KPI: " in x)
            return ModelReply(f"Industry practice (suggestion): others track {name}. Your company decides. Is that the measure you mean?")

    class Gate:
        def is_enabled(self, company_id, module_id):
            return True

    turns = [{"id": "t", "role": "person", "text": note, "at": "n"}]
    text, answered = north.next_question(Model(), Gate(), "co", _g(industry), turns, practice=True, library=False)
    assert answered and text.startswith("Industry practice (suggestion)") and text.count("?") == 1 and word in text.lower()
    assert _g(industry).north["advisor_role"] in seen["system"] and _g(industry).north["peers"] in seen["system"]
    for rule in _g(industry).north["rules"]:
        assert rule in seen["system"]


FO_FILES = ["clusters", "column_synonyms", "evidence_fields", "family_office.classifier", "family_office.signals",
            "feeds", "market_sources", "process_map_default"]
FO_ROOT = Path(__file__).resolve().parents[1] / "packs" / "family_office"


def test_the_family_office_pack_loads_the_second_snapshot_as_labelled_suggestions():
    p = REAL.load("family_office")
    assert not p.empty and p.status == "proposed" and "suggestion" in p.suggestion_label
    for name in FO_FILES + ["problems", "glossary", "kpi_tree", "north"]:
        assert name in p.sections() and p.section(name), name
    assert {k["id"] for k in p.section("kpi_tree")["kpis"]} >= {f"K{i:02d}" for i in range(1, 16)}  # K01-K15 already there
    meta = yaml.safe_load((FO_ROOT / "1" / "pack.yaml").read_text(encoding="utf-8"))
    assert meta["illustrative"] is True and "M1-DATA" in meta["provenance"] and "2026-10-03" in meta["provenance"]


def test_the_other_industries_do_not_get_family_office_sections():
    for industry in ("insurance", "asset_management"):
        assert not {"family_office.classifier", "family_office.signals", "evidence_fields"} & set(REAL.load(industry).sections())
    assert REAL.load("retail").empty


def test_demo_documents_are_text_types_the_reader_takes_and_never_the_adversarial_one():
    from sh_platform.context_docs import reader
    files = sorted((FO_ROOT / "1" / "demo_documents").iterdir())
    assert len(files) == 5 and not [f for f in files if f.name.startswith("untrusted")]
    for f in files:
        assert "synthetic" in f.read_text(encoding="utf-8").lower()
        assert reader.read_segments(f.name, f.read_bytes())[0][1].strip()
