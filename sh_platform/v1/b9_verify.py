"""V5W-3: verify the trial run, send it to the business owner, review it against the signed benchmark, fix the mix, accept the numbers.

One small record per project, `build/<pid>/verify.json`: {verified, review}. Nothing here calculates a return except the weighted sum of the
signed components' returns (Decimal) under the weights the run used; every other figure is a warehouse row or k7_routes.monthly.
Money and returns are Decimal strings, never floats."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import duckdb

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import DATA_ENGINEER, seat_of

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYS, _WEIGHTS = ("market_series_key", "series_key", "component"), ("component_weight", "weight")
_NUM = ("DECIMAL", "DOUBLE", "FLOAT", "BIGINT", "INTEGER", "HUGEINT", "REAL", "SMALLINT")
Q4 = Decimal("0.0001")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(plane, pid: str):
    return R._dir(plane, pid) / "verify.json"  # _dir refuses a bad project id


def load(plane, pid: str) -> dict:
    try:
        got = read_json_strict(_path(plane, pid), dict)
    except (OSError, ValueError):
        raise Refused(500, "The review record could not be read. Please ask your administrator.") from None
    return got or {"verified": None, "review": None, "log": []}


def _save(plane, pid: str, fn) -> dict:
    path = _path(plane, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(path):
        rec = load(plane, pid)
        fn(rec)
        write_json_atomic(path, rec)
    return rec


def _pct(v: Decimal | None) -> str | None:
    return None if v is None else str((Decimal(v) * 100).quantize(Q4, ROUND_HALF_UP))  # a plain 0 arrives when a sum is empty


def _dec(v) -> Decimal:
    return Decimal(str(v))


def _fmt(d: Decimal) -> str:
    return format(d.normalize(), "f") if d == d.to_integral() or abs(d) >= 1 else format(d, "f")


# ---- 1. verify: control totals ------------------------------------------------------------------------------------------------

def _trail(con, batch_id: str) -> dict | None:
    """One stored figure that came from this batch, so the screen can open its a5 trail."""
    for kind, table in (("valuation", "valuation_observations"), ("position", "position_snapshots")):
        r = con.execute(f"select t.id from {table} t join source_records s on s.id = t.source_record_id where s.source_batch_id = ? limit 1", [batch_id]).fetchone()  # noqa: S608 - fixed names
        if r:
            return {"kind": kind, "id": str(r[0])}
    return None


def _batch_figures(con, codes: set[str] | None = None) -> list[dict]:
    """The loaded files' control totals. `codes`: only the batches of these source systems (V6B: a project shows its own sources, not the company's); None = all."""
    out = []
    for bid, ref, uri, mname, exp, got, tol in con.execute(
            "select b.id, b.batch_reference, b.storage_uri, c.measure_name, c.expected_value, c.loaded_value, coalesce(c.tolerance, 0)"
            " from source_batches b join batch_control_totals c on c.source_batch_id = b.id left join source_systems s on s.id = b.source_system_id"
            " where b.validation_status = 'loaded'" + ("" if codes is None else " and lower(s.source_code) in (select unnest(?))") +
            " order by b.received_at, c.measure_name", [] if codes is None else [sorted(codes)]).fetchall():
        e, g = _dec(exp), _dec(got)
        file = (uri or ref or "").replace("\\", "/").rsplit("/", 1)[-1]
        out.append({"figure": mname.replace("_", " ").capitalize(), "source": _fmt(e), "run": _fmt(g), "traced_to": f"{file or ref}, batch {ref}",
                    "check": "Match" if abs(e - g) <= _dec(tol) else "Differs", "trail": _trail(con, str(bid))})
    return out


def _label(table: str) -> str:
    return table.removeprefix("gold_").replace("_", " ").capitalize()


def _cols(con, table: str) -> dict[str, str]:
    return {r[0]: r[1] for r in con.execute("select column_name, data_type from information_schema.columns where table_name = ?", [table]).fetchall()}


def _sum(con, table: str, col: str) -> Decimal | None:
    v = con.execute(f'select sum("{col}") from "{table}"').fetchone()[0]  # noqa: S608 - names checked against _NAME and information_schema
    return None if v is None else _dec(v)


def _gold_figures(con, plan: dict | None) -> list[dict]:
    """Row count and each numeric column's total of every gold table. Compared with the same column's total in the tables it reads from when
    one has the same name; else 'Not compared' (shown, never counted as a match)."""
    out = []
    for t in (plan or {}).get("tables", []):
        name = t.get("name", "")
        if t.get("layer") != "gold" or not _NAME.match(name) or not (cols := _cols(con, name)):
            continue
        n = con.execute(f'select count(*) from "{name}"').fetchone()[0]  # noqa: S608
        out.append({"figure": f"{_label(name)}: rows", "source": None, "run": str(n), "traced_to": "Pipeline run on the copy", "check": "Not compared", "trail": None})
        for c, ty in cols.items():
            if not ty.upper().startswith(_NUM) or not _NAME.match(c):
                continue
            mine, src, dep = _sum(con, name, c), None, None
            for d in t.get("depends_on") or []:
                if _NAME.match(d) and c in _cols(con, d):
                    src, dep = _sum(con, d, c), d
                    break
            out.append({"figure": f"{_label(name)}: total of {c.replace('_', ' ')}", "source": None if src is None else _fmt(src), "run": None if mine is None else _fmt(mine),
                        "traced_to": f"{_label(dep)}, from the loaded files" if dep else "No loaded file has this column",
                        "check": "Not compared" if src is None else "Match" if src == mine else "Differs", "trail": None})
    return out


def _copy(plane):
    """The trial-run copy when there is one (read only), else the warehouse."""
    f = plane.path("warehouse", "sandbox.duckdb")
    return duckdb.connect(str(f), read_only=True) if f.exists() else wh.connect(plane, read_only=True)


def figures(plane, pid: str) -> list[dict]:
    plan = R.latest_plan(plane, pid)
    codes = {str(s.get("landing_source") or s.get("code")).lower() for s in (plan or {}).get("sources") or []} if (plan or {}).get("own_batches") else None
    with wh.connect(plane, read_only=True) as live:
        out = _batch_figures(live, codes)
    try:
        con = _copy(plane)
    except (OSError, duckdb.IOException):
        raise Refused(503, "The trial run copy is busy. Try again in a minute.") from None
    try:
        return out + _gold_figures(con, plan)
    finally:
        con.close()


def mark_verified(plane, viewer, pid: str) -> dict:
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can verify a run.")
    figs = figures(plane, pid)
    bad = [f for f in figs if f["check"] == "Differs"]
    if bad:
        raise Refused(409, f"{len(bad)} figure{'s' if len(bad) > 1 else ''} differ from the source files, so the run cannot be marked verified: {bad[0]['figure']}.")
    if not any(f["check"] == "Match" for f in figs):
        raise Refused(409, "Nothing was compared against a source file yet. Load the source files and run again.")
    last = (R.runs(plane, pid, 1) or [{}])[0]
    mine = {"by": viewer.name, "at": _now(), "run_id": last.get("run_id"), "matched": sum(f["check"] == "Match" for f in figs), "total": len(figs)}
    _save(plane, pid, lambda r: (r.__setitem__("verified", mine), r.setdefault("log", []).append({"event": "verified", **mine})))
    return mine


# ---- 2. business review against the signed benchmark ---------------------------------------------------------------------------

def owner_of(plane, pid: str) -> str | None:
    """The business owner: the person who raised the project."""
    return P1.read(plane, pid)["people"].get("raiser")


def is_owner(plane, viewer, pid: str) -> bool:
    return viewer.name == owner_of(plane, pid) or "company_admin" in set(viewer.roles)


def _maker(rec: dict, viewer) -> bool:
    """Maker never checker: whoever verified, sent or fixed the run may not accept it."""
    rv = rec.get("review") or {}
    return viewer.name in {(rec.get("verified") or {}).get("by"), rv.get("requested_by"), (rv.get("fix") or {}).get("by")}


def _stale(plane, rec: dict, pid: str) -> bool:
    """The copy was run again after it was verified (for example by the fix)."""
    last = (R.runs(plane, pid, 1) or [{}])[0].get("run_id")
    return (rec.get("verified") or {}).get("run_id") != last


def _latest_month(plane, pid: str) -> str:
    """The newest month in the run's benchmark weights table; else last month."""
    con = _copy(plane)
    try:
        for t in (R.latest_plan(plane, pid) or {}).get("tables", []):
            n = t.get("name", "")
            if t.get("layer") == "gold" and "benchmark" in n and _NAME.match(n) and "month" in _cols(con, n):
                got = con.execute(f'select max(cast("month" as varchar)) from "{n}"').fetchone()[0]  # noqa: S608
                if got and re.match(r"\d{4}-\d{2}", str(got)):
                    return str(got)[:7]
    except (OSError, duckdb.Error):
        pass
    finally:
        con.close()
    first = wh.today(plane).replace(day=1)
    return (first - timedelta(1)).strftime("%Y-%m")


