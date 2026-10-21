import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type Context, type ReactNode } from "react";

import { useLocation } from "react-router-dom";

import * as api from "./api/client";
import { setCompanyZone } from "./design/dates";

export type SessionState = "loading" | "signed-out" | "signed-in" | "error";

interface Session {
  state: SessionState;
  user: api.Me | null;
  /** True after a signed-in session ended on its own; false on a first visit and after sign-in or sign-out. */
  sessionEnded: boolean;
  signIn: (email: string, password: string, otp?: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Check the session again after a failed check. */
  retry: () => void;
}

// One context per page, kept on the window: when the dev server re-runs this module after an edit (hot reload), a fresh createContext
// would leave the mounted provider on the old one and every useSession would throw "needs a SessionProvider".
const holder = globalThis as typeof globalThis & { __shSessionContext?: Context<Session | null> };
const SessionContext = (holder.__shSessionContext ??= createContext<Session | null>(null));

/** Survives a reload, so a session that ended server side can still be explained. Page works without it. */
export const HAD_SESSION_KEY = "sh_had_session";

function readMarker(): boolean {
  try {
    return sessionStorage.getItem(HAD_SESSION_KEY) === "1";
  } catch {
    return false;
  }
}
/** Set while this browser has a sign-in, in any tab. A join link asks who is signed in only when it is set. */
export const SIGNED_IN_HINT_KEY = "sh_signed_in_hint";

/** Pages that work without a sign-in: no need to ask who is signed in (a 401 would only add console noise). */
function needsNoSignIn(path: string): boolean {
  if (path.startsWith("/answer/")) return true;
  try {
    return path.startsWith("/join/") && localStorage.getItem(SIGNED_IN_HINT_KEY) !== "1"; // a signed-in person joins with their account
  } catch {
    return false;
  }
}

function writeMarker(on: boolean): void {
  try {
    if (on) sessionStorage.setItem(HAD_SESSION_KEY, "1");
    else sessionStorage.removeItem(HAD_SESSION_KEY);
    if (on) localStorage.setItem(SIGNED_IN_HINT_KEY, "1");
    else localStorage.removeItem(SIGNED_IN_HINT_KEY);
  } catch {
    // storage blocked: the in-memory flag still covers this page load
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>("loading");
  const [user, setUser] = useState<api.Me | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const hadSession = useRef(readMarker());
  const atStart = useRef(useLocation().pathname); // decided once per page load: moving about inside the app does not re-ask

  const markSession = useCallback((on: boolean) => {
    hadSession.current = on;
    writeMarker(on);
  }, []);

  const clear = useCallback(() => {
    setUser(null);
    setState("signed-out");
  }, []);

  useEffect(() => {
    api.setSessionExpiredHandler(() => {
      if (hadSession.current) setSessionEnded(true);
      clear();
    });
    return () => api.setSessionExpiredHandler(null);
  }, [clear]);

  useEffect(() => {
    if (attempt === 0 && needsNoSignIn(atStart.current)) {
      setState("signed-out"); // as far as this page is concerned; a sign-in elsewhere is asked about when it is needed
      return;
    }
    let live = true;
    api
      .me()
      .then((m) => {
        if (!live) return;
        setUser(m);
        if (m) markSession(true);
        else if (hadSession.current) setSessionEnded(true); // a 401 on a reload, after a session existed
        setState(m ? "signed-in" : "signed-out");
      })
      .catch(() => live && setState("error"));
    return () => {
      live = false;
    };
  }, [attempt, markSession]);

  useEffect(() => setCompanyZone(user?.time_zone), [user]); // PF2: every date on screen in the company's one time zone

  const signIn = useCallback(async (email: string, password: string, otp?: string) => {
    const m = await api.login(email, password, otp);
    setUser(m);
    setSessionEnded(false);
    markSession(true);
    setState("signed-in");
  }, [markSession]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // the session is gone or the service is down; either way this screen should be signed out
    }
    setSessionEnded(false);
    markSession(false);
    clear();
  }, [clear, markSession]);

  const retry = useCallback(() => {
    setState("loading");
    setAttempt((a) => a + 1);
  }, []);

  const value = useMemo(
    () => ({ state, user, sessionEnded, signIn, signOut, retry }),
    [state, user, sessionEnded, signIn, signOut, retry],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** The session when there is a provider, else null: for screens that remember something per person but work without one. */
export function useSessionIfAny(): Session | null {
  return useContext(SessionContext);
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession needs a SessionProvider");
  return s;
}
