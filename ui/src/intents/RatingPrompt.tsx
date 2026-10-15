import { useState } from "react";

import { apiSend } from "../api/client";
import { Button, Chip } from "../design";
import { rateCopy as t } from "./views/closeCopy";

export interface Rating {
  window_open: boolean; drop_at: string; dropped: boolean; can_rate: boolean; rated_by_you: boolean; waived: boolean;
  mine: { score: number; note: string; anonymous: boolean } | null;
  summary: { asked: number; rated: number; count: number; mean: number | null; bar: Record<string, number> | null;
    signed: { name: string; score: number; note: string }[]; anonymous_count: number; empty: string | null; hidden: string | null } | null;
  used: { answer: "yes" | "partly" | "no" | null; note: string | null; ask_on: string; due: boolean; can_answer: boolean;
    suggest: { text: string; href: string } | null } | null;
}

const NOTE_MAX = 140;
const day = (iso: string) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); };
const fail = (e: unknown) => (e instanceof Error && e.message ? e.message : t.failed);

/** Spec 10, screen A: the prompt. Nothing is sent until "Send rating"; anonymous unless the person puts a name on it. */
export function RatingPrompt({ intentId, rating, onChange }: { intentId: string; rating: Rating; onChange: () => void }) {
  const [score, setScore] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [named, setNamed] = useState(false);
  const [err, setErr] = useState("");
  const [skipped, setSkipped] = useState(false);
  const post = async (path: string, body?: unknown) => {
    try { await apiSend("POST", `/api/intents/${intentId}/${path}`, body); onChange(); } catch (e) { setErr(fail(e)); }
  };
  if (rating.mine) return (
    <div>
      <p role="status"><strong>{t.thanks(rating.mine.score)}</strong></p>
      {rating.mine.note && <p>{t.gaveNote(rating.mine.note)}</p>}
      <p className="n-muted">{rating.mine.anonymous ? t.anonymousAs : t.signedAs}</p>
    </div>
  );
  if (rating.waived) return <p className="n-muted">{t.waived}</p>;
  if (rating.dropped) return <p className="n-muted">{t.closedWindow(day(rating.drop_at))}</p>;
  if (!rating.can_rate || skipped) return null;
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <p><strong>{t.panel}</strong></p>
      <p className="n-muted">{t.helper}</p>
      <div role="group" aria-label={t.panel} style={{ display: "flex", gap: 8 }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" className={`ds-chip${score === n ? " ds-chip--active" : ""}`} aria-pressed={score === n}
            style={{ flex: "1 1 0", minWidth: 0, maxWidth: 56, minHeight: 56, display: "grid", placeItems: "center", padding: 4, fontSize: 13 }} onClick={() => setScore(n)}>
            <span>{n}</span><small style={{ fontSize: 10, lineHeight: 1.1, textAlign: "center", whiteSpace: "normal" }}>{t.words[n] ?? ""}</small>
          </button>
        ))}
      </div>
      <label>
        <span className="ic-sr">{t.note}</span>
        <input className="ds-input" value={note} maxLength={NOTE_MAX} placeholder={t.note} aria-label={t.note} onChange={(e) => setNote(e.target.value)} style={{ width: "100%" }} />
        <small className="n-muted">{t.count(note.length, NOTE_MAX)}</small>
      </label>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" role="switch" checked={named} onChange={(e) => setNamed(e.target.checked)} />
        <span>{t.nameOn}</span>
      </label>
      <p className="n-muted">{named ? t.nameHelper : t.anonOff}</p>
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button variant="primary" disabled={score === null} onClick={() => post("ratings", { score, note, anonymous: !named })}>{t.send}</Button>
        <Button onClick={() => setSkipped(true)}>{t.skip}</Button>
        <Button onClick={() => post("rating/waive")}>{t.notPart}</Button>
      </div>
    </div>
  );
}

/** Spec 10, screen B: counts for the organiser and sponsor. A mean and a bar only from three ratings; no one is named as anonymous. */
export function RatingSummary({ rating }: { rating: Rating }) {
  const s = rating.summary;
  if (!s) return null;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <Chip>{s.rated ? t.rated(s.rated, s.asked) : t.none}</Chip>
      {s.mean !== null && s.bar ? (
        <>
          <p><strong>{t.average(s.mean, s.count)}</strong></p>
          <div role="img" aria-label={Object.entries(s.bar).map(([k, v]) => `${k}: ${v}`).join(", ")} style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 40 }}>
            {Object.entries(s.bar).map(([k, v]) => <span key={k} title={`${k}: ${v}`} style={{ flex: 1, height: `${Math.max(4, (v / Math.max(1, ...Object.values(s.bar!))) * 40)}px`, background: "var(--ds-teal-bright)" }} />)}
          </div>
        </>
      ) : s.hidden ? <p className="n-muted">{s.hidden}</p> : null}
      {s.signed.length ? (
        <ul aria-label={t.signedList}>{s.signed.map((x, i) => <li key={i}>{x.name}: {x.score}{x.note ? `. ${x.note}` : ""}</li>)}</ul>
      ) : s.count > 0 ? <p className="n-muted">{t.noSigned}</p> : null}
      {s.anonymous_count > 0 && <p className="n-muted">{t.anonLine(s.anonymous_count)}</p>}
    </div>
  );
}

/** Spec 10, screen C: was the outcome used. The organiser answers once North asks, a month after closure. */
export function OutcomeUsed({ intentId, rating, onChange }: { intentId: string; rating: Rating; onChange: () => void }) {
  const u = rating.used;
  const [answer, setAnswer] = useState<"yes" | "partly" | "no" | null>(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  if (!u) return null;
  const save = async () => {
    try { await apiSend("POST", `/api/intents/${intentId}/outcome-used`, { answer, note }); onChange(); } catch (e) { setErr(fail(e)); }
  };
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {u.answer ? <p>{t.usedAnswered(t[u.answer], u.note ?? "")}</p> : <p className="n-muted">{u.due ? t.usedWaiting : t.usedAsk(day(u.ask_on))}</p>}
      {u.suggest && <p><strong>{t.suggest}:</strong> <a href={u.suggest.href}>{u.suggest.text}</a></p>}
      {u.can_answer && (
        <>
          <p>{t.usedQ}</p>
          <div role="group" aria-label={t.usedQ} style={{ display: "flex", gap: 8 }}>
            {(["yes", "partly", "no"] as const).map((a) => <Chip key={a} tone={answer === a ? "active" : "default"} onClick={() => setAnswer(a)}>{t[a]}</Chip>)}
          </div>
          <input className="ds-input" value={note} maxLength={200} placeholder={t.usedLine} aria-label={t.usedLine} onChange={(e) => setNote(e.target.value)} />
          {err && <p role="alert" className="ds-warn">{err}</p>}
          <Button variant="primary" disabled={!answer} onClick={save}>{t.usedSave}</Button>
        </>
      )}
    </div>
  );
}
