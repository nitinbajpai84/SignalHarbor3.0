import json

import pytest

from egress_helpers import log_lines
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import send_email
from sh_platform.egress.vault import NameVault


@pytest.fixture(autouse=True)
def outbox_mode(monkeypatch):
    monkeypatch.delenv("SH_SMTP_URL", raising=False)


def _allow(plane, domains=("acme.test",)):
    p = plane.area("context") / "egress_policy.json"
    p.write_text(json.dumps({"email_domains": list(domains)}), encoding="utf-8")


def test_outbox_fallback_writes_file_and_logs_seven_fields(plane):
    _allow(plane)
    assert send_email(plane, ["a@acme.test"], "Weekly note", "All quiet.") == "kept in the outbox"
    files = list((plane.root / "outbox").glob("*-*.eml"))
    assert len(files) == 1 and "All quiet." in files[0].read_text()
    (line,) = log_lines(plane)
    assert {"time", "module", "kind", "host", "decision", "reason_code", "bytes", "sha256"} <= set(line)
    assert line["decision"] == "kept in the outbox" and "All quiet" not in json.dumps(line)


def test_non_allowlisted_domain_refused(plane):
    _allow(plane)
    with pytest.raises(EgressBlocked) as e:
        send_email(plane, ["a@elsewhere.test"], "Hi", "Hello")
    assert e.value.reason_code == "destination_not_allowed"
    assert not (plane.root / "outbox").exists() and log_lines(plane)[0]["decision"] == "blocked"


def test_vault_name_in_body_refused(plane, monkeypatch):
    _allow(plane)
    NameVault(plane).register("person", "Zelda Quimby")
    monkeypatch.setattr(NameVault, "tokenise", lambda self, t: t)  # a tokeniser miss: the final check must still hold
    with pytest.raises(EgressBlocked) as e:
        send_email(plane, ["a@acme.test"], "Hi", "Please call Zelda Quimby.")
    assert e.value.reason_code == "vault_name" and not (plane.root / "outbox").exists()


def test_names_tokenised_in_what_is_sent(plane):
    _allow(plane)
    NameVault(plane).register("person", "Zelda Quimby")
    send_email(plane, ["a@acme.test"], "Note for Zelda Quimby", "Zelda Quimby asked for the plan.")
    text = next((plane.root / "outbox").glob("*.eml")).read_text()
    assert "Zelda" not in text and "PERSON_" in text
