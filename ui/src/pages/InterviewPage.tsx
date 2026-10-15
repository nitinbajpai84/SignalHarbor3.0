import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend, guestSend, Refused } from "../api/client";
import { copy } from "../copy";
import { Button, EmptyState, PageFrame, Pill, SideCard, type PillTone } from "../design";
import { c } from "./interviewCopy";

// The one interview, in the design system: a chat with North and Lens. Each question the documents already answer arrives as a draft
// with its source, to Keep or Change. The organiser also sees everyone with their status and can make an invite link.
// Routes: /company/interview (signed in, inside the centre shell) and /interview/:token (a guest's own link, no sign-in).
type StateName = "loading" | "empty" | "error" | "refused" | "populated";
const TONE: Record<string, PillTone> = { not_started: "draft", in_progress: "open", done: "ok" };

interface Person { id: string; name: string; role: string; kind: string; status: string; answered: number; of: number; self: boolean }
interface Card { qid: string; agent: string; mode: "ask" | "draft" | "confirm" | "followup"; text: string; draft: { text: string; from: string } | null; final: boolean; share: boolean }
interface Turn { who: string; qid: string | null; text: string }
interface Interview {
  person: { id: string; name: string };
  status: string;
  progress?: { answered: number; of: number; minutes_left: number };
  log: Turn[];
  card: Card | null;
}

const say = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : c.failed);
const initials = (n: string) => n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("");

/** Loading, error, refused and empty as one short block; populated renders nothing. */
function Notice({ state, message, onRetry }: { state: StateName; message?: string; onRetry: () => void }) {
  if (state === "populated") return null;
  if (state === "loading") return <p role="status" className="ds-muted">{message ?? copy.states.loading}</p>;
  if (state === "empty") return <EmptyState title={c.peopleTitle} lines={[message ?? copy.states.empty]} />;
  return (
    <div className="ds-card ds-side">
      <p role="alert" className="ds-warn">{message ?? copy.states.error}</p>
      {state === "error" && <div><Button onClick={onRetry}>{copy.states.retry}</Button></div>}
    </div>
  );
}

