"""Demo seed for the Intent Centre (v2): the Ardmore department roster and a plane of intents in the ruled shapes (SHAPES section 15).

Usage: python tools/seed_demo_intents.py [company_id] [--data-root PATH] [--reset]
Synthetic only. Idempotent: a record that exists is left alone (a person may have changed it); --reset rewrites the seed's own
records (intent folders it owns, its backlog items and opportunities), never anything else and never a password.
Accounts: one per roster person; new passwords are appended to <data_root>/_control/seed_credentials.txt and never printed.
Records go straight into `intents/` through the kernel store (`sh_platform/intents/store.py`) and `sh_platform/jsonfile.py`;
week items use the check-in builder's own item maker so the screens read them as they read their own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.intents import checkin as CK  # noqa: E402
from sh_platform.intents import lifecycle as L  # noqa: E402
from sh_platform.intents import processes as PR  # noqa: E402
from sh_platform.intents import store as S  # noqa: E402
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile import areas as PA  # noqa: E402
from sh_platform.profile import store as PS  # noqa: E402
from sh_platform.profile import view as PV  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from tools.seed import DOMAIN, HEADER, _new_password, _plane  # noqa: E402

log = logging.getLogger(__name__)
COMPANY = "ardmore"
BY = "Janet Shaw"  # the company admin who keeps the people file
FROM = "Department roster (illustrative seed)"

# (name, department, job title, company role, areas, legacy sign-in) from the wave 2 roster; the super admin is not a company person.
ROSTER = [
    ('Daniel Kerr', 'Leadership', 'Managing Director', 'sponsor', 'company-wide', 'sponsor.ardmore@example.test'),
    ('Eleanor Chua', 'Leadership', 'Chief Executive Officer', 'sponsor', 'company-wide', None),
    ('Marcus Teo', 'Leadership', 'Chief Financial Officer', 'sponsor', 'Finance, Leadership', None),
    ('Siti Aminah', 'Leadership', 'Chief Operating Officer', 'sponsor', 'Operations, Leadership', None),
    ('Vikram Nair', 'Leadership', 'Chief of Staff', 'participant', 'company-wide', None),
    ('Hui Min Goh', 'Leadership', 'Executive Assistant to the CEO', 'participant', 'Leadership', None),
    ('Aaron Lyle', 'Finance', 'Fund Accountant', 'participant', 'Finance, Operations', 'participant.ardmore@example.test'),
    ('Priya Raman', 'Finance', 'Financial Controller', 'approver', 'Finance', None),
    ('Jun Wei Ong', 'Finance', 'Senior Accountant', 'participant', 'Finance', None),
    ('Aisyah Salleh', 'Finance', 'Treasury Analyst', 'analyst', 'Finance', None),
    ('Kenneth Yap', 'Finance', 'Reporting Manager', 'owner', 'Finance', None),
    ('Wen Li Chia', 'Finance', 'Accounts Payable Executive', 'participant', 'Finance', None),
    ('Dinesh Pillai', 'Finance', 'Tax Manager', 'participant', 'Finance', None),
    ('Mei Ling Chong', 'Finance', 'Management Accountant', 'participant', 'Finance', None),
    ('Jia Hao Lee', 'Finance', 'Finance Business Partner', 'participant', 'Finance, Investments', None),
    ('Janet Shaw', 'Operations', 'Head of Operations and Office', 'company_admin', 'Operations, company-wide', 'company_admin.ardmore@example.test'),
    ('Harvey Rowley', 'Operations', 'Head of Fund Operations', 'owner', 'Operations', 'owner.ardmore@example.test'),
    ('Ravi Chandran', 'Operations', 'Settlements Specialist', 'participant', 'Operations', None),
    ('Rahul Mehta', 'Operations', 'Custody and Reconciliations Analyst', 'participant', 'Operations', None),
    ('Siew Ling Ho', 'Operations', 'Operations Associate', 'participant', 'Operations', None),
    ('Amirul Hakim', 'Operations', 'Corporate Actions Officer', 'participant', 'Operations', None),
    ('Natasha Wee', 'Operations', 'Reconciliations Lead', 'owner', 'Operations', None),
    ('Bryan Sim', 'Operations', 'Banking Operations Officer', 'participant', 'Operations', None),
    ('Farah Idris', 'Operations', 'Facilities and Travel Coordinator', 'participant', 'Operations', None),
    ('Chen Long Zhang', 'Operations', 'Operations Analyst', 'analyst', 'Operations', None),
    ('Rajesh Subramaniam', 'Investments', 'Head of Investments', 'sponsor', 'Investments', None),
    ('Alicia Fong', 'Investments', 'Portfolio Manager, Public Markets', 'participant', 'Investments', None),
    ('Tomoko Hayashi', 'Investments', 'Portfolio Manager, Private Markets', 'participant', 'Investments', None),
    ('Benjamin Ho', 'Investments', 'Investment Analyst', 'analyst', 'Investments', None),
    ('Anh Tran', 'Investments', 'Investment Analyst, Southeast Asia', 'analyst', 'Investments', None),
    ('Darren Quek', 'Investments', 'Risk Manager', 'owner', 'Investments', None),
    ('Sophia Lau', 'Investments', 'Private Markets Associate', 'participant', 'Investments', None),
    ('Hendra Wijaya', 'Investments', 'Fixed Income Trader', 'participant', 'Investments', None),
    ('Pooja Kapoor', 'Investments', 'Performance Analyst', 'analyst', 'Investments', None),
    ('Gabriel Soo', 'Investments', 'Investment Associate', 'participant', 'Investments', None),
    ('Grace Ward', 'Compliance', 'Head of Governance and Compliance', 'approver', 'Compliance', 'approver.ardmore@example.test'),
    ('Lakshmi Iyer', 'Compliance', 'Compliance Officer', 'approver', 'Compliance', None),
    ('Yusuf Ibrahim', 'Compliance', 'AML Analyst', 'analyst', 'Compliance', None),
    ('Cheryl Neo', 'Compliance', 'Legal Counsel', 'participant', 'Compliance', None),
    ('Ethan Goh', 'Compliance', 'Compliance Associate', 'participant', 'Compliance', None),
    ('Mariam Hashim', 'Compliance', 'Regulatory Reporting Officer', 'participant', 'Compliance', None),
    ('Rebecca Seah', 'HR', 'Head of People', 'sponsor', 'HR', None),
    ('Arjun Menon', 'HR', 'HR Business Partner', 'participant', 'HR', None),
    ('Joyce Toh', 'HR', 'Talent and Learning Manager', 'participant', 'HR', None),
    ('Nurul Huda', 'HR', 'Payroll and Benefits Executive', 'owner', 'HR', None),
    ('Calvin Ang', 'HR', 'HR Analyst', 'analyst', 'HR', None),
    ('Shirin Rahim', 'HR', 'Recruitment Coordinator', 'participant', 'HR', None),
    ('Katie Kingsley', 'Technology', 'Head of Data', 'analyst', 'Technology, Operations', 'analyst.ardmore@example.test'),
    ('Timothy Lam', 'Technology', 'Head of Technology', 'sponsor', 'Technology', None),
    ('Irfan Maulana', 'Technology', 'Data Engineer', 'participant', 'Technology', None),
    ('Sharon Pang', 'Technology', 'Integration Engineer', 'owner', 'Technology', None),
    ('Vincent Chew', 'Technology', 'Cybersecurity Lead', 'participant', 'Technology', None),
    ('Divya Nambiar', 'Technology', 'Business Intelligence Developer', 'analyst', 'Technology', None),
    ('Zhi Yang Tay', 'Technology', 'IT Support Specialist', 'participant', 'Technology', None),
    ('Linh Pham', 'Technology', 'Cloud and Platform Engineer', 'participant', 'Technology', None),
]
# Area id = the name lower-cased, so the three readers of areas (ids in visibility, normalised names in store and access) agree.
AREAS = [("leadership", "Leadership", "department"), ("finance", "Finance", "department"), ("operations", "Operations", "operations_area"),
         ("investments", "Investments", "department"), ("compliance", "Compliance", "department"), ("hr", "HR", "department"),
         ("technology", "Technology", "department")]
PACK_AREAS = {"finance", "investments", "operations", "compliance"}  # in packs/family_office/1/areas.yaml: accepted from suggestions


def slug(name: str) -> str:
    return "-".join(name.lower().replace(",", "").split())


def email_of(name: str) -> str:
    return f"{'.'.join(name.lower().split())}.{COMPANY}@{DOMAIN}"


def area_ids(text: str) -> list[str]:
    if "company-wide" in text:  # decision: a company-wide person is tagged to every area
        return [a for a, _, _ in AREAS]
    names = {n.lower(): a for a, n, _ in AREAS}
    return [names[t.strip().lower()] for t in text.split(",")]


def at(d: str, hm: str = "01:00") -> str:
    """A UTC stamp. 01:00 UTC is 09:00 in Singapore; 09:00 UTC is 17:00."""
    return f"{d}T{hm}:00+00:00"


def iid(key: str, type_: str) -> str:
    return f"{S.PREFIX[type_]}-{hashlib.md5(f'{COMPANY}:{key}'.encode()).hexdigest()}"


def item_id(key: str) -> str:
    return "it-" + hashlib.md5(key.encode()).hexdigest()[:12]


# ---- accounts and people -------------------------------------------------------------------------------------------------------

def seed_people(data_root: Path, plane) -> tuple[dict, dict]:
    """Accounts for the roster, profile people with their areas, the seven areas. Returns (name -> person entry, counts)."""
    store, made, lines = AccountStore(data_root), 0, []
    who: dict[str, dict] = {}
    for name, dept, title, role, areas, legacy in ROSTER:
        email = legacy or email_of(name)
        acct = store.get_by_email(email)
        if acct is None:
            password = _new_password()
            acct = store.create(email, password, name, COMPANY, [role])
            lines.append(f"{email}  {password}  {role}  {COMPANY}")
            made += 1
        who[name] = {"account_id": acct["account_id"], "name": name, "_display": acct["display_name"], "_dept": dept, "_title": title,
                     "_areas": area_ids(areas)}
    if lines:
        creds = data_root / "_control" / "seed_credentials.txt"
        creds.parent.mkdir(parents=True, exist_ok=True)
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    prov = {"mark": "stated", "by": BY, "from": FROM}

    def change(doc: dict) -> dict:
        out = {"areas_added": 0, "people_added": 0, "tags_set": 0}
        have = {k for k in (doc.get("areas") or {}) if k != PA.SETTINGS}
        for aid, nm, kind in AREAS:
            if aid not in have and not any(PA._same(nm, str(PA._v(a, "name") or "")) for a in PA._items(doc).values()):
                PA._add(doc, aid, nm, kind, BY, PA.ACCEPTED if aid in PACK_AREAS else "Added by the company admin")
                out["areas_added"] += 1
        linked = {PV._v(p, "account_id"): pid for pid, p in doc["people"].items() if PV._v(p, "account_id")}
        for name, p in who.items():
            targets = []
            pid = linked.get(p["account_id"])
            if pid:
                targets.append(pid)  # the person the sign-in already belongs to keeps its cells; it gets the roster's areas
            if not pid or p["_display"] != name:
                # A roster name the sign-in does not carry (the analyst sign-in is "Marcus Todd"): a person of its own, linked only
                # when no other person holds the sign-in.
                own = slug(name)
                if own not in doc["people"]:
                    for f, v in (("name", name), ("role", p["_title"]), ("team", p["_dept"]), ("email", email_of(name))):
                        PS.set_cell(doc, f"people.{own}.{f}", v, prov)
                    if not pid:
                        PS.set_cell(doc, f"people.{own}.account_id", p["account_id"], prov)
                    out["people_added"] += 1
                targets.append(own)
            for t in targets:
                if PA.people_areas(doc["people"][t]) == []:
                    PS.set_cell(doc, f"people.{t}.areas", p["_areas"], prov)
                    out["tags_set"] += 1
        return out
    counts = PS.mutate(plane, change)
    counts.update(accounts_created=made, accounts_total=len(who))
    return {n: {"account_id": p["account_id"], "name": n} for n, p in who.items()}, counts


# ---- intent records --------------------------------------------------------------------------------------------------------------

class Plan:
    """The records one intent owns: intent.json, events.jsonl and optional weeks/ and processes.json."""

    def __init__(self, key: str, rec: dict, events: list, weeks: list | None = None, processes: dict | None = None):
        self.key, self.rec, self.events, self.weeks, self.processes = key, rec, events, weeks or [], processes


def record(P: dict, key: str, type_: str, title: str, purpose: str, areas: list[str], people: dict, state: str, created: str,
           stages: list[tuple], ends: str, outcome: dict, *, starts: str | None = None, closure: dict | None = None,
           ratings: list[int] = (), link_from: str | None = None, links_to: list[str] = (), build: str | None = None,
           refs: dict | None = None, answers: dict | None = None) -> dict:
    """One intent record in the ruled shape, built on the lifecycle's own blank record. `stages` is one (state, opened, closed) per
    catalogue stage; `people` maps a slot or list to names."""
    org = P[people["organiser"]]
    rec = L.new_record(type_, COMPANY, org, created, title=title, purpose=purpose, areas=areas, link_from=link_from)
    rec["id"] = iid(key, type_)
    rec["record"] = f"intents/{rec['id']}/intent.json"
    for slot, names in people.items():
        rec["people"][slot] = [P[n] for n in names] if isinstance(names, list) else P[names]
    td = L.type_def(type_)
    rec["stages"] = [{"key": s["key"], "name": s["name"], "state": st, "opened_at": o, "closed_at": c}
                     for s, (st, o, c) in zip(td["stages"], stages)]
    opened = stages[0][1] if stages and stages[0][1] else None
    rec["state"] = state
    rec["time_box"] = {"starts": starts or opened or "", "ends": ends, "extended_by": []}
    rec["outcome"].update(outcome)
    rec["links"].update(to=list(links_to), build=build)
    rec["refs"].update(refs or {})
    rec["ratings"] = [{"by": "anonymous", "score": s, "note": ""} for s in ratings]
    rec["catalogue_version"] = str(L._types().get("version", ""))
    rec["start_answers"] = answers or {}
    hist = rec["history"]
    if opened:
        hist.append({"at": opened, "by": org["account_id"], "from": "draft", "to": "open", "note": ""})
    if closure:
        c = rec["closure"]
        c.update(closure)
        c["signed"] = True
        hist.append({"at": closure["closing_at"], "by": org["account_id"], "from": "open", "to": "closing", "note": ""})
        hist.append({"at": c["closed_at"], "by": org["account_id"], "from": "closing", "to": "closed", "note": ""})
        c.pop("closing_at")
        c["closed_by"], c["draft_by"] = org["account_id"], "north"
    return rec


def ev(at_: str, kind: str, who: dict | None, stage: str, detail: dict | None = None, role: str = "organiser") -> dict:
    return {"at": at_, "kind": kind, "by": {"account": who["account_id"], "name": who["name"], "role": role} if who else None,
            "agent": None if who else "north", "stage": stage, "detail": detail or {}}


def _events_lines(plan: Plan) -> list[dict]:
    out = []
    for n, e in enumerate(sorted(plan.events, key=lambda x: x["at"]), 1):
        out.append({"seq": n, "at": e["at"], "kind": e["kind"], "status": "draft" if e["agent"] else "act", "by": e["by"], "anonymous": False,
                    "agent": e["agent"], "stage": e["stage"], "ref": {"store": "intent", "id": plan.rec["id"], "version": None},
                    "detail": e["detail"], "confirms": None, "corrects": None, "sealed": False})
    return out


def week(P: dict, intent_key: str, opens: date, close_day: str, reporters: list[str], items: list[tuple], *, closed: str | None,
         reviewer: str, summary: str = "") -> dict:
    """A week file in the check-in builder's shape (SHAPES week keys plus the builder's own). items: (who|None anonymous, kind, text,
    fate, fate_reason, fate_ref)."""
    d = CK.week_dates(opens, close_day)
    wk = CK.week_key(d["opens"])
    rows, sent = [], []
    for n, (who, kind, text, fate, reason, ref) in enumerate(items):
        v = PV.Viewer(who or "", frozenset(), account_id=P[who]["account_id"] if who else None)
        it = CK._new_item(kind, text, v, anonymous=who is None)
        it["id"] = item_id(f"{intent_key}:{wk}:{n}")
        if fate:
            it.update(fate=fate, fate_reason=reason, fate_ref=ref, decided_by=P[reviewer]["account_id"], decided_at=closed or at(d["review_day"].isoformat(), "06:00"))
        rows.append(it)
        if who and who not in sent:
            sent.append(who)
    stamp = min(at(d["answers_close"].isoformat(), "08:00"), datetime.now(timezone.utc).replace(microsecond=0).isoformat())  # R13: never after now
    subs = [{"by": P[n]["account_id"], "by_name": n, "state": "closed" if closed else "submitted", "started_at": at(d["opens"].isoformat(), "02:00"),
             "submitted_at": stamp, "updated_at": stamp, "closed_at": closed, "active_seconds": 240, "minutes": 4, "skipped": [], "kept": [],
             "dropped": [], "last_saved_at": stamp} for n in sent]
    w = {"week_key": wk, "opens": d["opens"].isoformat(), "closes": d["closes"].isoformat(), "answers_close": d["answers_close"].isoformat(),
         "review_day": d["review_day"].isoformat(), "state": "closed" if closed else "collect", "people": [dict(P[n]) for n in reporters],
         "prompts": [{"kind": p["kind"], "lead": p["lead"]} for p in L.type_def("pulse")["weekly_prompts"]], "items": rows, "submissions": subs,
         "review": {}, "stage_closed_at": closed, "closed_at": closed}
    if closed:
        for it in rows:
            if not it["fate"]:
                it.update(fate="nothing", fate_reason="Not reviewed this week", fate_ref=None, decided_by=P[reviewer]["account_id"], decided_at=closed)
        w["closure"] = {"closed_by": P[reviewer]["account_id"], "closed_at": closed, "closed_for": None, "summary": summary, "edited_by_person": False}
        w["read_only"] = True
    else:
        w["state"] = CK._state_on(w, datetime.now(timezone.utc).date())
    return w


def outcome_row(w: dict) -> dict:
    return {"week_key": w["week_key"], "closed_at": w["closed_at"], "items_count": len(w["items"]),
            "broke_count": sum(1 for i in w["items"] if i["kind"] == "broke"),
            "fates": {f: sum(1 for i in w["items"] if i["fate"] == f) for f in ("problem", "backlog", "handled", "nothing")}}


def cell(v, by: str = BY, src: str = "Confirmed by the owner") -> dict:
    return PS.cell(v, {"mark": "stated", "by": by, "from": src, "at": None})


def guess(v, src: str) -> dict:
    return PS.cell(v, {"mark": "guessed", "by": "Lens", "from": src, "agent": "lens"})


def process(pid: str, name: str, owner: str, trigger: str, freq: str, steps: list[tuple], *, confirmed_by: str | None, at_: str) -> dict:
    """One process of file 27; steps (name, actor). A confirmed one carries the owner's confirmation and its steps hash."""
    mk = (lambda v: cell(v, confirmed_by)) if confirmed_by else (lambda v: guess(v, "Wall cards and the people file"))
    p = {"id": pid, "cluster": "unsorted", "key": None, "name": mk(name), "owner": mk(owner), "trigger": mk(trigger), "frequency": mk(freq),
         "inputs": mk([]), "outputs": mk([]), "systems": mk([]), "breaks": [], "status": "confirmed" if confirmed_by else "guessed",
         "confirmed": None, "removed": None, "created_by": "Lens", "history": [{"by": "Lens", "at": at_, "kind": "drafted"}],
         "steps": [{"id": f"{pid}-s{n}", "order": n, "name": mk(s), "actor": mk(a), "systems": mk([]), "inputs": mk([]), "outputs": mk([]),
                    "produces": [], "uses": [], "sources": []} for n, (s, a) in enumerate(steps, 1)]}
    if confirmed_by:
        p["confirmed"] = {"by": confirmed_by, "at": at_, "steps_hash": PR._steps_hash(p)}
        p["history"].append({"by": confirmed_by, "at": at_, "kind": "confirmed"})
    return p


