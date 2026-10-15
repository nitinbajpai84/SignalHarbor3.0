"""One entry point for every agent (MEM2a): `context_for` answers "what should this agent know before it answers?" from the context map, the memory
vectors, the document index and the short-term turns; `after_turn` is the one call after a turn (keeps the turn, learns, grows the map, summarises).

North, Span, Lumen, Tally and any later agent call these two and nothing else. Everything returned for the model is a list of plain strings (the
egress row guard refuses lists of records); the model sees it only through run_agent, with names tokenised by the gateway. Every read is filtered
by who the viewer is: their own talks, the talks of projects they may read (G1), the company's agreed words, and only the documents the caller
passes (the files the viewer may read; doc_index does not decide access)."""
from __future__ import annotations

import logging
import re

from sh_platform.v1 import doc_index
from sh_platform.v1 import mem_agent as MEM
from sh_platform.v1 import mem_graph as G
from sh_platform.v1 import mem_summary as S

log = logging.getLogger(__name__)
CAP = 6000  # characters across all the lists
SHORT_TURNS = 6


def _date(at: str) -> str:
    return (at or "")[:10]


def _whose(s: dict) -> str:
    """lumen-memory-c1-03: whose talk it was: "Your" for the viewer's own, else the person's name ("Mei Chen's"), never "our"."""
    return "Your" if s.get("mine") else f"{s['who']}'s" if s.get("who") else "Another person's"


def _line(s: dict) -> str:
    """NM-8: the talk is named by its subject and date, so the agent can cite it ("in your talk about X on 9 Oct ..."). c1-03: and by whose
    talk it was, so another person's talk is never told back as "you" or "we". LQ-5: mention it only when it answers the question."""
    about = f" about {s['about']}" if s.get("about") else ""
    return (f"{_whose(s)} earlier talk with {s['agent_name']}{about} on {_date(s['at'])} (mention it only when it answers the question, as "
            f"{'your' if s.get('mine') else 'that person' + chr(39) + 's'} talk): {s['text']}")


def adds_something(s: dict) -> bool:
    """LQ-5: a summary that holds only its topic line ("With Lumen about X.") adds nothing to an answer and is not given to the model."""
    return bool(s.get("decisions") or s.get("open") or s.get("prefs"))


def _passage(plane, p: dict) -> str:
    name = p["path"].replace("\\", "/").rsplit("/", 1)[-1]
    return f"{name}, lines {p['from']}-{p['to']}: {' '.join(p['text'].split())[:400]}"


def context_for(plane, agent: str, viewer, question: str, focus: dict | None = None, paths: list[str] | None = None, convo: str | None = None,
                cap: int = CAP) -> dict:
    """{recall, graph, passages, documents, trace}. recall/graph/passages/documents are lists of strings for the model; trace says what was used.
    `focus`: the object in hand ({project, intent, case, dashboard, tile, table} ids). `paths`: plane-relative paths of the files the viewer may read
    (default: none). `convo`: the conversation id, for the short-term turns. Never raises: a missing part is left out."""
    out: dict = {"recall": [], "graph": [], "passages": [], "documents": []}
    trace: dict = {"memory": [], "summaries": [], "graph": {"seeds": [], "nodes": 0, "edges": 0}, "passages": [], "turns": 0, "capped": False}
    summaries: dict[str, dict] = {}
    searched: set[str] = set()
    try:
        G.sync_items(plane, viewer)
    except Exception:  # noqa: BLE001
        log.warning("memory items could not be indexed", exc_info=True)
    # 1. the graph: neighbours (2 hops) of the focus object and of what the question names
    try:
        seeds = [e["id"] for e in G.focus_ids(plane, focus) + G.entities(plane, question, viewer)]
        near = G.neighbours(plane, viewer, seeds, 2) if seeds else {"nodes": [], "edges": []}
        trace["graph"] = {"seeds": seeds, "nodes": len(near["nodes"]), "edges": len(near["edges"])}
        out["graph"] = G.sentences(near["nodes"], near["edges"])
        for n in near["nodes"]:
            if n["type"] == "summary":
                s = S.get(plane, viewer, n["id"].split(":", 1)[1])
                if s and not s["superseded"]:
                    summaries[s["id"]] = s  # a neighbour of the focus: kept only when it holds something (LQ-5)
    except Exception:  # noqa: BLE001
        log.warning("the context map could not be read", exc_info=True)
    # 2. the memory vectors: summaries and items by words and meaning, access-filtered before ranking
    items: dict[str, str] = {}
    try:
        cache: dict = {}
        live = {i["id"] for i in MEM.mine(plane, viewer)} | {i["id"] for i in MEM.company_items(plane)}
        for h in G.search(plane, question, lambda o, p, k: G.visible(plane, viewer, o, p, cache), 8):
            if h["kind"] == "summary":
                s = S.get(plane, viewer, h["id"])
                if s and not s["superseded"]:
                    summaries.setdefault(s["id"], s)
                    searched.add(s["id"])  # found for the words of this question: relevant even when it holds only its topic
            elif h["id"] in live:  # a forgotten item is never returned, whatever the index still holds
                items[h["id"]] = h["text"]
    except Exception:  # noqa: BLE001
        log.warning("the memory could not be searched", exc_info=True)
    # 3. what the memory already says for this agent (preferences, corrections, agreed words, the focus line), then the above
    recall = list(MEM.lines(plane, agent, viewer, {"convo": convo, "text": question}))
    for t in items.values():
        line = f"About this person: {t}"
        if line not in recall:
            recall.append(line)
    summaries = {k: v for k, v in summaries.items() if k in searched or adds_something(v)}
    recall += [_line(s) for s in sorted(summaries.values(), key=lambda s: s["at"], reverse=True)]
    trace["memory"], trace["summaries"] = list(items), list(summaries)
    # lumen-memory-c1-06, NM2-7: which talk was used, by its subject, not six identical "talk with Lumen on <date>" labels
    trace["summary_labels"] = {k: f"{'your' if v.get('mine') else 'a teammate' + chr(39) + 's'} talk with {v['agent_name']}"
                               + (f" about {v['about'][:60]}" if v.get("about") else "") + f" on {_date(v['at'])}" for k, v in summaries.items()}
    # 4. the short-term turns (only those that hold no figure)
    try:
        turns = [t for t in MEM.convo(plane, viewer, agent, convo)["turns"] if MEM._keepable(plane, t["text"])][-SHORT_TURNS:] if convo else []
        recall += [f"Earlier in this conversation, {'the person' if t['by'] == 'person' else MEM.NAMES.get(t['by'], t['by'])} said: {t['text']}" for t in turns]
        trace["turns"] = len(turns)
    except Exception:  # noqa: BLE001
        log.warning("the short-term turns could not be read", exc_info=True)
    out["recall"] = recall
    # 5. document passages from the files the caller says the viewer may read
    if paths:
        try:
            found = doc_index.search(plane, list(paths), question, 4)
            out["passages"] = [_passage(plane, p) for p in found]
            out["documents"] = list(dict.fromkeys(p["path"].replace("\\", "/").rsplit("/", 1)[-1] for p in found))
            trace["passages"] = [{k: p[k] for k in ("path", "from", "to", "how")} for p in found]
        except Exception:  # noqa: BLE001
            log.warning("the documents could not be searched", exc_info=True)
    # 6. size cap: trim the tail of passages, then graph, then recall
    size = lambda: sum(len(x) for k in ("recall", "graph", "passages", "documents") for x in out[k])  # noqa: E731
    for k in ("passages", "graph", "recall"):  # ponytail: the oldest talks go first because recall lists them last
        while size() > cap and out[k]:
            out[k].pop()
            trace["capped"] = True
    out["trace"] = trace
    return out


