import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { apiSend } from "../../api/client";
import { Button, PageFrame, Pill, SideCard } from "../../design";
import { BuildState, day, useLoad } from "../BuildCentre";
import { StepStrip } from "./ChainPanel";
import "./chain.css";
import { backWord, EMPTY, SECTIONS, STEP_NAMES, TITLES, type Change, type Line, type SectionKey } from "./chain";

/** Span's note on a source's latest run (gate 3), sent from the step-4 view on. */
type RunNote = { source: string; run_id: string | null; note: { text?: string | null; sentence?: string | null; lines?: string[] } | null };

function RunNotes({ notes }: { notes: RunNote[] }) {
  return (
    <>
      <h4 style={{ margin: "var(--ds-s2) 0 var(--ds-s1)", fontSize: 14 }}>What Span saw in the runs</h4>
      <ul className="bc-lines">
        {notes.map((r) => {
          const n = r.note;
          const lines = n?.lines ?? [];
          const aside = lines.filter((l) => l.includes("set aside"));
          return (
            <li key={r.source}>
              {n ? <>{n.text || lines[0] || n.sentence}{aside.map((l, i) => <span key={i} className="ds-muted"> {l}</span>)}</> : `No run yet for ${r.source.replace(/_/g, " ")}`}
            </li>
          );
        })}
      </ul>
    </>
  );
}

const MARK = { guessed: "Guessed", stated: "Stated", unknown: "Unknown" } as const;

