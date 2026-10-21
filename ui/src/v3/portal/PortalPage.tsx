import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { askPortal, decideApproval, getPortal, type Approval, type Portal, type ShareLine } from "../portalApi";
import "./portal.css";

const num = (v: string | null | undefined, cur: string) => (v == null ? "Not available yet" : `${cur} ${Math.round(Number(v)).toLocaleString("en-US")}`);
const pct = (v: string | null) => (v == null ? "" : `${Number(v).toFixed(1)}%`);
const when = (at: string) => { const d = new Date(at); return Number.isNaN(d.getTime()) ? at : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); };

function Entity({ l, cur }: { l: ShareLine; cur: string }) {
  return (
    <article className="v3-card v3p-ent" aria-label={l.entity}>
      <header>
        <b>{l.entity}</b>
        <span className={`v3-pill ${l.level === "full" ? "done" : "info"}`}>{l.level === "full" ? "Full view" : "Summary"}</span>
      </header>
      {l.your_pct != null
        ? <p>Your {pct(l.your_pct)} is <span className="num">{num(l.your_value, cur)}</span> <small className="v3-mute">of {num(l.value, cur)}</small></p>
        : <p><span className="num">{num(l.value, cur)}</span> <small className="v3-mute">whole entity</small></p>}
      {l.via.length > 0 && <small className="v3-mute">Through {(l.via[0] ?? "").split(" > ").join(" → ")}</small>}
      {l.portfolios && l.portfolios.length > 0 && (
        <details><summary>Portfolios</summary>
          <table><tbody>{l.portfolios.map((p) => <tr key={p.name}><td>{p.name}</td><td className="n">{num(p.value, cur)}</td></tr>)}</tbody></table>
        </details>
      )}
    </article>
  );
}

function ApprovalCard({ a, canDecide, done }: { a: Approval; canDecide: boolean; done: (a: Approval) => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = (approve: boolean) => {
    setBusy(true);
    setErr("");
    decideApproval(a.id, approve).then(done, (e: unknown) => { setErr(e instanceof Error && e.message ? e.message : "I could not save that. Please try again."); setBusy(false); });
  };
  return (
    <article className={`v3-card v3p-ap ${a.status}`} aria-label={a.title}>
      <b>{a.title}</b>
      {a.detail && <p className="v3-mute">{a.detail}</p>}
      {a.amount && <p className="num">{num(a.amount, a.currency)}</p>}
      <small className="v3-mute">Asked by {a.raised_by}, {when(a.raised)}</small>
      {a.status === "pending" && canDecide ? (
        <div className="v3-row">
          <button type="button" className="go" disabled={busy} onClick={() => go(true)}>Approve</button>
          <button type="button" disabled={busy} onClick={() => go(false)}>Decline</button>
        </div>
      ) : <span className={`v3-pill ${a.status === "approved" ? "done" : a.status === "declined" ? "info" : "needs"}`}>{a.status === "pending" ? "Waiting for you" : a.status === "approved" ? "Approved" : "Declined"}</span>}
      {err && <p className="v3-err" role="alert">{err}</p>}
    </article>
  );
}

function AskCard({ member }: { member?: string }) {
  const [q, setQ] = useState("");
  const [a, setA] = useState<{ q: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = q.trim();
    if (!text) return;
    setBusy(true);
    setErr("");
    askPortal(text, member).then((r) => { setA({ q: text, text: r.answer }); setBusy(false); }, (x: unknown) => { setErr(x instanceof Error && x.message ? x.message : "I could not answer that just now."); setBusy(false); });
  };
  return (
    <section aria-labelledby="p-ask">
      <h2 id="p-ask">Ask about your own share</h2>
      <form className="v3p-ask" onSubmit={submit}>
        <label className="v3b-sr" htmlFor="p-q">Your question</label>
        <input id="p-q" type="text" value={q} placeholder="What is my share worth?" onChange={(e) => setQ(e.target.value)} />
        <button type="submit" className="go" disabled={busy || !q.trim()}>Ask</button>
      </form>
      {busy && <Waiting what="Looking…" />}
      {err && <p className="v3-err" role="alert">{err}</p>}
      {a && <article className="v3-card" aria-label="Answer"><small className="v3-mute">{a.q}</small><p className="v3p-answer">{a.text}</p></article>}
      <p className="v3-mute">I answer only from your own share, documents and approvals.</p>
    </section>
  );
}

export default function PortalPage() {
  const [params] = useSearchParams();
  const preview = params.get("member") || undefined; // the company admin's look at a member's portal; a member's own address has none
  const [got, again] = useRead(() => getPortal(preview));
  const [decided, setDecided] = useState<Record<string, Approval>>({});
  return (
    <V3Frame>
      <main className="v3p" id="portal">
        {got.state === "loading" ? <Waiting what="Opening your portal…" />
          : got.state === "error" ? <Failed message={got.message} again={again} />
          : <PortalBody p={got.data} preview={preview} decided={decided} onDecided={(a) => setDecided((d) => ({ ...d, [a.id]: a }))} />}
      </main>
    </V3Frame>
  );
}

function PortalBody({ p, preview, decided, onDecided }: { p: Portal; preview?: string; decided: Record<string, Approval>; onDecided: (a: Approval) => void }) {
  const { share } = p;
  const approvals = p.approvals.map((a) => decided[a.id] ?? a);
  const waiting = approvals.filter((a) => a.status === "pending");
  return (
    <>
      <div className="v3p-head">
        <h1>{preview ? `${p.member}'s portal` : `Hello, ${p.member.split(" ")[0]}`}</h1>
        <span className="v3-mute">{preview ? "Preview for the office. Read only." : "Read only"} · as at {when(share.as_of)}</span>
      </div>
      <div className="v3p-grid">
        <div className="v3p-col">
          <section className="v3-note v3p-note" aria-labelledby="p-note">
            <h2 id="p-note">Your morning note</h2>
            {p.note.lines.map((l, i) => <p key={i} className={i === 0 ? "" : "v3-mute"}>{l}</p>)}
          </section>
          <section aria-labelledby="p-share">
            <h2 id="p-share">My share</h2>
            <span className={`v3-pill ${share.basis === "lookthrough" ? "done" : "info"}`}>{share.basis === "lookthrough" ? "Follows the ownership chain" : "Entity level view"}</span>
            {share.total != null && <div className="v3-card v3p-total"><span className="v3-label">Your share in all</span><span className="num">{num(share.total, share.currency)}</span></div>}
            {share.lines.map((l) => <Entity key={l.code} l={l} cur={share.currency} />)}
            <p className="v3-mute">{share.note}</p>
          </section>
        </div>
        <div className="v3p-col">
          <section aria-labelledby="p-appr" id="approvals">
            <h2 id="p-appr">Approvals {waiting.length > 0 && <span className="v3-pill needs">{waiting.length} waiting</span>}</h2>
            {approvals.length ? approvals.map((a) => <ApprovalCard key={a.id} a={a} canDecide={!preview} done={onDecided} />) : <p className="v3-mute">Nothing needs your approval.</p>}
          </section>
          <section aria-labelledby="p-docs">
            <h2 id="p-docs">Your documents</h2>
            {p.documents.length
              ? <ul className="v3p-docs">{p.documents.map((d) => <li key={d.id}><span>{d.title}<br /><small>{d.kind}</small></span><small>{when(d.date)}</small></li>)}</ul>
              : <p className="v3-mute">No documents are filed for you yet.</p>}
          </section>
          <AskCard member={preview} />
        </div>
      </div>
    </>
  );
}
