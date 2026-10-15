"""The as-is process map, drawn from the owners' answers (M2-21). Pure functions over the SHARED.md shapes.

Ported from the earlier product's emitters/baseline.py (build_process_map, validate_step, edit_step, remove_step,
_step_touched): a step a person acted on is never overwritten by a redraw. Changed: steps come from the owners'
answers (the pack's default map only seeds proposals where there are none), lanes are teams or systems, and every
step names the answer it came from. Nothing here calls a model: `tidy_texts` receives one.
"""
import logging
import re
from pathlib import Path

import yaml

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain.questionnaire import source_rows

log = logging.getLogger(__name__)
CONTRACT = yaml.safe_load((Path(__file__).parents[1] / "contracts" / "process_map.yaml").read_text(encoding="utf-8"))
STATUS_IDS = [s["id"] for s in CONTRACT["statuses"]]
LIM = CONTRACT["limits"]
NO_LANE = "Not named yet"
REMOVED = "Restore the step first."
VERB_CLASSES = CONTRACT["verb_classes"]


class StepRemoved(Exception):
    """A removed step is not edited or validated back to life; the person restores it first."""


def _is_prov(x) -> bool:
    return isinstance(x, dict) and "mark" in x and "value" in x


def _val(x):
    return x["value"] if _is_prov(x) else x


def _text(x) -> str:
    v = _val(x)
    return v.strip() if isinstance(v, str) else ""


def step_touched(step: dict) -> bool:
    """A person validated, edited, removed or added this step (the earlier product's _step_touched)."""
    return step.get("state") != "proposal"


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text).lower()).split())


def lane_key(lane: str) -> str:
    """Two spellings of one team ("Finance", "finance team") are one lane."""
    return " ".join(w for w in _norm(lane).split() if w not in ("team", "department", "dept"))


def _entries(answer: dict, field: str, what_key: str):
    """One dict per thing an owner mentioned in one trace field: who, team, text, manual, order and confirmed.
    Confirmed means an owner stated it: every mark present is `stated`, and who and what are both there."""
    raw = answer.get(field)
    items = _val(raw)
    other = "what" if what_key == "step" else "step"  # the words of a step may sit under either name
    for e in items if isinstance(items, list) else []:
        if not isinstance(e, dict):
            continue
        who, what = _text(e.get("who")), _text(e.get(what_key)) or _text(e.get(other))
        team = _text(e.get("team"))
        if not who and not what:
            continue  # nothing was said: nothing is drawn
        marks = [p.get("mark") for p in (raw, e.get("who"), e.get(what_key)) if _is_prov(p)]
        order = _val(e.get("order"))
        yield {"who": who, "team": team, "what": what, "manual": bool(_val(e.get("manual"))), "order": order if isinstance(order, int) and order > 0 else None,
               "confirmed": bool(who and what and marks and all(m == "stated" for m in marks))}


def waiting_owners(kpi: dict, answers: list[dict], people: list[str] = ()) -> list[str]:
    """The people nominated as owners of this KPI, and `people` (the owners of the baseline's other measures, whom a hop may
    name), who have given no answer for it yet."""
    answered = {_norm(a.get("owner_name") or "") for a in answers}
    names = [_text(v) for v in ((kpi.get("owners") or {}).get(r) for r in ("business", "data", "process"))] + [str(p) for p in people]
    return [n for n in dict.fromkeys(names) if n and _norm(n) not in answered]


def _is_waiting(who: str, waiting: list[str]) -> str | None:
    """The full name of the owner who has not answered that `who` stands for ("Wei" is "Wei Chen"), else None."""
    w = _norm(who)
    return next((n for n in waiting if w and (_norm(n) == w or _norm(n).startswith(w + " "))), None)


_BASE = (0, 1000, 2000)  # a hop with no step number sorts upstream, then in between, then downstream


