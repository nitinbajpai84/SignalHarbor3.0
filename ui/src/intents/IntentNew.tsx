import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ComponentType, type KeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import MemoryOpening from "./MemoryOpening";
import ScreenState from "../components/ScreenState";
import { Button, Chip, PageFrame, SideCard } from "../design";
import { intentNewCopy as t } from "./intentNewCopy";

// The chooser (spec 03). Types, lines and time boxes are read from GET /api/intents/types; the questions belong to ui/src/intents/start/.

export interface CatalogueType { title: string; chooser_line: string; open_button: string; time_box_days?: number; start_questions: { id: string; lead: string; required: boolean }[] }
export interface Catalogue { version: number; chooser_heading?: string; types: Record<string, CatalogueType> }
/** What the per-type start screens receive. The draft already exists; the first typed line, if any, is in the draft's north_proposal.text. */
export interface StartProps { type: string; draftId: string; catalogue: CatalogueType; catalogueVersion: number }
interface Proposal { type: string | null; reason: string; confidence: string | null; title: string }
interface Draft { id: string; type: string; title?: string | null; draft_updated_at?: string | null; updated_at?: string | null }

/** Per-type screens by agreed name and spec file. A missing file shows the "waits for" line. */
const STARTS: Record<string, { file: string; spec: string }> = {
  initiative: { file: "InitiativeStart", spec: "22" }, brainstorm: { file: "BrainstormStart", spec: "35" }, pulse: { file: "CheckinStart", spec: "38" },
  problem: { file: "ProblemStart", spec: "41" }, decision: { file: "DecisionStart", spec: "43" },
};
const loaders = import.meta.glob<{ default?: ComponentType<StartProps> } & Record<string, unknown>>("./start/*Start.tsx");

function startFor(type: string): ComponentType<StartProps> {
  const s = STARTS[type];
  const load = s ? loaders[`./start/${s.file}.tsx`] : undefined;
  if (!s || !load) return () => <ScreenState state="empty" message={t.waits(s?.spec ?? "03")} />;
  return lazy(async () => {
    const m = await load();
    return { default: (m.default ?? m[s.file]) as ComponentType<StartProps> };
  });
}
const startCache: Record<string, ComponentType<StartProps>> = {};
const startOf = (type: string): ComponentType<StartProps> => (startCache[type] ??= startFor(type));

class Guard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <ScreenState state="empty" message={t.waits("03")} /> : this.props.children; }
}

/** 57: a start opened from an opportunity skips the chooser; its hypothesis fills the answers it can, each guessed by North. */
const CARRY_TYPES = ["initiative", "brainstorm"];
const problemCopy = { title: "Report a problem", help: "Say what is wrong. Nothing is saved until you press Continue.", label: "What is wrong?", go: "Continue" };
const carryCopy = { opening: "Opening the start with the opportunity's answers.", failed: "That opportunity could not be carried into a start. Pick it up on the radar again." };

// Spec 03 at 390: "Your drafts" collapses to one line that expands. Read once on load.
const phone = typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(max-width: 700px)").matches;
const when = (iso?: string | null): string => (iso ? new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "");

