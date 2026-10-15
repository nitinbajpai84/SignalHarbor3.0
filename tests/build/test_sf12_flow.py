"""SF12: Flow's run notes, the quarantine table, incident notes and the dialect explanation. Synthetic data on a temporary plane; the model
is a stub that records every payload."""
import json
import os
from datetime import datetime

import pytest

from sh_platform import warehouse as wh
from sh_platform.build import contracts, runner
from sh_platform.build.agents import flow as F
from sh_platform.build.agents import read_tools as T
from sh_platform.build.agents.runtime import Runtime
from sh_platform.egress.model import ModelReply
from sh_platform.plane import PlaneStore

BP = {"version": 1, "state": "signed", "signed_by": [{"name": "Mei Tan", "role": "sponsor", "at": "2026-10-01T09:00:00+00:00"}],
      "model": {"facts": [{"name": "trades", "grain": "trade", "keys": ["id"], "measures": ["AUM"]}], "dimensions": []},
      "lineage": [{"measure": "AUM", "source": "trades", "fields": ["amount"], "transform": "sum of amount", "mart": "gold.aum.aum_total"}],
      "rules": [{"measure": "AUM", "rule": "amount is not empty", "severity": "block", "from": "scan"},
                {"measure": "AUM", "rule": "amount range 0 to 100", "severity": "warn", "from": "scan"},
                {"measure": "AUM", "rule": "id is unique", "severity": "block", "from": "scan"}],
      "access": [], "schedule": [{"source": "trades", "expected": "D+2 09:00", "sla": "WD8", "depends_on": []}]}
# 12 silver rows: id 1 twice (unique fails, 2 rows held), 6 empty amounts (held), 2 out of range (a warn rule: counted, not held)
DATA = ("id,day,amount\n1,2026-09-01,10\n1,2026-09-01,11\n" + "".join(f"{i},2026-09-02,\n" for i in range(2, 8))
        + "8,2026-09-02,777\n9,2026-09-02,888\n10,2026-09-03,20\n11,2026-09-03,30\n")
SECRETS = ("777", "888", "2026-09-02")


@pytest.fixture
def plane(tmp_path):
    p = PlaneStore(tmp_path).create("sf12-co")
    bp = p.path("build", "blueprint.json")
    bp.parent.mkdir(parents=True, exist_ok=True)
    bp.write_text(json.dumps(BP), encoding="utf-8")
    f = p.area("landing") / "trades_2026-09.csv"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(DATA, encoding="utf-8")
    t = datetime(2026, 9, 4, 8, 0).timestamp()
    os.utime(f, (t, t))
    return p


def _run(plane) -> dict:
    return runner.run_pipeline(plane, next(c for c in contracts.ensure(plane) if c["source"] == "trades"))


class _Model:
    def __init__(self, text):
        self.text, self.calls = text, []

    def complete(self, module_id, messages, tools=None):
        self.calls.append(json.dumps(messages))
        return ModelReply(text=self.text)


def test_quarantine_holds_exactly_the_block_rule_rows_and_the_run_holds_counts(plane):
    run = _run(plane)
    assert run["status"] == "failed"
    held = {(q["rule"], q["field"]): q["count"] for q in run["quarantined"]}
    assert held == {("AUM:amount is not empty", "amount"): 6, ("AUM:id is unique", "id"): 2}  # the warn range rule is not held
    con = wh.open_readonly(plane)
    try:
        got = con.execute("select _rule, _field, _run_id, count(*) from quarantine.trades group by all order by 1").fetchall()
        assert got == [("AUM:amount is not empty", "amount", run["id"], 6), ("AUM:id is unique", "id", run["id"], 2)]
        assert sorted(r[0] for r in con.execute("select id from quarantine.trades where _field = 'id'").fetchall()) == [1, 1]
    finally:
        con.close()
    q = T.read_quarantine(plane, Runtime(None), "trades")
    assert q["row_count"] == 8 and {(x["rule"], x.get("count"), x.get("count_text")) for x in q["by_rule"]} == {
        ("AUM:amount is not empty", 6, None), ("AUM:id is unique", None, "fewer than five")}
    _run(plane)  # each run replaces the table: it holds the newest run's rows only
    con = wh.open_readonly(plane)
    try:
        assert con.execute("select count(distinct _run_id), count(*) from quarantine.trades").fetchone() == (1, 8)
    finally:
        con.close()


