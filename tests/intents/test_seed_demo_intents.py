"""F15 (R13): the demo seed carries no recorded moment after now. Planned dates (time-box ends, deadlines, review dates) may lie ahead."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.entitlements import EntitlementStore  # noqa: E402
from tools import seed_demo_intents as D  # noqa: E402

RECORDED = ("closed_at", "signed_at", "updated_at", "created_at", "opened_at", "submitted_at", "noticed_at", "raised_at", "done_at", "at",
            "confirmed_at", "closing_at", "drafted_at", "owner_accepted_at", "session_at", "picked_up_at", "reminded_at")


def _walk(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in RECORDED and isinstance(v, str) and v[:2] == "20":
                out.append((path + "/" + k, v))
            _walk(v, path + "/" + k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", out)


def test_no_recorded_moment_after_today(tmp_path):
    EntitlementStore(tmp_path).create_company("ardmore", "Illustrative Ardmore", "family_office", modules=["m1_intent"])
    D.seed(tmp_path)
    now, late = datetime.now(timezone.utc).isoformat(), []
    for f in tmp_path.rglob("*"):
        if f.suffix not in (".json", ".jsonl") or "_control" in f.parts:
            continue
        docs = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.suffix == ".jsonl" else [json.loads(f.read_text(encoding="utf-8"))]
        found = []
        for d in docs:
            _walk(d, "", found)
        late += [(f.name, p, v) for p, v in found if datetime.fromisoformat(v if "T" in v else v + "T00:00:00+00:00").isoformat() > now]
    assert not late, late[:10]
