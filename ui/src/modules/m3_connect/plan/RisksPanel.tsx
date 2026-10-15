import { useId, useState } from "react";

import Panel from "../../../components/Panel";
import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { acceptedSummary, splitAccepted } from "../plainText";
import { planCopy as T } from "./copy";
import type { RiskRow, RisksView, RiskState } from "./planApi";

const TONE: Record<RiskState, PillTone> = { open: "warning", accepted: "success", sent_back: "info", rechecked: "success" };
const day = (iso: string | null) => (iso && !Number.isNaN(new Date(iso).getTime()) ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");

interface Props {
  view: RisksView;
  disabled: boolean;
  onDecide: (id: string, body: { decision: "accepted" | "sent_back"; note?: string; reason?: string }) => void;
  onAcceptAll: () => void;
}

/** The risks Lens listed, each to accept (a note is optional) or send back (a reason is needed). One action accepts the rest. */
export default function RisksPanel({ view, disabled, onDecide, onAcceptAll }: Props) {
  const { open, sent_back: back } = view.counts;
  return (
    <Panel
      title={T.risks.title}
      actions={
        <>
          <StatusPill tone={open === 0 && back === 0 ? "success" : "warning"}>{T.risks.summary(open, back)}</StatusPill>
          {open > 0 && !disabled ? (
            <button type="button" className="n-btn" onClick={onAcceptAll}>
              {T.risks.acceptAll}
            </button>
          ) : null}
        </>
      }
    >
      <p className="n-muted">{T.risks.sub}</p>
      {acceptedSummary(view.risks.map((r) => r.text)).map((l) => (
        <p key={l} className="n-muted">{l}</p>
      ))}
      {view.risks.length === 0 ? <p className="state n-muted">{T.risks.none}</p> : null}
      <ul className="m1-list" style={{ display: "grid", gap: 12 }}>
        {view.risks.map((r) => (
          <Risk key={r.id} r={r} disabled={disabled} onDecide={onDecide} />
        ))}
      </ul>
    </Panel>
  );
}

function Risk({ r, disabled, onDecide }: { r: RiskRow; disabled: boolean; onDecide: Props["onDecide"] }) {
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState("");
  const field = useId();
  const d = r.decision;
  const send = (decision: "accepted" | "sent_back") => {
    if (decision === "sent_back" && !note.trim()) {
      setProblem(T.risks.needReason);
      return;
    }
    setProblem("");
    onDecide(r.id, decision === "sent_back" ? { decision, reason: note.trim() } : { decision, note: note.trim() || undefined });
    setNote("");
  };
  return (
    <li style={{ display: "grid", gap: 6 }}>
      <div className="n-flex between wrap" style={{ gap: 8 }}>
        <span>
          <StatusPill tone="muted">{T.risks.kind[r.kind]}</StatusPill> <strong>{r.restricted ? T.risks.restricted : splitAccepted(r.text).text}</strong>
        </span>
        <StatusPill tone={TONE[r.state]}>{T.risks.state[r.state]}</StatusPill>
      </div>
      {r.measures.length ? (
        <div className="n-e1-def-note">
          {T.risks.aboutMeasures}: {r.measures.map((m) => m.name).join(", ")}
        </div>
      ) : null}
      {d?.by ? (
        <div className="n-e1-def-note">
          {T.risks.by(d.by, day(d.at))}
          {d.reason || d.note ? `: ${d.reason ?? d.note}` : ""}
        </div>
      ) : null}
      {!r.restricted && !disabled ? (
        <div style={{ display: "grid", gap: 6 }}>
          <label htmlFor={field} className="n-e1-def-note">
            {T.risks.note} ({T.risks.noteHelp})
          </label>
          <input id={field} className="n-input" value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} aria-label={`${T.risks.note}: ${splitAccepted(r.text).text}`} />
          <div className="n-flex" style={{ gap: 8 }}>
            {r.state !== "accepted" ? (
              <button type="button" className="n-btn primary sm" onClick={() => send("accepted")}>
                {T.risks.accept}
              </button>
            ) : null}
            {r.state !== "sent_back" ? (
              <button type="button" className="n-btn sm" onClick={() => send("sent_back")}>
                {T.risks.sendBack}
              </button>
            ) : null}
          </div>
          {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
        </div>
      ) : null}
    </li>
  );
}