def suggest(plane, viewer, pid: str) -> dict:
    """Defaults for the send-for-review form (design C5): the viewer's first portfolio, the newest approved benchmark, the run's latest month, a drafted message."""
    from sh_platform.v1 import k7_routes
    out = {"portfolio": "", "code": "", "month": "", "message": ""}
    pk = (R.latest_plan(plane, pid, live=True) or {}).get("benchmark") or {}  # V6: the pack names the portfolio, benchmark and month (WALK 9: never typed by hand)
    out.update({k: str(pk[k]) for k in ("portfolio", "code", "month") if pk.get(k)})
    try:
        out["month"] = out["month"] or _latest_month(plane, pid)
        with wh.connect(plane, read_only=True) as con:
            code = con.execute("select benchmark_code from benchmark_definitions where approval_status = 'approved' order by effective_from desc, version_number desc").fetchone()
            codes = [r[0] for r in con.execute("select portfolio_code from portfolios order by portfolio_code").fetchall()]
        out["code"] = out["code"] or (code[0] if code else "")
        for c in ([] if out["portfolio"] else codes):
            try:
                k7_routes._portfolio(plane, viewer, c)
            except Refused:
                continue
            out["portfolio"] = c
            break
    except (OSError, duckdb.Error):
        return out
    if out["portfolio"] and out["code"] and out["month"]:
        try:
            c = comparison(plane, viewer, pid, {k: out[k] for k in ("portfolio", "code", "month")})
            if c["portfolio_pct"] is not None and c["benchmark_run_pct"] is not None:
                who = (owner_of(plane, pid) or "there").split()[0]
                out["message"] = (f"Hi {who}, here is the outcome of the trial run on {_month_name(out['month'])}. The totals match the source files and every figure is traced. "
                                  f"The liquid portfolio returned {c['portfolio_pct']}% and the benchmark in this run is {c['benchmark_run_pct']}%. "
                                  "Please send the benchmark you sign off against, so we can check the result against it before it goes to the council.")
        except (Refused, OSError, duckdb.Error):
            pass
    return out


