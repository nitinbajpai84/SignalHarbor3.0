"""IC v2 (32, 34): the charter with ten pages, the sponsor's signature, versions, and who does what.

The charter document stays where module 1 keeps it (intents/m1_intent/charters/<session id>.json, written through CharterStore);
this file reads it, assembles the ten pages from the records of the other cards, and adds the routes the spec names: sign (sponsor
only), new version, discard, accept a risk, and the roles. Pure helpers sit first (tested alone); the routes are thin.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, lifecycle
from sh_platform.intents import store as S
from sh_platform.intents.access import (CLOSER, ORGANISER, IntentAccess, IntentRefused, IntentRoute, Me,
                                        intent_roles, load_intent, person_name, roles_of)
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import links, store as profile_store
from sh_platform.profile import view as pview

log = logging.getLogger(__name__)
router = APIRouter(route_class=IntentRoute)

ROLES = ("architect", "head_of_department", "developer", "tester", "sponsor", "ops", "informed")  # 59, C25: head_of_department approves the design
LABEL = {"architect": "Architect", "developer": "Developer", "tester": "Tester", "sponsor": "Sponsor", "ops": "Operations",
         "informed": "Kept informed", "head_of_department": "Head of department"}
DUTY = {
    "architect": "Check the gap analysis and design the blueprint, and sign that the design fits what the charter asked for.",
    "developer": "Build the pipelines and measures from the blueprint and run them against the baseline.",
    "tester": "Check each measure against the benchmark and sign the user acceptance test or send it back with what needs fixing.",
    "sponsor": "Own the outcome, sign the charter, and approve the release.",
    "ops": "Run the release and watch it once live; take the first call when it breaks.",
    "informed": "Read the hand-overs and the release note. You are not asked to do anything.",
    "head_of_department": "Approve the design on the change note; this signs the blueprint. You cannot approve a design you drew as the architect.",
}
REQUIRED = ("architect", "developer", "sponsor")  # file 34 rules: tester has a fallback, ops may be named later, informed never blocks
PAGES = (("intent", "The intent"), ("wall", "The frozen wall"), ("problems", "Problems"), ("measures", "Measures"),
         ("processes", "Processes involved"), ("sources", "Data sources"), ("roles", "Who does what"), ("build", "Build needed"),
         ("parked", "Parked for later"), ("risks", "Known risks"))
BUILD_LINES = (("charter", "Charter signed"), ("business", "Business definitions confirmed"),
               ("technical", "Technical definition, catalogue and governed state"), ("processes", "Process owners"),
               ("sources", "Source owners"), ("team", "Team named"), ("needed", "Build needed answered"))
GOVERNED = ("owners", "classification", "may_see", "resolving", "affects", "review_date")
FROM_HYPOTHESIS = "From the hypothesis"
NO_WALL = "The wall was not frozen. The Initiative has no wall."
BLOCK_LINES = "Check the 'so that' lines first."
BLOCK_PROBLEM = "Add at least one problem."
BLOCK_BUILD = "Answer 'Is a build needed?' first."
DECLINE_MAX = 300


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _v(cell: Any) -> Any:
    """The value of a provenance cell, or the thing itself."""
    return cell.get("value") if isinstance(cell, dict) and "mark" in cell else cell


def _read(plane, *parts) -> Any:
    try:
        return read_json_strict(plane.path(*parts))
    except (OSError, ValueError):
        return None


def _page(key: str, status: str, text: str | None = None, **data) -> dict:
    n = next(i for i, (k, _) in enumerate(PAGES, 1) if k == key)
    return {"n": n, "key": key, "title": dict(PAGES)[key], "status": status, "text": text, **data}


def _waits(text: str, spec: str) -> str:
    return f"Not available yet: {text} Waits for file {spec}."


# ---- the pages ----------------------------------------------------------------------------------------------------------

def page_intent(intent: dict, organiser_name: str | None, role_word: str) -> dict:
    tb = intent.get("time_box") or {}
    oc = intent.get("outcome") or {}
    return _page("intent", "ok", name=intent.get("title") or "", purpose=intent.get("purpose") or None,
                 opened_by={"name": organiser_name, "role": role_word, "date": (intent.get("created_at") or "")[:10] or None},
                 why=oc.get("why") or oc.get("goal") or None, areas=list(intent.get("areas") or []),
                 time_box={"starts": tb.get("starts"), "ends": tb.get("ends")})


def page_wall(version: dict | None, intent_id: str) -> dict:
    wall = (version or {}).get("wall")
    if not wall:
        return _page("wall", "empty", NO_WALL)
    lanes = [{"lane": x.get("lane"), "count": x.get("count", 0),
              "cards": [{"text": c.get("text") or None, "author": c.get("author")} for c in x.get("cards") or [] if not c.get("sealed")]}
             for x in wall.get("lanes") or []]
    cards = [c for x in wall.get("lanes") or [] for c in x.get("cards") or []]
    names = sorted({c["author"] for c in cards if c.get("author") and c["author"] != "Anonymous" and not c.get("sealed")})
    return _page("wall", "ok", lanes=lanes, total=sum(x["count"] for x in lanes), took_part=names,
                 anonymous=sum(1 for c in cards if c.get("author") == "Anonymous"), sealed=sum(1 for c in cards if c.get("sealed")),
                 participants=((version or {}).get("footer") or {}).get("participants"), href=f"/centre/intent/{intent_id}/wall")


def page_problems(view: dict | None) -> dict:
    if not view or not view["problems"]:
        return _page("problems", "empty", "No problems were chosen.", lists=[])
    by_id = {p["id"]: p for p in view["problems"]}
    lists = [{"heading": l.get("heading"), "kind": l.get("kind"), "items": [by_id[i] for i in l.get("ids", []) if i in by_id]}
             for l in view.get("lists") or []]
    return _page("problems", "ok", lists=lists or [{"heading": "Problems", "kind": "intent", "items": list(by_id.values())}])


def page_measures(plane, intent: dict, view: dict | None) -> dict:
    ids = (intent.get("refs") or {}).get("baseline_ids") or []
    base = ("intents", "m2_baseline", ids[0]) if ids else None
    kpis = _read(plane, *base, "kpis.json") if base else None
    if not isinstance(kpis, list) or not kpis:
        return _page("measures", "missing", _waits("the glossary has no measures.", "29"))
    gloss = {e.get("kpi_id"): e for e in ((_read(plane, *base, "glossary.json") or {}).get("entries") or []) if isinstance(e, dict)}
    gov = _read(plane, *base, "governed_state.json") or {}
    rows = []
    for p in (view or {}).get("problems") or []:
        ms = []
        for k in kpis:
            if p["id"] not in (k.get("problem_ids") or []):
                continue
            g, st = gloss.get(k["id"]) or {}, gov.get(k["id"]) or {}
            marks = [st.get(f) for f in GOVERNED if isinstance(st.get(f), dict)]
            stated = [m for m in marks if m.get("mark") == "stated"]
            state = "Confirmed" if len(stated) == len(GOVERNED) else "Draft" if stated else "Unconfirmed"
            who = max(stated, key=lambda m: m.get("at") or "", default={})
            ms.append({"id": k["id"], "name": k.get("name"), "business": _v(g.get("business_definition")) or _v(k.get("definition")),
                       "technical": _v((k.get("technical") or {}).get("calculation")), "state": state,
                       "confirmed_by": who.get("by") if state == "Confirmed" else None,
                       "confirmed_at": (who.get("at") or "")[:10] if state == "Confirmed" else None,
                       "href": f"/centre/intent/{intent['id']}/define?tab=glossary&measure={k['id']}",
                       "catalogue_href": f"/centre/intent/{intent['id']}/define?tab=catalogue&measure={k['id']}"})
        rows.append({"problem": p["title"], "measures": ms,
                     "empty": None if ms else "No measure yet. Lens drafts one when the problem is chosen."})
    return _page("measures", "ok" if rows else "empty", None if rows else "No measure yet. Lens drafts one when the problem is chosen.", rows=rows)


def page_processes(plane, intent_id: str) -> dict:
    doc = _read(plane, "intents", intent_id, "processes.json")
    items = [p for p in (doc or {}).get("processes") or [] if isinstance(p, dict)] if isinstance(doc, dict) else []
    if not items:
        return _page("processes", "missing", _waits("the process map has not been drafted.", "27"))
    live = [p for p in items if not p.get("removed") and p.get("status") != "removed"]
    rows = []
    for p in live:
        conf = p.get("confirmed") if isinstance(p.get("confirmed"), dict) else None
        status = "confirmed" if conf and p.get("status") == "confirmed" else p.get("status") or "guessed"
        rows.append({"id": p.get("id"), "name": _v(p.get("name")), "owner": _v(p.get("owner")), "status": status,
                     "chip": f"Confirmed by {conf.get('by')}" if status == "confirmed" and conf.get("by") else
                     "Edited" if status == "edited" else "Guessed",
                     "steps": len(p.get("steps") or []), "breaks": len(p.get("breaks") or []),
                     "note": None if status == "confirmed" else "Not yet confirmed by its owner",
                     "href": f"/centre/intent/{intent_id}/define?tab=process-map&process={p.get('id')}"})
    if not rows:
        return _page("processes", "empty", "No process linked. Add one in the process map.", removed=len(items))
    return _page("processes", "ok", rows=rows, confirmed=sum(1 for r in rows if r["status"] == "confirmed"), removed=len(items) - len(live),
                 href=f"/centre/intent/{intent_id}/define?tab=process-map")


def page_sources(plane, intent: dict) -> dict:
    ids = (intent.get("refs") or {}).get("baseline_ids") or []
    cat = _read(plane, "intents", "m2_baseline", ids[0], "catalogue.json") if ids else None
    rows = [r for r in (cat or {}).get("sources") or [] if isinstance(r, dict)] if isinstance(cat, dict) else []
    if not rows:
        return _page("sources", "missing", _waits("the data sources map has not been drafted.", "28"))
    extras = _read(plane, "intents", "m2_baseline", ids[0], "data_sources.json") or {}
    ext = (extras.get("sources") or {}) if isinstance(extras, dict) else {}
    out, restricted = [], 0
    for r in rows:
        sid, x = _v(r.get("Source ID")), ext.get(_v(r.get("Source ID"))) or {}
        if x.get("restricted") is True:
            restricted += 1
            continue
        if x.get("left_out"):
            continue
        so, bo, do = _v(x.get("source_owner")), _v(x.get("business_owner")), _v(r.get("Data owner"))
        conf = _v(r.get("Confirmed by"))
        marks = {c.get("mark") for c in r.values() if isinstance(c, dict)}
        state = ("Confirmed by source owner" if so and conf and conf == so else "Needs source owner" if not so
                 else "Drafted by Lens" if "guessed" in marks and "stated" not in marks else "Edited")
        out.append({"id": sid, "name": _v(r.get("Source name")), "system": _v(r.get("Where it lands or lives")),
                    "format": _v(r.get("Source type")), "state": state, "source_owner": so, "data_owner": do, "business_owner": bo,
                    "href": f"/centre/intent/{intent['id']}/define?tab=data-sources&source={sid}"})
    areas = [a.get("name") for a in (extras.get("areas") or []) if isinstance(a, dict) and not a.get("hidden") and a.get("name")]
    named = sum(1 for s in out if s["source_owner"] and s["data_owner"] and s["business_owner"])
    return _page("sources", "ok" if out or restricted else "empty", None if out or restricted else "No data source linked.", rows=out,
                 named=named, confirmed=sum(1 for s in out if s["state"] == "Confirmed by source owner"), restricted=restricted,
                 areas=areas, href=f"/centre/intent/{intent['id']}/define?tab=data-sources")


def page_roles(rv: dict | None) -> dict:
    if not rv or not rv.get("rows") or not any(r["person"] for r in rv["rows"]):
        return _page("roles", "empty", "Roles not named yet", rows=[r | {"reason": None} for r in (rv or {}).get("rows", [])])
    return _page("roles", "ok", rows=[{k: r[k] for k in ("role", "label", "person", "mark", "answer")} for r in rv["rows"]])


def page_build(intent: dict) -> dict:
    needed, org, sp = intent.get("build_needed"), person_name(intent, "organiser"), person_name(intent, "sponsor")
    br = intent.get("build_ready") if isinstance(intent.get("build_ready"), dict) else None
    lines = []
    if br and br.get("lines"):
        by_key = {l.get("key"): l for l in br["lines"] if isinstance(l, dict)}
        lines = [{"key": k, "label": lab, "ok": bool((by_key.get(k) or {}).get("ok"))} for k, lab in BUILD_LINES]
    return _page("build", "ok", needed=needed, reason=intent.get("build_needed_reason"),
                 by=(intent.get("build_needed_by") or {}).get("name") if isinstance(intent.get("build_needed_by"), dict) else intent.get("build_needed_by"),
                 at=intent.get("build_needed_at"), lines=lines, passing=sum(1 for l in lines if l["ok"]) if lines else None,
                 not_answered=f"Not answered. {org or 'The organiser'} or {sp or 'the sponsor'} answers this." if needed is None else None,
                 not_checked=None if lines else "Not checked yet. North checks when Define has a charter draft.",
                 href=f"/centre/intent/{intent['id']}/build-ready", handoff=intent.get("build_handoff") or None)


def page_parked(version: dict | None) -> dict:
    v = version or {}
    rows = [{"title": p.get("title"), "reason": p.get("reason"), "review_date": p.get("review_date"), "kind": "Future shelf"} for p in v.get("parked") or []]
    rows += [{"title": l.get("title"), "reason": "Not ticked in the room", "review_date": None, "kind": "Left for later"} for l in v.get("later") or []]
    rows += [{"title": n.get("text") or "An anonymous note", "reason": "Left on its own, in no group", "review_date": None, "kind": "Note"}
             for n in v.get("alone") or []]
    return _page("parked", "ok" if rows else "empty", None if rows else "Nothing parked.", rows=rows)


def derive_risks(pages: list[dict]) -> list[dict]:
    """North's list of open items, from the other pages. Each line says what is open."""
    by = {p["key"]: p for p in pages}
    out = []

    def add(text: str, source: str) -> None:
        out.append({"text": text, "source": source})
    pr = by["processes"]
    if pr["status"] == "ok":
        for r in pr["rows"]:
            if r["status"] != "confirmed":
                add(f"Process '{r['name']}' is not yet confirmed by its owner.", "process")
    so = by["sources"]
    if so["status"] == "ok":
        for r in so["rows"]:
            if not r["source_owner"]:
                add(f"Source '{r['name']}' has no confirmed source owner.", "source")
    bd = by["build"]
    if bd["not_answered"]:
        add("Whether a build is needed has not been answered.", "build_ready")
    for l in bd["lines"]:
        if not l["ok"] and l["key"] != "charter":
            add(f"Build-ready: {l['label'].lower()} does not pass yet.", "build_ready")
    for r in by["roles"].get("rows", []):
        if r["role"] in REQUIRED and r["role"] != "sponsor" and (not r["person"] or (r["answer"] or {}).get("state") != "accepted"):
            add(f"The {r['label'].lower()} role is not accepted yet.", "role")
    return out


