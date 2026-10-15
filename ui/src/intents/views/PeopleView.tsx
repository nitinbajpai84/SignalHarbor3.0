import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, PageFrame } from "../../design";
import { getJoinLink, getRoom, newJoinLink, revokeSeat, type RoomView } from "../../modules/m1_intent/api";
import InviteDialog from "../InviteDialog";
import WhoHasNotActed from "../WhoHasNotActed";
import { copyText, DraftBox, InvitationCard, peopleCopy as t, postPeople, postPerson, RoleChange, say, StatusChip, usePeople, type PeopleData, type Row } from "../PeoplePanel";

const lt = {
  title: "Invite by link",
  linkLabel: "Join link",
  copyLink: "Copy link",
  newLink: "New link",
  newLinkNote: "A new link ends the old one",
  none: "No link yet. Make a link.",
  make: "Make a link",
  seats: "Seats",
  noSeats: "No seats. Seats open when you make a link.",
  seat: (n: number) => `Seat ${n}`,
  free: "free",
  revoked: "revoked",
  takeBack: "Take back",
  takeBackSeat: (n: number) => `Take back seat ${n}`,
  noWall: "Not available yet. A join link needs a wall, and this intent has none yet.",
  busy: "That could not be done. Try again.",
};
const vt = {
  title: "People and roles",
  crumb: "Intent Centre /",
  all: "All",
  filters: ["invited", "joined", "contributed", "confirmed", "declined", "removed"] as const,
  cols: { name: "Name", role: "Role", status: "Status", by: "Invited by", on: "Invited on", last: "Last activity" },
  started: "Started this intent",
  byLink: "the join link",
  history: "History",
  showHistory: "Show history",
  hideHistory: "Hide history",
  noHistory: "Nothing has changed yet.",
  drawerRole: "Role history",
  how: "How they came in",
  reminders: "Reminders drafted",
  none: "None",
  close: "Close",
  existence: "You can see that these changes happened. The reasons are the organiser's.",
};

