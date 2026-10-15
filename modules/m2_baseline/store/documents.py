"""M2-E4: the two documents a signature covers, "Business glossary" and "Data catalogue" (with its technical definitions, governance and accepted
risks), and their content fingerprints. A fingerprint is the sha256 of the document's FULL, unfiltered content (as the organiser sees it) as plain
data, never of a file (an Excel file carries a time stamp), so a rebuild of the same content gives the same fingerprint and a later change shows."""
import hashlib
import json

from modules.m2_baseline.domain import gate as D
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import glossary as SG
from modules.m2_baseline.store import governance as SGOV
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import technical as ST

NAMES = {"business_glossary": "Business glossary", "data_catalogue": "Data catalogue"}


WORKED_OUT = "worked out from the other cells"


def _stable(x):
    """The content without the time a derived column (Complete?, How sure are we ...) was last worked out: that time moves on every read."""
    if isinstance(x, dict):
        return {k: _stable(v) for k, v in x.items() if not (k == "at" and x.get("from") == WORKED_OUT)}
    return [_stable(v) for v in x] if isinstance(x, list) else x


def _sha(content) -> str:
    return hashlib.sha256(json.dumps(_stable(content), sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()


def contents(plane, baseline_id: str, left_out: dict | None = None) -> dict[str, dict]:
    """The full content of each document, in plain data."""
    left, kpis = left_out or {}, K.read_kpis(plane, baseline_id)
    SG.refresh_governance(plane, baseline_id)  # the glossary says what the measures' governance says, the moment it is fingerprinted
    rows, unmatched = SG.rows_for_download(plane, baseline_id, lambda k: True)
    shown, _ = ST.catalogue_for(plane, baseline_id, SA.ALL_SEEING)
    return {"business_glossary": {"rows": rows, "unmatched": unmatched},
            "data_catalogue": {"catalogue": shown, "governance": SGOV.table(plane, baseline_id, SA.ALL_SEEING), "technical": ST.table(plane, baseline_id, SA.ALL_SEEING),
                               "risks": D.accepted_risks(kpis, left), "left_out": D.left_out_rows(kpis, left)}}


def fingerprints(plane, baseline_id: str, left_out: dict | None, at: str) -> dict[str, dict]:
    return {k: {"sha256": _sha(v), "built_at": at} for k, v in contents(plane, baseline_id, left_out).items()}


def status(plane, baseline_id: str, left_out: dict | None, recorded: dict | None) -> list[dict]:
    """The two documents for the screen: name, and once signed the recorded fingerprint, when it was built and whether the content is still the same."""
    now = {k: _sha(v) for k, v in contents(plane, baseline_id, left_out).items()} if recorded else {}
    return [{"id": k, "name": n, **({"sha256": recorded[k]["sha256"], "built_at": recorded[k]["built_at"], "unchanged": now[k] == recorded[k]["sha256"]}
                                   if recorded and k in recorded else {})} for k, n in NAMES.items()]
