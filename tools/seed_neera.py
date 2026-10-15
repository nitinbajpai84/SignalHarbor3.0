"""Neera Family Office: a second, empty-of-intents company for the manual walk of the return cycle (synthetic, illustrative).

Usage: python tools/seed_neera.py [--data-root PATH]
Idempotent: the company, accounts, areas, people and systems are made once and left alone after; the pack data is reloaded through
tools/seed_demo_cycle.py (tables replaced, runs and alerts merged by id, documents skipped by name). Only the warehouse, run log,
alerts, landing files and text documents are loaded: no intents, opportunities, hypotheses, wall cards, week files or proving.
New passwords are appended to <data_root>/_control/seed_credentials.txt and never printed. What was written goes to
<plane>/settings/seed_neera.json.
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.jsonfile import lock_for, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile import areas as PA  # noqa: E402
from sh_platform.profile import store as PS  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from tools import seed_demo_cycle as DC  # noqa: E402
from tools.seed import DOMAIN, HEADER, _new_password  # noqa: E402

COMPANY, NAME, INDUSTRY = "neera", "Neera Family Office", "family_office"
TIME_ZONE, CURRENCY = "Asia/Singapore", "SGD"
BY = "Arjun Mehta"  # the company admin who keeps the people file
PROV = {"mark": "stated", "by": BY, "from": "Neera setup (illustrative seed)"}

# (name, job title, company role, team, areas)
PEOPLE = [
    ("Priya Nair", "Principal", "sponsor", "Leadership", "company-wide"),
    ("Arjun Mehta", "Head of Operations", "company_admin", "Operations", "Operations"),
    ("Leela Raman", "Head of Data", "analyst", "Technology", "Reporting, Technology"),
    ("Dev Sharma", "Analyst", "participant", "Investments", "Investments"),
    ("Kiran Iyer", "Operations Lead", "owner", "Operations", "Operations"),
    ("Meera Pillai", "Compliance Lead", "approver", "Compliance", "Compliance"),
    ("Rohan Das", "Treasury Officer", "participant", "Treasury", "Treasury"),
    ("Anita Bose", "Investments Associate", "participant", "Investments", "Investments"),
    ("Sameer Khan", "Reporting Officer", "participant", "Reporting", "Reporting"),
    ("Nisha Rao", "Technology Officer", "participant", "Technology", "Technology"),
]
AREAS = [("treasury", "Treasury", "department"), ("operations", "Operations", "operations_area"), ("investments", "Investments", "department"),
         ("compliance", "Compliance", "department"), ("reporting", "Reporting", "department"), ("technology", "Technology", "department")]
# Where the pack's data comes from, one per demo_cycle folder group, so the map has its sources before any Define.
SYSTEMS = [
    ("custodian-daily-files", "Custodian daily files", "feed", "Kiran Iyer", "Manual CSV download from three custodian portals", "Daily, working days"),
    ("fund-administrator-statements", "Fund administrator statements", "file drop", "Kiran Iyer", "File share; manual download", "Monthly"),
    ("bank-cash-balances", "Bank cash and money market balances", "feed", "Rohan Das", "Bank portal export", "Daily"),
    ("fx-rates-file", "FX rates file", "feed", "Rohan Das", "Daily rates file", "Daily, working days"),
    ("valuations-workbook", "Private asset valuations workbook", "spreadsheet", "Anita Bose", "Manager statements keyed into the workbook", "Quarterly"),
    ("family-report-pack", "Monthly family report pack", "spreadsheet", "Sameer Khan", "Built by hand from the files above", "Monthly"),
    ("family-reporting-portal", "Family reporting portal", "system", "Nisha Rao", "Page views and questions logged by the portal", "Daily"),
]
DOC_FOLDERS = ("text", "treasury")  # the 48 office documents; feedback notes and custody emails stay out
STEPS = [s for s in DC.STEPS if s[0] in ("silver", "gold", "runs and alerts", "landing")] + [
    ("documents", None, functools.partial(DC.load_documents, uploader="Kiran Iyer", folders=DOC_FOLDERS))]

# Names in the pack's documents become Neera's. Longest first; whole words; ids, measure codes, funds, custodians and administrators stay.
RENAMES = [
    ("Janet Shaw", "Arjun Mehta"), ("Daniel Kerr", "Priya Nair"), ("Katie Kingsley", "Leela Raman"), ("Marcus Todd", "Leela Raman"),
    ("Aaron Lyle", "Dev Sharma"), ("Harvey Rowley", "Kiran Iyer"), ("Grace Ward", "Meera Pillai"), ("Mei Ling Chong", "Rohan Das"),
    ("Ravi Chandran", "Anita Bose"), ("Rahul Mehta", "Sameer Khan"),
    ("Shaw Wei Jie", "Vikram Nair"), ("Kerr Mei Xin", "Asha Nair"), ("Shaw Family Trust", "Nair Family Trust"),
    ("Mr Shaw", "Mr Nair Senior"), ("Mrs Shaw", "Mrs Nair"), ("Wei Jie", "Vikram"), ("Mei Xin", "Asha"),
    ("janet.shaw", "arjun.mehta"), ("daniel.kerr", "priya.nair"), ("katie.kingsley", "leela.raman"), ("harvey.rowley", "kiran.iyer"),
    ("rahul.mehta", "sameer.khan"), ("ardmore.example", "neera.example"),
    ("Ardmore demo", "Neera Family Office demo"), ("Ardmore:", "Neera Family Office:"), ("Ardmore", "Neera"), ("ARDMORE", "NEERA"),
    ("Mei Ling", "Rohan"), ("Janet", "Arjun"), ("Daniel", "Priya"), ("Katie", "Leela"), ("Marcus", "Leela"), ("Aaron", "Dev"),
    ("Harvey", "Kiran"), ("Grace", "Meera"), ("Ravi", "Anita"), ("Rahul", "Sameer"),
]
_RENAME_RE = re.compile("|".join(r"(?<![\w.])" + re.escape(a) + r"(?![\w])" if a[0].isalnum() else re.escape(a) for a, _ in RENAMES))
_RENAME_TO = dict(RENAMES)


def localise_text(text: str) -> str:
    return _RENAME_RE.sub(lambda m: _RENAME_TO[m.group()], text)


def _walk(v):
    if isinstance(v, str):
        return localise_text(v)
    if isinstance(v, list):
        return [_walk(x) for x in v]
    if isinstance(v, dict):
        return {k: _walk(x) for k, x in v.items()}
    return v


def localise_documents(plane) -> list[str]:
    """Rewrite every loaded document (text, title, uploader, description) in Neera's names. Returns the files changed; a re-run changes none."""
    changed = []
    for f in sorted(plane.path("context", "agent_docs").rglob("*.json")):
        old = json.loads(f.read_text(encoding="utf-8"))
        doc = _walk(old)
        if doc != old:
            doc["chars"] = sum(len(c["text"]) for c in doc.get("chunks", [])) if "chars" in doc else doc.get("chars")
            write_json_atomic(f, doc)
            changed.append(f.name)
    return changed


