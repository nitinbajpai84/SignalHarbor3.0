"""Accounts in <data_root>/_control/accounts.json. No company data lives here."""
import hashlib
import hmac
import re
import secrets
import uuid
from functools import lru_cache
from pathlib import Path

from sh_platform.auth import permissions as P
from sh_platform.auth.permissions import load_permissions
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import valid_company_id  # the one rule for company ids


def _permission_stamp() -> tuple:
    """The permission files and when each last changed. Every AccountStore used to parse all of them (82 YAML files, about 0.2 s), on
    every request that reads accounts (Tally, Pulse, access, comments)."""
    from sh_platform.v1 import extra_permission_files
    return tuple((str(f), f.stat().st_mtime_ns) for f in [Path(P.DEFAULT_PATH), *extra_permission_files()])


@lru_cache(maxsize=4)
def _role_names(stamp: tuple) -> frozenset[str]:
    """The role names. `stamp` is only the cache key: a changed permission file gives a new stamp and a fresh parse."""
    return frozenset(load_permissions().roles)

_N, _R, _P = 2**15, 8, 1
_MAXMEM = 2**26  # scrypt needs 128*N*r = 32 MiB; leave headroom
_EMAIL = re.compile(r"[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+")
SUPER_ADMIN = "super_admin"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=_MAXMEM)
        return scheme == "scrypt" and hmac.compare_digest(got, bytes.fromhex(dk))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def normalise_email(email: str) -> str:
    return email.strip().casefold()


class AccountStore:
    def __init__(self, data_root: str | Path):
        self._path = Path(data_root) / "_control" / "accounts.json"
        self._lock = lock_for(self._path)
        self._roles = set(_role_names(_permission_stamp()))

    def _read(self) -> list[dict]:
        return read_json_strict(self._path, list) or []

    def _write(self, accounts: list[dict]) -> None:
        write_json_atomic(self._path, accounts)

    def create(self, email: str, password: str, display_name: str, company_id: str | None,
               roles: list[str], disabled: bool = False) -> dict:
        email = normalise_email(email)
        if len(email) > 254 or not _EMAIL.fullmatch(email):
            raise ValueError("invalid email")
        if not password:
            raise ValueError("a password is required")
        unknown = set(roles) - self._roles
        if unknown or not roles:
            raise ValueError(f"unknown or empty roles: {sorted(unknown)}")
        if (SUPER_ADMIN in roles) != (company_id is None):
            raise ValueError("a super admin has no company; every other account has one")
        if company_id is not None:
            valid_company_id(company_id)
        password_hash = hash_password(password)  # slow: outside the lock
        with self._lock:
            accounts = self._read()
            if any(a["email"] == email for a in accounts):
                raise ValueError("email already exists")
            acct = {"account_id": uuid.uuid4().hex, "email": email, "display_name": display_name,
                    "company_id": company_id, "roles": list(roles),
                    "password_hash": password_hash, "disabled": disabled}
            self._write(accounts + [acct])
        return acct

    def set_password(self, email: str, password: str) -> None:
        """Replace an account's password (hashed as create does). Unknown email: ValueError."""
        email = normalise_email(email)
        if not password:
            raise ValueError("a password is required")
        password_hash = hash_password(password)  # slow: outside the lock
        with self._lock:
            accounts = self._read()
            acct = next((a for a in accounts if a["email"] == email), None)
            if acct is None:
                raise ValueError("unknown account")
            acct["password_hash"] = password_hash
            self._write(accounts)

    def set_display_name(self, email: str, display_name: str) -> None:
        """Rename an account (the seed keeps illustrative names current). Unknown email: ValueError."""
        email, display_name = normalise_email(email), display_name.strip()
        if not display_name:
            raise ValueError("a display name is required")
        with self._lock:
            accounts = self._read()
            acct = next((a for a in accounts if a["email"] == email), None)
            if acct is None:
                raise ValueError("unknown account")
            acct["display_name"] = display_name
            self._write(accounts)

    def add_roles(self, email: str, roles: list[str]) -> None:
        """Add known company roles to an existing account (the seed backfills head_of_data). Unknown email or role: ValueError."""
        email = normalise_email(email)
        if set(roles) - self._roles or SUPER_ADMIN in roles:
            raise ValueError("unknown roles")
        with self._lock:
            accounts = self._read()
            acct = next((a for a in accounts if a["email"] == email), None)
            if acct is None:
                raise ValueError("unknown account")
            acct["roles"] = list(dict.fromkeys([*acct["roles"], *roles]))
            self._write(accounts)

    def set_roles(self, email: str, roles: list[str]) -> None:
        """Replace a company account's roles (the seed moves a person to the right seat). Unknown email or role: ValueError."""
        email = normalise_email(email)
        if not roles or set(roles) - self._roles or SUPER_ADMIN in roles:
            raise ValueError("unknown or empty roles")
        with self._lock:
            accounts = self._read()
            acct = next((a for a in accounts if a["email"] == email), None)
            if acct is None:
                raise ValueError("unknown account")
            acct["roles"] = list(dict.fromkeys(roles))
            self._write(accounts)

    def get_by_email(self, email: str) -> dict | None:
        email = normalise_email(email)
        return next((a for a in self._read() if a["email"] == email), None)

    def get(self, account_id: str) -> dict | None:
        return next((a for a in self._read() if a["account_id"] == account_id), None)

    def in_company(self, company_id: str) -> list[dict]:
        """The company's accounts as {account_id, display_name, roles, disabled}; never the email or password hash."""
        return [{"account_id": a["account_id"], "display_name": a["display_name"], "roles": list(a["roles"]),
                 "disabled": a["disabled"]} for a in self._read() if a.get("company_id") == company_id]

    def verify(self, email: str, password: str) -> dict | None:
        """Account if the password is right and it is enabled, else None. Same work either way."""
        acct = self.get_by_email(email)
        ok = check_password(password, acct["password_hash"] if acct else _DUMMY_HASH)
        return acct if acct and ok and not acct["disabled"] else None
