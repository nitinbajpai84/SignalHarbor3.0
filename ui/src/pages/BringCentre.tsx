import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";

import { ApiError, apiGet, apiSend, Refused } from "../api/client";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { bc as c } from "./bringCentreCopy";

// "Bring what you have" in the new look. The data calls are those of BringPage.tsx (readiness, upload per tile, read again, write the request),
// copied unchanged; only the layout and wording differ.

interface Group { id: number; key: string; title: string; required: boolean; state: string; reason: string; files: string[]; sealed?: number }
interface Ask { group: number; title: string; holder: { name: string | null; role: string | null; email: string | null } | null }
interface Readiness { groups: Group[]; percent: number; read: number; sentence: string; asks: Ask[] }
interface Line { name: string; ok: boolean; text: string }
interface Uploaded { results?: { name: string; result: string; reason: string }[] }
interface Written { subject: string; body: string; link: string }
interface Wrote { text: string; from: string; at: string }

const card: CSSProperties = { border: "1px solid var(--border-hairline)", borderRadius: "var(--radius-sm)", background: "var(--surface-elevated)", padding: 12 };
const mono: CSSProperties = { fontFamily: "var(--font-mono)", fontSize: 12 };
const pill = (state: string): CSSProperties => ({ ...mono, fontSize: 11, padding: "1px 8px", borderRadius: 999, border: `1px solid ${state === "read" ? "var(--teal)" : "var(--border-hairline)"}`, color: state === "read" ? "var(--teal)" : "var(--text-muted)" });

const say = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : c.failed);

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("unreadable"));
    r.readAsDataURL(file);
  });
}

function addedLine(file: File, out: Uploaded): Line {
  const mine = out.results?.[out.results.length - 1];
  if (!mine || mine.result === "read") return { name: file.name, ok: true, text: c.added(file.name) };
  if (mine.result === "context") return { name: file.name, ok: true, text: c.addedContext(file.name) };
  return { name: file.name, ok: true, text: c.addedNotRead(file.name, mine.reason) };
}

/** The newest cells the profile holds that say where they came from: an object with a mark and a `from` text. */
export function lastWritten(profile: unknown, n = 4): Wrote[] {
  const found: Wrote[] = [];
  const walk = (x: unknown): void => {
    if (Array.isArray(x)) return x.forEach(walk);
    if (!x || typeof x !== "object") return;
    const o = x as Record<string, unknown>;
    if ("mark" in o && typeof o.from === "string" && o.from) {
      const v = o.value;
      const text = Array.isArray(v) ? v.filter((i) => typeof i === "string" || typeof i === "number").join(", ") : typeof v === "string" || typeof v === "number" ? String(v) : "";
      if (text) found.push({ text, from: o.from, at: typeof o.at === "string" ? o.at : "" });
      return;
    }
    Object.values(o).forEach(walk);
  };
  walk(profile);
  return found.sort((a, b) => b.at.localeCompare(a.at)).slice(0, n);
}

