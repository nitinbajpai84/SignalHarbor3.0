import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

import { ApiError, apiGet, apiSend, me } from "../../api/client";
import { Button, Chip } from "../../design";
import LensCell, { DraftingLine, EscalationQueue, KIND_LABELS, stateWord, type EscalatedItem, type LensCellData } from "./LensCell";

export { DraftingLine };
export { default as SendBackDialog } from "./SendBackDialog";

// The Lens strip at the top of Define's right panel (spec 44, screens 1, 3, 3a and 4). Counts come from the server's `define.lens` record.

const t = {
  name: "Lens",
  notStarted: "Not available yet: Lens has not started. North starts it when Define opens.",
  noMeasures: "Not available yet: no measures to draft.",
  drafted: (n: number, total: number, m: number) => `Lens has drafted ${n} of ${total} items for ${m} ${m === 1 ? "measure" : "measures"}.`,
  resumed: (n: number, total: number) => `Lens stopped at ${n} of ${total}; carrying on`,
  drafting: (n: number, of: number, name: string) => `Drafting ${n} of ${of} for ${name}`,
  chip: (open: number, waiting: number) => `Questions: ${open} open for you, ${waiting} waiting`,
  noModel: "Lens could not read your documents because document reading is not set up for your company; these are the industry pack's suggestions.",
  read: (d: number, i: number, profile: boolean, pack: boolean) =>
    `Read: ${d} ${d === 1 ? "document" : "documents"}, ${i} ${i === 1 ? "interview" : "interviews"}${profile ? ", the profile" : ""}${pack ? ", the industry pack as suggestions" : ""}`,
  readNone: "Lens read no documents. The pack's suggestions are shown, marked as suggestions.",
  detail: "Show each measure",
  hideDetail: "Hide the measures",
  detailEmpty: "No measures behind this group yet. Lens drafts them once a baseline exists.",
  retryAll: (n: number) => `Try again for ${n} ${n === 1 ? "item" : "items"} that failed`,
  retryFailed: "Lens could not start the retry. Try again in a moment.",
  loadFailed: "Lens could not be reached just now. Reload the page to try again.",
  loading: "Lens is loading.",
  noQuestions: "Lens has no questions for you.",
  waiting: (n: number) => `${n} more ${n === 1 ? "question is" : "questions are"} waiting`,
  ownerWhy: "Lens is asking because you are named as the owner.",
  found: (n: number) => `The documents say ${n === 1 ? "one thing" : `${n} things`}:`,
  useMeaning: "Use this meaning",
  notMine: "Not mine",
  notMineIt: (who: string) => `Not mine, it is ${who}`,
  pickWho: "Who is it?",
  pickNone: "Choose a person",
  say: "Say it in your words",
  save: "Save my answer",
  saveFailed: "Your answer could not be saved. Try again.",
  draftingLine: "Lens is drafting this.",
  slow: "Taking longer than usual. You can carry on, the page is not blocked.",
  failedLine: "Lens could not draft this just now.",
  suggestion: "Suggestion from the industry pack, not a draft of yours",
  tryAgain: "Try again",
};

const MAX_NOTE = 300;
const RETRY_ROLES = ["company_admin", "analyst"];

export type LensCell = LensCellData;
export interface LensQuestion {
  id: string; to: string | null; about_cell: string; text: string; term: string; state: string; kind: string;
  item?: string; why?: string; meanings?: { meaning: string; where: string }[];
}
export interface LensState {
  run: { state: string; model_set_up: boolean; order: string[]; resumed_from?: number | null };
  reads: { documents: number; interviews: number; profile: boolean; pack: boolean };
  counts: Record<string, number>; total: number; drafted: number; failed: string[];
  questions: { mine_open: number; waiting: number; open_total: number };
  my_questions: LensQuestion[]; cells: Record<string, LensCell>;
  measures?: number; may_act?: string[]; may_decide?: boolean; people?: string[]; lead?: string | null; escalated?: EscalatedItem[];
}

const card: CSSProperties = { display: "grid", gap: 8, padding: "12px 16px", border: "1px solid var(--ds-line-2)", borderRadius: 12, background: "var(--ds-surface)" };
const row: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", justifyContent: "space-between" };
const note: CSSProperties = { margin: 0, fontSize: 13, color: "var(--ds-ink-soft)" };
const amber: CSSProperties = { ...note, color: "var(--ds-amber)" };

