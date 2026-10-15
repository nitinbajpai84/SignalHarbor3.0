import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Button, Chip, EmptyState, PageFrame, Pill, StatCard, StatGrid } from "../../../design";
import { getGlossary } from "../../m2_baseline/glossary/glossaryApi";
import { getGoverned, getWorkList, type GovernedCell, type GovernedMeasure, type GovernedView } from "../../m2_baseline/api";
import { getCharter, getTogether, makeCharterDraft, shelveCluster, type ShelfId, type TogetherCluster, type TogetherView } from "../api";
import { problemText, usePolled } from "../board/usePolled";
import StageTimer from "../timer/StageTimer";
import { m1Define as d } from "./copy";
import LensPanel, { cellText } from "./LensPanel";
import "./define.css";

/** The default review date the server sets for a parked cluster: today plus three months (shown so the organiser sees it; the server's date is the one kept). */
function reviewDate(from = new Date()): string {
  const last = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth() + 4, 0)).getUTCDate();
  const t = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth() + 3, Math.min(from.getUTCDate(), last)));
  return t.toISOString().slice(0, 10);
}

/** A cluster whose every card is sealed for this viewer: the server masks each note (`sealed: true`) and names the cluster "A sealed cluster". */
export const isSealed = (c: TogetherCluster) => c.notes.length > 0 && c.notes.every((n) => (n as { sealed?: boolean }).sealed === true);

/** The together view carries the baseline on each cluster; the view-level field is not served yet. */
const baselineOf = (v: TogetherView) => v.baseline_id ?? (v.clusters.find((c) => (c as { baseline_id?: string }).baseline_id) as { baseline_id?: string } | undefined)?.baseline_id;


export default function DefineScreen({ sessionId: given, defineOpen = false }: { sessionId?: string; defineOpen?: boolean } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const room = usePolled(() => getTogether(sessionId), `define:${sessionId}`);
  const notYet = room.failure instanceof ApiError && room.failure.status === 409;
  const closed = !defineOpen && room.data?.stage === "closed"; // a closed session is kept as locked: nothing moves, nothing is locked again
  const baseline = room.data ? baselineOf(room.data) : undefined;
  const links = useMeasureLinks(baseline);
  const lockedAt = useLockedAt(sessionId, closed);
  // the signed baseline's measures name the clusters they came from (kpi problem_ids): that link wins over the pack's suggestion
  const v = room.data && links
    ? { ...room.data, clusters: room.data.clusters.map((c) => (links[c.id]?.length ? { ...c, measure_codes: links[c.id] } : c)) }
    : room.data;
  const cards = v ? v.clusters.reduce((n, c) => n + c.note_count, 0) : 0;
  const withMeasures = v?.clusters.filter((c) => c.measure_codes !== undefined) ?? [];
  const measures = withMeasures.length > 0 ? new Set(withMeasures.flatMap((c) => c.measure_codes ?? [])).size : null;
  const state = room.state === "populated" && v && v.clusters.length === 0 ? "empty" : room.state;
  const [locking, setLocking] = useState(false);
  const [lockError, setLockError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const sel = v?.clusters.find((c) => c.id === selected) ?? null;
  const navigate = useNavigate();
  const org = v?.organiser === true && !closed;

  async function lock() {
    setLockError(null);
    try {
      await makeCharterDraft(sessionId, true);
      navigate(`/centre/intent/charter/${encodeURIComponent(sessionId)}`);
    } catch (e) {
      setLockError(e instanceof ApiError && e.message ? e.message : d.lockFailed);
    }
  }

  let body: ReactNode;
  if (notYet) body = <EmptyState title={d.notReady} lines={[]} />;
  else if (state === "loading") body = <div role="status"><EmptyState title={d.loadingTitle} lines={[d.loadingLine]} /></div>;
  else if (state === "refused") body = <EmptyState title={d.refusedTitle} lines={[problemText(room.failure)]} />;
  else if (state === "error") body = (
    <div className="ds-card df-park" role="alert">
      <strong>{d.errorTitle}</strong>
      <p className="ds-muted">{problemText(room.failure)}</p>
      <div className="df-row"><Button onClick={room.reload}>{d.retry}</Button></div>
    </div>
  );
  else if (state === "empty") body = <EmptyState title={d.empty} lines={[]} />;
  else body = v ? <Shelves sessionId={sessionId} view={v} put={room.put} selected={selected} onSelect={setSelected} lockedAt={lockedAt} defineOpen={defineOpen} /> : null;

  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={
          <span className="df-meta">
            <span>{d.crumbs[0]} / <b>{d.crumbs[1]}</b></span>
            {v ? (
              <span className="df-meta__counts">
                <span>{d.counts(cards, v.clusters.length, measures)}</span>
                <span>{d.people(v.people_count)}</span>
              </span>
            ) : null}
          </span>
        }
        title={d.title}
        subline={d.sub}
        aside={v && state === "populated" ? <LensPanel baselineId={baselineOf(v)} cluster={sel} organiser={v.organiser} sealed={sel ? isSealed(sel) : false} /> : undefined}
        actions={
          <>
            <Link className="ds-btn" to={`/centre/intent/wall/${encodeURIComponent(sessionId)}`}>{d.backToWall}</Link>
            {org ? <Button variant="primary" onClick={() => setLocking(true)}>{d.lock}</Button> : null}
            {closed ? <Link className="ds-btn ds-btn--primary" to={`/centre/intent/charter/${encodeURIComponent(sessionId)}`}>{d.openCharter}</Link> : null}
          </>
        }
      >
        {v && !closed ? <StageTimer sessionId={sessionId} /> : null}
        {locking && v ? (
          <div className="ds-card df-park" role="dialog" aria-label={d.lockTitle}>
            <strong>{d.lockTitle}</strong>
            <p className="ds-soft">{d.lockHelp(v.open_count)}</p>
            {lockError ? <p role="alert" className="df-alert">{lockError}</p> : null}
            <div className="df-row">
              <Button variant="primary" onClick={() => void lock()}>{d.lockYes}</Button>
              <Button onClick={() => { setLocking(false); setLockError(null); }}>{d.futureCancel}</Button>
            </div>
          </div>
        ) : null}
        {body}
      </PageFrame>
    </div>
  );
}

