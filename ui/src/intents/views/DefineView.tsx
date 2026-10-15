import { useEffect, useState, type DragEvent, type FormEvent, type SyntheticEvent } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, EmptyState } from "../../design";
import { getCharter, makeCharterDraft, type ShelfId } from "../../modules/m1_intent/api";
import { problemText, usePolled } from "../../modules/m1_intent/board/usePolled";
import DefineScreen from "../../modules/m1_intent/define/DefineScreen";
import { m1Define } from "../../modules/m1_intent/define/copy";
import DefineTabs, { Part, tabFrom } from "../define/DefineTabs";

// Define strategically inside an intent (file 26). The board, vote, shelves and Lens panel are module 1's DefineScreen, wrapped;
// this view adds the intent head, the session mode, the dated park dialog, the governed refusal and the close (stage only, ruling 26).

export const dv = {
  initiative: "Initiative",
  stage: "Define strategically",
  organiser: (n: string) => `Organiser: ${n}`,
  clockNa: "Not available yet: no time box on this intent.",
  clock: (day: number, of: number, left: number) => `Day ${day} of ${of}. ${left} ${left === 1 ? "day" : "days"} left on the intent.`,
  start: "Start the ninety-minute session",
  close: "Close the session and write the charter draft",
  reopen: "Reopen Define",
  reopenReason: "Why is Define reopened?",
  reopenSave: "Reopen",
  projector: "Projector view",
  normal: "Normal view",
  hold: "Hold the room",
  carryOn: "Carry on",
  decisions: (n: number, of: number) => `Decisions: ${n} of ${of}`,
  over: (mmss: string) => `+ ${mmss} over`,
  timeUp: (n: number, c: number) => `Ninety minutes are up. ${n} of ${c} decided. Close with what we have, or add time.`,
  addTime: "Add 15 minutes",
  addReason: "Why is more time needed?",
  addNeed: "Please say why more time is needed.",
  ringKey: "Solid: all six fields confirmed. Dashed: something is missing.",
  openLens: "Open Lens's definition",
  parkTitle: (name: string) => `Park ${name} for later`,
  parkReason: "Why is it parked?",
  parkDate: "Review date",
  parkNeedReason: "Please say why this is parked for later.",
  parkNeedDate: "Choose a date after today.",
  parkIt: "Park it",
  cancel: "Cancel",
  closeTitle: "Close the session and write the charter draft?",
  openItems: {
    unplaced: (n: number) => `${n} ${n === 1 ? "group has" : "groups have"} no shelf`,
    unticked: (n: number) => `${n} ${n === 1 ? "group" : "groups"} on Must or Should not ticked`,
    stillOpen: (names: string[]) => `${names.length} ${names.length === 1 ? "group is" : "groups are"} still open: ${names.join(", ")}. It stays out of the charter.`,
    ungoverned: (n: number) => `${n} ${n === 1 ? "group has" : "groups have"} measure fields not confirmed`,
    late: (n: number) => `${n} parked ${n === 1 ? "group is" : "groups are"} past the review date`,
  },
  nothingOpen: "Nothing is open. Every cluster has a shelf and every field is confirmed.",
  confirm: "Close and write the charter draft",
  writing: "Writing the charter draft",
  keepGoing: "Keep going",
  result: (n: number, g: number) => `Charter draft written from ${n} ticked ${n === 1 ? "group" : "groups"}. ${g} ${g === 1 ? "gap" : "gaps"} found.`,
  resultNa: "Not available yet: the build-ready check has not run.",
  openCharter: "Open the charter",
  noWall: "No clusters yet. This intent has no wall to define from.",
  failed: "That did not work. Please try again.",
  notFound: "We could not find that intent.",
  closedLine: "Define is closed. The shelves, votes and moves are kept.",
};