def plain_name(key: str) -> str:
    """V6: a series key as people say it (WALK 7: never IDX:GLEQ:SYN on a screen). The 'plus spread' part reads 'plus a spread'."""
    from sh_platform.v1.k9_daily import SERIES
    base, spread = key.removesuffix(" plus spread"), key.endswith(" plus spread")
    return SERIES.get(base, base) + (" plus a spread" if spread else "")


def _month_name(m: str) -> str:
    y, mo = m.split("-")
    return date(int(y), int(mo), 1).strftime("%B %Y")


def figure_lines(plane, viewer, pid: str) -> dict | None:
    """What the council is told (designs D4, D5): the month's figure against the SIGNED benchmark, from the review's own comparison. None when no review exists
    or the figures cannot be read; never invented."""
    rv = load(plane, pid).get("review")
    if not rv:
        return None
    try:
        c = comparison(plane, viewer, pid, rv)
    except (Refused, OSError, duckdb.Error):
        return None
    if c["portfolio_pct"] is None or c["benchmark_signed_pct"] is None or c["difference_signed_pts"] is None:
        return None
    pf, bm, d = (f"{Decimal(x):.2f}" for x in (c["portfolio_pct"], c["benchmark_signed_pct"], c["difference_signed_pts"]))
    mon, ahead = _month_name(rv["month"]), Decimal(d) >= 0
    gap = f"{'ahead by' if ahead else 'behind by'} {abs(Decimal(d))} points"
    return {"month": rv["month"], "month_name": mon, "portfolio_pct": pf, "benchmark_pct": bm, "difference_pts": d, "version": c["signed_version"], "name": c["benchmark_name"],
            "code": rv["code"], "portfolio": rv["portfolio"], "state": rv["state"], "accepted_by": rv.get("accepted_by"),
            "sentence": f"{mon.split()[0]} performance: the liquid portfolio returned {pf}% against the family benchmark of {bm}%, {gap}.",
            "email_subject": f"{mon.split()[0]}: portfolio {pf}%, benchmark {bm}%, {gap}",
            "note_line": f"{'Ahead of' if ahead else 'Behind'} the benchmark by {abs(Decimal(d))} points in {mon.split()[0]}.",
            "mix": [{"component": r["component"], "weight_pct": r["signed_weight_pct"]} for r in c["rows"]]}


