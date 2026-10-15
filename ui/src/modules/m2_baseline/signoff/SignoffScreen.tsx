import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import BaselineSteps, { SignedBanner } from "../BaselineSteps";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../../components/useLoad";
import {
  acceptUnknown,
  confirmPart,
  countersign,
  getAudit,
  getMyParts,
  getReview,
  nameOwner,
  newVersion,
  saveReview,
  settleChoice,
  type AuditEntry,
  type AuditLog,
  type KpiReview,
  type MyParts,
  type PartView,
  type SignoffView,
} from "../api";
import { m2Signoff as T } from "../copy";
import { DocumentsPanel, GatePanel } from "./GatePanel";
import OwnerTechnical from "../requests/OwnerTechnical";
import { confirmTechnical, getMyTechnical } from "../technical/technicalApi";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : T.busy);
const same = (a: string | null, b: string) => a !== null && a.trim().toLowerCase() === b.trim().toLowerCase();

/** The history in plain words: the measure and the part are named, and repeats on one day by one person are one line. */
export function auditLines(entries: AuditEntry[], kpis: KpiReview[]): string[] {
  const groups = new Map<string, { by: string; at: string; action: string; kpi: KpiReview | undefined; parts: string[]; detail?: string; n: number }>();
  for (const e of entries) {
    const key = [day(e.at), e.by, e.action, e.kpi_id ?? "", e.action === "confirm" ? "" : e.detail ?? ""].join("|");
    const g = groups.get(key) ?? { by: e.by, at: e.at, action: e.action, kpi: kpis.find((k) => k.id === e.kpi_id), parts: [], detail: e.detail, n: 0 };
    g.n += 1;
    const part = g.kpi?.parts.find((p) => p.id === e.part)?.owner_label;
    if (part && !g.parts.includes(part)) g.parts.push(part);
    groups.set(key, g);
  }
  const list = (xs: string[]) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}` : (xs[0] ?? ""));
  return [...groups.values()].map((g) => {
    const what = g.kpi ? ` ${g.kpi.name}` : "";
    const head = `${day(g.at)}: ${g.by}`;
    if (g.action === "confirm" && g.parts.length) return `${head} confirmed the ${list(g.parts)} ${g.parts.length > 1 ? "parts" : "part"} of${what}`;
    if (g.action === "accept") return `${head} accepted${what} as unknown for now`;
    const said = T.audit.actions[g.action] ?? g.action;
    const detail = g.detail && g.action !== "confirm" && g.action !== "accept" ? ` (${g.detail})` : "";
    return `${head} ${said}${what ? (g.action === "sign" ? "" : ` for${what}`) : ""}${detail}${g.n > 1 && !g.parts.length ? ` (${g.n} times)` : ""}`;
  });
}

interface Run {
  (work: () => Promise<SignoffView>, done?: string): Promise<void>;
}

/** The baseline review (deck slides 2 and 13): what is unknown, owners confirming their parts, readiness, then the signature paper. */
export default function SignoffScreen() {
  const { baselineId = "" } = useParams();
  // D4: an owner whose role cannot open the whole review (approver, participant) gets exactly their own parts instead
  const { state, data, message, retry } = useLoad<SignoffView | MyParts>(
    () => getReview(baselineId).catch((e: unknown) => (e instanceof ApiError && e.status === 403 ? getMyParts(baselineId) : Promise.reject(e))),
    `signoff:${baselineId}`,
  );
  return (
    <>
      <PageHead
        eyebrow={T.eyebrow}
        title={T.title}
        sub={T.sub}
        crumbs={[{ label: T.crumbHome, to: "/modules/m2_baseline" }, { label: T.crumb }]}
      />
      <BaselineSteps baselineId={baselineId} />
      <ScreenState state={state} onRetry={retry} message={message}>
        {data && "parts" in data ? <MyPartsOnly baselineId={baselineId} first={data} /> : data ? <Body baselineId={baselineId} first={data} /> : null}
      </ScreenState>
    </>
  );
}

/** An owner without the full review: their own parts, each with Confirm my part. Nothing else of the baseline is shown. */
function MyPartsOnly({ baselineId, first }: { baselineId: string; first: MyParts }) {
  const [mine, setMine] = useState(first);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const open = mine.status === "open";
  async function confirm(kpi: string, part: string) {
    setBusy(true);
    setProblem(null);
    try {
      await confirmPart(baselineId, kpi, part);
      setMine(await getMyParts(baselineId));
    } catch (e) {
      setProblem(problemText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title={T.mine.title}>
      <p className="n-e1-def-note">{mine.parts.length ? T.mine.help : T.mine.none}</p>
      <ul className="m1-list">
        {mine.parts.map((p) => (
          <li key={`${p.kpi_id}-${p.part}`}>
            {T.mine.line(p.kpi_name, p.label)}{" "}
            {p.confirmed ? (
              <strong>{T.mine.done}</strong>
            ) : open ? (
              <button type="button" className="n-btn sm" disabled={busy} aria-label={`${T.mine.confirm}: ${T.mine.line(p.kpi_name, p.label)}`} onClick={() => void confirm(p.kpi_id, p.part)}>
                {T.mine.confirm}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      <MyTechnical baselineId={baselineId} />
    </Panel>
  );
}

/** The technical definitions of the measures this person is the named data owner of, with Confirm (the same read as /my-parts, open to every role). */
function MyTechnical({ baselineId }: { baselineId: string }) {
  const loaded = useLoad(() => getMyTechnical(baselineId), `m2-my-technical-${baselineId}`);
  const mine = loaded.data;
  if (!mine?.kpis?.length) return null;
  return (
    <OwnerTechnical
      technical={mine.kpis}
      locked={mine.signed}
      onConfirm={async (kpi) => {
        await confirmTechnical(baselineId, kpi);
        return (await getMyTechnical(baselineId)).kpis;
      }}
    />
  );
}

function Body({ baselineId, first }: { baselineId: string; first: SignoffView }) {
  const [view, setView] = useState<SignoffView>(first);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditLog | null>(null);
  const [auditFailed, setAuditFailed] = useState(false);

  useEffect(() => {
    let live = true;
    getAudit(baselineId)
      .then((a) => live && (setAudit(a), setAuditFailed(false)))
      .catch(() => live && setAuditFailed(true));
    return () => {
      live = false;
    };
  }, [baselineId, view]);

  const run: Run = async (work, done) => {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      setView(await work());
      if (done) setNotice(done);
    } catch (e) {
      setProblem(problemText(e));
    } finally {
      setBusy(false);
    }
  };
  const open = view.status === "open" && view.signatures.length === 0;
  return (
    <>
      {view.status === "signed" ? <SignedBanner /> : null}
      <Readiness view={view} />
      {view.gate ? <GatePanel gate={view.gate} baselineId={baselineId} open={open} canLeave={view.viewer.can_settle} busy={busy} run={run} /> : null}
      <Panel title={T.kpis.title} eyebrow={T.version(view.version)}>
        {view.kpis.map((k) => (
          <KpiRow key={k.id} k={k} view={view} open={open} busy={busy} run={run} baselineId={baselineId} />
        ))}
        {notice ? <p role="status" className="state n-muted">{notice}</p> : null}
        {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      </Panel>
      <Coming view={view} />
      {view.documents ? <DocumentsPanel view={view} baselineId={baselineId} /> : null}
      <Paper view={view} baselineId={baselineId} busy={busy} run={run} />
      <Panel title={T.audit.title} tight>
        {auditFailed ? <p role="alert" className="state state-error">{T.busy}</p> : null}
        {audit && audit.entries.length === 0 ? <p className="state n-muted">{T.audit.empty}</p> : null}
        <ul>
          {auditLines(audit?.entries ?? [], view.kpis).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {audit ? (
          <p className={audit.intact ? "n-e1-def-note" : "state state-error"} role={audit.intact ? undefined : "alert"}>
            {audit.intact ? T.audit.intact : T.audit.broken}
          </p>
        ) : null}
      </Panel>
    </>
  );
}

/** The readiness checklist: the three rules, then what is not required but is still open. */
function Readiness({ view }: { view: SignoffView }) {
  const R = T.readiness;
  return (
    <Panel
      title={R.title}
      actions={<StatusPill tone={view.ready ? "success" : "warning"}>{view.ready ? R.ready : R.notReady}</StatusPill>}
    >
      {view.kpis.length === 0 ? <p className="state n-muted">{R.noMeasures}</p> : null}
      <ul className="n-companion-checklist static" aria-label={R.title}>
        {view.items.map((i) => (
          <li key={i.id}>
            <strong>{i.label}</strong>{" "}
            <StatusPill tone={i.met ? "success" : i.required ? "warning" : "muted"}>{i.met ? R.met : i.required ? R.open : `${R.open} · ${R.advice}`}</StatusPill>
            {i.missing.length ? (
              <ul className="n-e1-def-note">
                {i.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function KpiRow({ k, view, open, busy, run, baselineId }: { k: KpiReview; view: SignoffView; open: boolean; busy: boolean; run: Run; baselineId: string }) {
  const K = T.kpis;
  const tone = k.state === "ready" ? "success" : k.state === "blocked" ? "danger" : "warning";
  const source = k.source.status === "stated" ? String(k.source.value) : k.source.status === "unknown" ? K.sourceUnknown : k.source.status === "conflict" ? K.sourceConflict : K.notStated;
  return (
    <div className="n-e1-def-row" style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
        <div className="n-e1-def-name">{k.name}</div>
        <StatusPill tone={tone}>{K.state[k.state]}</StatusPill>
      </div>
      <div className="n-e1-def-note">
        {`${K.tracking}: ${k.tracking.label ?? K.trackingNotStated}. ${K.source}: ${source}.`}
      </div>
      {k.unknowns.length === 0 ? <div className="n-e1-def-note">{K.nothingUnknown}</div> : (
        <ul className="n-e1-def-note">
          {k.unknowns.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
      {k.waiting_note ? <div className="n-e1-def-note">{T.settle.waiting(k.waiting_note)}</div> : null}
      {k.sensing.map((s) =>
        s.status === "conflict" ? (
          <fieldset key={s.id} disabled={!open || busy || !view.viewer.can_settle} style={{ border: 0, padding: 0, display: "grid", gap: 6 }}>
            <legend className="n-e1-def-name">{`${T.settle.title}: ${s.label}`}</legend>
            <span className="n-e1-def-note">{T.settle.help}</span>
            {s.options.map((o) => (
              <div key={`${String(o.value)}-${o.by}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className="n-e1-def-note">{T.settle.option(o.label ?? String(o.value), o.by)}</span>
                {view.viewer.can_settle ? (
                  <button type="button" className="n-btn" aria-label={`${T.settle.button}: ${s.label}, ${o.label ?? String(o.value)}`}
                    onClick={() => void run(() => settleChoice(baselineId, k.id, s.id, String(o.value)))}>
                    {T.settle.button}
                  </button>
                ) : null}
              </div>
            ))}
          </fieldset>
        ) : s.settled ? (
          <div key={s.id} className="n-e1-def-note">{`${s.label}: ${T.settle.settledBy(s.settled.label ?? String(s.settled.value), s.settled.by, day(s.settled.at))}`}</div>
        ) : null,
      )}
      {k.parts.map((p) => (
        <Part key={p.id} p={p} kpi={k} view={view} open={open} busy={busy} run={run} baselineId={baselineId} />
      ))}
      {k.review ? <NextSteps k={k} view={view} open={open} busy={busy} run={run} baselineId={baselineId} /> : null}
    </div>
  );
}

