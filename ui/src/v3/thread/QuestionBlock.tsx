import type { Question } from "../api";
import "./trust.css";

const quoted = /^"([\s\S]*)" \(([^)]*)\)$/;

/** One Decision 2 question. `judge:` = two checks disagreed (amber, both answers + Something else); `doc:` = a line in a document to confirm; else a plain question. */
export default function QuestionBlock({ q, value, onPick, onElse }: { q: Question; value?: string; onPick: (v: string) => void; onElse?: () => void }) {
  const pick = (o: string) => { onPick(o); if (q.id.startsWith("judge:") && o.startsWith("Something else")) onElse?.(); };
  if (q.id.startsWith("doc:")) {
    return (
      <div className="t3-q">
        <span>{q.text}</span>
        {q.options.map((o) => {
          const m = quoted.exec(o);
          return m ? (
            <div key={o} className="t3-quote-opt">
              <blockquote className="t3-quote">{m[1]}<cite>{m[2]}</cite></blockquote>
              <div><button type="button" className={value === o ? "go" : undefined} aria-pressed={value === o} onClick={() => pick(o)}>Use this line</button></div>
            </div>
          ) : (
            <div key={o}><button type="button" className={value === o ? "go" : undefined} aria-pressed={value === o} onClick={() => pick(o)}>Keep as context only</button></div>
          );
        })}
      </div>
    );
  }
  const unsure = q.id.startsWith("judge:");
  return (
    <div className={`t3-q${unsure ? " unsure" : ""}`}>
      {unsure && <span className="v3-pill needs">I am not sure, two checks disagree</span>}
      <span>{q.text}</span>
      <div className={unsure ? "t3-opts" : "v3-row"}>
        {q.options.map((o) => <button key={o} type="button" className={value === o ? "go" : undefined} aria-pressed={value === o} onClick={() => pick(o)}>{o}</button>)}
      </div>
      {q.assumed && <small className="v3-mute">I have assumed {q.assumed}; change it if I am wrong.</small>}
    </div>
  );
}
