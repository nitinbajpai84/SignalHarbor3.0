import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button, CheckIcon, DocumentIcon, Pill, WarningIcon, when } from "../../design";
import { acceptNumbers, fixAndRun, flagIssue, getVerify, markVerified, sendForReview, type Comparison, type VerifyView } from "./api";
import { ask, num, pct, pts } from "./format";
import "./verify.css";

// V5W-3, designs C4 to C7. The Pipelines step shows this under the trial run: verify, send for review, the owner's review, the fix, accept.

export default function VerifyPanel({ pid }: { pid: string }) {
  const [v, setV] = useState<VerifyView | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [form, setForm] = useState<{ portfolio?: string; code?: string; month?: string }>({});
  const [msg, setMsg] = useState<string | undefined>(undefined);

  const load = useCallback(() => getVerify(pid).then((x) => { setV(x); setErr(""); }).catch((e) => setErr(ask(e))), [pid]);
  useEffect(() => { void load(); }, [load]);
  // C5: the form opens with the portfolio, the benchmark code, the month and a drafted message already filled in; a field the engineer has not touched shows the suggestion.
  const sg = v?.suggest;
  const field = (k: "portfolio" | "code" | "month") => form[k] ?? sg?.[k] ?? "";
  const message = msg ?? sg?.message ?? "";
  const act = async (f: () => Promise<VerifyView>) => { setBusy(true); try { setV(await f()); setErr(""); } catch (e) { setErr(ask(e)); } finally { setBusy(false); } };

  if (!v) return <p className={err ? "b9v-err" : "ds-muted"} role={err ? "alert" : "status"}>{err || "Loading the verification."}</p>;
  const rv = v.review, c = v.comparison;
  return (
    <section className="b9v" aria-label="Verify and business review">
      {err ? <p role="alert" className="b9v-err"><WarningIcon size={16} /> {err}</p> : null}

      <h2>Control totals: source files against the trial run</h2>
      <p className="ds-muted">Each figure is traced to the file it came from.</p>
      {v.figures.length === 0 ? <p>Nothing has been loaded or run yet, so there is nothing to compare.</p> : (
        <div className="ds-table-wrap"><table className="ds-table"><thead><tr><th>Figure</th><th>Source file</th><th>Trial run</th><th>Traced to</th><th>Check</th></tr></thead>
          <tbody>{v.figures.map((f) => (
            <tr key={f.figure + f.traced_to} data-check={f.check}>
              <td>{f.figure}</td><td>{num(f.source)}</td><td>{num(f.run)}</td><td>{f.traced_to}</td>
              <td><Pill tone={f.check === "Match" ? "ok" : f.check === "Differs" ? "failed" : "draft"}>{f.check}</Pill></td></tr>))}</tbody></table></div>)}
      <div className="b9v-note"><h3>What verification covers</h3>
        <p>{v.matched} of {v.total} figures match their source and each one is traced. It does not confirm the business definitions, such as the benchmark mix. That is the business owner&apos;s review{v.owner ? ` (${v.owner})` : ""}.</p></div>

      {v.verified && !v.stale ? <p className="b9v-ok"><CheckIcon size={16} /> {v.verified.by}, data engineer, verified on {when(v.verified.at)}.</p>
        : <Button variant="primary" disabled={!v.can.verify || busy} onClick={() => act(() => markVerified(pid))}>Mark this run as verified</Button>}

      {v.verified && !rv && v.can.send ? (
        <form className="b9v-card" onSubmit={(e) => { e.preventDefault(); void act(() => sendForReview(pid, { portfolio: field("portfolio"), code: field("code"), month: field("month"), message })); }}>
          <h2>Send for business review</h2>
          <p className="ds-muted">To {v.owner ?? "the business owner"}. They get it in Build. The project waits for their reply.</p>
          {(["portfolio", "code", "month"] as const).map((k) => (
            <label key={k}>{{ portfolio: "Portfolio", code: "Benchmark code", month: "Month (like 2026-09)" }[k]}
              <input required value={field(k)} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></label>))}
          <label>Message<textarea rows={4} value={message} onChange={(e) => setMsg(e.target.value)} placeholder="Optional. A short note goes with the outcome." /></label>
          <div className="b9v-note"><strong>Attached to the message</strong>
            <p>Trial run outcome{field("month") ? `, ${field("month")}` : ""}. Verification: {v.matched} of {v.total} figures match.</p>
            <p className="ds-muted">{v.owner ?? "The owner"} gets this in Build and by email. The project waits for them until they reply.</p></div>
          <Button variant="primary" type="submit" disabled={busy}>Send to {v.owner ?? "the owner"}</Button>
        </form>) : null}

      {rv ? (
        <div className="b9v-card">
          <h2>Business review against the benchmark</h2>
          <p className="ds-muted">Requested from {rv.owner} by {rv.requested_by} on {when(rv.requested_at)}. {rv.state === "requested" ? "Waiting for the review." : null}</p>
          {v.comparison_error ? <p>{v.comparison_error}</p> : null}
          {c ? <Compare c={c} /> : null}
          {c?.lumen_note ? <p className="b9v-note"><strong>Lumen, Consume agent.</strong> Compared the run with the signed benchmark. {c.lumen_note}</p> : null}
          {c ? <p><Link className="ds-link" to={`/centre/consume/benchmark?portfolio=${encodeURIComponent(rv.portfolio)}&code=${encodeURIComponent(rv.code)}&start=${rv.month}&end=${rv.month}`}>Open the signed benchmark definition</Link></p> : null}
          {rv.state === "flagged" ? <ul className="b9v-issues">{rv.issues.map((i) => <li key={i.at}><strong>{i.by}</strong> flagged: {i.text}</li>)}</ul> : null}
          {rv.first && rv.fix && c ? <Before first={rv.first} after={c} /> : null}
          {rv.state === "accepted" ? <p className="b9v-ok"><CheckIcon size={16} /> {rv.accepted_by}, business owner, accepted the numbers on {when(rv.accepted_at)}.</p> : null}
          {v.can.flag || v.can.accept ? (
            <>
              <label>Add to your comment<textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} /></label>
              <div className="b9v-actions">
                <Button variant="primary" disabled={busy || !v.can.accept || (c != null && !c.same)} onClick={() => act(() => acceptNumbers(pid))}>Accept the numbers</Button>
                <Button disabled={busy || !text.trim()} onClick={() => act(async () => { const r = await flagIssue(pid, text); setText(""); return r; })}>Send back with this issue</Button>
              </div></>) : null}
          {v.can.fix ? <Button variant="primary" disabled={busy} onClick={() => act(() => fixAndRun(pid))}>Fix the benchmark mix and run again</Button> : null}
          {rv.fix ? <p className="ds-muted"><DocumentIcon size={14} /> The signed mix is proposed as a rule version for signing; the copy was run again ({rv.fix.run_status}).</p> : null}
        </div>) : null}
    </section>
  );
}

