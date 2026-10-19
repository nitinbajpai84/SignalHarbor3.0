"""r7: a client polling every 5 s got connection resets while a thread was working. Uvicorn closed a kept-alive socket after its default 5 s idle,
just as the next poll went out on it. The server keeps idle connections for KEEP_ALIVE_S, and every launcher passes it. Also: POST /api/v3/files
judges files with the model, so it runs off the event loop. Synthetic, local only."""
import ast
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import KEEP_ALIVE_S  # noqa: E402

GET = b"GET /t HTTP/1.1\r\nHost: x\r\n\r\n"


SERVER = ("import sys, uvicorn\nfrom fastapi import FastAPI\napp = FastAPI()\napp.get('/t')(lambda: {'ok': True})\n"
          "uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='error', timeout_keep_alive=int(sys.argv[2]))")


def _serve(port: int, keep: int) -> subprocess.Popen:
    """Its own process: importing uvicorn here would put this test worker's warehouse into server mode (wh.connect checks sys.modules)."""
    srv = subprocess.Popen([sys.executable, "-c", SERVER, str(port), str(keep)])
    for _ in range(200):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return srv
        except OSError:
            time.sleep(0.05)
    srv.kill()
    raise RuntimeError("the test server did not start")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _second_poll_after(port: int, idle: float) -> bytes:
    """Two requests on one kept-alive connection, `idle` seconds apart: what the second one gets back."""
    def answer(c) -> bytes:
        got = b""
        while not got.endswith(b'{"ok":true}'):
            part = c.recv(4096)
            if not part:
                return got
            got += part
        return got

    with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
        c.sendall(GET)
        assert answer(c).startswith(b"HTTP/1.1 200")
        time.sleep(idle)
        try:
            c.sendall(GET)
            return answer(c)
        except OSError:  # a reset
            return b""


def test_an_idle_connection_outlives_a_5_second_poll():
    assert KEEP_ALIVE_S > 30
    port = _free_port()
    srv = _serve(port, KEEP_ALIVE_S)
    try:
        assert _second_poll_after(port, 5.5).startswith(b"HTTP/1.1 200")
    finally:
        srv.kill()
    port = _free_port()
    srv = _serve(port, 5)  # uvicorn's default: the same poll finds the socket closed
    try:
        assert not _second_poll_after(port, 5.5).startswith(b"HTTP/1.1 200")
    finally:
        srv.kill()


def test_every_launcher_passes_the_keep_alive():
    for f in ("tools/serve_test.py", "tools/serve_v1.py"):
        assert "timeout_keep_alive=KEEP_ALIVE_S" in (ROOT / f).read_text(encoding="utf-8"), f
    assert f"--timeout-keep-alive {KEEP_ALIVE_S}" in (ROOT / "tools/start.sh").read_text(encoding="utf-8")


def test_v3_routes_never_judge_files_on_the_event_loop():
    """The async routes of v3_routes hand drop, scan and decorate to the thread pool; none calls them directly."""
    src = (ROOT / "sh_platform/v1/v3_routes.py").read_text(encoding="utf-8")
    for fn in (n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.AsyncFunctionDef)):
        direct = [ast.get_source_segment(src, c.func) for c in ast.walk(fn) if isinstance(c, ast.Call)
                  and not any(c in ast.walk(x) for x in ast.walk(fn) if isinstance(x, (ast.Lambda, ast.FunctionDef)))]
        assert not {"H.scan", "H.drop", "SO.decorate"} & set(direct), fn.name
