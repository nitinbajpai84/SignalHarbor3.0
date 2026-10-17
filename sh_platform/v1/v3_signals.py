"""Signals: a decision schema that fires (docs/v3/SIGNAL-ENGINE.md).

A signal is a declared catch: what arrives or already exists -> the signal Harbor catches -> the one person who acts, and how little they do.
The library is the pack's `signals/<id>.yaml` (suggestions) plus the office's own `<company>/v3/signals/office/<id>.yaml` (same id overrides;
`disabled: true` switches one off). The engine evaluates it on a file load, a run, an earlier signal's action and a daily tick. A fired signal is an
Action card for the person who holds the routed role, with its receipts. The same signal for the same subject fires once. A hold blocks a named action
(held()) until the card is acted. Each card is a hit (acted) or a miss (dismissed as wrong), kept per signal and per office.

Conditions are a small safe language: numbers, text, + - * /, comparisons, and/or/not, in, dotted names, and the calls in FUNCS. The text is parsed
with ast and walked by evaluate_node(); it is never passed to eval or exec. Where a condition needs judgement (same_fund) the two-model check
(v3_judge) is asked."""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import operator
import re
import threading
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import yaml

from sh_platform.jsonfile import write_json_atomic

log = logging.getLogger(__name__)
LOCK = threading.RLock()
TRIGGERS = {"file_arrived", "figure_changed", "date_passed", "schedule", "run", "action_done"}
SEVERITY = {"info", "needs", "problem"}
VERBS = {"log", "record", "approve", "call_back", "see"}
PROVIDER = None  # hook (plane, kind, ref, event) -> {"value": ..., "receipt": {...}} | None, tried before the event's own facts; set to figure_provider below


class Missing(Exception):
    """An input or a name the condition needs is not there: the signal is skipped, never guessed."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- the safe expression language ------------------------------------------------------------------------------------------------------

BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
       ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


def num(v):
    """A number as Decimal; text such as '1,250,000.00' or 'USD 5' with one number in it too. Anything else is returned as it is."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    if isinstance(v, str) and re.fullmatch(r"\s*[A-Za-z]{0,3}\s*[-+]?[\d,]*\.?\d+\s*", v):
        try:
            return Decimal(re.sub(r"[^\d.+-]", "", v))
        except InvalidOperation:
            return v
    return v


def _dec(v):
    return Decimal(str(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def last4(v) -> str:
    return re.sub(r"\W", "", str(v))[-4:]


def _norm_name(s) -> str:
    drop = {"lp", "ltd", "inc", "sicav", "fund", "partners", "the"}
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", str(s).lower().replace(".", "")).split() if w not in drop)


def parse(text: str) -> ast.Expression:
    """Parse and check a condition: ValueError (plain words) when it uses anything outside the language."""
    try:
        tree = ast.parse(str(text).strip(), mode="eval")
    except SyntaxError:
        raise ValueError(f"I cannot read the condition: {text}") from None
    ok = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call, ast.Name, ast.Attribute, ast.Constant, ast.Load, ast.List, ast.Tuple,
          ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, *BIN, *CMP)
    for n in ast.walk(tree):
        if not isinstance(n, ok):
            raise ValueError(f"The condition may not use {type(n).__name__}: {text}")
        if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.keywords):
            raise ValueError(f"The condition may call only named functions: {text}")
        if isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            raise ValueError(f"A name may not start with an underscore: {text}")
    return tree


