import { useCallback, useEffect, useRef, useState } from "react";

import { listFiles, type BriefGroup, type FileRow } from "../api";
import { filesFromDrop, postFile } from "../files/upload";

const POLL_MS = 4000;
type Up = { key: string; name: string; pct: number; state: "sending" | "done" | "failed"; note?: string };

/** One chip per source line in the brief: arrived when a file for this thread was recognised as that source. */
export function expected(doc: BriefGroup[] | null | undefined, files: FileRow[]): { name: string; count: number }[] {
  const lines = doc?.find((g) => g.title === "Where the data comes from")?.lines ?? [];
  return lines.map((l) => {
    const n = l.label.trim().toLowerCase();
    return { name: l.label, count: files.filter((f) => f.source && f.source.trim().toLowerCase() === n).length };
  });
}

export default function DropBand({ id, doc, onFiles }: { id: string; doc?: BriefGroup[] | null; onFiles?: (files: FileRow[]) => void }) {
  const [files, setFiles] = useState<FileRow[] | null>(null);
  const [err, setErr] = useState("");
  const [ups, setUps] = useState<Up[]>([]);
  const [over, setOver] = useState(false);
  const seq = useRef(0);

  const load = useCallback(() => {
    listFiles().then((r) => { const mine = r.files.filter((f) => f.thread === id); setFiles(mine); onFiles?.(mine); setErr(""); }).catch((e: Error) => setErr(e.message));
  }, [id, onFiles]);
  useEffect(() => {
    load();
    const h = setInterval(load, POLL_MS);
    return () => clearInterval(h);
  }, [load]);

  const patch = (key: string, p: Partial<Up>) => setUps((u) => u.map((x) => (x.key === key ? { ...x, ...p } : x)));
  const send = async (list: File[]) => {
    const batch = list.map((f) => ({ file: f, up: { key: `u${seq.current++}`, name: f.name, pct: 0, state: "sending" as const } }));
    setUps((u) => [...batch.map((b) => b.up), ...u]);
    for (const { file, up } of batch) {
      try {
        await postFile(file, (pct) => patch(up.key, { pct }));
        patch(up.key, { pct: 100, state: "done" });
      } catch (e) {
        patch(up.key, { state: "failed", note: (e as Error).message });
      }
    }
    load();
  };

  const list = files ?? [];
  const chips = expected(doc, list);
  return (
    <section className="b3-band" aria-label="Files for this use case">
      <div
        className={`b3-drop${over ? " over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); filesFromDrop(e.dataTransfer).then(send).catch((x: Error) => setErr(x.message)); }}
      >
        <b>Drop the files for this use case</b>
        <small className="v3-mute">PDF, Excel or CSV. Files are read on this machine; nothing leaves.</small>
        <label className="v3-pick">Choose files
          <input type="file" multiple aria-label="Choose files" onChange={(e) => { void send(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
        </label>
        {ups.filter((u) => u.state !== "done").map((u) => (
          <div key={u.key} className="v3-up">
            <span>{u.name}</span>
            {u.state === "sending" ? <progress max={100} value={u.pct} aria-label={`${u.name} upload`} /> : <span className="b3-fail" role="alert">{u.note}</span>}
          </div>
        ))}
      </div>
      <div className="b3-files">
        <span className="v3-kicker">Expected from the graph · {chips.length} {chips.length === 1 ? "source" : "sources"}</span>
        {chips.length === 0 && <small className="v3-mute">No sources in the brief yet.</small>}
        <div className="b3-chips">
          {chips.map((c, i) => (
            <span key={`${c.name}-${i}`} className={c.count ? "b3-chip done" : "b3-chip needs"}>{c.name} · {c.count ? `arrived, ${c.count} ${c.count === 1 ? "file" : "files"}` : "waiting"}</span>
          ))}
        </div>
        <span className="v3-kicker">Dropped so far{files ? ` · ${list.length} ${list.length === 1 ? "file" : "files"}` : ""}</span>
        {err && <p className="v3-err" role="alert">{err}</p>}
        {files === null && !err && <small className="v3-mute" role="status">Loading files...</small>}
        {files !== null && list.length === 0 && <small className="v3-mute">Nothing dropped for this use case yet.</small>}
        <ul className="b3-recent">
          {list.slice(0, 6).map((f) => (
            <li key={f.name + f.arrived_at}><span className={`b3-fdot ${f.status === "question" || f.status === "waiting" ? "needs" : "done"}`} aria-hidden="true" /><b>{f.name}</b> <small className="v3-mute">{f.source || "not sure yet"}</small></li>
          ))}
        </ul>
      </div>
    </section>
  );
}
