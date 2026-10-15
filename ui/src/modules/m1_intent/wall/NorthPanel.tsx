import { useEffect, useState } from "react";

import { ApiError } from "../../../api/client";
import { Button } from "../../../design";
import { saveNote, sendMessage, submitNote, type Room, type RoomNote } from "../private_room/roomApi";
import { useRoom } from "../private_room/useRoom";
import { PlayButton, VoiceBar, combineText, useAutoSpeak, useVoice } from "../voice/VoiceControls";
import { wallCopy as t } from "./copy";
import WallState from "./WallState";

const IDS = ["q1", "q2", "q3", "q4"] as const;
type Q = (typeof IDS)[number];
interface Cell { text: string; mark: string; from: string | null }
interface Draft { text: string; from: string }
/** The room view since IC-2a: quarters and drafts on a card, the question leads on the room. Read when present. */
type WallNote = RoomNote & { quarters?: Record<Q, Cell>; quarter_drafts?: Partial<Record<Q, Draft>> };
type WallRoom = Omit<Room, "notes"> & { notes: WallNote[]; wall_questions?: { id: Q; lead: string }[] };

/** saveNote's typed change does not list `quarters` yet (roomApi.ts is outside this package); the route takes it. */
type Change = Parameters<typeof saveNote>[2];

const somethingNew = "Tell North something new";

const filled = (n: WallNote | undefined, q: Q): boolean => {
  const c = n?.quarters?.[q];
  return !!c && c.mark !== "unknown" && !!c.text;
};

function Turn({ you, children, now = false }: { you: boolean; children: React.ReactNode; now?: boolean }) {
  return (
    <div className={`ds-north__turn${you ? " ds-north__turn--you" : ""}${now ? " ds-north__turn--now" : ""}`}>
      <small>{you ? t.you : t.northName}</small>
      {children}
    </div>
  );
}

/** North's panel on the wall (canvas artboard 2): the question asked now and the quarter bars first, then the thread and the answer box. Same room calls as the private room. */
export default function NorthPanel({ sessionId, onChange }: { sessionId: string; onChange?: () => void }) {
  const { state, data, message, retry } = useRoom(sessionId);
  return (
    <WallState state={state} label={t.northLoading} message={message ?? t.northError} onRetry={retry} skeleton={1}>
      {data ? <Panel sessionId={sessionId} first={data.room as WallRoom} onChange={onChange} /> : null}
    </WallState>
  );
}

function Panel({ sessionId, first, onChange }: { sessionId: string; first: WallRoom; onChange?: () => void }) {
  const [room, setRoom] = useState<WallRoom>(first);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { voice, setOn } = useVoice(sessionId);
  useAutoSpeak(sessionId, voice, room.turns);
  useEffect(() => setRoom(first), [first]);

  // "Something new": the cards open when it was pressed step aside, so the answers go to North, which drafts a new card from them
  const [aside, setAside] = useState<string[] | null>(null);
  const open = room.notes.filter((n) => n.state === "draft" && !aside?.includes(n.id));
  const card = open.find((n) => n.quarters) ?? open[0];
  const count = IDS.filter((q) => filled(card, q)).length;
  const leads = Object.fromEntries((room.wall_questions ?? []).map((q) => [q.id, q.lead]));
  const draftQ = IDS.find((q) => card?.quarter_drafts?.[q]);
  const asking = draftQ ?? IDS.find((q) => card && !filled(card, q));
  const names = room.names ?? "choice";

  async function run(work: () => Promise<Room>, done?: () => void) {
    setBusy(true);
    setError(null);
    try {
      setRoom((await work()) as WallRoom);
      done?.();
      onChange?.();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : t.failed);
    } finally {
      setBusy(false);
    }
  }
  const answer = () =>
    void run(
      () => (card && asking ? saveNote(sessionId, card.id, { quarters: { [asking]: { text: text.trim() } } } as Change) : sendMessage(sessionId, text, "answer")),
      () => setText(""),
    );
  const keep = () => void run(() => saveNote(sessionId, card!.id, { quarters: { [draftQ!]: { keep: true } } } as Change));
  const canWall = !!card && count >= t.minAnswered && room.open;
  const drafted = card && asking ? card.quarter_drafts?.[asking] : undefined;

  return (
    <div className="ds-north">
      <div className="ds-north__who">
        <span aria-hidden="true" className="ds-north__mark">N</span>
        <strong>{t.northName}<span>{t.northRole}</span></strong>
      </div>
      {card && asking ? (
        <div data-testid="north-question">
          <Turn you={false} now>
            <span className="ds-wall-sr">{t.askingNow}: </span>
            <span>{leads[asking] ?? ""}</span>
            {drafted ? <><span>{drafted.text}</span><span className="ds-north__from">{t.readFrom(drafted.from)}</span></> : null}
          </Turn>
        </div>
      ) : null}
      <div>
        <p className="ds-north__card">{t.yourCard(count)}</p>
        <div className="ds-north__bars">
          {IDS.map((q) => <span key={q} data-testid="bar" data-filled={filled(card, q)} className={`ds-north__bar${filled(card, q) ? " ds-north__bar--on" : ""}`} />)}
        </div>
      </div>
      <ol aria-live="polite" className="ds-north__thread">
        {room.turns.map((turn) => <li key={turn.id}><Turn you={turn.role === "person"}>{turn.text}</Turn>{turn.role === "north" ? <PlayButton sessionId={sessionId} voice={voice} text={turn.text} /> : null}</li>)}
        {card ? IDS.filter((q) => filled(card, q)).map((q) => (
          <li key={q} className="ds-north__thread">
            <Turn you={false}>{leads[q] ?? ""}</Turn>
            <Turn you>{card.quarters?.[q].text}</Turn>
          </li>
        )) : <li className="ds-north__muted">{t.noQuestion}</li>}
      </ol>
      <label className="ds-north__answer">
        {t.yourAnswer}
        <textarea value={text} placeholder={t.answerHint} disabled={busy || !room.open} onChange={(e) => setText(e.target.value)} />
      </label>
      <VoiceBar sessionId={sessionId} voice={voice} onSwitch={(on) => void setOn(on)} disabled={busy} bare onText={(s) => setText((p) => combineText(p, s))} />
      {error ? <p role="alert" className="ds-north__error">{error}</p> : null}
      <div className="ds-north__actions">
        <Button variant="primary" disabled={busy || !text.trim() || !room.open} onClick={answer}>{t.answer}</Button>
        <Button disabled={busy || !draftQ} onClick={keep}>{t.stillRight}</Button>
        <Button disabled={busy || !canWall} onClick={() => void run(() => submitNote(sessionId, card!.id))}>{t.putOnWall}</Button>
      </div>
      {card && !canWall ? <p className="ds-north__muted">{t.needTwo}</p> : null}
      {card ? <Button disabled={busy} onClick={() => setAside(room.notes.filter((n) => n.state === "draft").map((n) => n.id))}>{somethingNew}</Button> : null}
      <label className="ds-north__choice">
        <input type="checkbox" disabled={!card || busy || names !== "choice"} checked={card?.anonymous === true}
          onChange={(e) => void run(() => saveNote(sessionId, card!.id, { anonymous: e.target.checked }))} />
        <span>{t.anonymous}</span>
      </label>
      <label className="ds-north__choice">
        <input type="checkbox" disabled={!card || busy} checked={card?.restricted === true}
          onChange={(e) => void run(() => saveNote(sessionId, card!.id, { restricted: e.target.checked }))} />
        <span>{t.sealBox}</span>
      </label>
    </div>
  );
}
