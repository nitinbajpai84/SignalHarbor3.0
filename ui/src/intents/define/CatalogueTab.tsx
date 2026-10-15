import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import DownloadButton from "../../components/DownloadButton";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import StatusPill from "../../components/StatusPill";
import { useLoad } from "../../components/useLoad";
import { getWorkList, notifyChanged, type KpiFull, type WorkList } from "../../modules/m2_baseline/api";
import OwnersPanel from "../../modules/m2_baseline/worklist/OwnersPanel";
import TechnicalSection from "../../modules/m2_baseline/technical/TechnicalSection";
import { useSession } from "../../useSession";
import {
  acceptUnknown,
  exportPath,
  getCatalogue,
  getEntry,
  lensDraft,
  renameMeasure,
  sendBack,
  STATES,
  type CatalogueList,
  type Entry,
  type EntryState,
  type ListRow,
} from "./catalogueApi";
import { catalogueCopy as t } from "./catalogueCopy";
import { GovernedPanel } from "./GovernedPanel";

const TONE: Record<EntryState, "success" | "warning" | "muted" | "info" | "danger"> = { confirmed: "success", draft: "warning", not_drafted: "muted", unknown_accepted: "info", changed: "danger" };

function useNarrow(): boolean {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 720px)") : null;
  const [narrow, setNarrow] = useState(!!q?.matches);
  useEffect(() => {
    if (!q) return;
    const on = () => setNarrow(q.matches);
    q.addEventListener?.("change", on);
    return () => q.removeEventListener?.("change", on);
  }, [q]);
  return narrow;
}

const fail = (e: unknown) => (e instanceof ApiError && e.message ? e.message : t.error);

function EntryHeader({ intent, entry, onChanged, canRename }: { intent: string; entry: Entry; onChanged: () => void; canRename: boolean }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(entry.label);
  const [problem, setProblem] = useState<string | null>(null);
  const save = async () => {
    setProblem(null);
    try {
      await renameMeasure(intent, entry.code, label);
      setEditing(false);
      onChanged();
    } catch (e) {
      setProblem(fail(e));
    }
  };
  return (
    <Panel title={entry.label} actions={<><StatusPill tone={TONE[entry.state]}>{entry.state_label}</StatusPill> <span className="n-muted">{t.version(entry.version)}</span></>}>
      <p><strong>{t.code}</strong> {entry.code}</p>
      {entry.aliases.length ? <p className="n-muted">{t.aliases}: {entry.aliases.join(", ")}</p> : null}
      {editing ? (
        <div className="n-flex wrap">
          <input className="n-input" aria-label={t.label} value={label} onChange={(e) => setLabel(e.target.value)} />
          <button type="button" className="n-btn sm primary" onClick={() => void save()}>{t.save}</button>
          <button type="button" className="n-btn sm" onClick={() => setEditing(false)}>{t.cancel}</button>
          <span className="n-muted">{t.renameHelp}</span>
        </div>
      ) : (
        <>
        <button type="button" className="n-btn sm" disabled={!canRename} title={canRename ? undefined : t.renameOnly} onClick={() => setEditing(true)}>{t.rename}</button>
        {canRename ? null : <p className="n-muted">{t.renameOnly}</p>}
        </>
      )}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </Panel>
  );
}

function OwnerLine({ label, who }: { label: string; who: string | null }) {
  return <li>{label}: {who ?? <StatusPill tone="warning">{t.notNamed}</StatusPill>}</li>;
}

/** "Name an owner" (organiser): the module 2 owners panel, which picks from the company's accounts or takes a typed name. */
function NameOwner({ baseline, code, signed, onChanged }: { baseline: string; code: string; signed: boolean; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [kpi, setKpi] = useState<KpiFull | null>(null);
  const load = () => getWorkList(baseline).then((w) => setKpi((w.kpis.find((k) => k.id === code && !k.restricted) as KpiFull | undefined) ?? null)).catch(() => setKpi(null));
  useEffect(() => { if (open) void load(); }, [open, code]);
  const act = (job: Promise<WorkList>) => void job.then(() => { void load(); notifyChanged(); onChanged(); }).catch(() => undefined);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <button type="button" className="n-btn sm" disabled={signed} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? t.cancel : t.nameOwner}</button>
      {open && kpi ? <OwnersPanel id={baseline} kpi={kpi} me="" locked={signed} act={act} /> : null}
    </div>
  );
}

