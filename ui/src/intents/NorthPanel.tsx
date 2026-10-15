import { useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiSend } from "../api/client";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { Button } from "../design";
import "../modules/m1_intent/wall/wall.css"; // the ds-north markup is shared with the wall's panel
import NorthSheet from "./NorthSheet";

const c = {
  name: "North",
  loading: "North is getting ready.",
  failed: "North could not do that just now. Please try again.",
  none: "North's panel is not shown for this intent.",
  pill: (n: number) => `North, ${n} waiting`,
  pillNone: "North, nothing waiting",
  askingNow: "Asking now",
  noQuestion: "North has nothing to ask right now.",
  waitingFor: (name: string) => `Waiting for ${name}`,
  noThread: "No conversation yet. North will open one when this intent starts.",
  yourAnswer: "Your answer",
  answer: "Answer",
  readOnly: "You are reading this intent. You cannot answer.",
  confirm: "Confirm",
  edit: "Edit",
  discard: "Discard",
  save: "Save my edit",
  onlyCan: (name: string) => `Only ${name} can confirm this`,
  basedOn: "Based on:",
  reason: "Why (one line)",
  record: "Record my pick",
  showEarlier: "Show earlier",
  you: "You",
  voiceOff: "Spoken replies are off",
  nudges: (n: number) => `Nudges sent: ${n}`,
  retry: "Try again",
  ask: "Ask North something about this intent",
  askButton: "Ask North",
  wrong: "Tell the organiser North got this wrong",
  wrongField: "What did North get wrong?",
  wrongSend: "Tell the organiser",
  nudgeOpen: "Open North",
  nudgeLater: "Not now",
  counts: (a: number, b: number, d: number) => `Drafts confirmed: ${a}. Edited: ${b}. Discarded: ${d}.`,
};

interface Option { key: string; label: string; reason: "required" | "optional" }
interface Draft {
  id: string; kind: string; text: string; status: string; chip: string; based_on: string[]; options: Option[] | null;
  can_confirm: boolean; confirm_by: string; is_proposal: boolean;
}
interface Turn { id: string; role: "north" | "person" | "system"; text: string; kind: string; mine: boolean; by_name: string | null }
export interface NorthState {
  head: { name: string; role_line: string };
  seat?: string | null; nudge?: { text: string; at: string } | null;
  read_only: boolean; can_answer: boolean; waiting: number;
  asking: { question: string; mine: boolean; holder_name: string | null } | null;
  turn: { line: string; mine: boolean } | null;
  clock: string | null; drafts: Draft[]; thread: Turn[];
  voice: { available: boolean; reason: string };
  footer?: { nudges: number; confirmed?: number; edited?: number; discarded?: number; note?: string };
  reply?: string | null;
}

const base = (id: string) => `/api/intents/${encodeURIComponent(id)}/north`;
const say = (e: unknown) => (e instanceof ApiError && e.message ? e.message : c.failed);

/** North's panel on every intent screen (spec 08, screen A): asking now, whose turn, the clock, drafts, the thread and the answer box.
 * The page places it (docked right at 1280, a sheet at 390); `onChange` lets the page reload what a confirmed draft changed. */
export default function NorthPanel({ intentId, onChange }: { intentId: string; onChange?: () => void }) {
  // no seat, a 403 or a 404 means no panel for this person (the page around it already loaded): nothing at all, never an error
  const load = useLoad<NorthState | null>(
    () => apiGet<NorthState>(base(intentId)).then((d) => (d.seat === null ? null : d), (e: unknown) => {
      if (e instanceof ApiError && (e.status === 403 || e.status === 404)) return null;
      throw e;
    }),
    intentId,
    (d) => d === null,
  );
  const [fresh, setFresh] = useState<NorthState | null>(null);
  const data = fresh ?? load.data;
  const [open, setOpen] = useState(false);
  const phone = usePhone();
  // the bottom bar of a stage view and the nudge strip ask for North by this event; on a phone it opens the sheet
  useEffect(() => {
    const f = () => setOpen(true);
    window.addEventListener("north:open", f);
    return () => window.removeEventListener("north:open", f);
  }, []);
  if (load.state === "empty" && !fresh) return null; // no seat: no panel and no thread (spec 08), and nothing that reads as an error
  const panel = (
    <aside className="ds-north" aria-label="North">
      <ScreenState state={fresh ? "populated" : load.state} message={load.state === "empty" ? c.none : load.message ?? (load.state === "loading" ? c.loading : undefined)} onRetry={load.retry}>
        {data ? <Body intentId={intentId} s={data} set={setFresh} onChange={onChange} /> : null}
      </ScreenState>
    </aside>
  );
  // at phone width the panel is the bottom sheet behind a pill: "North, 1 waiting" (spec 08, screen A)
  return phone ? <NorthSheet open={open} onOpenChange={setOpen} waiting={(data?.waiting ?? 0) > 0} label={data ? (data.waiting > 0 ? c.pill(data.waiting) : c.pillNone) : c.name} closeLabel="Close North">{panel}</NorthSheet> : panel;
}

