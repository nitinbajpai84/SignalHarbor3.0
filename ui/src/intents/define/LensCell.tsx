import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import { ApiError, apiSend } from "../../api/client";
import { Button, Chip } from "../../design";
import SendBackDialog from "./SendBackDialog";

// The draft cell (spec 44, screens 2, 3 and 5): label, value, mark chip, source line and the actions the viewer may take.
// Only the person named for the item sees Confirm, Not mine and Send back; the server refuses anyone else with a plain sentence.

const t = {
  notFound: "Not found yet",
  notDrafted: "Not drafted yet.",
  guessed: "Guessed",
  sentBack: "Sent back",
  confirmedBy: (who: string, on: string) => `Confirmed by ${who}${on ? `, ${on}` : ""}`,
  source: (s: string) => s,
  noSource: "Lens, no source found",
  owner: { business_owner: "Business owner", data_owner: "Data owner", source_owner: "Source owner" } as Record<string, string>,
  ownerNone: "not named yet",
  withLead: (who: string) => `With ${who} for a decision`,
  confirm: "Confirm",
  sendBack: "Send back with a note",
  notMine: "Not mine",
  notMineIt: (who: string) => `Not mine, it is ${who}`,
  pickWho: "Who is it?",
  pickNone: "Choose a person",
  first: "The first draft",
  redraft: "Lens's second draft",
  because: (n: string) => `Because: ${n}`,
  useThis: "Use this one",
  keepFirst: "Keep the first",
  lensNote: "Lens says:",
  draftingLine: "Lens is drafting this.",
  slow: "Taking longer than usual. You can carry on, the page is not blocked.",
  failedLine: "Lens could not draft this just now.",
  suggestion: "Suggestion from the industry pack, not a draft of yours",
  tryAgain: "Try again",
  failed: "That did not work. Please try again.",
  close: "Close",
  queueEmpty: "Nothing waiting for your decision.",
  queueTitle: "Waiting for your decision",
  useFirst: "Use the first draft",
  useRedraft: "Use the redraft",
  writeIt: "Write it myself",
  wordingLabel: "Your wording",
  save: "Save",
  unknown: "We do not know yet",
  noteOf: (n: number, text: string) => `${n === 1 ? "First" : "Second"} note: ${text}`,
};

export const KIND_LABELS: Record<string, string> = {
  mapping: "Cluster to measure", business_definition: "Business definition", technical_definition: "Technical definition",
  catalogue_entry: "Catalogue entry", owners: "The three owners", governed_state: "Governed state",
  process_steps: "Process steps", data_sources: "Data sources", ambiguities: "Ambiguities",
};
const STATE_WORDS: Record<string, string> = {
  not_drafted: "Not drafted", drafting: "Drafting", guessed: t.guessed, failed: "Failed",
  redrafted: t.sentBack, escalated: t.sentBack, confirmed: "Confirmed",
};

export interface LensCellData {
  cell_key: string; kind: string; measure_code: string; name?: string; state: string; outcome?: string | null;
  value?: unknown; source?: string; suggestion?: string; mark?: string; confirmed_by?: string | null; confirmed_at?: string | null;
  redraft?: { value: string; note: string; source?: string } | null;
}
export interface EscalatedItem { cell_key: string; with: string | null; notes: string[] }

const note: CSSProperties = { margin: 0, fontSize: 13, color: "var(--ds-ink-soft)" };
const amber: CSSProperties = { ...note, color: "var(--ds-amber)" };
const box: CSSProperties = { display: "grid", gap: 8, padding: "12px 16px", border: "1px solid var(--ds-line-2)", borderRadius: 12, background: "var(--ds-surface)" };
const field: CSSProperties = { width: "100%", boxSizing: "border-box", background: "var(--ds-surface-2)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 8, padding: 8, font: "inherit" };

const empty = (v: unknown) => v === null || v === undefined || v === "" || v === "Not known yet" ||
  (typeof v === "object" && Object.values(v as Record<string, { value?: unknown }>).every((x) => !x?.value));

/** The word on a chip or mark: a guessed cell with nothing behind it reads "Not found yet", never "Guessed" with no value. */
export function stateWord(c: Pick<LensCellData, "state" | "outcome" | "value"> | undefined): string {
  if (!c) return STATE_WORDS.not_drafted!;
  if (c.state === "guessed" && (c.outcome === "nothing" || empty(c.value))) return t.notFound;
  return STATE_WORDS[c.state] ?? c.state;
}

function valueText(v: unknown): string {
  if (typeof v === "string") return v;
  if (v && typeof v === "object") return Object.entries(v as Record<string, { value?: string | null }>).map(([k, o]) => `${t.owner[k] ?? k}: ${o?.value || t.ownerNone}`).join("\n");
  return "";
}

const day = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "");

