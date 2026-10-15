import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import ScreenState from "../../../components/ScreenState";
import { Button, EmptyState, PageFrame, Pill, type PillTone } from "../../../design";
import { useLoad } from "../../m1_intent/useLoad";
import { getSourceMap, type MapSource } from "../api";
import { getBenchmarks, getIntake, makeRequests, remind, uploadSource, type Benchmarks, type Email, type Intake, type IntakeRequest, type Outgoing } from "../intake/api";
import BenchmarkPanel from "../intake/BenchmarkPanel";
import FilePicker from "../intake/FilePicker";
import ProfileView from "../intake/ProfileView";
import { getPlan } from "../plan/planApi";
import { getSourceProfile, type QualityRule } from "./api";
import { requestText as t } from "./copy";

const INTENT = "/centre/intent";
const ZONES = ["p1", "p2", "identify", "unknown"];
const TONE: Record<keyof typeof t.state, PillTone> = { none: "draft", sent: "open", arrived: "ok", profiled: "signed" };

interface Loaded {
  intake: Intake;
  sources: MapSource[] | null;
  bench: Benchmarks | null;
  /** The plan is signed: the assessment takes no new request, reminder or file (the routes answer 409). */
  locked: boolean;
}
interface Row {
  id: string;
  name: string;
  restricted: boolean;
  req: IntakeRequest | null;
}
interface Shown {
  title: string;
  linkPath: string | null;
  email: Email;
}

/** Cards in plan order: the source map's zones (first ready, then next, then the rest); a source the viewer may not see is a placeholder. */
function rowsOf(d: Loaded): Row[] {
  const req = new Map(d.intake.requests.map((r) => [r.source_id, r]));
  const base: Row[] = d.sources
    ? [...d.sources].sort((a, b) => ZONES.indexOf(a.zone) - ZONES.indexOf(b.zone)).map((s) => ({ id: s.id, name: s.name, restricted: s.restricted, req: req.get(s.id) ?? null }))
    : d.intake.not_yet_asked.map((s) => ({ id: s.source_id, name: s.source_name, restricted: false, req: null }));
  const seen = new Set(base.map((r) => r.id));
  const extra = d.intake.requests.filter((r) => !seen.has(r.source_id)).map((r) => ({ id: r.source_id, name: r.source_name, restricted: false, req: r }));
  return d.sources ? [...base, ...extra] : [...extra, ...base];
}
const stateOf = (r: IntakeRequest | null): keyof typeof t.state => (!r ? "none" : r.state !== "arrived" ? "sent" : r.profile ? "profiled" : "arrived");
const fullLink = (path: string) => `${window.location.origin}${path}`;

