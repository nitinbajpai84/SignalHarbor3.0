"""G-feeds-api: the four sandbox API connectors, served by recorded SYNTHETIC JSON through a fake call. No network."""
import json
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from sh_platform.egress.errors import EgressBlocked
from sh_platform.plane import CompanyPlane
from sh_platform.v1.connectors import _http, base
from sh_platform.v1.connectors.banksg import BankSG
from sh_platform.v1.connectors.gocardless import GoCardless
from sh_platform.v1.connectors.plaid import Plaid
from sh_platform.v1.connectors.saxo import Saxo
from sh_platform.v1.v3_pack_readers import kind_of

FIX = Path(__file__).parent / "fixtures" / "feeds_api"
NS = {"c": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"}
ENVS = {"plaid": ({"PLAID_CLIENT_ID": "id", "PLAID_SECRET": "s"}, Plaid), "saxo": ({"SAXO_TOKEN": "t"}, Saxo),
        "gocardless": ({"GOCARDLESS_SECRET_ID": "i", "GOCARDLESS_SECRET_KEY": "k", "GOCARDLESS_REQUISITION_ID": "REQ1"}, GoCardless),
        "banksg": ({"BANKSG_HOST": "sandbox.bank.example", "BANKSG_CLIENT_ID": "i", "BANKSG_CLIENT_SECRET": "k"}, BankSG)}
SINCE = date(2026, 10, 1)


def fake(name):
    """Serves the recorded JSON: the longest recorded path that the URL path starts with."""
    table = json.loads((FIX / f"{name}.json").read_text())

    def call(method, url, headers=None, body=None):
        path = "/" + url.split("//", 1)[1].split("/", 1)[1].split("?")[0]
        for pre in ("/api/v2", "/sim/openapi"):
            if path.startswith(pre):
                path = path[len(pre):]
        hit = max((k for k in table if path.rstrip("/") == k.rstrip("/")), key=len, default=None)
        assert hit, f"unrecorded call {method} {url}"
        return table[hit]
    return call


def make(name, monkeypatch):
    envs, cls = ENVS[name]
    for k, v in envs.items():
        monkeypatch.setenv(k, v)
    return cls(call=fake(name))


@pytest.fixture()
def plane(tmp_path):
    return CompanyPlane("feeds-office", tmp_path)


@pytest.mark.parametrize("name", ENVS)
def test_missing_keys_name_the_variables_only(name, plane, monkeypatch):
    envs, cls = ENVS[name]
    for k in envs:
        monkeypatch.delenv(k, raising=False)
    first = list(envs)[-1] if len(envs) > 1 else None
    if first:
        monkeypatch.setenv(first, "SECRET-VALUE-XYZ")
    st = base.run(plane, cls(call=fake(name)), SINCE)
    assert not st.ok and st.files == 0
    assert "SECRET-VALUE-XYZ" not in repr(st) and set(st.missing) == set(envs) - {first}


def test_plaid_camt053(plane, monkeypatch):
    st = base.run(plane, make("plaid", monkeypatch), SINCE)
    assert st.ok and st.files == 1
    f = next(plane.path("dropbox").glob("camt053_plaid_*.xml"))
    s = ET.parse(f).getroot().find(".//c:Stmt", NS)
    ents = s.findall("c:Ntry", NS)
    assert len(ents) == 2  # the January line is before `since`
    signs = {e.find("c:AcctSvcrRef", NS).text: e.find("c:CdtDbtInd", NS).text for e in ents}
    assert signs == {"T1": "DBIT", "T2": "CRDT"}  # Plaid: positive = money out
    assert Decimal(s.find("c:Bal/c:Amt", NS).text) == Decimal("110.5")


def test_gocardless_camt053_uses_closing_booked(monkeypatch):
    (f,) = make("gocardless", monkeypatch).fetch(SINCE)
    s = ET.fromstring(f.data).find(".//c:Stmt", NS)
    assert s.find("c:Acct/c:Id/c:Othr/c:Id", NS).text == "GL00SYNTHETIC0001"
    assert s.find("c:Bal/c:Amt", NS).text == "1913.00"
    assert [e.find("c:Amt", NS).text for e in s.findall("c:Ntry", NS)] == ["45.00", "1500.00"]
    assert "Rent &amp; Co" in f.data.decode()  # escaped, still well-formed


def test_banksg_camt053(monkeypatch):
    (f,) = make("banksg", monkeypatch).fetch(SINCE)
    s = ET.fromstring(f.data).find(".//c:Stmt", NS)
    assert s.find("c:Acct/c:Ccy", NS).text == "SGD"
    assert [e.find("c:CdtDbtInd", NS).text for e in s.findall("c:Ntry", NS)] == ["CRDT", "DBIT"]


def test_saxo_files_are_read_by_the_pack(plane, monkeypatch):
    st = base.run(plane, make("saxo", monkeypatch), SINCE)
    assert st.ok and st.files == 2
    files = {p.name: p for p in plane.path("dropbox").iterdir()}
    kinds = {kind_of(n, p.read_bytes())[0] for n, p in files.items()}
    assert kinds == {"custodian_positions", "custodian_transactions"}
    pos = next(p for n, p in files.items() if n.startswith("positions_")).read_text()
    assert "SAXO-211" in pos and "19050.0" in pos
    txn = next(p for n, p in files.items() if n.startswith("transactions_")).read_text()
    assert "buy,SAXO-211,40,188.25,7530.0,USD,SAXO-9001" in txn


def test_the_real_call_is_blocked_until_the_company_switches_feeds_on(plane, monkeypatch):
    monkeypatch.setenv("SAXO_TOKEN", "SECRET-VALUE-XYZ")
    call = _http.gateway_call(plane)
    hdr = {"Authorization": "Bearer SECRET-VALUE-XYZ"}
    with pytest.raises(EgressBlocked):
        call("GET", "https://gateway.saxobank.com/sim/openapi/port/v1/positions/me", hdr)
    _http.enable(plane, "sandbox.plaid.com")  # on, but this host is not listed
    with pytest.raises(EgressBlocked) as e:
        call("GET", "https://gateway.saxobank.com/x", hdr)
    assert e.value.reason_code == "destination_not_allowed"
    log = (plane.area("context") / "egress_log.jsonl").read_text()
    assert "SECRET-VALUE-XYZ" not in log and log.count("blocked") == 2
