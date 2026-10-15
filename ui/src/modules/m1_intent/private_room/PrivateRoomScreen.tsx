import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import AgentChip, { type AgentStatus } from "../../../components/AgentChip";
import Icon from "../../../components/Icon";
import MessageBubble from "../../../components/MessageBubble";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import ScreenState from "../../../components/ScreenState";
import { copy } from "../../../copy";
import { askNira } from "../api";
import NiraDock from "../NiraDock"; // M1-UI2
import FinishPanel, { Finished } from "./FinishPanel"; // M1-UI2
import StageTimer from "../timer/StageTimer";
import LibraryPanel from "./LibraryPanel";
import NotesPanel from "./NotesPanel";
import { useRoom } from "./useRoom";
import {
  decidePractice, saveNote, sendMessage, setPriority, startFromLibrary, writeCards,
  type Library, type LibraryProblem, type MessageKind, type Priority, type Room, type RoomNote,
} from "./roomApi";
import { m1Companion, m1Flow, m1Lean, m1Look, m1Nira, m1PrivateRoom as t } from "../copy";
import { PlayButton, VoiceBar, combineText, useAutoSpeak, useVoice } from "../voice/VoiceControls"; // M1-P06

/** The time of a turn, as the earlier transcript cards show it (hours and minutes). */
const timeOf = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? undefined : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
};

/**
 * M1-08, M1-10, M1-13, M1-16: the person's private room with their own North. Laid out as the earlier Intent Studio's live
 * interview (screens/intent-studio.js renderLiveInterview): the transcript of message bubbles and the "Your turn" panel on the
 * left (n-e1-studio-grid), the person's notes as sticky notes on the right.
 */
export default function PrivateRoomScreen({ sessionId: given, onBack }: { sessionId?: string; onBack?: () => void } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? ""; // M1-P05: also shown inside the join page, where there is no route id
  const { state, data, message, retry } = useRoom(sessionId);
  const back = onBack ? (
    // M1-P05: a person who joined by link goes back inside the join page; a signed-in person by route
    <button type="button" className="n-btn" onClick={onBack}>
      {m1Flow.toBriefing}
    </button>
  ) : (
    <Link className="n-btn" to={`/modules/m1_intent/sessions/${sessionId}/briefing`}>
      {m1Flow.toBriefing}
    </Link>
  );
  return (
    <>
      <PageHead
        title={t.title}
        eyebrow={m1Look.northEyebrow}
        sub={t.intro}
        crumbs={onBack ? undefined : [{ label: m1Look.crumbModules, to: "/" }, { label: m1Look.crumbSessions, to: "/modules/m1_intent" }, { label: t.title }]}
        actions={
          <>
            <StatusPill tone="info">{m1Look.stageRoom}</StatusPill>
            {back}
          </>
        }
      />
      <ScreenState state={state} onRetry={retry} message={state === "error" ? (message ?? t.loadFailed) : message}>
        {data ? <RoomView sessionId={sessionId} first={data.room} library={data.library} /> : null}
      </ScreenState>
      <NiraDock
        sessionId={sessionId}
        stage="room"
        actions={[onBack ? { label: m1Companion.actions.toBriefing, onClick: onBack } : { label: m1Companion.actions.toBriefing, to: `/modules/m1_intent/sessions/${sessionId}/briefing` }]}
      />
    </>
  );
}

/** The one-minute warning for notes saved but not sent: what happens to them when time ends, and one click to make them anonymous. */
function UnsentWarning({ sessionId, room, onRoom }: { sessionId: string; room: Room; onRoom: (r: Room) => void }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!room.unsent || room.unsent.count < 1 || !room.unsent.message) return null;
  const choice = (room.names ?? "choice") === "choice"; // the one-click anonymous fix only where each person chooses
  const named = room.notes.filter((n) => n.state === "draft" && !n.anonymous);
  async function makeAnonymous() {
    setBusy(true);
    setFailed(false);
    try {
      let latest = room;
      for (const n of named) latest = await saveNote(sessionId, n.id, { anonymous: true });
      onRoom(latest);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div role="alert" className="state state-error m1-unsent">
      <p>{room.unsent.message}</p>
      {choice && room.unsent.named > 0 ? (
        <button type="button" className="n-btn primary" disabled={busy} onClick={() => void makeAnonymous()}>
          {busy ? t.makingAnonymous : t.makeAnonymous}
        </button>
      ) : null}
      {failed ? <p>{t.makeAnonymousFailed}</p> : null}
    </div>
  );
}