def send_for_review(plane, viewer, pid: str, body: dict) -> dict:
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can send a run for review.")
    rec = load(plane, pid)
    if not rec.get("verified"):
        raise Refused(409, "Verify the numbers first, then send them for review.")
    portfolio, code, month = (str(body.get(k) or "").strip() for k in ("portfolio", "code", "month"))
    if not (portfolio and code and re.fullmatch(r"\d{4}-\d{2}", month)):
        raise Refused(400, "Say which portfolio, which benchmark and which month (like 2026-09) to check.")
    owner = owner_of(plane, pid)
    if not owner:
        raise Refused(409, "This project has no business owner yet.")
    text = str(body.get("message") or "").strip()[:4000] or f"The trial run for {month} is verified. Please check it against the benchmark you signed."
    review = {"state": "requested", "owner": owner, "requested_by": viewer.name, "requested_at": _now(), "portfolio": portfolio, "code": code, "month": month,
              "table": str(body.get("table") or "") or None, "message": text, "issues": [], "case_id": None, "first": None, "accepted_by": None, "accepted_at": None}
    P1.comment(plane, pid, "benchmarks", None, viewer.name, "raiser", text, kind="note")  # the event the owner sees in Build; package 1's assignment replaces this
    _save(plane, pid, lambda r: (r.__setitem__("review", review), r.setdefault("log", []).append({"event": "review_requested", "to": owner, "at": review["requested_at"]})))
    return review


def _used_weights(plane, pid: str, month: str, table: str | None) -> tuple[str, dict[str, Decimal]]:
    """The weights the run used: the benchmark weights gold table of the copy (or the named table)."""
    plan = R.latest_plan(plane, pid) or {}
    names = [table] if table else [t["name"] for t in plan.get("tables", []) if "benchmark" in t.get("name", "") and t.get("layer") == "gold"]
    con = _copy(plane)
    try:
        for n in names:
            if not _NAME.match(n or ""):
                continue
            cols = _cols(con, n)
            k, w = next((c for c in _KEYS if c in cols), None), next((c for c in _WEIGHTS if c in cols), None)
            if not (k and w):
                continue
            sql = f'select "{k}", sum("{w}") from "{n}"' + (' where cast("month" as varchar) like ?' if "month" in cols else "") + f' group by "{k}"'  # noqa: S608
            return n, {str(a): _dec(b) for a, b in con.execute(sql, [month + "%"] if "month" in cols else []).fetchall()}
    finally:
        con.close()
    raise Refused(404, "The run has no benchmark weights table to check.")


def _note(rows: list[dict], version) -> str:
    """Lumen's one-paragraph reading of the mix (design C6). Plain words from the rows; nothing is worked out beyond counting the gaps."""
    n, bad = len(rows), [r for r in rows if r["differs"]]
    v = f"version {version}" if version else "the signed version"
    if not bad:
        return f"All {n} weights match {v}. The run used the signed mix."
    which = f"All {n}" if len(bad) == n else f"{len(bad)} of {n}"
    return f"{which} weights differ from {v}: " + "; ".join(f"{r['label']} is {r['used_weight_pct']}% in the run, signed at {r['signed_weight_pct']}%" for r in bad) + "."