/** `open_groups`: the groups not ticked into the charter, named as the server's charter draft names them. */
interface OpenItems { made: number; of: number; shelf_counts: Record<string, number>; unticked: number; parked_late: number; ungoverned: number | null; open_groups?: string[] }
interface Session { started_at: string | null; ended_at: string | null; planned_minutes: number; extensions: { minutes: number }[] }
export interface DefineData {
  intent: { id: string; type: string; title: string; purpose: string; state: string; organiser_name: string };
  stage: { state: string | null; opened_at: string | null; closed_at: string | null };
  tier: "content" | "exists";
  wall_session_id?: string | null;
  organiser?: boolean;
  start_blocked?: string | null;
  session?: Session | null;
  decisions?: { made: number; of: number };
  open_items?: OpenItems;
  signed?: boolean;
  has_baseline?: boolean;
  held?: boolean;
  today?: string;
  shelf_counts?: Record<string, number> | null;
}
interface ClockView { stage: { day_of: number; working_days_total: number } | null; box: { working_days_left: number } | null }

/** Seconds left on the ninety-minute clock (negative once over). Holds are not taken off (file 26 open point, see report). */
export function secondsLeft(s: Session, now: number): number {
  if (!s.started_at) return s.planned_minutes * 60;
  const minutes = s.planned_minutes + s.extensions.reduce((n, e) => n + e.minutes, 0);
  return Math.round((Date.parse(s.started_at) + minutes * 60000 - (s.ended_at ? Date.parse(s.ended_at) : now)) / 1000);
}
export function mmss(sec: number): string {
  const a = Math.abs(sec);
  return `${String(Math.floor(a / 60)).padStart(2, "0")}:${String(a % 60).padStart(2, "0")}`;
}
export const clockTone = (sec: number) => (sec <= 5 * 60 ? "red" : sec <= 15 * 60 ? "amber" : "plain");

/** Today plus one quarter, the proposed default review date (file 26 open question 12). */
export function quarterOn(today: string): string {
  const [y, m, d] = today.split("-").map(Number) as [number, number, number];
  const last = new Date(Date.UTC(y, m + 3, 0)).getUTCDate(); // m is 1-based: day 0 of month index m+3 is the last day of month m+3
  return new Date(Date.UTC(y, m + 2, Math.min(d, last))).toISOString().slice(0, 10);
}
export const dateOk = (v: string, today: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) && v > today;

function useWide(): boolean {
  const q = "(min-width: 768px)";
  const [wide, setWide] = useState(() => typeof window.matchMedia !== "function" || window.matchMedia(q).matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const m = window.matchMedia(q);
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}

function useNow(on: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [on]);
  return now;
}

const SHELF_OF_LABEL: Record<string, ShelfId> = Object.fromEntries(m1Define.shelves.map((s) => [s.label, s.id]));
const nameOfCluster = (id: string) => document.querySelector(`[data-cluster="${CSS.escape(id)}"] .df-cluster__name`)?.textContent ?? "";

