import { useCallback, useEffect, useState, type ReactNode } from "react";

import "../trust.css";

/** Load once, keep the value settable (POSTs return the fresh shape), and offer a retry on error. */
export function useLoad<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    fetcher().then(setData, () => setFailed(true));
  }, [fetcher]);
  useEffect(load, [load]);
  return { data, setData, failed, load };
}

/** The loading / error line every trust page shows before its content. */
export function Status({ failed, retry, what }: { failed: boolean; retry: () => void; what: string }): ReactNode {
  return failed ? (
    <div className="v3-row">
      <p className="v3-err">Could not load the {what}.</p>
      <button type="button" onClick={retry}>Try again</button>
    </div>
  ) : (
    <p className="v3-mute">Loading the {what}...</p>
  );
}
