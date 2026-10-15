// The only file that calls fetch.
import { copy } from "../copy";

export interface Health {
  status: string;
}
export interface Me {
  display_name: string | null;
  /** Names a person to this browser (the workbench layout is remembered per person). */
  account_id?: string;
  company_id: string | null;
  roles: string[];
  /** The company's one time zone for every displayed date (PF2); Asia/Singapore when the profile names none. */
  time_zone?: string;
}
export interface ModuleInfo {
  id: string;
  number: number;
  name: string;
  description: string;
  agent: string;
}
export interface Company {
  company_id: string;
  name: string;
  industry: string;
  /** Present only when the company has a brand record; the logo file is served by GET /api/company/logo. */
  brand?: { logo?: string; primary_colour?: string };
}

export class ApiError extends Error {
  readonly status: number;
  /** Which value a 422 is about, when the server says. */
  readonly field: string | null;
  constructor(message: string, status: number, field: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.field = field;
  }
}
/** 403: the module is not part of the plan (module_not_available), or this person's role has no access. */
export class Refused extends ApiError {
  constructor(message: string) {
    super(message, 403);
    this.name = "Refused";
  }
}
/** 401 session_expired: the handler has already been told; callers just stop. */
export class SessionExpired extends ApiError {
  constructor(message: string) {
    super(message, 401);
    this.name = "SessionExpired";
  }
}

type ExpiredHandler = () => void;
let expiredHandler: ExpiredHandler | null = null;
let expiredFired = false;

/** The session provider registers here; it clears its state and the router goes to /login. */
export function setSessionExpiredHandler(handler: ExpiredHandler | null): void {
  expiredHandler = handler;
  expiredFired = false;
}

export function csrfToken(): string {
  const hit = document.cookie.split("; ").find((c) => c.startsWith("sh_csrf="));
  return hit ? decodeURIComponent(hit.slice("sh_csrf=".length)) : "";
}

interface ErrorBody {
  error?: string;
  message?: string;
  field?: string;
}
/** Answers whose message is already plain words for the screen (the module routes write them that way). */
const PLAIN_STATUSES = new Set([400, 404, 409, 422, 429]);

async function readBody(res: Response): Promise<ErrorBody> {
  try {
    const body: unknown = await res.json();
    if (typeof body !== "object" || body === null) return {};
    // FastAPI wraps a raised refusal in `detail`: lift its error and message so the screen shows the server's sentence
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return { ...(body as ErrorBody), message: detail };
    if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) return { ...(detail as ErrorBody), ...(body as ErrorBody) };
    return body as ErrorBody;
  } catch {
    return {};
  }
}

interface Options {
  body?: unknown;
  /** me(): a 401 here just means "signed out", not a redirect. */
  quiet401?: boolean;
  /** M1-P02: a joined guest's participant token. Sent only in the X-Session-Token header, never in a URL. */
  token?: string;
}

async function request<T>(method: string, path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") {
    headers["X-CSRF-Token"] = csrfToken();
  }
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (opts.token) {
    headers["X-Session-Token"] = opts.token; // M1-P02
  }
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(copy.errors.network, 0);
  }
  if (res.ok) {
    return (await res.json()) as T;
  }
  const body = await readBody(res);
  if (res.status === 401 && opts.token) {
    throw new ApiError("", 401); // M1-P02: a guest's refusal is not a sign-in that ended; the screen words it
  }
  if (res.status === 401 && body.error === "session_expired") {
    if (!opts.quiet401 && !expiredFired) {
      expiredFired = true;
      expiredHandler?.();
    }
    throw new SessionExpired(copy.errors.sessionEnded);
  }
  if (res.status === 403 && body.error === "module_not_available") {
    throw new Refused(copy.states.refused);
  }
  if (res.status === 403 && body.error === "forbidden") {
    throw new Refused(copy.states.noAccess);
  }
  if (res.status === 403 && body.error === "not_allowed" && typeof body.message === "string") {
    throw new ApiError(body.message, 403); // M2-E1: a rule about who may do this (the data owner confirms, the organiser accepts a risk): the sentence says which
  }
  if (res.status === 403 && body.error === "other_company" && typeof body.message === "string") {
    throw new ApiError(body.message, 403); // M1-P02: a person of another company opened a join link
  }
  if (PLAIN_STATUSES.has(res.status) && typeof body.message === "string" && body.message !== "") {
    throw new ApiError(body.message, res.status, body.field ?? null);
  }
  throw new ApiError(copy.errors.server, res.status);
}

