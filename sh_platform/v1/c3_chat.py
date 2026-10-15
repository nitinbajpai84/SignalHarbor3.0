"""C3 Consumption conversation: Lumen talks with the analyst or screen designer (and, in a short version, the end users) and drafts the
consumption brief `consume/brief/<iid>.json` {views, feeds_wanted, levers, existing_dashboards, end_user_inputs, notes}.

Engine reused from I6a (`sh_platform.v1.i6_chat`): the context is flattened by `egress_fit.fit`, the facts for the number guard by
`i6_chat._facts`, the call is the kernel runtime (`run_agent`: egress gateway, number guard, run log), the fallback asks one fixed
question per goal and labels its turns. File saving and previews come from I2 (`i2_north`), the feed kinds from C2 (`c2_offers`),
the skill from `skills/consumer/` through `skill_loader`. The model never sees an id or a code: KPIs and feeds go by name and kind and
come back mapped. The conversation itself is kept in `consume/chat/<iid>.json` in the thread's shape {intent_id, turns, needs_done, state}.
"""
from __future__ import annotations

import json
import logging
import re

from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.build.agents.runtime import OpenGate, register_names
from sh_platform.context_docs import reader
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import c2_offers as O
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1.egress_fit import fit
from sh_platform.v1 import doc_tools as DT
from sh_platform.v1.file_context import added_line, library_lines, preview_for_agent
from sh_platform.v1.skill_loader import load_skill, skill_label
from sh_platform.v1.router import route  # R1

log = logging.getLogger(__name__)

LUMEN, FALLBACK_NAME, SKILL, MODULE_ID = "Lumen", "Lumen (rules only)", "consumer", "consume"
GOALS = {  # key -> (what Lumen must learn, the fallback's fixed question)
    "existing": ("any dashboard, pack or spreadsheet used today, and what is kept from it",
                 "Do you already have a dashboard or a pack? Drop it in with the paper-clip or describe what is on it."),
    "priority": ("which signed KPIs matter most and in what order", "Which of the figures do you look at first, and which next?"),
    "comparisons": ("what each figure is compared with: last period, target, benchmark, limit",
                    "What do you compare them with: last period, a target, a benchmark or a limit?"),
    "feeds": ("which outside feeds or market forces to bring in (by kind only)",
              "Which outside forces move these figures, such as market prices or currency rates? Name the feeds you would like."),
    "levers": ("which levers to try in a what-if, what each affects and within what range",
               "If you could change one thing and see the effect, what would it be, and within what range?"),
    "drivers": ("what pulls each KPI up or down and what keeps it steady", "When a figure moves, what usually pulled it, and what keeps it steady?"),
    "audiences": ("who reads which view", "Who reads this view?"),
    "refresh": ("how often each view refreshes and where it is read", "How often should it refresh: daily, weekly or monthly?"),
}
ASK_USERS = (  # the end users' short version: fixed questions, their answers go to end_user_inputs
    "Which figures do you look at first, and what do you decide from them?",
    "How often do you need them, and on what: a phone, a screen or a printed pack?",
    "What is missing today, or what would you compare them with?",
)
THANKS = "Thank you. Your answers are in the brief for the person shaping the page. Anything else, write it here."
CLOSING = "Here is the brief as I understand it; shall I lay out the Consume page this way?"
VIEW_LIMIT = 11_000
_NO = re.compile(r"^\s*(?:no|none|nothing|nope|n/a|not really)\b[\s.!]*$", re.I)

ROLE = """You are Lumen, the consumption agent. You help the analyst or screen designer, and the people who will read the figures, \
decide what the Consume page shows: the views, their audience, the signed KPIs in order, what each is compared with, the outside feeds \
to bring in, the what-if levers, the drivers behind each figure, and the refresh. Only signed KPIs can appear; a new figure is a wish \
for the decision maker, written in notes. Never name a data vendor or product: a feed is named by its kind only."""