/** The agent line that sits under a cell while Lens drafts it (screen 3): the slow wording after five seconds, and "Try again" on failure. */
export function DraftingLine({ state, suggestion, canRetry = false, onTryAgain, slowAfterMs = 5000 }: {
  state: "drafting" | "failed"; suggestion?: string | null; canRetry?: boolean; onTryAgain?: () => void; slowAfterMs?: number;
}) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (state !== "drafting") return;
    const id = window.setTimeout(() => setSlow(true), slowAfterMs);
    return () => window.clearTimeout(id);
  }, [state, slowAfterMs]);
  if (state === "failed") {
    return (
      <div style={{ display: "grid", gap: 6 }}>
        <p role="status" style={amber}>{t.failedLine}</p>
        {suggestion ? <p style={note}>{suggestion}<br /><em>{t.suggestion}</em></p> : null}
        {canRetry && onTryAgain ? <Button onClick={onTryAgain}>{t.tryAgain}</Button> : null}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div aria-hidden="true" style={{ border: "1px dashed var(--ds-teal)", borderRadius: 8, padding: 8, display: "grid", gap: 6 }}>
        {[90, 70, 50].map((w) => <span key={w} style={{ height: 8, width: `${w}%`, background: "var(--ds-line-2)", borderRadius: 4 }} />)}
      </div>
      <p role="status" style={note}>{slow ? t.slow : t.draftingLine}</p>
    </div>
  );
}

export default function LensCell({ cell, intentId, mayAct, canRetry, people, lead, withWho, onChanged, onClose }: {
  cell: LensCellData; intentId: string; mayAct: boolean; canRetry: boolean; people: string[]; lead?: string; withWho?: string | null;
  onChanged: () => void; onClose: () => void;
}) {
  const [dialog, setDialog] = useState(false);
  const [moving, setMoving] = useState(false);
  const [who, setWho] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [said, setSaid] = useState<string | null>(null);
  const base = `/api/intents/${intentId}/define/lens/cells/${encodeURIComponent(cell.cell_key)}`;
  const label = KIND_LABELS[cell.kind] ?? cell.kind;
  const name = cell.name ?? cell.measure_code;
  const go = async (path: string, body: Record<string, unknown> = {}) => {
    setProblem(null);
    try { await apiSend("POST", `${base}/${path}`, body); setMoving(false); onChanged(); } catch (e) { setProblem(e instanceof ApiError ? e.message : t.failed); }
  };
  const has = !empty(cell.value);
  const open = cell.state !== "confirmed" && cell.state !== "drafting";
  const mark = cell.state === "confirmed" ? t.confirmedBy(cell.confirmed_by ?? "", day(cell.confirmed_at)) : stateWord(cell);

  return (
    <section aria-label={`${label} for ${name}`} style={box}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <strong>{`${label}: ${name}`}</strong>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <Chip>{mark}</Chip>
          {cell.state === "escalated" ? <Chip>{t.withLead(withWho ?? lead ?? "the person who decides")}</Chip> : null}
          <Button onClick={onClose}>{t.close}</Button>
        </div>
      </div>
      {cell.state === "drafting" || cell.state === "failed"
        ? <DraftingLine state={cell.state} suggestion={cell.suggestion} canRetry={canRetry} onTryAgain={() => void go("try-again")} />
        : has
          ? <><p style={{ margin: 0, whiteSpace: "pre-line" }}>{valueText(cell.value)}</p><p style={note}>{cell.source || t.noSource}</p></>
          : <p style={note}>{cell.state === "guessed" ? t.notFound : t.notDrafted}</p>}
      {cell.state === "redrafted" && cell.redraft ? (
        <div style={{ ...box, borderStyle: "dashed" }}>
          <p style={note}>{t.first}</p><p style={{ margin: 0, whiteSpace: "pre-line" }}>{valueText(cell.value)}</p>
          <p style={note}>{t.redraft}</p><p style={{ margin: 0, whiteSpace: "pre-line" }}>{cell.redraft.value}</p>
          <p style={note}>{t.because(cell.redraft.note)}</p>
          {mayAct ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button variant="primary" onClick={() => void go("pick", { choice: "redraft" })}>{t.useThis}</Button>
              <Button onClick={() => void go("pick", { choice: "first" })}>{t.keepFirst}</Button>
            </div>
          ) : null}
        </div>
      ) : null}
      {said ? <p role="status" style={note}>{said}</p> : null}
      {problem ? <p role="alert" style={amber}>{problem}</p> : null}
      {mayAct && open ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {cell.state === "guessed" && has ? <Button variant="primary" onClick={() => void go("confirm")}>{t.confirm}</Button> : null}
          {cell.state !== "escalated" && cell.state !== "failed" ? <Button onClick={() => setDialog(true)}>{t.sendBack}</Button> : null}
          <Button onClick={() => setMoving(!moving)}>{t.notMine}</Button>
        </div>
      ) : null}
      {moving ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <select aria-label={t.pickWho} value={who} onChange={(e) => setWho(e.target.value)} style={{ ...field, width: "auto" }}>
            <option value="">{t.pickNone}</option>
            {people.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <Button disabled={!who} onClick={() => void go("not-mine", { person: who })}>{t.notMineIt(who || "...")}</Button>
        </div>
      ) : null}
      {dialog ? (
        <SendBackDialog intentId={intentId} cellKey={cell.cell_key} kind={label.toLowerCase()} measure={name} second={cell.state === "redrafted"} lead={lead}
          onClose={() => setDialog(false)}
          onDone={(outcome, text) => { setDialog(false); setSaid(outcome === "redrafted" || outcome === "escalated" ? null : text ?? null); onChanged(); }} />
      ) : null}
    </section>
  );
}

