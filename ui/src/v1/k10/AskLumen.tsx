import TalkBox from "../talk/TalkBox";

// Lumen's chat, as it was on every Consume tab, now one card at the foot of the page.
export default function AskLumen({ title = "Ask about what you see", hint = "For example: why did the September total move?" }: { title?: string; hint?: string }) {
  return (
    <section aria-label={title} className="ds-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <p className="ds-muted" style={{ marginTop: 0 }}>Figures, causes, where a number came from.</p>
      <TalkBox agent="Lumen" path="/api/v1/consume/chat" hint={hint} />
    </section>
  );
}
