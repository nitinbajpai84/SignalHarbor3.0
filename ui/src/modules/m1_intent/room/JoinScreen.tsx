import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../../api/client";
import ScreenState from "../../../components/ScreenState";
import { useSession } from "../../../useSession";
import { joinRoom, pGet, sessionPath, type JoinView, type RoomView, type SeatMe } from "../api";
import LaterStages from "../board/LaterStages"; // M1-P07: the board and back in the room
import { usePolled } from "../board/usePolled";
import BriefingScreen from "../briefing/BriefingScreen"; // M1-P05
import { m1Flow, m1Room } from "../copy";
import PrivateRoomScreen from "../private_room/PrivateRoomScreen"; // M1-P05
import { clearToken, loadTokenByCode, saveToken } from "./guestToken";
import Lobby from "./Lobby";

/** M1-P05: the stages a seated person walks, on this one page: the lobby, the briefing, the private room. No address to type. */
const LATER = new Set(["board", "together", "signing", "closed"]);

function GuestStages(props: { sessionId: string; token: string | null; seat: SeatMe; minutes: number; onEnded: () => void }) {
  const [screen, setScreen] = useState<"lobby" | "briefing" | "room">("lobby");
  // the session moves on without the guest: once the rooms close, follow it to the board and back in the room
  const live = usePolled(() => pGet<RoomView>(props.sessionId, `${sessionPath(props.sessionId)}/lobby`), `guest-stage:${props.sessionId}`, 10000);
  const [later, setLater] = useState(false); // once there, stay: a hold (paused) is shown by the later stages themselves
  if (!later && live.data && LATER.has(live.data.state)) setLater(true);
  if (later) return <LaterStages sessionId={props.sessionId} />;
  if (screen === "room") return <PrivateRoomScreen sessionId={props.sessionId} onBack={() => setScreen("briefing")} />;
  if (screen === "briefing") {
    return (
      <>
        <p>
          <button type="button" className="n-btn" onClick={() => setScreen("lobby")}>
            {m1Flow.toLobby}
          </button>
        </p>
        <BriefingScreen sessionId={props.sessionId} onRoom={() => setScreen("room")} />
      </>
    );
  }
  return <Lobby {...props} onBriefing={() => setScreen("briefing")} />;
}

/** The four opening lines (from the sketch). The seat picture gives who is in the room; the join answer carries no session purpose yet. */
const opening = {
  who: (taken: number, total: number) => `Who is in the room: ${taken} of ${total} seats are taken.`,
  purpose: "What it is for: Not available yet.",
  contribute: "What you can contribute: your own view, in your own private room.",
  stays: "Anything you upload stays with this company's agents.",
};

/** What the seat form says above the seats: a plain note, or (a seat just taken) an error. */
interface Note {
  text: string;
  error: boolean;
}

type Phase =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "refused"; message: string; otherCompany: boolean }
  | { kind: "pick"; view: JoinView; note: Note | null }
  | { kind: "lobby"; sessionId: string; token: string | null; seat: SeatMe; minutes: number };

function failure(e: unknown): Phase {
  if (e instanceof ApiError && e.status === 403) {
    return { kind: "refused", message: e.message || m1Room.join.notWorking, otherCompany: true };
  }
  if (e instanceof ApiError && (e.status === 404 || e.status === 409 || e.status === 401)) {
    return { kind: "refused", message: e.message || m1Room.join.notWorking, otherCompany: false };
  }
  return { kind: "error", message: e instanceof ApiError && e.status === 0 ? m1Room.join.network : "" };
}

/** The page a person lands on from the join link: no account needed. Pick a free seat, give a name and a role, wait in the lobby. */
export default function JoinScreen({ code }: { code: string }) {
  const { user, signOut } = useSession();
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    const stored = loadTokenByCode(code);
    setPhase({ kind: "loading" });
    joinRoom(code, stored?.token)
      .then((v) => {
        if (!live) return;
        if (v.me) {
          setPhase({ kind: "lobby", sessionId: v.session_id, token: v.signed_in ? null : (stored?.token ?? null), seat: v.me, minutes: v.length_minutes });
          return;
        }
        const earlier = !v.signed_in && stored !== null && stored.sessionId === v.session_id;
        if (earlier) clearToken(v.session_id); // that seat no longer works: only a free seat is left to take
        setPhase({ kind: "pick", view: v, note: earlier ? { text: m1Room.join.earlierGone, error: false } : null });
      })
      .catch((e: unknown) => {
        // a closed or withdrawn link: the seat held for it is of no use any more
        if (stored && e instanceof ApiError && (e.status === 404 || e.status === 409)) clearToken(stored.sessionId);
        if (live) setPhase(failure(e));
      });
    return () => {
      live = false;
    };
  }, [code, attempt]);

  if (phase.kind === "lobby") {
    return (
      <GuestStages
        sessionId={phase.sessionId}
        token={phase.token}
        seat={phase.seat}
        minutes={phase.minutes}
        onEnded={() => {
          clearToken(phase.sessionId);
          setAttempt((a) => a + 1);
        }}
      />
    );
  }
  if (phase.kind === "pick") {
    const free = phase.view.seats.filter((s) => s.state === "free");
    return (
      <ScreenState state={free.length === 0 ? "empty" : "populated"} message={m1Room.join.full}>
        <SeatForm
          view={phase.view}
          note={phase.note}
          signedInName={phase.view.signed_in ? (user?.display_name ?? null) : null}
          code={code}
          onSeated={(sessionId, token, seat, signedIn, minutes) => {
            if (token) saveToken({ token, sessionId, code });
            setPhase({ kind: "lobby", sessionId, token: signedIn ? null : token, seat, minutes });
          }}
          onRefresh={(view, note) => setPhase({ kind: "pick", view, note })}
        />
      </ScreenState>
    );
  }
  return (
    <>
      <ScreenState
        state={phase.kind === "loading" ? "loading" : phase.kind === "refused" ? "refused" : "error"}
        message={phase.kind === "loading" ? undefined : phase.message || undefined}
        onRetry={() => setAttempt((a) => a + 1)}
      />
      {phase.kind === "refused" && phase.otherCompany ? (
        <button type="button" className="n-btn" onClick={() => void signOut()}>
          {m1Room.join.signOut}
        </button>
      ) : null}
    </>
  );
}

