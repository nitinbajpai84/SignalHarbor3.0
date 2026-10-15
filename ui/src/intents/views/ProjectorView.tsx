import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import { usePolled } from "../../modules/m1_intent/board/usePolled";
import { wallCopy } from "../../modules/m1_intent/wall/copy";
import "../phone.css";

/** What the projector reads from GET /api/intents/{id}. Counts and the question; never a name. */
export interface ProjectorIntent {
  type?: string;
  state?: string;
  live?: boolean;
  time_box?: { ends?: string | null } | null;
  session?: { current_question?: { text?: string } | null } | null;
  share?: { short?: string | null } | null;
  review_item?: { text?: string } | null;
}
/** GET /api/intents/{id}/wall: the viewer's role, per-lane counts and the people count (numbers only, never a card). */
interface ProjectorWall {
  role?: string;
  counts?: { per_lane?: Partial<Record<LaneId, number>> } | null;
  people?: { invited?: number | null; joined?: number | null } | null;
}
type LaneId = keyof typeof wallCopy.lanes;

const LANES = Object.keys(wallCopy.lanes) as LaneId[];
const FAILS_BEFORE_RECONNECTING = 3;

export const projectorCopy = {
  back: wallCopy.exitProjector,
  noQuestion: "No question is set yet.",
  noEnd: "Not available yet",
  noEndLine: "The session has no end set.",
  over: "Over time",
  closed: "Session closed",
  join: "Join: ",
  noShare: "Turn on sharing to show the join code.",
  turnOn: "Turn on sharing",
  people: (n: number, of?: number | null) => (of ? `${n} / ${of} people` : n === 0 ? "No one has joined yet" : `${n} ${n === 1 ? "person" : "people"}`),
  reconnecting: "Reconnecting",
  na: "Not available yet",
  shareError: "Sharing could not be turned on. Try again.",
  loading: "Loading",
  error: "The projector could not load. Check the connection and reload.",
};

/** mm:ss under one hour, h:mm over; null when past the end. */
export function clockText(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  return now;
}

/** The short link as shown: a full address stays as it is, a bare code becomes the join page of this app. */
function joinLink(short: string): string {
  return /^https?:\/\//.test(short) ? short : `${window.location.origin}/join/${short}`;
}

/**
 * /centre/intent/<id>/projector (file 17). Full screen, no names, no card text: lane counts, the current question, the clock,
 * the join link, a people count. Organiser only: the server refuses anyone else and the person is sent back to the intent screen.
 */