function RoomView({ sessionId, first, library }: { sessionId: string; first: Room; library: Library }) {
  const [room, setRoom] = useState<Room>(first);
  const [text, setText] = useState("");
  const [correcting, setCorrecting] = useState<RoomNote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nira, setNira] = useState<string | null>(null);
  const [warning, setWarning] = useState(false); // inside the one-minute warning
  const box = useRef<HTMLTextAreaElement>(null);
  const { voice, setOn } = useVoice(sessionId); // M1-P06
  useAutoSpeak(sessionId, voice, room.turns); // M1-P06

  useEffect(() => setRoom(first), [first]);
  useEffect(() => {
    if (correcting) box.current?.focus();
  }, [correcting]);

  async function run(action: () => Promise<Room>, done?: () => void) {
    setBusy(true);
    setError(null);
    try {
      setRoom(await action());
      done?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : copy.errors.server);
    } finally {
      setBusy(false);
    }
  }
  const [askOthers, setAskOthers] = useState(false);
  const [finished, setFinished] = useState<null | "done" | "closed">(null); // M1-UI2: left the room early
  const send = (kind: MessageKind) =>
    run(() => sendMessage(sessionId, text, kind, kind === "correction" ? correcting?.id : undefined, askOthers), () => {
      setText("");
      setCorrecting(null);
      setAskOthers(false);
    });
  const askNiraHere = () =>
    askNira(sessionId, "ask", t.askNiraText).then(
      (r) => setNira(r.text),
      () => setNira(t.askNiraFailed),
    );
  const canSend = text.trim() !== "" && !busy && room.open;
  const pending = room.turns.some((x) => x.role === "north" && x.answered === false);
  // North's presence ring: thinking while a message is on its way, not available when it is off, otherwise waiting for you
  const northStatus: AgentStatus = busy ? "thinking" : !room.north.available && !pending ? "blocked" : room.open ? "waiting" : "idle";

  if (finished) return <Finished sessionId={sessionId} closed={finished === "closed"} />;
  return (
    <>
      {room.title ? <p className="n-page-sub">{room.title}</p> : null} {/* M1-P05 */}
      <StageTimer sessionId={sessionId} onWarningState={setWarning} />
      {warning && room.open ? <UnsentWarning sessionId={sessionId} room={room} onRoom={setRoom} /> : null}
      <div className="m1-room-grid n-e1-studio-grid">
        <div className="m1-room-main">
          <Panel title={t.chatHeading} eyebrow={t.chatEyebrow} className="m1-chat">
            <AgentChip name="North" status={northStatus} />
            {!room.north.available && !pending ? <p className="n-muted">{t.northOff}</p> : null}
            {room.cards_message ? <p role="status" className="n-muted">{room.cards_message}</p> : null}
            {room.interview?.drafted && room.interview.gaps.length > 0 ? <p className="n-muted">{m1Lean.room.gapsHeading}: {room.interview.gaps.map((g) => g.ask).join(" ")}</p> : null}
            <ol className="m1-turns n-e1-transcript" aria-live="polite">
              {room.turns.length === 0 ? <li className="n-empty ebody">{room.open ? t.emptyChat : t.emptyClosed}</li> : null}
              {room.turns.map((turn) => (
                <li key={turn.id} className="m1-turn">
                  <MessageBubble
                    from={turn.role === "person" ? "human" : "agent"}
                    who={turn.role === "person" ? t.you : t.north}
                    when={timeOf(turn.at)}
                    muted={turn.role === "north" && turn.answered === false}
                    text={turn.role === "north" && turn.answered === false ? turn.text || t.noAnswer : turn.text}
                  >
                    {turn.readback ? (
                      <div className="reason">
                        <span>{t.readback}</span>
                        <blockquote className="m1-quote">{turn.readback.text}</blockquote>
                        <span>{t.readbackAsk}</span>
                      </div>
                    ) : null}
                    {turn.role === "north" && turn.answered !== false ? <PlayButton sessionId={sessionId} voice={voice} text={turn.text} /> : null /* M1-P06 */}
                  </MessageBubble>
                </li>
              ))}
            </ol>
            {room.open ? null : (
              <div role="alert" className="state state-error">
                <strong>{t.closedTitle}</strong>
                <p>{room.message}</p>
              </div>
            )}
          </Panel>
          {room.open ? (
            <Panel title={t.yourTurn} eyebrow={t.speakOrType} className="m1-turn-form">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (canSend) void send(correcting ? "correction" : "answer");
                }}
              >
                {correcting ? (
                  <p className="m1-correcting" role="status">
                    {t.correctingLabel}: <q>{correcting.text}</q>{" "}
                    <button type="button" className="n-btn" onClick={() => setCorrecting(null)}>
                      {t.correctingCancel}
                    </button>
                  </p>
                ) : null}
                <label>
                  {correcting ? t.correctingField : t.placeholder}
                  <textarea
                    ref={box}
                    value={text}
                    onChange={(e) => {
                      setText(e.target.value);
                      if (e.target.value.trim() === "") setAskOthers(false); // a cleared box is no longer the ask
                    }}
                    onKeyDown={(e) => {
                      // Enter sends; Shift+Enter is a new line (and so is Enter while an input method is composing)
                      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        if (canSend) void send(correcting ? "correction" : "answer");
                      }
                    }}
                    disabled={busy}
                  />
                </label>
                <VoiceBar sessionId={sessionId} voice={voice} onSwitch={(on) => void setOn(on)} disabled={busy} onText={(s) => setText((p) => combineText(p, s))} /> {/* M1-P06 */}
                {error ? (
                  <p role="alert" className="state state-error">
                    {error}
                  </p>
                ) : null}
                <div className="m1-actions">
                  <button type="submit" className="n-btn primary" disabled={!canSend}>
                    <Icon name="send" />
                    {busy ? t.sending : correcting ? t.sendCorrection : t.sendReply}
                  </button>
                  {!correcting ? (
                    <button type="button" className="n-btn" disabled={!canSend} onClick={() => void send("note")}>
                      {t.sendNote}
                    </button>
                  ) : null}
                  {!correcting && room.north.available && room.turns.some((x) => x.role === "person") ? (
                    <button type="button" className="n-btn" disabled={busy} onClick={() => void run(() => writeCards(sessionId))}>
                      {busy ? m1Lean.room.writingCards : m1Lean.room.writeCards}
                    </button>
                  ) : null}
                </div>
                <div className="m1-actions m1-ask">
                  <button type="button" className="n-btn" onClick={() => void askNiraHere()}>
                    {t.askNira}
                  </button>
                  <button
                    type="button"
                    className="n-btn"
                    onClick={() => {
                      setText(t.askNorthText);
                      setAskOthers(true);
                      box.current?.focus();
                    }}
                  >
                    {t.askNorth}
                  </button>
                </div>
                {nira ? (
                  <div className="n-companion-guide-line m1-nira-answer" role="status">
                    <strong>{m1Nira.name}</strong>
                    <p>{nira}</p>
                  </div>
                ) : null}
              </form>
            </Panel>
          ) : null}
          {room.open ? <FinishPanel sessionId={sessionId} notes={room.notes} onRoom={setRoom} onFinished={(closed) => setFinished(closed ? "closed" : "done")} /> : null}
        </div>
        <div className="m1-room-side">
          <NotesPanel
            notes={room.notes}
            open={room.open}
            busy={busy}
            onCorrect={(n) => {
              setCorrecting(n);
              setText(n.text);
            }}
            onPriority={(n: RoomNote, p: Priority | null) => void run(() => setPriority(sessionId, n.id, p))}
            onPractice={(n, action) => void run(() => decidePractice(sessionId, n.id, action))}
            sessionId={sessionId} /* M1-P05 */
            form={room.form}
            northAvailable={room.north.available}
            onRoom={setRoom}
            kinds={room.kinds}
            names={room.names}
            north={room.north}
          />
          {library.on ? ( // only when the organiser turned the problem library on in Prepare: by default North listens and checks
                      <LibraryPanel
              library={library}
              open={room.open}
              busy={busy}
              onAdd={(p: LibraryProblem, body: string, priority: Priority | null) =>
                void run(() => startFromLibrary(sessionId, p.id, body, priority))
              }
            />
          ) : null}
        </div>
      </div>
    </>
  );
}
