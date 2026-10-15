"""M2-E1: the technical definition on the measure record (kpis.json: `technical`, `technical_proposal`, `technical_confirmed`) and the
catalogue rows it links to. Nothing new is stored beside the measure: the parts live on the measure and the links are ids of catalogue rows.

Who may see what: the caller passes a `viewer` (the catalogue's own rule, `C.guards`) and `sees` (the work list's rule). A part only ever
links to a row the viewer may see; a text part that names a row or measure the viewer may not see is withheld (`hidden_terms`).
A signed baseline is read-only (K.change raises Locked).
"""
from typing import Callable

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import catalogue as S
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import kpis as K
from sh_platform.jsonfile import lock_for

NOT_FOUND = "We could not find that measure."


def catalogue_for(plane, baseline_id: str, viewer: C.Viewer) -> tuple[dict, list[str]]:
    """(the catalogue as this person may see it, with hidden rows left out; the names and ids of the rows they may not see). The second is for
    withholding text that names them."""
    S._baseline(plane, baseline_id)
    cat, _ = S._raw(plane, baseline_id)
    shown, _f = C.view_of(cat, C.guards(cat, S._governance(plane, baseline_id)), viewer, drop=True)
    kept = {(t, C.row_id(t, r)) for t in C.TABS for r in shown[t]}
    heads = {"sources": "Source name", "tables": "Name of table, file or document type", "fields": "Field name as in the source", "extractions": "What to extract"}
    gone: list[str] = []
    for tab, head in heads.items():
        for r in cat[tab]:
            if (tab, C.row_id(tab, r)) not in kept:
                gone += [C.row_id(tab, r), C.text_of(r.get(head))]
    return shown, [g for g in gone if g]


def hidden_terms(plane, baseline_id: str, viewer: C.Viewer, sees: Callable[[dict], bool]) -> list[str]:
    """Everything this person may not see by name: catalogue rows (ids and names) and restricted measures. Used on every text shown to them."""
    _, gone = catalogue_for(plane, baseline_id, viewer)
    return gone + [k["name"] for k in K.read_kpis(plane, baseline_id) if not sees(k)]


def _own(plane, baseline_id: str, kpi_id: str, sees) -> dict:
    k = next((k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id), None)
    if k is None or not sees(k):
        raise LookupError(NOT_FOUND)  # a measure the person may not see answers like one that does not exist
    return k


def known_rows(plane, baseline_id: str, viewer: C.Viewer) -> set[str]:
    """The ids of the catalogue rows this person may link to."""
    shown, _ = catalogue_for(plane, baseline_id, viewer)
    return set(T.row_names(shown))


def edit(plane, baseline_id: str, kpi_id: str, part: str, value, mark: str, by: str, viewer: C.Viewer, sees) -> dict:
    """A person writes, changes or clears one part ("Edit"). A link only to a row they may see."""
    _own(plane, baseline_id, kpi_id, sees)
    known = known_rows(plane, baseline_id, viewer)
    why = f"the {T.LABELS.get(part, part).lower()} was changed by {by} after this was settled"
    return K.change(plane, baseline_id, kpi_id, lambda k: A.reopen_for_part(T.set_part(k, part, value, mark, by, known), part, why))


def use(plane, baseline_id: str, kpi_id: str, part: str, by: str, viewer: C.Viewer, sees) -> dict:
    """"Use this": Lens's draft beside a part becomes the person's own (stated by them)."""
    _own(plane, baseline_id, kpi_id, sees)
    known = known_rows(plane, baseline_id, viewer)

    def go(k):
        d = (k.get("technical_proposal") or {}).get(part)
        if part in T.LINKS and T.present(d) and any(i not in known for i in d["value"]):
            raise T.Refused("That draft links a row you may not see.")
        return A.reopen_for_part(T.use_proposal(k, part, by), part, f"the {T.LABELS.get(part, part).lower()} was changed by {by} after this was settled")
    return K.change(plane, baseline_id, kpi_id, go)


def definition_view(k: dict, names: dict[str, str], hidden: list[str]) -> dict:
    """One measure's technical definition as one person may see it (the screen, the data owner's own list and the answer link all show this): the
    business definition (for the pre-filled wording), the nine parts, who confirmed and which parts still need confirming."""
    c = T.confirmed(k)
    d = k.get("definition")
    return {"kpi_id": k["id"], "name": k["name"], "definition": T.text_of(d) if isinstance(d, dict) and d.get("mark") != "unknown" else "",
            "parts": T.view_parts(k, names, hidden), "confirmed": c, "confirmed_parts": [T.LABELS[x] for x in T.confirmed_parts(k)],
            "to_confirm": [T.LABELS[x] for x in T.to_confirm(k)], "complete": not T.missing(k), "missing": [T.LABELS[m] for m in T.missing(k)],
            "sent_back": _sent_back(k)}


MAX_NOTE = 300
SENT_BACK = "technical_sent_back"  # on the view only; the notes live in NOTES_FILE


def _sent_back(k: dict) -> dict | None:
    n = k.get(SENT_BACK)
    return {**n, "label": f"Sent back: {n['note']}"} if isinstance(n, dict) and n.get("note") else None


NOTES_FILE = "technical_sent_back.json"  # intents/m2_baseline/<baseline_id>/technical_sent_back.json = {kpi_id: {note, by, at}}: a proposal beside the
# (possibly signed) record, like quality_rules.json; kpis.json is never written, so a signed baseline is not edited


