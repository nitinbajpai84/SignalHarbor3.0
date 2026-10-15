"""M3-P02 intake: what to ask each source owner for, what came back, and the figures the customer already reports.

THE SHAPES OTHER PACKAGES READ (everything is JSON in `plane.path("intents", "m3_connect", "assessments", <assessment_id>)`):

`intake/<source_id>/rows.json`   the rows P03 runs rules on. Typed: None for an empty cell, int, float, bool, ISO date text "YYYY-MM-DD", or text.
    {"source_id": str, "tables": [{"file": str, "table_id": str | null, "name": str | null,
        "columns": [{"name": str, "type": "string|integer|decimal|date|boolean|unknown", "field_id": str | null, "personal": bool}],
        "rows": [{<column name>: value, ...}]}]}
    A table is one uploaded file (a second upload with the same file name replaces it). `table_id` / `field_id` are the catalogue's Item ID and
    Field ID when the file's columns matched; `name` is the catalogue's table name. Rows never go to the model.

`intake/<source_id>/profile.json`
    {"source_id", "period": {"from", "to", "label"}, "updated_at",
     "files": [{"file", "kind": "xlsx|csv|json", "table_id", "rows", "by", "at"}],
     "tables": [{"file", "table_id", "name", "row_count", "date_column", "date_range": {"from", "to"} | null, "series": bool,
                 "duplicate_key": {"columns": [..], "duplicates": int} | null,
                 "columns": [{"name", "type", "non_empty", "nulls", "fill": 0..1, "distinct", "personal", "samples": [..],   # never for personal
                              "field_id", "match": {"confidence": "low|medium|high", "reasons": [..]} | null}]}],
     "expected": [{"field_id", "name", "table_id", "table": str, "measures": [measure id], "found_as": column name | null}],
     "gaps": [{"kind": "file_not_arrived|missing_column|half_empty|some_empty|period_short", "text", "field_id", "column", "measures": [ids]}]}
    A column named in `gaps` is a gap for every measure listed. `half_empty` means below 80% full; `some_empty` has any empty cell above that.

`benchmarks.json`
    {"file": {"name", "by", "at"} | null,
     "measures": {<measure id>: {"figure": number, "unit": str | null, "period_end": "YYYY-MM-DD" | null, "came_from": str | null,
                                 "given_by": str, "line": str (the measure as the customer wrote it), "matched": "auto|person", "at"}},
     "unmatched": [{"index": int, "line", "figure": number | null, "unit", "period_end", "came_from", "given_by", "problem": str | null}]}

`requests.json`   a list, one per source asked: {"id", "source_id", "source_name", "owner", "zone", "period", "tables": [{"table_id", "name",
    "row_means", "columns": [{"field_id", "name", "meaning", "type", "measures": [{"id","name"}], "limit": [names] | null, "personal"}]}],
    "benchmarks": [{"measure_id", "measure_name", "ask"}], "token_hash", "state": "sent|opened|arrived", "sent_at", "expires_at", "revoked_at",
    "opened_at", "arrived_at", "reminders": [iso]}.  The link token itself is never stored, only its SHA-256 hash.

Who may see what (module 2's rule, M2-E3): a catalogue field with its own "Who may see it" cell is shown only to the people on it and to the
sponsor and head of data; for everyone else the field's column, its fill rate and its samples are hidden ("A restricted column").
"""
import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher

from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import intake_match as M
from modules.m3_connect.domain.steps import register

LINK_HOURS = 14 * 24
TOKEN = re.compile(r"di-([0-9a-f]{32})-([A-Za-z0-9_-]{43})")
ZONES = ("p1", "p2")
RESTRICTED_COLUMN = "A restricted column"
OPEN_CLASSES = {"neither", "none", "no", "not personal", "not_personal", "n/a"}  # module 2: "Neither"; a blank class is the source's own answer
ADMIN = I.SYSTEM  # the full catalogue, to build a request; every read is filtered for the reader
LINK_GONE = {"revoked": "This link was withdrawn. Please ask for a new one.", "expired": "This link has expired. Please ask for a new one."}
NO_MEASURE = "That measure is not one of this assessment's measures."


