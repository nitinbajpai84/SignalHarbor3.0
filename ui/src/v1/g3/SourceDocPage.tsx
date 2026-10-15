import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame } from "../../design";
import { getDoc, type DocView } from "./api";

// G3: /centre/build/:iid/source?file=<path>&line=<n>, the document a benchmark row was read from, with the line marked.
// The server shows it only to whoever may read the document (K1); anyone else gets the sentence it sends.
export default function SourceDocPage() {
  const { iid = "" } = useParams<{ iid: string }>();
  const [q] = useSearchParams();
  const file = q.get("file") ?? "";
  const line = Number(q.get("line")) || 0;
  const [doc, setDoc] = useState<DocView | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getDoc(iid, file, line).then((d) => { if (live) setDoc(d); })
      .catch((e: unknown) => { if (live) setProblem(e instanceof ApiError && e.message ? e.message : "The document could not be opened. Please try again."); });
    return () => { live = false; };
  }, [iid, file, line]);

  useEffect(() => { if (doc && line) document.getElementById(`line-${line}`)?.scrollIntoView?.({ block: "center" }); }, [doc, line]);

  return (
    <PageFrame title={doc?.name ?? "Source document"}>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : !doc ? <p className="ds-muted">Opening the document…</p> : (
        <ol style={{ listStyle: "none", padding: 0, margin: 0, fontFamily: "var(--ds-mono, monospace)" }}>
          {doc.lines.map((l) => (
            <li key={l.n} id={`line-${l.n}`} aria-current={l.n === line ? "true" : undefined}
              style={l.n === line ? { background: "var(--ds-highlight, rgba(255, 196, 0, 0.25))" } : undefined}>
              <span className="ds-muted" style={{ display: "inline-block", width: "3.5em" }}>{l.n}</span>{l.text}
            </li>
          ))}
        </ol>
      )}
    </PageFrame>
  );
}