function Shelves({ sessionId, view, put, selected, onSelect, lockedAt, defineOpen = false }: {
  sessionId: string; view: TogetherView; put: (v: TogetherView) => void; selected: string | null; onSelect: (id: string) => void; lockedAt: string | null; defineOpen?: boolean;
}) {
  const [parking, setParking] = useState<TogetherCluster | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const closed = !defineOpen && view.stage === "closed";
  const org = view.organiser && !closed;
  const [topic, setTopic] = useState<string | null>(null);
  const topics = [...new Set(view.clusters.map((c) => c.topic).filter((t): t is string => !!t))];
  const grouped = topics.length > 1; // one wall or no topics: nothing changes on screen
  const clusters = grouped && topic ? view.clusters.filter((c) => c.topic === topic) : view.clusters;
  const [gov, setGov] = useState<GovernedView | null>(null);
  const [terms, setTerms] = useState<number | null>(null);
  const baseline = baselineOf(view);
  useEffect(() => {
    setGov(null);
    setTerms(null);
    if (!baseline) return;
    let live = true;
    getGoverned(baseline).then((g) => live && setGov(g)).catch(() => undefined);
    getGlossary(baseline).then((g) => live && g.built && setTerms(g.counts.all)).catch(() => undefined);
    return () => { live = false; };
  }, [baseline]);
  const known = new Set<string>(d.shelves.map((s) => s.id));
  const unplaced = clusters.filter((c) => !c.shelf || !known.has(c.shelf));

  async function move(c: TogetherCluster, shelf: ShelfId, why?: string) {
    setError(null);
    try {
      put(await shelveCluster(sessionId, c.id, shelf, why));
      setParking(null);
      setReason("");
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : d.moveFailed);
    }
  }
  function ask(c: TogetherCluster, shelf: ShelfId) {
    if (shelf === c.shelf) return;
    if (shelf === "future") {
      setParking(c);
      setError(null);
    } else void move(c, shelf);
  }
  function save() {
    if (!parking) return;
    if (reason.trim() === "") setError(d.futureNeed);
    else void move(parking, "future", reason.trim());
  }

  const card = (c: TogetherCluster) => (
    <ClusterCard
      key={c.id} c={c} org={org} grouped={grouped} selected={selected === c.id} known={known}
      measures={(gov?.measures ?? []).filter((g) => (c.measure_codes ?? []).includes(g.id))}
      onSelect={() => onSelect(c.id)} onMove={(s) => ask(c, s)}
    />
  );
  const tiles: [string, string | number][] = [
    [d.tiles.decisions, view.open_count],
    [d.tiles.owners, gov ? d.percent(gov.percentages.owned) : d.notYet],
    [d.tiles.unchanged, d.notYet],
    [d.tiles.glossary, terms ?? d.notYet],
    [d.tiles.sealed, gov ? d.percent(gov.percentages.sealed) : d.notYet],
  ];
  return (
    <>
      {!org ? <p role="status" className="ds-muted" style={{ margin: 0 }}>{closed ? d.closedLine(lockedAt) : d.readOnly}</p> : null}
      {error ? <p role="alert" className="df-alert">{error}</p> : null}
      {parking ? (
        <form className="ds-card df-park" role="dialog" aria-label={d.futureTitle(parking.name)} onSubmit={(e) => { e.preventDefault(); save(); }}>
          <strong>{d.futureTitle(parking.name)}</strong>
          <label>
            {d.futureReason}
            <input type="text" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
          </label>
          <span className="ds-muted">{d.futureReview(reviewDate())}</span>
          <div className="df-row">
            <Button type="submit" variant="primary">{d.futureSave}</Button>
            <Button onClick={() => { setParking(null); setError(null); }}>{d.futureCancel}</Button>
          </div>
        </form>
      ) : null}
      {grouped ? (
        <div role="group" aria-label={d.topicFilter} className="df-topics">
          {[null, ...topics].map((t) => (
            <Chip key={t ?? "all"} tone={topic === t ? "active" : "default"} onClick={() => setTopic(t)}>{t ?? d.allTopics}</Chip>
          ))}
        </div>
      ) : null}
      {unplaced.length > 0 ? (
        <section aria-label={d.unplaced} className="df-shelf" style={{ minHeight: 0 }}>
          <div className="df-shelf__head"><h2>{d.unplaced}</h2><span>{unplaced.length}</span></div>
          <div className="df-unplaced">{unplaced.map(card)}</div>
        </section>
      ) : null}
      <div className="df-shelves">
        {d.shelves.map((s) => {
          const here = clusters.filter((c) => c.shelf === s.id);
          return (
            <section
              key={s.id}
              aria-label={s.label}
              className={`df-shelf${s.id === "must" ? " df-shelf--must" : ""}`}
              onDragOver={(e) => org && e.preventDefault()}
              onDrop={(e) => {
                const c = view.clusters.find((x) => x.id === e.dataTransfer.getData("text/plain"));
                if (org && c) ask(c, s.id);
              }}
            >
              <div className="df-shelf__head"><h2>{s.label}</h2><span>{here.length}</span></div>
              {here.map(card)}
              {here.length === 0 || org ? <p className="df-shelf__drop">{org ? d.dropHere : d.shelfEmpty}</p> : null}
              {s.id === "future" ? <p className="df-shelf__foot">{d.footer}</p> : null}
            </section>
          );
        })}
      </div>
      <StatGrid cols={5}>
        {tiles.map(([name, value]) => (
          <StatCard key={name} label={name} value={value} text={value === d.notYet} valueTone={name === d.tiles.decisions && Number(value) > 0 ? "warn" : undefined} />
        ))}
      </StatGrid>
    </>
  );
}