def new_token(request_id: str) -> str:
    return f"di-{request_id}-{secrets.token_urlsafe(32)}"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def link_state(req: dict, now: datetime) -> str:
    if req.get("revoked_at"):
        return "revoked"
    return "expired" if datetime.fromisoformat(req["expires_at"]) <= now else "open"


# ---- who may see a field (module 2 `catalogue.allows`, copied) -----------------------------------------------------------------
def may_see_field(limit: list[str] | None, viewer: I.Viewer) -> bool:
    """No own list: open. An own list: named people pass (unless another account shares their display name); the organiser roles always pass."""
    if limit is None or {"company_admin", "sponsor"} & set(viewer.roles):
        return True
    return I._norm(viewer.name) in {I._norm(n) for n in limit} and not viewer.shared_name


def _own_list(field_row: dict) -> list[str] | None:
    text = I._t(field_row.get("Who may see it"))
    return [p.strip() for p in re.split(r"[,;]", text) if p.strip()] if text.strip() else None


# ---- what to ask for, from the signed catalogue ----------------------------------------------------------------------------------
def source_plan(inputs: dict, sources_json, owners: dict | None = None) -> list[dict]:
    """The sources in zones p1 and p2 (all sources while P01's `sources.json` is not there yet) that feed at least one measure not left out,
    each with its tables, fields and measures. `owners` is module 2's `intake_owners` ({Source ID: {name, label}}): the person asked is the source
    owner, else the data owner (labelled so), else the catalogue's Data owner column."""
    owners = owners or {}
    rows = sources_json.get("sources") if isinstance(sources_json, dict) else sources_json
    zones = {str(s.get("id")): s.get("zone") for s in rows if isinstance(s, dict)} if isinstance(rows, list) else None
    feeds = {str(s.get("id")): s["measures"] for s in rows if isinstance(s, dict) and "measures" in s} if isinstance(rows, list) else {}  # P01 knows what each feeds
    names = {m["id"]: m["name"] for m in inputs["measures"] if not m.get("restricted")}
    out = []
    for s in inputs["sources"]:
        sid = I._t(s.get("Source ID"))
        zone = zones.get(sid) if zones is not None else None
        if not sid or (zones is not None and zone not in ZONES):
            continue
        holds_personal = I._norm(I._t(s.get("Contains personal data?"))) in ("yes", "not sure")
        tables = []
        for t in (t for t in inputs["tables"] if I._t(t.get("Source ID")) == sid):
            tid = I._t(t.get("Item ID"))
            cols = []
            for f in (f for f in inputs["fields"] if I._t(f.get("Item ID")) == tid):
                ms = [m for m in I._ids(I._t(f.get("Feeds KPI"))) if m in names]
                if not ms:
                    continue
                cls = I._t(f.get("Personal data class")).strip().lower()
                personal = (cls not in OPEN_CLASSES) if cls else holds_personal
                cols.append({"field_id": I._t(f.get("Field ID")), "name": I._t(f.get("Field name as in the source")),
                             "meaning": I._t(f.get("Business meaning")) or None, "type": I._t(f.get("Data type")) or None,
                             "measures": [{"id": m, "name": names[m]} for m in ms], "limit": _own_list(f), "personal": personal})
            tables.append({"table_id": tid, "name": I._t(t.get("Name of table, file or document type")) or tid,
                           "row_means": I._t(t.get("What one row or record means")) or None, "columns": cols,
                           "related": [m for m in I._ids(I._t(t.get("Related KPIs"))) if m in names]})
        fed = sorted({m["id"] for t in tables for c in t["columns"] for m in c["measures"]} | {m for t in tables for m in t["related"]})
        if not (feeds[sid] if sid in feeds else fed):
            continue  # feeds no measure that is left in: nothing to ask its owner for (listed as "Not needed for any measure")
        out.append({"source_id": sid, "source_name": I._t(s.get("Source name")) or sid, "owner": (owners.get(sid) or {}).get("name") or I._t(s.get("Data owner")) or None, "owner_label": (owners.get(sid) or {}).get("label"),
                    "zone": zone, "personal_source": holds_personal, "tables": tables, "measures": [{"id": m, "name": names[m]} for m in fed]})
    return out


