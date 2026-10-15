import { useCallback, useEffect, useRef, useState, type KeyboardEvent as RKey, type PointerEvent as RPtr, type ReactNode } from "react";

import Panel from "../../components/Panel";
import { useSessionIfAny } from "../../useSession";
import AddContextMenu from "./AddContextMenu";
import ChangeBar, { ChangedLines, type Proposal } from "./ChangeBar";
import DocumentCard from "./DocumentCard";
import "./workbench.css";

// L1: the one layout of the four conversation screens. The chat with the agent on the left (about 60%), the output documents stacked on
// the right (about 40%; collapse, enlarge, pin, close; a Documents menu reopens) with a draggable divider. "Focus on document" swaps the
// widths for reading. On a phone the documents sit above the chat as tabs. The layout and the split are remembered per person per
// screen in this browser; storage is optional.

/** `proposes`: the proposal documents (sow, process_map, design, mapping, brief) whose changes show inside this document. */
export interface Doc { id: string; title: string; render: () => ReactNode; proposes?: string[] }
interface Layout { closed: string[]; collapsed: string[]; enlarged: string | null; pinned: string | null }
const MIN = 40, MAX = 80;  // the chat takes 40 to 80 percent
const clamp = (n: number) => Math.min(MAX, Math.max(MIN, n));

const EMPTY: Layout = { closed: [], collapsed: [], enlarged: null, pinned: null };
const key = (k: string, who: string) => `sh.workbench.${who}.${k}`;
function read(k: string, who: string): Layout {
  try {
    const got = JSON.parse(localStorage.getItem(key(k, who)) ?? "null") as Partial<Layout> | null;
    return got ? { closed: Array.isArray(got.closed) ? got.closed : [], collapsed: Array.isArray(got.collapsed) ? got.collapsed : [], enlarged: got.enlarged ?? null, pinned: got.pinned ?? null } : EMPTY;
  } catch { return EMPTY; }
}

const splitKey = (k: string, who: string) => `${key(k, who)}.split`;
function readSplit(k: string, who: string): number {
  try { const n = Number(localStorage.getItem(splitKey(k, who))); return n ? clamp(n) : 60; } catch { return 60; }
}