function Part({ p, kpi, view, open, busy, run, baselineId }: { p: PartView; kpi: KpiReview; view: SignoffView; open: boolean; busy: boolean; run: Run; baselineId: string }) {
  const P = T.parts;
  const [name, setName] = useState("");
  const mine = same(p.owner_name, view.viewer.name);
  let right;
  if (p.confirmed) right = <span className="n-e1-def-note">{P.confirmedBy(p.confirmed.by, day(p.confirmed.at))}</span>;
  else if (p.owner_status === "named" && mine && open)
    right = (
      <button type="button" className="n-btn" disabled={busy} aria-label={`${P.confirm}: ${kpi.name}, ${p.label}`} onClick={() => void run(() => confirmPart(baselineId, kpi.id, p.id))}>
        {P.confirm}
      </button>
    );
  else if (p.owner_status === "named") right = <span className="n-e1-def-note">{P.waiting(p.owner_name ?? "")}</span>;
  else if (p.owner_status === "no_owner" && view.viewer.sponsor && open)
    right = (
      <span style={{ display: "inline-flex", gap: 6 }}>
        <input type="text" aria-label={P.nameLabel(p.owner_label)} value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" className="n-btn" disabled={busy || !name.trim()} onClick={() => void run(() => nameOwner(baselineId, kpi.id, p.id, name.trim()))}>
          {P.nameButton}
        </button>
      </span>
    );
  else right = <span className="n-e1-def-note">{p.owner_status === "no_owner" ? P.noOwner(p.owner_label) : P.notNominated(p.owner_label)}</span>;
  return (
    <div style={{ display: "flex", gap: 12, justifyContent: "space-between", alignItems: "center" }}>
      <span className="n-e1-def-note">{`${p.label}${p.owner_name ? ` · ${p.owner_name}` : ""}`}</span>
      {right}
    </div>
  );
}

