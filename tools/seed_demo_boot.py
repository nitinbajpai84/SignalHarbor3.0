"""First boot of the public demo: seeds the Evergreen family-office demo (seed_10uc runs seed_evergreen and seed_v3_demo too) into SH_DATA_ROOT
only when the volume has never been seeded. Idempotent, never wipes. Demo date pinned to 9 Oct 2026 (demo_today). Generated logins go to
<data_root>/_control/seed_credentials.txt and are never printed. SH_DEMO_PASSWORD (12+ characters, optional) sets one shared password on every
seeded account instead; it is read from the environment and never written or printed.

After the first seed (and on every later boot, because each step skips what is already there) tools/seed_demo_ready.py makes every screen
have something to show: silver tables, runs, live market rows, Action items, a pending model extension, a published and a delivered dashboard and the
benchmark project end to end (DEMO1). A step that fails is printed and never stops the boot.

Usage: python tools/seed_demo_boot.py [--data-root PATH] [--reset [--allow-repo-data] [--reset-db]]
  --reset  wipes everything inside the data root, then seeds it again from nothing (new sign-in details). It never touches the repo's own data/ unless
           --allow-repo-data is also given. Restart the web app afterwards (it keeps the old warehouse file open); see docs/demo/DEMO-DATA.md.
  --reset-db  with --reset and DATABASE_URL set: also TRUNCATE the sh_state_* and sh_outbox* tables (production mode keeps app records there). Never drops a table.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MARKER = "demo_seeded.json"


def boot(data_root: Path) -> str:
    """'seeded', 'kept' (already seeded: nothing touched) or 'kept+password'. Never prints a password."""
    from sh_platform.auth.accounts import AccountStore
    from tools import seed_10uc

    marker = data_root / "_control" / MARKER
    state = "kept"
    if not marker.is_file():
        data_root.mkdir(parents=True, exist_ok=True)
        seed_10uc.seed(data_root)  # EG.seed + V3.seed inside; demo_today = 9 Oct 2026
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"seeded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
        state = "seeded"
    from tools import seed_demo_ready

    for step, what in seed_demo_ready.seed(data_root).items():
        print(f"  demo-ready {step}: {what}")
    shared = (os.environ.get("SH_DEMO_PASSWORD") or "").strip()
    if shared:
        if len(shared) < 12:
            raise SystemExit("SH_DEMO_PASSWORD is shorter than 12 characters: not used.")
        store = AccountStore(data_root)
        for acct in store._read():  # the account file is the list; no public lister exists
            store.set_password(acct["email"], shared)
        state += "+password"
    return state


def reset(data_root: Path, allow_repo_data: bool = False) -> None:
    """Empty the data root (its contents, not the folder: on Railway the folder is the volume mount). Refuses the repo's data/ and any short or root-like path."""
    root = data_root.resolve()
    volume = os.environ.get("SH_DATA_ROOT")
    if os.environ.get("RAILWAY_ENVIRONMENT") and volume and root == Path(volume).resolve():
        pass  # the deployed volume itself (Railway mounts it at /data, which the repo's data/ may point to): an explicit, intended reset
    elif root == (ROOT / "data").resolve() and not allow_repo_data:
        raise SystemExit("Refusing to reset the repo's own data/. Pass --allow-repo-data if you really mean it.")
    elif len(root.parts) < 3 or root == Path.home().resolve():
        raise SystemExit(f"Refusing to reset {root}: not a data root.")
    from sh_platform.v1 import wh
    wh.reset_cache()  # any open warehouse handle of this process
    for child in root.iterdir() if root.is_dir() else []:
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def reset_db(url: str, connect=None) -> list[str]:
    """TRUNCATE every sh_state_* and sh_outbox* table of the database (rows only; the tables stay). Returns the tables emptied."""
    if connect is None:
        import psycopg
        connect = lambda: psycopg.connect(url)  # noqa: E731
    with connect() as conn:
        names = [r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema = current_schema() and table_type = 'BASE TABLE' "
            "and (table_name like 'sh!_state!_%' escape '!' or table_name like 'sh!_outbox%' escape '!') order by 1").fetchall()]
        for n in names:  # names come from the catalogue query above, never from input
            conn.execute(f'TRUNCATE TABLE "{n}" RESTART IDENTITY')
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT")
    ap.add_argument("--reset", action="store_true", help="wipe the data root, then seed it again")
    ap.add_argument("--allow-repo-data", action="store_true", help="with --reset: allow the repo's own data/")
    ap.add_argument("--reset-db", action="store_true", help="with --reset and DATABASE_URL: truncate the sh_state_* and sh_outbox* tables")
    a = ap.parse_args(argv)
    root = Path(a.data_root or os.environ.get("SH_DATA_ROOT") or "./data")
    if a.reset_db and not a.reset:
        raise SystemExit("--reset-db goes with --reset.")
    if a.reset:
        if not (a.data_root or os.environ.get("SH_DATA_ROOT")):
            raise SystemExit("--reset needs --data-root (or SH_DATA_ROOT): it will not guess which folder to wipe.")
        reset(root, a.allow_repo_data)
        if a.reset_db:
            url = os.environ.get("DATABASE_URL")
            if not url:
                raise SystemExit("--reset-db needs DATABASE_URL (production mode).")
            print(f"Emptied {len(reset_db(url))} database tables (rows only).")
    print(f"Demo boot: {boot(root)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
