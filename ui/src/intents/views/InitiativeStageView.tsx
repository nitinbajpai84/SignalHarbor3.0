import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiGet } from "../../api/client";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button } from "../../design";
import { getSession, startRoom, type SessionView } from "../../modules/m1_intent/api";
import { EventsLink } from "./EventsView";
import InvitePanel from "../../modules/m1_intent/wall/InvitePanel";
import { getPeople, type PeopleData } from "../PeoplePanel";

// The Initiative's stage view (spec 22, Screen C): the prepared wall hand-over card for the organiser, then the doors to the other views.
// The wall stays in module 1; this card only reads its session (m1 sessions/{id}) and starts its room (rooms start), both as today.

interface WallInfo { session_id: string | null; role: string; intent: { title: string; purpose: string; state: string | null; ends: string | null }; stages?: { key: string; state: string | null }[] }
interface ClockInfo { stages: { key: string; due: string | null; days?: number | null }[] }

export const stageCopy = {
  loading: "Loading this intent",
  card: "The wall is ready",
  cardOpen: "The wall is open",
  purpose: "Purpose",
  open: (until: string | null, days: number | null) => `Open ${until ? `until ${until} ` : ""}${days ? `(${days} working ${days === 1 ? "day" : "days"})` : ""}`.trim() + ".",
  lanes: "Lanes: Tracking today, Missing, Watch, Levers.",
  invited: (n: number) => `Invited: ${n} ${n === 1 ? "person" : "people"}.`,
  openWall: "Open the wall",
  opening: "Opening",
  goToWall: "Go to the wall",
  change: "Change the wall setup",
  topicTaken: "Topic already has an open wall. Change the topic.",
  openFailed: "The wall could not be opened. Try again.",
  drafts: "Invitation drafts",
  draftLine: (organiser: string) => `${organiser} has opened an Initiative and asked you to take part`,
  nobody: "Nobody was named. You can invite people from the people panel.",
  sendFrom: "Send or remind from the people panel",
  notReady: "Not available yet: the wall for this intent has not been prepared.",
  readerLead: "The wall for this intent",
  doors: "Other views",
  defineEyebrow: "Define strategically",
  defineOpen: "Define is open",
  defineLine: "The wall is frozen. The committee sorts its clusters onto shelves and confirms the definitions.",
  goToDefine: "Go to Define",
  frozenWall: "Open the frozen wall",
};

const DOORS: [string, string][] = [["define", "Define strategically"], ["charter", "Charter and signature"], ["build-ready", "Build-ready check"], ["people", "People and roles"],
  ["share", "Share links"], ["close", "Close this intent"]];

const nice = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : null);

function Doors({ id }: { id: string }) {
  return (
    <Panel title={stageCopy.doors}>
      <ul>{DOORS.map(([k, name]) => <li key={k}><Link to={`/centre/intent/${id}/${k}`}>{name}</Link></li>)}<li><EventsLink intentId={id} /></li></ul>
    </Panel>
  );
}

