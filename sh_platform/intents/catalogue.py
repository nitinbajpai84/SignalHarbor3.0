"""IC v2 B17 (specs 30 and 31): the data catalogue and the governed state of each measure, seen from an Initiative.

Nothing is stored twice. The technical definition, the catalogue rows and the six governed cells stay in the module 2 baseline files
(kpis.json, catalogue.json, governed_state.json, signoff.json); the Initiative points at its baseline (`refs.baseline_ids`). The only new
file is the code register `catalogue_measures.json` beside kpis.json: one row per measure code, the name being a label and an alias.

One id rule: a measure's node is `measure:<code>` and nothing else; `duplicate_name_blockers` is the guard the graph build must call.
One owner rule: `owners_of` is the single reading of who owns a measure; the list, the entry, the charter table and `company_owner_map`
(what Feeds and the register should read) all use it.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.api.governed import ensure_draft
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import catalogue as SC
from modules.m2_baseline.store import governed as GS
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import technical as ST
from sh_platform.graph.versions import append_version
from sh_platform.intents import _plane, _viewer, lens
from sh_platform.jsonfile import lock_for, read_json_strict
from sh_platform.profile import store as profile_store

log = logging.getLogger(__name__)
router = APIRouter()

REGISTER = "catalogue_measures.json"
RESTRICTED = "A restricted measure"
STATES = ("confirmed", "draft", "not_drafted", "unknown_accepted", "changed")
STATE_WORDS = {"confirmed": "Confirmed", "draft": "Draft", "not_drafted": "Not drafted", "unknown_accepted": "Unknown accepted", "changed": "Changed since confirmed"}
FIELD_WORDS = {"owners": "owners", "classification": "classification", "may_see": "who may see", "resolving": "resolving team", "affects": "affected downstream", "review_date": "review date"}
NO_BASELINE = "Not available yet. No baseline has been started for this Initiative."
NO_MEASURES = "No measures yet. Measures come from the wall clusters in Define. Open Clusters."


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- the code register ----------------------------------------------------------------------------------------------------------

def key_of(text) -> str:
    """Spaces, case and plural ignored: 'Total AUM', 'total  aum' and 'Total AUMs' are one name."""
    return "".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _reg_file(plane, bid: str):
    return B.root(plane) / bid / REGISTER


def register(plane, bid: str) -> list[dict]:
    """Every code of the baseline, retired ones included. A measure that came from the work list adopts its own id as its code (read only;
    the next write saves it)."""
    rows = B.read_file(_reg_file(plane, bid), list) or []
    have = {r["code"] for r in rows}
    for k in K.read_kpis(plane, bid):
        if k.get("id") and k["id"] not in have:
            rows.append(_row(k["id"], str(k.get("name") or k["id"]), "the work list", None))
    return rows


def _row(code: str, label: str, by: str, origin) -> dict:
    return {"code": code, "label": label, "aliases": [], "merged_into": None, "minted_by": by, "minted_at": _now(), "from": origin}


def _save(plane, bid: str, rows: list[dict]) -> None:
    B.write_file(_reg_file(plane, bid), rows)


def live(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not r.get("merged_into")]


def duplicate_of(rows: list[dict], label: str, skip: str | None = None) -> dict | None:
    """The live measure whose label or alias reads the same as `label`."""
    k = key_of(label)
    return next((r for r in live(rows) if r["code"] != skip and k and k in {key_of(r["label"]), *map(key_of, r["aliases"])}), None)


def duplicate_name_blockers(items: list[tuple[str, str, list[str]]]) -> list[str]:
    """The check the graph build runs: [(code, label, aliases)] of the live Measure nodes. One blocker line per shared name."""
    seen: dict[str, tuple[str, str]] = {}
    out: list[str] = []
    for code, label, aliases in items:
        for name in dict.fromkeys([label, *aliases]):
            k = key_of(name)
            if k in seen and seen[k][0] != code:
                out.append(f"Two measures share the name {seen[k][1]}: {seen[k][0]} and {code}. Merge or rename.")
            seen.setdefault(k, (code, name))
    return list(dict.fromkeys(out))


def graph_blockers(nodes: dict, codes: set[str]) -> list[str]:
    """For the graph build: `nodes` is {node id: {type, label}}. A Measure node id must be measure:<code> of a live code, and no two share a name."""
    measures = {i: n for i, n in nodes.items() if n.get("type") == "Measure"}
    bad = [f"The measure {n.get('label')} has no code. Promote or link it in Define." for i, n in measures.items() if i.split(":", 1)[-1] not in codes]
    return bad + duplicate_name_blockers([(i.split(":", 1)[-1], str(n.get("label")), []) for i, n in measures.items()])


def blockers(plane, bid: str) -> list[str]:
    return duplicate_name_blockers([(r["code"], r["label"], r["aliases"]) for r in live(register(plane, bid))])


def node_ids(plane, bid: str) -> list[str]:
    """The Measure nodes of the baseline: exactly one per live code, never one from a name."""
    return [f"measure:{r['code']}" for r in live(register(plane, bid))]


def _next_code(rows: list[dict]) -> str:
    n = max([int(m.group(1)) for r in rows if (m := re.fullmatch(r"M-(\d+)", r["code"]))] + [0])
    return f"M-{n + 1}"  # never reused: retired codes stay in the register


def mint(plane, bid: str, label: str, by: str, origin=None, different: str | None = None, priority: str = "should") -> dict:
    """The only writer of a new code. A name that reads like a live one is refused unless the person says in one line how it differs."""
    label = " ".join(str(label or "").split())
    if not label or len(label) > 120:
        raise Refused(422, "Please give the measure a name of up to 120 characters.")
    with lock_for(_reg_file(plane, bid)):
        rows = register(plane, bid)
        twin = duplicate_of(rows, label)
        if twin and not (different or "").strip():
            raise Refused(409, f"This looks like {twin['code']} {twin['label']}. Link it instead?")
        row = {**_row(_next_code(rows), label, by, origin), **({"different": " ".join(different.split())} if twin else {})}
        try:
            K.add(plane, bid, W.new_kpi(row["code"], label, [], priority))
        except B.Locked as e:
            raise Refused(409, str(e)) from None
        _save(plane, bid, [*rows, row])
    append_version(plane, f"measure:{row['code']}", "Measure added to the register", by, bid)
    return row


def _find(rows: list[dict], code: str) -> dict:
    row = next((r for r in rows if r["code"] == code), None)
    if row is None:
        raise Refused(404, "We could not find that measure.")
    return row


def set_label(plane, bid: str, code: str, label: str, by: str) -> dict:
    """Rename: the old label becomes an alias, the code stays."""
    label = " ".join(str(label or "").split())
    with lock_for(_reg_file(plane, bid)):
        rows = register(plane, bid)
        row = _find(rows, code)
        twin = duplicate_of(rows, label, skip=code)
        if twin:
            raise Refused(409, f"This looks like {twin['code']} {twin['label']}. Link it instead?")
        if label and key_of(label) != key_of(row["label"]):
            row["aliases"] = list(dict.fromkeys([*row["aliases"], row["label"]]))
            row["label"] = label
            K.change(plane, bid, code, lambda k: {**k, "name": label})
            _save(plane, bid, rows)
            append_version(plane, f"measure:{code}", f"Renamed to {label}", by, bid)
        return row


def add_alias(plane, bid: str, code: str, alias: str, by: str) -> dict:
    alias = " ".join(str(alias or "").split())
    with lock_for(_reg_file(plane, bid)):
        rows = register(plane, bid)
        row = _find(rows, code)
        twin = duplicate_of(rows, alias, skip=code)
        if twin:
            raise Refused(409, f"This looks like {twin['code']} {twin['label']}. Merge them instead.")
        if alias and key_of(alias) != key_of(row["label"]):
            row["aliases"] = list(dict.fromkeys([*row["aliases"], alias]))
            _save(plane, bid, rows)
            append_version(plane, f"measure:{code}", f"Alias {alias} added", by, bid)
        return row


def merge(plane, bid: str, keep: str, retire: str, by: str) -> dict:
    """Two codes turned out to be one: the retired code redirects to the survivor (kept as an alias), the survivor takes what it lacks."""
    if keep == retire:
        raise Refused(422, "Choose two different measures.")
    with lock_for(_reg_file(plane, bid)):
        rows = register(plane, bid)
        a, b = _find(rows, keep), _find(rows, retire)
        if a.get("merged_into") or b.get("merged_into"):
            raise Refused(409, "One of those measures is already merged.")
        if rows.index(a) > rows.index(b):  # the later code is the one retired, whichever way round it was asked
            (a, keep), (b, retire) = (b, retire), (a, keep)
        ks = {k["id"]: k for k in K.read_kpis(plane, bid)}
        if retire in ks and keep in ks:
            old = T.parts_of(ks[retire])

            def take(k: dict) -> dict:
                cur = T.parts_of(k)
                own = {**k.get("owners", {})}
                for r, c in (ks[retire].get("owners") or {}).items():
                    if (own.get(r) or {}).get("mark", "unknown") == "unknown" and (c or {}).get("mark", "unknown") != "unknown":
                        own[r] = c
                return {**k, "owners": own, "technical": {p: (old[p] if not T.present(cur[p]) and T.present(old[p]) else cur[p]) for p in T.PARTS}}
            K.change(plane, bid, keep, take)
            K.remove(plane, bid, retire)
        a["aliases"] = list(dict.fromkeys([*a["aliases"], b["label"], *b["aliases"], retire]))
        b["merged_into"] = keep
        _save(plane, bid, rows)
    append_version(plane, f"measure:{keep}", f"{retire} merged into this measure", by, bid)
    return a


# ---- one reading of who owns a measure ------------------------------------------------------------------------------------------

def _plain(cell) -> str | None:
    return str(cell["value"]) if isinstance(cell, dict) and cell.get("mark") != "unknown" and cell.get("value") else None


def source_owner(plane, bid: str, code: str) -> str | None:
    """The Data owner cell of the first source that feeds the measure (the Sources tab; spec 30 open question 11)."""
    cat, _ = SC._raw(plane, bid)
    for s in T.feeding(cat, code)["sources"]:
        if (who := C.text_of(s.get("Data owner"))):
            return who
    return None


def owners_of(k: dict, governed: dict | None, source: str | None = None) -> dict:
    """{business, data, source} each a name or None, with `confirmed`. A stated governed cell wins; else the work list; else Lens's guess.
    `process` is the business owner of the process (ruling 11) and only fills an empty business owner."""
    cell = (governed or {}).get("owners") or {}
    cell_v = cell.get("value") if isinstance(cell.get("value"), dict) and cell.get("mark") != "unknown" else {}
    work = {r: _plain((k.get("owners") or {}).get(r)) for r in ("business", "data", "process")}
    stated = cell.get("mark") == "stated"
    pick = (lambda r: (cell_v.get(r) if stated else None) or work.get(r) or cell_v.get(r))
    return {"business": pick("business") or pick("process"), "data": pick("data"), "source": cell_v.get("source") or source,
            "confirmed": stated}


def company_owner_map(plane) -> dict[str, dict]:
    """measure code (lowercase) -> owners, from the signed baseline, else the first (the helper Feeds and the register should call)."""
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    if base is None:
        return {}
    doc = GS._read(plane, base["id"])
    return {str(k["id"]).lower(): owners_of(k, doc.get(k["id"]), source_owner(plane, base["id"], k["id"])) for k in K.read_kpis(plane, base["id"]) if k.get("id")}


# ---- who sees and who owns a measure minted here (ruling R8) --------------------------------------------------------------------

def _names(k: dict, cell: dict | None) -> list[str]:
    own = [_plain(c) for c in (k.get("owners") or {}).values()]
    got = (cell or {}).get("owners") or {}
    stated = got.get("mark") == "stated" and isinstance(got.get("value"), dict)
    return [n for n in dict.fromkeys([*own, *([got["value"].get(r) for r in ("business", "data")] if stated else [])]) if n]


def adopt_owners(plane, bid: str, accounts: list[dict]) -> None:
    """Owners confirmed in the governed state become named owners of the measure (a role nobody is named for yet; a person the organiser
    named is never replaced). The same stored owner cell the work list and the confirm rule read."""
    gov = GS._read(plane, bid)
    for k in K.read_kpis(plane, bid):
        got = (gov.get(k["id"]) or {}).get("owners") or {}
        if got.get("mark") != "stated" or not isinstance(got.get("value"), dict):
            continue
        new = {}
        for role in ("business", "data"):
            who = got["value"].get(role)
            if who and (k.get("owners") or {}).get(role, {}).get("mark", "unknown") == "unknown":
                ids = [a["account_id"] for a in accounts if C.norm(a.get("display_name")) == C.norm(who) and not a.get("disabled")]
                new[role] = W.nominee({"name": who, "has_account": bool(ids)}, str(got.get("by")), ids[0] if len(ids) == 1 else None)
        if new:
            try:
                K.change(plane, bid, k["id"], lambda x, n=new: {**x, "owners": {**x["owners"], **n}})
            except B.Locked:
                return
            try:
                from sh_platform.intents import people
                people.confirmed_in_baseline(plane, bid, str(got.get("by") or ""), accounts)
            except Exception:  # noqa: BLE001 - never blocks the act
                pass


def share(plane, bid: str, accounts: list[dict]) -> None:
    """A measure minted from the catalogue starts at personal data "Not sure", which hides it from everyone but the organiser. Ruling R8: the
    analyst and the named owners may see it too, so they are added to who may see it (the organiser always can)."""
    minted = {r["code"] for r in live(register(plane, bid)) if r["minted_by"] != "the work list"}
    gov = GS._read(plane, bid)
    analysts = [a for a in accounts if "analyst" in (a.get("roles") or []) and not a.get("disabled")]
    for k in K.read_kpis(plane, bid):
        g = k.get("governance") or {}
        if k["id"] not in minted or g.get("personal") != "not_sure" or g.get("sensitive"):
            continue
        names = [*(a["display_name"] for a in analysts), *_names(k, gov.get(k["id"]))]
        have = {n.casefold() for n in g.get("may_see") or []}
        if all(n.casefold() in have for n in names):
            continue
        ids = lambda n: [a["account_id"] for a in accounts if C.norm(a.get("display_name")) == C.norm(n) and not a.get("disabled")]  # noqa: E731

        def edit(x: dict) -> dict:
            may = list(dict.fromkeys([*(x["governance"].get("may_see") or []), *names]))
            bound = {n.casefold(): i for n in may if (i := ids(n))}
            return {**x, "governance": {**x["governance"], "may_see": may, **({"may_see_accounts": {**x["governance"].get("may_see_accounts", {}), **bound}} if bound else {})}}
        try:
            K.change(plane, bid, k["id"], edit)
        except B.Locked:
            return


def tidy(request: Request, plane, bid: str) -> None:
    accounts = request.app.state.account_store.in_company(request.state.company_id)
    adopt_owners(plane, bid, accounts)
    share(plane, bid, accounts)


# ---- the entry state ------------------------------------------------------------------------------------------------------------

def accepted_unknown(plane, bid: str) -> dict[str, dict]:
    version = ((B.read_file(B.root(plane) / bid / "signoff.json", dict) or {}).get("versions") or [{}])[-1]
    return {c: r["accepted"] for c, r in (version.get("review") or {}).items() if isinstance(r, dict) and (r.get("accepted") or {}).get("by")}


def state_of(k: dict, accepted: dict | None = None) -> str:
    if T.confirmed(k):
        return "confirmed"
    if isinstance(k.get("technical_confirmed"), dict):
        return "changed"
    if accepted:
        return "unknown_accepted"
    p = T.parts_of(k)
    return "draft" if any(T.present(p[x]) for x in T.PARTS) else "not_drafted"


def guessed_parts(k: dict) -> int:
    return sum(1 for c in T.parts_of(k).values() if c.get("mark") == "guessed")


def _can_see(plane, bid: str, viewer: C.Viewer) -> list[dict]:
    return [k for k in K.read_kpis(plane, bid) if W.may_see(k, viewer.name, viewer.account_id, "company_admin" in viewer.roles)]


# ---- the list (Screen A) ----------------------------------------------------------------------------------------------------------

def catalogue_view(plane, bid: str, viewer: C.Viewer, owner_me: bool = False) -> dict:
    if B.read_baseline(plane, bid) is None:
        raise Refused(404, NO_BASELINE)
    reg = {r["code"]: r for r in live(register(plane, bid))}
    acc, gov = accepted_unknown(plane, bid), GS._read(plane, bid)
    kpis, seen = K.read_kpis(plane, bid), {k["id"] for k in _can_see(plane, bid, viewer)}
    rows, waiting = [], {}
    for k in kpis:
        if k["id"] not in reg:
            continue
        if k["id"] not in seen:
            if not owner_me:  # "my measures" lists only what is mine
                rows.append({"restricted": True, "label": RESTRICTED})
            continue
        st, own = state_of(k, acc.get(k["id"])), owners_of(k, gov.get(k["id"]), source_owner(plane, bid, k["id"]))
        if owner_me and not (own["data"] and C.norm(own["data"]) == C.norm(viewer.name)):
            continue
        row = {"code": k["id"], "label": reg[k["id"]]["label"], "aliases": reg[k["id"]]["aliases"], "owner": own["data"], "state": st, "state_label": STATE_WORDS[st],
               "guessed": guessed_parts(k), "priority": k.get("priority")}
        rows.append(row)
        if st in ("draft", "changed") and not T.missing(k) and own["data"]:
            waiting.setdefault(own["data"], []).append(k["id"])
    shown = [r for r in rows if not r.get("restricted")]
    counts = {s: sum(1 for r in shown if r["state"] == s) for s in STATES}
    guessed = sum(r["guessed"] for r in shown)
    unowned = [r["code"] for r in shown if not r["owner"]]
    lens_line = (f"I guessed {guessed} part{'s' if guessed != 1 else ''} across {sum(1 for r in shown if r['guessed'])} measures. "
                 f"{shown[[r['guessed'] > 0 for r in shown].index(True)]['owner'] or 'The data owner'}, please check them.") if guessed else "Lens has nothing to add."
    return {"baseline_id": bid, "measures": rows, "counts": counts if shown else None, "guessed_parts": guessed if shown else None,
            "empty": NO_MEASURES if not rows else None, "lens_line": lens_line, "not_drafted": counts["not_drafted"],
            "waiting": [{"person": p, "codes": c} for p, c in waiting.items()] + ([{"person": "Organiser", "text": f"{len(unowned)} measures have no data owner", "codes": unowned}] if unowned else []),
            "blockers": blockers(plane, bid), "signed": B.read_baseline(plane, bid)["state"] == "signed"}


# ---- the entry --------------------------------------------------------------------------------------------------------------------

def _trail(plane, bid: str, k: dict) -> list[dict]:
    """The version trail, worked out from the record so it can never disagree with it: who set or confirmed each part, plus the register's lines."""
    lines = []
    for p, c in T.parts_of(k).items():
        if c.get("at") and c.get("mark") != "unknown":
            lines.append({"at": str(c["at"]), "text": f"{c.get('by')} {'drafted' if c.get('by') == T.LENS else 'set'} {T.LABELS[p]}"})
    c = k.get("technical_confirmed")
    if isinstance(c, dict):
        lines.append({"at": str(c.get("at")), "text": f"{c.get('by')} confirmed" + ("" if T.confirmed(k) else " (lapsed: a part changed since)")})
    v = read_json_strict(plane.path("graph", "versions.json"), dict) if plane.path("graph", "versions.json").exists() else {}
    # a code is only unique inside one baseline: a line another baseline wrote for the same code is not this measure's history
    lines += [{"at": str(r.get("at")), "text": f"{r.get('by')}: {r.get('what')}"} for r in (v or {}).get(f"measure:{k['id']}", [])
              if isinstance(r, dict) and (r.get("ref") == bid or not B.is_id(r.get("ref")))]
    lines.sort(key=lambda x: x["at"])
    return [{"v": n + 1, "at": x["at"][:10], "text": x["text"]} for n, x in enumerate(lines)]


