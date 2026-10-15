import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import { Button } from "../../design";

// Ruling 31: a change or addition someone wants is an Initiative, never a Problem. After the first answer North reads it with the
// chooser's own classifier; when it sounds like an Initiative the reporter gets one click that carries the words across.
const t = {
  lead: "This sounds like an Initiative.", why: "A Problem is for something that is wrong in operations today. Adding or changing something is a project.",
  switch: "Switch to an Initiative", keep: "Keep it as a Problem", failed: "That did not work. Try again.",
};
interface Proposal { type: string | null; reason: string }

export default function ProblemSteer({ draftId, what, saw }: { draftId: string; what: string; saw: string }) {
  const nav = useNavigate();
  const [hit, setHit] = useState<Proposal | null>(null);
  const [kept, setKept] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const text = `${what.trim()}. ${saw.trim()}`.slice(0, 600);
  useEffect(() => {
    setHit(null);
    if (!what.trim()) return;
    apiSend<Proposal>("POST", "/api/intents/classify", { text }).then((p) => setHit(p.type === "initiative" ? p : null), () => setHit(null));
  }, [text, what]);
  if (!hit || kept === text) return null;

  const swap = async () => {
    setBusy(true); setError("");
    try {
      const made = await apiSend<{ id: string }>("POST", "/api/intents", {
        type: "initiative", title: what.trim().slice(0, 120),
        start_answers: { goal: { value: { line: what.trim().slice(0, 140), why: saw.trim() }, mark: "stated", by: "", from: "Carried from a Problem you started", at: new Date().toISOString() } },
      });
      const old = await apiGet<{ version: number }>(`/api/intents/${draftId}`);
      await apiSend("POST", `/api/intents/${draftId}/cancel`, { version: old.version, cancel_reason: "Became an Initiative before it was opened" }).catch(() => undefined);
      nav(`/centre/intent/new?type=initiative&draft=${made.id}`);
    } catch (e) { setError(e instanceof ApiError ? e.message : t.failed); setBusy(false); }
  };
  return (
    <div className="ds-card" role="region" aria-label={t.lead} style={{ padding: 12, margin: "0 0 12px" }}>
      <p style={{ margin: "0 0 8px" }}><strong>North.</strong> {t.lead} <span className="n-muted">{t.why}</span></p>
      <Button variant="primary" disabled={busy} onClick={() => void swap()}>{t.switch}</Button> <Button disabled={busy} onClick={() => setKept(text)}>{t.keep}</Button>
      {error && <p role="alert" className="state state-error">{error}</p>}
    </div>
  );
}