def comparison(plane, viewer, pid: str, review: dict) -> dict:
    from sh_platform.v1 import k7_routes
    sign = k7_routes.monthly(plane, viewer, review["portfolio"], review["code"], review["month"], review["month"])
    m, table = sign["months"][0], None
    table, used = _used_weights(plane, pid, review["month"], review.get("table"))
    rows, per_key = [], {}
    for c in m["components"]:  # two signed parts can share a series (the private sleeve is the equity index plus a spread)
        per_key[c["series_key"]] = per_key.get(c["series_key"], Decimal(0)) + _dec(c["weight"])
    named = {(f"{c['series_key']} plus spread" if _dec((c.get("spread_return") or {}).get("value") or 0) else c["series_key"]) for c in m["components"]}
    exact = len(named) == len(m["components"]) and bool(used) and named <= set(used)  # V6B: a weights table that names each leg ('... plus spread') gives each its own weight
    run_key = {k: used.pop(k, Decimal(0)) for k in per_key} if not exact else {}
    for c in m["components"]:
        k, ret, sw = c["series_key"], _dec(c["return"]["value"]), _dec(c["weight"])
        name = f"{k} plus spread" if _dec((c.get("spread_return") or {}).get("value") or 0) else k
        if exact:
            uw = used.pop(name)
            differs = uw != sw
        else:
            uw = run_key[k] * sw / per_key[k] if per_key[k] else run_key[k]  # the run's weight for a shared series, split as signed
            differs = run_key[k] != per_key[k]
        rows.append({"component": name, "label": plain_name(name), "return_pct": c["return"]["pct"], "signed_weight_pct": _pct(sw), "used_weight_pct": _pct(uw),
                     "gap_pts": _pct(uw - sw), "differs": differs, "_ret": ret, "_sw": sw, "_uw": uw})
    for key, uw in used.items():  # a component the run used that the signed definition does not have
        rows.append({"component": key, "label": plain_name(key), "return_pct": None, "signed_weight_pct": _pct(Decimal(0)), "used_weight_pct": _pct(uw), "gap_pts": _pct(uw), "differs": uw != 0,
                     "_ret": Decimal(0), "_sw": Decimal(0), "_uw": uw})
    run_b, signed_b = sum(r["_uw"] * r["_ret"] for r in rows), _dec(m["benchmark"]["value"]) if m["benchmark"] else None
    port = _dec(m["portfolio"]["value"]) if m["portfolio"] else None
    for r in rows:
        for k in ("_ret", "_sw", "_uw"):
            del r[k]
    v = sign["version_used"] or {}
    return {"month": review["month"], "table": table, "benchmark_name": v.get("name"), "signed_version": v.get("version"), "rows": rows,
            "portfolio_pct": _pct(port), "benchmark_run_pct": _pct(run_b), "benchmark_signed_pct": _pct(signed_b),
            "difference_run_pts": _pct(None if port is None else port - run_b), "difference_signed_pts": _pct(None if port is None or signed_b is None else port - signed_b),
            "same": not any(r["differs"] for r in rows), "problems": m["problems"], "lumen_note": _note(rows, v.get("version"))}


def flag(plane, viewer, pid: str, text: str) -> dict:
    """The owner flags the mix: one case for the issue, the words as a comment on it (n2). The run goes back to the data engineer."""
    from sh_platform.v1 import e4_cases, n2_comments
    rec = load(plane, pid)
    rv = rec.get("review")
    if not rv or rv["state"] in ("accepted",):
        raise Refused(409, "There is no review waiting for you.")
    if not is_owner(plane, viewer, pid):
        raise Refused(403, "Only the business owner can send a run back.")
    text = str(text or "").strip()
    if not text:
        raise Refused(400, "Say what is wrong, so the data engineer can fix it.")
    try:
        cmp = comparison(plane, viewer, pid, rv)
    except Refused:
        cmp = None  # W3 walk: a run with no benchmark weights table can still be sent back in the owner's words; the fix is then a plan change
    case_id = rv.get("case_id")
    if not case_id:
        case = {"exception_type": "benchmark_review", "title": f"Benchmark mix differs from the signed definition ({rv['code']}, {rv['month']})",
                "materiality_status": "unknown", "description": text[:1000], "actor": viewer}
        try:  # W3 walk: the owner holds the case, so she can see it and comment on it (a case about no portfolio is closed to everyone else)
            case_id = e4_cases.open(plane, {**case, "owner_user_id": viewer})
        except e4_cases.Refused:  # no users row for her (an administrator seat): the administrator sees every case anyway
            case_id = e4_cases.open(plane, case)
    n2_comments.add(plane, viewer, "case", case_id, text)
    first = rv.get("first") or cmp
    _save(plane, pid, lambda r: (r["review"].update(state="flagged", case_id=case_id, first=first, fix=None, issues=r["review"]["issues"] + [{"by": viewer.name, "at": _now(), "text": text[:1000]}]),
                                 r.setdefault("log", []).append({"event": "flagged", "by": viewer.name, "at": _now()})))
    return load(plane, pid)["review"]


