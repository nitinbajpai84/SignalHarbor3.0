"""LI-M3: what module 3 takes from the company profile instead of asking for it again.

Everything here reads the profile through `sh_platform.profile.read(plane, viewer)`, so a sample, a figure or a person the viewer may not see is
not in what comes back (the kernel drops it, it is never a stub). Nothing here reads the raw profile file.

- `samples(...)`: the sample files already in the profile (uploaded on "Bring what you have"), each with its plain label and its bytes.
- `file_source(...)`: which source a file is, by its columns (the matcher of `intake_match`, with the pack's spellings), its name and the system
  it came from; `certain` is False when a person has to choose.
- `adopt_samples(...)`: a certain sample becomes that source's intake (`intake_store.ingest`) and is marked, so it is not asked for again. A source
  the organiser already uploaded to keeps their file.
- `figures(...)` / `adopt_figures(...)`: reported figures become benchmarks, with their label; what matches no measure waits for a person.
- `people_teams(...)` / `source_owners(...)`: owners and their teams for the plan.
"""
import logging
from pathlib import Path

from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import intake as N
from modules.m3_connect.domain import intake_match as M
from modules.m3_connect.domain import intake_store as S
from modules.m3_connect.domain import tabular as T
from sh_platform import profile
from sh_platform.context_docs.reader import Refusal
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
MARK = "from_profile.json"          # intake/<source id>/from_profile.json: {"files": [{"key", "file", "label"}]}; a restricted sample's mark is {"key"} only
A_RESTRICTED_SAMPLE = "A restricted sample"
PROFILE_BY = "Company profile"
CANDIDATES = 3


def _v(item: dict, key: str):
    c = item.get(key)
    return c.get("value") if isinstance(c, dict) else None


def _label(item: dict, key: str) -> str:
    c = item.get(key)
    return str(c.get("from") or "") if isinstance(c, dict) else ""


# ---- reading the profile, for one viewer --------------------------------------------------------------------------------------------------
def _read(plane, viewer: profile.Viewer | None) -> dict:
    """The profile for `viewer`; None is the fixed "nobody restricted" view that adoption uses, so what it keeps is the same whoever asked."""
    return profile.read_unrestricted(plane) if viewer is None else profile.read(plane, viewer)


def samples(plane, viewer: profile.Viewer | None) -> list[dict]:
    """[{key, file, system, label, data}] for each sample the viewer may see whose file can still be read."""
    out = []
    for key, s in sorted(_read(plane, viewer)["samples"].items()):
        name, ref = _v(s, "file"), (s.get("file") or {}).get("ref") or {}
        if not name or not ref.get("id"):  # a file marked restricted loses its pointer in the viewer's read
            continue
        try:
            data = profile.sample_bytes(plane, {"id": ref["id"], "name": str(name)})
        except OSError:
            log.warning("a profile sample file could not be read")
            continue
        out.append({"key": key, "file": str(name), "system": str(_v(s, "system") or ""), "label": _label(s, "file"), "data": data})
    return out


def figures(plane, viewer: profile.Viewer | None) -> list[dict]:
    """[{line, figure, unit, period_end, label}]: the reported figures the viewer may see."""
    out = []
    for f in _read(plane, viewer)["reported_figures"].values():
        line, fig = _v(f, "measure"), _v(f, "figure")
        if line and isinstance(fig, (int, float)) and not isinstance(fig, bool):
            out.append({"line": str(line), "figure": fig, "unit": _v(f, "unit"), "period_end": _v(f, "period_end"), "label": _label(f, "figure")})
    return out


def people_teams(plane) -> dict[str, str]:
    """{person (normalised): team} from the profile's people, as a reader on no restricted list sees them: the plan is shared, so a team of a
    restricted area is never in it, whoever drafted it."""
    return {I._norm(_v(p, "name")): str(_v(p, "team")) for p in _read(plane, None)["people"].values() if _v(p, "name") and _v(p, "team")}


