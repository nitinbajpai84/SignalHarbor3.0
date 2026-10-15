import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiSend, apiGet } from "../../../api/client";
import { Button, Chip, EmptyState } from "../../../design";
import { getBoard, getBoardCounts, getRoom as getLobby, getSession, type BoardNote, type BoardView } from "../api";
import { getRoom, pickUpSuggestion } from "../private_room/roomApi";
import { useLoad } from "../useLoad";
import type { WallCard } from "./Card";
import { closesWhen, wallCopy as t } from "./copy";
import InvitePanel from "./InvitePanel";
import Lane from "./Lane";
import NorthPanel from "./NorthPanel";
import StageBar from "./StageBar";
import WallState from "./WallState";
import "./wall.css";

export const LANES: WallCard["lane"][] = ["intent", "pain_point", "future_signal", "lever"];
const PHONE = 700;

/** Fields the server may serve on a card later; read when present, never required. */
interface Extra { quarters?: number | Record<string, { text?: string; mark?: string }>; guessed?: number; sealed?: boolean; restricted?: boolean; area?: string; suggestion?: { from: string }; author_name?: string }
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
/** The board serves a count; the room serves the four answers themselves: count the ones given. */
const answered = (q: Extra["quarters"]): number | null =>
  q && typeof q === "object" ? Object.values(q).filter((c) => !!c?.text && c.mark !== "unknown").length : num(q);

const toCard = (n: (BoardNote | { id: string; text: string; anonymous: boolean; kind?: WallCard["lane"]; confirmed?: boolean | null; state?: string }) & Extra, mine: boolean): WallCard => ({
  id: n.id, lane: n.kind ?? "intent", text: n.text, anonymous: n.anonymous, author: n.author_name, mine,
  quarters: answered(n.quarters), guessed: num(n.guessed) ?? 0, sealed: !!(n.sealed || n.restricted), area: n.area,
  suggestionFrom: n.suggestion?.from, draft: "state" in n && n.state === "draft",
});

/** North's suggestion rows in the room view (`suggestions`): one dashed card each, under the person's own. */
interface SuggestionRow { id: string; text: string; kind: WallCard["lane"]; from: string }
const suggestionCards = (rows: SuggestionRow[] = []): WallCard[] =>
  rows.map((r) => ({ id: r.id, lane: r.kind, text: r.text, anonymous: true, mine: false, quarters: null, guessed: 0, sealed: false, suggestionFrom: r.from }));

/** The room's view of the wall while the rooms are open: how many cards other people have put in each lane, and who wrote by name. */
interface SoFar { others?: Partial<Record<WallCard["lane"], number>>; writers?: string[] }
/** Other people's cards while the rooms are open: a silhouette each, no words, no author. */
const silhouettes = (others: SoFar["others"] = {}): WallCard[] =>
  LANES.flatMap((lane) => Array.from({ length: others[lane] ?? 0 }, (_, i) => ({
    id: `other-${lane}-${i}`, lane, text: "", anonymous: true, mine: false, quarters: null, guessed: 0, sealed: false, other: true,
  })));

/** `submitted`: the organiser's count of cards sent to the wall while the rooms are open (the board itself is not served yet). */
interface Wall { cards: WallCard[]; live: boolean; people?: { n: number; total: number }; closes?: string; submitted?: number; writers?: string[] }
type BoardExtra = BoardView & { people?: number; people_total?: number; closes_at?: string };

const BEFORE_BOARD = ["draft", "lobby", "briefing", "private_rooms"];