function NextSteps({ k, view, open, busy, run, baselineId }: { k: KpiReview; view: SignoffView; open: boolean; busy: boolean; run: Run; baselineId: string }) {
  const N = T.next;
  const r = k.review!;
  const [date, setDate] = useState(r.tentative_date ?? "");
  const [step, setStep] = useState(r.next_step ?? "");
  const [project, setProject] = useState(r.project ?? "");
  useEffect(() => {
    setDate(r.tentative_date ?? "");
    setStep(r.next_step ?? "");
    setProject(r.project ?? "");
  }, [r.tentative_date, r.next_step, r.project]);
  return (
    <fieldset disabled={!open} style={{ border: 0, padding: 0, display: "grid", gap: 6 }}>
      <legend className="n-e1-def-name">{k.tracking.value === "partly" ? N.titlePartly : N.title}</legend>
      <label className="n-e1-def-note">
        {N.date}
        <input type="date" aria-label={`${N.date}: ${k.name}`} value={date} onChange={(e) => setDate(e.target.value)} style={{ display: "block" }} />
      </label>
      <label className="n-e1-def-note">
        {N.step}
        <input type="text" aria-label={`${N.step}: ${k.name}`} value={step} onChange={(e) => setStep(e.target.value)} style={{ display: "block", width: "100%" }} />
      </label>
      <label className="n-e1-def-note">
        {N.project}
        <input type="text" aria-label={`${N.project}: ${k.name}`} value={project} onChange={(e) => setProject(e.target.value)} style={{ display: "block", width: "100%" }} />
      </label>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" className="n-btn" disabled={busy} aria-label={`${N.save}: ${k.name}`} onClick={() => void run(() => saveReview(baselineId, k.id, { tentative_date: date, next_step: step, project }), N.saved)}>
          {N.save}
        </button>
        {r.accepted ? (
          <span className="n-e1-def-note">{N.accepted(r.accepted.by, day(r.accepted.at))}</span>
        ) : view.viewer.sponsor ? (
          <button type="button" className="n-btn" disabled={busy} aria-label={`${N.accept}: ${k.name}`} onClick={() => void run(() => acceptUnknown(baselineId, k.id))}>
            {N.accept}
          </button>
        ) : (
          <span className="n-e1-def-note">{k.covered ? N.covered : N.notAccepted}</span>
        )}
      </div>
    </fieldset>
  );
}

