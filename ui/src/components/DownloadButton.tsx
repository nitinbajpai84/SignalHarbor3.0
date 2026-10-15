import { useState } from "react";

import { ApiError, downloadFile } from "../api/client";
import { copy } from "../copy";

/** A button that downloads a file with the session (see downloadFile) and says plainly when it could not. */
export default function DownloadButton({ path, fallbackName, label, primary }: { path: string; fallbackName: string; label: string; primary?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    setProblem(null);
    try {
      await downloadFile(path, fallbackName);
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : copy.errors.server);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button type="button" className={primary ? "n-btn primary" : "n-btn"} disabled={busy} onClick={() => void go()}>
        {label}
      </button>
      {problem ? <span role="alert" className="state state-error">{problem}</span> : null}
    </>
  );
}
