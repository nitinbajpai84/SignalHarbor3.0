import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import ScreenState from "../../../components/ScreenState";
import { Button, DataTable, EmptyState, PageFrame, Pill, SideCard, Signature, StatCard, StatGrid, type PillTone } from "../../../design";
import { useSession } from "../../../useSession";
import { useLoad } from "../../m1_intent/useLoad";
import { getSourceMap, moveSource, type SourceMapData } from "../api";
import { getIntake, type Intake } from "../intake/api";
import { getPlan, getRisks, signPlan, type PlanItem, type PlanView, type RisksView } from "../plan/planApi";
import { planCopy } from "../plan/copy";
import { plainText } from "../plainText";
import { compileRules, getTrial, runTrial, type Result, type TrialRow, type TrialView } from "../trial/api";
import { truthText as t } from "./copy";
import SourceQuadrant from "./SourceQuadrant";

const TONE: Record<Result, PillTone> = { matches: "ok", gap: "late", cannot: "draft" };
const INTENT = "/centre/intent";
const BUILD = "/centre/build";
const BANDS = ["now", "next", "later"] as const;
const FIRST_ROWS = 8;
const row4 = { display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", alignItems: "start" } as const;

interface Loaded {
  trial: TrialView;
  map: SourceMapData | null;
  plan: PlanView | null;
  risks: RisksView | null;
  intake: Intake | null;
}

// A currency code goes before the figure (SGD 3,520,000), any other unit after it (12.92 %).
const figure = (v: number | null | undefined, unit?: string | null) => {
  if (v === null || v === undefined) return null;
  const n = v.toLocaleString("en", { maximumFractionDigits: 2 });
  return !unit ? n : /^[A-Z]{3}$/.test(unit) ? `${unit} ${n}` : `${n} ${unit}`;
};
const day = (iso: string) => (Number.isNaN(new Date(iso).getTime()) ? "" : new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }));

/** The reason as one sentence, with the fix (from "Fix:" on) in amber. */
function Why({ text, missing }: { text: string; missing?: string | null }) {
  const i = text.search(/\bFix:/);
  return (
    <>
      {i < 0 ? text : <>{text.slice(0, i)}<span className="ds-warn">{text.slice(i)}</span></>}
      {missing ? <> <span className="ds-warn">{plainText(missing)}</span></> : null}
    </>
  );
}

function Tiles({ trial, plan }: { trial: TrialView; plan: PlanView | null }) {
  const open = trial.measures.filter((m) => !m.restricted);
  const n = (r: Result) => open.filter((m) => (m.result ?? "cannot") === r).length;
  const items = plan ? BANDS.flatMap((b) => plan.bands[b]) : [];
  // Hidden from this viewer (trial rows, plan cards with no measure) and visible but fed by a source only some people may see.
  const hidden = trial.measures.length - open.length + items.filter((i) => i.restricted && i.measures.length === 0).length;
  const viaSource = items.filter((i) => i.restricted && i.measures.length > 0).reduce((k, i) => k + i.measures.length, 0);
  return (
    <section aria-label={t.title} style={{ display: "grid", gap: 12 }}>
      <StatGrid cols={3}>
        {(["matches", "gap", "cannot"] as const).map((r) => (
          <StatCard key={r} label={t.tiles[r].label} value={n(r)} note={t.tiles[r].note} valueTone={r === "gap" ? "warn" : undefined} />
        ))}
      </StatGrid>
      {hidden + viaSource > 0 ? (
        <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>{t.restrictedLine}{" "}
          {hidden > 0 ? <Pill tone="restricted">{t.restrictedCount(hidden)}</Pill> : null}{" "}
          {viaSource > 0 ? <Pill tone="restricted">{t.viaSourceCount(viaSource)}</Pill> : null}
        </p>
      ) : null}
    </section>
  );
}

