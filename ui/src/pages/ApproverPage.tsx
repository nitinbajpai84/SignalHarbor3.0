import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, guestSend } from "../api/client";
import BrandMark from "../components/BrandMark";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import ThemeControl from "../components/ThemeControl";
import { copy } from "../copy";
import { decideCharter, getApproverDraft, type ApproverDraft } from "../modules/m1_intent/api";
import CharterPaper from "../modules/m1_intent/CharterPaper";
import { m1Charter as T } from "../modules/m1_intent/copy";
import { useLoad } from "../modules/m1_intent/useLoad";
import { approverCopy as C, closeCopy } from "../intents/views/closeCopy";

interface ClosureDraft {
  title: string; purpose: string; role: string; approver_name: string; expires_at: string; sentences: string[];
  outcome: { label: string; value: string }[]; missing: string[]; next: { kind: string; title: string; reason: string }[];
}
const CLOSURE = "/api/modules/m1_intent/approver/closure";
const closure = (token: string) => token.startsWith("ci.");

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

/** The words for a refused link: too many tries gets its own sentence; every other refusal is the server's plain sentence. */
const linkProblem = (e: unknown): string =>
  e instanceof ApiError ? (e.status === 429 ? T.tooMany : e.status !== 0 && e.status < 500 && e.message ? e.message : T.linkMissing) : T.linkMissing;

/**
 * The page behind /approve/<token> (M1-26, deck slide 14). No sign-in and no module chrome: it shows one draft and asks
 * one question. The token is read from the address, sent only in a header, and never shown or stored.
 */
export default function ApproverPage() {
  const { token = "" } = useParams();
  const { state, data, message } = useLoad<ApproverDraft | ClosureDraft>(
    () => (closure(token) ? guestSend<ClosureDraft>("POST", CLOSURE, undefined, token) : getApproverDraft(token))
      .catch((e: unknown) => Promise.reject(new ApiError(linkProblem(e), 404))),
    "approver",
  );
  return (
    <>
      <header className="n-topbar">
        <div className="n-brand">
          <BrandMark named={false} size={36} />
          <strong>{copy.product}</strong>
        </div>
        <div className="n-topbar-spacer" />
        <div className="n-topbar-actions">
          <ThemeControl />
        </div>
      </header>
      <main className="page" style={{ maxWidth: 760, margin: "0 auto" }}>
        <h1 className="n-page-title">{closure(token) ? C.title : T.approverPageTitle}</h1>
        <ScreenState state={state} message={message} >
          {data ? <Decision token={token} draft={data} /> : null}
        </ScreenState>
      </main>
    </>
  );
}

function ClosurePaper({ d }: { d: ClosureDraft }) {
  return (
    <>
      <p>{C.intro(d.approver_name, d.role)}</p>
      <Panel title={d.title}>
        <p>{d.purpose}</p>
        <h3>{C.summary}</h3>
        {d.sentences.map((s, i) => <p key={i}>{s}</p>)}
        <h3>{C.outcome}</h3>
        <dl>{d.outcome.map((l, i) => <div key={i}><dt>{l.label}</dt><dd>{l.value}</dd></div>)}</dl>
        {d.missing.length > 0 && <p className="n-e1-def-note">{C.missing(d.missing.join(", "))}</p>}
        <h3>{C.next}</h3>
        <ul>{d.next.map((n, i) => <li key={i}><strong>{closeCopy.kind[n.kind] ?? n.kind}</strong>{n.title ? `: ${n.title}` : ""}. {n.reason}</li>)}</ul>
      </Panel>
    </>
  );
}

function Decision({ token, draft }: { token: string; draft: ApproverDraft | ClosureDraft }) {
  const isClosure = closure(token);
  const [comment, setComment] = useState("");
  const [done, setDone] = useState<"approve" | "decline" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function decide(decision: "approve" | "decline") {
    if (decision === "decline" && comment.trim() === "") {
      setProblem(isClosure ? C.commentHelp : T.commentHelp);
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      if (isClosure) await guestSend("POST", CLOSURE, { decision, comment: comment.trim() }, token);
      else await decideCharter(token, decision, comment.trim());
      setDone(decision);
    } catch (e) {
      setProblem(linkProblem(e));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p role="status" className="state n-muted">
        {done === "approve" ? (isClosure ? C.approved : T.approved) : isClosure ? C.declined : T.declined}
      </p>
    );
  }
  return (
    <>
      {isClosure ? <ClosurePaper d={draft as ClosureDraft} /> : (
        <>
          <p>{T.approverIntro(draft.approver_name)}</p>
          <CharterPaper doc={draft as ApproverDraft} status="awaiting_approver" />
        </>
      )}
      <Panel title={isClosure ? C.question : T.question}>
        <label>
          {T.commentLabel}
          <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        <p className="n-e1-def-note">{isClosure ? C.commentHelp : T.commentHelp}</p>
        <div className="m1-actions">
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => void decide("approve")}>
            {T.approve}
          </button>
          <button type="button" className="n-btn" disabled={busy} onClick={() => void decide("decline")}>
            {isClosure ? C.sendBack : T.decline}
          </button>
        </div>
        <p className="n-e1-def-note">{T.linkUntil(when(draft.expires_at))}</p>
        {problem ? (
          <p role="alert" className="state state-error">
            {problem}
          </p>
        ) : null}
      </Panel>
    </>
  );
}
