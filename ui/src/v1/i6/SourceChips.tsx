import { Link } from "react-router-dom";

export interface Source { file: string; path: string; from: number; to: number }

// D1: the passages North used for its reply, as small chips that open the source viewer (G3) at the line. The server checks access there.
export default function SourceChips({ iid, sources }: { iid: string; sources?: Source[] }) {
  if (!sources?.length) return null;
  return (
    <p className="ds-muted" aria-label="Sources North used" style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", margin: "0.35rem 0 0" }}>
      {sources.map((s) => (
        <Link key={`${s.path}:${s.from}-${s.to}`} className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/source?file=${encodeURIComponent(s.path)}&line=${s.from}`}
          style={{ border: "1px solid currentColor", borderRadius: "999px", padding: "0 0.5rem", fontSize: "0.8em" }}>
          {s.file}, lines {s.from}-{s.to}
        </Link>
      ))}
    </p>
  );
}
