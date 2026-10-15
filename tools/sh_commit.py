"""Signal Harbor commit gate: the only way a work package lands.

Refuses to commit unless the package has a builder report, an independent PASS review
(reviewer id != builder id), every staged path is inside the package's OWNS globs
(plus docs/signal-harbor/history/nira-platform/ and evidence/history/nira-platform/), and
no staged content matches a secret pattern or touches a protected path. After committing
it tags the package, writes the graft blast radius and appends the change ledger.

Usage: python tools/sh_commit.py <PACKAGE_ID>
"""
from __future__ import annotations

import fnmatch
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "ledger" / "packages.json"
CHANGELEDGER = ROOT / "docs" / "ledger" / "CHANGELEDGER.md"
ALWAYS_ALLOWED = ("docs/ledger/*",)
PROTECTED = (re.compile(r"(^|/)\.env(\.(?!example$)|$)"), re.compile(r"(^|/)data/"))
SECRETS = (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
           re.compile(r"AIza[0-9A-Za-z_-]{35}"), re.compile(r"xox[bpas]-[A-Za-z0-9-]{10,}"),
           re.compile(r"dapi[0-9a-f]{32}"), re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"))

log = logging.getLogger("sh_commit")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def fail(msg: str) -> None:
    log.error("REFUSED: %s", msg)
    sys.exit(1)


def in_scope(path: str, owns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) or path.startswith(g.rstrip("*").rstrip("/") + "/")
               for g in [*owns, *ALWAYS_ALLOWED])


def main(pkg_id: str) -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    pkg = ledger.get("packages", {}).get(pkg_id)
    if not pkg:
        fail(f"{pkg_id} is not in the ledger")
    builder, reviewer = pkg.get("builder_id"), pkg.get("reviewer_id")
    if not builder or not reviewer:
        fail("builder_id and reviewer_id must both be recorded")
    if builder == reviewer:
        fail("author and reviewer are the same agent")
    if str(pkg.get("verdict", "")).upper() != "PASS":
        fail(f"review verdict is {pkg.get('verdict')!r}, not PASS")
    for key in ("report", "review"):
        if not (ROOT / pkg.get(key, "__missing__")).is_file():
            fail(f"{key} file missing: {pkg.get(key)}")

    changed = [l[3:].strip().strip('"') for l in git("status", "--porcelain", "-uall").splitlines() if l.strip()]
    owns = pkg.get("owns", [])
    paths = [p.replace("\\", "/") for p in changed if in_scope(p.replace("\\", "/"), owns)]
    if not paths:
        fail("no changed files inside the package scope")
    for p in paths:
        if any(r.search(p) for r in PROTECTED):
            fail(f"protected path in package: {p}")
        f = ROOT / p
        if f.is_file() and f.stat().st_size < 2_000_000:
            text = f.read_text(encoding="utf-8", errors="ignore")
            if any(r.search(text) for r in SECRETS):
                fail(f"secret-like content in {p}")

    git("add", "--", *paths)
    stat = git("diff", "--cached", "--stat")
    msg = (f"{pkg_id}: {pkg.get('title', '')}\n\nBuilder: {builder}\n"
           f"Reviewer: {reviewer} verdict PASS\n"
           f"Report: {pkg['report']}\nReview: {pkg['review']}\n")
    git("commit", "-q", "-m", msg)
    sha = git("rev-parse", "--short", "HEAD").strip()
    git("tag", "-f", f"sh/{pkg_id}")

    blast_dir = ROOT / "docs" / "ledger" / pkg_id
    blast_dir.mkdir(parents=True, exist_ok=True)
    blast = subprocess.run("graft blast --base HEAD~1 --format markdown --no-owners", cwd=ROOT, shell=True,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    (blast_dir / "blast.md").write_text(blast.stdout or blast.stderr, encoding="utf-8")

    pkg.update({"state": "landed", "commit": sha, "landed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    with CHANGELEDGER.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {pkg_id} · {pkg.get('title', '')} · `{sha}` · tag `sh/{pkg_id}`\n\n"
                 f"- Phase: {pkg.get('phase')} · builder {builder} · reviewer {reviewer} · verdict PASS\n"
                 f"- Tests: {pkg.get('tests', 'see report')}\n- Blast radius: `docs/signal-harbor/history/nira-platform/packages/{pkg_id}/blast.md`\n\n"
                 f"```\n{stat.strip()}\n```\n")
    log.info("landed %s as %s", pkg_id, sha)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        fail("usage: sh_commit.py <PACKAGE_ID>")
    main(sys.argv[1])