function Lines({ k, lines }: { k: SectionKey; lines: Line[] }) {
  if (!lines.length) return <p className="bc-note">{EMPTY[k]}</p>;
  const groups = [...new Set(lines.map((l) => l.group ?? ""))];
  return (
    <>
      {groups.map((g) => (
        <div key={g}>
          {g ? <h4 style={{ margin: "var(--ds-s1) 0", fontSize: 14 }}>{g}</h4> : null}
          <ul className="bc-lines">
            {lines.filter((l) => (l.group ?? "") === g).map((l, i) => (
              <li key={i}>
                {l.href ? <Link to={l.href}>{l.text}</Link> : l.text}
                {l.done === true ? " (Done)" : l.done === false ? " (Not done)" : ""}
                {l.mark ? <span className="ds-muted"> · {MARK[l.mark]}{l.from ? ` from ${l.from}` : ""}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  );
}

/** A button that needs a typed reason before it posts. */
function WithReason({ label, ask, onSend }: { label: string; ask: string; onSend: (reason: string) => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  if (!open) return <Button onClick={() => setOpen(true)}>{label}</Button>;
  return (
    <label className="bc-field">{ask}
      <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={3} />
      <span className="bc-actions">
        <Button variant="primary" disabled={!text.trim()} onClick={() => onSend(text.trim())}>{label}</Button>
        <Button onClick={() => setOpen(false)}>Cancel</Button>
      </span>
    </label>
  );
}

function Action({ c, step, post }: { c: Change; step: number; post: (verb: string, body?: object) => void }) {
  const now = step === c.step;
  const off = !c.can_act || !now || !!c.gate;
  const why = !now ? "This is not the current step." : !c.can_act ? "Only the named person may act at this step. Name them in the charter: Who does what." : c.gate ?? "";
  const Why = () => (off && why ? <p className="bc-note" role="note">{why}</p> : null);
  const mine = c.can_act && now;
  if (step === 1) return (
    <>
      <p>{c.drafted_from ?? "The Architect, who designs the data, drafted this change from the signed blueprint and the signed gap report."}</p>
      <div className="bc-actions">
        <Button variant="primary" disabled={off} onClick={() => post("send")}>Send for approval</Button>
        {mine ? <WithReason label="Ask Span to redraft" ask="What should change?" onSend={(note) => post("redraft", { note })} /> : null}
      </div>
      <Why />
    </>
  );
  if (step === 2) return (
    <>
      <p>{c.completeness?.line ?? "North checks the note is complete."}</p>
      <div className="bc-actions">
        <Button variant="primary" disabled={off || !!c.completeness?.gap} onClick={() => post("approve")}>Approve the design</Button>
        {mine ? <WithReason label="Send back" ask="Why is it sent back?" onSend={(reason) => post("send-back", { to: 1, reason })} /> : null}
      </div>
      {c.completeness?.gap ? <p className="bc-note" role="note">{c.completeness.gap}</p> : <Why />}
    </>
  );
  if (step === 3) return (
    <>
      <p>{c.build_progress ? `${c.build_progress.done} of ${c.build_progress.of} build steps done, read from the run log.` : "No build steps."}</p>
      <div className="bc-actions">
        <Button variant="primary" disabled={off} onClick={() => post("built")}>Built, ready to test</Button>
        {mine ? <WithReason label="Send back to the Architect" ask="Why does the design need to change?" onSend={(reason) => post("send-back", { to: 1, reason })} /> : null}
      </div>
      <Why />
    </>
  );
  if (step === 4) return (
    <>
      <p>The tester checks each measure against the catalogue and the hypothesis, then signs or sends back with a note.</p>
      <div className="bc-actions"><Link className="ds-btn ds-btn--primary" to="/centre/build/prove">Sign UAT or send back on the Prove page</Link></div>
      <p className="bc-note">{c.release ? `Release signed by ${c.release.by} on ${day(c.release.at)}.` : "Waiting for the sponsor to sign the release."}</p>
    </>
  );
  return (
    <>
      <p>Read the run book additions, who is told and the first run of the operations monitor.</p>
      <div className="bc-actions">
        <Button variant="primary" disabled={off} onClick={() => post("take-over")}>I run this from today</Button>
        {mine ? <WithReason label="Not ready to take over" ask="What is missing?" onSend={(reason) => post("send-back", { to: 5, reason })} /> : null}
      </div>
      {c.release || !now ? <Why /> : <p className="bc-note">Waiting for the release.</p>}
    </>
  );
}

/** Screen C: one change note and its chain. */
export default function ChangeNotePage() {
  const { id = "" } = useParams();
  const [q] = useSearchParams();
  const { data: c, state, retry } = useLoad<Change>(`/api/company/build/changes/${encodeURIComponent(id)}`);
  const [err, setErr] = useState("");
  const step = Math.min(5, Math.max(1, Number(q.get("step")) || c?.step || 1));
  const post = (verb: string, body: object = {}) => {
    setErr("");
    apiSend("POST", `/api/company/build/changes/${encodeURIComponent(id)}/${verb}`, body).then(retry).catch((e: unknown) => setErr(e instanceof Error ? e.message : "That did not save. Try again."));
  };
  const cur = c?.steps.find((s) => s.n === c.step);
  return (
    <PageFrame
      crumbs={<Link to="/centre/build">Build centre</Link>}
      title={c ? `${c.id} · ${c.title}` : "Change note"}
      subline={c && cur ? `With ${cur.person ?? "nobody yet"}, ${cur.name.toLowerCase()}` : undefined}
      actions={c ? <><Pill tone={c.state === "live" ? "signed" : c.state === "stopped" ? "failed" : "open"}>{c.state.replace(/_/g, " ")}</Pill><Link to={`/centre/intent/${encodeURIComponent(c.intent_id)}`}>Open the Initiative</Link></> : undefined}
    >
      <BuildState state={state} onRetry={retry}>
        {c ? (
          <>
            <StepStrip c={c} current={step} />
            <div className="bc-cols" style={{ marginTop: "var(--ds-s3)" }}>
              <div>
                {SECTIONS.map((k) => (
                  <details key={k} className="ds-card bc-sec" open={k === "why" || k === "what_changes" || undefined}>
                    <summary>{TITLES[k]}</summary>
                    {k === "why" && c.handed ? <p className="bc-note">Handed to Build by {c.handed.by} on {day(c.handed.at)}</p> : null}
                    <Lines k={k} lines={c.sections[k] ?? []} />
                    {k === "build_steps" && (c as Change & { run_notes?: RunNote[] }).run_notes ? <RunNotes notes={(c as Change & { run_notes?: RunNote[] }).run_notes ?? []} /> : null}
                    {k === "what_changes" ? <Link to="/centre/build/architecture?focus=change">See the diagrams</Link> : null}
                  </details>
                ))}
              </div>
              <div>
                <section className="ds-card bc-row bc-sticky" aria-label={`Step ${step}: ${STEP_NAMES[step - 1]}`}>
                  <h2 style={{ margin: 0, fontSize: 16 }}>{step}. {STEP_NAMES[step - 1]}</h2>
                  <Action c={c} step={step} post={post} />
                  {err ? <p role="alert" className="ds-warn">{err}</p> : null}
                </section>
                <SideCard title="Signatures">
                  {c.signatures.length ? <ul className="bc-lines">{c.signatures.map((s, i) => <li key={i}>{STEP_NAMES[s.step - 1]}: {s.name}, {s.role}, {day(s.at)}</li>)}</ul> : <p className="bc-note">Nobody has signed yet.</p>}
                </SideCard>
                {c.returns.length ? <SideCard title="Sent back"><ul className="bc-lines">{c.returns.map((b, i) => <li key={i}>{backWord(b)}, {day(b.at)}</li>)}</ul></SideCard> : null}
                {c.can_stop && c.state !== "live" && c.state !== "stopped" ? (
                  <div style={{ marginTop: "var(--ds-s3)" }}><WithReason label="Stop this change" ask="Why stop it?" onSend={(reason) => post("stop", { reason })} /></div>
                ) : null}
              </div>
            </div>
          </>
        ) : null}
      </BuildState>
    </PageFrame>
  );
}
