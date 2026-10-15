"""Harbor 3.0 role suggestions: a person's job (`<company>/v3/settings.json` "jobs": {email: role_id}) picks the actions and the
builds the industry pack suggests (`role_builds.yaml`). Suggestions only; the person decides. No pack or no job: an honest empty."""
from __future__ import annotations

from sh_platform.jsonfile import lock_for
from sh_platform.v1 import v3_harbor as H, v3_model as M, v3_ops as O

ADMINISH = {"company_admin", "sponsor", "analyst"}


def _roles(plane) -> list[dict]:
    pack = M.pack_of(plane)
    try:
        doc = pack.section("role_builds") if pack is not None else None
    except KeyError:
        return []
    rows = doc.get("roles") if isinstance(doc, dict) else None
    return [r for r in rows or [] if isinstance(r, dict) and r.get("id")]


def _jobs(plane) -> dict:
    j = O.settings(plane).get("jobs")
    return j if isinstance(j, dict) else {}


def _first_say(t: dict) -> str:
    return next((str(e.get("text") or "") for e in t.get("events") or [] if e.get("kind") == "person"), "")


def my_role(plane, email: str) -> dict:
    rows = _roles(plane)
    out = {"role": None, "actions": [], "builds": [], "roles": [{"id": r["id"], "title": str(r.get("title") or r["id"])} for r in rows]}
    mine = next((r for r in rows if r["id"] == _jobs(plane).get(email.strip().casefold())), None)
    if mine is None:
        return out
    started = {_first_say(t): t["id"] for t in reversed(H.all_threads(plane))}  # newest wins
    out["role"] = {"id": mine["id"], "title": str(mine.get("title") or mine["id"])}
    out["actions"] = [str(a) for a in mine.get("actions") or []]
    out["builds"] = [{"id": str(b.get("id")), "title": str(b.get("title") or ""), "say": str(b.get("say") or ""),
                      "dashboard": str(b.get("dashboard") or ""), "skills": [str(s) for s in b.get("skills") or []],
                      "started": started.get(str(b.get("say") or "")) if b.get("say") else None}
                     for b in mine.get("builds") or [] if isinstance(b, dict)]
    return out


def set_job(plane, email: str, role: str) -> None:
    """ValueError when the role is not one of the pack's. An empty role clears the job."""
    if role and role not in {r["id"] for r in _roles(plane)}:
        raise ValueError("Choose one of the roles in the list.")
    email = email.strip().casefold()
    with lock_for(O._sfile(plane)):
        s = O.settings(plane)
        jobs = {k: v for k, v in _jobs(plane).items() if k != email}
        if role:
            jobs[email] = role
        s["jobs"] = jobs
        O._save(plane, s)


def jobs_list(plane, accounts: list[dict]) -> list[dict]:
    j = _jobs(plane)
    return sorted(({"email": a["email"], "name": a["display_name"], "role": j.get(a["email"])} for a in accounts if not a.get("disabled")),
                  key=lambda p: p["name"])
