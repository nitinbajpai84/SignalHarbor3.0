import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import type { WallCard } from "../../modules/m1_intent/wall/Card";
import Lane from "../../modules/m1_intent/wall/Lane";
import WallScreen, { LANES } from "../../modules/m1_intent/wall/WallScreen";
import "../../modules/m1_intent/wall/wall.css";
import IntentHeader, { type HeaderInfo } from "../IntentHeader";

/** `GET /api/intents/<id>/wall`: the session this intent's wall runs in, what the viewer may do, and the header fields. */
interface WallInfo {
  intent_id: string;
  session_id: string | null;
  role: "organiser" | "sponsor" | "participant" | "observer" | "affected";
  can_add: boolean;
  intent: { title: string; purpose: string; state: string | null; ends: string | null };
  stages: { key: string; name: string; state: string | null }[];
  wall: { rooms_closed_at: string | null; frozen_at: string | null };
  people: HeaderInfo["people"];
  /** Readers (sponsor, observer, affected) get their lane cards here; the session routes serve only seat holders and the organiser. */
  cards: WallCard[] | null;
}

export const wallViewCopy = {
  here: "Think unfiltered",
  noWall: "Not available yet: the wall for this intent has not been opened.",
  readOnly: "You can read this wall. You do not add cards.",
  frozenLink: "Open the frozen wall as charter page one",
  loading: "Loading the wall",
  notFound: "We could not find that.",
  notOpen: (who: string | null) => `The wall is not open yet. ${who ? `${who} opens it.` : "The organiser opens it."}`,
  refused: "You cannot open this wall yet. Ask the organiser to add you.",
  overdue: "Overdue",
};

/* The intent header carries the crumb, so the wall's own is hidden; the wall's North panel replaces the dock here at desktop width (file 23); at phone width the dock's North button stays, and only a
   participant has a room to talk in; the heading takes the ink colour the wall header would mute. */
const wallStyle = `
.ds-wall-intent > .ds-wall:not(:first-child) > .ds-wall__head > .ds-wall__crumb { display: none; }
.ds-wall-intent > .ds-wall:not(:first-child) [data-testid="purpose"] > span:first-child { display: none; }
.ds-wall-intent [data-testid="intent-clock"] { display: none; }
.ds-wall-intent .ds-wall__title { color: var(--ds-ink); }
.ic-with-north:has(.ds-wall-intent) { grid-template-columns: minmax(0, 1fr); }
@media (min-width: 600px) { .ic-with-north:has(.ds-wall-intent) > .ic-north-dock { display: none; } }
.ds-wall-intent:not(.ds-wall-intent--participant) .ds-wall__north, .ds-wall-intent:not(.ds-wall-intent--participant) .ds-wall__talk { display: none; }
.ds-wall-intent:not(.ds-wall-intent--participant) .ds-wall__body { grid-template-columns: minmax(0, 1fr); }
`;

/** The header's one count is the clock's (working days, file 07), not the calendar days between now and the end date. */
interface ClockBox { box: { state: string; unit: "days" | "hours"; working_days_left: number; hours_left: number } | null }
const clockLine = (c: ClockBox | null): string | null => {
  const b = c?.box;
  if (!b) return null;
  if (b.state === "overdue") return wallViewCopy.overdue;
  const n = b.unit === "hours" ? b.hours_left : b.working_days_left;
  return `${n} ${b.unit === "hours" ? (n === 1 ? "hour" : "hours") : (n === 1 ? "day" : "days")} left`;
};

const headerOf = (w: WallInfo): HeaderInfo => ({
  id: w.intent_id, title: w.intent.title, purpose: w.intent.purpose, state: w.intent.state, ends: w.intent.ends,
  stages: w.stages, people: w.people, frozenAt: w.wall.frozen_at,
});

/** A reader the wall route turns away: if the intent itself opens for them, the wall is simply not open yet, and the organiser is named. */
function WallRefusal({ intentId, state, message, onRetry }: { intentId: string; state: "refused" | "error" | "empty" | "loading" | "populated"; message?: string; onRetry: () => void }) {
  const [who, setWho] = useState<string | null | undefined>(undefined);
  const missing = state === "error" && (!message || message === wallViewCopy.notFound);
  useEffect(() => {
    if (!missing) return;
    apiGet<{ people?: { organiser?: { name?: string } | null } }>(`/api/intents/${intentId}`).then((h) => setWho(h.people?.organiser?.name ?? null), () => setWho(undefined));
  }, [missing, intentId]);
  if (state === "refused" || (state === "error" && message && !missing)) return <p role="status" className="ds-wall__sentence" style={{ padding: "0 var(--ds-s7)" }}>{message ?? wallViewCopy.refused}</p>;
  if (missing && who !== undefined) return <p role="status" className="ds-wall__sentence" style={{ padding: "0 var(--ds-s7)" }}>{wallViewCopy.notOpen(who)}</p>;
  return <ScreenState state={state} message={message} onRetry={onRetry} />;
}

/** /centre/intent/<id>/wall: the existing wall screen under the intent's header and stage bar. */
export default function WallView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const { state, data, message, retry } = useLoad<WallInfo>(() => apiGet(`/api/intents/${intentId}/wall`), `intent-wall:${intentId}`);
  const clock = useLoad<ClockBox>(() => apiGet(`/api/intents/${intentId}/clock`), `intent-wall-clock:${intentId}`);
  const left = clockLine(clock.data);
  const topUp = data?.can_add && data.session_id ? intentId : null;
  // North tops up the person's suggestions when they have the wall open; a failure changes nothing on screen
  useEffect(() => { if (topUp) apiSend("POST", `/api/intents/${topUp}/suggestions/refresh`, {}).catch(() => undefined); }, [topUp]);

  if (state !== "populated" || !data) {
    return state === "loading" ? <ScreenState state={state} message={wallViewCopy.loading} /> : <WallRefusal intentId={intentId} state={state} message={message} onRetry={retry} />;
  }
  return (
    <div className={`ds-wall-intent ds-wall-intent--${data.role}`} style={{ display: "flex", flexDirection: "column", width: "100%", minWidth: 0 }}>
      <style>{wallStyle}</style>
      <div className="ds-screen ds-wall" style={{ minHeight: "auto", paddingBottom: 0 }}>
        <IntentHeader info={headerOf(data)} here={wallViewCopy.here} stageKey="think_unfiltered" extra={left ? <span data-testid="wall-clock">{left}</span> : null} />
        {data.can_add ? null : <p data-testid="read-only" className="ds-wall__sentence">{wallViewCopy.readOnly}</p>}
        {data.wall.frozen_at ? <p><Link to={`/centre/intent/${intentId}/charter`}>{wallViewCopy.frozenLink}</Link></p> : null}
      </div>
      {data.cards ? (
        <div data-testid="lanes" className="ds-wall__lanes" style={{ padding: "0 var(--ds-s7)", display: "grid", gap: "var(--ds-s3)", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          {LANES.map((l) => <Lane key={l} id={l} projector={false} cards={data.cards!.filter((c) => c.lane === l)} />)}
        </div>
      ) : data.session_id ? <WallScreen sessionId={data.session_id} intentId={intentId} /> : <p role="status" className="ds-wall__sentence" style={{ padding: "0 var(--ds-s7)" }}>{wallViewCopy.noWall}</p>}
    </div>
  );
}
