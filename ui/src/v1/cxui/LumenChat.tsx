import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import ModeLine from "../router/ModeLine";
import UsedLine from "../teach/UsedLine";
import type { Used } from "../teach/api";

// OP1: Lumen's conversation as one set of pieces. Consume (read-only, questions about what is shown) and the Build studio (where dashboards are made)
// draw the same head, thread and picture box, so Lumen looks and acts the same in both.
export interface Turn { by: "lumen" | "person"; text: string; link?: string | null; used?: Used[] }
export const linkBtn = { background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit", fontSize: 13 } as const;

/** What Lumen remembers about this person (the first four items), re-read when the thread grows. */
export function useRemembered(turns: number): string[] {
  const [known, setKnown] = useState<string[]>([]);
  useEffect(() => {
    apiGet<{ items?: { agent: string; text: string }[] }>("/api/v1/memory/me")
      .then((r) => setKnown((r.items ?? []).filter((i) => i.agent === "lumen").map((i) => i.text.replace(/^Prefers: /, "")).slice(0, 4)), () => setKnown([]));
  }, [turns]);
  return known;
}

export function ChatHead({ busy, known, onFresh }: { busy: boolean; known: string[]; onFresh?: () => void }) {
  return (
    <>
      <p style={{ margin: 0 }}><strong>Lumen</strong> <span className="ds-muted">the consume agent · {busy ? "working" : "waiting for you"}</span></p>
      {known.length ? <p className="ds-muted" style={{ margin: 0 }}>Lumen remembers: {known.join(", ")}. <Link className="ds-link" to="/centre/settings/memory">Change this</Link></p> : null}
      {onFresh ? <button type="button" className="ds-link" style={linkBtn} onClick={onFresh}>Start a fresh talk</button> : null}
      <ModeLine />
    </>
  );
}

export function ChatLog({ intro, turns, busy, children }: { intro: string; turns: Turn[]; busy: boolean; children?: ReactNode }) {
  return (
    <>
      <MessageBubble from="agent" who="Lumen" text={intro} />
      {turns.map((t, i) => (
        <MessageBubble key={i} from={t.by === "lumen" ? "agent" : "human"} who={t.by === "lumen" ? "Lumen" : "You"} text={t.text}>
          <UsedLine used={t.used} />
          {t.link ? <p style={{ margin: "4px 0 0" }}><Link className="ds-link" to={t.link}>Open the dashboard studio</Link></p> : null}
        </MessageBubble>))}
      {children}
      {busy ? <p className="ds-muted" role="status">Lumen is working…</p> : null}
    </>
  );
}

/** "Add a picture": the picture is read on this machine; the tick says it holds no client figures. */
export function PictureBox({ pic, setPic, noFigures, setNoFigures }: { pic: File | null; setPic: (f: File | null) => void; noFigures: boolean; setNoFigures: (b: boolean) => void }) {
  const [show, setShow] = useState(false);
  if (!show) return <button type="button" className="ds-link" style={linkBtn} onClick={() => setShow(true)}>Add a picture</button>;
  return (
    <div>
      <label>Add a picture of the visual you want <input type="file" accept="image/*" onChange={(e) => setPic(e.target.files?.[0] ?? null)} /></label>
      {pic ? <label style={{ display: "block" }}><input type="checkbox" checked={noFigures} onChange={(e) => setNoFigures(e.target.checked)} /> This picture contains no client figures</label> : null}
      {pic && !noFigures ? <p className="ds-muted">Without the tick, only the words read from the picture on this machine are used; the picture itself is not sent.</p> : null}
    </div>
  );
}

export function readBase64(file: File): Promise<string> {
  return new Promise((ok, no) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",").pop() ?? "");
    r.onerror = () => no(r.error);
    r.readAsDataURL(file);
  });
}