def entry_view(plane, bid: str, code: str, viewer: C.Viewer) -> dict:
    code = next((r["merged_into"] for r in register(plane, bid) if r["code"] == code and r.get("merged_into")), code)  # a retired code redirects
    sees = ST.sees_for(viewer)
    k = next((x for x in K.read_kpis(plane, bid) if x["id"] == code), None)
    if k is None or not sees(k):
        raise Refused(404, "We could not find that measure.")
    reg = _find(live(register(plane, bid)), code)
    shown, _ = ST.catalogue_for(plane, bid, viewer)
    names, hidden = T.row_names(shown), ST.hidden_terms(plane, bid, viewer, sees)
    base = ST.definition_view(next(x for x in ST.read_with_notes(plane, bid) if x["id"] == code), names, hidden)
    gov = GS._read(plane, bid).get(code)
    feed = T.feeding(shown, code)
    fields = [{"id": T._rid(f, "fields"), "name": C.text_of(f.get("Field name as in the source") or f.get("What to extract")),
               "class": C.text_of(f.get("Personal data class")) or None} for f in feed["fields"]]
    acc = accepted_unknown(plane, bid).get(code)
    own = owners_of(k, gov, source_owner(plane, bid, code))
    trail = _trail(plane, bid, k)
    items = [a for a in SA.listing(plane, bid, viewer, sees) if a.get("kpi_id") == code]
    d = T.text_of(k.get("definition")) if isinstance(k.get("definition"), dict) and k["definition"].get("mark") != "unknown" else ""
    return {"code": code, "label": reg["label"], "aliases": reg["aliases"], "node": f"measure:{code}", "state": state_of(k, acc), "state_label": STATE_WORDS[state_of(k, acc)],
            "version": max(1, len(trail)), "parts": base["parts"], "complete": base["complete"], "missing": base["missing"], "confirmed": base["confirmed"],
            "sent_back": base["sent_back"], "business_definition": d or None, "owners": own,
            "sources": [{"id": T._rid(s, "sources"), "name": C.text_of(s.get("Source name")), "owner": C.text_of(s.get("Data owner")) or None} for s in feed["sources"]],
            "fields": fields, "personal_class": max((f["class"] for f in fields if f["class"]), default=None, key=lambda c: _CLASS_RANK.get(c, 0)),
            "may_see": ((gov or {}).get("may_see") or {}).get("value") if (gov or {}).get("may_see", {}).get("mark") != "unknown" else None,
            "accepted": acc, "questions": items, "trail": trail, "priority": k.get("priority"),
            "can_confirm": ST.is_data_owner(k, viewer.account_id, lambda n: C.norm(n) == C.norm(viewer.name) and not viewer.shared_name) and not base["missing"]}


