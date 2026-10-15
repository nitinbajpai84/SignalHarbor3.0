"""Seed one empty company with one owner account, for a from-scratch walk of the product (illustrative, synthetic).

Idempotent: the company and the account are made once; a re-run only switches on any module that is off. The password is appended to
<data_root>/_control/seed_credentials.txt and never printed. No data, no people, no areas: the owner sets the company up on screen."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.jsonfile import lock_for  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from tools.seed import HEADER, _new_password  # noqa: E402

COMPANY, NAME, INDUSTRY = "fresh", "Fresh Harbour Family Office", "family_office"
OWNER, EMAIL, ROLES = "Fresh Owner", "nitin.fresh@example.test", ["company_admin", "sponsor"]


def seed(data_root: Path) -> dict:
    es = EntitlementStore(data_root)
    made_company = es.company(COMPANY) is None
    if made_company:
        es.create_company(COMPANY, NAME, INDUSTRY, modules=es.catalogue.ids)
    for m in es.catalogue.ids:
        if not es.is_enabled(COMPANY, m):
            es.set_module(COMPANY, m, True)
    store = AccountStore(data_root)
    made_account = store.get_by_email(EMAIL) is None
    if made_account:
        password = _new_password()
        store.create(EMAIL, password, OWNER, COMPANY, ROLES)
        creds = data_root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + f"\n{EMAIL}  {password}  {'+'.join(ROLES)}  {COMPANY}\n", encoding="utf-8")
    return {"company_created": made_company, "account_created": made_account, "modules": es.enabled_modules(COMPANY)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", default=None, help="default: SH_DATA_ROOT from settings")
    a = ap.parse_args(argv)
    root = Path(a.data_root) if a.data_root else Path(load_settings({}).data_root)
    r = seed(root)
    print(f"{NAME} ({COMPANY}): company {'created' if r['company_created'] else 'already there'}, "
          f"owner account {'created' if r['account_created'] else 'already there'}, modules on: {', '.join(r['modules'])}.")
    print(f"Sign-in details are in: {root / '_control' / 'seed_credentials.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
