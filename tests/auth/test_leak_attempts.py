"""X9 data-leak attempts: what participant, owner and approver of ardmore must never read, tried as they would try it.

Runs the real app on a temporary copy of the real data root (same harness as test_role_matrix.py). Every needle is read from the
copied plane, so the test follows a reseed: the gold figures of K06 and K16 (the restricted measures), the text of sealed cards, the
author of each anonymous card, join keys and seat tokens, other people's memory and room text, and the other company's ids.
A positive control (the company admin does see K06) proves the grep is alive. Skipped if the seed credentials are absent.
"""
import glob
import json
import re
import shutil
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file() or not (ROOT / "data" / "ardmore").is_dir(), reason="no seeded demo data")

CO, OTHER = "ardmore", "lakeside-family-office"
RESTRICTED = ("K06", "K16")
ROLES = ["participant", "owner", "approver"]
M1 = "/api/modules/m1_intent"


def canon(x) -> str | None:
    try:
        return f"{round(float(str(x).replace(',', '')), 2):.2f}"
    except ValueError:
        return None


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def jload(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def gold(data: Path, co: str) -> dict[str, set[str]]:
    db = data / co / "warehouse" / "company.readonly.duckdb"
    out: dict[str, set[str]] = {}
    if not db.exists():
        return out
    con = duckdb.connect(str(db), read_only=True)
    try:
        for (t,) in con.execute("select table_name from information_schema.tables where table_schema='gold'").fetchall():
            cols = con.execute("select column_name, data_type from information_schema.columns where table_schema='gold' and table_name=?", [t]).fetchall()
            num = [c for c, d in cols if c != "period" and any(k in d.upper() for k in ("INT", "DOUBLE", "DECIMAL", "FLOAT", "REAL"))]
            vc = "value" if any(c == "value" for c, _ in cols) else (num[0] if num else None)
            if vc:
                out[t.upper()] = {canon(r[0]) for r in con.execute(f"select {vc} from gold.{t} where {vc} is not null").fetchall()} - {None}
    finally:
        con.close()
    return out


class Needles:
    def __init__(self, data: Path):
        self.gold = gold(data, CO)
        # A figure that an open measure also has (a 0.89 coverage ratio) proves nothing about a restricted one: keep each restricted
        # measure's own figures only.
        opn = set().union(*[v for k, v in self.gold.items() if k not in RESTRICTED])
        self.gold = {k: (v - opn if k in RESTRICTED else v) for k, v in self.gold.items()}
        self.sealed, self.anon, self.keys, self.memory = set(), {}, set(), {}
        m1 = data / CO / "intents" / "m1_intent"
        author_of = {}
        for f in glob.glob(str(m1 / "transcripts/*/*.json")):
            d = jload(f) or {}
            ns = d.get("notes", [])
            who = next((x["author_name"] for x in ns if x.get("author_name")), None)  # one seat, one author
            slug = re.sub(r"\W+", "-", who.lower()) if who else None
            for x in ns:
                if who:
                    author_of[x["id"]] = author_of[x.get("text")] = who
            for t in d.get("turns", []):
                if slug and isinstance(t, dict) and len(t.get("text") or "") > 25:
                    self.memory.setdefault(slug, set()).add(t["text"])
        for f in glob.glob(str(m1 / "notes/*.json")):
            for x in (jload(f) or {}).get("notes", []):
                if x.get("restricted"):
                    self.sealed |= {t for t in [x.get("text")] + [q.get("text") for q in (x.get("quarters") or {}).values()] if t and len(t) > 12}
                who = author_of.get(x["id"]) or author_of.get(x.get("text"))
                if x.get("anonymous") and who:
                    self.anon[x["id"]] = (x["text"], who)
        for f in glob.glob(str(m1 / "join_links/*.json")):
            if (jload(f) or {}).get("sealed"):
                self.keys.add(jload(f)["sealed"][:40])
        key = data / CO / "context" / "join_link.key"
        if key.exists():
            self.keys.add(key.read_text().strip()[:40])
        for f in glob.glob(str(m1 / "rooms/*.json")):
            self.keys |= {s["token_hash"] for s in (jload(f) or {}).get("seats", []) if s.get("token_hash")}
        for f in glob.glob(str(data / CO / "context/memory/*/people/*.json")):
            self.memory.setdefault(Path(f).stem, set()).update(e["text"] for e in (jload(f) or {}).get("entries", []) if len(e.get("text", "")) > 25)
        # What a person put on the wall is no longer private: the wall shows it (sealed and anonymous cards are checked above).
        self.wall = {x.get("text") for f in glob.glob(str(m1 / "notes/*.json")) for x in (jload(f) or {}).get("notes", [])}
        self.memory = {who: texts - self.wall for who, texts in self.memory.items()}

    def scan(self, me: str, body: str) -> list[str]:
        hits = []
        toks = {canon(t.rstrip(".")) for t in re.findall(r"(?<![\d.,])\d[\d,]*\.?\d*(?![\d])", body)} - {None}
        for code in RESTRICTED:
            found = sorted(self.gold.get(code, set()) & toks)
            if code == "K06" and any(float(f) >= 100000 for f in found):
                hits.append(f"K06 figures {found[:4]}")
            if code == "K16" and len(found) >= 3 and (re.search(code, body, re.I) or "manager" in body.lower()):
                hits.append(f"K16 series {found[:5]}")
        hits += [f"sealed card text {s[:40]!r}" for s in self.sealed if s in body]
        try:
            for d in walk(json.loads(body)):
                who = self.anon.get(d.get("id") or d.get("note_id"), (None, None))[1]
                if who and who != me and any(d.get(k) == who for k in ("author_name", "author", "name", "by")):
                    hits.append(f"anonymous card names its author {who!r}")
                if "authors" in d and "anonymous_seats" in d:
                    hits.append("note_authors map returned")
        except ValueError:
            pass
        hits += [f"join key or seat token {k[:8]}" for k in self.keys if k in body]
        mine = re.sub(r"\W+", "-", me.lower())
        hits += [f"memory or room text of {who}" for who, texts in self.memory.items() if who != mine and any(t in body for t in texts)]
        if "lakeside" in body.lower():
            hits.append("names the other company")
        return hits


class World:
    def __init__(self, tmp: Path):
        self.data = tmp / "data"
        shutil.copytree(ROOT / "data", self.data)
        self.app = create_app(Settings(mode="dev", data_root=str(self.data), session_secret="fake-test-secret-not-real"))
        self.pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
        self.need = Needles(self.data)

    def login(self, role: str, co: str = CO) -> TestClient:
        em = f"{role}.{co}@example.test"
        c = TestClient(self.app)
        assert c.post("/api/auth/login", json={"email": em, "password": self.pw[em]}).status_code == 200, em
        c.me = c.get("/api/auth/me").json()["display_name"]
        return c


def send(c: TestClient, method: str, url: str, **kw):
    kw["headers"] = {**kw.get("headers", {}), "X-CSRF-Token": c.cookies.get("sh_csrf", "")}
    return c.request(method, url, **kw)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    w = World(tmp_path_factory.mktemp("leak"))
    w.admin, w.other = w.login("company_admin"), w.login("company_admin", OTHER)
    w.sessions = [s["id"] for s in w.admin.get("/api/modules/m1_intent/sessions").json()]
    w.other_sessions = [s["id"] for s in w.other.get("/api/modules/m1_intent/sessions").json()]
    w.nodes = [n["id"] for n in w.admin.get("/api/company/graph").json()["nodes"]]
    w.other_nodes = [n["id"] for n in w.other.get("/api/company/graph").json()["nodes"]]
    w.other_baselines = [b["id"] for b in (w.other.get("/api/modules/m2_baseline/baselines").json() or []) if isinstance(b, dict)]
    return w


def figure_routes(w: World) -> list[str]:
    routes = ["/api/company/feeds", "/api/company/register", "/api/company/graph", "/api/company/market", "/api/pulse", "/api/company/build/prove",
              "/api/company/build/home", "/api/company/build/ops", "/api/company/build/blueprint", "/api/company/build/pipelines", "/api/company/build/runs",
              "/api/company/whatif/scenarios", "/api/company/whatif/kept", "/api/company/memory/north", "/api/company/memory/lens", "/api/company/outcomes",
              "/api/profile", "/api/profile/links", "/api/interview", "/api/pulse/messages"]
    routes += [f"/api/company/feeds/{c}" for c in RESTRICTED] + [f"/api/company/feeds/{c.lower()}" for c in RESTRICTED]
    routes += [f"/api/company/graph/node/{n}{s}" for n in w.nodes if n.startswith(("measure:", "source:", "rule:")) for s in ("", "/comments")]
    routes += [f"/api/memory/me/{a}" for a in ("north", "lens", "nira")]
    for sid in w.sessions:
        routes += [f"{M1}/sessions/{sid}{s}" for s in ("", "/board", "/board/counts", "/together", "/summary", "/briefing", "/lobby", "/charter", "/charter/email",
                                                         "/room", "/room/library", "/join-link", "/roles", "/voice")]
    return routes


@pytest.mark.parametrize("role", ROLES)
def test_no_restricted_figure_sealed_text_author_or_key_reaches_the_role(world, role):
    c = world.login(role)
    leaks = []
    for url in figure_routes(world):
        for params in ({}, {"company_id": OTHER, "person": "janet-shaw", "viewer": "daniel kerr"}):
            r = c.get(url, params=params)
            if r.status_code < 300 and "text/html" not in r.headers.get("content-type", ""):
                leaks += [f"{url} {params}: {h}" for h in world.need.scan(c.me, r.text)]
    assert not leaks, "\n" + "\n".join(sorted(set(leaks)))


@pytest.mark.parametrize("role", ROLES)
def test_whatif_leaves_out_restricted_measures(world, role):
    c = world.login(role)
    if role == "participant":
        assert send(c, "POST", "/api/company/whatif", json={"driver": world.nodes[0], "change_pct": 10}).status_code == 403
        return
    for d in [n for n in world.nodes if n in ("field:F001", "field:F016", "field:F021", "source:S01", "source:S04", "source:S06", "measure:K06", "measure:K16")]:
        r = send(c, "POST", "/api/company/whatif", json={"driver": d, "change_pct": 10})
        assert not world.need.scan(c.me, r.text), d
        assert not [m for m in (r.json().get("moved") or []) if m["code"].split(":")[-1] in RESTRICTED] if r.status_code == 200 else True, d


def test_positive_control_the_admin_does_see_k06(world):
    """If this fails the grep above is blind (a reseed changed the shape), not the product safe."""
    if "K06" not in world.need.gold:
        pytest.skip("no K06 in the gold tables")
    assert any("K06 figures" in h for h in world.need.scan("nobody", world.admin.get("/api/company/feeds").text))


@pytest.mark.parametrize("role", ROLES)
def test_control_panel_settings_and_egress_log_stay_closed(world, role):
    c = world.login(role)
    for p in ("/api/control/companies", "/api/control/providers", "/api/control/catalogue", "/api/company/settings", "/api/company/egress-log"):
        for v in (p, p + "/", p + "?x=1", p + ";x", p.upper()):
            r = c.get(v)
            assert r.status_code >= 300 or "text/html" in r.headers.get("content-type", ""), (v, r.status_code)
        for m in ("POST", "PUT", "DELETE"):
            assert send(c, m, p, json={}).status_code >= 400, (m, p)
        r = c.get(p, headers={"X-Original-URL": p, "X-Rewrite-URL": p, "X-Company-Id": OTHER})
        assert r.status_code >= 300 or "text/html" in r.headers.get("content-type", ""), p


@pytest.mark.parametrize("role", ROLES)
def test_another_companys_ids_open_nothing(world, role):
    c = world.login(role)
    urls = [f"{M1}/sessions/{s}{sub}" for s in world.other_sessions for sub in ("", "/board", "/room", "/together", "/summary", "/join-link", "/lobby", "/charter")]
    urls += [f"/api/modules/m2_baseline/baselines/{b}{sub}" for b in world.other_baselines for sub in ("", "/requests", "/governed", "/review", "/audit")]
    urls += [f"/api/company/graph/node/{n}" for n in world.other_nodes if n not in world.nodes]  # ids that exist only over there
    for u in urls:
        r = c.get(u, params={"company_id": OTHER})
        assert r.status_code >= 300 or "text/html" in r.headers.get("content-type", ""), (u, r.status_code, r.text[:80])


def test_company_admin_cannot_read_another_company_by_id(world):
    c = world.admin
    for s in world.other_sessions:
        assert c.get(f"{M1}/sessions/{s}/board", params={"company_id": OTHER}).status_code >= 400
    for b in world.other_baselines:
        assert c.get(f"/api/modules/m2_baseline/baselines/{b}").status_code >= 400
    for n in world.other_nodes:
        if n not in world.nodes:
            assert c.get(f"/api/company/graph/node/{n}").status_code >= 400


def test_guessed_or_malformed_link_tokens_open_nothing(world):
    anon = TestClient(world.app)
    for u in ("/api/modules/m2_baseline/answer/form", "/api/modules/m3_connect/intake/link/form"):
        for tok in ("A" * 43, "x", "", "../../etc/passwd", *list(world.need.keys)[:1]):
            r = anon.post(u, headers={"X-Session-Token": tok}, json={})
            assert r.status_code in (400, 401, 403, 404, 422, 429), (u, tok[:6], r.status_code)
            assert "kpi" not in r.text.lower() and "questionnaire" not in r.text.lower(), (u, tok[:6])
        assert anon.get(u).status_code in (401, 403, 404, 405)
    assert anon.get(f"{M1}/sessions/{world.sessions[0]}/board").status_code in (401, 403)


def test_signed_out_reads_nothing(world):
    anon = TestClient(world.app)
    for p in ("/api/company/feeds", "/api/company/graph", "/api/company/register", "/api/pulse", "/api/memory/me/north", "/api/company/egress-log", "/api/control/companies"):
        assert anon.get(p).status_code in (401, 403), p


@pytest.mark.parametrize("role", ROLES)
def test_room_text_never_reaches_the_wall_reads_but_the_wall_card_does(world, role):
    """N12: a room turn that was never put on the wall stays private; the card a person did put on the wall is readable."""
    m1 = world.data / CO / "intents" / "m1_intent"
    seat = next((f for f in glob.glob(str(m1 / "transcripts/*/*.json")) if any(x.get("state") == "submitted" and not x.get("anonymous")
                                                                                 for x in (jload(f) or {}).get("notes", []))), None)
    if not seat:
        pytest.skip("no seat with a named card on the wall")
    d, sid = jload(seat), Path(seat).parent.name
    card = next(x["text"] for x in d["notes"] if x.get("state") == "submitted" and not x.get("anonymous"))
    marker = f"N12 private room words only {d['notes'][0].get('author_name')} said to North, never on the wall"
    d["turns"].append({"id": "n12marker", "role": "person", "text": marker, "at": "2026-10-07T00:00:00+00:00"})
    Path(seat).write_text(json.dumps(d), encoding="utf-8")
    c = world.login(role)
    bodies = [c.get(u).text for u in ("/api/company/graph", *[f"{M1}/sessions/{sid}/{s}" for s in ("board", "summary", "together")])]
    assert not [b for b in bodies if marker in b]
    assert world.admin.get(f"{M1}/sessions/{sid}/board").text.count(card[:30]) >= 1  # positive control: the wall card is there