def new_request(plan: dict, period: dict, now: datetime) -> tuple[dict, str]:
    rid = secrets.token_hex(16)
    token = new_token(rid)
    req = {"id": rid, "source_id": plan["source_id"], "source_name": plan["source_name"], "owner": plan["owner"], "zone": plan["zone"],
           "period": period, "personal_source": plan["personal_source"], "tables": [{k: v for k, v in t.items() if k != "related"} for t in plan["tables"]],
           "benchmarks": [{"measure_id": m["id"], "measure_name": m["name"],
                           "ask": f"Your own reported figure for {m['name']}, same period ({period['label']})"} for m in plan["measures"]],
           "token_hash": digest(token), "state": "sent", "sent_at": now.isoformat(),
           "expires_at": (now + timedelta(hours=LINK_HOURS)).isoformat(), "revoked_at": None, "opened_at": None, "arrived_at": None, "reminders": []}
    return req, token


def refresh(req: dict, plan: dict, period: dict) -> dict:
    """A request already sent keeps its link; what it asks for is brought up to date from the catalogue. Columns are only added or updated, never
    dropped: the plan was built for one reader, who may not see every column another reader asked for."""
    tables = {t["table_id"]: {**t, "columns": list(t["columns"])} for t in req["tables"]}
    for t in plan["tables"]:
        mine = tables.setdefault(t["table_id"], {k: v for k, v in t.items() if k not in ("related", "columns")} | {"columns": []})
        have = {c["field_id"]: i for i, c in enumerate(mine["columns"])}
        for c in t["columns"]:
            if c["field_id"] in have:
                mine["columns"][have[c["field_id"]]] = c
            else:
                mine["columns"].append(c)
    return {**req, "source_name": plan["source_name"], "owner": plan["owner"], "zone": plan["zone"], "period": period, "personal_source": plan["personal_source"],
            "tables": list(tables.values()),
            "benchmarks": [{"measure_id": m["id"], "measure_name": m["name"],
                            "ask": f"Your own reported figure for {m['name']}, same period ({period['label']})"} for m in plan["measures"]]}


def plan_of(req: dict) -> dict:
    """The plan a stored request stands for: what an owner's link uploads against (whoever made the request was allowed to see the source)."""
    return {"source_id": req["source_id"], "source_name": req["source_name"], "personal_source": req.get("personal_source", True), "tables": req["tables"]}


def view(req: dict, now: datetime, visible_fields: set[str] | None, viewer: I.Viewer, visible_measures: set[str]) -> dict:
    """One request for one reader. A column the reader may not see is left out (its table too when nothing else shows); a measure they may
    not see is left out. Never carries the token hash. `visible_fields` None = no catalogue check (the field's own list still applies)."""
    tables = []
    for t in req["tables"]:
        cols = [{**c, "measures": [m for m in c["measures"] if m["id"] in visible_measures]} for c in t["columns"]
                if (visible_fields is None or c["field_id"] in visible_fields) and may_see_field(c.get("limit"), viewer)]
        if cols or not t["columns"]:
            tables.append({**t, "columns": [{k: v for k, v in c.items() if k != "limit"} for c in cols]})
    c = (now - datetime.fromisoformat(req["sent_at"])).days
    return {"id": req["id"], "source_id": req["source_id"], "source_name": req["source_name"], "owner": req["owner"], "zone": req["zone"],
            "period": req["period"], "tables": tables, "benchmarks": [b for b in req["benchmarks"] if b["measure_id"] in visible_measures],
            "state": req["state"], "link": link_state(req, now), "sent_at": req["sent_at"], "expires_at": req["expires_at"],
            "opened_at": req["opened_at"], "arrived_at": req["arrived_at"], "reminders": req["reminders"], "days_waiting": max(0, c)}


