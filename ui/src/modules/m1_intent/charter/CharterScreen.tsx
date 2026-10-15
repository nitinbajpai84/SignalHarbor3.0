import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { SummaryLink } from "../summary/SummaryScreen";
import {
  confirmSoThat,
  getCharter,
  makeCharterDraft,
  saveSoThat,
  saveTiedPriority,
  sendCharterUp,
  signCharter,
  withdrawCharterLink,
  type Charter,
  type CharterPage,
  type SentToApprover,
} from "../api";
import CharterPaper from "../CharterPaper";
import { m1Charter as T, m1Companion, m1Look } from "../copy";
import NiraDock from "../NiraDock"; // M1-UI2
import { useLoad } from "../useLoad";
import GraphPicture from "./GraphPicture";
import ShareCharter from "./ShareCharter";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const sessionHref = (id: string) => `/modules/m1_intent/sessions/${encodeURIComponent(id)}`;
const lines = (c: Charter | null): Record<string, string> => Object.fromEntries((c?.problems ?? []).map((p) => [p.id, p.so_that ?? ""]));
const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : T.busy);

/** The charter (deck slide 11): drafted from the ticked problems, then signed in the room or sent to the named approver. */
export default function CharterScreen() {
  const { sessionId = "" } = useParams();
  const { state, data, message, retry } = useLoad<CharterPage>(() => getCharter(sessionId), `charter:${sessionId}`);
  return (
    <>
      <PageHead
        title={T.title}
        sub={T.sub}
        crumbs={[{ label: m1Look.crumbModules, to: "/" }, { label: m1Look.crumbSessions, to: "/modules/m1_intent" }, { label: T.crumb }]}
        actions={
          <Link className="n-btn" to={sessionHref(sessionId)}>
            {T.back}
          </Link>
        }
      />
      <ScreenState state={state} onRetry={retry} message={message}>
        {data ? <CharterBody sessionId={sessionId} first={data} /> : null}
        {data ? <SummaryLink sessionId={sessionId} /> : null}
      </ScreenState>
      <NiraDock sessionId={sessionId} stage="charter" actions={[{ label: m1Companion.actions.toTogether, to: `/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/together` }]} />
    </>
  );
}