def evaluate_node(n, ns: dict, funcs: dict):
    ev = lambda x: evaluate_node(x, ns, funcs)  # noqa: E731
    if isinstance(n, ast.Expression):
        return ev(n.body)
    if isinstance(n, ast.Constant):
        return num(n.value) if isinstance(n.value, (int, float)) else n.value
    if isinstance(n, (ast.List, ast.Tuple)):
        return [ev(x) for x in n.elts]
    if isinstance(n, ast.Name):
        if n.id not in ns:
            raise Missing(n.id)
        return ns[n.id]
    if isinstance(n, ast.Attribute):
        base = ev(n.value)
        if not isinstance(base, dict) or base.get(n.attr) is None:
            raise Missing(f"{ast.unparse(n.value)}.{n.attr}")
        return base[n.attr]
    if isinstance(n, ast.UnaryOp):
        v = ev(n.operand)
        return (not v) if isinstance(n.op, ast.Not) else -num(v) if isinstance(n.op, ast.USub) else num(v)
    if isinstance(n, ast.BinOp):
        return BIN[type(n.op)](num(ev(n.left)), num(ev(n.right)))
    if isinstance(n, ast.BoolOp):
        vals = (ev(x) for x in n.values)
        return all(vals) if isinstance(n.op, ast.And) else any(vals)
    if isinstance(n, ast.Compare):
        left = ev(n.left)
        for op, right_node in zip(n.ops, n.comparators):
            right = ev(right_node)
            plain = isinstance(op, (ast.In, ast.NotIn)) or (isinstance(left, str) and isinstance(right, str))  # two texts stay texts (account 0123 is not 123)
            a, b = (left, right) if plain else (num(left), num(right))
            if not CMP[type(op)](a, b):
                return False
            left = right
        return True
    if isinstance(n, ast.Call):
        f = funcs.get(n.func.id)
        if f is None:
            raise ValueError(f"No such function in a condition: {n.func.id}")
        return f(*[ev(a) for a in n.args])
    raise ValueError("Not allowed in a condition.")  # pragma: no cover - parse() has refused it


def calc(text: str, ns: dict, funcs: dict):
    return evaluate_node(parse(text), ns, funcs)


def render(template: str, ns: dict) -> str:
    """`{doc.amount:,.0f}` in a message: a dotted name from ns and an optional format. A name that is not there stays as written."""
    def one(m):
        try:
            v = ns
            for part in m[1].split("."):
                v = v[part]
            return format(num(v) if m[2] else v, m[2] or "")
        except (KeyError, TypeError, ValueError):
            return m[0]
    return re.sub(r"\{([A-Za-z_][\w.]*)(?::([^{}]+))?\}", one, str(template))


# ---- the library -----------------------------------------------------------------------------------------------------------------------

def _dir(plane):
    d = plane.path("v3", "signals")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _roles(plane) -> dict[str, str]:
    from sh_platform.v1 import v3_roles as R
    return {r["id"]: str(r.get("title") or r["id"]) for r in R._roles(plane)}


def check(sig: dict, roles: dict | None) -> str | None:
    """Why a signal definition cannot be used, or None."""
    for k in ("id", "title", "trigger", "condition", "severity", "route_to", "action", "message"):
        if not sig.get(k):
            return f"missing {k}"
    t = sig["trigger"]
    if not isinstance(t, dict) or t.get("on") not in TRIGGERS:
        return "trigger.on must be one of " + ", ".join(sorted(TRIGGERS))
    if sig["severity"] not in SEVERITY:
        return "severity must be info, needs or problem"
    if not isinstance(sig["action"], dict) or sig["action"].get("verb") not in VERBS:
        return "action.verb must be one of " + ", ".join(sorted(VERBS))
    if roles is not None and sig["route_to"] not in roles:
        return f"route_to {sig['route_to']} is not a role of this office"
    try:
        parse(sig["condition"])
        for e in (sig.get("let") or {}).values():
            parse(e)
    except ValueError as e:
        return str(e)
    return None


def _read_dir(d, source: str) -> dict[str, dict]:
    out = {}
    for p in sorted(d.glob("*.yaml")) if d.is_dir() else []:
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            doc = None
        if isinstance(doc, dict) and doc.get("id"):
            if isinstance(doc.get("trigger"), dict) and True in doc["trigger"]:  # YAML 1.1 reads a bare `on` as true
                doc["trigger"] = {("on" if k is True else k): v for k, v in doc["trigger"].items()}
            out[str(doc["id"])] = {**doc, "source": source}
    return out


