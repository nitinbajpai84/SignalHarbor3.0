"""Run the agent eval golden sets (tests/evals/*.yaml) against a running product and write the results.

  python tools/run_evals.py --base http://127.0.0.1:8711 --creds <seed_credentials.txt> --mode testing --out docs/test/evals/run-testing
  python tools/run_evals.py --base ... --creds ... --mode real --agents north,lumen --out docs/test/evals/run-real
  python tools/run_evals.py --compare docs/test/evals/run-testing docs/test/evals/run-real --out docs/test/evals/compare

Per item it writes <out>/items/<id>.json (request, response, scores, trace id, cost, latency) and, at the end, <out>/summary.json and
<out>/REPORT.md. Synthetic data only. Passwords are read from the creds file, used for sign-in, and never written anywhere.
It does not start a server. Setting the Testing / Real use switch goes through POST /api/v1/router/mode and is put back when the run ends,
even when the run stops half way (Ctrl-C, a crash); the switch back is printed and written in REPORT.md. `--keep-mode` leaves it set, for
probes that follow the run (ER-17).
Per item the runner also reads the agents' loop traces (GET /api/v1/agent-runs/loops before and after, as the company admin): a trace id in
the response wins, else the newest new loop trace is the item's (EVT-16). After each item it forgets what the item left behind: the memory
items and talk summaries of every person the item signed in as, and the plan changes Span proposed (EVT-18, EVT-20).
Exit code 1 when any item failed (pending items do not count as failures). The draft intents North items start are deleted at the end
through DRAFT_DELETE, or listed in REPORT.md for manual cleanup while no product route deletes a draft.
A Ctrl-C writes summary.json and REPORT.md for the items already run (marked stopped) before the mode is put back.

Offline (no server, no model account, W2-H):
  python tools/run_evals.py --offline --out docs/test/evals/run-offline [--data-root <scratch>] [--replay no_credit] [--agents ...]
seeds the universe into a scratch data root (tools/seed_10uc.py, never data/), runs the product in process and sends every model call to
tests/evals/replay.py, which plays back the replies and failures recorded in docs/test-evidence/agents/ through the real gateway and
provider adapters. An item's `replay:` (a recorded shape or a list of steps) is its script; `--replay` gives one to the items that have
none. Items with no script are not run offline: they are listed as `live` (owed to the live run), never counted as passed.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import json
import re
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "evals"))
import scorers as S  # noqa: E402

UNIVERSE = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
# role -> first name of the seeded person; data_engineer is a seat (Leo Park, analyst) the runner needs to reject Span's pending changes
PERSON = {"sponsor": "daniel", "analyst": "mei", "approver": "raj", "participant": "sofia", "company_admin": "grace", "owner": "helen",
          "data_engineer": "leo", "head_of_data": "anita"}
AGENTS = ("north", "span", "lumen", "tally", "memory", "matrix")
TIMEOUT = 240  # a real model turn can take minutes
# No product route deletes a draft intent (checked 9 Oct: only cancel / admin-cancel, which keep the record). The intents North evals start
# are listed in REPORT.md for manual cleanup; once a delete route exists, set its path here (e.g. "/api/v1/intents/{iid}") and the runner uses it.
DRAFT_DELETE: str | None = None
STUDIO_TITLE = "Eval studio"  # the harness's own draft dashboard in the Build studio, one per maker (EVT-T1)
DRAFT_STATES = {"draft", "drafting", "cancelled", "withdrawn"}  # never the target of an {iid:...} placeholder unless the spec names the state
NET_ERRORS = (requests.RequestException, httpx.HTTPError)  # a live server (requests) or the in-process app (httpx, --offline)


# ---- sign-in ---------------------------------------------------------------------------------------------------------------------

def creds_for(path: str, role: str, company: str) -> tuple[str, str]:
    """(email, password) of the person for a role in the company: the row named for the person, else the row whose roles column is the role."""
    rows = [l.split() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
    rows = [r for r in rows if len(r) >= 3 and "@" in r[0] and company in r[0].lower() + " " + " ".join(r[3:]).lower()]
    hit = next((r for r in rows if r[0].lower().startswith(PERSON.get(role, "~") + ".")), None) or next((r for r in rows if len(r) > 2 and role in r[2].split(",")), None)
    if not hit:
        raise LookupError(f"no sign-in for role {role} in company {company}")
    return hit[0], hit[1]


class Client:
    """One signed-in session. `fresh()` signs the same person in again (a second session)."""

    def __init__(self, base: str, creds: str, role: str, company: str, session=requests.Session):
        self.base, self.role, self._session = base.rstrip("/"), role, session
        self.email, self._pw = creds_for(creds, role, company)
        self.s = None
        self.fresh()

    def fresh(self):
        self.s = self._session()
        r = self.s.post(self.base + "/api/auth/login", json={"email": self.email, "password": self._pw}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"sign-in failed for {self.role}: HTTP {r.status_code}")

    def call(self, method: str, path: str, body=None) -> tuple[int, object, int]:
        h = {"x-csrf-token": self.s.cookies.get("sh_csrf", "")} if method != "GET" else {}
        t = time.perf_counter()
        r = self.s.request(method, self.base + path, json=body if method in ("POST", "PUT", "PATCH") else None, headers=h, timeout=TIMEOUT)
        ms = round((time.perf_counter() - t) * 1000)
        try:
            return r.status_code, r.json(), ms
        except ValueError:
            return r.status_code, {"text": r.text[:2000]}, ms


# ---- placeholders ----------------------------------------------------------------------------------------------------------------

class Unresolved(Exception):
    pass


class Ctx:
    def __init__(self, base, creds, company, session=requests.Session):
        self.base, self.creds, self.company, self.session = base, creds, company, session
        self.clients: dict[str, Client] = {}
        self.pid = self.did = None
        self.studios: dict[str, str] = {}  # role -> the role's own studio draft (EVT-T1)
        self.mem_base: dict = {}  # role -> (memory ids, summary ids) as first seen: the clean state each item starts from

    def client(self, role: str) -> Client:
        if role not in self.clients:
            self.clients[role] = Client(self.base, self.creds, role, self.company, self.session)
        return self.clients[role]

    def project(self, c: Client) -> str:
        if not self.pid:
            st, js, _ = c.call("GET", "/api/v1/build/projects")
            title = UNIVERSE["project"]["title"]
            self.pid = next((p["id"] for p in (js.get("projects") if isinstance(js, dict) else None) or [] if p.get("title") == title), None)
            if not self.pid:
                raise Unresolved(f"project '{title}' not found (HTTP {st})")
        return self.pid

    def studio(self, c: Client) -> str:
        """EVT-T1: the role's own draft dashboard in the Build studio, where Lumen builds tiles (OP1). The seeded dashboard is its maker's
        private draft, so a maker builds on her own: the draft titled STUDIO_TITLE, made once and kept (tiles proposed on it are rejected)."""
        if c.role not in self.studios:
            base = f"/api/v1/build/p/{self.project(c)}/studio"
            st, js, _ = c.call("GET", base)
            did = next((d["id"] for d in (js.get("dashboards") if isinstance(js, dict) else None) or []
                        if d.get("title") == STUDIO_TITLE and d.get("status") == "draft"), None)
            if not did:
                st, js, _ = c.call("POST", base, {"title": STUDIO_TITLE})
                did = js.get("id") if st == 200 and isinstance(js, dict) else None
            if not did:
                raise Unresolved(f"no studio dashboard for {c.role} (HTTP {st})")
            self.studios[c.role] = did
        return self.studios[c.role]

    def find_case(self, c: Client, spec: str) -> str:
        parts = spec.split("|")
        typ = next((p[5:] for p in parts if p.startswith("type=")), "")
        needles = [p.lower() for p in parts if not p.startswith("type=")]
        for q in ([f"?exception_type={typ}"] if typ else []) + [""]:
            _, js, _ = c.call("GET", "/api/v1/cases" + q)
            for r in (js.get("cases") if isinstance(js, dict) else None) or []:
                if all(n in str(r.get("title", "")).lower() for n in needles):
                    return str(r["id"])
        raise Unresolved(f"no case matching '{spec}' visible to {c.role}")

    def find_intent(self, c: Client, spec: str) -> str:
        """`title[|state=open]`: the intent whose title IS the title named (else begins with it), in the state named (default: not a draft).
        EVT-T3: matching anywhere in the record found a person's own leftover question-intent ("What does the office already have about the
        monthly investment report") instead of the signed "Monthly investment report in USD and SGD"; the list shows no signed flag, so the
        title itself is the key."""
        parts = spec.split("|")
        state = next((p[6:] for p in parts if p.startswith("state=")), None)
        want = " ".join(p for p in parts if not p.startswith("state=")).strip().lower()
        _, js, _ = c.call("GET", "/api/intents")
        rows = js if isinstance(js, list) else (js.get("items") or js.get("intents") or []) if isinstance(js, dict) else []
        rows = [r for r in rows if (r.get("state") == state if state else r.get("state") not in DRAFT_STATES)]
        for test in (lambda t: t == want, lambda t: t.startswith(want)):
            hit = next((r for r in rows if test(str(r.get("title", "")).strip().lower())), None)
            if hit:
                return str(hit["id"])
        raise Unresolved(f"no intent matching '{spec}' visible to {c.role}")

    def as_admin_if_hidden(self, find, c: Client, spec: str) -> str:
        """The id as this role sees it; when the role cannot see it, the company admin's id, so the item's call tests the role's refusal
        (a participant's 403 on the signed intent) instead of stopping before it (ev.8)."""
        try:
            return find(c, spec)
        except Unresolved:
            if c.role == "company_admin":
                raise
            return find(self.client("company_admin"), spec)

    def fill(self, text: str, c: Client, saved: dict) -> str:
        def one(m):
            k = m.group(1)
            if k == "pid":
                return self.project(c)
            if k == "did":
                self.did = self.did or UNIVERSE["project"]["dashboard_id"]
                return self.did
            if k == "sdid":
                return self.studio(c)
            if k.startswith("case:"):
                return self.as_admin_if_hidden(self.find_case, c, k[5:])
            if k.startswith("iid:"):
                return self.as_admin_if_hidden(self.find_intent, c, k[4:])
            if k.startswith("saved."):
                if k[6:] not in saved or saved[k[6:]] is None:
                    raise Unresolved(f"nothing saved as '{k[6:]}'")
                return str(saved[k[6:]])
            return m.group(0)
        return re.sub(r"\{([^{}]+)\}", one, text)


# ---- one item --------------------------------------------------------------------------------------------------------------------

def find_key(obj, key):
    if isinstance(obj, dict):
        if obj.get(key):
            return obj[key]
        return next((x for v in obj.values() if (x := find_key(v, key))), None)
    if isinstance(obj, list):
        return next((x for v in obj if (x := find_key(v, key))), None)
    return None


def cells(rows) -> list:
    out = []
    for r in rows or []:
        out += [v for v in (r.values() if isinstance(r, dict) else r) if isinstance(v, (int, float, str))]
    return out


def file_part(turn: dict) -> tuple[list, str]:
    p = ROOT / turn["file"]
    if p.suffix.lower() == ".pdf":  # the research docs are PDFs: send their text, so `replace` can plant a passage
        from pypdf import PdfReader
        text = "\n".join(pg.extract_text() or "" for pg in PdfReader(p).pages)
    else:
        text = p.read_text(encoding="utf-8")
    for a, b in (turn.get("replace") or {}).items():
        text = text.replace(a, b)
    name = Path(turn.get("file_name") or p.name)
    name = f"{name.stem}-{uuid.uuid4().hex[:8]}{name.suffix}"  # unique per upload: a name already there with other text answers 409 (ev.5)
    return [{"name": name, "data": base64.b64encode(text.encode("utf-8")).decode(), "kind": None}], text


def probe(ctx: Ctx, c: Client):
    """Router cost log (calls, tokens, rows) and the egress log lines as they stand now."""
    _, cost, _ = c.call("GET", "/api/v1/router/costs")
    adm = ctx.clients.get("company_admin") or c
    st, eg, _ = adm.call("GET", "/api/company/egress-log?limit=500")
    return (cost if isinstance(cost, dict) else {}), ([json.dumps(e, sort_keys=True) for e in eg.get("entries", [])] if st == 200 and isinstance(eg, dict) else None)


def loop_ids(ctx: Ctx) -> list[dict] | None:
    """Loop trace rows ({trace_id, agent, ...}) as they stand now, newest first (company admin only; None when unreadable)."""
    try:
        st, js, _ = ctx.client("company_admin").call("GET", "/api/v1/agent-runs/loops")
    except (LookupError, RuntimeError, *NET_ERRORS):
        return None
    return [r for r in js.get("loops") or [] if isinstance(r, dict) and r.get("trace_id")] if st == 200 and isinstance(js, dict) else None


def item_loop(new: list[dict], agent: str) -> str | None:
    """The item's own loop among the loops it added, newest first: never a talk summary the summariser wrote meanwhile (S.is_summary);
    the item's agent first (a North item's loop, not a memory side loop); None when only summaries were added."""
    runs = [r for r in new if not S.is_summary(r.get("agent"))]
    mine = [r for r in runs if str(r.get("agent", "")).lower() == agent.lower()]
    return next((r["trace_id"] for r in mine or runs), None)


def traces_of(ctx: Ctx, ids: list[str]) -> list[dict]:
    """Each trace's loop runs and total, as GET /api/v1/agent-runs/trace/{id} gives them."""
    out = []
    for tid in ids:
        st, js, _ = ctx.client("company_admin").call("GET", f"/api/v1/agent-runs/trace/{tid}")
        out.append({"trace_id": tid, "status": st, **(js if st == 200 and isinstance(js, dict) else {})})
    return out


def roles_of(item: dict) -> list[str]:
    return list(dict.fromkeys([item["role"]] + [t["as_role"] for t in item.get("turns") or [] if t.get("as_role")]))


def remembered(ctx: Ctx, role: str) -> tuple[set, set]:
    """(memory item ids, talk summary ids) the person holds now."""
    c = ctx.client(role)
    _, me, _ = c.call("GET", "/api/v1/memory/me")
    _, g, _ = c.call("GET", "/api/v1/memory/graph")
    items = {str(i.get("id")) for i in (me.get("items") if isinstance(me, dict) else None) or [] if isinstance(i, dict)}
    sums = {str(n["summary"]["id"]) for n in (g.get("nodes") if isinstance(g, dict) else None) or []
            if isinstance(n, dict) and isinstance(n.get("summary"), dict) and n["summary"].get("id")}
    return items, sums


def forget_new(ctx: Ctx, before: dict) -> list[str]:
    """EVT-20: forget the memory items and talk summaries an item left, so the next item (and the next run) starts clean.
    ponytail: a summary written after the item ended (a background summariser) is caught by the next item's cleanup, not this one."""
    gone = []
    for role, (items0, sums0) in before.items():
        items, sums = remembered(ctx, role)
        c = ctx.client(role)
        for i in items - items0:
            if c.call("DELETE", f"/api/v1/memory/me/{i}")[0] == 200:
                gone.append(f"{role}: memory {i}")
        for sid in sums - sums0:
            if c.call("DELETE", f"/api/v1/memory/summaries/{sid}")[0] == 200:
                gone.append(f"{role}: summary {sid}")
    return gone


def pending_changes(ctx: Ctx, pid: str) -> set[str]:
    _, js, _ = ctx.client("data_engineer").call("GET", f"/api/v1/build/p/{pid}/plan")
    return {str(c["id"]) for c in (js.get("changes") if isinstance(js, dict) else None) or []
            if isinstance(c, dict) and c.get("status", "pending") == "pending"}


def reject_new_changes(ctx: Ctx, pid: str, before: set[str]) -> list[str]:
    """EVT-18: a change Span proposed during an item is turned down by the data engineer afterwards, so it never leaks into the next item."""
    c = ctx.client("data_engineer")
    return [cid for cid in sorted(pending_changes(ctx, pid) - before)
            if c.call("POST", f"/api/v1/build/p/{pid}/plan/changes/{cid}/reject", {"reason": "eval cleanup"})[0] == 200]


def run_item(ctx: Ctx, item: dict, mode: str) -> dict:
    c0 = ctx.client(item["role"])
    # EVT-20: a talk summary is written when a talk reaches its turn count and may show on the map only later, so what an earlier item left
    # (after its own cleanup ran) is forgotten here too, back to the state the run first saw for each person
    for r in roles_of(item):
        ctx.mem_base.setdefault(r, remembered(ctx, r))
    left = forget_new(ctx, {r: ctx.mem_base[r] for r in roles_of(item)})
    mem0 = {r: ctx.mem_base[r] for r in roles_of(item)}
    pid = None
    if "/build/p/" in json.dumps(item):
        try:
            pid = ctx.project(ctx.client("data_engineer"))
        except (Unresolved, LookupError, RuntimeError):
            pid = None
    changes0 = pending_changes(ctx, pid) if pid else set()
    loops0 = loop_ids(ctx)
    saved: dict = {}
    res = {"turns": [], "rows": [], "row_texts": [], "tiles": [], "vars": {}, "statuses": [], "intents": []}
    made: list[tuple[Client, str, str]] = []  # tiles Lumen proposed: rejected afterwards
    before_cost, before_eg = probe(ctx, c0)
    route = item["route"]
    turns = item.get("turns") or [{}]
    t0 = time.perf_counter()
    todo = list(turns)
    failed = False
    for turn in todo:
        if failed and not turn.get("cleanup"):
            continue
        c = ctx.client(turn.get("as_role") or item["role"])
        if turn.get("new_login"):
            c.fresh()
        method = turn.get("method") or route["method"]
        try:
            path = ctx.fill(turn.get("path") or route["path"], c, saved)
            body, ftext = None, ""
            if method in ("POST", "PUT", "PATCH"):
                body = dict(turn["body"]) if turn.get("body") else {}
                if turn.get("say"):
                    body[route.get("field", "text")] = turn["say"]
                if turn.get("file"):
                    body["files"], ftext = file_part(turn)
            if turn.get("accept_pending"):  # EVT-17: a person accepts what North proposed (human in the loop), as the item's own role
                res["turns"] += accept_all(c, path)
                continue
        except Unresolved as e:
            if turn.get("cleanup"):  # nothing to clean up (MEM-09: the figure was rightly never stored), not an error
                continue
            res["error"] = str(e)
            failed = True
            continue
        st, js, ms = c.call(method, path, body)
        rec = {"role": c.role, "method": method, "path": path, "request": body if not body or "files" not in body else {**body, "files": [f["name"] for f in body["files"]]},
               "status": st, "json": js, "ms": ms, "expect": turn.get("expect"), "file_text": ftext, "cleanup": bool(turn.get("cleanup")),
               "reply": bool(turn.get("say") or turn.get("reply"))}
        res["turns"].append(rec)
        res["statuses"].append(st)
        if method == "POST" and path == "/api/v1/intents/chat" and st == 200 and isinstance(js, dict) and js.get("id"):
            res["intents"].append((c, str(js["id"])))  # a draft intent North started: deleted (or listed) when the run ends
        for name, p in (turn.get("save") or {}).items():
            saved[name] = js if p == "$" else S._walk(js, p)
            res["vars"][name] = saved[name]
        if isinstance(js, dict) and isinstance(js.get("proposals"), list) and "/ask" in path:
            tile = js["proposals"][0] if js["proposals"] else None
            res["tiles"].append(tile)
            # EVT-T1: tiles are built in the Build studio (/studio/{did}/ask, OP1) as well as asked about in Consume (/dashboards/{did}/ask)
            m = re.search(r"/(dashboards|studio)/([^/]+)/ask$", path)
            did = js.get("dashboard_id") or (m[2] if m else None)
            dash = path[:m.start()] + f"/{m[1]}/{did}" if m and did else None
            if tile and tile.get("id") and dash:
                made.append((c, dash, tile["id"]))
            if tile and item.get("fetch_tile") and tile.get("id") and dash:
                s2, d2, _ = c.call("GET", dash + f"/tiles/{tile['id']}/data")
                if s2 == 200 and isinstance(d2, dict):
                    res["rows"] += cells(d2.get("rows"))
                    res["row_texts"] += [json.dumps(r, default=str) for r in d2.get("rows") or []]
        if isinstance(js, dict) and "rows" in js and method == "GET" and "/tiles/" in path:
            res["rows"] += cells(js["rows"])
            res["row_texts"] += [json.dumps(r, default=str) for r in js["rows"]]
        if st >= 400 and not turn.get("expect") and not turn.get("cleanup") and (item.get("expected") or {}).get("status", 200) < 400:
            failed = True  # later turns would only pile on
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    res["sources"] = source_rows(ctx, item, saved, res)
    for c, base_path, tid in made:  # leave the dashboard as seeded
        try:
            c.call("POST", f"{base_path}/tiles/{tid}/reject")
        except NET_ERRORS:
            pass
    main = [t for t in res["turns"] if not t["cleanup"]]
    last = main[-1] if main else {"status": None, "json": None}
    res["status"], res["json"] = last["status"], last["json"]
    said = [t for t in main if t.get("reply")]
    res["reply"] = said[-1]["json"] if said else last["json"]  # EVT-19: the agent's own words, not a plan GET that follows them
    loops1 = loop_ids(ctx)
    seen0 = {r["trace_id"] for r in loops0 or []}
    new = [r for r in loops1 or [] if r["trace_id"] not in seen0] if loops0 is not None else []
    res["trace_id"] = next((find_key(t["json"], "trace_id") for t in main if find_key(t["json"], "trace_id")), None) or item_loop(new, item["agent"])
    res["traces"] = traces_of(ctx, list(dict.fromkeys(([res["trace_id"]] if res["trace_id"] else []) + [r["trace_id"] for r in new])))         if loops1 is not None else None
    res["forgotten"] = [f"before: {x}" for x in left] + forget_new(ctx, mem0) + ([f"plan change {x}" for x in reject_new_changes(ctx, pid, changes0)] if pid else [])
    after_cost, after_eg = probe(ctx, c0)
    n = max(0, (after_cost.get("calls") or 0) - (before_cost.get("calls") or 0))
    rows = (after_cost.get("rows") or [])[-n:] if n else []
    res["cost"] = {"calls": n, "tokens": sum((r.get("tokens_in") or 0) + (r.get("tokens_out") or 0) for r in rows), "usd": usd_for(res.get("traces")),
                   "estimated": any(r.get("estimated") for r in rows)} if n else None
    res["egress"] = None if after_eg is None or before_eg is None else [json.loads(x) for x in (Counter(after_eg) - Counter(before_eg)).elements()]
    return res


def source_rows(ctx: Ctx, item: dict, saved: dict, res: dict) -> list[dict]:
    """EVT-T2: an answer on a chat route (/consume/chat, Tally's ask) carries words only and the trace keeps the size of a tool result, not its
    values, so groundedness had no source to check a correct figure against. An item's `sources:` names the product's own read routes that hold
    the figures the agent's tools read (the tile data, why-moved). They are read here, after the turns, as the company admin (the program's
    truth: whether the role may see a figure is the access scorer's question) and their values join `rows`, the program-filled pool."""
    out = []
    for spec in item.get("sources") or []:
        spec = spec if isinstance(spec, dict) else {"path": spec}
        c = ctx.client(spec.get("as_role") or "company_admin")
        try:
            path = ctx.fill(spec["path"], c, saved)
            st, js, _ = c.call("GET", path)
        except (Unresolved, *NET_ERRORS) as e:
            out.append({"path": spec["path"], "status": None, "error": str(e)})
            continue
        vals = [v for _, v in S.leaves(js)] if st == 200 else []
        res["rows"] += vals
        out.append({"path": path, "status": st, "values": len(vals)})
    return out


def usd_for(traces) -> float | None:
    """Dollars of the item's traces: each trace's total (the loop steps' prices), else its agent runs' cost."""
    vals = []
    for t in traces or []:
        tot = (t.get("total") or {}).get("cost_usd")
        vals += [tot] if tot is not None else [r.get("cost_usd") for r in t.get("runs") or [] if r.get("cost_usd") is not None]
    return round(sum(vals), 6) if vals else None


def _rec(c: Client, method: str, path: str, st, js, ms) -> dict:
    return {"role": c.role, "method": method, "path": path, "request": None, "status": st, "json": js, "ms": ms, "expect": None,
            "file_text": "", "cleanup": False, "reply": False}


def accept_all(c: Client, chat_path: str) -> list[dict]:
    """Accept every pending proposal on the intent of `chat_path` (/api/v1/intents/{iid}/...), oldest first."""
    iid = re.search(r"/api/v1/intents/([^/]+)", chat_path)[1]
    st, js, ms = c.call("GET", f"/api/v1/intents/{iid}/proposals")
    out = [_rec(c, "GET", f"/api/v1/intents/{iid}/proposals", st, js, ms)]
    for p in (js.get("pending") if isinstance(js, dict) else None) or []:
        path = f"/api/v1/intents/{iid}/proposals/{p['id']}/accept"
        out.append(_rec(c, "POST", path, *c.call("POST", path)))
    return out


def clean_drafts(made: list) -> list[str]:
    """Delete the draft intents the North items started, through DRAFT_DELETE. Returns the ids left behind (for the report)."""
    left = []
    for c, iid in made:
        try:
            st = c.call("DELETE", DRAFT_DELETE.format(iid=iid))[0] if DRAFT_DELETE else None
        except NET_ERRORS:
            st = None
        if st not in (200, 204):
            left.append(iid)
    return left


def missing_route(res: dict) -> bool:
    t = (res["turns"] or [{}])[0]
    return t.get("status") in (404, 405) and isinstance(t.get("json"), dict) and t["json"].get("detail") in ("Not Found", "Method Not Allowed")


def status_of(item: dict, res: dict, scores: list[dict]) -> str:
    if res.get("error") and not res["turns"]:
        return "error"
    if item.get("pending_if_missing") and (missing_route(res) or (res.get("error") and "route" in res["error"])):
        return "pending"
    if res.get("error"):
        return "error"
    return "pass" if all(s["passed"] is not False for s in scores) else "fail"


# ---- modes and loading -----------------------------------------------------------------------------------------------------------

def set_mode(ctx: Ctx, want: str) -> tuple[str | None, str]:
    """Flip Testing / Real use through the product route. Returns (the mode it found, a note)."""
    c = ctx.client("company_admin")
    st, js, _ = c.call("GET", "/api/v1/router/mode")
    old = js.get("mode") if st == 200 and isinstance(js, dict) else None
    if old == want:
        return old, f"mode already {want}"
    st, js, _ = c.call("POST", "/api/v1/router/mode", {"mode": want})
    return old, (f"mode switched {old} -> {want}" if st == 200 else f"could not switch mode (HTTP {st}); items ran in {old or 'the current'} mode")


def load_items(agents, only) -> list[dict]:
    out = []
    for a in agents:
        f = ROOT / "tests" / "evals" / f"{a}.yaml"
        if f.is_file():
            out += [i for i in yaml.safe_load(f.read_text(encoding="utf-8")) or [] if not only or i["id"] in only]
    return out


# ---- the report ------------------------------------------------------------------------------------------------------------------

def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))] if xs else None


