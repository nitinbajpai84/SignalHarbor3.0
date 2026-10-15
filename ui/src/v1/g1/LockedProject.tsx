import { useState } from "react";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import { requestProjectAccess, type Lock } from "./api";

// G1: a project the person may not read. Internal shows a lock with the title, stage and owner; Restricted shows only that it exists.
// "Request access" goes to the owner, who answers from Pulse.
export default function LockedProject({ lock, onChange }: { lock: Lock; onChange?: () => void }) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [state, setState] = useState(lock.request?.state ?? "");
  const [error, setError] = useState("");
  const preview = lock.access === "preview";
  const owner = lock.owner ?? "the project owner";
  const send = () => requestProjectAccess(lock.id, reason.trim()).then(
    () => { setState("requested"); setAsking(false); onChange?.(); },
    (e: unknown) => setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."));
  return (
    <PageFrame title={preview ? lock.title || "Project" : "A project you cannot see"}
      subline={<Pill tone="restricted">{lock.sensitivity === "restricted" ? "Restricted" : "Internal"}</Pill>}>
      <section aria-label="This project is locked" className="ds-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        <p style={{ margin: 0 }}>
          <strong><span aria-hidden="true">Locked: </span>{preview ? "You can see its title, stage and owner." : "This project exists, and it is not open to you."}</strong>
        </p>
        {preview ? <p className="ds-muted" style={{ margin: 0 }}>Stage: {lock.stage ?? "not set"}. Owner: {owner}.</p> : null}
        {state === "requested" ? <p style={{ margin: 0 }}>Requested: waiting for {preview ? owner : "its owner"} to answer.</p> : null}
        {state === "denied" ? <p style={{ margin: 0 }}>Not shared just now. You can ask again later.</p> : null}
        {state === "granted" ? <p style={{ margin: 0 }}>Access was given. Reload to open the project.</p> : null}
        {lock.can_request && !["requested", "granted"].includes(state) ? (
          asking ? (
            <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap" }}>
              <input aria-label="Why you need this project" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Why do you need it?" />
              <Button variant="primary" onClick={() => void send()}>Send request</Button>
              <button type="button" className="ds-link" onClick={() => setAsking(false)}>Cancel</button>
            </span>
          ) : <span><Button variant="primary" onClick={() => setAsking(true)}>Request access</Button></span>
        ) : null}
        {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
      </section>
    </PageFrame>
  );
}
