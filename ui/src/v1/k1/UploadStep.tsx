import { useEffect, useState } from "react";

import { Button } from "../../design";
import type { Found, UploadAnswer } from "../c4/api";
import { getProposal, type Choice, type Proposal, type Sensitivity } from "./api";

// K1: the upload step of the attach menu, for one file or a batch. One row per file: what the program found ("Looks like a reporting
// file. Contains personal data (email addresses in column 4). Keep as Restricted?"), its own sensitivity and topic, and its own status.
// One shared note and share switch (the parent's) go with the whole batch. Uploads run one after the other.
export const LEVELS: { id: Sensitivity; label: string; hint: string }[] = [
  { id: "open", label: "Open", hint: "anyone in the company" },
  { id: "internal", label: "Internal", hint: "people you name" },
  { id: "restricted", label: "Restricted", hint: "personal data, or you say so" },
];

export interface Waiting { file: File; data: string }
type Status = "ready" | "uploading" | "done" | "duplicate" | "similar" | "could-not-read";
interface Row extends Waiting {
  p: Proposal | null; level: Sensitivity; topic: string; reviewed: boolean; status: Status; message: string; found: Found[]; folder: string;
}
const lowers = (r: Row) => !!r.p?.pii.found && r.level !== "restricted";
const choiceOf = (r: Row): Choice => ({
  sensitivity: r.level, topic: r.topic.trim() ? [r.topic.trim()] : [], reviewed: lowers(r) && r.reviewed,
  folder: r.folder || undefined, folder_by: r.folder && r.folder !== r.p?.folder ? "owner" : r.p?.folder_by,  // L3
});
const day = (at: string) => { const d = new Date(at); return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { dateStyle: "medium" }); };

