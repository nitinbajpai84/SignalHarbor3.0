"""Sign-off for Decision 1: only a person the 2.0 seat rules allow may sign; anyone else sends the brief to a signer and is never stuck.

Rules are the 2.0 ones (i4_routes._may_sign, seats.DECISION_MAKER). The signer is the office's sponsor, else its company admin. The signed
record stays in the signer's name (v3_harbor.a_sign signs as the person who clicked Confirm). State lives on the thread as `signoff`."""
from sh_platform.profile.view import Viewer
from sh_platform.v1 import v3_skills as S
from sh_platform.v1.seats import DECISION_MAKER, SEAT_ROLES, seat_of

SIGN_ROLES = SEAT_ROLES[DECISION_MAKER]  # sponsor, company_admin


def _now() -> str:
    from sh_platform.v1.v3_harbor import now
    return now()


def _viewer(app, account_id) -> Viewer:
    a = app.state.account_store.get(account_id) or {}
    return Viewer(a.get("display_name") or "", frozenset(a.get("roles") or []), False, account_id)


def signers(app, plane) -> list[dict]:
    """The people who may sign in this office: sponsors first, then company admins."""
    accts = [a for a in app.state.account_store.in_company(plane.company_id) if DECISION_MAKER in seat_of(a.get("roles") or []) and not a.get("disabled")]
    accts.sort(key=lambda a: ("sponsor" not in (a.get("roles") or []), a.get("display_name") or ""))
    st = app.state.account_store
    return [{"id": a["account_id"], "name": a.get("display_name"), "email": (st.get(a["account_id"]) or {}).get("email")} for a in accts]


def may_sign(app, plane, th, account_id) -> bool:
    from sh_platform.v1.i4_routes import _may_sign
    v = _viewer(app, account_id)
    if _may_sign(plane, v, th.get("iid") or ""):
        return True
    # the person who started the thread raised its intent; with a role beyond participant that is enough (same rule as 2.0)
    return bool(set(v.roles) - {"participant"}) and bool(v.name) and v.name == th.get("started_by")


def _names(sg: list[dict]) -> str:
    n = [s["name"] for s in sg if s.get("name")]
    return ", ".join(n[:-1]) + " or " + n[-1] if len(n) > 1 else (n[0] if n else "")


def refusal(app, plane) -> str:
    sg = signers(app, plane)
    return (f"You cannot sign this. {_names(sg)} can; use \"Send to {sg[0]['name']} to confirm\"." if sg
            else "No one in this office may sign yet. Ask your administrator to give someone the sponsor role.")


def state(app, plane, th, account_id) -> dict | None:
    """What this person sees on Decision 1: `can_sign`, `send` (they may not sign: send it), `waiting` (they sent it) or `awaiting_you` (sent to them)."""
    if th.get("stage") != "decision1":
        return None
    so, sg = th.get("signoff") or {}, signers(app, plane)
    me = app.state.account_store.get(account_id) or {}
    base = {"signers": sg, "raised_by": th.get("started_by")}
    if may_sign(app, plane, th, account_id):
        return {**base, "state": "awaiting_you" if so else "can_sign", **({"sent_by": so.get("by"), "sent_at": so.get("at")} if so else {})}
    if so:
        return {**base, "state": "waiting", "signer": so["to"], "sent_at": so["at"], "mine": so.get("by_id") == account_id}
    gaps = blocking(plane, th.get("iid")) if sg else []
    if gaps:  # the signer could not sign it as it stands: the raiser fills or answers first, so the brief never travels unsignable
        return {**base, "state": "fill", "gaps": gaps, "signer": sg[0], "message": gap_question(th, sg[0]["name"], gaps), "me": me.get("display_name")}
    return {**base, "state": "send" if sg else "none", "signer": (sg or [None])[0], "message": refusal(app, plane), "me": me.get("display_name")}


