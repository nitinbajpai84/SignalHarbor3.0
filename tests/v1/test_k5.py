"""K3 Manager inbox and manager research: expected / received / late / revised per fund from the signed due rule, a follow-up draft that is
never sent, access filtering by portfolio, the manager profile, notes and questions, and "what changed since the last meeting" from dated
records only (with the document passages as sources). Never a verdict on a manager."""
import sys
import types
import uuid
from datetime import datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e2_intake as E
from sh_platform.v1 import e3_rules as R
from sh_platform.v1 import k5_managers as K
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused

U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_DNS, "k5-" + n))  # noqa: E731
GROWTH, CREDIT, INCOME, VENTURE = (U(n) for n in ("growth", "credit", "income", "venture"))
PF1, PF2 = U("pf1"), U("pf2")
NAMES = {"alder growth fund i": GROWTH, "alder credit fund ii": CREDIT, "alder income fund iii": INCOME, "birch venture fund iv": VENTURE}
ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}), False, "acc-mei")
RAJ = Viewer("Raj Iyer", frozenset({"analyst"}), False, "acc-raj")
PAT = Viewer("Pat Lim", frozenset({"analyst"}), False, "acc-pat")      # sees portfolio 2 only
NOBODY = Viewer("Sam Roe", frozenset({"analyst"}), False, "acc-sam")   # no grant at all
AS_OF = "2026-10-20"   # September month end is 30 Sep; 10 business days after it is 14 Oct


def at(day: int, month: int = 10) -> datetime:
    return datetime(2026, month, day, 9, tzinfo=timezone.utc)


def stmt(fund: str, status: str, nav: str, vdate: str = "30 September 2026") -> bytes:
    return f"{fund}\nManager statement\nValuation date: {vdate}\nNet asset value {nav} USD\nStatus: {status}\n".encode()


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    org, now = org_id(p), datetime(2026, 1, 1, tzinfo=timezone.utc)
    with wh.connect(p) as con:
        con.execute("insert into organizations values (?,?,?)", [org, "Acme", now])
        for iid, name, mgr in [(GROWTH, "Alder Growth Fund I", "Alder Capital"), (CREDIT, "Alder Credit Fund II", "Alder Capital"),
                               (INCOME, "Alder Income Fund III", "Alder Capital"), (VENTURE, "Birch Venture Fund IV", "Birch Partners")]:
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, manager_name, currency, created_at)"
                        " values (?,?,?,?,?,?,?)", [iid, org, name, "fund", mgr, "USD", now])
        for pid, code in [(PF1, "P1"), (PF2, "P2")]:
            con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency)"
                        " values (?,?,?,?,?,?)", [pid, org, U("le"), code, code, "USD"])
        rows = [(GROWTH, PF1, 10_000_000, "manager_estimate", "draft"), (CREDIT, PF1, 5_000_000, "official", "approved"),
                (INCOME, PF1, 2_000_000, "manager_estimate", "draft"), (VENTURE, PF2, 7_000_000, "official", "approved")]
        for i, (iid, pf, amt, kind, appr) in enumerate(rows):
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                        " value_amount, currency, valuation_type, approval_status) values (?,?,?,?,?,?,?,?,?,?,?)",
                        [U(f"v{i}"), org, iid, pf, "2026-08-31", now, now, amt, "USD", kind, appr])
        u = U("pat")
        con.execute("insert into users values (?,?,?,?,?,?,?,?)", [u, org, "acc-pat", "Pat Lim", "", None, True, now])
        con.execute("insert into access_groups values (?,?,?,?)", [U("g"), org, "P2 readers", ""])
        con.execute("insert into access_group_memberships values (?,?,?,?,?,?,?)", [U("m"), org, U("g"), u, now, None, None])
        con.execute("insert into access_group_scopes values (?,?,?,?,?,?)", [U("s"), org, U("g"), "portfolio", PF2, "read"])

    def resolve(plane, name, source_id):
        hit = NAMES.get(name.lower().strip())
        return {"instrument_id": hit, "status": "approved" if hit else "unknown", "candidates": []}
    fake = types.ModuleType("sh_platform.v1.e2_match")
    fake.resolve = resolve
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e2_match", fake)
    monkeypatch.setattr("sh_platform.v1.e2_match", fake, raising=False)
    monkeypatch.setattr("sh_platform.v1.doc_index._slow", lambda path: False)
    # the signed rule: statements are due 10 business days after month end (Mei proposes, Raj signs)
    v = R.propose(p, ADMIN, "statement_due", "Statements are due 10 business days after month end.", {"business_days_after_month_end": 10}, "2026-01-01", "deadline")
    R.approve(p, RAJ, v["rule_version_id"])
    with wh.connect(p) as con:   # Raj reads portfolio 1 (the Alder funds)
        raj = con.execute("select id from users where external_identity_id = 'acc-raj'").fetchone()[0]
        con.execute("insert into access_groups values (?,?,?,?)", [U("g1"), org, "P1 readers", ""])
        con.execute("insert into access_group_memberships values (?,?,?,?,?,?,?)", [U("m1"), org, U("g1"), raj, now, None, None])
        con.execute("insert into access_group_scopes values (?,?,?,?,?,?)", [U("s1"), org, U("g1"), "portfolio", PF1, "read"])
    return p


