import { useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { requestAccess } from "./api";

// K1: an item the viewer may see but not read: a lock, the preview (never a value), and Request access.
export interface Locked {
  id: string; name: string; kind: string; size: number; at: string; uploaded_by: string; sensitivity: string; topic?: string[];
  access: "request" | "requested" | "denied" | "granted" | "open" | "mine";
  preview?: { contains_personal_data: boolean; kinds: string[]; columns?: string[] | null; heading?: string | null };
}

export default function LockedRow({ item, iid, onChange }: { item: Locked; iid?: string; onChange?: () => void }) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [state, setState] = useState(item.access);
  const [error, setError] = useState("");
  const p = item.preview;
  const send = () => requestAccess(item.id, reason.trim(), iid).then(
    () => { setState("requested"); setAsking(false); onChange?.(); },
    (e: unknown) => setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."));
  return (
    <div style={{ padding: "2px 0" }}>
      <span aria-hidden="true">Locked: </span><strong>{item.name}</strong>{" "}
      <span className="ds-muted">
        ({item.sensitivity}{item.topic?.length ? `, ${item.topic.join(", ")}` : ""}, {item.uploaded_by}, {item.kind})
      </span>
      {p ? (
        <div className="ds-muted" style={{ fontSize: 13 }}>
          {p.contains_personal_data ? `Contains personal data: ${p.kinds.join(", ")}.` : null}
          {p.columns?.length ? ` Columns: ${p.columns.join(", ")}.` : null}
          {p.heading ? ` Starts with: ${p.heading}.` : null}
        </div>
      ) : null}
      {state === "requested" ? <span className="ds-muted">Requested: waiting for {item.uploaded_by}</span> : null}
      {state === "denied" ? <span className="ds-muted">Not shared just now. </span> : null}
      {state === "request" ? (
        asking ? (
          <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
            <input aria-label={`Why you need ${item.name}`} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Why do you need it?" />
            <Button onClick={() => void send()}>Send request</Button>
            <button type="button" className="ds-link" onClick={() => setAsking(false)}>Cancel</button>
          </span>
        ) : <button type="button" className="ds-link" aria-label={`Request access to ${item.name}`} onClick={() => setAsking(true)}>Request access</button>
      ) : null}
      {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
    </div>
  );
}