def sample_names(plane, viewer: profile.Viewer | None) -> dict[str, tuple[str, str]]:
    """{sample key: (file name, label)} for each sample the viewer may see (no file is read)."""
    return {k: (str(_v(s, "file") or ""), _label(s, "file")) for k, s in _read(plane, viewer)["samples"].items()}


# ---- which source is this file ------------------------------------------------------------------------------------------------------------
def _plan_fields(plan: dict) -> list[dict]:
    return [{"field_id": c["field_id"], "name": c["name"], "type": c["type"]} for t in plan["tables"] for c in t["columns"]]


def file_source(plans: list[dict], filename: str, header: list[str], synonyms: dict, system: str = "") -> dict:
    """{source_id, source_name, certain, candidates: [{source_id, source_name}]}. Certain when the system the file came from names one source, or
    when one source's fields match at least two of the file's columns and no other source matches as many. Otherwise a person chooses."""
    cols = [{"name": h} for h in header]
    words = M._tokens(Path(filename).stem)
    sysname = N._norm_text(system)
    scored = []
    for p in plans:
        hits = len(M.match_columns(cols, _plan_fields(p), synonyms))
        named = bool(words & (M._tokens(p["source_name"]) | {w for t in p["tables"] for w in M._tokens(t["name"])}))
        said = bool(sysname) and sysname in (N._norm_text(p["source_id"]), N._norm_text(p["source_name"]))
        scored.append((said, hits, named, p))
    said = [s for s in scored if s[0]]
    best = max((s for s in scored if s[1] >= 2), key=lambda s: s[1], default=None)
    sure = said[0][3] if len(said) == 1 else best[3] if best and sum(s[1] == best[1] for s in scored) == 1 else None
    pick = lambda p: {"source_id": p["source_id"], "source_name": p["source_name"]}  # noqa: E731
    ranked = [s[3] for s in sorted(scored, key=lambda s: (-s[1], not s[2], s[3]["source_id"])) if s[1] or s[2]] or [s[3] for s in scored]
    return {**(pick(sure) if sure else {"source_id": None, "source_name": None}), "certain": sure is not None, "candidates": [pick(p) for p in ranked[:CANDIDATES]]}


# ---- samples become intake -------------------------------------------------------------------------------------------------------------
def _mark(folder: Path, sid: str) -> dict:
    return read_json_strict(S.source_dir(folder, sid) / MARK, dict) or {"files": []}


def adopted(folder: Path) -> dict[str, list[dict]]:
    """{source id: the profile samples used as its intake}."""
    base = Path(folder) / "intake"
    found = {p.name: _mark(folder, p.name)["files"] for p in sorted(base.iterdir()) if (p / MARK).is_file()} if base.is_dir() else {}
    return {k: v for k, v in found.items() if v}


def served(folder: Path, plane, viewer: profile.Viewer) -> dict[str, dict]:
    """{source id: {"files": [{key, file, label}], "shut": bool}}: the adopted samples as `viewer` may see them. A mark counts only while its
    sample key is still open in `profile.read_unrestricted` (a sample restricted after adoption closes), or the viewer may see that sample; a
    source with any other mark is `shut` for them: no rows, profile, name or label of it is served."""
    opened, mine = sample_names(plane, None), sample_names(plane, viewer)
    out = {}
    for sid, marks in adopted(folder).items():
        files = [{"key": f["key"], "file": (opened.get(f["key"]) or mine[f["key"]])[0], "label": (opened.get(f["key"]) or mine[f["key"]])[1]}
                 for f in marks if f["key"] in opened or f["key"] in mine]
        out[sid] = {"files": files, "shut": len(files) < len(marks)}
    return out


def shut_sources(folder: Path, plane, viewer: profile.Viewer) -> set[str]:
    return {sid for sid, v in served(folder, plane, viewer).items() if v["shut"]}


def closed_sources(folder: Path, plane) -> set[str]:
    """The sources any of whose samples is not open to everyone (`profile.read_unrestricted`): the view the shared records (the plan, the signed
    outcome) are built from, so they are the same whoever drafted them and never carry what a restricted sample produced."""
    opened = sample_names(plane, None)
    return {sid for sid, marks in adopted(folder).items() if any(f["key"] not in opened for f in marks)}