/** Typed calls for module screens; this file stays the only one that calls fetch. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}
export function apiSend<T>(method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  return request<T>(method, path, { body });
}

export async function login(email: string, password: string): Promise<Me> {
  const me = await request<Me>("POST", "/api/auth/login", { body: { email, password } });
  expiredFired = false;
  return me;
}
export function logout(): Promise<unknown> {
  return request("POST", "/api/auth/logout");
}
/** Null when signed out. */
export async function me(): Promise<Me | null> {
  try {
    return await request<Me>("GET", "/api/auth/me", { quiet401: true });
  } catch (e) {
    if (e instanceof SessionExpired) {
      return null;
    }
    throw e;
  }
}
export function listModules(): Promise<ModuleInfo[]> {
  return request("GET", "/api/modules");
}
export function getCompany(): Promise<Company> {
  return request("GET", "/api/company");
}
export function getHealth(): Promise<Health> {
  return request("GET", "/api/health");
}

// ---- M1-P02: people with no account (a participant token), and the live stream ---------------------------------
/** The token goes in the X-Session-Token header and nowhere else. Signed-in people pass none: the cookie is used. */
export function guestGet<T>(path: string, token?: string): Promise<T> {
  return request<T>("GET", path, { token });
}
export function guestSend<T>(method: "POST", path: string, body: unknown, token?: string): Promise<T> {
  return request<T>(method, path, { body, token });
}

/**
 * A file the browser's own <video> or <img> tag cannot fetch for a guest (a tag cannot send the X-Session-Token header):
 * fetched here with the header and handed back as a Blob for a blob: address. Null when it could not be had.
 * ponytail: the whole file is held in memory; fine for the briefing video (100 MB at most), stream it if that grows.
 */
export async function guestBlob(path: string, token?: string): Promise<Blob | null> {
  try {
    const res = await fetch(path, { credentials: "same-origin", headers: token ? { "X-Session-Token": token } : {} });
    return res.ok ? await res.blob() : null;
  } catch {
    return null;
  }
}

export type StreamEnd = "ended" | "refused" | "failed";
/**
 * Server-sent events over fetch, because the browser's EventSource cannot send the X-Session-Token header.
 * Calls onText with each piece of text as it arrives; resolves when the stream ends. "refused" means the server
 * said no (the seat or the link stopped working), so the caller must not reconnect.
 */
export async function streamText(
  path: string,
  opts: { token?: string | null; signal: AbortSignal; onText: (text: string) => void },
): Promise<StreamEnd> {
  const headers: Record<string, string> = {};
  if (opts.token) {
    headers["X-Session-Token"] = opts.token;
  }
  try {
    const res = await fetch(path, { method: "GET", credentials: "same-origin", headers, signal: opts.signal });
    if (res.status === 401 || res.status === 403 || res.status === 404) {
      return "refused";
    }
    if (!res.ok || !res.body) {
      return "failed";
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        return "ended";
      }
      opts.onText(decoder.decode(value, { stream: true }));
    }
  } catch {
    return "failed";
  }
}

/**
 * A file download that works in every browser: fetched with the session, held as a blob: address, saved by clicking a real
 * <a download>, then released. The name comes from the response's Content-Disposition, else `fallback`. Throws ApiError with
 * the server's plain sentence when it fails.
 */
export async function downloadFile(path: string, fallback: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(path, { credentials: "same-origin" });
  } catch {
    throw new ApiError(copy.errors.network, 0);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { message?: string } | null;
    throw new ApiError(body?.message ?? copy.errors.server, res.status);
  }
  const named = /filename="?([^";]+)"?/i.exec(res.headers.get("Content-Disposition") ?? "")?.[1];
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = named || fallback;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
