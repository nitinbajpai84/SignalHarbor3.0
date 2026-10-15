"""E3a: the rules register. business_rules (one per rule_code) and rule_versions (draft, approved, retired).

The rule's owner proposes a version; someone else signs it. Only signed versions are returned by `current`, and a
figure computed under a version keeps that version's id. People are rows of the warehouse users table, made on first use and shown by display name.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime

from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused

ROLES = {"company_admin", "analyst", "sponsor"}  # propose and sign
READERS = ROLES | {"approver"}                     # see the register (the approver owns rules and reads them; P15)
RULE_TYPES = {"tolerance", "materiality", "policy", "fixing", "deadline", "limit"}


def need_role(viewer) -> None:
    """May see the register (the routes call this for reads)."""
    if not (set(viewer.roles) & READERS):
        raise Refused(403, "You do not have access to the rules.")


def _need_writer(viewer) -> None:
    if not (set(viewer.roles) & ROLES):
        raise Refused(403, "You can read the rules; the data team, the sponsor or the administrator proposes and signs them.")


def _day(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise Refused(400, "Give the date as year-month-day.") from None


def _params(raw):
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def _same(a, b) -> bool:
    return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())


def _version(row) -> dict:
    return {"rule_version_id": str(row[0]), "rule_code": row[1], "rule_type": row[2], "owner": row[3], "version_number": row[4],
            "definition_text": row[5], "parameters": _params(row[6]), "effective_from": row[7].isoformat(),
            "effective_to": row[8].isoformat() if row[8] else None, "state": row[9], "approved_by": row[10],
            "approved_at": row[11].isoformat() if row[11] else None}


_SELECT = """select v.id, r.rule_code, r.rule_type, coalesce(o.display_name, cast(r.owner_user_id as varchar)), v.version_number,
  v.definition_text, v.parameters, v.effective_from, v.effective_to, v.approval_status,
  coalesce(a.display_name, cast(v.approved_by as varchar)), v.approved_at
  from rule_versions v join business_rules r on r.id = v.business_rule_id
  left join users o on o.id = r.owner_user_id left join users a on a.id = v.approved_by where v.organization_id = ?"""


def _proposers(plane, add: dict | None = None) -> dict:
    """{rule_version_id: proposer name}: rule_versions has no proposer column, so it is kept beside the warehouse in the plane."""
    from sh_platform.jsonfile import lock_for, write_json_atomic
    path = plane.path("rules", "proposers.json")
    with lock_for(path):
        got = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if add:
            got.update(add)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(path, got)
    return got


def _org(plane) -> str:
    from sh_platform.v1.e1_write import org_id  # one UUID per company, the same in every card
    return org_id(plane)


def _uid(con, org: str, viewer) -> str:
    """The warehouse users row for this person (made on first use), so owner and signer columns hold real user ids."""
    r = con.execute("select id from users where organization_id = ? and display_name = ? limit 1", [org, viewer.name]).fetchone()
    if r:
        return str(r[0])
    uid = wh.new_id()
    con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, business_role, is_active, created_at)"
                " values (?, ?, ?, ?, '', null, true, ?)", [uid, org, str(viewer.account_id or viewer.name), viewer.name, wh.now()])
    return uid


def current(plane, rule_code: str, on_date) -> dict | None:
    """The signed version in force on `on_date`: {rule_version_id, parameters, definition_text}, or None."""
    d = _day(on_date)
    with wh.connect(plane) as con:
        row = con.execute(_SELECT + """ and r.rule_code = ? and v.approval_status = 'approved' and v.effective_from <= ?
          and (v.effective_to is null or v.effective_to >= ?) order by v.effective_from desc, v.version_number desc limit 1""",
                          [_org(plane), rule_code, d, d]).fetchone()
    if not row:
        return None
    v = _version(row)
    return {k: v[k] for k in ("rule_version_id", "parameters", "definition_text")}


def history(plane, rule_code: str) -> list[dict]:
    with wh.connect(plane) as con:
        rows = con.execute(_SELECT + " and r.rule_code = ? order by v.version_number desc", [_org(plane), rule_code]).fetchall()
    return [_version(r) for r in rows]


def listing(plane, viewer) -> list[dict]:
    """One line per rule: the version in force today, else the latest; `waiting` counts drafts to sign."""
    need_role(viewer)
    with wh.connect(plane) as con:
        codes = [r[0] for r in con.execute("select rule_code from business_rules where organization_id = ? order by rule_code",
                                           [_org(plane)]).fetchall()]
    out = []
    for code in codes:
        h = history(plane, code)
        today = current(plane, code, wh.today(plane))
        shown = next((v for v in h if today and v["rule_version_id"] == today["rule_version_id"]), h[0] if h else None)
        if shown:
            out.append({**shown, "in_force": bool(today), "waiting": sum(v["state"] == "draft" for v in h)})
    return out + benchmark_lines(plane)


_BENCH_WORDS = {"approved": "approved", "in_progress": "still in progress", "draft": "still a draft"}


def benchmark_lines(plane) -> list[dict]:
    """One register line per benchmark (k7): every version in words, e.g. 'version 2 (2026-10-01) still in progress'.
    A version not approved is never used for certified figures (k7_benchmark.certified_return)."""
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute("select d.benchmark_code, d.benchmark_name, d.version_number, d.effective_from, d.approval_status,"
                           " coalesce(u.display_name, cast(d.approved_by as varchar)) from benchmark_definitions d"
                           " left join users u on cast(u.id as varchar) = cast(d.approved_by as varchar)"
                           " where d.organization_id = ? order by d.benchmark_code, d.version_number", [_org(plane)]).fetchall()
    out: dict[str, dict] = {}
    for code, name, n, eff, status, by in rows:
        line = out.setdefault(code, {"rule_version_id": f"benchmark:{code}", "rule_code": code, "rule_type": "benchmark", "owner": None,
                                     "version_number": n, "parts": [], "parameters": {}, "effective_from": eff.isoformat(), "effective_to": None,
                                     "state": "approved", "approved_by": None, "approved_at": None, "in_force": False, "waiting": 0, "name": name})
        line["parts"].append(f"version {n} ({eff.isoformat()}) {_BENCH_WORDS.get(status, status)}{f' by {by}' if by and status == 'approved' else ''}")
        line["version_number"], line["effective_from"] = n, eff.isoformat()
        if status == "approved":
            line["in_force"] = True
        else:
            line["state"], line["waiting"] = "draft", line["waiting"] + 1
    for line in out.values():
        tail = " A version not approved is not used for certified figures." if line["waiting"] else ""
        line["definition_text"] = f"Benchmark {line.pop('name')}: " + "; ".join(line.pop("parts")) + "." + tail
    return list(out.values())


def propose(plane, viewer, rule_code: str, definition_text: str, parameters: dict | None, effective_from, rule_type: str = "") -> dict:
    """A draft version. The rule's owner proposes (whatever their role), or the data team, sponsor or administrator proposes for them;
    a new rule makes the proposer its owner. Neither the owner nor the proposer may sign it (`approve`)."""
    text = (definition_text or "").strip()
    if not text:
        raise Refused(400, "Say the rule in plain words.")
    if parameters is not None and not isinstance(parameters, dict):
        raise Refused(400, "The values must be a list of names and values.")
    eff = _day(effective_from)
    with wh.connect(plane) as con:
        org = _org(plane)
        row = con.execute("select r.id, coalesce(o.display_name, cast(r.owner_user_id as varchar)) from business_rules r"
                          " left join users o on o.id = r.owner_user_id where r.organization_id = ? and r.rule_code = ?", [org, rule_code]).fetchone()
        if row:
            rid = row[0]
            if not _same(row[1], viewer.name) and not set(viewer.roles) & ROLES:
                raise Refused(403, f"Only {row[1]}, the owner of this rule, or the data team, the sponsor or the administrator can propose a change.")
        else:
            _need_writer(viewer)
            if rule_type not in RULE_TYPES:
                raise Refused(400, "Say what kind of rule this is: " + ", ".join(sorted(RULE_TYPES)) + ".")
            rid = wh.new_id()
            con.execute("insert into business_rules (id, organization_id, rule_code, rule_type, owner_user_id) values (?, ?, ?, ?, ?)", [rid, org, rule_code, rule_type, _uid(con, org, viewer)])
        n = con.execute("select coalesce(max(version_number), 0) + 1 from rule_versions where business_rule_id = ?", [rid]).fetchone()[0]
        vid = wh.new_id()
        con.execute("insert into rule_versions (id, organization_id, business_rule_id, version_number, definition_text, parameters, effective_from,"
                    " effective_to, approval_status, approved_by, approved_at) values (?, ?, ?, ?, ?, ?, ?, null, 'draft', null, null)",
                    [vid, org, rid, n, text, json.dumps(parameters or {}), eff])
    _proposers(plane, {vid: viewer.name})
    return next(v for v in history(plane, rule_code) if v["rule_version_id"] == vid)


def approve(plane, viewer, rule_version_id: str) -> dict:
    """Sign a draft. Never the person who proposed it (the rule's owner)."""
    _need_writer(viewer)
    try:
        uuid.UUID(str(rule_version_id))
    except ValueError:
        raise Refused(404, "There is no such rule version.") from None
    with wh.connect(plane) as con:
        row = con.execute(_SELECT + " and v.id = ?", [_org(plane), rule_version_id]).fetchone()
        if not row:
            raise Refused(404, "There is no such rule version.")
        v = _version(row)
        if v["state"] != "draft":
            raise Refused(409, "This version is not waiting for a signature.")
        if _same(v["owner"], viewer.name) or _same(_proposers(plane).get(rule_version_id), viewer.name):
            raise Refused(403, "You own or proposed this rule, so someone else has to sign it.")
        me, now = _uid(con, _org(plane), viewer), wh.now()
        con.execute("update rule_versions set approval_status = 'approved', approved_by = ?, approved_at = ? where id = ?", [me, now, rule_version_id])
        con.execute("insert into approvals (id, organization_id, rule_version_id, approval_type, requested_from_user_id, decision_by_user_id,"
                    " status, requested_at, decided_at) values (?,?,?,?,?,?,?,?,?)",
                    [wh.new_id(), _org(plane), rule_version_id, "rule_version", me, me, "approved", now, now])
    return next(x for x in history(plane, v["rule_code"]) if x["rule_version_id"] == rule_version_id)


# ---- UC5: a signed limits workbook read as proposed versions ------------------------------------------------------------------------------

_LIMIT_KEYS = ("dimension", "bucket", "min_pct", "max_pct", "portfolio_code")
_HEAD = {"rule code": "rule_code", "portfolio": "portfolio_code", "dimension": "dimension", "item or bucket": "bucket", "bucket": "bucket",
         "minimum %": "min_pct", "minimum": "min_pct", "maximum %": "max_pct", "maximum": "max_pct", "definition": "definition"}


def _num_or_none(v):
    try:
        return None if v in (None, "") else float(str(v).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def read_signed_limits(path, sheet: str | None = None) -> dict:
    """{meta: {version, signed by, signed on, effective from, ...}, lines: [{rule_code, portfolio_code, dimension, bucket, min_pct, max_pct,
    definition}]} from a signed limits sheet: a title block of 'label | value' rows, then a table headed 'Rule code'."""
    from sh_platform.v1.e0b_tools import read_grid
    _, grid = read_grid(path, sheet)
    meta, lines, cols = {}, [], None
    for row in grid:
        cells = [c for c in row]
        first = str(cells[0]).strip() if cells and cells[0] not in (None, "") else ""
        if cols is None:
            if first.lower() == "rule code":
                cols = {i: _HEAD[str(c).strip().lower()] for i, c in enumerate(cells) if str(c or "").strip().lower() in _HEAD}
            elif first and len(cells) > 1 and cells[1] not in (None, ""):
                meta[first.lower()] = str(cells[1]).strip()
            continue
        if not first:
            continue
        ln = {k: (cells[i] if i < len(cells) else None) for i, k in cols.items()}
        ln.update(min_pct=_num_or_none(ln.get("min_pct")), max_pct=_num_or_none(ln.get("max_pct")))
        lines.append({k: (str(v).strip() if isinstance(v, str) else v) for k, v in ln.items()})
    if cols is None:
        raise Refused(400, "That sheet has no table headed 'Rule code', so no limits could be read.")
    return {"meta": meta, "lines": lines}


def _same_params(a: dict, b: dict) -> bool:
    norm = lambda p: (str(p.get("dimension") or "").lower(), str(p.get("bucket") or "").strip().lower(), _num_or_none(p.get("min_pct")),  # noqa: E731
                      _num_or_none(p.get("max_pct")), str(p.get("portfolio_code") or "").strip().lower())
    return norm(a) == norm(b)


def import_signed(plane, viewer, path, sheet: str | None = None) -> dict:
    """UC5 G-3: each line of a signed limits workbook against the register on the workbook's effective date. Unchanged: nothing. Different or
    new: a proposed version in the line's words, for someone other than the owner and the importer to sign; one Action item tells the signer
    what differs. Never signs anything itself. -> {version, effective_from, unchanged: [codes], proposed: [{rule_code, before, after,
    rule_version_id}], waiting: [codes], case_id}"""
    got = read_signed_limits(path, sheet)
    meta = got["meta"]
    eff = _day(meta.get("effective from") or meta.get("effective") or "")
    tag = " ".join(x for x in (f"Signed {meta.get('version')}" if meta.get("version") else "",
                               f"({meta.get('signed by')}, {meta.get('signed on')})" if meta.get("signed by") else "") if x)
    out = {"version": meta.get("version"), "effective_from": eff.isoformat(), "unchanged": [], "proposed": [], "waiting": [], "case_id": None}
    for ln in got["lines"]:
        code = str(ln.get("rule_code") or "").strip()
        if not code:
            continue
        params = {k: ln.get(k) for k in _LIMIT_KEYS}
        now = current(plane, code, eff)
        if now and _same_params(now["parameters"] or {}, params):
            out["unchanged"].append(code)
            continue
        if any(v["state"] == "draft" and v["effective_from"] == eff.isoformat() and _same_params(v["parameters"] or {}, params) for v in history(plane, code)):
            out["waiting"].append(code)  # imported before and not signed yet: never proposed twice
            continue
        text = " ".join(x for x in (str(ln.get("definition") or "").strip(), tag + f", effective {eff.isoformat()}." if tag else "") if x)
        v = propose(plane, viewer, code, text or code, params, eff, "limit")
        before = (now or {}).get("parameters") or {}
        out["proposed"].append({"rule_code": code, "before": {k: before.get(k) for k in ("min_pct", "max_pct")} if now else None,
                                "after": {k: params.get(k) for k in ("min_pct", "max_pct")}, "rule_version_id": v["rule_version_id"]})
    if out["proposed"]:
        from sh_platform.v1 import e4_cases
        diffs = "; ".join(f"{p['rule_code']}: " + (f"{p['before']['min_pct']}% to {p['before']['max_pct']}% in the register" if p["before"] else "not in the register")
                          + f", {p['after']['min_pct']}% to {p['after']['max_pct']}% signed" for p in out["proposed"])
        out["case_id"] = e4_cases.open(plane, {"exception_type": "policy_question", "materiality_status": "material",
                                               "title": f"Signed limits {meta.get('version') or ''} differ from the register from {eff.isoformat()}".replace("  ", " "),
                                               "description": f"The signed limits workbook ({tag or 'no signature named'}) differs from the rules register: {diffs}. "
                                                              "Each change waits as a proposed version on Settings > Rules; sign it, or say which is right."})
    return out