def reg(plane, name, data, day, month=10):
    return E.register(plane, None, None, received_at=at(day, month), data=data, filename=name)


def fund(inbox, name):
    return next(f for m in inbox["managers"] for f in m["funds"] if f["fund_name"] == name)


def story(plane):
    """Growth: received on time, then amended. Credit: nothing yet (late). Income: received two days late."""
    reg(plane, "growth.txt", stmt("Alder Growth Fund I", "Estimate", "10,000,000.00"), 9)
    reg(plane, "growth_amended.txt", stmt("Alder Growth Fund I", "Final amended", "10,180,000.00"), 12)
    reg(plane, "income.txt", stmt("Alder Income Fund III", "Final", "2,050,000.00"), 16)


def test_inbox_expected_received_late_revised(plane):
    story(plane)
    inbox = K.inbox(plane, ADMIN, AS_OF)
    assert inbox["due_rule_signed"] and [m["name"] for m in inbox["managers"]] == ["Alder Capital", "Birch Partners"]
    g, c, i = (fund(inbox, n) for n in ("Alder Growth Fund I", "Alder Credit Fund II", "Alder Income Fund III"))
    assert (g["state"], g["revised_count"], g["days_late"], g["due"]) == ("received", 1, 0, "2026-10-14")
    assert (c["state"], c["days_late"], c["received_on"]) == ("late", 4, None)
    assert (i["state"], i["days_late"], i["state_word"]) == ("received_late", 2, "Received late")
    assert fund(inbox, "Birch Venture Fund IV")["state"] == "late"
    assert inbox["managers"][0]["counts"] == {"expected": 3, "received": 2, "missing_earlier": 1, "late": 2, "revised": 1}
    assert c["last_value"].pop("recorded_at")      # a timestamp in the machine's zone
    assert c["last_value"] == {"amount": "5000000", "currency": "USD", "valuation_date": "2026-08-31", "status": "official", "status_word": "Official", "valuation_id": U("v1")}
    assert g["last_value"]["status"] == "estimated" and g["period_end"] == "2026-09-30"


def test_not_due_yet_and_no_signed_rule(plane):
    assert fund(K.inbox(plane, ADMIN, "2026-10-12"), "Alder Credit Fund II")["state"] == "not_due"      # 12 Oct is before the 14th
    with wh.connect(plane) as con:
        con.execute("delete from rule_versions")
    inbox = K.inbox(plane, ADMIN, AS_OF)
    assert not inbox["due_rule_signed"] and "No signed rule" in inbox["rule_note"]
    assert fund(inbox, "Alder Credit Fund II")["state"] == "no_rule"    # never called late without a rule


