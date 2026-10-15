"""Reset one company's 1.0 journey records so the walk can start again: the intents 1.0 made (those with a sow.json), their scan,
design and mapping records, the Loaded confirmations, Flow's staged landing copies and runs, and the glossary terms and catalogue
baselines the signatures wrote. Company data (landing files, documents, warehouse marts) stays. Synthetic companies only."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.graph.hooks import mark_dirty  # noqa: E402
from sh_platform.jsonfile import write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402


def reset(plane) -> dict:
    out = {"intents": 0, "records": 0, "staged": 0, "runs": 0, "baselines": 0}
    from sh_platform.v1.i4_sow import baseline_id_of
    for sow in list(plane.path("intents").glob("ini-*/sow.json")):
        b = plane.path("baseline", baseline_id_of(sow.parent.name))
        if b.is_dir():
            shutil.rmtree(b, ignore_errors=True)
            out["baselines"] += 1
        shutil.rmtree(sow.parent, ignore_errors=True)
        out["intents"] += 1
    for sub in ("scan", "mapping", "design"):
        d = plane.path("build", sub)
        if d.is_dir():
            out["records"] += sum(1 for _ in d.iterdir())
            shutil.rmtree(d, ignore_errors=True)
    for d in (plane.path("projects"), plane.path("build", "verify")):  # round 6: projects, benchmark checks
        if d.is_dir():
            out["records"] += sum(1 for _ in d.iterdir())
            shutil.rmtree(d, ignore_errors=True)
    for name in ("handovers", "tickets", "daily"):  # P5 ledgers; the model cost log is left alone
        f = plane.path("build", "ops", f"{name}.json")
        if f.exists():
            f.unlink()
            out["records"] += 1
    loaded = plane.path("build", "ops", "loaded.json")
    if loaded.exists():
        loaded.unlink()
        out["records"] += 1
    bp = plane.path("build", "blueprint.json")  # Span's draft from a SOW; a signed blueprint is never touched
    if bp.exists() and (json.loads(bp.read_text(encoding="utf-8")) or {}).get("state") != "signed":
        for f in list(plane.path("build").glob("blueprint*.json")):
            f.unlink()
            out["records"] += 1
        arch = plane.path("build", "architecture")
        if arch.is_dir():
            shutil.rmtree(arch, ignore_errors=True)
            out["records"] += 1
    for f in list(plane.path("build", "pipelines").glob("v1-*.json")) + list(plane.path("build", "flow", "runs").glob("*"))             if plane.path("build", "pipelines").is_dir() else []:
        if f.is_file():
            f.unlink()
            out["records"] += 1
    alerts = plane.path("build", "alerts.json")
    if alerts.exists():
        rec = json.loads(alerts.read_text(encoding="utf-8"))
        items = rec if isinstance(rec, list) else rec.get("alerts") or []
        keep = [a for a in items if not str(a.get("source") or "").startswith("v1_")]
        write_json_atomic(alerts, keep if isinstance(rec, list) else {**rec, "alerts": keep})
    for f in plane.path("landing").glob("_b4_*"):
        f.unlink()
        out["staged"] += 1
    runs = plane.path("warehouse", "runs.json")
    if runs.exists():
        rec = json.loads(runs.read_text(encoding="utf-8"))
        keep = [r for r in rec.get("runs") or [] if not str(r.get("source") or "").startswith("v1_")]
        out["runs"] = len(rec.get("runs") or []) - len(keep)
        write_json_atomic(runs, {**rec, "runs": keep})
    for idx in plane.path("intents").glob("_index.json"):  # the 2.0 index of intents, rebuilt on the next read
        idx.unlink()
    import duckdb
    from sh_platform.warehouse import refresh_readonly_copy
    wh = plane.path("warehouse", "company.duckdb")
    if wh.exists():
        con = duckdb.connect(str(wh))
        try:
            for schema, table in con.execute("select table_schema, table_name from information_schema.tables where table_schema in ('gold', 'silver', 'bronze')").fetchall():
                if schema == "bronze" and not table.startswith("v1_"):
                    continue
                con.execute(f'drop table if exists {schema}."{table}"')
                out["marts"] = out.get("marts", 0) + 1
        finally:
            con.close()
        refresh_readonly_copy(plane)
    mark_dirty(plane)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("company", nargs="?", default="neera")
    ap.add_argument("--data-root", default=None)
    a = ap.parse_args(argv)
    root = Path(a.data_root) if a.data_root else Path(load_settings({}).data_root)
    plane = PlaneStore(root).plane_for(a.company)
    r = reset(plane)
    print(f"{a.company}: removed {r['intents']} intents, {r['records']} build records, {r['staged']} staged files, {r['runs']} runs, "
          f"{r['baselines']} signed baselines, {r.get('marts', 0)} warehouse tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
