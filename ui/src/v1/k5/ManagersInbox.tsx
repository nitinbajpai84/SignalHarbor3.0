import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Pill, type PillTone } from "../../design";
import { WhereFrom } from "../a5/TrailHost";
import { day, draftFollowup, getInbox, money, revisedWords, type Followup, type FundRow, type Inbox, type ManagerRow } from "./api";

// K3: Action > Managers. Statements expected this month per manager and fund. A follow-up is only ever a draft to copy; nothing is sent.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const TONE: Record<FundRow["state"], PillTone> = { received: "signed", received_late: "late", late: "failed", not_due: "draft", not_expected: "draft", no_rule: "draft" };

/** "3 expected · 2 received · 0 late · 1 missing": late is always said when something is expected; an earlier missing statement always shows,
 * and then this month's late count says it is this month's (AUC3-08: "0 late" beside a statement 63 days late read wrong). */
export function countsLine(c: ManagerRow["counts"]): string {
  const late = `${c.late} late${c.missing_earlier ? " this month" : ""}`;
  const parts = c.expected ? [`${c.expected} expected`, `${c.received} received`, late] : ["Nothing expected this month"];
  if (c.missing_earlier) parts.push(`${c.missing_earlier} missing from earlier months`);
  if (c.revised) parts.push(`${c.revised} revised`);
  return parts.join(" · ");
}

export function FundLine({ f, where = false }: { f: FundRow; where?: boolean }) {
  const missing = f.earlier_missing ?? [];
  const late = f.state === "late" || f.state === "received_late";
  const n = f.days_late ?? 0;
  const days = `${n} business day${n === 1 ? "" : "s"} late`;
  const word = late && n ? (f.state === "late" ? days.charAt(0).toUpperCase() + days.slice(1) : `Received ${days}`) : f.state_word;
  return (
    <li style={{ display: "grid", gap: 2, padding: "8px 0", borderTop: "1px solid var(--ds-line, #ddd)" }}>
      <span><strong>{f.fund_name}</strong>{" "}
        {missing.length ? <><Pill tone="failed">{missing.length === 1 ? "Earlier statement missing" : `${missing.length} earlier statements missing`}</Pill>{" "}</> : null}
        <Pill tone={TONE[f.state]}>{word}</Pill>
        {f.revised_count ? <>{" "}<Pill tone="open">{f.revised_count === 1 ? "Revised once" : `Revised ${f.revised_count} times`}</Pill></> : null}</span>
      <span className="ds-muted">
        {f.state === "not_expected" ? `Reports ${f.cadence}; nothing is due for ${day(f.period_end)}.`
          : `Statement for ${day(f.period_end)}${f.due ? `, due ${day(f.due)}` : ""}${f.received_on ? `, received ${day(f.received_on)}` : ""}.`}
        {f.last_value ? ` Last value ${money(f.last_value)} on ${day(f.last_value.valuation_date)} (${f.last_value.status_word ?? f.last_value.status}).` : " No value is recorded yet."}
      </span>
      {(f.statements ?? []).map((s) => s.revision ? <span key={s.id}><strong>Revised:</strong> {s.title}, {revisedWords(s.revision)}.</span> : null)}
      {where && f.last_value?.valuation_id ? <span><WhereFrom kind="valuation" id={f.last_value.valuation_id} /></span> : null}
      {missing.map((e) => (
        <span key={e.period_end}><strong>Still missing:</strong> the statement for {day(e.period_end)}, due {day(e.due)}, {e.days_late} business day{e.days_late === 1 ? "" : "s"} late.</span>))}
    </li>
  );
}

export default function ManagersInbox() {
  const [inbox, setInbox] = useState<(Inbox & { can_draft?: boolean }) | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<{ id: string; d: Followup } | null>(null);
  const [copied, setCopied] = useState(false);
  const [asOf, setAsOf] = useState("");   // AUC3-04: judge a past month (a late statement shows in the month it fell due)
  const load = useCallback(() => { getInbox(asOf || undefined).then(setInbox).catch((e) => { setInbox({ as_of: "", due_rule_signed: true, rule_note: null, managers: [] }); setError(plain(e)); }); }, [asOf]);
  useEffect(load, [load]);

  async function ask(id: string) {
    setError(""); setCopied(false);
    try { setDraft({ id, d: await draftFollowup(id, undefined, asOf || undefined) }); } catch (e) { setError(plain(e)); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setError("Copying did not work here. Select the text and copy it yourself."); }
  }

  return (
    <section aria-label="Managers" className="ds-frame" style={{ paddingTop: 0 }}><div className="ds-frame__main">
      <p className="ds-muted">Which manager statements are expected this month, which have arrived, and which are late. Lateness follows the signed due-date rule.</p>
      <label>Judge as of <input className="ds-input" type="date" value={asOf} onChange={(e) => { setDraft(null); setAsOf(e.target.value); }} /></label>{" "}
      <span className="ds-muted">{inbox?.as_of ? `Judged on ${day(inbox.as_of)}: the statements for the month that ended before it.` : ""}</span>
      {asOf ? <Button onClick={() => { setDraft(null); setAsOf(""); }}>Back to today</Button> : null}
      {inbox?.rule_note ? <p role="status">{inbox.rule_note}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {inbox === null ? <p className="ds-muted" role="status">Loading the managers.</p>
        : !inbox.managers.length && !error ? <p className="ds-muted">No managers are set up yet, or none of their funds are open to you.</p> : (
          <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 12 }}>
            {inbox.managers.map((m) => (
              <li key={m.manager_id} className="ds-card" style={{ padding: 16 }}>
                <h2 style={{ margin: 0, fontSize: "1rem" }}><Link className="ds-link" to={`/centre/consume/managers/${m.manager_id}`}>{m.name}</Link></h2>
                <p className="ds-muted" style={{ margin: "4px 0" }}>
                  {countsLine(m.counts)}
                </p>
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>{m.funds.map((f) => <FundLine key={f.fund_id} f={f} />)}</ul>
                <div style={{ marginTop: 8 }}>
                  {!(m.counts.late + (m.counts.missing_earlier ?? 0)) ? <span className="ds-muted">Nothing is late.</span>
                    : inbox.can_draft === false ? null /* the server refuses this role a draft, so the button is not offered */
                      : <Button onClick={() => void ask(m.manager_id)}>Draft a follow-up</Button>}
                </div>
                {draft?.id === m.manager_id ? (
                  draft.d.draft ? (
                    <div style={{ marginTop: 8 }}>
                      <label>Draft email (not sent)
                        <textarea className="ds-input" readOnly rows={10} style={{ width: "100%" }} value={draft.d.draft} />
                      </label>
                      <Button variant="primary" onClick={() => void copy(draft.d.draft ?? "")}>Copy the draft</Button>
                      {copied ? <span role="status"> Copied.</span> : null}
                      <p className="ds-muted">{draft.d.note}</p>
                    </div>
                  ) : <p role="status">{draft.d.message}</p>
                ) : null}
              </li>))}
          </ul>)}
    </div></section>
  );
}
