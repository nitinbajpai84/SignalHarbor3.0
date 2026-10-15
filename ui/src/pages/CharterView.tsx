import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useSession } from "../useSession";
import { useLoad } from "../components/useLoad";
import { Button, EmptyState, PageFrame, Pill, SideCard, Signature, StatCard, StatGrid, Strip, VersionList } from "../design";
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
  type CharterProblem,
  type SentToApprover,
} from "../modules/m1_intent/api";
import { formatDay, soThatSentence } from "../modules/m1_intent/CharterPaper";
import GraphPicture from "../modules/m1_intent/charter/GraphPicture";
import RolesPanel from "../modules/m1_intent/charter/RolesPanel";
import ShareCharter from "../modules/m1_intent/charter/ShareCharter";
import { m1Charter as T } from "../modules/m1_intent/copy";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const wallHref = (id: string) => `/centre/intent/wall/${encodeURIComponent(id)}`;
const lines = (c: Charter | null): Record<string, string> => Object.fromEntries((c?.problems ?? []).map((p) => [p.id, p.so_that ?? ""]));
// the reader sees plain words, not a module number (the shared copy still says "module 2")
const handedOn = (...a: Parameters<typeof T.handedOn>) => T.handedOn(...a).replace("What goes to module 2:", "Handed on:");
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : T.busy);
const COPY = {
  crumbs: "Intent Centre / Charter",
  back: "Back to the wall",
  tookPart: "Took part",
  notes: "Cards",
  later: "Parked for later",
  signature: "Signature",
  loadingTitle: "Getting the charter ready",
  loadingLine: "Reading the shelves and the signatures.",
  slowLine: "This is taking longer than it should. The server may be busy.",
  errorTitle: "The charter could not be loaded",
  refusedTitle: "This charter is not open to you",
  retry: "Try again",
  inRoom: "in the room",
  sponsorSigns: "The sponsor signs the charter. You will see it here as soon as they have.",
  waitingOn: (who: string) => `Waiting for ${who} to sign.`,
  viaApprover: "by the approver's link",
  raised: (n: number) => `Raised in ${n} ${n === 1 ? "card" : "cards"}.`, // the tile below says "Cards": one word for one thing
};

/** A signed version names who signed it (the signing record), not who drafted it. */
const signedBy = (c: Charter, v: Charter["versions"][number]) =>
  v.status === "signed" && v.version === c.version && c.signing.signers.length > 0 ? c.signing.signers.map((s) => s.name).join(", ") : v.created_by;