/** Screen 5: what Grace decides. Both drafts and both notes, then the options. */
export function EscalationQueue({ intentId, items, cells, onChanged }: {
  intentId: string; items: EscalatedItem[]; cells: Record<string, LensCellData>; onChanged: () => void;
}) {
  const [problem, setProblem] = useState<string | null>(null);
  const [wording, setWording] = useState<Record<string, string>>({});
  const decide = async (key: string, choice: string, text = "") => {
    setProblem(null);
    try { await apiSend("POST", `/api/intents/${intentId}/define/lens/cells/${encodeURIComponent(key)}/decide`, { choice, wording: text }); onChanged(); } catch (e) { setProblem(e instanceof ApiError ? e.message : t.failed); }
  };
  return (
    <section aria-label={t.queueTitle} style={box}>
      <strong>{t.queueTitle}</strong>
      {items.length === 0 ? <p style={note}>{t.queueEmpty}</p> : (
        <ul style={{ margin: 0, padding: 0, display: "grid", gap: 8 }}>
          {items.map((it) => {
            const c = cells[it.cell_key];
            const w = wording[it.cell_key] ?? "";
            return (
              <li key={it.cell_key} style={{ ...box, listStyle: "none" }}>
                <strong>{`${KIND_LABELS[c?.kind ?? ""] ?? c?.kind}: ${c?.name ?? c?.measure_code}`}</strong>
                <p style={note}>{t.first}</p><p style={{ margin: 0, whiteSpace: "pre-line" }}>{valueText(c?.value) || t.notFound}</p>
                {c?.redraft ? <><p style={note}>{t.redraft}</p><p style={{ margin: 0, whiteSpace: "pre-line" }}>{c.redraft.value}</p></> : null}
                {it.notes.map((n, i) => <p key={i} style={note}>{t.noteOf(i + 1, n)}</p>)}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Button onClick={() => void decide(it.cell_key, "first")}>{t.useFirst}</Button>
                  {c?.redraft ? <Button onClick={() => void decide(it.cell_key, "redraft")}>{t.useRedraft}</Button> : null}
                  <Button onClick={() => void decide(it.cell_key, "unknown")}>{t.unknown}</Button>
                </div>
                <label style={note}>{t.wordingLabel}
                  <textarea value={w} maxLength={300} onChange={(e) => setWording({ ...wording, [it.cell_key]: e.target.value })} style={{ ...field, minHeight: 56 }} />
                </label>
                <div><Button disabled={w.trim() === ""} onClick={() => void decide(it.cell_key, "write", w.trim())}>{`${t.writeIt}: ${t.save}`}</Button></div>
              </li>
            );
          })}
        </ul>
      )}
      {problem ? <p role="alert" style={amber}>{problem}</p> : null}
    </section>
  );
}
