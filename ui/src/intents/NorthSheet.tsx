import { useEffect, useRef, type ReactNode } from "react";

import "./phone.css";

/**
 * North as a bottom sheet on phone. The button goes in the bottom bar: it opens the sheet and, relabelled, closes it. The page behind
 * stops scrolling, a swipe down closes the sheet, focus returns to the button. `children` is the host's NorthPanel.
 * The sheet never opens by itself; `waiting` only puts a dot on the button.
 */
export default function NorthSheet({ open, onOpenChange, children, waiting = false, label = "Talk to North", closeLabel = "Close North", panelLabel = "North, your conversation" }: {
  open: boolean; onOpenChange: (open: boolean) => void; children: ReactNode; waiting?: boolean; label?: string; closeLabel?: string; panelLabel?: string;
}) {
  const button = useRef<HTMLButtonElement>(null);
  const was = useRef(open);
  const startY = useRef<number | null>(null);
  const sheet = useRef<HTMLElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (open) closeBtn.current?.focus(); }, [open]);
  // Escape closes; Tab stays inside the sheet (Close North is its first control)
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); onOpenChange(false); return; }
    if (e.key !== "Tab" || !sheet.current) return;
    const f = Array.from(sheet.current.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'));
    const first = f[0], last = f[f.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  useEffect(() => {
    document.body.classList.toggle("ic-noscroll", open);
    if (was.current && !open) button.current?.focus();
    was.current = open;
    return () => document.body.classList.remove("ic-noscroll");
  }, [open]);
  return (
    <>
      <button ref={button} type="button" className="ds-btn" aria-expanded={open} aria-haspopup="dialog" tabIndex={open ? -1 : undefined} onClick={() => onOpenChange(!open)}>
        {open ? closeLabel : label}
        {waiting && !open ? <span className="ic-bar__dot" aria-hidden="true" /> : null}
      </button>
      {open ? (
        <aside
          ref={sheet}
          role="dialog"
          aria-modal="true"
          aria-label={panelLabel}
          className="ic-sheet"
          onKeyDown={onKey}
          onTouchStart={(e) => { startY.current = e.touches[0]?.clientY ?? null; }}
          onTouchEnd={(e) => {
            const y = e.changedTouches[0]?.clientY;
            if (startY.current !== null && y !== undefined && y - startY.current > 60 && e.currentTarget.scrollTop === 0) onOpenChange(false);
            startY.current = null;
          }}
        >
          <span className="ic-sheet__handle" aria-hidden="true" />
          <button ref={closeBtn} type="button" className="ds-btn ic-sheet__close" onClick={() => onOpenChange(false)}>{closeLabel}</button>
          {children}
        </aside>
      ) : null}
    </>
  );
}
