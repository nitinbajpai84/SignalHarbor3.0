import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Chip } from "../../design";
import TrailPanel from "../a5trail/TrailPanel";
import { canTeach } from "../../shell/roles";
import { useSession } from "../../useSession";
import UsedLine from "../teach/UsedLine";
import { MicButton, SpeakButton, combineText } from "../voice";
import { act, askTally, getTally, type Chip as SourceChip, type Tally } from "./api";

// N1: Tally, the data analyst of the Action centre. Read-only: it looks and proposes; the case owner acts.
// A source chip opens "Where is this from?" for a stored fact, or the statement itself; any other chip is a plain label.
const TRAIL_KINDS = new Set(["valuation", "position", "cash", "nav", "metric"]);
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "Tally could not look at this case just now. Please try again.");

function Sources({ chips, open, onOpen }: { chips: SourceChip[]; open: string; onOpen: (c: SourceChip) => void }) {
  if (!chips.length) return null;
  return <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap", marginLeft: 6 }}>
    {chips.map((c) => c.kind === "document" ? <Chip key={`${c.kind}:${c.id}`} href={`/centre/action/evidence/${c.id}`}>{c.label}</Chip>
      : TRAIL_KINDS.has(c.kind) ? <Chip key={`${c.kind}:${c.id}`} tone={open === `${c.kind}:${c.id}` ? "active" : "default"} onClick={() => onOpen(c)}>{c.label}</Chip>
      : <Chip key={`${c.kind}:${c.id}`}>{c.label}</Chip>)}
  </span>;
}

export default function TallyPanel({ caseId, canFile = false, onFiled }: { caseId: string; canFile?: boolean; onFiled?: () => void }) {
  const [filed, setFiled] = useState(false);
  const [t, setT] = useState<Tally | null>(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [asked, setAsked] = useState<{ q: string; a: string; used?: Tally["used"] } | null>(null);
  const { user } = useSession();
  const [trail, setTrail] = useState<SourceChip | null>(null);

  useEffect(() => { setT(null); setError(""); setAsked(null); setFiled(false); let live = true;
    // the rules analysis first (instant), then the model's wording replaces it when it arrives
    getTally(caseId, true).then((q) => { if (live) setT(q); }).catch((e) => { if (live) setError(plain(e)); });
    getTally(caseId).then((full) => { if (live) setT(full); }).catch(() => undefined);
    return () => { live = false; }; }, [caseId]);
  const ask = async () => {
    const q = question.trim();
    if (!q) return;
    setAsking(true); setError("");
    try { const r = await askTally(caseId, q); setAsked({ q, a: r.answer ?? r.summary, used: r.used }); setQuestion(""); } catch (e) { setError(plain(e)); } finally { setAsking(false); }
  };
  const file = async () => {
    setError("");
    try { await act(caseId, "explain"); setFiled(true); onFiled?.(); } catch (e) { setError(plain(e)); }
  };
  const open = trail ? `${trail.kind}:${trail.id}` : "";
  const toggle = (c: SourceChip) => setTrail(trail && `${trail.kind}:${trail.id}` === `${c.kind}:${c.id}` ? null : c);

  return (
    <section aria-label="Tally, the data analyst" className="ds-card" style={{ padding: 16, margin: "12px 0" }}>
      <h2 style={{ marginTop: 0 }}>Tally, the data analyst</h2>
      <p className="ds-muted">Tally looks at the records behind this case and proposes. The case owner acts.</p>
      {error ? <p role="alert">{error}</p> : null}
      {!t && !error ? <p className="ds-muted" role="status">Tally is looking at this case.</p> : null}
      {t ? <>
        <p>{t.summary}</p>
        {t.findings.length ? <><h3>What Tally found</h3>
          <ul aria-label="Findings">{t.findings.map((f, i) => <li key={`${f.key}:${i}`}>{f.text}<Sources chips={f.chips} open={open} onOpen={toggle} /></li>)}</ul></> : null}
        {trail ? <TrailPanel kind={trail.kind} id={trail.id} onClose={() => setTrail(null)} /> : null}
        {t.next_steps.length ? <><h3>What to do next</h3>
          <ul aria-label="Next steps">{t.next_steps.map((s, i) => <li key={i}><strong>{s.who}:</strong> {s.text}</li>)}</ul></> : null}
        {t.proposals?.length ? <><h3>What Tally proposes</h3>
          <ul aria-label="Proposals">{t.proposals.map((p, i) => <li key={i}>
            {p.kind === "next_step" ? <><strong>{p.who}:</strong> {p.text}</> : <>{p.text}{p.note ? ` ${p.note}` : ""}
              {p.item_ref ? <> <Chip>{p.item_ref}</Chip></> : null}{(p.sources ?? []).map((l) => <Chip key={l}>{l}</Chip>)}</>}
          </li>)}</ul>
          {canFile ? <Button variant="primary" disabled={filed} onClick={() => void file()}>{filed ? "Filed on the case" : "File these proposals on the case"}</Button>
            : <p className="ds-muted">Only the case owner can file these.</p>}</> : null}
        {t.missing.length ? <><h3>What is missing</h3><ul aria-label="Missing">{t.missing.map((m, i) => <li key={i}>{m}</li>)}</ul></> : null}
        <p className="ds-muted">{t.worded_by === "model" ? "Worded by Tally from the recorded facts; every figure is copied from the records." : "Worded from the recorded facts by fixed rules; every figure is copied from the records."}</p>
      </> : null}
      <h3>Ask Tally</h3>
      {canTeach(user?.roles, "tally") ? <p style={{ margin: "0 0 8px" }}><Link className="ds-link" to="/centre/settings/teach?agent=tally">Teach Tally</Link></p> : null}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input className="ds-input" aria-label="Ask Tally a question about this case" placeholder="For example: is this timing?" value={question}
          onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void ask(); }} style={{ flex: "1 1 280px" }} />
        <MicButton agent="Tally" disabled={asking} onText={(said) => setQuestion((q) => combineText(q, said))} />
        <Button variant="primary" disabled={!question.trim() || asking} onClick={() => void ask()}>Ask Tally</Button>
      </div>
      {asked ? <div role="status" aria-label="Tally's answer"><p className="ds-muted" style={{ marginBottom: 0 }}>You asked: {asked.q}</p><p style={{ marginTop: 4 }}>{asked.a}</p><UsedLine used={asked.used} /><SpeakButton text={asked.a} /></div> : null}
    </section>
  );
}
