"""E6c shadow-mode replay: load past periods in received order with the clock set to each file's historical receipt,
run recons and revision impacts, write two CSVs for a reviewer.

    python tools/shadow_run.py <company> <spec.json> [--out report.csv] [--data-root data] [--allow-live]

spec.json: {"periods": [{"name": "2026-08", "cutoff": "2026-09-05", "files": [{"path": "a.xlsx", "received_at": "2026-09-02T09:00:00+00:00"}]}]}
Default replays into a COPY of the company in a temp folder (deleted afterwards); `--allow-live` replays into the company itself (it appends rows there).
Report <out>: one row per finding (time from receipt, case, blank false_alert column for the reviewer).
Report <out stem>_reproducible.csv: per period cutoff, the figures fingerprint at the end of the period vs after all periods.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import shutil
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile.view import Viewer  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402

log = logging.getLogger("shadow_run")
RECONS = ("cash_by_entity", "nav_vs_investment")
FIGURE_TABLES = ("valuation_observations", "position_snapshots", "nav_snapshots")
VIEWER = Viewer("Shadow replay", frozenset({"company_admin"}), False, "acc-shadow")


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class ReplayClock:
    """wh.now() while replaying: the file's receipt time plus the real seconds spent since,
    so receipt-to-finding is machine time. This is the replay flag; it is always restored."""

    def __init__(self):
        self._orig = wh.now

    def set(self, receipt: datetime) -> None:
        t0 = time.monotonic()
        wh.now = lambda: receipt + timedelta(seconds=time.monotonic() - t0)

    def restore(self) -> None:
        wh.now = self._orig


def _ids(plane, table: str) -> set[str]:
    with wh.connect(plane, read_only=True) as con:
        return {str(r[0]) for r in con.execute(f"select id from {table}").fetchall()}  # one warehouse file per company


def _exceptions(plane, ids: set[str]) -> list[dict]:
    if not ids:
        return []
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute(f"select id, exception_type, title, detected_at from exceptions where id in ({','.join('?' * len(ids))}) order by detected_at", list(ids))
        return [dict(zip(("id", "exception_type", "title", "detected_at"), r)) for r in cur.fetchall()]


def default_loader(plane, path: Path, viewer) -> str:
    """Drop the file in the inbox, register it with the landing scan, load it with the landing load. Returns the file's state."""
    try:
        from sh_platform.v1 import e0c_landing
    except ImportError:
        log.warning("E0c landing not built; cannot replay files")
        raise
    inbox = plane.path("landing", "inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, inbox / path.name)
    e0c_landing.scan_inbox(plane)  # registers what is new; a file with the same bytes is already known
    rec = e0c_landing.by_hash(plane, hashlib.sha256(path.read_bytes()).hexdigest())
    if rec is None:
        raise RuntimeError(f"{path.name} was not registered by the landing scan")
    return e0c_landing.load(plane, rec["file_id"], viewer).get("state", "")


def default_recon(plane, code: str, as_of: date, cutoff: datetime):
    from sh_platform.v1 import e3_recon
    return e3_recon.run(plane, code, as_of, cutoff=cutoff)


def default_impact(plane, valuation_id: str):
    from sh_platform.v1 import e3_impact
    return e3_impact.on_new_valuation(plane, valuation_id)


def fingerprint(plane, cutoff) -> dict[str, tuple[int, str]]:
    from sh_platform.v1 import e1_asof
    out = {}
    for t in FIGURE_TABLES:
        rows = e1_asof.snapshot(plane, t, {}, cutoff)
        body = "|".join(sorted(f"{r['id']}:{r.get('value_amount', r.get('amount', ''))}" for r in rows))
        out[t] = (len(rows), hashlib.sha256(body.encode()).hexdigest()[:16])
    return out


def _superseding(plane, ids: set[str]) -> list[str]:
    if not ids:
        return []
    with wh.connect(plane, read_only=True) as con:
        q = f"select id from valuation_observations where supersedes_valuation_id is not null and id in ({','.join('?' * len(ids))}) order by id"
        return [str(r[0]) for r in con.execute(q, list(ids)).fetchall()]


def replay(plane, spec: dict, viewer=VIEWER, loader=default_loader, recon=default_recon, impact=default_impact,
           recons=RECONS, base: Path = Path(".")) -> dict:
    clock, findings, repro = ReplayClock(), [], []
    try:
        for period in spec["periods"]:
            for f in sorted(period["files"], key=lambda f: _dt(f["received_at"])):
                receipt = _dt(f["received_at"])
                clock.set(receipt)
                before_exc, before_val = _ids(plane, "exceptions"), _ids(plane, "valuation_observations")
                state = loader(plane, base / f["path"], viewer)  # an absolute path ignores base
                for vid in _superseding(plane, _ids(plane, "valuation_observations") - before_val):
                    impact(plane, vid)
                for code in recons:
                    recon(plane, code, receipt.date(), receipt)
                for e in _exceptions(plane, _ids(plane, "exceptions") - before_exc):
                    findings.append({"period": period["name"], "file": Path(f["path"]).name, "load_state": state, "received_at": receipt.isoformat(),
                                     "finding_id": str(e["id"]), "kind": e["exception_type"], "title": e["title"], "case_opened": "yes",
                                     "seconds_to_finding": round((e["detected_at"] - receipt).total_seconds(), 3), "false_alert": ""})
            c = period["cutoff"]
            cutoff = _dt(c) if "T" in c else _dt(c + "T23:59:59+00:00")
            repro.append({"period": period["name"], "cutoff": cutoff, "at_end": fingerprint(plane, cutoff)})
    finally:
        clock.restore()
    for r in repro:  # the same cutoff asked again after every later period has loaded
        r["again"] = fingerprint(plane, r["cutoff"])
        r["reproducible"] = r["again"] == r["at_end"]
    return {"findings": findings, "reproducible": repro}


def write_reports(result: dict, out: Path) -> tuple[Path, Path]:
    cols = ["period", "file", "load_state", "received_at", "finding_id", "kind", "title", "case_opened", "seconds_to_finding", "false_alert"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        w.writerows(result["findings"])
    rep = out.with_name(out.stem + "_reproducible.csv")
    with rep.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["period", "cutoff", "table", "rows_at_period_end", "rows_now", "fingerprint_at_period_end", "fingerprint_now", "reproducible"])
        for r in result["reproducible"]:
            for t, (n, h) in r["at_end"].items():
                n2, h2 = r["again"][t]
                w.writerow([r["period"], r["cutoff"].isoformat(), t, n, n2, h, h2, "yes" if (n, h) == (n2, h2) else "NO"])
    return out, rep


def working_copy(data_root: Path, company: str, allow_live: bool = False):
    """(plane, cleanup): the company copied to a temp folder, or the company itself with allow_live. An unknown company starts empty."""
    store = PlaneStore(data_root)
    if allow_live:
        return (store.plane_for(company) if store.exists(company) else store.create(company)), lambda: None
    tmp = tempfile.mkdtemp(prefix="sh_shadow_")
    if store.exists(company):
        shutil.copytree(store.plane_for(company).root, Path(tmp) / company)
        plane = PlaneStore(tmp).plane_for(company)
    else:
        plane = PlaneStore(tmp).create(company)
    return plane, lambda: shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company")
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, default=Path("shadow_report.csv"))
    ap.add_argument("--data-root", type=Path, default=ROOT / "data")
    ap.add_argument("--allow-live", action="store_true", help="replay into the company itself, not a temp copy")
    a = ap.parse_args(argv)
    plane, cleanup = working_copy(a.data_root, a.company, a.allow_live)
    try:
        spec = json.loads(a.spec.read_text(encoding="utf-8"))
        res = replay(plane, spec, base=a.spec.resolve().parent)
    finally:
        cleanup()
    out, rep = write_reports(res, a.out)
    bad = [r["period"] for r in res["reproducible"] if not r["reproducible"]]
    print(f"{len(res['findings'])} findings in {out}; reproducibility in {rep}; not reproducible: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