def library(plane) -> list[dict]:
    """Every signal of the office: the pack's suggestions, overridden by the office's own files. Each has `error` when it cannot run."""
    from sh_platform.v1 import v3_model as M
    pack = M.pack_of(plane)
    folder = getattr(pack, "folder", None)
    sigs = _read_dir(folder / "signals", "pack") if folder else {}
    for sid, o in _read_dir(_dir(plane) / "office", "office").items():
        sigs[sid] = {**sigs.get(sid, {}), **o}
    roles = _roles(plane) or None
    out = []
    for s in sigs.values():
        s.setdefault("suggestion", s["source"] == "pack")
        s["error"] = check(s, roles)
        s["role_title"] = (roles or {}).get(s.get("route_to"))
        out.append(s)
    return sorted(out, key=lambda s: s["id"])


# ---- the record: fired cards -----------------------------------------------------------------------------------------------------------

def _fp(plane):
    return _dir(plane) / "fired.json"


def fired(plane) -> list[dict]:
    from sh_platform.jsonfile import read_json_strict
    try:
        d = read_json_strict(_fp(plane), dict) if _fp(plane).is_file() else None
    except (OSError, ValueError):
        d = None
    return sorted((d or {}).values(), key=lambda r: (r["at"], r["id"]))


def _put(plane, rec: dict) -> None:
    with LOCK:
        d = {r["id"]: r for r in fired(plane)}
        d[rec["id"]] = rec
        write_json_atomic(_fp(plane), d)


def stats(plane) -> dict[str, dict]:
    """Per signal: fired, acted (hits), dismissed (misses), open, hit_rate (acted / settled, None until one is settled)."""
    out: dict[str, dict] = {}
    for r in fired(plane):
        s = out.setdefault(r["signal"], {"fired": 0, "acted": 0, "dismissed": 0, "open": 0, "hit_rate": None, "last_fired": None})
        s["fired"] += 1
        s[{"acted": "acted", "dismissed": "dismissed"}.get(r["status"], "open")] += 1
        s["last_fired"] = r["at"]
    for s in out.values():
        done = s["acted"] + s["dismissed"]
        s["hit_rate"] = round(s["acted"] / done, 3) if done else None
    return out


def held(plane, action: str, scope: str | None = None) -> list[dict]:
    """Open cards that hold `action` (for example prepare_payment), for one scope (a fund) or all. A caller that prepares the action refuses when any."""
    return [r for r in fired(plane) if r["status"] == "open" and (r.get("hold") or {}).get("blocks") == action
            and (scope is None or _norm_name((r["hold"] or {}).get("scope", "")) == _norm_name(scope))]


# ---- inputs and receipts ---------------------------------------------------------------------------------------------------------------

def same_fund(plane, a, b, judged: list) -> bool:
    """Same name once case, punctuation and generic words are ignored; otherwise the two-model check decides, and a pair that disagrees is not the same."""
    if _norm_name(a) == _norm_name(b):
        return True
    from sh_platform.v1 import v3_judge as J
    try:
        r = J.ask_kind(plane, "fund_match", {"page": a, "on_file": b}, ["same fund", "different fund"], {"page": a, "on_file": b}, person=False)
    except Exception:  # noqa: BLE001 - no judge is a no
        return False
    judged.append({"kind": "judge", "question": f"Is '{a}' the same fund as '{b}'?", "answer": r.get("answer"), "agreed": r.get("agreed"),
                   "models": [o.get("model") for o in r.get("opinions") or []]})
    return bool(r.get("agreed")) and r.get("answer") == "same fund"


def _fact(plane, ev: dict, kind: str, ref: str):
    if PROVIDER and (got := PROVIDER(plane, kind, ref, ev)):
        return got
    got = ((ev.get("facts") or {}).get({"figure": "figures", "rule": "rules"}.get(kind, kind)) or {}).get(ref)
    if got is not None:
        return got if isinstance(got, dict) and "value" in got else {"value": got}
    if kind == "figure":
        from sh_platform.v1 import v3_figstore as FS
        rec = FS.read(plane, ref) or FS.read(plane, FS.fid(ref))
        cur = FS.version(rec) if rec else None
        if cur and cur.get("value") is not None:
            return {"value": cur["value"], "receipt": {"v": cur["v"], "status": cur.get("status"), "approved_by": cur.get("approved_by")}}
    if kind == "rule":
        from sh_platform.v1 import e3_rules
        try:
            r = e3_rules.current(plane, ref, ev.get("today") or date.today())
        except Exception:  # noqa: BLE001 - no warehouse yet is no rule
            r = None
        if r:
            return {"value": {**r["parameters"], "text": r.get("definition_text") or ""}, "receipt": {"version_id": r["rule_version_id"]}}
    return None


