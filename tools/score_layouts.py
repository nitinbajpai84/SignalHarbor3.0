"""W2: the real model over the 100 synthetic layouts (tests/v1/fixtures/layouts, answer key keys.yaml): field accuracy on layouts it has never seen.

    python tools/score_layouts.py [--types capital_call,nav_statement] [--limit 3] [--workers 4] [--json out.json]

Uses the model the company settings name (.env, router tier of task doc_read), through the egress gateway, exactly as the hook in v3_pdf does.
It costs real tokens (one extraction call per file, a second to classify when no marker matches), so it is not run by the test suite.
Per expected field: right (same value), wrong (another value), missed (not read). A wrong or missed field in a document the reader marked "ok"
went through silently; in a document marked "review" a person would have seen it. Target (PROGRAM-GAPS W2): 95% right or sent to review,
0% wrong and passed silently."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "v1" / "fixtures" / "layouts"
SCHEMAS = ROOT / "packs" / "family_office" / "1" / "doc_schemas"


def score_one(plane, name: str, key: dict) -> dict:
    from sh_platform.v1 import v3_doc_extract as DE
    got = DE.read(plane, name, (FIX / name).read_bytes(), folder=SCHEMAS)
    out = Counter()
    status = got["status"] if got else "unread"
    if got is None:
        out["unread_documents"] = 1
    elif got["doc_type"] != key["doc_type"]:
        out["misclassified"] = 1
    fields = (got or {}).get("fields", {})
    silent = status == "ok"
    for f, want in key["fields"].items():
        have = (fields.get(f) or {}).get("value")
        kind = "right" if have == want else "wrong" if have is not None else "missed"
        out[kind] += 1
        if kind != "right":
            out[kind + ("_silent" if silent else "_reviewed")] += 1
    for f in set(fields) - set(key["fields"]):  # a value for a field the document does not state
        out["wrong"] += 1
        out["wrong_silent" if silent else "wrong_reviewed"] += 1
    return {"file": name, "status": status, "counts": dict(out), "dropped": (got or {}).get("dropped", []),
            "wrong": {f: [fields[f]["value"], key["fields"].get(f)] for f in fields if fields[f]["value"] != key["fields"].get(f)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--types")
    ap.add_argument("--limit", type=int, default=20, help="layouts per type")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json")
    a = ap.parse_args()
    keys = yaml.safe_load((FIX / "keys.yaml").read_text(encoding="utf-8"))
    want = set(a.types.split(",")) if a.types else None
    names = [n for n, k in sorted(keys.items()) if (want is None or k["doc_type"] in want) and k["layout"] < a.limit]
    from sh_platform.plane import PlaneStore
    with tempfile.TemporaryDirectory() as tmp:
        plane = PlaneStore(tmp).plane_for("scoring")
        with ThreadPoolExecutor(a.workers) as ex:
            rows = list(ex.map(lambda n: score_one(plane, n, keys[n]), names))
    tot, by_type = Counter(), {}
    for r in rows:
        tot.update(r["counts"])
        by_type.setdefault(keys[r["file"]]["doc_type"], Counter()).update(r["counts"])
    n = tot["right"] + tot["wrong"] + tot["missed"] or 1
    print(f"{len(rows)} documents, {n} expected fields")
    for t, c in {**by_type, "ALL": tot}.items():
        m = (c["right"] + c["wrong"] + c["missed"]) or 1
        print(f"{t:28} right {c['right'] / m:6.1%}  right or reviewed {(c['right'] + c['wrong_reviewed'] + c['missed_reviewed']) / m:6.1%}  "
              f"wrong silent {c['wrong_silent'] / m:5.1%}  missed silent {c['missed_silent'] / m:5.1%}  unread docs {c['unread_documents']}  misclassified {c['misclassified']}")
    scans = [r for r in rows if keys[r["file"]]["scanned"]]
    if scans:
        c = sum((Counter(r["counts"]) for r in scans), Counter())
        m = (c["right"] + c["wrong"] + c["missed"]) or 1
        print(f"{'scanned only':28} right {c['right'] / m:6.1%}  right or reviewed {(c['right'] + c['wrong_reviewed'] + c['missed_reviewed']) / m:6.1%}  wrong silent {c['wrong_silent'] / m:5.1%}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
