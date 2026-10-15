import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import Icon from "./Icon";
import { shellCopy } from "./shellCopy";

// The earlier companion dock (js/companion.js 296-334 and js/chat-panel.js attachChatPanel), as one React component:
// a pill that opens a panel docked on the right, the panel head with the expand and collapse controls, a scrolling body
// and a footer pinned under it. Under 768 px the legacy CSS turns the panel into a bottom sheet. The page reserves the
// panel's width while it is open, so it never covers what the person is reading.

const KEY = "sh:companion";
const read = (k: string): string | null => {
  try {
    return localStorage.getItem(`${KEY}-${k}`);
  } catch {
    return null;
  }
};
const write = (k: string, v: boolean) => {
  try {
    localStorage.setItem(`${KEY}-${k}`, v ? "1" : "0");
  } catch {
    /* not remembered */
  }
};

/** js/chat-panel.js dockedWidth(): a quarter of the screen, at least 360 and at most 720 px, and always inside the screen. */
export function dockedWidth(viewport: number): number {
  const widest = Math.max(360, Math.min(720, viewport - 32));
  return Math.round(Math.min(widest, Math.max(360, viewport * 0.24)));
}
/** What the page keeps free for the floating (not docked) panel: its 340 px and a margin (css default 372). */
const FLOATING_RESERVE = 372;
export const SMALL_SCREEN = 768;

interface Props {
  /** The panel's own accessible name (a region). */
  label: string;
  /** Which agent this is: "Nira" and "your companion", "Lens" and "the business analyst". One panel serves every agent. */
  name: string;
  role?: string;
  sub?: string;
  /** Controls in the panel head, before the expand button (Voice mode). */
  headExtra?: ReactNode;
  /** Pinned under the scrolling body: the ask box and its notes. */
  footer: ReactNode;
  /** Goes up by one when Nira says something: while collapsed, the pill shows a dot. */
  replies?: number;
  children: ReactNode;
}

export default function AgentPanel({ label, name, role = shellCopy.dock.role, sub = shellCopy.dock.sub, headExtra, footer, replies = 0, children }: Props) {
  // open on a wide screen unless the person closed it; always closed to start with on a phone
  const [expanded, setExpanded] = useState(() => window.innerWidth >= SMALL_SCREEN && read("expanded") !== "0");
  const [large, setLarge] = useState(() => read("large") !== "0"); // docked on the right is how it first appears
  const [width, setWidth] = useState(() => window.innerWidth);
  const [unread, setUnread] = useState(false);
  const panel = useRef<HTMLElement>(null);
  const pill = useRef<HTMLButtonElement>(null);
  const seen = useRef(replies);

  const open = (v: boolean, focus = true) => {
    setExpanded(v);
    write("expanded", v);
    if (v) {
      setUnread(false);
      if (focus) window.setTimeout(() => panel.current?.focus({ preventScroll: true }), 0);
    } else if (focus) pill.current?.focus({ preventScroll: true });
  };
  const dock = (v: boolean) => {
    setLarge(v);
    write("large", v);
  };

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    const onKey = (e: globalThis.KeyboardEvent) => {
      const mod = navigator.platform.includes("Mac") ? e.metaKey : e.ctrlKey;
      if (mod && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setExpanded((v) => {
          write("expanded", !v);
          return !v;
        });
      }
    };
    window.addEventListener("resize", onResize);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", onResize);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  // the page keeps the panel's width free while it is open (legacy: body.n-companion-open .n-main)
  useEffect(() => {
    const root = document.documentElement;
    document.body.classList.toggle("n-companion-open", expanded);
    if (expanded) root.style.setProperty("--n-companion-reserve", `${large ? dockedWidth(width) : FLOATING_RESERVE}px`);
    else root.style.removeProperty("--n-companion-reserve");
  }, [expanded, large, width]);
  useEffect(
    () => () => {
      document.body.classList.remove("n-companion-open");
      document.documentElement.style.removeProperty("--n-companion-reserve");
    },
    [],
  );

  useEffect(() => {
    if (replies > seen.current && !expanded) setUnread(true);
    seen.current = replies;
  }, [replies, expanded]);

  // Escape steps back: first out of the docked reading view, then closed
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape" || !expanded) return;
    if (large) dock(false);
    else open(false);
  };

  const avatar = (
    <div className="n-companion-avatar">
      <img src="/brand/signal-harbor-mark-32-on-dark.png" width={22} height={22} alt="" />
      <span className="n-companion-dot" aria-hidden="true" />
    </div>
  );
  return (
    <div className={`n-companion-dock${expanded ? " expanded" : ""}${large ? " large" : ""}`} role="complementary" aria-label={shellCopy.dock.region(name, role)} onKeyDown={onKeyDown}>
      <section ref={panel} className="n-companion-panel" tabIndex={-1} aria-label={label} hidden={!expanded} style={large && expanded ? { width: dockedWidth(width) } : undefined}>
        <div className="n-companion-panel-head">
          {avatar}
          <div className="n-companion-panel-title">
            <div>{name}</div>
            <div className="n-companion-panel-sub">{sub}</div>
          </div>
          {headExtra}
          <button
            type="button"
            className="n-icon-btn n-companion-expand-btn"
            aria-label={large ? shellCopy.dock.exitExpand : shellCopy.dock.expand(name)}
            aria-pressed={large}
            title={large ? shellCopy.dock.exitExpand : shellCopy.dock.expand(name)}
            onClick={() => dock(!large)}
          >
            ⤢
          </button>
          <button type="button" className="n-icon-btn" aria-label={shellCopy.dock.collapse(name)} title={shellCopy.dock.collapse(name)} onClick={() => open(false)}>
            <Icon name="close" size={13} />
          </button>
        </div>
        <div className="n-companion-scroll">{children}</div>
        <div className="n-companion-footer">{footer}</div>
      </section>
      <button
        ref={pill}
        type="button"
        className={`n-companion-pill${unread ? " has-unread" : ""}`}
        aria-expanded={expanded}
        aria-label={shellCopy.dock.pill(name, role)}
        title={shellCopy.dock.pill(name, role)}
        onClick={() => open(!expanded)}
      >
        {avatar}
        <span className="n-companion-pill-text">{name}</span>
        <span className="n-companion-unread-dot" aria-hidden="true" />
      </button>
    </div>
  );
}