function EntryBlock({ entry, extra }: { entry: Entry; extra?: React.ReactNode }) {
  return (
    <Panel title={t.entryTitle}>
      <h3>{t.sources}</h3>
      {entry.sources.length ? <ul>{entry.sources.map((s) => <li key={s.id}>{s.name} <span className="n-muted">({t.sourceOwner(s.owner)})</span></li>)}</ul> : <p className="n-muted">{t.noSources}</p>}
      <h3>{t.fields}</h3>
      {entry.fields.length ? (
        <ul>{entry.fields.map((f) => <li key={f.id}>{f.name} {f.class ? <StatusPill tone={f.class === "Neither" ? "muted" : "warning"}>{f.class}</StatusPill> : <StatusPill tone="warning">{t.notDecided}</StatusPill>}</li>)}</ul>
      ) : <p className="n-muted">{t.noFields}</p>}
      <p><strong>{t.personalClass}</strong>: {entry.personal_class ?? <StatusPill tone="warning">{t.notDecided}</StatusPill>}</p>
      <p><strong>{t.whoMaySee}</strong>: {entry.may_see?.length ? entry.may_see.join(", ") : t.everyone}</p>
      <h3>{t.owners}</h3>
      <ul>
        <OwnerLine label={t.business} who={entry.owners.business} />
        <OwnerLine label={t.data} who={entry.owners.data} />
        <OwnerLine label={t.source} who={entry.owners.source} />
      </ul>
      {extra}
    </Panel>
  );
}

function Actions({ baseline, entry, roles, onChanged }: { baseline: string; entry: Entry; roles: string[]; onChanged: () => void }) {
  const [note, setNote] = useState("");
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const run = async (job: Promise<unknown>) => {
    setProblem(null);
    try {
      await job;
      setAsking(false);
      setNote("");
      notifyChanged();
      onChanged();
    } catch (e) {
      setProblem(fail(e));
    }
  };
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {entry.accepted ? <p>{t.acceptedBy(entry.accepted.by, entry.accepted.at)}</p> : null}
      {entry.sent_back ? <p className="n-muted">{entry.sent_back.label}</p> : null}
      <div className="n-flex wrap">
        {entry.state !== "not_drafted" && (entry.can_confirm || roles.includes("company_admin") || roles.includes("analyst")) ? <button type="button" className="n-btn sm" onClick={() => setAsking(true)}>{t.sendBack}</button> : null}
        {roles.includes("sponsor") && !entry.accepted && entry.state !== "confirmed" ? <button type="button" className="n-btn sm" onClick={() => void run(acceptUnknown(baseline, entry.code))}>{t.acceptUnknown}</button> : null}
      </div>
      {asking ? (
        <div className="n-flex wrap">
          <input className="n-input" aria-label={t.sendBackReason} placeholder={t.sendBackReason} value={note} onChange={(e) => setNote(e.target.value)} />
          <button type="button" className="n-btn sm primary" disabled={!note.trim()} onClick={() => void run(sendBack(baseline, entry.code, note))}>{t.sendBack}</button>
          <button type="button" className="n-btn sm" onClick={() => setAsking(false)}>{t.cancel}</button>
          <span className="n-muted">{t.sendBackHelp}</span>
        </div>
      ) : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </div>
  );
}

