"""The production-mode worker: runs queued jobs (pipeline runs, deliveries, graph rebuilds) and hands outbox events to their consumers.

    set DATABASE_URL=...  set REDIS_URL=...   python tools/worker.py

Needs the same data root and settings as the web server (SH_DATA_ROOT). Run one or several; a job is taken by exactly one worker.
Stops cleanly on Ctrl+C. Exits with a plain message when it is not in production mode.
"""
import logging
import signal
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sh_platform import jobs, mode  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        if mode.check() != "production":
            print("Not in production mode: set both DATABASE_URL and REDIS_URL.")
            return 2
    except mode.ModeError as e:
        print(e)
        return 2
    from sh_platform.settings import load_settings
    from sh_platform.state import routing
    routing.configure(load_settings().data_root)  # the same documents as the web app: Postgres
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    logging.getLogger("worker").info("worker started")
    jobs.run_worker(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
