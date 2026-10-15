import { apiSend } from "../../../api/client";

/** The 3.0 card kinds that can be added, mapped onto the 2.0 connector kinds in sh_platform/v1/c5_connect/spec.py. */
export type AddKind = "mailbox" | "sftp" | "http";

export interface FieldDef { key: string; label: string; secret?: boolean; place: "top" | "credentials" | "params"; hint?: string }

const VAR = "Name of the server setting that holds it, such as CONN_SFTP_USER";

export const FORMS: Record<AddKind, { label: string; kind: "imap" | "sftp" | "graph"; fields: FieldDef[] }> = {
  mailbox: {
    label: "Mailbox", kind: "imap",
    fields: [
      { key: "host", label: "Host", place: "top" },
      { key: "mailbox", label: "Folder", place: "params" },
      { key: "user", label: "User", secret: true, place: "credentials", hint: VAR },
      { key: "password", label: "Password", secret: true, place: "credentials", hint: VAR },
    ],
  },
  sftp: {
    label: "SFTP", kind: "sftp",
    fields: [
      { key: "host", label: "Host", place: "top" },
      { key: "port", label: "Port", place: "params" },
      { key: "remote_path", label: "Folder", place: "params" },
      { key: "user", label: "User", secret: true, place: "credentials", hint: VAR },
      { key: "key_file", label: "Key file", secret: true, place: "credentials", hint: VAR },
    ],
  },
  http: {
    label: "Shared drive", kind: "graph",
    fields: [
      { key: "drive_id", label: "Drive", place: "params" },
      { key: "folder", label: "Folder", place: "params" },
      { key: "tenant", label: "Tenant", secret: true, place: "credentials", hint: VAR },
      { key: "client_id", label: "Client", secret: true, place: "credentials", hint: VAR },
      { key: "client_secret", label: "Secret", secret: true, place: "credentials", hint: VAR },
    ],
  },
};

/** The 2.0 schedules; the artboard's finer ones are not offered by the server. */
export const SCHEDULES: [string, string][] = [["daily", "Daily"], ["hourly", "Hourly"], ["weekly", "Weekly"], ["manual", "Manual"]];

export interface TestResult { ok: boolean; message?: string }

export const connectorId = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);

/** PUT /api/v1/connectors/{id}: the existing 2.0 route. Credential values are variable names, never secrets. */
export function saveConnector(a: AddKind, name: string, v: Record<string, string>, pattern: string, schedule: string, sourceCode: string) {
  const f = FORMS[a];
  const pick = (place: FieldDef["place"]) => Object.fromEntries(f.fields.filter((x) => x.place === place && v[x.key]).map((x) => [x.key, v[x.key]]));
  const id = connectorId(name);
  return apiSend<unknown>("PUT", `/api/v1/connectors/${encodeURIComponent(id)}`, {
    kind: f.kind, host: v.host ?? "", schedule, source_code: sourceCode, credentials: pick("credentials"), params: pick("params"), file_pattern: pattern,
  }).then(() => id);
}

/** POST /api/v1/connectors/{id}/test: read only. */
export const testConnector = (id: string) => apiSend<TestResult>("POST", `/api/v1/connectors/${encodeURIComponent(id)}/test`);