function Question({ q, intentId, people, onDone }: { q: LensQuestion; intentId: string; people: string[]; onDone: () => void }) {
  const [text, setText] = useState("");
  const [moving, setMoving] = useState(false);
  const [who, setWho] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const post = async (leaf: string, body: Record<string, unknown>) => {
    try {
      await apiSend("POST", `/api/intents/${intentId}/define/lens/questions/${q.id}/${leaf}`, body);
      onDone();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : t.saveFailed);
    }
  };
  const field: CSSProperties = { width: "100%", boxSizing: "border-box", background: "var(--ds-surface-2)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 8, padding: 8, font: "inherit" };
  const meanings = q.meanings ?? [];
  return (
    <li style={{ ...card, listStyle: "none" }}>
      <strong>{q.text}</strong>
      {q.item ? <p style={note}>{q.item}</p> : null}
      <p style={note}>{q.why ?? t.ownerWhy}</p>
      {meanings.length > 0 ? (
        <div style={{ display: "grid", gap: 6 }}>
          <p style={note}>{t.found(meanings.length)}</p>
          {meanings.map((m) => (
            <div key={m.meaning} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span>{m.meaning}{m.where ? ` (${m.where})` : ""}</span>
              <Button onClick={() => void post("answer", { answer: m.meaning })}>{t.useMeaning}</Button>
            </div>
          ))}
        </div>
      ) : null}
      <label style={note}>{t.say}
        <textarea value={text} onChange={(e) => setText(e.target.value)} style={{ ...field, minHeight: 64 }} />
      </label>
      {problem ? <p role="alert" style={amber}>{problem}</p> : null}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <Button variant="primary" disabled={text.trim() === ""} onClick={() => void post("answer", { answer: text.trim() })}>{t.save}</Button>
        {q.kind !== "escalation" ? <Button onClick={() => setMoving(!moving)}>{t.notMine}</Button> : null}
      </div>
      {moving ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <select aria-label={t.pickWho} value={who} onChange={(e) => setWho(e.target.value)} style={{ ...field, width: "auto" }}>
            <option value="">{t.pickNone}</option>
            {people.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <Button disabled={!who} onClick={() => void post("reassign", { person: who })}>{t.notMineIt(who || "...")}</Button>
        </div>
      ) : null}
    </li>
  );
}

/** What is being drafted now: the first measure with a cell on the go, and how many of its nine kinds are done. */
function progress(s: LensState): { n: number; of: number; name: string } | null {
  if (s.run.state !== "running") return null;
  const cells = Object.values(s.cells);
  const on = cells.find((c) => c.state === "drafting") ?? cells.find((c) => c.state === "not_drafted");
  if (!on) return null;
  const mine = cells.filter((c) => c.measure_code === on.measure_code);
  const done = mine.filter((c) => c.state !== "drafting" && c.state !== "not_drafted").length;
  return { n: Math.min(done + 1, s.run.order.length), of: s.run.order.length, name: on.name ?? on.measure_code };
}

