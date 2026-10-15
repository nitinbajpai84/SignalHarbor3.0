import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../../api/client";
import { Button, EmptyState, Pill } from "../../design";
import { useSession } from "../../useSession";
import { useLoad, type LoadState } from "../BuildCentre";
import "./chain.css";
import { askModel, fileModel, getModelDraft, modelDraftPath, type ModelDraft } from "./spanApi";
import { plain, sc } from "./spanCopy";

/** What a refused or failed action says: the server's own sentence, or who may do it when the answer was a 403. */
export const sayWhy = (e: unknown): string => (e instanceof ApiError ? (e.status === 403 ? sc.notArchitect : e.message) : sc.error);

/** Loading, error and refused for one Span panel; the panel's own empty and populated states go inside. */
export function SpanGate({ state, retry, title, children }: { state: LoadState; retry: () => void; title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="ds-card bc-row" style={{ marginBottom: "var(--ds-s3)" }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
      {state === "loading" ? <p role="status" aria-busy="true" className="bc-note">{sc.loading}</p> : null}
      {state === "refused" ? <p role="alert" className="bc-note">{sc.refused}</p> : null}
      {state === "error" ? <div role="alert"><p className="bc-note">{sc.error}</p><Button onClick={retry}>{sc.retry}</Button></div> : null}
      {state === "populated" ? children : null}
    </section>
  );
}

/** Room 1: Span's silver model and gold marts, built in a sandbox. Asking and filing are the architect's; the server says who that is. */
export default function SpanModelPanel() {
  const { data, state, retry, setData } = useLoad<ModelDraft>(modelDraftPath);
  const { user } = useSession();
  const [note, setNote] = useState("");
  const [revising, setRevising] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const draft = data?.state;
  useEffect(() => {
    if (draft !== "drafting") return;
    const t = setInterval(() => { getModelDraft().then(setData).catch(() => undefined); }, 3000);
    return () => clearInterval(t);
  }, [draft, setData]);

  const may = !!user?.roles.some((r) => r === "company_admin" || r === "analyst");
  const act = (go: () => Promise<ModelDraft>) => {
    setBusy(true);
    go().then((d) => { setData(d); setErr(""); setRevising(false); setNote(""); }).catch((e: unknown) => setErr(sayWhy(e))).finally(() => setBusy(false));
  };
  const has = !!draft && draft !== "none" && draft !== "drafting" && ["ready", "failed", "fallback", "filed"].includes(draft);
  const errors = (data?.errors ?? []).map(plain).filter(Boolean);

  return (
    <SpanGate state={state} retry={retry} title={sc.modelTitle}>
      <p className="bc-note">{sc.modelLine}</p>
      {draft === "drafting" ? <p role="status" className="bc-note">{sc.drafting}</p> : null}
      {!has && draft !== "drafting" ? <EmptyState title={data?.message ? plain(data.message) : sc.modelEmpty} lines={[]} /> : null}
      {draft === "fallback" ? <p role="status" className="ds-warn">{sc.fallback}</p> : null}
      {draft === "failed" ? <p role="alert" className="ds-warn">{data?.message ? plain(data.message) : sc.error}</p> : null}
      {draft === "failed" && errors.length ? (
        <div><strong>{sc.errorsTitle}</strong><ul className="bc-lines">{errors.map((x) => <li key={x}>{x}</li>)}</ul></div>
      ) : null}
      {draft === "ready" ? (
        <div>
          <p><Pill tone="draft">{sc.tag}</Pill> {data?.message ? plain(data.message) : null}</p>
          {data?.rounds ? <p className="bc-note">{sc.rounds(data.rounds)}</p> : null}
          {data?.counts?.length ? (
            <div><strong>{sc.builtTitle}</strong><ul className="bc-lines">{data.counts.map((c) => <li key={c.label}>{plain(c.label)}: {c.value ?? c.text ?? sc.notYet}</li>)}</ul></div>
          ) : null}
        </div>
      ) : null}
      {draft === "filed" && data?.filed ? <p role="status">{sc.filed(data.filed.version)}{data.filed.skipped.length ? ` ${sc.skipped}` : ""}</p> : null}
      {data?.open_questions?.length ? (
        <div><strong>{sc.questionsTitle}</strong><ul className="bc-lines">{data.open_questions.map((q) => <li key={q}>{plain(q)}</li>)}</ul></div>
      ) : null}
      {may && draft !== "drafting" ? (
        <>
          {has && revising ? (
            <label className="bc-field">{sc.reviseLabel}
              <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2} />
            </label>
          ) : null}
          <div className="bc-actions">
            {has && !revising ? <Button disabled={busy} onClick={() => setRevising(true)}>{sc.askRevise}</Button>
              : <Button disabled={busy} onClick={() => act(() => askModel(note.trim()))}>{has ? sc.send : sc.askModel}</Button>}
            {draft === "ready" && data?.id ? <Button variant="primary" disabled={busy} onClick={() => act(() => fileModel(data.id as string))}>{sc.file}</Button> : null}
          </div>
        </>
      ) : null}
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
    </SpanGate>
  );
}