CHAT_PROMPT = """Talk plainly: at most three sentences, exactly one question per reply. Build on what you already know (the signed KPIs, \
the brief so far, what readers said, the earlier turns, a dashboard the person dropped in). Propose instead of asking when you can.

What you must learn (goals, not a script; cover several at once):
GOALS
Already covered: `goals_covered` in the context.

Reply with ONLY one JSON object:
{"reply": "what you say", "brief_patch": {...}, "covered": [goal keys], "ready": true or false}
brief_patch holds only what you add or change:
{"views": [{"name", "audience", "kpis": [signed KPI names, most important first], "comparisons": [], "filters": [], "refresh"}],
 "feeds_wanted": [feed kinds from outside_feeds], "levers": [{"name", "affects": [signed KPI names], "range"}],
 "existing_dashboards": [{"name", "note"}], "notes": ["drivers, wishes and anything else worth keeping"]}
A view or lever is matched by its name: repeat it exactly to change it. Use "" for what was not said.
covered: the goal keys (KEYS) now answered well enough to write down.
ready: true only when every goal is covered; then your reply is exactly: "CLOSING".
Never write a bare number outside a string, and never write ids or codes. No text outside the JSON."""


# ---- records ---------------------------------------------------------------------------------------------------------------------

def _brief_path(plane, iid: str):
    return plane.path("consume", "brief", f"{iid}.json")


def _chat_path(plane, iid: str):
    return plane.path("consume", "chat", f"{iid}.json")


def empty_brief() -> dict:
    return {"views": [], "feeds_wanted": [], "levers": [], "existing_dashboards": [], "end_user_inputs": [], "notes": []}


def _load(path, blank: dict) -> dict:
    try:
        got = read_json_strict(path, dict)
    except (OSError, ValueError):
        raise N.Refused(500, "The brief could not be read. Please ask your administrator.") from None
    return {**blank, **(got or {})}


def read_brief(plane, iid: str) -> dict:
    return _load(_brief_path(plane, iid), empty_brief())


def read_chat(plane, iid: str) -> dict:
    return _load(_chat_path(plane, iid), {"intent_id": iid, "turns": [], "needs_done": [], "state": "open"})


def pick(plane, iid: str | None) -> str | None:
    """The asked intent (its SOW must exist), else the one whose SOW changed last (C2's rule)."""
    try:
        return O.pick_intent(plane, iid)
    except O.Refusal as e:
        raise N.Refused(e.status, "That intent was not found.") from None


def _sow(plane, iid: str) -> dict:
    try:
        return read_json_strict(plane.path("intents", iid, "sow.json"), dict) or {}
    except (OSError, ValueError):
        return {}


def _kpis(sow: dict) -> list[dict]:
    return [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code") and k.get("name")]


def _feeds(pack) -> dict[str, str]:
    """feed id -> kind, for the feeds that unlock at least one measure (C2's offers)."""
    return {fid: O.kind_of(fid) for fid, f in O._pack_feeds(pack).items()
            if any(isinstance(x, dict) and x.get("required_for") for x in (f or {}).get("fields") or [])}


def view(plane, iid: str | None, viewer=None, pack=None) -> dict:
    """The conversation, the brief, the signed KPIs and the feeds by kind, for the screen. `ask_next`: the end user's next question."""
    if iid is None:
        return {"intent_id": None, "line": "No intent of work yet, so there is nothing to shape.", "turns": [], "needs_done": [],
                "state": "open", "brief": empty_brief(), "kpis": [], "feeds": [], "skill": skill_label(SKILL, plane), "ask_next": None, "greeting": greeting(viewer), "me": getattr(viewer, "name", "")}
    sow = _sow(plane, iid)
    brief = read_brief(plane, iid)
    mine = [x for x in brief["end_user_inputs"] if isinstance(x, dict) and viewer is not None and x.get("by") == viewer.name]
    return {"intent_id": iid, "title": sow.get("title"), "signed": sow.get("state") == "signed", "line": None, **read_chat(plane, iid),
            "brief": brief, "kpis": [{"code": k["code"], "name": k["name"]} for k in _kpis(sow)],
            "feeds": [{"id": f, "kind": k} for f, k in _feeds(pack).items()], "skill": skill_label(SKILL, plane),
            "ask_next": ASK_USERS[len(mine)] if len(mine) < len(ASK_USERS) else THANKS, "greeting": greeting(viewer), "me": getattr(viewer, "name", ""),
            "proposals": _proposals(plane, iid)}


def _proposals(plane, iid: str) -> dict:
    try:
        return L2.view(plane, iid)
    except L2.Refused:
        return {"pending": [], "recent": []}


def greeting(viewer) -> str:
    first = (getattr(viewer, "name", "") or "").split(" ")[0]
    return (f"Hello {first}. I am Lumen. I know the signed figures; let us decide how people should see them. "
            "Do you already have a dashboard or a pack you would like to bring?")


# ---- files: an existing dashboard ------------------------------------------------------------------------------------------------

def save_file(plane, iid: str, filename: str, data: bytes) -> dict:
    """A dashboard, pack or screenshot under consume/brief/files/<iid>/; it is read on the machine, only a preview reaches the model."""
    name = reader.safe_name(filename)
    ext = reader.ext_of(name)
    if ext not in N.SAMPLE_EXT and ext not in reader.allowed_extensions():
        raise N.Refused(422, f"Cannot accept .{ext or '(no extension)'} files here.")
    if not data:
        raise N.Refused(400, "That file is empty.")
    if len(data) > reader.MAX_UPLOAD_BYTES:
        raise N.Refused(413, f"That file is too large. The limit is {reader.MAX_UPLOAD_BYTES // 1_000_000} MB.")
    rel = f"consume/brief/files/{iid}/{name}"
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"name": name, "path": rel, "kind": "document"}


