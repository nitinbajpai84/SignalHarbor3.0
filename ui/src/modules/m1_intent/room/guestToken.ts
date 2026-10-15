// What this browser remembers between page loads. A guest's participant token lives in localStorage, one entry per
// session, so closing the tab does not lose the seat: the same browser returns with the same link. It is cleared when
// the session closes or the seat stops working. The join link the organiser made on this screen stays in
// sessionStorage (this tab only). Both are secrets: never put in a URL, never sent anywhere but the header or body
// described in client.ts, never logged. Every access is wrapped: storage can be blocked, and the screens must still
// work without it.
const TOKEN_KEY = "sh.m1.guest.";
const LINK_KEY = "sh.m1.link.";

export interface StoredToken {
  token: string;
  sessionId: string;
  /** The join code the seat was taken with, so the link finds its seat again before the session is known. */
  code?: string;
}

const local = () => localStorage;
const tab = () => sessionStorage;

function read(store: () => Storage, key: string): string | null {
  try {
    return store().getItem(key);
  } catch {
    return null;
  }
}
function write(store: () => Storage, key: string, value: string | null): void {
  try {
    if (value === null) store().removeItem(key);
    else store().setItem(key, value);
  } catch {
    // storage blocked: the screen carries on for this page load
  }
}

function parse(raw: string | null): StoredToken | null {
  if (raw === null) return null;
  try {
    const v: unknown = JSON.parse(raw);
    if (typeof v === "object" && v !== null) {
      const { token, sessionId, code } = v as Partial<StoredToken>;
      if (typeof token === "string" && typeof sessionId === "string") return { token, sessionId, ...(typeof code === "string" ? { code } : {}) };
    }
  } catch {
    // not ours: treat as nothing stored
  }
  return null;
}

export function loadToken(sessionId: string): StoredToken | null {
  return parse(read(local, TOKEN_KEY + sessionId));
}
/** The seat this browser holds for the session behind a join link, if any. */
export function loadTokenByCode(code: string): StoredToken | null {
  try {
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key?.startsWith(TOKEN_KEY)) {
        const found = parse(localStorage.getItem(key));
        if (found?.code === code) return found;
      }
    }
  } catch {
    // storage blocked
  }
  return null;
}
export function saveToken(value: StoredToken): void {
  write(local, TOKEN_KEY + value.sessionId, JSON.stringify(value));
}
export function clearToken(sessionId: string): void {
  write(local, TOKEN_KEY + sessionId, null);
}

/** The join path (/join/<code>) of a room this tab started, so the organiser can copy it again after a reload. */
export function loadLink(sessionId: string): string | null {
  const v = read(tab, LINK_KEY + sessionId);
  return v !== null && /^\/join\/[A-Za-z0-9_-]{22}$/.test(v) ? v : null;
}
export function saveLink(sessionId: string, joinPath: string): void {
  write(tab, LINK_KEY + sessionId, joinPath);
}
