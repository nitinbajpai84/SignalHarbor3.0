// P1: projects, artefacts as documents of numbered lines, comments (docs/plan/V1-BUILD.md Round 6), through the shared client.
import { apiGet, apiSend, downloadFile } from "../../api/client";

export type Kind = "intent" | "design" | "build_pack" | "brief" | "run_book" | "benchmarks";
export const KINDS: Kind[] = ["intent", "design", "build_pack", "benchmarks", "brief", "run_book"];
export interface Artefact { kind: Kind; record_path: string; version: number | null; state: "draft" | "signed"; signed_by: string | null; signed_at: string | null }
export interface Project {
  id: string; intent_id: string; title: string; started_by: string | null; started_at: string;
  stage: "talking" | "signed" | "designed" | "built" | "live"; artefacts: Artefact[];
  people: { raiser: string | null; sponsor: string | null; builder: string | null; head_of_data: string | null; ops: string | null };
}
export interface Comment {
  id: string; artefact: Kind; line_ref: string | null; by: string; name: string; to: string | null; text: string;
  kind: "comment" | "handover" | "note" | "ticket"; state: "open" | "answered" | "resolved"; at: string; answer: string | null; answered_at: string | null;
}
export interface Doc {
  project: string; kind: Kind; name: string; title: string; state: "draft" | "signed"; version: number | null; signed_by: string | null;
  signed_at: string | null; signers: string[]; me: string;
  sections: { n: number; heading: string; lines: { ref: string; text: string }[] }[]; comments: Comment[];
}

const base = (pid: string) => `/api/v1/projects/${encodeURIComponent(pid)}`;
export const getProject = (pid: string) => apiGet<Project>(base(pid));
export const projectOf = (iid: string) => apiGet<Project>(`/api/v1/intents/${encodeURIComponent(iid)}/project`);
export const getDoc = (pid: string, kind: Kind) => apiGet<Doc>(`${base(pid)}/artefacts/${kind}`);
export const addComment = (pid: string, body: { artefact: Kind; line_ref: string | null; to: string; text: string }) =>
  apiSend<Comment>("POST", `${base(pid)}/comments`, body);
export const answerComment = (pid: string, cid: string, text: string) => apiSend<Comment>("POST", `${base(pid)}/comments/${cid}/answer`, { text });
export const resolveComment = (pid: string, cid: string) => apiSend<Comment>("POST", `${base(pid)}/comments/${cid}/resolve`);
// G2: Go live (the project's owner) and the run book (Flow drafts, the ops manager edits and signs).
export const goLive = (pid: string) => apiSend<Project>("POST", `${base(pid)}/go-live`);
export const draftRunBook = (pid: string) => apiSend<unknown>("POST", `${base(pid)}/run-book/draft`);
export const saveRunBook = (pid: string, sections: { lines: string[] }[]) => apiSend<unknown>("PUT", `${base(pid)}/run-book`, { sections });
export const signRunBook = (pid: string) => apiSend<unknown>("POST", `${base(pid)}/run-book/sign`);
export const exportDoc = (pid: string, kind: Kind, format: "md" | "docx" | "xlsx") =>
  downloadFile(`${base(pid)}/artefacts/${kind}/export?format=${format}`, `${pid}-${kind}.${format}`);