def figure_provider(plane, kind: str, ref: str, ev: dict):
    """`figure:<id>` -> the rows of the figure's latest verified version, read from its ready table on the live warehouse (v3_figures' answer path:
    cx_dash.run_sql). The receipt names the figure version, the run and the table. The signal's `by` then scopes the rows to its fund, entity or date."""
    if kind != "figure":
        return None
    from sh_platform.v1 import cx_dash as CD, v3_figstore as FS, v3_harbor as H
    rec = FS.read(plane, ref) or FS.read(plane, FS.fid(ref))
    ok = [x for x in (rec or {}).get("versions", []) if x["status"] == "verified"]
    if not ok:
        return None
    ver = max(ok, key=lambda x: x["v"])
    for use in reversed(rec.get("used_by") or []):  # the newest thread that uses the figure and knows its ready table
        try:
            table = next((f.get("table") for f in H.load(plane, use["thread"]).get("figures") or [] if f.get("kpi") == rec["name"] and f.get("table")), None)
        except (KeyError, OSError, ValueError):
            continue
        if table and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            try:
                _, rows, _ = CD.run_sql(plane, f'select * from "{table}"')
            except Exception:  # noqa: BLE001 - no warehouse or no table yet is no value
                return None
            run = next((r.get("run_id") for r in reversed(ver.get("runs") or []) if r.get("ok")), None)
            return {"value": rows, "receipt": {"figure": rec["id"], "v": ver["v"], "status": "verified", "run_id": run, "table": table, "approved_by": ver.get("approved_by")}}
    return None


PROVIDER = figure_provider


def _key(v):
    return _norm_name(v) if isinstance(v, str) else num(v)


def _pick(plane, rows, by: dict, ns: dict, judged: list):
    """The one row whose columns equal the wanted values. A value is a name from ns (doc.fund) or a literal. Fund names go to same_fund()."""
    want = {}
    for col, v in by.items():
        try:
            want[col] = calc(str(v), ns, {}) if re.fullmatch(r"[A-Za-z_]\w*(\.\w+)*", str(v)) else v
        except Missing:
            want[col] = v
    if isinstance(rows, dict):
        rows = [rows]
    hit = [r for r in rows or [] if all(_key(r.get(c)) == _key(w) for c, w in want.items())]
    if not hit:  # the same fund under another spelling
        hit = [r for r in rows or [] if all(_key(r.get(c)) == _key(w) or (c == "fund" and same_fund(plane, w, r.get(c), judged)) for c, w in want.items())]
    return hit[0] if len(hit) == 1 else None


def resolve(plane, sig: dict, ev: dict, funcs: dict, judged: list) -> tuple[dict, dict]:
    """(ns, receipts): every declared input in the names the expressions use, and where each came from. Missing -> Missing."""
    doc = ev.get("doc") or {}
    ns: dict = {"doc": {}}
    rec: dict = {"doc": []}
    for inp in sig.get("inputs") or []:
        kind = inp.get("kind")
        if kind == "doc":
            for f in inp.get("fields") or []:
                d = doc.get(f)
                v = d.get("value") if isinstance(d, dict) else d
                if v in (None, ""):
                    raise Missing(f"doc.{f}")
                ns["doc"][f] = _dec(v)
                rec["doc"].append({"kind": "document", "field": f, "value": str(v), "file": ev.get("file"),
                                   **({"page": d.get("page"), "quote": d.get("quote")} if isinstance(d, dict) else {})})
        elif kind in ("figure", "rule", "recipe"):
            got = _fact(plane, ev, "figure" if kind == "recipe" else kind, inp["id"])
            if got is None:
                raise Missing(f"{kind} {inp['id']}")
            val = got["value"]
            if inp.get("by"):
                val = _pick(plane, val, inp["by"], ns, judged)
                if val is None:
                    raise Missing(f"{kind} {inp['id']} for {inp['by']}")
            val = {k: _dec(v) for k, v in val.items()} if isinstance(val, dict) else _dec(val)
            name = inp.get("as") or inp["id"]
            ns[name] = val
            r = {"kind": "rule" if kind == "rule" else "figure", "id": inp["id"], "value": {k: str(v) for k, v in val.items()} if isinstance(val, dict) else str(val),
                 **(got.get("receipt") or {})}
            if kind == "rule":
                r["text"] = (val or {}).get("text") if isinstance(val, dict) else None
            elif FS_v := _fig_v(plane, inp["id"]):
                r.setdefault("v", FS_v)
            rec[name] = [r]
    return ns, rec


