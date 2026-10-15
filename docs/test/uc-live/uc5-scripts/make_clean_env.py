"""UC5 run 2: build a clean Evergreen Office environment (company, people, accounts, master data, signed rules) with none of the
ten-use-case history, cases, runs, projects or gold tables.

    python docs/test/uc-live/uc5-scripts/make_clean_env.py .sh-tmp/testenv/uc5-run2/data

Uses only the repo's own seed functions, in this order:
  1. tools/seed_evergreen.seed      company, 7 accounts (passwords -> <root>/_control/seed_credentials.txt), entities, EG-GROWTH/EG-LIQUID/EG-B-OPS,
                                    source systems, 4 base instruments, 5 base rules (and its small 30 Sep story: Fund A/B in EG-GROWTH, cash 8 Oct,
                                    September report - none of it is in a limit-monitored portfolio except one 'Evergreen Liquid Book' position row).
  2. tools/seed_10uc._static        the universe's portfolios (EG-FUNDS ...), funds, securities, identifiers, managers' contacts, the alert window
                                    and the four signed limit rules (as the register holds them: single name 5% from 1 Jan 2026), benchmark definitions.
  3. tools/seed_10uc._owner         Helen Foo (family principal) - so the people list matches the demo.
NOT run: seed_10uc._history/_live/_trades/_checks (13 months of valuations, statements, trades, the 9 Oct cases), _library, _manager_notes,
_process, tools/seed_v3_demo (the demo project, gold tables, dashboards), tools/seed_demo_ready. The demo clock is not pinned (real today).
Refuses an existing root that already has a warehouse.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from sh_platform.plane import PlaneStore  # noqa: E402
from tools import seed_10uc as U  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    assert "testenv" in root.parts and root != (ROOT / "data").resolve(), "use a test root, never data/"
    if (root / "evergreen").exists():
        raise SystemExit(f"{root} already holds a company; delete the folder first for a clean run")
    out = EG.seed(root)
    plane = PlaneStore(root).plane_for(EG.COMPANY).ensure()
    ids, _ = EG.accounts(root)
    out.update(U._static(plane, ids))
    out.update(U._owner(root, plane))
    print(out)


if __name__ == "__main__":
    main()