/** The charter: drafted from the shelves, then signed in the room by the sponsor or sent to the named approver. */
export default function CharterView() {
  const { sessionId = "" } = useParams();
  const { state, data, message, retry } = useLoad<CharterPage>(() => getCharter(sessionId), `charter:${sessionId}`);
  const c = data?.charter ?? null;
  // a request that hangs (the server restarting) would leave the loading line up for good: after eight seconds offer a retry
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    setSlow(false);
    if (state !== "loading") return;
    const t = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(t);
  }, [state]);
  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={COPY.crumbs}
        title={T.title}
        subline={T.sub}
        actions={
          <>
            {c ? <Pill tone={c.status === "signed" ? "signed" : c.status === "returned" ? "late" : "draft"}>{cap(T.statusLabel[c.status])}</Pill> : null}
            <Link className="ds-btn" to={wallHref(sessionId)}>{COPY.back}</Link>
          </>
        }
        aside={c ? (
          <>
            <RolesPanel sessionId={sessionId} />
            {c.versions.length > 0 ? (
              <SideCard title={T.versionsTitle}>
                <VersionList versions={c.versions.map((v) => ({ v: v.version, what: cap(T.statusLabel[v.status]) + (v.comment ? ` · ${T.versionComment(v.comment)}` : ""), by: signedBy(c, v), at: when(v.created_at) }))} />
              </SideCard>
            ) : null}
          </>
        ) : undefined}
      >
        {state === "loading" ? (
          <div role="status">
            <EmptyState title={COPY.loadingTitle} lines={[slow ? COPY.slowLine : COPY.loadingLine]} />
            {slow ? <div><Button onClick={retry}>{COPY.retry}</Button></div> : null}
          </div>
        )
          : state === "refused" ? <EmptyState title={COPY.refusedTitle} lines={message ? [message] : []} />
          : state === "error" ? (
            <div className="ds-card ds-empty" role="alert">
              <strong className="ds-empty__title">{COPY.errorTitle}</strong>
              {message ? <p>{message}</p> : null}
              <div><Button onClick={retry}>{COPY.retry}</Button></div>
            </div>
          )
          : data ? <CharterBody sessionId={sessionId} first={data} /> : null}
      </PageFrame>
    </div>
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
  const messages = (
    <>
      {notice ? <p role="status" className="ds-muted" style={{ margin: 0 }}>{notice}</p> : null}
      {problem ? <p role="alert" className="ds-warn" style={{ margin: 0 }}>{problem}</p> : null}
    </>
  );

  if (c === null) {
    return page.can_draft ? (
      <div className="ds-card ds-empty">
        <strong className="ds-empty__title">{T.makeDraft}</strong>
        <p>{T.makeDraftHelp}</p>
        <div><Button variant="primary" disabled={busy} onClick={() => void run(() => makeCharterDraft(sessionId, true))}>{T.makeDraft}</Button></div>
        {messages}
      </div>
    ) : (
      <div role="status"><EmptyState title={page.no_result ? T.noResult : T.notYet} lines={[]} /></div>
    );
  }

  const changed = c.problems.some((p) => (values[p.id] ?? "") !== (p.so_that ?? ""));
  const edit = c.editable;
  // four lists, each with its heading: problems to solve now, pain points, what to track for the future, levers. A charter with no lists is one list of problems.
  const sections = c.lists?.length
    ? c.lists.map((l) => ({ kind: l.kind, heading: l.heading, items: c.problems.filter((p) => (p.kind ?? "intent") === l.kind) }))
    : [{ kind: "intent", heading: T.title, items: c.problems }];
  const sg = c.signing;
  const f = c.footer;
  const waiting = Math.max(0, sg.needed - sg.signed);
  return (
    <>
      {c.problems.length === 0 ? <EmptyState title={T.nothingTicked} lines={[]} /> : sections.map((sec) => (
        <Strip key={sec.kind} label={sec.heading}>
          {sec.items.length === 0 ? <p className="ds-muted" style={{ margin: 0 }}>{T.noneRaised}</p> : sec.items.map((p) => (
            <Line key={p.id} p={p} signed={c.status === "signed"} edit={edit} value={values[p.id] ?? ""} columns={c.template.columns}
              onChange={(text) => setValues((v) => ({ ...v, [p.id]: text }))}
              onConfirm={() => void run(() => confirmSoThat(sessionId, [p.id]), T.saved)}
              onPriority={(priority) => void run(() => saveTiedPriority(sessionId, p.id, priority), T.saved)} />
          ))}
        </Strip>
      ))}
      {edit ? (
        <div>
          <Button disabled={busy || !changed} onClick={() => void run(() => saveSoThat(sessionId, Object.fromEntries(c.problems.filter((p) => (values[p.id] ?? "") !== (p.so_that ?? "")).map((p) => [p.id, values[p.id] ?? ""]))), T.saved)}>
            {T.saveSoThat}
          </Button>
        </div>
      ) : null}
      {c.later.length > 0 || (c.alone ?? []).length > 0 ? (
        <Strip label={COPY.later} tone="amber">
          <div className="ds-card ds-side">
            {c.later.length > 0 ? (
              <>
                <strong className="ds-side__title">{T.laterTitle}</strong>
                <ul>{c.later.map((l) => <li key={l.id}>{l.title}</li>)}</ul>
              </>
            ) : null}
            {(c.alone ?? []).length > 0 ? (
              <>
                <strong className="ds-side__title">{T.leftForLater((c.alone ?? []).length)}</strong>
                <ul>{(c.alone ?? []).map((n, i) => <li key={i}>{n.text ?? T.leftAnonymous}{n.author_name ? ` (${T.by(n.author_name)})` : ""}</li>)}</ul>
              </>
            ) : null}
          </div>
        </Strip>
      ) : null}
      <StatGrid cols={3}>
        <StatCard label={COPY.tookPart} value={f.participants} note={formatDay(f.date)} />
        <StatCard label={COPY.notes} value={f.notes} />
        <StatCard label={COPY.later} value={f.later} />
      </StatGrid>
      {c.graph ? <GraphPicture graph={c.graph} /> : null}
      <Strip label={COPY.signature}>
        <p className="ds-muted" style={{ margin: 0 }}>{T.signers(sg.signed, sg.needed)}</p>
        {sg.signers.map((s, i) => <Signature key={i} state="signed" by={s.name} at={`${when(s.at)} · ${s.how === "approver" ? COPY.viaApprover : COPY.inRoom}`} />)}
        {Array.from({ length: waiting }, (_, i) => <Signature key={`w${i}`} state="waiting" by={i === 0 && c.approver.name ? c.approver.name : undefined} />)}
        <div className="ds-card ds-side">
          <SignActions c={c} page={page} link={link} busy={busy} run={run} sessionId={sessionId} send={send} copyLink={copyLink} />
          {!page.organiser && !sg.can_sign && c.status !== "signed" ? <p>{T.readOnlyGuest}</p> : null}
          {messages}
        </div>
      </Strip>
    </>
  );
}

