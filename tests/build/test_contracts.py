"""Contract titles and owners come from the environment answers, not from the blueprint signer alone."""
import json

from sh_platform.build import contracts


class _Plane:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return self.root.joinpath(*parts)


def _write(root, rel, doc):
    p = root.joinpath(*rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_owner_and_title_from_the_catalogue(tmp_path):
    _write(tmp_path, ("build", "blueprint.json"), {"signed_by": [{"name": "Head Person"}], "lineage": [], "rules": [],
           "schedule": [{"source": "Custodian daily file", "expected": "Daily", "sla": "Not stated"},
                        {"source": "Treasury cash plan", "expected": "Weekly", "sla": "Not stated"}]})
    _write(tmp_path, ("context", "profile", "profile.json"), {"systems": {
        "custodian-daily-file": {"name": {"value": "Custodian daily file"}, "owner": {"value": "Harvey Rowley"}}}})
    by = {c["source"]: c for c in contracts.derive(_Plane(tmp_path))}
    assert by["custodian_daily_file"]["owner"] == "Harvey Rowley" and by["custodian_daily_file"]["title"] == "Custodian daily file"
    assert by["treasury_cash_plan"]["owner"] == "Head Person" and by["treasury_cash_plan"]["title"] == "Treasury cash plan"
