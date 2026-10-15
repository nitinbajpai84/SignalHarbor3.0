import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLive } from "../../../live/useLive";
import { asRoomView, getJoinLink, livePath, newJoinLink, revokeSeat, startBriefing, type RoomView, type Seat } from "../api";
import { m1Flow, m1Look, m1Room } from "../copy";
import { loadLink, saveLink } from "./guestToken";
import { SummaryLink } from "../summary/SummaryScreen";
import SeatPicture from "./SeatPicture";

/** The organiser's room (M1-03, M1-04): the link to share, who has arrived against the seats (live), remove a seat, start the briefing. */
export default function OrganiserRoom({ sessionId, title, onChanged }: { sessionId: string; title?: string; onChanged: () => void }) {
  const { view, status } = useLive(livePath(sessionId), null, asRoomView);
  const [override, setOverride] = useState<RoomView | null>(null);
  const [link, setLink] = useState<string | null>(() => loadLink(sessionId));
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | "link" | `free:${number}` | null>(null);
  const [busy, setBusy] = useState(false);

  // M1-P05: the server keeps the current link (sealed), so it can be shown again in any tab without making a new one
  useEffect(() => {
    getJoinLink(sessionId)
      .then((l) => {
        saveLink(sessionId, l.join_path);
        setLink(l.join_path);
      })
      .catch(() => undefined); // no saved link: the screen offers a new one
  }, [sessionId]);

  // the answer to a removal shows at once; the next live update (equal or newer) replaces it
  useEffect(() => setOverride(null), [view]);
  const room = override ?? view;

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : m1Room.organiser.busy);
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  const copyLink = () =>
    run(async () => {
      const url = `${window.location.origin}${link ?? ""}`;
      try {
        await navigator.clipboard.writeText(url);
        setNotice(m1Room.organiser.copied);
      } catch {
        setNotice(m1Room.organiser.copyFailed);
      }
    });
  const makeLink = () =>
    run(async () => {
      const made = await newJoinLink(sessionId);
      saveLink(sessionId, made.join_path);
      setLink(made.join_path);
    });
  const remove = (n: number) =>
    run(async () => {
      setOverride(await revokeSeat(sessionId, n));
      setNotice(m1Room.removedNote(n)); // the link still works: say so, and what to do about it
    });
  const free = (n: number) =>
    run(async () => {
      setOverride(await revokeSeat(sessionId, n, true));
      setNotice(m1Room.freedNote(n));
    });
  const briefing = () =>
    run(async () => {
      await startBriefing(sessionId);
      onChanged();
    });

  const closed = room?.state === "closed";
  const beforeRooms = room?.state === "lobby" || room?.state === "briefing"; // a seat can be freed only before the private rooms open
  const action = (s: Seat) =>
    s.state !== "taken" || closed ? null : confirming === `free:${s.n}` ? (
      <div role="alertdialog" aria-label={m1Room.organiser.freeSure(s.name ?? "", s.n)} className="m1-actions">
        <span>{m1Room.organiser.freeSure(s.name ?? "", s.n)}</span>
        <button type="button" className="n-btn primary" disabled={busy} onClick={() => void free(s.n)}>
          {m1Room.organiser.freeYes}
        </button>
        <button type="button" className="n-btn" onClick={() => setConfirming(null)}>
          {m1Room.organiser.removeNo}
        </button>
      </div>
    ) : confirming === s.n ? (
      <div role="alertdialog" aria-label={m1Room.organiser.removeSure(s.name ?? "", s.n)} className="m1-actions">
        <span>{m1Room.organiser.removeSure(s.name ?? "", s.n)}</span>
        <button type="button" className="n-btn primary" disabled={busy} onClick={() => void remove(s.n)}>
          {m1Room.organiser.removeYes}
        </button>
        <button type="button" className="n-btn" onClick={() => setConfirming(null)}>
          {m1Room.organiser.removeNo}
        </button>
      </div>
    ) : (
      <div className="m1-actions">
        {beforeRooms ? (
          <button type="button" className="n-btn" aria-label={m1Room.freeLabel(s.name ?? "", s.n)} onClick={() => setConfirming(`free:${s.n}`)}>
            {m1Room.organiser.free}
          </button>
        ) : null}
        <button type="button" className="n-btn" aria-label={m1Room.removeLabel(s.name ?? "", s.n)} onClick={() => setConfirming(s.n)}>
          {m1Room.organiser.remove}
        </button>
      </div>
    );

  return (
    <Panel title={m1Room.organiser.title} eyebrow={m1Look.organiserEyebrow} className="m1-room">
      {title ? <div className="n-room-purpose">{title}</div> : null}
      {status === "offline" ? (
        <p role="status" className="state n-muted">
          {m1Room.organiser.offline}
        </p>
      ) : null}
      {closed ? (
        <>
          <p role="status" className="state n-muted">
            {m1Room.organiser.sessionClosed}
          </p>
          <SummaryLink sessionId={sessionId} />
        </>
      ) : (
        <div>
          <h3>{m1Room.organiser.linkTitle}</h3>
          <p className="n-muted">{m1Room.organiser.linkHelp}</p>
          {link ? (
            <>
              <label>
                {m1Room.organiser.linkLabel}
                <input type="text" readOnly value={`${window.location.origin}${link}`} onFocus={(e) => e.currentTarget.select()} />
              </label>
              <div className="m1-actions">
                <button type="button" className="n-btn" disabled={busy} onClick={() => void copyLink()}>
                  {m1Room.organiser.copy}
                </button>
                <Link className="n-btn" to={link}>
                  {m1Room.organiser.joinMyself}
                </Link>
              </div>
            </>
          ) : (
            <p className="state n-muted">{m1Room.organiser.linkGone}</p>
          )}
          {confirming === "link" ? (
            <div role="alertdialog" aria-label={m1Room.organiser.newLinkSure} className="m1-actions">
              <span>{m1Room.organiser.newLinkSure}</span>
              <button type="button" className="n-btn primary" disabled={busy} onClick={() => void makeLink()}>
                {m1Room.organiser.newLinkYes}
              </button>
              <button type="button" className="n-btn" onClick={() => setConfirming(null)}>
                {m1Room.keepLink}
              </button>
            </div>
          ) : (
            <>
              <button type="button" className="n-btn" disabled={busy} onClick={() => (link ? setConfirming("link") : void makeLink())}>
                {m1Room.organiser.newLink}
              </button>
              <p className="n-muted">{m1Flow.linkMakeHelp}</p>
            </>
          )}
        </div>
      )}
      {notice ? (
        <p role="status" className="state n-muted">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      <h3>{m1Room.organiser.seatsTitle}</h3>
      <ScreenState state={status === "refused" ? "refused" : room ? "populated" : "loading"} message={status === "refused" ? m1Room.organiser.refused : undefined}>
        {room ? (
          <>
            <div className="n-room-progress">
              <div
                className="n-room-progress-bar"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={room.seat_count}
                aria-valuenow={room.arrived}
                aria-label={m1Room.organiser.seatsTitle}
              >
                <div className="fill" style={{ width: `${room.seat_count > 0 ? Math.round((room.arrived / room.seat_count) * 100) : 0}%` }} />
              </div>
              <div className="n-room-progress-label">{m1Room.organiser.arrived(room.arrived, room.seat_count)}</div>
            </div>
            <SeatPicture seats={room.seats} action={action} />
            {room.state === "lobby" ? (
              <div className="m1-actions">
                <button type="button" className="n-btn primary" disabled={busy} onClick={() => void briefing()}>
                  {m1Room.organiser.startBriefing}
                </button>
                <span className="n-muted">{m1Room.organiser.startBriefingHelp}</span>
              </div>
            ) : room.state === "paused" ? (
              <p className="state n-muted">{m1Room.organiser.sessionPaused}</p>
            ) : closed ? null : (
              <>
                <p className="state n-muted">{m1Room.organiser.briefingStarted}</p>
                <div className="m1-actions">
                  <Link className="n-btn primary" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/briefing`}>
                    {m1Flow.organiserBriefing}
                  </Link>
                  {room.state === "private_rooms" ? (
                    <Link className="n-btn" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/room`}>
                      {m1Flow.organiserRoom}
                    </Link>
                  ) : null}
                </div>
              </>
            )}
          </>
        ) : null}
      </ScreenState>
    </Panel>
  );
}