/** cluster id -> measure codes, from the signed baseline's work list; null until read or when it cannot be read. */
function useMeasureLinks(baseline: string | undefined): Record<string, string[]> | null {
  const [links, setLinks] = useState<Record<string, string[]> | null>(null);
  useEffect(() => {
    setLinks(null);
    if (!baseline) return;
    let live = true;
    getWorkList(baseline).then((w) => live && setLinks(Object.fromEntries(w.problems.map((p) => [p.id, p.kpi_ids])))).catch(() => undefined);
    return () => { live = false; };
  }, [baseline]);
  return links;
}

/** When the shelves were locked: the charter's first version is drafted at that moment. */
function useLockedAt(sessionId: string, closed: boolean): string | null {
  const [at, setAt] = useState<string | null>(null);
  useEffect(() => {
    if (!closed) return;
    let live = true;
    getCharter(sessionId).then((p) => live && setAt(p.charter?.versions[0]?.created_at ?? null)).catch(() => undefined);
    return () => { live = false; };
  }, [sessionId, closed]);
  return at;
}

function ClusterCard({ c, org, grouped, selected, known, measures, onSelect, onMove }: {
  c: TogetherCluster; org: boolean; grouped: boolean; selected: boolean; known: Set<string>; measures: GovernedMeasure[];
  onSelect: () => void; onMove: (s: ShelfId) => void;
}) {
  const sealed = isSealed(c);
  // the ring reads the baseline's governed state; the together view's own flag is the fallback
  const fromBaseline = measures.length > 0;
  const isGoverned = fromBaseline ? measures.every((g) => g.missing.length === 0) : c.governed;
  const missing = fromBaseline ? [...new Set(measures.flatMap((g) => g.missing))] : c.missing ?? [];
  const ringText = isGoverned === undefined ? d.ringMissing : isGoverned ? d.governed : missing.length > 0 ? d.needs(missing.map((f) => d.fieldWords[f] ?? f)) : d.notGoverned;
  const owners = measures.map((g) => g.state.owners).filter((o): o is GovernedCell => !!o && cellText(o) !== d.notYet);
  // as on the canvas: only owners still to confirm are named on the card (each name once); the ring says the rest
  const pending = [...new Set(owners.filter((o) => o.mark !== "stated").flatMap((o) => cellText(o).split(" · ")))];
  return (
    <div
      data-cluster={c.id}
      data-sealed={sealed || undefined}
      draggable={org}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", c.id)}
      className={`df-cluster${selected ? " df-cluster--selected" : ""}${sealed ? " df-cluster--sealed" : ""}`}
    >
      <div className="df-cluster__top">
        <span className="df-cluster__meta">
          <span className={`df-dot ${sealed ? "df-dot--sealed" : `df-dot--${(c.colour ?? 0) % 8}`}`} aria-hidden="true" />
          {sealed ? d.sealedMeta(c.vote_total) : d.cardMeta(c.note_count, c.vote_total)}
        </span>
        <span data-ring={isGoverned === true ? "solid" : "dashed"} className="df-ring" title={ringText}>
          <span className="df-ring__mark" aria-hidden="true" />
          <span>{ringText}</span>
        </span>
      </div>
      <button type="button" className="df-cluster__name" aria-label={d.select(c.name)} aria-pressed={selected} onClick={onSelect}>{c.name}</button>
      {grouped && c.topic ? <span className="df-topic" data-testid="topic"><Chip>{c.topic}</Chip></span> : null}
      {c.measure_codes === undefined ? <p className="df-cluster__note">{d.measures(undefined)}</p> : c.measure_codes.length > 0 ? (
        <div className="df-codes" aria-label={d.measures(c.measure_codes)}>{c.measure_codes.map((k) => <span key={k} className="df-code">{k}</span>)}</div>
      ) : <p className="df-cluster__note">{d.measures([])}</p>}
      {sealed ? <p className="df-cluster__note">{d.sealedLine}</p> : null}
      {pending.length > 0 ? <Pill tone="open">{d.ownerNotConfirmed(pending.join(", "))}</Pill> : null}
      {c.shelf === "future" ? (
        <>
          {c.shelf_reason ? <p className="df-cluster__note">{d.parkedReason(c.shelf_reason)}</p> : null}
          {c.review_date ? <p className="df-cluster__note">{d.reviewOn(c.review_date)}</p> : null}
        </>
      ) : null}
      {org ? (
        <select aria-label={d.moveTo(c.name)} value={c.shelf && known.has(c.shelf) ? c.shelf : ""} onChange={(e) => onMove(e.target.value as ShelfId)}>
          <option value="" disabled>{d.moveTo(c.name)}</option>
          {d.shelves.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
      ) : null}
    </div>
  );
}
