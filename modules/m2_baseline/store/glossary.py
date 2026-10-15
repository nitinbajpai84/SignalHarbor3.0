"""The baseline's glossary file: intents/m2_baseline/<baseline id>/glossary.json (M2-E2), written with sh_platform.jsonfile like every other
module 2 file (atomic write, strict read, lock_for). Shape:

{baseline_version, provided: {title, filename, doc_id, by, at, truncated, terms: [{term, definition, aliases, owner, frequency, source}]} | null,
 entries: [one per measure, domain/glossary.py], matches: {term key: kpi id} found by meaning, unmatched_terms: [{term, definition}]}

`baseline_version` is the sign-off version the working copy was last written for. A signed baseline is read-only (Locked). The caller says who
may see which measure (`sees(kpi)`, the work list's rule); a measure a person may not see is never in what this module hands back to them.
`glossary_ready` is what the sign-off gate (M2-E4) calls.
"""
import hashlib
import json
import logging
from typing import Callable

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import glossary as G
from modules.m2_baseline.domain import preread as PR
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import kpis as K
from sh_platform.context_docs import documents_for
from sh_platform.context_docs.store import DocStore
from sh_platform.jsonfile import lock_for, read_json_strict

log = logging.getLogger(__name__)

FILE = "glossary.json"
NO_ENTRY = "We could not find that entry."


def _path(plane, baseline_id):
    return B.root(plane) / baseline_id / FILE


def read(plane, baseline_id: str) -> dict:
    """The stored glossary; an empty one when it has not been built. StoreError when the file is damaged."""
    doc = B.read_file(_path(plane, baseline_id), dict) if B.is_id(baseline_id) else None
    return {"baseline_version": 1, "provided": None, "entries": [], "matches": {}, "unmatched_terms": [], "rejected": [], "asked": None, "documents": [], "restricted_kept": 0, **(doc or {})}


def _version(plane, baseline_id) -> int:
    try:
        versions = (read_json_strict(B.root(plane) / baseline_id / "signoff.json", dict) or {}).get("versions") or [{}]
    except (OSError, ValueError):
        raise B.StoreError(B.UNREADABLE) from None
    return int(versions[-1].get("version") or 1)


def _editable(plane, baseline_id) -> None:
    base = B.read_baseline(plane, baseline_id)
    if base is None:
        raise LookupError("no baseline")
    if base["state"] == "signed":
        raise B.Locked(B.LOCKED)


def _save(plane, baseline_id, doc: dict) -> None:
    B.write_file(_path(plane, baseline_id), {**doc, "baseline_version": _version(plane, baseline_id)})


# Matcher: ([unmatched terms], [unmatched measure names]) -> {term index: measure index}. The API gives the model call; tests give a stub.
Matcher = Callable[[list[str], list[str]], dict[int, int] | None]  # None: the model could not be reached


def build(plane, baseline_id: str, sees: Callable[[dict], bool], matcher: Matcher | None = None, provided: dict | None = None,
          at: str | None = None) -> dict:
    """Build or update the glossary from the measures (and a provided glossary: a new one in `provided`, else the one already kept).
    Exact name and alias matches are found in code; the unmatched terms and the unmatched measures this person may see go to `matcher`
    once. A person's decision is kept; a ambiguity found is added to the measure. Returns the stored glossary.
    ponytail: the lock is held during the model call; a per-baseline queue if two people build at once ever waits too long."""
    with lock_for(_path(plane, baseline_id)):
        _editable(plane, baseline_id)
        out, raised = _build(plane, baseline_id, sees, matcher, provided, at)
    for kid, items in raised.items():
        K.change(plane, baseline_id, kid, lambda k, items=items: A.with_ambiguities(k, items))
    sync_documents(plane, baseline_id)
    return out