/** The organiser's join link and seat list: the wall's invite panel, reshaped. The wall's own routes stay the truth. */
function LinkPanel({ sessionId }: { sessionId: string | null }) {
  const [room, setRoom] = useState<RoomView | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(() => {
    if (!sessionId) return;
    getRoom(sessionId).then((r) => { setRoom(r); if (r.state !== "closed") getJoinLink(sessionId).then((l) => setLink(l.join_path), () => setLink(null)); }, () => undefined);
  }, [sessionId]);
  useEffect(load, [load]);
  if (!sessionId) return <Panel title={lt.title}><p className="n-muted">{lt.noWall}</p></Panel>;
  const url = link ? `${window.location.origin}${link}` : "";
  const fresh = () => newJoinLink(sessionId).then((l) => { setLink(l.join_path); setNote(null); load(); }, () => setNote(lt.busy));
  const revoke = (n: number) => revokeSeat(sessionId, n).then(setRoom, () => setNote(lt.busy));
  return (
    <Panel title={lt.title}>
      {link ? (
        <p style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap" }}>
          <input type="text" readOnly aria-label={lt.linkLabel} value={url} onFocus={(e) => e.currentTarget.select()} style={{ flex: "1 1 200px", minHeight: 44, minWidth: 0 }} />
          <Button onClick={() => void copyText(url).then(setNote)}>{lt.copyLink}</Button>
        </p>
      ) : <p className="n-muted">{lt.none}</p>}
      <p style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center", flexWrap: "wrap" }}>
        <Button onClick={() => void fresh()}>{link ? lt.newLink : lt.make}</Button>
        {link ? <span className="n-muted">{lt.newLinkNote}</span> : null}
      </p>
      {note ? <p role="status">{note}</p> : null}
      <h3 style={{ margin: 0, fontSize: 14 }}>{lt.seats}</h3>
      {!room || room.seats.length === 0 ? <p className="n-muted">{lt.noSeats}</p> : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 4 }}>
          {room.seats.map((s) => (
            <li key={s.n} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--ds-s1)" }}>
              <span>{lt.seat(s.n)}: {s.state === "taken" ? s.name : s.state === "free" ? lt.free : lt.revoked}</span>
              {s.state === "taken" && room.state !== "closed" ? <Button aria-label={lt.takeBackSeat(s.n)} onClick={() => void revoke(s.n)}>{lt.takeBack}</Button> : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** The person drawer: how they came in, dates, reminders, the decline reason, role history, and the organiser's buttons. */
function Drawer({ intentId, row, data, reload, onClose, onReminders }: {
  intentId: string; row: Row; data: PeopleData; reload: () => void; onClose: () => void; onReminders: (r: NonNullable<PeopleData["reminders"]>) => void;
}) {
  const [mode, setMode] = useState<"role" | "remove" | null>(null);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const done = () => { setMode(null); setReason(""); reload(); };
  const live = data.intent.state !== "closed" && data.intent.state !== "cancelled";
  const gone = row.status === "declined" || row.status === "removed";
  const remove = () => postPerson(intentId, row.person_id, "remove", { reason }).then(done, (e) => setProblem(say(e)));
  const again = () => postPeople(intentId, { people: [{ person_id: row.person_id, role: row.role }] }).then(done, (e) => setProblem(say(e)));
  const remind = () => postPeople(intentId, { remind: [row.person_id] }).then((r) => { onReminders(r.reminders ?? []); reload(); }, (e) => setProblem(say(e)));
  return (
    <Panel title={row.name} actions={<Button onClick={onClose}>{vt.close}</Button>}>
      <p style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap", alignItems: "center" }}><Chip>{t.role[row.role]}</Chip><StatusChip status={row.status} /></p>
      <p>{vt.how}: {row.via ? t.via[row.via] : ""}{row.invited_on ? `, ${row.invited_on}` : ""}{row.joined_on ? `. Joined ${row.joined_on}.` : ""}</p>
      {row.declined ? <p className="ds-warn">{t.declinedOn(row.declined.on, row.declined.reason)}</p> : null}
      {row.removed ? <p className="ds-warn">{t.removedOn(row.removed.on, row.removed.reason)}</p> : null}
      <p>{vt.reminders}: {row.reminders?.length ? row.reminders.join(", ") : vt.none}</p>
      {row.role_history?.length ? (
        <>
          <h3 style={{ margin: 0, fontSize: 14 }}>{vt.drawerRole}</h3>
          <ul>{row.role_history.map((h, i) => <li key={i}>{h.at}: {t.role[h.from]} to {t.role[h.to]}{h.reason ? `. ${h.reason}` : ""}</li>)}</ul>
        </>
      ) : null}
      {live ? (
        mode === "role" ? <RoleChange intentId={intentId} row={row} roles={data.roles_allowed} onClose={() => setMode(null)} onDone={done} /> :
        mode === "remove" ? (
          <div style={{ display: "grid", gap: "var(--ds-s1)" }}>
            <p>{t.removeAsk(row.name)}</p>
            <textarea aria-label={t.reasonLabel} placeholder={t.reasonLabel} value={reason} onChange={(e) => setReason(e.target.value)} style={{ minHeight: 80 }} />
            <div style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap" }}>
              <Button variant="primary" disabled={!reason.trim()} onClick={() => void remove()}>{t.removeConfirm}</Button>
              <Button onClick={() => setMode(null)}>{t.cancel}</Button>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap" }}>
            {row.role !== "organiser" && !gone ? <Button onClick={() => setMode("role")}>{t.roleMenu}</Button> : null}
            {row.role !== "organiser" ? <Button disabled={row.role === "affected" || gone} onClick={() => void remind()}>{t.remind}</Button> : null}
            {row.role !== "organiser" && !gone ? <Button onClick={() => setMode("remove")}>{t.remove}</Button> : null}
            {gone && data.can_invite ? <Button onClick={() => void again()}>{t.inviteAgain}</Button> : null}
          </div>
        )
      ) : null}
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
    </Panel>
  );
}

/** Screen B of spec 06: /centre/intent/<id>/people. */
export default function PeopleView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const [params, setParams] = useSearchParams();
  const { state, data, message, reload } = usePeople(intentId);
  const [filter, setFilter] = useState<string>("all");
  const [dialog, setDialog] = useState(false);
  const [history, setHistory] = useState(false);
  const [reminders, setReminders] = useState<NonNullable<PeopleData["reminders"]>>([]);
  const focus = params.get("focus");

  const crumbs = <><Link to="/centre/intent" className="ds-link">{vt.crumb}</Link> {data?.intent.title ?? ""}</>;
  if (state !== "populated" || !data) return <PageFrame title={vt.title} crumbs={crumbs}><ScreenState state={state} message={message} onRetry={reload} /></PageFrame>;

  const org = data.level === "organiser";
  const c = data.counts;
  const rows = data.people.filter((p) => filter === "all" || p.status === filter);
  const open = org ? data.people.find((p) => p.person_id === focus) : undefined;
  const live = data.intent.state !== "closed" && data.intent.state !== "cancelled";
  const chips = org ? vt.filters : vt.filters.filter((s) => s !== "declined" && s !== "removed");
  const countOf = (s: string) => data.people.filter((p) => p.status === s).length;
  const aside = org ? (
    <>
      <LinkPanel sessionId={data.wall_session_id} />
      <DraftBox title={t.draftEmail} draft={data.drafts?.invite ?? null} />
      {data.drafts?.fyi ? <DraftBox title={t.draftEmail} draft={data.drafts.fyi} /> : null}
      {reminders.map((r) => <DraftBox key={r.person_id} title={`${t.reminderTitle}: ${r.name}`} draft={r} />)}
    </>
  ) : undefined;

  return (
    <PageFrame
      title={vt.title}
      subline={c ? `${t.count(c.people)}. ${t.summary(c)}` : undefined}
      crumbs={crumbs}
      actions={org && live && data.can_invite ? <Button variant="primary" onClick={() => setDialog(true)}>{t.invite}</Button> : undefined}
      aside={aside}
    >
      {data.invitation ? <InvitationCard intentId={intentId} onAnswered={reload} onDeclined={reload} /> : null}
      {data.gone.length ? <p className="ds-warn">{t.seatGone(data.gone.map((r) => t.role[r] ?? r))}</p> : null}
      {c ? (
        <div style={{ display: "flex", gap: "var(--ds-s1)", flexWrap: "wrap" }} role="group" aria-label="Filter by status">
          <Chip tone={filter === "all" ? "active" : "default"} onClick={() => setFilter("all")}>{vt.all}</Chip>
          {chips.map((s) => <Chip key={s} tone={filter === s ? "active" : "default"} onClick={() => setFilter(s)}>{`${t.status[s]} ${countOf(s)}`}</Chip>)}
        </div>
      ) : null}
      {open ? <Drawer intentId={intentId} row={open} data={data} reload={reload} onReminders={setReminders} onClose={() => { params.delete("focus"); setParams(params); }} /> : null}
      <Panel title={t.title}>
        {rows.length === 0 ? <p className="n-muted">{data.people.length === 0 ? t.noOne : t.emptyOthers}</p> : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--ds-s2)" }}>
            {rows.map((p) => (
              <li key={p.person_id} className="ds-card" style={{ padding: "var(--ds-s2)", display: "grid", gap: 4 }}>
                <span style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center", flexWrap: "wrap" }}>
                  {org ? <Link to={`?focus=${encodeURIComponent(p.person_id)}`} className="ds-link"><strong>{p.name}</strong></Link> : <strong>{p.name}</strong>}
                  <Chip>{t.role[p.role] ?? p.role}</Chip>
                  <StatusChip status={p.status} />
                </span>
                {org ? <span className="n-muted">{p.role === "organiser" ? vt.started : `${vt.cols.by} ${p.invited_by ?? vt.byLink}`}{p.invited_on ? `, ${p.invited_on}` : ""}. {vt.cols.last}: {p.last_activity ?? "Not available yet"}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      {org && live ? <WhoHasNotActed intentId={intentId} /> : null}
      {org || data.level === "admin" ? (
        <Panel title={vt.history} actions={<Button onClick={() => setHistory(!history)}>{history ? vt.hideHistory : vt.showHistory}</Button>}>
          {history || window.innerWidth > 700 ? (
            data.history.length === 0 ? <p className="n-muted">{vt.noHistory}</p> : (
              <>
                {org ? null : <p className="n-muted">{vt.existence}</p>}
                <ul>{data.history.map((h, i) => <li key={i}>{h.at}: {h.kind === "joined" || h.kind === "declined" ? `${h.person ?? ""} ${t.history[h.kind]}` : `${h.by ? `${h.by} ` : ""}${t.history[h.kind] ?? h.kind} ${h.person ?? ""}`}{h.to ? ` (${t.role[h.to]})` : ""}{h.reason ? `. ${h.reason}` : ""}</li>)}</ul>
              </>
            )
          ) : null}
        </Panel>
      ) : null}
      {dialog ? <InviteDialog intentId={intentId} data={data} onClose={() => setDialog(false)} onDone={() => { setDialog(false); reload(); }} /> : null}
    </PageFrame>
  );
}

