"""Railway boot for the 3.0 tester demo: an empty volume gets the synthetic Evergreen Office (docs/demo/v3-office.zip, a liquidity
use case already live with July figures); a volume that holds data is never touched. Then, when SH_DEMO_PASSWORD is set (12+
characters), every account of the office signs in with it. The password is never printed or written anywhere but the account store.
    python tools/seed_v3_office.py --data-root /data"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
log = logging.getLogger("seed_v3_office")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    root = Path(ap.parse_args().data_root)
    accounts = root / "_control" / "accounts.json"
    if accounts.exists():
        log.info("v3 office: the volume already holds data; nothing unpacked")
    else:
        root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ROOT / "docs" / "demo" / "v3-office.zip") as z:
            z.extractall(root)
        log.info("v3 office: unpacked the synthetic Evergreen Office")
    pw = (os.environ.get("SH_DEMO_PASSWORD") or "").strip()
    if not pw:
        log.info("v3 office: SH_DEMO_PASSWORD is not set; sign-in is closed until it is")
        return
    if len(pw) < 12:
        raise SystemExit("SH_DEMO_PASSWORD is shorter than 12 characters: not used.")
    from sh_platform.auth.accounts import AccountStore
    store = AccountStore(root)
    emails = [a["email"] for a in json.loads(accounts.read_text(encoding="utf-8")) if a.get("email")]
    for email in emails:
        store.set_password(email, pw)
    _set_in_postgres(root, emails, pw)
    log.info("v3 office: %d demo accounts sign in with SH_DEMO_PASSWORD", len(emails))


def _set_in_postgres(root: Path, emails: list[str], pw: str) -> None:
    """Production mode: the app reads accounts from Postgres, and the copy into Postgres never overwrites, so a password set (or changed)
    after the first production boot must also be written there. On a first boot Postgres has no accounts yet: nothing to do here, the
    copy that runs next carries the volume's (new) password across."""
    from sh_platform import mode
    if not mode.production():
        return
    from sh_platform.auth.accounts import AccountStore
    from sh_platform.state import routing
    routing.configure(root)
    try:
        routed = AccountStore(root)
        for email in emails:
            try:
                routed.set_password(email, pw)
            except ValueError:  # not in Postgres yet (first production boot)
                log.info("v3 office: accounts are not in Postgres yet; the copy will carry the password")
                return
        log.info("v3 office: the demo password is set in Postgres too")
    finally:
        routing.release()


if __name__ == "__main__":
    main()