def success_measures(plane, intent: dict) -> dict | None:
    """The success measures from the hypothesis the Initiative carries (57, C7): measure, baseline, target, review date. None without one."""
    ref = intent.get("hypothesis_ref")
    if not isinstance(ref, dict) or not ref.get("id"):
        return None
    from sh_platform.intents import hypotheses as H
    v = H.latest(H.get(plane, str(ref["id"])))
    if not v:
        return {"label": FROM_HYPOTHESIS, "hypothesis": None, "text": "Not available yet: the hypothesis could not be read."}
    m = v.get("measure") or {}
    gaps = [w for w, ok in (("no measure", m), ("no baseline", v.get("baseline")), ("no target", v.get("target")), ("no review date", v.get("review_date"))) if not ok]
    return {"label": FROM_HYPOTHESIS, "hypothesis": {"id": ref["id"], "version": v["v"]}, "belief": v.get("belief"),
            "measure": {"id": m.get("id"), "name": m.get("name") or m.get("id")} if m else None, "baseline": v.get("baseline"),
            "target": v.get("target"), "review_date": v.get("review_date"), "text": "Not available yet: " + ", ".join(gaps) + "." if gaps else None}


def edit_success(plane, intent: dict, raw, name: str) -> None:
    """The organiser changes the target or the review date: a new hypothesis version (a version is never edited in place)."""
    from sh_platform.intents import hypotheses as H
    ref = intent.get("hypothesis_ref") or {}
    v = H.latest(H.get(plane, str(ref.get("id") or "")))
    if not v:
        raise _refuse(409, "charter_no_hypothesis", "This Initiative carries no hypothesis to change.")
    if not isinstance(raw, dict) or not raw or not set(raw) <= {"target", "review_date"}:
        raise _refuse(400, "bad_request", "That could not be read. Please try again.")
    changes: dict = {}
    if "review_date" in raw:
        try:
            changes["review_date"] = datetime.strptime(str(raw["review_date"]), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise _refuse(422, "charter_review_date", "Pick a review date.") from None
    if "target" in raw:
        t = raw["target"]
        if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float)) or t != t or abs(t) > 1e15):
            raise _refuse(422, "charter_target", "The target should be a number.")
        unit = (v.get("target") or v.get("baseline") or {}).get("unit")
        changes["target"] = None if t is None else {"value": t, "unit": unit, "by": changes.get("review_date") or v.get("review_date"), "set_by": name}
    elif "review_date" in raw and v.get("target"):
        changes["target"] = {**v["target"], "by": changes["review_date"]}
    if "target" in changes:
        changes["expected_uplift"] = H.uplift_gap(v.get("baseline"), changes["target"]) if (v.get("expected_uplift") or {}).get("basis") in (None, "gap_to_target") else v["expected_uplift"]
    H.add_version(plane, ref["id"], changes, name)


