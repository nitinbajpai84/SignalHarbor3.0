import type { ReactNode } from "react";

import StatusPill, { type PillTone } from "../../../components/StatusPill";
import type { Seat, SeatState } from "../api";
import { m1Room } from "../copy";

const STATE_WORD: Record<SeatState, string> = {
  free: m1Room.seat.free,
  taken: m1Room.seat.taken,
  revoked: m1Room.seat.revoked,
};
const STATE_TONE: Record<SeatState, PillTone> = { free: "muted", taken: "success", revoked: "danger" };

function initials(name: string | undefined, n: number): string {
  const words = (name ?? "").split(/\s+/).filter(Boolean);
  return words.length > 0 ? words.slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("") : String(n);
}

const style = `
  .m1-seats { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .m1-seat { background: var(--surface-elevated); border: 1px solid var(--border-hairline); border-radius: var(--radius-lg); color: var(--text-primary); }
  .m1-seat[data-state="taken"] { border-color: var(--border-luminous); }
`;

interface Props {
  seats: Seat[];
  /** What to show beside a seat (a Remove button for the organiser). */
  action?: (seat: Seat) => ReactNode;
}

/**
 * The seats at a glance, laid out as the earlier room's participants (n-room-participants of n-person-chip): free, taken
 * (with the name and role) or removed. Same picture for everyone, plus what `action` adds.
 */
export default function SeatPicture({ seats, action }: Props) {
  return (
    <>
    <style>{style}</style>
    <ul className="n-room-participants m1-seats" aria-label={m1Room.seat.picture}>
      {seats.map((s) => (
        <li key={s.n} className="n-step-card m1-seat" data-state={s.state}>
          <div className="n-person-chip">
            <div className="avatar" aria-hidden="true">
              {s.state === "taken" ? initials(s.name, s.n) : s.n}
            </div>
            <div>
              <div className="name">{m1Room.seat.seat(s.n)}</div>
              {s.state === "taken" ? ( // a removed person's name is not shown again: the seat just says "Removed"
                <div className="role">
                  {s.name ? `${s.name}${s.role ? `, ${s.role}` : ""}` : ""}
                  {s.late ? ` (${m1Room.organiser.cameLate})` : ""}
                </div>
              ) : null}
            </div>
          </div>
          <div className="n-flex wrap">
            <StatusPill tone={STATE_TONE[s.state]}>{STATE_WORD[s.state]}</StatusPill>
            {s.mine ? <StatusPill tone="info">{m1Room.seat.you}</StatusPill> : null}
          </div>
          {action ? action(s) : null}
        </li>
      ))}
    </ul>
    </>
  );
}
