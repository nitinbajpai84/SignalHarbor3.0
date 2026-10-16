"""Decision schemas: one versioned record per figure the office has defined (spec: docs/v3/STEP1-DECISION-SCHEMAS.md).

The record is built when a brief is confirmed (Decision 1), gets its reads, sql hash, tie-out and first run at the trial run (Decision 3), appends a run for each
live or monthly run, and is offered to the next brief that names the same figure. A new version that fails its tie-out is held and the last verified version stays
current (the rollback). Stored one file per figure: <company>/v3/figures/<figure_id>.json. The office sees "Built from", "Where this number comes from",
"What I assumed" and "Also used by", never the word schema."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timezone

from sh_platform.jsonfile import write_json_atomic
from sh_platform.v1 import v3_skills as SK

log = logging.getLogger(__name__)
LOCK = threading.RLock()
DEFINE, REUSE, CHECK, WHERE = "intent.define-figure", "model.find-reusable", "check.adds-up", "consume.explain-number"
LOADER = {  # what the loaders did to the data a figure reads: table -> (plain line, where it is recorded)
    "cash_movements": ("Money in is positive and money out is negative. With Debit and Credit columns, the amount is credit minus debit.", "ASSUMPTIONS A5"),
    "transactions": ("A buy adds quantity and takes cash; a sell does the reverse; an FX forward takes the sold amount and adds the bought amount.", "loader"),
    "position_snapshots": ("A snapshot that a later one supersedes is left out; a carried-forward row is left out when a real row of the same portfolio, instrument, date and currency exists.", "loader"),
    "fx_confirmations": ("An FX confirmation has its own table with both currency legs, trade and value dates.", "ASSUMPTIONS A1"),
    "expected_statements": ("A missing statement is counted against the statements the office expects from each fund each month.", "ASSUMPTIONS A2"),
}
DATES = ("A text date is read with the date format confirmed in the file's mapping; a date that cannot be read is set aside, never guessed.", "loader")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fid(name: str) -> str:
    return "fig-" + (re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:60] or "figure")


# ---- the store --------------------------------------------------------------------------------------------------------------------------

def _dir(plane):
    d = plane.path("v3", "figures")
    d.mkdir(parents=True, exist_ok=True)
    return d


def read(plane, figure_id: str) -> dict | None:
    p = _dir(plane) / f"{re.sub(r'[^a-z0-9-]', '', str(figure_id))}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except (OSError, ValueError):
        return None


def _save(plane, rec: dict) -> None:
    with LOCK:
        write_json_atomic(_dir(plane) / f"{rec['id']}.json", rec)


def every(plane) -> list[dict]:
    return [r for p in sorted(_dir(plane).glob("*.json")) if (r := read(plane, p.stem))]


def version(rec: dict, v: int | None = None) -> dict | None:
    """Version v, or (no v) the current one."""
    if v is None:
        v = rec.get("current_v")
    return next((x for x in rec["versions"] if x["v"] == v), None)


def _best(rec: dict) -> int:
    ok = [x["v"] for x in rec["versions"] if x["status"] == "verified"]
    return max(ok) if ok else rec["versions"][-1]["v"]


def _status(rec: dict, ver: dict, status: str) -> None:
    """Set a version's status. A verified version becomes current; a held one never displaces a verified current version (the rollback)."""
    ver["status"] = status
    cur = version(rec)
    if status == "verified":
        rec["current_v"] = ver["v"]
    elif cur is None or cur["status"] != "verified":
        rec["current_v"] = _best(rec)


def hold_of(rec: dict) -> dict | None:
    """A newer version that failed its tie-out while an earlier verified one stays current: {v, reason}."""
    cur = rec.get("current_v") or 0
    h = next((x for x in reversed(rec["versions"]) if x["v"] > cur and x["status"] == "held"), None)
    return {"v": h["v"], "reason": h.get("reason") or ""} if h else None


def row(rec: dict) -> dict:
    cur = version(rec) or {}
    last = max((r["at"] for x in rec["versions"] for r in x.get("runs") or []), default=None)
    return {"id": rec["id"], "name": rec["name"], "current_v": rec.get("current_v"), "status": cur.get("status"), "built_from": cur.get("built_from"),
            "used_by_count": len(rec.get("used_by") or []), "last_run_at": last, "hold": hold_of(rec)}


# ---- what a figure assumed ----------------------------------------------------------------------------------------------------------------