async function loadWall(id: string, intentId?: string): Promise<Wall> {
  // the board is served once the rooms close: before that it is not asked for, so the console stays clean (no expected 409)
  const early = await getLobby(id).catch(() => null);
  try {
    if (early && BEFORE_BOARD.includes(early.state)) throw new ApiError("", 409);
    const b = (await getBoard(id)) as BoardExtra;
    const seen = new Set<string>();
    // the organiser's board carries no quarters; the intent's wall read serves the count per card (null for everyone else)
    const q = intentId ? ((await apiGet<{ quarters?: Record<string, number> | null }>(`/api/intents/${intentId}/wall`).catch(() => null))?.quarters ?? null) : null;
    const cards = [...b.clusters.flatMap((c) => c.notes), ...b.on_its_own]
      .filter((n) => !seen.has(n.id) && !!seen.add(n.id))
      .map((n) => ({ ...toCard(n, n.mine), ...(intentId ? { quarters: q && typeof q[n.id] === "number" ? q[n.id] : null } : {}) })); // inside an intent only the organiser's n / 4 shows
    const people = b.people !== undefined && b.people_total !== undefined ? { n: b.people, total: b.people_total } : undefined;
    return { cards, live: b.stage === "private_rooms", people, closes: b.closes_at };
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 409)) throw e;
    // the board is not open yet: the wall shows what the viewer has put on it themselves
    const room = await getRoom(id);
    const lobby = early;
    if (lobby?.organiser) {
      const counts = await getBoardCounts(id).catch(() => null);
      return { cards: room.notes.filter((n) => n.confirmed !== false).map((n) => toCard(n, true)), live: room.open, submitted: counts?.submitted };
    }
    // a seat holder: their own cards (North's drafts too, marked) and a silhouette for each card someone else has put up
    const so = (room as { wall?: SoFar }).wall ?? {};
    const own = room.notes.map((n) => toCard(n, true));
    const others = silhouettes(so.others);
    // North's untouched suggestions are shown but are not cards (file 25): the count is the person's own cards put up and everyone else's
    return { cards: [...own, ...suggestionCards((room as { suggestions?: SuggestionRow[] }).suggestions), ...others], live: room.open, writers: so.writers,
      submitted: own.filter((c) => !c.draft).length + others.length };
  }
}

