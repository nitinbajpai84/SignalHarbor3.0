import { useState } from "react";
import { Link } from "react-router-dom";

import { actSignal, type Receipt, type SignalNeed } from "../api";
import { plainName, roleName } from "../plain";

const SEVERITY: Record<SignalNeed["severity"], string> = { info: "Just so you know", needs: "Needs you", problem: "Something is wrong" };
const BLOCKS: Record<string, string> = { prepare_payment: "payment" };
const show = (v: unknown): string =>
  v && typeof v === "object" ? Object.entries(v).map(([k, x]) => `${plainName(k)} ${String(x)}`).join(", ") : String(v ?? "");

function Evidence({ items }: { items: Receipt[] }) {
  const figs = items.filter((r) => r.kind === "figure");
  const docs = items.filter((r) => r.kind === "document");
  const rules = items.filter((r) => r.kind === "rule");
  return (
    <div className="sg-ev">
      {figs.length > 0 && <section><h4>Figures</h4><ul>{figs.map((r, i) => (
        <li key={i}><Link to={`/v3/knowledge/figures/${encodeURIComponent(r.id ?? "")}`}>{plainName(r.id ?? "")}</Link>{r.v ? <small>version {r.v}</small> : null}<span>{show(r.value)}</span></li>))}</ul></section>}
      {docs.length > 0 && <section><h4>From the document</h4><ul>{docs.map((r, i) => (
        <li key={i}><q>{r.quote || show(r.value)}</q><small>{r.file ? `${r.file}, ` : ""}{r.page ? `page ${r.page}` : plainName(r.field ?? "")}</small></li>))}</ul></section>}
      {rules.length > 0 && <section><h4>The office rule</h4><ul>{rules.map((r, i) => <li key={i}><span>{r.text || show(r.value)}</span></li>)}</ul></section>}
    </div>
  );
}

/** A fired signal on the Action list: what it is, why it is for you, the one thing to do, and the evidence behind it. */
export default function SignalCard({ card, onDone }: { card: SignalNeed; onDone: () => void }) {
  const [more, setMore] = useState(false);
  const [pick, setPick] = useState<string | null>(null); // a held card asks for a note before the action that releases it
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const acts = card.actions.filter((a) => a.answer !== "dismiss");
  const dismiss = card.actions.some((a) => a.answer === "dismiss");

  async function send(body: { choice?: string; note?: string; dismiss?: boolean }) {
    setBusy(true);
    setProblem("");
    try {
      await actSignal(card.id, body);
      onDone();
    } catch (e) {
      setProblem(e instanceof Error && e.message ? e.message : "That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }
  const choose = (answer: string) => (card.hold ? setPick(answer) : void send({ choice: answer }));
  const h = card.hold;

  return (
    <article className={`sg-card ${card.severity}`} aria-label={card.title}>
      <div className="v3-head"><span className="v3-kicker">{SEVERITY[card.severity]}</span></div>
      <b className="act-title">{card.title}</b>
      <p>{card.text}</p>
      <p className="sg-for v3-mute">For you because you are the {roleName(card.role).replace(/^(?![A-Z]{2})./, (c) => c.toLowerCase())}.</p>
      {h && <p className="sg-held" role="status">Held: {BLOCKS[h.blocks] ?? plainName(h.blocks).toLowerCase()}{h.scope ? ` for ${h.scope}` : ""}{h.until ? ` until ${h.until}` : ""}</p>}
      {problem && <p className="v3-err" role="alert">{problem}</p>}
      {pick ? (
        <div className="sg-note">
          <label>Who did you speak to, and when?
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="v3-row">
            <button type="button" className="go" disabled={busy || !note.trim()} onClick={() => void send({ choice: pick, note })}>{pick}</button>
            <button type="button" disabled={busy} onClick={() => setPick(null)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="v3-row">
          {acts.map((a, j) => <button key={a.answer} type="button" className={j === 0 ? "go" : ""} disabled={busy} onClick={() => choose(a.answer)}>{a.label}</button>)}
          {dismiss && <button type="button" disabled={busy} onClick={() => void send({ dismiss: true })}>Not right</button>}
        </div>
      )}
      {card.evidence.length > 0 && (
        <>
          <button type="button" className="sg-toggle" aria-expanded={more} onClick={() => setMore(!more)}>{more ? "Hide the evidence" : "Show the evidence"}</button>
          {more && <Evidence items={card.evidence} />}
        </>
      )}
    </article>
  );
}
