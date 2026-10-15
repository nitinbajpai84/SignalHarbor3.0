import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { Button, Chip, Pill, type PillTone } from "../design";
import InviteDialog from "./InviteDialog";

/** Spec 06. Screen A (this panel), Screen D (the invitation card) and what the people view and the dialog share: the copy, the types, the load. */
export const peopleCopy = {
  title: "People",
  count: (n: number) => `People (${n})`,
  summary: (c: { joined: number; contributed: number; confirmed: number }) => `${c.joined} joined, ${c.contributed} contributed, ${c.confirmed} confirmed`,
  phoneLine: (c: { people: number; joined: number; contributed: number }) => `${c.people} people, ${c.joined} joined, ${c.contributed} contributed`,
  emptyOrganiser: "Just you so far. Invite people to start.",
  emptyOthers: "Nobody else has been added yet.",
  noOne: "Nobody has been added.",
  invite: "Invite",
  askAdd: "Ask the organiser to add someone",
  askPlaceholder: "Who should be added, and why?",
  askSend: "Send the note",
  askDone: "The organiser has your note.",
  openPeople: "Open people",
  waiting: (names: string[], last: string | null) => `North is waiting for ${names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`}.${last ? ` Last reminder ${last}.` : ""}`,
  nobody: "Nobody is holding this up.",
  remindThem: "Remind them",
  remind: "Remind",
  draftEmail: "Draft the email",
  nothingToDraft: "Nothing to draft.",
  copy: "Copy",
  copied: "Copied.",
  copyFailed: "That could not be copied. Select the text and copy it yourself.",
  suggestion: "A suggestion from North. Nothing is sent.",
  draftNote: "A draft from Nira. Copy it and send it from your own mail.",
  reminderTitle: "Reminder drafts",
  roleMenu: "Change role",
  reasonLabel: "Why? One line.",
  save: "Save",
  cancel: "Cancel",
  remove: "Remove",
  removeAsk: (name: string) => `Remove ${name}? Their cards stay in the record.`,
  removeConfirm: "Remove and keep in record",
  inviteAgain: "Invite again",
  declinedOn: (d: string, why: string | null) => `Declined ${d}${why ? `: ${why}` : ""}`,
  removedOn: (d: string, why: string | null) => `Removed ${d}${why ? `: ${why}` : ""}`,
  seatGone: (roles: string[]) => `${roles.join(" and ")} declined. Name another person before this moves on.`,
  rangeNote: (low: number, high: number, have: number) => `Brainstorm works best with ${low} to ${high} invited people. You have ${have}.`,
  failed: "That could not be saved. Try again.",
  loadFailed: "The people could not be loaded. Try again.",
  role: { organiser: "Organiser", sponsor: "Sponsor", decider: "Decider", participant: "Participant", affected: "Affected", observer: "Observer", adviser: "Adviser", reporter: "Reporter", owner: "Owner" } as Record<string, string>,
  status: { invited: "Invited", joined: "Joined", contributed: "Contributed", confirmed: "Confirmed", declined: "Declined", removed: "Removed" } as Record<string, string>,
  via: { picked: "Picked", link: "Join link", area: "Told through an area" } as Record<string, string>,
  history: {
    invited: "invited", joined: "joined", declined: "declined", role_changed: "changed the role of", removed: "removed", reminded: "drafted a reminder for", asked: "left a note about",
  } as Record<string, string>,
  // Screen D
  invitedBy: (who: string, title: string) => `${who} has invited you to ${title}`,
  noPurpose: "The organiser has not written a purpose yet.",
  ends: (d: string) => `This ends on ${d}.`,
  minutes: (n: number) => `It should take about ${n} minutes.`,
  accept: "Accept",
  decline: "Decline",
  reasonPlaceholder: "Why not? A short line helps the organiser plan.",
  sendReason: "Send my reason",
  thanks: (who: string) => `Thank you. ${who} has been told.`,
  askRole: "Ask for a different role",
  askRolePlaceholder: "Which role would suit you, and why?",
  sendRequest: "Send request",
  requestSent: "Your request is with the organiser.",
  closedNote: "This intent has closed. You can read the outcome.",
  cancelledNote: "This intent was cancelled.",
  closedOn: (d: string) => `Closed on ${d}.`,
  cancelledOn: (d: string) => `Cancelled on ${d}.`,
  readOutcome: "Read what came out",
  notFound: "We could not find that.",
};
const t = peopleCopy;

export interface Row {
  person_id: string; name: string; role: string; status?: string; via?: string; invited_by?: string | null; invited_on?: string | null; last_activity?: string | null;
  required?: boolean; joined_on?: string | null; declined?: { on: string; reason: string | null } | null; removed?: { on: string; reason: string | null; by: string | null } | null;
  role_history?: { from: string; to: string; by: string | null; at: string; reason: string | null }[]; reminders?: string[]; seat?: { session_id: string; n: number } | null;
}
export interface Counts { people: number; joined: number; contributed: number; confirmed: number; invited: number; named?: number; affected: number; not_answered: number; declined?: number; removed?: number }
export interface Invitation { inviter: string; title: string | null; purpose: string | null; ask: string | null; note: string | null; ends: string | null; minutes: number; reason_required: boolean; closed: boolean; closed_note: string | null }
export interface Draft { subject: string; body: string }
export interface PeopleData {
  intent: { id: string; type: string; title: string | null; state: string; areas: { id: string; name: string }[]; area_ids: string[]; ends: string | null };
  level: "organiser" | "member" | "affected" | "admin" | "area";
  me: { person_id: string; role: string; status: string } | null;
  people: Row[]; counts: Counts | null; roles_allowed: string[]; can_invite: boolean; can_ask: boolean;
  range: { low: number; high: number; have: number } | null;
  waiting: { names: string[]; ids: string[]; last_reminder: string | null } | null; gone: string[];
  drafts: { invite: Draft | null; fyi: Draft | null } | null; wall_session_id: string | null;
  history: { at: string | null; kind: string; by: string | null; person: string | null; role: string | null; to: string | null; reason: string | null }[];
  invitation: Invitation | null;
  reminders?: (Draft & { person_id: string; name: string })[];
}

const base = (id: string) => `/api/intents/${encodeURIComponent(id)}/people`;
const origin = () => `?origin=${encodeURIComponent(window.location.origin)}`;
export const getPeople = (id: string) => apiGet<PeopleData>(`${base(id)}${origin()}`);
export const postPeople = (id: string, body: unknown) => apiSend<PeopleData>("POST", `${base(id)}${origin()}`, body);
export const postPerson = (id: string, person: string, act: "answer" | "role" | "remove", body: unknown) =>
  apiSend<Partial<PeopleData>>("POST", `${base(id)}/${encodeURIComponent(person)}/${act}`, body);
export const say = (e: unknown) => (e instanceof ApiError && e.message ? e.message : t.failed);

/** The one load every part of the screen shares; `reload` asks again after a change. */
export function usePeople(intentId: string) {
  const l = useLoad(() => getPeople(intentId), intentId);
  return { ...l, reload: l.retry };
}

const tone = (s: string): PillTone => (({ invited: "open", joined: "ok", contributed: "signed", confirmed: "signed", declined: "failed", removed: "restricted" }) as Record<string, PillTone>)[s] ?? "draft";

export function StatusChip({ status }: { status?: string }) {
  return status ? <Pill tone={tone(status)}>{t.status[status] ?? status}</Pill> : null;
}

export async function copyText(text: string): Promise<string> {
  try {
    await navigator.clipboard.writeText(text);
    return t.copied;
  } catch {
    return t.copyFailed;
  }
}

/** A drafted email in a copy box. Nothing is sent. */
export function DraftBox({ title, draft, note = t.draftNote }: { title: string; draft: Draft | null; note?: string }) {
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <Panel title={title}>
      {draft ? (
        <>
          <p className="n-muted">{note}</p>
          <p><strong>{draft.subject}</strong></p>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, font: "inherit", overflowWrap: "anywhere" }}>{draft.body}</pre>
          <p style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center" }}>
            <Button onClick={() => void copyText(`${draft.subject}\n\n${draft.body}`).then(setMsg)}>{t.copy}</Button>
            {msg ? <span role="status">{msg}</span> : null}
          </p>
        </>
      ) : <p className="n-muted">{t.nothingToDraft}</p>}
    </Panel>
  );
}

/** "Change role": the roles this type allows, and one line of reason where the spec asks for it. The server checks the same. */
export function RoleChange({ intentId, row, roles, onDone, onClose }: { intentId: string; row: Row; roles: string[]; onDone: () => void; onClose: () => void }) {
  const [role, setRole] = useState(row.role);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const options = Array.from(new Set([...roles, ...(row.status === "joined" || row.status === "contributed" || row.status === "confirmed" ? ["organiser"] : [])]));
  const save = () => postPerson(intentId, row.person_id, "role", { role, reason }).then(onDone, (e) => setProblem(say(e)));
  return (
    <div role="group" aria-label={t.roleMenu} style={{ display: "grid", gap: "var(--ds-s1)" }}>
      <label>{t.roleMenu}{" "}
        <select value={role} onChange={(e) => setRole(e.target.value)} style={{ minHeight: 44 }}>
          {options.map((r) => <option key={r} value={r}>{t.role[r]}</option>)}
        </select>
      </label>
      <label>{t.reasonLabel}
        <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: "100%", boxSizing: "border-box", minHeight: 44 }} />
      </label>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      <div style={{ display: "flex", gap: "var(--ds-s1)" }}>
        <Button variant="primary" disabled={role === row.role} onClick={() => void save()}>{t.save}</Button>
        <Button onClick={onClose}>{t.cancel}</Button>
      </div>
    </div>
  );
}

function usePhone(): boolean {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 700px)") : null;
  const [phone, setPhone] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const on = () => setPhone(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, [q]);
  return phone;
}

/** Screen A: the people panel on every intent screen. At 1280 a column; at 390 one line that opens the people view. */
export default function PeoplePanel({ intentId }: { intentId: string }) {
  const { state, data, message, reload } = usePeople(intentId);
  const phone = usePhone();
  const [dialog, setDialog] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [reminders, setReminders] = useState<NonNullable<PeopleData["reminders"]>>([]);
  const [email, setEmail] = useState(false);
  const [ask, setAsk] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const remind = useCallback((ids: string[]) => postPeople(intentId, { remind: ids }).then((r) => { setReminders(r.reminders ?? []); reload(); }, (e) => setNote(say(e))), [intentId, reload]);
  const sendAsk = () => postPeople(intentId, { ask }).then(() => { setAsk(null); setNote(t.askDone); }, (e) => setNote(say(e)));

  if (state !== "populated" || !data) return <ScreenState state={state} message={message} onRetry={reload} />;
  const org = data.level === "organiser";
  const c = data.counts;
  const here = data.people.filter((p) => p.status !== "removed" && p.status !== "declined");
  const live = !isClosed(data.intent.state);
  if (phone) {
    return (
      <p><Link to={`/centre/intent/${intentId}/people`} className="ds-link">{c ? t.phoneLine(c) : t.openPeople}</Link></p>
    );
  }
  return (
    // spec 06: a 320 px column on the right at 1280 (the screen's own grid is the orchestrator's: this block right-aligns itself)
    <div className="n-people-col" style={{ width: "100%", maxWidth: 320, justifySelf: "end", boxSizing: "border-box" }}>
    <Panel
      title={c ? t.count(c.people) : t.title}
      actions={org && live && data.can_invite ? <Button variant="primary" onClick={() => setDialog(true)}>{t.invite}</Button> : undefined}
    >
      {c ? <p className="n-muted">{t.summary(c)}</p> : null}
      {here.every((p) => p.role === "organiser") ? <p className="n-muted">{org ? t.emptyOrganiser : t.emptyOthers}</p> : null}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--ds-s1)" }}>
        {here.map((p) => (
          <li key={p.person_id} style={{ display: "grid", gap: 4 }}>
            <span style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center", flexWrap: "wrap" }}>
              {org ? <Link to={`/centre/intent/${intentId}/people?focus=${encodeURIComponent(p.person_id)}`} className="ds-link">{p.name}</Link> : <span>{p.name}</span>}
              {org && p.role !== "organiser" && live ? <Chip onClick={() => setEditing(editing === p.person_id ? null : p.person_id)}>{t.role[p.role] ?? p.role}</Chip> : <Chip>{t.role[p.role] ?? p.role}</Chip>}
              <StatusChip status={p.status} />
            </span>
            {editing === p.person_id ? <RoleChange intentId={intentId} row={p} roles={data.roles_allowed} onClose={() => setEditing(null)} onDone={() => { setEditing(null); reload(); }} /> : null}
          </li>
        ))}
      </ul>
      {data.gone.length ? <p className="ds-warn">{t.seatGone(data.gone.map((r) => t.role[r] ?? r))}</p> : null}
      {org && live && data.waiting ? (
        <p>
          {data.waiting.names.length ? t.waiting(data.waiting.names, data.waiting.last_reminder) : t.nobody}{" "}
          {data.waiting.names.length ? <Button onClick={() => void remind(data.waiting?.ids ?? [])}>{t.remindThem}</Button> : null}
        </p>
      ) : null}
      {data.can_ask && live ? (
        ask === null ? <p><Button onClick={() => setAsk("")}>{t.askAdd}</Button></p> : (
          <p style={{ display: "grid", gap: "var(--ds-s1)" }}>
            <input type="text" aria-label={t.askAdd} placeholder={t.askPlaceholder} value={ask} onChange={(e) => setAsk(e.target.value)} />
            <Button disabled={!ask.trim()} onClick={() => void sendAsk()}>{t.askSend}</Button>
          </p>
        )
      ) : null}
      {note ? <p role="status">{note}</p> : null}
      <p style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap", alignItems: "center" }}>
        <Link to={`/centre/intent/${intentId}/people`} className="ds-link">{t.openPeople}</Link>
        {org && live ? <Button disabled={!data.drafts?.invite && !data.drafts?.fyi} onClick={() => setEmail(!email)}>{t.draftEmail}</Button> : null}
      </p>
      {org && email ? <><DraftBox title={t.draftEmail} draft={data.drafts?.invite ?? null} />{data.drafts?.fyi ? <DraftBox title={t.draftEmail} draft={data.drafts.fyi} /> : null}</> : null}
      {reminders.map((r) => <DraftBox key={r.person_id} title={`${t.reminderTitle}: ${r.name}`} draft={r} />)}
      {dialog ? <InviteDialog intentId={intentId} data={data} onClose={() => setDialog(false)} onDone={() => { setDialog(false); reload(); }} /> : null}
    </Panel>
    </div>
  );
}

export const isClosed = (state?: string | null) => state === "closed" || state === "cancelled";

/** W2F2: what a closed or cancelled intent says instead of any invitation, join or note: one line with the date and the outcome. */
export function ClosedLine({ intentId, state }: { intentId: string; state: string }) {
  type Head = { closed_on: string | null; cancel: { reason: string } | null; outcome: { lines: { label: string; value: string }[] } };
  const { data } = useLoad(() => apiGet<Head>(`/api/intents/${encodeURIComponent(intentId)}/closure`), `closed:${intentId}`);
  const cancelled = state === "cancelled";
  const when = data?.closed_on;
  const first = data?.outcome?.lines?.[0];
  const what = cancelled ? data?.cancel?.reason : first ? `${first.label}: ${first.value}` : null;
  return (
    <section className="ds-card" role="status" style={{ padding: "var(--ds-s3)", display: "grid", gap: "var(--ds-s1)" }}>
      <p style={{ margin: 0 }}><strong>{when ? (cancelled ? t.cancelledOn(when) : t.closedOn(when)) : cancelled ? t.cancelledNote : t.closedNote}</strong>{what ? ` ${what}` : ""}</p>
      {data ? <p style={{ margin: 0 }}><Link to={`/centre/intent/${intentId}/close`} className="ds-link">{t.readOutcome}</Link></p> : null}
    </section>
  );
}

/** Screen D: what an invited person sees at /centre/intent/<id>?view=invitation. `onAnswered` runs after Accept, so the screen can show the stage view. */
export function InvitationCard({ intentId, onAnswered, onDeclined }: { intentId: string; onAnswered?: () => void; onDeclined?: () => void }) {
  const { state, data, message, reload } = usePeople(intentId);
  const [reason, setReason] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // mounted above a stage view (no onAnswered): stay silent unless there is an invitation to show
  if (state !== "populated" || !data) return onAnswered ? <ScreenState state={state} message={message ?? t.notFound} onRetry={reload} /> : null;
  if (isClosed(data.intent.state)) return <ClosedLine intentId={intentId} state={data.intent.state} />; // closed: no invitation, one line
  const inv = data.invitation, me = data.me;
  if (!inv || !me) return null; // not invited: the stage view carries on without a card
  const send = (body: unknown, after: () => void) => postPerson(intentId, me.person_id, "answer", body).then(after, (e) => setProblem(say(e)));
  const answered = me.status === "declined" || done === "declined";
  return (
    <section className="ds-card" style={{ maxWidth: 640, margin: "0 auto", padding: "var(--ds-s4)", display: "grid", gap: "var(--ds-s3)" }}>
      <h1 style={{ margin: 0, fontSize: 22 }}>{t.invitedBy(inv.inviter, inv.title ?? "")}</h1>
      <p>{inv.purpose ?? t.noPurpose}</p>
      {inv.ask ? <p>{inv.ask}</p> : null}
      {inv.note ? <p className="n-muted">{inv.note}</p> : null}
      <p className="n-muted">{[inv.ends ? t.ends(inv.ends) : null, t.minutes(inv.minutes)].filter(Boolean).join(" ")}</p>
      {answered ? <p role="status">{t.thanks(inv.inviter)}</p> : (
        <>
          <div style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap" }}>
            <Button variant="primary" disabled={me.status !== "invited"} onClick={() => void send({ action: "accept" }, onAnswered ?? (() => window.location.reload()))}>{t.accept}</Button>
            <Button disabled={me.status !== "invited"} onClick={() => setReason(reason === null ? "" : null)}>{t.decline}</Button>
            <Button onClick={() => setRole(role === null ? "" : null)}>{t.askRole}</Button>
          </div>
          {reason !== null ? (
            <div style={{ display: "grid", gap: "var(--ds-s1)" }}>
              <textarea aria-label={t.reasonPlaceholder} placeholder={t.reasonPlaceholder} value={reason} onChange={(e) => setReason(e.target.value)} style={{ minHeight: 80 }} />
              <Button disabled={inv.reason_required && !reason.trim()} onClick={() => void send({ action: "decline", reason }, () => { setDone("declined"); reload(); onDeclined?.(); })}>{t.sendReason}</Button>
            </div>
          ) : null}
          {role !== null ? (
            <div style={{ display: "grid", gap: "var(--ds-s1)" }}>
              <input type="text" aria-label={t.askRolePlaceholder} placeholder={t.askRolePlaceholder} value={role} onChange={(e) => setRole(e.target.value)} />
              <Button disabled={!role.trim()} onClick={() => void send({ action: "ask_role", note: role }, () => { setRole(null); setDone("asked"); })}>{t.sendRequest}</Button>
            </div>
          ) : null}
          {done === "asked" ? <p role="status">{t.requestSent}</p> : null}
        </>
      )}
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
    </section>
  );
}
