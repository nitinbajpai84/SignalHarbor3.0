// Typed calls for M3-P02 intake. Everything goes through the shared client; nothing here calls fetch.
import { apiGet, apiSend, guestSend } from "../../../api/client";
import { BASE } from "../api";

export interface Period {
  from: string;
  to: string;
  label: string;
}
export interface AskedColumn {
  field_id: string;
  name: string;
  meaning: string | null;
  type: string | null;
  measures: { id: string; name: string }[];
  personal: boolean;
}
export interface AskedTable {
  table_id: string;
  name: string;
  row_means: string | null;
  columns: AskedColumn[];
}
export interface ProfileColumn {
  name: string;
  restricted?: boolean;
  type?: string;
  fill?: number;
  nulls?: number;
  non_empty?: number;
  personal?: boolean;
  samples?: string[];
  match?: { confidence: "low" | "medium" | "high"; reasons: string[] } | null;
}
export interface ProfileTable {
  file: string;
  name: string | null;
  row_count: number;
  date_column: string | null;
  date_range: { from: string; to: string } | null;
  duplicate_key: { columns: string[]; duplicates: number } | null;
  columns: ProfileColumn[];
}
export interface Gap {
  kind: "file_not_arrived" | "missing_column" | "half_empty" | "some_empty" | "period_short";
  text: string;
  measures: string[];
}
export interface Profile {
  period: Period;
  files: { file: string; kind: string; rows: number; by: string; at: string }[];
  tables: ProfileTable[];
  gaps: Gap[];
}
export type RequestState = "sent" | "opened" | "arrived";
export interface IntakeRequest {
  id: string;
  source_id: string;
  source_name: string;
  owner: string | null;
  zone: string | null;
  period: Period;
  tables: AskedTable[];
  benchmarks: { measure_id: string; measure_name: string; ask: string }[];
  state: RequestState;
  link: "open" | "revoked" | "expired";
  expires_at: string;
  days_waiting: number;
  reminders: string[];
  profile?: Profile | null;
}
export interface Candidate {
  source_id: string;
  source_name: string;
}
/** A source whose sample the company profile already held: no request is made for it. */
export interface FromProfile {
  source_id: string;
  source_name: string;
  from: string;
  files: string[];
  profile?: Profile | null;
}
/** A profile sample Lens could not place for certain. */
export interface ToConfirm {
  key: string;
  file: string;
  from: string;
  candidates: Candidate[];
}
export interface Intake {
  requests: IntakeRequest[];
  from_profile?: FromProfile[];
  to_confirm?: ToConfirm[];
  period: Period;
  not_yet_asked: { source_id: string; source_name: string }[];
  summary: { asked: number; arrived: number };
}
export interface Email {
  subject: string;
  body: string;
}
export interface Outgoing {
  request: IntakeRequest;
  link_path?: string;
  email: Email;
}
export interface BenchmarkRow {
  measure_id: string;
  measure_name: string;
  restricted: boolean;
  figure?: number;
  unit?: string | null;
  period_end?: string | null;
  came_from?: string | null;
  given_by?: string;
  line?: string;
  matched?: "auto" | "person";
  from_profile?: boolean;
}
export interface UnmatchedLine {
  index: number;
  line: string;
  figure: number | null;
  unit: string | null;
  period_end: string | null;
  came_from: string | null;
  problem: string | null;
}
export interface Benchmarks {
  file: { name: string; by: string; at: string } | null;
  measures: BenchmarkRow[];
  unmatched: UnmatchedLine[];
  choices: { id: string; name: string }[];
  waiting_for: { id: string; name: string }[];
}

const I = (id: string) => `${BASE}/assessments/${id}/intake`;
export const getIntake = (id: string) => apiGet<Intake>(`${I(id)}/requests`);
export const makeRequests = (id: string) => apiSend<{ sent: (Outgoing & { source_id: string })[]; new: number }>("POST", `${I(id)}/requests`);
export const remind = (id: string, rid: string) => apiSend<Outgoing>("POST", `${I(id)}/requests/${rid}/remind`);
export const revoke = (id: string, rid: string) => apiSend<{ request: IntakeRequest }>("POST", `${I(id)}/requests/${rid}/revoke`);
export const relink = (id: string, rid: string) => apiSend<Outgoing>("POST", `${I(id)}/requests/${rid}/relink`);
export const uploadSource = (id: string, sourceId: string, filename: string, data: string) =>
  apiSend<{ profile: Profile | null }>("POST", `${I(id)}/sources/${sourceId}/upload`, { filename, data });
/** A file with no source chosen: Lens files it, or answers `needs_confirm` with the sources it might be (nothing is kept then). */
export interface Filed {
  filed?: Candidate;
  needs_confirm?: { file: string; candidates: Candidate[] };
  profile?: Profile | null;
}
export const uploadAuto = (id: string, filename: string, data: string) => apiSend<Filed>("POST", `${I(id)}/sources/_auto/upload`, { filename, data });
export const uploadChosen = (id: string, sourceId: string, filename: string, data: string) => apiSend<Filed>("POST", `${I(id)}/sources/${sourceId}/upload`, { filename, data });
export const placeSample = (id: string, key: string, sourceId: string) => apiSend<Filed>("POST", `${I(id)}/sources/_auto/upload`, { profile_sample: key, source_id: sourceId });
export const getBenchmarks = (id: string) => apiGet<Benchmarks>(`${I(id)}/benchmarks`);
export const uploadBenchmarks = (id: string, filename: string, data: string) => apiSend<Benchmarks>("POST", `${I(id)}/benchmarks/upload`, { filename, data });
export const mapBenchmark = (id: string, index: number, measureId: string) => apiSend<Benchmarks>("POST", `${I(id)}/benchmarks/map`, { index, measure_id: measureId });

// the owner's link: no sign-in, the token goes in a header only
export const linkForm = (token: string) => guestSend<IntakeRequest & { profile: Profile | null }>("POST", `${BASE}/intake/link/form`, {}, token);
export const linkUpload = (token: string, filename: string, data: string, kind: "source" | "benchmark") =>
  guestSend<IntakeRequest & { profile: Profile | null }>("POST", `${BASE}/intake/link/upload`, { filename, data, kind }, token);

/** The file as base64 text (the upload body). */
export function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("read"));
    r.readAsDataURL(file);
  });
}
