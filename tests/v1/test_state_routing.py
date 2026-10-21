"""Production mode keeps every JSON document of a company plane in the state store (sh_platform/state/routing.py).
Real Postgres tests use the database signal_harbor_test (TEST_PG_URL, else built from D:/Temp/sh3-prod/.env); they skip when it cannot be reached."""
import datetime
import importlib.util
import json
import os
import re
import threading
import uuid
from pathlib import Path

import pytest

from sh_platform import jsonfile
from sh_platform.plane import PlaneStore
from sh_platform.state import Conflict, FileStore, PgStore, routing, update
from sh_platform.v1 import v3_harbor as H


def _pg_url():
    if os.environ.get("TEST_PG_URL"):
        return os.environ["TEST_PG_URL"]
    env = Path("D:/Temp/sh3-prod/.env")
    m = re.search(r"^SH_PG_PASSWORD=(.+)$", env.read_text(encoding="utf-8"), re.M) if env.is_file() else None
    return f"postgresql://sh:{m.group(1).strip()}@127.0.0.1:5434/signal_harbor_test" if m else None


@pytest.fixture(scope="module")
def pg_url():
    url = _pg_url()
    try:
        import psycopg
        psycopg.connect(url, connect_timeout=3).close()
    except Exception:  # noqa: BLE001
        pytest.skip("no test Postgres")
    return url


@pytest.fixture
def co():
    """A company id no other test run shares."""
    return "t" + uuid.uuid4().hex[:10]


@pytest.fixture
def pg(pg_url, co):
    store = PgStore(pg_url)
    yield store
    routing.release()
    for kind in ("v3", "intents", "build", "projects", "settings"):
        for k in store.keys(kind, co):
            store.delete(kind, k)


def _trace(store, co):
    """A sequence of writes, reads, lists and conflicts; what each step gives back."""
    out = []

    def k(p):
        return f"{co}/{p}"

    def short(keys):
        return [x[len(co) + 1:] for x in keys]

    out.append(store.get("intents", k("i1/a.json")))
    v1 = store.put("intents", k("i1/a.json"), {"n": 1}, expected="0")
    out.append(store.get("intents", k("i1/a.json"))[0])
    for stale in ("0", "nope"):
        try:
            store.put("intents", k("i1/a.json"), {"n": 2}, expected=stale if isinstance(store, FileStore) else {"0": "0", "nope": "999"}[stale])
            out.append("no conflict")
        except Conflict:
            out.append("conflict")
    store.put("intents", k("i1/a.json"), {"n": 3}, expected=v1)
    out.append(store.get("intents", k("i1/a.json"))[0])
    store.put("intents", k("i1/b.json"), {"é": [1, 2.5, None, "x"]})
    store.put("intents", k("i2/c.json"), {"c": True})
    store.put("build", k("i1/z.json"), {"other": "kind"})
    out.append(short(store.keys("intents", co + "/")))
    out.append(short(store.keys("intents", co + "/i1/")))
    out.append(store.get("intents", k("i1/b.json"))[0])
    out.append(update(store, "intents", k("i1/a.json"), lambda d: {"n": d["n"] + 10}))
    store.delete("intents", k("i2/c.json"))
    out.append(store.get("intents", k("i2/c.json")))
    out.append(short(store.keys("intents", co + "/")))
    for bad in ("x/../y.json", "/abs.json", "noslash"):
        try:
            store.get("intents", bad)
            out.append("accepted")
        except ValueError:
            out.append("refused")
    store.delete("intents", k("i1/a.json"))
    store.delete("intents", k("i1/b.json"))
    store.delete("build", k("i1/z.json"))
    return out


def test_file_store_and_pg_store_give_the_same_results(tmp_path, pg, co):
    a, b = _trace(FileStore(tmp_path), co), _trace(pg, co)
    assert a == b and "no conflict" not in a and a.count("conflict") == 2


