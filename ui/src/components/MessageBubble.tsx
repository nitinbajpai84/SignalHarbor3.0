import type { ReactNode } from "react";

// The earlier prototype's North advisor labels (js/ui.js _ADVISOR_LABELS): a small chip before the line. A person's own
// message never gets a chip. Every North line that is a pack's practice is a suggestion, and says so.
const ADVISOR_LABELS = [
  { prefix: "Industry practice (suggestion):", cls: "industry" },
  { prefix: "From your data:", cls: "from-data" },
] as const;

function Line({ text, from }: { text: string; from: "agent" | "human" }) {
  const trimmed = text.trimStart();
  const hit = from === "agent" ? ADVISOR_LABELS.find((l) => trimmed.startsWith(l.prefix)) : undefined;
  if (!hit) return <div className="text-line">{text}</div>;
  const rest = trimmed.slice(hit.prefix.length).trim();
  return (
    <div className={`text-line advisor-line ${hit.cls}`}>
      <span className="advisor-chip">{hit.prefix.replace(/:$/, "")}</span>
      {rest ? ` ${rest}` : ""}
    </div>
  );
}

interface Props {
  from: "agent" | "human";
  who: string;
  when?: string;
  text: string;
  /** Small tags under the text (for example "Suggestion"). */
  tags?: string[];
  /** A reply that was not an answer is shown in the muted ink. */
  muted?: boolean;
  children?: ReactNode;
}

/** The earlier prototype's messageBubble(): n-message from-agent | from-human with who-row, text lines and tags. */
export default function MessageBubble({ from, who, when, text, tags = [], muted = false, children }: Props) {
  return (
    <div className={`n-message from-${from}${muted ? " is-muted" : ""}`}>
      <div className="bubble">
        <div className="who-row">
          <span className="who">{who}</span>
          {when ? <span className="when">{when}</span> : null}
        </div>
        <div className="text">
          {text.split("\n").map((line, i) => (
            <Line key={i} text={line} from={from} />
          ))}
        </div>
        {tags.length > 0 ? (
          <div className="tags">
            {tags.map((t) => (
              <span key={t} className="tag">
                {t}
              </span>
            ))}
          </div>
        ) : null}
        {children}
      </div>
    </div>
  );
}