# ---- merging a patch into the brief ----------------------------------------------------------------------------------------------

def _norm(v) -> str:
    return " ".join(str(v or "").lower().split())


def _strs(v) -> list[str]:
    return N._ls(v) if isinstance(v, list) else ([N._s(v, 200)] if N._s(v) else [])


def _add(lst: list, items) -> None:
    for x in items:
        if x and _norm(x) not in {_norm(y) for y in lst}:
            lst.append(x)


def _row(rows: list, name, blank: dict) -> dict | None:
    n = _norm(name)
    if not n:
        return None
    row = next((r for r in rows if isinstance(r, dict) and _norm(r.get("name")) == n), None)
    if row is None:
        row = {"name": N._s(name, 120), **blank}
        rows.append(row)
    return row


def merge(brief: dict, patch, codes: dict[str, str], feeds: dict[str, str]) -> None:
    """The model's (or the fallback's) patch into the brief. `codes`: KPI name -> code; `feeds`: feed kind -> feed id."""
    patch = patch if isinstance(patch, dict) else {}
    kpi = lambda names: [codes[_norm(x)] for x in _strs(names) if _norm(x) in codes]  # noqa: E731 - unsigned names are dropped
    for it in C._items(patch.get("views")):
        row = _row(brief["views"], it.get("name"), {"audience": "", "kpis": [], "comparisons": [], "filters": [], "refresh": ""})
        if row is None:
            continue
        for f in ("audience", "refresh"):
            if N._s(it.get(f)):
                row[f] = N._s(it[f], 200)
        if kpi(it.get("kpis")):
            row["kpis"] = list(dict.fromkeys(kpi(it.get("kpis")) + row["kpis"]))  # the order given is the priority
        for f in ("comparisons", "filters"):
            _add(row[f], _strs(it.get(f)))
    _add(brief["feeds_wanted"], [feeds[_norm(k)] for k in _strs(patch.get("feeds_wanted")) if _norm(k) in feeds])
    for it in C._items(patch.get("levers")):
        row = _row(brief["levers"], it.get("name"), {"affects": [], "range": ""})
        if row is None:
            continue
        _add(row["affects"], kpi(it.get("affects")))
        if N._s(it.get("range")):
            row["range"] = N._s(it["range"], 200)
    for it in C._items(patch.get("existing_dashboards")):
        if N._s(it.get("name")) and not any(_norm(d.get("name")) == _norm(it["name"]) for d in brief["existing_dashboards"] if isinstance(d, dict)):
            brief["existing_dashboards"].append({"name": N._s(it["name"], 200), "path": N._s(it.get("path"), 300), "note": N._s(it.get("note"))})
    _add(brief["notes"], _strs(patch.get("notes")))


# ---- the model, and the fallback --------------------------------------------------------------------------------------------------