def from_answers(answers: list[dict], waiting: list[str] = ()) -> list[dict]:
    """The owners' hops merged into one sequence: by step number where given, else upstream, in between, downstream, each owner's
    own list in the order they wrote it. A hop's lane is its team; with none, the team the same person was given elsewhere,
    the system of that name, or the name itself."""
    hops = []
    for ai, a in enumerate(answers):
        for group, field, key in ((0, "upstream", "what"), (1, "in_between", "step"), (2, "downstream", "what")):
            carry = None
            for i, e in enumerate(_entries(a, field, key)):
                carry = e["order"] if e["order"] else carry  # a hop with no number follows the numbered one before it
                hops.append({**e, "a": a, "field": field, "i": i, "at": (e["order"] or carry or _BASE[group], group, ai, i)})
    team_of = {_norm(h["who"]): h["team"] for h in hops if h["who"] and h["team"]}
    systems = {_norm(r["name"]["value"]): r["name"]["value"] for a in answers for r in source_rows(a)}
    lanes: dict[str, str] = {}
    out = []
    for h in sorted(hops, key=lambda h: h["at"]):
        who, lane = h["who"], h["team"] or team_of.get(_norm(h["who"])) or systems.get(_norm(h["who"])) or h["who"] or NO_LANE
        ask = _is_waiting(who, list(waiting)) if who else None
        twin = _twin(out, lanes.get(lane_key(lane), lane), h["what"], str(h["a"]["id"]))
        if twin is not None:  # the same step said twice, by one owner or two: drawn once, with both sources
            if str(h["a"]["id"]) not in [twin["from"], *twin.get("also_from", [])]:
                twin.setdefault("also_from", []).append(str(h["a"]["id"]))
            continue
        step = {"id": f"{h['a']['id']}-{h['field'][0]}{h['i']}", "lane": lanes.setdefault(lane_key(lane), lane),
                "text": h["what"] or f"To confirm: what {who} does here", "order": len(out) + 1, "manual": h["manual"] and h["field"] == "in_between",
                "confirmed": h["confirmed"] and not ask, "from": str(h["a"]["id"]), "state": "proposal", "by": "Lens"}
        if ask:
            step["ask"] = ask  # the step is described by someone else: the person who does it has not answered
        out.append(step)
    return out


def _twin(steps: list[dict], lane: str, text: str, owner: str = "") -> dict | None:
    """The step already drawn in this lane that says the same thing, else None: the same words (or all but a few), and, when
    the other step came from another owner, a paraphrase (paraphrased() below)."""
    mine = set(_norm(text).split())
    for s in steps:
        theirs = set(_norm(s["text"]).split())
        if not mine or lane_key(s["lane"]) != lane_key(lane):
            continue
        if len(mine & theirs) / len(mine | theirs) >= 0.8 or (s["from"] != owner and paraphrased(s["text"], text)):
            return s
    return None


_VERBS = {w: cls for cls, ws in VERB_CLASSES.items() for w in ws}


def _verb_class(word: str) -> str | None:
    for w in (word, word.removesuffix("s"), word.removesuffix("es"), word.removesuffix("ies") + "y"):
        if w in _VERBS:
            return _VERBS[w]
    return None


