import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { dropFiles } from "../voice";
import type { Choice } from "../k1/api";
import LockedRow from "../k1/LockedRow";
import UploadStep, { type Waiting } from "../k1/UploadStep";
import {
  changeItem, deleteItem, getContext, getSuggestions, listLibrary, putContext, readBase64, uploadItem,
  type LibItem,
} from "./api";

// C4: the one Context box of the four conversation screens. A drop zone with a one-line note; the library items ticked for this
// conversation (only these reach the agent); suggestions from the library (never pre-ticked); all my files and shared files.
// A duplicate or similar file is asked about inline ("Use it" / "Upload anyway"). Page-specific lines come in as children.


const day = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { dateStyle: "medium" });
};
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const KIND = { sample: "sample file", document: "document", external: "external file", picture: "picture" } as const;

export default function ContextBox({ iid, agent, skill, canAdd = true, children }: {
  iid: string; agent: string; skill?: string; canAdd?: boolean; children?: ReactNode;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const [ticked, setTicked] = useState<LibItem[]>([]);
  const [suggested, setSuggested] = useState<LibItem[]>([]);
  const [all, setAll] = useState<LibItem[] | null>(null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [note, setNote] = useState("");
  const [share, setShare] = useState(false);
  const [pending, setPending] = useState<Waiting[]>([]);  // K1: files waiting for their sensitivity and topic
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [unread, setUnread] = useState(false);

  const load = useCallback(async () => {
    if (iid) {
      const [c, s] = await Promise.all([getContext(iid), getSuggestions(iid)]);
      setTicked(c.items ?? []);
      setSuggested(Array.isArray(s) ? s : []);
    }
    if (open) { const got = await listLibrary(q); setAll(Array.isArray(got) ? got : []); }
  }, [iid, open, q]);

  useEffect(() => { load().then(() => setUnread(false), () => setUnread(true)); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try { await fn(); await load(); } catch (err) { setError(plain(err)); } finally { setBusy(false); }
  };
  const setIds = (ids: string[]) => act(() => putContext(iid, ids));
  const tick = (id: string) => setIds([...ticked.map((i) => i.id), id]);
  const untick = (id: string) => setIds(ticked.filter((i) => i.id !== id).map((i) => i.id));

  const send = async (file: File, choice: Choice, force: boolean) =>
    uploadItem({ name: file.name, data: await readBase64(file), note: note.trim() || undefined, share, iid: iid || undefined, force, ...choice });
  const add = (files: File[]) => {
    if (files.length) void act(async () => {
      const rows = await Promise.all(files.map(async (file) => ({ file, data: await readBase64(file) })));
      setPending((p) => [...p, ...rows]);
    });
  };

  const isTicked = (id: string) => ticked.some((i) => i.id === id);
  return (
    <Panel tight title="Context">
      {canAdd ? (
        <div {...dropFiles(add)} style={{ border: "1px dashed currentColor", borderRadius: 8, padding: 12, opacity: 0.9 }}>
          Drop sample files or documents here, or{" "}
          <button type="button" className="ds-btn" disabled={busy} onClick={() => picker.current?.click()}>choose files</button>
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
      {pending.length ? <UploadStep files={pending} note={note.trim() || undefined} send={send} onUse={iid ? tick : undefined}
        onUploaded={() => void load().catch(() => undefined)} onDone={() => { setPending([]); setNote(""); }} /> : null}
      {error ? <p role="alert" style={{ margin: "8px 0 0" }}>{error}</p> : null}
      {unread ? <p className="ds-muted" style={{ margin: "8px 0 0" }}>The library could not be opened just now.</p> : null}

      {iid ? (
        <>
          <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>In this conversation</h3>
          {ticked.length ? (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {ticked.map((i) => (
                <li key={i.id}>{i.name} <span className="ds-muted">({i.note || KIND[i.kind]})</span>{" "}
                  <button type="button" className="ds-link" aria-label={`Untick ${i.name}`} disabled={busy} onClick={() => void untick(i.id)}>untick</button>
                </li>
              ))}
            </ul>
          ) : <p className="ds-muted" style={{ margin: 0 }}>Nothing ticked yet: {agent} reads only the files ticked here.</p>}
          {suggested.length ? (
            <>
              <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>Suggested from the library</h3>
              <p className="ds-muted" style={{ margin: 0 }}>These may be relevant: tick any to use them.</p>
              {suggested.map((i) => (
                <label key={i.id} style={{ display: "block" }}>
                  <input type="checkbox" checked={false} disabled={busy} onChange={() => void tick(i.id)} /> {i.name}
                  {i.note ? <span className="ds-muted"> ({i.note})</span> : null}
                </label>
              ))}
            </>
          ) : null}
        </>
      ) : null}

      <details style={{ marginTop: 12 }} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>All my files and shared files</summary>
        <input aria-label="Search the library" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" style={{ width: "100%", margin: "4px 0" }} />
        {all === null ? <p className="ds-muted">Opening the library…</p> : !all.length ? <p className="ds-muted">No files found.</p> : all.map((i) => i.locked ? (
          <LockedRow key={i.id} item={{ ...i, sensitivity: i.sensitivity ?? "restricted", access: i.access ?? "request" }} iid={iid || undefined} onChange={() => void load()} />
        ) : (
          <div key={i.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "2px 0" }}>
            <label style={{ flex: "1 1 160px" }}>
              <input type="checkbox" checked={isTicked(i.id)} disabled={busy || !iid} aria-label={`Use ${i.name} in this conversation`}
                onChange={() => void (isTicked(i.id) ? untick(i.id) : tick(i.id))} /> {i.name}{" "}
              <span className="ds-muted">({i.mine ? "mine" : i.uploaded_by}{i.note ? `, ${i.note}` : ""})</span>
            </label>
            {i.mine ? (
              <>
                <label style={{ fontSize: 13 }}>
                  <input type="checkbox" role="switch" checked={i.visibility === "company"} disabled={busy} aria-label={`Share ${i.name} with the company`}
                    onChange={(e) => void act(() => changeItem(i.id, { visibility: e.target.checked ? "company" : "private" }))} /> Share with the company
                </label>
                <button type="button" className="ds-link" disabled={busy} onClick={() => void act(() => deleteItem(i.id))}>Delete</button>
              </>
            ) : null}
          </div>
        ))}
      </details>
      {children}
      {skill ? <p className="ds-muted" style={{ margin: "8px 0 0" }}>{skill}</p> : null}
    </Panel>
  );
}
