"""Plaid sandbox: accounts, balances and transactions -> one camt.053 file. The sandbox needs no bank login: we ask it for a test Item and read that."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from . import _http
from .base import Fetched, register

HOST = _http.HOSTS["plaid"]
INSTITUTION = "ins_109508"  # Plaid's sandbox test bank


@dataclass(frozen=True)
class Plaid:
    id: str = "plaid"
    label: str = "Plaid (sandbox)"
    kind: str = "api"
    env: tuple[str, ...] = ("PLAID_CLIENT_ID", "PLAID_SECRET")
    call: object = None

    def with_plane(self, plane) -> "Plaid":
        return replace(self, call=_http.gateway_call(plane))

    def fetch(self, since: date) -> list[Fetched]:
        h = {"PLAID-CLIENT-ID": _http.env("PLAID_CLIENT_ID"), "PLAID-SECRET": _http.env("PLAID_SECRET")}

        def post(path, body):
            return self.call("POST", f"https://{HOST}{path}", h, body)
        pub = post("/sandbox/public_token/create", {"institution_id": INSTITUTION, "initial_products": ["transactions"]})["public_token"]
        token = post("/item/public_token/exchange", {"public_token": pub})["access_token"]
        accounts, added, cursor = [], [], None
        while True:  # ponytail: a fresh sandbox Item may still be preparing its data (empty first page); a real feed would poll transactions_update_status
            r = post("/transactions/sync", {"access_token": token, **({"cursor": cursor} if cursor else {})})
            accounts, added, cursor = r.get("accounts") or accounts, added + r.get("added", []), r.get("next_cursor")
            if not r.get("has_more"):
                break
        stmts = []
        for a in accounts:
            b = a["balances"]
            # Plaid: a positive amount is money OUT of the account; camt: credit is money in
            ents = [dict(amount=-Decimal(str(t["amount"])), date=t["date"], ref=t["transaction_id"], text=t.get("name", ""))
                    for t in added if t["account_id"] == a["account_id"] and date.fromisoformat(t["date"]) >= since]
            stmts.append(dict(id=a["account_id"], account=f"{a.get('name', '')} {a.get('mask', '')}".strip() or a["account_id"],
                              ccy=b.get("iso_currency_code") or "USD", balance=b.get("current"), entries=ents))
        return [Fetched(f"camt053_plaid_{date.today():%Y-%m-%d}.xml", _http.camt053(stmts, "plaid-sandbox"), "Plaid sandbox, test Item")]


PLAID = register(Plaid())
