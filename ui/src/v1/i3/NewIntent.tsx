import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import AgentChip from "../../components/AgentChip";
import Panel from "../../components/Panel";
import { Button, PageFrame } from "../../design";
import { createIntent } from "./api";

/** /centre/intent/new: one line, then North's thread. */
export default function NewIntent() {
  const nav = useNavigate();
  const [line, setLine] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start(e: FormEvent) {
    e.preventDefault();
    if (!line.trim()) return;
    setBusy(true);
    setError("");
    try {
      const made = await createIntent(line.trim());
      const iid = made.id ?? made.intent_id;
      if (!iid) throw new ApiError("North could not open the thread. Please try again.", 500);
      nav(`/centre/intent/${encodeURIComponent(iid)}/thread`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "North could not open the thread. Please try again.");
      setBusy(false);
    }
  }

  return (
    <PageFrame title="What do you want to know?" subline="One line is enough. North, the industry expert, asks the rest.">
      <Panel>
        <AgentChip name="North" status="waiting" />
        <form onSubmit={start} style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16 }}>
          <label style={{ flex: "1 1 280px", display: "flex", flexDirection: "column", gap: 6 }}>
            Your question in one line
            <input value={line} onChange={(e) => setLine(e.target.value)} maxLength={300}
              placeholder="For example: how did our portfolios do against the benchmark each month?" />
          </label>
          <Button type="submit" variant="primary" disabled={busy || !line.trim()} style={{ alignSelf: "flex-end" }}>
            {busy ? "Opening…" : "Start with North"}
          </Button>
        </form>
        {error ? <p role="alert">{error}</p> : null}
      </Panel>
    </PageFrame>
  );
}
