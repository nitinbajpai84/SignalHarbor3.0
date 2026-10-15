import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiGet, apiSend, ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, PageFrame, Pill, StatGrid } from "../../design";
import { useLoad } from "../../components/useLoad";
import { shareCopy as t } from "./shareCopy";
import { shareStyle } from "./shareStyle";

// Screen A of spec 11: the organiser's share panel. Everything shown comes from GET /api/intents/{id}/share.

export interface ShareEntry { id: string; kind: string; who: string; made_by: string; made_on: string; ends_on: string; state: string; opens: number }
export interface SharePerson { id: string; name: string; role: string; department: string; status: "pickable" | "shared" | "in_intent" }
export interface SharePanelData {
  intent: { id: string; title: string; state: string };
  guard: string | null;
  company: string;
  never: string[];
  areas: { area: string; head_count: number }[];
  people: SharePerson[];
  entries: ShareEntry[];
  counts: { people: number; areas: number; links: number; opened: number; of: number | null; notes: number; unread: number; live: number };
  opens: { name: string; first: string; last: string; times: number; through: string }[];
  notes: { id: string; name: string; at: string; text: string; read: boolean }[];
  link?: { url: string; expires_at: string } | null;
}
interface Pending { kind: "person" | "area" | "link"; target: string | null; label: string }

const when = (iso: string) => `${new Date(iso).toLocaleString("en-GB", { timeZone: "UTC", dateStyle: "medium", timeStyle: "short" })} UTC`;
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { timeZone: "UTC", dateStyle: "medium" });
const sameRow = (a: Pending, b: Pending) => a.kind === b.kind && a.target === b.target;

export default function ShareView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const { state, data, message, retry } = useLoad<SharePanelData>(() => apiGet(`/api/intents/${intentId}/share`), `share-${intentId}`);
  const [panel, setPanel] = useState<SharePanelData | null>(null);
  useEffect(() => setPanel(data), [data]);
  return (
    <>
      <style>{shareStyle}</style>
      <ScreenState state={state} message={message ?? (state === "error" ? t.loadError : undefined)} onRetry={retry}>
        {panel ? <Body intentId={intentId} panel={panel} setPanel={setPanel} /> : null}
      </ScreenState>
    </>
  );
}

