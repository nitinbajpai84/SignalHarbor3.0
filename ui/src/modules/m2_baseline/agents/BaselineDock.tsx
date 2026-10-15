import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../../api/client";
import AgentPanel from "../../../components/AgentPanel";
import AskBox from "../../../components/AskBox";
import ChatSection from "../../../components/ChatSection";
import { askLens, askNira, CHANGED, getLens, lensDraft, notifyChanged, type LensState, type NiraStep } from "../api";
import { m2Lens, m2Nira } from "../copy";
import { lensTechnical } from "../technical/technicalApi";
import { AskCard, RefineCard } from "./LensCards";
import WaitingDocuments from "./WaitingDocuments";

type Turn = { who: "you" | "agent"; text: string };

/** Nira in module 2: small, one line (where you are and what is next), expandable to ask her how to do something. Lens is the
 * main agent here; Nira is the orchestrator, so she never takes a block of her own. Her words come from /nira (facts built from the baseline). */
function NiraStrip({ baselineId, step }: { baselineId: string; step: NiraStep }) {
  const [line, setLine] = useState("");
  const [next, setNext] = useState("");
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    Promise.all([askNira(baselineId, "welcome", step), askNira(baselineId, "now", step)])
      .then(([w, n]) => { setLine(w.text); setNext(n.text); setState("ready"); })
      .catch(() => setState("error"));
  }, [baselineId, step]);
  useEffect(() => {
    load();
    window.addEventListener(CHANGED, load);
    return () => window.removeEventListener(CHANGED, load);
  }, [load]);
  const send = () => {
    const q = question.trim();
    if (!q) return;
    setTurns((t) => [...t, { who: "you", text: q }]);
    setQuestion("");
    setBusy(true);
    askNira(baselineId, "ask", step, q)
      .then((r) => setTurns((t) => [...t, { who: "agent", text: r.text }]))
      .catch((e: unknown) => setTurns((t) => [...t, { who: "agent", text: e instanceof ApiError ? e.message : m2Lens.sayFailed }]))
      .finally(() => setBusy(false));
  };
  return (
    <section aria-label={m2Nira.strip} className="n-companion-guide-line" style={{ display: "grid", gap: 4 }}>
      <div className="n-flex between wrap">
        <strong>{m2Nira.strip}</strong>
        <button type="button" className="n-btn sm" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? m2Nira.close : m2Nira.open}</button>
      </div>
      {state === "loading" ? <span className="n-muted" role="status">{m2Nira.loading}</span> : null}
      {state === "error" ? <span className="n-muted" role="alert">{m2Nira.failed}</span> : null}
      {state === "ready" ? <span>{line}</span> : null}
      {open && state === "ready" ? (
        <>
          <span><strong>{m2Nira.now}</strong> {next}</span>
          <div role="log" aria-label={m2Nira.conversation} aria-live="polite">
            {turns.map((t, i) => <div key={i} className={`n-companion-bubble ${t.who === "you" ? "human" : "nira"}`}>{t.text}</div>)}
          </div>
          <AskBox value={question} onChange={setQuestion} onSubmit={send} label={m2Nira.askLabel} placeholder={m2Nira.askLabel} sendLabel={m2Nira.ask} busy={busy} />
        </>
      ) : null}
    </section>
  );
}

/** Lens's own block, docked on every module 2 screen with the shared agent panel (Nira's, generalised). On opening it does the
 * first move without a click: it drafts what is still undrafted, one measure at a time ("drafting 3 of 8"), then says what it did
 * and what it needs. The page stays usable meanwhile. A change made anywhere on the baseline reloads it (CHANGED). */
