"""Synthetic seed: four illustrative companies, their people and one platform account.

Usage: python tools/seed.py [--data-root PATH] [--reset-credentials]
Idempotent and never deletes. Passwords go only to <data_root>/_control/seed_credentials.txt; never printed.
"""
from __future__ import annotations

import argparse
import logging
import secrets
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import SUPER_ADMIN, AccountStore  # noqa: E402
from sh_platform.context_docs.reader import Refusal, allowed_extensions, safe_name  # noqa: E402
from sh_platform.context_docs.store import DocStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402

log = logging.getLogger(__name__)

# The industry is a parameter: change this table, nothing else. Industry content lives in packs/.
COMPANIES = [
    {"id": "harbor-mutual", "name": "Illustrative Harbor Mutual", "industry": "insurance",
     "package": "discover", "roles": None},
    {"id": "tidewater-capital", "name": "Illustrative Tidewater Capital", "industry": "asset_management",
     "package": "build", "roles": None},
    {"id": "lakeside-family-office", "name": "Illustrative Lakeside Family Office", "industry": "family_office",
     "package": "discover", "roles": None},
    {"id": "solo-studio", "name": "Illustrative Solo Studio", "industry": "unlisted",
     "package": None, "roles": [["company_admin", "sponsor"]]},  # one person, no package, no modules
]
TEAM_ROLES = ["company_admin", "sponsor", "analyst", "participant", "approver", "owner"]
# A person's name, not a role: every part of a display name is protected by the egress vault, so a role-and-company
# name ("Company Admin (Lakeside Family Office)") blocked ordinary words such as "family office" (3 Oct 2026).
#
# The names follow the family-office demo story (packs/family_office/1/demo_story/00_story.md). The analyst is a person who owns no
# measure in it (the story's Investment Analyst seat is vacant), so an analyst never answers as a process owner (CRITIC-M2 P7);
# Sara Lim, the story's process owner, holds the owner role. Lena Kerr, an extra with no part in the story, is gone.
PERSON_NAMES = {"company_admin": "Mei Tan", "sponsor": "Arjun Rao", "analyst": "Priya Nair",
                "participant": "Wei Chen", "approver": "Tom Ng", "owner": "Sara Lim"}
# Lina Ho (HR Lead, owner of the pay measure) deliberately has no account: she answers by link, as an owner with no account.
OFF_SYSTEM_OWNERS = {"lakeside-family-office": ["Lina Ho"]}
DOMAIN = "example.test"
HEADER = ("# SYNTHETIC, LOCAL ONLY. Sign-in details for the Illustrative seed accounts.\n"
          "# Never commit or share this file. Columns: email  password  roles  company\n")


LOCAL_FILE = ROOT / "local" / "companies.yaml"  # optional and gitignored: companies that must never be committed
LOCAL_MODULES = ["m1_intent", "m2_baseline", "m3_connect"]


def _inside(base: Path, rel) -> Path:
    """The resolved path (links followed), refused unless it lies inside the local folder."""
    p = (base / str(rel)).resolve()
    if not p.is_relative_to(base.resolve()):
        raise ValueError(f"{rel!r} in the local company file points outside the local folder: refused")
    return p


def load_local_companies(path: Path | None = LOCAL_FILE) -> list[dict]:
    """Companies from an optional local file, in the shape of COMPANIES plus `names` (role -> person), `brand`
    ({logo: absolute Path, primary_colour}), `documents` (files) and `off_system` (people with no account).
    Paths in the file are relative to the file's folder. No file, or a bad one, gives [] and a log line."""
    if path is None or not Path(path).is_file():
        return []
    base = Path(path).parent
    try:
        rows = (yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}).get("companies") or []
    except (OSError, yaml.YAMLError) as e:
        log.warning("local company file %s was not read: %s", path, e)
        return []
    out = []
    for r in rows:
        try:
            people_ = r.get("people") or []
            names = {}
            for p in people_:  # the first person with a seeded role takes that role's account
                if p.get("role") in TEAM_ROLES:
                    names.setdefault(p["role"], p["name"])
            brand = r.get("brand") or {}
            if r["id"] in {b["id"] for b in COMPANIES}:
                raise ValueError(f"local company id {r['id']!r} is a built-in company's id: choose another id")
            logo = _inside(base, brand["logo"]) if brand.get("logo") else None
            docs: list[Path] = []
            for d in r.get("documents") or []:
                d = _inside(base, d)
                found = sorted(p for p in d.iterdir() if p.is_file()) if d.is_dir() else [d]
                for p in found:
                    if _inside(base, p).suffix.lower().lstrip(".") in allowed_extensions():
                        docs.append(p)
                    else:
                        log.warning("local document %s skipped: its type cannot be read", p.name)
            out.append({"id": r["id"], "name": r["name"], "industry": r["industry"], "package": None, "roles": None,
                        "modules": r.get("modules") or LOCAL_MODULES, "names": names, "documents": docs,
                        "brand": {"logo": logo, "primary_colour": brand.get("primary_colour")},
                        "off_system": [p["name"] for p in people_ if p.get("role") not in TEAM_ROLES]})
        except (KeyError, TypeError, AttributeError) as e:
            log.warning("a company in %s was skipped (missing or odd field: %s)", path, e)
    return out


