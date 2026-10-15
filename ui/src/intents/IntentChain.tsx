import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiGet, ApiError } from "../api/client";
import ScreenState from "../components/ScreenState";
import { Button, PageFrame, Pill } from "../design";
import { chainCopy as t, typeName } from "./pastCopy";
import TurnInto from "./TurnInto";
import "./past.css";

/** The chain (/centre/intent/past/:intentId/chain, spec 20 Screen C and 12 Screen D), read from GET /api/intents/{id}/chain.
 * Cards copy the ds-trail look of the node page; unseen steps are not drawn and only counted. */

export interface ChainStep {
  id: string; type: string; title: string; state: string; date: string | null; organiser: string | null; dir: "from" | "self" | "to";
  parent: string | null; tier: string; cancel_reason: string | null; outcome_line: string;
  link: { kind: string; by: string | null; at: string | null; proposed_by: string | null; item: { kind: string; id: string } | null; private_item: boolean } | null;
}
export interface ChainDoc {
  chain: ChainStep[]; hidden: number; build: { ref: string; at: string | null; by: string | null; blueprint: string | null } | null; branches: number; capped: boolean;
  may_link?: boolean; me?: string;
}

/** One plain sentence from the link entries (the GraphPage trail() join of short clauses, reshaped for a chain). */
export function chainSentence(doc: ChainDoc): string {
  const parts = doc.chain.filter((s) => s.type !== "backlog").map((s) => t.step(s.type, s.title, s.date));
  if (doc.build) parts.push(`was handed to Build${doc.build.at ? ` on ${new Date(doc.build.at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : ""}`);
  return parts.length > 1 ? t.sentence(parts) : t.noLinks;
}

const stateTone = (s: string) => (s === "cancelled" ? "late" : s === "closed" ? "signed" : s === "draft" ? "draft" : "open");
const stateWord = (s: string) => ({ in_session: "in session" } as Record<string, string>)[s] ?? s;

function Card({ s, here }: { s: ChainStep; here: boolean }) {
  const backlog = s.type === "backlog";
  const href = backlog ? `/centre/intent/backlog?item=${s.id}` : `/centre/intent/${s.id}`;
  const when = s.state === "cancelled" ? t.cancelledBy(s.date) : s.state === "closed" ? t.closedOn(s.date) : !backlog && s.date ? t.due(s.date) : "";
  return (
    <Link to={href} aria-current={here ? "page" : undefined}
      className={`ds-trail__step ds-trail__step--link${here ? " pi-step--here" : ""}${s.state === "cancelled" ? " pi-step--cancelled" : ""}`}>
      <span className="ds-trail__cap">{backlog ? t.backlogState(s.state) : typeName[s.type] ?? s.type}{here ? ` · ${t.here}` : ""}</span>
      <strong>{s.title}</strong>
      <span className="pi-row">{backlog ? null : <Pill tone={stateTone(s.state)}>{stateWord(s.state)}</Pill>}<span className="ds-trail__detail">{when}</span></span>
      {s.organiser ? <span className="ds-trail__detail">{s.organiser}</span> : null}
      {s.cancel_reason ? <span className="ds-trail__detail">{s.cancel_reason}</span> : null}
      {s.outcome_line ? <span className="ds-trail__detail">{s.outcome_line}</span> : null}
      {s.link?.private_item ? <span className="ds-trail__detail">{t.privateItem}</span> : s.link?.item ? <span className="ds-trail__detail">{t.fromItem(s.link.item.kind)}</span> : null}
    </Link>
  );
}

/** The line of cards: earliest first, the viewed intent outlined, a "led to" label between cards. */
export function Chain({ doc }: { doc: ChainDoc }) {
  const before = doc.chain.filter((s) => s.dir === "from");
  const after = doc.chain.filter((s) => s.dir === "to");
  const arrow = (s: ChainStep) => <span className="pi-chain__arrow" aria-hidden>{s.link ? t.ledToLabel(s.link.by, s.link.at, s.link.proposed_by === "north") : "led to"}</span>;
  return (
    <div className="pi-stack">
      {before.length ? <span className="pi-dir">{t.cameFrom}</span> : null}
      <div className="pi-chain" role="list" aria-label={t.title}>
        {doc.chain.map((s, i) => (
          <span key={s.id} style={{ display: "contents" }}>
            {i > 0 ? arrow(s) : null}
            <span role="listitem" style={{ display: "contents" }}><Card s={s} here={s.dir === "self"} /></span>
          </span>
        ))}
        {doc.build ? (
          <>
            <span className="pi-chain__arrow" aria-hidden>{t.handed(doc.build.by, doc.build.at)}</span>
            <div className="ds-trail__step"><span className="ds-trail__cap">{t.build}</span><strong>{doc.build.blueprint ?? t.waitingBuild}</strong>
              <span className="ds-trail__detail">{t.release}</span></div>
          </>
        ) : null}
      </div>
      {after.length ? <span className="pi-dir">{t.ledTo}{doc.branches > 1 ? ` · ${t.branches(doc.branches)}` : ""}</span> : null}
      {doc.hidden ? <span className="ds-muted">{t.hidden(doc.hidden)}</span> : null}
    </div>
  );
}

export default function IntentChain() {
  const { intentId = "" } = useParams();
  const [doc, setDoc] = useState<ChainDoc | "failed" | "missing" | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let live = true;
    apiGet<ChainDoc>(`/api/intents/${encodeURIComponent(intentId)}/chain`)
      .then((d) => live && setDoc(d), (e) => live && setDoc(e instanceof ApiError && e.status === 404 ? "missing" : "failed"));
    return () => { live = false; };
  }, [intentId]);
  const back = <Link className="ds-link" to={`/centre/intent/${intentId}`}>{t.back}</Link>;
  if (doc === null) return <PageFrame title={t.title} crumbs={back}><ScreenState state="loading" /></PageFrame>;
  if (doc === "missing") return <PageFrame title={t.title} crumbs={back}><ScreenState state="empty" message={t.notFound} /></PageFrame>;
  if (doc === "failed") return <PageFrame title={t.title} crumbs={back}><ScreenState state="error" message={t.loadError} /></PageFrame>;
  const lonely = doc.chain.length === 1 && !doc.build && !doc.hidden;
  const copy = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setCopied(true); } catch { setCopied(false); }
  };
  return (
    <PageFrame title={t.title} subline={chainSentence(doc)} crumbs={back}
      actions={<span className="pi-row">{doc.may_link ? <TurnInto intentId={intentId} me={doc.me ?? ""} /> : null}
        <Button onClick={() => void copy()}>{copied ? t.copied : t.copy}</Button></span>}>
      <div className="pi-stack">
        {lonely ? <div className="ds-card ds-empty"><p>{t.empty}</p></div> : <Chain doc={doc} />}
        <section className="ds-card pi-stack" style={{ padding: 14 }} aria-label={t.map}>
          <h2 className="pi-band" style={{ cursor: "default" }}>{t.map}</h2>
          <p className="ds-muted" style={{ margin: 0 }}>{t.mapEmpty}</p>
          <div className="pi-chips">
            {doc.chain.filter((s) => s.type !== "backlog" && s.state !== "draft").map((s) => (
              <Link key={s.id} className="ds-chip" to={`/centre/intent/map/intent:${s.id}`}>{s.title}</Link>
            ))}
          </div>
        </section>
      </div>
    </PageFrame>
  );
}