def freeze_hypothesis(plane, store, sid: str, intent: dict, version: int, name: str) -> None:
    """At signature the hypothesis gets a version frozen by this charter version, and the frozen pages name it (57, 32, read by 58)."""
    from sh_platform.intents import hypotheses as H
    ref = intent.get("hypothesis_ref") or {}
    if not ref.get("id"):
        return
    rec = H.add_version(plane, str(ref["id"]), {"frozen_by": f"charter:{intent['id']} v{version}"}, name, state="carried")
    if rec:
        fz = H.ref(rec)
        _mutate_doc(store, sid, lambda ver, d, i: {**ver, "pages_frozen": {**(ver.get("pages_frozen") or {}), "hypothesis_ref": fz}}
                    if ver.get("version") == version else ver)


def with_acceptance(derived: list[dict], stored: list[dict] | None) -> list[dict]:
    old = {x.get("text"): x for x in stored or [] if isinstance(x, dict)}
    return [{**d, "accepted_by": (old.get(d["text"]) or {}).get("accepted_by"), "accepted_at": (old.get(d["text"]) or {}).get("accepted_at")}
            for d in derived]


def assemble(plane, intent: dict, version: dict | None, view: dict | None, rv: dict | None, organiser_name: str | None = None) -> list[dict]:
    """The ten pages. A signed version reads its frozen copy for pages 4 to 8 and 10, so later edits in Define never change it."""
    frozen = (version or {}).get("pages_frozen")
    signed = bool(frozen) and (version or {}).get("status") == "signed"
    if signed:
        by = {p["key"]: p for p in frozen["pages"]}
        pages = [page_intent(intent, organiser_name, "organiser"), page_wall(version, intent["id"]), page_problems(view),
                 *[by[k] for k in ("measures", "processes", "sources", "roles", "build")], page_parked(version)]
        return [*pages, _page("risks", "ok" if version.get("risks") else "empty", None if version.get("risks") else "No known risks.",
                              rows=version.get("risks") or [], accept=False)]
    measures = page_measures(plane, intent, view)
    if (success := success_measures(plane, intent)):
        measures["success"] = success
    pages = [page_intent(intent, organiser_name, "organiser"), page_wall(version, intent["id"]), page_problems(view),
             measures, page_processes(plane, intent["id"]), page_sources(plane, intent), page_roles(rv),
             page_build(intent), page_parked(version)]
    risks = with_acceptance(derive_risks([*pages, _page("risks", "ok")]), (version or {}).get("risks"))
    return [*pages, _page("risks", "ok" if risks else "empty", None if risks else "No known risks.", rows=risks, accept=True)]


# ---- rules: signing, versions, edits ---------------------------------------------------------------------------------------

def current_index(doc: dict) -> int:
    """The live version: the last one that was not discarded."""
    return max(i for i, v in enumerate(doc["versions"]) if not v.get("discarded"))


def sign_blocker(version: dict, intent: dict) -> str | None:
    """Why the sponsor cannot sign yet, in the spec's words; None when they can."""
    if any(p.get("so_that_draft") for p in version["problems"]):
        return BLOCK_LINES
    if not version["problems"]:
        return BLOCK_PROBLEM
    if intent.get("build_needed") is None:
        return BLOCK_BUILD
    return None


def new_draft(prior: dict, number: int, by: str, now: str, comment: str | None) -> dict:
    """A draft copy of a signed version. The signed one stays signed and current for Build until this one is signed."""
    if prior["status"] != "signed":
        raise ValueError("only a signed version can start a new one")
    return {**prior, "version": number, "status": "draft", "created_at": now, "created_by": by, "edited_at": None,
            "edited_by": None, "signatures": [], "returned": None, "pages_frozen": None, "superseded_by": None, "superseded_at": None,
            "discarded": None, "comment": comment or None,
            "risks": [{**r, "accepted_by": None, "accepted_at": None} for r in prior.get("risks") or []]}


def signed_how(sig: dict) -> str:
    return "by approver link" if sig.get("how") == "approver" else "in the charter"


# ---- who does what (34) --------------------------------------------------------------------------------------------------

def blank_answer() -> dict:
    return {"state": "not_asked", "asked_at": None, "at": None, "by": None, "reason": None}