def test_quarterly_fund_is_not_expected_in_a_month_between(plane):
    reg(plane, "q_jun.txt", stmt("Birch Venture Fund IV", "Final", "7,000,000.00", "30 June 2026"), 15, 7)
    reg(plane, "q_mar.txt", stmt("Birch Venture Fund IV", "Final", "6,900,000.00", "31 March 2026"), 15, 4)
    f = fund(K.inbox(plane, ADMIN, "2026-08-20"), "Birch Venture Fund IV")     # period end 31 July, a quarterly fund
    assert (f["cadence"], f["state"], f["state_word"]) == ("quarterly", "not_expected", "Not expected this month")
    assert fund(K.inbox(plane, ADMIN, AS_OF), "Birch Venture Fund IV")["state"] == "late"   # 30 September is a quarter end


def test_access_follows_portfolio_grants(plane):
    assert [m["name"] for m in K.inbox(plane, PAT, AS_OF)["managers"]] == ["Birch Partners"]
    assert K.inbox(plane, NOBODY, AS_OF)["managers"] == []
    with pytest.raises(Refused) as e:
        K.profile(plane, PAT, "alder-capital")
    assert e.value.status == 404
    with pytest.raises(Refused):
        K.add_note(plane, NOBODY, "alder-capital", "hello")
    with pytest.raises(Refused):
        K.draft_followup(plane, PAT, "alder-capital", as_of=AS_OF)


def test_followup_is_a_draft_and_never_sent(plane):
    story(plane)
    d = K.draft_followup(plane, ADMIN, "alder-capital", as_of=AS_OF)
    assert d["sent"] is False and "not been sent" in d["note"]
    assert "Alder Credit Fund II: due 14 Oct 2026, 4 business days overdue" in d["body"] and "Growth" not in d["body"] and "Income" not in d["body"]
    assert d["subject"] == "Statement request: 30 Sep 2026 (Alder Credit Fund II)" and d["body"].endswith("Mei Tan")
    assert K.draft_followup(plane, ADMIN, "alder-capital", fund_id=GROWTH, as_of=AS_OF)["draft"] is None     # nothing to chase for that fund
    with pytest.raises(Refused) as e:
        K.draft_followup(plane, ADMIN, "alder-capital", fund_id=VENTURE, as_of=AS_OF)
    assert e.value.status == 404
    assert any("drafted (not sent)" in n["text"] for n in K.notes(plane, "alder-capital"))   # the draft is logged, quietly
    assert not any(n["system"] for n in K.profile(plane, ADMIN, "alder-capital")["notes"])   # and kept out of the person's notes


def test_profile_timeline_notes_questions_and_documents(plane):
    story(plane)
    n = K.add_note(plane, ADMIN, "alder-capital", "Met the team; new head of credit.", "meeting", "2026-09-15")
    q = K.add_note(plane, RAJ, "alder-capital", "Why was the Growth NAV amended?", "question", "2026-10-13")
    with pytest.raises(Refused):
        K.add_note(plane, RAJ, "alder-capital", "", "note")
    with pytest.raises(Refused):
        K.add_note(plane, RAJ, "alder-capital", "x", "verdict")
    K.add_note(plane, RAJ, "alder-capital", "Fee terms in the side letter.", "note", "2026-10-01")
    p = K.profile(plane, ADMIN, "alder-capital", AS_OF)
    assert [f["fund_name"] for f in p["funds"]] == ["Alder Credit Fund II", "Alder Growth Fund I", "Alder Income Fund III"]
    rev = [t for t in p["timeline"] if t["fund_name"] == "Alder Growth Fund I"]
    assert [(t["status"], t["current"]) for t in rev] == [("final", True), ("estimate", False)] and rev[0]["replaces"] == rev[1]["document_id"]
    assert p["last_meeting"] == "2026-09-15" and [x["id"] for x in p["questions"]] == [q["id"]] and len(p["notes"]) == 2
    assert p["commitments"]["available"] and p["commitments"]["rows"] == []
    done = K.resolve_question(plane, RAJ, "alder-capital", q["id"])
    assert done["state"] == "answered" and done["answered_by"] == "Raj Iyer" and done["answered_at"]
    assert n["kind"] == "meeting"
    with pytest.raises(Refused):
        K.resolve_question(plane, RAJ, "alder-capital", n["id"])    # only a question can be answered


