import { useCallback, useEffect, useState } from "react";

import { Button } from "../../design";
import * as t from "./talkApi";

// STUDIO2 F1 (design board 3): every change is a step. Go back to any, compare with now, discard the draft, or pull a sent draft back.
export default function HistoryDrawer({ pid, did, canWithdraw, canDiscard, onChanged, onDiscard, onClose }: {
  pid: string; did: string; canWithdraw: boolean; canDiscard: boolean; onChanged: () => void; onDiscard: () => void; onClose: () => void;
}) {
  const [h, setH] = useState<{ steps: t.Step[]; now: number } | null>(null);
  const [diff, setDiff] = useState<{ n: number; c: t.Compare } | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { t.getHistory(pid, did).then(setH, () => setErr("The history did not load. Please try again.")); }, [pid, did]);
  useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>) => { setErr(""); try { await fn(); onChanged(); load(); } catch { setErr("That did not go through. Please try again."); } };
  const list = h ? [...h.steps].sort((a, b) => b.n - a.n) : [];
  return (
    <aside aria-label="History" className="b7-panel b8-tools" style={{ margin: "8px 0" }}>
      <h3 style={{ marginTop: 0 }}>Every change is a step</h3>
      <p className="ds-muted">Nothing is lost. Go back to any step, compare one with now, or start over.</p>
      {err ? <p role="alert">{err}</p> : null}
      <ol aria-label="Steps" style={{ listStyle: "none", padding: 0, display: "grid", gap: 6 }}>
        {list.map((s) => (
          <li key={s.n}>
            {s.n} · {s.by}{s.said ? `: "${s.said}"` : ""} · {s.summary} <span className="ds-muted">{s.at}</span>{" "}
            {s.n === h!.now ? <strong>Now</strong> : <>
              <Button onClick={() => void act(() => t.restore(pid, did, s.n))}>Go back here</Button>{" "}
              <Button onClick={() => void t.compare(pid, did, s.n).then((c) => setDiff({ n: s.n, c }), () => setErr("The comparison did not load."))}>Compare with now</Button></>}
          </li>))}
      </ol>
      {diff ? (
        <div role="group" aria-label={`Step ${diff.n} compared with now`}>
          <strong>Step {diff.n} against now</strong>
          <ul>
            {diff.c.added.map((x) => <li key={"a" + x}>Added since: {x}</li>)}
            {diff.c.removed.map((x) => <li key={"r" + x}>Removed since: {x}</li>)}
            {diff.c.changed.map((x) => <li key={"c" + x}>Changed since: {x}</li>)}
            {!diff.c.added.length && !diff.c.removed.length && !diff.c.changed.length ? <li>No difference.</li> : null}
          </ul>
        </div>) : null}
      <h4>This draft</h4>
      {canDiscard ? <p><Button onClick={onDiscard}>Discard draft</Button> <span className="ds-muted">Any draft you started, at any time. A draft untouched for 14 days moves to Archived on its own.</span></p> : null}
      {canWithdraw ? <p><Button onClick={() => void act(() => t.withdraw(pid, did))}>Withdraw from approval</Button> <span className="ds-muted">Pulls a sent draft back to keep editing.</span></p> : null}
      <Button onClick={onClose}>Close history</Button>
    </aside>
  );
}