/** /centre/intent/<id> for an Initiative. */
export default function InitiativeStageView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const wall = useLoad<WallInfo>(() => apiGet(`/api/intents/${intentId}/wall`), `initiative-wall:${intentId}`);
  const [session, setSession] = useState<SessionView | null>(null);
  const [due, setDue] = useState<string | null>(null);
  const [wallDays, setWallDays] = useState<number | null>(null);
  const [people, setPeople] = useState<PeopleData | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const sid = wall.data?.session_id ?? null;
  const organiser = wall.data?.role === "organiser";

  const read = useCallback(() => { if (sid) getSession(sid).then(setSession, () => setSession(null)); }, [sid]);
  useEffect(() => {
    if (!organiser) return;
    read();
    apiGet<ClockInfo>(`/api/intents/${intentId}/clock`).then((c) => { const w = c.stages.find((s) => s.key === "think_unfiltered"); setDue(w?.due ?? null); setWallDays(w?.days ?? null); }, () => { setDue(null); setWallDays(null); });
    getPeople(intentId).then(setPeople, () => setPeople(null));
  }, [organiser, read, intentId]);

  if (wall.state !== "populated" || !wall.data) return <ScreenState state={wall.state} message={wall.state === "loading" ? stageCopy.loading : wall.message} onRetry={wall.retry} />;
  const w = wall.data;
  const started = !!session && session.state !== "draft";
  const days = wallDays; // from the stage's dates, so the count agrees with the clock
  const go = async () => {
    if (!sid) return;
    setBusy(true); setProblem("");
    try { await startRoom(sid); read(); } catch (e) { setProblem(e instanceof ApiError && e.status === 409 ? stageCopy.topicTaken : stageCopy.openFailed); } finally { setBusy(false); }
  };
  const named = (people?.people ?? []).filter((p) => p.role !== "organiser" && p.status !== "removed" && p.status !== "declined" && p.person_id !== people?.me?.person_id);
  const inviter = people?.people.find((p) => p.role === "organiser")?.name ?? "The organiser";

  return (
    <div style={{ display: "grid", gap: "var(--ds-s4)" }}>
      {w.stages?.some((s) => s.key === "think_unfiltered" && s.state === "closed") ? ( // the wall froze: the intent page moves on to Define (spec 50 step 5)
        <Panel title={stageCopy.defineOpen} eyebrow={stageCopy.defineEyebrow}>
          <p>{stageCopy.defineLine}</p>
          <div style={{ display: "flex", gap: "var(--ds-s3)", flexWrap: "wrap", alignItems: "center" }}>
            <Link className="ds-btn" to={`/centre/intent/${intentId}/define`}>{stageCopy.goToDefine}</Link>
            <Link to={`/centre/intent/${intentId}/wall`}>{stageCopy.frozenWall}</Link>
          </div>
        </Panel>
      ) : !sid ? <p role="status">{stageCopy.notReady}</p> : !organiser ? (
        <Panel title={stageCopy.readerLead}><p><Link to={`/centre/intent/${intentId}/wall`}>{stageCopy.goToWall}</Link></p></Panel>
      ) : (
        <>
          <Panel title={started ? stageCopy.cardOpen : stageCopy.card} eyebrow="Think unfiltered">
            <div data-testid="handover" style={{ display: "grid", gap: "var(--ds-s2)" }}>
              <p><strong>{stageCopy.purpose}:</strong> {w.intent.purpose}</p>
              <p>{stageCopy.open(nice(due), days)}</p>
              <p>{stageCopy.lanes}</p>
              <p>{stageCopy.invited(people?.counts?.named ?? named.length)}</p>
              {problem ? <p role="alert">{problem}</p> : null}
              <div style={{ display: "flex", gap: "var(--ds-s3)", flexWrap: "wrap", alignItems: "center" }}>
                {started
                  ? <Link className="ds-btn" to={`/centre/intent/${intentId}/wall`}>{stageCopy.goToWall}</Link>
                  : <Button variant="primary" disabled={busy || !session} style={{ minHeight: 44 }} onClick={() => void go()}>{busy ? stageCopy.opening : stageCopy.openWall}</Button>}
                {started ? null : <Link to={`/modules/m1_intent/sessions/${sid}`}>{stageCopy.change}</Link>}
              </div>
            </div>
          </Panel>
          {started ? <InvitePanel sessionId={sid} /> : null}
          <Panel title={stageCopy.drafts}>
            {named.length === 0 ? <p>{stageCopy.nobody}</p> : (
              <>
                <ul data-testid="drafts">{named.map((p) => <li key={p.person_id}><strong>{p.name}</strong>: {stageCopy.draftLine(inviter)}</li>)}</ul>
                <p><Link to={`/centre/intent/${intentId}/people`}>{stageCopy.sendFrom}</Link></p>
              </>
            )}
          </Panel>
        </>
      )}
      <Doors id={intentId} />
    </div>
  );
}
