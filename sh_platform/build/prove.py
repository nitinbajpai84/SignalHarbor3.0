"""BC-6: the Prover and the release. Recomputes each blueprint measure from the gold mart for every period the company has a reported figure,
compares with the reported figure (docs/plan/SHAPES.md shape 5, build/prove.json). A read never writes: build/prove.json changes only on an
explicit act (a UAT signature, an accepted gap, the release, a re-check with a reason). Only the re-check voids a signature. Figures leave the plane only to a viewer who passes the measure's access list.

Copied from modules/m3_connect (not imported, so the kernel stays under the modules): contracts/trial.yaml `tolerance` and the `none_found`
reason words; domain/from_profile.figures for reading the reported figures (a figure's period is its `period_end` month)."""
import copy
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal

import duckdb
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.build.contracts import slug
from sh_platform.build.uat import _role
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.perf import cached
from sh_platform.profile import store, view
from sh_platform.profile.api import _plane, _viewer
from sh_platform.warehouse import open_readonly

log = logging.getLogger(__name__)
router = APIRouter()
TOL_ABS, TOL_REL = Decimal("0.005"), Decimal("0.001")  # trial.yaml tolerance
DATA_ENDS = "The mart has no figure for {period}; its data ends at {last}."
NONE_FOUND = "No reason found yet. Ask whoever works out the reported figure how they do it."
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _v(item: dict, key: str):
    c = item.get(key)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _reported(plane) -> dict[str, dict[str, tuple[float, str]]]:
    """{measure key: {period 'YYYY-MM': (figure, owner name)}} from the profile's reported figures."""
    out: dict = {}
    for f in store.raw(plane)["reported_figures"].values():
        fig, end, name = _v(f, "figure"), str(_v(f, "period_end") or "")[:7], _v(f, "measure")
        if name and end and isinstance(fig, (int, float)) and not isinstance(fig, bool):
            out.setdefault(view._key(name), {})[end] = (float(fig), str(_v(f, "owner") or ""))
    return out


def _ours(con, mart: str, transform: str, period: str) -> tuple[float | None, str | None]:
    """(figure, last period in the mart). Mart is gold.<table>.<column>; the table has a `period` column ('YYYY-MM')."""
    _, table, col = mart.split(".")
    if not (IDENT.match(table) and IDENT.match(col)):
        raise ValueError("bad mart name")
    for c in dict.fromkeys((col, "value")):  # the column the blueprint names, else the demo tables' `value`
        agg = f"arg_max({c}, period)" if "latest" in transform.lower() else f"sum({c})"
        try:
            v = con.execute(f"select {agg} from gold.{table} where period = ?", [period]).fetchone()[0]
            last = con.execute(f"select max(period) from gold.{table}").fetchone()[0]
        except duckdb.Error:
            continue
        return (None if v is None else float(v)), last
    return None, None


def _of(reported: dict, names: dict, code: str) -> dict:
    """The reported figures of a measure: the profile keys them by the measure's name, older records by its code."""
    return reported.get(view._key(names.get(code) or code)) or reported.get(view._key(code)) or {}


def _compare(ours: float | None, theirs: float) -> tuple[str, str | None]:
    if ours is None:
        return "not_yet", None
    t = Decimal(str(theirs))
    ok = abs(Decimal(str(ours)) - t) <= max(TOL_ABS, TOL_REL * abs(t))
    return ("match", None) if ok else ("gap", NONE_FOUND)


def _ready(periods: list[dict], uat: dict) -> bool:
    return bool(periods) and all(p["result"] == "match" or (p["result"] == "gap" and p["accepted_by"]) for p in periods) and uat.get("state") == "signed"


def _waits(m: dict) -> str | None:
    """What a measure that is not release-ready waits for, in words that finish 'K04 waits for ...'; None when it is ready."""
    if m["release_ready"]:
        return None
    if m.get("changed"):
        return "a re-check, because its result changed after the tester signed it"
    ps = m["periods"]
    if not ps or any(p["result"] == "not_yet" for p in ps):
        return "its figure"
    if any(p["result"] == "gap" and not p["accepted_by"] for p in ps):
        return "an accepted reason for its gap"
    return "the tester's signature"