def _split_words(text: str) -> tuple[set[str], set[str]]:
    """(verb classes, other content words) of a step's text. A light verb (conduct, perform) says nothing and is left out."""
    classes, nouns = set(), []
    for w in _norm(text).split():
        c = _verb_class(w)
        if c == "light" or w in _FILLER:
            continue
        if c:
            classes.add(c)
        else:
            nouns.append(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return classes, nouns


def paraphrased(a: str, b: str) -> bool:
    """Two owners' wording of one step: all the content words of the shorter one are in the longer ("Calls" in "Tracker calls", "Review"
    in "Review draft pack" after the light verb in "Conduct review" is dropped), or the same kind of action on the same object (the last noun)
    ("Pastes levels into the workbook", "Copies values into the exposure workbook").
    ponytail: word lists and overlap, no understanding; two different steps that share every word of the shorter may merge."""
    (ca, na), (cb, nb) = _split_words(a), _split_words(b)
    wa, wb = set(na) | ca, set(nb) | cb
    small = min(wa, wb, key=len)
    if small and len(wa & wb) / len(small) >= 0.75:
        return True
    return bool(ca) and ca == cb and bool(na) and bool(nb) and na[-1] == nb[-1] 


def from_pack(default: dict | None, source: str, kpi_id: str = "") -> list[dict]:
    """The pack's default map: proposals marked as guessed, used only where the answers gave no steps, and only for the measures the
    default lists (`for_kpis`). A default that lists none (an older pack) applies to every measure."""
    listed = (default or {}).get("for_kpis")
    if listed is not None and kpi_id not in listed:
        return []
    out = []
    for s in (default or {}).get("steps") or []:
        if isinstance(s, dict) and s.get("lane") and s.get("name"):
            out.append({"id": f"pack-{s.get('step_id', len(out) + 1)}", "lane": str(s["lane"]), "text": str(s["name"]),
                        "order": len(out) + 1, "manual": False, "confirmed": False,  # the pack's way of working is not an owner's word: shown only when one says so
                        "from": source, "state": "proposal", "by": "the pack"})
    return out


TECHNICAL = "technical"  # the `from` of a step drawn from the measure's technical definition: the screen says so
_ROW_ID = re.compile(r"^[A-Za-z]{1,3}-?\d+$")


def from_technical(kpi: dict, names: dict[str, str] | None = None) -> list[dict]:
    """Steps from the measure's own technical definition: one step per source (the lane is the system or file) and one per step of the
    calculation (the lane is the measure's data, process or business owner, in that order). `names` is {catalogue row id: name}; a source
    that cannot be named is left out, never shown as an id. Read-only over the `technical` block; nothing when it holds neither."""
    tech = kpi.get("technical") if isinstance(kpi.get("technical"), dict) else {}
    cell = lambda p: tech.get(p) if _is_prov(tech.get(p)) and tech[p].get("mark") != "unknown" else None  # noqa: E731
    src, calc = cell("sources"), cell("calculation")
    raw = _val(src) if src else []
    named = [(names or {}).get(str(x)) or ("" if _ROW_ID.match(str(x).strip()) else str(x).strip()) for x in (raw if isinstance(raw, list) else re.split(r"[;,]", str(raw)))]
    systems = list(dict.fromkeys(n for n in named if n))[:4]
    parts = [p.strip(" .") for p in re.split(r"[;\n]|(?<=[a-z0-9\)])\.\s+(?=[A-Z])", _text(calc) if calc else "") if p.strip(" .")][:6]
    owner = next((_text(o) for o in ((kpi.get("owners") or {}).get(r) for r in ("data", "process", "business")) if _text(o)), NO_LANE)
    steps = [(s, f"Provide the data for {kpi.get('name', 'this measure')}", src) for s in systems] + [(owner, p, calc) for p in parts]
    return [{"id": f"tech-{n}", "lane": lane, "text": text, "order": n, "manual": False,
             "confirmed": bool(c and c.get("mark") == "stated"), "from": TECHNICAL, "state": "proposal", "by": "Lens"}
            for n, (lane, text, c) in enumerate(steps, 1)]


def without_hidden(steps: list[dict], hidden: list[str]) -> list[dict]:
    """The steps a person may be shown: a step drawn from the technical definition that names something they may not see (a restricted measure,
    a restricted field or source) is left out, and the rest keep their order. Steps from owners' answers and from people are never touched here."""
    if not hidden:
        return steps
    keep = [s for s in steps if not (s.get("from") == TECHNICAL and A.mentions({"text": f"{s.get('lane', '')} {s.get('text', '')}"}, hidden))]
    return [{**s, "order": n} for n, s in enumerate(keep, 1)] if len(keep) != len(steps) and all(s.get("from") == TECHNICAL for s in keep) else keep


def tidy_texts(model, texts: list[str]) -> list[str] | None:
    """Lens rewords the steps as plain text through the egress client. Anything odd returns None and the
    original wording stays: the map must be drawn with no model, a refusal or a bad reply."""
    if model is None or not texts:
        return None
    body = "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    messages = [{"role": "system", "content": CONTRACT["tidy"]["instruction"]}, {"role": "user", "content": body}]
    try:
        reply = model.complete(CONTRACT["tidy"]["module_id"], messages)
    except Exception:  # noqa: BLE001 -- a refusal or a provider failure never stops the drawing
        log.warning("the step wording could not be tidied; the original wording is kept")
        return None
    lines = [ln.strip() for ln in str(reply.text).splitlines() if ln.strip()]
    if not (len(lines) == len(texts) and all(len(ln) <= LIM["text_chars"] for ln in lines)):
        return None
    return [new if keeps_words(old, new) else old for old, new in zip(texts, lines)]  # a reword that changed the nouns or added a verb is not used


_FILLER = frozenset("a an and the of to in into on at by for from with or is are as it its this that".split())


def _roots(text: str) -> set[str]:
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in _norm(text).split() if w not in _FILLER}


