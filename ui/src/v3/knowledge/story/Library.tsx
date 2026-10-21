import { Link } from "react-router-dom";

const CARDS: [string, string, string][] = [
  ["/v3/knowledge/figures", "Figures", "Every figure the office has defined: where its number comes from, what I assumed, and which use cases use it."],
  ["/v3/knowledge/skills", "Skills Harbor uses", "The focused skills Harbor writes and reuses, and how each one has done."],
  ["/v3/knowledge/signals", "What Harbor watches for", "The signals that raise a card for a person: what they watch, who they go to, and how often they were right."],
];

/** The library: the pages Knowledge already had, one click away. */
export default function Library() {
  return (
    <section className="kl" aria-label="Library">
      <h2>Library</h2>
      <p className="kd-intro">The reference pages behind the stories.</p>
      <div className="kl-cards">
        {CARDS.map(([to, name, text]) => <Link key={to} to={to} className="kl-card"><b>{name}</b><span>{text}</span></Link>)}
      </div>
    </section>
  );
}