def test_what_changed_since_the_last_meeting_from_dated_records(plane):
    story(plane)
    assert "No meeting is recorded" in K.changes(plane, ADMIN, "alder-capital")["answer"]
    K.add_note(plane, ADMIN, "alder-capital", "Quarterly catch-up.", "meeting", "2026-10-10")
    K.add_note(plane, RAJ, "alder-capital", "They will restate Income next month.", "note", "2026-10-14")
    from sh_platform.v1 import c4_library
    c4_library.upload(plane, ADMIN, "Alder Capital newsletter.txt", b"Alder Capital newsletter\nTeam change: our head of credit has left the firm.\n",
                      kind="other", note="Alder Capital newsletter", share=True)
    out = K.changes(plane, ADMIN, "alder-capital")
    assert out["since"] == "2026-10-10" and out["worded_by"] == "rules"
    texts = [i["text"] for i in out["items"]]
    assert any("A statement for Alder Income Fund III dated 30 Sep 2026 arrived" in t for t in texts)
    assert any("A revised statement for Alder Growth Fund I" in t for t in texts)
    assert not any("A statement for Alder Growth Fund I" in t for t in texts)      # the first Growth statement came before the meeting
    assert any(t.startswith("Note by Raj Iyer: They will restate") for t in texts)
    dated = [i for i in out["items"] if i["kind"] != "document"]                   # a document is dated by when it was added (today)
    assert all(i["date"] > "2026-10-10" and i["source"]["label"] for i in dated)
    assert [i["date"] for i in out["items"]] == sorted((i["date"] for i in out["items"]), reverse=True)
    wide = K.changes(plane, ADMIN, "alder-capital", "2020-01-01")                  # a chosen date overrides the last meeting
    assert any(i["kind"] == "document" and "newsletter" in i["text"] for i in wide["items"])
    assert any("head of credit" in c["text"] and c["file"] == "Alder Capital newsletter.txt" and c["date"] for c in wide["passages"])
    with pytest.raises(Refused):
        K.changes(plane, ADMIN, "alder-capital", "last week")


def test_no_verdict_on_a_manager(plane):
    story(plane)
    K.add_note(plane, ADMIN, "alder-capital", "Call.", "meeting", "2026-10-01")
    text = " ".join([str(K.inbox(plane, ADMIN, AS_OF)), str(K.profile(plane, ADMIN, "alder-capital")), str(K.changes(plane, ADMIN, "alder-capital")),
                     K.draft_followup(plane, ADMIN, "alder-capital", as_of=AS_OF)["body"]]).lower()
    for word in ("good manager", "bad manager", "poor manager", "strong manager", "weak manager", "we recommend", "you should redeem", "underperform"):
        assert word not in text
    assert "does not say whether the manager is doing well or badly" in text


def test_routes_are_declared_and_default_deny():
    from pathlib import Path

    import yaml

    from sh_platform.v1 import k5_routes
    declared = set(yaml.safe_load((Path(k5_routes.__file__).parent / "k5.permissions.yaml").read_text())["routes"])
    live = {f"{m} {r.path}" for r in k5_routes.router.routes for m in r.methods}
    assert live == declared