def keeps_words(old: str, new: str) -> bool:
    """True when the reword still has every content word of the original ("Call notices" must not become "Access notices").
    ponytail: strict word overlap, so a reword that drops a verb is also refused; the original wording then stays."""
    added = _roots(new) - _roots(old)
    return _roots(old) <= _roots(new) and not any(_verb_class(w) for w in added)  # never an invented verb ("Prepare funding pack page")


def _may_name_someone(text: str, known: set[str]) -> bool:
    """True when the text has a capitalised word, not at the start of a sentence, that the vault does not know.
    ponytail: a heuristic that may skip more than needed (Excel, a Capitalised system), never sends a name."""
    for m in re.finditer(r"[A-Z][\w'’-]*", text):
        before = text[:m.start()].rstrip()
        if before and before[-1] not in ".!?:" and m.group().lower().removesuffix("'s").removesuffix("’s") not in known:
            return True
    return False


def _lanes(steps: list[dict]) -> list[str]:
    """The lanes in the order of the steps, one per team (spellings of one team are one lane)."""
    seen: dict[str, str] = {}
    for s in sorted(steps, key=lambda s: s["order"]):
        if s["state"] != "removed":
            seen.setdefault(lane_key(s["lane"]), s["lane"])
    return list(seen.values())


def waiting_markers(steps: list[dict], own_waiting: list[str]) -> list[dict]:
    """One "Waiting on <owner>" step, to confirm (drawn dashed), for each owner of this measure who has not answered and is not
    already named as the person to ask on a step."""
    asked = {_norm(s.get("ask") or "") for s in steps}
    return [{"id": f"wait-{_norm(n).replace(' ', '-')}", "lane": n, "text": f"Waiting on {n}", "order": 0, "manual": False,
             "confirmed": False, "from": "waiting", "state": "proposal", "by": "Lens", "ask": n, "waiting": True}
            for n in own_waiting if _norm(n) not in asked]


def draw(answers: list[dict], pack_default: dict | None, pack_source: str, existing: dict | None, model=None,
         known_names: frozenset[str] = frozenset(), waiting: list[str] = (), own_waiting: list[str] = (), kpi_id: str = "", technical: list[dict] = ()) -> dict:
    """One KPI's map. Untouched steps are redrawn from the answers; a step a person acted on is kept as it is. `waiting` names the
    owners who have not answered: a step they are said to do is drawn dashed, to confirm with them."""
    old = {s["id"]: s for s in (existing or {}).get("steps", [])}
    new = from_answers(answers, waiting) or list(technical) or from_pack(pack_default, pack_source, kpi_id)  # the pack's way only when nothing of this measure's own exists
    for m in waiting_markers(new, list(own_waiting)):
        new.append({**m, "order": len(new) + 1})
    kept = {s["id"] for s in new if s["id"] in old and step_touched(old[s["id"]])}
    last = max((s["order"] for s in old.values()), default=0)
    if any(step_touched(s) for s in old.values()):  # else nobody has acted on the map: the steps keep the order the answers give them
        for s in new:  # a step new to this map goes after every step there, so a person's added step never collides with it
            if s["id"] in old:
                s["order"] = old[s["id"]]["order"]
            else:
                last += 1
                s["order"] = last
    fresh = [s for s in new if s["id"] not in kept]
    safe = [s for s in fresh if not s.get("waiting") and not _may_name_someone(s["text"], known_names)]  # the others keep their wording
    for s, t in zip(safe, tidy_texts(model, [s["text"] for s in safe]) or []):
        s["text"] = t
    steps = [old[s["id"]] if s["id"] in kept else s for s in new]
    ids = {s["id"] for s in steps}
    steps += [s for i, s in old.items() if i not in ids and step_touched(s)]  # added by a person, or no longer in the answers
    steps.sort(key=lambda s: s["order"])
    return {"lanes": _lanes(steps), "steps": steps}


