import { Link } from "react-router-dom";

import StepIcon from "./StepIcons";
import { STEPS, stepPath, type StepId } from "./steps";
import type { Mark } from "./progress";
import "./b9.css";

const SAY: Record<Mark, string> = { done: "done", here: "in progress", waiting: "waiting", todo: "not started" };

/** The small four-step strip on a project card: a bar per step, its icon and name. */
export function MiniStrip({ marks }: { marks: Mark[] }) {
  return (
    <ol className="b9-mini" aria-label="Progress">
      {STEPS.map((s, i) => (
        <li key={s.id} data-mark={marks[i]}><span><StepIcon step={s.id} size={14} />{s.name}</span><span className="b9-sr">{SAY[marks[i] ?? "todo"]}</span></li>
      ))}
    </ol>
  );
}

/** The rail on every step page: the four steps, each one a link, the current one marked. */
export function Rail({ pid, current, statuses }: { pid: string; current: StepId; statuses?: string[] }) {
  return (
    <ol className="b9-rail" aria-label="Project steps">
      {STEPS.map((s, i) => (
        <li key={s.id} data-current={s.id === current}>
          {pid ? <Link to={stepPath(pid, s.id)} aria-current={s.id === current ? "step" : undefined}><StepIcon step={s.id} size={16} />{s.n} · {s.name.toUpperCase()}</Link>
            : <a aria-current={s.id === current ? "step" : undefined} aria-disabled={s.id !== current}><StepIcon step={s.id} size={16} />{s.n} · {s.name.toUpperCase()}</a>}
          <small>{s.id === current ? "You are here" : statuses?.[i] ? "" : s.line.split(".")[0]}{statuses?.[i] ? <>{s.id === current ? " · " : ""}<span className="b9-status">{statuses[i]}</span></> : null}</small>
        </li>
      ))}
    </ol>
  );
}