def heal(plane, th) -> dict:
    """A thread that stopped at the sign step because its person may not sign (the old dead end) goes back to Decision 1, brief intact."""
    r = th.get("resume") or {}
    q = next((e.get("text") or "" for e in reversed(th["events"]) if e["kind"] == "question"), "")
    if th.get("stage") == "question" and r.get("chain") == "A" and r.get("i") == 0 and th.get("brief") and (
            q.startswith("Only the person who raised this") or q.startswith("You cannot sign this") or q.startswith("No one in this office may sign")):
        from sh_platform.v1.v3_harbor import ev, save
        th["stage"], th["resume"] = "decision1", None
        th["decision"] = {"n": 1, "title": "Is this what you want?", "brief": th["brief"], "gaps": []}
        ev(th, "harbor", "This brief needs a signer. Send it to the person who can confirm it.")
        save(plane, th)
    elif th.get("stage") == "question" and r.get("chain") == "A" and r.get("i") == 0 and th.get("iid") and q.startswith("Before ") and "I still need from" in q:
        # the signer's gap fill left a part only a person can say: back to the raiser's Decision 1 with the gap named; they send it again
        from sh_platform.v1 import i4_sow as SW
        from sh_platform.v1.v3_harbor import brief, ev, save
        try:
            b = brief(SW.read(plane, th["iid"]))  # the brief as the signer's fill left it
        except SW.SowError:
            b = th.get("brief")
        th["stage"], th["resume"] = "decision1", None
        th["decision"] = {"n": 1, "title": "Is this what you want?", "brief": b, "gaps": blocking(plane, th["iid"])}
        th.pop("signoff", None)
        ev(th, "harbor", "Back to you: answer what is still open above, then send it to the signer again.")
        save(plane, th)
    return th


def decorate(app, plane, v: dict, account_id) -> dict:
    from sh_platform.v1.v3_harbor import load, view
    if v.get("stage") == "question":
        v = view(heal(plane, load(plane, v["id"])))
    if v.get("stage") != "decision1":
        return v
    return {**v, "signoff": state(app, plane, load(plane, v["id"]), account_id)}


def send(app, plane, th, to, account_id) -> None:
    """Park Decision 1 on the signer's Action card. The thread keeps its stage; the raiser sees 'waiting for <signer>'."""
    if th.get("stage") != "decision1":
        raise ValueError("Decision 1 is not waiting for you.")
    if may_sign(app, plane, th, account_id):
        raise ValueError("You can confirm this yourself.")
    sg = signers(app, plane)
    if not sg:
        raise ValueError(refusal(app, plane))
    pick = next((s for s in sg if to and (to.lower() in (str(s["email"]).lower(), str(s["name"]).lower()))), None) if to else sg[0]
    if not pick:
        raise ValueError(f"{to} cannot sign. Choose {_names(sg)}.")
    gaps = blocking(plane, th.get("iid"))
    if gaps:
        raise ValueError(gap_question(th, pick["name"], gaps))
    me = app.state.account_store.get(account_id) or {}
    with S.record(plane, th["id"], "intent.sign") as rec:
        th["signoff"] = {"to": pick, "by": me.get("display_name"), "by_id": account_id, "at": _now()}
        from sh_platform.v1.v3_harbor import ev
        ev(th, "harbor", f"Sent to {pick['name']} to confirm. You will see it here once it is signed.")
        rec["detail"] = f"sent to {pick['name']}"


def guard(app, plane, th, n, answer, account_id) -> None:
    """Called by decide before Confirm acts. A person who may not sign cannot confirm; the signer's confirm closes the hand-off."""
    if n != 1 or th.get("stage") != "decision1":
        return
    if answer == "confirm" and not may_sign(app, plane, th, account_id):
        raise ValueError(refusal(app, plane))
    if answer == "not_yet" and th.get("signoff"):
        th.pop("signoff")  # the signer sent it back: the raiser can change the brief and send it again
    if answer == "confirm" and th.get("signoff"):
        th["signoff"]["confirmed_at"] = _now()


