"""GoCardless Bank Account Data: the accounts of one linked requisition, their balances and booked transactions -> one camt.053 file.
The person links a bank once (the sandbox bank, SANDBOXFINANCE_SFIN0000) and sets GOCARDLESS_REQUISITION_ID; see docs/v3/FEEDS-SETUP.md."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from . import _http
from .base import Fetched, register

HOST = _http.HOSTS["gocardless"]


@dataclass(frozen=True)
class GoCardless:
    id: str = "gocardless"
    label: str = "GoCardless Bank Account Data (open banking, EU and UK)"
    kind: str = "api"
    env: tuple[str, ...] = ("GOCARDLESS_SECRET_ID", "GOCARDLESS_SECRET_KEY", "GOCARDLESS_REQUISITION_ID")
    call: object = None

    def with_plane(self, plane) -> "GoCardless":
        return replace(self, call=_http.gateway_call(plane))

    def fetch(self, since: date) -> list[Fetched]:
        base = f"https://{HOST}/api/v2"
        tok = self.call("POST", f"{base}/token/new/", None, {"secret_id": _http.env("GOCARDLESS_SECRET_ID"), "secret_key": _http.env("GOCARDLESS_SECRET_KEY")})["access"]
        h = {"Authorization": f"Bearer {tok}"}

        def get(path):
            return self.call("GET", f"{base}{path}", h)
        stmts = []
        for acc in get(f"/requisitions/{_http.env('GOCARDLESS_REQUISITION_ID')}/")["accounts"]:
            info = get(f"/accounts/{acc}/").get("account", {})
            bals = get(f"/accounts/{acc}/balances/").get("balances", [])
            book = get(f"/accounts/{acc}/transactions/?date_from={since.isoformat()}")["transactions"]["booked"]
            pick = next((b for b in bals if b.get("balanceType") == "closingBooked"), bals[0] if bals else None)
            ccy = (pick or {}).get("balanceAmount", {}).get("currency") or info.get("currency") or "EUR"
            ents = [dict(amount=Decimal(t["transactionAmount"]["amount"]), date=t.get("bookingDate") or t["valueDate"],
                         ref=t.get("transactionId") or t.get("internalTransactionId", ""), text=t.get("remittanceInformationUnstructured", "")) for t in book]
            stmts.append(dict(id=acc, account=info.get("iban") or acc, ccy=ccy, balance=Decimal(pick["balanceAmount"]["amount"]) if pick else None, entries=ents))
        return [Fetched(f"camt053_gocardless_{date.today():%Y-%m-%d}.xml", _http.camt053(stmts, "gocardless"), "GoCardless Bank Account Data, sandbox bank")]


GOCARDLESS = register(GoCardless())