def email_text(v: dict, organiser: str, link: str | None) -> dict:
    """Nira's words for the organiser to copy: what we need, for which period, how to send it. Names only, no figures, nothing is sent."""
    owner = (v["owner"] or "there").replace(" (illustrative)", "")
    lines = []
    for t in v["tables"]:
        cols = ", ".join(c["name"] for c in t["columns"]) or "the whole table"
        lines.append(f"- {t['name']}: {cols}")
    bench = "\n".join(f"- {b['ask']}" for b in v["benchmarks"])
    return {"subject": f"Data for {v['source_name']}, {v['period']['label']}",
            "body": (f"Hello {owner},\n\n{organiser} is checking how ready {v['source_name']} is. Could you send, for {v['period']['label']}:\n{chr(10).join(lines)}\n\n"
                     f"And, so we can check our reading against yours:\n{bench or '- Any figure you already report from this source, same period'}\n\n"
                     f"Excel, CSV or JSON is fine. Send it here: {link or '{link}'}\nYou can do it without signing in. Please do not send real client names or "
                     f"account numbers; a sample is enough.\n\nThank you,\nNira")}


def reminder_text(v: dict, organiser: str) -> dict:
    owner = (v["owner"] or "there").replace(" (illustrative)", "")
    return {"subject": f"Reminder: data for {v['source_name']}",
            "body": f"Hello {owner},\n\nA gentle reminder: {organiser} is still waiting for the {v['source_name']} data for {v['period']['label']}. "
                    "Please use the link in my earlier message.\n\nThank you,\nNira"}


# ---- benchmarks: the figures the customer already reports ----------------------------------------------------------------------------
_WANT = {"measure": ("measure", "kpi", "metric", "indicator", "name"), "figure": ("figure", "value", "reported", "result", "amount", "actual"),
         "unit": ("unit", "uom"), "period_end": ("period end", "as at", "as of", "period", "date"),
         "came_from": ("where it came from", "source", "reference", "page", "cell", "origin")}


def benchmark_columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for key, words in _WANT.items():
        for w in words:  # the more specific word first
            i = next((i for i, h in enumerate(header) if i not in found.values() and w in h.lower()), None)
            if i is not None:
                found[key] = i
                break
    return found


def _norm_text(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split())


def match_measure(text: str, measures: list[dict]) -> str | None:
    """A measure id for the customer's own words: exact name or id, else the one clearly best fuzzy match; None when unsure or tied."""
    t = _norm_text(text)
    live = [m for m in measures if not m.get("restricted")]
    for m in live:
        if t in (_norm_text(m["name"]), _norm_text(m["id"])):
            return m["id"]
    scored = sorted(((max(SequenceMatcher(None, t, _norm_text(m["name"])).ratio(), 1.0 if M._name_score(text, m["name"])[0] == 3 else 0.0), m["id"]) for m in live), reverse=True)
    if scored and scored[0][0] >= 0.8 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
        return scored[0][1]
    return None


def parse_benchmarks(header: list[str], rows: list[list], measures: list[dict], by: str, now: datetime) -> tuple[dict, list[dict]]:
    """(matched {measure id: record}, unmatched lines). Raises ValueError (plain words) when no measure and figure columns can be found."""
    from modules.m3_connect.domain.profile import coerce
    cols = benchmark_columns(header)
    if "measure" not in cols or "figure" not in cols:
        raise ValueError("We could not find a column naming the measure and a column with the figure. Please check the header row.")
    cell = lambda r, k: (coerce(r[cols[k]]) if k in cols else None)  # noqa: E731
    matched, unmatched = {}, []
    for i, r in enumerate(rows):
        line, fig = str(r[cols["measure"]] or "").strip(), cell(r, "figure")
        if not line:
            continue
        rec = {"figure": fig if isinstance(fig, (int, float)) and not isinstance(fig, bool) else None, "unit": cell(r, "unit"),
               "period_end": cell(r, "period_end") if str(cell(r, "period_end") or "").count("-") == 2 else None,
               "came_from": cell(r, "came_from"), "given_by": by}
        mid = match_measure(line, measures) if rec["figure"] is not None else None
        if mid and mid not in matched:
            matched[mid] = {**rec, "line": line, "matched": "auto", "at": now.isoformat()}
        else:
            unmatched.append({"index": i, "line": line, **rec, "problem": None if rec["figure"] is not None else "There is no figure on this line."})
    return matched, unmatched


