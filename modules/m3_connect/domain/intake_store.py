"""M3-P02 files: requests.json, the link index, the uploaded files, rows.json, profile.json and benchmarks.json (shapes: domain/intake.py).

The link follows module 2's pattern (`modules/m2_baseline/store/requests.py`, copied, not imported): "di-<request id>-<secret>", only its SHA-256
hash is stored, it expires, can be withdrawn, and a new one replaces the old. The control index (<data root>/_control/m3_intake_index.json) maps a
request id to its company and assessment, so a link with no account finds its company; it holds no token and no hash.
Files stay in the plane under intake/<source_id>/; a source id is used in a path only after it matches the catalogue and a plain pattern.
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.m3_connect.domain import intake as N
from modules.m3_connect.domain import intake_match as M
from modules.m3_connect.domain import profile as P
from modules.m3_connect.domain import tabular as T
from sh_platform.context_docs.reader import Refusal, ext_of, safe_name
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

UNREADABLE = "Intake files could not be read, so nothing was changed. Please ask your administrator."
_SOURCE = re.compile(r"[A-Za-z0-9_-]{1,40}")
STATES = ("sent", "opened", "arrived")
MAX_UNMATCHED = 200   # a benchmark file with more lines Lens could not match than this is not a benchmark file


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


class LinkError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class WrongState(Exception):
    pass


def _read(path: Path, kind: type, empty):
    try:
        got = read_json_strict(path, kind)
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None
    return empty if got is None else got


def valid_source(source_id) -> bool:
    return isinstance(source_id, str) and _SOURCE.fullmatch(source_id) is not None


def now_iso(clock) -> datetime:
    return datetime.fromtimestamp(clock(), timezone.utc)


# ---- the control index ------------------------------------------------------------------------------------------------------------
class Index:
    def __init__(self, data_root):
        self._path = Path(data_root).resolve() / "_control" / "m3_intake_index.json"

    def add(self, request_id: str, company_id: str, assessment_id: str) -> None:
        with lock_for(self._path):
            data = _read(self._path, dict, {})
            data[request_id] = {"company_id": company_id, "assessment_id": assessment_id}
            write_json_atomic(self._path, data)

    def lookup(self, request_id: str) -> dict | None:
        with lock_for(self._path):
            found = _read(self._path, dict, {}).get(request_id)
        return found if isinstance(found, dict) and set(found) == {"company_id", "assessment_id"} else None


# ---- requests ---------------------------------------------------------------------------------------------------------------------
class Requests:
    def __init__(self, folder: Path, clock):
        self.dir, self._clock, self._file = folder, clock, folder / "requests.json"

    def now(self) -> datetime:
        return now_iso(self._clock)

    def all(self) -> list[dict]:
        return _read(self._file, list, [])

    def get(self, request_id: str) -> dict:
        found = next((r for r in self.all() if r.get("id") == request_id), None)
        if found is None:
            raise LookupError("no request")
        return found

    def for_source(self, source_id: str) -> dict | None:
        return next((r for r in self.all() if r.get("source_id") == source_id), None)

    def _change(self, request_id: str, change) -> dict:
        with lock_for(self.dir):
            rows, out = self.all(), None
            for i, r in enumerate(rows):
                if r["id"] == request_id:
                    out = rows[i] = change(dict(r))
            if out is None:
                raise LookupError("no request")
            write_json_atomic(self._file, rows)
            return out

    def sync(self, plans: list[dict], period: dict, index: Index, company_id: str, assessment_id: str) -> list[tuple[dict, str | None]]:
        """One request per source in `plans`. A source that has one keeps its link and is brought up to date; a new one gets a link, returned
        once and never stored. Returns [(request, token or None)]."""
        with lock_for(self.dir):
            rows, out, now = self.all(), [], self.now()
            for plan in plans:
                at = next((i for i, r in enumerate(rows) if r["source_id"] == plan["source_id"]), None)
                if at is not None:
                    rows[at] = N.refresh(rows[at], plan, period)
                    out.append((rows[at], None))
                    continue
                req, token = N.new_request(plan, period, now)
                rows.append(req)
                index.add(req["id"], company_id, assessment_id)
                out.append((req, token))
            write_json_atomic(self._file, rows)
            return out

    def relink(self, request_id: str, index: Index, company_id: str, assessment_id: str) -> tuple[dict, str]:
        token = N.new_token(request_id)
        now = self.now()
        row = self._change(request_id, lambda r: {**r, "token_hash": N.digest(token), "state": "sent" if r["state"] != "arrived" else "arrived",
                                                   "sent_at": now.isoformat(), "reminders": [], "revoked_at": None,
                                                   "expires_at": (now + timedelta(hours=N.LINK_HOURS)).isoformat()})
        index.add(request_id, company_id, assessment_id)
        return row, token

    def revoke(self, request_id: str, will_not_send: bool = False, by: dict | None = None) -> dict:
        """Withdraws the link. `will_not_send` also records that the owner will not send (state "will_not_send", with who, `by` =
        {account_id, name}, and when); either way the request blocks nothing. Asking again (relink) reopens it. A request whose files already
        arrived keeps its state."""
        def change(r: dict) -> dict:
            now = self.now().isoformat()
            mark = {"state": "will_not_send", "will_not_send_by": by, "will_not_send_at": now} if will_not_send and r["state"] != "arrived" else {}
            return {**r, "revoked_at": r["revoked_at"] or now, **mark}
        return self._change(request_id, change)

    def remind(self, request_id: str) -> dict:
        def change(r):
            if r["state"] == "arrived":
                raise WrongState("Their files are in, so there is nothing to remind them about.")
            return {**r, "reminders": [*r["reminders"], self.now().isoformat()]}
        return self._change(request_id, change)

    def ground(self, request_id: str, token: str) -> dict:
        """The request for a token that is good right now (LinkError otherwise; only a holder of the real secret learns why)."""
        found = next((r for r in self.all() if r.get("id") == request_id), None)
        if found is None or not hmac.compare_digest(found["token_hash"], N.digest(token)):
            raise LinkError("link_invalid", "This link is not working. Please ask for a new one.")
        gone = N.link_state(found, self.now())
        if gone != "open":
            raise LinkError("link_gone", N.LINK_GONE[gone])
        return found

    def opened(self, request_id: str) -> dict:
        return self._change(request_id, lambda r: {**r, "state": "opened", "opened_at": self.now().isoformat()} if r["state"] == "sent" else r)

    def arrived(self, source_id: str, by: dict | None = None) -> None:
        """A file came in. On a request marked "will not send" that reopens it: who and when are kept (`reopened_by`, `reopened_at`)."""
        r = self.for_source(source_id)
        if r is not None:
            def change(x: dict) -> dict:
                now = self.now().isoformat()
                again = {"reopened_by": by, "reopened_at": now} if x["state"] == "will_not_send" else {}
                return {**x, "state": "arrived", "arrived_at": now, **again}
            self._change(r["id"], change)


# ---- one source's files ----------------------------------------------------------------------------------------------------------
def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def source_dir(folder: Path, source_id: str) -> Path:
    if not valid_source(source_id):
        raise LookupError("no source")
    return folder / "intake" / source_id


def read_profile(folder: Path, source_id: str) -> dict | None:
    return _read(source_dir(folder, source_id) / "profile.json", dict, None)


def _pick_table(plan: dict, header: list[str], filename: str, synonyms: dict) -> tuple[dict | None, dict]:
    """The catalogue table this file is, by how many of its columns match the table's fields (else the only table, else None)."""
    cols = [{"name": h} for h in header]
    best, best_hits = None, 0
    for t in plan["tables"]:
        hits = M.match_columns(cols, [{"field_id": c["field_id"], "name": c["name"], "type": c["type"]} for c in t["columns"]], synonyms)
        if len(hits) > best_hits:
            best, best_hits = (t, hits), len(hits)
    if best:
        return best
    only = plan["tables"][0] if len(plan["tables"]) == 1 else None
    return only, {}


