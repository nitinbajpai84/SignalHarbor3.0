import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../../api/client";
import type { LibItem } from "../c4/api";
import LockedRow from "../k1/LockedRow";
import { getFolders, moveItem, type Folders } from "./api";

// L3, shown in the "Saved documents" window: folders with counts on the left, the files of the chosen folder (or of all folders) on the
// right with name, folder, date added and kind, a search across all folders, ticks and an Open link. Nothing is ticked for the person.
// While Jev is still sorting the unclear files the panel says so.
const GLYPH: Record<string, string> = {
  process: "⇄", report: "▤", target: "◎", policy: "§", table: "▦", statement: "❏", capital: "⇅", mail: "✉", minutes: "✎", market: "◈", picture: "▣", other: "…",
};
const KIND: Record<string, string> = { sample: "Sample", document: "Document", external: "External file", picture: "Picture" };
const day = (at: string) => { const d = new Date(at); return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { dateStyle: "medium" }); };

// The Library page uses it without ticks (browse): no onTick, so the name is plain text.
export default function LibraryFolders({ iid, openIn, ticked = [], busy = false, onTick, onUntick, extra }: {
  iid?: string; openIn?: (item: LibItem) => string | undefined; ticked?: string[]; busy?: boolean; onTick?: (id: string) => void; onUntick?: (id: string) => void;
  extra?: (item: LibItem, reload: () => void) => ReactNode;
}) {
  const [q, setQ] = useState("");
  const [data, setData] = useState<Folders | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setData(await getFolders(q)); setError(""); } catch (e) {
      setError(e instanceof ApiError && e.status === 403
        ? "The library is open to the sponsor, the analysts and the company administrator. Ask your company administrator if you need a document from it."
        : "The library could not be opened just now. Close the window and try again.");
    }
  }, [q]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {  // "sorting…" clears by itself when the background batch finishes
    if (!data?.sorting) return;
    const t = setInterval(() => void load(), 3000);
    return () => clearInterval(t);
  }, [data?.sorting, load]);

  const folders = Array.isArray(data?.folders) ? data.folders : [];
  const searching = Boolean(q.trim());
  const items = folders.filter((f) => searching || !open || f.folder === open).flatMap((f) => f.items.map((i) => ({ ...i, folder: i.folder ?? f.folder })));
  const total = folders.reduce((n, f) => n + f.count, 0);

  const row = (i: LibItem) => i.locked ? (
    <li key={i.id} className="l3-row l3-row--locked">
      <LockedRow item={{ ...i, sensitivity: i.sensitivity ?? "restricted", access: i.access ?? "request" }} iid={iid} onChange={() => void load()} />
    </li>
  ) : (
    <li key={i.id} className="l3-row">
      {(() => {
        const notes = i.sorting || i.note || i.visibility === "private" || i.sensitivity === "restricted" ? (
          <span className="ds-muted"> ({[i.sorting && "sorting…", i.note, i.visibility === "private" && "private", i.sensitivity === "restricted" && "restricted"].filter(Boolean).join(", ")})</span>
        ) : null;
        return onTick && onUntick ? (
          <label className="l3-name">
            <input type="checkbox" checked={ticked.includes(i.id)} disabled={!iid} aria-label={`Use ${i.name} in this conversation`}
              onChange={() => (ticked.includes(i.id) ? onUntick(i.id) : onTick(i.id))} /> {i.name}{notes}
          </label>
        ) : <span className="l3-name">{i.name}{notes}</span>;
      })()}
      <span>{i.folder}{i.subfolder ? `, ${i.subfolder}` : ""}</span>
      <span>{day(i.at)}</span>
      <span>{KIND[i.kind] ?? i.kind}</span>
      <span className="l3-acts">
        {(() => {  // INT3: the project to open in is ?iid=, else the one openIn picks (the Library page from the menu)
          const at = iid ?? openIn?.(i);
          // W06: no project fits (the Library page has loaded its places and found none): the project-free read-only viewer
          const href = at ? `/centre/build/${encodeURIComponent(at)}/source?file=${encodeURIComponent(i.path)}` : openIn && !i.locked ? `/centre/library/view?file=${encodeURIComponent(i.path)}` : null;
          return href ? <a className="ds-link" href={href} target="_blank" rel="noopener"
            aria-label={`Open ${i.name} in a new tab`}>Open</a> : null;
        })()}
        {i.can_change && data ? (
          <select aria-label={`Move ${i.name} to another folder`} value={i.folder ?? "Other"} disabled={busy}
            onChange={(e) => void moveItem(i.id, e.target.value).then(load, () => setError("That did not go through. Please try again."))}>
            {data.all.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        ) : null}
        {extra?.(i, () => void load())}
      </span>
    </li>
  );

  return (
    <div className="l3">
      <input type="search" className="l3-search" aria-label="Search the library" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search file names in all folders" />
      {data?.sorting ? <p className="ds-muted" role="status" style={{ margin: 0 }}>sorting…</p> : null}
      {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
      <div className="l3-cols">
        <nav aria-label="Library folders" className="l3-folders">
          <button type="button" className="ds-btn" aria-pressed={!open && !searching} onClick={() => { setOpen(null); setQ(""); }}>
            All folders <span className="ds-muted">{total}</span>
          </button>
          {folders.map((f) => (
            <button key={f.folder} type="button" className="ds-btn" aria-pressed={!searching && open === f.folder}
              aria-label={`${f.folder}, ${f.count} ${f.count === 1 ? "file" : "files"}`} onClick={() => { setOpen(f.folder); setQ(""); }}>
              <span aria-hidden="true">{GLYPH[f.icon] ?? "…"}</span> {f.folder} <span className="ds-muted">{f.count}</span>
            </button>
          ))}
        </nav>
        <section className="l3-files" aria-label={searching ? "Files found" : open ?? "All files"}>
          {data === null && !error ? <p className="ds-muted">Opening the library…</p> : null}
          {data && !items.length ? <p className="ds-muted">{searching ? "No file name matches that search." : "No files in this folder yet."}</p> : null}
          {items.length ? (
            <>
              <div className="l3-row l3-head" aria-hidden="true"><span>Name</span><span>Folder</span><span>Added</span><span>Kind</span><span /></div>
              <ul className="l3-list">{items.map(row)}</ul>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
