import type { ReactNode } from "react";

import Panel from "../../components/Panel";
import StatusPill from "../../components/StatusPill";
import type { CharterDoc, CharterProblem, CharterStatus } from "./api";
import { m1, m1Charter, m1Look } from "./copy";

interface PreviewProps {
  purpose: string;
  outcome: string;
  templateName: string;
  approver: string;
}
/** M1-P09: the real charter. `children` is the signature block; `edit` turns each "So that" line into a field. */
interface DocumentProps {
  doc: CharterDoc;
  status: CharterStatus;
  edit?: { values: Record<string, string>; onChange: (id: string, text: string) => void; onPriority?: (id: string, priority: string) => void; onConfirm?: (id: string) => void };
  children?: ReactNode;
}
type Props = PreviewProps | DocumentProps;

/** "3 October 2026" from the day the server recorded, the same wherever the reader is. */
export function formatDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

/** A purpose line as the full sentence "So that ...": North writes it that way; an older line without the words gets them. */
export function soThatSentence(line: string): string {
  const body = line.trim().replace(/[.!?]$/, "");
  return /^so that\b/i.test(body) ? `${body}.` : `${m1Charter.soThat} ${body}.`;
}

function Document({ doc, status, edit, children }: DocumentProps) {
  const T = m1Charter;
  const cols = doc.template.columns;
  const f = doc.footer;
  // four lists, each with its heading: problems to solve now, pain points, what to track for the future, levers for what-if.
  // A charter with no lists (drafted before kinds existed) is one list of problems.
  const sections = doc.lists?.length
    ? doc.lists.map((l) => ({ kind: l.kind, heading: l.heading, items: doc.problems.filter((p) => (p.kind ?? "intent") === l.kind) }))
    : [{ kind: "intent", heading: null, items: doc.problems }];
  return (
    <Panel
      eyebrow={`${T.crumb} · ${T.statusLabel[status]} · ${T.templateLabel(doc.template.name)}`}
      title={T.title}
      className="m1-charter"
      actions={<StatusPill tone={status === "signed" ? "success" : status === "returned" ? "warning" : "muted"}>{T.statusLabel[status]}</StatusPill>}
    >
      <p className="n-e1-def-note">{T.sub}</p>
      {doc.problems.length === 0 ? <p className="state n-muted">{T.nothingTicked}</p> : null}
      {doc.problems.length > 0 ? sections.map((sec) => (
      <div key={sec.kind}>
        {sec.heading ? <h3>{sec.heading}</h3> : null}
        {sec.heading && sec.items.length === 0 ? <p className="n-e1-def-note">{T.noneRaised}</p> : null}
        {sec.items.map((p, i) => {
          const id = (p as Partial<CharterProblem>).id;
          const proposal = (p as Partial<CharterProblem>).so_that_proposal;
          const tie = (p as Partial<CharterProblem>).tie;
          const tied = (p as Partial<CharterProblem>).tied_options ?? [];
          const note = status === "signed" ? null : (p as Partial<CharterProblem>).so_that_note; // "Draft from North..." or "Ask the room..."
          return (
            <div key={id ?? i} className="n-e1-def-row" style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div className="n-e1-def-name">{p.title}</div>
                {cols.includes("purpose") ? (
                  edit && id ? (
                    <label className="n-e1-def-note">
                      {T.soThatField}
                      <input type="text" aria-label={T.soThatLabel(p.title)} style={{ display: "block", width: "100%", marginTop: 4 }} value={edit.values[id] ?? ""} placeholder={T.soThatNone} onChange={(e) => edit.onChange(id, e.target.value)} />
                    </label>
                  ) : (
                    <div className="n-e1-def-note">{p.so_that ? soThatSentence(p.so_that) : T.soThatNone}{cols.includes("notes") ? ` ${T.raised(p.note_count)}` : ""}</div>
                  )
                ) : cols.includes("notes") ? (
                  <div className="n-e1-def-note">{T.raised(p.note_count)}</div>
                ) : null}
                {edit && id && cols.includes("notes") ? <div className="n-e1-def-note">{T.raised(p.note_count)}</div> : null}
                {(p.details ?? []).map((d) => (
                  <div key={d.label} className="n-e1-def-note">
                    {d.label}: {d.values.join(", ")}
                  </div>
                ))}
                {note ? <div className="n-e1-def-note">{note}</div> : null}
                {edit?.onConfirm && id && (p as Partial<CharterProblem>).so_that_draft ? (
                  <button type="button" className="n-btn" aria-label={T.useThisLineLabel(p.title)} onClick={() => edit.onConfirm?.(id)}>
                    {T.useThisLine}
                  </button>
                ) : null}
                {tie ? <div className="n-e1-def-note">{tie}</div> : null}
                {edit?.onPriority && id && tie && tied.length > 0 ? (
                  <label className="n-e1-def-note">
                    <select aria-label={T.chooseTied(p.title)} defaultValue="" onChange={(e) => e.target.value && edit.onPriority?.(id, e.target.value)}>
                      <option value="">{T.chooseTiedNone}</option>
                      {tied.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {proposal ?<div className="n-e1-def-note">{T.soThatProposal(proposal)}</div> : null}
              </div>
              {cols.includes("priority") ? (
                <div style={{ flexShrink: 0 }}>
                  <StatusPill tone={p.priority_label ? "info" : "muted"}>{p.priority_label ?? ((p as Partial<CharterProblem>).tie ? T.tiedPill : T.noPriority)}</StatusPill>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      )) : null}
      {doc.later.length > 0 ? (
        <>
          <h3>{T.laterTitle}</h3>
          <ul className="n-e1-def-note">
            {doc.later.map((l, i) => (
              <li key={i}>{l.title}</li>
            ))}
          </ul>
        </>
      ) : null}
      {doc.alone && doc.alone.length > 0 ? (
        <>
          <h3>{T.leftForLater(doc.alone.length)}</h3>
          <ul className="n-e1-def-note">
            {doc.alone.map((n, i) => (
              <li key={i}>
                {n.text ?? T.leftAnonymous}
                {n.author_name ? ` (${T.by(n.author_name)})` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="n-e1-def-note">{T.footer(formatDay(f.date), f.participants, f.notes, f.later)}</p>
      {children}
    </Panel>
  );
}

/**
 * The charter as a document, laid out the way the earlier Intent Charter screen does (screens/intent-charter.js, charter-doc.js):
 * two columns of definition rows and a signature block with the approver and "not signed yet". Layout only: the problem and the
 * wording are agreed in the session, and a named person signs; nothing here is signed or invented.
 */
export default function CharterPaper(props: Props) {
  if ("doc" in props) {
    return <Document {...props} />;
  }
  const { purpose, outcome, templateName, approver } = props;
  const C = m1Look.charter;
  const none = m1.wizard.noValue;
  const rows: [string, string][] = [
    [C.problem, C.toBeAgreed],
    [C.purpose, purpose.trim() || none],
    [C.outcome, outcome.trim() || none],
    [C.template, templateName || none],
  ];
  return (
    <Panel eyebrow={C.eyebrow} title={C.title} className="m1-charter">
      <p className="n-e1-def-note">{C.note}</p>
      <div className="n-e1-charter-grid">
        <div>
          {rows.map(([label, value]) => (
            <div key={label} className="n-e1-def-row">
              <div>
                <div className="n-e1-def-name">{label}</div>
                <div className="n-e1-def-note">{value}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="n-e1-signature">
          <div>
            <div className="sig-meta">{C.approverLabel}</div>
            <div className="sig-actor">{approver.trim() || C.noApprover}</div>
          </div>
          <StatusPill tone="muted">{C.unsigned}</StatusPill>
        </div>
      </div>
    </Panel>
  );
}
