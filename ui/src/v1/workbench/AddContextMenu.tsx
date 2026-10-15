import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { changeItem, deleteItem, getContext, putContext, readBase64, uploadItem, type LibItem } from "../c4/api";
import type { Choice } from "../k1/api";
import UploadStep, { type Waiting } from "../k1/UploadStep";
import SavedDocuments from "./SavedDocuments";

// L1: the chat footer's "Add context for a more relevant conversation". Two entries: upload from this computer (K1's upload step with
// the note, sensitivity and topic proposal) and "Saved documents", which opens its own window (UX2, SavedDocuments: L3's folders with
// counts, search, ticks, lock, Open). Chips under
// the box show what the agent is reading, each with an untick. Nothing is ticked for the person.

type View = "menu" | "upload";

const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

export default function AddContextMenu({ iid, agent, canAdd = true }: { iid: string; agent: string; canAdd?: boolean }) {
  const picker = useRef<HTMLInputElement>(null);
  const [ticked, setTicked] = useState<LibItem[]>([]);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("menu");
  const [note, setNote] = useState("");
  const [share, setShare] = useState(false);
  const [waiting, setWaiting] = useState<Waiting[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (iid) { const c = await getContext(iid); setTicked(Array.isArray(c?.items) ? c.items : []); }
  }, [iid]);
  useEffect(() => { load().catch(() => { if (open) setError("The library could not be opened just now."); }); }, [load, open]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try { await fn(); await load(); return true; } catch (err) { setError(plain(err)); return false; } finally { setBusy(false); }
  };
  const ids = ticked.map((i) => i.id);
  const tick = (id: string) => act(() => putContext(iid, [...ids, id]));
  const [docs, setDocs] = useState(false);
  const untick = (id: string) => act(() => putContext(iid, ids.filter((x) => x !== id)));
  const isTicked = (id: string) => ids.includes(id);

  const send = async (file: File, choice: Choice, force: boolean) =>
    uploadItem({ name: file.name, data: await readBase64(file), note: note.trim() || undefined, share, iid: iid || undefined, force, ...choice });
  const add = (files: File[]) => {
    if (files.length) void act(async () => {
      const rows = await Promise.all(files.map(async (file) => ({ file, data: await readBase64(file) })));
      setWaiting((p) => [...p, ...rows]);
    });
  };
  const close = () => { setOpen(false); setView("menu"); };

  return (
    <div className="wb-ctx">
      {iid ? (
        <div className="wb-chips" aria-label="What the agent is reading">
          <span className="ds-muted">{ticked.length ? `${agent} is reading ${ticked.length} ${ticked.length === 1 ? "file" : "files"}:` : `${agent} is reading only what you add.`}</span>
          {ticked.map((i) => (
            <button key={i.id} type="button" className="ds-chip" aria-label={`Untick ${i.name}`} disabled={busy} onClick={() => void untick(i.id)}>{i.name} ×</button>
          ))}
        </div>
      ) : null}
      {canAdd ? (
        <button type="button" className="ds-btn" aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
          <span aria-hidden="true">📎</span> Add context for a more relevant conversation
        </button>
      ) : null}
      {open && canAdd ? (
        <div className="wb-menu" role="group" aria-label="Add context">
          {view === "menu" ? (
            <>
              <button type="button" className="ds-btn" onClick={() => setView("upload")}>Upload from this computer</button>
              <button type="button" className="ds-btn" aria-haspopup="dialog" onClick={() => setDocs(true)}>Saved documents</button>
            </>
          ) : <button type="button" className="ds-link" onClick={() => setView("menu")}>Back</button>}

          {view === "upload" ? (
            <div>
              <button type="button" className="ds-btn" disabled={busy} onClick={() => picker.current?.click()}>Choose files</button>
              <input ref={picker} type="file" multiple hidden aria-label={`Add files for ${agent}`}
                onChange={(e) => { add(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
              <input aria-label="Say what this is" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
                placeholder="Say what this is, e.g. performance reporting file, external file" style={{ display: "block", width: "100%", marginTop: 8 }} />
              <label style={{ display: "inline-flex", gap: 4, alignItems: "center", marginTop: 4, fontSize: 13 }}>
                <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} /> Share with the company
              </label>
              {!iid ? <p className="ds-muted" style={{ margin: "4px 0 0" }}>Files go to your library; tick them here once the conversation has started.</p> : null}
            </div>
          ) : null}
          {waiting.length ? <UploadStep files={waiting} note={note.trim() || undefined} send={send} onUse={iid ? tick : undefined}
            onUploaded={() => void load().catch(() => undefined)} onDone={() => { setWaiting([]); setNote(""); }} /> : null}

          {docs ? (
            <SavedDocuments iid={iid || undefined} current={ids} busy={busy} error={error} onClose={() => setDocs(false)}
              onUse={(chosen) => void act(() => putContext(iid, chosen)).then((ok) => { if (ok) setDocs(false); })}
              extra={(i, reload) => i.mine ? (
                <>
                  <label style={{ fontSize: 13 }}>
                    <input type="checkbox" role="switch" checked={i.visibility === "company"} disabled={busy} aria-label={`Share ${i.name} with the company`}
                      onChange={(e) => void act(() => changeItem(i.id, { visibility: e.target.checked ? "company" : "private" })).then(reload)} /> Share with the company
                  </label>
                  <button type="button" className="ds-link" disabled={busy} onClick={() => void act(() => deleteItem(i.id)).then(reload)}>Delete</button>
                </>
              ) : null} />
          ) : null}
          <button type="button" className="ds-link" onClick={close}>Close</button>
        </div>
      ) : null}
      {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
    </div>
  );
}