def _fig_v(plane, fid: str):
    from sh_platform.v1 import v3_figstore as FS
    r = FS.read(plane, fid)
    return r.get("current_v") if r else None


def _evidence(sig: dict, rec: dict, judged: list) -> list[dict]:
    out, seen = [], set()
    for ref in sig.get("evidence") or list(rec):
        head, _, field = str(ref).partition(".")
        for r in rec.get(head, []):
            if field and r.get("field") != field:
                continue
            if (k := repr(r)) not in seen:
                seen.add(k)
                out.append(r)
    return out + judged


# ---- evaluation ------------------------------------------------------------------------------------------------------------------------

def _matches(sig: dict, ev: dict) -> bool:
    t = sig["trigger"]
    if t["on"] != ev.get("trigger"):
        return False
    return all(ev.get(k) == t[k] for k in ("kind", "signal", "figure", "chain") if k in t)


def _person(plane, role: str) -> dict:
    from sh_platform.v1 import v3_roles as R
    emails = sorted(e for e, r in R._jobs(plane).items() if r == role)
    return {"email": emails[0] if emails else None, "emails": emails}


def evaluate(plane, ev: dict) -> dict:
    """Run the library over one event. {fired: [cards], skipped: [{signal, why}]}. Idempotent: a signal fires once for a subject."""
    funcs_judged: list = []
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": last4, "num": num,
             "same_fund": lambda a, b: same_fund(plane, a, b, funcs_judged)}
    out = {"fired": [], "skipped": []}
    for sig in library(plane):
        if sig.get("disabled") or sig.get("error") or not _matches(sig, ev):
            continue
        funcs_judged.clear()
        try:
            ns, rec = resolve(plane, sig, ev, funcs, funcs_judged)
            for name, e in (sig.get("let") or {}).items():
                ns[name] = calc(e, ns, funcs)
            hit = bool(calc(sig["condition"], ns, funcs))
        except Missing as m:
            out["skipped"].append({"signal": sig["id"], "why": f"{m} is not there yet"})
            continue
        if not hit:
            continue
        subject = render(sig.get("subject") or ev.get("subject") or ev.get("file") or ev.get("today") or "", ns)
        fid = "sg-" + hashlib.sha1(f"{sig['id']}|{subject}".encode()).hexdigest()[:10]
        with LOCK:
            if any(r["id"] == fid for r in fired(plane)):
                continue
            hold = sig.get("hold")
            card = {"id": fid, "signal": sig["id"], "title": sig["title"], "subject": subject, "severity": sig["severity"], "route_to": sig["route_to"],
                    "role_title": sig.get("role_title"), "person": _person(plane, sig["route_to"]), "action": sig["action"], "status": "open", "at": now(),
                    "message": render(sig["message"], ns), "suggestion": bool(sig.get("suggestion")), "trigger": ev.get("trigger"),
                    "hold": {"blocks": hold["blocks"], "scope": render(hold.get("scope", ""), ns), "until": hold.get("until", "")} if hold else None,
                    "values": {k: str(v) for k, v in ns.items() if k not in ("doc",) and not isinstance(v, dict)},
                    "evidence": _evidence(sig, rec, funcs_judged),
                    "event": json.loads(json.dumps({k: ev[k] for k in ("trigger", "kind", "file", "doc", "facts", "subject") if k in ev}, default=str))}
            _put(plane, card)
        out["fired"].append(card)
    return out