def fed_by(findings: list[dict], source_ids: set[str]) -> set[str]:
    """The measures (ids) whose findings say they are fed by any of `source_ids`."""
    return {f["measure_id"] for f in findings if set(f["sources"]) & source_ids}


def forget_closed(folder: Path, plane, sid: str) -> None:
    """A person who may see a restricted sample replaced the source's rows with their own upload: the marks of samples not open to everyone no
    longer describe those rows and go."""
    opened = sample_names(plane, None)
    with lock_for(S.source_dir(folder, sid)):
        mark = _mark(folder, sid)
        keep = [f for f in mark["files"] if f["key"] in opened]
        if keep != mark["files"]:
            write_json_atomic(S.source_dir(folder, sid) / MARK, {**mark, "files": keep})


def has_files(folder: Path, sid: str) -> bool:
    prof = S.read_profile(folder, sid)
    return bool(prof and prof.get("files"))


def take_sample(folder: Path, plan: dict, sample: dict, period: dict, synonyms: dict, clock, shared: bool = True) -> dict:
    """Uses one profile sample as `plan`'s source intake and marks it. Raises Refusal for a file that cannot be read. `shared` is False for a
    sample not open to everyone (placed by hand by a person who may see it): its mark holds the key only, never the file name or label."""
    prof = S.ingest(folder, plan, sample["file"], sample["data"], PROFILE_BY, period, synonyms, clock)
    with lock_for(S.source_dir(folder, plan["source_id"])):
        mark = _mark(folder, plan["source_id"])
        mark["files"] = [f for f in mark["files"] if f["key"] != sample["key"]] + [{"key": sample["key"], **({"file": sample["file"], "label": sample["label"]} if shared else {})}]
        write_json_atomic(S.source_dir(folder, plan["source_id"]) / MARK, mark)
    return prof


def adopt_samples(folder: Path, plans: list[dict], found: list[dict], synonyms: dict, period: dict, clock) -> list[dict]:
    """Takes every profile sample that is certainly one of `plans`' sources and is not used yet. Returns the samples left for a person to place
    (each {key, file, from, candidates}). A source the organiser uploaded to already keeps their file; its profile samples are not asked about."""
    done = {f["key"] for files in adopted(folder).values() for f in files}
    own = {p["source_id"] for p in plans if has_files(folder, p["source_id"]) and p["source_id"] not in adopted(folder)}
    ask = []
    for s in found:  # ponytail: files of one source go in name order and a newer table replaces an older; a period column would pick the month properly
        if s["key"] in done:
            continue
        try:
            header, _ = T.read_table(s["file"], s["data"])
        except (Refusal, ValueError):
            log.warning("a profile sample could not be read as a table")
            continue
        m = file_source(plans, s["file"], header, synonyms, s["system"])
        plan = next((p for p in plans if p["source_id"] == m["source_id"]), None)
        if plan is None:
            ask.append({"key": s["key"], "file": s["file"], "from": s["label"], "candidates": m["candidates"]})
        elif plan["source_id"] not in own:
            take_sample(folder, plan, s, period, synonyms, clock)
    return ask


def to_confirm(folder: Path, plans: list[dict], found: list[dict], synonyms: dict) -> list[dict]:
    """Read-only. The samples (all the viewer may see) not used as intake yet, for a person to place: [{key, file, from, candidates}]. A sample
    that certainly belongs to a source the organiser uploaded to is not asked about."""
    done = {f["key"] for files in adopted(folder).values() for f in files}
    own = {p["source_id"] for p in plans if has_files(folder, p["source_id"]) and p["source_id"] not in adopted(folder)}
    ask = []
    for s in found:
        if s["key"] in done:
            continue
        try:
            header, _ = T.read_table(s["file"], s["data"])
        except (Refusal, ValueError):
            continue
        m = file_source(plans, s["file"], header, synonyms, s["system"])
        if m["source_id"] not in own:
            ask.append({"key": s["key"], "file": s["file"], "from": s["label"], "candidates": m["candidates"]})
    return ask