def report_md(rows: list[dict], meta: dict) -> str:
    L = [f"# Agent eval report: {meta.get('mode', '?')} mode", "",
         f"Run {meta.get('at', '')} against {meta.get('base', '')}. {len(rows)} items. {meta.get('note', '')}", ""]
    cnt = Counter(r["status"] for r in rows)
    L += [f"Pass {cnt['pass']}, fail {cnt['fail']}, error {cnt['error']}, pending {cnt['pending']} (pending = the route does not exist yet)"
          + (f", live {cnt['live']} (no offline replay script: owed to the live run, not run)" if cnt["live"] else "") + ".", "",
          "## Pass rate per agent", "", "| Agent | Items | Pass | Fail | Error | Pending | Pass rate (of items that ran) |", "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[r["agent"]].append(r)
    for a, rs in by.items():
        c = Counter(r["status"] for r in rs)
        ran = len(rs) - c["pending"] - c["live"]
        L.append(f"| {a} | {len(rs)} | {c['pass']} | {c['fail']} | {c['error']} | {c['pending']} | {pct(c['pass'], ran)} |")
    L += ["", "## Pass rate per scorer", "", "| Scorer | Scored | Pass | Fail | Pass rate |", "|---|---|---|---|---|"]
    sc = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["status"] in ("pending", "live"):
            continue
        for s in r["scores"]:
            if s["passed"] is not None:
                sc[s["name"]][0] += 1
                sc[s["name"]][1] += bool(s["passed"])
    for n, (tot, ok) in sorted(sc.items()):
        L.append(f"| {n} | {tot} | {ok} | {tot - ok} | {pct(ok, tot)} |")
    L += ["", "## Cost and latency per agent", "", "| Agent | Median ms | p95 ms | Calls | Tokens | USD (agent-runs) | Egress lines | Egress blocked |", "|---|---|---|---|---|---|---|---|"]
    for a, rs in by.items():
        ms = [r["latency_ms"] for r in rs if r["status"] != "pending" and r.get("latency_ms") is not None]
        cs = [r["cost"] for r in rs if r.get("cost")]
        usd = [c["usd"] for c in cs if c.get("usd") is not None]
        eg = [r["egress_lines"] for r in rs if r.get("egress_lines") is not None]
        L.append(f"| {a} | {int(statistics.median(ms)) if ms else '-'} | {p95(ms) or '-'} | {sum(c['calls'] for c in cs)} | {sum(c['tokens'] for c in cs)} | "
                 f"{round(sum(usd), 4) if usd else '-'} | {sum(eg) if eg else '-'} | {sum(r.get('egress_blocked') or 0 for r in rs)} |")
    bad = [r for r in rows if r["status"] in ("fail", "error")]
    L += ["", "## Worst items", ""]
    if not bad:
        L.append("No failed items.")
    for r in bad[:20]:
        why = "; ".join(f"{s['name']}: {s['detail']}" for s in r["scores"] if s["passed"] is False) or r.get("error", "")
        L.append(f"- **{r['id']}** ({r['agent']}, {r['role']}, {r['status']}): {r['desc']} -> {why}")
    slow = sorted((r for r in rows if r.get("latency_ms") and r["status"] != "pending"), key=lambda r: -r["latency_ms"])[:5]
    L += ["", "## Slowest items", ""] + [f"- {r['id']}: {r['latency_ms']} ms" for r in slow]
    if meta.get("drafts_left"):
        L += ["", "## Draft intents to delete by hand", "", "The North items started these intents and no product route deletes a draft yet. "
              "Delete them by hand (or cancel each one) so they do not crowd the Intent Centre:", ""] + [f"- {i}" for i in meta["drafts_left"]]
    live = [r for r in rows if r["status"] == "live"]
    if live:
        L += ["", "## Owed to the live run (no offline replay script)", ""] + [f"- {r['id']}: {r['desc']}" for r in live]
    pend = [r for r in rows if r["status"] == "pending"]
    if pend:
        L += ["", "## Pending (route not built yet)", ""] + [f"- {r['id']}: {r['desc']}" for r in pend]
    L += ["", "Per-item request, response, scores, trace id, cost and latency: `items/<id>.json`.", ""]
    return "\n".join(L)


def compare_md(a: Path, b: Path) -> str:
    A = {r["id"]: r for r in json.loads((a / "summary.json").read_text(encoding="utf-8"))["items"]}
    B = {r["id"]: r for r in json.loads((b / "summary.json").read_text(encoding="utf-8"))["items"]}
    ma, mb = (json.loads((x / "summary.json").read_text(encoding="utf-8")).get("mode", x.name) for x in (a, b))
    L = [f"# Agent eval comparison: {ma} ({a.name}) against {mb} ({b.name})", "", "| Agent | Pass rate " + ma + " | Pass rate " + mb + " | Median ms " + ma + " | Median ms " + mb + " | Tokens " + ma + " | Tokens " + mb + " |", "|---|---|---|---|---|---|---|"]
    for ag in AGENTS:
        def stats(D):
            rs = [r for r in D.values() if r["agent"] == ag and r["status"] not in ("pending", "live")]
            ms = [r["latency_ms"] for r in rs if r.get("latency_ms") is not None]
            return pct(sum(r["status"] == "pass" for r in rs), len(rs)), (int(statistics.median(ms)) if ms else "-"), sum((r.get("cost") or {}).get("tokens", 0) for r in rs)
        if any(r["agent"] == ag for r in list(A.values()) + list(B.values())):
            (pa, la, ta), (pb, lb, tb) = stats(A), stats(B)
            L.append(f"| {ag} | {pa} | {pb} | {la} | {lb} | {ta} | {tb} |")
    L += ["", "## Items that differ", "", "| Item | " + ma + " | " + mb + " | What changed |", "|---|---|---|---|"]
    for i in sorted(set(A) | set(B)):
        x, y = A.get(i), B.get(i)
        if (x or {}).get("status") != (y or {}).get("status"):
            det = "; ".join(f"{s['name']}: {s['detail']}" for s in ((y if (y or {}).get("status") == "fail" else x) or {}).get("scores", []) if s["passed"] is False)
            L.append(f"| {i} | {(x or {}).get('status', '-')} | {(y or {}).get('status', '-')} | {det[:200]} |")
    return "\n".join(L) + "\n"


# ---- main ------------------------------------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", help="server URL, e.g. http://127.0.0.1:8711 (never 8400)")
    ap.add_argument("--creds", help="seed_credentials.txt")
    ap.add_argument("--company", default="evergreen")
    ap.add_argument("--mode", choices=("testing", "real"), default=None, help="set the Testing / Real use switch for the run (put back at the end)")
    ap.add_argument("--agents", default=",".join(AGENTS))
    ap.add_argument("--items", default="", help="comma list of item ids")
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"))
    ap.add_argument("--keep-mode", action="store_true", help="leave the switch as --mode set it when the run ends (for probes that follow)")
    ap.add_argument("--offline", action="store_true", help="no server, no model account: the product in process, model calls replayed")
    ap.add_argument("--data-root", help="--offline: the scratch data root to seed and use (default: a new temporary folder; never data/)")
    ap.add_argument("--replay", help="--offline: the recorded shape (tests/evals/replay.py SHAPES) for items with no `replay:` of their own")
    a = ap.parse_args(argv)
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    if a.compare:
        (out / "COMPARE.md").write_text(compare_md(*[Path(x) if Path(x).is_absolute() else ROOT / x for x in a.compare]), encoding="utf-8")
        print(f"wrote {out / 'COMPARE.md'}")
        return 0
    items = load_items([x for x in a.agents.split(",") if x], set(filter(None, a.items.split(","))))
    with contextlib.ExitStack() as stack:
        if a.offline:
            ctx, rp = offline_ctx(a, stack)
        else:
            if not (a.base and a.creds):
                ap.error("--base and --creds are required to run (or --offline)")
            if re.search(r":8400\b", a.base):
                ap.error("port 8400 is not for evals")
            ctx, rp = Ctx(a.base, a.creds, a.company), None
        return run_and_report(a, ctx, items, out, rp)


def offline_ctx(a, stack: contextlib.ExitStack):
    """W2-H: the seeded universe in a scratch data root, the app in process, every model call replayed (tests/evals/replay.py)."""
    import os
    import tempfile
    sys.path.insert(0, str(ROOT))  # sh_platform and tools.seed_10uc, when run as python tools/run_evals.py
    from fastapi.testclient import TestClient
    import replay as R
    from sh_platform.app import create_app
    from sh_platform.settings import Settings
    from tools import seed_10uc
    root = Path(a.data_root).resolve() if a.data_root else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="sh-evals-offline-")))
    data = (ROOT / "data").resolve()
    if root == data or data in root.parents:
        raise SystemExit("--data-root must be a scratch folder, never data/")
    seed_10uc.seed(root)  # idempotent: a second run on the same root changes nothing
    rp = stack.enter_context(R.install(a.replay or "no_credit"))
    secret = os.environ.get("SH_SESSION_SECRET") or uuid.uuid4().hex  # the in-process app's own cookie key, never written anywhere
    app = create_app(Settings(mode="dev", data_root=str(root), session_secret=secret))
    base = "http://testserver"
    a.base = f"offline ({root})"
    return Ctx(base, str(root / "_control" / "seed_credentials.txt"), a.company,
               session=lambda: TestClient(app, base_url=base, raise_server_exceptions=False)), rp