function Table({ rows, plan }: { rows: TrialRow[]; plan: PlanView | null }) {
  const [all, setAll] = useState(false);
  const items = plan ? BANDS.flatMap((b) => plan.bands[b]) : [];
  const owner = (m: string) => items.find((i) => !i.restricted && i.measures.some((x) => x.id === m))?.team.join(", ") || t.noOwner;
  const shown = all ? rows : rows.slice(0, FIRST_ROWS);
  const cells: Record<string, ReactNode>[] = shown.map((r) => {
    if (r.restricted) return { measure: <em className="ds-muted">{t.restricted}</em>, pack: "·", files: "·", result: <Pill tone="restricted">{t.pill.restricted}</Pill>, why: <span className="ds-muted">{t.restrictedWhy}</span>, owner: "·" };
    const res = r.result ?? "cannot";
    const ours = figure(r.our_figure, r.unit);
    return {
      measure: <strong>{r.measure} {r.name}</strong>,
      pack: figure(r.their_figure, r.unit) ?? <span className="ds-muted">{t.notAvailable}</span>,
      files: ours ?? <span className="ds-muted">{t.notYet}</span>,
      result: <Pill tone={TONE[res]}>{t.pill[res]}</Pill>,
      why: <Why text={plainText(r.likely_reason_lens || r.likely_reason || "")} missing={r.missing} />,
      owner: owner(r.measure),
    };
  });
  return (
    <section aria-label={t.tableTitle} style={{ display: "grid", gap: 8 }}>
      <DataTable columns={Object.entries(t.head).map(([key, label]) => ({ key, label }))} rows={cells} />
      {!all && rows.length > FIRST_ROWS ? <div><Button onClick={() => setAll(true)}>{t.moreRows(rows.length - FIRST_ROWS)}</Button></div> : null}
    </section>
  );
}

function Signing({ plan, risks, busy, onSign }: { plan: PlanView; risks: RisksView | null; busy: boolean; onSign: () => void }) {
  const slots = [{ slot: "sponsor", label: "Sponsor" }, { slot: "head_of_data", label: "Head of data" }];
  const hiddenRisks = risks?.risks.filter((r) => r.restricted).length ?? 0;
  const decided = (kind: string) => risks?.risks.filter((r) => !r.restricted && r.kind === kind && r.state !== "open").length ?? 0;
  return (
    <SideCard title={t.signTitle}>
      <p>{t.risksLine(decided("risk"), hiddenRisks, decided("ambiguity") + decided("unknown"), plan.risks_undecided)}</p>
      {slots.map(({ slot, label }) => {
        const s = plan.signatures.find((x) => x.slot === slot);
        return s ? <Signature key={slot} state="signed" by={`${s.name}, ${s.label}`} at={day(s.at)} /> : <Signature key={slot} state="waiting" by={label} />;
      })}
      {!plan.signed_at && plan.drafted && plan.viewer.slot ? (
        <Button variant="primary" disabled={busy || !plan.can_sign} onClick={onSign}>{t.signButton}</Button>
      ) : null}
    </SideCard>
  );
}

/** "K04, K09 · ready" when every measure matched in the trial, otherwise what it waits on (the first blocker), from the plan and the trial only. */
function cardNote(it: PlanItem, rows: TrialRow[]): string {
  const ids = it.measures.map((m) => m.id);
  const ready = ids.length > 0 && ids.every((id) => rows.find((r) => r.measure === id)?.result === "matches");
  return t.feeds(ids, ready ? t.ready : it.restricted ? t.viaSource : plainText(it.blocked_by[0] ?? "") || t.waiting);
}

function Plan({ plan, rows, side }: { plan: PlanView; rows: TrialRow[]; side: ReactNode }) {
  return (
    <div style={row4}>
      {BANDS.map((b) => (
        <section key={b} aria-label={plan.bands_info[b].label} className="ds-card ds-side">
          <strong className="ds-strip__label">{plan.bands_info[b].label}{plan.bands_info[b].weeks ? ` · ${plan.bands_info[b].weeks}` : ""}</strong>
          {plan.bands[b].length === 0 ? <span className="ds-muted" style={{ fontSize: 13 }}>{t.emptyBand}</span> : null}
          {plan.bands[b].map((it) => (
            <div key={it.key} className="ds-card ds-stat">
              <strong>{it.measures.length ? it.measures.map((m) => m.name).join(" · ") : planCopy.plan.restrictedCard}</strong>
              {it.measures.length ? <span className="ds-stat__note ds-muted">{cardNote(it, rows)}</span> : null}
            </div>
          ))}
        </section>
      ))}
      {side}
    </div>
  );
}

