"""Load the demo cycle (packs/family_office/1/demo_cycle, synthetic) into one company plane.

Usage: python tools/seed_demo_cycle.py [company_id] [--data-root PATH] [--dry-run]
Each step reads one folder of the pack and skips with a line when the folder is not there. Idempotent: tables are replaced,
runs and alerts are merged by id, intents and documents the loader owns are rewritten or left alone, never duplicated.
--dry-run copies the company plane (and the accounts file) to a temporary folder, loads there and prints the counts;
the live plane is not touched.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from sh_platform.warehouse import open_company, refresh_readonly_copy  # noqa: E402

DC = ROOT / "packs" / "family_office" / "1" / "demo_cycle"
COMPANY = "ardmore"
OWNED = "dc-"  # ids this loader owns in runs, alerts, cards


def _name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _csvs(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.csv"))


# ---- warehouse ---------------------------------------------------------------------------------------------------------------

def load_silver(plane, dc: Path) -> dict:
    """Every CSV of every area except gold becomes silver.<area>_<file> (replaced, never appended)."""
    out, con = {}, open_company(plane)
    try:
        con.execute("create schema if not exists silver")
        for area in sorted(p for p in dc.iterdir() if p.is_dir() and p.name != "gold"):
            for f in _csvs(area):
                t = f"silver.{_name(area.name)}_{_name(f.stem)}"
                con.execute(f"create or replace table {t} as select * from read_csv(?, header = true, all_varchar = false)", [str(f)])
                out[t] = con.execute(f"select count(*) from {t}").fetchone()[0]
    finally:
        con.close()
    return out


def _gold_rows(folder: Path) -> dict[str, list[dict]]:
    """code -> rows. Accepts one file per measure (k01.csv / gold.k01.csv, with period and value) or long files with a code column."""
    by: dict[str, list[dict]] = {}
    for f in _csvs(folder):
        with f.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        m = re.search(r"k(\d\d)$", f.stem.lower())
        codecol = next((c for c in ("code", "measure", "measure_code", "kpi") if rows and c in rows[0]), None)
        for r in rows:
            code = (r[codecol] if codecol else f"k{m.group(1)}" if m else "").strip().lower()
            if re.fullmatch(r"k\d\d", code):
                by.setdefault(code, []).append(r)
    return by


def load_gold(plane, dc: Path) -> dict:
    """gold.k01 .. gold.k27: period, value, plus whatever extra columns the gold folder carries (source, entity, note)."""
    out, con = {}, open_company(plane)
    try:
        con.execute("create schema if not exists gold")
        for code, rows in sorted(_gold_rows(dc / "gold").items()):
            cols = [c for c in rows[0] if c not in ("code", "measure", "measure_code", "kpi")]
            t = f"gold.{code}"
            con.execute(f"create or replace table {t} (" + ", ".join(
                f'"{c}" {"double" if c == "value" else "varchar"}' for c in cols) + ")")
            con.executemany(f"insert into {t} values ({', '.join('?' * len(cols))})",
                            [[(float(r[c]) if r[c] not in ("", None) else None) if c == "value" else r[c] for c in cols] for r in rows])
            out[t] = len(rows)
    finally:
        con.close()
    return out


def _gold_units(dc: Path) -> dict[str, str]:
    """code -> unit, from the gold README's table (| k01.csv | columns | unit | how |)."""
    f = dc / "gold" / "README.md"
    text = f.read_text(encoding="utf-8") if f.is_file() else ""
    return {m.group(1).upper(): m.group(2).strip() for m in re.finditer(r"^\| (k\d\d)\.csv \| [^|]+\| ([^|]+)\|", text, re.M)}