export default function DefineView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const tab = tabFrom(useLocation().search);
  const path = `/api/intents/${encodeURIComponent(intentId)}/define/session`;
  const room = usePolled(() => apiGet<DefineData>(path), `dv:${intentId}`, 5000);
  const v = room.data;
  const [clockLine, setClockLine] = useState<string>(dv.clockNa);
  const [cluster, setCluster] = useState<string | null>(null);
  const [board, setBoard] = useState(0); // a new key reloads the wrapped board at once after a move
  const [refusal, setRefusal] = useState<{ message: string; cid: string } | null>(null);
  const [parking, setParking] = useState<{ cid: string; name: string } | null>(null);
  const [closing, setClosing] = useState(false);
  const [projector, setProjector] = useState(false);
    const [error, setError] = useState("");
  const wide = useWide();
  const running = !!v?.session?.started_at && !v.session.ended_at;
  const now = useNow(running);

  useEffect(() => {
    apiGet<ClockView>(`/api/intents/${encodeURIComponent(intentId)}/clock`).then(
      (c) => setClockLine(c.stage && c.box ? dv.clock(c.stage.day_of, c.stage.working_days_total, c.box.working_days_left) : dv.clockNa),
      () => setClockLine(dv.clockNa));
  }, [intentId]);

  if (room.state === "loading" && !v) return <ScreenState state="loading" />;
  if (!v) {
    if (room.failure instanceof ApiError && room.failure.status === 404) return <ScreenState state="empty" message={dv.notFound} />;
    return <ScreenState state={room.state === "refused" ? "refused" : "error"} onRetry={room.reload} />;
  }

  const sid = v.wall_session_id ?? null;
  const org = v.organiser === true;
  const closed = !!v.stage.closed_at;
  const say = (e: unknown) => setError(problemText(e) || dv.failed);
  const act = async (body: Record<string, unknown>, to = "session") => {
    setError("");
    try { room.put(await apiSend<DefineData>("POST", path.replace(/session$/, to), body)); return true; } catch (e) { say(e); return false; }
  };

  async function shelve(cid: string, shelf: ShelfId, extra: Record<string, string> = {}) {
    setError(""); setRefusal(null);
    try {
      await apiSend("POST", `/api/intents/${encodeURIComponent(intentId)}/define/shelf`, { cluster_id: cid, shelf, ...extra });
      setParking(null); setBoard((n) => n + 1); room.reload();
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && (shelf === "must" || shelf === "should")) setRefusal({ message: e.message, cid });
      else say(e);
      return false;
    }
  }
  function ask(cid: string, shelf: ShelfId | undefined) {
    if (!shelf || !org || closed) return;
    if (shelf === "future") setParking({ cid, name: nameOfCluster(cid) });
    else void shelve(cid, shelf);
  }
  // Every move into a shelf comes through here (the board's own menu and drop are caught before they act)
  const onChange = (e: SyntheticEvent) => {
    const t = e.target;
    const card = t instanceof HTMLSelectElement ? t.closest<HTMLElement>("[data-cluster]") : null;
    if (!card) return;
    e.stopPropagation();
    ask(card.dataset.cluster ?? "", (t as HTMLSelectElement).value as ShelfId);
  };
  const onDrop = (e: DragEvent) => {
    const label = (e.target as Element).closest?.("section.df-shelf")?.getAttribute("aria-label") ?? "";
    if (!SHELF_OF_LABEL[label]) return;
    e.stopPropagation(); e.preventDefault();
    ask(e.dataTransfer.getData("text/plain"), SHELF_OF_LABEL[label]);
  };
  const onClick = (e: SyntheticEvent) => {
    const card = (e.target as Element).closest?.(".df-cluster__name") ? (e.target as Element).closest<HTMLElement>("[data-cluster]") : null;
    if (card) setCluster(card.dataset.cluster ?? null);
  };
  const openLens = (cid: string) => document.querySelector<HTMLButtonElement>(`[data-cluster="${CSS.escape(cid)}"] .df-cluster__name`)?.click();

  const left = v.session ? secondsLeft(v.session, now) : 90 * 60;
  const decided = v.decisions ?? { made: 0, of: 0 };
  const tone = clockTone(left);
  const toneColour = tone === "red" ? "var(--ds-red, #b42318)" : tone === "amber" ? "var(--ds-amber, #b54708)" : undefined;
  const showProjector = projector && wide && running;

  const clusters = sid ? (
    <div data-define-view onChangeCapture={onChange} onDropCapture={onDrop} onClickCapture={onClick} style={showProjector ? { zoom: 1.25 } : undefined}>
      {/* the board's own lock button is replaced by "Close the session" above, which also closes the stage */}
      <style>{"[data-define-view] .ds-frame__actions button.ds-btn--primary{display:none}"}</style>
      <DefineScreen key={board} sessionId={sid} defineOpen={!closed} />
      <p className="ds-muted">{dv.ringKey}</p>
    </div>
  ) : <EmptyState title={dv.noWall} lines={[]} />;

  return (
    <div className="ds-screen" style={{ padding: "0 16px" }}>
      {!showProjector ? (
        <section className="ds-card" aria-label={v.intent.title} style={{ padding: 16, marginTop: 12 }}>
          <h1 style={{ margin: 0 }}><Link className="ds-link" to={`/centre/intent/${encodeURIComponent(intentId)}`}>{v.intent.title}</Link></h1>
          {v.intent.purpose ? <p className="ds-muted" style={{ margin: "4px 0" }}>{v.intent.purpose}</p> : null}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <Chip>{dv.initiative}</Chip><Chip>{dv.stage}</Chip>
            {v.intent.organiser_name ? <span className="ds-muted">{dv.organiser(v.intent.organiser_name)}</span> : null}
          </div>
          <p role="status" style={{ margin: "8px 0 0" }}>{clockLine}</p>
        </section>
      ) : null}

      {v.tier === "content" ? (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", margin: "12px 0" }} aria-label="Session">
            {org && !closed && !running ? (
              <span>
                <Button variant="primary" disabled={!!v.start_blocked || v.intent.state !== "open"} onClick={() => void act({ action: "start" })}>{dv.start}</Button>
                {v.start_blocked ? <span className="ds-muted"> {v.start_blocked}</span> : null}
              </span>
            ) : null}
            {org && !closed && sid ? <Button variant={running ? "primary" : "secondary"} onClick={() => setClosing(true)}>{dv.close}</Button> : null}
            {org && closed && !v.signed ? <ReopenForm onSave={(reason) => act({ action: "reopen", reason })} /> : null}
            <strong data-testid="session-clock" style={{ color: toneColour, fontVariantNumeric: "tabular-nums" }}>{left < 0 ? dv.over(mmss(left)) : mmss(left)}</strong>
            {wide ? <span data-testid="decisions">{dv.decisions(decided.made, decided.of)}</span> : null}
            {org && wide && running ? <Button onClick={() => setProjector((p) => !p)}>{projector ? dv.normal : dv.projector}</Button> : null}
            {org && running && sid ? (
              <Button onClick={() => void act({ held: !v.held }, "hold")}>{v.held ? dv.carryOn : dv.hold}</Button>
            ) : null}
          </div>
          {running && left <= 0 ? <TimeUp made={decided.made} of={decided.of} organiser={org} onClose={() => setClosing(true)} onAdd={(reason) => act({ action: "extend", reason })} /> : null}
          {closed ? <p role="status" className="ds-muted">{dv.closedLine}</p> : null}
          {error ? <p role="alert" className="df-alert">{error}</p> : null}
          {refusal ? (
            <p role="alert" aria-live="assertive" className="df-alert">
              {refusal.message} <button type="button" className="ds-link" onClick={() => openLens(refusal.cid)}>{dv.openLens}</button>
            </p>
          ) : null}
          {parking && v.today ? (
            <ParkDialog name={parking.name} today={v.today} onCancel={() => setParking(null)}
              onPark={(reason, date) => shelve(parking.cid, "future", { reason, review_date: date })} />
          ) : null}
          {closing && sid && v.open_items ? (
            <CloseDialog items={v.open_items} intentId={intentId} sessionId={sid} onCancel={() => setClosing(false)}
              onClosed={(d) => room.put(d)} />
          ) : null}
          {!showProjector && sid ? <Part file="LensStrip" spec="44" intentId={intentId} sessionId={sid} clusterId={cluster} /> : null}
          <DefineTabs tab={tab} props={{ intentId, sessionId: sid, clusterId: cluster }} hasBaseline={v.has_baseline !== false} clusters={clusters} />
        </>
      ) : (
        <p className="ds-muted">{closed && v.shelf_counts ? m1Define.shelves.map((s) => `${s.label}: ${v.shelf_counts?.[s.id] ?? 0}`).join(", ") : dv.stage}</p>
      )}
    </div>
  );
}

