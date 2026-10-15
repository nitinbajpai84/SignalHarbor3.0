import { useCallback, useEffect, useState } from "react";

import { ApiError, Refused } from "../api/client";
import type { ScreenStateName } from "./ScreenState";

export interface Loaded<T> {
  state: ScreenStateName;
  data: T | null;
  /** Plain words from the server for a refused or failed load, when it gave some. */
  message: string | undefined;
  retry: () => void;
}

/** Loads once per key and says which of the five screen states applies. */
export function useLoad<T>(load: () => Promise<T>, key: string, isEmpty?: (data: T) => boolean): Loaded<T> {
  const [state, setState] = useState<ScreenStateName>("loading");
  const [data, setData] = useState<T | null>(null);
  const [message, setMessage] = useState<string | undefined>(undefined);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setState("loading");
    load()
      .then((d) => {
        if (!live) return;
        setData(d);
        setMessage(undefined);
        setState(isEmpty?.(d) ? "empty" : "populated");
      })
      .catch((e: unknown) => {
        if (!live) return;
        setMessage(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : undefined);
        setState(e instanceof Refused ? "refused" : "error");
      });
    return () => {
      live = false;
    };
    // `load` and `isEmpty` are new functions on every render on purpose: only the key and a retry reload.
  }, [key, attempt]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { state, data, message, retry };
}
