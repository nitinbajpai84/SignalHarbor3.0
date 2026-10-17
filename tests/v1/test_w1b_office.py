"""Wave 1b, domain office, cards 51 to 100 (docs/v3/w1/build51-office.md). None of the 20 cards of this domain can be built on the real pack readers yet: each one
reads a file kind the pack has no reader for (the 36 kinds of tools/gen_office6m/more.py NEW_KINDS), and nine also need a table the model steward left for later
(docs/v3/MODEL-ADDITIONS.md, class d). This test keeps that honest: it reads the card's input kinds from answer_keys.yaml and fails the day a card's files are
all read, which is the day to build the card (recipe in recipes/office.yaml, signals, builds/office-51.yaml, key values from answer_keys.yaml)."""
import re
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import wh
from tests.v1.test_w2_loader import office_dropbox  # noqa: F401  (the same dropbox copy as the W2 loader test)

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
CARDS = [c["id"] for c in yaml.safe_load((REPO / "packs/family_office/1/use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"]
         if c.get("domain") in ("Run the office", "Family and people") and c["order"] > 50 and c["id"] in KEYS]


def kinds_of(card: str) -> set[str]:
    """The file kinds (folder names) in the card's input_files: '*/kind/file' or 'kind/file'."""
    return {m.group(1) for f in KEYS[card]["input_files"] if (m := re.match(r"(?:\*/)?([a-z_]+)/", f))}


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w1b")
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    return L.load_plane(plane, office_dropbox(tmp))


def test_the_domain_has_twenty_cards_to_51_to_100():
    assert len(CARDS) == 20, CARDS


@pytest.mark.parametrize("card", CARDS)
def test_card_waits_for_a_reader(card, report):
    unread = {k for k in kinds_of(card) if k in report and "no reader for this kind" in report[k]["not_loaded"]}
    assert unread, f"{card}: every input kind now has a reader ({sorted(kinds_of(card))}); build the card (docs/v3/w1/build51-office.md)"