def check_signer(x) -> None:
    """a_sign: sign as the person at the screen, never another account. If they may not, the question names who may."""
    if not may_sign(x.app, x.plane, x.th, x.account_id):
        from sh_platform.v1.v3_harbor import Q
        raise Q(refusal(x.app, x.plane))


def record_line(th, sig_name) -> str | None:
    if not (th.get("started_by") and sig_name):
        return None
    return f"Raised by {th['started_by']} · Confirmed and signed by {sig_name}"


def needs(app, plane, th, d, account_id) -> dict | None:
    """The Action-queue item for a Decision 1 thread, as this person sees it (None: leave the standard card)."""
    st = state(app, plane, th, account_id)
    if not st or st["state"] in ("can_sign",):
        return None
    base = {"thread": th["id"], "title": d["title"], "text": th["title"]}
    if st["state"] == "awaiting_you":
        return {**base, "kind": "decision", "text": f"{th['title']} (raised by {th.get('started_by')})", "actions": [{"label": "Confirm", "answer": "confirm"}, {"label": "Not yet", "answer": "not_yet"}]}
    if st["state"] == "waiting":
        return {**base, "kind": "decision", "waiting": True, "text": f"Waiting for {st['signer']['name']} to confirm.", "actions": []}
    if st["state"] == "send":
        return {**base, "kind": "decision", "actions": [{"label": f"Send to {st['signer']['name']} to confirm", "answer": "send_for_signature"}]}
    return {**base, "kind": "question", "text": st["message"], "actions": [{"label": "Open the thread", "answer": "open"}]}


def desk_for(app, plane, account_id) -> dict:
    """The Action queue as this person sees it: Decision 1 cards become Confirm (the signer), Send (cannot sign) or Waiting (sent)."""
    from sh_platform.v1.v3_harbor import all_threads, desk as base, load
    for t in all_threads(plane):
        heal(plane, t)
    desk, out = base(plane), []
    for n in desk["needs"]:
        th = load(plane, n["thread"]) if n["kind"] == "decision" and n["thread"] else None
        mine = needs(app, plane, th, th["decision"], account_id) if th and th.get("stage") == "decision1" and th.get("decision") else None
        out.append(mine or n)
    return {**desk, "needs": out}


# ---- no dead end: the gaps a signer would face are shown, filled or asked before the brief travels (test cycle 1) ------------------

GAP_Q = "Before {signer} can sign this, I still need from {raiser}: "


def accept_drafts(x, iid: str) -> None:
    """North's drafted lines count as filled (the person reviews them in Decision 1). A raiser who may not write the intent of work
    (a participant) still gets their own drafts in their brief, accepted in their name as North's draft; the signer confirms them on signing."""
    from sh_platform.v1 import l2_proposals as L2
    me = (x.app.state.account_store.get(x.account_id) or {}).get("display_name") if getattr(x, "app", None) else None
    for pr in x.api("me", "GET", f"/api/v1/intents/{iid}/proposals", soft=True).get("pending", []):
        if x.api("me", "POST", f"/api/v1/intents/{iid}/proposals/{pr['id']}/accept", soft=True) or not me or me != x.th.get("started_by"):
            continue
        if pr.get("document") in ("sow", "process_map"):  # ponytail: only the raiser's own unsigned brief; signing stays the signer's act
            try:
                L2.accept(x.plane, iid, pr["id"], f"{me} (North's draft; confirmed when signed)")
            except Exception:  # noqa: BLE001 - a draft that cannot apply stays pending and its gap stays shown
                pass


def _after_confirm(sow: dict) -> dict:
    """The intent of work as Confirm leaves it (v3_harbor._no_earlier_figures), without writing it: what a self-signer would face."""
    import copy
    sow = copy.deepcopy(sow)
    for k in sow.get("kpis") or []:
        if isinstance(k, dict):
            k.setdefault("benchmark", None)
            if k.get("pack_suggested") and k.get("status") == "unclear":
                k["status"] = "defined"
    return sow


