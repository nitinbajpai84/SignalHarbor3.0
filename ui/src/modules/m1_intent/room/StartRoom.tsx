import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import { startRoom } from "../api";
import { m1Room } from "../copy";
import { saveLink } from "./guestToken";

/** On a saved draft: "Start the room" creates the seats and the join link and fixes the prepared details (M1-03). Asks first. */
export default function StartRoom({ sessionId, saved, onStarted }: { sessionId: string; saved: boolean; onStarted: () => void }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const link = await startRoom(sessionId);
      saveLink(sessionId, link.join_path); // shown on this screen only; the server keeps just a hash of it
      onStarted();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : m1Room.organiser.busy);
      setBusy(false);
    }
  }

  return (
    <Panel title={m1Room.start.title} className="m1-room">
      <p>{m1Room.start.intro}</p>
      {saved ? null : (
        <p role="status" className="n-muted">
          {m1Room.start.saveFirst}
        </p>
      )}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      {asking ? (
        <div role="alertdialog" aria-label={m1Room.start.sure} className="m1-actions">
          <p>{m1Room.start.sure}</p>
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => void start()}>
            {busy ? m1Room.start.busy : m1Room.start.yes}
          </button>
          <button type="button" className="n-btn" disabled={busy} onClick={() => setAsking(false)}>
            {m1Room.start.no}
          </button>
        </div>
      ) : (
        <button type="button" className="n-btn primary" onClick={() => setAsking(true)}>
          {m1Room.start.button}
        </button>
      )}
    </Panel>
  );
}