def _people_rows(request: Request, plane) -> list[dict]:
    """The company people list: profile people with their role and team (viewer-filtered), and the account they are linked to."""
    seen = pview.read(plane, _viewer(request)).get("people", {})
    raw = profile_store.raw(plane)["people"]
    return [{"id": pid, "name": pview._v(p, "name"), "role": pview._v(p, "role"), "team": pview._v(p, "team"),
             "account_id": links._account_of(raw.get(pid) or {})} for pid, p in seen.items() if isinstance(p, dict) and pview._v(p, "name")]


def _pid(value: Any, people: list[dict]) -> str | None:
    """A role holds a person id. An old file holds a name: it is matched to one person, else not named."""
    if isinstance(value, str) and any(p["id"] == value for p in people):
        return value
    hits = [p["id"] for p in people if isinstance(value, str) and pview.norm(p["name"]) == pview.norm(value)]
    return hits[0] if len(hits) == 1 else None


def merge_roles(stored: dict | None, drafted: tuple[dict, dict], people: list[dict], sponsor: dict | None) -> dict:
    """Stated rows win; the rest take Lens's guess (never one person in two roles). The sponsor is the Initiative's sponsor, one source."""
    st = stored or {}
    roles, prov, ans = {}, {}, {}
    for r in ROLES:
        mark = (st.get("provenance") or {}).get(r) or {}
        if mark.get("mark") == "stated":
            raw = (st.get("roles") or {}).get(r)
            roles[r] = [x for x in (_pid(i, people) for i in raw or []) if x] if r == "informed" else _pid(raw, people)
            if r != "informed" and raw and roles[r] is None:
                mark = {**mark, "unresolved": raw}
            prov[r] = mark
        elif drafted[1].get(r):
            raw = drafted[0].get(r)
            roles[r] = [x for x in (_pid(i, people) for i in raw or []) if x] if r == "informed" else _pid(raw, people)
            prov[r] = drafted[1][r] if roles[r] else {"mark": "unknown"}
        else:
            roles[r], prov[r] = ([] if r == "informed" else None), {"mark": "unknown"}
        ans[r] = ((st.get("answers") or {}).get(r)) or blank_answer()
    if sponsor:
        pid = _pid(sponsor.get("name"), people)
        if pid:
            roles["sponsor"], prov["sponsor"] = pid, {"mark": "stated", "by": "the Initiative", "from": "Set from the intent's sponsor"}
    return {"roles": roles, "provenance": prov, "answers": ans, "answer_history": st.get("answer_history") or [],
            "handed_over_at": st.get("handed_over_at")}


def roles_rows(rec: dict, people: list[dict], see_reasons: bool) -> list[dict]:
    by = {p["id"]: p for p in people}
    rows = []
    for r in ROLES:
        raw, mark, ans = rec["roles"].get(r), rec["provenance"].get(r) or {"mark": "unknown"}, rec["answers"].get(r) or blank_answer()
        ids = raw if isinstance(raw, list) else [raw] if raw else []
        label = {"stated": "Stated", "guessed": "Guessed"}.get(mark.get("mark"), "Left open")
        person = ", ".join(by[i]["name"] for i in ids if i in by) or None
        rows.append({"role": r, "label": LABEL[r], "duty": DUTY[r], "required": r in REQUIRED, "person_ids": ids, "person": person,
                     "mark": label, "mark_reason": mark.get("from") if mark.get("mark") == "guessed" else (f"Stated by {mark.get('by')}" if mark.get("by") else None),
                     "unresolved": mark.get("unresolved"),
                     "answer": {"state": ans["state"], "at": ans.get("at"), "asked_at": ans.get("asked_at"),
                                "reason": ans.get("reason") if see_reasons else None}})
    return rows


def ask_roles(rec: dict, which: list[str] | None, now: str) -> list[str]:
    """The stated, named, not-yet-asked roles become `waiting`. Returns the roles asked."""
    asked = []
    for r in which or ROLES:
        named = rec["roles"].get(r)
        if r not in ROLES or not named or (rec["provenance"].get(r) or {}).get("mark") != "stated":
            continue
        if rec["answers"][r]["state"] == "not_asked":
            rec["answers"][r] = {**blank_answer(), "state": "waiting", "asked_at": now}
            asked.append(r)
    return asked


def set_roles(rec: dict, changes: dict, people: list[dict], by: str, now: str) -> None:
    """The organiser names a person per role. A changed name resets the answer and keeps the old one in the history."""
    ids = {p["id"] for p in people}
    for r, v in changes.items():
        if r not in ROLES or r == "sponsor":
            raise ValueError("That role is not set here.")
        if r == "informed":
            if not isinstance(v, list) or not all(isinstance(x, str) and x in ids for x in v):
                raise ValueError("Pick someone from the people list. If they are missing, add them in the profile.")
            v = list(dict.fromkeys(v))
        elif v is not None and (not isinstance(v, str) or v not in ids):
            raise ValueError("Pick someone from the people list. If they are missing, add them in the profile.")
        old = rec["roles"].get(r)
        if old != v and rec["answers"][r]["state"] != "not_asked":
            rec["answer_history"].append({"role": r, "person_id": old, "state": rec["answers"][r]["state"],
                                          "reason": rec["answers"][r].get("reason"), "at": now})
        if old != v:
            rec["answers"][r] = blank_answer()
        rec["roles"][r] = v
        rec["provenance"][r] = {"mark": "stated" if v else "unknown", "by": by, "from": "Set by the organiser", "at": now}


def answer_role(rec: dict, role: str, person_id: str, answer: str, reason: str | None, now: str) -> None:
    """The named person accepts or declines (informed: seen). A decline needs a reason; an answer can change until hand-over."""
    named = rec["roles"].get(role)
    if role not in ROLES:
        raise ValueError("That role is not here.")
    if person_id not in (named if isinstance(named, list) else [named]):
        raise PermissionError("Only the person named for this role can answer.")
    if rec.get("handed_over_at"):
        raise ValueError("This Initiative has been handed to Build. Ask the organiser to change the role.")
    if rec["answers"][role]["state"] == "not_asked":
        raise ValueError("You have not been asked yet.")
    if role == "informed":
        if answer != "seen":
            raise ValueError("Kept informed is answered with Got it.")
        state = "seen"
    elif answer == "accept":
        state = "accepted"
    elif answer == "decline":
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Please say why you cannot take the role.")
        state = "declined"
    else:
        raise ValueError("Please accept or decline.")
    rec["answers"][role] = {**rec["answers"][role], "state": state, "at": now, "by": person_id,
                            "reason": reason.strip()[:DECLINE_MAX] if state == "declined" else None}


# ---- storage and the m1 charter document ----------------------------------------------------------------------------------

def _sid(intent: dict) -> str | None:
    ids = (intent.get("refs") or {}).get("wall_session_ids") or []
    return ids[0] if ids and isinstance(ids[0], str) else None


def _roles_path(plane, sid: str):
    return plane.path("intents", "m1_intent", "roles", f"{sid}.json")


def _m1(request: Request, plane):
    """The module's charter store and settings, imported when needed: the kernel holds no module code at load time."""
    from modules.m1_intent.domain import charter as C
    from modules.m1_intent.store.charter import CharterStore
    contracts = getattr(request.app.state, "m1_contracts_dir", None)
    return C, CharterStore(plane, contracts_dir=contracts), C.load_charter_settings(contracts)


def _refuse(status: int, code: str, message: str) -> IntentRefused:
    return IntentRefused(status, code, message)


def _name(request: Request) -> str:
    return _viewer(request).name or "A person"


