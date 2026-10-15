import { useState } from "react";

import { Button } from "../../design";
import { decide, type AccessRequest } from "./api";

// K1: the approve card. "Priya asks to use the custodian statements. Approve / Not now": one click grants for 30 days, or until revoked.
// G1 reuses it for a project: `answer` replaces the library call and `req.item_name` is the project title.
export default function AccessCard({ req, onDone, answer }: { req: AccessRequest; onDone: () => void; answer?: (approve: boolean, days: number) => Promise<unknown> }) {
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const go = (approve: boolean) => {
    setBusy(true);
    (answer ? answer(approve, days) : decide(req.id, approve, days)).then(onDone, () => { setError("That did not go through. Please try again."); setBusy(false); });
  };
  return (
    <div role="group" aria-label={`Request from ${req.requester}`} style={{ border: "1px solid currentColor", borderRadius: 8, padding: 12, margin: "8px 0" }}>
      <p style={{ margin: 0 }}>{req.requester} asks to use {req.item_name}.{req.reason ? ` "${req.reason}"` : ""}</p>
      {req.owner_left ? <p className="ds-muted" style={{ margin: "4px 0 0" }}>The owner has left, so you answer as company administrator.</p> : null}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
        <Button variant="primary" disabled={busy} onClick={() => go(true)}>Approve</Button>
        <label style={{ fontSize: 13 }}>for{" "}
          <select aria-label="How long" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={30}>30 days</option><option value={7}>7 days</option><option value={0}>until I take it back</option>
          </select>
        </label>
        <Button disabled={busy} onClick={() => go(false)}>Not now</Button>
      </div>
      {error ? <p role="alert" style={{ margin: "4px 0 0" }}>{error}</p> : null}
    </div>
  );
}