_CLASS_RANK = {"Neither": 0, "Personal": 1, "Sensitive": 2}


# ---- the charter page (Screen C), read only ----------------------------------------------------------------------------------

def charter_view(plane, bid: str, viewer: C.Viewer) -> dict:
    if B.read_baseline(plane, bid) is None:
        raise Refused(404, NO_BASELINE)
    reg, acc, gov = {r["code"]: r for r in live(register(plane, bid))}, accepted_unknown(plane, bid), GS._read(plane, bid)
    shown, _ = ST.catalogue_for(plane, bid, viewer)
    cols = ST.columns(plane, bid, viewer)["kpis"]
    rows = []
    for k in _can_see(plane, bid, viewer):
        if k["id"] not in reg:
            continue
        feed, c = T.feeding(shown, k["id"]), T.confirmed(k)
        classes = [C.text_of(f.get("Personal data class")) for f in feed["fields"] if C.text_of(f.get("Personal data class"))]
        t = cols.get(k["id"], {})
        rows.append({"code": k["id"], "label": reg[k["id"]]["label"], "sources": t.get("sources", ""), "fields": t.get("fields", ""), "field_count": len(feed["fields"]),
                     "calculation": (t.get("calculation") or "").splitlines()[0] if t.get("calculation") else "", "period": t.get("period", ""), "currency": t.get("currency_basis", ""),
                     "personal_class": max(classes, key=lambda x: _CLASS_RANK.get(x, 0)) if classes else None,
                     "owners": {x: v for x, v in owners_of(k, gov.get(k["id"]), source_owner(plane, bid, k["id"])).items() if x != "confirmed"},
                     "state": state_of(k, acc.get(k["id"])), "version": len(_trail(plane, bid, k)) or 1,
                     "confirmed_by": c and c.get("by"), "confirmed_at": c and str(c.get("at"))[:10]})
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    who = next((v["by"] for v in acc.values()), None)
    foot = (f"{counts['confirmed']} of {len(rows)} confirmed; {counts['unknown_accepted']} unknown accepted" + (f" by {who}" if who and counts["unknown_accepted"] else "")
            + f"; {len(rows) - counts['confirmed'] - counts['unknown_accepted']} not confirmed") if rows else "Not available yet: no measures in the code register."
    return {"measures": rows, "footer": foot, "counts": counts,
            "empty": None if rows else "The catalogue has not been confirmed yet. Charter cannot be signed as build-ready."}