function Tile({ g, onDone }: { g: Group; onDone: (lines: Line[]) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [restricted, setRestricted] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const busy = progress !== "";
  const submit = async () => {
    const files = Array.from(ref.current?.files ?? []);
    if (files.length === 0) return setError(c.chooseFile);
    setError("");
    const lines: Line[] = [];
    for (const [i, file] of files.entries()) {
      setProgress(c.progress(i + 1, files.length));
      try {
        const out = await apiSend<Uploaded>("POST", `/api/profile/inputs/${g.id}/upload`, { filename: file.name, data: await readBase64(file), restricted });
        lines.push(addedLine(file, out));
      } catch (e) {
        lines.push({ name: file.name, ok: false, text: c.notAdded(file.name, e instanceof Error && e.message === "unreadable" ? c.unreadable : say(e)) });
      }
    }
    if (ref.current) ref.current.value = "";
    setRestricted(false);
    setProgress("");
    onDone(lines);
  };
  return (
    <article aria-label={g.title} style={card}>
      <div className="n-flex between" style={{ gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{g.id}. {g.title}</h3>
        <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {g.sealed ? <span style={pill("sealed")}>{c.sealed(g.sealed)}</span> : null}
          <span style={pill(g.state)}>{c.pill[g.state] ?? g.state}</span>
        </span>
      </div>
      <p className="n-muted" style={{ fontSize: 12 }}>{g.reason}</p>
      {g.files.length ? <ul style={{ ...mono, margin: "4px 0", paddingLeft: 16 }}>{g.files.map((f) => <li key={f}>{f}</li>)}</ul> : <p className="n-muted" style={{ fontSize: 12 }}>{c.noFiles}</p>}
      <div style={{ border: "1px dashed var(--border-hairline)", borderRadius: "var(--radius-sm)", padding: 8, marginTop: 8 }}>
        <span className="n-muted" style={{ fontSize: 12 }}>{c.drop}</span>
        <div className="n-flex" style={{ gap: 8, marginTop: 4, flexWrap: "wrap" }}>
          <input className="n-input sm" type="file" multiple ref={ref} aria-label={c.file(g.title)} />
          <label className="n-flex" style={{ gap: 4 }}>
            <input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} />
            <span className="n-muted" style={{ fontSize: 12 }}>{c.restricted}</span>
          </label>
          <button type="button" className="n-btn sm primary" disabled={busy} onClick={submit}>{busy ? progress : c.add}</button>
        </div>
      </div>
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
    </article>
  );
}

function NiraAsk({ ask }: { ask: Ask }) {
  const [text, setText] = useState<Written | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const write = async () => {
    setError("");
    try {
      const r = await apiSend<{ email: Written }>("POST", `/api/profile/inputs/${ask.group}/ask`);
      setText({ ...r.email, link: `${window.location.origin}${r.email.link}` });
    } catch (e) {
      setError(say(e));
    }
  };
  const full = text ? `Subject: ${text.subject}\n\n${text.body.replace(/\/company\/bring\?ask=/, `${window.location.origin}/company/bring?ask=`)}` : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      setCopied(true);
    } catch {
      setError(c.failed);
    }
  };
  return (
    <div style={{ ...card, padding: 10 }}>
      <strong>{ask.title}</strong>
      <div className="n-muted" style={{ fontSize: 12 }}>{ask.holder?.name ? c.niraAsk(`${ask.holder.name}${ask.holder.role ? `, ${ask.holder.role}` : ""}`, ask.title) : c.niraNobody(ask.title)}</div>
      <button type="button" className="n-btn sm ghost" style={{ marginTop: 8 }} onClick={write}>{c.write(ask.title)}</button>
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
      {text ? (
        <div className="n-stack" style={{ marginTop: 8 }}>
          <p className="n-muted" style={{ fontSize: 12 }}>{c.copyNote}</p>
          <textarea className="n-input" readOnly rows={9} aria-label={`Request for ${ask.title}`} value={full} />
          <div><button type="button" className="n-btn sm" onClick={copy}>{c.copy}</button> {copied ? <span role="status" className="n-muted">{c.copied}</span> : null}</div>
        </div>
      ) : null}
    </div>
  );
}