def _compute(plane) -> dict:
    """The stored prove.json recomputed in memory; never writes. Cached per company until any file of the company changes (no viewer: the
    GET filters per viewer afterwards); each caller gets its own copy."""
    path = plane.path("build", "prove.json")
    return copy.deepcopy(cached(plane, "prove", [plane.root], lambda: _merge(plane, read_json_strict(path, dict) or {})))


def _merge(plane, old: dict) -> dict:
    """`old` (the stored prove.json) with every period recomputed from the mart, in memory. Accepted gaps that still hold, every `uat` and the
    `release` are read as stored. A signed measure whose result has since moved away from a match carries `changed` (those periods) and is not
    release-ready; only an explicit re-check (recheck, a named person with a reason) voids its signature. A move to a match voids nothing."""
    bp = read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    reported, names = _reported(plane), _kpi_names(plane)
    try:
        con = open_readonly(plane)
    except duckdb.Error:
        con = None
    olds = {m["code"]: m for m in old.get("measures", []) if isinstance(m, dict) and m.get("code")}
    measures = []
    first: dict[str, dict] = {}
    for ln in bp.get("lineage", []):  # a measure fed by two sources has two lineage rows and one result
        first.setdefault(ln["measure"], ln)
    try:
        for code, ln in first.items():
            prev = olds.get(code, {})
            kept = {p["period"]: p for p in prev.get("periods") or []}
            periods = []
            for period, (theirs, _owner) in sorted(_of(reported, names, code).items()):
                ours, last = _ours(con, ln["mart"], str(ln.get("transform") or ""), period) if con else (None, None)
                result, reason = _compare(ours, theirs)
                if result == "gap" and last and last < period:
                    reason = DATA_ENDS.format(period=period, last=last)
                old_p = kept.get(period, {})
                acc = old_p.get("accepted_by") if result == "gap" and old_p.get("result") == "gap" else None
                periods.append({"period": period, "ours": ours, "reported": theirs, "result": result,
                                "reason": old_p.get("reason") if acc else reason, "accepted_by": acc})
            uat = prev.get("uat") or {"state": "pending", "by": None, "at": None, "note": None}
            changed = [q["period"] for q in periods if q["period"] in kept and kept[q["period"]].get("result") != q["result"] and q["result"] != "match"]
            m = {"code": code, "periods": periods, "uat": uat, "release_ready": _ready(periods, uat)}
            if changed and uat.get("state") == "signed":
                m["changed"], m["release_ready"] = changed, False
            measures.append(m)
    finally:
        if con:
            con.close()
    return {**old, "band": bp.get("band") or old.get("band"), "measures": measures,
            "release": old.get("release") or {"state": "draft", "by": None, "at": None}}


def settle(plane, old: dict) -> dict:
    """What an explicit act (a UAT signature, an accepted gap, the release) writes back: the fresh periods of every measure, except a signed
    measure whose result changed, which keeps its stored row until someone re-checks. Rows of measures outside the blueprint are kept."""
    doc = _merge(plane, old)
    if not doc["measures"]:  # no blueprint lineage: nothing to recompute
        return old
    olds = {m.get("code"): m for m in old.get("measures", []) if isinstance(m, dict)}
    rows = [olds[m["code"]] if m.pop("changed", None) else m for m in doc["measures"]]
    have = {m["code"] for m in rows}
    doc["measures"] = rows + [m for c, m in olds.items() if c not in have]
    return doc