def scenario(P: dict) -> tuple[list[Plan], list[dict], list[dict]]:
    """The demo plane: the wave 2 roster's twelve intents plus the card's closed Initiative and closed Decision, the backlog and two
    opportunities. Every date is on the October 2026 demo clock (UTC)."""
    w = "waiting"
    ids = {k: iid(k, t) for k, t in (("ini_cap", "initiative"), ("dec_cap", "decision"), ("i1", "initiative"), ("i2", "initiative"),
                                       ("i3", "initiative"), ("b1", "brainstorm"), ("b2", "brainstorm"), ("w1", "pulse"), ("w2", "pulse"),
                                       ("p1", "problem"), ("p2", "problem"), ("p3", "problem"), ("d1", "decision"), ("d2", "decision"))}
    bl = {k: f"bk-{hashlib.md5(f'{COMPANY}:{k}'.encode()).hexdigest()[:16]}" for k in ("fees", "checklist", "notices", "vintage")}
    plans: list[Plan] = []
    J, D, K, A, H, G = (P[n] for n in ("Janet Shaw", "Daniel Kerr", "Katie Kingsley", "Aaron Lyle", "Harvey Rowley", "Grace Ward"))

    # Closed Initiative with a signed charter (m1 session 03cb..., charter outcome 00a68d...) and a hand-off to Build.
    rec = record(P, "ini_cap", "initiative", "Fund capital calls with time to spare",
                 "Treasury learns of capital calls too late to fund them calmly.", ["finance", "investments"],
                 {"organiser": "Janet Shaw", "sponsor": "Daniel Kerr", "participants": ["Aisyah Salleh", "Priya Raman", "Tomoko Hayashi", "Harvey Rowley", "Katie Kingsley"]},
                 "closed", at("2026-04-06"), [("closed", at("2026-04-07"), at("2026-04-09", "09:00")), ("closed", at("2026-04-10"), at("2026-04-17", "06:00")),
                                              ("closed", at("2026-04-17", "06:00"), at("2026-04-20", "03:00"))], at("2026-04-20", "09:00"),
                 {"goal": "Fund every capital call with at least ten working days of headroom", "why": "Two calls in the last year were funded from the overdraft.",
                  "build_needed": "yes", "definitions_exist": "some", "build_ready": True},
                 closure={"closing_at": at("2026-04-17", "06:00"), "closed_at": at("2026-04-20", "04:00"),
                          "summary": "The charter is signed and the plan is with Build.", "why_it_happened": "Call notices reached Treasury by email, days late.",
                          "what_came_out": "A signed charter with four priorities and a plan handed to Build.",
                          "one_liner": "Charter signed by Daniel Kerr; handed to Build on 20 April.",
                          "next": [{"kind": "decision", "ref": ids["dec_cap"], "reason": "The reserve level was left open in the charter."},
                                   {"kind": "backlog", "ref": bl["vintage"], "reason": "Kept for later in the charter."}],
                          "confirmed": [{"role": "sponsor", "by": D["account_id"], "at": at("2026-04-20", "03:30")}]},
                 ratings=[5, 4, 4, 5], links_to=[ids["dec_cap"]], build="build/blueprint.json",
                 refs={"wall_session_ids": ["03cb51711272dffcb719d96a52ed5821"], "charter_outcome_id": "00a68d916b91396870d446e9f2c44158",
                       "processes_file": f"intents/{iid('ini_cap', 'initiative')}/processes.json"})
    procs = {"version": 1, "intent_id": rec["id"], "drafted_at": at("2026-04-10"), "drafted_from": {"cards": 30, "interviews": 0, "documents": 1},
             "processes": [process("p-capcall", "Capital call notice to funding", "harvey-rowley", "A call notice arrives", "About twice a month",
                                   [("Log the notice the day it arrives", "Fund Operations"), ("Check headroom in the cash plan", "Treasury"),
                                    ("Approve and pay the call", "Finance")], confirmed_by="Harvey Rowley", at_=at("2026-04-15"))],
             "questions": []}
    plans.append(Plan("ini_cap", rec, [ev(at("2026-04-07"), "intent_opened", J, "think_unfiltered"),
                                        ev(at("2026-04-09", "09:00"), "stage_closed", J, "think_unfiltered", {"cards": 30}),
                                        ev(at("2026-04-15"), "process_confirmed", H, "define_strategically", role="participant"),
                                        ev(at("2026-04-17", "06:00"), "charter_signed", D, "define_strategically", {"version": 1}, "sponsor"),
                                        ev(at("2026-04-20", "03:00"), "build_ready_checked", J, "build_ready", {"passed": 7, "of": 7}),
                                        ev(at("2026-04-20", "03:10"), "handed_to_build", J, "build_ready"),
                                        ev(at("2026-04-20", "03:30"), "closure_confirmed", D, "build_ready", role="sponsor"),
                                        ev(at("2026-04-20", "04:00"), "intent_closed", J, "build_ready", {"next": 2})], processes=procs))

    rec = record(P, "dec_cap", "decision", "How much cash do we hold in reserve for capital calls?",
                 "The charter left the reserve level open.", ["finance", "investments"],
                 {"organiser": "Janet Shaw", "decider": "Daniel Kerr", "advisers": ["Priya Raman", "Aisyah Salleh"]},
                 "closed", at("2026-04-20", "05:00"), [("closed", at("2026-04-20", "05:00"), at("2026-04-21", "05:00")),
                                                       ("closed", at("2026-04-21", "05:00"), at("2026-04-22", "03:00"))], at("2026-04-22", "09:00"),
                 {"question": "How much cash do we hold in reserve for capital calls?",
                  "options": [{"id": "o1", "text": "Hold the next two months of expected calls", "drafted_by": "north", "added_by": None},
                              {"id": "o2", "text": "Hold a fixed amount set each quarter", "drafted_by": "north", "added_by": None},
                              {"id": "o3", "text": "Use a standing credit line instead of cash", "drafted_by": None, "added_by": "adviser"}],
                  "chosen": {"option_id": "o1", "text": "Hold the next two months of expected calls", "by": D["account_id"], "at": at("2026-04-22", "02:00")},
                  "why": "It follows the call schedule and the treasurer can check it every month."},
                 closure={"closing_at": at("2026-04-22", "02:30"), "closed_at": at("2026-04-22", "03:00"),
                          "summary": "Daniel Kerr chose to hold two months of expected calls.", "why_it_happened": "The charter left the reserve level open.",
                          "what_came_out": "A reserve rule the treasurer checks every month.", "one_liner": "Hold the next two months of expected calls.",
                          "next": [{"kind": "handled", "ref": None, "reason": "The rule is in the treasury cash plan."}],
                          "confirmed": [{"role": "decider", "by": D["account_id"], "at": at("2026-04-22", "02:40")}]},
                 ratings=[4, 5, 4], link_from=ids["ini_cap"])
    plans.append(Plan("dec_cap", rec, [ev(at("2026-04-20", "05:00"), "intent_opened", J, "options"),
                                        ev(at("2026-04-21", "05:00"), "stage_closed", J, "options", {"options": 3}),
                                        ev(at("2026-04-22", "02:00"), "decision_recorded", D, "decide", role="decider"),
                                        ev(at("2026-04-22", "03:00"), "intent_closed", J, "decide", {"next": 1})]))

    # I1: Initiative in Define (journey 50's topic).
    rec = record(P, "i1", "initiative", "Cut the days it takes to produce the quarterly client report",
                 "The quarterly client report takes twelve working days and most of it is copying.", ["finance", "operations"],
                 {"organiser": "Janet Shaw", "sponsor": "Daniel Kerr", "participants": ["Aaron Lyle", "Katie Kingsley", "Harvey Rowley", "Kenneth Yap", "Mei Ling Chong"],
                  "advisers": ["Grace Ward"], "observers": ["Chen Long Zhang"]},
                 "open", at("2026-09-29"), [("closed", at("2026-09-30"), at("2026-10-02", "09:00")), ("open", at("2026-10-05"), None), (w, None, None)],
                 at("2026-10-13", "09:00"),
                 {"goal": "Produce the quarterly client report in five working days", "why": "Clients wait two weeks after quarter end.",
                  "build_needed": "yes", "definitions_exist": "some", "build_ready": None},
                 links_to=[ids["d1"]], refs={"processes_file": f"intents/{iid('i1', 'initiative')}/processes.json"},
                 answers={"i1": {"goal_line": "Produce the quarterly client report in five working days"}, "i3": "yes", "i4": "some", "i5": ["finance", "operations"]})
    procs = {"version": 2, "intent_id": rec["id"], "drafted_at": at("2026-10-05"), "drafted_from": {"cards": 24, "interviews": 0, "documents": 1},
             "processes": [process("p-qcr-data", "Gather holdings and returns for the report", "harvey-rowley", "Quarter end", "Quarterly",
                                   [("Export holdings from the portfolio system", "Fund Operations"), ("Check returns against the administrator", "Fund Operations")],
                                   confirmed_by="Harvey Rowley", at_=at("2026-10-06")),
                           process("p-qcr-pack", "Write and check the client report", "kenneth-yap", "Holdings are ready", "Quarterly",
                                   [("Fill the report template", "Reporting"), ("Second check", "Finance")], confirmed_by=None, at_=at("2026-10-05"))],
             "questions": []}
    plans.append(Plan("i1", rec, [ev(at("2026-09-30"), "intent_opened", J, "think_unfiltered"),
                                   ev(at("2026-10-02", "09:00"), "stage_closed", J, "think_unfiltered", {"cards": 24}),
                                   ev(at("2026-10-05"), "stage_opened", J, "define_strategically"),
                                   ev(at("2026-10-05", "02:00"), "processes_drafted", None, "define_strategically", {"processes": 2}),
                                   ev(at("2026-10-06"), "process_confirmed", H, "define_strategically", role="participant")], processes=procs))

    rec = record(P, "i2", "initiative", "One month-end close calendar across Finance and Operations",
                 "Finance and Operations keep two calendars and chase each other for the same files.", ["finance", "operations"],
                 {"organiser": "Priya Raman", "sponsor": "Marcus Teo", "owner": "Harvey Rowley",
                  "participants": ["Jun Wei Ong", "Aisyah Salleh", "Wen Li Chia", "Natasha Wee", "Rahul Mehta", "Katie Kingsley"],
                  "observers": ["Siti Aminah"], "advisers": ["Dinesh Pillai"]},
                 "open", at("2026-10-05"), [("open", at("2026-10-06"), None), (w, None, None), (w, None, None)], at("2026-10-19", "09:00"),
                 {"goal": "Close the month on one shared calendar", "why": "Files arrive late because nobody owns the dates.",
                  "build_needed": "not_sure", "definitions_exist": "no", "build_ready": None})
    plans.append(Plan("i2", rec, [ev(at("2026-10-06"), "intent_opened", P["Priya Raman"], "think_unfiltered")]))

    rec = record(P, "i3", "initiative", "A single new-joiner checklist for HR, Technology and Operations",
                 "New joiners wait for desks, laptops and access because three teams keep three lists.", ["hr", "technology", "operations"],
                 {"organiser": "Arjun Menon", "sponsor": "Rebecca Seah", "participants": ["Joyce Toh", "Shirin Rahim", "Zhi Yang Tay", "Vincent Chew", "Farah Idris"],
                  "advisers": ["Cheryl Neo"], "affected": ["Hui Min Goh"]},
                 "draft", at("2026-10-07", "02:00"), [], "", {"goal": "One checklist every new joiner's first day runs from", "build_needed": "no"})
    plans.append(Plan("i3", rec, []))

    rec = record(P, "b1", "brainstorm", "Performance reviews take two weeks and nobody trusts the scores",
                 "Reviews take two weeks of managers' time and people doubt the scores.", ["hr", "finance", "operations"],
                 {"organiser": "Janet Shaw", "participants": ["Aaron Lyle", "Katie Kingsley", "Harvey Rowley", "Grace Ward", "Mei Ling Chong", "Ravi Chandran"],
                  "sponsor": "Daniel Kerr", "advisers": ["Rebecca Seah"], "observers": ["Calvin Ang"], "affected": ["Joyce Toh"]},
                 "in_session", at("2026-10-05", "07:00"), [("closed", at("2026-10-06"), at("2026-10-07", "01:59")), ("open", at("2026-10-07", "02:00"), None), (w, None, None)],
                 at("2026-10-08", "09:00"), {"statement": "Performance reviews take two weeks and nobody trusts the scores",
                                             "good_outcome": "One idea to make reviews shorter and fairer, with an owner", "session_at": at("2026-10-07", "02:00")},
                 starts=at("2026-10-06"))
    plans.append(Plan("b1", rec, [ev(at("2026-10-06"), "intent_opened", J, "think_alone"),
                                   ev(at("2026-10-07", "02:00"), "session_started", J, "live_session", {"present": 6, "of": 7})]))

    rec = record(P, "b2", "brainstorm", "Cut manual work on private fund capital calls",
                 "Capital call notices are retyped by hand from emails and PDFs.", ["investments", "finance", "operations"],
                 {"organiser": "Tomoko Hayashi", "participants": ["Sophia Lau", "Benjamin Ho", "Aisyah Salleh", "Siew Ling Ho", "Bryan Sim", "Irfan Maulana"],
                  "advisers": ["Priya Raman"], "affected": ["Jia Hao Lee"]},
                 "closed", at("2026-09-28", "07:00"), [("closed", at("2026-09-29"), at("2026-09-30", "09:00")), ("closed", at("2026-10-01", "02:00"), at("2026-10-01", "03:00")),
                                                       ("closed", at("2026-10-01", "03:00"), at("2026-10-02", "05:00"))], at("2026-10-02", "09:00"),
                 {"statement": "Cut manual work on private fund capital calls", "good_outcome": "One idea we can turn into an Initiative",
                  "session_at": at("2026-10-01", "02:00"),
                  "chosen": {"text": "Read call notices from the shared mailbox into one list Treasury confirms",
                             "reason": "Most backs, and it removes the retyping at the source.", "backs": 5,
                             "confirmed_by": P["Tomoko Hayashi"]["account_id"], "confirmed_at": at("2026-10-01", "03:00")},
                  "backed": [{"text": "Read call notices from the shared mailbox into one list Treasury confirms", "backs": 5}],
                  "runners_up": [{"text": "Ask fund administrators to send notices in one format", "backs": 3},
                                 {"text": "A calendar of expected calls from the commitment schedule", "backs": 2}],
                  "ideas_kept": [{"text": "Flag notices that change an earlier call"}], "dropped": [{"text": "Hire a temporary clerk", "reason": "Does not remove the work"}]},
                 starts=at("2026-09-29"),
                 closure={"closing_at": at("2026-10-01", "03:00"), "closed_at": at("2026-10-02", "05:00"),
                          "summary": "The group backed reading notices from the mailbox.", "why_it_happened": "Notices are retyped by hand.",
                          "what_came_out": "One chosen idea with five backs and two runners-up.",
                          "one_liner": "Read call notices from the mailbox into one list Treasury confirms.",
                          "next": [{"kind": "initiative", "ref": None, "reason": "Nobody has opened the Initiative yet."},
                                   {"kind": "backlog", "ref": bl["notices"], "reason": "The runner-up is worth asking the administrators."}]},
                 ratings=[5, 4, 4, 3, 5])
    plans.append(Plan("b2", rec, [ev(at("2026-09-29"), "intent_opened", P["Tomoko Hayashi"], "think_alone"),
                                   ev(at("2026-10-01", "02:00"), "session_started", P["Tomoko Hayashi"], "live_session", {"present": 7, "of": 7}),
                                   ev(at("2026-10-01", "03:00"), "outcome_confirmed", P["Tomoko Hayashi"], "choose", {"backs": 5}),
                                   ev(at("2026-10-02", "05:00"), "intent_closed", P["Tomoko Hayashi"], "choose", {"next": 2})]))

    # W1: Operations weekly check-in, three weeks: two closed, the third collecting. The custodian break repeats every week.
    w1r = ["Aaron Lyle", "Harvey Rowley", "Mei Ling Chong", "Rahul Mehta", "Ravi Chandran", "Natasha Wee"]
    cust = "The custodian cash balance did not match the ledger on Monday. I fixed it by hand again."
    weeks1 = [
        week(P, "w1", date(2026, 9, 21), "fri", w1r, [
            ("Aaron Lyle", "broke", "The custodian cash balance did not match the ledger on Monday. Fixed by hand.", "handled", "Matched by hand the same day.", "/centre/build"),
            ("Harvey Rowley", "ran", "The nightly valuation load finished on time every day.", None, None, None),
            ("Mei Ling Chong", "broke", "The fee schedule for two managers lives only in a spreadsheet.", "backlog", "Worth a proper fix, not this week.", bl["fees"]),
            ("Rahul Mehta", "thought", "Could reconciliations start from last month's checklist?", "backlog", "A good idea for the backlog.", bl["checklist"]),
            ("Natasha Wee", "ran", "All reconciliations signed off by Thursday.", None, None, None)],
             closed=at("2026-09-25", "09:00"), reviewer="Katie Kingsley", summary="One break handled, two items to the backlog."),
        week(P, "w1", date(2026, 9, 28), "fri", w1r, [
            ("Aaron Lyle", "broke", "The custodian cash balance did not match the ledger on Monday again.", "problem", "Third time; it needs an owner.", ids["p1"]),
            ("Rahul Mehta", "broke", "Custodian cash break on Monday; matched by hand by noon.", "problem", "Same break as Aaron's.", ids["p1"]),
            ("Harvey Rowley", "broke", "The valuation load ran after 08:00 on Tuesday.", "handled", "Rerun by Harvey before the pack went out.", "/centre/build"),
            ("Ravi Chandran", "broke", "One broker's settlement confirmation came after cut-off.", "handled", "Chased and settled the same day.", "/centre/build"),
            ("Mei Ling Chong", "thought", "Month-end will be tight with the holiday.", None, None, None)],
             closed=at("2026-10-02", "09:00"), reviewer="Katie Kingsley", summary="One Problem opened for the custodian break; two handled."),
        week(P, "w1", date(2026, 10, 5), "fri", w1r, [
            ("Aaron Lyle", "broke", cust, None, None, None),
            ("Rahul Mehta", "broke", "Two settlement confirmations arrived after cut-off on Tuesday.", None, None, None),
            ("Harvey Rowley", "ran", "The valuation load finished before 07:30 every day this week.", None, None, None),
            (None, "thought", "Reviews are coming up and nobody knows the timetable.", None, None, None)],
             closed=None, reviewer="Katie Kingsley")]
    series = {"status": "running", "close_day": "fri", "reviewer": K["account_id"], "reviewer_name": K["name"], "extra_prompt": None,
              "week_length_days": 5, "next_week_opens": CK.add_wd(date.fromisoformat(weeks1[-1]["closes"]), 1).isoformat(),
              "current_week": weeks1[-1]["week_key"], "weeks": [x["week_key"] for x in weeks1], "paused": None, "ended": None}
    rec = record(P, "w1", "pulse", "Operations weekly check-in", CK.PURPOSE, ["operations"],
                 {"organiser": "Katie Kingsley", "participants": w1r, "observers": ["Janet Shaw"]},
                 "open", at("2026-09-18", "07:00"), [], at(weeks1[-1]["closes"], "15:59"), {"weeks": [outcome_row(x) for x in weeks1[:2]]},
                 starts=at(weeks1[-1]["opens"], "00:00"))
    rec["stages"] = [{"key": "running", "name": "Running", "state": "open", "opened_at": at("2026-09-18", "07:00"), "closed_at": None}]
    rec["history"].append({"at": at("2026-09-18", "07:00"), "by": K["account_id"], "from": "draft", "to": "open", "note": ""})
    rec["series"], rec["refs"]["weeks_dir"] = series, f"intents/{rec['id']}/weeks"
    plans.append(Plan("w1", rec, [ev(at("2026-09-18", "07:00"), "series_started", K, "running")] +
                      [ev(at(x["opens"], "00:00"), "week_opened", None, "running", {"week_key": x["week_key"]}) for x in weeks1] +
                      [ev(x["closed_at"], "week_closed", K, "running", {"week_key": x["week_key"], "items": len(x["items"])}) for x in weeks1[:2]],
                      weeks=weeks1))

    w2r = ["Irfan Maulana", "Sharon Pang", "Vincent Chew", "Divya Nambiar", "Linh Pham", "Zhi Yang Tay"]
    weeks2 = [week(P, "w2", date(2026, 10, 5), "thu", w2r, [
        ("Irfan Maulana", "broke", "The index provider feed arrived without Friday's prices.", None, None, None),
        ("Sharon Pang", "broke", "The payroll bank upload was rejected on the first try.", None, None, None),
        ("Divya Nambiar", "ran", "The monthly report refresh ran on time.", None, None, None),
        ("Vincent Chew", "ran", "Access reviews finished for Finance.", None, None, None),
        ("Linh Pham", "thought", "Could platform changes move to a Tuesday window?", None, None, None)], closed=None, reviewer="Timothy Lam")]
    T = P["Timothy Lam"]
    rec = record(P, "w2", "pulse", "Technology weekly check-in", CK.PURPOSE, ["technology"],
                 {"organiser": "Timothy Lam", "participants": w2r, "observers": ["Katie Kingsley"]},
                 "open", at("2026-10-02", "07:00"), [], at(weeks2[0]["closes"], "15:59"), {"weeks": []}, starts=at(weeks2[0]["opens"], "00:00"))
    rec["stages"] = [{"key": "running", "name": "Running", "state": "open", "opened_at": at("2026-10-02", "07:00"), "closed_at": None}]
    rec["history"].append({"at": at("2026-10-02", "07:00"), "by": T["account_id"], "from": "draft", "to": "open", "note": ""})
    rec["series"] = {**series, "close_day": "thu", "reviewer": T["account_id"], "reviewer_name": T["name"],
                     "next_week_opens": CK.add_wd(date.fromisoformat(weeks2[0]["closes"]), 1).isoformat(),
                     "current_week": weeks2[0]["week_key"], "weeks": [weeks2[0]["week_key"]]}
    rec["refs"]["weeks_dir"] = f"intents/{rec['id']}/weeks"
    plans.append(Plan("w2", rec, [ev(at("2026-10-02", "07:00"), "series_started", T, "running"),
                                   ev(at(weeks2[0]["opens"], "00:00"), "week_opened", None, "running", {"week_key": weeks2[0]["week_key"]})], weeks=weeks2))

    rec = record(P, "p1", "problem", "Custodian cash does not match the ledger each Monday",
                 "Operations matches the custodian cash by hand every Monday.", ["operations", "finance", "technology"],
                 {"organiser": "Aaron Lyle", "reporter": "Aaron Lyle", "owner": "Katie Kingsley", "participants": ["Rahul Mehta"],
                  "advisers": ["Sharon Pang", "Harvey Rowley"], "affected": ["Grace Ward", "Daniel Kerr"]},
                 "open", at("2026-10-01", "02:00"), [("closed", at("2026-10-01", "02:00"), at("2026-10-02", "03:00")), ("open", at("2026-10-02", "03:00"), None),
                                                     (w, None, None), (w, None, None)], at("2026-10-07", "09:00"),
                 {"what": "The custodian cash balance does not match the ledger on Mondays.", "saw": "Two Mondays running, matched by hand.",
                  "bites": "slowed", "count": 2, "amount": None, "owner_accepted_at": at("2026-10-02", "03:00")},
                 link_from=ids["w1"])
    plans.append(Plan("p1", rec, [ev(at("2026-10-01", "02:00"), "intent_opened", A, "describe", role="reporter"),
                                   ev(at("2026-10-01", "06:00"), "owner_passed", H, "describe", role="adviser"),
                                   ev(at("2026-10-02", "03:00"), "owner_accepted", K, "describe", role="owner"),
                                   ev(at("2026-10-02", "03:00"), "stage_opened", A, "find_cause", role="reporter")]))

    Y, Lk = P["Yusuf Ibrahim"], P["Lakshmi Iyer"]
    rec = record(P, "p2", "problem", "Trade surveillance alerts wait days before anyone reviews them",
                 "Surveillance alerts sat unreviewed for up to four days.", ["compliance", "investments"],
                 {"organiser": "Yusuf Ibrahim", "reporter": "Yusuf Ibrahim", "owner": "Lakshmi Iyer", "advisers": ["Divya Nambiar"],
                  "affected": ["Hendra Wijaya", "Alicia Fong"]},
                 "closed", at("2026-09-28", "02:00"), [("closed", at("2026-09-28", "02:00"), at("2026-09-28", "08:00")), ("closed", at("2026-09-28", "08:00"), at("2026-09-30", "04:00")),
                                                       ("closed", at("2026-09-30", "04:00"), at("2026-10-01", "06:00")), ("closed", at("2026-10-01", "06:00"), at("2026-10-02", "04:00"))],
                 at("2026-10-02", "09:00"),
                 {"what": "Surveillance alerts wait days before anyone reviews them.", "saw": "Eleven alerts older than two days last week.",
                  "bites": "slowed", "count": 11, "amount": None, "owner_accepted_at": at("2026-09-28", "08:00"),
                  "root_cause": {"text": "Alerts went to a shared mailbox nobody was named to watch.", "confirmed_by": Lk["account_id"], "confirmed_at": at("2026-09-30", "04:00")},
                  "fix": {"text": "Alerts now go to a named reviewer each day, with a cover person.", "doer": Lk["account_id"], "done_at": at("2026-10-01", "06:00")}},
                 closure={"closing_at": at("2026-10-01", "06:00"), "closed_at": at("2026-10-02", "04:00"),
                          "summary": "Alerts now have a named reviewer each day.", "why_it_happened": "Nobody was named to watch the alerts mailbox.",
                          "what_came_out": "A daily named reviewer and a cover person.", "one_liner": "A named reviewer now clears alerts each day.",
                          "next": [{"kind": "handled", "ref": None, "reason": "The fix is running and the reporter confirmed it."}],
                          "confirmed": [{"role": "owner", "by": Lk["account_id"], "at": at("2026-10-02", "02:00")},
                                        {"role": "reporter", "by": Y["account_id"], "at": at("2026-10-02", "03:00")}]},
                 ratings=[4, 4, 5])
    plans.append(Plan("p2", rec, [ev(at("2026-09-28", "02:00"), "intent_opened", Y, "describe", role="reporter"),
                                   ev(at("2026-09-28", "08:00"), "owner_accepted", Lk, "describe", role="owner"),
                                   ev(at("2026-09-30", "04:00"), "root_cause_confirmed", Lk, "find_cause", role="owner"),
                                   ev(at("2026-10-01", "06:00"), "fix_done", Lk, "fix", role="owner"),
                                   ev(at("2026-10-02", "03:00"), "closure_confirmed", Y, "confirm", role="reporter"),
                                   ev(at("2026-10-02", "04:00"), "intent_closed", Y, "confirm", {"next": 1})]))

    rec = record(P, "p3", "problem", "The payroll file upload to the bank fails once a month",
                 "The payroll upload is rejected by the bank about once a month.", ["hr", "finance", "technology"],
                 {"organiser": "Nurul Huda", "reporter": "Nurul Huda", "owner": "Sharon Pang", "advisers": ["Bryan Sim"],
                  "participants": ["Wen Li Chia"], "affected": ["Priya Raman"]},
                 "open", at("2026-10-06", "03:00"), [("open", at("2026-10-06", "03:00"), None), (w, None, None), (w, None, None), (w, None, None)],
                 at("2026-10-13", "03:00"), {"what": "The payroll file upload to the bank fails once a month.", "saw": "Rejected on the first try in August and September.",
                                             "bites": "stopped", "count": 2, "amount": None, "owner_accepted_at": ""})
    plans.append(Plan("p3", rec, [ev(at("2026-10-06", "03:00"), "intent_opened", P["Nurul Huda"], "describe", role="reporter")]))

    rec = record(P, "d1", "decision", "Move the monthly fund return report to one agreed set of measures",
                 "The monthly report uses different measures in different sections.", ["investments", "finance", "operations"],
                 {"organiser": "Janet Shaw", "decider": "Daniel Kerr", "advisers": ["Katie Kingsley", "Harvey Rowley", "Grace Ward", "Pooja Kapoor"],
                  "affected": ["Aaron Lyle"]},
                 "open", at("2026-10-06", "02:00"), [("open", at("2026-10-06", "02:00"), None), (w, None, None)], at("2026-10-08", "09:00"),
                 {"question": "How do we move the monthly fund return report to one agreed set of measures?",
                  "options": [{"id": "o1", "text": "Adopt the governed measures from the baseline for every section", "drafted_by": "north", "added_by": None},
                              {"id": "o2", "text": "Keep the current measures and add a reconciliation page", "drafted_by": "north", "added_by": None}]},
                 link_from=ids["i1"])
    plans.append(Plan("d1", rec, [ev(at("2026-10-06", "02:00"), "intent_opened", J, "options"),
                                   ev(at("2026-10-06", "05:00"), "options_drafted", None, "options", {"options": 2})]))

    rec = record(P, "d2", "decision", "Set the pre-clearance rule for staff personal trades",
                 "Staff personal trades have no pre-clearance rule.", ["compliance", "investments"],
                 {"organiser": "Lakshmi Iyer", "decider": "Grace Ward", "advisers": ["Rajesh Subramaniam", "Alicia Fong", "Darren Quek", "Cheryl Neo"],
                  "observers": ["Eleanor Chua"]},
                 "open", at("2026-10-07", "01:00"), [("open", at("2026-10-07", "01:00"), None), (w, None, None)], at("2026-10-09", "09:00"),
                 {"question": "What pre-clearance rule do staff follow before a personal trade?"})
    plans.append(Plan("d2", rec, [ev(at("2026-10-07", "01:00"), "intent_opened", Lk, "options")]))

    def item(key, title, kind, area, src, by, at_, why, quote):
        return {"id": bl[key], "title": title, "kind": kind, "area": area,
                "source": {"intent_id": src[0], "type": src[1], "stage_ref": src[2], "week_key": src[3], "week_item_id": src[4]},
                "raised_by": by, "raised_at": at_, "why_it_matters": {"text": why, "drafted_by": "north", "edited_by": None, "edited_at": None},
                "source_quote": quote, "taps": [{"by": by, "at": at_}], "review_date": "2027-01-04", "status": "open", "parked": None, "dropped": None,
                "merged_into": None, "merged_from": [], "opened_intent": None, "reminded_at": [], "history": [{"at": at_, "by": "north", "action": "created", "note": ""}]}
    wk39, wk40, wk41 = (x["week_key"] for x in weeks1)
    backlog = [
        item("fees", "Keep the manager fee schedule in one governed place", "ops_problem", "operations", (ids["w1"], "pulse", None, wk39, weeks1[0]["items"][2]["id"]),
             P["Mei Ling Chong"]["account_id"], weeks1[0]["closed_at"], "Fees are checked against a spreadsheet only one person keeps.", weeks1[0]["items"][2]["text"]),
        item("checklist", "Start reconciliations from last month's checklist", "idea", "operations", (ids["w1"], "pulse", None, wk39, weeks1[0]["items"][3]["id"]),
             P["Rahul Mehta"]["account_id"], weeks1[0]["closed_at"], "It would save the first hour of every month-end.", weeks1[0]["items"][3]["text"]),
        item("notices", "Ask fund administrators to send call notices in one format", "idea", "investments", (ids["b2"], "brainstorm", "choose", None, None),
             P["Tomoko Hayashi"]["account_id"], at("2026-10-02", "05:00"), "Three backs in the session; it removes retyping for every fund.", ""),
        item("vintage", "Show unfunded commitments by vintage year", "request", "finance", (ids["ini_cap"], "initiative", "close", None, None),
             J["account_id"], at("2026-04-20", "04:00"), "The committee asked for it; the charter kept it for later.", ""),
    ]

    opps = [
        {"id": "opp-" + hashlib.md5(f"{COMPANY}:custodian".encode()).hexdigest()[:16], "title": "Custodian cash breaks come back every Monday",
         "state": "proposed", "noticed_by": "watcher", "noticed_at": at("2026-10-06", "00:30"), "areas": ["operations", "finance"],
         "touches": {"measures": ["k02"], "processes": [], "sources": ["custodian_daily_file"]},
         "pattern": {"text": "A custodian cash break is reported in each of the last three weekly check-ins, and the custodian file has an open alert.",
                     "periods": [wk39, wk40, wk41],
                     "numbers": [{"label": "Weeks running with a custodian cash break", "value": 3, "unit": "weeks",
                                  "trace": {"kind": "week_item", "ref": f"{ids['w1']}/{wk41}/{weeks1[2]['items'][0]['id']}", "at": weeks1[2]["opens"]}},
                                 {"label": "Open alerts on the custodian daily file", "value": 1, "unit": "alerts",
                                  "trace": {"kind": "alert", "ref": "gold.k02:range", "at": "2026-09-09"}}]},
         "evidence": [{"id": "ev1", "text": "Week items on 21 September, 28 September and 5 October name the same break.", "kind": "supports",
                       "source": {"kind": "week_item", "ref": f"{ids['w1']}/{wk40}/{weeks1[1]['items'][0]['id']}"}, "by": "lens", "at": at("2026-10-06", "01:00")},
                      {"id": "ev2", "text": "A Problem is already open for the break itself.", "kind": "supports",
                       "source": {"kind": "intent", "ref": ids["p1"]}, "by": "lens", "at": at("2026-10-06", "01:05")}],
         "judgement": {"fits": True, "why": "The break repeats every week; a fix by hand does not stop it, so the match itself needs building.",
                       "confidence": "fairly_sure",
                       "start_answers": {"goal": "Match custodian cash to the ledger automatically every morning", "people": "Katie Kingsley, Harvey Rowley, Aaron Lyle",
                                         "build": "yes", "definitions": "some", "areas": "operations, finance", "deadline": "2026-10-23"},
                       "at": at("2026-10-06", "02:00")},
         "picked_up_by": None, "picked_up_at": None, "became": None, "parked": None, "dismissed": None,
         "history": [{"at": at("2026-10-06", "00:30"), "by": "watcher", "action": "noticed", "note": ""},
                     {"at": at("2026-10-06", "02:00"), "by": "north", "action": "proposed", "note": ""}]},
        {"id": "opp-" + hashlib.md5(f"{COMPANY}:settlements".encode()).hexdigest()[:16], "title": "Settlement confirmations arrive after cut-off more often",
         "state": "under_review", "noticed_by": "watcher", "noticed_at": at("2026-10-07", "00:30"), "areas": ["operations"],
         "touches": {"measures": [], "processes": [], "sources": []},
         "pattern": {"text": "Late settlement confirmations are reported in two of the last two weekly check-ins.", "periods": [wk40, wk41],
                     "numbers": [{"label": "Weeks with a late settlement confirmation", "value": 2, "unit": "weeks",
                                  "trace": {"kind": "week_item", "ref": f"{ids['w1']}/{wk41}/{weeks1[2]['items'][1]['id']}", "at": weeks1[2]["opens"]}}]},
         "evidence": [{"id": "ev1", "text": "Week items on 28 September and 5 October.", "kind": "supports",
                       "source": {"kind": "week_item", "ref": f"{ids['w1']}/{wk40}/{weeks1[1]['items'][3]['id']}"}, "by": "lens", "at": at("2026-10-07", "00:40")},
                      {"id": "ev2", "text": "Both came from one broker that changed its cut-off; it may already be settled.", "kind": "disputes",
                       "source": {"kind": "person", "ref": "natasha-wee"}, "by": P["Natasha Wee"]["account_id"], "at": at("2026-10-07", "01:30")}],
         "judgement": {"fits": None, "why": "", "confidence": None,
                       "start_answers": {"goal": "", "people": "", "build": "", "definitions": "", "areas": "", "deadline": ""}, "at": None},
         "picked_up_by": None, "picked_up_at": None, "became": None, "parked": None, "dismissed": None,
         "history": [{"at": at("2026-10-07", "00:30"), "by": "watcher", "action": "noticed", "note": ""}]},
    ]
    return plans, backlog, opps


