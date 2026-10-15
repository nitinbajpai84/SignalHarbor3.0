// W3: jobs and events (routes in sh_platform/v1/w3_jobs_routes.py).
import { apiGet, apiSend } from "../../../api/client";

export type JobState = "queued" | "running" | "retrying" | "done" | "failed";
export interface Job { id: string; name: string; state: JobState; tries: number; max_tries: number; error: string | null; queued_at: string; started_at: string | null; finished_at: string | null }
export interface Ev { id: number; topic: string; at: string; payload: Record<string, unknown> }
export interface PipelineRun { project_id: string; title: string | null; run_id: string; mode: "sandbox" | "live"; status: string; started: string; finished: string | null }
export interface JobsView { mode: "simple" | "production"; stats: Record<JobState, number>; jobs: Job[]; failed: Job[]; events: Ev[]; /** Pipeline runs from the projects' own run logs (a simple-mode run is not on the queue). */ runs?: PipelineRun[] }

export const NAMES: Record<string, string> = {
  "b6.tick": "Scheduled pipeline check", "b6.run": "Pipeline run", "b6.on_arrival": "Pipeline run on file arrival",
  "d1.tick": "Delivery check", "graph.rebuild": "Graph rebuild",
};
export const STATE_WORDS: Record<JobState, string> = { queued: "Waiting", running: "Running", retrying: "Will try again", done: "Done", failed: "Failed" };

export const getJobs = () => apiGet<JobsView>("/api/v1/jobs");
export const retryJob = (id: string) => apiSend<{ retried: string }>("POST", `/api/v1/jobs/${encodeURIComponent(id)}/retry`);