export default function BaselineDock({ baselineId, step }: { baselineId: string; step: NiraStep }) {
  const [lens, setLens] = useState<LensState | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [progress, setProgress] = useState<{ n: number; total: number } | null>(null);
  const [problem, setProblem] = useState("");
  const [skipped, setSkipped] = useState<string[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const tried = useRef<Set<string>>(new Set());
  const triedTech = useRef<Set<string>>(new Set());
  const running = useRef(false);

  const load = useCallback(() => {
    getLens(baselineId).then((s) => { setLens(s); setState("ready"); }).catch(() => setState("error"));
  }, [baselineId]);
  useEffect(() => {
    load();
    window.addEventListener(CHANGED, load);
    return () => window.removeEventListener(CHANGED, load);
  }, [load]);

  // the first move: draft what is undrafted, one at a time, so progress shows and the page is never blocked
  useEffect(() => {
    if (!lens || lens.locked || running.current) return;
    const todo = lens.pending.filter((id) => !tried.current.has(id));
    if (todo.length === 0) return;
    running.current = true;
    setProblem("");
    (async () => {
      try {
        for (const [i, id] of todo.entries()) {
          tried.current.add(id);
          setProgress({ n: i + 1, total: todo.length });
          const onList = lens.refine.find((r) => r.id === id)?.kind === "measure";
          await lensDraft(baselineId, onList ? [id] : undefined, onList ? undefined : [id]);
        }
      } catch (e) {
        setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : m2Lens.draftFailed);
      } finally {
        running.current = false;
        setProgress(null);
        load();
        notifyChanged();
      }
    })();
  }, [lens, baselineId, load]);

  // M2-E1: then the technical definition of each measure, one at a time, and the open questions found on the way
  useEffect(() => {
    if (!lens || lens.locked || running.current || lens.pending.some((id) => !tried.current.has(id))) return;
    const todo = (lens.technical?.pending ?? []).filter((id) => !triedTech.current.has(id));
    if (todo.length === 0) return;
    running.current = true;
    setProblem("");
    (async () => {
      try {
        for (const [i, id] of todo.entries()) {
          triedTech.current.add(id);
          setProgress({ n: i + 1, total: todo.length });
          await lensTechnical(baselineId, [id]);
        }
      } catch (e) {
        setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : m2Lens.draftFailed);
      } finally {
        running.current = false;
        setProgress(null);
        load();
        notifyChanged();
      }
    })();
  }, [lens, baselineId, load]);

  /** "Try again": the server skips what was already tried (so two tabs never draft twice) unless told to retry. */
  const again = async (ids: string[]) => {
    const kind = (i: string) => lens?.refine.find((r) => r.id === i)?.kind;
    const measures = ids.filter((i) => kind(i) === "measure");
    const suggestions = ids.filter((i) => kind(i) === "suggestion");
    setProblem("");
    try {
      if (measures.length || suggestions.length) await lensDraft(baselineId, measures, suggestions, true);
    } catch (e) {
      setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : m2Lens.draftFailed);
    }
    load();
    notifyChanged();
  };
  const retry = () => again([...tried.current]);
  /** The organiser decided on a document: Lens drafts again the measures it could not define, through the same retry path. */
  const decided = async () => {
    const unknown = (lens?.refine ?? []).filter((r) => r.kind === "measure" && (!r.definition || r.definition.mark === "unknown")).map((r) => r.id);
    if (unknown.length) {
      await again(unknown);
      try { await lensTechnical(baselineId, unknown, true); } catch { /* the block shows it on the next reload */ }
    } else notifyChanged();
    load();
  };
  const send = () => {
    const q = question.trim();
    if (!q) return;
    setTurns((t) => [...t, { who: "you", text: q }]);
    setQuestion("");
    setBusy(true);
    askLens(baselineId, q)
      .then((r) => {
        setTurns((t) => [...t, { who: "agent", text: r.text }]);
        if (r.changed) notifyChanged();
      })
      .catch((e: unknown) => setTurns((t) => [...t, { who: "agent", text: e instanceof ApiError ? e.message : m2Lens.sayFailed }]))
      .finally(() => setBusy(false));
  };

  const asking = lens?.asks.find((a) => !skipped.includes(a.id));
  const pendingIds = new Set(lens?.pending ?? []);
  const draftingIds = new Set(lens?.drafting ?? []);
  return (
    <AgentPanel
      label={m2Lens.region}
      name={m2Lens.name}
      role={m2Lens.role}
      sub={m2Lens.sub}
      replies={turns.filter((t) => t.who === "agent").length}
      footer={<AskBox value={question} onChange={setQuestion} onSubmit={send} label={m2Lens.askLabel} placeholder={m2Lens.askHelp} sendLabel={m2Lens.send} busy={busy} />}
    >
      <NiraStrip baselineId={baselineId} step={step} />
      {state === "loading" ? <p className="n-muted" role="status">{m2Lens.loading}</p> : null}
      {state === "error" ? (
        <p role="alert" className="state state-error">
          {m2Lens.loadFailed} <button type="button" className="n-btn sm" onClick={() => { setState("loading"); load(); }}>{m2Lens.retry}</button>
        </p>
      ) : null}
      {lens ? (
        <>
          <WaitingDocuments baselineId={baselineId} docs={lens.waiting ?? []} onDecided={() => void decided()} />
          {progress ? <p role="status" className="n-companion-behind">{m2Lens.drafting(progress.n, progress.total)}</p> : null}
          {problem ? <p role="alert" className="state state-error">{problem} <button type="button" className="n-btn sm" onClick={retry}>{m2Lens.retry}</button></p> : null}
          {lens.failed.length > 0 && !progress ? <button type="button" className="n-btn sm" onClick={() => again(lens.failed)}>{m2Lens.retry}</button> : null}
          <ChatSection id="m2-said" label={m2Lens.sections.said} defaultOpen>
            <p><strong>{m2Lens.did}.</strong> {lens.say.did}</p>
            <p><strong>{m2Lens.next}.</strong> {lens.say.next}</p>
            <p><strong>{m2Lens.need}.</strong> {lens.say.need}</p>
            {lens.technical?.say ? <p>{lens.technical.say}</p> : null}
            {lens.locked ? <p className="n-muted">{m2Lens.signedNote}</p> : null}
            {!lens.available && !lens.locked ? <p className="n-muted">{m2Lens.noModel}</p> : null}
          </ChatSection>
          {asking ? (
            <ChatSection id="m2-ask" label={m2Lens.sections.ask} defaultOpen>
              <AskCard key={asking.id} baselineId={baselineId} ask={asking} people={lens.people} locked={lens.locked} onSkip={() => setSkipped((s) => [...s, asking.id])} />
            </ChatSection>
          ) : null}
          <ChatSection id="m2-review" label={`${m2Lens.sections.review} (${lens.refine.length})`} defaultOpen>
            <p className="n-muted">{m2Lens.reviewHelp}</p>
            {lens.refine.length === 0 ? <p className="n-muted">{m2Lens.noItems}</p> : (
              <ul className="m1-list" style={{ padding: 0 }}>
                {lens.refine.map((r) => <RefineCard key={r.id} baselineId={baselineId} item={r} pending={(pendingIds.has(r.id) && progress !== null) || draftingIds.has(r.id)} locked={lens.locked} />)}
              </ul>
            )}
          </ChatSection>
        </>
      ) : null}
      <div role="log" aria-live="polite" aria-label={m2Lens.conversation} className="n-companion-convo">
        {turns.map((t, i) => <div key={i} className={`n-companion-bubble ${t.who === "you" ? "human" : "nira"}`}>{t.text}</div>)}
      </div>
    </AgentPanel>
  );
}