export default function LensStrip({ intentId, onPick }: { intentId: string; onPick?: (cell: LensCell) => void }) {
  const [s, setS] = useState<LensState | null>(null);
  const [failed, setFailed] = useState(false);
  const [roles, setRoles] = useState<string[]>([]);
  const [open, setOpen] = useState<"detail" | "questions" | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setS(await apiGet<LensState>(`/api/intents/${intentId}/define/lens`));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [intentId]);

  useEffect(() => { void load(); me().then((m) => setRoles(m?.roles ?? [])).catch(() => setRoles([])); }, [load]);
  const running = s?.run.state === "running";
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(id);
  }, [running, load]);

  if (failed && !s) return <p role="alert" style={{ ...amber, padding: "8px 0" }}>{t.loadFailed}</p>;
  if (!s) return <p role="status" style={note}>{t.loading}</p>;

  const cells = Object.values(s.cells);
  const measures = s.measures ?? new Set(cells.map((c) => c.measure_code)).size;
  const idle = s.run.state === "idle";
  const prog = progress(s);
  const mayRetry = roles.some((r) => RETRY_ROLES.includes(r));
  const retry = async () => {
    try {
      await apiSend("POST", `/api/intents/${intentId}/define/lens/run`, { retry: true });
      setProblem(null);
      void load();
    } catch {
      setProblem(t.retryFailed);
    }
  };
  const byMeasure = [...new Set(cells.map((c) => c.measure_code))].map((code) => ({ code, name: cells.find((c) => c.measure_code === code)?.name ?? code, cells: s.run.order.map((k) => cells.find((c) => c.measure_code === code && c.kind === k)) }));
  const q = s.questions;
  const read = s.reads.documents + s.reads.interviews === 0 && !s.reads.profile && !s.reads.pack ? t.readNone : t.read(s.reads.documents, s.reads.interviews, s.reads.profile, s.reads.pack);

  return (
    <section aria-label={t.name} style={card}>
      <div style={row}>
        <div style={{ display: "grid", gap: 4 }}>
          <p style={{ margin: 0, fontWeight: 600 }}>
            {idle ? t.notStarted : s.total === 0 ? t.noMeasures : t.drafted(s.drafted, s.total, measures)}
          </p>
          {running && s.run.resumed_from != null ? <p role="status" style={note}>{t.resumed(s.run.resumed_from, s.total)}</p> : null}
          {prog ? <p role="status" style={note}>{t.drafting(prog.n, prog.of, prog.name)}</p> : null}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {s.total > 0 ? <Chip onClick={() => setOpen(open === "detail" ? null : "detail")} tone={open === "detail" ? "active" : "default"}>{open === "detail" ? t.hideDetail : t.detail}</Chip> : null}
          {q.open_total + q.waiting > 0 ? <Chip onClick={() => setOpen(open === "questions" ? null : "questions")} tone={open === "questions" ? "active" : "default"}>{t.chip(q.mine_open, q.waiting)}</Chip> : null}
        </div>
      </div>
      {!idle && !s.run.model_set_up ? <p style={amber}>{t.noModel}</p> : null}
      {!idle ? <p style={note}>{read}</p> : null}
      {mayRetry && s.failed.length > 0 ? <div><Button onClick={retry}>{t.retryAll(s.failed.length)}</Button></div> : null}
      {problem ? <p role="alert" style={amber}>{problem}</p> : null}
      {open === "detail" ? (
        byMeasure.length === 0 ? <p style={note}>{t.detailEmpty}</p> : (
          <ul style={{ margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {byMeasure.map((m) => (
              <li key={m.code} style={{ listStyle: "none", display: "grid", gap: 4 }}>
                <strong>{m.name}</strong>
                <ul style={{ margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {m.cells.map((c, i) => (
                    <li key={s.run.order[i]} style={{ listStyle: "none" }}>
                      <Chip onClick={c ? () => { setPicked(c.cell_key); onPick?.(c); } : undefined}>{`${KIND_LABELS[s.run.order[i] ?? ""] ?? s.run.order[i]}: ${stateWord(c)}`}</Chip>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )
      ) : null}
      {open === "detail" && picked && s.cells[picked] ? (
        <LensCell cell={s.cells[picked]!} intentId={intentId} mayAct={(s.may_act ?? []).includes(picked)} canRetry={mayRetry || (s.may_act ?? []).includes(picked)}
          people={s.people ?? []} lead={s.lead ?? undefined} withWho={s.escalated?.find((e) => e.cell_key === picked)?.with}
          onChanged={() => void load()} onClose={() => setPicked(null)} />
      ) : null}
      {s.may_decide && (s.escalated ?? []).length > 0 ? <EscalationQueue intentId={intentId} items={s.escalated ?? []} cells={s.cells} onChanged={() => void load()} /> : null}
      {open === "questions" ? (
        <div style={{ display: "grid", gap: 8 }}>
          {s.my_questions.length === 0 ? <p style={note}>{t.noQuestions}</p> : (
            <ul style={{ margin: 0, padding: 0, display: "grid", gap: 8 }}>
              {s.my_questions.map((x) => <Question key={x.id} q={x} intentId={intentId} people={s.people ?? []} onDone={() => void load()} />)}
            </ul>
          )}
          {q.waiting > 0 ? <p style={note}>{t.waiting(q.waiting)}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