def commit_with_calls(plane):
    """One 5,000,000 USD commitment of the entity behind portfolio 1 to Alder Credit Fund II; returns (commitment id, a source record id)."""
    from sh_platform.v1 import e1_write, k6_liquidity as L
    org = org_id(plane)
    with wh.connect(plane) as con:
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", [U("le"), org, "LE", "Acme Holdings", "USD"])
    cid = L.record_commitment(plane, {"legal_entity_id": U("le"), "instrument_id": CREDIT, "commitment_amount": 5_000_000, "currency": "USD", "committed_on": "2025-01-15"})
    story(plane)
    with wh.connect(plane) as con:
        doc = con.execute("select id, source_system_id, original_uri, content_hash, received_at from documents limit 1").fetchone()
    src = L._notice_source(plane, dict(zip(("id", "source_system_id", "original_uri", "content_hash", "received_at"), doc)))
    return cid, src, e1_write


def call(e1_write, plane, cid, src, amount, status, supersedes=None):
    return e1_write.record(plane, "cash_movements", {"source_record_id": src, "portfolio_id": PF1, "instrument_id": CREDIT, "movement_type": "call",
                           "effective_date": "2026-09-01", "received_at": at(1), "amount": amount, "currency": "USD", "confirmation_status": status,
                           "due_date": "2026-09-10", "notice_kind": "call", "commitment_id": cid}, supersedes_id=supersedes)


def test_commitments_are_plain_money_and_count_only_confirmed_calls(plane):
    cid, src, w = commit_with_calls(plane)
    row = lambda: K.profile(plane, ADMIN, "alder-capital", AS_OF)["commitments"]["rows"][0]  # noqa: E731
    r = row()      # no call yet: no raw decimals such as 5000000.00000000 or 0E-8
    assert (r["commitment"], r["called"], r["uncalled"], r["entity"]) == ("5000000", "0", "5000000", "Acme Holdings")
    call(w, plane, cid, src, 500_000, "noticed")                        # read, not confirmed
    call(w, plane, cid, src, 700_000, "cancelled")                      # cancelled
    first = call(w, plane, cid, src, 1_000_000, "confirmed")
    assert (row()["called"], row()["uncalled"]) == ("1000000", "4000000")
    call(w, plane, cid, src, 1_200_000, "confirmed", supersedes=first)  # a correction replaces the call, it is not added to it
    assert (row()["called"], row()["uncalled"]) == ("1200000", "3800000")
    assert K.profile(plane, PAT, "birch-partners")["commitments"]["rows"] == []     # the entity's portfolio is not Pat's


def test_earlier_missing_statement_is_listed_and_chased(plane):
    story(plane)      # Credit has a value dated 31 Aug and no statement for August, which was due on 14 Sep
    f = fund(K.inbox(plane, ADMIN, AS_OF), "Alder Credit Fund II")
    assert f["earlier_missing"] == [{"period_end": "2026-08-31", "due": "2026-09-14", "days_late": 26}]
    assert fund(K.inbox(plane, ADMIN, AS_OF), "Alder Growth Fund I")["earlier_missing"] == []
    d = K.draft_followup(plane, ADMIN, "alder-capital", fund_id=CREDIT, as_of=AS_OF)
    assert "Alder Credit Fund II (period ending 31 Aug 2026): due 14 Sep 2026, 26 business days overdue" in d["body"]
    assert "Alder Credit Fund II: due 14 Oct 2026, 4 business days overdue" in d["body"]


def test_changes_catches_a_restated_older_value_and_formats_the_amount(plane):
    story(plane)
    K.add_note(plane, ADMIN, "alder-capital", "Catch-up.", "meeting", "2026-10-01")
    with wh.connect(plane) as con:   # the Aug value of Credit was restated and recorded today, after the meeting
        con.execute("update valuation_observations set value_amount = 5100000, recorded_at = ? where id = ?", [at(8), U("v1")])
    texts = [i["text"] for i in K.changes(plane, ADMIN, "alder-capital")["items"] if i["kind"] == "valuation"]
    assert any(t.startswith("Alder Credit Fund II last valued at 5,100,000 USD on 31 Aug 2026") and "recorded 8 Oct 2026" in t for t in texts)


