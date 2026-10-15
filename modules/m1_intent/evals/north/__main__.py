"""python -m modules.m1_intent.evals.north [--live]   (stub by default; no network)."""
import os
import sys
import tempfile
from pathlib import Path

from modules.m1_intent.evals.north.cases import run_all
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.plane import PlaneStore


def main(argv: list[str]) -> int:
    live = "--live" in argv
    model_for = None
    if live:
        root = Path(tempfile.mkdtemp(prefix="sh_north_eval_"))  # a throwaway plane: the vault and the log live here
        plane = PlaneStore(root).create("eval-co")
        try:
            client = build_model_client(plane, os.environ)
        except ProviderError as e:
            sys.stderr.write(f"{e}\n")
            return 2
        if client is None:
            sys.stderr.write("A live run needs GOOGLE_API_KEY or OPENROUTER_API_KEY to be set up (names only; values are never shown).\n")
            return 2
        model_for = lambda: client  # noqa: E731
    results = run_all(model_for, live=live)
    for cid, ok, why in results:
        sys.stdout.write(f"{'ok  ' if ok else 'FAIL'} {cid} {'; '.join(why)}\n")
    failed = sum(not ok for _, ok, _ in results)
    sys.stdout.write(f"{len(results) - failed} passed, {failed} failed of {len(results)}\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
