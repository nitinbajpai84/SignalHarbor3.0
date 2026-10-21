"""Copy a data root into Postgres, one table per store kind. Safe to run again: a document already in Postgres is never overwritten,
because once the app runs in production mode Postgres holds the live copy and the files on the volume are only the first load.

    python tools/migrate_to_postgres.py <data_root> [--database-url URL] [--dry-run]

DATABASE_URL is read from the environment when --database-url is not given (the value is never printed). Only .json documents move
(kind = the area folder, key = "<company>/<path in the area>", the same scheme and the same rule for what is a state document as
sh_platform/state/routing.py, which the running app reads through). Everything else (DuckDB warehouse, uploaded and dropped files,
.jsonl logs, markdown) stays on the volume and is counted as "kept on disk". The source is never changed or deleted.
--refresh overwrites documents that differ (use it to reload a restored volume, never on a live system).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sh_platform.state import Conflict, PgStore  # noqa: E402
from sh_platform.state.routing import key_of_parts  # noqa: E402

KIND = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


def migrate(root, store, dry_run: bool = False, refresh: bool = False) -> dict:
    """Copy every company/<area>/**/*.json of `root` into `store`. Returns counts and the lists of files that could not be read."""
    root = Path(root)
    out = {"copied": 0, "unchanged": 0, "kept_on_disk": 0, "unreadable": [], "bad_area": [], "companies": 0}
    for company in sorted(d for d in root.iterdir() if d.is_dir()) if root.is_dir() else []:
        out["companies"] += 1
        for f in sorted(p for p in company.rglob("*") if p.is_file()):
            rel = f.relative_to(company)
            if f.suffix == ".json" and ".tmp" not in f.name and len(rel.parts) >= 2 and not KIND.match(rel.parts[0]):
                out["bad_area"].append(f"{company.name}/{rel.parts[0]}")
                continue
            ck = key_of_parts([company.name, *rel.parts])  # the app's own rule for what is a state document
            if ck is None:  # logs, uploads, the warehouse, raw files that happen to end in .json
                out["kept_on_disk"] += 1
                continue
            area, key = ck
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                out["unreadable"].append(f"{company.name}/{rel.as_posix()}")
                continue
            have, ver = store.get(area, key)
            if ver != "0" and (have == doc or not refresh):
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
    ap.add_argument("--refresh", action="store_true", help="overwrite documents already in Postgres that differ")
    a = ap.parse_args(argv)
    url = a.database_url or os.environ.get("DATABASE_URL")
    if not url:
        print("Give --database-url or set DATABASE_URL.")
        return 2
    res = migrate(a.data_root, PgStore(url), a.dry_run, a.refresh)
    print(("DRY RUN " if a.dry_run else "") + f"{res['companies']} companies: {res['copied']} copied, {res['unchanged']} unchanged, "
          f"{res['kept_on_disk']} kept on disk, {len(res['unreadable'])} unreadable, {len(res['bad_area'])} area names skipped")
    for x in res["unreadable"] + res["bad_area"]:
        print("  not copied:", x)
    return 1 if res["unreadable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
