"""M1-08 storage: one transcript per seat in the company's plane, atomic, strict, and per seat."""
import json
import threading

import pytest

from modules.m1_intent.store.files import StoreError
from modules.m1_intent.store.transcripts import TranscriptStore
from sh_platform.plane import PlaneStore

S1, S2 = "a" * 32, "b" * 32
SEAT1, SEAT2 = "1" * 32, "2" * 32


@pytest.fixture
def store(tmp_path):
    planes = PlaneStore(tmp_path / "data")
    (tmp_path / "data").mkdir()
    return TranscriptStore(planes.create("co-a"))


def test_a_new_room_is_empty_and_nothing_is_written_until_something_is_said(store):
    t = store.load(S1, SEAT1)
    assert t["turns"] == [] and t["notes"] == [] and t["seat_id"] == SEAT1 and t["session_id"] == S1
    assert not list(store._plane.area("intents").rglob("*.json"))


def test_update_saves_atomically_in_the_plane_under_the_seat(store):
    store.update(S1, SEAT1, lambda t: t["turns"].append({"id": "t1", "role": "person", "text": "hi", "at": "now"}))
    files = [p for p in store._plane.area("intents").rglob("*.json")]
    assert len(files) == 1 and files[0].name == f"{SEAT1}.json" and S1 in files[0].parts
    assert not list(store._plane.area("intents").rglob("*.tmp"))
    assert store.load(S1, SEAT1)["turns"][0]["text"] == "hi"


def test_each_seat_and_each_session_has_its_own_room(store):
    store.update(S1, SEAT1, lambda t: t["turns"].append({"id": "t1", "role": "person", "text": "mine", "at": "n"}))
    assert store.load(S1, SEAT2)["turns"] == [] and store.load(S2, SEAT1)["turns"] == []


def test_ids_are_checked_before_they_reach_a_path(store):
    for bad in ("../x", "A" * 32, "", "a" * 31, None):
        with pytest.raises(StoreError):
            store.load(bad, SEAT1)
        with pytest.raises(StoreError):
            store.load(S1, bad)


def test_a_damaged_file_is_refused_and_never_overwritten(store):
    store.update(S1, SEAT1, lambda t: t["turns"].append({"id": "t1", "role": "person", "text": "hi", "at": "n"}))
    path = next(store._plane.area("intents").rglob(f"{SEAT1}.json"))
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreError):
        store.load(S1, SEAT1)
    with pytest.raises(StoreError):
        store.update(S1, SEAT1, lambda t: None)
    assert path.read_text(encoding="utf-8") == "{not json"
    path.write_text(json.dumps({"session_id": S1, "seat_id": SEAT2, "turns": [], "notes": []}), encoding="utf-8")
    with pytest.raises(StoreError):  # a file that belongs to another seat is not this seat's room
        store.load(S1, SEAT1)


def test_a_failing_change_saves_nothing(store):
    def boom(t):
        t["turns"].append({"id": "t1", "role": "person", "text": "x", "at": "n"})
        raise ValueError("no")
    with pytest.raises(ValueError):
        store.update(S1, SEAT1, boom)
    assert store.load(S1, SEAT1)["turns"] == []


def test_parallel_posts_all_land(store):
    def add(i):
        store.update(S1, SEAT1, lambda t: t["turns"].append({"id": f"t{i}", "role": "person", "text": str(i), "at": "n"}))
    ts = [threading.Thread(target=add, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(store.load(S1, SEAT1)["turns"]) == 8