# ---- governed state (spec 31) -------------------------------------------------------------------------------------------------

def _missing_words(state: dict) -> list[str]:
    return [FIELD_WORDS[f] for f in G.FIELDS if state[f].get("mark") != "stated"]


def owner_slots(k: dict, state: dict, profile: dict, viewer: C.Viewer) -> dict:
    """Spec 31: the business owner confirms the business slot, the data owner the data slot; the head of data may confirm either. The source
    slot is read from the data sources tab, so nobody confirms it here. The organiser confirms nothing for others."""
    head = G.head_of_data(profile, viewer)
    cell = state.get("owners") or {}
    said = cell.get("value") if cell.get("mark") == "stated" and isinstance(cell.get("value"), dict) else {}
    def named(role: str) -> bool:
        c = (k.get("owners") or {}).get(role) or {}
        return (c.get("mark") != "unknown" and G._is(viewer, C.value_of(c), c.get("account_id"))) or G._is(viewer, said.get(role))
    return {**{r: head or named(r) for r in ("business", "data")}, "source": False}


def governed_view(plane, bid: str, viewer: C.Viewer) -> dict:
    """The strip, a ring and a card per measure, all counted from governed_state.json. What the person may confirm is worked out per field."""
    out = GS.governed_for(plane, bid, viewer)
    prof, kp = profile_store.raw(plane), {k["id"]: k for k in K.read_kpis(plane, bid)}
    rows = []
    for r in out["measures"]:
        st, can = r["state"], {}
        for f in G.FIELDS:
            try:
                G.check_confirm(f, kp[r["id"]], prof, viewer)
                can[f] = True
            except C.CatalogueError:
                can[f] = False
        slots = owner_slots(kp[r["id"]], st, prof, viewer)
        can["owners"] = any(slots.values())  # the whole cell is confirmed one slot at a time
        rows.append({"id": r["id"], "name": r["name"], "priority": kp[r["id"]].get("priority"), "state": st, "complete": r["complete"], "slots": slots,
                     "n": sum(1 for f in G.FIELDS if st[f].get("mark") == "stated"), "needs": _missing_words(st), "missing": r["missing"], "can_confirm": can,
                     "proposals": {f: p for f, p in (st.get("proposals") or {}).items() if not p.get("declined")},
                     "owners": owners_of(kp[r["id"]], st)})
    m = len(rows)
    count = lambda f: sum(1 for r in rows if r["state"][f].get("mark") == "stated")  # noqa: E731
    strip = {name: {"n": count(f), "of": m, "pct": round(100 * count(f) / m)} for name, f in (("owned", "owners"), ("classified", "classification"),
             ("may_see_confirmed", "may_see"), ("team_assigned", "resolving"))} if m else None
    must = [r for r in rows if r["priority"] == "must"]
    should = [r for r in rows if r["priority"] != "must"]
    waiting = sorted({o for r in rows for o in (r["owners"]["business"], r["owners"]["data"]) if o and not r["owners"]["confirmed"]})
    return {"baseline_id": bid, "measures": rows, "strip": strip, "empty": None if m else "Governed: Not available yet. No measures have been named in this Initiative.",
            "must": {"n": sum(1 for r in must if r["complete"]), "of": len(must)}, "should": {"n": sum(1 for r in should if r["complete"]), "of": len(should)},
            "not_governed": [{"id": r["id"], "name": r["name"], "needs": r["needs"]} for r in must if not r["complete"]],
            "waiting_on": waiting, "refusal": G.REFUSED}


