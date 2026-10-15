import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Pill, day, when } from "../../design";
import { useSession } from "../../useSession";
import { CHECKS, listRuns, runCheck, type ReconRun } from "./api";
import { useCycle } from "../router/CycleDate";
import { WhereFrom } from "./TrailHost";

// A1: Reconciliations. Each check, its last run, breaks open. Server decides who may run (E3b: head of data and analyst).
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
// `cause` and `over_by` (plain digits) come from the server on a breached limit line; until it sends `cause`, the run's causes are paired with its
// breached lines in order (the server builds both lists from the same breaches, in the same order).
export type Result = { words: string; breached: boolean; case_id?: string; cause?: string; over_by?: string };
export type Run = ReconRun & { rule_words?: string[]; causes?: { title: string; cause: string }[]; matched?: number;
  results?: Result[]; questions?: { instrument: string; portfolio: string; status: string; value: string; currency: string; exposure_pct: string }[] };
const amount = (v: string) => Number(v).toLocaleString("en-GB", { maximumFractionDigits: Number(v) % 1 ? 2 : 0 });
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }; // local calendar day, not UTC

export default function ReconPage() {
  const { user } = useSession();
  const mayRun = (user?.roles ?? []).some((r) => r === "company_admin" || r === "analyst" || r === "owner");  // the business owner runs the month's check too
  const [runs, setRuns] = useState<ReconRun[] | null>(null);
  const [failed, setFailed] = useState(false);  // the runs could not be read (no access): say only that, never "not run yet"
  const [error, setError] = useState("");
  const [asAt, setAsAt] = useState(today());
  const [cycle] = useCycle();
  useEffect(() => { if (cycle) setAsAt(cycle.today); }, [cycle]);  // FIXE2: the check runs as at the company's cycle date
  const [cutoff, setCutoff] = useState("");  // optional: when the files were received
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { listRuns().then((r) => { setFailed(false); setRuns(r); }).catch((e) => { setFailed(true); setError(plain(e)); }); }, []);
  useEffect(load, [load]);

  async function run(code: string) {
    setError(""); setBusy(code);
    try { await runCheck(code, asAt, cutoff ? new Date(cutoff).toISOString() : ""); load(); } catch (e) { setError(plain(e)); } finally { setBusy(""); }
  }
  return (
    <div className="ds-frame" style={{ paddingTop: 0 }}>
    <section aria-label="Reconciliations" className="ds-frame__main">
      <p className="ds-muted">These checks compare two records of the same money. Every difference beyond the agreed allowance becomes a case.</p>
      {mayRun ? <p style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <label>Check as at <input className="ds-input" type="date" value={asAt} onChange={(e) => setAsAt(e.target.value)} /></label>
        <label>Files received by (optional) <input className="ds-input" type="datetime-local" value={cutoff} onChange={(e) => setCutoff(e.target.value)} /></label></p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {failed ? null : runs === null ? <p className="ds-muted" role="status">Loading the checks.</p> : (
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 12 }}>
          {CHECKS.map((c) => {
            const mine = (runs as Run[]).filter((r) => r.recon_code === c.code);  // newest first
            const last = mine[0];
            const prior = last && !last.checked ? mine.find((r) => r.checked) : undefined;  // a day with no files keeps the last real result in view
            const shown = prior ?? last;
            // each line with a case carries its own trail; a card-level trail only for a run whose lines name no case
            const caseId = shown?.results?.some((x) => x.case_id) ? undefined : shown?.opened[0];
            return (
              <li key={c.code} className="ds-card" style={{ padding: 16 }}>
                <h2 style={{ margin: 0, fontSize: "1rem" }}>{c.title}</h2>
                <p className="ds-muted" style={{ margin: "4px 0" }}>{c.what}</p>
                {last ? <RunView run={last} limits={c.code === "limits"} /> : <p className="ds-muted">This check has not been run yet.</p>}
                {prior ? <><p className="ds-muted">The last run that had figures to compare:</p><RunView run={prior} limits={c.code === "limits"} /></> : null}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {mayRun ? <Button variant="primary" disabled={busy === c.code} onClick={() => void run(c.code)}>Run now</Button> : null}
                  {caseId ? <WhereFrom kind="case" id={caseId} /> : null}
                </div>
              </li>);
          })}
        </ul>)}
    </section>
    </div>
  );
}

function RunView({ run: last, limits }: { run: Run; limits: boolean }) {
  const pill = !last.checked ? <Pill tone="open">Nothing to compare</Pill>
    : <Pill tone={last.breaks ? "late" : "signed"}>{last.breaks ? limits ? `${last.breaks} limits breached` : `${last.breaks} ${last.breaks === 1 ? "difference" : "differences"} to look at` : limits ? "All within limits" : "Everything matches"}</Pill>;
  // UC5-C2-09: a signed limit is a limit; "allowance" is the tolerance on the cash, NAV and trade checks
  const rule = limits ? "Signed limit" : "Allowance";
  const breached = (last.results ?? []).filter((x) => x.breached);
  const paired = limits && !!last.causes?.length && last.causes.length === breached.length;
  // UC5-C2-01: "Outside the limit; real breach, over by 308,000."
  const outside = (x: Result) => {
    const cause = x.cause ?? (paired ? last.causes![breached.indexOf(x)]?.cause : undefined);
    return `Outside the limit${cause ? `; ${cause}` : ""}${x.over_by ? `, over by ${amount(x.over_by)}` : ""}.`;
  };
  return (
    <>
      <p>{pill}{" "}
        Last run {when(last.ran_at)} as at {day(last.as_of_date)}: {last.checked} compared{last.matched != null ? `, ${last.matched} matched` : ""}.</p>
      {last.rule_words?.length ? last.rule_words.map((w) => <p key={w} className="ds-muted">{rule}: {w}</p>)
        : <p className="ds-muted">{rule}: not stated</p>}
      {last.results?.length ? <ul>{last.results.map((x) => <li key={x.words}>{x.words}{x.breached ? limits ? ` ${outside(x)}` : " Over the allowance." : ""}
        {x.case_id ? <> <Link className="ds-link" to={`/centre/action/cases/${encodeURIComponent(x.case_id)}`}>Open the case</Link>{" "}<WhereFrom kind="case" id={x.case_id} /></> : null}</li>)}</ul> : null}
      {last.questions?.length ? <ul>{last.questions.map((q) => <li key={q.instrument + q.portfolio}>{q.instrument} in {q.portfolio}: {q.status}. {amount(q.value)} {q.currency} ({q.exposure_pct}% of the portfolio) is counted in no class and opens no breach.</li>)}</ul> : null}
      {paired ? null : last.causes?.length ? <ul>{last.causes.map((x) => <li key={x.title}>{x.title}: {x.cause}</li>)}</ul> : null}
      {last.skipped.length ? <ul>{last.skipped.map((s) => <li key={s}>Not compared: {s}</li>)}</ul> : null}
    </>
  );
}
