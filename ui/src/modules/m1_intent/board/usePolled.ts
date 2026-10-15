import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, Refused } from "../../../api/client";
import { copy } from "../../../copy";
import type { ScreenStateName } from "../../../components/ScreenState";

export const POLL_MS = 3000;

/** Plain words for a failed call: the server's own sentence when it gave one, else the shared error line. */
export function problemText(e: unknown): string {
  return e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : copy.states.error;
}

export interface Polled<T> {
  state: ScreenStateName;
  data: T | null;
  /** The last failure, so a screen can tell "not yet" (409) from a real error. */
  failure: unknown;
  reload: () => void;
  /** Shows a newer view at once (the answer to an action) until the next poll replaces it. */
  put: (next: T) => void;
}

/** Loads at once and again every few seconds: the board and the room fill live for everyone in them. */
export function usePolled<T>(load: () => Promise<T>, key: string, ms = POLL_MS): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [state, setState] = useState<ScreenStateName>("loading");
  const latest = useRef(load);
  latest.current = load;
  const epoch = useRef(0); // moves on with every `put`: a poll that started before it is stale and is dropped

  const run = useCallback(() => {
    const mine = epoch.current;
    latest.current().then(
      (d) => {
        if (mine !== epoch.current) return;
        setData(d);
        setFailure(null);
        setState("populated");
      },
      (e: unknown) => {
        if (mine !== epoch.current) return;
        setFailure(e);
        // a short dropout while a view is on screen keeps that view; only a refusal or a first failure replaces it
        setState((was) => (was === "populated" && !(e instanceof Refused) ? was : e instanceof Refused ? "refused" : "error"));
      },
    );
  }, []);

  useEffect(() => {
    setState("loading");
    setData(null);
    run();
    const t = setInterval(run, ms);
    return () => clearInterval(t);
  }, [key, ms, run]);

  const put = useCallback((next: T) => {
    epoch.current += 1;
    setData(next);
  }, []);

  return { state, data, failure, reload: run, put };
}