def _build(plane, baseline_id, sees, matcher, provided, at, cur: dict | None = None):
    """The work of `build`, under the caller's lock: (the stored glossary, the ambiguities to add)."""
    if True:
        kpis, cur = K.read_kpis(plane, baseline_id), cur or read(plane, baseline_id)
        rejected = {(r["kpi_id"], r["term_key"]) for r in cur.get("rejected", [])}
        doc = provided if provided is not None else cur["provided"]
        terms = doc["terms"] if doc else []
        kept = {} if provided is not None else cur["matches"]
        aliases = {} if provided is not None else {e["kpi_id"]: [a for a in G.text_of(e["aliases"]).split("; ") if a] for e in cur["entries"]}
        found = {k: (i, "name") for k, i in G.code_matches(kpis, terms, aliases, rejected).items()}
        by_id = {k["id"]: k for k in kpis}
        taken = {i for i, _ in found.values()}
        # what the model's answer depends on: the file's terms (in a fixed order) and the measures this person may see
        sig = hashlib.sha1(json.dumps([sorted(G.key(t["term"]) for t in terms), [[k["id"], k["name"]] for k in kpis if sees(k)]]).encode()).hexdigest()
        asked = cur.get("asked")
        if asked and asked.get("sig") == sig:  # the same file and measures: the model's earlier answer is reused, never asked again
            kept = {**kept, **asked["pairs"]}
        for i, t in enumerate(terms):  # a match by meaning an earlier build found stays
            kid = kept.get(G.key(t["term"]))
            if i not in taken and kid in by_id and kid not in found and (kid, G.key(t["term"])) not in rejected:
                found[kid] = (i, "meaning")
                taken.add(i)
        meaning = {G.key(terms[i]["term"]): kid for kid, (i, how) in found.items() if how == "meaning"}
        loose_t = [i for i in range(len(terms)) if i not in taken]
        loose_k = [k for k in kpis if k["id"] not in found and sees(k)]
        loose_t.sort(key=lambda i: G.key(terms[i]["term"]))  # a fixed order: the same file and measures always send the same question
        if matcher and loose_t and loose_k and not (asked and asked.get("sig") == sig):
            got = matcher([terms[i]["term"] for i in loose_t], [k["name"] for k in loose_k])
            if got is not None:  # None: the model could not be reached, so nothing is kept and the next build asks again
                for ti, mi in sorted(got.items()):
                    if not (0 <= ti < len(loose_t) and 0 <= mi < len(loose_k)) or loose_t[ti] in taken or loose_k[mi]["id"] in found:
                        continue
                    if (loose_k[mi]["id"], G.key(terms[loose_t[ti]]["term"])) not in rejected:
                        found[loose_k[mi]["id"]] = (loose_t[ti], "meaning")
                        meaning[G.key(terms[loose_t[ti]]["term"])] = loose_k[mi]["id"]
                        taken.add(loose_t[ti])
                asked = {"sig": sig, "pairs": dict(meaning)}
        if asked and asked.get("sig") == sig:
            asked = {"sig": sig, "pairs": {t: kid for t, kid in asked["pairs"].items() if (kid, t) not in rejected}}  # a pair a person undid is dropped too
        entries, raised = G.build_entries(kpis, terms, found, doc["title"] if doc else "", cur["entries"], at)
        out = {**cur, "provided": doc, "entries": entries, "matches": meaning, "asked": asked,
               "unmatched_terms": [{"term": t["term"], "definition": t["definition"]} for i, t in enumerate(terms) if i not in taken]}
        _save(plane, baseline_id, out)
        return out, raised


def refresh_governance(plane, baseline_id: str) -> None:
    """Who may see each entry, and whether it is personal, are read from the measures' governance (the one place they are decided). Called after
    every governance change and before the glossary is fingerprinted for signing, so the signed glossary and catalogue agree. A signed baseline
    is left as it is, and so is an entry that already says the same."""
    with lock_for(_path(plane, baseline_id)):
        base = B.read_baseline(plane, baseline_id)
        doc = read(plane, baseline_id)
        if base is None or base["state"] == "signed" or not doc["entries"]:
            return
        by_id, changed = {k["id"]: k.get("governance") or {} for k in K.read_kpis(plane, baseline_id)}, False
        for e in doc["entries"]:
            gov = by_id.get(e["kpi_id"])
            if gov is None:
                continue
            fresh = {"who_may_see": list(gov.get("may_see") or []), "personal": gov.get("personal", "not_sure"), "sensitive": bool(gov.get("sensitive"))}
            if any(e.get(f) != v for f, v in fresh.items()):
                e.update(fresh)
                changed = True
        if changed:
            _save(plane, baseline_id, doc)
    if changed:
        sync_documents(plane, baseline_id)  # what Lens may read follows the same change


def seen(plane, baseline_id: str, sees: Callable[[dict], bool]) -> list[dict]:
    """The entries of the measures this person may see, in the measures' order."""
    by_id = {k["id"]: k for k in K.read_kpis(plane, baseline_id)}
    return [e for e in read(plane, baseline_id)["entries"] if e["kpi_id"] in by_id and sees(by_id[e["kpi_id"]])]


