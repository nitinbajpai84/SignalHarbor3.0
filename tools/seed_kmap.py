"""Seed a six-month Evergreen office env so the Knowledge map is rich without live builds (synthetic data only).

    python tools/seed_kmap.py D:/Temp/sh3-kmap-env      (the env from docs/test/uc-live/uc6-scripts/v3_team_env.py <root> --data office6m --flat)

Loads the office6m files with the pack readers, registers the dropbox files as read, signs four use cases (briefs) and gives each figure a figure record built from a
pack recipe (one has a newer version held), then fires the pack signals once. Idempotent on the figure records and threads; the signals fire once per subject.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import v3_figstore as FS, v3_harbor as H, v3_pack_readers as PR, v3_recipes as R, v3_signals as SG, wh  # noqa: E402

FIXTURE = ROOT / "tests" / "v1" / "fixtures" / "office6m"
TODAY = "2026-10-13"
MASTER = {"instruments", "portfolios", "legal_entities", "bank_accounts"}
CASES = [  # title, started and signed by, readers, [recipe ids], what it asks
    ("Cash across the entities", "Daniel Foo", ["Raj Patel", "Mei Chen"], ["cash_by_entity", "cash_break", "cash_by_bank"], "Where is our cash, and does it agree with the bank?"),
    ("Capital calls", "Daniel Foo", ["Raj Patel", "Grace Ong"], ["called_to_date", "calls_due", "cash_after_calls"], "Which calls are due and can each entity fund them?"),
    ("Net worth and limits", "Raj Patel", ["Mei Chen", "Sofia Reyes"], ["net_worth", "concentration", "single_name_breach"], "What are we worth, and is any holding over its limit?"),
    ("Statements on time", "Anita Rao", ["Grace Ong", "Helen Foo"], ["missing_statements", "statement_timeliness", "amendments_open"], "Which manager statements are late or amended?"),
]


def files(plane) -> int:
    """Register every dropbox file the pack readers know as read, with its source, as the intake does."""
    out = []
    for p in sorted(plane.path("dropbox").iterdir()):
        r = PR.recognise(plane, p.name)
        if r:
            out.append({"name": p.name, "arrived_at": (PR._name_day(p.name) or __import__("datetime").date(2026, 10, 1)).isoformat() + "T06:00:00Z",
                        "status": "loaded", "source": PR.KINDS[r[0]][0], "thread": None})
    H._fp(plane).parent.mkdir(parents=True, exist_ok=True)
    H._fp(plane).write_text(json.dumps(out), encoding="utf-8")
    return len(out)


def cases(plane) -> None:
    for i, (title, by, readers, rids, ask) in enumerate(CASES):
        tid, iid, day = f"th-kmap-{i + 1}", f"int-kmap-{i + 1}", f"2026-10-0{i + 2}T06:00:00Z"
        recs = [R.recipe(r) for r in rids]
        srcs = sorted({PR.KINDS[k][0] for r in recs for t in r.get("may_read") or [] if t not in MASTER for k, v in PR.KINDS.items() if t.replace("_", " ") in v[2]})
        sow = {"state": "signed", "goal": {"line": ask, "readers": readers, "decisions": [f"Act on {title.lower()}"]},
               "kpis": [{"name": r["label"], "definition": r.get("why", "")[:200]} for r in recs], "sources": [{"name": s, "holds": s} for s in srcs]}
        d = plane.path("intents", iid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "sow.json").write_text(json.dumps(sow), encoding="utf-8")
        H.save(plane, {"id": tid, "title": title, "stage": "live", "created": day, "iid": iid, "pid": f"EV-{i + 10:04d}", "events": [{"at": "2026-10-13T06:00:00Z", "kind": "harbor"}],
                       "steps": [], "started_by": by, "sources": srcs, "record": {"signed_by": by, "role": "owner", "signed_at": day}, "exceptions": []})
        for j, r in enumerate(recs):
            name = r["label"]
            reads = sorted(t for t in r.get("may_read") or [] if t not in MASTER)
            vs = [{"v": 1, "status": "verified", "built_from": {"kind": "recipe", "id": r["id"]}, "reads": reads, "sql_hash": "x", "runs": [{"at": "2026-10-0%dT06:00:00Z" % (i + 2), "ok": True}],
                   "tie_out": {"rule": r.get("tie_out", {}).get("label") or "Adds up to the source", "ok": True, "at": day}, "at": day}]
            if r["id"] == "single_name_breach":
                vs += [{"v": 2, "status": "held", "reason": "The new version did not add up to the signed limit rule", "built_from": {"kind": "recipe", "id": r["id"]}, "reads": reads,
                        "runs": [], "tie_out": {"rule": "Adds up to the signed limit rule", "ok": False, "at": "2026-10-12T06:00:00Z"}, "at": "2026-10-12T06:00:00Z"}]
            rec = FS.read(plane, FS.fid(name)) or {"id": FS.fid(name), "name": name, "definition": r.get("why", "")[:200], "grain": [], "versions": vs, "current_v": 1, "used_by": []}
            if not any(u["thread"] == tid for u in rec["used_by"]):
                rec["used_by"].append({"thread": tid, "brief": title, "person": by})
            FS._save(plane, rec)
    # one figure is shared by two use cases
    rec = FS.read(plane, FS.fid(R.recipe("cash_by_entity")["label"]))
    if not any(u["thread"] == "th-kmap-2" for u in rec["used_by"]):
        rec["used_by"].append({"thread": "th-kmap-2", "brief": "Capital calls", "person": "Daniel Foo"})
        FS._save(plane, rec)


def fire(plane) -> int:
    """Fire the pack signals once, on the events the office has had: each capital call notice as it arrived (the call arrives; one notice disagrees with itself)
    and every run chain. The notice reader does not read a currency or a table total, so those two fields are added here, as the PDF loader's layout would."""
    with wh.connect(plane) as con:
        docs = con.execute("select id, original_filename from documents where document_type = 'capital_call_notice' order by document_date").fetchall()
        for n, (did, name) in enumerate(docs):
            vals = {fn: {"value": vt if vt is not None else float(vn), "page": pg, "quote": f"{fn} {vt if vt is not None else vn}"} for fn, vt, vn, pg in con.execute(
                "select field_name, value_text, value_numeric, page_number from extracted_fields where document_id = ?", [did]).fetchall()}
            vals["currency"] = {"value": "USD", "page": 1, "quote": "Amounts in USD"}
            vals["amount_in_table"] = {"value": vals["amount"]["value"] + (10000 if n == 3 else 0), "page": 2, "quote": "Total due"}
            SG.on_document(plane, name or str(did), "capital_call_notice", vals)
    for chain in "BCM":
        SG.on_run(plane, chain, "th-kmap-1")
    return len(SG.fired(plane))


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    plane = PlaneStore(root).plane_for("evergreen")
    wh.reset_cache()
    rep = PR.load_plane(plane, FIXTURE, TODAY)
    print("loaded kinds:", len(rep), "files registered:", files(plane))
    cases(plane)
    print("signals fired:", fire(plane))


if __name__ == "__main__":
    main()
