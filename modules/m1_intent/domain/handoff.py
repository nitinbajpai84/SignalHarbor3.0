"""The hand-off to module 2 (M1-30, D-026): the outcome record, built from a signed charter version and checked
against contracts/outcome.yaml. Pure Python; the file is written by store/charter.py. Module 2 reads only this."""
from pathlib import Path

import yaml

from modules.m1_intent.domain.contracts import DEFAULT_DIR, ContractError

MODULE_ID = "m1_intent"


def load_outcome_contract(folder=None) -> dict:
    name = "outcome.yaml"
    try:
        d = yaml.safe_load((Path(folder or DEFAULT_DIR) / name).read_text(encoding="utf-8"))
        keys = ("kind", "required", "problem_fields", "later_fields", "signature_fields", "footer_fields", "extra_lists", "extra_list_fields")
        if not isinstance(d, dict) or any(k not in d for k in keys):
            raise ValueError("a key is missing")
    except (OSError, yaml.YAMLError, ValueError):
        raise ContractError(f"{name} is not valid.") from None
    return d


def _pick(row: dict, fields) -> dict:
    return {f: row[f] for f in fields}


def _of_kind(version: dict, kind: str) -> list[dict]:
    """The version's problems of one kind; a problem drafted before kinds existed is an intent."""
    return [{"details": [], **p} for p in version["problems"] if p.get("kind", "intent") == kind]


def build_outcome(contract: dict, *, outcome_id: str, session_id: str, version: dict) -> dict:
    """The record for a signed version. Raises ValueError for a version that is not signed: nothing unsigned leaves module 1."""
    if version["status"] != "signed" or not version["signatures"]:
        raise ValueError("only a signed charter can be handed on")
    sigs = [{"name": s["name"], "at": s["at"], "how": s["how"]} for s in version["signatures"]]
    record = {"outcome_id": outcome_id, "session_id": session_id, "module": MODULE_ID, "kind": contract["kind"],
              "charter_version": version["version"], "signed_at": max(s["at"] for s in sigs), "signatures":
              [_pick(s, contract["signature_fields"]) for s in sigs], "template": version["template"]["id"],
              "problems": [_pick(p, contract["problem_fields"]) for p in _of_kind(version, "intent")],
              **{key: [_pick(p, contract["extra_list_fields"]) for p in _of_kind(version, kind)]
                 for key, kind in contract["extra_lists"].items()},
              "later": [_pick(p, contract["later_fields"]) for p in version["later"]],
              "footer": _pick(version["footer"], contract["footer_fields"])}
    missing = [k for k in contract["required"] if k not in record]
    if missing:
        raise ValueError(f"the outcome record lacks {missing}")
    return record
