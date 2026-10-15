import { useEffect, useState } from "react";

import { streamText } from "../api/client";
import { createEventReader } from "./sse";

/** connecting: waiting for the first update. live: updates arriving. offline: the connection dropped, retrying.
 *  refused: the server said no (the seat or the link stopped working): no retry. */
export type LiveStatus = "connecting" | "live" | "offline" | "refused";

const RETRY_MS = 2000;

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

/**
 * The latest view the server pushed for this path. A person with a participant token passes it; a signed-in person
 * passes null and the cookie is used. The stream ends now and then on purpose; this reconnects until refused.
 * `parse` turns the pushed JSON into the screen's type, or returns null for something it does not recognise.
 */
export function useLive<T>(path: string | null, token: string | null, parse: (raw: unknown) => T | null) {
  const [view, setView] = useState<T | null>(null);
  const [status, setStatus] = useState<LiveStatus>("connecting");

  useEffect(() => {
    if (path === null) {
      return;
    }
    const ctl = new AbortController();
    setStatus("connecting");
    void (async () => {
      while (!ctl.signal.aborted) {
        const read = createEventReader((data) => {
          try {
            const next = parse(JSON.parse(data));
            if (next !== null) {
              setView(next);
              setStatus("live");
            }
          } catch {
            // a piece we cannot read is skipped; the next update replaces it
          }
        });
        const how = await streamText(path, { token, signal: ctl.signal, onText: read });
        if (ctl.signal.aborted) {
          return;
        }
        if (how === "refused") {
          setStatus("refused");
          return;
        }
        setStatus(how === "failed" ? "offline" : "connecting");
        await wait(RETRY_MS, ctl.signal);
      }
    })();
    return () => ctl.abort();
    // `parse` is a new function each render on purpose; only the path and the token restart the stream.
  }, [path, token]);

  return { view, status };
}