def ingest(folder: Path, plan: dict, filename: str, data: bytes, by: str, period: dict, synonyms: dict, clock) -> dict:
    """Reads, matches and profiles one uploaded file for a source, keeps it, and returns the source's profile. Raises Refusal for a bad file."""
    sid = plan["source_id"]
    kind = ext_of(filename)
    header, raw = T.read_table(filename, data)
    table, hits = _pick_table(plan, header, filename, synonyms)
    if table is not None and not hits:
        hits = M.match_columns([{"name": h} for h in header], [{"field_id": c["field_id"], "name": c["name"], "type": c["type"]} for c in table["columns"]], synonyms)
    flagged = {c["name"] for t in plan["tables"] for c in t["columns"] if c["personal"]}
    personal = {h for h, m in hits.items() if any(c["field_id"] == m["field_id"] and c["personal"] for t in plan["tables"] for c in t["columns"])} | \
               {h for h in header if h in flagged} | ({h for h in header if h not in hits} if plan.get("personal_source") else set())  # a source holding personal data: nothing unmatched is shown
    prof = P.profile_table(header, raw, personal)
    for c in prof["columns"]:
        m = hits.get(c["name"])
        c["field_id"], c["match"] = (m["field_id"], {"confidence": m["confidence"], "reasons": m["reasons"]}) if m else (None, None)
    fname = f"{hashlib.sha256(data).hexdigest()[:8]}_{safe_name(filename)}"  # no Windows device name (CON.csv) can be a file name; a changed file is a new name
    typed = P.rows_of(header, raw)
    tb = {"file": fname, "table_id": table["table_id"] if table else None, "name": table["name"] if table else None}
    when = now_iso(clock).isoformat()
    with lock_for(folder):
        root = source_dir(folder, sid)
        rows_doc = _read(root / "rows.json", dict, {"source_id": sid, "tables": []})
        old = _read(root / "profile.json", dict, {"files": [], "tables": []})
        keep_rows = [t for t in rows_doc["tables"] if t["file"] != fname]
        keep_prof = [t for t in old["tables"] if t["file"] != fname]
        files = [f for f in old["files"] if f["file"] != fname] + [{"file": fname, "kind": kind, "table_id": tb["table_id"], "rows": prof["row_count"], "by": by, "at": when}]
        keep_rows.append({**tb, "columns": [{"name": c["name"], "type": c["type"], "field_id": c["field_id"], "personal": c["personal"]} for c in prof["columns"]], "rows": typed})
        keep_prof.append({**tb, **{k: v for k, v in prof.items() if k != "duplicate_key"}, "duplicate_key": prof["duplicate_key"]})
        _write_bytes(root / "files" / fname, data)
        # one table per catalogue table: a newer file for the same table replaces the older one's rows
        if tb["table_id"]:
            keep_rows = [t for t in keep_rows if t["table_id"] != tb["table_id"] or t["file"] == fname]
            keep_prof = [t for t in keep_prof if t["table_id"] != tb["table_id"] or t["file"] == fname]
        profile = _assemble(sid, plan, keep_prof, files, period, when)
        write_json_atomic(root / "rows.json", {"source_id": sid, "tables": keep_rows})
        write_json_atomic(root / "profile.json", profile)
    return profile


