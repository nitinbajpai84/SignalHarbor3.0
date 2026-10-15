// C5: connectors (routes in sh_platform/v1/c5_routes.py). Credentials are environment variable NAMES; no secret is ever typed here.
import { apiGet, apiSend } from "../../api/client";

export type Kind = "imap" | "sftp" | "graph";
export interface Health { status: "never" | "ok" | "failed"; failed: boolean; late: boolean; last_run: string | null; last_ok: string | null; last_files: number; files_landed: number; duplicates_skipped: number; error: { code: string; message: string } | null }
export interface Connector { id: string; kind: Kind; host: string; schedule: string; source_code: string; credentials: Record<string, string>; params: Record<string, string>; file_pattern: string; health: Health | null }
export interface Listing { connectors: Connector[]; kinds: Kind[]; schedules: string[]; egress_note: string }
export interface OpResult { ok?: boolean; message?: string; code?: string; would_arrive?: { name: string; size: number }[]; status?: string; landed?: number; duplicates?: number; error?: { message: string } | null }

export const KIND_NAMES: Record<Kind, string> = { imap: "Statements mailbox (IMAP)", sftp: "SFTP pull", graph: "Cloud folder (SharePoint, OneDrive)" };
// the credential and parameter fields each kind asks for
export const FIELDS: Record<Kind, { creds: string[]; params: string[]; host: boolean }> = {
  imap: { creds: ["user", "password"], params: ["mailbox"], host: true },
  sftp: { creds: ["user", "password"], params: ["remote_path", "port"], host: true },
  graph: { creds: ["tenant", "client_id", "client_secret"], params: ["drive_id", "folder"], host: false },
};

const u = (id: string) => `/api/v1/connectors/${encodeURIComponent(id)}`;
export const listConnectors = () => apiGet<Listing>("/api/v1/connectors");
export const saveConnector = (id: string, body: Omit<Connector, "id" | "health">) => apiSend<Connector>("PUT", u(id), body);
export const removeConnector = (id: string) => apiSend<{ deleted: string }>("DELETE", u(id));
export const runOp = (id: string, op: "test" | "dry-run" | "fetch") => apiSend<OpResult>("POST", `${u(id)}/${op}`);

// Connect an API (routes in sh_platform/v1/c5_routes.py, logic in c5_connect/api.py): fixed public providers, series chosen from their lists.
export interface ApiSeries { id: string; label: string; kind: string }
export interface ApiProvider { id: string; name: string; host: string; blurb: string; needs_key: boolean; key_env: string | null; key_set: boolean; series: ApiSeries[] }
export interface ApiTest { ok: boolean; message: string; code?: string; seconds?: number; rows?: { series: string; date: string; value: string }[]; headlines?: string[] }
export const listApiProviders = () => apiGet<{ providers: ApiProvider[]; default_at: string }>("/api/v1/connect-api/providers");
export const testApi = (provider: string, series: string[]) => apiSend<ApiTest>("POST", "/api/v1/connect-api/test", { provider, series });
export const saveApi = (provider: string, series: string[]) => apiSend<Connector>("PUT", u(`api-${provider}`), { kind: "api", provider, series, schedule: "daily", at: "05:30" });
