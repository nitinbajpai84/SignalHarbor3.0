"""Linking a profile person to a sign-in account (LI-LINK, decision A-043): `people.<pid>.account_id`.

Only the company admin writes `account_id`: a person's own cell (stated, "Linked by <admin>"), or an unlink. store.set_cell refuses any agent or
draft write there. Lens may only suggest, in `people.<pid>.account_suggestion` (guessed, agent lens, "Matched by email", with the file ref), when a
person's profile email equals the email of exactly one enabled account of the same company, and only when a company admin did the read. A
suggestion never replaces a person's link or unlink. One account belongs to at most one person."""
from typing import Any, Callable

from sh_platform.profile import store, view

# email -> the enabled accounts of this company with that email, as {account_id, ...}; the caller scopes it to the signed-in company
EmailLookup = Callable[[str], list[dict]]
LENS = "Lens"
MATCHED = "Matched by email"


class LinkRefusal(ValueError):
    """A link that cannot be made. The message is plain words for the screen."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _account_of(p: dict) -> str | None:
    c = p.get("account_id")
    return c.get("value") if isinstance(c, dict) and c.get("mark") == "stated" and not store.is_agent(c) else None


def _holder(doc: dict, account_id: str, besides: str) -> str | None:
    return next((k for k, p in doc["people"].items() if k != besides and _account_of(p) == account_id), None)


def auto_link(doc: dict, lookup: EmailLookup) -> None:
    """Suggests (never links) the account for every person with an email that matches exactly one enabled account. Works on `doc` in place."""
    for pid, p in doc["people"].items():
        email = p.get("email")
        if isinstance(p.get("account_id"), dict):
            continue  # a person linked or unlinked this one: never suggested again
        if not isinstance(email, dict) or email.get("mark") == "unknown" or not str(email.get("value") or "").strip():
            continue
        found = lookup(str(email["value"]).strip().casefold())
        if len(found) != 1 or _holder(doc, found[0]["account_id"], pid):
            continue
        prov = {"mark": "guessed", "by": LENS, "agent": "lens", "from": MATCHED, **({"ref": email["ref"]} if email.get("ref") else {})}
        store.set_cell(doc, f"people.{pid}.account_suggestion", found[0]["account_id"], prov)


def set_link(plane, accounts, company_id: str, pid: str, account_id: str | None, by: str) -> None:
    """The admin's link (or unlink when `account_id` is None). `accounts` is the account store; raises LinkRefusal."""
    acct = None
    if account_id is not None:
        acct = accounts.get(account_id)
        if not acct or acct.get("company_id") != company_id:
            raise LinkRefusal("That account is not available for this company. Pick one from the list.")
        if acct.get("disabled"):
            raise LinkRefusal("That account is switched off. Switch it on first, or pick another.")

    def change(doc: dict) -> None:
        if pid not in doc["people"]:
            raise LinkRefusal("We could not find that person.", 404)
        if account_id is not None:
            other = _holder(doc, account_id, pid)
            if other:
                name = (doc["people"][other].get("name") or {}).get("value") or "someone else"
                raise LinkRefusal(f"That account is already linked to {name}. Unlink it there first.", 409)
        doc["people"][pid].pop("account_suggestion", None)  # the admin has decided
        who = by or "your administrator"
        prov = {"mark": "stated" if account_id else "unknown", "by": who, "from": f"{'Linked' if account_id else 'Unlinked'} by {who}"}
        store.set_cell(doc, f"people.{pid}.account_id", account_id, prov)
    store.mutate(plane, change)


def _suggestion(p: dict, files: dict) -> dict | None:
    c = p.get("account_suggestion")
    if _account_of(p) or isinstance(p.get("account_id"), dict) or not isinstance(c, dict) or not c.get("value"):
        return None
    return {"account_id": c["value"], "file": files.get((c.get("ref") or {}).get("id"))}


def listing(plane, accounts, company_id: str) -> dict:
    """What the admin's picker needs: each person with their linked account, and the company's enabled accounts by display name."""
    doc = store.raw(plane)
    files = {d.get("id"): d.get("name") for i in doc["inputs"].values() for d in view._list(i.get("documents"))}
    people = []
    for pid, p in doc["people"].items():
        c = p.get("account_id") if isinstance(p.get("account_id"), dict) else {}
        people.append({"id": pid, "name": view._v(p, "name") or pid, "role": view._v(p, "role"), "team": view._v(p, "team"),
                       "account_id": _account_of(p), "link_from": c.get("from") if _account_of(p) else None, "suggestion": _suggestion(p, files)})
    enabled = [{"account_id": a["account_id"], "display_name": a["display_name"]} for a in accounts.in_company(company_id) if not a["disabled"]]
    return {"people": people, "accounts": enabled}


def lookup_for(accounts, company_id: str) -> EmailLookup:
    """Looks an email up among the enabled accounts of one company only."""
    def find(email: str) -> list[dict]:
        a = accounts.get_by_email(email)
        return [a] if a and a.get("company_id") == company_id and not a.get("disabled") else []
    return find