# ---- writing ---------------------------------------------------------------------------------------------------------------------

def write_plan(plane, plan: Plan) -> None:
    rec, lines = plan.rec, _events_lines(plan)
    last = lines[-1] if lines else None
    rec["event_count"] = len(lines)
    rec["events"] = {"path": f"intents/{rec['id']}/events.jsonl", "count": len(lines), "last_seq": len(lines), "last_at": last["at"] if last else None}
    folder = plane.path("intents", rec["id"])
    with S.locked(plane):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "events.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        for w_ in plan.weeks:
            CK.write_week(plane, rec["id"], w_)
        if plan.processes:
            write_json_atomic(folder / "processes.json", plan.processes)
        S.write_intent(plane, rec, create=True)


def seed(data_root: Path, company_id: str = COMPANY, reset: bool = False) -> dict:
    data_root = Path(data_root)
    plane = _plane(PlaneStore(data_root), company_id)
    people, counts = seed_people(data_root, plane)
    plans, backlog, opps = scenario(people)
    written, kept = [], []
    for plan in plans:
        folder = plane.path("intents", plan.rec["id"])
        if folder.exists() and reset:
            shutil.rmtree(folder)  # the seed's own intent folder only (its id is the seed's)
        if (folder / "intent.json").exists():
            kept.append(plan)
            continue
        write_plan(plane, plan)
        written.append(plan)
    bpath = plane.path("intents", "backlog.json")
    with lock_for(bpath):
        doc = read_json_strict(bpath, dict) or {"items": []}
        mine = {b["id"] for b in backlog}
        if reset:
            doc["items"] = [i for i in doc.get("items") or [] if i.get("id") not in mine]
        have = {i.get("id") for i in doc.setdefault("items", [])}
        new_items = [b for b in backlog if b["id"] not in have]
        if new_items:
            doc["items"].extend(new_items)
            write_json_atomic(bpath, doc)
    new_opps = []
    for o in opps:
        p = plane.path("intents", "opportunities", f"{o['id']}.json")
        if reset or not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(p, o)
            new_opps.append(o)
    S.rebuild_index(plane, "demo seed")
    return {"people": counts, "written": written, "kept": kept, "backlog_added": len(new_items), "backlog_total": len(doc["items"]),
            "opportunities_added": len(new_opps), "home": home_numbers(plane), "credentials": data_root / "_control" / "seed_credentials.txt"}