def propose(plane, bid: str, code: str, field: str, value, reason: str, viewer: C.Viewer, initiative_id: str | None = None) -> dict:
    """A later Initiative proposes a change beside a stated cell; the cell stays until the person named for it applies the proposal."""
    kp = next((k for k in _can_see(plane, bid, viewer) if k["id"] == code), None)
    if kp is None:
        raise Refused(404, "We could not find that measure.")
    if field not in G.FIELDS or not " ".join(str(reason or "").split()):
        raise Refused(422, "Choose the part and give a reason.")
    if not ({"company_admin", "analyst"} & viewer.roles or G.named_owner(kp, viewer)):
        raise Refused(403, "Only the organiser, the analyst or a named owner can propose a change.")
    try:
        new = G.clean(field, value)
        if field == "owners":  # a slot left out stays out: applying it keeps that slot's current name
            new = {r: v for r, v in new.items() if r in value}
        with lock_for(GS._file(plane, bid)):
            GS._editable(plane, bid)
            doc = GS._read(plane, bid)
            entry = {**G.blank(), **doc.get(code, {})}
            if entry[field].get("mark") != "stated":
                raise Refused(409, "Nothing is confirmed for this part yet. Confirm it instead of proposing a change.")
            entry["proposals"] = {**(entry.get("proposals") or {}), field: {"value": new, "reason": " ".join(reason.split()), "by": viewer.name, "at": _now(), "initiative_id": initiative_id}}
            doc[code] = entry
            B.write_file(GS._file(plane, bid), doc)
    except (C.CatalogueError, B.Locked) as e:
        raise Refused(422 if isinstance(e, C.CatalogueError) else 409, getattr(e, "message", str(e))) from None
    return entry


