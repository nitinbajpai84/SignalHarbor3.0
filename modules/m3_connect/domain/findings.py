"""Findings and the risk list (M3-P03). findings.json = {"measures": {measure_id: entry}, "risks": [risk]}.

entry: {measure, name, group: ready|unclear|unknown, reasons[], pain_points[{id,title}], levers[{id,title}], problem, result}
risk:  {id, kind: risk|ambiguity|unknown, text, measures[], pain_points[], decision: null}
The customer's decision on a risk (accepted or sent back, with a note) is written by M3-P04 into `decision`; a rebuild keeps it.
A measure goes to
  ready   its rule matches the figure reported (or a person checked the rule and there is nothing to compare with); an ambiguity module 2
          accepted is a known risk, listed with the risks, and does not stop it;
  unclear a gap, owners who disagree, no definition, an ambiguity still open in module 2;
  unknown no rule written ("No rule yet"), no source data, a figure that cannot be worked out, a restricted measure with no data.
A risk about a restricted measure carries `restricted: true`: the head of data decides it, not the sponsor (D9).
Pain points and levers come through the charter: the ones that name the measure, or share one of its problems.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.jsonfile import lock_for

from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import trial as T

HIDDEN = {"name": I.RESTRICTED_NAME, "restricted": True}


def technical_of(measure: dict) -> tuple[str, list[dict]]:
    """(the technical definition as one text, the ambiguities) of a measure; ("", []) when module 2 has not added the block yet."""
    t = measure.get("technical") if isinstance(measure.get("technical"), dict) else {}
    text = " ".join(v for k in ("calculation", "filters", "grain", "period", "currency_basis") if (v := I._t(t.get(k)).strip()) and v != "unknown")  # a part is plain or a provenance cell
    return text, [a for a in measure.get("ambiguities") or [] if isinstance(a, dict)]


def _linked(items: list[dict], measure: dict) -> list[dict]:
    probs = set(measure.get("problem_ids") or [])
    return [{"id": i["id"], "title": i.get("title")} for i in items
            if measure["id"] in (i.get("measures") or []) or probs & set(i.get("problem_ids") or [])]


def _classify(m: dict, t: dict | None, rec: dict | None, marks: list[dict]) -> tuple[str, list[str]]:
    reasons, unclear, known = [], False, []
    _, ambiguities = technical_of(m)
    for a in ambiguities:
        text = str(a.get("text") or a.get("question") or "an ambiguity")
        if a.get("status") == "open":
            unclear = True
            reasons.append("Open in the baseline: " + text)
        elif a.get("status") == "accepted":  # module 2 accepted it: a known risk, listed with the risks, not a blocker
            known.append("Known risk, accepted in module 2: " + text)
    if any(s.get("owners_disagree") for s in marks):
        unclear = True
        reasons.append("The people who own the sources disagree about it.")
    if not str(m.get("definition") or "").strip() and not technical_of(m)[0]:
        unclear = True
        reasons.append("The measure has no definition to work from.")
    if rec and rec.get("state") == R.COULD_NOT and rec.get("reason_kind") == "invalid":
        unclear = True
        reasons.append("The definition could not be turned into a rule: " + str(rec.get("reason") or "unclear wording") + ".")
    t = t or {}
    if not rec or rec.get("state") == R.COULD_NOT or not rec.get("rule"):  # no rule written: never ready, whatever else is known
        why = str((rec or {}).get("reason") or t.get("missing") or "").strip().rstrip(".")
        return "unknown", ["No rule yet" + (f": {why}." if why else ".")] + reasons + known
    if t.get("result") == "gap":
        return "unclear", [f"Lens and your figure differ. {t.get('likely_reason')}".strip()] + reasons + known
    if t.get("our_figure") is None:
        return "unknown", [t.get("missing") or "It cannot be worked out yet."] + reasons + known
    if unclear:
        return "unclear", reasons + known
    if t.get("result") == "matches":
        n = len(known)
        return "ready", ["Lens's figure matches yours."] + ([f"{n} known risk{'s' if n != 1 else ''} from module 2 {'are' if n != 1 else 'is'} listed with the risks."] if n else [])
    if rec.get("state") == "checked":
        return "ready", ["The rule was checked by " + str(rec.get("checked_by")) + "; there is no figure from you to compare with."]
    return "unclear", [t.get("missing") or "There is no figure from you to compare with."] + known


def build(adir: Path, inputs: dict, hidden: set[str]) -> dict:
    """Writes and returns findings.json from the trial, the rules and the inputs; entries and risks for `hidden` measures are kept as they were."""
    rules, trial = R.read_rules(adir), R.read_file(adir, "trial.json", {})
    old = R.read_file(adir, "findings.json", {})
    old = old if isinstance(old, dict) else {}
    old_m, old_risks = old.get("measures") or {}, [r for r in old.get("risks") or [] if isinstance(r, dict)]
    decisions = {r.get("id"): r.get("decision") for r in old_risks}
    marks = T.source_marks(adir)
    out_m, risks = {}, []
    for m in inputs.get("measures") or []:
        mid = m["id"]
        if mid in hidden:
            out_m[mid] = old_m.get(mid) or {"measure": mid, "group": "unknown", "reasons": ["Restricted: not looked at yet."], "pain_points": [], "levers": [], "restricted": True}
            risks += [r for r in old_risks if mid in r.get("measures", []) and not str(r.get("id")).startswith("risk-source")] or \
                [{"id": f"risk-measure-{mid}", "kind": "unknown", "text": "A restricted measure has no data yet.", "measures": [mid], "pain_points": [], "decision": None}]
            continue
        mine = [s for s in marks if mid in [str(x) for x in s.get("measures") or s.get("measures_fed") or []]]
        group, reasons = _classify(m, trial.get(mid), rules.get(mid), mine)
        pps, lv = _linked(inputs.get("pain_points") or [], m), _linked(inputs.get("levers") or [], m)
        out_m[mid] = {"measure": mid, "name": m.get("name"), "group": group, "reasons": reasons, "pain_points": pps, "levers": lv,
                      "problem": m.get("problem"), "result": (trial.get(mid) or {}).get("result")}
        pp_ids = [p["id"] for p in pps]
        for a in technical_of(m)[1]:
            if a.get("status") in ("open", "accepted"):
                risks.append({"id": f"risk-ambiguity-{mid}-{a.get('id')}", "kind": "ambiguity", "measures": [mid], "pain_points": pp_ids, "decision": None,
                              "text": f"{m.get('name')}: {a.get('text') or a.get('question')}" + (" (still open in the baseline)." if a["status"] == "open" else ""),
                              **({"accepted_in_module_2": {"by": a.get("by"), "at": a.get("at"), "reason": a.get("reason")}} if a["status"] == "accepted" else {})})
        if group != "ready":
            kind = "unknown" if group == "unknown" else "ambiguity" if any("definition" in r or "disagree" in r for r in reasons) else "risk"
            risks.append({"id": f"risk-measure-{mid}", "kind": kind, "measures": [mid], "pain_points": pp_ids, "decision": None,
                          "text": f"{m.get('name')} is {group}. " + " ".join(reasons[:2])})
    seen = {I._t(s.get("Source ID")) for s in inputs.get("sources") or []}
    names = {m["id"]: m.get("name") for m in inputs.get("measures") or []}
    for s in marks:
        sid = str(s["id"])
        fed = [x for x in (str(x) for x in s.get("measures") or s.get("measures_fed") or []) if x not in hidden and x in names]
        if sid not in seen or not fed:
            continue
        pp = sorted({p["id"] for x in fed for p in out_m.get(x, {}).get("pain_points", [])})
        for flag, text in (("blocked_upstream", f"{s.get('name')} is blocked upstream, so its data cannot arrive until that is released."),
                           ("licence", f"{s.get('name')} needs a licence before its data can be used.")):
            if s.get(flag):
                risks.append({"id": f"risk-source-{sid}-{flag}", "kind": "risk", "text": text, "measures": fed, "pain_points": pp, "decision": None, "source": sid})
    for g in inputs.get("gaps") or []:
        if g.get("kind") == "personal_undecided" and g.get("kpi_id") in names and g["kpi_id"] not in hidden:
            risks.append({"id": f"risk-personal-{g['kpi_id']}", "kind": "unknown", "measures": [g["kpi_id"]],
                          "pain_points": [p["id"] for p in out_m[g["kpi_id"]]["pain_points"]], "decision": None,
                          "text": f"It is not yet decided whether {names[g['kpi_id']]} uses personal data."})
    sent_back = {k: v for k, v in ((R.read_file(adir, "decisions.json", {}).get("risks")) or {}).items() if isinstance(v, dict) and v.get("decision") == "sent_back"}
    was = {r.get("id"): r.get("rechecked_at") for r in old_risks}
    guarded = {m["id"] for m in inputs.get("measures") or [] if m.get("restricted") or m.get("guarded")}  # the head of data decides these (D9)
    uniq = {}
    for r in risks:
        r["decision"] = decisions.get(r["id"])
        if set(r.get("measures") or []) & (guarded | hidden):
            r["restricted"] = True
        back = sent_back.get(r["id"])
        if back:  # a sent-back risk counts as decided only after a re-check: this run is that re-check, unless it already happened after the decision
            r["rechecked_at"] = was.get(r["id"]) if str(was.get(r["id"]) or "") > str(back.get("at") or "") else datetime.now(timezone.utc).isoformat()
        uniq[r["id"]] = r
    left = [{"measure": x["kpi_id"], "name": x.get("name"), "reason": x.get("reason"), "by": x.get("by"), "at": x.get("at"),
             "restricted": bool(x.get("restricted"))} for x in inputs.get("left_out") or []]
    data = {"measures": out_m, "risks": list(uniq.values()), "left_out": left, "built_at": R.now()}
    R.write_file(adir, "findings.json", data)
    return data


def _salt(adir: Path) -> bytes:
    """The assessment's random salt (trial_salt.json, owned by M3-P03), created once. Never sent to a client."""
    adir = Path(adir)
    with lock_for(adir):
        got = R.read_file(adir, "trial_salt.json", {})
        if not (isinstance(got.get("salt"), str) and len(got["salt"]) == 32):
            got = {"salt": secrets.token_hex(16)}
            R.write_file(adir, "trial_salt.json", got)
    return got["salt"].encode()