def _roles_record(request: Request, plane, intent: dict, sid: str | None, people: list[dict]) -> dict:
    from modules.m1_intent.domain import roles as R
    stored = _read(plane, "intents", "m1_intent", "roles", f"{sid}.json") if sid else None
    names = [p.get("name") for p in (intent.get("people") or {}).get("participants") or [] if isinstance(p, dict) and p.get("name")]
    seen = pview.read(plane, _viewer(request)).get("people", {})
    drafted = R.draft(seen, "", names)
    return merge_roles(stored if isinstance(stored, dict) else None, drafted, people, (intent.get("people") or {}).get("sponsor"))


def _save_roles(plane, sid: str, rec: dict, people: list[dict]) -> None:
    by = {p["id"]: p["name"] for p in people}
    names = {r: ([by.get(i) for i in v] if isinstance(v, list) else by.get(v)) for r, v in rec["roles"].items()}
    write_json_atomic(_roles_path(plane, sid), {**rec, "names": names})


def _ids(v: Any) -> set:
    return set(v) if isinstance(v, list) else {v} - {None}


def _my_pids(me: Me, people: list[dict]) -> set[str]:
    """The people-list entries that are this viewer: by linked account, else by a name that is theirs alone."""
    return {p["id"] for p in people if (p["account_id"] and p["account_id"] == me.account_id) or
            (not p["account_id"] and not me.shared_name and pview.norm(p["name"]) == pview.norm(me.name))}


def _named_person(me: Me, rec: dict, people: list[dict]) -> list[str]:
    """The role keys this viewer is named for."""
    mine = _my_pids(me, people)
    return [r for r in ROLES if mine & _ids(rec["roles"].get(r)) and (rec["provenance"].get(r) or {}).get("mark") == "stated"]  # a guess names nobody


# ---- the view ------------------------------------------------------------------------------------------------------------

def version_row(v: dict, current: bool) -> dict:
    sig = (v.get("signatures") or [None])[-1]
    state = "Discarded" if v.get("discarded") else "Superseded" if v.get("superseded_by") else "Signed" if v["status"] == "signed" else "Draft"
    return {"version": v["version"], "state": state, "created_by": v["created_by"], "created_at": v["created_at"],
            "signed_by": sig and sig["name"], "signed_at": sig and sig["at"], "comment": v.get("comment") or (v.get("returned") or {}).get("comment"),
            "discarded": v.get("discarded"), "current": current}


def build_view(request: Request, plane, intent: dict, roles: frozenset[str], want: int | None = None) -> dict:
    head = {"id": intent["id"], "title": intent.get("title"), "purpose": intent.get("purpose"), "state": intent.get("state")}
    if "content" not in roles:
        signed = (intent.get("outcome") or {}).get("signed_at")
        return {"intent": head, "tier": "card", "available": False,
                "message": "You can see that the charter exists. You can open it if the organiser adds you.",
                "outcome_line": f"Signed by {(intent['outcome'] or {}).get('signed_by')} on {str(signed)[:10]}." if signed else None}
    intent = sync_approved(request, plane, intent)
    head = {**head, "state": intent.get("state")}
    sid = _sid(intent)
    C, store, settings = _m1(request, plane)
    doc = store.read(sid) if sid else None
    people = _people_rows(request, plane)
    rv = _roles_record(request, plane, intent, sid, people)
    organiser = "organiser" in roles
    see_reasons = organiser or "company_admin" in roles
    rows = roles_rows(rv, people, see_reasons)
    if "organiser" not in roles and not roles & {"closer", "participant", "observer", "company_admin", "creator"}:  # an affected reader: names, not answers
        rows = [{**r, "answer": {"state": r["answer"]["state"], "at": None, "asked_at": None, "reason": None}} for r in rows]
    rview = {"rows": rows}
    org_name = person_name(intent, "organiser")
    sponsor_name = person_name(intent, "sponsor")
    base = {"intent": head, "tier": "content", "sponsor": sponsor_name, "organiser": org_name, "available": doc is not None,
            "viewer": {"organiser": organiser, "closer": "closer" in roles, "company_admin": "company_admin" in roles, "name": _name(request)},
            "roles": {"rows": rows, "footer": _roles_footer(rows, people), "can_edit": False, "people": []}}
    if doc is None:
        return {**base, "message": "The charter is drafted when Define closes. Nothing to read yet.", "pages": assemble(plane, intent, None, None, rview, org_name),
                "charter": None, "versions": []}
    cur = current_index(doc)
    idx = cur if want is None else next((i for i, v in enumerate(doc["versions"]) if v["version"] == want and not v.get("discarded")), cur)
    v = doc["versions"][idx]
    shown = {**doc, "versions": doc["versions"][: idx + 1]}
    from modules.m1_intent.api import charter as M
    cview = M.charter_view(request, plane, store.sessions.get(sid), shown, settings, organiser, request.state.account_id)
    is_current = idx == cur
    editable = organiser and is_current and v["status"] == "draft" and not v["signatures"] and intent.get("state") not in S.STATES[-2:]
    block = sign_blocker(v, intent)
    can_sign = "closer" in roles and is_current and v["status"] == "draft" and not v["signatures"] and intent.get("type") == "initiative"
    sig = (v["signatures"] or [None])[-1]
    state = "Superseded" if v.get("superseded_by") else "Signed" if v["status"] == "signed" else "Draft"
    pages = assemble(plane, intent, v, cview, rview, org_name)
    unchecked = sum(1 for p in v["problems"] if p.get("so_that_draft"))
    return {**base, "message": None, "pages": pages,
            "roles": {**base["roles"], "can_edit": editable, "people": [{"id": p["id"], "name": p["name"], "role": p["role"]} for p in people] if organiser else []},
            "charter": {"version": v["version"], "edited_at": v.get("edited_at"), "of": len(doc["versions"]), "state": state, "status": v["status"], "editable": editable,
                        "current": is_current, "session_id": sid, "problems": cview["problems"], "approver": cview["approver"],
                        "returned": cview["returned"], "footer": cview["footer"],
                        "signature": {"needed": sponsor_name, "signed_by": sig and sig["name"], "signed_at": sig and sig["at"],
                                      "how": sig and signed_how(sig)},
                        "can_sign": can_sign and block is None, "sign_block": block if can_sign else None,
                        "can_new_version": organiser and is_current and v["status"] == "signed",
                        "can_discard": organiser and is_current and v["status"] != "signed" and v["version"] >= 2,
                        "can_download": v["status"] == "signed",
                        "north": (f"North drafted {unchecked} 'so that' lines. Check them." if unchecked and organiser else
                                  "All lines are checked. Ask the sponsor to sign." if organiser and v["status"] == "draft" and not block else None),
                        "handoff": None if not intent.get("build_handoff") else intent["build_handoff"]},
            "versions": [version_row(x, x is v) for x in doc["versions"]]}


def _roles_footer(rows: list[dict], people: list[dict]) -> str:
    if not people:
        return "No roles drafted: the people list is empty. Add people in the profile first."
    guessed = sum(1 for r in rows if r["mark"] == "Guessed" and r["person"])
    if guessed:
        return f"Lens drafted {guessed} {'role' if guessed == 1 else 'roles'} from the people list. Check them."
    return "All six roles are stated." if all(r["person"] and r["mark"] == "Stated" for r in rows) else ""


# ---- mutations ------------------------------------------------------------------------------------------------------------

