import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import TrailPanel from "../a5trail/TrailPanel";
import { Button, EmptyState, PageFrame, Pill, day, type PillTone } from "../../design";
import StepperShell from "../b9/StepperShell";
import { getStudio } from "../b7/api";
import { useProjectTitle } from "../s1/useProjectTitle";
import * as api from "./api";
import type { Channel, Delivery, Kind, OutboxRow } from "./api";
import "./d1.css";

// V5 D1: /centre/build/p/:projectId/delivery. Design: docs/plan/v5-designs/D4-Delivery and BuildDelivery. Makers choose where an approved dashboard goes;
// someone else approves each channel; Go live switches them on and sends nothing. A channel that is not set up keeps its message in the outbox.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const WORDS: Record<Channel["status"], string> = { draft: "Draft", submitted: "Waiting for approval", approved: "Approved", stopped: "Stopped" };
const TONE: Record<Channel["status"], PillTone> = { draft: "draft", submitted: "open", approved: "signed", stopped: "restricted" };
const OUT_TONE: Record<OutboxRow["status"], PillTone> = { sent: "ok", held: "open", blocked: "failed" };
const OUT_WORDS: Record<OutboxRow["status"], string> = { sent: "Sent", held: "Kept here, not sent", blocked: "Not sent" };
const NEEDS_ADDRESS = (k: Kind, via: string) => k === "email" || (k === "alert" && via === "email");
type Run = (fn: () => Promise<unknown>) => void;

function When({ c }: { c: Channel }) {
  if (c.kind === "consume" || c.kind === "morning_note") return <>Shown in Signal Harbor{c.kind === "morning_note" ? ", in the Morning Note" : ""}</>;
  if (c.kind === "alert" && c.alert) return <>At once when the tile {c.alert.op === "lt" ? "falls below" : "goes above"} {c.alert.limit}</>;
  const f = { daily: "Every day", weekly: "Every week", monthly: "Every month", on_change: "When the figures change" }[c.when.freq] ?? c.when.freq;
  return <>{f}{c.when.freq === "on_change" ? "" : ` at ${c.when.at}`}</>;
}

function ChannelCard({ c, pid, busy, run, shown, show }: { c: Channel; pid: string; busy: boolean; run: Run; shown: boolean; show: () => void }) {
  const [reason, setReason] = useState("");
  const warn = !c.set_up && c.kind !== "consume" && c.kind !== "morning_note";
  return (
    <li className="d1-card" data-warn={warn || undefined}>
      <header>
        <h3>{c.title}</h3>
        <span className="d1-row"><Pill tone={TONE[c.status]}>{WORDS[c.status]}</Pill>{c.live && c.status === "approved" && <Pill tone="ok">Live</Pill>}</span>
      </header>
      <p>{c.label} · <When c={c} />{c.addresses?.length ? ` · to ${c.addresses.join(", ")}` : ""}</p>
      <p>Set up by {c.made_by_name}{c.approved_by_name ? `. Approved by ${c.approved_by_name}${c.approved_at ? `, ${day(c.approved_at)}` : ""}.` : "."}</p>
      {warn && <p role="status">{c.label} is not set up yet. Ask your administrator. Messages for it are kept in the outbox below.</p>}
      {c.sent_back && <p role="status">Sent back by {c.sent_back.by}: {c.sent_back.reason}</p>}
      <div className="d1-row">
        {c.preview && <Button onClick={show} aria-pressed={shown}>Preview</Button>}
        {c.can.submit && <Button variant="primary" disabled={busy} onClick={() => run(() => api.stepChannel(pid, c.id, "submit"))}>Send for approval</Button>}
        {c.can.approve && <Button variant="primary" disabled={busy} onClick={() => run(() => api.stepChannel(pid, c.id, "approve"))}>Approve</Button>}
        {c.can.stop && <Button disabled={busy} onClick={() => run(() => api.stepChannel(pid, c.id, "stop"))}>Stop</Button>}
      </div>
      {c.can.approve && <div className="d1-row">
        <label className="d1-note">Why send it back <textarea value={reason} rows={2} onChange={(e) => setReason(e.target.value)} /></label>
        <Button disabled={busy || !reason.trim()} onClick={() => run(async () => { await api.sendBack(pid, c.id, reason); setReason(""); })}>Send back</Button>
      </div>}
    </li>
  );
}