function EntryView({ intent, baseline, code, signed, roles, me, onChanged }: { intent: string; baseline: string; code: string; signed: boolean; roles: string[]; me: string | null; onChanged: () => void }) {
  const loaded = useLoad(() => getEntry(intent, code), `entry-${intent}-${code}`);
  const [tick, setTick] = useState(0);
  const [fresh, setFresh] = useState<Entry | null>(null);
  useEffect(() => { setFresh(null); }, [loaded.data, code]);
  useEffect(() => {
    if (!tick) return;
    getEntry(intent, code).then(setFresh).catch(() => undefined);
  }, [tick]);
  useEffect(() => {
    const again = () => setTick((n) => n + 1);
    window.addEventListener("sh:baseline-changed", again);
    return () => window.removeEventListener("sh:baseline-changed", again);
  }, []);
  const entry = fresh ?? loaded.data;
  const changed = () => { setTick((n) => n + 1); onChanged(); };
  return (
    <ScreenState state={fresh ? "populated" : loaded.state} message={loaded.message} onRetry={loaded.retry}>
      {entry ? (
        <div style={{ display: "grid", gap: 12 }}>
          <EntryHeader intent={intent} entry={entry} onChanged={changed} canRename={roles.includes("company_admin") || roles.includes("analyst")} />
          <Panel title={t.businessDefinition}>
            {entry.business_definition ? <p>{entry.business_definition}</p> : <p className="n-muted">{t.noBusinessDefinition}</p>}
          </Panel>
          <TechnicalSection baselineId={baseline} kpiId={code} locked={signed} governor={roles.includes("company_admin") || roles.includes("sponsor")} />
          <EntryBlock entry={entry} extra={roles.includes("company_admin") ? <NameOwner baseline={baseline} code={code} signed={signed} onChanged={changed} /> : null} />
          <Actions baseline={baseline} entry={entry} roles={roles} onChanged={changed} />
          <GovernedPanel intentId={intent} measureId={code} me={me} roles={roles} />
          <Panel title={t.trail}>
            {entry.trail.length > 1 ? (
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{[...entry.trail].reverse().map((x) => <li key={`${x.v}-${x.text}`}>v{x.v}, {x.at}, {x.text}</li>)}</ul>
            ) : <p className="n-muted">{t.trailEmpty}</p>}
          </Panel>
        </div>
      ) : null}
    </ScreenState>
  );
}

function Row({ r, active, onOpen }: { r: ListRow; active: boolean; onOpen: (code: string) => void }) {
  if (r.restricted || !r.code || !r.state) return <li className="n-muted" style={{ padding: 8 }}>{t.restricted}</li>;
  const code = r.code;
  return (
    <li>
      <button type="button" className="n-btn" aria-pressed={active} onClick={() => onOpen(code)} style={{ width: "100%", textAlign: "left", display: "grid", gap: 4 }}>
        <span><strong>{code}</strong> {r.label}</span>
        <span className="n-flex wrap">
          <StatusPill tone={TONE[r.state]}>{r.state_label}</StatusPill>
          <span className="n-muted">{t.owner}: {r.owner ?? t.notNamed}</span>
          {r.guessed ? <span className="n-muted">{t.guessed(r.guessed)}</span> : null}
        </span>
      </button>
    </li>
  );
}

