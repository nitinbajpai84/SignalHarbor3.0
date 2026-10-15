import { useState } from "react";
import type { CSSProperties } from "react";

import { ApiError, apiSend } from "../../api/client";
import { Button } from "../../design";

// Screen 3a of spec 44. "Send back" stays off until the note is filled. The server redrafts once, then passes a second send back to the person who decides.

const c = {
  sendTitle: (kind: string, measure: string) => `Send back ${kind} for ${measure} to Lens`,
  noteLabel: "Tell Lens what to change",
  noteNeeded: "Please say what to change.",
  second: (lead: string) => `This was already sent back once. Sending it back again passes it to ${lead} to decide.`,
  send: "Send back",
  cancel: "Cancel",
  sendFailed: "The note could not be sent. Try again.",
};
const MAX_NOTE = 300;
const card: CSSProperties = { display: "grid", gap: 8, padding: "12px 16px", border: "1px solid var(--ds-line-2)", borderRadius: 12, background: "var(--ds-surface)" };
const note: CSSProperties = { margin: 0, fontSize: 13, color: "var(--ds-ink-soft)" };
const amber: CSSProperties = { ...note, color: "var(--ds-amber)" };

export default function SendBackDialog({ intentId, cellKey, kind, measure, second = false, lead = "the person who decides", onClose, onDone }: {
  intentId: string; cellKey: string; kind: string; measure: string; second?: boolean; lead?: string;
  onClose: () => void; onDone: (outcome: string, noteText?: string) => void;
}) {
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const narrow = typeof window !== "undefined" && window.innerWidth <= 600;
  const empty = text.trim() === "";

  const send = async () => {
    setBusy(true);
    try {
      const r = await apiSend<{ outcome: string; note?: string }>("POST", `/api/intents/${intentId}/define/lens/cells/${encodeURIComponent(cellKey)}/send-back`, { note: text.trim() });
      onDone(r.outcome, r.note);
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : c.sendFailed);
      setBusy(false);
    }
  };
  const back: CSSProperties = { position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", display: "grid", placeItems: narrow ? "stretch" : "center", zIndex: 50 };
  const box: CSSProperties = { ...card, width: narrow ? "100%" : 480, maxWidth: "100%", height: narrow ? "100%" : undefined, boxSizing: "border-box", padding: 24, overflow: "auto", ...(narrow ? { display: "flex", flexDirection: "column" as const } : {}) };

  return (
    <div style={back}>
      <div role="dialog" aria-modal="true" aria-label={c.sendTitle(kind, measure)} style={box}>
        <h2 style={{ margin: 0, fontSize: 18 }}>{c.sendTitle(kind, measure)}</h2>
        {second ? <p style={amber}>{c.second(lead)}</p> : null}
        <label style={note}>{c.noteLabel}
          <textarea value={text} maxLength={MAX_NOTE} onBlur={() => setTouched(true)} onChange={(e) => setText(e.target.value)}
            style={{ width: "100%", minHeight: 96, boxSizing: "border-box", background: "var(--ds-surface-2)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 8, padding: 8, font: "inherit" }} />
        </label>
        {touched && empty ? <p role="alert" style={amber}>{c.noteNeeded}</p> : null}
        {problem ? <p role="alert" style={amber}>{problem}</p> : null}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: narrow ? "auto" : undefined }}>
          <Button variant="primary" disabled={empty || busy} onClick={send}>{c.send}</Button>
          <Button onClick={onClose}>{c.cancel}</Button>
        </div>
      </div>
    </div>
  );
}