def withdraw(plane, bid: str, code: str, field: str, viewer: C.Viewer) -> dict:
    with lock_for(GS._file(plane, bid)):
        GS._editable(plane, bid)
        doc = GS._read(plane, bid)
        p = ((doc.get(code) or {}).get("proposals") or {}).get(field)
        if not p:
            raise Refused(404, "There is no proposal to withdraw.")
        if C.norm(p["by"]) != C.norm(viewer.name):
            raise Refused(403, "Only the person who proposed it can withdraw it.")
        del doc[code]["proposals"][field]
        B.write_file(GS._file(plane, bid), doc)
        return doc[code]


def decide(plane, bid: str, code: str, field: str, decision: str, reason: str | None, viewer: C.Viewer) -> dict:
    """Apply or decline: the same who-may-confirm check as a confirmation. Applying keeps the old cell in `history`."""
    kp = next((k for k in _can_see(plane, bid, viewer) if k["id"] == code), None)
    if kp is None:
        raise Refused(404, "We could not find that measure.")
    try:
        G.check_confirm(field, kp, profile_store.raw(plane), viewer)
    except C.CatalogueError as e:
        raise Refused(403, e.message) from None
    if decision not in ("apply", "decline") or (decision == "decline" and not " ".join(str(reason or "").split())):
        raise Refused(422, "Choose apply or decline, and give a reason to decline.")
    with lock_for(GS._file(plane, bid)):
        GS._editable(plane, bid)
        doc = GS._read(plane, bid)
        entry = {**G.blank(), **doc.get(code, {})}
        p = (entry.get("proposals") or {}).get(field)
        if not p or p.get("declined"):
            raise Refused(404, "There is no proposal waiting for this part.")
        if decision == "apply":  # applying an owners proposal follows the per-slot rule (F12)
            try:
                G.check_confirm(field, kp, profile_store.raw(plane), viewer, p["value"], entry.get("owners"))
            except C.CatalogueError as e:
                raise Refused(403, e.message) from None
        if decision == "decline":
            p["declined"] = {"by": viewer.name, "at": _now(), "reason": " ".join(reason.split())}
        else:
            hist = {**(entry.get("history") or {})}
            hist[field] = [*hist.get(field, []), {"cell": entry[field], "replaced_at": _now(), "replaced_by": viewer.name, "initiative_id": p.get("initiative_id")}]
            entry["history"] = hist
            got = G.clean(field, p["value"], stated=True)
            if field == "owners":
                now = (entry[field].get("value") or {}) if isinstance(entry[field].get("value"), dict) else {}
                got = {r: (got[r] if r in p["value"] else now.get(r)) for r in got}
            entry[field] = G.person_cell(got, viewer.name)
            del entry["proposals"][field]
        doc[code] = entry
        B.write_file(GS._file(plane, bid), doc)
        if decision == "apply" and field == "owners" and isinstance(p.get("value"), dict):
            GS.sync_owners(plane, bid, code, {r: v for r, v in (entry["owners"]["value"] or {}).items() if r in p["value"]}, viewer.name)
        return entry


