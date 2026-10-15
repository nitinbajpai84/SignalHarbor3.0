import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ApiError, Refused } from "../../api/client";
import { Button, EmptyState, PageFrame, Pill, SideCard, Strip } from "../../design";
import { accept, fileName, getExtraction, getQueue, type Extraction, type Queue } from "./api";

// X5 review queue: a document a check failed on. The passage with the field's line highlighted, a box per value to correct, one
// click to accept. A corrected value becomes a worked example in the spec; North never guesses a value.
type Load = "loading" | "error" | "refused" | "ready";

function Review({ x, onDone }: { x: Extraction; onDone: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(x.values).map(([k, v]) => [k, v.value])));
  const [failed, setFailed] = useState("");
  const bad = new Set(x.checks.filter((c) => !c.ok).map((c) => c.field));
  const marked = new Set(Object.values(x.values).map((v) => v.line).filter((n): n is number => n !== null));
  const send = () => {
    const changed = Object.fromEntries(Object.entries(vals).filter(([k, v]) => v !== (x.values[k]?.value ?? "")));
    accept(x.doc_id, changed).then(onDone).catch((e: unknown) => setFailed(e instanceof Error ? e.message : "Could not save. Try again."));
  };
  return (
    <SideCard title={`${fileName(x.file)} · ${x.type_name}, version ${x.version}`}>
      <ul className="ds-soft">
        {x.checks.filter((c) => !c.ok).map((c) => <li key={`${c.field}-${c.kind}`}><Pill tone="failed">{c.field}</Pill> {c.why}</li>)}
      </ul>
      <div aria-label="Document passage" className="ds-passage">
        {x.lines.map((l, i) => <div key={i}>{marked.has(i) ? <mark>{l}</mark> : l}</div>)}
      </div>
      {Object.keys(x.values).map((k) => (
        <p key={k}>
          <label>{k}{bad.has(k) ? " (needs a look)" : ""}{" "}
            <input aria-label={`Value for ${k}`} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
          </label>
        </p>
      ))}
      <Button variant="primary" onClick={send}>Accept</Button>
      {failed && <p role="alert" className="ds-warn">{failed}</p>}
    </SideCard>
  );
}

export default function ReviewPage() {
  const [load, setLoad] = useState<Load>("loading");
  const [queue, setQueue] = useState<Queue | null>(null);
  const [open, setOpen] = useState<Extraction | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    getQueue()
      .then(async (q) => {
        const first = q.items[0] ? await getExtraction(q.items[0].doc_id) : null;
        if (live) { setQueue(q); setOpen(first); setLoad("ready"); }
      })
      .catch((e: unknown) => { if (live) setLoad(e instanceof Refused || (e instanceof ApiError && e.status === 403) ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const pick = (docId: string) => { getExtraction(docId).then(setOpen).catch(() => setLoad("error")); };

  const frame = (body: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Documents to look at" crumbs="Build · Extraction" subline={queue?.line ?? "Values a check could not confirm."}>{body}</PageFrame>
    </div>
  );
  if (load === "loading") return frame(<EmptyState title="Reading the queue" lines={["The documents that need a look are on their way."]} />);
  if (load === "error") return frame(<><EmptyState title="The queue could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={retry}>Try again</Button></>);
  if (load === "refused" || !queue) return frame(<EmptyState title="The review queue is for the data engineer" lines={["The analyst or the company admin looks at documents."]} />);
  if (!queue.items.length) return frame(<EmptyState title="Nothing needs a look" lines={["When a document does not match its spec, it waits here."]} />);
  return frame(
    <Strip label={queue.line} tone="amber">
      <p>{queue.items.map((i) => <Button key={i.doc_id} onClick={() => pick(i.doc_id)}>{fileName(i.file)}</Button>)}</p>
      {open && <Review key={open.doc_id} x={open} onDone={retry} />}
    </Strip>,
  );
}