def view(plane, baseline_id: str, sees: Callable[[dict], bool]) -> dict:
    """What the screen is drawn from, for this person: their entries, a stub (id and "A restricted measure") for the others, the counts of
    theirs, what is only in the provided glossary, and whether measures are waiting to be added."""
    kpis, doc = K.read_kpis(plane, baseline_id), read(plane, baseline_id)
    by_id, have = {k["id"]: k for k in kpis}, {e["kpi_id"] for e in doc["entries"]}
    rows, mine = [], []
    for e in doc["entries"]:
        if e["kpi_id"] not in by_id:
            continue
        if sees(by_id[e["kpi_id"]]):  # a measure the person may not see is not in the answer at all: no stub, no id, no count
            mine.append(e)
            rows.append({**e, "text": G.flat(e)})
    p = doc["provided"]
    return {"built": bool(doc["entries"]), "entries": rows, "counts": G.counts(mine), "unmatched_terms": _unmatched(doc, kpis, sees), "restricted_kept": doc.get("restricted_kept", 0) if all(sees(k) for k in kpis) else 0,
            "provided": {k: p[k] for k in ("title", "filename", "by", "at", "truncated")} if p else None,
            "waiting": sum(1 for k in kpis if k["id"] not in have and sees(k)), "baseline_version": doc["baseline_version"]}


DOC_OPEN = "Business glossary"


def _line(t: dict) -> str:
    extra = [f"{label}: {t[f]}" for f, label in (("owner", "Owner"), ("frequency", "How often reported")) if t.get(f)]
    also = [f"Also called: {'; '.join(t['aliases'])}"] if t.get("aliases") else []
    return " ".join([f"{t['term']}: {t['definition']}".rstrip(": "), *also, *extra])


def sync_documents(plane, baseline_id: str) -> None:
    """What Lens may read of the provided glossary: ONE company context document, rebuilt from the parsed terms (never the raw file), of the
    terms matched to measures that are NOT restricted (checked over every measure of the baseline, not one person's view). Unmatched terms are
    in it only when the baseline has no restricted measure. Everything else stays in glossary.json and is never a company document.
    Called after every build, so a measure that becomes restricted (or is relaxed) moves its wording the next time. Fails closed: an earlier
    document is marked restricted before it is deleted, and one that could not be deleted keeps its id here and is retried next time."""
    with lock_for(_path(plane, baseline_id)):
        doc, store = read(plane, baseline_id), DocStore(plane)
        kpis = K.read_kpis(plane, baseline_id)
        stuck = []
        try:  # an organiser's "not personal data" belongs to the content: the fingerprints of the earlier documents she cleared
            scan = LS.scans(plane)
            cleared = {scan[d["doc_id"]]["sha"] for d in documents_for(plane, "lens", restricted_ok=True)
                       if d["doc_id"] in doc.get("documents", []) and (scan.get(d["doc_id"]) or {}).get("state") == PR.CLEARED and scan[d["doc_id"]].get("sha")}
        except (B.StoreError, OSError, ValueError):
            cleared = set()
        for old in doc.get("documents", []):
            shelf = next((a for a in ("lens", "north") if store._file(a, old).exists()), None)  # an earlier build filed it under North
            if shelf is None:
                continue  # already gone
            try:
                store.set_restricted(shelf, old, True)  # first closed, then removed
            except (OSError, ValueError):
                log.warning("an earlier glossary document could not be restricted")
            try:
                store.delete(shelf, old)
            except FileNotFoundError:
                pass
            except (OSError, ValueError):
                log.warning("an earlier glossary document could not be removed; it stays restricted and is retried")
                stuck.append(old)  # never forget an id that still exists
        p, parts = doc["provided"], {False: [], True: []}
        if p:
            restricted = {k["id"] for k in kpis if W.treated_as_personal(k["governance"]) or k["governance"].get("sensitive")}
            owner = {G.key(e["matched_term"]): e["kpi_id"] for e in doc["entries"] if e.get("matched_term")}
            for t in p["terms"]:
                kid = owner.get(G.key(t["term"]))
                parts[(kid in restricted) if kid else bool(restricted)].append(_line(t))
        ids = []
        if parts[False]:
            try:
                ids.append(store.upload("lens", p["by"], "glossary.txt", "\n".join(parts[False]).encode("utf-8"), title=p["title"],
                                        description=DOC_OPEN, visibility="shared_full", restricted=False)["doc_id"])
                fresh = next((d for d in documents_for(plane, "lens", restricted_ok=True) if d["doc_id"] == ids[-1]), None)
                if fresh and PR.text_hash(fresh) in cleared:  # the same content as one she cleared: the decision carries over
                    LS.set_scan(plane, ids[-1], {"words": [], "state": PR.CLEARED, "sha": PR.text_hash(fresh)})
            except (OSError, ValueError, B.StoreError):
                log.warning("the glossary could not be kept as a company document")
        doc["documents"], doc["restricted_kept"] = stuck + ids, len(parts[True])
        B.write_file(_path(plane, baseline_id), doc)


def _unmatched(doc: dict, kpis: list[dict], sees) -> list[dict]:
    """The provided terms no measure matched. A term may be about a measure this person may not see, so only someone who sees every
    measure is shown them; for everyone else the list is empty, with no count."""
    return doc["unmatched_terms"] if all(sees(k) for k in kpis) else []


