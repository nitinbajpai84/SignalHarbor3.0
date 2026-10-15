import { Button, Pill } from "../../design";
import type { Studio } from "./api";

// H10: the banner over a starter dashboard Lumen proposed when the pipeline went live. Three ways on: accept as it is, add something specific
// (Lumen's conversation, the same one as ever), or send for approval (accepts first; the existing approval does the rest).
export default function StarterBanner({ board, busy, onAccept, onAsk, onSend }: { board: Studio; busy: boolean; onAccept: () => void; onAsk: () => void; onSend: () => void }) {
  const st = board.starter;
  if (!st || !board.can.edit) return null;
  const waiting = st.status === "proposed";
  return (
    <section aria-label="Lumen's starter dashboard" className="ds-card b7-panel" style={{ padding: 12, margin: "8px 0" }}>
      <h3 style={{ marginTop: 0 }}>Lumen&apos;s starter dashboard <Pill tone={waiting ? "draft" : "signed"}>{waiting ? "Proposed by Lumen" : "Accepted"}</Pill></h3>
      <p style={{ margin: "4px 0" }}>
        {waiting ? "The pipeline is live. I put this together from the signed intent so nothing has to be built from scratch. Open any tile to see where it reads."
          : "You accepted the starter. Change anything, or send it for approval."}
        {st.pack_version ? ` It reads gold, pack version ${st.pack_version}.` : ""}
      </p>
      <ul aria-label="Why Lumen chose these" style={{ margin: "4px 0", paddingLeft: 18 }}>{st.why.map((w) => <li key={w}>{w}</li>)}</ul>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {waiting ? <Button variant="primary" disabled={busy} onClick={onAccept}>Accept as it is</Button> : null}
        <Button disabled={busy} onClick={onAsk}>Add something specific</Button>
        <Button variant={waiting ? undefined : "primary"} disabled={busy || !board.can.submit} onClick={onSend}>Send for approval</Button>
      </div>
    </section>
  );
}
