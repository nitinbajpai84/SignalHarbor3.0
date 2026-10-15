import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import { answerOwnerQuestion, type OwnerQuestion } from "../api";

const WORDS = {
  title: "Questions for you",
  help: "Someone asked for your answer to these. Write it in your own words; it is recorded on the question and the person who asked decides what changes in the definition.",
  label: (q: string) => `Your answer: ${q}`,
  send: "Send this answer",
  done: "Thank you. That question is settled.",
  failed: "That could not be sent. Please try again.",
  signIn: "Sign in to answer",
  signInNote: "You have an account, so please sign in to answer this one.",
};

/** M2-E1: the questions an organiser put to this owner, each with a text reply. Worded for the owner: a question that would name something
 * hidden from them reads generically. The reply settles the item and is recorded as the owner's answer; it never rewrites a definition by itself. */
export default function OwnerQuestions({ token, questions, locked }: { token: string; questions: OwnerQuestion[]; locked: boolean }) {
  const [open, setOpen] = useState(questions);
  const [text, setText] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [thanks, setThanks] = useState(false);
  if (open.length === 0 && !thanks) return null;
  const send = async (q: OwnerQuestion) => {
    setProblem(null);
    try {
      setOpen((await answerOwnerQuestion(token, q.kpi_id, q.ambiguity_id, text[q.ambiguity_id] ?? "")).questions);
      setThanks(true);
    } catch (e) {
      setProblem(e instanceof ApiError && e.message && e.status < 500 ? e.message : WORDS.failed);
    }
  };
  return (
    <Panel title={WORDS.title}>
      <p className="n-e1-def-note">{WORDS.help}</p>
      <ul className="m1-list">
        {open.map((q) => (
          <li key={q.ambiguity_id}>
            <strong>{q.kpi_name}</strong>
            <p>{q.text}</p>
            {q.needs_sign_in ? (
              <p>
                <span className="n-muted">{WORDS.signInNote}</span>{" "}
                <a className="n-btn sm primary" href={`/login?next=${encodeURIComponent(window.location.pathname)}`}>{WORDS.signIn}</a>
              </p>
            ) : null}
            {q.needs_sign_in ? null : <textarea className="n-input" rows={2} aria-label={WORDS.label(q.text)} value={text[q.ambiguity_id] ?? ""} disabled={locked} onChange={(e) => setText((t) => ({ ...t, [q.ambiguity_id]: e.target.value }))} />}
            {q.needs_sign_in ? null : (
              <button type="button" className="n-btn sm primary" disabled={locked || !(text[q.ambiguity_id] ?? "").trim()} onClick={() => void send(q)}>
                {WORDS.send}
              </button>
            )}
          </li>
        ))}
      </ul>
      {thanks ? <p role="status" className="n-muted">{WORDS.done}</p> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </Panel>
  );
}