def test_days_late_are_business_days():
    assert K._bdays_after(K._day("2026-07-14"), K._day("2026-10-09")) == 63      # fund D's June statement at 9 Oct
    assert K._bdays_after(K._day("2026-09-14"), K._day("2026-09-22")) == 6       # fund H2's August statement received 22 Sep


def test_followup_names_the_contact_and_the_profile_shows_status_words(plane):
    story(plane)
    assert "Dear Alder Capital team," in K.draft_followup(plane, ADMIN, "alder-capital", as_of=AS_OF)["body"]
    with wh.connect(plane) as con:
        sid = str(uuid.uuid4())
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?,?,?,?,?,?)",
                    [sid, org_id(plane), "contacts", "Manager contacts", "internal", True])
        con.execute("insert into instrument_identifiers (id, organization_id, instrument_id, source_system_id, identifier_type, identifier_value, mapping_status)"
                    " values (?,?,?,?,?,?,?)", [str(uuid.uuid4()), org_id(plane), CREDIT, sid, "manager_contact", "Hana Sato", "approved"])
    d = K.draft_followup(plane, ADMIN, "alder-capital", as_of=AS_OF)
    assert d["contact"] == "Hana Sato" and d["body"].startswith("Dear Hana Sato (Alder Capital),")
    funds = {f["fund_name"]: f for f in K.profile(plane, ADMIN, "alder-capital", AS_OF)["funds"]}
    assert funds["Alder Credit Fund II"]["last_value"]["status_word"] == "Official"     # 31 Aug is 50 days before 20 Oct
    assert funds["Alder Growth Fund I"]["last_value"]["status_word"] == "Estimated"
    old = K.profile(plane, ADMIN, "alder-capital", "2027-01-20")["funds"]
    assert {f["last_value"]["status_word"] for f in old} == {"Stale"}


def test_changes_shows_revised_value_old_to_new_and_late_business_days(plane):
    story(plane)
    K.add_note(plane, ADMIN, "alder-capital", "Catch-up.", "meeting", "2026-10-01")
    with wh.connect(plane) as con:
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                    " value_amount, currency, valuation_type, approval_status, supersedes_valuation_id) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [U("rev"), org_id(plane), CREDIT, PF1, "2026-08-31", at(8), at(8), 5_100_000, "USD", "official", "approved", U("v1")])
    texts = [i["text"] for i in K.changes(plane, ADMIN, "alder-capital")["items"]]
    assert any("Alder Credit Fund II value for 31 Aug 2026 was revised from 5,000,000 to 5,100,000 USD (+100,000), recorded 8 Oct 2026" in t for t in texts)
    assert any("Income Fund III" in t and "arrived (final), 2 business days late" in t for t in texts)


# ---- cycle 1 fixes (TRIAGE-cycle-1 P5) ----

def _val(plane, name, amount, day, appr, sup=None):
    with wh.connect(plane) as con:
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                    " value_amount, currency, valuation_type, approval_status, supersedes_valuation_id) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [U(name), org_id(plane), CREDIT, PF1, "2026-08-31", at(day), at(day), amount, "USD", "official", appr, U(sup) if sup else None])


def test_a3_0_revision_compares_with_the_last_value_of_record_not_a_pending_step(plane):
    """Estimate 5,000,000 -> pending 5,180,000 -> confirmed 5,180,000 is one revision, 5,000,000 to 5,180,000; never X to X."""
    K.add_note(plane, ADMIN, "alder-capital", "Catch-up.", "meeting", "2026-10-01")
    _val(plane, "pend", 5_180_000, 7, "pending", "v1")
    _val(plane, "conf", 5_180_000, 8, "confirmed", "pend")
    texts = [i["text"] for i in K.changes(plane, ADMIN, "alder-capital")["items"] if i["kind"] == "revised_value"]
    assert texts == ["Alder Credit Fund II value for 31 Aug 2026 was revised from 5,000,000 to 5,180,000 USD (+180,000), recorded 8 Oct 2026."]