def blocking(plane, iid: str | None) -> list[str]:
    """The must-fill parts a Confirm would still not cover (same check as signing, t1_templates.sign_block)."""
    if not iid:
        return []
    from sh_platform.v1 import t1_templates as T
    try:
        pin = T._read(T.N._path(plane, iid, "template.json"))
    except T.N.Refused:  # no such intent: nothing to check
        return []
    if pin is None:
        return []
    sow = _after_confirm(T.record_for_intent(plane, iid))
    pinned = pin.get("companions") or {}
    gaps = []
    for kind in ("intent_of_work", *(k for k in T.COMPANIONS if k in pinned)):
        t = T.for_intent(plane, iid, kind)
        gaps += [(f"{T.KINDS[kind]}: {g}" if kind != "intent_of_work" else g) for g in (T.missing_required(t, sow) if t else [])]
    return gaps


def gap_question(th, signer: str, gaps: list[str]) -> str:
    return (GAP_Q.format(signer=signer, raiser=th.get("started_by") or "you") + "; ".join(gaps)
            + ". Tell me in your own words, or say \"use the usual practice\"; then send it again.")


def fill(x, gaps: list[str]) -> list[str]:
    """The self-signer's gap fill (v3_harbor._north): North fills what is open with the usual practice, twice at most; a first report
    has no earlier figures. Returns what is still open."""
    from sh_platform.v1 import v3_harbor as H
    iid = x.th["iid"]
    with H._skill(x, "intent.fill-with-practice", "Filling the open parts with the usual practice"):
        for _ in range(2):
            if not gaps:
                break
            x.api("me", "POST", f"/api/v1/intents/{iid}/chat", {"text": H.FILL + "; ".join(gaps)})
            gaps = H._gaps(x, iid)
        if gaps and all("last period" in g for g in gaps):
            x.api("me", "POST", f"/api/v1/intents/{iid}/chat", {"text": H.NO_EARLIER})
            gaps = H._gaps(x, iid)
    return gaps


def before_sign(x) -> None:
    """a_sign, before the signature: the signer's Confirm runs the self-signer's gap fill. What only a person can say goes back to the
    raiser's Decision 1 as a question naming the gap (heal turns it round); the brief never sits signed-but-unsignable."""
    from sh_platform.v1 import v3_harbor as H
    iid = x.th["iid"]
    H._no_earlier_figures(x.app, x.plane, iid)
    H._gaps(x, iid)  # North's drafts are accepted first, by the signer
    gaps = blocking(x.plane, iid)
    if gaps:
        gaps = fill(x, gaps)
        H._no_earlier_figures(x.app, x.plane, iid)
        gaps = blocking(x.plane, iid)
    if gaps:
        me = (x.app.state.account_store.get(x.account_id) or {}).get("display_name") or "the signer"
        raise H.Q(gap_question(x.th, me, gaps))


def claim_files(x) -> int:
    """At sign-off: files dropped before it that no thread has claimed (the brief named no source yet, or several threads were open)
    are claimed by this thread when their name shares a word with its question or its sources. Returns how many."""
    from sh_platform.v1 import v3_harbor as H
    th = x.th
    words = H._toks(" ".join([th.get("title") or "", (th.get("brief") or {}).get("question") or ""] + list(th.get("sources") or [])))
    n = 0
    with S.record(x.plane, th["id"], "data.recognise-file") as rec, H.LOCK:
        fs = H.read_files(x.plane)
        for f in fs:
            if f["status"] in ("waiting", "question") and not f.get("thread") and "benchmark" not in H._toks(f["name"]) and H._toks(f["name"]) & words:
                src = max(th.get("sources") or [""], key=lambda s: len(H._toks(s) & H._toks(f["name"])))
                f["status"], f["thread"] = "recognised", th["id"]
                f["source"] = src if H._toks(src) & H._toks(f["name"]) else f["name"].rsplit(".", 1)[0].replace("_", " ")
                n += 1
        if n:
            H._fp(x.plane).write_text(__import__("json").dumps(fs), encoding="utf-8")
        rec["detail"] = f"{n} files dropped before sign-off claimed"
    return n