/** A design-system card with a real heading, so each source is a named section. */
function Card({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="ds-card ds-side" aria-label={title}>
      <div className="ds-side__head">
        <h2 className="ds-side__title" style={{ margin: 0 }}>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Message({ shown }: { shown: Shown }) {
  const [copied, setCopied] = useState(false);
  const text = shown.linkPath ? shown.email.body.replace("{link}", fullLink(shown.linkPath)) : shown.email.body;
  async function copy() {
    try {
      await navigator.clipboard.writeText(`${shown.email.subject}\n\n${text}`);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <Card title={shown.title}>
      {shown.linkPath ? <p className="ds-warn">{t.linkNote}</p> : null}
      <strong>{shown.email.subject}</strong>
      <pre className="ds-soft" style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit", fontSize: 13 }}>{text}</pre>
      <div><Button onClick={() => void copy()}>{copied ? t.copied : t.copy}</Button></div>
    </Card>
  );
}

function Rules({ assessmentId, sourceId }: { assessmentId: string; sourceId: string }) {
  const [rules, setRules] = useState<QualityRule[]>([]);
  useEffect(() => {
    let live = true;
    getSourceProfile(assessmentId, sourceId)
      // one rule can serve several measures: show each wording once
      .then((d) => live && setRules([...new Map(Object.values(d.quality_rules ?? {}).flat().map((r) => [r.text, r])).values()]))
      .catch(() => live && setRules([]));
    return () => { live = false; };
  }, [assessmentId, sourceId]);
  return (
    <div>
      <strong className="ds-side__title">{t.rulesTitle}</strong>
      {rules.length === 0 ? <p>{t.noRules}</p> : <ul>{rules.map((r) => <li key={r.id}>{r.text}</li>)}</ul>}
    </div>
  );
}

function SourceCard({ row, assessmentId, busy, locked, onSend, onRemind, onUploaded }:
  { row: Row; assessmentId: string; busy: boolean; locked: boolean; onSend: () => void; onRemind: () => void; onUploaded: () => void }) {
  if (row.restricted) {
    return (
      <article className="ds-card ds-side">
        <strong className="ds-side__title">{t.restrictedSource}</strong>
        <p>{t.restrictedNote}</p>
      </article>
    );
  }
  const st = stateOf(row.req);
  const profile = row.req?.profile ?? null;
  const tables = profile?.tables ?? [];
  const rowCount = tables.reduce((n, x) => n + x.row_count, 0);
  const cols = tables.flatMap((x) => x.columns).filter((c) => !c.restricted);
  const fill = cols.length ? Math.round((cols.reduce((n, c) => n + (c.fill ?? 0), 0) / cols.length) * 100) : 0;
  return (
    <Card title={row.name} aside={<Pill tone={TONE[st]}>{t.state[st]}</Pill>}>
      <p>{row.req?.owner ? t.owner(row.req.owner) : t.noOwner}</p>
      {st === "none" && !locked ? <div><Button variant="primary" disabled={busy} onClick={onSend}>{t.send}</Button></div> : null}
      {st === "sent" && !locked ? <div><Button disabled={busy} onClick={onRemind}>{t.remind}</Button></div> : null}
      {row.req && !locked ? (
        <div className="ds-soft" style={{ border: "1px dashed var(--ds-line-2)", borderRadius: 8, padding: 12, display: "grid", gap: 8, fontSize: 13 }}>
          <strong>{t.dropTitle}</strong>
          <FilePicker label={`${t.dropLabel}: ${row.name}`} button={t.upload}
            send={async (name, data) => { await uploadSource(assessmentId, row.id, name, data); onUploaded(); }} />
        </div>
      ) : null}
      {profile ? (
        <>
          <p><strong>{t.profileRows(rowCount)}</strong> · {t.profileCols(cols.length)} · <span className={fill < 90 ? "ds-warn" : undefined}>{t.profileFill(fill)}</span></p>
          <Rules assessmentId={assessmentId} sourceId={row.id} />
          <ProfileView profile={profile} />
        </>
      ) : null}
    </Card>
  );
}

/** The data request in the Intent Centre: source cards in plan order, the benchmarks and what is still missing, from the existing module 3 intake routes. */
export default function RequestScreen() {
  const { assessmentId = "" } = useParams();
  const [stamp, setStamp] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [shown, setShown] = useState<Shown[]>([]);
  const load = useLoad<Loaded>(async () => {
    const intake = await getIntake(assessmentId);
    const [sources, bench, plan] = await Promise.all([getSourceMap(assessmentId).then((m) => m.sources).catch(() => null), getBenchmarks(assessmentId).catch(() => null),
      getPlan(assessmentId).catch(() => null)]);
    return { intake, sources, bench, locked: !!plan?.signed_at };
  }, `m3-request-${assessmentId}-${stamp}`, (d) => d.intake.requests.length === 0 && d.intake.not_yet_asked.length === 0 && (d.sources ?? []).length === 0);

  async function act(run: () => Promise<Shown[]>) {
    setBusy(true);
    setProblem("");
    try {
      const made = await run();
      setShown((s) => [...made, ...s]);
      setStamp((n) => n + 1);
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : t.actionFailed);
    } finally {
      setBusy(false);
    }
  }
  const out = (o: Outgoing, title: string): Shown => ({ title, linkPath: o.link_path ?? null, email: o.email });
  const d = load.data;
  const rows = d ? rowsOf(d) : [];
  const missing = d
    ? [
        ...rows.filter((r) => !r.restricted && !r.req).map((r) => t.notAsked(r.name)),
        ...rows.filter((r) => r.req && r.req.state !== "arrived").map((r) => t.waiting(r.name)),
        ...d.intake.requests.flatMap((r) => (r.profile?.gaps ?? []).map((g) => t.gap(r.source_name, g.text))),
        ...(d.bench?.waiting_for ?? []).map((w) => t.benchWaiting(w.name)),
      ]
    : [];

  const crumbs = <><Link to={INTENT}>{t.crumbs[0]}</Link> / <Link to={`${INTENT}/truth/${assessmentId}`}>{t.crumbs[1]}</Link> / {t.crumbs[2]}</>;
  return (
    <PageFrame title={t.title} subline={d ? t.counts(d.intake.summary.asked, d.intake.summary.arrived, d.bench?.measures.length ?? 0) : t.sub} crumbs={crumbs}
      aside={d ? (
        // ponytail: inline-size containment stops the benchmark tables widening the stacked page on a phone; the real fix is in design.css (report)
        <div style={{ display: "grid", gap: 16, contain: "inline-size" }}>
          <BenchmarkPanel assessmentId={assessmentId} />
          <Card title={t.missingTitle}>
            {missing.length === 0 ? <p>{t.nothingMissing}</p> : <ul>{missing.map((m, i) => <li key={i}>{m}</li>)}</ul>}
          </Card>
        </div>
      ) : undefined}>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      {load.state === "empty" ? (
        <EmptyState title={t.emptyTitle} lines={[t.empty]} links={[{ label: t.crumbs[1], href: `${INTENT}/truth/${assessmentId}` }]} />
      ) : (
        <ScreenState state={load.state} message={load.message ?? (load.state === "error" ? t.loadFailed : undefined)} onRetry={load.retry}>
          {d ? (
            <section aria-label={t.title} style={{ display: "grid", gap: 12 }}>
              {d.locked ? <p className="ds-muted" style={{ margin: 0 }}>{t.locked}</p> : null}
              {shown.map((s, i) => <Message key={i} shown={s} />)}
              {rows.map((r) => (
                <SourceCard key={r.id} row={r} assessmentId={assessmentId} busy={busy} locked={d.locked}
                  onSend={() => void act(async () => (await makeRequests(assessmentId)).sent.map((s) => out(s, s.request.source_name)))}
                  onRemind={() => void act(async () => [out(await remind(assessmentId, r.req?.id ?? ""), `${t.remind}: ${r.name}`)])}
                  onUploaded={() => setStamp((n) => n + 1)} />
              ))}
            </section>
          ) : null}
        </ScreenState>
      )}
    </PageFrame>
  );
}