export function Compare({ c }: { c: Comparison }) {
  return (
    <>
      <div className="b9v-tiles">
        <div><span>Portfolio</span><strong>{pct(c.portfolio_pct)}</strong></div>
        <div data-differs={c.benchmark_run_pct !== c.benchmark_signed_pct}><span>Benchmark in the run</span><strong>{pct(c.benchmark_run_pct)}</strong>
          <small>signed definition gives {pct(c.benchmark_signed_pct)}</small></div>
        <div><span>Difference</span><strong>{pts(c.difference_run_pts)}</strong><small>signed definition gives {pts(c.difference_signed_pts)}</small></div>
      </div>
      <p className="ds-muted">{c.benchmark_name ?? "Benchmark"}, version {c.signed_version ?? "Not available yet"}, {c.month}. Mix signed against used in the run.</p>
      <div className="ds-table-wrap"><table className="ds-table"><thead><tr><th>Component</th><th>Month return</th><th>Signed weight</th><th>Used in run</th><th>Gap</th></tr></thead>
        <tbody>{c.rows.map((r) => (
          <tr key={r.component} data-differs={r.differs}><td>{r.label ?? r.component}</td><td>{pct(r.return_pct, 4)}</td><td>{pct(r.signed_weight_pct, 0)}</td><td>{pct(r.used_weight_pct, 0)}</td>
            <td>{r.differs ? <strong>{pts(r.gap_pts)}</strong> : "same"}</td></tr>))}</tbody></table></div>
    </>
  );
}

function Before({ first, after }: { first: Comparison; after: Comparison }) {
  return (
    <table className="ds-table" aria-label="First run and after the fix"><thead><tr><th /><th>First run</th><th>After the fix</th></tr></thead>
      <tbody>{first.rows.map((r) => (
        <tr key={r.component}><td>{r.label ?? r.component} weight</td><td>{pct(r.used_weight_pct, 0)}</td><td>{pct(after.rows.find((x) => x.component === r.component)?.used_weight_pct ?? null, 0)}</td></tr>))}
        <tr><td>Office benchmark</td><td>{pct(first.benchmark_run_pct, 4)}</td><td>{pct(after.benchmark_run_pct, 4)}</td></tr>
        <tr><td>Difference</td><td>{pts(first.difference_run_pts)}</td><td>{pts(after.difference_run_pts)}</td></tr></tbody></table>
  );
}
