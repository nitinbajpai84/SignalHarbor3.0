import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiSend, Refused } from "../api/client";
import { Button, EmptyState, PageFrame, Pill, SideCard, type PillTone } from "../design";
import { c } from "./bringCopy";

// Bring what you have: nine input tiles, upload per tile, the readiness progress bar,
// and Nira's list of what is missing and from whom.

type StateName = "loading" | "empty" | "error" | "refused" | "populated";

interface Group { id: number; key: string; title: string; required: boolean; state: string; reason: string; files: string[] }
interface Ask { group: number; title: string; holder: { name: string | null; role: string | null; email: string | null } | null }
interface Readiness { groups: Group[]; percent: number; read: number; sentence: string; asks: Ask[] }
interface Line { name: string; ok: boolean; text: string }
interface Uploaded { results?: { name: string; result: string; reason: string }[] }
interface Written { subject: string; body: string; link: string }

const TONE: Record<string, PillTone> = { read: "ok", partly: "open", missing: "draft" };
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

function Notice({ state, message, onRetry }: { state: StateName; message?: string; onRetry: () => void }) {
  if (state === "populated" || state === "empty") return null;
  if (state === "loading") return <p role="status" className="ds-muted">Loading…</p>;
  return (
    <div className="ds-card ds-side">
      <p role="alert" className="ds-warn">{message ?? "That did not work."}</p>
      {state === "error" && <div><Button onClick={onRetry}>Try again</Button></div>}
    </div>
  );
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
    <div className="ds-card" style={{ minHeight: 160, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 14 }}>{g.id}. {g.title}</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <Pill tone={TONE[g.state] ?? "draft"}>{c.state[g.state] ?? g.state}</Pill>
          <Pill tone="draft">{g.required ? c.required : c.helpful}</Pill>
        </div>
      </div>
      <p className="ds-muted" style={{ margin: 0, fontSize: 13, flex: 1 }}>{g.reason}</p>
      <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>{g.files.length ? c.from(g.files) : c.noFiles}</p>
      <div style={{ display: "flex", gap: 8, marginTop: "auto", alignItems: "flex-end", flexWrap: "wrap" }}>
        <input className="ds-input" style={{ flex: 1, minWidth: 140, fontSize: 12 }} type="file" multiple ref={ref} aria-label={c.file(g.title)} />
        <label style={{ display: "flex", gap: 4, alignItems: "center", cursor: "pointer", whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} />
          <span className="ds-muted" style={{ fontSize: 11 }}>{c.restricted}</span>
        </label>
        <Button disabled={busy} onClick={submit}>{busy ? progress : c.add}</Button>
      </div>
      {error ? <p role="alert" className="ds-warn" style={{ margin: 0, fontSize: 12 }}>{error}</p> : null}
    </div>
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
    <div className="ds-card">
      <strong style={{ display: "block", marginBottom: 6 }}>{ask.title}</strong>
      <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>
        {ask.holder?.name ? c.niraAsk(`${ask.holder.name}${ask.holder.role ? `, ${ask.holder.role}` : ""}`, ask.title) : c.niraNobody(ask.title)}
      </p>
      <div style={{ marginTop: 12 }}>
        <Button onClick={write}>{c.write(ask.title)}</Button>
      </div>
      {error ? <p role="alert" className="ds-warn" style={{ marginTop: 8, fontSize: 12 }}>{error}</p> : null}
      {text ? (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          <p className="ds-muted" style={{ margin: 0, fontSize: 12 }}>{c.copyNote}</p>
          <textarea className="ds-input" readOnly rows={6} aria-label={`Request for ${ask.title}`} value={full} style={{ fontSize: 12 }} />
          <div>
            <Button onClick={copy}>{c.copy}</Button> {copied ? <span role="status" className="ds-muted" style={{ fontSize: 12, marginLeft: 8 }}>{c.copied}</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function BringPage() {
  const [state, setState] = useState<StateName>("loading");
  const [data, setData] = useState<Readiness | null>(null);
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
    return () => {
      live = false;
    };
  }, [attempt]);

  const reload = useCallback(() => setAttempt((a) => a + 1), []);

  const done = (msg: string) => {
    setNote(msg);
    setLines([]);
    setError("");
    reload();
  };

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
      done(c.readDone);
    } catch (e) {
      setNote("");
      setError(say(e));
    } finally {
      setBusy(false);
    }
  };

  const sidebar = data ? (
    <>
      <SideCard title="Where this lives">
        <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
          <div>
            <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>Files</p>
            <p style={{ margin: 0 }}>This company's space, on this machine</p>
          </div>
          <div>
            <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>Who can open the originals</p>
            <p style={{ margin: 0 }}>The uploader, the company admin</p>
          </div>
          <div>
            <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>Which agent reads them</p>
            <p style={{ margin: 0 }}>Lens; North reads only shared summaries</p>
          </div>
          <div>
            <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>What may leave the machine</p>
            <p style={{ margin: 0 }}>Short passages, names replaced by tokens</p>
          </div>
          <div>
            <p className="ds-muted" style={{ margin: 0, fontSize: 11 }}>Sealed files</p>
            <p style={{ margin: 0, color: "var(--ds-amber)" }}>Never read, never leave</p>
          </div>
        </div>
      </SideCard>

      <SideCard title="What Lens wrote, with its source">
        <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
          {/* Placeholder for actual Lens findings */}
          <p className="ds-muted" style={{ margin: 0 }}>Not available yet</p>
        </div>
      </SideCard>

      {data.asks.length > 0 && (
        <SideCard title="Nira · What is missing, from whom">
          <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
            {data.asks.map((a) => (
              <div key={a.group}>
                <p style={{ margin: 0 }}>
                  <strong>{a.title}</strong>
                </p>
                <p className="ds-muted" style={{ margin: "4px 0 0" }}>
                  {a.holder?.name ? `${a.holder.name} holds it.` : "Nobody is named yet."}
                </p>
              </div>
            ))}
            <Button variant="primary" style={{ marginTop: "auto" }} onClick={readAgain}>
              Write the requests
            </Button>
          </div>
        </SideCard>
      )}
    </>
  ) : undefined;

  return (
    <div className="ds-screen">
      <PageFrame
        title={c.title}
        subline={c.sub}
        actions={data ? <Button disabled={busy} onClick={readAgain}>{busy ? c.reading : c.readAgain}</Button> : undefined}
        aside={sidebar}
      >
        <Notice state={state} message={state === "refused" ? c.noAccess : undefined} onRetry={reload} />

        {state === "empty" ? <EmptyState title={c.tilesTitle} lines={[c.empty]} /> : null}

        {data && (state === "populated" || state === "empty") ? (
          <>
            {/* Progress bar and stats */}
            <div className="ds-card">
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span className="ds-muted" style={{ fontSize: 12 }}>{c.meterTitle}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ds-teal-bright)" }}>{data.percent}%</span>
                </div>
                <div style={{ height: 8, borderRadius: 4, backgroundColor: "var(--ds-line)", overflow: "hidden" }}>
                  <div style={{ width: `${data.percent}%`, height: "100%", backgroundColor: "var(--ds-teal-bright)" }} />
                </div>
              </div>
              <p style={{ margin: 0, fontSize: 13 }}>
                <strong>{c.meterLine(data.percent)}</strong> <span className="ds-muted">{c.meterRead(data.read)}</span>
              </p>
            </div>

            {error ? <p role="alert" className="ds-warn">{error}</p> : null}
            {note ? <p role="status" className="ds-muted">{note}</p> : null}

            {lines.length ? (
              <div style={{ backgroundColor: "var(--ds-surface)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
                <p style={{ margin: 0, fontSize: 12, marginBottom: 8, fontWeight: 600 }}>{c.results}</p>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
                  {lines.map((l, i) => (
                    <li key={i} style={{ fontSize: 12, color: l.ok ? "var(--ds-ink-soft)" : "var(--ds-warn)" }}>
                      {l.text}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Nine tiles grid */}
            {state === "populated" || state === "empty" ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
                {data.groups.map((g) => (
                  <Tile key={g.id} g={g} onDone={uploaded} />
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </PageFrame>
    </div>
  );
}
