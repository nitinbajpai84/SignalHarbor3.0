import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import Sticky from "../../../components/Sticky";
import { PRIORITIES, type Priority, type Room, type RoomNote } from "./roomApi";
import NoteForm from "./NoteForm"; // M1-P05
import { m1Notes } from "../copy"; // M1-P05
import { m1Lean, m1PrivateRoom as room } from "../copy";
import { saveNote } from "./roomApi";
import { wallCopy } from "../wall/copy";

interface Props {
  notes: RoomNote[];
  open: boolean;
  busy: boolean;
  onCorrect: (note: RoomNote) => void;
  onPriority: (note: RoomNote, priority: Priority | null) => void;
  onPractice: (note: RoomNote, action: "add" | "dismiss") => void;
  /** M1-P05: what the note form needs. */
  sessionId: string;
  form: Room["form"];
  northAvailable: boolean;
  onRoom: (room: Room) => void;
  kinds?: Room["kinds"];
  names?: Room["names"];
  north?: Room["north"];
}

/**
 * The person's note drafts as the earlier prototype's yellow stickies (n-sticky n-sticky-yellow, the words in italic Fraunces),
 * in their own words, with the industry practice card (copper "you decide" block) where the pack matched.
 */
export default function NotesPanel({ notes, open, busy, onCorrect, onPriority, onPractice, sessionId, form, northAvailable, onRoom, kinds, names, north }: Props) {
  // LI-M1: a draft North wrote waits for Keep, Change or Anonymous
  const decide = (id: string, change: { keep?: boolean; anonymous?: boolean }) => void saveNote(sessionId, id, change).then(onRoom, () => undefined);
  return (
    <Panel title={room.notesHeading} eyebrow={room.notesCount(notes.length)} className="m1-notes">
      <p className="n-muted">{room.notesHelp}</p>
      {notes.length === 0 ? (
        <p className="n-empty ebody">{room.notesEmpty}</p>
      ) : (
        <ul className="m1-note-list">
          {notes.map((n) => (
            <li key={n.id} aria-label={n.text}>
              <Sticky tone="yellow" className="m1-note-sticky" question={n.text}>
                <div className="m1-note-meta">
                  {n.source.kind === "library" ? <StatusPill tone="info">{room.fromLibrary}</StatusPill> : null}
                  {n.confirmed === false ? <StatusPill tone="warning">{m1Lean.room.draftBy}</StatusPill> : null}
                  {n.source.from && (n.source.kind === "interview" || n.source.kind === "north") ? <span className="m1-help">{m1Lean.room.draftFrom(n.source.from)}</span> : null}
                  {kinds?.length ? <StatusPill tone="muted">{kinds.find((k) => k.id === (n.kind ?? "intent"))?.label}</StatusPill> : null}
                  {names === "named" || names === "anonymous" ? null : <StatusPill tone="info">{n.anonymous ? m1Notes.anonymousPill : m1Notes.byNamePill}</StatusPill>}
                  {n.restricted ? <StatusPill tone="muted">{wallCopy.sealedLabel}</StatusPill> : null}
                  {n.state === "submitted" ? <StatusPill tone="success">{m1Notes.submitted}</StatusPill> : null}
                  <label className="m1-priority">
                    {room.priority}
                    <select
                      value={n.priority ?? ""}
                      disabled={!open || busy}
                      onChange={(e) => onPriority(n, e.target.value === "" ? null : (e.target.value as Priority))}
                    >
                      <option value="">{room.priorityNone}</option>
                      {PRIORITIES.map((p) => (
                        <option key={p} value={p}>
                          {room.priorityNames[p]}
                        </option>
                      ))}
                    </select>
                  </label>
                  {open && n.state === "draft" ? (
                    <button type="button" className="n-btn" disabled={busy} onClick={() => onCorrect(n)}>
                      {room.correct}
                    </button>
                  ) : null}
                </div>
                {n.confirmed === false && open ? (
                  <div className="m1-actions" role="group" aria-label={n.text}>
                    <button type="button" className="n-btn primary" disabled={busy} onClick={() => decide(n.id, { keep: true })}>
                      {m1Lean.room.keep}
                    </button>
                    <button type="button" className="n-btn" disabled={busy} onClick={() => onCorrect(n)}>
                      {m1Lean.room.change}
                    </button>
                    {(names ?? "choice") === "choice" && !n.anonymous ? (
                      <button type="button" className="n-btn" disabled={busy} onClick={() => decide(n.id, { anonymous: true })}>
                        {m1Lean.room.anonymous}
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {n.confirmed === false ? (
                  <details>
                    <summary>{m1Lean.room.writeMyself}</summary>
                    <NoteForm sessionId={sessionId} note={n} form={form} open={open} northAvailable={northAvailable} onRoom={onRoom} kinds={kinds} names={names} north={north} />
                  </details>
                ) : (
                  <NoteForm sessionId={sessionId} note={n} form={form} open={open} northAvailable={northAvailable} onRoom={onRoom} kinds={kinds} names={names} north={north} />
                )}
                {n.practice && n.practice.decision === "offered" ? (
                  <div className="n-suggest-block m1-practice" role="group" aria-label={room.practiceLabel}>
                    <div className="n-suggest-label">{room.practiceLabel}</div>
                    <span className="n-illus">{room.illustrative}</span>
                    <ul>
                      {n.practice.items.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                    <p className="n-muted">{n.practice.company_decides}</p>
                    {open ? (
                      <div className="m1-actions">
                        <button type="button" className="n-btn primary" disabled={busy} onClick={() => onPractice(n, "add")}>
                          {room.practiceAdd}
                        </button>
                        <button type="button" className="n-btn" disabled={busy} onClick={() => onPractice(n, "dismiss")}>
                          {room.practiceDismiss}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {n.practice?.decision === "added" ? (
                  <div className="n-suggest-block m1-practice">
                    <div className="n-suggest-label">{room.practiceLabel}</div>
                    <span className="n-illus">{room.illustrative}</span>
                    <p>{room.practiceAdded}</p>
                    <ul>
                      {n.practice_added.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {n.practice?.decision === "dismissed" ? <p className="n-muted">{room.practiceDismissed}</p> : null}
              </Sticky>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
