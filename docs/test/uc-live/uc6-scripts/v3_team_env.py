"""Team of ten: make a fresh synthetic Evergreen office for the persona runs.

    sh py.sh v3_team_env.py <root> [--today 2026-10-09]      (use --today 2026-07-31 for the UC6 / cfo runs)

1. runs make_clean_env.py (clean master data, no ten-use-case history) with the given company clock,
2. adds Tom Hale, Priya Nair and Sam Lee (AccountStore.create; passwords only in <root>/_control/seed_credentials.txt, same format),
3. writes <root>/evergreen/v3/settings.json "jobs": {email: role_id} from packs/family_office/1/role_builds.yaml.
Refuses the repo data/ folder. Nothing secret is printed.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.jsonfile import lock_for  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import v3_ops  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402
from tools.seed import HEADER, _new_password  # noqa: E402

BUILDS = ROOT / "packs" / "family_office" / "1" / "role_builds.yaml"
NEW = {"Tom Hale": "participant", "Priya Nair": "analyst", "Sam Lee": "analyst"}  # platform roles that may use /api/v3 (Helen Foo is already the seed's family principal account, owner)


def add_people(root: Path) -> int:
    store, lines = AccountStore(root), []
    for name, role in NEW.items():
        email = EG.email_of(name)
        if store.get_by_email(email) is None:
            pw = _new_password()
            store.create(email, pw, name, EG.COMPANY, [role])
            lines.append(f"{email}  {pw}  {role}  {EG.COMPANY}")
    if lines:
        creds = root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def save_jobs(root: Path) -> dict:
    roles = yaml.safe_load(BUILDS.read_text(encoding="utf-8"))["roles"]
    jobs = {EG.email_of(r["person"]): r["id"] for r in roles}
    plane = PlaneStore(root).plane_for(EG.COMPANY).ensure()
    s = v3_ops.settings(plane)
    s["jobs"] = jobs
    v3_ops._save(plane, s)
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--today", default="2026-10-09")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if root == (ROOT / "data").resolve():
        raise SystemExit("refusing the repo data/ folder")
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("make_clean_env.py")), "--root", str(root), "--today", a.today],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit("make_clean_env failed:\n" + (r.stderr or r.stdout)[-1500:])
    made = add_people(root)
    jobs = save_jobs(root)
    print(json.dumps({"root": str(root), "today": a.today, "new_accounts": made, "jobs": len(jobs),
                      "credentials": str(root / "_control" / "seed_credentials.txt")}))


if __name__ == "__main__":
    main()