export default function ProjectorView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const navigate = useNavigate();
  const intent = usePolled<ProjectorIntent>(() => apiGet<ProjectorIntent>(`/api/intents/${encodeURIComponent(intentId)}`), `proj:${intentId}`);
  const counts = usePolled<ProjectorWall>(() => apiGet<ProjectorWall>(`/api/intents/${encodeURIComponent(intentId)}/wall`), `projc:${intentId}`);
  const now = useNow();
  const [shareProblem, setShareProblem] = useState(false);

  // consecutive failed polls: the last numbers stay up, a strip says so after three
  const fails = useRef(0);
  const [failed, setFailed] = useState(0);
  useEffect(() => {
    const bad = intent.failure !== null || counts.failure !== null;
    fails.current = bad ? fails.current + 1 : 0;
    setFailed(fails.current);
  }, [intent.failure, counts.failure, intent.data, counts.data]);

  // full screen on arrival, Escape leaves the route
  useEffect(() => {
    document.documentElement.requestFullscreen?.().catch(() => undefined);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") navigate(-1); };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
    };
  }, [navigate]);

  const status = [intent.failure, counts.failure].map((f) => (f instanceof ApiError ? f.status : 0));
  const refused = intent.state === "refused" || counts.state === "refused" || status.some((x) => x === 403 || x === 404);
  // a brainstorm has its own room screen (spec 36 Screen C)
  if (intent.data?.type === "brainstorm") return <Navigate to={`/centre/intent/${encodeURIComponent(intentId)}/session?display=projector`} replace />;
  // organiser only (file 17): the wall read names the viewer's role; nothing shows until it has said so
  if (refused || (counts.data && counts.data.role !== "organiser")) return <Navigate to={`/centre/intent/${encodeURIComponent(intentId)}`} replace />;
  const d = counts.data ? intent.data : undefined;
  const live = d ? (d.live ?? !["closing", "closed", "cancelled"].includes(d.state ?? "")) : false;
  const question = d?.review_item?.text ?? d?.session?.current_question?.text ?? "";
  const ends = d?.time_box?.ends ? Date.parse(d.time_box.ends) : NaN;
  const left = Number.isNaN(ends) ? null : Math.floor((ends - now) / 1000);
  const people = counts.data?.people?.joined ?? counts.data?.people?.invited ?? undefined;
  const short = d?.share?.short ?? null;

  const turnOnSharing = () => {
    setShareProblem(false);
    apiSend("POST", `/api/intents/${encodeURIComponent(intentId)}/share`, {}).then(intent.reload, () => setShareProblem(true));
  };

  return (
    <main className="ic-proj" aria-label="Projector view">
      <Link to={`/centre/intent/${encodeURIComponent(intentId)}`} className="ds-chip ic-proj__back" onClick={(e) => { e.preventDefault(); navigate(-1); }}>{projectorCopy.back}</Link>

      {(intent.state === "loading" || counts.state === "loading") && !d ? <p role="status">{projectorCopy.loading}</p> : null}
      {(intent.state === "error" && !d) ? <p role="alert">{projectorCopy.error}</p> : null}

      <section className="ic-proj__top">
        {question ? <p className="ic-proj__q" data-testid="question">{question}</p> : <p className="ic-proj__q ic-proj__q--none" data-testid="question">{projectorCopy.noQuestion}</p>}
        <div className="ic-proj__clock" data-testid="clock">
          {d && !live && d.state ? (
            <p className="ic-proj__time">{projectorCopy.closed}</p>
          ) : left === null ? (
            <>
              <p className="ic-proj__time ic-proj__count--na">{projectorCopy.noEnd}</p>
              <p className="ic-proj__hint">{projectorCopy.noEndLine}</p>
            </>
          ) : left < 0 ? (
            <p className="ic-proj__time ic-proj__time--over">{projectorCopy.over}</p>
          ) : (
            <p className="ic-proj__time">{clockText(left)}</p>
          )}
        </div>
      </section>

      <section className="ic-proj__lanes" data-testid="lanes">
        {LANES.map((l) => {
          const n = counts.data?.counts?.per_lane?.[l];
          return (
            <section key={l} aria-label={wallCopy.lanes[l].name} className="ic-proj__lane">
              <h2>{wallCopy.lanes[l].name}</h2>
              {typeof n === "number" ? <p className="ic-proj__count" data-testid={`count-${l}`}>{n}</p> : <p className="ic-proj__count ic-proj__count--na" data-testid={`count-${l}`}>{projectorCopy.na}</p>}
            </section>
          );
        })}
      </section>

      <section className="ic-proj__bottom">
        <div className="ic-proj__join" data-testid="join">
          {short ? (
            <span>{projectorCopy.join}<strong>{joinLink(short)}</strong></span>
          ) : d ? (
            <>
              <span>{projectorCopy.noShare}</span>
              <button type="button" className="ds-btn ds-btn--primary" onClick={turnOnSharing}>{projectorCopy.turnOn}</button>
              {shareProblem ? <span role="alert">{projectorCopy.shareError}</span> : null}
            </>
          ) : null}
        </div>
        <div className="ic-proj__meta">
          {typeof people === "number" ? <span data-testid="people">{projectorCopy.people(people, counts.data?.people?.invited)}</span> : null}
          {live ? <span className="ic-proj__live">{wallCopy.live}</span> : null}
        </div>
      </section>

      {failed >= FAILS_BEFORE_RECONNECTING ? <p className="ic-proj__retry" role="status">{projectorCopy.reconnecting}</p> : null}
    </main>
  );
}