def _notes_file(plane, baseline_id: str):
    return B.root(plane) / baseline_id / NOTES_FILE


def read_with_notes(plane, baseline_id: str) -> list[dict]:
    """The measures with each one's sent-back note (if any) attached for the view."""
    notes = (B.read_file(_notes_file(plane, baseline_id), dict) or {}) if B.is_id(baseline_id) else {}
    return [{**k, SENT_BACK: notes[k["id"]]} if k["id"] in notes else k for k in K.read_kpis(plane, baseline_id)]


def send_back(plane, baseline_id: str, kpi_id: str, note, by: str, sees) -> dict:
    """"Send back with a note": the note waits beside the technical definition for its data owner. Allowed on a signed baseline (nothing signed is
    edited); it goes when the owner confirms."""
    _own(plane, baseline_id, kpi_id, sees)
    text = " ".join(note.split()) if isinstance(note, str) else ""
    if not text:
        raise T.Refused("Please write a note first.")
    if len(text) > MAX_NOTE:
        raise T.Refused(f"That is too long. Please keep it under {MAX_NOTE} characters.")
    with lock_for(_notes_file(plane, baseline_id)):
        doc = B.read_file(_notes_file(plane, baseline_id), dict) or {}
        doc[kpi_id] = {"note": text, "by": by, "at": A.now()}
        B.write_file(_notes_file(plane, baseline_id), doc)
    return doc[kpi_id]


def is_data_owner(k: dict, account_id: str | None, named) -> bool:
    """Is this person the data owner named on the measure: by account id when the nomination has one, else by name (`named(name)` says whether
    the asker is that name)."""
    o = (k.get("owners") or {}).get("data") or {}
    if o.get("mark") == "unknown" or not o.get("value"):
        return False
    return account_id is not None and account_id == o["account_id"] if o.get("account_id") else bool(named(o["value"]))


def confirm(plane, baseline_id: str, kpi_id: str, by: str, sees) -> dict:
    _own(plane, baseline_id, kpi_id, sees)
    out = K.change(plane, baseline_id, kpi_id, lambda k: T.confirm(k, by))
    with lock_for(_notes_file(plane, baseline_id)):  # the owner has answered the note
        doc = B.read_file(_notes_file(plane, baseline_id), dict) or {}
        if doc.pop(kpi_id, None) is not None:
            B.write_file(_notes_file(plane, baseline_id), doc)
    return out


def sees_for(viewer: C.Viewer) -> Callable[[dict], bool]:
    """The work list's rule for one viewer (so the catalogue routes, which have no work-list context, can use it)."""
    return lambda k: W.may_see(k, viewer.name, viewer.account_id, "company_admin" in viewer.roles)


COLUMNS = ("calculation", "sources", "tables", "fields", "filters", "grain", "period", "currency_basis", "notes")


def columns(plane, baseline_id: str, viewer: C.Viewer) -> dict:
    """The technical definitions for the catalogue, in words, of the measures this person may see: {"kpis": {kpi id: {part: text, confirmed}},
    "inputs": {field or extraction row id: [measure names that use it]}}. A part that names something they may not see is left empty."""
    sees = sees_for(viewer)
    shown, gone = catalogue_for(plane, baseline_id, viewer)
    names, hidden = T.row_names(shown), gone + [k["name"] for k in K.read_kpis(plane, baseline_id) if not sees(k)]
    out, inputs = {}, {}
    for k in K.read_kpis(plane, baseline_id):
        if not sees(k):
            continue
        parts = {p["part"]: p for p in T.view_parts(k, names, hidden)}
        row = {x: ("; ".join(l["name"] for l in parts[x]["links"]) if x in T.LINKS else ("" if parts[x]["withheld"] else T.text_of(parts[x]["cell"]))) for x in COLUMNS}
        c = T.confirmed(k)
        out[k["id"]] = {**row, "confirmed": f"{c['by']}, {str(c['at'])[:10]}" if c else ""}
        for link in parts["fields"]["links"]:
            inputs.setdefault(link["id"], []).append(k["name"])
    return {"kpis": out, "inputs": inputs}


def table(plane, baseline_id: str, viewer: C.Viewer) -> list[list[str]]:
    """The Excel sheet "Technical definitions": one row per measure this person may see."""
    cols = columns(plane, baseline_id, viewer)["kpis"]
    names = {k["id"]: k["name"] for k in K.read_kpis(plane, baseline_id)}
    return [[kid, names[kid], *(c[x] for x in COLUMNS), c["confirmed"]] for kid, c in cols.items()]


def unmark_restricted(kpi: dict, titles=()) -> dict:
    """A measure made less restricted: what Lens drew from a restricted document (technical parts, their drafts, open questions) is cleared."""
    out = A.clear_restricted(dict(kpi))
    cur = T.parts_of(kpi)
    gone = lambda v: isinstance(v, dict) and v.get("by") == T.LENS and (v.get("restricted") or any(t in str(v.get("from") or "") for t in titles))  # noqa: E731
    if isinstance(kpi.get("technical"), dict):
        out["technical"] = {p: (T.unknown(T.LENS, "cleared: drawn from a restricted document") if gone(c) else c) for p, c in cur.items()}
    out["technical_proposal"] = {p: c for p, c in (kpi.get("technical_proposal") or {}).items() if not gone(c)}
    return out
