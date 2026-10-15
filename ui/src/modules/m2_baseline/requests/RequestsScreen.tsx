import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { useLoad } from "../../../components/useLoad";
import { answerInMeeting, getOutstanding, newLink, remindOwner, reopenRequest, sendRequests, withdrawLink, type EmailText, type Outstanding, type RequestRow } from "../api";
import BaselineSteps from "../BaselineSteps";
import { m2, m2Req as T } from "../copy";

const TONE: Record<string, PillTone> = { sent: "info", opened: "warning", answered: "success", no_reply: "danger", in_meeting: "muted" };
const OWES = ["sent", "opened", "no_reply"];

/** What the organiser copies and sends: a link (shown once) with the email around it, or a reminder with no link. */
interface Outgoing {
  key: string;
  title: string;
  help: string;
  linkPath: string | null;
  address?: string | null; // the full address from the server: the same one its email text carries
  email: EmailText;
}

const fullLink = (o: { address?: string | null; linkPath: string | null }) => o.address ?? (o.linkPath ? `${window.location.origin}${o.linkPath}` : null);
async function toClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Requests to owners and who still owes answers (M2-06, M2-29; deck slide 6). */
export default function RequestsScreen() {
  const { baselineId = "" } = useParams();
  const first = useLoad<Outstanding>(() => getOutstanding(baselineId), `requests-${baselineId}`, (d) => d.summary.asked === 0 && d.not_yet_asked.length === 0);
  const [fresh, setFresh] = useState<Outstanding | null>(null);
  const [out, setOut] = useState<Outgoing[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const view = fresh ?? first.data;

  async function act(id: string, run: () => Promise<Outgoing[]>) {
    setBusy(id);
    setProblem(null);
    try {
      const made = await run();
      setOut((o) => [...made, ...o.filter((x) => !made.some((m) => m.key === x.key))]);
      setFresh(await getOutstanding(baselineId));
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : T.retry);
    } finally {
      setBusy(null);
    }
  }

  const make = () =>
    act("send", async () => {
      const r = await sendRequests(baselineId);
      return r.sent.filter((s) => s.link_path && s.email).map((s) => ({ key: s.id, title: T.linkTitle(s.owner_name), help: T.linkHelp, linkPath: s.link_path, address: s.address, email: s.email as EmailText }));
    });
  const remind = (r: RequestRow) =>
    act(r.id, async () => {
      const x = await remindOwner(baselineId, r.id);
      return [{ key: `remind-${r.id}`, title: T.reminderTitle(r.owner_name), help: T.reminderHelp, linkPath: null, email: x.email }];
    });
  const relink = (r: RequestRow) =>
    act(r.id, async () => {
      const x = await newLink(baselineId, r.id);
      return [{ key: r.id, title: T.linkTitle(r.owner_name), help: T.linkHelp, linkPath: x.link_path, address: x.address, email: x.email }];
    });
  const reopen = (r: RequestRow) =>
    act(r.id, async () => {
      const x = await reopenRequest(baselineId, r.id);
      return [{ key: r.id, title: T.linkTitle(r.owner_name), help: T.linkHelp, linkPath: x.link_path, address: x.address, email: x.email }];
    });
  const plain = (r: RequestRow, run: () => Promise<unknown>) => act(r.id, async () => (await run(), []));

  return (
    <>
      <PageHead title={T.title} eyebrow={T.eyebrow} crumbs={[{ label: m2.title, to: "/modules/m2_baseline" }, { label: T.title }]} sub={T.intro} />
      <BaselineSteps baselineId={baselineId} signed={view?.signed === true} />
      <p className="n-e1-def-note">{T.noEmail}</p>
      <ScreenState state={first.state} message={first.state === "empty" ? T.nobodyToAsk : first.state === "loading" ? T.loading : first.message} onRetry={first.retry}>
        {view ? (
          <>
            <fieldset disabled={view.signed === true} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <Summary view={view} onSend={() => void make()} busy={busy === "send"} />
            </fieldset>
            {problem ? (
              <p role="alert" className="state state-error">
                {problem}
              </p>
            ) : null}
            {out.map((o) => (
              <OutgoingPanel key={o.key} o={o} onDone={() => setOut((all) => all.filter((x) => x.key !== o.key))} />
            ))}
            {view.alerts.length > 0 ? (
              <Panel title={T.tellsYou} eyebrow={T.nira}>
                <ul className="m1-list">
                  {view.alerts.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </Panel>
            ) : null}
            <Panel title={T.title} actions={<StatusPill tone="info">{T.summary(view.summary)}</StatusPill>}>
              <fieldset disabled={view.signed === true} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <div className="n-table-wrap">
                <table className="n-table">
                  <thead>
                    <tr>
                      <th scope="col">Who</th>
                      <th scope="col">Where it stands</th>
                      <th scope="col">Chasing</th>
                      <th scope="col">What you can do</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.requests.map((r) => (
                      <Row key={r.id} r={r} baselineId={baselineId} busy={busy === r.id} onRemind={() => void remind(r)} onRelink={() => void relink(r)} onReopen={() => void reopen(r)}
                        onWithdraw={() => void plain(r, () => withdrawLink(baselineId, r.id))} onMeeting={() => void plain(r, () => answerInMeeting(baselineId, r.id))} />
                    ))}
                  </tbody>
                </table>
              </div>
              </fieldset>
            </Panel>
            <Panel title={T.waitingTitle}>
              {view.waiting_on.length === 0 ? (
                <p className="n-muted">{T.waitingNobody}</p>
              ) : (
                <ul className="m1-list">
                  {view.waiting_on.map((w) => (
                    <li key={w.kpi_id}>{T.waitingOn(w.kpi_name, w.waiting_on)}</li>
                  ))}
                </ul>
              )}
            </Panel>
          </>
        ) : null}
      </ScreenState>
    </>
  );
}

