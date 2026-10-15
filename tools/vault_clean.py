"""Clean one company's egress name vault of entries the registration rule would not make.

Usage: python tools/vault_clean.py [--data-root PATH] COMPANY_ID
Removes generic words ("Finance", "Market data vendor API", "illustrative"), a person entry that is only a word of
the company's own name ("Lakeside"), a lowercase word ("email"), and a parenthesised suffix ("Mei Tan (illustrative)" becomes "Mei Tan", same
token). Backs the file up next to it first (only when something changes), prints counts only, and is idempotent.
The rule is sh_platform/egress/names.py; real names are never printed.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.egress.names import STOP_WORDS, protected_names  # noqa: E402
from sh_platform.egress.vault import NameVault  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402


def clean(plane) -> dict:
    if not plane.area("context").is_dir():  # not a company plane: refuse, create nothing
        raise LookupError("not a company plane")
    v = NameVault(plane)
    with v._locked():
        entries = v._parse(v._read_raw())
        company_words = {w.casefold() for e in entries.values() if e["kind"] == "company" for w in e["name"].split()}
        out, seen, removed, renamed = {}, set(), 0, 0
        for tok, e in entries.items():
            kind = e["kind"]
            got = protected_names(e["name"], []) if kind == "company" else protected_names("", [e["name"]])
            name = got[0][1] if got else ""
            if kind == "person" and (name.casefold() in company_words or name[:1].islower()):
                name = ""  # a word of the company's own name, or a lowercase word ("email", "via"), is not a person
            if kind == "person" and name and len(name.split()) >= 2 and all(w.casefold() in company_words | STOP_WORDS for w in name.split()) and any(w.casefold() in STOP_WORDS - company_words for w in name.split()):
                name = ""  # a title and a word of the company's own name ("Sponsor Lakeside") is nobody
            if kind == "person" and name and got[0][0] == "company":
                kind, e, renamed = "company", {**e, "kind": "company"}, renamed + 1  # a team or organisation that was registered as a person
            if kind in ("company", "person") and (not name or (kind, name.casefold()) in seen):
                removed += 1
                continue
            if name and name != e["name"]:
                e, renamed = {**e, "name": name}, renamed + 1
            seen.add((kind, e["name"].casefold()))
            out[tok] = e
        if out != entries:
            shutil.copy2(v._path, v._path.with_name(f"{v._path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
            v._save(out)
    return {"before": len(entries), "removed": removed, "renamed": renamed, "after": len(out)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Remove generic words from a company's egress name vault.")
    ap.add_argument("company_id")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    try:
        r = clean(PlaneStore(root).plane_for(args.company_id))
    except (LookupError, ValueError, PermissionError):
        print("That is not a company plane in the data root. Nothing was changed.")
        return 1
    print(f"Vault entries before: {r['before']}, removed: {r['removed']}, renamed: {r['renamed']}, after: {r['after']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