def opaque_id(adir: Path, risk_id: str) -> str:
    """What a viewer who may not see a source gets as the id of a risk about it: an HMAC with the assessment's salt, so guessing the
    few possible real ids and hashing them finds nothing. The same every time for the same risk."""
    return "risk-" + hmac.new(_salt(adir), str(risk_id).encode(), hashlib.sha256).hexdigest()[:24]


def real_id(adir: Path, data: dict, given: str) -> str | None:
    """Server side: the real risk id for an id a client sent (the real one, or the opaque one), or None. M3-P04 uses it to match decisions."""
    return next((r["id"] for r in data.get("risks") or [] if given in (r["id"], opaque_id(adir, r["id"]))), None)


def for_viewer(data: dict, hidden: set[str], sources_seen: set[str] | None = None, adir: Path | None = None, terms: list[str] = ()) -> dict:
    """What this viewer may see of findings.json: a hidden measure is "A restricted measure" and nothing else, and so are the risks touching it;
    a risk about a source that is not in the viewer's visible sources (`sources_seen`, from inputs.read_inputs) names no source or measure."""
    ms = {k: ({"measure": k, "group": v.get("group"), "reasons": [], "pain_points": [], "levers": [], **HIDDEN} if k in hidden
              else {**v, "reasons": [I.mask_text(x, terms) for x in v.get("reasons") or []]})  # a reason may name a row this reader may not see
          for k, v in (data.get("measures") or {}).items()}
    def mask(r: dict) -> dict:
        if r.get("source") and sources_seen is not None and r["source"] not in sources_seen:
            return {**r, "id": opaque_id(adir, r["id"]), "text": "A restricted source has something open.", "measures": [], "pain_points": [], "source": None}
        if set(r.get("measures") or []) & hidden:
            return {**r, "text": I.RESTRICTED_NAME + " has something open.", "pain_points": []}
        return r
    risks = [{**r, "text": I.mask_text(r.get("text"), terms)} for r in map(mask, data.get("risks") or [])]
    left = [{"measure": x.get("measure"), "name": I.RESTRICTED_NAME, "reason": None, "restricted": True} if x.get("measure") in hidden
            else {**x, "reason": I.mask_text(x.get("reason"), terms)} for x in data.get("left_out") or []]
    return {**data, "measures": ms, "risks": risks, "left_out": left}


def state(adir: Path) -> dict:
    d = R.read_file(Path(adir), "findings.json", {})
    if isinstance(d, dict) and d.get("measures") and T.source_ids(adir):  # findings count only once some source data arrived
        return {"state": "done", "waiting_on": ""}
    return {"state": "not_started", "waiting_on": ""}