function Summary({ view, onSend, busy }: { view: Outstanding; onSend: () => void; busy: boolean }) {
  const waiting = view.not_yet_asked.length > 0;
  return (
    <Panel>
      <div className="m1-actions">
        <button type="button" className="n-btn primary" disabled={busy || !waiting} onClick={onSend}>
          {busy ? T.sending : T.sendButton}
        </button>
        <span className="n-muted">{waiting ? T.notYetAsked(view.not_yet_asked) : T.summary(view.summary)}</span>
      </div>
    </Panel>
  );
}

function Row({ r, baselineId, busy, onRemind, onRelink, onReopen, onWithdraw, onMeeting }: {
  r: RequestRow; baselineId: string; busy: boolean; onRemind: () => void; onRelink: () => void; onReopen: () => void; onWithdraw: () => void; onMeeting: () => void;
}) {
  const owes = OWES.includes(r.state);
  const label = r.state === "no_reply" ? T.stateFor("no_reply", r.days_waiting) : T.states[r.state];
  return (
    <tr>
      <td>
        <strong>{r.owner_name}</strong>
        <div className="n-e1-def-note">
          {r.role} · {T.measures(r.kpis.length)}: {r.kpis.map((k) => k.name).join(", ")}
        </div>
      </td>
      <td>
        <StatusPill tone={TONE[r.state]}>{label}</StatusPill>
        <div className="n-e1-def-note">{r.state === "answered" || r.state === "in_meeting" ? (r.meeting ? T.meetingBy(r.meeting.by) : T.answeredOf(r.answered_kpis, r.kpis.length)) : T.sentOn(r.sent_at)}</div>
        {owes ? <div className="n-e1-def-note">{r.link === "open" ? T.linkUntil(r.expires_at) : T.linkGone[r.link]}</div> : null}
      </td>
      <td>
        {r.reminders.length > 0 ? <div>{T.reminded(r.reminders.length, r.reminders.at(-1) ?? r.sent_at)}</div> : null}
        {owes && r.remind_due ? <StatusPill tone="warning">{T.reminderDue}</StatusPill> : null}
        {owes && !r.remind_due && r.next_reminder_on ? <div className="n-e1-def-note">{T.nextReminder(r.next_reminder_on)}</div> : null}
        {r.nira ? <div className="n-e1-def-note">{T.nira}: {r.nira}</div> : null}
      </td>
      <td>
        <div className="m1-actions">
          {owes ? (
            <button type="button" className="n-btn" disabled={busy} onClick={onRemind}>
              {T.remind}
            </button>
          ) : null}
          {owes && r.link === "open" ? (
            <button type="button" className="n-btn" disabled={busy} onClick={onWithdraw}>
              {T.withdraw}
            </button>
          ) : null}
          {r.state !== "answered" ? (
            <button type="button" className="n-btn" disabled={busy} onClick={onRelink}>
              {T.newLink}
            </button>
          ) : (
            <button type="button" className="n-btn" disabled={busy} title={T.reopenHelp} onClick={onReopen}>
              {T.reopen}
            </button>
          )}
          {owes ? (
            <button type="button" className="n-btn" disabled={busy} onClick={onMeeting}>
              {T.meeting}
            </button>
          ) : null}
          {r.state === "in_meeting" ? (
            <Link className="n-btn" to={`/modules/m2_baseline/requests/${encodeURIComponent(baselineId)}/meeting?owner=${encodeURIComponent(r.owner_name)}`}>
              {T.meetingOpen}
            </Link>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function OutgoingPanel({ o, onDone }: { o: Outgoing; onDone: () => void }) {
  const link = fullLink(o);
  const body = link ? o.email.body.replace("{link}", link) : o.email.body;
  const [copied, setCopied] = useState("");
  const copy = async (what: string, text: string) => setCopied((await toClipboard(text)) ? what : "");
  return (
    <Panel title={o.title}>
      <p className="n-e1-def-note">{o.help}</p>
      {link ? (
        <label>
          {T.linkLabel}
          <input type="text" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
        </label>
      ) : null}
      <label>
        {T.emailTitle}
        <textarea readOnly rows={9} value={`Subject: ${o.email.subject}\n\n${body}`} onFocus={(e) => e.currentTarget.select()} />
      </label>
      <div className="m1-actions">
        <button type="button" className="n-btn primary" onClick={() => void copy("email", `Subject: ${o.email.subject}\n\n${body}`)}>
          {copied === "email" ? T.copied : T.copy}
        </button>
        <button type="button" className="n-btn" onClick={onDone}>
          {T.close}
        </button>
      </div>
    </Panel>
  );
}