def test_a_v3_thread_round_trips_through_postgres_and_leaves_no_file(tmp_path, pg, co):
    routing.configure(tmp_path, pg)
    plane = PlaneStore(tmp_path).create(co)
    th = {"id": "t-abc", "created": "2026-10-20T10:00:00Z", "stage": "open", "iid": "i1", "events": [{"k": "x", "when": datetime.date(2026, 1, 2)}]}
    H.save(plane, th)
    assert H.load(plane, "t-abc")["events"][0]["when"] == "2026-01-02"  # default=str, as the file did
    H.save(plane, {**th, "id": "t-def", "created": "2026-10-21T10:00:00Z"})
    H.save(plane, {**th, "id": "t-old", "created": "2026-10-19T10:00:00Z", "stage": "discarded"})
    assert [t["id"] for t in H.all_threads(plane)] == ["t-def", "t-abc"]
    assert len(H.all_threads(plane, discarded=True)) == 3
    assert pg.get("v3", f"{co}/threads/t-abc.json")[0]["iid"] == "i1"  # same key scheme as the migration
    assert not list((tmp_path / co).rglob("*.json"))  # nothing on the volume
    with pytest.raises(KeyError):
        H.load(plane, "t-missing")
    other = PlaneStore(tmp_path).create(co + "x")  # another company sees none of it
    assert H.all_threads(other) == []
    with H.LOCK:  # the advisory lock is taken and given back
        with H.LOCK:
            pass


def test_path_methods_go_to_the_store_for_documents_and_to_disk_for_the_rest(tmp_path, pg, co):
    routing.configure(tmp_path, pg)
    plane = PlaneStore(tmp_path).create(co)
    p = plane.path("projects", "prj-1.json")
    assert not p.exists()
    p.write_text(json.dumps({"id": "prj-1"}), encoding="utf-8")
    assert p.is_file() and json.loads(p.read_text(encoding="utf-8")) == {"id": "prj-1"} and p.stat().st_mtime > 0
    plane.path("projects", "prj-2", "comments.json").write_text("[]", encoding="utf-8")
    assert [x.name for x in sorted(plane.path("projects").glob("prj-*.json"))] == ["prj-1.json"]
    assert plane.path("projects", "prj-2").is_dir() and [x.name for x in plane.path("projects").iterdir() if x.is_dir()] == ["prj-2"]
    assert sorted(x.name for x in plane.path("projects").rglob("*.json")) == ["comments.json", "prj-1.json"]
    plane.path("projects", "prj-1.json").replace(plane.path("projects", "prj-9.json"))
    assert not p.exists() and plane.path("projects", "prj-9.json").exists()
    plane.path("projects", "prj-9.json").unlink()
    assert not plane.path("projects", "prj-9.json").exists()
    with pytest.raises(FileNotFoundError):
        plane.path("projects", "prj-9.json").unlink()
    plane.path("projects", "prj-9.json").unlink(missing_ok=True)
    # a log, a dropped file and a raw upload stay on the volume
    plane.path("ops").mkdir(exist_ok=True)
    plane.path("ops", "audit.jsonl").write_text("{}\n", encoding="utf-8")
    plane.path("dropbox").mkdir(exist_ok=True)
    plane.path("dropbox", "d.json").write_text("[1]", encoding="utf-8")
    plane.path("projects", "prj-2", "files").mkdir(parents=True)
    plane.path("projects", "prj-2", "files", "up.json").write_text("[2]", encoding="utf-8")
    assert (tmp_path / co / "ops" / "audit.jsonl").is_file() and (tmp_path / co / "dropbox" / "d.json").is_file()
    assert (tmp_path / co / "projects" / "prj-2" / "files" / "up.json").is_file()
    assert pg.keys("projects", co + "/") == [f"{co}/prj-2/comments.json"]


def test_read_json_strict_and_write_json_atomic_use_the_store(tmp_path, pg, co):
    routing.configure(tmp_path, pg)
    plane = PlaneStore(tmp_path).create(co)
    f = plane.path("settings", "a.json")
    assert jsonfile.read_json_strict(f) is None
    jsonfile.write_json_atomic(f, {"a": 1})
    assert jsonfile.read_json_strict(f, dict) == {"a": 1} and pg.get("settings", f"{co}/a.json")[0] == {"a": 1}
    with pytest.raises(ValueError):
        jsonfile.read_json_strict(f, list)
    assert not any(tmp_path.rglob("*.json*"))


def test_the_platform_control_files_are_state_too(tmp_path, pg, co):
    routing.configure(tmp_path, pg)
    f = tmp_path / "_control" / f"{co}.json"
    jsonfile.write_json_atomic(f, [{"id": "u1"}])
    try:
        assert jsonfile.read_json_strict(f, list) == [{"id": "u1"}] and pg.get("control", f"_control/{co}.json")[0] == [{"id": "u1"}]
        assert not (tmp_path / "_control").exists()
        assert type(jsonfile.lock_for(f)).__name__ == "PgLock"
    finally:
        pg.delete("control", f"_control/{co}.json")


