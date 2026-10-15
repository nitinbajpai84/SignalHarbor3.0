"""I5: the catalogue from files and documents. `scan(plane, iid)` reads every sample (CSV/XLSX: fields, types, examples) and every
document (definitions, owners, systems, rules: i5_docs) the intent has, from the thread's files and the SOW's own sources, and writes
`sow.sources` and `sow.catalogue`, each saying where it was read. Called by I2 after a file drop and by I4 before sign.

Reused: the CSV reader (sh_platform/profile/tabular.csv_rows), the zip guard and file types (context_docs/reader), the cell typing
(modules/m3_connect/domain/profile.coerce, infer_type, PERSONAL_WORDS: no example is kept for a personal-data column) and the name matching
(modules/m2_baseline/domain/catalogue.match_name). A draft never overwrites a person's edit (rule 7): a cell someone filled stays.
"""
import hashlib
import io
import logging
import re
from pathlib import PurePosixPath

from modules.m2_baseline.domain.catalogue import match_name
from modules.m3_connect.domain.profile import PERSONAL_WORDS, coerce, infer_type
from sh_platform.context_docs.reader import Refusal, _guard_office_zip, ext_of, read_segments
from sh_platform.graph.hooks import mark_dirty
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane, CrossCompanyError
from sh_platform.profile.tabular import csv_rows
from sh_platform.v1.i5_docs import read_document

log = logging.getLogger(__name__)
SAMPLE_TYPES = ("csv", "xlsx")
TYPE_ROWS = 200  # rows looked at to type a column
MAX_BYTES = 15 * 1024 * 1024


