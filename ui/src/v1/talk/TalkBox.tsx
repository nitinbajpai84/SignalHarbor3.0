import { useEffect, useRef, useState } from "react";

import { apiSend } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import UsedLine from "../teach/UsedLine";
import type { Used } from "../teach/api";
import { Composer } from "../voice";

interface Turn { id: number; by: "person" | "agent"; text: string; used?: Used[] }

/** Talk to an agent outside any project. Anyone signed in may ask; the answer comes from what they may see. The thread stays on the page for
 * the visit (newest last); the server keeps the short-term conversation, so a follow-up works. Enter sends, Shift+Enter adds a line. */
export default function TalkBox({ agent, path, hint }: { agent: "Span" | "Lumen"; path: string; hint: string }) {
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns, busy]);
  async function send(said: string) {
    setError(""); setText("");
    setTurns((t) => [...t, { id: t.length, by: "person", text: said }]);
    setBusy(true);
    try {
      const got = await apiSend<{ reply: string; used?: Used[] }>("POST", path, { text: said });
      setTurns((t) => [...t, { id: t.length, by: "agent", text: got.reply, used: got.used }]);
    } catch {
      setError(`${agent} could not answer just now. Please try again.`);
    } finally { setBusy(false); }
  }
  return (
    <section aria-label={`Talk to ${agent}`} style={{ margin: "12px 0" }}>
      <h2 style={{ fontSize: 16 }}>Talk to {agent}</h2>
      <div role="log" aria-label={`Conversation with ${agent}`}>
        {turns.map((t) => <MessageBubble key={t.id} from={t.by === "agent" ? "agent" : "human"} who={t.by === "agent" ? agent : "You"} text={t.text}><UsedLine used={t.used} /></MessageBubble>)}
        {busy ? <p className="ds-muted" role="status">{agent} is working…</p> : null}
        <div ref={end} />
      </div>
      <Composer agent={agent} text={text} setText={setText} files={files} setFiles={setFiles} onSend={(said) => void send(said)}
        onEmpty={() => setError("Type a question first.")} busy={busy} error={error} placeholder={hint} />
    </section>
  );
}