def _assemble(sid: str, plan: dict, tables: list[dict], files: list[dict], period: dict, when: str) -> dict:
    expected, gaps_for, absent = [], [], []
    got_tables = {t["table_id"] for t in tables if t["table_id"]}
    for t in plan["tables"]:
        here = next((x for x in tables if x["table_id"] == t["table_id"]), None)
        if t["columns"] and here is None and t["table_id"] not in got_tables:
            absent.append(t)
            continue
        for c in t["columns"]:
            found = next((k["name"] for k in (here or {"columns": []})["columns"] if k.get("field_id") == c["field_id"]), None)
            e = {"field_id": c["field_id"], "name": c["name"], "table_id": t["table_id"], "table": t["name"], "measures": [m["id"] for m in c["measures"]], "found_as": found}
            expected.append(e)
            gaps_for.append(e)
    gaps = P.gaps_for(sid, tables, gaps_for, period)
    for t in absent:
        gaps.append({"kind": "file_not_arrived", "field_id": None, "column": None, "table": t["name"],
                     "measures": sorted({m["id"] for c in t["columns"] for m in c["measures"]}), "text": f"Nothing has arrived yet for “{t['name']}”."})
        expected += [{"field_id": c["field_id"], "name": c["name"], "table_id": t["table_id"], "table": t["name"], "measures": [m["id"] for m in c["measures"]], "found_as": None} for c in t["columns"]]
    return {"source_id": sid, "period": period, "updated_at": when, "files": files, "tables": tables, "expected": expected, "gaps": gaps}


