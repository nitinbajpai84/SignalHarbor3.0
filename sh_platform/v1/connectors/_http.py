"""Shared plumbing of the API connectors: every call goes through the egress gateway (switch, host allow-list, log line with host and hash, never content),
secrets stay in headers read from the environment at call time, and a fake `call` can replace all of it in tests."""
from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape, quoteattr

from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import MAX_RESPONSE_BYTES, EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault

MODULE = "feeds"  # the egress switch a company turns on for feed connectors
HOSTS = {"plaid": "sandbox.plaid.com", "saxo": "gateway.saxobank.com", "gocardless": "bankaccountdata.gocardless.com"}  # banksg: the host comes from BANKSG_HOST


def enable(plane, *hosts: str) -> None:
    """Turn the feeds switch on for this company and add the hosts to its allow-list (what the Connections page does when a person connects a feed)."""
    pol = EgressPolicy(plane)
    pol.set_internet(MODULE, True)
    pol.set_internet_hosts(set(pol.internet_hosts()) | set(hosts))


def env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _off():
    raise EgressBlocked("internet_off")


def gateway_call(plane):
    """call(method, url, headers=None, body=None) -> dict, through the gateway. Redirects are never followed; a reply over the gateway's size cap is refused."""
    import httpx
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[], transport=None)

    def call(method: str, url: str, headers: dict | None = None, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else b""

        def transport(u: str, _b: bytes) -> str:
            h = {"content-type": "application/json", "accept": "application/json", **(headers or {})}
            with httpx.Client(timeout=60, follow_redirects=False) as c:
                r = c.request(method, u, content=data or None, headers=h)
                r.raise_for_status()
                if len(r.content) > MAX_RESPONSE_BYTES:
                    raise EgressBlocked("transport_failed")
                return r.text
        raw = gw._run(MODULE, "api", url, gw.policy.internet_hosts(), transport,
                      lambda: None if gw.policy.is_internet_allowed(MODULE) else _off(), lambda box: box.update(body=data))
        return json.loads(raw)
    return call


def camt053(statements: list[dict], source: str) -> bytes:
    """ISO 20022 camt.053 (BkToCstmrStmt). statements: {id, account, ccy, balance, entries: [{amount (signed Decimal), date, ref, text}]}."""
    today = date.today().isoformat()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt>',
           f"<GrpHdr><MsgId>{escape(source)}</MsgId><CreDtTm>{today}T00:00:00</CreDtTm></GrpHdr>"]
    for s in statements:
        ccy = s["ccy"]
        out.append(f"<Stmt><Id>{escape(s['id'])}</Id><Acct><Id><Othr><Id>{escape(s['account'])}</Id></Othr></Id><Ccy>{ccy}</Ccy></Acct>")
        if s.get("balance") is not None:
            b = Decimal(str(s["balance"]))
            out.append(f"<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy={quoteattr(ccy)}>{abs(b)}</Amt>"
                       f"<CdtDbtInd>{'CRDT' if b >= 0 else 'DBIT'}</CdtDbtInd><Dt><Dt>{today}</Dt></Dt></Bal>")
        for e in s["entries"]:
            a = Decimal(str(e["amount"]))
            out.append(f"<Ntry><Amt Ccy={quoteattr(ccy)}>{abs(a)}</Amt><CdtDbtInd>{'CRDT' if a >= 0 else 'DBIT'}</CdtDbtInd><Sts>BOOK</Sts>"
                       f"<BookgDt><Dt>{e['date']}</Dt></BookgDt><ValDt><Dt>{e['date']}</Dt></ValDt><AcctSvcrRef>{escape(str(e['ref']))}</AcctSvcrRef>"
                       f"<AddtlNtryInf>{escape(e['text'])}</AddtlNtryInf></Ntry>")
        out.append("</Stmt>")
    out.append("</BkToCstmrStmt></Document>")
    return "".join(out).encode("utf-8")