def recheck(plane, by: str, reason: str) -> dict:
    """The explicit re-check: writes the fresh results, voids the signature of each measure whose result moved away from a match, and adds a
    version line to `checks` (who, when, why, what moved). Nothing moved: nothing written, no line."""
    path = plane.path("build", "prove.json")
    with lock_for(path):
        old = read_json_strict(path, dict) or {}
        doc = settle(plane, old)  # keeps rows outside the blueprint; the changed rows are recomputed below
        fresh = {m["code"]: m for m in _merge(plane, old)["measures"]}
        voided = []
        for i, m in enumerate(doc["measures"]):
            f = fresh.get(m.get("code"))
            if f and f.pop("changed", None):
                voided.append(f["code"])
                f["uat"] = {"state": "pending", "by": None, "at": None, "note": f"result changed; re-checked on {_now()[:10]} by {by}"}
                f["release_ready"] = _ready(f["periods"], f["uat"])
                doc["measures"][i] = f
        if doc == old:
            return doc
        olds = {m.get("code"): m for m in old.get("measures", []) if isinstance(m, dict)}
        moved = [m["code"] for m in doc["measures"] if (olds.get(m["code"]) or {}).get("periods") != m.get("periods")]
        checks = list(old.get("checks") or [])
        checks.append({"version": len(checks) + 1, "at": _now(), "by": by, "reason": reason, "changed": moved, "voided": voided})
        doc["checks"] = checks
        write_json_atomic(path, doc)
    return doc


def _kpi_names(plane) -> dict[str, str]:
    root, found = plane.path("intents", "m2_baseline"), []
    for d in root.iterdir() if root.is_dir() else []:
        try:
            b = read_json_strict(d / "baseline.json", dict) or {}
        except (OSError, ValueError):
            continue
        if b.get("state") == "signed":
            found.append((str(b.get("created_at")), d))
    try:
        kpis = read_json_strict(max(found)[1] / "kpis.json", list) if found else []
    except (OSError, ValueError):
        kpis = []
    return {str(k["id"]): str(k["name"]) for k in kpis or [] if isinstance(k, dict) and k.get("id") and k.get("name")}


def _rule_counts(plane, bp: dict, code: str) -> dict | None:
    """{failed, passed} rule counts of the latest run of each pipeline feeding the measure; None when no run is logged."""
    try:
        runs = (read_json_strict(plane.path("warehouse", "runs.json"), dict) or {}).get("runs", [])
    except (OSError, ValueError):
        return None
    out, seen = {"failed": 0, "passed": 0}, False
    for src in {slug(ln.get("source")) for ln in bp.get("lineage", []) if ln["measure"] == code}:
        last = next((r for r in reversed(runs) if slug(r.get("source")) == src), None)
        for r in (last or {}).get("rules") or []:
            seen = True
            out["passed" if r.get("passed") else "failed"] += 1
    return out if seen else None


def _owners(plane, code: str) -> set[str]:
    return {view.norm(o) for _, o in _of(_reported(plane), _kpi_names(plane), code).values() if o}


def _may_see(plane, code: str, viewer: view.Viewer) -> bool:
    bp = read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    mart = next((ln["mart"].rsplit(".", 1)[0] for ln in bp.get("lineage", []) if ln["measure"] == code), None)
    entry = next((a for a in bp.get("access", []) if a.get("mart") == mart), None)
    if entry is None:  # no access entry: closed
        return False
    names = entry.get("may_see")
    return True if names is None else view.allows(frozenset(view.norm(n) for n in names), viewer)


def _open_plane(request: Request):
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, "No company space") from None


@router.get("/api/company/build/prove")
def get_api_company_build_prove(request: Request):
    plane, viewer = _open_plane(request), _viewer(request)
    doc = _compute(plane)
    bp = read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    names, tester, doc["sponsor"] = _kpi_names(plane), _role(plane, "tester"), _role(plane, "sponsor")
    for m in doc["measures"]:
        m["name"], m["tester"], m["rules"] = names.get(m["code"], m["code"]), tester, _rule_counts(plane, bp, m["code"])
        m["waits_for"] = _waits(m)
        if not _may_see(plane, m["code"], viewer):  # result and reason only
            m["periods"] = [{**p, "ours": None, "reported": None} for p in m["periods"]]
    return doc