/** The Moment of truth (artboard 4): the scoreboard and the source map, the trial table, the plan in three bands and the signing panel, from the existing module 3 routes. */
export default function TruthScreen() {
  const { assessmentId = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const canAct = !!user?.roles.some((r) => r === "analyst" || r === "company_admin");
  const [stamp, setStamp] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  // Map, plan, risks and intake may not exist yet; the trial alone is enough to show the screen.
  const load = useLoad<Loaded>(async () => {
    const trial = await getTrial(assessmentId);
    const [map, plan, risks, intake] = await Promise.all([
      getSourceMap(assessmentId).catch(() => null),
      getPlan(assessmentId).catch(() => null),
      getRisks(assessmentId).catch(() => null),
      getIntake(assessmentId).catch(() => null),
    ]);
    return { trial, map, plan, risks, intake };
  }, `m3-truth-${assessmentId}-${stamp}`, (d) => !d.trial.run && !d.trial.compiled);

  async function act(fn: () => Promise<unknown>, failed: string, then?: () => void) {
    setBusy(true);
    setProblem("");
    try {
      await fn();
      setStamp((n) => n + 1);
      then?.();
    } catch {
      setProblem(failed);
    } finally {
      setBusy(false);
    }
  }
  const d = load.data;
  const request = `${INTENT}/truth/${assessmentId}/request`;
  const files = d?.intake ? d.intake.requests.reduce((n, r) => n + (r.profile?.files.length ?? 0), 0) + (d.intake.from_profile ?? []).reduce((n, f) => n + f.files.length, 0) : 0;
  const subline = d?.intake ? t.header(d.intake.period.label, files, d.map?.sources.length ?? 0) : t.sub;
  return (
    <PageFrame title={t.title} subline={subline}
      crumbs={<><Link to={INTENT}>{t.crumbs[0]}</Link> / {t.crumbs[1]}</>}
      actions={
        <>
          <Link className="ds-btn" to={request}>{t.dataRequest}</Link>
          {canAct && !d?.plan?.signed_at ? (
            <Button variant="primary" disabled={busy} onClick={() => void act(async () => { await compileRules(assessmentId); await runTrial(assessmentId); }, t.runFailed)}>
              {busy ? t.running : t.run}
            </Button>
          ) : null}
        </>
      }>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      {load.state === "empty" ? (
        <EmptyState title={t.emptyTitle} lines={[t.empty]} links={[{ label: t.emptyLink, href: request }]} />
      ) : (
        <ScreenState state={load.state} message={load.message} onRetry={load.retry}>
          {d ? (
            <>
              <div style={row4}>
                <Tiles trial={d.trial} plan={d.plan} />
                <SideCard title={t.mapTitle}>
                  {canAct && d.map ? <span className="ds-muted" style={{ fontSize: 12 }}>{t.dragHint}</span> : null}
                  {d.map ? (
                    <SourceQuadrant sources={d.map.sources} canMove={canAct}
                      onMove={async (id, spot, reason) => { await moveSource(assessmentId, id, { ...spot, reason }); setStamp((n) => n + 1); }} />
                  ) : <p>{t.noMap}</p>}
                </SideCard>
              </div>
              <Table rows={d.trial.measures} plan={d.plan} />
              {d.plan?.drafted ? (
                <Plan plan={d.plan} rows={d.trial.measures} side={<Signing plan={d.plan} risks={d.risks} busy={busy} onSign={() => void act(() => signPlan(assessmentId), t.signFailed, () => navigate(BUILD))} />} />
              ) : (
                <>
                  <p className="ds-muted">{t.noPlan}</p>
                  {d.plan ? <Signing plan={d.plan} risks={d.risks} busy={busy} onSign={() => void act(() => signPlan(assessmentId), t.signFailed, () => navigate(BUILD))} /> : null}
                </>
              )}
            </>
          ) : null}
        </ScreenState>
      )}
    </PageFrame>
  );
}