def slug(name: str) -> str:
    return "-".join(name.lower().split())


def email_of(name: str) -> str:
    return f"{'.'.join(name.lower().split())}.{COMPANY}@{DOMAIN}"


def area_ids(text: str) -> list[str]:
    if text == "company-wide":
        return [a for a, _, _ in AREAS]
    by = {n.lower(): a for a, n, _ in AREAS}
    return [by[t.strip().lower()] for t in text.split(",")]


def company(data_root: Path) -> dict:
    es = EntitlementStore(data_root)
    if es.company(COMPANY) is None:
        es.create_company(COMPANY, NAME, INDUSTRY, modules=es.catalogue.ids)
        return {"created": True, "modules": es.enabled_modules(COMPANY)}
    for m in es.catalogue.ids:  # a re-run switches on what is off, never off what is on
        if not es.is_enabled(COMPANY, m):
            es.set_module(COMPANY, m, True)
    return {"created": False, "modules": es.enabled_modules(COMPANY)}


def accounts(data_root: Path) -> tuple[dict[str, str], int]:
    store, lines, ids = AccountStore(data_root), [], {}
    for name, _, role, _, _ in PEOPLE:
        acct = store.get_by_email(email_of(name))
        if acct is None:
            password = _new_password()
            acct = store.create(email_of(name), password, name, COMPANY, [role])
            lines.append(f"{email_of(name)}  {password}  {role}  {COMPANY}")
        ids[name] = acct["account_id"]
    if lines:
        creds = data_root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return ids, len(lines)


def profile(plane, ids: dict[str, str]) -> dict:
    def change(doc: dict) -> dict:
        out = {"areas_added": 0, "people_added": 0, "systems_added": 0}
        co = doc.setdefault("company", {})
        for f, v in (("name", NAME), ("time_zone", TIME_ZONE), ("currency", CURRENCY)):
            co.setdefault(f, PS.cell(v, PROV))
        have = set(doc.get("areas") or {})
        for aid, nm, kind in AREAS:
            if aid not in have:
                PA._add(doc, aid, nm, kind, BY, "Added by the company admin")
                out["areas_added"] += 1
        for name, title, _, team, areas in PEOPLE:
            pid = slug(name)
            if pid in doc["people"]:
                continue
            for f, v in (("name", name), ("role", title), ("team", team), ("email", email_of(name)), ("account_id", ids[name]), ("areas", area_ids(areas))):
                PS.set_cell(doc, f"people.{pid}.{f}", v, PROV)
            out["people_added"] += 1
        for sid, nm, kind, owner, lands, freq in SYSTEMS:
            if sid in doc["systems"]:
                continue
            for f, v in (("name", nm), ("kind", kind), ("owner", owner), ("lands", lands), ("frequency", freq), ("personal_data", "No")):
                PS.set_cell(doc, f"systems.{sid}.{f}", v, PROV)
            out["systems_added"] += 1
        return out
    return PS.mutate(plane, change)


def seed(data_root: Path, log=print) -> dict:
    data_root = Path(data_root)
    out = {"company": company(data_root)}
    plane = PlaneStore(data_root).plane_for(COMPANY).ensure()
    ids, made = accounts(data_root)
    out["accounts"] = {"created": made, "total": len(ids), "ids": ids}
    out["profile"] = profile(plane, ids)
    out["pack"] = DC.seed(data_root, COMPANY, log=log, steps=STEPS)
    out["documents_localised"] = localise_documents(plane)
    out["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json_atomic(plane.path("settings", "seed_neera.json"), out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed Neera Family Office (illustrative, synthetic).")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed(root)
    print(f"Neera: company {'created' if r['company']['created'] else 'kept'}, modules {len(r['company']['modules'])}, "
          f"accounts created {r['accounts']['created']} of {r['accounts']['total']}, profile {r['profile']}.")
    print(f"Sign-in details are in: {root / '_control' / 'seed_credentials.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
