import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import GuestShell from "../components/GuestShell";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { confirmOwnerPart, confirmOwnerTechnical, getOwnerForm, saveOwnerAnswers, submitOwnerAnswers, uploadOwnerSample, type AnswerRecord, type OwnerForm } from "../modules/m2_baseline/api";
import { SignedBanner } from "../modules/m2_baseline/BaselineSteps";
import { m2Form as T } from "../modules/m2_baseline/copy";
import OwnerQuestions from "../modules/m2_baseline/requests/OwnerQuestions";
import OwnerTechnical from "../modules/m2_baseline/requests/OwnerTechnical";
import QuestionnaireForm from "../modules/m2_baseline/requests/QuestionnaireForm";
import { useLoad } from "../modules/m1_intent/useLoad";

/** The words for a refused link: too many tries gets its own sentence; every other refusal is the server's plain sentence. */
const linkProblem = (e: unknown): string =>
  e instanceof ApiError ? (e.status === 429 ? T.tooMany : e.status !== 0 && e.status < 500 && e.message ? e.message : T.noPage) : T.noPage;

/**
 * The page behind /answer/<token> (M2-07, deck slide 6). No sign-in and no module chrome: it shows one person's measures and
 * their questions. The token is read from the address, sent only in a header, and never shown or stored.
 */
export default function OwnerAnswerPage() {
  const { token = "" } = useParams();
  const { state, data, message } = useLoad<OwnerForm>(() => getOwnerForm(token).catch((e: unknown) => Promise.reject(new ApiError(linkProblem(e), 404))), "owner-answers");
  return (
    <GuestShell title={T.ownerTitle}>
      <ScreenState state={state} message={message}>
        {data ? <Answers token={token} form={data} /> : null}
      </ScreenState>
    </GuestShell>
  );
}

function Answers({ token, form }: { token: string; form: OwnerForm }) {
  const [records, setRecords] = useState<Record<string, AnswerRecord | null>>(() => Object.fromEntries(form.kpis.map((k) => [k.id, k.answers])));
  const [done, setDone] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [parts, setParts] = useState(form.confirmable ?? []);
  const [confirmProblem, setConfirmProblem] = useState<string | null>(null);

  async function confirm(kpiId: string, part: string) {
    setConfirmProblem(null);
    try {
      setParts((await confirmOwnerPart(token, kpiId, part)).confirmable);
    } catch (e) {
      setConfirmProblem(e instanceof ApiError && e.message && e.status < 500 ? e.message : T.confirmFailed);
    }
  }

  async function send() {
    setBusy(true);
    setProblem(null);
    try {
      await submitOwnerAnswers(token);
      setDone(true);
    } catch (e) {
      setProblem(linkProblem(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p>{T.ownerIntro(form.owner_name, form.role)}</p>
      <p className="n-e1-def-note">
        {T.dontKnow} {T.lensHint}
      </p>
      <p className="n-e1-def-note">{T.untilNote(form.expires_at)}</p>
      {form.signed ? <SignedBanner help={false} /> : null}
      {done ? (
        <p role="status" className="state n-muted">
          {T.sentThanks}
        </p>
      ) : null}
      <fieldset disabled={form.signed === true} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
      {form.kpis.map((k, i) => (
        <Panel key={k.id} title={T.measure(i + 1, form.kpis.length, k.name)}>
          <QuestionnaireForm
            spec={form.questionnaire}
            measure={k.name}
            initial={records[k.id] ?? null}
            onSave={async (answers) => (await saveOwnerAnswers(token, k.id, answers)).saved}
            onSample={async (file) => (await uploadOwnerSample(token, k.id, file)).saved}
            onSaved={(rec) => setRecords((r) => ({ ...r, [k.id]: rec }))}
          />
        </Panel>
      ))}
      <OwnerQuestions token={token} questions={form.questions ?? []} locked={form.signed === true} />
      <OwnerTechnical technical={form.technical ?? []} onConfirm={async (kpi) => (await confirmOwnerTechnical(token, kpi)).technical} signIn={form.technical_sign_in ?? []} signInPath={form.sign_in_path} locked={form.signed === true} />
      {parts.length > 0 ? (
        <Panel title={T.confirmTitle}>
          <p className="n-e1-def-note">{T.confirmHelp}</p>
          <ul className="m1-list">
            {parts.map((p) => {
              const measure = form.kpis.find((k) => k.id === p.kpi_id)?.name ?? "";
              return (
                <li key={`${p.kpi_id}-${p.part}`}>
                  {T.confirmPart(measure, p.label)}{" "}
                  {p.confirmed ? (
                    <strong>{T.confirmedDone}</strong>
                  ) : (
                    <button type="button" className="n-btn sm" aria-label={`${T.confirmButton}: ${T.confirmPart(measure, p.label)}`} onClick={() => void confirm(p.kpi_id, p.part)}>
                      {T.confirmButton}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          {confirmProblem ? (
            <p role="alert" className="state state-error">
              {confirmProblem}
            </p>
          ) : null}
        </Panel>
      ) : null}
      {(form.sign_in_parts ?? []).length > 0 && form.sign_in_path ? (
        <Panel title={T.signInTitle}>
          <p className="n-e1-def-note">{T.signInHelp}</p>
          <a className="n-btn" href={`/login?next=${encodeURIComponent(form.sign_in_path)}`}>
            {T.signInButton}
          </a>
        </Panel>
      ) : null}
      <Panel>
        <div className="m1-actions">
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => void send()}>
            {busy ? T.sending : T.send}
          </button>
        </div>
        {problem ? (
          <p role="alert" className="state state-error">
            {problem}
          </p>
        ) : null}
      </Panel>
      </fieldset>
    </>
  );
}