function Body({ intentId, panel, setPanel }: { intentId: string; panel: SharePanelData; setPanel: (p: SharePanelData) => void }) {
  const [pending, setPending] = useState<Pending[]>([]);
  const [expiry, setExpiry] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [link, setLink] = useState<SharePanelData["link"]>(null);
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const canShare = panel.guard === null || panel.intent.state === "cancelled";
  const draft = panel.intent.state === "draft";
  const has = (p: Pending) => pending.some((x) => sameRow(x, p));
  const toggle = (p: Pending) => setPending((cur) => (has(p) ? cur.filter((x) => !sameRow(x, p)) : [...cur, p]));
  const pickable = panel.people.filter((p) => p.status === "pickable" || p.status === "shared");
  const live = panel.entries.filter((e) => e.state === "live");

  async function act<T>(fn: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setProblem("");
    try {
      return await fn();
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : t.actionError);
      return null;
    } finally {
      setBusy(false);
    }
  }
  async function share() {
    const out = await act(() => apiSend<SharePanelData>("POST", `/api/intents/${intentId}/share`, { targets: pending.map(({ kind, target }) => ({ kind, target })), expires_at: expiry }));
    if (!out) return;
    setPanel(out);
    setLink(out.link ?? null);
    setPending([]);
  }
  async function withdraw(which: string) {
    setConfirm(null);
    const out = await act(() => apiSend<SharePanelData>("DELETE", `/api/intents/${intentId}/share/${which}`));
    if (out) setPanel(out);
  }
  async function markRead(id: string) {
    const out = await act(() => apiSend<SharePanelData>("POST", `/api/intents/${intentId}/share`, { mark_read: id }));
    if (out) setPanel(out);
  }
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link?.url ?? "");
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const c = panel.counts;
  const madeAny = c.people + c.areas + c.links > 0;
  const preview = t.previewLines[panel.intent.state];

  return (
    <PageFrame title={t.title(panel.intent.title)} subline={<Pill tone="open">{t.states[panel.intent.state] ?? panel.intent.state}</Pill>}>
      {panel.guard ? <p role="status" className="sv-banner">{panel.guard}</p> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      {link ? (
        <Panel title={t.linkResultTitle}>
          <p className="sv-link">{link.url}</p>
          <p className="sv-note">{t.linkOnce}</p>
          <div className="sv-row">
            <Button variant="primary" onClick={copyLink}>{copied ? t.copied : t.copy}</Button>
            <Button onClick={() => { setLink(null); setCopied(false); }}>{t.done}</Button>
          </div>
        </Panel>
      ) : null}
      <div className="sv-grid">
        <div className="sv-col">
          <Panel title={t.shareWith}>
            <h3>{t.people}</h3>
            {pickable.length === 0 ? <p className="n-muted">{t.peopleNone}</p> : null}
            {panel.people.length > 0 ? (
              <ul className="sv-list sv-pick" aria-label={t.people}>
                {panel.people.map((p) => {
                  const row: Pending = { kind: "person", target: p.id, label: p.name };
                  const locked = p.status === "in_intent";
                  return (
                    <li key={p.id} className="sv-row">
                      <label className="sv-grow">
                        <input type="checkbox" disabled={locked || p.status === "shared" || !canShare} checked={has(row) || p.status === "shared"} onChange={() => toggle(row)} />{" "}
                        <strong>{p.name}</strong> <span className="n-muted">{[p.role, p.department].filter(Boolean).join(", ")}</span>
                      </label>
                      {locked ? <span className="n-muted">{t.inIntent}</span> : p.status === "shared" ? <span className="n-muted">{t.alreadyShared}</span> : null}
                    </li>
                  );
                })}
              </ul>
            ) : null}
            <h3>{t.areas}</h3>
            {panel.areas.length === 0 ? <p className="n-muted">{t.areasNone}</p> : (
              <ul className="sv-list" aria-label={t.areas}>
                {panel.areas.map((a) => {
                  const row: Pending = { kind: "area", target: a.area, label: a.area };
                  return (
                    <li key={a.area} className="sv-row">
                      <label className="sv-grow">
                        <input type="checkbox" disabled={!canShare} checked={has(row)} onChange={() => toggle(row)} /> <strong>{a.area}</strong> <span className="n-muted">{t.headCount(a.head_count)}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="sv-row">
              <Button disabled={!canShare || has({ kind: "link", target: null, label: "" })} onClick={() => toggle({ kind: "link", target: null, label: t.linkRow })}>{t.makeLink}</Button>
              <span className="sv-note">{t.linkLine(panel.company)}</span>
            </div>
            <h3>{t.pending}</h3>
            {pending.length === 0 ? <p className="n-muted">{t.nothingChosen}</p> : (
              <ul className="sv-list">
                {pending.map((p) => (
                  <li key={`${p.kind}-${p.target}`} className="sv-row">
                    <span className="sv-grow">{p.label}</span>
                    <Button aria-label={`${t.remove} ${p.label}`} onClick={() => toggle(p)}>{t.remove}</Button>
                  </li>
                ))}
              </ul>
            )}
            <label>
              <span>{t.expiry}</span>
              <input className="sv-field" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
            </label>
            {expiry === "" ? <p className="sv-note">{t.expiryNeeded}</p> : null}
            <div className="sv-row">
              <Button variant="primary" disabled={busy || draft || pending.length === 0 || expiry === ""} onClick={share}>{t.share}</Button>
            </div>
          </Panel>
          <Panel title={t.previewTitle}>
            <p>{preview ?? ""}</p>
            <p className="sv-note"><strong>{t.neverShown}:</strong> {panel.never.join("; ")}</p>
          </Panel>
        </div>
        <div className="sv-col">
          <Panel title={t.shared} actions={live.length > 0 ? <Button onClick={() => setConfirm("all")}>{t.withdrawAll}</Button> : undefined}>
            {confirm === "all" ? <Confirm line={t.withdrawAllConfirm} onYes={() => withdraw("all")} onNo={() => setConfirm(null)} /> : null}
            {panel.entries.length === 0 ? <p className="n-muted">{t.sharedNone}</p> : (
              <ul className="sv-list">
                {panel.entries.map((e) => (
                  <li key={e.id} className="sv-row">
                    <div className="sv-grow">
                      <strong>{t.kinds[e.kind]}: {e.who}</strong> <Pill tone={e.state === "live" ? "ok" : "draft"}>{t.rowStates[e.state]}</Pill>
                      <p className="sv-note">{t.rowLine(e.made_by, day(e.made_on), day(e.ends_on), e.opens)}</p>
                      {confirm === e.id ? <Confirm line={t.withdrawConfirm} onYes={() => withdraw(e.id)} onNo={() => setConfirm(null)} /> : null}
                    </div>
                    {e.state === "live" ? <Button onClick={() => setConfirm(e.id)}>{t.withdraw}</Button> : null}
                  </li>
                ))}
              </ul>
            )}
            {madeAny ? (
              <StatGrid cols={1}>
                <p className="sv-note">{t.countsShared(c.people, c.areas, c.links)}</p>
                <p className="sv-note">{t.countsOpened(c.opened, c.of)}</p>
                {c.of === null ? <p className="sv-note">{t.countsOfMissing}</p> : null}
                <p className="sv-note">{t.countsNotes(c.notes)}</p>
              </StatGrid>
            ) : <p className="sv-note">{t.countsNone}</p>}
          </Panel>
          <Panel title={t.opened}>
            <details open={typeof window === "undefined" || window.innerWidth > 900}>
              <summary>{t.countsOpened(c.opened, c.of)}</summary>
              {panel.opens.length === 0 ? <p className="n-muted">{t.openedNone}</p> : (
                <ul className="sv-list">
                  {panel.opens.map((o) => (
                    <li key={o.name} className="sv-row">
                      <div className="sv-grow"><strong>{o.name}</strong>
                        <p className="sv-note">{when(o.first)} to {when(o.last)}. {t.openedLine(o.times, o.through)}</p></div>
                    </li>
                  ))}
                </ul>
              )}
            </details>
          </Panel>
        </div>
      </div>
      <div id="notes">
        <Panel title={t.notes}>
          {panel.notes.length === 0 ? <p className="n-muted">{t.notesNone}</p> : (
            <ul className="sv-list">
              {panel.notes.map((n) => (
                <li key={n.id} className="sv-row">
                  <div className="sv-grow"><strong>{n.name}</strong> <span className="n-muted">{when(n.at)}</span>
                    <p>{n.text}</p></div>
                  {n.read ? <Chip>{t.read}</Chip> : <Button disabled={busy} onClick={() => markRead(n.id)}>{t.markRead}</Button>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </PageFrame>
  );
}

function Confirm({ line, onYes, onNo }: { line: string; onYes: () => void; onNo: () => void }) {
  return (
    <div role="alertdialog" aria-label={line} className="sv-banner">
      <p>{line}</p>
      <div className="sv-row"><Button variant="primary" onClick={onYes}>{t.yes}</Button><Button onClick={onNo}>{t.no}</Button></div>
    </div>
  );
}