/** Define > Catalogue (spec 30, Screen A and B). `owner=me` in the address shows the signed-in data owner's own list. Mounted by the Define view. */
export function CatalogueTab({ intentId, onOpenClusters }: { intentId: string; onOpenClusters?: () => void }) {
  const [params] = useSearchParams();
  const mine = params.get("owner") === "me";
  const loaded = useLoad(() => getCatalogue(intentId, mine ? "me" : undefined), `cat-${intentId}-${mine}`);
  const [fresh, setFresh] = useState<CatalogueList | null>(null);
  const [filter, setFilter] = useState<EntryState | null>((params.get("filter") as EntryState | null) ?? null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const narrow = useNarrow();
  const { user } = useSession();
  const roles = user?.roles ?? [];
  useEffect(() => { setFresh(null); }, [loaded.data]);
  const data = fresh ?? loaded.data;
  const reload = () => void getCatalogue(intentId, mine ? "me" : undefined).then(setFresh).catch(() => undefined);
  const draft = async () => {
    if (!data) return;
    setBusy(true);
    setProblem(null);
    try {
      await lensDraft(data.baseline_id);
      reload();
    } catch (e) {
      setProblem(fail(e));
    } finally {
      setBusy(false);
    }
  };
  const norm = (s: string) => s.toLowerCase();
  const rows = (data?.measures ?? []).filter((r) => r.restricted || ((!filter || r.state === filter) && (!q || norm([r.code, r.label, ...(r.aliases ?? [])].join(" ")).includes(norm(q)))));
  const canDraft = roles.includes("company_admin") || roles.includes("analyst");
  const list = (
    <Panel title={t.listTitle}>
      <input className="n-input" type="search" aria-label={t.search} placeholder={t.search} value={q} onChange={(e) => setQ(e.target.value)} />
      {rows.some((r) => !r.restricted) ? (
        <ul style={{ listStyle: "none", margin: "8px 0 0", padding: 0, display: "grid", gap: 8 }}>
          {rows.map((r, i) => <Row key={r.code ?? `r${i}`} r={r} active={r.code === open} onOpen={setOpen} />)}
        </ul>
      ) : <p className="n-muted">{t.noMatch}</p>}
    </Panel>
  );
  const side = data ? (
    <div style={{ display: "grid", gap: 12 }}>
      <Panel title={t.waiting}>
        {data.waiting.length ? (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {data.waiting.map((w) => (
              <li key={w.person}>
                <button type="button" className="n-btn sm" onClick={() => setOpen(w.codes[0] ?? null)}>{w.text ?? t.waitingFor(w.codes.length)}</button> <span className="n-muted">{w.person}</span>
              </li>
            ))}
          </ul>
        ) : <p className="n-muted">{t.waitingNone}</p>}
      </Panel>
      <Panel title={t.lens}>
        <p>{data.lens_line}</p>
      </Panel>
      {data.blockers.map((b) => <p key={b} role="alert" className="state state-error">{t.blocker}: {b}</p>)}
      <div className="n-flex wrap">
        <DownloadButton path={exportPath(data.baseline_id)} fallbackName="catalogue.xlsx" label={t.download} />
        <Link className="n-btn" to={`/modules/m2_baseline/catalogue/${data.baseline_id}`}>{t.openFull}</Link>
      </div>
    </div>
  ) : null;
  return (
    <ScreenState state={fresh ? "populated" : loaded.state} message={loaded.state === "loading" ? t.loading : loaded.state === "error" ? t.failed : loaded.state === "refused" ? t.refused : loaded.message} onRetry={loaded.retry}>
      {data ? (
        data.empty || (mine && !data.measures.length) ? (
          <div className="n-empty">
            <p className="ebody">{mine ? t.mineEmpty : data.empty}</p>
            {onOpenClusters && !mine ? <button type="button" className="n-btn" onClick={onOpenClusters}>{t.openClusters}</button> : null}
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            <div className="n-flex wrap" role="group" aria-label={t.tab}>
              <button type="button" className="n-btn sm" aria-pressed={filter === null} onClick={() => setFilter(null)}>{t.filterAll}</button>
              {STATES.map((s) => (
                <button key={s} type="button" className="n-btn sm" aria-pressed={filter === s} onClick={() => setFilter(filter === s ? null : s)}>{t.counts[s]} {data.counts?.[s] ?? 0}</button>
              ))}
              {data.not_drafted > 0 && canDraft ? <button type="button" className="n-btn sm primary" disabled={busy} onClick={() => void draft()}>{t.draftWithLens}</button> : null}
              {busy ? <span role="status" className="n-muted">{t.drafting(data.not_drafted)}</span> : null}
            </div>
            {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
            {narrow ? (
              open ? (
                <div style={{ display: "grid", gap: 12 }}>
                  <button type="button" className="n-btn" style={{ width: "100%" }} onClick={() => setOpen(null)}>{t.back}</button>
                  <EntryView intent={intentId} baseline={data.baseline_id} code={open} signed={data.signed} roles={roles} me={user?.display_name ?? null} onChanged={reload} />
                </div>
              ) : <>{list}{side}</>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) minmax(0, 2fr) minmax(220px, 1fr)", gap: 16, alignItems: "start" }}>
                {list}
                <div>{open ? <EntryView intent={intentId} baseline={data.baseline_id} code={open} signed={data.signed} roles={roles} me={user?.display_name ?? null} onChanged={reload} /> : <div className="n-empty"><p className="ebody">{t.listTitle}</p></div>}</div>
                {side}
              </div>
            )}
          </div>
        )
      ) : null}
    </ScreenState>
  );
}

export default CatalogueTab;