@router.post("/api/company/build/prove/{measure}/accept")
def post_api_company_build_prove_measure_accept(request: Request, measure: str, body: dict = Body(...)):
    plane, viewer = _open_plane(request), _viewer(request)
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(422, "A reason is needed to accept a gap")
    if "company_admin" not in viewer.roles and view.norm(viewer.name) not in _owners(plane, measure):
        raise HTTPException(403, "Only the measure's owner or the company admin can accept a gap")
    doc = _compute(plane)
    m = next((m for m in doc["measures"] if m["code"] == measure), None)
    if m is None:
        raise HTTPException(404, "No such measure in the band")
    if m.get("changed"):
        raise HTTPException(409, "This measure's result changed after the tester signed it. Re-check the figures first.")
    if not any(p["result"] == "gap" and body.get("period") in (None, p["period"]) for p in m["periods"]):
        raise HTTPException(409, "This measure has no gap to accept")
    path = plane.path("build", "prove.json")
    with lock_for(path):  # re-read: the uat route may have written since
        doc = settle(plane, read_json_strict(path, dict) or {})
        for mm in doc["measures"]:
            if mm["code"] == measure:
                for p in mm["periods"]:
                    if p["result"] == "gap" and body.get("period") in (None, p["period"]):
                        p["accepted_by"], p["reason"] = viewer.name, reason
                mm["release_ready"] = _ready(mm["periods"], mm["uat"])
        write_json_atomic(path, doc)
    return {"measure": measure, "accepted_by": viewer.name}


@router.post("/api/company/build/prove/recheck")
def post_api_company_build_prove_recheck(request: Request, body: dict = Body(...)):
    """A named person re-checks the figures on purpose: the only act that voids a signature over a changed result."""
    plane, viewer = _open_plane(request), _viewer(request)
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(422, "Say why you are re-checking the figures")
    tester = _role(plane, "tester")
    if not ({"company_admin", "sponsor", "analyst"} & set(viewer.roles)) and not (tester and view.norm(viewer.name) == view.norm(tester)):
        raise HTTPException(403, "Only the company admin, the sponsor, the analyst or the named tester can re-check the figures")
    checks = recheck(plane, viewer.name, reason).get("checks") or []
    return {"checks": checks}


@router.post("/api/company/build/release/sign")
def post_api_company_build_release_sign(request: Request):
    plane, viewer = _open_plane(request), _viewer(request)
    if "sponsor" not in viewer.roles:
        raise HTTPException(403, "Only the sponsor signs the release")
    if (read_json_strict(plane.path("build", "blueprint.json"), dict) or {}).get("state") != "signed":
        raise HTTPException(409, "The blueprint is not signed yet, so there is nothing to release. Sign the blueprint first.")
    doc = _compute(plane)
    released = [m["code"] for m in doc["measures"] if m["release_ready"]]
    if not released:
        raise HTTPException(409, "Nothing is ready to release yet. " + "; ".join(f"{m['code']} waits for {_waits(m)}" for m in doc["measures"]))
    held = [{"code": m["code"], "reason": f"waits for {_waits(m)}"} for m in doc["measures"] if not m["release_ready"]]
    path = plane.path("build", "prove.json")
    with lock_for(path):
        doc = settle(plane, read_json_strict(path, dict) or {})
        doc["release"] = {"state": "signed", "by": viewer.name, "at": _now(), "released": released, "held_back": held}
        write_json_atomic(path, doc)
    from sh_platform.graph.knowledge_map import try_moment
    try_moment(plane, "release", doc["release"]["at"], viewer.name)
    from sh_platform.build import chain  # 59: changes waiting for the release move to the ops manager now
    try:
        chain.on_release(plane, viewer.name)
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the change notes were not moved on the release", exc_info=True)
    return doc["release"]
