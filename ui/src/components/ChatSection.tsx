import { useState, type ReactNode } from "react";

/** Open or closed is remembered per section, in this browser only. A browser that blocks storage just forgets it. */
const keyOf = (id: string) => `sh:companion-section-${id}`;
function remembered(id: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(keyOf(id));
    return v === null ? fallback : v === "1";
  } catch {
    return fallback;
  }
}

interface Props {
  id: string;
  label: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

/**
 * The earlier companion's chatSection() (js/chat-panel.js 303-326): a compact collapsible for secondary information, so
 * the conversation keeps the bulk of the panel. Same classes (n-chat-section, -toggle, -body) and the same remembered state.
 */
export default function ChatSection({ id, label, defaultOpen = false, children }: Props) {
  const [open, setOpen] = useState(() => remembered(id, defaultOpen));
  const bodyId = `chat-section-${id}`;
  const toggle = () => {
    const next = !open;
    setOpen(next);
    try {
      localStorage.setItem(keyOf(id), next ? "1" : "0");
    } catch {
      /* the choice just is not remembered */
    }
  };
  return (
    <div className="n-chat-section">
      <button type="button" className={`n-chat-section-toggle${open ? " open" : ""}`} aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
        <span className="n-chat-section-label">{label}</span>
      </button>
      <div id={bodyId} className={`n-chat-section-body${open ? " open" : ""}`}>
        {children}
      </div>
    </div>
  );
}