def test_a3_0_a_confirmation_of_the_same_figure_is_not_a_revision(plane):
    K.add_note(plane, ADMIN, "alder-capital", "Catch-up.", "meeting", "2026-10-01")
    _val(plane, "same", 5_000_000, 8, "confirmed", "v1")
    assert not [i for i in K.changes(plane, ADMIN, "alder-capital")["items"] if i["kind"] == "revised_value"]


def test_a7_2_a_revised_statement_is_never_called_late_but_a_late_first_statement_is(plane):
    reg(plane, "credit_aug.txt", stmt("Alder Credit Fund II", "Final", "5,000,000.00", "31 August 2026"), 9, 9)     # 9 Sep: on time (due 14 Sep)
    reg(plane, "credit_aug_am.txt", stmt("Alder Credit Fund II", "Final amended", "5,010,000.00", "31 August 2026"), 1)  # 1 Oct: a revision
    K.add_note(plane, ADMIN, "alder-capital", "Catch-up.", "meeting", "2026-09-01")
    texts = [i["text"] for i in K.changes(plane, ADMIN, "alder-capital")["items"] if i["kind"] == "statement"]
    assert "A revised statement for Alder Credit Fund II dated 31 Aug 2026 arrived (final)." in texts
    assert not [t for t in texts if "revised" in t and "late" in t]
    tl = [t for t in K.profile(plane, ADMIN, "alder-capital", AS_OF)["timeline"] if t["fund_name"] == "Alder Credit Fund II"]
    assert sorted((bool(t["replaces"]), t["days_late"]) for t in tl) == [(False, 0), (True, 0)]


def test_j_uc3a_2_timeline_carries_business_days_late_for_a_late_first_statement(plane):
    story(plane)
    tl = {t["fund_name"]: t for t in K.profile(plane, ADMIN, "alder-capital", AS_OF)["timeline"]}
    assert tl["Alder Income Fund III"]["days_late"] == 2       # received 16 Oct, due 14 Oct


def test_a3_10_inbox_and_profile_say_who_may_draft_and_write(plane):
    story(plane)
    assert K.inbox(plane, RAJ, AS_OF)["can_draft"] is True and K.profile(plane, RAJ, "alder-capital")["can_write"] is True
    reader = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-raj")
    assert K.inbox(plane, reader, AS_OF)["can_draft"] is False and K.profile(plane, reader, "alder-capital")["can_write"] is False


def test_a7_9_passages_drop_page_headers_and_markdown_and_never_cut_mid_word(plane, monkeypatch):
    lines = ["Alder Capital  |  Alder DDQ 2026  |  Confidential  |  Synthetic test document", "Page 1", "# Meeting note: Alder call",
             "| Reference | MN-1 |", "|---|---|", "- Quarterly statements are delivered within 45 days of quarter end.", "2.1",
             "Auditor change effective Q2 2026."]
    monkeypatch.setattr("sh_platform.v1.doc_index.read", lambda plane, path, a, b, **k: list(enumerate(lines, 1)))
    text = K._readable(plane, {"path": "x", "from": 1, "to": 9, "text": ""})
    assert text == ("Meeting note: Alder call. Reference: MN-1. Quarterly statements are delivered within 45 days of quarter end. "
                    "Auditor change effective Q2 2026.")
    assert K._cut("Respondent: Hana Sato, Investor Relations", 25) == "Respondent: Hana Sato …"


