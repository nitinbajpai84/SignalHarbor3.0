"""R1: the six build roles named at the charter. Lens drafts them from the profile's people (guessed, with the source);
the organiser sets them (stated). A guess never replaces a stated value. Pure rules: no files here."""
from datetime import datetime, timezone

ROLES = ("architect", "developer", "tester", "sponsor", "ops", "informed", "head_of_department")  # 59, C25: the seventh, who approves the design
LENS = "Lens"


def _v(p: dict, field: str):
    c = p.get(field)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _guess(source: str) -> dict:
    return {"mark": "guessed", "by": LENS, "from": source}


def draft(people: dict, approver_name: str, participants: list[str]) -> tuple[dict, dict]:
    """(roles, provenance) drafted from the people list, the session's approver and the people who took part."""
    rows = [(str(_v(p, "name") or ""), p) for p in people.values()]
    rows = [(n, p) for n, p in rows if n]
    roles: dict = {r: None for r in ROLES} | {"informed": []}
    prov: dict = {}

    def pick(role: str, test, source: str) -> None:
        for n, p in rows:
            if n not in roles.values() and test(p):
                roles[role], prov[role] = n, _guess(f"{source}: {n}")
                return

    text = lambda p: str(_v(p, "role") or "").lower()
    pick("architect", lambda p: _v(p, "is_head_of_data") is True, "The profile names the head of data")
    pick("developer", lambda p: "engineer" in text(p) or "data" in text(p), "Role in the profile reads engineer or data")
    pick("ops", lambda p: "operations" in text(p), "Role in the profile reads operations")
    if approver_name.strip():
        roles["sponsor"], prov["sponsor"] = approver_name.strip(), _guess("The approver named for this session")
    else:
        pick("sponsor", lambda p: _v(p, "is_sponsor") is True, "The profile names the sponsor")
    if participants:
        roles["informed"], prov["informed"] = participants, _guess("The people who took part in this session")
    return roles, prov


def merge(stored: dict | None, drafted: tuple[dict, dict]) -> dict:
    """Stated values from `stored` win; every other role takes the draft."""
    roles, prov = dict(drafted[0]), dict(drafted[1])
    for r, p in ((stored or {}).get("provenance") or {}).items():
        if r in ROLES and p.get("mark") == "stated":
            roles[r], prov[r] = stored["roles"].get(r), p
    return {"roles": roles, "provenance": prov}


def state(stored: dict | None, changes: dict, by: str) -> dict:
    """The organiser sets any of the roles: each one set becomes stated, by that person. Returns the record to keep."""
    now = datetime.now(timezone.utc).isoformat()
    roles = dict((stored or {}).get("roles") or {})
    prov = dict((stored or {}).get("provenance") or {})
    for r, v in changes.items():
        roles[r] = v
        prov[r] = {"mark": "stated", "by": by, "from": "Set by the organiser", "at": now}
    return {"roles": roles, "provenance": prov}


def clean(body: dict) -> dict | None:
    """The changes from a PUT body, or None when anything is not a role or not a name (informed: a list of names)."""
    ch = body.get("roles") if isinstance(body.get("roles"), dict) else body
    if not ch or set(ch) - set(ROLES):
        return None
    out: dict = {}
    for r, v in ch.items():
        if r == "informed":
            if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                return None
            out[r] = [x.strip()[:80] for x in v]
        elif v is None or (isinstance(v, str) and not v.strip()):
            out[r] = None
        elif isinstance(v, str):
            out[r] = v.strip()[:80]
        else:
            return None
    return out
