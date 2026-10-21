"""Print accuracy by round: python tools/accuracy_report.py [live-folder]  (default: SH3_LIVE_DIR, else D:/Temp/sh3-live)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sh_platform.v1 import v3_accuracy as A  # noqa: E402

rows = A.rounds(None, sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SH3_LIVE_DIR") or "D:/Temp/sh3-live")
print(f"{'round':<8}{'answers':>8}{'right':>7}{'right %':>9}{'slipped':>9}{'corrected':>10}")
for r in rows:
    print(f"{r['round']:<8}{r['total']:>8}{r['right']:>7}{r['right_pct']:>9}{r['slipped']:>9}{r['corrected']:>10}")
