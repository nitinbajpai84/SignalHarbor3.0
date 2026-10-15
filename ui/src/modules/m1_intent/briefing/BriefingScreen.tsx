import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { copy } from "../../../copy";
import Icon from "../../../components/Icon";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import ScreenState from "../../../components/ScreenState";
import Sticky from "../../../components/Sticky";
import { confirmClear, getBriefing, sendEveryone, type BriefingView } from "../api";
import { m1Briefing, m1Companion, m1Flow, m1Look } from "../copy";
import StageTimer from "../timer/StageTimer";
import { useLoad } from "../useLoad";
import { playReply } from "../voice/VoiceControls"; // M1-P06: the same speech the private room uses
import NiraDock from "../NiraDock";
import VideoSlot from "./VideoSlot";

function problemText(e: unknown): string {
  return e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : copy.states.error;
}

/** The briefing (M1-05): the room rules, the video slot, "I'm clear" or ask Nira, and the organiser's send. */
export default function BriefingScreen({ sessionId: given, onRoom }: { sessionId?: string; onRoom?: () => void } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? ""; // M1-P05: also shown inside the join page, where there is no route id
  const { state, data, message, retry } = useLoad<BriefingView>(() => getBriefing(sessionId), `briefing:${sessionId}`);
  return (
    <>
      {data ? (
        <PageHead
          title={data.title || m1Briefing.title}
          eyebrow={data.company_name}
          sub={!["draft", "lobby", "briefing"].includes(data.stage) ? m1Flow.nowRoomsOpen : m1Briefing.title}
          crumbs={onRoom ? undefined : [{ label: m1Look.crumbModules, to: "/" }, { label: m1Look.crumbSessions, to: "/modules/m1_intent" }, { label: m1Briefing.title }]}
          actions={
            <>
              <StatusPill tone="info">{m1Look.stageBriefing}</StatusPill>
              {onRoom ? null : (
                <Link className="n-btn" to="/modules/m1_intent">
                  {m1Briefing.back}
                </Link>
              )}
            </>
          }
        />
      ) : onRoom ? null : (
        <p>
          <Link to="/modules/m1_intent">{m1Briefing.back}</Link>
        </p>
      )}
      <ScreenState state={state} onRetry={retry} message={state === "empty" ? m1Briefing.nothingYet : message}>
        {data ? <Briefing sessionId={sessionId} first={data} reload={retry} onRoom={onRoom} /> : null}
      </ScreenState>
    </>
  );
}

function Briefing({ sessionId, first, reload, onRoom }: { sessionId: string; first: BriefingView; reload: () => void; onRoom?: () => void }) {
  const [view, setView] = useState<BriefingView>(first);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [aloud, setAloud] = useState<string | null>(null);
  const [warnings, setWarnings] = useState(0);
  const onWarning = useCallback(() => setWarnings((n) => n + 1), []);
  const organiser = view.me.role === "organiser";
  const clear = view.me.status === "clear";
  const roomsOpen = !["draft", "lobby", "briefing"].includes(view.stage);
  const notStarted = view.stage === "draft" || view.stage === "lobby"; // M1-P05: nothing to confirm yet
  const toRoom = onRoom ? (
    <button type="button" className="n-btn primary" onClick={onRoom}>
      {m1Flow.toRoom}
    </button>
  ) : (
    <Link className="n-btn primary" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/room`}>
      {m1Flow.toRoom}
    </Link>
  );

  const act = (work: () => Promise<unknown>) => {
    setBusy(true);
    setProblem(null);
    work()
      .catch((e: unknown) => setProblem(problemText(e)))
      .finally(() => setBusy(false));
  };
  // The rules, spoken with the same speech the private room uses. Without speech the plain message says so.
  const readAloud = async () => {
    if (!view.read_aloud.available) {
      setAloud(view.read_aloud.message ?? m1Briefing.readAloud);
      return;
    }
    setAloud(m1Briefing.readingAloud);
    const played = await playReply(sessionId, view.rules.map((r) => `${r.label}. ${r.text}`).join(" "));
    setAloud(played ? m1Briefing.readingAloud : m1Briefing.aloudFailed);
  };
  const onClear = () => act(() => confirmClear(sessionId).then(setView));
  const onSend = () => act(() => sendEveryone(sessionId).then(() => reload()));
  const onAsked = () => setView((v) => (v.me.status === "clear" ? v : { ...v, me: { ...v.me, status: "asked" } }));

  return (
    <>
      <StageTimer sessionId={sessionId} onStageChange={reload} onWarning={onWarning} />
      {roomsOpen && view.next === "briefing" ? (
        <p role="status" className="state">
          {m1Briefing.lateNote}
        </p>
      ) : null}
      <div className="m1-brief-grid">
        <VideoSlot sessionId={sessionId} video={view.video} />
        <Panel title={m1Briefing.rulesTitle} eyebrow={m1Briefing.rulesEyebrow} className="m1-rules">
          <p className="n-muted">{m1Briefing.rulesNote}</p>
          <div className="n-sticky-board">
            {view.rules.map((r) => (
              <Sticky key={r.id} tone="yellow" question={r.label}>
                <div className="n-sticky-pain">{r.text}</div>
              </Sticky>
            ))}
          </div>
          <button type="button" className="n-btn" onClick={() => void readAloud()}>
            <Icon name="speaker" />
            {m1Briefing.readAloud}
          </button>
          {aloud ? (
            <p role="status" className="n-muted">
              {aloud}
            </p>
          ) : null}
        </Panel>
      </div>
      <Panel label={m1Briefing.yourPart} className="m1-your-part">
        {notStarted ? (
          <p role="status">{m1Flow.briefingNotStarted}</p>
        ) : clear ? (
          <>
            <p role="status">{roomsOpen ? m1Briefing.readyForRoom : m1Briefing.clearDone}</p>
            {roomsOpen ? <p>{toRoom}</p> : null}
          </>
        ) : (
          <>
            {view.me.status === "asked" ? <p className="n-muted">{m1Briefing.asked}</p> : null}
            <button type="button" className="n-btn primary" disabled={busy} onClick={onClear}>
              {busy ? m1Briefing.saving : m1Briefing.clear}
            </button>
            {roomsOpen && !organiser ? <p>{toRoom}</p> : null}{/* a latecomer: the rules say "then go to your room", so the way is here */}
          </>
        )}
        {organiser ? (
          <div className="m1-organiser-part">
            <p role="status">{m1Briefing.ready(view.confirmed ?? 0, view.seats ?? 1)}</p>
            {view.can_send ? (
              <>
                <button type="button" className="n-btn primary" disabled={busy} onClick={onSend}>
                  {busy ? m1Briefing.sending : m1Briefing.send}
                </button>
                <p className="n-muted">{m1Briefing.sendHelp}</p>
              </>
            ) : roomsOpen ? (
              <>
                <p className="n-muted">{m1Briefing.roomsOpen}</p>
                {clear ? null : <p>{toRoom}</p>}
              </>
            ) : null}
          </div>
        ) : null}
        {!organiser && clear && !roomsOpen ? <p className="n-muted">{m1Briefing.waiting}</p> : null}
        {problem ? (
          <p role="alert" className="state state-error">
            {problem}
          </p>
        ) : null}
      </Panel>
      <NiraDock
        sessionId={sessionId}
        stage="briefing"
        onAsked={onAsked}
        warning={warnings}
        actions={roomsOpen ? [onRoom ? { label: m1Companion.actions.toRoom, onClick: onRoom } : { label: m1Companion.actions.toRoom, to: `/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/room` }] : []}
      />
    </>
  );
}
