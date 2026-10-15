import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiSend, guestSend } from "../api/client";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { Chip, PageFrame } from "../design";
import { visitorCopy as t } from "./views/shareCopy";
import { shareStyle } from "./views/shareStyle";

// Screen B of spec 11: what a signed-in visitor reads through a share. Read only. Named and area shares send the intent id in the body;
// a link's token is read from the address and sent only in the X-Session-Token header.

export interface VisitorData {
  banner: { organiser: string; ends: string };
  intent: { title: string; purpose: string; type: string; state: string; areas: string[] };
  people: { name: string; role: string }[];
  stages: { key: string; name: string; state: string; opened_at: string | null; closed_at: string | null }[];
  wall: { kind: "wall"; lanes: { lane: string; cards: { text: string; author: string }[] }[] } | { kind: "weeks"; items: { week: string; kind: string; text: string; fate: string | null; reason: string | null }[] } | null;
  outcome: Record<string, unknown> | null;
  sealed: number;
  restricted: number;
  closure: { summary: string; why_it_happened: string; what_came_out: string; next: { kind: string; reason: string }[]; closed_at: string | null } | null;
  cancelled: { by: string; on: string | null; reason: string } | null;
  note_max: number;
}

const day = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { timeZone: "UTC", dateStyle: "medium" }) : "");
const label = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** The words for a refused open: too many tries and the server's own plain sentences; anything else is the not-working line. */
const problem = (e: unknown): string =>
  e instanceof ApiError && e.status === 429 ? t.tooMany : // the api client drops 429 bodies, so the sentence lives here
  e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : t.notWorking;

export default function VisitorView() {
  const { intentId = "", token = "" } = useParams<{ intentId?: string; token?: string }>();
  const open = () => (token ? guestSend<VisitorData>("POST", "/api/modules/m1_intent/shared/view", {}, token) : apiSend<VisitorData>("POST", "/api/modules/m1_intent/shared/view", { intent_id: intentId }));
  const { state, data, message } = useLoad<VisitorData>(() => open().catch((e: unknown) => Promise.reject(new ApiError(problem(e), 404))), `shared-${token || intentId}`);
  return (
    <>
      <style>{shareStyle}</style>
      <ScreenState state={state} message={message}>
        {data ? <Body data={data} intentId={intentId} token={token} /> : null}
      </ScreenState>
    </>
  );
}

function Body({ data, intentId, token }: { data: VisitorData; intentId: string; token: string }) {
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const who = data.banner.organiser || "the organiser";
  const { intent } = data;

  async function send() {
    setBusy(true);
    setErr("");
    try {
      const body = token ? { text } : { intent_id: intentId, text };
      await (token ? guestSend("POST", "/api/modules/m1_intent/shared/note", body, token) : apiSend("POST", "/api/modules/m1_intent/shared/note", body));
      setText("");
      setSent(true);
    } catch (e) {
      setErr(problem(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageFrame title={intent.title} subline={intent.purpose}>
      <p role="status" className="sv-banner">{t.banner(who, day(data.banner.ends))}</p>
      <div className="sv-visit">
        <div className="sv-col">
          <Panel title={t.stages}>
            {data.stages.length === 0 ? <p className="n-muted">{t.stagesNone}</p> : (
              <div className="sv-row">
                {data.stages.map((s) => <Chip key={s.key} tone={s.state === "open" ? "active" : "default"}>{label(s.name)}{s.closed_at ? ` (closed ${day(s.closed_at)})` : s.opened_at ? ` (opened ${day(s.opened_at)})` : ""}</Chip>)}
              </div>
            )}
          </Panel>
          {intent.state === "cancelled" && data.cancelled ? (
            <Panel title={label("cancelled")}><p>{t.cancelled(data.cancelled.by, day(data.cancelled.on), data.cancelled.reason)}</p></Panel>
          ) : (
            <>
              <Panel title={data.wall?.kind === "weeks" ? t.weeks : t.wall}>
                <Wall wall={data.wall} />
              </Panel>
              {data.outcome ? (
                <Panel title={t.outcome}>
                  <ul className="sv-list">
                    {Object.entries(data.outcome).map(([k, v]) => <li key={k}><strong>{label(k)}:</strong> {typeof v === "string" ? v : JSON.stringify(v)}</li>)}
                  </ul>
                </Panel>
              ) : null}
              {data.sealed > 0 ? <p className="sv-banner">{t.sealed(data.sealed)}</p> : null}
              {data.restricted > 0 ? <p className="sv-banner">{t.restricted(data.restricted)}</p> : null}
              <Panel title={t.closure}>
                {data.closure ? (
                  <>
                    <p><strong>{t.summary}:</strong> {data.closure.summary}</p>
                    <p><strong>{t.why}:</strong> {data.closure.why_it_happened}</p>
                    <p><strong>{t.came}:</strong> {data.closure.what_came_out}</p>
                    <h3>{t.next}</h3>
                    <ul className="sv-list">{data.closure.next.map((n, i) => <li key={i}>{label(n.kind)}. {n.reason}</li>)}</ul>
                  </>
                ) : <p className="n-muted">{t.closureNone}</p>}
              </Panel>
            </>
          )}
        </div>
        <div className="sv-col">
          <Panel title={t.people}>
            <details open={typeof window === "undefined" || window.innerWidth > 900}>
              <summary>{t.peopleCount(data.people.length)}</summary>
              {data.people.length === 0 ? <p className="n-muted">{t.peopleNone}</p> : (
                <ul className="sv-list">{data.people.map((p, i) => <li key={`${p.name}-${i}`}><strong>{p.name}</strong> <span className="n-muted">{p.role}</span></li>)}</ul>
              )}
            </details>
          </Panel>
          <Panel title={t.noteTitle(who)}>
            <label>
              <span className="sv-note">{t.noteHelp(who)}</span>
              <textarea className="sv-field" value={text} maxLength={data.note_max} aria-label={t.noteTitle(who)} onChange={(e) => { setText(e.target.value); setSent(false); }} />
            </label>
            <div className="sv-row">
              <button type="button" className="ds-btn ds-btn--primary" disabled={busy || text.trim() === ""} onClick={send}>{t.send}</button>
            </div>
            {sent ? <p role="status">{t.sent(who)}</p> : null}
            {err ? <p role="alert" className="state state-error">{err}</p> : null}
          </Panel>
        </div>
      </div>
    </PageFrame>
  );
}

function Wall({ wall }: { wall: VisitorData["wall"] }) {
  if (!wall) return <p className="n-muted">{t.wallNone}</p>;
  if (wall.kind === "weeks") {
    return (
      <ul className="sv-list">
        {wall.items.map((i, n) => <li key={n} className="sv-card"><strong>{label(i.kind)}</strong> <span className="n-muted">{i.week}</span><p>{i.text}</p>{i.fate ? <p className="sv-note">{label(i.fate)}. {i.reason ?? ""}</p> : null}</li>)}
      </ul>
    );
  }
  return (
    <div className="sv-lanes">
      {wall.lanes.map((l) => (
        <div key={l.lane} className="sv-col">
          <h3>{label(l.lane)}</h3>
          {l.cards.map((c, i) => <div key={i} className="sv-card"><p>{c.text}</p><p className="sv-note">{c.author}</p></div>)}
        </div>
      ))}
    </div>
  );
}
