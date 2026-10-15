"""Film the launch film's Build scenes (11 Architecture, 12 Pipelines, 13 Studio, 14 Approval) again on the V6 screens.

    python tools/video/film6.py --rehearse      # Testing mode only (free): checks the moves, keeps nothing
    python tools/video/film6.py --real          # scenes 11 and 13 once more in Real use (paid), 12 and 14 in Testing; then stops the server

Own data folder (.sh-tmp/testenv/vid6) and port 8696. The new project is taken to the builder's first run before the server starts
(vid6_prep.py ready); the demo project carries scenes 11, 13 and 14. After this: python tools/video/build.py --film --assemble-only.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

os.environ["SH_FILM_ENV"] = "vid6"
os.environ["SH_FILM_PORT"] = "8696"
ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "docs/video/out/film/new_project.txt"
os.environ["SH_FILM_NEW"] = str(NEW)
sys.path.insert(0, str(Path(__file__).parent))
import record  # noqa: E402
import narrate  # noqa: E402
from common import BASE, DATA  # noqa: E402

PREP = str(Path(__file__).with_name("vid6_prep.py"))


def stop() -> None:
    ps = ("Get-NetTCPConnection -LocalPort 8696 -State Listen -ErrorAction SilentlyContinue | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(1.5)


def up() -> bool:
    try:
        return urllib.request.urlopen(BASE + "/", timeout=3).status == 200
    except OSError:
        return False


def fresh() -> None:
    stop()
    subprocess.run([sys.executable, str(ROOT / "tools/make_test_env.py"), "vid6", "--seed"], check=True, cwd=ROOT)
    run = lambda *a: subprocess.run([sys.executable, PREP, *a], check=True, cwd=ROOT, capture_output=True, text=True).stdout.split()[-1]  # noqa: E731
    pid = run("start")
    NEW.write_text(pid, encoding="utf-8")
    run("ready")
    run("report")
    subprocess.Popen([sys.executable, str(ROOT / "tools/serve_test.py"), "--port", "8696", "--data-root", str(DATA)], cwd=ROOT,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        if up():
            return
        time.sleep(1)
    raise SystemExit("the recording server did not start")


if __name__ == "__main__":
    real = "--real" in sys.argv
    narrate.main()
    try:
        fresh()
        if real:
            os.environ["SH_RERECORD"] = "11 13"
        only = [int(a) for a in sys.argv[1:] if a.isdigit()] or [11, 12, 13, 14]     # e.g. `--real 14`: only scene 14, in Testing
        record.main(only, agents=real, rehearse=not real)
    finally:
        stop()
