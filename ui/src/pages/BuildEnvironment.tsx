import { useState } from "react";
import { Link } from "react-router-dom";

import { apiSend } from "../api/client";
import { Button, Footnote, PageFrame, SideCard } from "../design";
import { BuildState, useLoad } from "./BuildCentre";

// The environment check (BUILD-CENTRE-SPEC 3.1, sh_platform/build_env.py): five questions, each with its prefilled answer, its mark and its source.
// Confirm one, or all five in one pass; a confirmed answer comes back Stated with the person's name.

interface Cell { value: string | null; mark: "stated" | "guessed" | "unknown"; by: string; from: string }
interface Question { key: string; question: string; answer: Cell }
interface Env { questions: Question[] }
const MARK = { stated: "Stated", guessed: "Guessed", unknown: "Unknown" } as const;

export default function BuildEnvironment() {
  const { data, state, retry, setData } = useLoad<Env>("/api/company/build/environment");
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const [changing, setChanging] = useState<string[]>([]);
  const qs = data?.questions ?? [];
  const text = (q: Question) => texts[q.key] ?? q.answer.value ?? "";
  const confirm = async (keys: string[]) => {
    try {
      const got = await apiSend<Env>("PUT", "/api/company/build/environment", { answers: Object.fromEntries(qs.filter((q) => keys.includes(q.key)).map((q) => [q.key, text(q).trim()])) });
      setData(got);
      setTexts((t) => Object.fromEntries(Object.entries(t).filter(([k]) => !keys.includes(k))));
      setChanging((c) => c.filter((k) => !keys.includes(k)));
      setErr("");
    } catch { setErr("That answer could not be saved. Try again in a moment."); }
  };
  const stated = qs.filter((q) => q.answer.mark === "stated").length;
  const allFilled = qs.length > 0 && qs.every((q) => text(q).trim());
  // a stated answer nobody has changed needs no second confirmation
  const done = (q: Question) => q.answer.mark === "stated" && text(q).trim() === (q.answer.value ?? "") && !changing.includes(q.key);
  const allDone = qs.length > 0 && qs.every(done);
  return (
    <PageFrame
      crumbs={<Link className="ds-link" to="/centre/build">Build centre</Link>}
      title="Environment check"
      subline="Five questions, prefilled from the company profile. Confirm each answer, or change it first."
      actions={state === "populated" ? <Button variant="primary" disabled={!allFilled || allDone} onClick={() => void confirm(qs.map((q) => q.key))}>{allDone ? "All confirmed" : "Confirm all"}</Button> : undefined}
      aside={
        <>
          <SideCard title="Confirmed" action={{ label: "Review the blueprint", href: "/centre/build/blueprint" }}>
            <p>{stated} of {qs.length || 5} answers stated by a person.</p>
          </SideCard>
          <SideCard title="Why these five">
            <p>The answers set where the warehouse lives and what runs the pipelines in the blueprint. Whether a warehouse exists today decides whether the estate scan runs.</p>
          </SideCard>
          <Footnote>Guessed answers come from the company profile; Stated answers were confirmed here.</Footnote>
        </>
      }
    >
      <BuildState state={state} onRetry={retry}>
        {err ? <p role="alert" className="ds-warn">{err}</p> : null}
        {qs.map((q) => (
          <div key={q.key} className="ds-card ds-side">
            <label htmlFor={q.key} className="ds-side__title">{q.question}</label>
            {done(q) ? <p id={q.key}><strong>{q.answer.value}</strong></p> : null}
            <p className={q.answer.mark === "unknown" ? "ds-warn" : undefined}>{MARK[q.answer.mark]} · {q.answer.from}{q.answer.mark === "stated" ? ` · ${q.answer.by}` : ""}</p>
            {done(q) ? (
              <span><Button onClick={() => setChanging([...changing, q.key])} aria-label={`Change: ${q.question}`}>Change</Button></span>
            ) : (
              <div className="ds-comment__decide">
                <input id={q.key} value={text(q)} onChange={(e) => setTexts({ ...texts, [q.key]: e.target.value })} maxLength={300} />
                <Button variant="primary" disabled={!text(q).trim()} onClick={() => void confirm([q.key])} aria-label={`Confirm: ${q.question}`}>Confirm</Button>
              </div>
            )}
          </div>
        ))}
      </BuildState>
    </PageFrame>
  );
}