export default function BringCentre() {
  const [state, setState] = useState<ScreenStateName>("loading");
  const [data, setData] = useState<Readiness | null>(null);
  const [wrote, setWrote] = useState<Wrote[] | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setState("loading");
    apiGet<Readiness>("/api/profile/readiness")
      .then((r) => {
        if (!live) return;
        setData(r);
        setState(r.groups.every((g) => g.state === "missing" && g.files.length === 0) ? "empty" : "populated");
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    apiGet<unknown>("/api/profile").then((p) => live && setWrote(lastWritten(p))).catch(() => live && setWrote(null));
    return () => {
      live = false;
    };
  }, [attempt]);
  const reload = useCallback(() => setAttempt((a) => a + 1), []);
  const uploaded = (got: Line[]) => {
    setNote("");
    setLines(got);
    setError("");
    if (got.some((l) => l.ok)) reload();
  };
  const readAgain = async () => {
    setBusy(true);
    setError("");
    try {
      await apiSend("POST", "/api/profile/read");
      setNote(c.readDone);
      setLines([]);
      reload();
    } catch (e) {
      setNote("");
      setError(say(e));
    } finally {
      setBusy(false);
    }
  };

  const shown = data && (state === "populated" || state === "empty");
  return (
    <>
      <h1 className="n-page-title">{c.title}</h1>
      {shown ? <p className="n-muted" style={mono}>{c.head(data.groups.reduce((n, g) => n + g.files.length, 0), data.read)}</p> : null}
      {state === "empty" || state === "populated" ? null : (
        <ScreenState state={state} onRetry={reload} message={state === "refused" ? c.noAccess : undefined} />
      )}
      {state === "empty" ? <p className="n-muted">{c.empty}</p> : null}
      {shown ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 16, alignItems: "start" }}>
          <div className="n-stack" style={{ gridColumn: "span 2" }}>
            <div style={card}>
              <div role="progressbar" aria-label={c.meterTitle} aria-valuemin={0} aria-valuemax={100} aria-valuenow={data.percent}
                   style={{ background: "var(--border-hairline)", borderRadius: 6, height: 10, overflow: "hidden" }}>
                <div style={{ width: `${data.percent}%`, height: "100%", background: "var(--teal)" }} />
              </div>
              <div className="n-flex between" style={{ marginTop: 6 }}>
                <strong>{c.meterLine(data.percent)}</strong>
                <button type="button" className="n-btn sm ghost" disabled={busy} onClick={readAgain}>{busy ? c.reading : c.readAgain}</button>
              </div>
            </div>
            {error ? <p role="alert" className="state state-error">{error}</p> : null}
            {note ? <p role="status" className="n-muted">{note}</p> : null}
            {lines.length ? (
              <ul aria-label={c.results} style={{ listStyle: "none", padding: 0 }}>
                {lines.map((l, i) => (l.ok ? <li key={i} role="status" className="n-muted">{l.text}</li> : <li key={i} role="alert" className="state state-error">{l.text}</li>))}
              </ul>
            ) : null}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: 12 }}>
              {data.groups.map((g) => <Tile key={g.id} g={g} onDone={uploaded} />)}
            </div>
          </div>
          <aside className="n-stack" style={{ minWidth: 0 }}>
            <section style={card} aria-label={c.livesTitle}>
              <h2 style={{ fontSize: 15, marginTop: 0 }}>{c.livesTitle}</h2>
              <ul style={{ paddingLeft: 16, margin: 0 }}>{c.lives.map((l) => <li key={l}>{l}</li>)}</ul>
            </section>
            <section style={card} aria-label={c.wroteTitle}>
              <h2 style={{ fontSize: 15, marginTop: 0 }}>{c.wroteTitle}</h2>
              {wrote === null ? <p className="n-muted">{c.na}</p> : wrote.length === 0 ? <p className="n-muted">{c.wroteNone}</p> : (
                <ul style={{ paddingLeft: 16, margin: 0 }}>{wrote.map((w, i) => <li key={i}>{w.text} <span className="n-muted" style={mono}>{c.wroteFrom(w.from)}</span></li>)}</ul>
              )}
            </section>
            <section aria-label={c.niraTitle} className="n-stack">
              <h2 style={{ fontSize: 15, margin: 0 }}>{c.niraTitle}</h2>
              {data.asks.length === 0 ? <p className="n-muted">{c.niraNone}</p> : data.asks.map((a) => <NiraAsk key={a.group} ask={a} />)}
            </section>
          </aside>
        </div>
      ) : null}
    </>
  );
}