def load_reported(plane, dc: Path) -> dict:
    """The reported side of the Prove comparison from the same pack data: each reported figure the profile already holds for a blueprint
    measure takes the pack's gold value for its period (aggregated as the Prover aggregates it) and the gold README's unit. Only cells that
    differ are written; a period the gold lacks is left as it is. Then one re-check of the Prover, recorded as a version line."""
    from sh_platform.build import prove as PV
    from sh_platform.profile import store as PS
    bp = read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    lineage: dict[str, dict] = {}
    for ln in bp.get("lineage", []):
        lineage.setdefault(ln["measure"], ln)
    if not lineage:
        return {"figures": 0, "note": "no blueprint lineage"}
    names, units = PV._kpi_names(plane), _gold_units(dc)
    by_key = {PV.view._key(names.get(c) or c): c for c in lineage} | {PV.view._key(c): c for c in lineage}
    prov = {"mark": "stated", "by": "Demo cycle loader", "from": f"{dc.relative_to(ROOT).as_posix()}/gold"}
    con = open_company(plane)
    todo: list[tuple[str, object]] = []
    try:
        for fid, item in PS.raw(plane)["reported_figures"].items():
            code = by_key.get(PV.view._key(str(PV._v(item, "measure") or "")))
            period = str(PV._v(item, "period_end") or "")[:7]
            if not code or not period:
                continue
            ln = lineage[code]
            ours, _ = PV._ours(con, ln["mart"], str(ln.get("transform") or ""), period)
            if ours is None:
                continue
            for field, value in (("figure", round(ours, 6)), ("unit", units.get(code))):
                if value is not None and PV._v(item, field) != value:
                    todo.append((f"reported_figures.{fid}.{field}", value))
    finally:
        con.close()
    if todo:
        def apply(doc):
            for path, value in todo:
                PS.set_cell(doc, path, value, prov)
        PS.mutate(plane, apply)
    doc = PV.recheck(plane, "Demo cycle loader", "Demo cycle reload: reported figures refreshed from the pack's gold")
    res = [p["result"] for m in doc.get("measures", []) for p in m.get("periods") or []]
    return {"cells": len(todo), "checks": len(doc.get("checks") or []), "match": res.count("match"), "gap": res.count("gap"),
            "not_yet": res.count("not_yet"), "signed": sum(1 for m in doc.get("measures", []) if (m.get("uat") or {}).get("state") == "signed")}


# ---- run log, alerts, landing --------------------------------------------------------------------------------------------------

def _merge(path: Path, key: str, new: list[dict], sort: str | None = None) -> int:
    """Replace this loader's rows by id, keep everyone else's."""
    with lock_for(path):
        doc = read_json_strict(path, dict) or {key: []}
        ids = {r["id"] for r in new}
        rows = [r for r in doc.get(key) or [] if r.get("id") not in ids] + new
        if sort:
            rows.sort(key=lambda r: r.get(sort) or "")
        doc[key] = rows
        write_json_atomic(path, doc)
    return len(new)


def _read_any(f: Path, key: str) -> list[dict]:
    if f.suffix == ".json":
        d = json.loads(f.read_text(encoding="utf-8"))
        return d.get(key, []) if isinstance(d, dict) else d
    with f.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_runs(plane, dc: Path) -> dict:
    ops = dc / "operations"
    out = {}
    f = next((p for p in (ops / "runs.json", ops / "runs.csv") if p.is_file()), None)
    if f:
        runs = _read_any(f, "runs")
        out["runs"] = _merge(plane.path("warehouse", "runs.json"), "runs", runs, sort="started")
    f = next((p for p in (ops / "alerts.json", ops / "alerts.csv") if p.is_file()), None)
    if f:
        out["alerts"] = _merge(plane.path("build", "alerts.json"), "alerts", _read_any(f, "alerts"))
    return out


def load_landing(plane, dc: Path) -> dict:
    """Files under demo_cycle/landing/ except the README are copied into the plane's landing zone (same names)."""
    n = 0
    for f in sorted((dc / "landing").rglob("*")):
        if f.is_file() and f.name != "README.md":
            dst = plane.path("landing", *f.relative_to(dc / "landing").parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
            n += 1
    return {"files": n}


# ---- people ------------------------------------------------------------------------------------------------------------------
# Two id spaces land in the pack: master/people.csv (P01 Janet Shaw .. P09 Rahul Mehta, read by initiatives/) and the wave 2 roster
# (.sh-tmp/ic/wave2/ROSTER.md, P01 Daniel Kerr .. P55, read by operations/). Both resolve to a name, the name to the roster account.

ROSTER_MD = ROOT / ".sh-tmp" / "ic" / "wave2" / "ROSTER.md"
PID = re.compile(r"P\d\d")
_PEOPLE: dict = {}


def master_ids(dc: Path) -> dict[str, str]:
    f = dc / "master" / "people.csv"
    if not f.is_file():
        return {}
    with f.open(newline="", encoding="utf-8") as fh:
        return {r["person_id"]: r["name"] for r in csv.DictReader(fh)}


def roster_ids() -> dict[str, str]:
    if not ROSTER_MD.is_file():
        return {}
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"^\| (P\d\d) \| ([^|]+)\|", ROSTER_MD.read_text(encoding="utf-8"), re.M)}


