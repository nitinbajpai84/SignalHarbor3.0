"""Saxo OpenAPI simulation: positions and trades -> the custodian positions CSV and the custodian transactions CSV the pack reads.
SAXO_TOKEN is the 24-hour simulation token from the developer portal. The portfolio column carries the Saxo account id; the mapping sheet maps it.
Field names follow Saxo's reference (port/v1/positions, cs/v1/audit/orderactivities); check the trade fields on the first live run."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace
from datetime import date

from . import _http
from .base import Fetched, register

HOST = _http.HOSTS["saxo"]
BASE = f"https://{HOST}/sim/openapi"
POS_COLS = "as_of,portfolio,custodian,security_id,ticker,security_name,asset_class,quantity,price,market_value,currency".split(",")
TXN_COLS = "txn_date,settle_date,type,security_id,quantity,price,amount,currency,reference".split(",")
CLASS = {"Stock": "listed_equity", "Bond": "bond", "CfdOnStock": "listed_equity", "FxSpot": "fx", "ContractFutures": "future"}


def _csv(cols, rows) -> bytes:
    s = io.StringIO()
    w = csv.DictWriter(s, cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return s.getvalue().encode()


@dataclass(frozen=True)
class Saxo:
    id: str = "saxo"
    label: str = "Saxo OpenAPI (simulation)"
    kind: str = "api"
    env: tuple[str, ...] = ("SAXO_TOKEN",)
    call: object = None

    def with_plane(self, plane) -> "Saxo":
        return replace(self, call=_http.gateway_call(plane))

    def fetch(self, since: date) -> list[Fetched]:
        h = {"Authorization": f"Bearer {_http.env('SAXO_TOKEN')}"}

        def get(path):
            return self.call("GET", BASE + path, h)
        today = date.today().isoformat()
        pos = []
        for p in get("/port/v1/positions/me?FieldGroups=PositionBase,PositionView,DisplayAndFormat")["Data"]:
            b, v, d = p["PositionBase"], p.get("PositionView", {}), p.get("DisplayAndFormat", {})
            pos.append(dict(as_of=today, portfolio=b["AccountId"], custodian="Saxo (simulation)", security_id=f"SAXO-{b['Uic']}", ticker=d.get("Symbol", ""),
                            security_name=d.get("Description", ""), asset_class=CLASS.get(b.get("AssetType"), ""), quantity=b["Amount"], price=v.get("CurrentPrice", ""),
                            market_value=v.get("MarketValue", ""), currency=d.get("Currency", "")))
        trades = []
        for t in get(f"/cs/v1/audit/orderactivities?Status=FinalFill&FromDateTime={since.isoformat()}T00:00:00Z")["Data"]:
            day = t["ActivityTime"][:10]
            qty, px = t["FilledAmount"], t["AveragePrice"]
            trades.append(dict(txn_date=day, settle_date=day, type=t["BuySell"].lower(), security_id=f"SAXO-{t['Uic']}", quantity=qty, price=px,
                               amount=round(float(qty) * float(px), 2), currency=t.get("Currency", ""), reference=f"SAXO-{t['OrderId']}"))
        src = "Saxo OpenAPI simulation"
        return [Fetched(f"positions_{today.replace('-', '')}_saxo.csv", _csv(POS_COLS, pos), src),
                Fetched(f"transactions_saxo_{today[:7]}.csv", _csv(TXN_COLS, trades), src)]


SAXO = register(Saxo())