const style = `
  .m1-join { display: flex; flex-direction: column; gap: 14px; color: var(--text-primary); }
  .m1-opening { margin: 0; padding: 12px 16px 12px 32px; background: var(--accent-soft); border: 1px solid var(--border-hairline); border-radius: var(--radius-lg); }
  .m1-join .m1-choice { display: flex; gap: 8px; padding: 8px 10px; border: 1px solid var(--border-hairline); border-radius: var(--radius-md); margin-bottom: 6px; }
`;

interface FormProps {
  view: JoinView;
  note: Note | null;
  signedInName: string | null;
  code: string;
  onSeated: (sessionId: string, token: string | null, seat: SeatMe, signedIn: boolean, minutes: number) => void;
  onRefresh: (view: JoinView, note: Note) => void;
}

function SeatForm({ view, note, signedInName, code, onSeated, onRefresh }: FormProps) {
  const [seat, setSeat] = useState<number | null>(null);
  const [name, setName] = useState(signedInName ?? "");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; field: string | null } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (seat === null) {
      setError({ message: m1Room.join.needSeat, field: "seat" });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const v = await joinRoom(code, undefined, { n: seat, name, role });
      if (v.me) onSeated(v.session_id, v.token, v.me, v.signed_in, v.length_minutes);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // the seat was just taken (or is not available): show the fresh picture with the plain message
        try {
          onRefresh(await joinRoom(code), { text: err.message, error: true });
          return;
        } catch {
          // fall through to the message below
        }
      }
      setError({
        message: err instanceof ApiError && err.message ? err.message : m1Room.join.network,
        field: err instanceof ApiError ? err.field : null,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
    <style>{style}</style>
    <form className="m1-join" onSubmit={(e) => void submit(e)} aria-label={m1Room.join.title}>
      <ul className="m1-opening" aria-label="About this session">
        <li>{opening.who(view.seats.filter((s) => s.state === "taken").length, view.seats.length)}</li>
        <li>{opening.purpose}</li>
        <li>{opening.contribute}</li>
        <li>{opening.stays}</li>
      </ul>
      <div className="n-room-purpose">{m1Room.join.intro}</div>
      {signedInName ? <p className="n-muted">{m1Room.join.signedInAs(signedInName)}</p> : null}
      {note ? (
        <p role={note.error ? "alert" : "status"} className={note.error ? "state state-error" : "state n-muted"}>
          {note.text}
        </p>
      ) : null}
      <fieldset className="m1-fieldset">
        <legend>{m1Room.join.chooseSeat}</legend>
        {view.seats.map((s) => (
          <label key={s.n} className="m1-choice">
            <input
              type="radio"
              name="seat"
              value={s.n}
              aria-label={m1Room.seatLabel(s.n, s.state === "free" ? m1Room.seat.free : s.state === "taken" ? m1Room.seat.taken : m1Room.seat.revoked)}
              disabled={s.state !== "free"}
              checked={seat === s.n}
              onChange={() => setSeat(s.n)}
            />
            <span>
              <strong>{m1Room.seat.seat(s.n)}</strong>{" "}
              <span className="m1-help">{s.state === "free" ? m1Room.seat.free : s.state === "taken" ? m1Room.seat.taken : m1Room.seat.revoked}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label>
        {m1Room.join.name}
        <input type="text" required maxLength={60} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        {m1Room.join.role}
        <input type="text" required maxLength={80} value={role} onChange={(e) => setRole(e.target.value)} />
        <span className="m1-help">{m1Room.join.roleHelp}</span>
      </label>
      {error ? (
        <p role="alert" className="state state-error">
          {error.message}
        </p>
      ) : null}
      <button type="submit" className="n-btn primary" disabled={busy}>
        {busy ? m1Room.join.busy : m1Room.join.submit}
      </button>
    </form>
    </>
  );
}
