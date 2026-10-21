"""W7 restore test: decrypt a backup into a temp folder and prove it is whole.

  python tools/restore_test.py D:/backups/wah-hin-20261021T031500Z.shbk --key-env SH_BACKUP_KEY

Checks, then deletes the temp folder: every file's sha256 equals the manifest written at backup time, no file is missing or extra,
and every figure record (v3/figures/*.json) reads back as JSON with the digest it had. Exit 0 only if all hold.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import backup as B  # noqa: E402


def restore_to(archive: Path, passphrase: str, dest: Path) -> dict:
    raw = archive.read_bytes()
    if not raw.startswith(B.MAGIC):
        raise ValueError("not a Signal Harbor backup")
    from cryptography.fernet import Fernet, InvalidToken
    salt, token = raw[5:21], raw[21:]
    try:
        plain = Fernet(B.derive(passphrase, salt)).decrypt(token)
    except InvalidToken:
        raise ValueError("wrong passphrase, or the backup was changed") from None
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    return json.loads((dest / "_manifest.json").read_text(encoding="utf-8"))


def check(dest: Path, man: dict) -> list[str]:
    problems = [f"not backed up: {r}" for r in man.get('skipped', [])]
    got = B.manifest_of(dest / "plane")
    for rel, h in man["files"].items():
        if rel not in got["files"]:
            problems.append(f"missing: {rel}")
        elif got["files"][rel] != h:
            problems.append(f"changed: {rel}")
    problems += [f"extra: {r}" for r in got["files"] if r not in man["files"]]
    for fid, h in man["figures"].items():
        f = dest / "plane" / "v3" / "figures" / f"{fid}.json"
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            problems.append(f"figure unreadable: {fid}")
        if got["figures"].get(fid) != h:
            problems.append(f"figure differs: {fid}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archive")
    ap.add_argument("--key-env", required=True)
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="sh-restore-") as d:
        try:
            man = restore_to(Path(a.archive), B.passphrase_from(a.key_env), Path(d))
        except ValueError as e:
            print("RESTORE FAILED:", e)
            return 1
        bad = check(Path(d), man)
    print(f"files {len(man['files'])}, figures {len(man['figures'])}, skipped at backup {len(man['skipped'])}")
    print("RESTORE OK: the figures match" if not bad else "RESTORE FAILED:\n  " + "\n  ".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
