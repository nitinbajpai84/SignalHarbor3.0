"""Team of ten: make a fresh synthetic Evergreen office for the persona runs.

    sh py.sh v3_team_env.py <root> [--today 2026-10-09]      (use --today 2026-07-31 for the UC6 / cfo runs)
    sh py.sh v3_team_env.py <root> --data office6m [--today 2026-10-13] [--flat]   (the six-month Evergreen Office, see below)

1. runs make_clean_env.py (clean master data, no ten-use-case history) with the given company clock,
2. adds Tom Hale, Priya Nair and Sam Lee (AccountStore.create; passwords only in <root>/_control/seed_credentials.txt, same format),
3. writes <root>/evergreen/v3/settings.json "jobs": {email: role_id} from packs/family_office/1/role_builds.yaml.
Refuses the repo data/ folder. Nothing secret is printed.

--data office6m (default clock 2026-10-13) then also loads tests/v1/fixtures/office6m (made by `python -m tools.gen_office6m`):
4. copies every file that has arrived by --today (month folders up to that month; daily files dated after --today are left out) and the reference/ folder
   to <root>/evergreen/dropbox/office6m/<YYYY-MM>/<kind>/... (with --flat: straight into <root>/evergreen/dropbox/),
5. puts the answer keys and the manifest in <root>/_control/office6m/ (outside the dropbox on purpose: the product must not read them),
6. writes <root>/evergreen/office6m_loaded.json (today, months, file count). Run the generator first if the fixtures folder is missing.
The platform master data stays the clean ten-use-case Evergreen master data (entities, portfolios, funds A to E); funds F, G, K, the 12 bank accounts and the
commitments are in reference/master_data.json for the intake to read.
"""
import re
import shutil
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


OFFICE6M = ROOT / "tests" / "v1" / "fixtures" / "office6m"


def load_office6m(root: Path, today: str, flat: bool = False) -> dict:
    """Drop the office6m files that have arrived by `today` into the dropbox (see the module docstring)."""
    if not (OFFICE6M / "MANIFEST.md").is_file():
        raise SystemExit(f"{OFFICE6M} is missing: run `python -m tools.gen_office6m` first")
    box = root / "evergreen" / "dropbox"
    box = box if flat else box / "office6m"
    day = today.replace("-", "")
    months, n = [], 0
    for src in sorted(OFFICE6M.rglob("*")):
        if not src.is_file() or src.name in {"MANIFEST.md", "answer_keys.yaml", ".office6m"}:
            continue
        rel = src.relative_to(OFFICE6M)
        top = rel.parts[0]
        if re.fullmatch(r"\d{4}-\d{2}", top):
            if top > today[:7]:
                continue
            m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", src.stem)
            if m and "".join(m.groups()) > day:
                continue
            if top not in months:
                months.append(top)
        dst = box / (src.name if flat else rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        n += 1
    ctl = root / "_control" / "office6m"
    ctl.mkdir(parents=True, exist_ok=True)
    for f in ("MANIFEST.md", "answer_keys.yaml"):
        shutil.copyfile(OFFICE6M / f, ctl / f)
    info = {"today": today, "months": months, "files": n, "dropbox": str(box), "flat": flat}
    (root / "evergreen" / "office6m_loaded.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--today", default=None)
    ap.add_argument("--data", choices=("10uc", "office6m"), default="10uc", help="office6m also loads the six-month Evergreen Office files")
    ap.add_argument("--flat", action="store_true", help="office6m: copy all files straight into the dropbox, no sub-folders")
    a = ap.parse_args()
    a.today = a.today or ("2026-10-13" if a.data == "office6m" else "2026-10-09")
    root = Path(a.root).resolve()
    if root == (ROOT / "data").resolve():
        raise SystemExit("refusing the repo data/ folder")
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("make_clean_env.py")), "--root", str(root), "--today", a.today],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit("make_clean_env failed:\n" + (r.stderr or r.stdout)[-1500:])
    made = add_people(root)
    jobs = save_jobs(root)
    out = {"root": str(root), "today": a.today, "new_accounts": made, "jobs": len(jobs), "credentials": str(root / "_control" / "seed_credentials.txt")}
    if a.data == "office6m":
        out["office6m"] = load_office6m(root, a.today, a.flat)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