def test_two_processes_updating_one_document_under_lock_for_lose_nothing(tmp_path, pg_url, co):
    pg_a = PgStore(pg_url)
    ra, rb = routing.Route(tmp_path, pg_a), routing.Route(tmp_path, PgStore(pg_url))  # two routes = two PgLock objects, as two processes have
    path = tmp_path / co / "build" / "counter.json"
    pg_a.put("build", f"{co}/counter.json", {"n": 0})

    def work(route):
        lock = routing.PgLock(route, routing.lock_name(route, path))
        for _ in range(15):
            with lock:
                d, _v = route.store.get("build", f"{co}/counter.json")
                route.store.put("build", f"{co}/counter.json", {"n": d["n"] + 1})

    ts = [threading.Thread(target=work, args=(r,)) for r in (ra, rb, ra, rb)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    try:
        assert pg_a.get("build", f"{co}/counter.json")[0] == {"n": 60}
    finally:
        pg_a.delete("build", f"{co}/counter.json")


def test_a_ticket_number_is_claimed_once(tmp_path, pg, co):
    routing.configure(tmp_path, pg)
    plane = PlaneStore(tmp_path).create(co)
    f = plane.path("build", "tickets", "TCK-0001.json")
    jsonfile.claim_new(f)
    with pytest.raises(FileExistsError):
        jsonfile.claim_new(f)


# ---- simple mode is exactly as before ---------------------------------------------------------------------------------------------------
def test_simple_mode_writes_the_same_files_as_before(tmp_path, monkeypatch):
    for k in ("DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(k, raising=False)
    assert routing.configure(tmp_path) is None and jsonfile.ROUTE is None
    plane = PlaneStore(tmp_path).create("acme")
    assert type(plane.root) is type(Path()) and type(plane.path("v3")) is type(Path())  # plain paths, no StatePath
    th = {"id": "t-abc", "created": "2026-10-20", "n": [1, {"é": 2}]}
    H.save(plane, th)
    jsonfile.write_json_atomic(plane.path("intents", "i1", "sow.json"), {"a": [1, 2]})
    plane.path("v3", "files.json").write_text(json.dumps([{"name": "x"}]), encoding="utf-8")
    got = {p.relative_to(tmp_path).as_posix(): p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file()}
    assert got == {
        "acme/v3/threads/t-abc.json": json.dumps(th, default=str),
        "acme/intents/i1/sow.json": json.dumps({"a": [1, 2]}, indent=2),
        "acme/v3/files.json": '[{"name": "x"}]',
    }
    assert H.load(plane, "t-abc") == th and [t["id"] for t in H.all_threads(plane)] == ["t-abc"]
    assert jsonfile.read_json_strict(plane.path("intents", "i1", "sow.json")) == {"a": [1, 2]}
    assert type(jsonfile.lock_for(plane.path("v3", "files.json"))).__name__ == "RLock"


def test_the_migration_and_the_app_agree_on_what_a_document_is(tmp_path):
    spec = importlib.util.spec_from_file_location("mig", Path(__file__).resolve().parents[2] / "tools" / "migrate_to_postgres.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    files = ["acme/intents/i1/sow.json", "acme/v3/threads/t.json", "acme/dropbox/up.json", "acme/landing/originals/x__a.json",
             "acme/projects/p1/files/raw.json", "acme/projects/p1/comments.json", "acme/ops/audit.jsonl", "acme/build/x.json.tmp",
             "acme/warehouse/w.json", "acme/settings/s.json", "_control/accounts.json", "_control/vault.bin"]
    for f in files:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("{}")
    store = FileStore(tmp_path / "dst")
    m.migrate(tmp_path, store)
    route = routing.Route(tmp_path, store)
    mine = sorted(f"{route.key(tmp_path / f)[0]}:{route.key(tmp_path / f)[1]}" for f in files if route.key(tmp_path / f))
    theirs = sorted(f"{kind}:{key}" for kind in ("intents", "v3", "projects", "settings", "ops", "build", "control") for key in store.keys(kind))
    assert mine == theirs and len(mine) == 5
