"""W7 backup: an encrypted, timestamped copy of one company's plane.

  python tools/backup.py --company wah-hin --out D:/backups --key-env SH_BACKUP_KEY [--data-root PATH]

The passphrase is read from the environment variable NAMED by --key-env (never from the command line, never written down).
File: SHBK1 + 16-byte salt + a Fernet token (AES-128-CBC with HMAC-SHA256) of a tar.gz that holds the plane and `_manifest.json`
(sha256 of every file, and a digest of every figure). Key = scrypt(passphrase, salt).
ponytail: the archive is built in memory (fine for office-size planes; stream it if a plane passes a few GB).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAGIC = b"SHBK1"


def derive(passphrase: str, salt: bytes) -> bytes:
    return base64.urlsafe_b64encode(hashlib.scrypt(passphrase.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=2**26))


def passphrase_from(env_name: str) -> str:
    v = os.environ.get(env_name, "")
    if len(v) < 12:
        raise SystemExit(f"Set the environment variable {env_name} to a passphrase of at least 12 characters.")
    return v


def manifest_of(root: Path) -> dict:
    files, figures, skipped = {}, {}, []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            try:
                files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                skipped.append(rel)
    for rel, h in files.items():
        if rel.startswith("v3/figures/") and rel.endswith(".json"):
            figures[Path(rel).stem] = h
    return {"files": files, "figures": figures, "skipped": skipped}


def make_backup(plane_root: Path, out_dir: Path, passphrase: str, company: str) -> Path:
    man = manifest_of(plane_root)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in man["files"]:
            tar.add(plane_root / rel, arcname="plane/" + rel)
        data = json.dumps({"company": company, **man}, indent=1).encode()
        ti = tarfile.TarInfo("_manifest.json")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{company}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.shbk"
    out.write_bytes(MAGIC + salt + Fernet(derive(passphrase, salt)).encrypt(buf.getvalue()))
    if man["skipped"]:
        print("WARNING: could not read", len(man["skipped"]), "file(s):", man["skipped"][:5], file=sys.stderr)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--company", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--key-env", required=True, help="NAME of the environment variable holding the passphrase")
    ap.add_argument("--data-root")
    a = ap.parse_args(argv)
    from sh_platform.plane import PlaneStore
    from sh_platform.settings import load_settings
    plane = PlaneStore(a.data_root or load_settings().data_root).plane_for(a.company)
    out = make_backup(plane.root, Path(a.out), passphrase_from(a.key_env), a.company)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