def people(local: list[dict] | None = None) -> list[dict]:
    out = [{"email": f"platform@{DOMAIN}", "name": "Illustrative Platform Admin",
            "company": None, "roles": [SUPER_ADMIN]}]
    for c in [*COMPANIES, *(local or [])]:
        for roles in c["roles"] or [[r] for r in TEAM_ROLES]:
            out.append({"email": f"{'-'.join(roles)}.{c['id']}@{DOMAIN}",
                        "name": c.get("names", {}).get(roles[0]) or PERSON_NAMES[roles[0]],
                        "company": c["id"], "roles": roles})
    return out


def _new_password() -> str:
    return secrets.token_urlsafe(16)


# The demo story's presenter script and the owners' example answers are for the presenter and the end-to-end test,
# not documents a client would send: they never go into a company's context.
NOT_CLIENT_DOCUMENTS = {"00_story.md", "12_owner_answers_example.md", "18_glossary_ambiguities_answer_key.md"}
# Pay and bonus documents are restricted: no agent ever reads them, whoever asks (a family office's HR content).
RESTRICTED_WORDS = ("bonus", "payroll", "pay_workbook", "pay workbook", "salary")


def is_restricted(name: str) -> bool:
    return any(w in name.lower() for w in RESTRICTED_WORDS)


def _plane(planes: PlaneStore, company_id: str):
    """The company's plane; a registered company whose folder is missing gets one made, so the seed carries on."""
    try:
        return planes.plane_for(company_id).ensure()
    except LookupError:
        return planes.create(company_id)


def seed_demo_documents(data_root: Path, packs_root: Path = ROOT / "packs") -> int:
    """Puts each company's industry pack demo documents (packs/<industry>/<latest>/demo_documents/ and demo_story/) into that company's
    Company context for North (private) and for Lens (shared_full), as the company admin. Skips a file name already there, so a re-run adds nothing.
    A file that cannot be read is logged and skipped; the rest still go in."""
    es, accounts, planes = EntitlementStore(data_root), AccountStore(data_root), PlaneStore(data_root)
    added = 0
    for c in COMPANIES:
        versions = [int(v.name) for v in (packs_root / c["industry"]).glob("*") if v.name.isdigit()]
        latest = packs_root / c["industry"] / str(max(versions, default=0))
        files = [p for folder in (latest / "demo_documents", latest / "demo_story") if folder.is_dir()
                 for p in sorted(folder.iterdir()) if p.is_file() and p.name not in NOT_CLIENT_DOCUMENTS]
        admin = accounts.get_by_email(f"company_admin.{c['id']}@{DOMAIN}")
        if not files or admin is None or es.company(c["id"]) is None:
            continue
        docs = DocStore(_plane(planes, c["id"]))
        for agent, visibility in (("north", "private"), ("lens", "shared_full")):  # Lens reads the same set, in full
            have = {d["filename"]: d for d in docs.documents(agent)}
            for f in files:
                if safe_name(f.name) in have:
                    if is_restricted(f.name) and not have[safe_name(f.name)].get("restricted"):
                        docs.set_restricted(agent, have[safe_name(f.name)]["doc_id"], True)
                    continue
                try:
                    docs.upload(agent, admin["account_id"], f.name, f.read_bytes(),
                                title=f"Illustrative: {f.stem.replace('_', ' ')}", visibility=visibility, restricted=is_restricted(f.name))
                    added += 1
                except Refusal as e:
                    log.warning("demo document %s was not taken in: %s", f.name, e)
    return added


def seed_local_documents(data_root: Path, local: list[dict]) -> int:
    """A local company's documents go onto North's shelf and onto Lens's, as the company admin. Lens's copies are
    `shared_full`, exactly as seed_demo_documents does; pay and HR documents stay restricted on both. A re-run adds nothing."""
    es, accounts, planes = EntitlementStore(data_root), AccountStore(data_root), PlaneStore(data_root)
    added = 0
    for c in local:
        admin = accounts.get_by_email(f"company_admin.{c['id']}@{DOMAIN}")
        if not c["documents"] or admin is None or es.company(c["id"]) is None:
            continue
        docs = DocStore(_plane(planes, c["id"]))
        for agent, visibility in (("north", "private"), ("lens", "shared_full")):
            have = {d["filename"]: d for d in docs.documents(agent)}
            for f in c["documents"]:
                restricted = is_restricted(f.name)
                if safe_name(f.name) in have:
                    if restricted and not have[safe_name(f.name)].get("restricted"):
                        docs.set_restricted(agent, have[safe_name(f.name)]["doc_id"], True)
                    continue
                try:
                    docs.upload(agent, admin["account_id"], f.name, f.read_bytes(),
                                title=f"Illustrative: {f.stem.replace('_', ' ')}", visibility=visibility, restricted=restricted)
                    added += 1
                except (Refusal, OSError) as e:
                    log.warning("local document %s was not taken in on %s: %s", f.name, agent, e)
    return added


