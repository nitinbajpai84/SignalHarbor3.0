"""Copy a data root into Postgres, one table per store kind. Safe to run again: a document already there and equal is left alone.

    python tools/migrate_to_postgres.py <data_root> [--database-url URL] [--dry-run]

DATABASE_URL is read from the environment when --database-url is not given (the value is never printed). Only .json documents move
(kind = the area folder, key = "<company>/<path in the area>"). Everything else (DuckDB warehouse, uploaded files, .jsonl logs, markdown)
stays on the volume and is counted as "kept on disk". The source is never changed or deleted.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sh_platform.state import Conflict, PgStore  # noqa: E402

KIND = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


def migrate(root, store, dry_run: bool = False) -> dict:
    """Copy every company/<area>/**/*.json of `root` into `store`. Returns counts and the lists of files that could not be read."""
    root = Path(root)
    out = {"copied": 0, "unchanged": 0, "kept_on_disk": 0, "unreadable": [], "bad_area": [], "companies": 0}
    for company in sorted(d for d in root.iterdir() if d.is_dir()) if root.is_dir() else []:
        out["companies"] += 1
        for f in sorted(p for p in company.rglob("*") if p.is_file()):
            rel = f.relative_to(company)
            if len(rel.parts) < 2:
                out["kept_on_disk"] += 1  # a file at the company folder's top has no area
                continue
            area, inner = rel.parts[0], "/".join(rel.parts[1:])
            if f.suffix != ".json" or ".tmp" in f.name:
                out["kept_on_disk"] += 1
                continue
            if not KIND.match(area):
                out["bad_area"].append(f"{company.name}/{area}")
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                out["unreadable"].append(f"{company.name}/{rel.as_posix()}")
                continue
            key = f"{company.name}/{inner}"
            have, ver = store.get(area, key)
            if ver != "0" and have == doc:
                out["unchanged"] += 1
                continue
            if not dry_run:
                try:
                    store.put(area, key, doc, expected=ver)
                except Conflict:  # someone wrote it between the read and the write: the next run sorts it out
                    out["unreadable"].append(f"{company.name}/{rel.as_posix()} (changed while copying)")
                    continue
            out["copied"] += 1
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_root")
    ap.add_argument("--database-url")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    url = a.database_url or os.environ.get("DATABASE_URL")
    if not url:
        print("Give --database-url or set DATABASE_URL.")
        return 2
    res = migrate(a.data_root, PgStore(url), a.dry_run)
    print(("DRY RUN " if a.dry_run else "") + f"{res['companies']} companies: {res['copied']} copied, {res['unchanged']} unchanged, "
          f"{res['kept_on_disk']} kept on disk, {len(res['unreadable'])} unreadable, {len(res['bad_area'])} area names skipped")
    for x in res["unreadable"] + res["bad_area"]:
        print("  not copied:", x)
    return 1 if res["unreadable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