class Refused(ValueError):
    """The scan may not run: the plain words say why."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _sid(kind: str, path: str) -> str:
    stem = _slug(PurePosixPath(path).stem)[:40] or "file"
    return f"{'doc' if kind == 'document' else 'src'}-{stem}-{hashlib.sha256(path.encode()).hexdigest()[:6]}"


def _read(path) -> dict:
    try:
        return read_json_strict(path, dict) if path.exists() else {}
    except (OSError, ValueError):
        log.warning("a record could not be read for the catalogue scan")
        return {}


def _files(plane: CompanyPlane, iid: str, sow: dict, viewer=None) -> dict[str, tuple[str, str]]:
    """path (relative to the company plane) -> ("sample" | "document", source id); a file that is no table is read as a document.
    A source the SOW already lists for the path keeps its id."""
    found: dict[str, str] = {}
    ids = {str(s["sample_path"]): str(s["id"]) for s in sow.get("sources") or [] if isinstance(s, dict) and s.get("sample_path") and s.get("id")}
    for t in _read(plane.path("intents", iid, "thread.json")).get("turns") or []:
        for f in (t.get("files") or []) if isinstance(t, dict) else []:
            if isinstance(f, dict) and f.get("path"):
                found.setdefault(str(f["path"]), str(f.get("kind") or ""))
    for s in sow.get("sources") or []:
        if isinstance(s, dict) and s.get("sample_path") and s.get("kind") in ("file", "document"):
            found.setdefault(str(s["sample_path"]), "document" if s["kind"] == "document" else "sample")
    from sh_platform.v1 import c4_library
    out = {}
    for p, k in found.items():
        if not c4_library.path_ok(plane, p, viewer, check=True):  # a library path is read through its index row, as this viewer may see it
            continue
        kind = "sample" if ext_of(p) in SAMPLE_TYPES and k != "document" else "document"
        out[p] = (kind, ids.get(p) or _sid(kind, p))
    return out


def _folder_documents(plane: CompanyPlane, iid: str, viewer=None) -> tuple[list[str], set[str]]:
    """C4: the context-library items ticked for this intent that the viewer may see (no viewer: shared items only), as
    (files, landing folder names): files are paths relative to the plane, a sample folder item is read by `_landing_sources`."""
    from sh_platform.v1 import c4_library
    files, folders = [], set()
    for item in c4_library.selected(plane, iid, viewer):
        parts = PurePosixPath(item["path"]).parts
        if len(parts) == 2 and parts[0] == "landing" and plane.path(*parts).is_dir():
            folders.add(parts[1])
        else:
            files.append(item["path"])
    return files, folders


def _landing_sources(plane: CompanyPlane, known: set[str] = frozenset(), folders: set[str] = frozenset()) -> list[tuple[dict, list[dict], str]]:
    """One source per ticked landing folder (`folders`), one catalogue table per distinct header set across its files (monthly files
    share one table). Files the loader stages (`_b4_*`), files over MAX_BYTES and files the thread or the SOW already names (`known`)
    are left out."""
    root = plane.path("landing")
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and p.name in folders):
        files = sorted(f for f in folder.iterdir() if f.is_file() and ext_of(f.name) in SAMPLE_TYPES and not f.name.startswith("_b4_")
                       and f"landing/{folder.name}/{f.name}" not in known)
        if not files:
            continue
        sid, tables, rows_n, fields = f"src-{_slug(folder.name)}", {}, 0, []
        for f in files:
            try:
                if f.stat().st_size > MAX_BYTES:
                    continue
                for sheet, rows in _tables(f.name, f.read_bytes()):
                    if not rows:
                        continue
                    fs = _fields(rows)
                    key = (sheet, tuple(x["name"] for x in fs))
                    t = tables.setdefault(key, {
                        "table": _slug(f"{folder.name}_{sheet}" if sheet else folder.name), "layer": "landing",
                        "meaning": f"As received in landing/{folder.name}" + (f", sheet {sheet}" if sheet else ""),
                        "source_id": sid, "files": 0, "rows": 0,
                        "fields": [{"name": _slug(x["name"]), "type": x["type"], "meaning": "", "source_field": x["name"]} for x in fs],
                        "feeds_kpis": []})
                    t["files"] += 1
                    t["rows"] += len(rows) - 1
                    rows_n += len(rows) - 1
                    known = {y["name"] for y in fields}
                    fields += [x for x in fs if x["name"] not in known]
            except (OSError, Refusal, ValueError):
                log.warning("a landing file could not be read for the catalogue scan")
        if not tables:
            continue
        seen: dict[str, int] = {}
        for t in tables.values():  # two header sets in one folder (a column renamed mid-year) keep one table name with a suffix
            name = t["table"]
            if name in seen:
                seen[name] += 1
                t["table"] = f"{name}_v{seen[name]}"
                t["meaning"] += " (a later file set with different columns)"
            else:
                seen[name] = 1
        cat = [{k: v for k, v in t.items() if k not in ("files", "rows")} for t in tables.values()]
        holds = f"{len(files)} file{'s' if len(files) != 1 else ''}, {rows_n} rows, {len(fields)} columns"
        src = {"id": sid, "name": folder.name.replace("_", " "), "kind": "file", "holds": holds,
               "sample_path": f"landing/{folder.name}", "owner": "", "fields": fields}
        out.append((src, cat, f"landing/{folder.name}"))
    return out


_STOP = {"the", "a", "an", "and", "of", "file", "files", "monthly", "data", "system", "feed", "already", "folder", "landing"}


def _words(text: str) -> set[str]:
    return {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in _slug(text).split("_") if w and w not in _STOP}


def _merge_named(sources: list[dict], catalogue: list[dict]) -> None:
    """A source North wrote from the person's words ("the bank cash balances") and the landing folder that holds it ("bank_cash") become
    one source: North's id stays (the KPIs point at it), the folder's fields, holds and path move across, the folder's tables repoint."""
    folders = [s for s in sources if isinstance(s, dict) and str(s.get("id") or "").startswith("src-")
               and str(s.get("sample_path") or "").startswith("landing/")]
    named = [s for s in sources if isinstance(s, dict) and s.get("kind") != "document" and s not in folders]
    taken: set[str] = set()
    for f in folders:  # each folder joins the named source that already holds its path, else the one sharing most words
        n = next((n for n in named if n.get("sample_path") == f["sample_path"] or f["sample_path"] in (n.get("paths") or [])), None)
        if n is None:
            nw = {id(x): _words(x.get("name") or "") | _words(x.get("holds") or "") for x in named}
            fw, last = _words(f["name"]), (_words(str(f["name"]).split()[-1]) or {""}).pop()
            score, n = max(((len(nw[id(x)] & fw) + (1 if last and last in nw[id(x)] else 0), x) for x in named),
                           key=lambda t: t[0], default=(0, None))
            if score == 0:
                continue
        taken.add(f["id"])
        if not n.get("sample_path"):
            n["sample_path"] = f["sample_path"]
        n["paths"] = sorted(set(n.get("paths") or []) | {f["sample_path"]})
        if not n.get("holds") or n.get("holds") == f.get("holds"):
            n["holds"] = f.get("holds")
        known = {x.get("name") for x in n.get("fields") or []}
        n["fields"] = (n.get("fields") or []) + [x for x in f.get("fields") or [] if x.get("name") not in known]
        n["kind"] = "file"
        for c in catalogue:
            if c.get("source_id") == f["id"]:
                c["source_id"] = n["id"]
    sources[:] = [s for s in sources if not (isinstance(s, dict) and s.get("id") in taken)]


