import { useCallback, useEffect, useRef, useState } from "react";

import V3Frame from "../Frame";
import { getConnections, listFiles, type FileRow } from "../api";
import { filesFromDrop, postFile } from "./upload";
import "./files.css";

type Upload = { key: string; name: string; size: number; pct: number; state: "sending" | "done" | "skipped" | "failed"; note?: string };

const PILL: Record<FileRow["status"], string> = { recognised: "Recognised", loaded: "Loaded", waiting: "Waiting", question: "Question" };
/** Arrived or loaded = done; waiting or a question = needs (docs/v3/COLOURS.md). */
const MEANS: Record<FileRow["status"], "done" | "needs"> = { recognised: "done", loaded: "done", waiting: "needs", question: "needs" };
const FALLBACK_MAIL = "the office mailbox";
const FALLBACK_FOLDER = "the dropbox folder in your company folder, checked every 30 seconds";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};
const size = (b: number) => (b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);

/** One line per source seen in the list: how many files and the latest arrival. Nothing is shown for a source that never sent anything. */
export function bySource(files: FileRow[]): { source: string; count: number; last: string }[] {
  const m = new Map<string, { source: string; count: number; last: string }>();
  for (const f of files) {
    if (!f.source) continue;
    const g = m.get(f.source) ?? { source: f.source, count: 0, last: f.arrived_at };
    g.count += 1;
    if (f.arrived_at > g.last) g.last = f.arrived_at;
    m.set(f.source, g);
  }
  return [...m.values()].sort((a, b) => a.source.localeCompare(b.source));
}

export default function FilesPage() {
  const [files, setFiles] = useState<FileRow[] | null>(null);
  const [err, setErr] = useState("");
  const [mail, setMail] = useState(FALLBACK_MAIL);
  const [folder, setFolder] = useState(FALLBACK_FOLDER);
  const [ups, setUps] = useState<Upload[]>([]);
  const [over, setOver] = useState(false);
  const seq = useRef(0);

  const load = useCallback(() => {
    listFiles().then((r) => { setFiles(r.files); setErr(""); }).catch((e: Error) => setErr(e.message));
  }, []);
  useEffect(() => {
    load();
    getConnections()
      .then(({ connections }) => {
        const m = connections.find((c) => c.kind === "mailbox" && c.target);
        const f = connections.find((c) => c.kind === "folder" && c.target);
        if (m) setMail(m.target);
        if (f) setFolder(f.target);
      })
      .catch(() => undefined); // ponytail: the static lines stand until the connections route answers
  }, [load]);

  const patch = (key: string, p: Partial<Upload>) => setUps((u) => u.map((x) => (x.key === key ? { ...x, ...p } : x)));

  const send = async (list: File[]) => {
    const batch = list.map((f) => ({ file: f, up: { key: `u${seq.current++}`, name: f.name, size: f.size, pct: 0, state: "sending" as const } }));
    setUps((u) => [...batch.map((b) => b.up), ...u]);
    for (const { file, up } of batch) {
      try {
        const rows = await postFile(file, (pct) => patch(up.key, { pct }));
        const mine = rows.find((r) => r.name === file.name);
        if (mine?.skipped || mine?.duplicate) patch(up.key, { pct: 100, state: "skipped", note: `${file.name} is the same as a file Harbor already has, so it was skipped. Nothing was loaded twice.` });
        else patch(up.key, { pct: 100, state: "done" });
        setFiles(rows);
      } catch (e) {
        patch(up.key, { state: "failed", note: (e as Error).message });
      }
    }
  };

  const questions = (files ?? []).filter((f) => f.status === "question");
  const sources = bySource(files ?? []);

  return (
    <V3Frame>
      <main className="v3-files">
        <div className="v3-files-head">
          <h1>Files</h1>
          <p className="v3-mute">Anything that arrives lands here first.</p>
        </div>

        <section
          className={`v3-drop${over ? " over" : ""}`}
          aria-label="Drop files"
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); filesFromDrop(e.dataTransfer).then(send).catch((x: Error) => setErr(x.message)); }}
        >
          <h2>Drop files or a folder here</h2>
          <div className="v3-row">
            <label className="v3-pick">Choose files
              <input type="file" multiple aria-label="Choose files" onChange={(e) => { void send(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
            </label>
            <label className="v3-pick">Choose a folder
              <input type="file" multiple aria-label="Choose a folder" {...{ webkitdirectory: "" }} onChange={(e) => { void send(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
            </label>
          </div>
          <p className="v3-mute">or email them to <span className="num">{mail}</span></p>
          <p className="v3-mute">or your drop folder <span className="num">{folder}</span></p>
        </section>

        {err && <p className="v3-err" role="alert">{err}</p>}

        {ups.some((u) => u.state === "sending") && (
          <section className="v3-card" aria-label="Uploading now">
            <span className="v3-kicker">Uploading now</span>
            {ups.filter((u) => u.state === "sending").map((u) => (
              <div key={u.key} className="v3-up">
                <b>{u.name}</b><span className="num">{u.pct}%</span>
                <progress max={100} value={u.pct} aria-label={`${u.name} upload`} />
                <small className="v3-mute">{size(u.size)}</small>
              </div>
            ))}
          </section>
        )}

        {ups.filter((u) => u.state === "skipped" || u.state === "failed").map((u) => (
          <section key={u.key} className={u.state === "failed" ? "v3-card problem" : "v3-card need"}>
            <span className="v3-kicker">{u.state === "skipped" ? "Duplicate, skipped" : "Not uploaded"}</span>
            <p>{u.state === "skipped" ? u.note : `${u.name}: ${u.note}`}</p>
          </section>
        ))}

        {questions.map((f) => (
          <section key={f.name} className="v3-card need" aria-label={`Question about ${f.name}`}>
            <span className="v3-kicker">Question: {f.name}</span>
            <h2>What is this file?</h2>
            <p>Arrived {when(f.arrived_at)}. {f.source ? `It could belong to ${f.source}, but more than one thread uses that source` : "Harbor does not recognise it"}, so it is waiting for you.</p>
          </section>
        ))}

        <section aria-label="Sources seen">
          <h2>Sources seen</h2>
          {files !== null && sources.length === 0 && <p className="v3-mute">No source recognised yet.</p>}
          <div className="v3-strip">
            {sources.map((s) => (
              <div key={s.source} className="v3-fig">
                <small className="f3-src"><span className="f3-dot" aria-hidden="true" />{s.source}</small>
                <b className="f3-big">{s.count} {s.count === 1 ? "file" : "files"}</b>
                <small>Last arrived {when(s.last)}</small>
              </div>
            ))}
          </div>
        </section>

        <section aria-label="Recent files">
          <h2>Recent files</h2>
          {files === null && !err && <p className="v3-mute">Loading files...</p>}
          {files !== null && files.length === 0 && <p className="v3-mute">Nothing has arrived yet. Drop a file above to start.</p>}
          <ul className="v3-list">
            {(files ?? []).map((f) => (
              <li key={f.name + f.arrived_at}>
                <div>
                  <b>{f.name}</b>
                  <small className="v3-mute">Arrived {when(f.arrived_at)} · Recognised as {f.source || "not yet"}</small>
                </div>
                <span className={`v3-pill ${MEANS[f.status]}`}>{PILL[f.status]}</span>
              </li>
            ))}
          </ul>
        </section>

        <p className="v3-mute">Files are read on this machine; the original never leaves.</p>
      </main>
    </V3Frame>
  );
}