function Chat({ data, canAnswer, send, onFinish }: { data: Interview; canAnswer: boolean; send: (b: object) => Promise<void>; onFinish: () => Promise<void> }) {
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const card = data.card;
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      setText("");
      setEditing(false);
    } catch (e) {
      setError(say(e));
    } finally {
      setBusy(false);
    }
  };
  const p = data.progress;
  const panel = (title: string, body: ReactNode) => <div className="ds-card ds-side"><strong className="ds-side__title">{title}</strong>{body}</div>;
  return (
    <>
      {p ? <p role="status" className="ds-muted">{data.status === "done" ? c.progressDone(p.answered, p.of) : c.progress(p.answered, p.of, p.minutes_left)}</p> : null}
      <div className="ds-thread" aria-label="Conversation">
        {data.log.map((t, i) => (
          <div key={i} className="ds-comment">
            <span className="ds-avatar" aria-hidden="true">{initials(c.who[t.who] ?? t.who)}</span>
            <div className="ds-comment__body">
              <b>{c.who[t.who] ?? t.who}</b>
              <span>{t.text}</span>
            </div>
          </div>
        ))}
      </div>
      {data.status === "done" ? <p role="status">{c.finished}</p> : null}
      {card && canAnswer
        ? panel(
            card.final && card.mode !== "followup" ? c.last : card.agent === "lens" ? "Lens" : "North",
            card.draft && !editing ? (
              <article aria-label="Draft to confirm" className="ds-side">
                <span className="ds-muted">{card.mode === "confirm" ? c.from(card.draft.from) : c.draftFrom(card.draft.from)}</span>
                <p>{card.draft.text}</p>
                <div className="ds-frame__actions">
                  <Button variant="primary" disabled={busy} onClick={() => act(() => send({ action: "keep" }))}>{c.keep}</Button>
                  <Button disabled={busy} onClick={() => { setText(card.draft?.text ?? ""); setEditing(true); }}>{c.change}</Button>
                </div>
              </article>
            ) : card.share ? (
              <>
                <p>{card.text}</p>
                <div className="ds-frame__actions">
                  {[["named", c.named], ["anonymous", c.anonymous], ["private", c.private]].map(([v, label]) => (
                    <Button key={v} disabled={busy} onClick={() => act(() => send({ text: v }))}>{label}</Button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <label htmlFor="iv-answer" className="ds-muted">{c.yourAnswer}</label>
                <textarea id="iv-answer" className="ds-input" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
                <div><Button variant="primary" disabled={busy || !text.trim()} onClick={() => act(() => send({ text, action: "change" }))}>{busy ? c.sending : c.send}</Button></div>
              </>
            ),
          )
        : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
      {data.status !== "done" && canAnswer ? <div><Button disabled={busy} onClick={() => act(onFinish)}>{c.done}</Button></div> : null}
    </>
  );
}

function Guest({ token }: { token: string }) {
  const [state, setState] = useState<StateName>("loading");
  const [data, setData] = useState<Interview | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [msg, setMsg] = useState("");
  const first = useSearchParams()[0].get("for") || "the person this link is for"; // the invite link carries the first name
  useEffect(() => {
    let live = true;
    setState("loading");
    guestSend<Interview>("POST", "/api/modules/interview/guest/start", {}, token)
      .then((r) => { if (live) { setData(r); setState("populated"); } })
      .catch((e: unknown) => { if (live) { setMsg(e instanceof Refused ? c.signedInAs(first) : e instanceof ApiError && e.status === 404 ? c.noLink : ""); setState(e instanceof ApiError && (e.status === 404 || e instanceof Refused) ? "refused" : "error"); } });
    return () => { live = false; };
  }, [token, attempt, first]);
  const send = async (b: object) => setData(await guestSend<Interview>("POST", "/api/modules/interview/guest/answer", b, token));
  const finish = async () => setData(await guestSend<Interview>("POST", "/api/modules/interview/guest/finish", {}, token));
  return (
    <div className="ds-screen">
      <header className="ds-topbar"><div className="ds-topbar__mark" aria-hidden="true" /><strong className="ds-topbar__product">{copy.product}</strong></header>
      <PageFrame title={c.guestTitle} subline={c.sub}>
        {state === "populated" && data ? <Chat data={data} canAnswer send={send} onFinish={finish} /> : <Notice state={state} message={msg || undefined} onRetry={() => setAttempt((a) => a + 1)} />}
      </PageFrame>
    </div>
  );
}

function Organiser() {
  const [state, setState] = useState<StateName>("loading");
  const [people, setPeople] = useState<Person[]>([]);
  const [isOrganiser, setIsOrganiser] = useState(false);
  const [open, setOpen] = useState<Person | null>(null);
  const [data, setData] = useState<Interview | null>(null);
  const [link, setLink] = useState<{ name: string; url: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  const load = useCallback(() => {
    let live = true;
    setState("loading");
    apiGet<{ people: Person[]; organiser: boolean }>("/api/interview")
      .then((r) => {
        if (!live) return;
        setPeople(r.people);
        setIsOrganiser(r.organiser);
        setState(r.people.length ? "populated" : "empty");
        if (!r.organiser && r.people[0]) void begin(r.people[0]);
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);
  useEffect(load, [load]);

  const begin = async (p: Person) => {
    setError("");
    try {
      setData(await apiSend<Interview>("POST", `/api/interview/${p.id}/start`));
      setOpen(p);
    } catch (e) {
      setError(say(e));
    }
  };
  const invite = async (p: Person) => {
    setError("");
    try {
      const r = await apiSend<{ link: string }>("POST", `/api/interview/${p.id}/link`);
      setLink({ name: p.name, url: `${window.location.origin}${r.link}` });
      setCopied(false);
    } catch (e) {
      setError(say(e));
    }
  };
  const send = async (b: object) => setData(await apiSend<Interview>("POST", `/api/interview/${open?.id}/answer`, b));
  const finish = async () => setData(await apiSend<Interview>("POST", `/api/interview/${open?.id}/finish`));
  const refresh = () => { setOpen(null); setData(null); setAttempt((a) => a + 1); };

  const aside = link ? (
    <SideCard title={c.invite(link.name)}>
      <p>{c.linkNote}</p>
      <textarea className="ds-input" readOnly rows={3} aria-label={`Link for ${link.name}`} value={link.url} />
      <div>
        <Button onClick={async () => { try { await navigator.clipboard.writeText(link.url); setCopied(true); } catch { setError(c.failed); } }}>{c.copy}</Button>{" "}
        {copied ? <span role="status" className="ds-muted">{c.copied}</span> : null}
      </div>
    </SideCard>
  ) : undefined;

  return (
    <div className="ds-screen">
      <PageFrame title={c.title} subline={c.sub} crumbs={<Link to="/centre/action">{c.crumbPulse}</Link>} aside={aside}
        actions={open && isOrganiser ? <Button onClick={refresh}>{c.peopleTitle}</Button> : undefined}>
        <Notice state={state} onRetry={() => setAttempt((a) => a + 1)} message={state === "refused" ? c.noAccess : state === "empty" ? c.empty : undefined} />
        {error ? <p role="alert" className="ds-warn">{error}</p> : null}
        {open && data ? (
          <>
            <strong>{open.name}</strong>
            {open.self ? null : <p className="ds-muted">{c.onlyThem(open.name)}</p>}
            <Chat data={data} canAnswer={open.self} send={send} onFinish={finish} />
          </>
        ) : state === "populated" ? (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            {people.map((p) => (
              <li key={p.id} aria-label={p.name} className="ds-card ds-side">
                <div className="ds-side__head">
                  <span><strong>{p.name}</strong>{p.role ? <span className="ds-muted"> · {p.role}</span> : null}</span>
                  <Pill tone={TONE[p.status] ?? "draft"}>{c.status[p.status] ?? p.status}</Pill>
                </div>
                {p.of ? <span className="ds-muted">{p.answered} of {p.of}</span> : null}
                <div className="ds-frame__actions">
                  <Button onClick={() => begin(p)}>{c.open(p.name)}</Button>
                  {isOrganiser ? <Button onClick={() => invite(p)}>{c.invite(p.name)}</Button> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </PageFrame>
    </div>
  );
}

export default function InterviewPage() {
  const { token } = useParams();
  return token ? <Guest token={token} /> : <Organiser />;
}
