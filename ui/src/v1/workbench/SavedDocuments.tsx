import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import type { LibItem } from "../c4/api";
import LibraryFolders from "../l3/LibraryFolders";

// UX2: "Add context" › "Saved documents" opens its own window over the page (full screen on a phone). Ticks are held here until
// "Use N files in the conversation"; Cancel or Escape leaves the conversation as it was. Focus stays inside and returns to the opener.
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function SavedDocuments({ iid, current, busy, error, onUse, onClose, extra }: {
  iid?: string; current: string[]; busy: boolean; error?: string; onUse: (ids: string[]) => void; onClose: () => void;
  extra?: (item: LibItem, reload: () => void) => ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [chosen, setChosen] = useState<string[]>(current);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    box.current?.querySelector<HTMLElement>("input")?.focus();
    return () => { document.body.style.overflow = overflow; opener?.focus?.(); };
  }, []);

  const keys = (e: KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !box.current) return;
    const all = Array.from(box.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = all[0], last = all[all.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };

  const n = chosen.length;
  return createPortal(
    <div className="wb-docs-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={box} role="dialog" aria-modal="true" aria-labelledby="wb-docs-title" className="ds-card wb-docs-win" onKeyDown={keys}>
        <h2 id="wb-docs-title">Saved documents</h2>
        {!iid ? <p className="ds-muted" style={{ margin: 0 }}>Files can be chosen once the conversation has started.</p> : null}
        <div className="wb-docs-body">
          <LibraryFolders iid={iid} ticked={chosen} busy={busy} extra={extra}
            onTick={(id) => setChosen((c) => [...c, id])} onUntick={(id) => setChosen((c) => c.filter((x) => x !== id))} />
        </div>
        <footer className="wb-docs-foot">
          <a className="ds-link" href={iid ? `/centre/library?iid=${encodeURIComponent(iid)}` : "/centre/library"} target="_blank" rel="noopener">Open the library in a new tab</a>
          {error ? <p role="alert" style={{ margin: 0, marginRight: "auto" }}>{error}</p> : null}
          <button type="button" className="ds-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ds-btn ds-btn--primary" disabled={busy || !iid} onClick={() => onUse(chosen)}>
            Use {n} {n === 1 ? "file" : "files"} in the conversation
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