def propose_fix(plane, viewer, pid: str) -> dict:
    """Propose the signed mix as a rule version (signed by someone else through the rules register), then run the plan again on the copy."""
    from sh_platform.v1 import e3_rules
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can fix the run.")
    rv = load(plane, pid).get("review")
    if not rv or rv["state"] != "flagged":
        raise Refused(409, "Nothing has been sent back to fix.")
    cmp = rv["first"]  # worked out when the owner flagged it: the data engineer may not see the portfolio
    weights = {r["component"]: r["signed_weight_pct"] for r in cmp["rows"] if r["signed_weight_pct"] not in (None, "0.0000")}
    start = date.fromisoformat(rv["month"] + "-01")
    ver = e3_rules.propose(plane, viewer, f"benchmark_mix:{rv['code']}",
                           f"Benchmark {rv['code']} weights for {rv['month']} come from the signed version {cmp['signed_version']}, not from a draft.",
                           {"signed_version": cmp["signed_version"], "weights_pct": weights}, start, rule_type="policy")
    from sh_platform.jobs.handlers import run_pipeline  # W3: through the job queue
    run = run_pipeline(plane, pid, "sandbox", viewer.name)
    fix = {"rule_version_id": ver["rule_version_id"], "run_id": run["run_id"], "run_status": run["status"], "by": viewer.name, "at": _now()}
    _save(plane, pid, lambda r: (r["review"].__setitem__("fix", fix), r.setdefault("log", []).append({"event": "fix", **fix})))
    return fix


def accept(plane, viewer, pid: str) -> dict:
    rec = load(plane, pid)
    rv = rec.get("review")
    if not rv or rv["state"] not in ("requested", "flagged"):
        raise Refused(409, "There is no review waiting for you.")
    if not is_owner(plane, viewer, pid):
        raise Refused(403, "Only the business owner can accept the numbers.")
    if _maker(rec, viewer):
        raise Refused(403, "You verified, sent or fixed this run, so someone else must accept the numbers.")
    if _stale(plane, rec, pid):
        raise Refused(409, "The copy was run again after it was verified. The data engineer verifies the new run first.")
    if not comparison(plane, viewer, pid, rv)["same"]:
        raise Refused(409, "The mix in the run still differs from the signed benchmark. Send it back, or wait for the fixed run.")
    mine = {"state": "accepted", "accepted_by": viewer.name, "accepted_at": _now()}
    _save(plane, pid, lambda r: (r["review"].update(mine), r.setdefault("log", []).append({"event": "accepted", "by": viewer.name, "at": mine["accepted_at"]})))
    return load(plane, pid)["review"]


def view(plane, viewer, pid: str) -> dict:
    rec = load(plane, pid)
    rv = rec.get("review")
    figs = figures(plane, pid)
    seats, owner = seat_of(viewer), is_owner(plane, viewer, pid)
    out = {"project_id": pid, "figures": figs, "matched": sum(f["check"] == "Match" for f in figs), "total": len(figs), "verified": rec.get("verified"),
           "review": rv, "owner": owner_of(plane, pid), "comparison": None, "comparison_error": None,
           "suggest": suggest(plane, viewer, pid) if DATA_ENGINEER in seats and not rv else None}
    if rv:
        try:
            out["comparison"] = comparison(plane, viewer, pid, rv)
        except Refused as e:
            out["comparison_error"] = e.message
    st = (rv or {}).get("state")
    out["stale"] = bool(rec.get("verified")) and _stale(plane, rec, pid)  # W3 walk: the copy ran again after the verification; verify the new run
    out["can"] = {"verify": DATA_ENGINEER in seats and not any(f["check"] == "Differs" for f in figs), "send": DATA_ENGINEER in seats and bool(rec.get("verified")) and st is None,
                  "flag": owner and st in ("requested", "flagged"), "accept": owner and st in ("requested", "flagged") and not _maker(rec, viewer) and not _stale(plane, rec, pid)
                            and bool((out["comparison"] or {}).get("same")),  # accept() refuses without a matching comparison: never offer it
                  "fix": DATA_ENGINEER in seats and st == "flagged" and not (rv or {}).get("fix") and bool((rv or {}).get("first"))}
    return out