function usePhone() {
  const q = "(max-width: 599px)";
  const [on, setOn] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(q).matches);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const f = () => setOn(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return on;
}

function Body({ intentId, s, set, onChange }: { intentId: string; s: NorthState; set: (s: NorthState) => void; onChange?: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [ask, setAsk] = useState("");
  const [wrong, setWrong] = useState<string | null>(null);
  const again = useRef<(() => void) | null>(null);
  const narrow = typeof window !== "undefined" && window.innerWidth < 600;
  const turns = narrow && !all ? s.thread.slice(-3) : s.thread;
  const can = s.can_answer && (s.asking ? s.asking.mine : true);

  async function run(path: string, body?: unknown, done?: () => void) {
    again.current = () => void run(path, body, done);
    setBusy(true);
    setError(null);
    try {
      set(await apiSend<NorthState>("POST", `${base(intentId)}${path}`, body));
      done?.();
      onChange?.();
    } catch (e) {
      setError(say(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="ds-north__who">
        <span aria-hidden="true" className="ds-north__mark">N</span>
        <strong>{s.head.name}<span>{s.head.role_line}</span></strong>
      </div>
      <p className="ds-north__card" data-testid="north-pill">{s.waiting > 0 ? c.pill(s.waiting) : c.pillNone}</p>
      <button type="button" className="n-btn" disabled aria-label={c.voiceOff} title={s.voice.reason}>{s.voice.reason}</button>
      <div data-testid="north-asking" className={`ds-north__turn${s.asking?.mine ? " ds-north__turn--now" : ""}`}>
        <small>{c.askingNow}</small>
        {s.asking ? (
          <>
            <span>{s.asking.question}</span>
            {s.asking.mine ? null : <span className="ds-north__muted">{c.waitingFor(s.asking.holder_name ?? "someone")}</span>}
          </>
        ) : <span>{c.noQuestion}</span>}
      </div>
      <p className="ds-north__muted" data-testid="north-turn">{s.turn?.line ?? "Nobody is waiting"}</p>
      {s.clock ? <p className="ds-north__muted" data-testid="north-clock">{s.clock}</p> : null}
      {s.drafts.map((d) => <DraftCard key={d.id} d={d} busy={busy} run={run} />)}
      <ol aria-live="polite" className="ds-north__thread">
        {narrow && !all && s.thread.length > 3 ? <li><button type="button" className="n-btn" onClick={() => setAll(true)}>{c.showEarlier}</button></li> : null}
        {turns.length === 0 ? <li className="ds-north__muted">{c.noThread}</li> : null}
        {turns.map((t) => (
          <li key={t.id}>
            <div className={`ds-north__turn${t.role === "person" ? " ds-north__turn--you" : ""}`}>
              <small>{t.role === "person" ? (t.mine ? c.you : t.by_name ?? c.you) : c.name}</small>
              {t.text}
            </div>
          </li>
        ))}
      </ol>
      {s.read_only ? <p className="ds-north__muted">{c.readOnly}</p> : (
        <>
          <label className="ds-north__answer">
            {c.yourAnswer}
            <textarea value={text} placeholder={s.asking?.question ?? ""} disabled={busy || !can} onChange={(e) => setText(e.target.value)} />
          </label>
          {!can && s.asking ? <p className="ds-north__muted">{c.waitingFor(s.asking.holder_name ?? "someone")}</p> : null}
          <div className="ds-north__actions">
            <Button variant="primary" disabled={busy || !can || !text.trim()} onClick={() => void run("/turns", { text: text.trim() }, () => setText(""))}>{c.answer}</Button>
          </div>
          <label className="ds-north__answer">
            {c.ask}
            <textarea value={ask} disabled={busy} onChange={(e) => setAsk(e.target.value)} />
          </label>
          <div className="ds-north__actions">
            <Button disabled={busy || !ask.trim()} onClick={() => void run("/turns", { text: ask.trim(), ask: true }, () => setAsk(""))}>{c.askButton}</Button>
          </div>
          {s.seat !== "organiser" && s.seat !== "admin" ? (
            wrong === null
              ? <button type="button" className="n-btn" onClick={() => setWrong("")}>{c.wrong}</button>
              : (
                <>
                  <label className="ds-north__answer">{c.wrongField}<textarea value={wrong} onChange={(e) => setWrong(e.target.value)} /></label>
                  <div className="ds-north__actions">
                    <Button disabled={busy || !wrong.trim()} onClick={() => void run("/turns", { text: wrong.trim(), wrong: true }, () => setWrong(null))}>{c.wrongSend}</Button>
                  </div>
                </>
              )
          ) : null}
        </>
      )}
      {error ? (
        <p role="alert" className="ds-north__error">
          {error} <button type="button" className="n-btn" onClick={() => again.current?.()}>{c.retry}</button>
        </p>
      ) : null}
      {s.footer ? (
        <p className="ds-north__muted" data-testid="north-footer">
          {c.nudges(s.footer.nudges)} {s.footer.note ?? c.counts(s.footer.confirmed ?? 0, s.footer.edited ?? 0, s.footer.discarded ?? 0)}
        </p>
      ) : null}
    </>
  );
}

function DraftCard({ d, busy, run }: { d: Draft; busy: boolean; run: (path: string, body?: unknown, done?: () => void) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(d.text);
  const [pick, setPick] = useState<string | null>(null);
  const [why, setWhy] = useState("");
  const chosen = d.options?.find((o) => o.key === pick);
  const need = chosen?.reason === "required" && !why.trim();
  const p = `/drafts/${d.id}`;
  return (
    <div className="ds-north__turn" style={{ borderStyle: "dashed", opacity: d.can_confirm ? 1 : 0.7 }} data-testid="north-draft">
      <small>{d.chip}</small>
      {editing ? <textarea aria-label={c.edit} value={text} onChange={(e) => setText(e.target.value)} /> : <span>{d.text}</span>}
      {d.based_on.length ? <span className="ds-north__muted">{c.basedOn} {d.based_on.join(", ")}</span> : null}
      {d.is_proposal && d.options ? (
        <>
          <div className="ds-north__actions">
            {d.options.map((o) => (
              <Button key={o.key} aria-pressed={pick === o.key} disabled={busy || !d.can_confirm} onClick={() => setPick(o.key)}>{o.label}</Button>
            ))}
          </div>
          {pick ? (
            <>
              <label className="ds-north__answer">{c.reason}<textarea value={why} onChange={(e) => setWhy(e.target.value)} /></label>
              <Button variant="primary" disabled={busy || need} onClick={() => void run(`/proposals/${d.id}/pick`, { key: pick, reason: why.trim() || null })}>{c.record}</Button>
            </>
          ) : null}
        </>
      ) : (
        <div className="ds-north__actions">
          {editing
            ? <Button variant="primary" disabled={busy || !text.trim()} onClick={() => void run(`${p}/confirm`, { text: text.trim() })}>{c.save}</Button>
            : <Button variant="primary" disabled={busy || !d.can_confirm} onClick={() => void run(`${p}/confirm`, {})}>{c.confirm}</Button>}
          <Button disabled={busy || !d.can_confirm} onClick={() => setEditing((e) => !e)}>{c.edit}</Button>
          <Button disabled={busy || !d.can_confirm} onClick={() => void run(`${p}/discard`)}>{c.discard}</Button>
        </div>
      )}
      {d.can_confirm ? null : <span className="ds-north__muted">{c.onlyCan(d.confirm_by)}</span>}
    </div>
  );
}

/** Spec 08, screen B: the one-line "waiting for you" strip under the page head. Shows today's nudge for this person only; "Not now"
 * hides it until tomorrow in this browser and writes nothing to the record. */
export function NorthNudge({ intentId }: { intentId: string }) {
  const [text, setText] = useState<string | null>(null);
  const key = `north-nudge:${intentId}:${new Date().toISOString().slice(0, 10)}`;
  const [gone, setGone] = useState(() => { try { return localStorage.getItem(key) === "1"; } catch { return false; } });
  useEffect(() => {
    let live = true;
    apiGet<NorthState>(base(intentId)).then((d) => { if (live) setText(d.nudge?.text ?? null); }, () => undefined);
    return () => { live = false; };
  }, [intentId]);
  if (!text || gone) return null;
  const hide = () => { try { localStorage.setItem(key, "1"); } catch { /* the strip just comes back on reload */ } setGone(true); };
  return (
    <p className="ds-north__card" data-testid="north-nudge" role="status">
      {c.name}: {text}{" "}
      <Button onClick={() => window.dispatchEvent(new Event("north:open"))}>{c.nudgeOpen}</Button>{" "}
      <Button onClick={hide}>{c.nudgeLater}</Button>
    </p>
  );
}
