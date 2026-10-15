import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { useLoad } from "../../m1_intent/useLoad";
import { getAssessment } from "../api";
import ConnectSteps from "../ConnectSteps";
import { m3 } from "../copy";
import NiraNext from "../NiraNext";
import AskedTables from "./AskedTables";
import { getIntake, makeRequests, relink, remind, revoke, uploadSource, type Email, type Intake, type IntakeRequest, type Outgoing } from "./api";
import BenchmarkPanel from "./BenchmarkPanel";
import { m3Intake as T } from "./copy";
import FilePicker from "./FilePicker";
import ProfileSamples from "./ProfileSamples";
import ProfileView from "./ProfileView";

const TONE: Record<string, PillTone> = { sent: "warning", opened: "info", arrived: "success" };
const fullLink = (path: string) => `${window.location.origin}${path}`;

interface Shown {
  title: string;
  linkPath: string | null;
  email: Email;
}

/** M3-P02: the data request (what to ask each source for), the upload, the profile with its gaps, and the figures already reported. */
export default function IntakeScreen() {
  const { assessmentId = "" } = useParams();
  const detail = useLoad(() => getAssessment(assessmentId), `m3-assessment-${assessmentId}`);
  const first = useLoad<Intake>(() => getIntake(assessmentId), `m3-intake-${assessmentId}`, (d) => d.requests.length === 0 && d.not_yet_asked.length === 0 && (d.from_profile ?? []).length === 0);
  const [fresh, setFresh] = useState<Intake | null>(null);
  const [shown, setShown] = useState<Shown[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const view = fresh ?? first.data;

  async function act(run: () => Promise<Shown[]>) {
    setBusy(true);
    setProblem(null);
    try {
      const made = await run();
      setShown((s) => [...made, ...s]);
      setFresh(await getIntake(assessmentId));
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : T.actionFailed);
    } finally {
      setBusy(false);
    }
  }
  const out = (o: Outgoing, title: string): Shown => ({ title, linkPath: o.link_path ?? null, email: o.email });

  return (
    <>
      <PageHead title={T.title} sub={view ? T.period(view.period.label) : ""} eyebrow={m3.eyebrow}
        crumbs={[{ label: m3.crumbModules, to: "/" }, { label: m3.crumbAssess, to: "/modules/m3_connect" }, { label: T.title }]} />
      {detail.data ? <ConnectSteps assessmentId={assessmentId} steps={detail.data.steps} /> : null}
      <ScreenState state={first.state} message={first.state === "empty" ? T.noSources : first.message ?? (first.state === "error" ? T.loadFailed : undefined)} onRetry={first.retry}>
        {view ? (
          <>
            <Panel title={T.title} actions={<StatusPill tone="info">{T.summary(view.summary.asked, view.summary.arrived)}</StatusPill>}>
              <p className="n-muted">{T.askAllHelp}</p>
              <button type="button" className="n-btn" disabled={busy} onClick={() => void act(async () => (await makeRequests(assessmentId)).sent.map((s) => out(s, s.request.source_name)))}>
                {T.askAll}
              </button>
              {problem ? (
                <p role="alert" className="state state-error">
                  {problem}
                </p>
              ) : null}
            </Panel>
            <ProfileSamples assessmentId={assessmentId} fromProfile={view.from_profile ?? []} toConfirm={view.to_confirm ?? []} onChanged={() => void act(async () => [])} />
            {shown.map((s, i) => (
              <Panel key={i} title={s.title}>
                {s.linkPath ? <p className="n-muted">{T.linkNote}</p> : null}
                <Message shown={s} />
              </Panel>
            ))}
            {view.requests.map((r) => (
              <Source key={r.id} r={r} assessmentId={assessmentId} busy={busy}
                onRemind={() => void act(async () => [out(await remind(assessmentId, r.id), `${T.wayRemind}: ${r.source_name}`)])}
                onRelink={() => void act(async () => [out(await relink(assessmentId, r.id), `${T.newLink}: ${r.source_name}`)])}
                onRevoke={() => void act(async () => (await revoke(assessmentId, r.id), []))}
                onUploaded={() => void act(async () => [])} />
            ))}
            <BenchmarkPanel assessmentId={assessmentId} />
          </>
        ) : null}
      </ScreenState>
      {detail.data ? <NiraNext steps={detail.data.steps} /> : null}
    </>
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
    <>
      <p>
        <strong>{shown.email.subject}</strong>
      </p>
      <pre className="n-muted" style={{ whiteSpace: "pre-wrap" }}>{text}</pre>
      <button type="button" className="n-btn" onClick={() => void copy()}>
        {copied ? T.copied : T.copy}
      </button>
    </>
  );
}

function Source({ r, assessmentId, busy, onRemind, onRelink, onRevoke, onUploaded }:
  { r: IntakeRequest; assessmentId: string; busy: boolean; onRemind: () => void; onRelink: () => void; onRevoke: () => void; onUploaded: () => void }) {
  const [profile, setProfile] = useState(r.profile ?? null);
  const arrived = r.state === "arrived";
  return (
    <Panel title={r.source_name} actions={<StatusPill tone={TONE[r.state]}>{T.state[r.state]}</StatusPill>}>
      <p className="n-muted">
        {T.period(r.period.label)}
        {!arrived ? ` · ${T.daysWaiting(r.days_waiting)}` : ""}
        {r.link !== "open" ? ` · ${T.linkGone[r.link]}` : ""}
      </p>
      <h4>{T.weNeed}</h4>
      <AskedTables tables={r.tables} />
      <h4>{T.threeWays}</h4>
      <ol>
        <li>
          <FilePicker label={`${T.wayUpload}: ${r.source_name}`} button={T.upload}
            send={async (name, data) => {
              setProfile((await uploadSource(assessmentId, r.source_id, name, data)).profile);
              onUploaded();
            }} />
          <p className="n-muted">{T.stays}</p>
        </li>
        <li>
          <button type="button" className="n-btn" disabled={busy} onClick={onRelink}>
            {T.wayLink}
          </button>{" "}
          {r.link === "open" ? (
            <button type="button" className="n-btn" disabled={busy} onClick={onRevoke}>
              {T.withdraw}
            </button>
          ) : null}
        </li>
        <li>
          <button type="button" className="n-btn" disabled={busy || arrived} onClick={onRemind}>
            {T.wayRemind}
          </button>
        </li>
      </ol>
      {profile ? <ProfileView profile={profile} /> : null}
    </Panel>
  );
}