// D4: the side panel. What the council sees, for the channel picked (Slack first). The benchmark sentence comes from the business owner's review (b9_verify);
// when there is no review the panel shows the message the channel will really send, and nothing more.
function SidePreview({ d, ch }: { d: Delivery; ch: Channel | undefined }) {
  const [trail, setTrail] = useState(false);
  const f = d.figures, mail = d.channels.find((c) => c.kind === "email" && c.preview), tile = ch?.preview?.tile;
  if (!ch?.preview) return null;
  const lines = ch.preview.text.split(String.fromCharCode(10)).slice(1, -1);
  return (
    <aside className="d1-card d1-side" aria-label="What people see">
      <h3>What {ch.kind === "slack" ? "the council sees in Slack" : `people see in ${ch.label}`}</h3>
      <div className="d1-preview">
        <span className="d1-note">{ch.title} · Lumen, Signal Harbor · preview of the post</span>
        {f && <p><strong>{f.sentence}</strong></p>}
        {lines.map((l) => <p key={l}>{l}</p>)}
        <div className="d1-row"><Link className="ds-link" to="/centre/consume">Open the dashboard</Link>
          {tile && <button type="button" className="ds-link d1-linkbtn" aria-expanded={trail} onClick={() => setTrail(!trail)}>Where is this from?</button>}</div>
      </div>
      {trail && tile && <TrailPanel kind="tile" id={tile} onClose={() => setTrail(false)} />}
      {(f || mail) && <p className="d1-note"><strong>Email digest subject</strong><br />{f ? f.email_subject : mail?.preview?.subject}</p>}
      {f && <p className="d1-note"><strong>Morning Note line</strong><br />{f.note_line} <Link className="ds-link" to="/centre/consume">See the Morning Note</Link></p>}
      <span className="d1-note">Preview. Names are masked when a message leaves Signal Harbor.</span>
      <Link className="ds-link" to="/centre/operations#deliveries">See a Slack thread in Operations</Link>
    </aside>
  );
}

