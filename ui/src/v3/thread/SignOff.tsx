import type { ReactNode } from "react";

import type { SignOff } from "../api";

/** Decision 1 for someone who may not sign: the act-coloured send button; for the signer or the sender, the state in the needs colour. */
export function signAction(s: SignOff | null | undefined, label: string, busy: boolean, confirm: () => void, send: () => void): ReactNode {
  if ((s?.state === "send" || s?.state === "fill") && s.signer) {  // "fill": the signer could not sign it yet; the note names what is missing
    return <button className="go" disabled={busy || s.state === "fill"} onClick={send}>Send to {s.signer.name} to confirm</button>;
  }
  if (s?.state === "waiting" || s?.state === "none") return null;
  return <button className="go" disabled={busy} onClick={confirm}>{label}</button>;
}

export function SignNote({ s }: { s?: SignOff | null }) {
  if (!s) return null;
  if (s.state === "waiting") {
    return <p className="v3-gap" role="status">Waiting for {s.signer?.name} to confirm{s.sent_at ? `. Sent ${new Date(s.sent_at).toLocaleString()}` : ""}. It is on their Action list.</p>;
  }
  if (s.state === "awaiting_you") return <p className="v3-mute" role="status">{s.sent_by ?? s.raised_by} sent this to you to confirm. Your Confirm signs it in your name.</p>;
  if (s.state === "send") return <p className="v3-mute" role="status">Only {s.signers.map((p) => p.name).join(" or ")} can sign. Send it and they get a card with this brief.</p>;
  if (s.state === "none" || s.state === "fill") return <p className="v3-gap" role="status">{s.message}</p>;
  return null;
}
