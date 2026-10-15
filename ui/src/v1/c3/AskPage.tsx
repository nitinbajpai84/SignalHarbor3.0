import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import Panel from "../../components/Panel";
import { Button, PageFrame } from "../../design";
import { getBrief, sendInput, type LumenChat } from "./api";

// C3: /centre/consume/design/:iid/ask. The end users' short version: Lumen's three questions, each answer added to the brief.

const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

export default function AskPage() {
  const { iid = "" } = useParams();
  const [chat, setChat] = useState<LumenChat | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setChat(await getBrief(iid)); setError(""); } catch (err) { setError(plain(err)); }
  }, [iid]);
  useEffect(() => { void load(); }, [load]);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      setChat(await sendInput(iid, text.trim()));
      setText("");
    } catch (err) {
      setError(plain(err));
    } finally {
      setBusy(false);
    }
  }

  const mine = chat?.brief.end_user_inputs.filter((x) => x.by === chat.me) ?? [];
  return (
    <PageFrame title="Your view of the figures" subline={chat?.title ? `For ${chat.title}. Three short questions from Lumen.` : "Three short questions from Lumen."}>
      <Panel label="Questions from Lumen">
        {!chat && !error ? <p className="ds-muted" role="status">Opening…</p> : null}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "12px 0" }} aria-live="polite">
          {mine.map((x, i) => (
            <div key={i}>
              <MessageBubble from="agent" who="Lumen" text={x.question} />
              <MessageBubble from="human" who={x.by} text={x.answer} />
            </div>
          ))}
          {chat?.ask_next ? <MessageBubble from="agent" who="Lumen" text={chat.ask_next} /> : null}
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {chat?.intent_id ? (
          <form onSubmit={send} aria-label="Answer Lumen" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <textarea aria-label="Your answer" rows={2} value={text} onChange={(e) => setText(e.target.value)} style={{ flex: 1, minWidth: 0 }} />
            <Button type="submit" variant="primary" disabled={busy || !text.trim()}>Send</Button>
          </form>
        ) : null}
      </Panel>
    </PageFrame>
  );
}