LINK_PROMPT = ("You map each KPI of an intent of work to the sources holding the data it is worked out from (a return needs positions, "
               "transactions and prices; a fee ratio needs fees and positions; a concentration needs positions). Answer with one JSON object "
               'only: {"links": {"<kpi code>": ["<source id>", ...]}}. Use only the source ids given; name every source the KPI needs.')


def _link_kpis(rt, sow: dict) -> None:
    """KPIs with no sources yet get them: from the model through the runtime when it is on, else by shared words; marked on the KPI."""
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code") and not k.get("source_ids")]
    srcs = [s for s in sow.get("sources") or [] if isinstance(s, dict) and s.get("id") and s.get("kind") != "document"]
    if not kpis or not srcs:
        return
    ids = {s["id"] for s in srcs}
    links: dict[str, list[str]] = {}
    model = getattr(rt, "model", None)
    from sh_platform.v1.router import route  # R1
    model = route(model, "north", "link_kpis", str(sow.get("intent_id") or ""), want_json=True)  # R1
    if model is not None:
        try:
            import json as _json
            from sh_platform.agents.loop import run_agent
            from sh_platform.agents.registry import ToolRegistry
            from sh_platform.v1.egress_fit import fit
            from sh_platform.v1.i2_north import OpenGate
            alias = {f"source {chr(ord('a') + i)}": s["id"] for i, s in enumerate(srcs[:26])}
            back = {v: k for k, v in alias.items()}
            kalias = {f"kpi {chr(ord('a') + i)}": k["code"] for i, k in enumerate(kpis[:26])}
            kback = {v: k for k, v in kalias.items()}
            ctx = fit({"kpis": [{"code": kback[k["code"]], "name": k.get("name"), "definition": k.get("definition")} for k in kpis[:26]],
                       "sources": [{"id": back[s["id"]], "name": s.get("name"), "holds": s.get("holds"),
                                    "fields": [f.get("name") for f in (s.get("fields") or [])[:40]]} for s in srcs[:26]]})
            res = run_agent(model, ToolRegistry(OpenGate()), getattr(rt, "company_id", "") or "", "m1_intent", "North", LINK_PROMPT, ctx,
                            "Which sources supply each KPI?", recorder=getattr(rt, "recorder", None))
            a, b = res.text.find("{"), res.text.rfind("}")
            got = _json.loads(res.text[a:b + 1]) if res.status == "done" and 0 <= a < b else {}
            links = {kalias.get(str(c), str(c)): [alias.get(x, x) for x in v if alias.get(x, x) in ids]
                     for c, v in (got.get("links") or {}).items() if isinstance(v, list)}
        except Exception:  # noqa: BLE001 - a failed call falls back to words, below
            log.warning("the KPI-to-source link could not be asked of the model")
            links = {}
    by = "North" if links else "shared words (rules only)"
    for k in kpis:
        got = links.get(k["code"])
        if not got:
            kw = _words(k.get("name") or "") | _words(k.get("definition") or "")
            got = [s["id"] for s in srcs if kw & (_words(s.get("name") or "") | _words(s.get("holds") or ""))]
        k["source_ids"] = got
        k["sources_by"] = by


def _gold_tables(sow: dict) -> None:
    """One gold table per KPI that has a source, named after the KPI code (k01): the mapping sheet fills it, Flow builds it, Consume reads
    it. Added once; a person's edits to it are kept."""
    have = {c.get("table") for c in sow.get("catalogue") or [] if isinstance(c, dict)}
    for k in sow.get("kpis") or []:
        if not (isinstance(k, dict) and k.get("code") and k.get("source_ids")):
            continue
        t = str(k["code"]).lower()
        if t in have:
            continue
        sow["catalogue"].append({"table": t, "layer": "gold", "meaning": f"{k.get('name') or k['code']}, one row per {k.get('period') or 'period'}",
                                 "source_id": k["source_ids"][0], "feeds_kpis": [k["code"]],
                                 "fields": [{"name": "period", "type": "text", "meaning": "The period the figure is for", "source_field": ""},
                                            {"name": "value", "type": "number", "meaning": k.get("definition") or k.get("name") or "", "source_field": ""}]})
        have.add(t)


def _tables(name: str, data: bytes) -> list[tuple[str | None, list[list]]]:
    """(sheet or None, rows) per table in the file."""
    if ext_of(name) == "csv":
        return [(None, csv_rows(data))]
    _guard_office_zip(data, ".xlsx")
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        return [(ws.title, [list(r) for r in ws.iter_rows(values_only=True) if any(v not in (None, "") for v in r)]) for ws in wb.worksheets]
    finally:
        wb.close()


