import { useState } from "react";

import { ApiError } from "../../../api/client";
import { markRestricted, notPersonal } from "../api";
import { m2Pre } from "../copy";

interface Props {
  baselineId: string;
  docId: string;
  title: string;
  words: string[];
  restrictPath: string;
  onDecided: () => void;
}

/** A document that mentions personal data waits for the company admin: restrict it (the Company context page's own route) or say it is not personal. */
export default function PersonalNotice({ baselineId, docId, title, words, restrictPath, onDecided }: Props) {
  const [problem, setProblem] = useState("");
  const run = (job: Promise<unknown>) => job.then(onDecided).catch((e: unknown) => setProblem(e instanceof ApiError ? e.message : m2Pre.saveFailed));
  return (
    <div role="note" className="n-note" style={{ margin: "8px 0", padding: 10, border: "1px solid var(--n-line, #ddd)" }}>
      <strong>{title}</strong>
      <p>{m2Pre.personalNotice(words)}</p>
      <p className="n-muted">{m2Pre.personalHeld}</p>
      <div className="n-flex wrap">
        <button type="button" className="n-btn primary sm" onClick={() => void run(markRestricted(restrictPath))}>{m2Pre.markRestricted}</button>
        <button type="button" className="n-btn sm" onClick={() => void run(notPersonal(baselineId, docId))}>{m2Pre.notPersonal}</button>
      </div>
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </div>
  );
}