export default function UploadStep({ files, note, send, onUse, onUploaded, onDone }: {
  files: Waiting[]; note?: string; send: (file: File, choice: Choice, force: boolean) => Promise<UploadAnswer>;
  onUse?: (id: string) => Promise<unknown> | void; onUploaded?: () => void; onDone: () => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const patch = (file: File, change: Partial<Row>) => setRows((p) => p.map((r) => (r.file === file ? { ...r, ...change } : r)));

  useEffect(() => {  // a file added while the step is open joins the list
    const fresh = files.filter((f) => !rows.some((r) => r.file === f.file));
    if (!fresh.length) return;
    setRows((p) => [...p, ...fresh.map((f): Row => ({ ...f, p: null, level: "open", topic: "", reviewed: false, status: "ready", message: "", found: [], folder: "" }))]);
    fresh.forEach((f) => getProposal(f.file.name, f.data, note).then(
      (got) => patch(f.file, { p: got, level: got.sensitivity, topic: got.topics[0] ?? "", folder: got.folder ?? "" }),
      () => patch(f.file, { status: "could-not-read" })));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files]);

  const go = async (r: Row, force = false) => {
    patch(r.file, { status: "uploading" });
    try {
      const got = await send(r.file, choiceOf(r), force);
      if ("duplicate" in got) patch(r.file, { status: "duplicate", found: [got.duplicate] });
      else if ("similar" in got) patch(r.file, { status: "similar", found: got.similar });
      else { patch(r.file, { status: "done", message: got.message ?? "Added to the library." }); onUploaded?.(); }
    } catch {
      patch(r.file, { status: "could-not-read", message: "That did not go through. Please try again." });
    }
  };
  const runAll = async () => {
    setRunning(true);
    for (const r of rows.filter((x) => x.status === "ready" && x.p)) await go(r);  // one after the other
    setRunning(false);
  };
  const use = async (r: Row) => { await onUse?.(r.found[0]?.id ?? ""); patch(r.file, { status: "done", message: "Using the file already in the library." }); };

  const ready = rows.filter((r) => r.status === "ready" && r.p);
  const blocked = ready.some((r) => lowers(r) && !r.reviewed);
  return (
    <div role="group" aria-label="Files to add" style={{ marginTop: 8 }}>
      {rows.map((r, n) => (
        <div key={r.file.name + n} role="group" aria-label={`Upload ${r.file.name}`} style={{ border: "1px solid currentColor", borderRadius: 8, padding: 12, marginTop: 8 }}>
          <p style={{ margin: 0 }}><strong>{r.file.name}</strong></p>
          {r.status === "could-not-read" ? (
            <p role="alert" style={{ margin: "4px 0" }}>{r.message || `We could not read ${r.file.name}.`}{" "}
              <button type="button" className="ds-link" onClick={() => setRows((p) => p.filter((x) => x !== r))}>Dismiss</button></p>
          ) : !r.p ? <p className="ds-muted" style={{ margin: "4px 0" }}>Looking at {r.file.name}…</p> : (
            <>
              <p style={{ margin: "4px 0" }}>{r.p.message}</p>
              {r.status === "ready" || r.status === "uploading" ? (
                <>
                  <div role="radiogroup" aria-label={`Who may use ${r.file.name}`} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {LEVELS.map((l) => (
                      <button key={l.id} type="button" role="radio" aria-checked={r.level === l.id} className="ds-btn" disabled={running || r.status === "uploading"}
                        style={{ fontWeight: r.level === l.id ? 700 : 400 }} onClick={() => patch(r.file, { level: l.id })}>{l.label} <span className="ds-muted">({l.hint})</span></button>
                    ))}
                  </div>
                  {lowers(r) ? (
                    <label style={{ display: "block", marginTop: 4, fontSize: 13 }}>
                      <input type="checkbox" checked={r.reviewed} onChange={(e) => patch(r.file, { reviewed: e.target.checked })} /> I have looked and this is not personal data
                    </label>
                  ) : null}
                  {r.p.folder ? (
                    <p style={{ margin: "8px 0 0" }}>Goes to: <strong>{r.folder || r.p.folder}</strong>{" "}
                      <select aria-label={`Change the folder for ${r.file.name}`} value={r.folder || r.p.folder} disabled={running || r.status === "uploading"}
                        onChange={(e) => patch(r.file, { folder: e.target.value })}>
                        {(r.p.folders ?? [r.p.folder]).map((f) => <option key={f} value={f}>{f}</option>)}
                      </select> <span className="ds-muted">change</span></p>
                  ) : null}
                  <label style={{ display: "block", marginTop: 8 }}>Topic{" "}
                    <input list="k1-topics" aria-label={`Topic for ${r.file.name}`} value={r.topic} onChange={(e) => patch(r.file, { topic: e.target.value })} maxLength={40} />
                    <datalist id="k1-topics">{r.p.topic_list.map((t) => <option key={t} value={t} />)}</datalist>
                  </label>
                </>
              ) : null}
              <p style={{ margin: "4px 0" }} aria-live="polite"><span className="ds-muted">
                {r.status === "ready" ? "Ready to add." : r.status === "uploading" ? "Uploading…" : r.status === "done" ? r.message : null}
              </span></p>
              {r.status === "duplicate" || r.status === "similar" ? (
                <div role="alert">
                  <p style={{ margin: 0 }}>{r.status === "duplicate"
                    ? `${r.file.name} is already in the library, uploaded by ${r.found[0]?.uploaded_by ?? "a colleague"} on ${day(r.found[0]?.at ?? "")}. Use it?`
                    : `The library has a similar file: ${r.found.map((f) => `${f.name} (${f.uploaded_by}, ${day(f.at)})`).join("; ")}. Use it instead?`}</p>
                  <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                    {onUse ? <Button onClick={() => void use(r)}>Use it</Button> : null}
                    <Button onClick={() => void go(r, true)}>Upload anyway</Button>
                    <button type="button" className="ds-link" onClick={() => setRows((p) => p.filter((x) => x !== r))}>Dismiss</button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        {ready.length ? (
          <Button disabled={running || blocked} onClick={() => void runAll()}>
            {ready.length > 1 ? `Add ${ready.length} files to the library` : "Add to the library"}
          </Button>
        ) : null}
        <button type="button" className="ds-link" onClick={onDone}>{rows.some((r) => r.status === "done") && !ready.length ? "Close" : "Cancel"}</button>
      </div>
    </div>
  );
}
