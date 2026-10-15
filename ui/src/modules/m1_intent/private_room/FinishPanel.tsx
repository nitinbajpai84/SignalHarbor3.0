import { useEffect, useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import { closeRooms, pGet, sayRoomsDone, sessionPath, type RoomView } from "../api";
import LaterStages from "../board/LaterStages";
import { usePolled } from "../board/usePolled";
import { m1Board, m1PrivateRoom as t } from "../copy";
import { submitNote, type Room, type RoomNote } from "./roomApi";

const LATER = new Set(["board", "together", "signing", "closed"]);

/** After "I'm done": a calm waiting state that follows the session to the board by itself (the board, then back in the room). */
export function Finished({ sessionId, closed }: { sessionId: string; closed: boolean }) {
  const live = usePolled(() => pGet<RoomView>(sessionId, `${sessionPath(sessionId)}/lobby`), `done-stage:${sessionId}`);
  const [later, setLater] = useState(closed); // the organiser who closed the rooms goes straight on
  useEffect(() => {
    if (live.data && LATER.has(live.data.state)) setLater(true);
  }, [live.data]);
  if (later) return <LaterStages sessionId={sessionId} />;
  return (
    <Panel title={t.waitingTitle} className="m1-room">
      <p role="status">{t.waiting}</p>
    </Panel>
  );
}

interface Props {
  sessionId: string;
  notes: RoomNote[];
  onRoom: (r: Room) => void;
  onFinished: (closed: boolean) => void;
}

/**
 * Ending the private room early. Everyone gets "I'm done": it submits this person's own drafts, one by one, through the
 * existing note submit route, after one plain question, and tells the server so the rooms can close early when everyone is done. The organiser also gets "Close the rooms now" (rooms/close).
 */
export default function FinishPanel({ sessionId, notes, onRoom, onFinished }: Props) {
  const [asking, setAsking] = useState<"done" | "close" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [organiser, setOrganiser] = useState(false);
  useEffect(() => {
    let live = true;
    pGet<RoomView>(sessionId, `${sessionPath(sessionId)}/lobby`).then(
      (v) => live && setOrganiser(v.organiser),
      () => undefined, // not known: no organiser control is shown
    );
    return () => {
      live = false;
    };
  }, [sessionId]);

  async function run(work: () => Promise<void>, fail: string) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : fail);
    } finally {
      setBusy(false);
      setAsking(null);
    }
  }
  const done = () =>
    run(async () => {
      for (const n of notes.filter((x) => x.state === "draft")) onRoom(await submitNote(sessionId, n.id));
      if (!organiser) await sayRoomsDone(sessionId); // the rooms close early once everyone seated has said so; the organiser decides on their own
      onFinished(false);
    }, t.doneFailed);
  const close = () =>
    run(async () => {
      await closeRooms(sessionId);
      onFinished(true);
    }, m1Board.closeFailed);

  const confirm = (text: string, yes: string, no: string, go: () => void) => (
    <div role="alertdialog" aria-label={text} className="m1-actions">
      <span>{text}</span>
      <button type="button" className="n-btn primary" disabled={busy} onClick={go}>
        {yes}
      </button>
      <button type="button" className="n-btn" onClick={() => setAsking(null)}>
        {no}
      </button>
    </div>
  );
  return (
    <Panel title={t.finishTitle} className="m1-finish">
      {asking === "done" ? (
        confirm(t.doneSure, t.doneYes, t.doneNo, () => void done())
      ) : asking === "close" ? (
        confirm(m1Board.closeSure, m1Board.closeYes, m1Board.closeNo, () => void close())
      ) : (
        <div className="m1-actions">
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => setAsking("done")}>
            {t.done}
          </button>
          {organiser ? (
            <button type="button" className="n-btn" disabled={busy} onClick={() => setAsking("close")}>
              {m1Board.close}
            </button>
          ) : null}
        </div>
      )}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
    </Panel>
  );
}