def _find(kpi_map: dict, step_id: str) -> dict:
    for s in kpi_map["steps"]:
        if s["id"] == step_id:
            return s
    raise KeyError(step_id)


def _person(by: str) -> str:
    by = (by or "").strip()
    if not by:
        raise ValueError("A person's name is needed to change a step.")
    return by


def _clean(lane, text) -> tuple[str, str]:
    lane, text = (lane or "").strip(), (text or "").strip()
    if not lane or not text:
        raise ValueError("A step needs a team or system and a few words about what happens.")
    if len(lane) > LIM["lane_chars"] or len(text) > LIM["text_chars"]:
        raise ValueError("That is too long. Please shorten it.")
    return lane, text


def _done(kpi_map: dict) -> dict:
    kpi_map["steps"].sort(key=lambda s: s["order"])
    kpi_map["lanes"] = _lanes(kpi_map["steps"])
    return kpi_map


def _live(kpi_map: dict, step_id: str) -> dict:
    s = _find(kpi_map, step_id)
    if s["state"] == "removed":
        raise StepRemoved(REMOVED)
    return s


def validate_step(kpi_map: dict, step_id: str, by: str) -> dict:
    _live(kpi_map, step_id).update(state="validated", confirmed=True, by=_person(by))
    return _done(kpi_map)


def edit_step(kpi_map: dict, step_id: str, by: str, lane=None, text=None, manual=None) -> dict:
    s = _live(kpi_map, step_id)
    s["lane"], s["text"] = _clean(lane if lane is not None else s["lane"], text if text is not None else s["text"])
    if manual is not None:
        s["manual"] = bool(manual)
    s.update(state="edited", confirmed=True, by=_person(by))
    return _done(kpi_map)


def remove_step(kpi_map: dict, step_id: str, by: str) -> dict:
    """Never deletes: the step stays in the file, flagged removed, so a redraw cannot bring it back."""
    _find(kpi_map, step_id).update(state="removed", by=_person(by))
    return _done(kpi_map)


def add_step(kpi_map: dict, lane: str, text: str, manual: bool, by: str, order: float | None = None) -> dict:
    lane, text = _clean(lane, text)
    by = _person(by)
    n = 1 + sum(1 for s in kpi_map["steps"] if s["id"].startswith("added-"))
    last = max((s["order"] for s in kpi_map["steps"]), default=0)
    kpi_map["steps"].append({"id": f"added-{n}", "lane": lane, "text": text, "order": order if isinstance(order, (int, float)) else last + 1,
                             "manual": bool(manual), "confirmed": True, "from": f"added by {by}", "state": "validated", "by": by})
    return _done(kpi_map)


def mark_of(step: dict) -> str:
    """What the screen says about a step: stated by an owner, guessed from the pack, or still to confirm."""
    if step["by"] == "the pack":
        return "guessed"
    return "stated" if step["confirmed"] else "to_confirm"


def view(kpi_map: dict, answers: list[dict]) -> dict:
    """The map as the screen reads it: removed steps counted apart, each step with who said it and its mark."""
    owners = {str(a["id"]): a.get("owner_name") for a in answers}  # a step from the technical definition has no answering owner
    who = lambda s: " and ".join(dict.fromkeys(str(n) for n in (owners.get(i) for i in [s["from"], *s.get("also_from", [])]) if n)) or None  # noqa: E731
    steps = [{**s, "owner": who(s), "mark": mark_of(s)} for s in kpi_map["steps"] if s["state"] != "removed"]
    return {"lanes": _lanes(kpi_map["steps"]), "steps": steps, "removed": len(kpi_map["steps"]) - len(steps),
            "counts": {"answers": len({s["from"] for s in steps if s["from"] in owners}),
                       "to_confirm": sum(1 for s in steps if not s["confirmed"]),
                       "manual": sum(1 for s in steps if s["manual"])}}