export default function Workbench({ layoutKey, documents, agent, iid, canAdd = true, chatHead, chatLog, composer, proposals, onAccept, onReject, changeError, changeBusy }: {
  /** Names this screen's remembered layout, e.g. "north". */
  layoutKey: string;
  documents: Doc[];
  agent: string;
  /** The conversation's id for the context chips and the library ticks; empty before the conversation exists. */
  iid: string;
  canAdd?: boolean;
  chatHead?: ReactNode;
  chatLog: ReactNode;
  composer: ReactNode;
  proposals?: Proposal[];
  onAccept?: (id: string) => void;
  onReject?: (id: string, reason?: string) => void;
  changeError?: string;
  changeBusy?: boolean;
}) {
  const who = useSessionIfAny()?.user?.account_id ?? "guest";
  const [layout, setLayout] = useState<Layout>(() => read(layoutKey, who));
  const [menu, setMenu] = useState(false);
  const [split, setSplit] = useState(() => readSplit(layoutKey, who));  // the chat's percent of the width
  const [focus, setFocus] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const saveSplit = (n: number) => { try { localStorage.setItem(splitKey(layoutKey, who), String(n)); } catch { /* not remembered */ } };
  const chatPct = focus ? MIN : split;
  const drag = (e: RPtr) => {
    const box = wrap.current?.getBoundingClientRect();
    if (!box?.width) return;
    e.preventDefault();
    let last = chatPct;
    const move = (m: PointerEvent) => { last = Math.round(clamp(((m.clientX - box.left) / box.width) * 100)); setSplit(last); setFocus(false); };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); saveSplit(last); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const nudge = (e: RKey) => {
    const d = e.key === "ArrowLeft" ? -5 : e.key === "ArrowRight" ? 5 : 0;
    if (d) { e.preventDefault(); const n = clamp(chatPct + d); setSplit(n); setFocus(false); saveSplit(n); }
  };
  const [phone, setPhone] = useState(documents[0]?.id ?? "");
  const change = useCallback((next: Layout) => {
    setLayout(next);
    try { localStorage.setItem(key(layoutKey, who), JSON.stringify(next)); } catch { /* the layout just is not remembered */ }
  }, [layoutKey, who]);

  useEffect(() => {
    if (!layout.enlarged) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") change({ ...layout, enlarged: null }); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [layout, change]);

  const strip = useRef<HTMLDivElement>(null);
  useEffect(() => {  // L2: text already in a document that a proposal changes or removes is marked until the person decides
    const root = strip.current;
    if (!root || !proposals?.length) return;
    const marked: Element[] = [];
    const lines = proposals.flatMap((p) => p.changes).filter((c) => c.op !== "add" && c.before.length >= 4);
    root.querySelectorAll("p,li,td,dd,span,div").forEach((el) => {
      if (el.closest(".wb-lines") || el.children.length > 0) return;
      const t = el.textContent ?? "";
      const c = lines.find((l) => t.includes(l.before));
      if (c) { el.classList.add(c.op === "remove" ? "wb-hl-removed" : "wb-hl-changed"); marked.push(el); }
    });
    return () => marked.forEach((el) => el.classList.remove("wb-hl-removed", "wb-hl-changed"));
  }, [proposals, documents, layout]);

  const known = new Set(documents.map((d) => d.id));
  const shown = documents.filter((d) => !layout.closed.includes(d.id))
    .sort((a, b) => Number(b.id === layout.pinned) - Number(a.id === layout.pinned));
  const big = layout.enlarged && known.has(layout.enlarged) && shown.some((d) => d.id === layout.enlarged) ? layout.enlarged : null;
  const active = shown.some((d) => d.id === phone) ? phone : shown[0]?.id;
  const toggle = (id: string) => change({ ...layout, closed: layout.closed.includes(id) ? layout.closed.filter((x) => x !== id) : [...layout.closed, id] });

  return (
    <div className="wb" ref={wrap}>
      <div className="wb-chatcol" style={{ flexGrow: chatPct, flexShrink: 1, flexBasis: 0 }}>
      <Panel label={`Conversation with ${agent}`} className="wb-chat">
        {chatHead}
        <div className="wb-log" aria-live="polite">{chatLog}</div>
        {composer}
        <AddContextMenu iid={iid} agent={agent} canAdd={canAdd} />
      </Panel>
      </div>
      <div className="wb-divider" role="separator" aria-orientation="vertical" aria-label="Resize chat and documents" tabIndex={0}
        aria-valuemin={MIN} aria-valuemax={MAX} aria-valuenow={chatPct} onPointerDown={drag} onKeyDown={nudge} />
      <section className="wb-docs" aria-label="Documents" style={{ flexGrow: 100 - chatPct, flexShrink: 1, flexBasis: 0 }}>
        <div className="wb-docs-head">
          <h2 className="wb-docs-title">Documents</h2>
          <button type="button" className="ds-btn" aria-pressed={focus} onClick={() => setFocus(!focus)}>
            {focus ? "Back to chat" : "Focus on document"}
          </button>
          <div className="wb-menu-wrap">
            <button type="button" className="ds-btn" aria-expanded={menu} onClick={() => setMenu(!menu)}>
              Documents menu ({shown.length} of {documents.length} open)
            </button>
            {menu ? (
              <div className="wb-popover" role="group" aria-label="Documents menu">
                {documents.map((d) => (
                  <label key={d.id}>
                    <input type="checkbox" checked={!layout.closed.includes(d.id)} onChange={() => toggle(d.id)} /> {d.title}
                  </label>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        <div className="wb-phonetabs">
          {shown.map((d) => (
            <button key={d.id} type="button" className={`ds-chip${d.id === active ? " ds-chip--active" : ""}`} aria-pressed={d.id === active}
              aria-label={`Show ${d.title}`} onClick={() => setPhone(d.id)}>{d.title}</button>
          ))}
        </div>
        <ChangeBar proposals={proposals} onAccept={onAccept} onReject={onReject} error={changeError} busy={changeBusy} />
        {shown.length ? (
          <div className="wb-strip" ref={strip}>
            {shown.map((d) => d.id !== (big ?? d.id) ? (
              <button key={d.id} type="button" className="wb-thin" aria-label={`Open ${d.title}`} onClick={() => change({ ...layout, enlarged: d.id })}>{d.title}</button>
            ) : (
              <div key={d.id} className={`wb-doc${big ? " wb-big" : ""}`} data-active={d.id === active}>
                <DocumentCard title={d.title} enlarged={big === d.id} collapsed={layout.collapsed.includes(d.id)} pinned={layout.pinned === d.id}
                  onCollapse={() => change({ ...layout, collapsed: layout.collapsed.includes(d.id) ? layout.collapsed.filter((x) => x !== d.id) : [...layout.collapsed, d.id] })}
                  onEnlarge={() => change({ ...layout, enlarged: big === d.id ? null : d.id })}
                  onPin={() => change({ ...layout, pinned: layout.pinned === d.id ? null : d.id })}
                  onClose={() => change({ ...layout, closed: [...layout.closed, d.id], enlarged: layout.enlarged === d.id ? null : layout.enlarged })}>
                  <ChangedLines changes={(proposals ?? []).filter((p) => d.proposes?.includes(p.document)).flatMap((p) => p.changes)} />
                  {d.render()}
                </DocumentCard>
              </div>
            ))}
          </div>
        ) : <p className="ds-muted">Every document is closed. Open one from the Documents menu.</p>}
      </section>
    </div>
  );
}
