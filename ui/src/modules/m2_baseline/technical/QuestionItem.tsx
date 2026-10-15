import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import StatusPill from "../../../components/StatusPill";
import { notifyChanged } from "../api";
import { m2Tech as t } from "./copy";
import { acceptAmbiguity, answerAmbiguity, askOwner, LINK_PARTS, type Ambiguity, type TechKpi, type TechnicalScreen } from "./technicalApi";

interface Props {
  baselineId: string;
  item: Ambiguity;
  /** The measure the question is about: the current wording of its parts is shown for editing when an answer changes one. */
  kpi?: TechKpi;
  locked: boolean;
  /** Only the organiser or the sponsor may accept a risk. */
  governor: boolean;
  onScreen: (s: TechnicalScreen) => void;
  /** Show the measure's name (on the whole-baseline tab); the measure's own list does not. */
  withMeasure?: boolean;
}

const TONE = { open: "warning", settled: "success", accepted: "info" } as const;

/** One open question: what is unclear, the question, Lens's suggested answer (a suggestion, never applied by itself), and the three ways to
 * deal with it: answer it, ask the owner, or accept it as a known risk with a reason. */
export default function QuestionItem({ baselineId, item, kpi, locked, governor, onScreen, withMeasure }: Props) {
  const [mode, setMode] = useState<"answer" | "accept" | null>(null);
  const [text, setText] = useState("");
  const [part, setPart] = useState("");
  const [wording, setWording] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState<{ owner: string; body: string } | null>(null);
  const open = item.status === "open";
  // the parts an answer may change: the business definition and the text parts (a link to the catalogue is made with Edit, not by an answer)
  const choices = [
    ...(kpi ? [{ id: "definition", label: t.partDefinition, text: kpi.definition ?? "" }] : []),
    ...(kpi?.parts ?? []).filter((p) => !LINK_PARTS.includes(p.part) && !p.withheld).map((p) => ({ id: p.part, label: p.label, text: p.cell.mark === "unknown" ? "" : String(p.cell.value ?? "") })),
  ];
  const current = (id: string) => choices.find((c) => c.id === id)?.text ?? "";
  const choose = (id: string) => {
    setPart(id);
    setWording(current(id)); // pre-filled with the current text for the person to edit
  };
  const startAnswer = () => {
    setMode("answer");
    setText(item.suggestion?.value ?? "");
    choose(choices.some((c) => c.id === item.suggested_part) ? (item.suggested_part ?? "") : "");
  };

  const run = async (p: Promise<TechnicalScreen>) => {
    setBusy(true);
    setError(null);
    try {
      const s = await p;
      if (s.asked) setEmail({ owner: s.asked.owner, body: s.asked.email.body });
      setMode(null);
      setText("");
      onScreen(s);
      notifyChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="n-suggest-block" aria-label={`${t.kind[item.kind]}: ${item.question}`}>
      <div className="n-flex wrap">
        <StatusPill tone={TONE[item.status]}>{t.status[item.status]}</StatusPill>
        <StatusPill tone="muted">{t.kind[item.kind]}</StatusPill>
        {withMeasure ? <strong>{item.kpi_name || t.tab.across}</strong> : null}
        <span className="n-muted">{t.raisedBy(item.raised_by)}</span>
      </div>
      {item.reopened ? <p role="note"><strong>{item.reopened}</strong>{item.history?.length ? ` (${t.before(item.history[item.history.length - 1]?.resolution ?? "")})` : ""}</p> : null}
      <p>{item.text}</p>
      <p><strong>{item.question}</strong></p>
      {item.suggestion && open ? (
        <p className="n-muted">
          {t.suggestion}: {item.suggestion.value}
        </p>
      ) : null}
      {item.asked && open ? <p className="n-muted">{t.asked(item.asked.owner)}</p> : null}
      {!open ? (
        <p>
          {item.resolution} <span className="n-muted">{item.auto ? t.closedAuto : item.by && item.at ? t.settledBy(item.by, item.at) : ""}</span>
        </p>
      ) : null}
      {open && item.derived ? (
        <p className="n-muted">
          {t.decideInGovernance} <Link to={`/modules/m2_baseline/governance/${baselineId}`}>{t.tabGovernance}</Link>
        </p>
      ) : null}
      {open && !item.derived ? (
        <>
          <div className="n-flex wrap">
            <button type="button" className="n-btn sm primary" disabled={locked || busy} onClick={startAnswer}>{t.answer}</button>
            <button type="button" className="n-btn sm" disabled={locked || busy} onClick={() => void run(askOwner(baselineId, item.kpi_id, item.id))}>{t.ask}</button>
            {governor ? <button type="button" className="n-btn sm" disabled={locked || busy} onClick={() => { setMode("accept"); setText(""); }}>{t.accept}</button> : null}
          </div>
          {mode === "answer" ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="n-flex wrap">
                <textarea className="n-input" rows={2} aria-label={t.answerLabel} value={text} onChange={(e) => setText(e.target.value)} />
                {item.suggestion ? <button type="button" className="n-btn sm" onClick={() => setText(item.suggestion?.value ?? "")}>{t.useSuggestion}</button> : null}
              </div>
              <label className="n-muted">
                {t.whichPart}{" "}
                <select className="n-select" aria-label={t.whichPart} value={part} onChange={(e) => choose(e.target.value)}>
                  <option value="">{t.justRecord}</option>
                  {choices.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              </label>
              {part ? (
                <>
                  <textarea className="n-input" rows={4} aria-label={t.wordingLabel} value={wording} onChange={(e) => setWording(e.target.value)} />
                  <span className="n-muted">{t.wordingHelp}</span>
                </>
              ) : null}
              <div>
                <button type="button" className="n-btn sm primary" disabled={busy || !text.trim() || (!!part && !wording.trim())} onClick={() => void run(answerAmbiguity(baselineId, item.kpi_id, item.id, text, part || undefined, part ? wording : undefined))}>{t.answerSave}</button>
              </div>
            </div>
          ) : null}
          {mode === "accept" ? (
            <div className="n-flex wrap">
              <input className="n-input" aria-label={t.reasonLabel} placeholder={t.reasonLabel} value={text} onChange={(e) => setText(e.target.value)} />
              <button type="button" className="n-btn sm primary" disabled={busy || !text.trim()} onClick={() => void run(acceptAmbiguity(baselineId, item.kpi_id, item.id, text))}>{t.acceptSave}</button>
            </div>
          ) : null}
        </>
      ) : null}
      {email ? (
        <div role="status">
          <p>{t.asked(email.owner)} {t.askedEmail}</p>
          <pre style={{ whiteSpace: "pre-wrap" }}>{email.body}</pre>
        </div>
      ) : null}
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
    </li>
  );
}