def assumptions(reads, r: dict | None, th: dict | None = None) -> list[dict]:
    """The loaders' normalisations for the tables the figure reads, the recipe's stated reading (A7, A8) and what the person answered."""
    at, out = now(), []
    for t in sorted(reads or []):
        if t in LOADER:
            out.append({"text": LOADER[t][0], "source": LOADER[t][1], "at": at})
    if reads:
        out.append({"text": DATES[0], "source": DATES[1], "at": at})
    if r:
        out.append({"text": f"Built from the written {r['label']} recipe: {r.get('why') or r.get('formula') or ''}".strip(), "source": "ASSUMPTIONS A7", "at": at})
        if r.get("may_read"):
            out.append({"text": "It may read only: " + ", ".join(r["may_read"]) + ".", "source": "ASSUMPTIONS A8", "at": at})
    for q in (th or {}).get("span_q") or []:
        a = ((th or {}).get("answers") or {}).get(q["id"])
        if isinstance(a, str) and a.strip():
            out.append({"text": f"{q['text']} {a.strip()}", "source": "person", "at": at})
    return out


def _built(k: dict, plane) -> dict:
    from sh_platform.v1 import v3_recipes as R
    if r := R.bound(k):
        return {"kind": "recipe", "id": r["id"]}
    return {"kind": "skill", "id": R.skill_id(k["name"])} if R.saved(plane, k["name"]) else {"kind": "design", "id": fid(k["name"])}


# ---- Decision 1: create, offer, reuse -----------------------------------------------------------------------------------------------------

def _usable(rec: dict | None) -> dict | None:
    cur = version(rec) if rec else None
    return cur if cur and cur["status"] == "verified" else None


def _threads(rec: dict) -> set:
    return {u.get("thread") for u in rec.get("used_by") or []}


def reuse_for(plane, th: dict) -> list[dict]:
    """The verified figures a brief figure matches, by the same figure or the same recipe: what Decision 1 offers (the person decides)."""
    from sh_platform.v1.v3_figures import kpis_of
    out, figs = [], every(plane)
    for k in kpis_of(plane, th.get("iid")):
        bid, rid = fid(k["name"]), k.get("built_from") or None
        cands = [r for r in figs if _usable(r) and th.get("id") not in _threads(r)
                 and (r["id"] == bid or (rid and _usable(r)["built_from"].get("id") == rid))]
        if cands:
            r = sorted(cands, key=lambda r: r["id"] != bid)[0]
            cur = _usable(r)
            out.append({"brief_figure": bid, "figure_id": r["id"], "name": r["name"], "built_from": cur["built_from"],
                        "verified_runs": sum(1 for x in cur.get("runs") or [] if x.get("ok")), "first_used_by": (r.get("used_by") or [{}])[0].get("person"), "suggest": True})
    return out


def confirm(plane, th: dict, who: str | None, reuse: dict | None) -> None:
    """Decision 1 confirmed: each brief figure becomes a figure version (draft), or links to the verified figure the person accepted. Never blocks the confirm."""
    from sh_platform.v1 import v3_recipes as R
    from sh_platform.v1.v3_figures import kpis_of
    try:
        kpis = kpis_of(plane, th.get("iid"))
        if not kpis:
            return
        reuse = reuse if isinstance(reuse, dict) else {}
        offers = {o["brief_figure"]: o["figure_id"] for o in reuse_for(plane, th)}  # the map is keyed by the offer's figure_id: itself to use it, null to keep one's own
        offered = set(offers)
        at, linked, made = now(), th.setdefault("figs", {}), []
        with SK.record(plane, th.get("id"), REUSE) as rec:
            rec["detail"] = f"offered {len(offered)}, accepted {sum(1 for f in offers.values() if reuse.get(f) == f)}"
        with SK.record(plane, th.get("id"), DEFINE) as rec, LOCK:
            for k in kpis:
                bid = fid(k["name"])
                target = read(plane, offers[bid] if reuse.get(offers.get(bid)) == offers.get(bid) and bid in offers else "")
                use = {"thread": th["id"], "brief": th.get("title") or "", "person": who}
                if _usable(target):
                    if th["id"] not in _threads(target):
                        target["used_by"].append(use)
                    _save(plane, target)
                    linked[k["name"]] = {"id": target["id"], "v": target["current_v"], "reused": True}
                    made.append(f"{k['name']}: uses {target['name']} v{target['current_v']}")
                    continue
                r = R.bound(k)
                fig = read(plane, bid) or {"id": bid, "name": k["name"], "definition": "", "grain": [], "versions": [], "used_by": []}
                fig["definition"] = str(k.get("definition") or k.get("formula") or fig["definition"] or "")
                fig["grain"] = R.dims_for(r, k) if r else fig.get("grain") or []
                last = fig["versions"][-1] if fig["versions"] else None
                if last and last["status"] == "draft" and th["id"] in _threads(fig):
                    ver = last  # the same thread confirming again: the draft it made stands
                else:
                    ver = {"v": last["v"] + 1 if last else 1, "built_from": _built(k, plane), "reads": [], "sql_hash": None, "model": None, "prompt_hash": None,
                           "assumptions": [], "tie_out": None, "approved_by": who, "approved_at": at, "runs": [], "status": "draft"}
                    fig["versions"].append(ver)
                    fig.setdefault("current_v", ver["v"])
                ver["assumptions"] = assumptions((r or {}).get("may_read"), r, th)
                if th["id"] not in _threads(fig):
                    fig["used_by"].append(use)
                _save(plane, fig)
                linked[k["name"]] = {"id": bid, "v": ver["v"], "reused": False}
                made.append(f"{k['name']}: v{ver['v']} draft" + (", reuse declined" if bid in offered else ""))
            rec["detail"] = "; ".join(made)[:300]
    except Exception:  # noqa: BLE001 - the figure record never stops the confirm
        log.warning("the figure records could not be made", exc_info=True)