def _fields(rows: list[list]) -> list[dict]:
    header, body = [str(h or "").strip() for h in rows[0]], rows[1:1 + TYPE_ROWS]
    out = []
    for i, h in enumerate(header):
        if not h:
            continue
        vals = [coerce(r[i]) if i < len(r) else None for r in body]
        ex = next((v for v in vals if v is not None), None)
        personal = any(w in re.split(r"[^a-z]+", h.lower()) for w in PERSONAL_WORDS)
        out.append({"name": h, "type": infer_type(vals), "example": "" if personal or ex is None else str(ex)[:60], "meaning": ""})
    return out


def _sample(path: str, data: bytes, sid: str) -> tuple[dict, list[dict]]:
    name = PurePosixPath(path).name
    tables = [(sheet, rows) for sheet, rows in _tables(name, data) if rows]
    many = len(tables) > 1
    fields, catalogue, holds = [], [], []
    for sheet, rows in tables:
        fs = _fields(rows)
        fields += [{**f, "name": f"{sheet}.{f['name']}"} for f in fs] if many else fs
        where = f"{name}, sheet {sheet}" if sheet else name
        holds.append(f"{len(rows) - 1} rows of {len(fs)} columns{f' (sheet {sheet})' if many else ''}")
        catalogue.append({"table": _slug(f"{PurePosixPath(path).stem}_{sheet}" if many else PurePosixPath(path).stem), "layer": "landing",
                          "meaning": f"As received in {where}", "source_id": sid,
                          "fields": [{"name": _slug(f["name"]), "type": f["type"], "meaning": "", "source_field": f["name"]} for f in fs],
                          "feeds_kpis": []})
    source = {"id": sid, "name": PurePosixPath(path).stem.replace("_", " "), "kind": "file", "holds": "; ".join(holds) or "No rows",
              "sample_path": path, "owner": "", "fields": fields}
    return source, catalogue


def _document(rt, path: str, data: bytes, sid: str) -> dict:
    name = PurePosixPath(path).name
    text = "\n".join(t for _, t in read_segments(name, data))
    head = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), "")
    read = read_document(rt, name, text)
    return {"id": sid, "name": PurePosixPath(path).stem.replace("_", " "), "kind": "document", "holds": head[:120] or "Document text",
            "sample_path": path, "owner": "", "fields": [], "read": read}


def _keep(old: dict, new: dict) -> dict:
    """New draft cells only where the old one is empty; `read` (what was read) is always the scan's."""
    out = {**new, **{k: v for k, v in old.items() if v not in (None, "", []) and k != "read"}}
    if old.get("fields") and new.get("fields"):
        mine = {f.get("name"): f for f in old["fields"] if isinstance(f, dict)}
        out["fields"] = [_keep(mine.get(f["name"], {}), f) for f in new["fields"]] + \
                        [f for n, f in mine.items() if n not in {x["name"] for x in new["fields"]}]
    return out


def _cross_fill(sources: list[dict], catalogue: list[dict], kpis: list[dict], unclear: list[dict]) -> int:
    """Definitions fill empty field meanings, owners fill empty source owners, KPIs name the tables of their sources, and a term two
    documents define differently becomes an unclear point (never a guess). Returns the number of unclear points added."""
    defs: dict[str, list[dict]] = {}
    for s in sources:
        for d in (s.get("read") or {}).get("definitions") or []:
            defs.setdefault(match_name(d.get("term") or ""), []).append(d)
    # ponytail: a field takes the first definition whose term matches its column name, in any file; match on the table heading too if a
    # shared column name (currency, say) picks up another table's meaning.
    for f in [f for s in sources for f in s.get("fields") or []] + [f for c in catalogue for f in c.get("fields") or []]:
        d = (defs.get(match_name(f.get("source_field") or f.get("name") or "")) or [None])[0]
        if d and not f.get("meaning"):
            f["meaning"] = f"{d['text']} (read in {d['file']})"
    owners = {match_name(o.get("what") or ""): o for s in sources for o in (s.get("read") or {}).get("owners") or []}
    for s in sources:
        o = owners.get(match_name(s.get("name") or ""))
        if o and not s.get("owner") and s.get("kind") != "document":
            s["owner"] = o["who"]
    for c in catalogue:
        if c.get("layer") == "gold":
            continue  # a gold table feeds the one KPI it was made for
        codes = [k["code"] for k in kpis if isinstance(k, dict) and c.get("source_id") in (k.get("source_ids") or [])]
        c["feeds_kpis"] = list(dict.fromkeys((c.get("feeds_kpis") or []) + codes))
    have, added = {u.get("id") for u in unclear if isinstance(u, dict)}, 0
    for term, ds in defs.items():
        said = {re.sub(r"[^a-z0-9 ]", "", d["text"].lower()).strip(): d for d in ds}
        files = sorted({d["file"] for d in said.values()})
        uid = f"i5-{hashlib.sha256(term.encode()).hexdigest()[:8]}"
        if term and len(said) > 1 and len(files) > 1 and uid not in have:
            unclear.append({"id": uid, "question": f"{' and '.join(files[:2])} define {ds[0]['term']} differently. Which one is right?",
                            "about": ds[0]["term"], "who_can_settle": "", "settled": False, "answer": ""})
            added += 1
    return added