# ---- figures become benchmarks -----------------------------------------------------------------------------------------------------------
def adopt_figures(folder: Path, found: list[dict], measures: list[dict], period: dict, clock) -> None:
    """Writes the profile's reported figures into benchmarks.json: a figure for a measure (the period asked for, else the newest), with its label.
    A figure a person mapped by hand, or one from an uploaded benchmark file, is never replaced; a line that matches no measure waits for a person.
    A line that names a restricted measure is dropped, not listed."""
    shut = [{**m, "restricted": False} for m in measures if m.get("restricted")]
    open_ = [m for m in measures if not m.get("restricted")]
    want = period.get("to")
    best: dict[str, dict] = {}
    for f in found:
        if N.match_measure(f["line"], shut):
            continue
        key = N.match_measure(f["line"], open_) or "?" + N._norm_text(f["line"])
        old = best.get(key)
        rank = (f["period_end"] == want, str(f["period_end"] or ""))
        if old is None or rank > (old["period_end"] == want, str(old["period_end"] or "")):
            best[key] = f
    with lock_for(folder):
        doc = S.read_benchmarks(folder)
        hand = {N._norm_text(r.get("line")) for r in doc["measures"].values() if r.get("matched") == "person"}
        old_by_line = {u["line"]: u for u in doc["unmatched"] if u.get("from_profile")}
        measures_out = {k: v for k, v in doc["measures"].items() if not v.get("from_profile")}
        unmatched = [u for u in doc["unmatched"] if not u.get("from_profile")]
        free = 1 + max([u["index"] for u in doc["unmatched"]], default=-1)
        for key, f in best.items():
            if N._norm_text(f["line"]) in hand:
                continue
            rec = {"figure": f["figure"], "unit": f["unit"], "period_end": f["period_end"] if str(f["period_end"] or "").count("-") == 2 else None,
                   "came_from": f["label"], "given_by": PROFILE_BY, "line": f["line"], "from_profile": True}
            if not key.startswith("?"):
                if key not in measures_out:  # an uploaded file's figure, or a person's mapping, stays
                    prev = doc["measures"].get(key, {})
                    measures_out[key] = {**rec, "matched": "auto", "at": prev["at"] if prev.get("from_profile") else S.now_iso(clock).isoformat()}
            else:
                prev = old_by_line.get(f["line"])
                idx = prev["index"] if prev else free
                free += 0 if prev else 1
                unmatched.append({**rec, "index": idx, "problem": None})
        new = {"file": doc["file"], "measures": measures_out, "unmatched": sorted(unmatched, key=lambda u: u["index"])}
        if new != {k: doc[k] for k in new}:
            write_json_atomic(Path(folder) / "benchmarks.json", new)


# ---- owners and teams for the plan -------------------------------------------------------------------------------------------------------
def _owner_names(text) -> list[str]:
    return [n.strip() for n in str(text or "").replace(";", ",").split(",") if n.strip()]


def source_owners(inputs: dict, source_id: str, measure_ids: list[str], teams: dict[str, str]) -> list[dict]:
    """[{name, role, team}] for a source: its catalogue data owner, and the data and process owners module 2 named for the measures it feeds. The
    team is the profile's; a person the profile does not know has an empty team (the plan then shows the name, never "not named")."""
    src = next((s for s in inputs.get("sources") or [] if I._t(s.get("Source ID")) == source_id), None)
    names = _owner_names(I._t(src.get("Data owner"))) if src else []
    for m in inputs.get("measures") or []:
        if m["id"] in measure_ids and not m.get("restricted"):
            names += [n for k in ("data", "process") for n in _owner_names((m.get("owners") or {}).get(k))]
    seen, out = set(), []
    for n in names:
        if I._norm(n) not in seen:
            seen.add(I._norm(n))
            out.append({"name": n, "role": "data owner", "team": teams.get(I._norm(n), "")})
    return out