def rows_for_download(plane, baseline_id: str, sees: Callable[[dict], bool]) -> tuple[list[dict], list[dict]]:
    """(flat rows of the measures this person may see, the terms only in the provided glossary). Hidden measures are left out, never named."""
    return [G.flat(e) for e in seen(plane, baseline_id, sees)], _unmatched(read(plane, baseline_id), K.read_kpis(plane, baseline_id), sees)


def _change_entry(plane, baseline_id: str, kpi_id: str, sees, edit: Callable[[dict], dict]) -> None:
    with lock_for(_path(plane, baseline_id)):
        _editable(plane, baseline_id)
        doc = read(plane, baseline_id)
        kpi = next((k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id), None)
        i = next((n for n, e in enumerate(doc["entries"]) if e["kpi_id"] == kpi_id), None)
        if kpi is None or i is None or not sees(kpi):
            raise LookupError(NO_ENTRY)  # a measure the person may not see answers like one that does not exist
        doc["entries"][i] = edit(doc["entries"][i])
        _save(plane, baseline_id, doc)


def decide(plane, baseline_id: str, kpi_id: str, sees, choice: str, text: str, by: str) -> None:
    if choice == G.NOT_SAME:
        return reject_match(plane, baseline_id, kpi_id, sees)
    _change_entry(plane, baseline_id, kpi_id, sees, lambda e: G.decide(e, choice, text, by))
    if choice in ("provided", "edited"):  # the measure's own definition says the same: work list, catalogue and glossary agree
        value = G.text_of(next(e for e in read(plane, baseline_id)["entries"] if e["kpi_id"] == kpi_id)["business_definition"])
        K.change(plane, baseline_id, kpi_id, lambda k: G.with_chosen_definition(k, value, by))


def reject_match(plane, baseline_id: str, kpi_id: str, sees) -> None:
    """"This is not the same thing": the provided term is no longer this measure's. The term goes back to the unmatched list, the entry is
    new again (its decision and review are dropped), the ambiguities that match raised are removed, and a rebuild never matches the pair again."""
    with lock_for(_path(plane, baseline_id)):
        _editable(plane, baseline_id)
        doc = read(plane, baseline_id)
        kpi = next((k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id), None)
        e = next((x for x in doc["entries"] if x["kpi_id"] == kpi_id), None)
        if kpi is None or e is None or not sees(kpi) or not e.get("matched_term"):
            raise LookupError(NO_ENTRY)
        doc["rejected"] = [*doc.get("rejected", []), {"kpi_id": kpi_id, "term_key": G.key(e["matched_term"])}]
        doc["entries"] = [{k: v for k, v in x.items() if k not in ("decided", "reviewed", "proposal")} if x["kpi_id"] == kpi_id else x for x in doc["entries"]]
        _build(plane, baseline_id, sees, None, None, None, doc)
    where = f"Business glossary: {kpi['name']}"
    sync_documents(plane, baseline_id)
    K.change(plane, baseline_id, kpi_id, lambda k: {**k, "ambiguities": [a for a in k.get("ambiguities") or []
                                                                      if not (a.get("where") == where and a.get("raised_by") == "Lens" and a.get("status") == "open")]})


def review(plane, baseline_id: str, kpi_id: str, sees, by: str) -> None:
    _change_entry(plane, baseline_id, kpi_id, sees, lambda e: G.reviewed(e, by))


def review_unchanged(plane, baseline_id: str, sees, by: str) -> int:
    """Marks every unchanged entry this person may see as reviewed; changed and new ones are reviewed one by one. How many were marked."""
    with lock_for(_path(plane, baseline_id)):
        _editable(plane, baseline_id)
        doc, by_id, n = read(plane, baseline_id), {k["id"]: k for k in K.read_kpis(plane, baseline_id)}, 0
        for i, e in enumerate(doc["entries"]):
            if e["change"] == "unchanged" and not e.get("reviewed") and e["kpi_id"] in by_id and sees(by_id[e["kpi_id"]]):
                doc["entries"][i], n = G.reviewed(e, by), n + 1
        if n:
            _save(plane, baseline_id, doc)
        return n


def glossary_ready(plane, baseline_id: str) -> tuple[bool, list[str]]:
    """(ready, reasons in plain words) for the sign-off gate (M2-E4): every measure has an entry and every entry is reviewed. Whole baseline,
    not one person's view; reasons are counts and never name a measure."""
    have = {e["kpi_id"] for e in read(plane, baseline_id)["entries"]}
    kpis = K.read_kpis(plane, baseline_id)
    return G.glossary_ready([e for e in read(plane, baseline_id)["entries"] if e["kpi_id"] in {k["id"] for k in kpis}],
                            sum(1 for k in kpis if k["id"] not in have))