export default function IntentNew() {
  const [params] = useSearchParams();
  const type = params.get("type") ?? "";
  const draftId = params.get("draft") ?? "";
  const from = params.get("from");
  const opp = from && /^opp-/.test(from) ? from : null; // an opportunity, not an intent: the start carries its hypothesis (57)
  const nav = useNavigate();
  const [cat, setCat] = useState<Catalogue | null | "failed">(null);
  const [drafts, setDrafts] = useState<Draft[] | "failed" | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [off, setOff] = useState(false);
  const [error, setError] = useState("");
  const [discarding, setDiscarding] = useState<string | null>(null);
  const tiles = useRef<HTMLDivElement>(null);
  const starting = useRef(false); // one draft per press: a double click must not write two

  const load = useCallback(() => {
    setCat(null);
    apiGet<Catalogue>("/api/intents/types").then(setCat, () => setCat("failed"));
    apiGet<{ intents?: Draft[] } | Draft[]>("/api/intents?state=draft&mine=1").then(
      (r) => setDrafts(Array.isArray(r) ? r : r.intents ?? []), () => setDrafts("failed"));
  }, []);
  useEffect(load, [load]);

  const typesAll = cat && cat !== "failed" ? cat.types : {};
  const keys = Object.keys(typesAll);
  // A Problem arrives from an item or an alert with ?type=problem: the draft is written at once and the questions open (spec 41).
  // With no item, alert or source it waits for the first typed answer: opening the page alone saves nothing.
  const carried = ["from", "item", "alert"].some((k) => params.get(k));
  const plainProblem = type === "problem" && !draftId && !carried;
  const autoProblem = type === "problem" && !draftId && carried && !!typesAll.problem?.time_box_days;
  useEffect(() => { if (autoProblem) void start("problem", false); }, [autoProblem]); // eslint-disable-line react-hooks/exhaustive-deps
  const autoCarry = !!opp && CARRY_TYPES.includes(type) && !draftId && !!typesAll[type]?.time_box_days;
  useEffect(() => { if (autoCarry) void start(type, false); }, [autoCarry]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async (key: string, accepted: boolean) => {
    if (starting.current) return;
    starting.current = true;
    setError("");
    const p = proposal;
    try {
      // a Problem carries from and item in its own answers (spec 41); the others link at creation (records.py reads links.from)
      const made = await apiSend<{ id: string; version: number }>("POST", "/api/intents", {
        type: key, ...(from && !opp && key !== "problem" ? { links: { from } } : {}), ...(p?.title && accepted ? { title: p.title } : {}),
        ...(text.trim() ? { north_proposal: { text: text.trim(), type: p?.type ?? null, confidence: p?.confidence ?? null, accepted, picked_type: key } } : {}),
      });
      if (opp && CARRY_TYPES.includes(key)) {
        try {
          await apiSend("PUT", `/api/intents/${made.id}/start`, { version: made.version, carry: opp });
        } catch (e) {
          setError(e instanceof ApiError && e.status < 500 && e.message ? e.message : carryCopy.failed);
          await apiSend("POST", `/api/intents/${made.id}/cancel`, { version: made.version, cancel_reason: t.discardReason }).catch(() => undefined);
          starting.current = false;
          return;
        }
      }
      if (key === "problem" && plainProblem && text.trim()) await apiSend("POST", `/api/intents/${made.id}/problem/start`, { what: text.trim(), step: 0 }); // keeps the first answer
      const carry = ["from", "item", "alert"].flatMap((k) => { const v = params.get(k); return v ? [`&${k}=${encodeURIComponent(v)}`] : []; }).join("");
      nav(`/centre/intent/new?type=${key}&draft=${made.id}${carry}`);
    } catch {
      setError(t.startFailed);
    }
    starting.current = false;
  };

  const ask = async () => {
    setBusy(true); setOff(false); setProposal(null);
    try { setProposal(await apiSend<Proposal>("POST", "/api/intents/classify", { text: text.trim() })); } catch { setOff(true); }
    setBusy(false);
  };
  const onText = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (text.trim() && !busy) void ask(); }
  };
  const arrows = (e: KeyboardEvent<HTMLDivElement>) => {
    const go = ({ ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 } as Record<string, number>)[e.key];
    if (!go) return;
    const all = [...(tiles.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    all[(at + go + all.length) % all.length]?.focus();
    e.preventDefault();
  };
  const discard = async (id: string) => {
    try {
      const { version } = await apiGet<{ version: number }>(`/api/intents/${id}`);
      await apiSend("POST", `/api/intents/${id}/cancel`, { version, cancel_reason: t.discardReason });
      setDrafts((d) => (Array.isArray(d) ? d.filter((x) => x.id !== id) : d));
    } catch { setError(t.discardFailed); }
    setDiscarding(null);
  };

  // Hand over: the per-type screen owns everything from here.
  if (type && draftId && cat && cat !== "failed" && typesAll[type]) {
    const Start = startOf(type);
    return (
      <PageFrame title={typesAll[type]!.title} crumbs={<Link to="/centre/intent/new" className="ds-link">{t.title}</Link>}>
        <Guard><Suspense fallback={<ScreenState state="loading" message={t.loadingStart} />}>
          <Start type={type} draftId={draftId} catalogue={typesAll[type]!} catalogueVersion={cat.version} />
        </Suspense></Guard>
      </PageFrame>
    );
  }

  if (plainProblem && cat && cat !== "failed" && typesAll.problem) {
    return (
      <PageFrame title={problemCopy.title} subline={problemCopy.help} crumbs={<Link to="/centre/intent/new" className="ds-link">{t.title}</Link>}>
        <textarea aria-label={problemCopy.label} placeholder={problemCopy.label} rows={3} maxLength={600} value={text} style={{ width: "100%", boxSizing: "border-box" }} onChange={(e) => setText(e.target.value)} />
        {error && <p role="alert" className="state state-error">{error}</p>}
        <Button variant="primary" disabled={!text.trim()} onClick={() => void start("problem", false)}>{problemCopy.go}</Button>
      </PageFrame>
    );
  }
  if (autoCarry && !error) return <ScreenState state="loading" message={carryCopy.opening} />;

  const name = proposal?.type ? typesAll[proposal.type]?.title ?? proposal.type : "";
  const list = Array.isArray(drafts) ? drafts : [];
  const aside = (
    <>
      <SideCard title={t.draftsTitle}>
        {drafts === "failed" ? <p className="n-muted">{t.draftsNa}</p>
          : list.length === 0 ? <p className="n-muted">{t.draftsEmpty}</p>
          : <details open={!phone}><summary>{t.draftCount(list.length)}</summary>{list.map((d) => (
            <div key={d.id} style={{ marginBottom: 12 }}>
              <strong>{d.title || t.untitled}</strong> <Chip>{typesAll[d.type]?.title ?? d.type}</Chip>
              <p className="n-muted">{t.lastTouched} {when(d.draft_updated_at ?? d.updated_at)}</p>
              {discarding === d.id ? (
                <div role="group" aria-label={t.discardAsk}>
                  <p>{t.discardAsk}</p>
                  <Button variant="primary" onClick={() => void discard(d.id)}>{t.discardYes}</Button> <Button onClick={() => setDiscarding(null)}>{t.discardNo}</Button>
                </div>
              ) : (
                <>
                  <Link className="ds-btn" to={`/centre/intent/new?type=${d.type}&draft=${d.id}`}>{t.carryOn}</Link> <Button onClick={() => setDiscarding(d.id)}>{t.discard}</Button>
                </>
              )}
            </div>
          ))}</details>}
      </SideCard>
      <SideCard title="North"><MemoryOpening /><p>{t.northLine}</p></SideCard>
    </>
  );

  return (
    <PageFrame title={cat && cat !== "failed" && cat.chooser_heading ? cat.chooser_heading : t.title} subline={t.help} crumbs={t.eyebrow} aside={aside}
      actions={<Link to="/centre/intent" className="ds-btn">{t.back}</Link>}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
        <textarea aria-label={t.placeholder} placeholder={t.placeholder} rows={1} maxLength={600} value={text} style={{ flex: "1 1 260px", minHeight: 44 }}
          onChange={(e) => setText(e.target.value)} onKeyDown={onText} />
        <Button variant="primary" disabled={!text.trim() || busy} onClick={() => void ask()}>{busy ? t.asking : t.ask}</Button>
      </div>
      {text.length > 400 && <p className="n-muted">{text.length} / 600</p>}
      {off && <p role="alert" className="state state-error">{t.northOff}</p>}
      {proposal && (
        <div className="ds-card" role="region" aria-label={t.suggestion} style={{ padding: 16, margin: "12px 0" }}>
          {proposal.type ? (
            <>
              <p><strong>{t.suggestion}.</strong> {t.looksLike(name)} {proposal.reason} {proposal.confidence && <Chip>{proposal.confidence === "Likely" ? t.likely : t.possible}</Chip>}</p>
              <p className="n-muted">{proposal.title}</p>
              <Button variant="primary" onClick={() => void start(proposal.type!, true)}>{t.yes(name)}</Button>{" "}
              <Button onClick={() => { setProposal(null); tiles.current?.querySelector("button")?.focus(); }}>{t.pickAnother}</Button>
            </>
          ) : (
            <p><strong>{t.suggestion}.</strong> {t.notSure} {proposal.reason}</p>
          )}
        </div>
      )}
      {error && <p role="alert" className="state state-error">{error}</p>}
      {cat === null && <ScreenState state="loading" />}
      {cat === "failed" && <ScreenState state="error" message={t.loadError} onRetry={load} />}
      {cat && cat !== "failed" && keys.length === 0 && <ScreenState state="empty" message={t.catalogueEmpty} />}
      {keys.length > 0 && (
        <div ref={tiles} role="radiogroup" aria-label={t.title} onKeyDown={arrows} style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginTop: 12 }}>
          {keys.map((k) => {
            const ty = typesAll[k]!;
            const days = ty.time_box_days;
            return (
              <button key={k} type="button" role="radio" aria-checked={type === k} disabled={!days} className="ds-card" style={{ textAlign: "left", padding: 16, minHeight: 56, cursor: days ? "pointer" : "default", ...(type === k ? { outline: "2px solid currentColor" } : {}) }}
                onClick={() => void start(k, proposal?.type === k)}>
                <strong>{ty.title}</strong>
                <span style={{ display: "block", margin: "6px 0" }}>{ty.chooser_line}</span>
                <Chip>{days ? t.timeBox(days) : t.timeBoxMissing}</Chip>
              </button>
            );
          })}
        </div>
      )}
    </PageFrame>
  );
}