def on_document(plane, file: str, kind: str, values: dict) -> dict:
    """A file was read and loaded: values = {field: {value, page, quote}}. Called by the PDF loader (v3_pdf.load_files)."""
    kind = re.sub(r"[^a-z0-9]+", "_", kind.lower()).strip("_")
    doc = {re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_"): v for k, v in values.items()}
    from sh_platform.v1 import v3_signal_draft as SD
    SD.arrival(plane, kind, file, doc)  # kept, so a signal Harbor drafts later can be tried on what already arrived
    return evaluate(plane, {"trigger": "file_arrived", "kind": kind, "file": file, "doc": doc})


def on_file(plane, file: str) -> dict:
    """A file that is not a PDF finished loading (v3_harbor.set_status): csv, xlsx, eml ... arrive with their extension as `kind` and no document fields.
    The PDF loader calls on_document with the layout instead."""
    return evaluate(plane, {"trigger": "file_arrived", "kind": file.rsplit(".", 1)[-1].lower() if "." in file else "file", "file": file, "doc": {}})


def on_run(plane, chain: str, thread: str | None = None) -> dict:
    """A chain (B, C or M) finished. Signals that read figures run here."""
    return evaluate(plane, {"trigger": "run", "chain": chain, "subject": f"{thread or ''} {now()[:10]}"})


def _day(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def dated_items(plane, today: str) -> list[dict]:
    """What has a date on it today or earlier, from what exists: a `due` field of a document read (fund notices, capital call notices), the capital calls
    of the capital_calls figure, and the statements the managers inbox expects and has not received. Each is {kind, file, doc: {..., days_past}, subject}."""
    now_ = _day(today)
    out = []

    def add(kind, file, fields, field, v):
        if (d := _day(v)) and d <= now_:
            out.append({"kind": kind, "file": file, "subject": f"{file} {field} {d}", "doc": {**fields, field: str(d), "days_past": (now_ - d).days}})
    slug = lambda t: re.sub(r"[^a-z0-9]+", "_", str(t).lower()).strip("_")  # noqa: E731
    for p in sorted(plane.path("extractions").glob("*.json")) if plane.path("extractions").is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        vals = rec.get("values") or {}
        if rec.get("status") == "ok":
            for f in [f for f in vals if "due" in f.lower()]:
                add(slug(rec.get("type_name") or "document"), rec.get("file") or p.stem, {slug(k): (v.get("value") if isinstance(v, dict) else v) for k, v in vals.items()}, slug(f),
                    vals[f].get("value") if isinstance(vals[f], dict) else vals[f])
    got = PROVIDER and PROVIDER(plane, "figure", "capital_calls", {})
    for r in (got or {}).get("value") or []:
        add("capital_call", f"{r.get('fund')} call {r.get('call_no')}", {k: v for k, v in r.items() if k != "due_date"}, "due_date", r.get("due_date"))
    try:
        from sh_platform.v1 import k5_managers as K5
        from sh_platform.profile.view import Viewer
        box = K5.inbox(plane, Viewer("Harbor", frozenset({"company_admin"}), False, None), now_)
        for m in box.get("managers") or []:
            for f in m.get("funds") or []:
                if f.get("state") == "late":
                    add("expected_statement", f"{f['fund_name']} statement {f['period_end']}", {"fund": f["fund_name"], "period_end": f["period_end"]}, "due_date", f.get("due"))
    except Exception:  # noqa: BLE001 - no managers inbox yet is no expected statements
        log.info("no expected statements to watch", exc_info=True)
    return out


def tick(plane, today: str | None = None, items: list[dict] | None = None) -> dict:
    """The daily tick: schedule signals, then date_passed signals over `items` (default: dated_items, from what exists)."""
    today = today or now()[:10]
    if items is None:
        items = dated_items(plane, today)
    res = evaluate(plane, {"trigger": "schedule", "every": "daily", "today": today, "subject": today})
    for it in items or []:
        r = evaluate(plane, {**it, "trigger": "date_passed", "today": today})
        res["fired"] += r["fired"]
        res["skipped"] += r["skipped"]
    return res


# ---- acting ----------------------------------------------------------------------------------------------------------------------------

def act(plane, fired_id: str, by: str, choice: str | None = None, note: str = "", dismiss: bool = False) -> dict:
    """The person does what the card asks (a hit) or dismisses it as wrong (a miss). ValueError in plain words. An acted card releases its hold
    and starts the signals that follow it (trigger action_done)."""
    with LOCK:
        card = next((r for r in fired(plane) if r["id"] == fired_id), None)
        if card is None:
            raise KeyError(fired_id)
        if card["status"] != "open":
            raise ValueError("This card is already done.")
        opts = card["action"].get("options") or []
        if not dismiss:
            if opts and choice not in opts:
                raise ValueError("Choose one of: " + ", ".join(opts) + ".")
            if card["action"]["verb"] == "call_back" and not (note or "").strip():
                raise ValueError("Write down who you spoke to and when.")
        card.update(status="dismissed" if dismiss else "acted", by=by, done_at=now(), choice=choice, note=(note or "").strip())
        _put(plane, card)
    _watch(plane, card, by, dismiss)
    follow = {"fired": []} if dismiss else evaluate(plane, {**card["event"], "trigger": "action_done", "signal": card["signal"], "choice": choice})
    out = {**card, "next": [r["id"] for r in follow["fired"]]}
    then = card["action"].get("then") or {}
    if not dismiss and then.get("do") == "prepare_payment" and choice == then.get("choice"):  # an approve that leads to a payment being prepared
        fund = ((card["event"].get("doc") or {}).get("fund") or {})
        try:
            out["payment"] = prepare_payment(plane, fund.get("value") if isinstance(fund, dict) else fund, by, card["id"], card["subject"])
        except ValueError as e:  # held: the approval stands, the payment is refused with the hold's reason
            out["payment"] = {"status": "refused", "why": str(e)}
    return out


def _watch(plane, card: dict, by: str, dismissed: bool) -> None:
    """A dismissal, or a note written while acting, is a check a person applied by hand: Harbor watches it (v3_signal_draft)."""
    from sh_platform.v1 import v3_signal_draft as SD
    who = str(card["person"].get("email") or by)
    if dismissed:
        SD.observe(plane, "dismissal", who, "dismissed_" + card["signal"], card["subject"], text=f"Dismissed: {card['title']}")
    elif card.get("note") and (k := SD.kind_of_note(card["note"])):
        SD.observe(plane, "check", who, k[0], k[1] or card["subject"], file_kind=(card.get("event") or {}).get("kind"), text=card["note"])


def prepare_payment(plane, fund: str | None, by: str, card_id: str | None = None, subject: str = "") -> dict:
    """Record the intent to pay: "payment prepared, waiting for release". Refused (ValueError, the hold's reason) while an open card holds prepare_payment
    for the fund. It never moves money and never calls a bank: release is a person's act, outside Harbor."""
    if hold := held(plane, "prepare_payment", fund):
        raise ValueError(f"Payment is held: {hold[0]['message']} It lifts when {hold[0]['hold'].get('until') or 'the card is done'}.")
    pid = "pay-" + hashlib.sha1(f"{fund}|{card_id}|{subject}".encode()).hexdigest()[:10]
    with LOCK:
        p = _dir(plane) / "payments.json"
        from sh_platform.jsonfile import read_json_strict
        d = read_json_strict(p, dict) if p.is_file() else {}
        d.setdefault(pid, {"id": pid, "fund": fund, "subject": subject, "card": card_id, "by": by, "at": now(), "status": "prepared", "note": "Payment prepared, waiting for release"})
        write_json_atomic(p, d)
    return d[pid]


def cards(plane) -> list[dict]:
    """The open cards, as the Desk's needs: kind signal, severity, the person and the one action."""
    return [{"kind": "signal", "id": r["id"], "signal": r["signal"], "title": r["title"], "text": r["message"], "severity": r["severity"], "role": r["route_to"],
             "person": r["person"]["email"], "hold": r["hold"], "evidence": r["evidence"],
             "actions": [{"label": o, "answer": o} for o in r["action"].get("options") or [r["action"]["verb"]]] + [{"label": "Not right", "answer": "dismiss"}]}
            for r in fired(plane) if r["status"] == "open"]