function useWidth(): number {
  const [w, setW] = useState(window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

/** The session's label, purpose and topic for the purpose line; the wall still works without them. */
function useSessionLine(id: string): { label?: string; purpose?: string; topic?: string } {
  const [s, setS] = useState<{ label?: string; purpose?: string; topic?: string }>({});
  useEffect(() => {
    let live = true;
    getSession(id).then((v) => live && setS({ label: v.label, purpose: v.preparation?.purpose, topic: v.preparation?.topic ?? undefined }), () => undefined);
    return () => { live = false; };
  }, [id]);
  return s;
}

const initial = (name: string): string => name.trim().charAt(0).toUpperCase();

/** `intentId`: set when the wall runs inside an intent; then a suggestion can be hidden ("Not this one") and brought back (Undo). */
export default function WallScreen({ sessionId: given, intentId }: { sessionId?: string; intentId?: string } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const { state, data: loaded, retry } = useLoad<Wall>(() => loadWall(sessionId, intentId), `wall:${sessionId}`, (w) => w.cards.length === 0);
  // North's panel changed a card: the lanes reload quietly, with no loading state in between
  const [fresh, setFresh] = useState<Wall | null>(null);
  useEffect(() => setFresh(null), [loaded]);
  const data = fresh ?? loaded;
  const refresh = useCallback(() => { loadWall(sessionId, intentId).then(setFresh, () => undefined); }, [sessionId, intentId]);
  const [mine, setMine] = useState(false);
  const [projector, setProjector] = useState(false);
  const [lane, setLane] = useState<WallCard["lane"]>("intent");
  const [sheet, setSheet] = useState(false);
  const all = data?.cards ?? [];
  const phone = useWidth() < PHONE;
  const line = useSessionLine(sessionId);
  const what = line.purpose || line.label;
  // named contributors only: an anonymous author is never shown, not even as an initial
  const initials = [...new Set([...all.filter((c) => !c.anonymous && !c.sealed && c.author).map((c) => c.author!), ...(data?.writers ?? [])].map(initial))];
  const msg = state === "error" ? t.error : state === "refused" ? t.refused : undefined;
  const cards = mine ? all.filter((c) => c.mine) : all;
  const inLane = (l: WallCard["lane"]) => cards.filter((c) => c.lane === l);
  const when = closesWhen(data?.closes);

  const handlePickUp = async (suggestionId: string) => {
    await pickUpSuggestion(sessionId, suggestionId);
    retry(); // the picked-up card comes back as the person's own and the suggestion goes
  };

  const hide = (path: "hide" | "unhide") => async (suggestionId: string) => {
    await apiSend("POST", `/api/intents/${intentId}/suggestions/${suggestionId}/${path}`, {});
    if (path === "unhide") retry(); // Undo: the suggestion is back in the room's list
  };

  return (
    <div className={`ds-screen ds-wall${projector || phone ? " ds-wall--wide" : ""}${projector ? " ds-wall--projector" : ""}`}>
      <header className="ds-wall__head">
        <p className="ds-wall__crumb">{t.crumbLead}<strong>{t.crumbHere}</strong></p>
        <div className="ds-wall__stats">
          {data ? <span>{t.cards(data.submitted ?? all.filter((c) => !c.draft).length)}</span> : null}
          {data?.people || (initials.length && !projector && !intentId) ? ( // inside an intent the header above already shows the initials
            <span data-testid="participants">
              {projector || intentId ? null : <span className="ds-wall__initials">{initials.map((i) => <span key={i} aria-hidden="true" className="ds-avatar">{i}</span>)}</span>}
              {data?.people ? t.people(data.people.n, data.people.total) : null}
            </span>
          ) : null}
          {when ? <span>{t.closesLead} <span className="ds-wall__when">{when}</span></span> : null}
          {data?.live ? <span className="ds-wall__live">{t.live}</span> : null}
        </div>
      </header>

      <div className="ds-wall__body">
        <div className="ds-wall__main">
          <h1 className="ds-wall__title">{t.title}</h1>
          <p className="ds-wall__sentence">{t.sentence}</p>
          {what || line.topic ? (
            <p data-testid="purpose" className="ds-wall__purpose">
              {what ? <span><strong>{t.purposeLead}</strong> {what}</span> : null}
              {line.topic ? <span data-testid="topic"><Chip>{line.topic}</Chip></span> : null}
            </p>
          ) : null}
          {projector ? null : <StageBar sessionId={sessionId} closes={data?.closes ?? null} />}
          {projector ? null : <InvitePanel sessionId={sessionId} />}

          <WallState state={state === "empty" ? "populated" : state} label={t.loading} message={msg} onRetry={retry}>
            {/* the empty wall still shows the lanes, so a person sees where their first card will go */}
            {state === "empty" ? <EmptyState title={data?.submitted ? t.inRooms(data.submitted) : t.empty} lines={[]} /> : null}
            <div className="ds-wall__tools">
              {projector ? null : <Chip tone={mine ? "active" : "default"} onClick={() => setMine(!mine)}>{t.onlyMine}</Chip>}
              <Chip tone={projector ? "active" : "default"} onClick={() => { setProjector(!projector); setMine(false); }}>{projector ? t.exitProjector : t.projector}</Chip>
            </div>
            {phone ? (
              <div role="tablist" aria-label={t.laneSwitcher} className="ds-wall__tabs">
                {LANES.map((l) => (
                  <button key={l} type="button" role="tab" aria-selected={l === lane} className={`ds-chip${l === lane ? " ds-chip--active" : ""}`} onClick={() => setLane(l)}>
                    {t.lanes[l].name}<span aria-hidden="true">{inLane(l).length}</span>
                  </button>
                ))}
              </div>
            ) : null}
            <div data-testid="lanes" className="ds-wall__lanes">
              {(phone ? [lane] : LANES).map((l) => <Lane key={l} id={l} cards={inLane(l)} projector={projector} onPickUp={projector ? undefined : handlePickUp} onHide={projector || !intentId ? undefined : hide("hide")} onUndo={projector || !intentId ? undefined : hide("unhide")} />)}
            </div>
          </WallState>
        </div>

        {projector || !data?.live ? null : phone ? (
          <>
            <Button variant="primary" className="ds-wall__talk" aria-expanded={sheet} onClick={() => setSheet(!sheet)}>{sheet ? t.closeNorth : t.talkToNorth}</Button>
            {sheet ? <aside aria-label={t.panelTitle} className="ds-wall__north ds-wall__sheet"><NorthPanel sessionId={sessionId} onChange={refresh} /></aside> : null}
          </>
        ) : (
          <aside aria-label={t.panelTitle} className="ds-wall__north"><NorthPanel sessionId={sessionId} onChange={refresh} /></aside>
        )}
      </div>
    </div>
  );
}