function AddChannel({ d, pid, busy, run }: { d: Delivery; pid: string; busy: boolean; run: Run }) {
  const [kind, setKind] = useState<Kind>("slack");
  const [dash, setDash] = useState(d.dashboards[0]?.id ?? "");
  const [freq, setFreq] = useState("daily");
  const [at, setAt] = useState("07:00");
  const [addr, setAddr] = useState("");
  const [tiles, setTiles] = useState<{ id: string; title: string }[]>([]);
  const [tile, setTile] = useState("");
  const [op, setOp] = useState<"lt" | "gt">("lt");
  const [limit, setLimit] = useState("");
  const [via, setVia] = useState("email");
  useEffect(() => {
    if (kind !== "alert" || !dash) return;
    let live = true;
    getStudio(pid, dash).then((s) => { if (!live) return; const t = s.tiles.filter((x) => x.state === "accepted"); setTiles(t); setTile(t[0]?.id ?? ""); }).catch(() => { if (live) setTiles([]); });
    return () => { live = false; };
  }, [kind, dash, pid]);
  const inside = kind === "consume" || kind === "morning_note";
  const body: api.NewChannel = { kind, dashboard_id: dash, ...(inside || kind === "alert" ? {} : { when: freq, at }),
    ...(NEEDS_ADDRESS(kind, via) ? { addresses: addr } : {}), ...(kind === "alert" ? { alert: { tile, op, limit, via } } : {}) };
  const ready = !!dash && (!NEEDS_ADDRESS(kind, via) || !!addr.trim()) && (kind !== "alert" || (!!tile && !!limit.trim()));
  return (
    <section className="d1-card" aria-label="Add a channel">
      <h3>Add a channel</h3>
      <div className="d1-row">{d.kinds.map((k) => <button key={k.kind} type="button" className={`ds-chip${kind === k.kind ? " ds-chip--active" : ""}`} aria-pressed={kind === k.kind} onClick={() => setKind(k.kind)}>{k.label}</button>)}</div>
      <div className="d1-form">
        <label>Dashboard <select value={dash} onChange={(e) => setDash(e.target.value)}>{d.dashboards.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
        {!inside && kind !== "alert" && <>
          <label>How often <select value={freq} onChange={(e) => setFreq(e.target.value)}><option value="daily">Every day</option><option value="weekly">Every week</option><option value="monthly">Every month</option><option value="on_change">When the figures change</option></select></label>
          {freq !== "on_change" && <label>At <input type="time" value={at} onChange={(e) => setAt(e.target.value)} /></label>}</>}
        {kind === "alert" && <>
          <label>Tile to watch <select value={tile} onChange={(e) => setTile(e.target.value)}>{tiles.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
          <label>Tell people when it <select value={op} onChange={(e) => setOp(e.target.value as "lt" | "gt")}><option value="lt">falls below</option><option value="gt">goes above</option></select></label>
          <label>The limit <input inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} /></label>
          <label>Send it by <select value={via} onChange={(e) => setVia(e.target.value)}><option value="email">Email</option><option value="slack">Slack</option><option value="teams">Microsoft Teams</option><option value="webhook">Outgoing webhook</option></select></label></>}
        {NEEDS_ADDRESS(kind, via) && <label>Email addresses, separated by commas <input value={addr} onChange={(e) => setAddr(e.target.value)} /></label>}
      </div>
      <div className="d1-row"><Button variant="primary" disabled={busy || !ready} onClick={() => run(() => api.createChannel(pid, body))}>Add as a draft</Button>
        <span className="d1-note">A draft is sent for approval to someone other than you.</span></div>
    </section>
  );
}

function Outbox({ rows, pid, canRetry, run, busy }: { rows: OutboxRow[]; pid: string; canRetry: boolean; run: Run; busy: boolean }) {
  if (!rows.length) return null;
  return (
    <section aria-label="Outbox"><h2>Outbox</h2>
      <p className="d1-note">Every message Lumen tried to send, and what happened to it. Nothing fails quietly.</p>
      <ul className="d1-list">{rows.map((r) => (
        <li key={r.id} className="d1-card" data-warn={r.status !== "sent" || undefined}>
          <header><h3>{r.title}</h3><Pill tone={OUT_TONE[r.status]}>{OUT_WORDS[r.status]}</Pill></header>
          <p>{day(r.at)} · {r.reason}</p>
          <div className="d1-preview"><strong>{r.subject}</strong><pre>{r.preview}</pre></div>
          {r.status !== "sent" && canRetry && <div className="d1-row"><Button disabled={busy} onClick={() => run(() => api.retry(pid, r.id))}>Send again</Button></div>}
        </li>))}</ul>
    </section>
  );
}

export default function DeliveryPage() {
  const { projectId = "" } = useParams();
  const title = useProjectTitle(projectId);
  const [d, setD] = useState<Delivery | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [sel, setSel] = useState("");
  const load = useCallback(() => api.getDelivery(projectId).then(setD).catch((e) => setError(plain(e))), [projectId]);
  useEffect(() => { void load(); }, [load]);
  const run: Run = (fn) => { setBusy(true); setError(""); fn().then(load).catch((e) => setError(plain(e))).finally(() => setBusy(false)); };
  // A stopped channel goes below the live ones, so a stopped "Slack channel" never sits above the one that replaced it.
  const rank = (c: Channel) => (c.status === "stopped" ? 1 : 0);
  const list = [...(d?.channels ?? [])].sort((a, b) => rank(a) - rank(b));
  const approved = list.filter((c) => c.status === "approved");
  const shown = list.find((c) => c.id === sel && c.preview) ?? list.find((c) => c.kind === "slack" && c.preview && c.status !== "stopped") ?? list.find((c) => c.preview);
  const p = encodeURIComponent(projectId);
  return (
    <StepperShell pid={projectId} current="dashboards">
      <PageFrame title="Choose where it goes"
        subline={`${title || "This project"}. Lumen sends the approved dashboard to each place below. Every channel is approved by someone other than you before it goes live.`}
        actions={d?.can.go_live ? <Button variant="primary" disabled={busy} onClick={() => run(async () => { await api.goLive(projectId); setNote("Live. Nothing was sent just now; the first message goes at each channel's next time."); })}>Go live</Button> : undefined}>
        {error && <p role="alert">{error}</p>}
        {note && <p role="status">{note}</p>}
        {!d ? <p>{error ? "" : "Loading…"}</p> : <>
          {!d.dashboards.length && <EmptyState title="No approved dashboard yet" lines={["Delivery sends a dashboard that someone else has approved."]} links={[{ label: "Open the dashboard studio", href: `/centre/build/p/${p}/studio` }]} />}
          {list.length ? <div className="d1-split"><div><p className="d1-note">{approved.length} of {list.length} channels approved.{d.live_at ? ` Live since ${day(d.live_at)}.` : ""}</p>
            <ul className="d1-list">{list.map((c) => <ChannelCard key={c.id} c={c} pid={projectId} busy={busy} run={run} shown={shown?.id === c.id} show={() => setSel(c.id)} />)}</ul></div>
            <SidePreview d={d} ch={shown} /></div>
            : d.dashboards.length > 0 && <p>No channels yet. Add the first one below.</p>}
          {d.can.make && d.dashboards.length > 0 && <AddChannel d={d} pid={projectId} busy={busy} run={run} />}
          <Outbox rows={d.outbox} pid={projectId} canRetry={d.can.make} run={run} busy={busy} />
          <p className="d1-note">Nothing is sent when you press Go live. Names and figures leave only through the gateway, and only to places your administrator has set up. {d.can.settings && <Link className="ds-link" to="/centre/build/delivery-settings">Set up Slack, Teams and email</Link>}</p>
          {d.live_at && <p><Link className="ds-link" to={`/centre/build/p/${p}/complete`}>See the project summary</Link></p>}
        </>}
      </PageFrame>
    </StepperShell>
  );
}
