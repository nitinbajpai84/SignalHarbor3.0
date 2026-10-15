import { useState } from "react";

import { discardThread, type Thread } from "../api";
import "./discard.css";

/** Discard a thread the person no longer wants. Asks once, takes an optional reason; the thread stays in the record, off the Desk. */
export default function Discard({ id, onDone, compact = false }: { id: string; onDone: (t: Thread) => void; compact?: boolean }) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  if (!asking) {
    return <button type="button" className={compact ? "v3-discard small" : "v3-discard"} onClick={() => setAsking(true)}>Discard</button>;
  }
  return (
    <div className="v3-discard-ask" role="group" aria-label="Discard this thread">
      <span>Discard this thread? It stops and leaves your Desk; it stays in the record with your name and the time.</span>
      <input aria-label="Why (optional)" placeholder="Why (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <span className="v3-row">
        <button type="button" className="danger" disabled={busy} onClick={() => {
          setBusy(true);
          discardThread(id, reason.trim()).then(onDone, (e: Error) => setProblem(e.message)).finally(() => setBusy(false));
        }}>Discard</button>
        <button type="button" onClick={() => { setAsking(false); setProblem(""); }}>Keep it</button>
      </span>
      {problem && <span className="v3-err" role="alert">{problem}</span>}
    </div>
  );
}
