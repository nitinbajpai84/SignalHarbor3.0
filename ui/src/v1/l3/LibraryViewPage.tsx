import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame } from "../../design";
import { getFileView, type FileView } from "./api";

// W06: /centre/library/view?file=<path>, a library file read-only with line numbers, for a person with no project to open it in.
export default function LibraryViewPage() {
  const [q] = useSearchParams();
  const file = q.get("file") ?? "";
  const [doc, setDoc] = useState<FileView | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getFileView(file).then((d) => live && setDoc(d))
      .catch((e: unknown) => live && setProblem(e instanceof ApiError && e.message ? e.message : "The document could not be opened. Please try again."));
    return () => { live = false; };
  }, [file]);
  return (
    <PageFrame title={doc?.name ?? "Library document"}>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : !doc ? <p className="ds-muted">Opening the document…</p> : (
        <ol style={{ listStyle: "none", padding: 0, margin: 0, fontFamily: "var(--ds-mono, monospace)" }}>
          {doc.lines.map((l) => (
            <li key={l.n} id={`line-${l.n}`}><span className="ds-muted" style={{ display: "inline-block", width: "3.5em" }}>{l.n}</span>{l.text}</li>
          ))}
        </ol>
      )}
    </PageFrame>
  );
}