def _mutate_doc(store, sid: str, change) -> dict:
    """Read the charter document, change its live version, write it. The lock is the module's own, as its store uses."""
    with store._lock():
        doc = store.read(sid)
        if doc is None:
            raise LookupError("no charter")
        i = current_index(doc)
        doc["versions"][i] = change(doc["versions"][i], doc, i)
        store._save(doc)
        return doc


def _intent_to_closing(plane, intent_id: str, v: dict, sid_outcome: str | None, name_of_signer: str) -> None:
    """Signing moves an Initiative to closing, and sets the outcome (references only). The same move B01's table allows North."""
    def change(rec: dict) -> None:
        now = now_iso()
        if rec["state"] in ("open", "in_session"):
            lifecycle.move(rec, "closing", "north", now, note=f"Charter version {v['version']} signed by {name_of_signer}")
        rec["outcome"].update(charter_version=v["version"], signed_by=name_of_signer, signed_at=v["signatures"][-1]["at"],
                              problems=[p["id"] for p in v["problems"]], measures=None, build_needed=rec.get("build_needed"))
        if sid_outcome:
            rec.setdefault("refs", {})["charter_outcome_id"] = sid_outcome
    with S.locked(plane):  # re-entrant: update_intent takes the same lock
        S.update_intent(plane, intent_id, S.read_intent(plane, intent_id)["version"], change)


STALE = "The charter changed since you opened it. Read it again, then sign."


def seen_is_current(seen: dict, v: dict) -> bool:
    """The sponsor signs the version and the edit they read: {"version": n, "edited_at": iso|null} must match the live draft."""
    return seen.get("version") == v["version"] and seen.get("edited_at") == v.get("edited_at")


def intent_for_session(plane, sid: str) -> dict | None:
    """The intent whose wall session this is, or None. The module's own sign route uses it to send an Initiative to this route."""
    root = plane.path("intents")
    for f in sorted(root.glob("*/intent.json")) if root.is_dir() else []:
        rec = _read(plane, "intents", f.parent.name, "intent.json")
        if isinstance(rec, dict) and sid in ((rec.get("refs") or {}).get("wall_session_ids") or []):
            return rec
    return None


def sign_charter(request: Request, plane, intent: dict, seen: dict | None = None) -> None:
    sid = _sid(intent)
    C, store, settings = _m1(request, plane)
    doc = store.read(sid) if sid else None
    if doc is None:
        raise _refuse(409, "charter_missing", "There is no charter to sign yet.")
    v = doc["versions"][current_index(doc)]
    if v["status"] != "draft" or v["signatures"]:
        raise _refuse(409, "charter_read_only", "This charter is already signed or is with an approver. A change is a new version.")
    if seen is not None and not seen_is_current(seen, v):
        raise _refuse(409, "charter_stale", STALE)
    block = sign_blocker(v, intent)
    if block:
        raise _refuse(409, "charter_not_ready", block)
    people = _people_rows(request, plane)
    rv = _roles_record(request, plane, intent, sid, people)
    now, name = now_iso(), _name(request)
    if rv["roles"].get("sponsor"):  # the sponsor's signature counts as accepting the sponsor role (file 34)
        rv["answers"]["sponsor"] = {**blank_answer(), "state": "accepted", "asked_at": rv["answers"]["sponsor"].get("asked_at") or now,
                                    "at": now, "by": rv["roles"]["sponsor"]}
    frozen, risks = freeze_pages(plane, intent, v, rv, people)
    _mutate_doc(store, sid, lambda ver, d, i: {**ver, "pages_frozen": frozen, "risks": risks})
    signer = {"name": name, "account_id": request.state.account_id}
    s = store.sessions.get(sid)
    try:
        if s and s["state"] == "signing":
            store.sign(sid, signer, 1)
        else:  # a later version: the session is already closed, so the signature and the outcome are written here
            def sign(ver: dict, d: dict, i: int) -> dict:
                done = C.sign_in_room(ver, signer, 1, now)
                for j in range(i):
                    if d["versions"][j]["status"] == "signed" and not d["versions"][j].get("superseded_by"):
                        d["versions"][j] = {**d["versions"][j], "superseded_by": ver["version"], "superseded_at": now}
                return done
            done = _mutate_doc(store, sid, sign)["versions"][-1]
            from modules.m1_intent.domain import handoff as H
            from modules.m1_intent.store.files import write_json
            contracts = getattr(request.app.state, "m1_contracts_dir", None)
            write_json(plane.path("intents", "m1_intent", "outcomes", f"{s['outcome_id']}.json"),
                       H.build_outcome(H.load_outcome_contract(contracts), outcome_id=s["outcome_id"], session_id=sid, version=done))
    except C.CharterError as e:
        _mutate_doc(store, sid, lambda ver, d, i: {**ver, "pages_frozen": None})
        raise _refuse(409, "charter_not_ready", e.message) from None
    doc = store.read(sid)
    done = doc["versions"][current_index(doc)]
    if sid and rv["roles"].get("sponsor"):
        with lock_for(_roles_path(plane, sid)):
            _save_roles(plane, sid, rv, people)
    _intent_to_closing(plane, intent["id"], done, (s or {}).get("outcome_id"), name)
    freeze_hypothesis(plane, store, sid, intent, done["version"], name)
    record_charter_moment(plane, intent["id"], name)


def freeze_pages(plane, intent: dict, v: dict, rv: dict, people: list[dict]) -> tuple[dict, list]:
    """The pages 4 to 8 and the risks as they stand now, for a signature to freeze (line 1 of Build passes by the signature)."""
    pages = assemble(plane, intent, v, {"problems": v["problems"], "lists": []}, {"rows": roles_rows(rv, people, False)}, person_name(intent, "organiser"))
    risks = next(p for p in pages if p["key"] == "risks")["rows"]
    build = next(p for p in pages if p["key"] == "build")
    lines = [{**l, "ok": True} if l["key"] == "charter" else l for l in build["lines"]]
    build.update(lines=lines, passing=sum(1 for l in lines if l["ok"]) if lines else None)
    return {"pages": [p for p in pages if p["key"] in ("measures", "processes", "sources", "roles", "build")], "build": {
        "needed": build["needed"], "reason": build["reason"], "by": build["by"], "at": build["at"], "lines": lines}}, risks


def record_charter_moment(plane, intent_id: str, by: str) -> None:
    """The charter is a map update moment. A map failure never blocks or undoes a signature."""
    try:
        from sh_platform.graph import knowledge_map as km
        km.record_moment(plane, "charter_signed", intent_id, by)
    except Exception:  # noqa: BLE001 - the signature stands whatever the map does
        log.warning("The knowledge map was not updated for the charter of intent %s.", intent_id, exc_info=True)


def sync_approved(request: Request, plane, intent: dict) -> dict:
    """The approver link signs in the module, which knows nothing of intents. The next read of the charter finishes the job: freeze
    the pages, move the intent to closing, record the map moment. Returns the intent as it now stands."""
    sid = _sid(intent)
    if not sid or intent.get("state") not in ("open", "in_session"):
        return intent
    C, store, _ = _m1(request, plane)
    doc = store.read(sid)
    v = doc["versions"][current_index(doc)] if doc else None
    if not v or v["status"] != "signed" or not v["signatures"] or v["signatures"][-1].get("how") != "approver":
        return intent
    people = _people_rows(request, plane)
    rv = _roles_record(request, plane, intent, sid, people)
    frozen, risks = freeze_pages(plane, intent, v, rv, people)
    _mutate_doc(store, sid, lambda ver, d, i: {**ver, "pages_frozen": frozen, "risks": risks})
    s = store.sessions.get(sid) or {}
    _intent_to_closing(plane, intent["id"], v, s.get("outcome_id"), v["signatures"][-1]["name"])
    freeze_hypothesis(plane, store, sid, intent, v["version"], v["signatures"][-1]["name"])
    record_charter_moment(plane, intent["id"], v["signatures"][-1]["name"])
    return load_intent(plane, intent["id"])