def people(plane) -> dict[str, dict]:
    """name -> {account_id, name}: the roster's accounts, made by the intents seed's own people step (idempotent)."""
    key = str(plane.root)
    if key not in _PEOPLE:
        from tools.seed_demo_intents import seed_people
        _PEOPLE[key] = seed_people(plane.root.parent, plane)[0]
    return _PEOPLE[key]


class Who:
    """Resolves pack person ids against one id space; remembers any that do not resolve."""

    def __init__(self, plane, ids: dict[str, str]):
        self.P, self.ids, self.unknown = people(plane), ids, set()
        self.by_acct = {p["account_id"]: p for p in self.P.values()}

    def person(self, pid) -> dict | None:
        if pid is None:
            return None
        if pid in self.by_acct:
            return dict(self.by_acct[pid])
        p = self.P.get(self.ids.get(pid, pid))
        if p is None:
            self.unknown.add(str(pid))
        return dict(p) if p else None

    def acct(self, pid):
        p = self.person(pid) if isinstance(pid, str) and PID.fullmatch(pid) else None
        return p["account_id"] if p else pid


# ---- intents: initiatives and the decision -------------------------------------------------------------------------------------

def dc_id(pack_id: str, type_: str) -> str:
    from sh_platform.intents import store as S
    return f"{S.PREFIX[type_]}-{hashlib.md5(f'{COMPANY}:dc:{pack_id}'.encode()).hexdigest()}"


def _swap(x, who: Who, idmap: dict):
    """Every P id becomes an account id; every pack intent id becomes its store id (whole strings only)."""
    if isinstance(x, dict):
        return {k: _swap(v, who, idmap) for k, v in x.items()}
    if isinstance(x, list):
        return [_swap(v, who, idmap) for v in x]
    if isinstance(x, str):
        return idmap.get(x) or who.acct(x)
    return x


def _lines(rec: dict, raw: list[dict]) -> list[dict]:
    """Events in the store's line shape (SHAPES 15); `detail` keeps keys, enums and numbers only."""
    out = []
    for n, e in enumerate(sorted(raw, key=lambda e: e.get("at") or ""), 1):
        by = e.get("by")
        if isinstance(by, str):
            by = {"account": by, "name": None, "role": e.get("role")}
        detail = {k: v for k, v in (e.get("detail") or {}).items() if v is None or isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 40)}
        out.append({"seq": n, "at": e.get("at"), "kind": e.get("kind"), "status": e.get("status") or ("draft" if e.get("agent") else "act"),
                    "by": by, "anonymous": bool(e.get("anonymous")), "agent": e.get("agent"), "stage": e.get("stage"),
                    "ref": e.get("ref") or {"store": "intent", "id": rec["id"], "version": None}, "detail": detail,
                    "confirms": None, "corrects": None, "sealed": False})
    return out


