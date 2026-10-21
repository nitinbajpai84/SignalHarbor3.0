"""A Singapore bank developer sandbox, DBS-style: OAuth2 client credentials, then accounts and their transactions -> one camt.053 file.
The bank's sandbox host is set in BANKSG_HOST (a bare host name, also added to the company's egress allow-list). Paths follow the common
Singapore open-API shape (/v1/accounts, /v1/accounts/{id}/transactions); confirm them against the bank's portal when the account is created."""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from . import _http
from .base import Fetched, register


@dataclass(frozen=True)
class BankSG:
    id: str = "banksg"
    label: str = "Singapore bank developer sandbox"
    kind: str = "api"
    env: tuple[str, ...] = ("BANKSG_HOST", "BANKSG_CLIENT_ID", "BANKSG_CLIENT_SECRET")
    call: object = None

    def with_plane(self, plane) -> "BankSG":
        return replace(self, call=_http.gateway_call(plane))

    def fetch(self, since: date) -> list[Fetched]:
        base = f"https://{_http.env('BANKSG_HOST')}"
        basic = base64.b64encode(f"{_http.env('BANKSG_CLIENT_ID')}:{_http.env('BANKSG_CLIENT_SECRET')}".encode()).decode()
        tok = self.call("POST", f"{base}/oauth/token", {"Authorization": f"Basic {basic}"}, {"grant_type": "client_credentials"})["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        stmts = []
        for a in self.call("GET", f"{base}/v1/accounts", h)["accounts"]:
            tx = self.call("GET", f"{base}/v1/accounts/{a['accountId']}/transactions?fromDate={since.isoformat()}", h)["transactions"]
            ents = [dict(amount=Decimal(str(t["amount"])) * (1 if t.get("creditDebit", "CR") == "CR" else -1), date=t["valueDate"], ref=t["reference"],
                         text=t.get("description", "")) for t in tx]
            stmts.append(dict(id=a["accountId"], account=a.get("accountNumber") or a["accountId"], ccy=a.get("currency", "SGD"), balance=a.get("ledgerBalance"), entries=ents))
        return [Fetched(f"camt053_banksg_{date.today():%Y-%m-%d}.xml", _http.camt053(stmts, "banksg-sandbox"), "Singapore bank developer sandbox")]


BANKSG = register(BankSG())
