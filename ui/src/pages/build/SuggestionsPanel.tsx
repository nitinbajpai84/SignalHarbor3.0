import { useState } from "react";

import { Button, EmptyState, Pill } from "../../design";
import { useSession } from "../../useSession";
import { useLoad } from "../BuildCentre";
import "./chain.css";
import { accept, askQuestion, decline, proposalsPath, review, type Proposal, type ProposalList } from "./spanApi";
import { EFFORT, plain, sc } from "./spanCopy";
import { SpanGate, sayWhy } from "./SpanModelPanel";

const KINDS = ["model_change", "architecture_decision"];
const OPEN = ["proposed", "asked"];
const names = (xs?: string[]) => [...new Set((xs ?? []).map(plain).filter(Boolean))].join(", ");

/** One suggestion: what, why, evidence, what it touches, the other options, and who decides. Only the named person sees the buttons. */
function Card({ p, onChange }: { p: Proposal; onChange: (p: Proposal) => void }) {
  const [mode, setMode] = useState<"" | "decline" | "ask">("");
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const run = (go: () => Promise<Proposal>) => {
    go().then((n) => { setErr(""); setMode(""); setText(""); onChange(n); }).catch((e: unknown) => setErr(sayWhy(e)));
  };
  const facts = [...(p.evidence?.counts ?? []).map((c) => `${plain(c.label)}: ${c.value}`), ...(p.evidence?.fields ?? []).map(plain)].filter(Boolean);
  const touches = [names(p.impact?.contracts), names(p.impact?.marts), names(p.impact?.dashboards)].filter(Boolean).join(", ");
  const open = OPEN.includes(p.state);
  return (
    <li className="ds-card bc-row" aria-label={plain(p.title)}>
      <div className="bc-actions" style={{ alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>{plain(p.title)}</h3>
        <Pill tone="draft">{sc.tag}</Pill>
        {p.state === "accepted" ? <Pill tone="ok">{sc.accepted}</Pill> : null}
        {p.state === "declined" ? <Pill tone="failed">{sc.declined}</Pill> : null}
      </div>
      {p.to ? <p className="bc-note">{sc.forWho(p.to, p.to_role)}</p> : null}
      <p><strong>{sc.what}:</strong> {plain(p.what)}</p>
      <p><strong>{sc.why}:</strong> {plain(p.why)}</p>
      {p.technique ? <p className="bc-note">{sc.technique}: {plain(p.technique)}{p.effort ? ` · ${sc.effort}: ${EFFORT[p.effort] ?? p.effort}` : ""}</p> : null}
      {facts.length ? <p className="bc-note">{sc.evidence}: {facts.join(" · ")}</p> : null}
      {touches ? <p className="bc-note">{sc.impact}: {touches}</p> : null}
      {p.alternatives?.length ? (
        <div><strong>{sc.alternatives}</strong>
          <ul className="bc-lines">{p.alternatives.map((a) => <li key={a.option}>{plain(a.option)}: {plain(a.why_not)}</li>)}</ul>
        </div>
      ) : null}
      {p.outside_note ? <p className="bc-note">{p.outside_note}</p> : null}
      {p.thread?.length ? <div><strong>{sc.thread}</strong><ul className="bc-lines">{p.thread.map((t, i) => <li key={i}>{t.by}: {t.text}</li>)}</ul></div> : null}
      {open && p.can_decide ? (
        <>
          <div className="bc-actions">
            <Button variant="primary" onClick={() => run(() => accept(p.id))}>{sc.accept}</Button>
            <Button onClick={() => setMode("decline")}>{sc.decline}</Button>
            <Button onClick={() => setMode("ask")}>{sc.ask}</Button>
          </div>
          {mode ? (
            <div className="bc-field">
              <label>{mode === "decline" ? sc.reasonLabel : sc.questionLabel}
                <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} rows={3} />
              </label>
              <div className="bc-actions">
                <Button variant="primary" disabled={!text.trim()}
                  onClick={() => run(() => (mode === "decline" ? decline(p.id, text.trim()) : askQuestion(p.id, text.trim())))}>{sc.send}</Button>
                <Button onClick={() => { setMode(""); setText(""); }}>{sc.cancel}</Button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
      {open && !p.can_decide && p.to ? <p className="bc-note">{sc.waitingOn(p.to)}</p> : null}
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
    </li>
  );
}

/** Room 1: what Span suggests to the data team. A suggestion is never applied by Span; the named person accepts, declines or asks. */
export default function SuggestionsPanel() {
  const { data, state, retry, setData } = useLoad<ProposalList>(proposalsPath);
  const { user } = useSession();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [fallback, setFallback] = useState("");
  const list = (data?.proposals ?? []).filter((p) => KINDS.includes(p.kind));
  const may = !!user?.roles.some((r) => r === "company_admin" || r === "analyst" || r === "owner");
  const ask = () => {
    setBusy(true);
    review().then((r) => { setFallback(r.fallback ? r.message ?? sc.reviewFallback : ""); setErr(""); retry(); })
      .catch((e: unknown) => setErr(sayWhy(e))).finally(() => setBusy(false));
  };
  const change = (n: Proposal) => setData({ ...data, proposals: (data?.proposals ?? []).map((p) => (p.id === n.id ? n : p)) });
  return (
    <section id="suggestions" aria-label="Span's suggestions">
      <SpanGate state={state} retry={retry} title={sc.sugTitle}>
        <p className="bc-note">{sc.sugLine}</p>
        {!list.length ? <EmptyState title={sc.sugEmpty} lines={[]} /> : null}
        <ul className="bc-rows">{list.map((p) => <Card key={p.id} p={p} onChange={change} />)}</ul>
        {fallback ? <p role="status" className="ds-warn">{fallback}</p> : null}
        {may ? <div className="bc-actions"><Button disabled={busy} onClick={ask}>{sc.review}</Button></div> : null}
        {err ? <p role="alert" className="ds-warn">{err}</p> : null}
      </SpanGate>
    </section>
  );
}