function CharterBody({ sessionId, first }: { sessionId: string; first: CharterPage }) {
  const [page, setPage] = useState<CharterPage>(first);
  const [link, setLink] = useState<SentToApprover | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>(() => lines(first.charter));
  const c = page.charter;

  // the purpose lines are the person's to edit: reset the fields only when a different version arrives
  useEffect(() => {
    setValues(lines(c));
  }, [c?.version, c?.status, c?.problems.length]);

  async function run(work: () => Promise<CharterPage>, done?: string) {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      setPage(await work());
      if (done) setNotice(done);
    } catch (e) {
      setProblem(problemText(e));
    } finally {
      setBusy(false);
    }
  }

  const send = () =>
    run(async () => {
      const sent = await sendCharterUp(sessionId);
      setLink(sent);
      return sent;
    });
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${link?.link_path ?? ""}`);
      setNotice(T.copied);
    } catch {
      setNotice(T.copyFailed);
    }
  };

  if (c === null) {
    return (
      <Panel title={T.title} className="m1-charter">
        {page.can_draft ? (
          <>
            <p>{T.makeDraftHelp}</p>
            <button type="button" className="n-btn primary" disabled={busy} onClick={() => void run(() => makeCharterDraft(sessionId, true))}>
              {T.makeDraft}
            </button>
          </>
        ) : (
          <p className="state n-muted" role="status">
            {page.no_result ? T.noResult : T.notYet}
          </p>
        )}
        {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      </Panel>
    );
  }

  const changed = c.problems.some((p) => (values[p.id] ?? "") !== (p.so_that ?? ""));
  const sg = c.signing;
  return (
    <>
      <CharterPaper
        doc={c}
        status={c.status}
        edit={c.editable ? { values, onChange: (id, text) => setValues((v) => ({ ...v, [id]: text })), onPriority: (id, priority) => void run(() => saveTiedPriority(sessionId, id, priority), T.saved), onConfirm: (id) => void run(() => confirmSoThat(sessionId, [id]), T.saved) } : undefined}
      >
        {c.editable ? (
          <div className="m1-actions">
            <button type="button" className="n-btn" disabled={busy || !changed} onClick={() => void run(() => saveSoThat(sessionId, Object.fromEntries(c.problems.filter((p) => (values[p.id] ?? "") !== (p.so_that ?? "")).map((p) => [p.id, values[p.id] ?? ""]))), T.saved)}>
              {T.saveSoThat}
            </button>
          </div>
        ) : null}
        <div className="m1-sign" style={{ marginTop: 16, display: "grid", gap: 12 }}>
          <p className="n-e1-def-name">{T.signers(sg.signed, sg.needed)}</p>
          {sg.signers.map((s, i) => (
            <p key={i} className="n-e1-def-note">
              {T.signedBy(s.name, when(s.at), s.how)}
            </p>
          ))}
          <SignActions c={c} page={page} link={link} busy={busy} run={run} sessionId={sessionId} send={send} copyLink={copyLink} />
        </div>
        {!page.organiser && !sg.can_sign ? <p className="n-e1-def-note">{T.readOnlyGuest}</p> : null}
        {notice ? <p role="status" className="state n-muted">{notice}</p> : null}
        {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      </CharterPaper>
      {c.graph ? <GraphPicture graph={c.graph} /> : null}
      <Panel title={T.versionsTitle} tight>
        <ul>
          {c.versions.map((v) => (
            <li key={v.version}>
              {T.versionRow(v.version, T.statusLabel[v.status], v.created_by, when(v.created_at))}
              {v.comment ? <div className="n-e1-def-note">{T.versionComment(v.comment)}</div> : null}
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}

interface ActionProps {
  c: Charter;
  page: CharterPage;
  link: SentToApprover | null;
  busy: boolean;
  sessionId: string;
  run: (work: () => Promise<CharterPage>, done?: string) => Promise<void>;
  send: () => Promise<void>;
  copyLink: () => Promise<void>;
}

function SignActions({ c, page, link, busy, sessionId, run, send, copyLink }: ActionProps) {
  const sg = c.signing;
  const unchecked = c.problems.some((p) => p.so_that_draft === true); // North's drafts the organiser has not yet used or edited
  if (c.status === "signed") {
    return (
      <>
        <p role="status" className="state n-muted">{T.readOnly}</p>
        <p className="n-e1-def-note">{T.handedOn(c.problems, c.later.length)}</p>
        <ShareCharter sessionId={sessionId} organiser={page.organiser} />
      </>
    );
  }
  if (c.status === "returned") {
    return (
      <>
        {c.returned ? <p role="status" className="state n-muted">{T.returnedBy(c.returned.by, c.returned.comment)}</p> : null}
        {page.can_draft ? (
          <button type="button" className="n-btn primary" disabled={busy} onClick={() => void run(() => makeCharterDraft(sessionId, true))}>
            {T.makeNew}
          </button>
        ) : null}
      </>
    );
  }
  if (c.status === "awaiting_approver") {
    const a = c.approver;
    return (
      <>
        <p role="status" className="state n-muted">
          {a.link === "expired" ? T.linkExpired : a.link === "used" ? T.linkUsed : a.expires_at ? T.linkOut(a.name, when(a.expires_at)) : null}
        </p>
        {link ? (
          <div>
            <h3>{T.linkTitle}</h3>
            <p className="n-muted">{T.linkHelp}</p>
            <label>
              {T.linkField}
              <input style={{ width: "100%" }} type="text" readOnly value={`${window.location.origin}${link.link_path}`} onFocus={(e) => e.currentTarget.select()} />
            </label>
            <div className="m1-actions">
              <button type="button" className="n-btn" onClick={() => void copyLink()}>
                {T.copy}
              </button>
            </div>
          </div>
        ) : null}
        {page.organiser ? (
          <button type="button" className="n-btn" disabled={busy} onClick={() => void run(() => withdrawCharterLink(sessionId))}>
            {T.withdraw}
          </button>
        ) : null}
      </>
    );
  }
  return (
    <>
      <div className="m1-actions">
        {sg.can_sign ? (
          <button type="button" className="n-btn primary" disabled={busy || unchecked} onClick={() => void run(() => signCharter(sessionId))}>
            {T.signNow}
          </button>
        ) : null}
        {page.organiser && sg.signed === 0 && c.approver.name ? (
          <button type="button" className="n-btn" disabled={busy} onClick={() => void send()}>
            {T.sendUp}
          </button>
        ) : null}
      </div>
      {sg.can_sign && unchecked ? <p role="status" className="n-e1-def-note">{T.checkLinesFirst}</p> : null}
      {sg.can_sign ? <p className="n-e1-def-note">{T.signNowHelp}</p> : sg.i_signed ? <p className="n-e1-def-note">{T.alreadySigned}</p> : <p className="n-e1-def-note">{T.noSignRole}</p>}
      {page.organiser && sg.signed === 0 ? <p className="n-e1-def-note">{c.approver.name ? T.sendUpHelp(c.approver.name) : T.noApprover}</p> : null}
    </>
  );
}