# ---- Decision 3: the trial run -----------------------------------------------------------------------------------------------------------

def trial(x) -> None:
    """Decision 3: each figure version this thread made gets its reads, sql hash, tie-out and first run; verified, or held when its checks fail. A reused figure
    only gains the run. A held new version leaves the last verified one current."""
    from sh_platform.v1 import b9_verify as V, v3_recipes as R
    from sh_platform.v1.v3_figures import kpis_of
    th, plane = x.th, x.plane
    if not th.get("figs"):
        return
    con = None
    try:
        gold = x.api("leo", "GET", f"/api/v1/build/p/{th['pid']}/architecture/pack", soft=True).get("pack", {}).get("target", {}).get("gold") or []
        kp = {k["name"]: k for k in kpis_of(plane, th.get("iid"))}
        run_id = str(th.get("run_id") or "trial")
        with SK.record(plane, th["id"], CHECK) as rec, LOCK:
            said = []
            for name, link in th["figs"].items():
                fig = read(plane, link["id"])
                ver = version(fig, link["v"]) if fig else None
                f = next((f for f in th.get("figures") or [] if f.get("kpi") == name), None)
                if not ver or f is None or "ok" not in f:
                    continue
                ver["runs"] = [r for r in ver["runs"] if r.get("run_id") != run_id] + [{"run_id": run_id, "at": now(), "ok": bool(f["ok"]), "rows": int(f.get("rows") or 0)}]
                if link.get("reused"):
                    _save(plane, fig)
                    said.append(f"{name}: run added to {fig['name']}")
                    continue
                k = kp.get(name) or {"name": name}
                sql = str(next((g.get("sql") for g in gold if g.get("name") == f.get("table")), "") or "")
                r = R.bound(k)
                t = None
                if r and f.get("table"):
                    con = con or V._copy(plane)
                    t = R.tie_out(con, r, f["table"])
                try:
                    reads = sorted(R.tables_read(sql)) if sql else []
                except Exception:  # noqa: BLE001 - SQL the parser cannot read: no reads listed, never a guess
                    reads = []
                ok = bool(f["ok"]) and not f.get("held") and (t is None or t["ok"])
                ver.update(built_from=_built(k, plane), reads=reads, sql_hash=hashlib.sha256(sql.encode("utf-8")).hexdigest()[:12] if sql else None,
                           model="model design" if (th.get("model_tables") or {}).get(f.get("table")) else None,
                           tie_out={"rule": t["label"], "ok": t["ok"], "at": now()} if t else None, assumptions=assumptions(reads, r, th),
                           reason="" if ok else (f.get("reason") or (t and not t["ok"] and t["label"]) or "The figure has no numbers yet."))
                _status(fig, ver, "verified" if ok else "held")
                _save(plane, fig)
                said.append(f"{name}: v{ver['v']} {ver['status']}")
            rec["detail"] = "; ".join(said)[:300]
    except Exception:  # noqa: BLE001 - the record never breaks Decision 3
        log.warning("the figure records could not be checked", exc_info=True)
    finally:
        if con is not None:
            con.close()


# ---- live and monthly runs ---------------------------------------------------------------------------------------------------------------

def runs(x) -> str:
    """After a live or monthly run: one run on each figure this thread uses (the ready table's rows now)."""
    th, plane = x.th, x.plane
    if not th.get("figs"):
        return "no figures to record"
    from sh_platform.v1 import cx_dash as CD
    try:
        rows = {t["name"]: t["rows"] for t in CD.gold_tables(plane, th["pid"])}
        got = x.api("leo", "GET", f"/api/v1/build/p/{th['pid']}/runs", soft=True)
        last = ((got.get("runs") if isinstance(got, dict) else got) or [{}])[0] or {}
        run_id, n = str(last.get("run_id") or now()), 0
        with SK.record(plane, th["id"], CHECK) as rec, LOCK:
            for name, link in th["figs"].items():
                fig = read(plane, link["id"])
                ver = version(fig, link["v"]) if fig else None
                tab = next((f.get("table") for f in th.get("figures") or [] if f.get("kpi") == name), None)
                if ver is None or tab is None:
                    continue
                n_rows = int(rows.get(tab) or 0)
                ver["runs"] = [r for r in ver["runs"] if r.get("run_id") != run_id] + [{"run_id": run_id, "at": now(), "ok": n_rows > 0, "rows": n_rows}]
                _save(plane, fig)
                n += 1
            rec["detail"] = f"run {run_id} recorded on {n} figures"
        return f"run recorded on {n} figures"
    except Exception:  # noqa: BLE001 - the record never stops a run
        log.warning("the run could not be recorded on the figures", exc_info=True)
        return "run not recorded"