function ReopenForm({ onSave }: { onSave: (reason: string) => Promise<boolean> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  if (!open) return <Button onClick={() => setOpen(true)}>{dv.reopen}</Button>;
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (reason.trim()) void onSave(reason.trim()).then((ok) => ok && setOpen(false)); }}>
      <label>{dv.reopenReason} <input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></label>{" "}
      <Button type="submit" disabled={!reason.trim()}>{dv.reopenSave}</Button> <Button onClick={() => setOpen(false)}>{dv.cancel}</Button>
    </form>
  );
}

function TimeUp({ made, of, organiser, onClose, onAdd }: { made: number; of: number; organiser: boolean; onClose: () => void; onAdd: (reason: string) => Promise<boolean> }) {
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  return (
    <div role="alert" className="ds-card" style={{ padding: 12, margin: "8px 0" }}>
      <p style={{ margin: 0 }}><strong>North</strong> {dv.timeUp(made, of)}</p>
      {organiser ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          <Button variant="primary" onClick={onClose}>{dv.close}</Button>
          {asking ? (
            <>
              <label>{dv.addReason} <input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></label>
              <Button disabled={!reason.trim()} onClick={() => void onAdd(reason.trim()).then((ok) => ok && (setAsking(false), setReason("")))}>{dv.addTime}</Button>
              {!reason.trim() ? <span className="ds-muted">{dv.addNeed}</span> : null}
            </>
          ) : <Button onClick={() => setAsking(true)}>{dv.addTime}</Button>}
        </div>
      ) : null}
    </div>
  );
}

