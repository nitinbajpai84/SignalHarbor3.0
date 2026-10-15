import { useCallback, useEffect, useState } from "react";

import { Button } from "../../../design";
import { getJoinLink, getRoom, newJoinLink, revokeSeat, type RoomView } from "../api";
import { m1Room } from "../copy";
import { wallCopy as t } from "./copy";

/** The organiser's invite panel on the wall: one line, opens to the join link and the seats. Nothing for anyone else. */
export default function InvitePanel({ sessionId }: { sessionId: string }) {
  const [room, setRoom] = useState<RoomView | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    // the join link is the organiser's: ask for it only once the room says so, so a participant never meets a refusal
    getRoom(sessionId).then((r) => {
      setRoom(r);
      if (r.organiser && r.state !== "closed") getJoinLink(sessionId).then((l) => setLink(l.join_path), () => setLink(null));
    }, () => undefined);
  }, [sessionId]);
  useEffect(load, [load]);

  if (!room?.organiser) return null;
  const done = room.state === "closed"; // a closed wall keeps its seat list; no link to share and no seat to take back
  const url = link ? `${window.location.origin}${link}` : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setNote(m1Room.organiser.copied);
    } catch {
      setNote(m1Room.organiser.copyFailed);
    }
  };
  const revoke = (n: number) => revokeSeat(sessionId, n).then(setRoom, () => setNote(m1Room.organiser.busy));
  const fresh = () => newJoinLink(sessionId).then((l) => { setLink(l.join_path); setNote(null); }, () => setNote(m1Room.organiser.busy));

  return (
    <section aria-label={t.inviteLabel} className="ds-card ds-invite">
      <Button className="ds-invite__line" aria-expanded={open} onClick={() => setOpen(!open)}>
        {t.inviteLine(room.seat_count, room.arrived)}
      </Button>
      {open ? (
        <>
          {done ? null : link ? (
            <div className="ds-invite__row">
              <input type="text" readOnly aria-label={t.joinLink} value={url} onFocus={(e) => e.currentTarget.select()} />
              <Button onClick={() => void copy()}>{t.copyLink}</Button>
            </div>
          ) : (
            <p className="ds-invite__row">{m1Room.organiser.linkGone}</p>
          )}
          {done ? null : <div className="ds-invite__row">
            <Button onClick={() => void fresh()}>{t.newLink}</Button>
            <span>{t.newLinkNote}</span>
          </div>}
          {note ? <p role="status" className="ds-invite__row">{note}</p> : null}
          <ul className="ds-invite__seats">
            {room.seats.map((s) => (
              <li key={s.n}>
                <span>{m1Room.seat.seat(s.n)}: {s.state === "taken" ? s.name : s.state === "free" ? t.free : t.revoked}</span>
                {s.state === "taken" && !done ? <Button aria-label={t.revokeSeat(s.n)} onClick={() => void revoke(s.n)}>{t.revoke}</Button> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