def scan(plane: CompanyPlane, iid: str, rt=None, viewer=None) -> dict:
    """Reads the intent's files into the SOW. Returns {sources, tables, unclear_added, read: [{file, kind, by}], skipped: [{file, why}], sow}.
    `rt`: a Runtime (sh_platform.build.agents.runtime); built from the plane when None (the model is off with SH_MODEL_PROVIDER=off).
    Besides the thread's and the SOW's files, only the context-library items ticked for the intent are read (C4), as `viewer` may see them."""
    path = plane.path("intents", iid, "sow.json")
    sow = _read(path)
    if not sow:
        raise Refused("This intent has no intent of work yet.")
    if sow.get("state") == "signed":
        raise Refused("The intent of work is signed, so its catalogue cannot change.")
    files = _files(plane, iid, sow, viewer)
    ticked, folders = _folder_documents(plane, iid, viewer)
    for p in ticked:
        kind = "sample" if ext_of(p) in SAMPLE_TYPES else "document"
        files.setdefault(p, (kind, _sid(kind, p)))
    if rt is None and (any(k == "document" for k, _ in files.values())
                       or any(not k.get("source_ids") for k in sow.get("kpis") or [] if isinstance(k, dict))):
        from sh_platform.build.agents.runtime import runtime_for_plane
        rt = runtime_for_plane(plane)
    sources, catalogue, read, skipped = [], [], [], []
    for src, cat, where in _landing_sources(plane, set(files), folders):  # the files a company drops in its landing folders, one source per folder
        sources.append(src)
        catalogue += cat
        read.append({"file": where, "kind": "sample", "by": "Read on this machine"})
    for p, (kind, sid) in files.items():
        try:
            f = plane.path(*PurePosixPath(p.replace("\\", "/")).parts)
            if f.stat().st_size > MAX_BYTES:
                raise Refusal("The file is too large to read here.")
            data = f.read_bytes()
            if kind == "sample":
                src, cat = _sample(p, data, sid)
                sources.append(src)
                catalogue += cat
                read.append({"file": p, "kind": kind, "by": "Read on this machine"})
            else:
                src = _document(rt, p, data, sid)
                sources.append(src)
                read.append({"file": p, "kind": kind, "by": src["read"]["by"]})
        except (CrossCompanyError, OSError, Refusal, ValueError) as e:
            why = str(e) if isinstance(e, Refusal) else "The file could not be found or read."
            skipped.append({"file": p, "why": why})
    with lock_for(path):
        sow = _read(path)  # again: a person may have edited it while the files were read
        if sow.get("state") == "signed":
            raise Refused("The intent of work is signed, so its catalogue cannot change.")
        old_s = {s.get("id"): s for s in sow.get("sources") or [] if isinstance(s, dict)}
        old_c = {c.get("table"): c for c in sow.get("catalogue") or [] if isinstance(c, dict)}
        new_s = [_keep(old_s.get(s["id"], {}), s) for s in sources]
        new_c = [_keep(old_c.get(c["table"], {}), c) for c in catalogue]
        ids, tables = {s["id"] for s in new_s}, {c["table"] for c in new_c}
        sow["sources"] = [s for s in sow.get("sources") or [] if isinstance(s, dict) and s.get("id") not in ids] + new_s
        sow["catalogue"] = [c for c in sow.get("catalogue") or [] if isinstance(c, dict) and c.get("table") not in tables] + new_c
        sow["unclear"] = list(sow.get("unclear") or [])
        _merge_named(sow["sources"], sow["catalogue"])
        _link_kpis(rt, sow)
        _gold_tables(sow)
        added = _cross_fill(sow["sources"], sow["catalogue"], sow.get("kpis") or [], sow["unclear"])
        write_json_atomic(path, sow)
    mark_dirty(plane)
    return {"sources": len(new_s), "tables": len(new_c), "unclear_added": added, "read": read, "skipped": skipped, "sow": sow}