def home_numbers(plane, today: date | None = None) -> dict:
    """The home's figures (04 subline, 19 M01, M02, M13, M08) from the records on disk, each with the ids it counts."""
    today = today or datetime.now(timezone.utc).date()
    month = today.isoformat()[:7]
    quarter = (today.year, (today.month - 1) // 3)
    recs = [r for r in (S.read_intent(plane, row["id"]) for row in S.read_index(plane)) if r]
    live = [r for r in recs if r["state"] != "draft"]
    closed = [r for r in live if r["state"] == "closed"]
    inside = [r for r in closed if r["closure"]["closed_at"] <= r["time_box"]["ends"]]
    rated = [r for r in closed if r["type"] != "pulse"]
    scores = [x["score"] for r in rated for x in r["ratings"]]

    def q(s: str) -> tuple:
        d = date.fromisoformat(s[:10])
        return d.year, (d.month - 1) // 3
    ready = [r for r in live if r["type"] == "initiative" and r["outcome"].get("build_ready") is True
             and any(s["key"] == "build_ready" and s["closed_at"] and q(s["closed_at"]) == quarter for s in r["stages"])]
    ids = lambda rs: [r["id"] for r in rs]  # noqa: E731
    return {
        "running": ids([r for r in live if r["state"] in ("open", "in_session", "closing")]),
        "closed_this_month": ids([r for r in closed if r["closure"]["closed_at"][:7] == month]),
        "M01_opened_this_month": ids([r for r in live if r["stages"] and (r["stages"][0]["opened_at"] or "")[:7] == month]),
        "M02_closed_inside_time_box": {"n": len(inside), "of": len(closed), "ids": ids(inside)},
        "M13_ratings": {"count": len(scores), "mean": round(sum(scores) / len(scores), 1) if len(scores) >= 3 else None, "ids": ids(rated)},
        "M08_build_ready_this_quarter": {"n": len(ready), "handed_to_build": sum(1 for r in ready if r["links"]["build"]), "ids": ids(ready)},
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Seed the Intent Centre demo plane (illustrative, synthetic).")
    ap.add_argument("company_id", nargs="?", default=COMPANY)
    ap.add_argument("--reset", action="store_true", help="rewrite the seed's own intent records, backlog items and opportunities")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed(root, args.company_id, args.reset)
    c = r["people"]
    print(f"Accounts: {c['accounts_created']} created, {c['accounts_total']} on the roster. People added to the profile: {c['people_added']}. "
          f"Area tags set: {c['tags_set']}. Areas added: {c['areas_added']}.")
    if c["accounts_created"]:
        print(f"Sign-in details for the new accounts were appended to: {r['credentials']}")
    print(f"Intents written: {len(r['written'])}, already there and left alone: {len(r['kept'])}.")
    for p in r["written"] + r["kept"]:
        stage = next((s["key"] for s in p.rec["stages"] if s["state"] == "open"), "-")
        print(f"  {p.key:8} {p.rec['id']}  {p.rec['type']:10} {p.rec['state']:10} {stage:22} {p.rec['title']}")
    print(f"Backlog items added: {r['backlog_added']} (total {r['backlog_total']}). Opportunities written: {r['opportunities_added']}.")
    print("Home figures and the records they count:")
    for k, v in r["home"].items():
        print(f"  {k}: {json.dumps(v)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