def role_pulse_lines(plane, v, now) -> list[dict]:
    """Pulse lines for the reader to add (files 32, 34): a role ask for the named person, a decline for the organiser, and the
    sponsor's signature. Built from the records; B13's reader may call it."""
    from sh_platform.pulse import lines as pl
    from sh_platform.pulse.intent_lines import records  # one read of the records per Pulse request
    out = []
    me = Me(v.account_id, v.name, v.roles, v.shared_name)
    for intent in records(plane):
        if intent.get("type") != "initiative" or intent.get("state") not in ("open", "in_session", "closing") or not _sid(intent):
            continue
        rec_file = _read(plane, "intents", "m1_intent", "roles", f"{_sid(intent)}.json")
        if not isinstance(rec_file, dict):
            continue
        title, href = intent.get("title") or "An intent", f"/centre/intent/{intent['id']}/charter"
        rec = f"intents/{intent['id']}"
        for r, a in (rec_file.get("answers") or {}).items():
            if a.get("state") == "waiting" and r in ROLES:
                names = (rec_file.get("names") or {}).get(r)
                if pview.norm(me.name) in {pview.norm(n) for n in (names if isinstance(names, list) else [names]) if n}:
                    out.append(pl.line(f"role-ask:{intent['id']}:{r}", "decision", title, f"You are named as {LABEL[r].lower()}. Accept or decline.",
                                       f"{href}?role={r}", "Answer", rec, a.get("asked_at")))
            if a.get("state") == "declined" and "organiser" in roles_of(intent, me):
                out.append(pl.line(f"role-declined:{intent['id']}:{r}", "ops", title, f"The {LABEL[r].lower()} role was declined. Name someone else.",
                                   f"{href}?focus=roles", "Name someone", rec, a.get("at")))
        if "closer" in roles_of(intent, me) and intent.get("state") != "closing":
            out.append(pl.line(f"charter-sign:{intent['id']}", "signature", title, "The charter is ready for your signature.", href, "Open the charter", rec,
                               intent.get("updated_at")))
    return out


# ---- routes ------------------------------------------------------------------------------------------------------------

def _body(body: Any) -> dict:
    if not isinstance(body, dict):
        raise _refuse(400, "bad_request", "That could not be read. Please try again.")
    return body


def _ok(fn):
    """Plain answers for the module's charter errors."""
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except LookupError:
            return JSONResponse({"error": "intent_not_found", "message": "We could not find that."}, status_code=404)
        except ValueError as e:
            return JSONResponse({"error": "invalid", "message": str(e)}, status_code=422)
        except PermissionError as e:
            return JSONResponse({"error": "intent_read_only", "message": str(e)}, status_code=403)
    return run


@router.get("/api/intents/{intent_id}/charter")
def get_charter(request: Request, intent_id: str, version: int | None = None):
    plane, intent, me, roles, sid, people, rec = _access(request, intent_id)
    if not roles:  # named for a role only: the role request page
        return {"intent": {"id": intent["id"], "title": intent.get("title"), "purpose": intent.get("purpose"), "state": intent.get("state")},
                "tier": "named", "available": False, "message": "You can see the role you were asked to take.",
                "role_request": role_request(intent, me, rec, people)}
    view = _ok(build_view)(request, plane, intent, roles, version)
    if isinstance(view, dict) and rec is not None:
        view["role_request"] = role_request(intent, me, rec, people) if _named_person(me, rec, people) else None
    return view


@router.put("/api/intents/{intent_id}/charter")
def put_charter(request: Request, intent_id: str, body: dict | None = Body(None), a: IntentAccess = Depends(intent_roles(ORGANISER))):
    """The organiser's edits on a draft: the 'so that' lines, "Use this line", and a tied priority. A signed version refuses."""
    raw = _body(body)
    if not raw or not set(raw) <= {"so_that", "confirm_so_that", "priority", "success"}:
        raise _refuse(400, "bad_request", "That could not be read. Please try again.")
    sid = _sid(a.intent)
    C, store, settings = _m1(request, a.plane)
    name, now = _name(request), now_iso()
    if "success" in raw:  # 57: the success measures live on the hypothesis; the charter must still be an unsigned draft
        doc = store.read(sid) if sid else None
        cur = doc["versions"][current_index(doc)] if doc else None
        if not cur or cur["status"] != "draft" or cur["signatures"]:
            raise _refuse(409, "charter_read_only", "This charter is already signed or is with an approver. A change is a new version.")
        edit_success(a.plane, a.intent, raw["success"], name)
        if set(raw) == {"success"}:
            return _ok(build_view)(request, a.plane, a.intent, a.roles)

    def change(v: dict, doc: dict, i: int) -> dict:
        if v["status"] != "draft" or v["signatures"]:
            raise C.CharterError("read_only", "This charter is already signed or is with an approver. A change is a new version.")
        if "so_that" in raw:
            v = C.edit_purposes(v, raw["so_that"], settings, name, now)
        if "confirm_so_that" in raw:
            v = C.confirm_purposes(v, raw["confirm_so_that"], name, now)
        return C.edit_priorities(v, raw["priority"], settings, name, now) if "priority" in raw else v
    try:
        _mutate_doc(store, sid, change)
    except C.CharterError as e:
        raise _refuse(409 if e.code == "read_only" else 422, "charter_" + e.code, e.message) from None
    return _ok(build_view)(request, a.plane, a.intent, a.roles)


@router.post("/api/intents/{intent_id}/charter/sign")
def post_charter_sign(request: Request, intent_id: str, body: dict | None = Body(None), a: IntentAccess = Depends(intent_roles(CLOSER))):
    """Only the named sponsor signs, and only after "Are you the sponsor?" is answered Yes. Signing moves the intent to closing."""
    raw = _body(body)
    if raw.get("confirm_sponsor") is not True:
        raise _refuse(422, "sponsor_unconfirmed", "Please confirm that you are the sponsor.")
    if a.intent.get("type") != "initiative":
        raise _refuse(409, "charter_not_here", "Only an Initiative has a charter.")
    sign_charter(request, a.plane, a.intent, raw)
    fresh = load_intent(a.plane, intent_id)
    return _ok(build_view)(request, a.plane, fresh, roles_of(fresh, Me.of(request, a.plane)))


@router.post("/api/intents/{intent_id}/charter/versions")
def post_charter_version(request: Request, intent_id: str, body: dict | None = Body(None), a: IntentAccess = Depends(intent_roles(ORGANISER))):
    """Start a new version: a draft copy of the signed one. The signed one stays current for Build until the new one is signed."""
    comment = _body(body or {}).get("comment")
    C, store, _ = _m1(request, a.plane)
    sid = _sid(a.intent)
    doc = store.read(sid) if sid else None
    if doc is None or doc["versions"][current_index(doc)]["status"] != "signed":
        raise _refuse(409, "charter_not_signed", "A new version starts from a signed charter.")
    with store._lock():
        doc = store.read(sid)
        doc["versions"].append(new_draft(doc["versions"][current_index(doc)], len(doc["versions"]) + 1, _name(request), now_iso(), comment if isinstance(comment, str) else None))
        store._save(doc)
    return _ok(build_view)(request, a.plane, a.intent, a.roles)


