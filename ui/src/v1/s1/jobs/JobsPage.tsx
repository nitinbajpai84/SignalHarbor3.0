import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../../api/client";
import { PageFrame, Pill } from "../../../design";
import { useLive } from "../../../live/useLive";
import { getJobs, NAMES, retryJob, STATE_WORDS, type Ev, type Job, type JobsView } from "./api";

// W3: Settings, Jobs and events. What the server does in the background, and what failed. In production mode a worker does the
// work; in simple mode the server does it itself. The list refreshes when the event stream says something moved.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const when = (at: string | null) => (at ? new Date(at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "");
const tone = (s: Job["state"]) => (s === "failed" ? "failed" : s === "done" ? "signed" : s === "retrying" ? "late" : "open");
const label = (n: string) => NAMES[n] ?? n;
const saying = (e: Ev) => {
  const p = e.payload as { name?: string; state?: keyof typeof STATE_WORDS };
  return e.topic.startsWith("job.") ? `${label(p.name ?? "job")}: ${STATE_WORDS[p.state ?? "queued"] ?? e.topic}` : e.topic === "badge.action" ? "Something new in Action" : e.topic;
};

export default function JobsPage() {
  const [data, setData] = useState<JobsView | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { getJobs().then((r) => { setData(r); setError(""); }).catch((e) => setError(plain(e))); }, []);
  const live = useLive<Ev>("/api/v1/events/stream", null, (raw) => (raw && typeof raw === "object" && "topic" in raw ? (raw as Ev) : null));
  useEffect(() => { load(); }, [load, live.view?.id]);
  const again = (id: string) => retryJob(id).then(load).catch((e) => setError(plain(e)));

  return (
    <PageFrame title="Jobs and events" subline="What the server does in the background: pipeline runs, deliveries, graph rebuilds.">
      {error ? <p role="alert">{error}</p> : null}
      {data === null && !error ? <p className="ds-muted" role="status">Loading the jobs.</p> : null}
      {data ? (
        <>
          <p>
            <Pill tone="open">{data.mode === "production" ? "Production mode: a worker runs the jobs" : "Simple mode: this server runs the jobs"}</Pill>{" "}
            <span className="ds-muted">{data.stats.running} running, {data.stats.queued + data.stats.retrying} waiting, {data.stats.failed} failed, {data.stats.done} done</span>
          </p>
          <h2>Failed</h2>
          {data.failed.length === 0 ? <p className="ds-muted">Nothing has failed.</p> : (
            <table className="ds-table" style={{ width: "100%" }}>
              <thead><tr><th>Job</th><th>When</th><th>Tries</th><th>Why</th><th /></tr></thead>
              <tbody>{data.failed.map((j) => (
                <tr key={j.id}>
                  <td>{label(j.name)}</td><td>{when(j.finished_at)}</td><td>{j.tries}</td><td>{j.error}</td>
                  <td><button className="ds-btn" onClick={() => void again(j.id)}>Send again</button></td>
                </tr>))}</tbody>
            </table>)}
          <h2>Recent pipeline runs</h2>
          {(data.runs ?? []).length === 0 ? <p className="ds-muted">No pipeline has run yet.</p> : (
            <table className="ds-table" style={{ width: "100%" }}>
              <thead><tr><th>Project</th><th>Run</th><th>State</th><th>Started</th></tr></thead>
              <tbody>{(data.runs ?? []).map((r) => (
                <tr key={`${r.project_id}-${r.run_id}`}><td>{r.title ?? "A project"}</td><td>{r.mode === "live" ? "Live run" : "Trial run on a copy"}</td>
                  <td><Pill tone={r.status === "ok" ? "signed" : r.status === "failed" ? "failed" : "open"}>{r.status === "ok" ? "Done" : r.status === "failed" ? "Failed" : r.status}</Pill></td><td>{when(r.started)}</td></tr>))}</tbody>
            </table>)}
          <h2>Recent jobs</h2>
          {data.jobs.length === 0 ? <p className="ds-muted">{data.mode === "simple" ? "No queued jobs. In simple mode a pipeline run happens inside the server and is listed above." : "No jobs yet."}</p> : (
            <table className="ds-table" style={{ width: "100%" }}>
              <thead><tr><th>Job</th><th>State</th><th>Queued</th><th>Tries</th></tr></thead>
              <tbody>{data.jobs.map((j) => (
                <tr key={j.id}><td>{label(j.name)}</td><td><Pill tone={tone(j.state)}>{STATE_WORDS[j.state]}</Pill></td><td>{when(j.queued_at)}</td><td>{j.tries} of {j.max_tries}</td></tr>))}</tbody>
            </table>)}
          <h2>Latest events</h2>
          {data.events.length === 0 ? <p className="ds-muted">No events yet.</p> : (
            <ul>{data.events.map((e) => <li key={e.id}>{when(e.at)}: {saying(e)}</li>)}</ul>)}
        </>) : null}
    </PageFrame>
  );
}