def run_and_report(a, ctx: Ctx, items: list[dict], out: Path, rp=None) -> int:
    note, old = "", None
    try:
        ctx.client("company_admin")
        if a.mode:
            old, note = set_mode(ctx, a.mode)
        else:
            _, js, _ = ctx.client("company_admin").call("GET", "/api/v1/router/mode")
            a.mode = js.get("mode", "unknown") if isinstance(js, dict) else "unknown"
    except (LookupError, RuntimeError, *NET_ERRORS) as e:
        note = f"admin sign-in or mode switch failed ({e}); costs per call in dollars and the egress log are unavailable"
    (out / "items").mkdir(exist_ok=True)
    rows, drafts, stopped = [], [], False
    try:
        run_all(ctx, items, a.mode, out, rows, drafts, rp, getattr(a, "replay", None))
    except KeyboardInterrupt:  # H residual 1: the items already run are still reported
        stopped = True
        note += f" Stopped by Ctrl-C after {len(rows)} of {len(items)} items; the rest did not run."
    finally:
        note += restore_mode(ctx, old, a.mode, a.keep_mode)
    meta = {"mode": f"{a.mode}{' (offline replay)' if rp else ''}", "base": a.base, "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "note": note.strip(), "stopped": stopped, "drafts_left": clean_drafts(drafts)}
    (out / "summary.json").write_text(json.dumps({**meta, "items": rows}, indent=2, default=str), encoding="utf-8")
    (out / "REPORT.md").write_text(report_md(rows, meta), encoding="utf-8")
    print(f"wrote {out / 'REPORT.md'}")
    return 130 if stopped else 1 if any(r["status"] in ("fail", "error") for r in rows) else 0


def restore_mode(ctx: Ctx, old: str | None, mode: str, keep: bool) -> str:
    """ER-17: put the switch back (or say it was kept), loudly: a probe started after a --mode real run must know which mode it gets."""
    if not old or old == mode:
        return ""
    if keep:
        msg = f" Mode left at {mode} (--keep-mode); it was {old} before the run."
    else:
        try:
            st = ctx.client("company_admin").call("POST", "/api/v1/router/mode", {"mode": old})[0]
            msg = f" Mode put back to {old} at the end of the run." if st == 200 else f" Could not put the mode back to {old} (HTTP {st}): it is still {mode}."
        except (LookupError, RuntimeError, *NET_ERRORS) as e:
            msg = f" Could not put the mode back to {old} ({type(e).__name__}): it is still {mode}."
    print("MODE:" + msg, file=sys.stderr, flush=True)
    return msg


def run_all(ctx: Ctx, items: list[dict], mode: str, out: Path, rows: list, drafts: list, rp=None, default_replay=None) -> None:
    for it in items:
        if rp is not None and not (it.get("replay") or default_replay):  # offline with no script: owed to the live run, never a pass
            rows.append({"id": it["id"], "agent": it["agent"], "role": it["role"], "desc": it["desc"], "status": "live", "scores": [], "error": None})
            print(f"{'LIVE':8} {it['id']:12} {it['desc'][:70]}", flush=True)
            continue
        if rp is not None:
            rp.load(it.get("replay") or default_replay)
        try:
            res = run_item(ctx, it, mode)
        except (LookupError, RuntimeError, *NET_ERRORS) as e:
            res = {"turns": [], "rows": [], "tiles": [], "statuses": [], "error": f"{type(e).__name__}: {e}"}
        drafts += res.get("intents") or []
        scores = S.score(it, res) if res["turns"] else []
        st = status_of(it, res, scores)
        row = {"id": it["id"], "agent": it["agent"], "role": it["role"], "desc": it["desc"], "status": st, "scores": scores, "error": res.get("error"),
               "latency_ms": res.get("latency_ms"), "cost": res.get("cost"), "trace_id": res.get("trace_id"), "forgotten": res.get("forgotten"),
               "egress_lines": None if res.get("egress") is None else len(res["egress"]),
               "egress_blocked": sum(1 for e in res.get("egress") or [] if str(e.get("decision")).lower() in ("blocked", "refused"))}
        if rp is not None:
            row["replay"] = {"script": rp.spec if isinstance(rp.spec, str) else "inline", "model_calls": len(rp.seen)}
        rows.append(row)
        full = {**row, "mode": mode, "route": it["route"], "expected": it.get("expected"), "turns": [{k: v for k, v in t.items() if k != "file_text"} for t in res["turns"]],
                "rows_seen": len(res.get("rows") or []), "sources": res.get("sources"), "egress": res.get("egress"), "traces": res.get("traces")}
        (out / "items" / f"{it['id']}.json").write_text(json.dumps(full, indent=2, default=str), encoding="utf-8")
        print(f"{st.upper():8} {it['id']:12} {it['desc'][:70]}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
