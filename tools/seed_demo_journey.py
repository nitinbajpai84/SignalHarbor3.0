"""Give one demo company a complete, believable journey (synthetic data only), through the real stores and routes.

Usage: python tools/seed_demo_journey.py <company_id> [--reset] [--data-root PATH]

Content: packs/family_office/1/demo_journey/journey.yaml (illustrative). In order: (1) a closed wall with cards, groups, votes, shelves, a signed
charter and its build roles; (2) an open wall in the private rooms; (3) a signed baseline of twelve measures; (4) a module 3 assessment, its trial
on the demo samples and a signed plan; (5) the build centre's environment, blueprint, pipeline contracts, run log, prove, UAT and release draft;
(6) two comments on the map; (7) a kept what-if; (8) one drafted message of each kind. The graph is rebuilt after each step, and the pulse of
each demo account is printed at the end.

Routes are called in-process (no server, no port) as the people who would act, with a session made for their existing account; a person with
no account acts through the store the route would call. No model is called: every model factory is switched off, so the stores' own fallbacks
run. A step the code refuses is logged and reported, never forced.

Idempotent: a second run does nothing. `--reset` puts back what the first run changed (a manifest in context/seed_demo_journey/ lists the
files it made and keeps the earlier copy of each file it changed) and seeds again. Only this company's plane is touched, apart from the
shared join and link indexes the stores add to (left as they are: their entries point at records that no longer exist after a reset).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import secrets
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from modules.m1_intent.domain import board as BD  # noqa: E402
from modules.m1_intent.domain import notes as N  # noqa: E402
from modules.m1_intent.domain import notes_quarters as Q  # noqa: E402
from modules.m1_intent.domain import private_room as PR  # noqa: E402
from modules.m1_intent.domain import together as T  # noqa: E402
from modules.m1_intent.domain.briefing import StageStore  # noqa: E402
from modules.m1_intent.domain.seat_identity import seat_id_of  # noqa: E402
from modules.m1_intent.store.board import BoardStore, TogetherStore  # noqa: E402
from modules.m1_intent.store.notes import NoteStore, submit_drafts  # noqa: E402
from modules.m1_intent.store.room import RoomStore  # noqa: E402
from modules.m1_intent.store.sessions import SessionStore  # noqa: E402
from modules.m1_intent.store.together_shelves import ShelfStore  # noqa: E402
from modules.m1_intent.store.transcripts import TranscriptStore  # noqa: E402
from modules.m2_baseline.domain import catalogue as CD  # noqa: E402
from modules.m2_baseline.domain import technical as TD  # noqa: E402
from modules.m2_baseline.domain.provenance import prov  # noqa: E402
from modules.m2_baseline.store import baseline as MB  # noqa: E402
from modules.m2_baseline.store import catalogue as MC  # noqa: E402
from modules.m2_baseline.store import glossary as MG  # noqa: E402
from modules.m2_baseline.store import governed as MGOV  # noqa: E402
from modules.m2_baseline.store import kpis as MK  # noqa: E402
from modules.m2_baseline.store.answers import AnswerStore  # noqa: E402
from modules.m2_baseline.store.signoff import SignoffStore  # noqa: E402
from sh_platform import build_env  # noqa: E402
from sh_platform import pulse  # noqa: E402
from sh_platform.app import create_app  # noqa: E402
from sh_platform.build import blueprint as BP  # noqa: E402
from sh_platform.build import contracts as BC  # noqa: E402
from sh_platform.build import runner as BR  # noqa: E402
from sh_platform.build.contracts import slug  # noqa: E402
from sh_platform.graph import build as graph_build  # noqa: E402
from sh_platform.graph import comments as GC  # noqa: E402
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile import store as profile_store  # noqa: E402
from sh_platform.profile import view  # noqa: E402
from sh_platform.pulse import messages  # noqa: E402
from sh_platform.settings import Settings, load_settings  # noqa: E402
from tools.seed_demo_warehouse import seed_demo_warehouse  # noqa: E402

log = logging.getLogger(__name__)
PACK = ROOT / "packs" / "family_office" / "1"
CONTENT = PACK / "demo_journey" / "journey.yaml"
SAMPLES = PACK / "demo_module3"
M1, M2, M3 = "/api/modules/m1_intent", "/api/modules/m2_baseline", "/api/modules/m3_connect"
KIND_OF_LANE = {lane: kind for kind, lane in N.__dict__.get("LANE_OF", {}).items()} or {
    "tracking": "intent", "missing": "pain_point", "watch": "future_signal", "levers": "lever"}
FROM = "Illustrative demo journey"
TEXT_FIELDS = {"Fund / Manager", "Asset Cls", "Acct", "Security", "notice_ref", "status", "replaces", "Index", "Issuer", "Person", "Vehicle"}
MANIFEST = ("context", "seed_demo_journey")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Refused(Exception):
    """A step the code refused; the message says why, in its own words."""


# ---- the manifest: what this script made and what it changed --------------------------------------------------------------------------

def _files(root: Path, skip: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and skip not in p.parents}


def _manifest_dir(plane) -> Path:
    return plane.path(*MANIFEST)


def undo(plane) -> bool:
    """Puts the plane back as it was before the journey: files made are removed, files changed get their earlier copy. False with no manifest."""
    folder = _manifest_dir(plane)
    doc = read_json_strict(folder / "manifest.json", dict) if (folder / "manifest.json").is_file() else None
    if not doc:
        return False
    for rel in doc["made"]:
        plane.path(rel).unlink(missing_ok=True)
    for rel in doc["changed"]:
        shutil.copyfile(folder / "before" / rel, plane.path(rel))
    for d in sorted((p for p in plane.root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if d != plane.root and not any(d.iterdir()) and d.relative_to(plane.root).as_posix() in doc.get("dirs_made", []):
            d.rmdir()
    shutil.rmtree(folder)
    return True


def clear_strays(plane, topics: set[str]) -> list[str]:
    """Removes sessions this script did not make that would block or clutter the journey: a topic the journey uses, or no topic. Returns their ids."""
    root = plane.path("intents", "m1_intent")
    idx = root / "index.json"
    doc = read_json_strict(idx, dict) if idx.is_file() else None
    removed = []
    for r in (doc or {}).get("sessions", []):
        f = root / "sessions" / f"{r['id']}.json"
        topic = ((read_json_strict(f, dict) or {}).get("preparation") or {}).get("topic") if f.is_file() else None
        if (topic or "").casefold() in topics or not topic:
            removed.append(r["id"])
    for sid in removed:
        for p in root.rglob(f"*{sid}*"):
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if removed:
        write_json_atomic(idx, {**doc, "sessions": [r for r in doc["sessions"] if r["id"] not in removed]})
    return removed


# ---- the in-process app and the people -------------------------------------------------------------------------------------------------

class World:
    def __init__(self, data_root: Path, company_id: str):
        self.root, self.cid = Path(data_root), company_id
        self.plane = PlaneStore(self.root).plane_for(company_id).ensure()
        self.app = create_app(Settings(mode="dev", data_root=str(self.root), session_secret=secrets.token_hex(32)))
        st = self.app.state
        st.model_env, st.speech_env = {}, {}  # no model and no speech: the stores' own fallbacks run
        st.north_model_factory = st.lens_model_factory = lambda plane: None
        self.accounts = {a["display_name"]: st.account_store.get(a["account_id"]) for a in st.account_store.in_company(company_id) if not a.get("disabled")}
        self._clients: dict[str, TestClient] = {}
        self.done: list[str] = []
        self.refused: list[str] = []

    def account(self, name: str) -> dict | None:
        return self.accounts.get(name)

    def as_(self, name: str) -> TestClient:
        """A client signed in as this person's own account (a server session made in-process, as the login route makes it)."""
        if name not in self._clients:
            acct = self.account(name)
            if acct is None:
                raise Refused(f"{name} has no account in {self.cid}")
            cookie, csrf = self.app.state.sessions.create(acct)
            c = TestClient(self.app)
            c.cookies.set("sh_session", cookie)
            c.headers["x-csrf-token"] = csrf
            self._clients[name] = c
        return self._clients[name]

    def call(self, name: str, method: str, url: str, ok=(200, 201), **kw) -> dict:
        r = getattr(self.as_(name), method)(url, **kw)
        if r.status_code not in ok:
            raise Refused(f"{method.upper()} {url} as {name}: {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    def viewer(self, name: str) -> view.Viewer:
        a = self.account(name)
        return view.Viewer(name, frozenset(a["roles"]) if a else frozenset(), False, a["account_id"] if a else None)

    def step(self, what: str, fn, *a) -> object:
        try:
            out = fn(*a)
            self.done.append(what)
            return out
        except Refused as e:
            msg = str(e)
            # Treat 409 "already done" errors as done, not refused
            if "409" in msg and ("already signed off" in msg or "no gap to accept" in msg):
                log.info("done (already done): %s", what)
                self.done.append(what)
                return None
            log.warning("not done: %s: %s", what, e)
            self.refused.append(f"{what}: {e}")
            return None

    def rebuild(self) -> None:
        graph_build.rebuild(self.plane)


# ---- (1) and (2): the walls -----------------------------------------------------------------------------------------------------------

def _note(spec, wallq, card: dict, author: str) -> dict:
    now, anon = _now(), card.get("anonymous") is True
    note = N.start(PR.new_note(card["q1"], now, secrets.token_hex(8)), author, "choice")
    note = N.edit(spec, note, {"kind": KIND_OF_LANE[card["lane"]], "anonymous": anon, "restricted": bool(card.get("sealed"))}, author, now)
    note = {**note, "restricted": bool(card.get("sealed"))}
    answers = {q: {"text": card[q]} for q in ("q1", "q2", "q3", "q4") if card.get(q)}
    return Q.answer(wallq, Q.start(note), answers)


def open_wall(w: World, wall: dict, organiser: str) -> dict:
    """Prepare, start, seat, brief, open the rooms and put the cards on the wall. Returns {sid, seats: name->seat id, notes: [(card, note id)]}."""
    prep = {"purpose": wall["purpose"], "outcome": wall["outcome"], "topic": wall["topic"], "seats": wall["seats"], "wall_window_days": 5}
    sid = w.call(organiser, "post", f"{M1}/sessions", json=prep)["id"]
    w.call(organiser, "post", f"{M1}/sessions/{sid}/start")
    rooms, seats = RoomStore(w.plane), {}
    for n, p in enumerate(wall["people"], 1):
        acct = w.account(p["name"])
        seat, _ = rooms.take(sid, n, p["name"], p["role"], acct["account_id"] if acct else None)  # a guest's token is not kept
        seats[p["name"]] = seat_id_of(w.plane, sid, seat)
    w.call(organiser, "post", f"{M1}/sessions/{sid}/briefing")
    SessionStore(w.plane).transition(sid, "private_rooms")  # the briefing ends (the route's own timer move)
    StageStore(w.plane).start(sid, "private_rooms", time.time())
    spec, wallq, notes = N.load_fields(), Q.load(), []
    by_seat: dict[str, list[dict]] = {}
    for card in wall["cards"]:
        author = card["by"]  # an anonymous card is still written by someone in a seat; the wall never shows who
        note = _note(spec, wallq, card, author)
        by_seat.setdefault(seats[author], []).append(note)
        notes.append((card, note["id"]))
    for seat, drafts in by_seat.items():
        if any(d["anonymous"] for d in drafts):
            NoteStore(w.plane).mark_anonymous(sid, seat)
        TranscriptStore(w.plane).update(sid, seat, lambda t, d=drafts: t["notes"].extend(d))
        submit_drafts(w.plane, sid, seat)
    return {"sid": sid, "seats": seats, "notes": notes}


def close_wall(w: World, wall: dict, made: dict, cast: dict) -> None:
    """Rooms close, the organiser groups the notes, the room votes and shelves, the charter is drafted, its lines written, roles named, signed."""
    sid, organiser, s = made["sid"], cast["organiser"], BD.load_settings()
    SessionStore(w.plane).transition(sid, "board")  # the close freezes the wall
    ids = {c["key"]: [nid for card, nid in made["notes"] if card.get("cluster") == c["key"]] for c in wall["clusters"]}
    clusters: list[dict] = []
    all_ids = [nid for _, nid in made["notes"]]
    for c in wall["clusters"]:
        clusters = BD.add_cluster(s, clusters, all_ids, c["name"], ids[c["key"]])
    BoardStore(w.plane).set_grouping(sid, "done", BD.assign_colours(clusters), fallback=True)  # grouped by the organiser, not by North
    keys = {c["name"]: c["key"] for c in wall["clusters"]}
    w.call(organiser, "post", f"{M1}/sessions/{sid}/together")
    split = wall.get("split")
    if split:
        cid = next(c["id"] for c in BoardStore(w.plane).get(sid)["clusters"] if keys.get(c["name"]) == split["from"])
        moved = [nid for card, nid in made["notes"] if card.get("split")]
        w.call(organiser, "post", f"{M1}/sessions/{sid}/board/clusters/{cid}/split", json={"note_ids": moved, "name": split["name"]})
        keys[split["name"]] = split["key"]
    board = BoardStore(w.plane).get(sid)["clusters"]
    by_key = {keys[c["name"]]: c for c in board}
    order = [p["name"] for p in wall["people"]]
    for key, options in wall["votes"].items():
        for name, option in zip(order, options):
            TogetherStore(w.plane).update(sid, lambda d, c=by_key[key]["id"], seat=made["seats"][name], o=option:
                                          T.apply_auto_ticks(s, T.vote(s, d, c, seat, o), board))
    acct = w.account(organiser)
    for key, shelf in (wall.get("shelves") or {}).items():
        ShelfStore(w.plane).update(sid, lambda d, c=by_key[key]: T.move_to_shelf(d, c, shelf, None, organiser, time.time(), s.comment_chars,
                                                                                 acct["account_id"] if acct else None))
    w.call(organiser, "post", f"{M1}/sessions/{sid}/charter", json={"confirm": True})
    lines = {by_key[k]["id"]: text for k, text in wall["so_that"].items() if k in by_key}
    w.call(organiser, "put", f"{M1}/sessions/{sid}/charter", json={"so_that": lines})
    people = [p["name"] for p in wall["people"]]
    named = {cast[r] for r in ("organiser", "sponsor", "head_of_data", "tester", "ops") if cast.get(r)}
    roles = {"architect": cast["head_of_data"], "developer": cast.get("developer"), "tester": _tester_name(w, cast), "sponsor": cast["sponsor"],
             "ops": cast["ops"], "informed": [p for p in people if p not in named]}
    w.call(organiser, "put", f"{M1}/sessions/{sid}/roles", json={"roles": roles})
    w.call(cast["sponsor"], "post", f"{M1}/sessions/{sid}/charter/sign")
    made["clusters"] = {k: c["id"] for k, c in by_key.items()}


# ---- (3) the baseline -----------------------------------------------------------------------------------------------------------------

def _cell(v, by: str) -> dict:
    return prov(v, "stated", by, FROM)


def baseline(w: World, content: dict, wall: dict, made: dict) -> str:
    cast, plane = content["cast"], w.plane
    outcome_id = SessionStore(plane).get(made["sid"])["outcome_id"]
    bid = MB.start(plane, outcome_id)[0]["id"]
    kpi_tree = {k["id"]: k for k in yaml.safe_load((PACK / "kpi_tree.yaml").read_text(encoding="utf-8"))["kpis"]}
    cat = content["catalogue"]
    src_ids, table_ids, field_ids = {}, {}, {}
    for s in cat["sources"]:
        src_ids[s["key"]] = MC.add_row(plane, bid, "sources", {
            "Source name": s["name"], "Source type": s["kind"], "Structured or unstructured": "Structured", "Data owner": s["owner"],
            "Where it lands or lives": "A shared folder", "How often it arrives": s["arrives"], "Contains personal data?": "No",
            "Connection method": "File drop"}, cast["head_of_data"])
    for m in content["measures"]:  # the measures first: the catalogue links tables and fields to measures that exist
        code, (business, data, process) = m["code"], m["owners"]
        MK.add(plane, bid, {
            "id": code, "name": kpi_tree[code]["name"], "problem_ids": [made["clusters"][p] for p in m["problems"] if p in made["clusters"]],
            "priority": "must", "definition": _cell(kpi_tree[code]["definition"], business),
            "owners": {"business": _cell(business, cast["sponsor"]), "data": _cell(data, cast["sponsor"]), "process": _cell(process, cast["sponsor"])},
            "governance": {"personal": "no", "sensitive": bool(m.get("may_see")), "may_see": list(m.get("may_see") or [])},
            "tracking": _cell(m["tracked"], data)})
        sources = next(s["name"] for s in cat["sources"] if s["key"] == cat["tables"][m["tables"][0]]["source"])  # the main one, as named in the catalogue
        for owner in dict.fromkeys((business, data, process)):  # each owner answers once per measure, in the baseline review meeting
            AnswerStore(plane, bid).save(owner, code, {
                "tracked_today": _cell("yes" if m["tracked"] == "tracked_now" else "no", owner), "could_track": _cell("yes", owner),
                "source": _cell(sources, owner), "data_type": _cell("structured", owner), "arrival": _cell("Monthly, by working day 8", owner)},
                meeting={"id": "baseline-review", "title": "Baseline review meeting", "at": _now()})
    MC.refresh(plane, bid)
    for tkey, t in cat["tables"].items():
        feeds = sorted({x.strip() for _, f in t["fields"] for x in str(f).split(",")})
        table_ids[tkey] = MC.add_row(plane, bid, "tables", {"Source ID": src_ids[t["source"]], "Name of table, file or document type": t["name"],
                                                            "Related KPIs": ", ".join(feeds)}, cast["head_of_data"])
        for name, f in t["fields"]:
            field_ids[(tkey, name)] = MC.add_row(plane, bid, "fields", {
                "Item ID": table_ids[tkey], "Field name as in the source": name, "Business meaning": f"What {name} holds",
                "Data type": "text" if name in TEXT_FIELDS else "decimal", "Feeds KPI": str(f), "Personal data class": "Neither"}, cast["head_of_data"])
    for m in content["measures"]:  # the data owner writes the technical definition against the catalogue rows, then confirms it
        code, data, tables = m["code"], m["owners"][1], m["tables"]

        def technical(k: dict, m=m, data=data, tables=tables) -> dict:
            k = TD.set_part(k, "sources", sorted({src_ids[cat["tables"][t]["source"]] for t in tables}), "stated", data)
            k = TD.set_part(k, "tables", [table_ids[t] for t in tables], "stated", data)
            k = TD.set_part(k, "fields", [fid for (t, name), fid in field_ids.items()
                                          if t in tables and m["code"] in str(dict(map(tuple, cat["tables"][t]["fields"]))[name])], "stated", data)
            for part, v in (("calculation", m["calc"]), ("grain", m["grain"]), ("period", m["period"])):
                k = TD.set_part(k, part, v, "stated", data)
            return TD.confirm(k, data)
        MK.change(plane, bid, code, technical)
    MC.refresh(plane, bid)
    everyone = lambda k: True  # noqa: E731  (the glossary is built over every measure; each screen filters per viewer)
    MG.build(plane, bid, everyone)
    for m in content["measures"]:  # every entry is new: each is reviewed one by one, by the head of data
        MG.review(plane, bid, m["code"], everyone, cast["head_of_data"])
    _govern(w, bid, content)
    sponsors = [(a["display_name"], a["account_id"]) for a in w.accounts.values() if "sponsor" in a["roles"]]
    store = SignoffStore(plane, sponsors=sponsors)
    for m in content["measures"]:
        for part, name in zip(("definition", "source", "process"), m["owners"]):
            try:
                store.confirm_by_link(bid, name, m["code"], part)
            except Exception as e:  # noqa: BLE001  the store's own refusal (already confirmed by the same person for two parts)
                if "already" not in str(e).lower():
                    raise Refused(f"{m['code']} {part} by {name}: {e}") from None
    for who in (cast["sponsor"], cast["organiser"]):
        a = w.account(who)
        if a is None:
            raise Refused(f"{who} has no account to sign the baseline")
        try:
            store.countersign(bid, who, a["account_id"], a["roles"])
        except Exception as e:  # noqa: BLE001  SignoffError carries the gate's sentence
            raise Refused(f"baseline signature by {who}: {getattr(e, 'message', e)}") from None
    return bid


def _govern(w: World, bid: str, content: dict) -> None:
    """The six governed fields of every measure, stated by the people the contract names (governed_state.yaml confirmers)."""
    cast, plane = content["cast"], w.plane
    head = CD.Viewer(cast["head_of_data"], frozenset(), False, None)
    MGOV.draft_all(plane, bid, CD.Viewer(cast["organiser"], frozenset({"company_admin"}), False, None))
    for m in content["measures"]:
        business, data, process = m["owners"]
        restricted = bool(m.get("may_see"))
        sponsor = w.account(cast["sponsor"])
        rows = [("owners", {"business": business, "data": data, "process": process}, head),
                ("classification", "restricted" if restricted else "open", head),
                ("may_see", list(m.get("may_see") or []), head),
                ("resolving", {"team": m["team"], "target_week": m["week"]}, CD.Viewer(cast["sponsor"], frozenset({"sponsor"}), False,
                                                                           sponsor["account_id"] if sponsor else None)),
                ("affects", [], CD.Viewer(business, frozenset(), False, (w.account(business) or {}).get("account_id"))),
                ("review_date", "2026-12-31", head)]
        for field, value, who in rows:
            try:
                MGOV.confirm_field(plane, bid, m["code"], field, value, who)
            except CD.CatalogueError as e:
                w.refused.append(f"governed {m['code']} {field} by {who.name}: {e.message}")


# ---- (4) module 3 -----------------------------------------------------------------------------------------------------------------------

def _payload(name: str) -> dict:
    return {"filename": name, "data": base64.b64encode((SAMPLES / name).read_bytes()).decode()}


def assess(w: World, content: dict) -> str:
    head, sponsor = content["cast"]["organiser"], content["cast"]["sponsor"]  # the plan's head-of-data slot is the company admin's
    aid = w.call(head, "post", f"{M3}/assessments")["assessment"]["id"]
    a = f"{M3}/assessments/{aid}"
    w.call(head, "post", f"{a}/sources/score")
    sent = w.call(head, "post", f"{a}/intake/requests").get("sent") or []
    by_name = {s["name"]: s for s in content["catalogue"]["sources"]}
    for s in w.call(head, "get", f"{a}/sources").get("sources", []):
        f = (by_name.get(s.get("name")) or {}).get("file")
        if f:
            w.step(f"upload {f}", lambda sid=s["id"], f=f: w.call(head, "post", f"{a}/intake/sources/{sid}/upload", json=_payload(f)))
    del sent
    w.step("benchmarks", lambda: w.call(head, "post", f"{a}/intake/benchmarks/upload", json=_payload(content["benchmarks_file"])))
    w.step("compile rules", lambda: w.call(head, "post", f"{a}/trial/compile"))
    w.step("trial run", lambda: w.call(head, "post", f"{a}/trial/run"))
    w.step("accept the risks", lambda: w.call(head, "post", f"{a}/risks/accept-all", json={"note": "Known risks, kept on the plan."}))
    plan = w.call(head, "post", f"{a}/plan/draft")
    for band, items in (plan.get("bands") or {}).items():
        for it in items if band != "now" else []:
            w.step(f"plan item {it['key']} to now",
                   lambda k=it["key"]: w.call(head, "put", f"{a}/plan/item", json={"key": k, "band": "now", "reason": content["plan_reason"]}))
    w.call(sponsor, "post", f"{a}/plan/sign")
    w.call(head, "post", f"{a}/plan/sign")
    return aid


# ---- (5) the build centre -----------------------------------------------------------------------------------------------------------

def build(w: World, content: dict) -> None:
    cast, plane = content["cast"], w.plane
    for key, value in content["environment"].items():
        build_env.confirm(plane, key, value, cast["head_of_data"])
    seed_demo_warehouse(w.root, w.cid)  # the illustrative gold tables the feeds and the prover read
    with lock_for(BP._file(plane)):  # the sign route's own record, signed by the head of data (who has no account to call it with)
        doc = BP._current(plane)
        if doc is None or doc.get("basis") == BP.DRAFT_BASIS:
            raise Refused("there is no blueprint drafted from a signed baseline")
        if doc["state"] != "signed":
            doc = {**doc, "state": "signed", "signed_by": [{"name": cast["head_of_data"], "role": "Head of data",
                                                            "at": content["blueprint_signed_at"]}]}
            write_json_atomic(BP._file(plane), doc)
    pipes = {c["source"]: c for c in BC.ensure(plane)}
    runs = BR.read_runs(plane)
    for r in content["runs"]:  # the runner's own log entry; real runs would replace the demo's gold tables, so none is started
        c = pipes.get(r["source"]) or {"owner": r["owner"]}
        start = datetime.fromisoformat(content["runs_at"])  # before the six months of history, so Ops reads September as the latest day
        runs.append({"id": secrets.token_hex(16), "source": r["source"], "started": start.isoformat(), "ended": start.isoformat(),
                     "on_time": r["on_time"], "rows": r["rows"], "schema_ok": True,
                     "rules": [{"rule": f"{m}:{text}", "passed": passed, "count": n} for m, text, passed, n in r["rules"]],
                     "not_run": [], "notes": [FROM], "marts_ready": start.isoformat() if r["status"] == "ok" else None,
                     "sla_met": r["status"] == "ok", "owner": c.get("owner") or r["owner"], "status": r["status"]})
    with lock_for(BR._runs_path(plane)):
        write_json_atomic(BR._runs_path(plane), {"runs": runs})
    for r in content["prove"].get("reported_extra") or []:  # the two measures the company's pack never reported, so every baseline measure has a figure to prove
        for end, fig in r["figures"].items():
            for field, value in (("measure", r["measure"]), ("figure", fig), ("unit", r["unit"]), ("period_end", end)):
                profile_store.record(plane, f"reported_figures.{slug(r['measure'])}-{end}.{field}", value,
                                     {"mark": "stated", "by": cast["sponsor"], "from": FROM})
    proved = w.call(cast["organiser"], "get", "/api/company/build/prove")
    codes = [m["code"] for m in proved.get("measures", [])]
    skip = set(content["prove"]["uat_skip"])
    signer = _tester_name(w, cast) if _tester_named(w) else cast["sponsor"]
    for code in codes:
        if code not in skip:
            w.step(f"UAT {code}", lambda c=code: w.call(signer, "post", f"/api/company/build/uat/{c}/sign", json={"state": "signed", "note": FROM}))
    gap = content["prove"]["accept_gap"]
    w.step(f"accept the gap on {gap['measure']}", lambda: w.call(cast["organiser"], "post", f"/api/company/build/prove/{gap['measure']}/accept",
                                                                  json={"reason": gap["reason"]}))


def _tester_name(w: World, cast: dict) -> str:
    """The named tester must hold an account to sign UAT: the cast's tester when they have one, else the analyst account's person."""
    if w.account(cast["tester"]):
        return cast["tester"]
    analyst = next((a["display_name"] for a in w.accounts.values() if "analyst" in a["roles"]), None)
    return analyst or cast["tester"]


def _tester_named(w: World) -> bool:
    from sh_platform.build.uat import _tester
    return _tester(w.plane) is not None


# ---- (6), (7), (8) ------------------------------------------------------------------------------------------------------------------

def comment(w: World, content: dict) -> None:
    cast = content["cast"]
    for c in content["comments"]:
        node = f"measure:{c['node']}"
        item = w.call(c["by"], "post", f"/api/company/graph/node/{node}/comments",
                      json={"kind": c["kind"], "text": c["text"], "anonymous": bool(c.get("anonymous"))})
        if c.get("decide"):  # the steward decides: the head of data, who has no account, through the comments module's own writers
            path = w.plane.path("graph", "comments.json")
            with lock_for(path):
                doc = GC._read(w.plane)
                hit = next(x for x in doc[node] if x["id"] == item["id"])
                hit.update(state=c["decide"], decided_by=cast["head_of_data"], decided_at=GC._now(), answer=c.get("answer"))
                write_json_atomic(path, doc)
            if c["decide"] == "accepted":
                GC._add_version(w.plane, node, f"Accepted: {item['text'][:120]}", cast["head_of_data"], f"comment:{item['id']}")


def whatif(w: World, content: dict) -> None:
    wi = content["whatif"]
    g = read_json_strict(w.plane.path("graph", "company.json"), dict) or {}
    driver = next((e["from"] for e in g.get("edges", []) if e.get("type") in ("moves", "measured_by")), None)
    if driver is None:
        raise Refused("the map has no edge a what-if can follow yet")
    w.call(wi["by"], "post", "/api/company/whatif/save", json={"driver": driver, "change_pct": wi["change_pct"], "note": wi["note"]})


def draft_messages(w: World, content: dict, record_of: dict) -> None:
    for kind, rec in content["messages"].items():
        to = [{"name": n, "account_id": (w.account(n) or {}).get("account_id")} for n in rec.get("to", [])]
        acct = w.account(content["cast"]["organiser"])
        messages.draft(w.plane, kind, {**rec, "to": to, "from_record": record_of.get(kind, "demo journey"),
                                       "organiser_account_id": acct["account_id"] if acct else None})


# ---- the whole journey ----------------------------------------------------------------------------------------------------------------

def journey(w: World, content: dict) -> dict:
    cast, walls = content["cast"], {x["key"]: x for x in content["walls"]}
    out: dict = {}
    closed = walls["treasury"]
    made = w.step("1 closed wall", open_wall, w, closed, cast["organiser"])
    if made:
        w.step("1 charter signed with roles", close_wall, w, closed, made, cast)
        out["closed_wall"] = made["sid"]
    w.rebuild()
    live = w.step("2 open wall", open_wall, w, walls["performance"], cast["organiser"])
    out["open_wall"] = live["sid"] if live else None
    w.rebuild()
    if made and made.get("clusters"):
        out["baseline"] = w.step("3 baseline signed", baseline, w, content, closed, made)
    w.rebuild()
    if out.get("baseline"):
        out["assessment"] = w.step("4 plan signed", assess, w, content)
    w.rebuild()
    w.step("5 build centre", build, w, content)
    w.rebuild()
    w.step("6 map comments", comment, w, content)
    w.rebuild()
    w.step("7 what-if kept", whatif, w, content)
    w.step("8 Nira drafts", draft_messages, w, content, {"invite": f"sessions/{out.get('open_wall')}",
                                                         "reminder": f"sessions/{out.get('open_wall')}/reminder",
                                                         "sponsor_ask": f"m3_connect/{out.get('assessment')}", "ops_report": "warehouse/runs",
                                                         "owner_ask": "warehouse/runs/custodian_daily_file"})
    w.rebuild()
    return out


def pulses(w: World) -> dict[str, dict]:
    return {a["display_name"]: pulse.build(w.plane, w.viewer(a["display_name"])) for a in w.accounts.values()}


def seed_journey(data_root: Path, company_id: str, reset: bool = False, content_file: Path = CONTENT) -> dict:
    """Runs the journey once for this company. Returns {"status": "seeded"|"already", ids, done, refused, pulses}."""
    plane = PlaneStore(Path(data_root)).plane_for(company_id).ensure()
    folder = _manifest_dir(plane)
    if (folder / "manifest.json").is_file():
        if not reset:
            return {"status": "already", "done": [], "refused": [], "pulses": {}}
        undo(plane)
    content = yaml.safe_load(content_file.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        before = Path(tmp) / "before"
        removed = clear_strays(plane, {x["topic"].casefold() for x in content["walls"]})
        shutil.copytree(plane.root, before)
        dirs_before = {p.relative_to(plane.root).as_posix() for p in plane.root.rglob("*") if p.is_dir()}
        w = World(Path(data_root), company_id)
        ids = journey(w, content)
        old, new = _files(before, before / Path(*MANIFEST)), _files(plane.root, folder)
        changed = sorted(r for r in old if r in new and old[r] != new[r])
        for rel in changed:
            dest = folder / "before" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(before / rel, dest)
        dirs_made = sorted({p.relative_to(plane.root).as_posix() for p in plane.root.rglob("*") if p.is_dir()} - dirs_before)
        write_json_atomic(folder / "manifest.json", {"seeded_at": _now(), "ids": ids, "made": sorted(set(new) - set(old)), "changed": changed,
                                                     "dirs_made": [d for d in dirs_made if not d.startswith("/".join(MANIFEST))],
                                                     "done": w.done, "refused": w.refused, "removed": removed})
    return {"status": "seeded", "ids": ids, "done": w.done, "refused": w.refused, "pulses": pulses(w)}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Seed one demo company's whole journey (illustrative, synthetic).")
    ap.add_argument("company_id")
    ap.add_argument("--reset", action="store_true", help="put back what an earlier run wrote, then seed again")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    try:
        r = seed_journey(root, args.company_id, args.reset)
    except (LookupError, ValueError) as e:
        print(f"Journey not seeded: {e}")
        return 1
    if r["status"] == "already":
        print(f"{args.company_id} already has the demo journey. Run with --reset to put it back and seed it again.")
        return 0
    print(f"Seeded the demo journey into {args.company_id}: {len(r['done'])} steps done, {len(r['refused'])} refused.")
    for line in r["refused"]:
        print(f"  refused: {line}")
    for name, p in r["pulses"].items():
        print(f"\n{name} ({', '.join(p['person']['roles'])}):")
        for strip in p["strips"]:
            for ln in strip["lines"]:
                print(f"  [{strip['key']}] {ln['kind']}: {ln['title']}")
        if not p["strips"]:
            print("  nothing to act on today")
    return 0


if __name__ == "__main__":
    sys.exit(main())
