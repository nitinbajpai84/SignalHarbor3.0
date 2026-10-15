import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import ChatSection from "../../components/ChatSection";
import Icon from "../../components/Icon";
import AgentPanel from "../../components/AgentPanel";
import AskBox from "../../components/AskBox";
import { copy } from "../../copy";
import { askNira, type NiraKind } from "./api";
import { loadToken } from "./room/guestToken";
import { m1Companion as c, m1Nira, m1Voice, type CompanionStage } from "./copy";
import { VoiceBar, combineText, playReply, useVoice } from "./voice/VoiceControls"; // M1-P06

/** A button for the next step the person may take: a route that already exists, or something the screen does itself. */
export interface NiraAction {
  label: string;
  to?: string;
  onClick?: () => void;
}

interface Props {
  /** Empty while a draft is not saved yet: Nira then explains the screen but cannot be asked. */
  sessionId: string;
  stage: CompanionStage;
  actions?: NiraAction[];
  /** Called after a question was sent, so the screen can show that this person asked. */
  onAsked?: () => void;
  /** Goes up by one each time the stage timer reaches its warning time: she then gives her one-minute warning. */
  warning?: number;
}

type Turn = { who: "human" | "nira"; text: string };

/**
 * Nira, docked on the right of every module 1 screen: the earlier companion's panel (js/companion.js). Four collapsible
 * sections (about, what is needed, what am I looking at, suggested actions), the conversation, and the ask box. Her fixed
 * messages and her answers come from the existing /nira route; the rest is wording per stage in copy.ts.
 */
export default function NiraDock({ sessionId, stage, actions = [], onAsked, warning = 0 }: Props) {
  const { voice, setOn } = useVoice(sessionId);
  const info = c.stages[stage];
  const guest = loadToken(sessionId) !== null; // a person who joined by link has no account: nothing here leads out of the session
  const [welcome, setWelcome] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const spoken = useRef(false);
  spoken.current = voice?.available === true && voice.on;

  const say = (text: string) => {
    setTurns((t) => [...t, { who: "nira", text }]);
    if (spoken.current) void playReply(sessionId, text);
  };
  const run = (kind: NiraKind, text?: string) => {
    if (sessionId === "") {
      setProblem(m1Nira.noSession);
      return;
    }
    if (text !== undefined) setTurns((t) => [...t, { who: "human", text }]);
    setBusy(true);
    setProblem(null);
    askNira(sessionId, kind, text)
      .then((r) => {
        say(r.text);
        if (kind === "ask") onAsked?.();
      })
      .catch((e: unknown) => setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : copy.states.error))
      .finally(() => setBusy(false));
  };

  const welcomed = useRef(false);
  useEffect(() => {
    // Her welcome is read once when the screen opens. If she cannot answer, the section says so and nothing else changes.
    if (welcomed.current || sessionId === "") return;
    welcomed.current = true;
    askNira(sessionId, "welcome").then((r) => setWelcome(r.text), () => undefined);
  }, [sessionId]);
  useEffect(() => {
    if (warning > 0) run("warning");
  }, [warning]);
  useEffect(() => {
    log.current?.scrollIntoView?.({ block: "nearest" }); // the newest line stays in view
  }, [turns.length]);

  const submit = () => {
    if (question.trim() === "") {
      setProblem(m1Nira.needQuestion);
      return;
    }
    run("ask", question.trim());
    setQuestion("");
  };
  const next: NiraAction[] = [...actions, ...(sessionId === "" ? [] : [{ label: m1Nira.now, onClick: () => run("now") }])];

  return (
    <AgentPanel
      label={m1Nira.name}
      name="Nira"
      replies={turns.filter((t) => t.who === "nira").length}
      headExtra={
        sessionId === "" ? null : (
          // always there, as in the earlier panel; without speech it is switched off and says why
          <button
            type="button"
            className="n-btn"
            aria-pressed={voice?.available ? voice.on : false}
            disabled={!voice?.available}
            title={voice && !voice.available ? (voice.message ?? m1Voice.unavailable) : undefined}
            onClick={() => voice && void setOn(!voice.on)}
          >
            <Icon name="speaker" size={13} />
            {c.voiceMode}
          </button>
        )
      }
      footer={
        <>
          <AskBox value={question} onChange={setQuestion} onSubmit={submit} label={m1Nira.question} placeholder={m1Nira.questionHelp} sendLabel={m1Nira.ask} busy={busy} />
          {sessionId === "" ? null : <VoiceBar sessionId={sessionId} voice={voice} bare onSwitch={(on) => void setOn(on)} disabled={busy} onText={(s) => setQuestion((q) => combineText(q, s))} />}
          <div className="n-companion-privacy-note">{m1Nira.audioNote}</div>
        </>
      }
    >
      <div className="n-companion-guide-line">
        {info.line}
      </div>
      <div className="n-companion-behind">
        <span className="dot" aria-hidden="true" />
        <span className="txt">{busy ? c.thinking : c.here}</span>
      </div>
      <ChatSection id="about" label={c.sections.about}>
        <div className="n-companion-intro">{c.aboutIntro}</div>
        <p className="n-companion-explainer-body">
          {welcome ?? (sessionId === "" ? null : c.aboutNone)}
        </p>
      </ChatSection>
      <ChatSection id="needed" label={c.sections.needed} defaultOpen>
        <div className="n-companion-checklist">
          {info.needed.map((n) => (
            <div key={n.label} className="n-companion-checklist-row">
              <span className="n-companion-checklist-dot" aria-hidden="true" />
              <div className="body">
                <div className="title">{n.label}</div>
                <div className="meta">{n.why}</div>
              </div>
            </div>
          ))}
        </div>
      </ChatSection>
      <ChatSection id="looking" label={c.sections.looking}>
        <p className="n-companion-explainer-body">
          {info.looking}
        </p>
      </ChatSection>
      <ChatSection id="actions" label={c.sections.actions} defaultOpen>
        <div className="n-companion-actions">
          {next.map((a) =>
            a.to ? (
              <Link key={a.label} className="n-btn" to={a.to}>
                {a.label}
                <Icon name="arrowRight" size={13} />
              </Link>
            ) : (
              <button key={a.label} type="button" className="n-btn" disabled={busy} onClick={a.onClick}>
                {a.label}
                <Icon name="arrowRight" size={13} />
              </button>
            ),
          )}
        </div>
      </ChatSection>
      <div ref={log} className="n-companion-convo" role="log" aria-live="polite" aria-label={m1Nira.conversation}>
        {turns.map((t, i) => (
          <div key={i} className={`n-companion-bubble ${t.who}`}>
            {t.text}
          </div>
        ))}
      </div>
      {problem ? (
        <p role="alert" className="state state-error">
          {problem}
        </p>
      ) : null}
      {guest ? null : (
        <Link className="n-companion-flow-link" to="/modules/m1_intent">
          <Icon name="arrowRight" size={13} />
          {c.flow}
        </Link>
      )}
    </AgentPanel>
  );
}
