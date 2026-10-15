"""W11: one shared warehouse connection in the server; threads write at once without a busy file; a second process gets a plain
message naming the server."""
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sh_platform.v1 import wh  # noqa: E402

PY = sys.executable


class Plane:
    def __init__(self, root: Path):
        self.root = root

    def path(self, *parts) -> Path:
        return self.root.joinpath(*parts)


@pytest.fixture
def plane(tmp_path, monkeypatch):
    monkeypatch.setattr(wh, "_ensure_schema", lambda plane, con: con.execute("create table if not exists t (thread int, i int)"))
    wh.reset_cache()
    yield Plane(tmp_path)
    wh.reset_cache()


def _hammer(plane, threads=8, each=30):
    errors = []

    def work(n):
        for i in range(each):
            try:
                with wh.connect(plane) as con:
                    con.execute("insert into t values (?, ?)", [n, i])
                    con.execute("select count(*) from t").fetchone()
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

    ts = [threading.Thread(target=work, args=(n,)) for n in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return errors


def test_server_threads_share_one_connection(plane):
    wh.serve()
    errors = _hammer(plane)
    assert errors == []
    assert len(wh._SHARED) == 1
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from t").fetchone()[0] == 240
    assert "Signal Harbor server" in Path(str(wh.path(plane)) + ".server").read_text(encoding="utf-8")
    wh.release()
    assert wh._SHARED == {} and not Path(str(wh.path(plane)) + ".server").exists()


def test_without_server_mode_threads_still_write(plane):
    assert _hammer(plane, threads=4, each=20) == []
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from t").fetchone()[0] == 80


def test_script_while_server_runs_gets_a_plain_message(plane):
    wh.serve()
    with wh.connect(plane) as con:
        con.execute("insert into t values (0, 0)")
    script = (f"import sys; sys.path.insert(0, {str(ROOT)!r}); from sh_platform.v1 import wh; wh._TRIES = 2; wh._WAIT = 0.1\n"
              f"wh._READY.add({str(wh.path(plane))!r})\n"
              f"class P:\n    def path(self, *a): return __import__('pathlib').Path({str(plane.root)!r}).joinpath(*a)\n"
              "try:\n    wh.connect(P())\nexcept wh.Busy as e:\n    print(e)\n")
    out = subprocess.run([PY, "-c", script], capture_output=True, text=True, timeout=60)
    assert "open in another program" in out.stdout and "Signal Harbor server (process" in out.stdout, out.stdout + out.stderr
    assert "Traceback" not in out.stderr