def _brief_names(brief: dict, names: dict[str, str], kinds: dict[str, str]) -> dict:
    """The brief as the model may see it: codes and feed ids turned back into names and kinds."""
    by = lambda cs: [names.get(c, "") for c in cs if names.get(c)]  # noqa: E731
    return {"views": [{**v, "kpis": by(v.get("kpis") or [])} for v in brief["views"] if isinstance(v, dict)],
            "feeds_wanted": [kinds[f] for f in brief["feeds_wanted"] if f in kinds],
            "levers": [{**lv, "affects": by(lv.get("affects") or [])} for lv in brief["levers"] if isinstance(lv, dict)],
            "existing_dashboards": [{"name": d.get("name"), "note": d.get("note")} for d in brief["existing_dashboards"] if isinstance(d, dict)],
            "notes": brief["notes"]}


def ask(model, plane, iid: str, chat: dict, brief: dict, sow: dict, pack, files: list, latest: str, people: list[str], viewer=None) -> dict | None:
    """The model's answer as {reply, brief_patch, covered, ready}, or None (then the fallback runs)."""
    covered = [g for g in chat.get("needs_done") or [] if g in GOALS]
    names = {k["code"]: k["name"] for k in _kpis(sow)}
    feeds = _feeds(pack)
    ctx = fit({
        "goals_covered": covered, "goals_open": [g for g in GOALS if g not in covered],
        "signed_kpis": [{"name": k["name"], "definition": k.get("definition"), "unit": k.get("unit"), "period": k.get("period")} for k in _kpis(sow)],
        "outside_feeds": list(feeds.values()),
        "brief_so_far": _brief_names(brief, names, feeds),
        "readers_said": [f"{x.get('question')} {x.get('answer')}" for x in brief["end_user_inputs"] if isinstance(x, dict)],
        "files_now": preview_for_agent(plane, iid, files),  # V1: one flat line per dropped file
        "library": library_lines(plane, iid, viewer),  # C4: the context-library items ticked for this conversation
        "earlier_turns": [{"by": t.get("name"), "text": t.get("text")} for t in chat["turns"][-13:-1]],
    }, (("readers_said", None), ("earlier_turns", None), ("files_now", None), ("library", None), ("outside_feeds", None)), limit=VIEW_LIMIT)
    question = f"LATEST MESSAGE FROM THE PERSON: {latest}"
    ctx.update(L2.facts(plane, iid, ("brief",)))  # L2: what waits for a yes, and what was turned down and why
    ctx["facts"] = C._facts(ctx, question, [latest] + [str(t.get("text") or "") for t in chat["turns"][-13:]])
    prompt = (CHAT_PROMPT.replace("GOALS", "\n".join(f"- {k}: {v[0]}" for k, v in GOALS.items()))
              .replace("KEYS", ", ".join(GOALS)).replace("CLOSING", CLOSING))
    skill = load_skill(SKILL, plane)
    register_names(plane, "", people)
    model = route(model, "lumen", "brief", iid, plane, want_json=True, text=latest, files=bool(files), closing=all(g in covered for g in GOALS))  # R1
    reg, _ = DT.registry(OpenGate(), MODULE_ID, plane, iid, viewer, ctx["facts"])  # D1: search_documents and read_document
    res = run_agent(model, reg, plane.company_id, MODULE_ID, LUMEN,
                    "\n\n".join(x for x in (ROLE, skill, prompt, DT.PROMPT_LINE) if x), ctx, question, recorder=RunRegistry(plane))
    if res.status != "done":
        return None
    a, b = res.text.find("{"), res.text.rfind("}")
    try:
        got = json.loads(res.text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        return None
    if not isinstance(got, dict) or not N._s(got.get("reply")):
        return None
    return {"reply": N._s(got["reply"], 1200), "brief_patch": got.get("brief_patch") if isinstance(got.get("brief_patch"), dict) else {},
            "covered": [g for g in got.get("covered") or [] if g in GOALS] if isinstance(got.get("covered"), list) else [],
            "ready": got.get("ready") is True}


def fallback(chat: dict, sow: dict, pack, text: str, files: list) -> dict:
    """No model: the first goal not yet covered is the one Lumen (rules only) asked; the answer is read with plain rules."""
    covered = [g for g in chat.get("needs_done") or [] if g in GOALS]
    goal = next((g for g in GOALS if g not in covered), None)
    patch: dict = {}
    said = "" if _NO.match(text) else text.strip()
    low = said.lower()
    one = lambda **kw: {"views": [{"name": "Overview", **kw}]}  # noqa: E731 - one view until the person names more
    parts = [p for p in N._parts(said) if p]
    if goal == "existing":
        patch = {"existing_dashboards": [{"name": f["name"], "path": f["path"], "note": said} for f in files]
                 or ([{"name": "Described in the conversation", "note": said}] if said else [])}
    elif goal == "priority":
        found = sorted((low.find(k["name"].lower()), k["name"]) for k in _kpis(sow) if k["name"].lower() in low)
        patch = one(kpis=[n for _, n in found] or [k["name"] for k in _kpis(sow)])
    elif goal == "comparisons":
        patch = one(comparisons=parts)
    elif goal == "feeds":
        patch = {"feeds_wanted": [k for k in _feeds(pack).values() if k.lower() in low]}
    elif goal == "levers":
        patch = {"levers": [{"name": p[:120]} for p in parts]}
    elif goal == "drivers":
        patch = {"notes": [f"What drives it: {p}" for p in parts]}
    elif goal == "audiences":
        patch = one(audience=said)
    elif goal == "refresh":
        patch = one(refresh=said)
    done = [goal] if goal else []
    nxt = next((g for g in GOALS if g not in covered and g not in done), None)
    return {"reply": GOALS[nxt][1] if nxt else CLOSING, "brief_patch": patch, "covered": done, "ready": nxt is None}


def closing_summary(brief: dict, names: dict[str, str], kinds: dict[str, str]) -> str:
    v = _brief_names(brief, names, kinds)
    views = [f"- {x['name']}{' for ' + x['audience'] if x.get('audience') else ''}: {', '.join(x['kpis']) or 'no figure yet'}"
             + (f"; compared with {', '.join(x['comparisons'])}" if x.get("comparisons") else "")
             + (f"; refreshed {x['refresh']}" if x.get("refresh") else "") for x in v["views"]]
    levers = [f"- {lv['name']}{' (affects ' + ', '.join(lv['affects']) + ')' if lv.get('affects') else ''}" for lv in v["levers"]]
    return "\n\n".join([
        "Here is the brief as I understand it.",
        "Views:\n" + ("\n".join(views) or "- none yet"),
        "Outside feeds: " + (", ".join(v["feeds_wanted"]) or "none"),
        "What-if levers:\n" + ("\n".join(levers) or "- none"),
        "Anything to change? Tell me and I will redraft. If not, the Consume page follows this order.",
    ])


def propose_patch(plane, iid: str, brief: dict, patch: dict, codes: dict, feeds: dict, names: dict, kinds: dict, who: str) -> int:
    """L2: Lumen's patch to the brief waits for a yes; the changes are shown by name, not by KPI code. Returns how many changes."""
    import copy
    twin = copy.deepcopy(brief)
    merge(twin, patch, codes, feeds)
    changes = L2.diff(_brief_names(brief, names, kinds), _brief_names(twin, names, kinds))
    return len(changes) if L2.propose(plane, iid, "brief", None, changes, payload={"patch": patch, "codes": codes, "feeds": feeds, "who": who}) else 0


def apply_proposal(plane, iid: str, p: dict, who: str) -> None:
    """Accept: the same merge as before, on the live brief."""
    pl, bpath = p["payload"], _brief_path(plane, iid)
    with lock_for(bpath):
        brief = read_brief(plane, iid)
        merge(brief, pl["patch"], pl["codes"], pl["feeds"])
        write_json_atomic(bpath, brief)
    try:  # the company map follows every write that changes what it shows
        from sh_platform.v1.m1_map import touch; touch(plane)
    except ImportError:
        pass


# ---- the acts -------------------------------------------------------------------------------------------------------------------

def chat(plane, iid: str, viewer, text: str, files: list[dict] | None = None, *, model=None, pack=None) -> dict:
    """The designer's message and Lumen's reply; the brief merged. `files`: records already stored by `save_file`."""
    from sh_platform.v1 import g1_access as G1; G1.check_agent(plane, iid, viewer, lambda m: N.Refused(403, m))  # G1: the agent reads a project's artefacts only for a person who may see it
    text = str(text or "").strip()[:N.MAX_TEXT]
    files = list(files or [])
    if not text and not files:
        raise N.Refused(400, "Write something or add a file.")
    sow = _sow(plane, iid)
    names = {k["code"]: k["name"] for k in _kpis(sow)}
    kinds = _feeds(pack)
    cpath, bpath = _chat_path(plane, iid), _brief_path(plane, iid)
    cpath.parent.mkdir(parents=True, exist_ok=True)
    bpath.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(cpath):
        act = bool({"analyst", "company_admin", "sponsor"} & set(getattr(viewer, "roles", ()) or ()))  # anyone may talk to Lumen; only the designers shape the brief
        if act:
            L2.resolve_words(plane, iid, text, viewer.name, ("brief",))  # L2: "yes" accepts what Lumen proposed, "no ..." turns it down with the reason
        thread = read_chat(plane, iid)
        thread["turns"].append(N._turn("person", viewer.name, text, None, files))
        said = text or added_line(files)
        got = ask(model, plane, iid, thread, read_brief(plane, iid), sow, pack, files, said, [viewer.name], viewer) if model else None
        name = LUMEN if got else FALLBACK_NAME
        got = got or fallback(thread, sow, pack, said, files)
        if not act:  # talk yes, act no: the question is answered and kept in the thread; the brief is left to the person shaping the page
            thread["turns"].append(N._turn("lumen", name, got["reply"] + " (The brief is shaped by the analyst or the decision maker; I have noted what you said for them.)", None))
            write_json_atomic(cpath, thread)
            return view(plane, iid, viewer, pack)
        dropped = [{"name": f["name"], "path": f["path"], "note": text} for f in files]  # a dropped dashboard is always kept, whatever the model said
        codes, feed_ids = {_norm(n): c for c, n in names.items()}, {_norm(k): f for f, k in kinds.items()}
        with lock_for(bpath):
            brief = read_brief(plane, iid)
            if name == LUMEN:  # L2: the model's patch waits for a yes; the rules-only reading applies as before
                merge(brief, {"existing_dashboards": dropped}, codes, feed_ids)
                if proposed := propose_patch(plane, iid, brief, got["brief_patch"], codes, feed_ids, names, kinds, viewer.name):
                    got["ready"], got["reply"] = False, (got["reply"] + L2.tail(proposed)).strip()
            else:
                got["brief_patch"].setdefault("existing_dashboards", [])
                got["brief_patch"]["existing_dashboards"] = C._items(got["brief_patch"]["existing_dashboards"]) + dropped
                merge(brief, got["brief_patch"], codes, feed_ids)
            write_json_atomic(bpath, brief)
            try:  # the company map follows every write that changes what it shows
                from sh_platform.v1.m1_map import touch; touch(plane)
            except ImportError:
                pass
        thread["needs_done"] = [g for g in GOALS if g in thread["needs_done"] or g in got["covered"]]
        thread["state"] = "ready" if got["ready"] else "open"
        thread["turns"].append(N._turn("lumen", name, closing_summary(brief, names, kinds) if got["ready"] else got["reply"], None))
        write_json_atomic(cpath, thread)
    return view(plane, iid, viewer, pack)


def end_user_input(plane, iid: str, viewer, text: str, pack=None) -> dict:
    """An end user's answer to the short version: it appends to the brief's end_user_inputs with the question it answers."""
    text = str(text or "").strip()[:N.MAX_TEXT]
    if not text:
        raise N.Refused(400, "Write your answer first.")
    bpath = _brief_path(plane, iid)
    bpath.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(bpath):
        brief = read_brief(plane, iid)
        mine = [x for x in brief["end_user_inputs"] if isinstance(x, dict) and x.get("by") == viewer.name]
        q = ASK_USERS[len(mine)] if len(mine) < len(ASK_USERS) else "Anything else"
        brief["end_user_inputs"].append({"by": viewer.name, "question": q, "answer": text, "at": N._now()})
        write_json_atomic(bpath, brief)
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    return view(plane, iid, viewer, pack)


def kpi_order(plane, iid: str) -> list[str]:
    """For C1: the KPI codes in the order the brief's views give them (first view first); [] when there is no brief."""
    try:
        views = read_brief(plane, iid)["views"]
    except N.Refused:
        return []
    return list(dict.fromkeys(c for v in views if isinstance(v, dict) for c in v.get("kpis") or []))


def feeds_wanted(plane, iid: str) -> list[str]:
    """For C2: the feed ids the brief asks for, to put those offers first."""
    try:
        return list(read_brief(plane, iid)["feeds_wanted"])
    except N.Refused:
        return []