def seed_brand(data_root: Path, local: list[dict]) -> None:
    """Copies each local company's logo into its plane (brand/logo.<ext>) and records the brand. Same bytes: nothing written."""
    es, planes = EntitlementStore(data_root), PlaneStore(data_root)
    for c in local:
        src, colour = c["brand"]["logo"], c["brand"]["primary_colour"]
        if es.company(c["id"]) is None or (src is None and not colour):
            continue
        brand = {"primary_colour": colour}
        if src is not None and src.suffix.lower() in (".png", ".svg") and src.is_file():
            brand["logo"] = f"logo{src.suffix.lower()}"
            dest = _plane(planes, c["id"]).path("brand", brand["logo"])
            dest.parent.mkdir(exist_ok=True)
            if not dest.is_file() or dest.read_bytes() != src.read_bytes():
                shutil.copyfile(src, dest)
        elif src is not None:
            log.warning("logo %s for %s is missing or not a .png or .svg: no logo set", src, c["id"])
        if (es.company(c["id"]) or {}).get("brand") != {k: v for k, v in brand.items() if v}:
            es.set_brand(c["id"], brand)


def seed(data_root: Path, reset: bool = False, local_file: Path | None = None) -> dict:
    """Returns counts and the credentials path; never a password. `local_file` is the optional local company file
    (main passes LOCAL_FILE when it exists); with none, the seed is exactly the built-in companies."""
    data_root = Path(data_root)
    local = load_local_companies(local_file)
    es, store = EntitlementStore(data_root), AccountStore(data_root)
    made_companies = 0
    for c in COMPANIES:
        if es.company(c["id"]) is None:
            es.create_company(c["id"], c["name"], c["industry"], package=c["package"])
            es.set_centre(c["id"], "intent", True)
            made_companies += 1
    for c in local:
        if es.company(c["id"]) is None:
            es.create_company(c["id"], c["name"], c["industry"], modules=c["modules"])
            es.set_centre(c["id"], "intent", True)
            made_companies += 1
        else:  # a re-run brings the switches up to date, never down
            for m in c["modules"]:
                if not es.is_enabled(c["id"], m):
                    es.set_module(c["id"], m, True)
    creds_path = data_root / "_control" / "seed_credentials.txt"
    lines: dict[str, str] = {}  # email -> credentials line
    if creds_path.is_file() and not reset:
        for ln in creds_path.read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.startswith("#"):
                lines[ln.split()[0]] = ln
    made = reissued = 0
    for p in people(local):
        existing = store.get_by_email(p["email"])
        if existing and existing.get("display_name") != p["name"]:
            store.set_display_name(p["email"], p["name"])
        if existing and not reset:
            continue
        password = _new_password()
        if existing:
            store.set_password(p["email"], password)
            reissued += 1
        else:
            store.create(p["email"], password, p["name"], p["company"], p["roles"])
            made += 1
        lines[p["email"]] = f"{p['email']}  {password}  {','.join(p['roles'])}  {p['company'] or '-'}"
    if made or reissued:
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        creds_path.write_text(HEADER + "\n".join(lines.values()) + "\n", encoding="utf-8")
    seed_brand(data_root, local)
    off_system = {**OFF_SYSTEM_OWNERS, **{c["id"]: c["off_system"] for c in local if c["off_system"]}}
    return {"companies": made_companies, "accounts": made, "reissued": reissued,
            "total": len(lines), "path": creds_path, "off_system_owners": off_system,
            "documents": seed_demo_documents(data_root) + seed_local_documents(data_root, local)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed illustrative companies and people (synthetic, local).")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    ap.add_argument("--reset-credentials", action="store_true", help="issue new passwords for the seeded accounts")
    ap.add_argument("--local-file", help=f"optional local company file; default: {LOCAL_FILE.relative_to(ROOT)} if it exists")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    local_file = Path(args.local_file) if args.local_file else LOCAL_FILE
    try:
        r = seed(root, args.reset_credentials, local_file if local_file.is_file() else None)
    except ValueError as e:  # a refused local company file: say why, change nothing further
        print(f"Seed stopped: {e}")
        return 1
    print(f"Companies created: {r['companies']}. Accounts created: {r['accounts']}, "
          f"passwords re-issued: {r['reissued']}. Demo documents added: {r['documents']}.")
    for company, names in r["off_system_owners"].items():
        print(f"Owners with no account in {company} (they answer by link): {', '.join(names)}.")
    if r["accounts"] or r["reissued"]:
        print(f"Sign-in details for {r['total']} accounts are in: {r['path']}")
    else:
        print(f"Nothing to do: existing accounts and passwords are unchanged. Details are in: {r['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
