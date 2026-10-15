import type { ReactNode } from "react";

import Panel from "../../components/Panel";

// Small icon button: the drawing is decorative, the label names the action for screen readers and for the hover tip.
function IconButton({ label, d, onClick, pressed }: { label: string; d: string; onClick: () => void; pressed?: boolean }) {
  return (
    <button type="button" className="wb-icon" aria-label={label} title={label} aria-pressed={pressed} onClick={onClick}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        aria-hidden="true" focusable="false"><path d={d} /></svg>
    </button>
  );
}

// L1: one output document in the workbench stack, with enlarge (or restore), pin and close.
export default function DocumentCard({ title, enlarged, collapsed = false, pinned, onCollapse, onEnlarge, onPin, onClose, children }: {
  title: string; enlarged: boolean; collapsed?: boolean; pinned: boolean; onCollapse?: () => void; onEnlarge: () => void; onPin: () => void; onClose: () => void; children: ReactNode;
}) {
  return (
    <Panel
      title={title}
      className={`wb-card${pinned ? " wb-pinned" : ""}`}
      actions={
        <span className="wb-actions">
          {onCollapse ? <IconButton label={`${collapsed ? "Expand" : "Collapse"} ${title}`} pressed={collapsed} onClick={onCollapse}
            d={collapsed ? "M6 9l6 6 6-6" : "M6 15l6-6 6 6"} /> : null}
          <IconButton label={`${pinned ? "Unpin" : "Pin"} ${title}`} pressed={pinned} onClick={onPin}
            d={pinned ? "M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6Zm3 11v7" : "M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6Zm3 11v7M4 4l16 16"} />
          <IconButton label={`${enlarged ? "Restore" : "Enlarge"} ${title}`} onClick={onEnlarge}
            d={enlarged ? "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" : "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"} />
          <IconButton label={`Close ${title}`} onClick={onClose} d="M6 6l12 12M18 6 6 18" />
        </span>
      }
    >
      {collapsed && !enlarged ? null : children}
    </Panel>
  );
}