# ---- routes (/api/intents/{id}/...) ---------------------------------------------------------------------------------------------

def _slots(intent: dict) -> list:
    p = intent.get("people") or {}
    return [p.get(s) for s in ("organiser", "sponsor", "decider", "owner", "reporter")] + [x for s in ("participants", "advisers", "observers") for x in p.get(s) or []] \
        + ([x for x in p.get("affected") or []] if intent.get("affected_may_read") else [])


def _is(slot, viewer: C.Viewer) -> bool:
    ids = [slot.get(x) for x in ("account", "account_id", "id", "name")] if isinstance(slot, dict) else [slot]
    return any(i and (i == viewer.account_id or (not viewer.shared_name and C.norm(i) == C.norm(viewer.name))) for i in ids)


def baseline_of(plane, intent_id: str, viewer: C.Viewer) -> str:
    """The baseline an Initiative works in, by reference. A draft is the creator's alone; content opens to participants and observers only."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", intent_id or ""):
        raise Refused(404, "We could not find that.")
    path = plane.path("intents", intent_id, "intent.json")
    intent = read_json_strict(path, dict) if path.exists() else None
    if not intent or not (any(_is(s, viewer) for s in _slots(intent)) if intent.get("state") != "draft" else _is(intent.get("created_by"), viewer)):
        raise Refused(404, "We could not find that.")
    ids = (intent.get("refs") or {}).get("baseline_ids") or []
    if not ids:
        raise Refused(404, NO_BASELINE)
    return str(ids[-1])


def _answer(fn):
    def inner(request: Request, intent_id: str, *a, **kw):
        try:
            plane, viewer = _plane(request), _viewer(request)
            return fn(plane, baseline_of(plane, intent_id, viewer), viewer, *a, **kw)
        except Refused as e:
            return JSONResponse({"error": "refused", "message": e.message}, status_code=e.status)
        except (C.CatalogueError, B.StoreError) as e:
            return JSONResponse({"error": "refused", "message": getattr(e, "message", str(e))}, status_code=403 if getattr(e, "code", "") == "forbidden" else 409)
    inner.__name__ = fn.__name__
    return inner


@router.get("/api/intents/{intent_id}/catalogue")
def get_catalogue(request: Request, intent_id: str, owner: str | None = None):
    def go(p, b, v):
        tidy(request, p, b)
        return catalogue_view(p, b, v, owner == "me")
    return _answer(go)(request, intent_id)


@router.get("/api/intents/{intent_id}/catalogue/entry/{code}")
def get_entry(request: Request, intent_id: str, code: str):
    def go(p, b, v):
        tidy(request, p, b)
        return entry_view(p, b, code, v)
    return _answer(go)(request, intent_id)


def _planner(viewer: C.Viewer) -> None:
    if not ({"company_admin", "analyst"} & viewer.roles):
        raise Refused(403, "Only the organiser or the analyst can change the list of measures.")


@router.post("/api/intents/{intent_id}/catalogue/measures")
def post_measure(request: Request, intent_id: str, body: dict = Body(default_factory=dict)):
    def go(p, b, v):
        _planner(v)
        row = mint(p, b, body.get("label"), v.name, body.get("from"), body.get("different"), body.get("priority") or "should")
        tidy(request, p, b)
        return row
    return _answer(go)(request, intent_id)


@router.post("/api/intents/{intent_id}/catalogue/measures/{code}/alias")
def post_alias(request: Request, intent_id: str, code: str, body: dict = Body(default_factory=dict)):
    def go(p, b, v):
        _planner(v)
        return set_label(p, b, code, body["label"], v.name) if body.get("label") else add_alias(p, b, code, body.get("alias"), v.name)
    return _answer(go)(request, intent_id)


@router.post("/api/intents/{intent_id}/catalogue/measures/{code}/merge")
def post_merge(request: Request, intent_id: str, code: str, body: dict = Body(default_factory=dict)):
    def go(p, b, v):
        _planner(v)
        return merge(p, b, code, str(body.get("retire") or ""), v.name)
    return _answer(go)(request, intent_id)


@router.get("/api/intents/{intent_id}/charter/catalogue")
def get_charter_catalogue(request: Request, intent_id: str):
    return _answer(lambda p, b, v: charter_view(p, b, v))(request, intent_id)


@router.get("/api/intents/{intent_id}/governed")
def get_governed(request: Request, intent_id: str, redraft: str | None = None):
    """`redraft=<measure code>`: "Ask Lens to draft again" for the organiser and the analyst (spec 31). It runs the governed draft again, which keeps every
    stated cell, and Lens's own draft of that measure; the answer says how many parts Lens drafted. (A read with this one effect so no new route is needed.)"""
    def go(p, b, v):
        have = GS._read(p, b)
        signed = B.read_baseline(p, b)["state"] == "signed"
        if redraft and not signed:
            if not ({"company_admin", "analyst"} & v.roles):
                raise Refused(403, "Only the organiser or the analyst can ask Lens to draft again.")
            ensure_draft(request, b)
            lens.draft_for(p, intent_id, "governed_state", redraft, rt=lens.runtime_for_request(request, p), retry=True)
        elif not signed and any(k["id"] not in have for k in K.read_kpis(p, b)):
            ensure_draft(request, b)  # Lens's first look covers a measure added since; a stated cell is never replaced
        tidy(request, p, b)
        out = governed_view(p, b, v)
        if redraft:
            row = next((m for m in out["measures"] if m["id"] == redraft), None)
            out["redrafted"] = {"id": redraft, "n": sum(1 for f in G.FIELDS if row["state"][f].get("mark") == "guessed")} if row else None
        return out
    return _answer(go)(request, intent_id)


@router.post("/api/intents/{intent_id}/governed/{measure}/propose")
def post_propose(request: Request, intent_id: str, measure: str, body: dict = Body(default_factory=dict)):
    return _answer(lambda p, b, v: propose(p, b, measure, str(body.get("field")), body.get("value"), body.get("reason"), v, intent_id))(request, intent_id)


@router.post("/api/intents/{intent_id}/governed/{measure}/withdraw")
def post_withdraw(request: Request, intent_id: str, measure: str, body: dict = Body(default_factory=dict)):
    return _answer(lambda p, b, v: withdraw(p, b, measure, str(body.get("field")), v))(request, intent_id)


@router.post("/api/intents/{intent_id}/governed/{measure}/proposal/{field}/decide")
def post_decide(request: Request, intent_id: str, measure: str, field: str, body: dict = Body(default_factory=dict)):
    return _answer(lambda p, b, v: decide(p, b, measure, field, str(body.get("decision")), body.get("reason"), v))(request, intent_id)