def test_failed_run_without_a_model_names_the_first_missing_link(plane):
    run = _run(plane)
    note = F.explain_run(plane, run["id"], Runtime(None))
    assert note["fallback"] and note["sentence"] == F.NO_MODEL_RUN and note["text"] is None
    assert note["first_missing_link"] == "checks" and "The first missing link is the checks." in note["lines"][0]
    assert any("fewer than five rows" in ln and "id is unique" in ln for ln in note["lines"])  # a count under five
    assert any("6 rows set aside" in ln for ln in note["lines"]) and any("fewer than five rows" in ln and "range" in ln for ln in note["lines"])
    assert json.loads(plane.path("build", "flow", "runs", f"{run['id']}.json").read_text())["lines"] == note["lines"]
    assert F.explain_run(plane, run["id"], Runtime(None))["at"] == note["at"]  # stored note returned
    assert F.explain_run(plane, "../x", Runtime(None)) is None and F.explain_run(plane, "0" * 32, Runtime(None)) is None


def test_model_note_payload_carries_no_quarantine_value(plane):
    run = _run(plane)
    m = _Model("The run failed its checks: 6 rows have no amount and were set aside, out of 12 rows loaded.")
    note = F.explain_run(plane, run["id"], Runtime(m), fresh=True)
    assert m.calls and not note["fallback"] and note["text"].startswith("The run failed")
    stored = plane.path("build", "flow", "runs", f"{run['id']}.json").read_text()
    props = "".join(p.read_text() for p in plane.path("build", "proposals").glob("P-*.json"))
    for blob in m.calls + [stored, props]:
        assert not any(s in blob for s in SECRETS)
    assert '"value": 2,' not in m.calls[0]  # a count under five is never a fact


def test_invented_figure_falls_back(plane):
    run = _run(plane)
    note = F.explain_run(plane, run["id"], Runtime(_Model("42 rows failed.")), fresh=True)
    assert note["fallback"] and note["sentence"] == F.NO_MODEL_RUN


def test_non_unique_grain_files_one_model_change_naming_span(plane):
    run = _run(plane)
    note = F.explain_run(plane, run["id"], Runtime(None))
    assert len(note["proposals"]) == 1
    p = json.loads(plane.path("build", "proposals", f"{note['proposals'][0]}.json").read_text())
    assert p["kind"] == "model_change" and p["fix_by"] == "Span" and p["by_agent"] == "Flow" and p["to"] == "Mei Tan"
    assert p["subject"] == "the grain of trades" and p["evidence"]["fields"] == ["id"]
    assert F.explain_run(plane, run["id"], Runtime(None), fresh=True)["proposals"] == []  # one open proposal per target


def test_incident_note_goes_to_the_alerts_tell_person(plane):
    run = _run(plane)
    path = plane.path("build", "alerts.json")
    path.write_text(json.dumps({"alerts": [
        {"id": "trades:failed", "kind": "failed", "source": "trades", "state": "open", "tell": "Katie Menon", "opened": "2026-09-04"},
        {"id": "trades:late", "kind": "late", "source": "trades", "state": "open", "tell": None, "opened": "2026-09-04"},
        {"id": "gone:missing", "kind": "missing", "source": "gone", "state": "closed", "tell": "Katie Menon"}]}), encoding="utf-8")
    p = F.incident_note(plane, Runtime(None), "trades:failed")
    assert p["kind"] == "incident_note" and p["to"] == "Katie Menon" and p["to_role"] == "alert contact" and p["fallback"]
    assert "checks" in p["why"] and p["next_step"] and not any(s in json.dumps(p) for s in SECRETS)
    assert F.incident_note(plane, Runtime(None), "trades:failed")["id"] == p["id"]  # the open note, not a second one
    assert F.incident_note(plane, Runtime(None), "trades:late") is None  # nobody named to tell
    assert F.incident_note(plane, Runtime(None), "gone:missing") is None  # not open
    assert json.loads(path.read_text())["alerts"][0]["state"] == "open"  # Flow never closes or acknowledges
    assert run["status"] == "failed"


def test_dialect_lines(plane, monkeypatch):
    assert F.explain_dialect(plane, Runtime(None))["state"] == "none"
    monkeypatch.setattr(T, "read_dialect", lambda pl, rt: {"state": "ready", "dialect": "snowflake", "message": "A draft for your warehouse.",
                                                           "statements": [{"name": "silver.trades", "changed_constructs": ["strftime to to_char"]}]})
    m = _Model("Dates are formatted with a different function there.")
    d = F.explain_dialect(plane, Runtime(m))
    assert d["changed"] == ["strftime to to_char"] and d["text"] and not d["fallback"]
    assert "select " not in m.calls[0].lower()  # names only, never SQL text
    assert F.explain_dialect(plane, Runtime(None))["sentence"] == F.NO_MODEL_DIALECT


def test_listed_names_with_digits_pass_the_guard(plane):
    run = _run(plane)
    m = _Model(f"Run {run['id']} of trades failed the check on amount for AUM: 6 rows were set aside.")
    note = F.explain_run(plane, run["id"], Runtime(m), fresh=True)
    assert not note["fallback"] and "Names you may use:" in m.calls[0] and "Never make up a name that contains digits." in m.calls[0]