# ---- the answer, the thread view, the page -------------------------------------------------------------------------------------------------

def link_answer(plane, th: dict, kpi_name: str) -> dict | None:
    """{id, name, v}: the figure an answer came from, for "Where this number comes from"."""
    link = (th.get("figs") or {}).get(kpi_name)
    fig = read(plane, link["id"]) if link else None
    if not fig:
        return None
    with SK.record(plane, th.get("id"), WHERE) as rec:
        rec["detail"] = f"{kpi_name} comes from {fig['name']} v{fig.get('current_v')}"
    return {"id": fig["id"], "name": fig["name"], "v": fig.get("current_v")}


def thread_figures(plane, th: dict) -> list[dict]:
    """The figures a thread uses; `hold` is set when a newer version failed its tie-out, so every thread using the figure shows it."""
    out = []
    for link in (th.get("figs") or {}).values():
        if fig := read(plane, link["id"]):
            out.append({"figure_id": fig["id"], "name": fig["name"], "v": fig.get("current_v"), "status": (version(fig) or {}).get("status"), "hold": hold_of(fig)})
    return out


def lineage(plane, rec: dict) -> dict:
    """files -> tables -> figure, from the first thread that used the figure."""
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1.v3_figures import table_rows
    reads = set((version(rec) or {}).get("reads") or [])
    try:
        silver = table_rows(plane)
    except Exception:  # noqa: BLE001 - a busy warehouse: the lineage shows names without counts
        log.info("the table counts could not be read for the lineage", exc_info=True)
        silver = {}
    th = None
    for u in rec.get("used_by") or []:
        try:
            th = H.load(plane, u["thread"])
            break
        except (KeyError, OSError):
            continue
    files = [{"name": m["name"], "rows": sum(silver.get(t, 0) for t in m.get("tables") or [] if t in reads)}
             for m in ((th or {}).get("maps") or {}).values() if reads & set(m.get("tables") or [])]
    name = next((k for k, l in ((th or {}).get("figs") or {}).items() if l["id"] == rec["id"]), None)
    f = next((f for f in (th or {}).get("figures") or [] if f.get("kpi") == name), {})
    return {"files": files, "tables": [{"name": t, "rows": silver.get(t)} for t in sorted(reads)], "figure": {"name": f.get("words") or rec["name"], "rows": f.get("rows")}}


def detail(plane, rec: dict) -> dict:
    return {**rec, "hold": hold_of(rec), "lineage": lineage(plane, rec)}


def rollback(plane, figure_id: str, v, by: str | None, admin: bool) -> dict:
    """An earlier verified version becomes current again. Company admin or the figure's approver only."""
    with LOCK:
        rec = read(plane, figure_id)
        if rec is None:
            raise KeyError(figure_id)
        if not admin and by not in {x.get("approved_by") for x in rec["versions"]}:
            raise PermissionError("Only a company admin or the person who approved this figure can roll it back.")
        ver = version(rec, v) if isinstance(v, int) else None
        if ver is None or ver["status"] != "verified":
            raise ValueError("Choose a version that was verified.")
        rec["current_v"] = ver["v"]
        _save(plane, rec)
        return rec


# ---- hooks into v3_harbor (called once when it loads) ---------------------------------------------------------------------------------------

def install(H) -> None:
    d2, d3 = H.DECISIONS["decision2"], H.DECISIONS["decision3"]

    def decision2(x):
        d = d2(x)
        got = [{"figure": n, "text": a["text"], "source": a["source"]} for n, l in (x.th.get("figs") or {}).items()
               if (fig := read(x.plane, l["id"])) and (ver := version(fig, l["v"])) for a in ver.get("assumptions") or []]
        return {**d, "assumptions": got} if got else d  # "What I assumed"

    def decision3(x):
        d = d3(x)
        trial(x)
        return d
    H.DECISIONS["decision2"], H.DECISIONS["decision3"] = decision2, decision3

    def figure_runs(x):
        return runs(x)
    for c in ("C", "M"):
        steps, final = H.CHAINS[c]
        H.CHAINS[c] = ([*steps, ("Flow", "Recorded the run on each figure", figure_runs)], final)
