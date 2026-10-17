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

/** Decision 1's gap line: what Confirm will do about the open parts, so a Confirm with gaps never looks like it does nothing. */
export function gapLine(gaps: string[] | undefined, updating: boolean, s: SignOff | null | undefined): string | null {
  if (!gaps?.length) return null;
  const list = gaps.join("; ").replace(/[.?!]$/, "");  // "Which figures do you want?" never ends as "?."
  if (updating) return `Harbor is working on these now: ${list}.`;
  if (!s || s.state === "can_sign" || s.state === "awaiting_you") {
    return `Still open: ${list}. Confirm and Harbor tries the usual practice for these before signing; anything only you can say comes back here as a question. Or tell me in the box below.`;
  }
  return `Still needed before you confirm: ${list}.`;
}

/** Why Confirm is greyed, said next to it (Nitin, 17 Oct: a grey button with no reason looks broken). Null when it is not greyed for these. */
export function confirmWhy(updating: boolean, lost: boolean, noDoc = false): string | null {
  if (updating && lost) return "The page lost touch with Harbor while it was updating the brief. It keeps trying; Confirm opens when the brief is back.";
  if (updating) return "Confirm opens when Harbor has finished updating the brief. This can take a few minutes; you can leave this page.";
  if (noDoc) return "Confirm opens once the brief has its first lines.";
  return null;
}

/** "Change something" / "Something is off": bring the box into view, focus it and say what to type there. */
export function openComposer(box: HTMLTextAreaElement | null, hint = "Say what to change, for example \"use 90 days\""): void {
  if (!box) return;
  box.placeholder = hint;
  box.scrollIntoView?.({ block: "center", behavior: "smooth" });
  box.focus();
}
