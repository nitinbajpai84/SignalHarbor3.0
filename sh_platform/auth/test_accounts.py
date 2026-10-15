"""Separate throwaway accounts per agent for tests. Never a real person's account."""
import secrets

from sh_platform.auth.accounts import AccountStore


def make_test_account(store: AccountStore, agent_name: str, company_id: str | None,
                      roles: list[str]) -> tuple[dict, str]:
    """Create one account for `agent_name`; returns (account, random password). Password is shown once."""
    password = secrets.token_urlsafe(16)
    slug = "".join(c if c.isalnum() else "-" for c in agent_name.lower())
    acct = store.create(f"{slug}@test.invalid", password, f"Test {agent_name}", company_id, roles)
    return acct, password
