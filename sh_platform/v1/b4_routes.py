"""B4 Flow loads: POST /api/v1/build/{iid}/load runs every source of the intent's mapping sheet; GET /api/v1/build/{iid}/runs reads them
back with Flow's note per run. Contracts and loading: b4_load.py."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from sh_platform.build import runner
from sh_platform.build.agents import flow
from sh_platform.build.agents.runtime import runtime_for_plane
from sh_platform.v1 import b4_load as L

log = logging.getLogger(__name__)
router = APIRouter()
NO_SHEET = "There is no mapping sheet for this intent yet. Span writes it once the scope is agreed."


def _post(plane, iid: str, kind: str, text: str, refs: list[dict]) -> None:
    """A note in the intent's room; a missing or broken room never breaks a load."""
    try:
        from sh_platform.v1.room import post
        post(plane, iid, "flow", kind, text, to=["people"], refs=refs)
    except Exception as e:  # noqa: BLE001 - the room is another card's; the load stands without it
        log.warning("room post skipped (%s)", type(e).__name__)


def _fixed(note: dict | None, run: dict) -> dict | None:
    if note and note.get("first_missing_link") == "contract":
        # ponytail: flow.run_lines knows only the blueprint's contracts; this one is the mapping sheet's. Drop when run_lines accepts v1_ sources.
        lines = [x for x in note["lines"][1:] if "no contract" not in x]
        note = {**note, "first_missing_link": None, "lines": [f"{run['source'].removeprefix(L.PREFIX)} {run['status']}."] + lines}
    return note


def _sheet(plane, iid: str) -> list[dict]:
    if not L.IID.fullmatch(iid) or not L.mapping(plane, iid):
        raise HTTPException(404, NO_SHEET)
    return L.contracts_for(plane, iid)[0]


@router.post("/api/v1/build/{iid}/load")
def post_load(request: Request, iid: str):
    plane, viewer = runner._company(request)
    cs = _sheet(plane, iid)
    rt = runtime_for_plane(plane, viewer)
    done, missing = [], []
    for c in cs:
        try:
            run = L.load(plane, c)
        except (FileNotFoundError, runner.Blocked) as e:
            missing.append({"source": c["source"], "title": c["title"], "reason": str(e)})
            _post(plane, iid, "note", f"{c['title']}: {e}", [{"kind": "mapping", "id": iid}])
            continue
        except (ValueError, OSError) as e:  # a file that will not load; the message holds no row
            missing.append({"source": c["source"], "title": c["title"], "reason": str(e)})
            _post(plane, iid, "note", f"{c['title']} could not be loaded: {e}", [{"kind": "mapping", "id": iid}])
            continue
        note = _fixed(flow.explain_run(plane, run["id"], rt), run)
        if run["status"] == "failed":
            _post(plane, iid, "note", f"{c['title']} failed. " + " ".join((note or {}).get("lines", [])[1:4]),
                  [{"kind": "run", "id": run["id"]}])
        done.append({**run, "title": c["title"], "note": note})
    from sh_platform.v1 import b4_formula
    formulas = b4_formula.build(plane, iid, rt)  # the gold tables whose value is a formula: Flow's checked SQL, or an unclear row
    for f in formulas:
        if f["built"]:
            _post(plane, iid, "note", f"Flow built gold.{f['table']} ({f['code']}) from its own SQL: {f.get('note') or 'see the mapping row'}. "
                  "The data engineer should read the SQL on the mapping row.", [{"kind": "mapping", "id": iid}])
        else:
            _post(plane, iid, "note", f"Flow could not build gold.{f['table']} ({f['code']}): {f.get('why')}", [{"kind": "mapping", "id": iid}])
    try:  # P4: each gold figure against its benchmark; a miss becomes a comment to the raiser and the sponsor
        from sh_platform.v1 import p4_benchmarks
        benchmarks = p4_benchmarks.verify(plane, iid)
    except Exception as e:  # noqa: BLE001 - a failed check never fails the load; the record says nothing new
        log.warning("benchmark check skipped (%s)", type(e).__name__)
        benchmarks = []
    left = L.contracts_for(plane, iid)[1]
    return {"intent_id": iid, "runs": done, "missing": missing, "rows_left_out": left, "formulas": formulas, "benchmarks": benchmarks}


@router.get("/api/v1/build/{iid}/runs")
def get_runs(request: Request, iid: str):
    plane, viewer = runner._company(request)
    cs = _sheet(plane, iid)
    titles = {c["source"]: c["title"] for c in cs}
    runs = [r for r in reversed(runner.read_runs(plane)) if r.get("source") in titles]  # newest first
    runs = runner._mask_runs(plane, viewer, runs)
    return {"intent_id": iid,
            "contracts": [{k: v for k, v in c.items() if k not in ("fields_of", "gold")} for c in cs],
            "runs": [{**r, "title": titles[r["source"]], "note": _fixed(flow.read_note(plane, r["id"]), r)} for r in runs]}