def after_turn(plane, agent: str, viewer, convo: str, text: str, reply: str = "", focus: dict | None = None, follow_up: bool = False, model=None) -> list[str]:
    """Replaces `mem_agent.after_turn` in an agent: the same call and the same "I will remember" lines back, and also the map grows and a quiet or long
    talk is summarised. `model` (the routed egress client) is used for preferences and summaries; leave it out for rules only. Never raises."""
    shown = MEM.after_turn(plane, agent, viewer, convo, text, reply, focus, follow_up, model)
    ctx = {k: v for k, v in (focus or {}).items() if k in G.OBJECTS and isinstance(v, str)}

    def grow() -> None:
        try:
            G.note_turn(plane, viewer, agent, convo, f"{text} {_real_tables_only(plane, reply)}", ctx)
            if S.touch(plane, viewer, agent, convo, ctx, 2 if reply else 1):
                # H1-08: a turn that taught the agent something to remember ("I prefer blue lines") is summarised at once, like a decision, so the
                # map shows it (and the person can forget it) straight away, not after the talk's eighth turn
                S.maybe(plane, viewer, agent, convo, ctx, model, decision=S.decided(text) or bool(shown))
                S.sweep(plane, model, owner=MEM.who(viewer), skip=MEM._h(f"{agent}|{MEM.who(viewer)}|{convo}"), limit=2)
        except Exception:  # noqa: BLE001 - the map must never stop the conversation
            log.warning("the context map could not grow", exc_info=True)
    if getattr(getattr(model, "base", model), "route_env", None) is not None:  # FIXD: a live model: the summaries (up to three calls) run after the reply, not before it
        import threading
        threading.Thread(target=grow, name=f"mem-{agent}", daemon=True).start()
    else:
        grow()
    return shown


_TABLE = re.compile(r"\b(?:bronze|silver|gold)_[a-z0-9_]+\b")


def _real_tables_only(plane, text: str) -> str:
    """SS-4: a table name the agent repeated from a planted document never becomes a node of the context map: names that are not in the
    catalogue are dropped from the agent's words before the map reads them (SS-2: the map's entities() checks the person's words too)."""
    names = set(_TABLE.findall(text or ""))
    if not names:
        return text
    real = G.known_tables(plane)
    return _TABLE.sub(lambda m: m.group(0) if m.group(0) in real else "", text)


def forget(plane, viewer, item_id: str) -> None:
    """Forget anything the person may forget, with its vectors and edges: a summary (s-...) or a memory item (m-...)."""
    if item_id.startswith("s-"):
        S.forget(plane, viewer, item_id)
        return
    MEM.forget(plane, viewer, item_id)
    G.drop_vec(plane, item_id)

