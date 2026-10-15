"""Seed the family-office demo company for 1.0 (illustrative, synthetic): the company on the control plane, six accounts in the PRD's
roles, the profile's people and systems, and the landing files and documents restored from local/ when they exist.

Idempotent. New passwords are appended to <data_root>/_control/seed_credentials.txt and never printed. The company name is an
argument: it lives in data/ and local/ only."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.jsonfile import lock_for  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from tools.seed import HEADER, _new_password  # noqa: E402

INDUSTRY = "family_office"
# (name, title, company role)
PEOPLE = [("Meredith Shaw", "Principal and chief investment officer", "company_admin"),
          ("Daniel Kerr", "Investment analyst", "analyst"),
          ("Grace Ward", "Head of operations and finance", "analyst"),
          ("Harvey Rowley", "Tax adviser", "owner"),
          ("Aaron Lyle", "External adviser", "approver"),
          ("Katie Kingsley", "Family member", "participant")]
ROLES_EXTRA = {"Meredith Shaw": ["sponsor"]}


def email_of(name: str, company: str) -> str:
    return f"{'.'.join(name.lower().split())}.{company}@example.test"


def seed(data_root: Path, company: str, name: str) -> dict:
    es = EntitlementStore(data_root)
    made = es.company(company) is None
    if made:
        es.create_company(company, name, INDUSTRY, modules=es.catalogue.ids)
    for m in es.catalogue.ids:
        if not es.is_enabled(company, m):
            es.set_module(company, m, True)
    plane = PlaneStore(data_root).plane_for(company).ensure()
    store, lines, accounts = AccountStore(data_root), [], 0
    for person, _, role in PEOPLE:
        email = email_of(person, company)
        if store.get_by_email(email) is None:
            pw = _new_password()
            roles = [role] + ROLES_EXTRA.get(person, [])
            store.create(email, pw, person, company, roles)
            lines.append(f"{email}  {pw}  {'+'.join(roles)}  {company}")
            accounts += 1
    if lines:
        creds = data_root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    restored = {"landing": 0, "documents": 0}
    for sub, src in (("landing", ROOT / "local" / "samples" / company), ("documents", ROOT / "local" / "documents" / company)):
        if src.is_dir():
            dst = plane.path(sub)
            for f in src.rglob("*"):
                if f.is_file():
                    target = dst / f.relative_to(src)
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, target)
                        restored[sub] += 1
    return {"company_created": made, "accounts_created": accounts, "restored": restored, "modules": es.enabled_modules(company)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--company", default="ardmore-1")
    ap.add_argument("--name", default="Ardmore")
    ap.add_argument("--data-root", default=None, help="default: SH_DATA_ROOT from settings")
    a = ap.parse_args(argv)
    root = Path(a.data_root) if a.data_root else Path(load_settings({}).data_root)
    r = seed(root, a.company, a.name)
    print(f"{a.name} ({a.company}): company {'created' if r['company_created'] else 'already there'}, accounts created {r['accounts_created']}, "
          f"files restored {r['restored']}, modules on: {', '.join(r['modules'])}.")
    print(f"Sign-in details are in: {root / '_control' / 'seed_credentials.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