/** M2-23's one-page view: what is coming and which project brings it. */
function Coming({ view }: { view: SignoffView }) {
  return (
    <Panel title={T.coming.title} tight>
      {view.coming.length === 0 ? <p className="state n-muted">{T.coming.nothing}</p> : null}
      <ul>
        {view.coming.map((c) => (
          <li key={c.kpi_id}>{T.coming.row(c.name, c.tentative_date, c.project)}</li>
        ))}
      </ul>
    </Panel>
  );
}

// Shown when the baseline is signed but its outcome record is not closed yet; the same sign call retries the closing step.
const PENDING = { note: "Signed. The outcome record is pending: it has not been closed yet.", retry: "Retry the outcome record" };

/** The signature paper, laid out like the charter's: the signature lines, then the way to sign or to start a new version. */
function Paper({ view, baselineId, busy, run }: { view: SignoffView; baselineId: string; busy: boolean; run: Run }) {
  const P = T.paper;
  const signed = view.status === "signed";
  const pending = (view as SignoffView & { record_pending?: boolean }).record_pending === true;
  const [saving, setSaving] = useState(false);
  // D10: the page never shows the old "Not signed yet" while a signature is on its way; it says so, then shows the response
  const sign = async () => {
    setSaving(true);
    try {
      await run(() => countersign(baselineId));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Panel
      eyebrow={`${T.crumb} · ${signed ? T.status.signed : T.status.open}`}
      title={P.title}
      className="m1-charter"
      actions={<StatusPill tone={signed ? "success" : "muted"}>{signed ? T.status.signed : T.status.open}</StatusPill>}
    >
      <p className="n-e1-def-note">{P.sub}</p>
      {view.note ? <p role="note" className="n-e1-def-note">{view.note}</p> : null}
      <p className="n-e1-def-name">{P.signers(view.signatures.length, view.signatures.length + view.waiting_for.length)}</p>
      <div className="n-e1-charter-grid">
        {view.signatures.map((s) => (
          <div key={s.slot} className="n-e1-signature">
            <div>
              <div className="sig-meta">{`${s.label} · ${day(s.at)}`}</div>
              <div className="sig-actor">{s.name}</div>
              {s.note ? <div className="sig-meta">{s.note}</div> : null}
            </div>
            <StatusPill tone="success">{T.status.signed}</StatusPill>
          </div>
        ))}
        {view.waiting_for.map((label) => (
          <div key={label} className="n-e1-signature">
            <div>
              <div className="sig-meta">{label}</div>
              <div className="sig-actor">{saving ? P.saving : P.notSigned}</div>
            </div>
            <StatusPill tone="muted">{T.status.open}</StatusPill>
          </div>
        ))}
      </div>
      {signed && pending ? (
        <>
          <p role="status" className="n-e1-def-note">{PENDING.note}</p>
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => void run(() => countersign(baselineId))}>
            {PENDING.retry}
          </button>
        </>
      ) : signed ? <p className="n-e1-def-note">{`${P.locked} ${P.handedOn}`}</p> : null}
      {!signed && view.signatures.length > 0 ? <p className="n-e1-def-note">{P.waiting(view.waiting_for)}</p> : null}
      {!signed && view.viewer.slot && view.can_countersign && view.gate && !view.gate.ok ? <p role="note" className="n-e1-def-note">{view.gate.refusal}</p> : null}
      {!signed && view.viewer.slot && view.can_countersign ? (
        <button type="button" className="n-btn primary" disabled={busy || saving || (!!view.gate && !view.gate.ok)} onClick={() => void sign()}>
          {saving ? P.saving : P.sign}
        </button>
      ) : null}
      {saving ? <p role="status" className="n-e1-def-note">{P.saving}</p> : null}
      {!signed && view.viewer.slot && !view.can_countersign ? <p className="n-e1-def-note">{P.cannot}</p> : null}
      {signed ? (
        <button type="button" className="n-btn" disabled={busy} onClick={() => void run(() => newVersion(baselineId))}>
          {P.newVersion}
        </button>
      ) : null}
    </Panel>
  );
}