export function ParkDialog({ name, today, onPark, onCancel }: { name: string; today: string; onPark: (reason: string, date: string) => Promise<boolean>; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(() => quarterOn(today));
  const [tried, setTried] = useState(false);
  const ok = reason.trim() !== "" && dateOk(date, today);
  const submit = (e: FormEvent) => { e.preventDefault(); setTried(true); if (ok) void onPark(reason.trim(), date); };
  const min = new Date(Date.parse(today) + 86400000).toISOString().slice(0, 10);
  return (
    <form className="ds-card df-park" role="dialog" aria-label={dv.parkTitle(name)} onSubmit={submit} style={{ padding: 16, margin: "8px 0" }}>
      <strong>{dv.parkTitle(name)}</strong>
      <label style={{ display: "block" }}>{dv.parkReason} <input type="text" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} onBlur={() => setTried(true)} /></label>
      {tried && !reason.trim() ? <p role="alert" className="df-alert">{dv.parkNeedReason}</p> : null}
      <label style={{ display: "block" }}>{dv.parkDate} <input type="date" value={date} min={min} onChange={(e) => setDate(e.target.value)} /></label>
      {!dateOk(date, today) ? <p role="alert" className="df-alert">{dv.parkNeedDate}</p> : null}
      <div className="df-row" style={{ display: "flex", gap: 8 }}>
        <Button type="submit" variant="primary" disabled={!ok}>{dv.parkIt}</Button>
        <Button onClick={onCancel}>{dv.cancel}</Button>
      </div>
    </form>
  );
}

function CloseDialog({ items, intentId, sessionId, onCancel, onClosed }: {
  items: OpenItems; intentId: string; sessionId: string; onCancel: () => void; onClosed: (d: DefineData) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const lines = [
    items.shelf_counts.not_placed ? dv.openItems.unplaced(items.shelf_counts.not_placed) : "",
    items.open_groups?.length ? dv.openItems.stillOpen(items.open_groups) : items.unticked ? dv.openItems.unticked(items.unticked) : "",
    items.ungoverned ? dv.openItems.ungoverned(items.ungoverned) : "",
    items.parked_late ? dv.openItems.late(items.parked_late) : "",
  ].filter(Boolean);
  const id = encodeURIComponent(intentId);

  async function confirm() {
    setBusy(true); setError("");
    try {
      const page = await getCharter(sessionId).catch(() => null);
      const drafted = page?.charter ? page : await makeCharterDraft(sessionId, true); // the existing draft from the ticked clusters
      onClosed(await apiSend<DefineData>("POST", `/api/intents/${id}/define/session`, { action: "close" }));
      const ticked = drafted.charter?.problems.length ?? 0;
      const check = await apiSend<{ todo?: unknown[] }>("POST", `/api/intents/${id}/build-ready/check`).catch(() => null);
      setResult(Array.isArray(check?.todo) ? dv.result(ticked, check.todo.length) : dv.resultNa);
    } catch (e) {
      setError(problemText(e) || dv.failed);
    }
    setBusy(false);
  }

  return (
    <div className="ds-card df-park" role="dialog" aria-label={dv.closeTitle} style={{ padding: 16, margin: "8px 0" }}>
      <strong>{dv.closeTitle}</strong>
      {result === null ? (
        <>
          {lines.length ? <ul>{lines.map((l) => <li key={l}>{l}</li>)}</ul> : <p>{dv.nothingOpen}</p>}
          {error ? <p role="alert" className="df-alert">{error}</p> : null}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button variant="primary" disabled={busy} onClick={() => void confirm()}>{busy ? dv.writing : dv.confirm}</Button>
            <Button onClick={onCancel}>{dv.keepGoing}</Button>
          </div>
        </>
      ) : (
        <p role="status"><strong>North</strong> {result} <Link className="ds-link" to={`/centre/intent/${id}/charter`}>{dv.openCharter}</Link></p>
      )}
    </div>
  );
}
