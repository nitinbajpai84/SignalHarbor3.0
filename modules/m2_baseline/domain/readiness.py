"""Readiness for module 3 (M2-26) and the review view (M2-23). Pure Python: the rule and its wording are in
contracts/signoff.yaml. Nothing is invented: a blank is "not stated yet", never known (SHARED.md provenance).

Rule (deck slide 15, decided): every KPI has its three owners or is marked blocked, a stated source or "unknown", and the
sensing questions answered. Unknown is allowed but stays visible.
"""
import json
from functools import lru_cache
from pathlib import Path

import yaml

from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.questionnaire import BLANK, load_questionnaire, source_rows

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "contracts"


class ContractError(Exception):
    pass


def load_contract(name: str = "signoff.yaml", folder=None) -> dict:
    try:
        d = yaml.safe_load((Path(folder or DEFAULT_DIR) / name).read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("not a mapping")
        if name == "signoff.yaml":
            for k in ("parts", "countersign", "sponsor_roles", "tracking", "readiness", "audit_actions"):
                d[k]
        return d
    except (OSError, yaml.YAMLError, ValueError, KeyError):
        raise ContractError(f"{name} is not valid.") from None


def _text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


@lru_cache(maxsize=1)
def choice_fields() -> frozenset[str]:
    """The questions answered by picking from a list (tracked today, could track, data type). Only these can conflict."""
    return frozenset(k for k, f in load_questionnaire().fields.items() if f.get("kind") == "choice")


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _together(stated: list[dict]) -> str:
    """Free-text answers from different people, side by side: "Arjun: ...; Sara: ..."."""
    seen: list[tuple] = []
    for v in stated:
        item = (str(v.get("by") or "").strip(), str(v["value"]).strip())
        if item not in seen:
            seen.append(item)
    return "; ".join(f"{by}: {text}" if by else text for by, text in seen)


def conflict_options(values: list[dict], labels: dict | None = None) -> list[dict]:
    """The stated choices in a conflict, each with who gave it and its plain label: what a person settling it picks from."""
    labels = labels or {}
    return [{"value": v["value"], "label": labels.get(v["value"], str(v["value"])), "by": v.get("by")} for v in values
            if isinstance(v, dict) and v.get("mark") == "stated" and v.get("value") not in (None, "")]


def choice_labels(c: dict, field: str) -> dict:
    """Plain words for a choice answer: the tracking words of the contract for "tracked today", else the questionnaire's own."""
    if field == "tracked_today":  # the older yes / no answers read the same way (see _YES_NO)
        return {**c["tracking"], **{old: c["tracking"][new] for old, new in _YES_NO.items()}}
    return {x["value"]: x["label"] for x in load_questionnaire().fields.get(field, {}).get("choices", [])}


def best(values: list[dict], choice: bool = False, settled: dict | None = None) -> tuple[str, dict | None]:
    """One field across the answers given for a KPI: stated | unknown | conflict | pending. Free text from different
    owners is combined, never a conflict. Only a choice field can conflict, and then Lens never picks one (M2-24): a
    person settles it (`settled` = {"value": ...}) and both answers stay on record. A guess or a blank is still pending."""
    stated = [v for v in values if isinstance(v, dict) and v.get("mark") == "stated" and v.get("value") not in (None, "")]
    if stated:
        latest = max(stated, key=lambda v: str(v.get("at", "")))
        if all(_same(v["value"], stated[0]["value"]) for v in stated):
            return "stated", latest
        if not choice:
            return "stated", {**latest, "value": _together(stated)}
        if settled and any(_same(v["value"], settled.get("value")) for v in stated):
            return "stated", {**latest, "value": settled["value"]}
        return "conflict", None
    # an unknown from "not answered yet" is a blank the reader filled in, not someone saying "I don't know"
    unk = [v for v in values if isinstance(v, dict) and v.get("mark") == "unknown" and v.get("from") != BLANK]
    return ("unknown", unk[0]) if unk else ("pending", None)


def owner_of(kpi: dict, named: dict, owner_key: str) -> tuple[str, str | None]:
    """(named | no_owner | pending, name). A name the sponsor gave counts; a guessed or blank owner is still pending."""
    n = (named.get(kpi["id"]) or {}).get(owner_key)
    if n and _text(n.get("name")):
        return "named", n["name"]
    p = (kpi.get("owners") or {}).get(owner_key)
    if isinstance(p, dict):
        if p.get("mark") == "stated" and _text(p.get("value")):
            return "named", p["value"]
        if p.get("mark") == "unknown":
            return "no_owner", None
    return "pending", None


def answered(answers: list[dict], kpi_id: str, name) -> bool:
    """Whether this person gave a real answer for the measure, themselves or through a meeting (N-D): at least one field that
    is not blank. An explicit "I don't know" counts; a field never answered (from "not answered yet") does not."""
    fields = load_questionnaire().fields

    def real(v) -> bool:
        return isinstance(v, dict) and (v.get("mark") == "unknown" and v.get("from") != BLANK
                                        or v.get("mark") in ("stated", "guessed") and v.get("value") not in (None, "", []))
    return any(a.get("kpi_id") == kpi_id and " ".join(str(a.get("owner_name") or "").split()).casefold()
               == " ".join(str(name or "").split()).casefold() and any(real(a.get(f)) for f in fields) for a in answers)


def owner_account(kpi: dict, named: dict, owner_key: str) -> str | None:
    """The account id of the nominated owner, when the nomination carries one (`named[..].account_id`, or M2-P01's
    `owners.<role>.account_id`); None for a name-only nomination."""
    n = (named.get(kpi["id"]) or {}).get(owner_key)
    if n and _text(n.get("name")):
        return n.get("account_id")
    p = (kpi.get("owners") or {}).get(owner_key)
    return p.get("account_id") if isinstance(p, dict) and _text(p.get("account_id")) else None


def tracked_today(kpi: dict) -> bool:
    t = kpi.get("tracking")
    return isinstance(t, dict) and t.get("mark") == "stated" and t.get("value") == "tracked_now"


_YES_NO = {"yes": "tracked_now", "no": "not_tracked"}  # an older answer to "tracked today?"


def with_tracking(kpis: list[dict], answers: list[dict], version: dict, c: dict, mapped: dict | None = None) -> list[dict]:
    """The KPIs with their one tracking status (N-A). First the status someone set on the process map (`mapped` =
    process_map_tracking.json), then the KPI's own stated status, then what the owners answered to "tracked today?" (a real
    conflict between owners that nobody settled leaves it as it was). Everything that reads tracking (the review, readiness,
    the hand-off, "no next step needed") reads it from here."""
    out = []
    for k in kpis:
        if not (isinstance(k, dict) and k.get("id")):
            out.append(k)
            continue
        own, rec = k.get("tracking"), ((mapped or {}).get(k["id"]) or {}).get("status")
        if isinstance(rec, dict) and rec.get("mark") == "stated" and rec.get("value") in c["tracking"]:
            out.append({**k, "tracking": rec})
            continue
        if isinstance(own, dict) and own.get("mark") == "stated":
            out.append(k)
            continue
        said = [{**a["tracked_today"], "value": _YES_NO.get(a["tracked_today"].get("value"), a["tracked_today"].get("value"))}
                for a in answers if a.get("kpi_id") == k["id"] and isinstance(a.get("tracked_today"), dict)]
        st, v = best(said, True, ((version.get("settled") or {}).get(k["id"]) or {}).get("tracked_today"))
        out.append({**k, "tracking": prov(v["value"], "stated", v.get("by") or "", "the owners' answers", v.get("at"))}
                   if st == "stated" and v["value"] in c["tracking"] else k)
    return out


def _arrival(mine: list[dict]) -> list[dict]:
    """Each owner's stated arrival, from their own words: how often and when, for every system they named, without the
    system's name (that may belong to a restricted row). Falls back to the plain `arrival` answer."""
    labels = {c["value"]: c["label"] for r in load_questionnaire().fields["sources"]["row"] if r["key"] == "frequency" for c in r["choices"]}
    out = []
    for a in mine:
        said = []
        for r in source_rows(a):
            f, t = r.get("frequency") or {}, r.get("sla") or {}
            text = ", ".join(x for x in (labels.get(f.get("value"), f.get("value")) if f.get("mark") == "stated" else "",
                                         t.get("value") if t.get("mark") == "stated" else "") if x)
            if text and text not in said:
                said.append(text)
        got = a.get("arrival")
        if said:
            out.append({"value": "; ".join(said), "mark": "stated", "by": a.get("owner_name") or "", "at": (got or {}).get("at")})
        elif isinstance(got, dict):
            out.append({**got, "by": a.get("owner_name") or got.get("by")} if got.get("mark") == "stated" else got)
    return out


def _kpi(kpi: dict, answers: list[dict], version: dict, c: dict) -> dict:
    sensing_fields = c["readiness"]["sensing_fields"]
    named = version["named"]
    parts, pending, no_owner = [], [], []
    for part in c["parts"]:
        status, name = owner_of(kpi, named, part["owner"])
        got = (version["parts"].get(kpi["id"]) or {}).get(part["id"])
        parts.append({"id": part["id"], "label": part["label"], "owner_label": part["owner_label"], "owner_status": status,
                      "owner_name": name, "named_by_sponsor": bool((named.get(kpi["id"]) or {}).get(part["owner"])),
                      "confirmed": got,
                      "silent": status == "named" and not answered(answers, kpi["id"], name)})
        (pending if status == "pending" else no_owner if status == "no_owner" else []).append(part)
    mine = [a for a in answers if a.get("kpi_id") == kpi["id"]]
    settled = (version.get("settled") or {}).get(kpi["id"]) or {}
    waiting = list(dict.fromkeys(n for part in c["parts"] for s, n in [owner_of(kpi, named, part["owner"])]
                                 if s == "named" and not answered(answers, kpi["id"], n)))
    rev = version["review"].get(kpi["id"]) or {}
    accepted = bool(rev.get("accepted")) and not tracked_today(kpi)  # the sponsor accepted "unknown for now" with a plan
    src_status, src = best([a["source"] for a in mine if "source" in a])
    if accepted and src_status == "pending":
        src_status = "unknown"
    sensing = []
    for f in sensing_fields:
        given = _arrival(mine) if f["id"] == "arrival" else [a[f["id"]] for a in mine if f["id"] in a]
        st, v = best(given, f["id"] in choice_fields(), settled.get(f["id"]))
        if accepted and st == "pending":
            st = "unknown"
        said = {json.dumps(x["value"]) for x in given if isinstance(x, dict) and x.get("mark") == "stated" and x.get("value") not in (None, "")}
        words = choice_labels(c, f["id"])
        done = settled.get(f["id"]) if st == "stated" else None
        sensing.append({"id": f["id"], "label": f["label"], "status": st, "value": (v or {}).get("value"), "differs": len(said) > 1,
                        "options": conflict_options(given, words) if st == "conflict" else [],
                        "settled": {**done, "label": words.get(done["value"], str(done["value"]))} if done else None})
    blocked = bool(no_owner) and not pending
    R = c["readiness"]
    missing = [("owners", R["owners"]["needs"].format(role=p["owner_label"]).capitalize()) for p in pending]
    if not pending and not blocked:  # a pending owner or a blocked KPI is not asked for a source or sensing answers
        if src_status in ("pending", "conflict"):
            missing.append(("source", "Source: " + R["source"]["needs" if src_status == "pending" else "conflict"]))
        for s in sensing:
            if s["status"] in ("pending", "conflict"):
                missing.append(("sensing", R["sensing"]["needs" if s["status"] == "pending" else "conflict"]
                                .format(field=s["label"]).capitalize()))
    unknowns = [f"No {p['owner_label']}: the sponsor needs to name one" for p in parts if p["owner_status"] == "no_owner"]
    if not blocked:
        if src_status == "unknown":
            unknowns.append("Source is unknown")
        unknowns += [f"{s['label']} is unknown" for s in sensing if s["status"] == "unknown"]
        unknowns += [f"{s['label']}: owners gave different answers" for s in sensing if s["differs"] and s["status"] == "stated"]
    if isinstance(kpi.get("definition"), dict) and kpi["definition"].get("mark") == "unknown":
        unknowns.append("Definition is unknown")
    track = kpi.get("tracking") if isinstance(kpi.get("tracking"), dict) else {}
    today = tracked_today(kpi)
    if track.get("mark") != "stated":
        unknowns.insert(0, "Tracking status is unknown" if track.get("mark") == "unknown" else "Tracking status not stated yet")
    confirmed = all(p["confirmed"] for p in parts)
    return {"id": kpi["id"], "name": kpi.get("name") or kpi["id"], "priority": kpi.get("priority"),
            "state": "blocked" if blocked else "not_ready" if missing else "ready",
            "parts": parts, "source": {"status": src_status, "value": (src or {}).get("value")}, "sensing": sensing,
            "tracking": {"value": track.get("value"), "mark": track.get("mark"),
                         "label": c["tracking"].get(track.get("value")) if track.get("mark") == "stated" else None,
                         "today": today},
            "waiting_on": waiting, "waiting_note": f"waiting on {', '.join(waiting)}" if waiting else None, "unknowns": unknowns, "missing": [m for _, m in missing], "needs": missing, "confirmed_all": confirmed,
            "review": {"tentative_date": rev.get("tentative_date"), "next_step": rev.get("next_step"),
                       "project": rev.get("project"), "accepted": rev.get("accepted")} if not today else None}


def _covered(kpi: dict, row: dict, blind: frozenset) -> bool:
    """A measure the sponsor cannot see (`blind`) whose three named owners all confirmed it. The sponsor cannot accept it, so it
    never blocks the checklist (A-044: covered by its named owners). A measure the sponsor can see still needs its acceptance."""
    return kpi["id"] in blind and row["state"] != "blocked" and all(p["confirmed"] for p in row["parts"])


def compute(kpis: list[dict], answers: list[dict], version: dict, c: dict, mapped: dict | None = None,
            blind: frozenset = frozenset()) -> dict:
    """The review view: one entry per KPI, the readiness checklist, and the one-page list of what is coming. `mapped` is the
    tracking set on the process map (see with_tracking); `blind` the measures the sponsor may not see."""
    kpis = with_tracking(kpis, answers, version, c, mapped)
    rows = [_kpi(k, answers, version, c) for k in kpis if isinstance(k, dict) and k.get("id")]
    cover = {k["id"] for k, r in zip((k for k in kpis if isinstance(k, dict) and k.get("id")), rows) if _covered(k, r, blind)}
    R = c["readiness"]

    def item(id_, label, bad, required=True):
        return {"id": id_, "label": label, "met": not bad, "required": required, "missing": bad}

    def bad(kind):
        return [f"{r['name']}: {m}" for r in rows for k, m in r["needs"] if k == kind]

    owners_bad = bad("owners") if rows else ["There are no measures to baseline yet"]
    items = [item("owners", R["owners"]["label"], owners_bad), item("source", R["source"]["label"], bad("source")),
             item("sensing", R["sensing"]["label"], bad("sensing"))]
    steps_bad = [f"{r['name']}: no next step, project or tentative date" if not (r["review"]["next_step"] or r["review"]["project"] or r["review"]["tentative_date"])
                 else f"{r['name']}: the sponsor has not accepted it as unknown for now"
                 for r in rows if r["review"] is not None and r["id"] not in cover
                 and not ((r["review"]["next_step"] or r["review"]["project"] or r["review"]["tentative_date"]) and r["review"]["accepted"])]
    conf_bad = [f"{r['name']}: {p['label'].lower()} not confirmed by the {p['owner_label']}"
                for r in rows if r["state"] != "blocked" for p in r["parts"]
                if not p["confirmed"] and not ((r["review"] or {}).get("accepted") and p["silent"])]  # N2: acceptance waives only a silent owner
    items.append(item("next_steps", c["advice"]["next_steps"]["label"], steps_bad, required=False))
    items.append(item("confirmations", c["advice"]["confirmations"]["label"], conf_bad, required=False))
    ready = bool(rows) and all(i["met"] for i in items if i["required"])
    rows = [{**r, "covered": r["id"] in cover} for r in rows]  # the screen says "covered by its named owners", not "not accepted yet"
    coming = [{"kpi_id": r["id"], "name": r["name"], **r["review"]} for r in rows if r["review"] is not None]
    return {"ready": ready, "can_countersign": ready and items[-1]["met"], "items": items, "kpis": rows, "coming": coming}


# ---- M2-E1: ready to build, per measure --------------------------------------------------------------------------------------------

OPEN_RESTRICTED = "Something restricted is still open."


def open_reason(n: int) -> str:
    return f"{n} open {'question needs' if n == 1 else 'questions need'} a person."


def ready_to_build(kpi: dict, derived_open: int) -> tuple[bool, list[str]]:
    """(ready, reasons in plain words) for one measure: the business definition STATED by a person, the technical definition complete (sources,
    fields and calculation, each stated) and confirmed by the data owner, no open ambiguity, governance decided. `derived_open` is REQUIRED: the
    count of open ambiguities that are not stored on the measure (governance items worked out from the catalogue), over EVERY row, never one
    person's view (`store.ambiguities.derived_open_all`), so the gate is the same for everyone. Reasons are counts and parts and name no field,
    source or other measure. Reads only; this is what the sign-off gate (M2-E4) calls."""
    from modules.m2_baseline.domain import ambiguities as A  # imported here: ambiguities and technical do not import this file
    from modules.m2_baseline.domain import technical as T
    why = []
    d = kpi.get("definition") or {}
    if d.get("mark") != "stated" or not d.get("value") or str(d.get("by")) in ("Lens", "the pack"):
        why.append("The business definition has not been confirmed by a person yet.")
    p = T.parts_of(kpi)
    gaps = T.missing(kpi)
    if gaps:
        why.append("The technical definition is not complete: it still needs its " + ", ".join(T.LABELS[g].lower() for g in gaps) + ".")
    elif not T.confirmed(kpi) or any(p[x].get("mark") != "stated" for x in T.NEEDED):
        why.append("The data owner has not confirmed the technical definition.")
    n = A.open_count(kpi.get("ambiguities") or []) + max(0, int(derived_open))
    if n:
        why.append(open_reason(n))
    g = kpi.get("governance") or {}
    if g.get("personal", "not_sure") == "not_sure":
        why.append("Governance is not decided: is there personal data in it?")
    elif (g.get("personal") == "yes" or g.get("sensitive")) and not g.get("may_see"):
        why.append("Governance is not decided: nobody is named to see it yet.")
    return not why, why


def open_total(kpi: dict, derived_open: int) -> int:
    from modules.m2_baseline.domain import ambiguities as A
    return A.open_count(kpi.get("ambiguities") or []) + max(0, int(derived_open))


def open_label(kpi: dict, derived_open: int) -> str:
    """The plain pill on the work list: "Ready to build", or what is open ("3 things open"). The same for everyone."""
    ok, why = ready_to_build(kpi, derived_open)
    n = len(why) + max(0, open_total(kpi, derived_open) - 1)  # each open question is one thing
    return "Ready to build" if ok else f"{n} thing{'s' if n != 1 else ''} open"


def reasons_for_viewer(why: list[str], total_open: int, visible_open: int) -> list[str]:
    """The reasons one person may see: the open-question count is theirs (what they may see), and when something they may not see is also
    open, one plain line says so with no detail."""
    out = [r for r in why if "open question" not in r]
    if visible_open:
        out.append(open_reason(visible_open))
    if total_open > visible_open:
        out.append(OPEN_RESTRICTED)
    return out