def test_a7_1_the_document_passage_is_the_terms_not_the_cover_page():
    cover = "Alder DDQ 2026 Operational due diligence questionnaire. Completed for Evergreen Office, 2026-03-05. Respondent: Hana Sato, Investor Relations."
    body = "Firm name and strategy Alder Capital. Quarterly statements are delivered within 45 days of quarter end. External auditor Auditor change effective Q2 2026."
    out = K._key_sentences(cover + " " + body, 2)
    assert "45 days" in out and "Auditor change effective Q2 2026" in out and "Respondent" not in out


# ---- cycle 2 (TRIAGE-cycle-2 P2) ----
def test_c2_one_manager_page_works_out_that_manager_only(plane, monkeypatch):
    """AUC3-02/C2-UC7-01: the profile and 'what changed' no longer work out every manager's inbox, and read the warehouse once per kind."""
    story(plane)
    rows, reads = [], []
    real_row, real_listing = K._fund_row, E.listing
    monkeypatch.setattr(K, "_fund_row", lambda f, *a: rows.append(f["fund_name"]) or real_row(f, *a))
    monkeypatch.setattr(E, "listing", lambda *a, **k: reads.append(1) or real_listing(*a, **k))
    K.changes(plane, ADMIN, "birch-partners", "2026-01-01")
    assert rows == ["Birch Venture Fund IV"] and len(reads) == 1


def test_c2_revision_figures_and_document_kind_words():
    figs = {"new": {"amount": "8275000", "currency": "USD"}, "old": {"amount": "8420000", "currency": "USD"}}
    assert K._revision(figs, {"id": "new", "supersedes_document_id": "old"}) == {"from": "8420000", "to": "8275000", "change": "-145000", "currency": "USD"}
    assert K._revision(figs, {"id": "old", "supersedes_document_id": "new"})["change"] == "+145000"
    assert K._revision(figs, {"id": "new", "supersedes_document_id": "gone"}) is None      # never a guessed figure
    words = [K._kind_word(n, "document") for n in ("Kestrel Ridge Advisors DDQ 2026.pdf", "Kestrel Ridge Advisors Q3 2026 newsletter.pdf",
                                                    "Kestrel Ridge Advisors on-site meeting.md", "Northgate Partners mid-year letter.pdf", "Fees.xlsx")]
    assert words == ["due diligence questionnaire", "newsletter", "meeting note", "letter", "document"]


def test_c2_auc3_08_a_draft_for_one_statement_speaks_of_one(plane):
    reg(plane, "credit_aug.txt", stmt("Alder Credit Fund II", "Final", "5,000,000.00", "31 August 2026"), 9, 9)
    d = K.draft_followup(plane, ADMIN, "alder-capital", fund_id=CREDIT, as_of=AS_OF)
    assert "the statement for the period ending 30 Sep 2026 for:" in d["body"] and "send it," in d["body"]
    many = K.draft_followup(plane, ADMIN, "alder-capital", as_of=AS_OF)     # Credit and Growth/Income missing for September
    assert "statements" in many["body"] and "send them," in many["body"]


def test_c2_auc3_01_a_warehouse_collision_is_tried_again_then_a_plain_503(monkeypatch):
    import asyncio
    import json

    import duckdb
    from sh_platform.v1 import k5_routes as KR
    monkeypatch.setattr(KR, "require_seat", lambda request, seat: ADMIN)
    monkeypatch.setattr(KR, "_plane", lambda request: "plane")
    calls = []

    def flaky(p, v):
        calls.append(1)
        if len(calls) == 1:
            raise duckdb.BinderException('Unique file handle conflict: Cannot attach "evidence"')
        return {"ok": True}
    assert asyncio.run(KR._run(None, flaky)) == {"ok": True} and len(calls) == 2

    def stuck(p, v):
        raise wh.Busy("held")
    r = asyncio.run(KR._run(None, stuck))
    assert r.status_code == 503 and json.loads(r.body)["error"] == "busy"