# ---- the two steps this package reports (domain/steps.py) --------------------------------------------------------------------------
def _read(path):
    from sh_platform.jsonfile import read_json_strict
    try:
        return read_json_strict(path)
    except (OSError, ValueError):
        return None


def withdrawn(req: dict) -> bool:
    """The organiser withdrew the request (the link was revoked) or marked it "will not send": nothing is owed, so it blocks nothing."""
    return bool(req.get("revoked_at")) or req.get("state") == "will_not_send"


def counted(assessment_dir, reqs: list[dict]) -> list[dict]:
    """The requests the Data request and Scan steps wait on: not withdrawn, and for a source in priority 1 or 2 that feeds at least one measure
    that is not left out (P01's sources.json; a source it does not list, or lists in another zone or with no measure, is not waited on)."""
    live = [r for r in reqs if isinstance(r, dict) and not withdrawn(r)]
    doc = _read(assessment_dir / "sources.json")
    rows = doc.get("sources") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return live
    ok = {str(s.get("id")) for s in rows if isinstance(s, dict) and s.get("zone") in ZONES and ("measures" not in s or s["measures"])}
    return [r for r in live if str(r.get("source_id")) in ok]


def _adopted(assessment_dir) -> set[str]:
    """Sources whose sample the company profile already held (LI-M3): `intake/<source>/from_profile.json`, written when the sample was taken."""
    base = assessment_dir / "intake"
    return {p.parent.name for p in base.glob("*/from_profile.json")} if base.is_dir() else set()


def _unasked(assessment_dir, reqs: list, adopted: set[str]) -> list[str]:
    """When nobody has been sent a request at all: the sources in priority 1 and 2 that still have no sample (P01's sources.json; none known = none)."""
    doc = _read(assessment_dir / "sources.json")
    rows = doc.get("sources") if isinstance(doc, dict) else doc
    if reqs or not isinstance(rows, list):
        return []
    return [str(s.get("name") or s["id"]) for s in rows if isinstance(s, dict) and s.get("id") and s.get("zone") in ZONES and s.get("measures", True) and str(s["id"]) not in adopted]


def _names(owing: list[str], tail: str) -> str:
    return "Waiting for the owners of " + ", ".join(owing[:4]) + (" and others" if len(owing) > 4 else "") + " " + tail


def request_state(assessment_dir) -> dict:
    reqs = _read(assessment_dir / "requests.json")
    reqs, adopted = reqs if isinstance(reqs, list) else [], _adopted(assessment_dir)
    if not reqs and not adopted:
        return {"state": "not_started"}
    owing = [r.get("source_name") or "a source" for r in counted(assessment_dir, reqs) if r.get("state") != "arrived" and str(r.get("source_id")) not in adopted]
    owing += _unasked(assessment_dir, reqs, adopted)
    if not owing:
        return {"state": "done"}
    return {"state": "in_progress", "waiting_on": _names(owing, "to send their files.")}


def scan_state(assessment_dir) -> dict:
    reqs = _read(assessment_dir / "requests.json")
    reqs, adopted = counted(assessment_dir, reqs if isinstance(reqs, list) else []), _adopted(assessment_dir)
    have = [r for r in reqs if (assessment_dir / "intake" / str(r.get("source_id")) / "profile.json").is_file()]
    if not have and not adopted:
        return {"state": "not_started"}
    owing = [r.get("source_name") or "a source" for r in reqs if r not in have] + _unasked(assessment_dir, reqs, adopted)
    if not owing:
        return {"state": "done"}
    return {"state": "in_progress", "waiting_on": "Waiting for the files from " + ", ".join(owing)[:200] + "."}


register("request", request_state)
register("scan", scan_state)


def latest_full_month(today: date | None = None) -> dict:
    from modules.m3_connect.domain.profile import month_of
    return month_of(today or datetime.now(timezone.utc).date())