@router.post("/api/intents/{intent_id}/charter/versions/{n}/discard")
def post_charter_discard(request: Request, intent_id: str, n: int, body: dict | None = Body(None), a: IntentAccess = Depends(intent_roles(ORGANISER))):
    reason = _body(body).get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise _refuse(422, "reason_needed", "Please say why this draft is discarded.")
    C, store, _ = _m1(request, a.plane)
    sid = _sid(a.intent)

    def change(v: dict, doc: dict, i: int) -> dict:
        if v["version"] != n or v["version"] < 2 or v["status"] == "signed" or v["signatures"]:
            raise C.CharterError("read_only", "Only a draft that is version 2 or later can be discarded.")
        return {**v, "discarded": {"by": _name(request), "at": now_iso(), "reason": reason.strip()[:300]}}
    try:
        _mutate_doc(store, sid, change)
    except C.CharterError as e:
        raise _refuse(409, "charter_read_only", e.message) from None
    return _ok(build_view)(request, a.plane, a.intent, a.roles)


@router.put("/api/intents/{intent_id}/charter/risks")
def put_charter_risks(request: Request, intent_id: str, body: dict | None = Body(None), a: IntentAccess = Depends(intent_roles(ORGANISER))):
    """Tick or untick "Accept this risk" per line: {"accept": [text, ...], "unaccept": [text, ...]}. Draft only."""
    raw = _body(body)
    C, store, _ = _m1(request, a.plane)
    sid, name, now = _sid(a.intent), _name(request), now_iso()
    pages = build_view(request, a.plane, a.intent, a.roles)["pages"]
    derived = next(p for p in pages if p["key"] == "risks")["rows"]
    accept, undo = set(raw.get("accept") or []), set(raw.get("unaccept") or [])

    def change(v: dict, doc: dict, i: int) -> dict:
        if v["status"] != "draft" or v["signatures"]:
            raise C.CharterError("read_only", "This charter is already signed or is with an approver. A change is a new version.")
        rows = [{**r, **({"accepted_by": name, "accepted_at": now} if r["text"] in accept else
                         {"accepted_by": None, "accepted_at": None} if r["text"] in undo else {})} for r in derived]
        return {**v, "risks": rows, "edited_at": now, "edited_by": name}
    try:
        _mutate_doc(store, sid, change)
    except C.CharterError as e:
        raise _refuse(409, "charter_read_only", e.message) from None
    return _ok(build_view)(request, a.plane, a.intent, a.roles)


def _access(request: Request, intent_id: str):
    """(plane, intent, me, roles, sid, people, roles record). A person named for a role may reach the intent's roles even when the
    intent does not otherwise show them; anyone else with no role here does not know it exists (404)."""
    plane = _plane(request)
    intent = load_intent(plane, intent_id)
    me, sid = Me.of(request, plane), _sid(intent)
    roles = roles_of(intent, me)
    people = _people_rows(request, plane) if sid else []
    rec = _roles_record(request, plane, intent, sid, people) if sid else None
    if not roles and not (rec and _named_person(me, rec, people)):
        raise _refuse(404, "intent_not_found", "We could not find that.")
    return plane, intent, me, roles, sid, people, rec


def _roles_context(request: Request, intent_id: str, organiser_only: bool):
    plane, intent, me, roles, sid, people, rec = _access(request, intent_id)
    if organiser_only and "organiser" not in roles:
        raise _refuse(403, "intent_read_only", "Only the organiser can name the roles.")
    if rec is None:
        raise _refuse(409, "charter_missing", "This Initiative has no wall, so no roles can be named yet.")
    return plane, intent, me, roles, sid, people, rec


def role_request(intent: dict, me: Me, rec: dict, people: list[dict]) -> dict:
    """What a named person sees (file 34, screen B): their roles, the duty, the purpose and end date, who else is named."""
    mine = _named_person(me, rec, people)
    rows = roles_rows(rec, people, False)
    tb = intent.get("time_box") or {}
    return {"intent": {"id": intent["id"], "title": intent.get("title"), "purpose": intent.get("purpose"), "ends": tb.get("ends")},
            "organiser": person_name(intent, "organiser"), "mine": [r for r in rows if r["role"] in mine],
            "others": [{**r, "answer": {"state": r["answer"]["state"]}} for r in rows if r["role"] not in mine and r["person"]],
            "handed_over": bool(rec.get("handed_over_at"))}


def _roles_answer(request: Request, plane, intent: dict, roles: frozenset[str], rec: dict, people: list[dict]) -> dict:
    organiser = "organiser" in roles or "company_admin" in roles
    return {"rows": roles_rows(rec, people, organiser), "footer": _roles_footer(roles_rows(rec, people, False), people),
            "people": [{"id": p["id"], "name": p["name"], "role": p["role"]} for p in people] if "organiser" in roles else []}


@router.get("/api/intents/{intent_id}/roles")
def get_roles(request: Request, intent_id: str):
    plane, intent, me, roles, sid, people, rec = _roles_context(request, intent_id, False)
    return {**_roles_answer(request, plane, intent, roles, rec, people), "mine": _named_person(me, rec, people)}


@router.put("/api/intents/{intent_id}/roles")
def put_roles(request: Request, intent_id: str, body: dict | None = Body(None)):
    """The organiser names, confirms or clears roles: {"developer": "<person id>"}, {"developer": null}, {"informed": [ids]}. Each saves at once."""
    plane, intent, me, roles, sid, people, rec = _roles_context(request, intent_id, True)
    if intent.get("state") in S.STATES[-2:]:
        raise _refuse(409, "intent_closed", "This intent is closed. It is kept as it was and cannot be changed.")
    ch = _body(body)
    if not ch:
        raise _refuse(400, "bad_request", "That could not be read. Please try again.")

    def run():
        with lock_for(_roles_path(plane, sid)):
            set_roles(rec, ch, people, _name(request), now_iso())
            _save_roles(plane, sid, rec, people)
        return {**_roles_answer(request, plane, intent, roles, rec, people), "mine": _named_person(me, rec, people)}
    return _ok(run)()


@router.post("/api/intents/{intent_id}/roles/ask")
def post_roles_ask(request: Request, intent_id: str, body: dict | None = Body(None)):
    plane, intent, me, roles, sid, people, rec = _roles_context(request, intent_id, True)
    which = (_body(body or {}).get("roles")) or None

    def run():
        with lock_for(_roles_path(plane, sid)):
            asked = ask_roles(rec, which, now_iso())
            if asked:
                _save_roles(plane, sid, rec, people)
        return {**_roles_answer(request, plane, intent, roles, rec, people), "asked": asked}
    return _ok(run)()


@router.post("/api/intents/{intent_id}/roles/{role}/answer")
def post_roles_answer(request: Request, intent_id: str, role: str, body: dict | None = Body(None)):
    plane, intent, me, roles, sid, people, rec = _roles_context(request, intent_id, False)
    mine = _named_person(me, rec, people)
    if role not in mine:
        raise _refuse(403, "intent_read_only", "Only the person named for this role can answer.")
    b = _body(body)
    pid = next(iter(_my_pids(me, people) & _ids(rec["roles"][role])))

    def run():
        with lock_for(_roles_path(plane, sid)):
            answer_role(rec, role, pid, str(b.get("answer") or ""), b.get("reason"), now_iso())
            _save_roles(plane, sid, rec, people)
        return {**_roles_answer(request, plane, intent, roles, rec, people), "mine": mine}
    return _ok(run)()
