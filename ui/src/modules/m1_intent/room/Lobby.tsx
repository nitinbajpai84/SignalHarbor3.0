import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Icon from "../../../components/Icon";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLive } from "../../../live/useLive";
import { asRoomView, getBriefing, livePath, type SeatMe } from "../api";
import { m1Companion, m1Flow, m1Nira, m1Room } from "../copy";
import NiraDock from "../NiraDock"; // M1-UI2
import SeatPicture from "./SeatPicture";

const style = `
  .m1-room .n-room-purpose { font-family: var(--font-heading); font-size: 18px; color: var(--text-primary); }
  .m1-room .n-room-announce { background: var(--accent-soft); border: 1px solid var(--border-hairline); border-radius: var(--radius-lg); padding: 10px 12px; }
`;

interface Props {
  sessionId: string;
  /** A person with no account passes their token; a signed-in person passes null and the cookie is used. */
  token: string | null;
  /** The seat the join answer gave, shown at once while the first live update is on its way. */
  seat: SeatMe;
  /** The session length from the join answer, so Nira can greet at once. */
  minutes: number;
  /** The seat stopped working (removed, or the session closed): the screen goes back to the link. */
  onEnded: () => void;
  /** M1-P05: go on to the briefing (shown once it has started). */
  onBriefing?: () => void;
}

/** The lobby (M1-04): Nira greets the person by name and says how long the session takes; the seat picture updates live. No notes here. */
export default function Lobby({ sessionId, token, seat, minutes: firstMinutes, onEnded, onBriefing }: Props) {
  const { view, status } = useLive(livePath(sessionId), token, asRoomView);
  const [title, setTitle] = useState(""); // M1-P05: the session's own clear title, from the briefing answer
  useEffect(() => {
    getBriefing(sessionId).then((b) => setTitle(b.title), () => undefined);
  }, [sessionId]);
  const me = view?.me ?? seat;
  const minutes = view?.length_minutes ?? firstMinutes;
  const stage = view?.state ?? "lobby";

  if (status === "refused") {
    return (
      <Panel label={m1Room.lobby.title} className="m1-room">
        <p role="alert" className="state state-error">
          {m1Room.lobby.ended}
        </p>
        <button type="button" className="n-btn primary" onClick={onEnded}>
          {m1Room.lobby.endedButton}
        </button>
      </Panel>
    );
  }
  const canGo = stage !== "lobby" && stage !== "draft" && stage !== "paused" && stage !== "closed" && onBriefing;
  return (
    <>
    <style>{style}</style>
    <Panel title={m1Room.lobby.title} eyebrow={m1Nira.name} className="m1-room">
      <div className="n-room-session">
        <div className="n-room-purpose">{title || m1Flow.untitled}</div>
        <div className="n-room-announce">
          <div className="n-companion-avatar-inline">
            <Icon name="spark" size={14} />
          </div>
          <div>
            <div className="n-room-announce-who">Nira</div>
            <div className="n-room-announce-text">{m1Room.lobby.greeting(me.name, minutes)}</div>
          </div>
        </div>
      </div>
      <p className="n-muted">{m1Room.lobby.yourSeat(me.seat, me.name, me.role)}</p>
      {me.see_briefing_first ? <p className="state n-muted">{m1Room.lobby.briefingFirst}</p> : null}
      <p role="status" className="state n-muted">
        {stage === "lobby"
          ? m1Room.lobby.waiting
          : stage === "paused"
            ? m1Room.lobby.paused
            : stage === "closed"
              ? m1Room.lobby.closed
              : m1Room.lobby.briefing}
      </p>
      {stage !== "lobby" && stage !== "draft" && stage !== "paused" && stage !== "closed" && onBriefing ? (
        <p>
          <button type="button" className="n-btn primary" onClick={onBriefing}>
            {m1Flow.toBriefing}
          </button>
        </p>
      ) : null}
      {status === "offline" ? (
        <p role="status" className="state n-muted">
          {m1Room.lobby.offline}
        </p>
      ) : null}
      <ScreenState state={view ? "populated" : "loading"}>
        {view ? (
          <>
            <p className="n-muted">{m1Room.lobby.arrived(view.arrived, view.seat_count)}</p>
            <SeatPicture seats={view.seats} />
            {view.organiser ? (
              <p>
                <Link className="n-btn" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}`}>
                  {m1Room.lobby.backToOrganiser}
                </Link>
              </p>
            ) : null}
          </>
        ) : null}
      </ScreenState>
    </Panel>
    <NiraDock sessionId={sessionId} stage="lobby" actions={canGo ? [{ label: m1Companion.actions.toBriefing, onClick: onBriefing }] : []} />
    </>
  );
}
