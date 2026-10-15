import { useCallback, useEffect, useState, type ReactNode } from "react";

import V3Frame from "../../Frame";
import TrustTabs from "../../TrustTabs";
import "../trust.css";

export interface Loaded<T> { data: T | null; err: string; loading: boolean; retry: () => void; set: (d: T) => void }

/** One load with loading and error state; retry re-runs it. */
export function useLoad<T>(fn: () => Promise<T>, key: string): Loaded<T> {
  const [data, set] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [n, setN] = useState(0);
  const retry = useCallback(() => setN((x) => x + 1), []);
  useEffect(() => {
    let live = true;
    setLoading(true);
    setErr("");
    fn()
      .then((d) => { if (live) set(d); })
      .catch((e: Error) => { if (live) setErr(e.message || "Could not load"); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, n]);
  return { data, err, loading: loading && data === null, retry, set };
}

/** Frame, Trust tabs, heading, and the loading / error / empty states every trust page shares. */
export function TrustPage(p: {
  kicker: string; title: string; sub?: string;
  state: { err: string; loading: boolean; retry: () => void };
  empty?: string | false; children: ReactNode;
}) {
  const { err, loading, retry } = p.state;
  return (
    <V3Frame>
      <TrustTabs />
      <main className="v3-main tr-page">
        <div>
          <p className="v3-kicker" style={{ margin: 0 }}>{p.kicker}</p>
          <h1>{p.title}</h1>
          {p.sub && <p className="v3-mute">{p.sub}</p>}
        </div>
        {loading ? <p className="v3-mute" role="status">Loading...</p>
          : err ? <div role="alert"><p className="v3-err">{err}</p><button onClick={retry}>Try again</button></div>
          : p.empty ? <p className="v3-mute">{p.empty}</p> : p.children}
      </main>
    </V3Frame>
  );
}