function Line({ p, signed, edit, value, columns, onChange, onConfirm, onPriority }: {
  p: CharterProblem; signed: boolean; edit: boolean; value: string; columns: string[];
  onChange: (text: string) => void; onConfirm: () => void; onPriority: (priority: string) => void;
}) {
  const note = signed ? null : p.so_that_note; // "Draft from North..." or "Ask the room..."
  const tied = p.tied_options ?? [];
  return (
    <div className="ds-card ds-side">
      <div className="ds-side__head">
        <strong className="ds-side__title">{p.title}</strong>
        {columns.includes("priority") ? <Pill tone={p.priority_label ? "ok" : "draft"}>{p.priority_label ?? (p.tie ? T.tiedPill : T.noPriority)}</Pill> : null}
      </div>
      {columns.includes("purpose") ? (
        edit ? (
          <label className="ds-soft" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
            {T.soThatField}
            <input type="text" aria-label={T.soThatLabel(p.title)} className="ds-btn" style={{ justifyContent: "flex-start", textAlign: "left" }} value={value} placeholder={T.soThatNone} onChange={(e) => onChange(e.target.value)} />
          </label>
        ) : <p>{p.so_that ? soThatSentence(p.so_that) : T.soThatNone}</p>
      ) : null}
      {columns.includes("notes") ? <p className="ds-muted">{COPY.raised(p.note_count)}</p> : null}
      {(p.details ?? []).map((x) => <p key={x.label}>{x.label}: {x.values.join(", ")}</p>)}
      {note ? <p className="ds-muted">{note}</p> : null}
      {edit && p.so_that_draft ? <div><Button aria-label={T.useThisLineLabel(p.title)} onClick={onConfirm}>{T.useThisLine}</Button></div> : null}
      {p.tie ? <p className="ds-warn">{p.tie}</p> : null}
      {edit && p.tie && tied.length > 0 ? (
        <select aria-label={T.chooseTied(p.title)} className="ds-btn" defaultValue="" onChange={(e) => e.target.value && onPriority(e.target.value)}>
          <option value="">{T.chooseTiedNone}</option>
          {tied.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      ) : null}
      {p.so_that_proposal ? <p className="ds-muted">{T.soThatProposal(p.so_that_proposal)}</p> : null}
    </div>
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
  const { user } = useSession();
  const canSign = sg.can_sign && (user?.roles ?? []).includes("sponsor"); // only the sponsor signs; the organiser sees the state
  const unchecked = c.problems.some((p) => p.so_that_draft === true); // North's drafts the organiser has not yet used or edited
  if (c.status === "signed") {
    return (
      <>
        <p role="status">{T.readOnly}</p>
        <p>{handedOn(c.problems, c.later.length)}</p>
        <ShareCharter sessionId={sessionId} organiser={page.organiser} />
      </>
    );
  }
  if (c.status === "returned") {
    return (
      <>
        {c.returned ? <p role="status">{T.returnedBy(c.returned.by, c.returned.comment)}</p> : null}
        {page.can_draft ? <div><Button variant="primary" disabled={busy} onClick={() => void run(() => makeCharterDraft(sessionId, true))}>{T.makeNew}</Button></div> : null}
      </>
    );
  }
  if (c.status === "awaiting_approver") {
    const a = c.approver;
    return (
      <>
        <p role="status">{a.link === "expired" ? T.linkExpired : a.link === "used" ? T.linkUsed : a.expires_at ? T.linkOut(a.name, when(a.expires_at)) : null}</p>
        {link ? (
          <>
            <strong className="ds-side__title">{T.linkTitle}</strong>
            <p>{T.linkHelp}</p>
            <label className="ds-soft" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
              {T.linkField}
              <input type="text" readOnly className="ds-btn" style={{ justifyContent: "flex-start" }} value={`${window.location.origin}${link.link_path}`} onFocus={(e) => e.currentTarget.select()} />
            </label>
            <div><Button onClick={() => void copyLink()}>{T.copy}</Button></div>
          </>
        ) : null}
        {page.organiser ? <div><Button disabled={busy} onClick={() => void run(() => withdrawCharterLink(sessionId))}>{T.withdraw}</Button></div> : null}
      </>
    );
  }
  return (
    <>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {canSign ? <Button variant="primary" disabled={busy || unchecked} onClick={() => void run(() => signCharter(sessionId))}>{T.signNow}</Button> : null}
        {page.organiser && sg.signed === 0 && c.approver.name ? <Button disabled={busy} onClick={() => void send()}>{T.sendUp}</Button> : null}
      </div>
      {canSign && unchecked ? <p role="status">{T.checkLinesFirst}</p> : null}
      {canSign ? <p>{T.signNowHelp}</p> : sg.i_signed ? <p>{T.alreadySigned}</p> : <p>{c.approver.name ? COPY.waitingOn(c.approver.name) : COPY.sponsorSigns}</p>}
      {page.organiser && sg.signed === 0 ? <p>{c.approver.name ? T.sendUpHelp(c.approver.name) : T.noApprover}</p> : null}
    </>
  );
}