def _write(plane, rec: dict, lines: list[dict], weeks: list[dict]) -> None:
    """One loader-owned intent folder, rewritten whole: events, weeks, then the record through the kernel store."""
    from sh_platform.intents import checkin as CK, store as S
    rec["event_count"] = len(lines)
    rec["events"] = {"path": f"intents/{rec['id']}/events.jsonl", "count": len(lines), "last_seq": len(lines),
                     "last_at": lines[-1]["at"] if lines else None}
    folder = plane.path("intents", rec["id"])
    with S.locked(plane):
        if folder.exists():
            shutil.rmtree(folder)  # this loader's own id (dc_id), never another seed's
        folder.mkdir(parents=True)
        (folder / "events.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        for w in weeks:
            CK.write_week(plane, rec["id"], w)
        S.write_intent(plane, rec, create=True)


def load_intents(plane, dc: Path) -> dict:
    """initiatives/*.json, each {"intent": {...}} (optional "hypothesis", "events", "weeks", "notes") or a bare record, into intents/. Pack ids become
    store ids (prefix + hash of the pack id); people go from master ids to roster accounts; keys outside the store's set are dropped
    and reported."""
    from sh_platform.intents import store as S
    who = Who(plane, master_ids(dc))
    docs = []
    for f in sorted((dc / "initiatives").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        wrap = d if isinstance(d, dict) and isinstance(d.get("intent"), dict) else {"intent": d}
        if isinstance(wrap["intent"], dict) and wrap["intent"].get("type") in S.PREFIX:
            docs.append(wrap)
    idmap = {w["intent"]["id"]: dc_id(w["intent"]["id"], w["intent"]["type"]) for w in docs}
    out, dropped = {"written": 0, "ids": {}}, {}
    for wrap in docs:
        pack_id = wrap["intent"]["id"]
        w = _swap(wrap, who, idmap)
        rec = w["intent"]
        ppl = rec.setdefault("people", {})
        for slot in S.SLOTS:
            ppl[slot] = who.person(ppl.get(slot)) if isinstance(ppl.get(slot), str) else ppl.get(slot)
        for lst in S.LISTS:
            ppl[lst] = [who.person(v) or v if isinstance(v, str) else v for v in ppl.get(lst) or []]
        if w.get("notes") and not rec.get("notes"):
            rec["notes"] = w["notes"]
        hyp = w.get("hypothesis")
        if isinstance(hyp, dict) and hyp.get("id"):
            # spec 57: the hypothesis in intents/hypotheses/<hyp id>.json, the intent keeps hypothesis_ref
            write_json_atomic(plane.path("intents", "hypotheses", f"{hyp['id']}.json"), hyp)
            rec.setdefault("hypothesis_ref", {"id": hyp["id"], "version": len(hyp.get("versions") or [])})
            out["hypotheses"] = out.get("hypotheses", 0) + 1
        extra = set(rec) - S.KEYS
        if extra:
            dropped[pack_id] = sorted(extra)
            for k in extra:
                rec.pop(k)
        rec["record"] = f"intents/{rec['id']}/intent.json"
        rec.setdefault("company", COMPANY)
        raw = w.get("events") or [{"at": rec.get("created_at"), "kind": "intent_opened", "by": rec.get("created_by"),
                                   "stage": ((rec.get("stages") or [{}])[0]).get("key")}]
        _write(plane, rec, _lines(rec, raw), w.get("weeks") or [])
        out["written"] += 1
        out["ids"][pack_id] = rec["id"]
    if dropped:
        out["dropped_keys"] = dropped
    if who.unknown:
        out["unknown_people"] = sorted(who.unknown)
    return out


# ---- week files: one check-in series ---------------------------------------------------------------------------------------------

PULSE_KEY = "dc-pulse-ops"
PULSE_TITLE = "Fund operations and reporting weekly check-in"


def _stamp(d: str) -> str:
    return f"{d}T00:00:00+00:00"


def load_weeks(plane, dc: Path) -> dict:
    """operations/weeks/<week_key>.json (roster ids) under one Weekly check-in series, items in the check-in builder's own shape."""
    from sh_platform.intents import checkin as CK, lifecycle as L
    from sh_platform.profile import view as PV
    from tools.seed_demo_intents import outcome_row
    raw = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((dc / "operations" / "weeks").glob("*.json"))]
    if not raw:
        return {"weeks": 0}
    who = Who(plane, roster_ids())
    prompts = [{"kind": p["kind"], "lead": p["lead"]} for p in L.type_def("pulse")["weekly_prompts"]]
    weeks, reporters, reviewer = [], [], None
    for w in raw:
        rows = []
        for it in w["items"]:
            anon = it.get("by") in (None, "anonymous")
            p = None if anon else who.person(it["by"])
            row = CK._new_item(it["kind"], it["text"], PV.Viewer(p["name"] if p else "", frozenset(), account_id=p["account_id"] if p else None),
                               anonymous=anon)
            row.update({k: it.get(k) for k in ("severity", "count", "amount", "ref", "fate", "fate_reason")})
            row["id"] = f"dc-{it['id']}"
            row["decided_by"] = who.acct(it.get("decided_by"))
            if row["fate"]:
                row["decided_at"] = w.get("closed_at")
            rows.append(row)
            if p and p["name"] not in reporters:
                reporters.append(p["name"])
        review = dict(w.get("review") or {})
        if review.get("reviewer"):
            reviewer = reviewer or who.person(review["reviewer"])
            review["reviewer"] = who.acct(review["reviewer"])
        weeks.append({"week_key": w["week_key"], "opens": w["opens"], "closes": w["closes"], "answers_close": w["closes"], "review_day": w["closes"],
                      "state": w["state"], "people": [], "prompts": prompts, "items": rows, "submissions": [], "review": review,
                      "stage_closed_at": w.get("closed_at"), "closed_at": w.get("closed_at"), **({"read_only": True} if w.get("closed_at") else {})})
    P = who.P
    for w in weeks:
        w["people"] = [dict(P[n]) for n in reporters]
    org = reviewer or dict(P["Katie Kingsley"])
    opened = _stamp(weeks[0]["opens"])
    rec = L.new_record("pulse", COMPANY, org, opened, title=PULSE_TITLE, purpose=CK.PURPOSE, areas=["operations"])
    rec["id"] = dc_id(PULSE_KEY, "pulse")
    rec["record"] = f"intents/{rec['id']}/intent.json"
    rec["people"]["participants"] = [dict(P[n]) for n in reporters]
    rec["people"]["observers"] = [dict(P["Janet Shaw"])]
    rec["state"] = "open"
    rec["time_box"] = {"starts": _stamp(weeks[-1]["opens"]), "ends": f"{weeks[-1]['closes']}T15:59:00+00:00", "extended_by": []}
    rec["stages"] = [{"key": "running", "name": "Running", "state": "open", "opened_at": opened, "closed_at": None}]
    rec["history"].append({"at": opened, "by": org["account_id"], "from": "draft", "to": "open", "note": ""})
    closed = [w for w in weeks if w["closed_at"]]
    rec["outcome"].update(weeks=[outcome_row(w) for w in closed])
    rec["series"] = {"status": "running", "close_day": "fri", "reviewer": org["account_id"], "reviewer_name": org["name"], "extra_prompt": None,
                     "week_length_days": 5, "next_week_opens": None, "current_week": weeks[-1]["week_key"],
                     "weeks": [w["week_key"] for w in weeks], "paused": None, "ended": None}
    rec["refs"]["weeks_dir"] = f"intents/{rec['id']}/weeks"
    rec["catalogue_version"] = str(L._types().get("version", ""))
    rec["start_answers"] = {}
    ev = [{"at": opened, "kind": "series_started", "by": org["account_id"], "stage": "running"}]
    ev += [{"at": _stamp(w["opens"]), "kind": "week_opened", "agent": "north", "stage": "running", "detail": {"week_key": w["week_key"]}} for w in weeks]
    ev += [{"at": w["closed_at"], "kind": "week_closed", "by": org["account_id"], "stage": "running",
            "detail": {"week_key": w["week_key"], "items": len(w["items"])}} for w in closed]
    _write(plane, rec, _lines(rec, ev), weeks)
    out = {"intent": rec["id"], "weeks": len(weeks), "items": sum(len(w["items"]) for w in weeks)}
    if who.unknown:
        out["unknown_people"] = sorted(who.unknown)
    return out


# ---- wall cards and brainstorm ideas through the profile store ------------------------------------------------------------------

def load_cards(plane, dc: Path) -> dict:
    """operations/walls/*.json and brainstorm_ideas.json, each card through record_card: id dc-<card id>, room dc-<file stem> (the pack's
    rooms are all "main"), author a roster account. Rewriting the same cells is idempotent."""
    from sh_platform.profile import record_card
    who = Who(plane, roster_ids())
    ops = dc / "operations"
    files = sorted((ops / "walls").glob("*.json")) + [p for p in [ops / "brainstorm_ideas.json"] if p.is_file()]
    n = 0
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        room = "dc-" + f.stem.replace("_", "-")
        for c in d.get("cards") or d.get("ideas") or []:
            card = {k: c.get(k) for k in ("lane", "q1", "q2", "q3", "q4", "cluster", "shelf")}
            card.update(id=f"dc-{c['id']}", room=room, sealed=bool(c.get("sealed")), anonymous=bool(c.get("anonymous")),
                        from_interview=bool(c.get("from_interview")))
            p = None if card["anonymous"] else who.person(c.get("author"))
            if card["anonymous"]:
                card["anon_key"] = "anon-" + hashlib.md5(f"{room}:{c['id']}".encode()).hexdigest()[:10]
            else:
                card["author"] = p["account_id"] if p else c.get("author")
            record_card(plane, card, by=p["name"] if p else "the wall", source=d.get("wall") or d.get("brainstorm") or "A card on the wall")
            n += 1
    out = {"cards": n}
    if who.unknown:
        out["unknown_people"] = sorted(who.unknown)
    return out


# ---- documents on the context shelf ---------------------------------------------------------------------------------------------

TEXT = (".md", ".txt", ".eml")


def load_documents(plane, dc: Path, agent: str = "north", uploader: str = "Janet Shaw", folders: tuple[str, ...] | None = None) -> dict:
    """Every text file of the pack (not READMEs) onto North's shelf, shared. A file already there by name is left alone.
    `folders` keeps only files under those top-level pack folders (None: all)."""
    from sh_platform.context_docs.store import DocStore
    store = DocStore(plane)
    have = {d["filename"] for d in store.documents(agent)}
    added = kept = 0
    for f in sorted(dc.rglob("*")):
        if not f.is_file() or f.suffix not in TEXT or f.name == "README.md":
            continue
        rel = f.relative_to(dc)
        if folders is not None and rel.parts[0] not in folders:
            continue
        fname = "_".join(rel.parts[:-1] + (rel.stem,)) + (".txt" if f.suffix == ".eml" else f.suffix)
        if fname in have:
            kept += 1
            continue
        store.upload(agent, uploader, fname, f.read_bytes(), title=rel.stem.replace("_", " "), visibility="shared",
                     description=f"Demo cycle, {rel.parts[0]}")
        added += 1
    return {"added": added, "kept": kept}


# ---- the run ----------------------------------------------------------------------------------------------------------------

STEPS = [("silver", None, load_silver), ("gold", "gold", load_gold), ("runs and alerts", "operations", load_runs),
         ("landing", "landing", load_landing), ("intents", "initiatives", load_intents), ("weeks", "operations/weeks", load_weeks),
         ("cards", "operations", load_cards), ("documents", None, load_documents)]


def seed(data_root: Path, company_id: str = COMPANY, dc: Path = DC, log=print, steps=None) -> dict:
    """`steps` (default STEPS) lets another company load only some of the pack, e.g. tools/seed_neera.py."""
    plane = PlaneStore(data_root).plane_for(company_id)
    if not dc.is_dir():
        log(f"skip all: {dc} not there yet")
        return {}
    out = {}
    for name, folder, fn in steps or STEPS:
        if folder and not (dc / folder).is_dir():
            log(f"skip {name}: {dc / folder} not there yet")
            continue
        out[name] = fn(plane, dc)
        log(f"{name}: {out[name] if not isinstance(out[name], dict) or len(out[name]) < 8 else f'{len(out[name])} items'}")
    from sh_platform.intents import store as S
    S.rebuild_index(plane, "demo cycle")
    refresh_readonly_copy(plane)
    if (dc / "gold").is_dir():  # after the copy: the Prover reads the read-only warehouse
        out["reported"] = load_reported(plane, dc)
        log(f"reported: {out['reported']}")
    return out


def dry_copy(data_root: Path, company_id: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sh-demo-cycle-"))
    shutil.copytree(data_root / company_id, tmp / company_id, ignore=shutil.ignore_patterns("*.tmp"))
    (tmp / "_control").mkdir()
    for f in ("accounts.json", "companies.json"):
        if (data_root / "_control" / f).is_file():
            shutil.copyfile(data_root / "_control" / f, tmp / "_control" / f)
    return tmp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load the demo cycle (illustrative, synthetic) into a company plane.")
    ap.add_argument("company_id", nargs="?", default=COMPANY)
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    ap.add_argument("--dry-run", action="store_true", help="load into a temporary copy of the plane")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    if args.dry_run:
        root = dry_copy(root, args.company_id)
        print(f"dry run on a copy: {root}")
    seed(root, args.company_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
