"""tools/seed_neera.py on an empty data root: the company, ten people, the pack's data and documents, nothing in intents; a re-run adds nothing."""
from tools import seed_neera as N


def test_seed_neera_is_idempotent_and_starts_empty(tmp_path):
    first = N.seed(tmp_path, log=lambda *_: None)
    assert first["company"]["created"] and len(first["company"]["modules"]) == 6
    assert first["accounts"]["created"] == 10
    assert first["profile"] == {"areas_added": 6, "people_added": 10, "systems_added": 7}
    assert first["pack"]["documents"]["added"] == 48 and first["pack"]["gold"]
    plane = tmp_path / "neera"
    assert not list((plane / "intents").glob("*-*/intent.json"))  # no intents, no opportunities, no week files
    assert not (plane / "intents" / "opportunities").exists()
    again = N.seed(tmp_path, log=lambda *_: None)
    assert not again["company"]["created"] and again["accounts"]["created"] == 0
    assert again["profile"] == {"areas_added": 0, "people_added": 0, "systems_added": 0}
    assert again["pack"]["documents"] == {"added": 0, "kept": 48}
    assert (tmp_path / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").count(".neera@") == 10