def redact(profile: dict, visible_fields: set[str] | None, limits: dict[str, list[str] | None], viewer) -> dict:
    """The profile for one reader: a column that matched a field the reader may not see keeps only a placeholder name (no type, fill rate or
    samples), and its gaps and expected rows are left out. `limits` = {field id: the field's own list}."""
    hide = {fid for fid in {c["field_id"] for t in profile["tables"] for c in t["columns"] if c.get("field_id")} | {e["field_id"] for e in profile["expected"]}
            if (visible_fields is not None and fid not in visible_fields) or not N.may_see_field(limits.get(fid), viewer)}
    tables = [{**t, "columns": [{"name": N.RESTRICTED_COLUMN, "restricted": True} if c.get("field_id") in hide else c for c in t["columns"]]} for t in profile["tables"]]
    return {**profile, "tables": tables, "expected": [e for e in profile["expected"] if e["field_id"] not in hide],
            "gaps": [g for g in profile["gaps"] if g.get("field_id") not in hide]}


# ---- benchmarks ------------------------------------------------------------------------------------------------------------------
def read_benchmarks(folder: Path) -> dict:
    return _read(folder / "benchmarks.json", dict, {"file": None, "measures": {}, "unmatched": []})


def save_benchmarks(folder: Path, filename: str, data: bytes, measures: list[dict], by: str, clock, only: set[str] | None = None) -> dict:
    header, rows = T.read_table(filename, data)
    when = now_iso(clock)
    try:
        matched, unmatched = N.parse_benchmarks(header, rows, measures, by, when)
    except ValueError as e:
        raise Refusal(str(e)) from None
    with lock_for(folder):
        doc = read_benchmarks(folder)
        if only is not None:  # an owner's link: only the measures of their own source; their other lines are added to the list, not swapped in
            matched = {k: v for k, v in matched.items() if k in only}
            base = 1 + max([u["index"] for u in doc["unmatched"]], default=-1)
            unmatched = doc["unmatched"] + [{**u, "index": base + i} for i, u in enumerate(unmatched)]
        # a figure a person mapped by hand is never overwritten by a file (rule 7)
        for mid, rec in matched.items():
            if doc["measures"].get(mid, {}).get("matched") != "person":
                doc["measures"][mid] = rec
        doc = {"file": {"name": safe_name(filename), "by": by, "at": when.isoformat()}, "measures": doc["measures"], "unmatched": unmatched[:MAX_UNMATCHED]}
        write_json_atomic(folder / "benchmarks.json", doc)
    return doc


def map_benchmark(folder: Path, index: int, measure_id: str, measures: list[dict], by: str, clock) -> dict:
    live = {m["id"] for m in measures if not m.get("restricted")}
    if measure_id not in live:
        raise LookupError(N.NO_MEASURE)
    with lock_for(folder):
        doc = read_benchmarks(folder)
        line = next((u for u in doc["unmatched"] if u["index"] == index), None)
        if line is None:
            raise LookupError("no line")
        if line.get("figure") is None:
            raise WrongState("That line has no figure, so it cannot be used.")
        doc["measures"][measure_id] = {"figure": line["figure"], "unit": line["unit"], "period_end": line["period_end"], "came_from": line["came_from"],
                                       "given_by": line["given_by"], "line": line["line"], "matched": "person", "at": now_iso(clock).isoformat(), "mapped_by": by}
        doc["unmatched"] = [u for u in doc["unmatched"] if u["index"] != index]
        write_json_atomic(folder / "benchmarks.json", doc)
    return doc
